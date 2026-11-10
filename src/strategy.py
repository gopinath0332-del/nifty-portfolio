"""
src/strategy.py
===============
Core strategy engine for 20-Day Donchian Breakout + 52-Week High Filter.
Performs:
  1. Exit evaluation on active portfolio positions.
  2. Nifty 500 breakout scan.
  3. 52-Week High trend filtering (within 15%).
  4. Breakout% * RVOL tie-breaking ranking.
  5. Selection of Top N candidates to fill available portfolio slots.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config import AppConfig
from src.indicators import compute_indicators, evaluate_breakout_and_exit
from src.market_data import MarketDataFetcher
from src.portfolio import PortfolioManager
from src.universe import StockInfo

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    symbol: str
    company_name: str
    close_price: float
    entry_price: float
    quantity: int
    low_20_level: float
    exit_reason: str
    pnl: float
    pnl_pct: float


@dataclass
class EntryCandidate:
    symbol: str
    company_name: str
    industry: str
    close_price: float
    suggested_qty: int
    investment_amount: float
    high_20_level: float
    breakout_pct: float
    rvol: float
    high_52w: float
    dist_52w_pct: float
    composite_score: float
    rank: int = 0


@dataclass
class ScanResult:
    scan_date: str
    open_slots_before: int
    open_slots_after: int
    exits: List[ExitSignal] = field(default_factory=list)
    recommended_entries: List[EntryCandidate] = field(default_factory=list)
    runner_ups: List[EntryCandidate] = field(default_factory=list)
    total_scanned: int = 0
    total_breakouts_found: int = 0


class StrategyEngine:
    """Executes the daily strategy scan and candidate ranking."""

    def __init__(
        self,
        config: AppConfig,
        portfolio: PortfolioManager,
        fetcher: MarketDataFetcher,
    ):
        self.config = config
        self.portfolio = portfolio
        self.fetcher = fetcher

    def run_daily_scan(
        self,
        universe: List[StockInfo],
        use_cache: bool = True,
        max_stocks_to_scan: Optional[int] = None,
    ) -> ScanResult:
        """
        Run the complete daily scan:
        1. Check exits on active positions.
        2. Scan universe for new breakout entries.
        3. Rank by Breakout% * RVOL and select top N candidates.
        """
        scan_date = datetime.now().strftime("%Y-%m-%d")
        initial_open_slots = self.portfolio.open_slots
        logger.info(
            "Starting Daily Strategy Scan [%s] | Active: %d | Open Slots: %d",
            scan_date,
            len(self.portfolio.positions),
            initial_open_slots,
        )

        exits: List[ExitSignal] = []
        breakout_candidates: List[EntryCandidate] = []
        scanned_count = 0

        stocks_to_scan = universe[:max_stocks_to_scan] if max_stocks_to_scan else universe

        # Map symbol -> StockInfo for quick metadata lookup
        stock_map = {s.symbol: s for s in stocks_to_scan}

        # ------------------------------------------------------------------
        # Phase 1: Check Exits on Active Portfolio Positions
        # ------------------------------------------------------------------
        for sym, pos in list(self.portfolio.positions.items()):
            stock_info = stock_map.get(sym) or StockInfo(symbol=sym, company_name=sym, industry="")
            inst_token = stock_info.instrument_token
            if not inst_token:
                logger.warning("No instrument token for active position %s. Skipping exit check.", sym)
                continue

            df = self.fetcher.fetch_daily_candles(
                instrument_token=inst_token,
                symbol=sym,
                days=365,
                use_cache=use_cache,
            )
            if df is None or len(df) < 25:
                continue

            df_ind = compute_indicators(
                df,
                entry_len=self.config.strategy.entry_len,
                exit_len=self.config.strategy.exit_len,
            )
            eval_res = evaluate_breakout_and_exit(
                df_ind,
                entry_len=self.config.strategy.entry_len,
                exit_len=self.config.strategy.exit_len,
                enable_52w_filter=False,
            )

            # Check Exit: Channel Exit (Close < 20-Day Low[1]) OR Hard Stop (-8%)
            close = eval_res["close"]
            is_channel_exit = eval_res.get("is_channel_exit", False)
            max_loss_pct = self.config.strategy.max_loss_stop_pct
            hard_stop_price = pos.entry_price * (1.0 - max_loss_pct / 100.0) if max_loss_pct > 0 else 0.0
            is_hard_stop = close <= hard_stop_price if hard_stop_price > 0 else False

            if is_channel_exit or is_hard_stop:
                pnl = round((close - pos.entry_price) * pos.quantity, 2)
                pnl_pct = round(((close - pos.entry_price) / pos.entry_price) * 100.0, 2)
                reason = f"Hard Stop Loss Hit (-{max_loss_pct:.0f}%)" if is_hard_stop and not is_channel_exit else "20-Day Low Channel Breakdown"
                exits.append(
                    ExitSignal(
                        symbol=sym,
                        company_name=stock_info.company_name,
                        close_price=close,
                        entry_price=pos.entry_price,
                        quantity=pos.quantity,
                        low_20_level=eval_res["low_20_prev"],
                        exit_reason=reason,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                    )
                )

        # After exits, effective available slots for new entries:
        effective_open_slots = min(self.portfolio.max_positions, initial_open_slots + len(exits))
        logger.info("Found %d exit signals. Effective open slots for new entries: %d", len(exits), effective_open_slots)

        # ------------------------------------------------------------------
        # Phase 2: Market Regime Check (Nifty 500 >= 50 EMA)
        # ------------------------------------------------------------------
        is_market_bullish = True
        index_close = 0.0
        index_ema50 = 0.0

        if self.config.market_regime.enabled:
            df_idx = self.fetcher.fetch_daily_candles(
                instrument_token=self.config.market_regime.index_token,
                symbol="NIFTY_500",
                days=150,
                use_cache=use_cache,
            )
            if df_idx is not None and len(df_idx) >= self.config.market_regime.ema_len:
                df_idx["ema_50"] = df_idx["close"].ewm(span=self.config.market_regime.ema_len, adjust=False).mean()
                index_close = float(df_idx["close"].iloc[-1])
                index_ema50 = float(df_idx["ema_50"].iloc[-1])
                is_market_bullish = index_close >= index_ema50
                logger.info(
                    "Market Regime Check: Nifty 500 = %.1f | 50 EMA = %.1f | Bullish = %s",
                    index_close,
                    index_ema50,
                    is_market_bullish,
                )

        if not is_market_bullish:
            logger.warning(
                "Nifty 500 is BELOW its 50 EMA (%.1f < %.1f). Market regime is BEARISH. Pausing all new breakout entries to protect capital.",
                index_close,
                index_ema50,
            )
            stocks_to_scan = []

        # ------------------------------------------------------------------
        # Phase 3: Scan Universe for New Breakout Entries (If Bullish)
        # ------------------------------------------------------------------
        for stock in stocks_to_scan:
            sym = stock.symbol
            # Skip if already in portfolio and not exiting today
            if sym in self.portfolio.positions and not any(e.symbol == sym for e in exits):
                continue

            inst_token = stock.instrument_token
            if not inst_token:
                continue

            scanned_count += 1
            df = self.fetcher.fetch_daily_candles(
                instrument_token=inst_token,
                symbol=sym,
                days=365,
                use_cache=use_cache,
            )
            if df is None or len(df) < max(self.config.strategy.entry_len, self.config.strategy.exit_len) + 1:
                continue

            df_ind = compute_indicators(
                df,
                entry_len=self.config.strategy.entry_len,
                exit_len=self.config.strategy.exit_len,
            )
            eval_res = evaluate_breakout_and_exit(
                df_ind,
                entry_len=self.config.strategy.entry_len,
                exit_len=self.config.strategy.exit_len,
                within_52w_pct=self.config.filters.within_52w_high_pct,
                enable_52w_filter=self.config.filters.near_52w_high_enabled,
            )

            # Filter: Must be a 20-Day Breakout AND pass 52-Week High filter
            if eval_res.get("is_breakout") and eval_res.get("passes_52w_filter"):
                close = eval_res["close"]

                # Liquidity & Penny Stock Filter
                if close < self.config.filters.min_stock_price:
                    continue
                if eval_res.get("vol_sma_20", 0) < self.config.filters.min_20d_avg_volume:
                    continue

                suggested_qty = self.portfolio.calculate_quantity(close)
                if suggested_qty <= 0:
                    continue

                investment = round(close * suggested_qty, 2)

                breakout_candidates.append(
                    EntryCandidate(
                        symbol=sym,
                        company_name=stock.company_name,
                        industry=stock.industry,
                        close_price=close,
                        suggested_qty=suggested_qty,
                        investment_amount=investment,
                        high_20_level=eval_res["high_20_prev"],
                        breakout_pct=round(eval_res["breakout_pct"], 2),
                        rvol=round(eval_res["rvol"], 2),
                        high_52w=round(eval_res["high_52w"], 2),
                        dist_52w_pct=round(eval_res["dist_52w_high_pct"], 2),
                        composite_score=round(eval_res["composite_score"], 2),
                    )
                )

        # ------------------------------------------------------------------
        # Phase 3: Rank Candidates and Enforce Sector Diversification Limit
        # ------------------------------------------------------------------
        # Sort descending by composite score
        breakout_candidates.sort(key=lambda c: c.composite_score, reverse=True)

        for i, cand in enumerate(breakout_candidates, 1):
            cand.rank = i

        max_per_sector = self.config.capital.max_per_sector
        sector_counts = self.portfolio.get_sector_counts()

        recommended: List[EntryCandidate] = []
        runner_ups: List[EntryCandidate] = []

        for cand in breakout_candidates:
            cand_sec = cand.industry or "Unknown"
            cur_sec_count = sector_counts.get(cand_sec, 0)

            if len(recommended) < effective_open_slots and (max_per_sector <= 0 or cur_sec_count < max_per_sector):
                recommended.append(cand)
                sector_counts[cand_sec] = cur_sec_count + 1
            else:
                runner_ups.append(cand)

        logger.info(
            "Scan completed: %d scanned, %d breakouts found, %d recommended entries for %d open slots",
            scanned_count,
            len(breakout_candidates),
            len(recommended),
            effective_open_slots,
        )

        return ScanResult(
            scan_date=scan_date,
            open_slots_before=initial_open_slots,
            open_slots_after=max(0, effective_open_slots - len(recommended)),
            exits=exits,
            recommended_entries=recommended,
            runner_ups=runner_ups,
            total_scanned=scanned_count,
            total_breakouts_found=len(breakout_candidates),
        )

