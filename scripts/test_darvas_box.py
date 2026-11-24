"""
scripts/test_darvas_box.py
==========================
Comprehensive Multi-Horizon Backtester for the Darvas Box Momentum Strategy
and Screener.in Filters across the Nifty 500 universe.

Screener.in Conditions Tested:
  1. Within 10% of 52-Week High: (High_52W - Close) / High_52W * 100 < 10
  2. At least 2x above 52-Week Low: Close >= 2.0 * Low_52W (i.e. +100% gain from 52W Low)
  3. Liquidity: Daily Volume >= 100,000 shares & 20D Volume SMA >= 100,000
  4. Breakout Volume: RVOL >= 1.5
  5. Darvas Box Formation:
     - Classic 3-Day Pivot Box (Nicolas Darvas State Machine)
     - 20-Day Range Box with Tightness Filter (<= 15%)
  6. Stop Loss & Trailing:
     - Box Bottom Stop
     - Dynamic Step-Ladder Trailing Exit

Compares against the repository's Baseline (50D Donchian Breakout, 2-Tier Exit)
across 4 standard horizons:
  - 2026 YTD
  - Last 12 Months
  - Last 2 Years
  - Last 5 Years
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tabulate import tabulate

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest import PortfolioBacktester, SimTrade

HORIZONS = [
    ("2026 YTD", "2026-01-01", "2026-11-09"),
    ("Last 12 Months", "2025-11-10", "2026-11-09"),
    ("Last 2 Years", "2024-11-11", "2026-11-09"),
    ("Last 5 Years", "2021-11-10", "2026-11-09"),
]


def compute_darvas_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Precompute 52W High, 52W Low, 2x 52W Low, 20D/50D Donchian, Volume, and Classic Darvas Boxes."""
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # 1. 52-Week High & 52-Week Low (252 trading days)
    out["high_52w"] = out["high"].rolling(window=252, min_periods=min(50, len(out))).max()
    out["low_52w"] = out["low"].rolling(window=252, min_periods=min(50, len(out))).min()

    # Screener.in metric 1: Within 10% of 52W High
    out["dist_52w_high_pct"] = ((out["close"] - out["high_52w"]) / out["high_52w"]) * 100.0

    # Screener.in metric 2: Price at least 2x 52W low (Gain >= 100%)
    out["gain_from_52w_low_pct"] = ((out["close"] - out["low_52w"]) / out["low_52w"]) * 100.0
    out["is_2x_52w_low"] = out["close"] >= (2.0 * out["low_52w"])

    # 2. EMAs and SMAs for Trend Filters
    out["ema_20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema_50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["sma_200"] = out["close"].rolling(window=200, min_periods=min(100, len(out))).mean()
    out["is_stage_2"] = (out["close"] > out["ema_50"]) & (out["ema_50"] > out["sma_200"])

    # 3. Volume Filters
    out["vol_sma_20"] = out["volume"].rolling(window=20, min_periods=10).mean()
    out["rvol"] = np.where(out["vol_sma_20"] > 0, out["volume"] / out["vol_sma_20"], 1.0)

    # 4. 20-Day and 50-Day Donchian Channels (as Box proxies)
    out["high_20_prev"] = out["high"].shift(1).rolling(window=20, min_periods=20).max()
    out["low_20_prev"] = out["low"].shift(1).rolling(window=20, min_periods=20).min()
    out["high_50_prev"] = out["high"].shift(1).rolling(window=50, min_periods=50).max()
    out["low_50_prev"] = out["low"].shift(1).rolling(window=50, min_periods=50).min()

    # 20-Day Box Tightness: (High - Low) / Low * 100
    out["box_20_tightness_pct"] = np.where(
        out["low_20_prev"] > 0,
        ((out["high_20_prev"] - out["low_20_prev"]) / out["low_20_prev"]) * 100.0,
        100.0,
    )

    # 6. Candle Close Strength: (Close - Low) / (High - Low)
    hl_spread = out["high"] - out["low"]
    out["candle_strength"] = np.where(hl_spread > 0, (out["close"] - out["low"]) / hl_spread, 0.5)

    # 5. Classic Nicolas Darvas 3-Day State Machine Box
    # Algorithm:
    # State: NONE -> TOP_CANDIDATE (waiting 3 days of non-violation) -> TOP_CONFIRMED -> BOT_CANDIDATE -> BOX_LOCKED
    n = len(out)
    box_tops = np.full(n, np.nan)
    box_bots = np.full(n, np.nan)

    highs = out["high"].values
    lows = out["low"].values
    closes = out["close"].values

    state = 0  # 0: Search Top, 1: Check Top, 2: Search Bot, 3: Check Bot, 4: Box Active
    curr_top = 0.0
    top_cand_idx = 0
    curr_bot = 0.0
    bot_cand_idx = 0

    active_top = np.nan
    active_bot = np.nan

    for i in range(len(out)):
        h = highs[i]
        l = lows[i]
        c = closes[i]

        if np.isnan(h) or np.isnan(l):
            continue

        if state == 0:
            # Start search for top candidate
            curr_top = h
            top_cand_idx = i
            state = 1
        elif state == 1:
            # Checking if top holds for 3 consecutive days
            if h > curr_top:
                # New higher high, reset top
                curr_top = h
                top_cand_idx = i
            elif i - top_cand_idx == 3:
                # Top held for 3 consecutive days! Top is confirmed
                curr_bot = l
                bot_cand_idx = i
                state = 3
        elif state == 3:
            # Checking if bottom holds for 3 consecutive days
            if h > curr_top:
                # Broken above before bot confirmed, restart top
                curr_top = h
                top_cand_idx = i
                state = 1
            elif l < curr_bot:
                # New lower low, reset bot
                curr_bot = l
                bot_cand_idx = i
            elif i - bot_cand_idx == 3:
                # Bot held for 3 consecutive days! Box is fully locked
                active_top = curr_top
                active_bot = curr_bot
                state = 4
        elif state == 4:
            # Box is active
            if c > active_top:
                # Breakout! Box broken upward. Search for next top.
                curr_top = h
                top_cand_idx = i
                state = 1
            elif c < active_bot:
                # Breakdown! Box broken downward. Reset.
                curr_top = h
                top_cand_idx = i
                state = 1

        box_tops[i] = active_top
        box_bots[i] = active_bot

    out["darvas_box_top"] = box_tops
    out["darvas_box_bot"] = box_bots
    out["darvas_box_top_prev"] = pd.Series(box_tops, index=out.index).shift(1)
    out["darvas_box_bot_prev"] = pd.Series(box_bots, index=out.index).shift(1)

    return out


class DarvasStrategyBacktester:
    def __init__(
        self,
        strategy_variant: str = "screener_box",
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 1.25,
        max_position_size_pct: float = 15.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        max_loss_pct: float = 8.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        universe_csv: str = "data/nifty500.csv",
        use_market_regime: bool = True,
    ):
        """
        strategy_variant options:
          - 'baseline': 50D Donchian High, within 10% 52W High, Price > 50 EMA > 200 SMA, 2-tier exit
          - 'baseline_plus_2x_52w_low': Baseline + Close >= 2.0 * Low_52W (Gain >= 100% from 52W Low)
          - 'screener_box_20d': 20D Box Breakout, within 10% 52W High, 2x 52W Low, Vol >= 100k, RVOL >= 1.5, Box Bottom Stop
          - 'screener_box_20d_tight': Same as above + Box Tightness <= 15%
          - 'classic_darvas_box': Classic Nicolas Darvas 3-day pivot box breakout, 2x 52W Low, trailing box bottom
        """
        self.strategy_variant = strategy_variant
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.max_loss_pct = max_loss_pct
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None
        self.universe_csv = universe_csv
        self.use_market_regime = use_market_regime

        self.symbol_industry_map: Dict[str, str] = {}
        if os.path.exists(universe_csv):
            try:
                df_u = pd.read_csv(universe_csv)
                for _, r in df_u.iterrows():
                    self.symbol_industry_map[str(r["Symbol"]).strip()] = str(r["Industry"]).strip()
            except Exception:
                pass

    def load_universe_data(self, cache_dir: str = "data/cache/daily_candles") -> Dict[str, pd.DataFrame]:
        files = glob.glob(os.path.join(cache_dir, "*.csv"))
        stock_dfs = {}

        for f in files:
            try:
                base = os.path.basename(f)
                sym = base.split("_")[0]
                df = pd.read_csv(f)
                if len(df) < 60:
                    continue
                df["dt"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
                df = df.sort_values("dt").reset_index(drop=True)
                df = compute_darvas_indicators(df)
                stock_dfs[sym] = df
            except Exception:
                continue

        return stock_dfs

    def run(self, stock_dfs: Dict[str, pd.DataFrame]) -> Dict:
        all_dates = set()
        for df in stock_dfs.values():
            all_dates.update(df["dt"])

        sorted_dates = sorted(list(all_dates))
        if self.start_date:
            sorted_dates = [d for d in sorted_dates if d >= self.start_date]
        if self.end_date:
            sorted_dates = [d for d in sorted_dates if d <= self.end_date]

        if not sorted_dates:
            raise ValueError("No trading dates found in the specified backtest range.")

        # Load Nifty 500 Index for Regime Filter
        index_regime_map = {}
        index_csv = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(index_csv) and self.use_market_regime:
            try:
                df_idx = pd.read_csv(index_csv)
                df_idx["dt"] = pd.to_datetime(df_idx["date"]).dt.tz_localize(None)
                df_idx = df_idx.sort_values("dt").reset_index(drop=True)
                df_idx["ema_50"] = df_idx["close"].ewm(span=50, adjust=False).mean()
                for _, r in df_idx.iterrows():
                    index_regime_map[r["dt"]] = bool(r["close"] >= r["ema_50"])
            except Exception:
                pass

        stock_date_maps = {sym: df.set_index("dt") for sym, df in stock_dfs.items()}

        cash = self.initial_capital
        positions = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []

        pending_exits = {}
        pending_entries = []

        for current_idx, current_dt in enumerate(sorted_dates):
            date_str = current_dt.strftime("%Y-%m-%d")

            # -------------------------------------------------------------
            # STEP A: Execute Pending Exits at Today's OPEN
            # -------------------------------------------------------------
            for sym, reason in list(pending_exits.items()):
                if sym in positions and sym in stock_date_maps:
                    stk_map = stock_date_maps[sym]
                    if current_dt in stk_map.index:
                        row = stk_map.loc[current_dt]
                        open_px = float(row["open"])
                        pos = positions.pop(sym)
                        exit_val = pos["qty"] * open_px
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_days = (current_dt - pos["entry_dt"]).days

                        peak_h = max(pos.get("peak_high", pos["entry_price"]), open_px)
                        trough_l = min(pos.get("trough_low", pos["entry_price"]), open_px)
                        mfe_pct = ((peak_h - pos["entry_price"]) / pos["entry_price"]) * 100.0
                        mae_pct = ((trough_l - pos["entry_price"]) / pos["entry_price"]) * 100.0

                        cash += exit_val
                        closed_trades.append(
                            SimTrade(
                                symbol=sym,
                                entry_date=pos["entry_date"],
                                exit_date=date_str,
                                entry_price=pos["entry_price"],
                                exit_price=open_px,
                                quantity=pos["qty"],
                                invested=pos["invested"],
                                exit_val=exit_val,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                holding_days=holding_days,
                                exit_reason=reason,
                                mfe_pct=round(mfe_pct, 2),
                                mae_pct=round(mae_pct, 2),
                            )
                        )
            pending_exits.clear()

            # -------------------------------------------------------------
            # STEP B: Execute Pending Entries at Today's OPEN
            # -------------------------------------------------------------
            open_pos_val = sum(
                float(stock_date_maps[s].loc[current_dt]["open"]) * p["qty"]
                for s, p in positions.items()
                if s in stock_date_maps and current_dt in stock_date_maps[s].index
            )
            current_equity = cash + open_pos_val

            for cand in pending_entries:
                sym = cand["symbol"]
                if sym in positions or sym not in stock_date_maps:
                    continue
                if len(positions) >= self.max_positions or cash < 5000:
                    break

                sec = self.symbol_industry_map.get(sym, "Unknown")
                curr_sec_count = sum(1 for p in positions.values() if p.get("industry") == sec)
                if self.max_per_sector > 0 and curr_sec_count >= self.max_per_sector:
                    continue

                stk_map = stock_date_maps[sym]
                if current_dt in stk_map.index:
                    row = stk_map.loc[current_dt]
                    open_px = float(row["open"])
                    stop_px = cand["stop_loss"]

                    if open_px <= stop_px or open_px <= 0:
                        continue

                    hard_stop = open_px * (1.0 - self.max_loss_pct / 100.0)
                    effective_stop = max(stop_px, hard_stop)
                    risk_per_share = max(open_px - effective_stop, open_px * 0.02)
                    risk_amount = current_equity * (self.risk_per_trade_pct / 100.0)
                    qty = int(risk_amount / risk_per_share)

                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    qty = min(qty, int(max_alloc // open_px))
                    qty = min(qty, int(cash // open_px))

                    if qty <= 0:
                        continue

                    inv = qty * open_px
                    cash -= inv
                    positions[sym] = {
                        "symbol": sym,
                        "qty": qty,
                        "entry_price": open_px,
                        "invested": inv,
                        "entry_date": date_str,
                        "entry_dt": current_dt,
                        "entry_trading_idx": current_idx,
                        "stop_loss": effective_stop,
                        "industry": sec,
                        "peak_high": open_px,
                        "trough_low": open_px,
                        "active_box_bot": cand.get("box_bot", effective_stop),
                    }

            pending_entries.clear()

            # -------------------------------------------------------------
            # STEP C: EOD Signals & Exits Evaluation
            # -------------------------------------------------------------
            is_market_bullish = True
            if self.use_market_regime and index_regime_map:
                is_market_bullish = index_regime_map.get(current_dt, True)

            todays_candidates = []

            for sym, df_map in stock_date_maps.items():
                if current_dt not in df_map.index:
                    continue

                row = df_map.loc[current_dt]
                close = float(row["close"])
                high = float(row["high"])
                low = float(row["low"])
                vol = float(row.get("volume", 0))
                vol_sma = float(row.get("vol_sma_20", 0))
                rvol = float(row.get("rvol", 1.0))
                dist_52w = float(row.get("dist_52w_high_pct", -999))
                is_2x_52w = bool(row.get("is_2x_52w_low", False))
                is_stage_2 = bool(row.get("is_stage_2", False))
                ema_20 = float(row.get("ema_20", 0))
                ema_50 = float(row.get("ema_50", 0))

                # Update running high/low tracking for open positions
                if sym in positions:
                    pos = positions[sym]
                    pos["peak_high"] = max(pos.get("peak_high", pos["entry_price"]), high)
                    pos["trough_low"] = min(pos.get("trough_low", pos["entry_price"]), low)
                    entry_px = pos["entry_price"]
                    unrealized_pnl_pct = ((close - entry_px) / entry_px) * 100.0
                    trading_days_held = current_idx - pos.get("entry_trading_idx", current_idx)

                    # ---------------- Exit Evaluation ----------------
                    if self.strategy_variant in ("baseline", "baseline_plus_2x_52w_low"):
                        # Baseline 2-Tier Exit
                        low_20_prev = float(row.get("low_20_prev", 0))
                        if close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                            pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"
                        elif trading_days_held >= 20 and unrealized_pnl_pct < 0:
                            pending_exits[sym] = f"Tenure Loss Cut ({trading_days_held}d, {unrealized_pnl_pct:.1f}%)"
                        elif unrealized_pnl_pct >= 25.0 and ema_20 > 0 and close < ema_20:
                            pending_exits[sym] = f"Profit Lock (+{unrealized_pnl_pct:.1f}% & Close < 20 EMA)"
                        elif ema_50 > 0 and close < ema_50:
                            pending_exits[sym] = "Stage 2 Breakdown (Close < 50 EMA)"
                        elif low_20_prev > 0 and close < low_20_prev:
                            pending_exits[sym] = "20-Day Low Breakdown"

                    elif self.strategy_variant in ("screener_box_20d", "screener_box_20d_tight"):
                        # Screener Darvas Box Exit:
                        # 1. Hard stop -8%
                        # 2. Profit Lock: Gain >= +25% & Close < 20 EMA
                        # 3. Dynamic Box Bottom Trailing (20-Day Low breakdown)
                        # 4. Tenure cut 20d if negative
                        low_20_prev = float(row.get("low_20_prev", 0))
                        if close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                            pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"
                        elif trading_days_held >= 20 and unrealized_pnl_pct < 0:
                            pending_exits[sym] = f"Tenure Loss Cut ({trading_days_held}d, {unrealized_pnl_pct:.1f}%)"
                        elif unrealized_pnl_pct >= 25.0 and ema_20 > 0 and close < ema_20:
                            pending_exits[sym] = f"Profit Lock (+{unrealized_pnl_pct:.1f}% & Close < 20 EMA)"
                        elif low_20_prev > 0 and close < low_20_prev:
                            pending_exits[sym] = "20D Box Bottom Breakdown"

                    elif self.strategy_variant == "classic_darvas_box":
                        # Classic Nicolas Darvas Trailing Box Exit
                        # Step-ladder stop: If a new higher box has established, trail stop to new box bottom
                        cur_box_bot = float(row.get("darvas_box_bot_prev", 0))
                        if not np.isnan(cur_box_bot) and cur_box_bot > pos.get("active_box_bot", 0):
                            pos["active_box_bot"] = cur_box_bot

                        stop_floor = pos.get("active_box_bot", entry_px * (1.0 - self.max_loss_pct / 100.0))
                        if close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                            pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"
                        elif close < stop_floor:
                            pending_exits[sym] = "Darvas Box Bottom Breakdown"
                        elif unrealized_pnl_pct >= 25.0 and ema_20 > 0 and close < ema_20:
                            pending_exits[sym] = f"Profit Lock (+{unrealized_pnl_pct:.1f}% & Close < 20 EMA)"

                    elif self.strategy_variant in ("golden_hybrid", "golden_hybrid_adaptive_2x"):
                        # Golden Hybrid Exit:
                        # 1. Hard Stop -8%
                        # 2. Tenure Loss Cut (20d held, P&L < 0)
                        # 3. Profit Lock: Gain >= +25% & Close < 20 EMA
                        # 4. Stage 2 Breakdown: Close < 50 EMA
                        # 5. Darvas Step-Ladder Trailing Stop: ratchets up whenever a new higher box is locked
                        cur_box_bot = float(row.get("darvas_box_bot_prev", 0))
                        if not np.isnan(cur_box_bot) and cur_box_bot > pos.get("active_box_bot", 0):
                            pos["active_box_bot"] = cur_box_bot

                        stop_floor = pos.get("active_box_bot", entry_px * (1.0 - self.max_loss_pct / 100.0))
                        low_20_prev = float(row.get("low_20_prev", 0))

                        if close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                            pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"
                        elif trading_days_held >= 20 and unrealized_pnl_pct < 0:
                            pending_exits[sym] = f"Tenure Loss Cut ({trading_days_held}d, {unrealized_pnl_pct:.1f}%)"
                        elif unrealized_pnl_pct >= 25.0 and ema_20 > 0 and close < ema_20:
                            pending_exits[sym] = f"Profit Lock (+{unrealized_pnl_pct:.1f}% & Close < 20 EMA)"
                        elif ema_50 > 0 and close < ema_50:
                            pending_exits[sym] = "Stage 2 Breakdown (Close < 50 EMA)"
                        elif close < stop_floor:
                            pending_exits[sym] = "Darvas Step-Ladder Box Breakdown"
                        elif low_20_prev > 0 and close < low_20_prev:
                            pending_exits[sym] = "20-Day Low Breakdown"

                # ---------------- Entry Evaluation ----------------
                elif is_market_bullish:
                    if close < 100.0:
                        continue

                    if self.strategy_variant == "baseline":
                        high_50_prev = float(row.get("high_50_prev", 0))
                        low_20_prev = float(row.get("low_20_prev", 0))
                        is_breakout = close > high_50_prev and high_50_prev > 0
                        passes_52w = dist_52w >= -10.0
                        is_liquid = vol_sma >= 50000

                        if is_breakout and passes_52w and is_liquid and is_stage_2:
                            breakout_pct = ((close - high_50_prev) / high_50_prev) * 100.0
                            score = breakout_pct * max(rvol, 0.1)
                            todays_candidates.append({
                                "symbol": sym,
                                "close": close,
                                "score": score,
                                "stop_loss": low_20_prev,
                                "box_bot": low_20_prev,
                            })

                    elif self.strategy_variant == "baseline_plus_2x_52w_low":
                        high_50_prev = float(row.get("high_50_prev", 0))
                        low_20_prev = float(row.get("low_20_prev", 0))
                        is_breakout = close > high_50_prev and high_50_prev > 0
                        passes_52w = dist_52w >= -10.0
                        is_liquid = vol_sma >= 50000

                        # MUST BE AT LEAST 2X FROM 52W LOW
                        if is_breakout and passes_52w and is_liquid and is_stage_2 and is_2x_52w:
                            breakout_pct = ((close - high_50_prev) / high_50_prev) * 100.0
                            score = breakout_pct * max(rvol, 0.1)
                            todays_candidates.append({
                                "symbol": sym,
                                "close": close,
                                "score": score,
                                "stop_loss": low_20_prev,
                                "box_bot": low_20_prev,
                            })

                    elif self.strategy_variant == "screener_box_20d":
                        # Full Screener.in conditions:
                        # 1. Within 10% 52W High
                        # 2. At least 2x 52W Low (Gain >= 100%)
                        # 3. Daily Vol >= 100k & Vol SMA >= 100k
                        # 4. RVOL >= 1.5
                        # 5. Breakout above 20D Box Top (high_20_prev)
                        high_20_prev = float(row.get("high_20_prev", 0))
                        low_20_prev = float(row.get("low_20_prev", 0))
                        passes_52w = dist_52w >= -10.0
                        is_liquid = vol >= 100000 and vol_sma >= 100000
                        is_breakout = close > high_20_prev and high_20_prev > 0
                        has_rvol = rvol >= 1.5

                        if is_breakout and passes_52w and is_2x_52w and is_liquid and has_rvol and is_stage_2:
                            breakout_pct = ((close - high_20_prev) / high_20_prev) * 100.0
                            score = breakout_pct * rvol
                            todays_candidates.append({
                                "symbol": sym,
                                "close": close,
                                "score": score,
                                "stop_loss": low_20_prev,
                                "box_bot": low_20_prev,
                            })

                    elif self.strategy_variant == "screener_box_20d_tight":
                        # Same + Box Tightness <= 15%
                        high_20_prev = float(row.get("high_20_prev", 0))
                        low_20_prev = float(row.get("low_20_prev", 0))
                        box_tightness = float(row.get("box_20_tightness_pct", 100))
                        passes_52w = dist_52w >= -10.0
                        is_liquid = vol >= 100000 and vol_sma >= 100000
                        is_breakout = close > high_20_prev and high_20_prev > 0
                        has_rvol = rvol >= 1.5
                        is_tight = box_tightness <= 15.0

                        if is_breakout and passes_52w and is_2x_52w and is_liquid and has_rvol and is_stage_2 and is_tight:
                            breakout_pct = ((close - high_20_prev) / high_20_prev) * 100.0
                            score = breakout_pct * rvol
                            todays_candidates.append({
                                "symbol": sym,
                                "close": close,
                                "score": score,
                                "stop_loss": low_20_prev,
                                "box_bot": low_20_prev,
                            })

                    elif self.strategy_variant == "classic_darvas_box":
                        # Classic Nicolas Darvas State Machine Box
                        darvas_top = float(row.get("darvas_box_top_prev", np.nan))
                        darvas_bot = float(row.get("darvas_box_bot_prev", np.nan))

                        if not np.isnan(darvas_top) and not np.isnan(darvas_bot):
                            is_breakout = close > darvas_top
                            passes_52w = dist_52w >= -10.0
                            is_liquid = vol >= 100000 and vol_sma >= 100000
                            has_rvol = rvol >= 1.5

                            if is_breakout and passes_52w and is_2x_52w and is_liquid and has_rvol:
                                breakout_pct = ((close - darvas_top) / darvas_top) * 100.0
                                score = breakout_pct * rvol
                                todays_candidates.append({
                                    "symbol": sym,
                                    "close": close,
                                    "score": score,
                                    "stop_loss": darvas_bot,
                                    "box_bot": darvas_bot,
                                })

                    elif self.strategy_variant in ("golden_hybrid", "golden_hybrid_adaptive_2x"):
                        # Golden Hybrid: 50D Breakout + 52W Proximity + RVOL >= 1.2 + Candle Close Strength >= 0.70
                        high_50_prev = float(row.get("high_50_prev", 0))
                        low_20_prev = float(row.get("low_20_prev", 0))
                        candle_str = float(row.get("candle_strength", 0.5))
                        is_breakout = close > high_50_prev and high_50_prev > 0
                        passes_52w = dist_52w >= -10.0
                        is_liquid = vol >= 100000 and vol_sma >= 50000
                        has_rvol = rvol >= 1.2
                        strong_close = candle_str >= 0.70  # closed in top 30% of day's range

                        passes_adaptive = True
                        if self.strategy_variant == "golden_hybrid_adaptive_2x":
                            # Require at least 50% gain from 52w low (Price >= 1.5 * Low_52W)
                            gain_52w_low = float(row.get("gain_from_52w_low_pct", 0))
                            passes_adaptive = gain_52w_low >= 50.0

                        if is_breakout and passes_52w and is_liquid and has_rvol and is_stage_2 and strong_close and passes_adaptive:
                            breakout_pct = ((close - high_50_prev) / high_50_prev) * 100.0
                            score = breakout_pct * rvol
                            darvas_bot = float(row.get("darvas_box_bot_prev", np.nan))
                            initial_stop = low_20_prev
                            if not np.isnan(darvas_bot) and darvas_bot > 0:
                                initial_stop = max(low_20_prev, darvas_bot)

                            todays_candidates.append({
                                "symbol": sym,
                                "close": close,
                                "score": score,
                                "stop_loss": initial_stop,
                                "box_bot": initial_stop,
                            })

            todays_candidates.sort(key=lambda x: x["score"], reverse=True)
            pending_entries = todays_candidates

            # -------------------------------------------------------------
            # STEP D: Mark-to-Market Portfolio Equity
            # -------------------------------------------------------------
            open_pos_value = 0.0
            for sym, pos in positions.items():
                if sym in stock_date_maps and current_dt in stock_date_maps[sym].index:
                    row_stk = stock_date_maps[sym].loc[current_dt]
                    c = float(row_stk["close"])
                    open_pos_value += c * pos["qty"]
                else:
                    open_pos_value += pos["invested"]

            total_equity = cash + open_pos_value
            equity_curve.append((current_dt, total_equity, cash, len(positions)))

        # Close any lingering positions on final day
        final_dt = sorted_dates[-1]
        final_date_str = final_dt.strftime("%Y-%m-%d")
        for sym, pos in list(positions.items()):
            if sym in stock_date_maps and final_dt in stock_date_maps[sym].index:
                row = stock_date_maps[sym].loc[final_dt]
                close_px = float(row["close"])
                exit_val = pos["qty"] * close_px
                pnl = exit_val - pos["invested"]
                pnl_pct = (pnl / pos["invested"]) * 100.0
                holding_days = (final_dt - pos["entry_dt"]).days

                peak_h = max(pos.get("peak_high", pos["entry_price"]), close_px)
                trough_l = min(pos.get("trough_low", pos["entry_price"]), close_px)
                mfe_pct = ((peak_h - pos["entry_price"]) / pos["entry_price"]) * 100.0
                mae_pct = ((trough_l - pos["entry_price"]) / pos["entry_price"]) * 100.0

                closed_trades.append(
                    SimTrade(
                        symbol=sym,
                        entry_date=pos["entry_date"],
                        exit_date=final_date_str,
                        entry_price=pos["entry_price"],
                        exit_price=close_px,
                        quantity=pos["qty"],
                        invested=pos["invested"],
                        exit_val=exit_val,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        holding_days=holding_days,
                        exit_reason="End of Backtest",
                        mfe_pct=round(mfe_pct, 2),
                        mae_pct=round(mae_pct, 2),
                    )
                )

        return self._calc_stats(equity_curve, closed_trades)

    def _calc_stats(self, equity_curve: List[Tuple], trades: List[SimTrade]) -> Dict:
        if not equity_curve:
            return {}

        df_eq = pd.DataFrame(equity_curve, columns=["dt", "equity", "cash", "num_positions"])
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["drawdown_val"] = df_eq["equity"] - df_eq["peak"]
        df_eq["drawdown_pct"] = np.where(df_eq["peak"] > 0, (df_eq["drawdown_val"] / df_eq["peak"]) * 100.0, 0.0)

        max_dd_pct = df_eq["drawdown_pct"].min()
        max_dd_val = df_eq["drawdown_val"].min()

        start_eq = self.initial_capital
        end_eq = df_eq["equity"].iloc[-1]
        net_profit = end_eq - start_eq
        total_return_pct = (net_profit / start_eq) * 100.0

        num_days = (df_eq["dt"].iloc[-1] - df_eq["dt"].iloc[0]).days
        years = max(num_days / 365.25, 0.1)
        cagr_pct = ((end_eq / start_eq) ** (1.0 / years) - 1.0) * 100.0 if end_eq > 0 else -100.0

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        avg_win_pct = np.mean([t.pnl_pct for t in wins]) if wins else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in losses]) if losses else 0.0

        # Daily returns for Sharpe
        df_eq["daily_ret"] = df_eq["equity"].pct_change().fillna(0)
        mean_ret = df_eq["daily_ret"].mean() * 252
        std_ret = df_eq["daily_ret"].std() * np.sqrt(252)
        rf = 0.065
        sharpe = (mean_ret - rf) / std_ret if std_ret > 0 else 0.0

        return {
            "start_capital": start_eq,
            "end_equity": end_eq,
            "net_profit": net_profit,
            "return_pct": total_return_pct,
            "cagr_pct": cagr_pct,
            "max_dd_pct": max_dd_pct,
            "max_dd_val": max_dd_val,
            "profit_factor": profit_factor,
            "sharpe": sharpe,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "trades": trades,
            "equity_df": df_eq,
        }


def run_all_benchmarks():
    print("=" * 80)
    print("DARVAS BOX & SCREENER.IN MOMENTUM STRATEGY - MULTI-HORIZON BENCHMARK")
    print("=" * 80)

    # Load and precompute
    loader = DarvasStrategyBacktester()
    print("Loading universe candles and precomputing Darvas Box indicators...")
    stock_dfs = loader.load_universe_data()
    print(f"Loaded {len(stock_dfs)} stock DataFrames with Darvas Box metrics.\n")

    variants = [
        ("Baseline (50D Donchian, 2-Tier Exit)", "baseline"),
        ("Classic Darvas State Machine (3-Day Pivot)", "classic_darvas_box"),
        ("Golden Hybrid (50D + Close>=70% + Darvas Trailing)", "golden_hybrid"),
        ("Golden Hybrid + Adaptive 1.5x Low", "golden_hybrid_adaptive_2x"),
        ("Screener 20D Box (Vol>100k, RVOL>=1.5, 2x Low)", "screener_box_20d"),
    ]

    for h_name, start_d, end_d in HORIZONS:
        print(f"\n{'='*35} HORIZON: {h_name} ({start_d} to {end_d}) {'='*35}")
        rows = []
        for label, v_key in variants:
            bt = DarvasStrategyBacktester(strategy_variant=v_key, start_date=start_d, end_date=end_d)
            res = bt.run(stock_dfs)
            rows.append([
                label,
                f"₹{res['end_equity']:,.2f}",
                f"{res['return_pct']:+.2f}%",
                f"{res['cagr_pct']:+.1f}%",
                f"{res['max_dd_pct']:.2f}%",
                f"{res['profit_factor']:.2f}",
                f"{res['sharpe']:.2f}",
                f"{res['win_rate']:.1f}%",
                f"{res['total_trades']} ({res['wins']}W/{res['losses']}L)",
                f"{res['avg_win_pct']:+.1f}% / {res['avg_loss_pct']:.1f}%",
            ])

        headers = [
            "Strategy Variant",
            "Ending Equity",
            "Return %",
            "CAGR",
            "Max DD",
            "Prof Fact",
            "Sharpe",
            "Win Rate",
            "Trades (W/L)",
            "Avg W / Avg L",
        ]
        print(tabulate(rows, headers=headers, tablefmt="github"))


if __name__ == "__main__":
    run_all_benchmarks()
