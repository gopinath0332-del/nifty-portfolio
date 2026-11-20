"""
scripts/test_oliver_kell.py
===========================
Rigorous Multi-Horizon Backtester for Oliver Kell's Swing Trading Strategy
(US Investing Champion 2020: +941.1% audited return).

Strategy Components:
  1. Core EMAs: 10 EMA & 20 EMA.
  2. Trend Condition: Price > 10 EMA and 10 EMA > 20 EMA.
  3. "Base 'n Break" Setup:
     - 3 to 7 days (default 5 days) tight consolidation base (Base Tightness <= 8% to 10%).
     - Base forms near the 10 EMA / 20 EMA support.
     - Breakout: Day T Close breaks above the highest high of the base with RVOL >= 1.2.
  4. Stop Loss:
     - Placed right at the low of the consolidation base: Stop = min(Low of base).
     - Max risk capped at -8.0% hard stop.
  5. Sizing:
     - 1.25% equity risk per trade, max 15% capital per stock, max 10 concurrent positions.
  6. Exits:
     - Exit A (Swing Trend End): Close < 20 EMA (executed at Day T+1 Open).
     - Exit B (Fast Momentum Break): Close < 10 EMA (executed at Day T+1 Open).
     - Exit C (Exhaustion Extension): Profit take when price is stretched >= 15% above 10 EMA with >= 15% profit.
     - Exit D (Stop Loss): Base low stop or hard stop -8%.

Benchmarks against the repository's Baseline Donchian Model across 4 standard horizons:
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


def compute_kell_indicators(df: pd.DataFrame, base_len: int = 5) -> pd.DataFrame:
    """Precompute 10 EMA, 20 EMA, 50 EMA, 200 SMA, 20D Vol SMA, and Base 'n Break metrics."""
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # EMAs & SMAs
    out["ema_10"] = out["close"].ewm(span=10, adjust=False).mean()
    out["ema_20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema_50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["sma_200"] = out["close"].rolling(window=200, min_periods=min(100, len(out))).mean()

    # 20-Day Volume SMA & RVOL
    out["vol_sma_20"] = out["volume"].rolling(window=20, min_periods=10).mean()
    out["rvol"] = np.where(out["vol_sma_20"] > 0, out["volume"] / out["vol_sma_20"], 1.0)

    # Base 'n Break indicators over lookback window (e.g. 5 days prior to today: [t-base_len, t-1])
    out["base_high"] = out["high"].shift(1).rolling(window=base_len, min_periods=base_len).max()
    out["base_low"] = out["low"].shift(1).rolling(window=base_len, min_periods=base_len).min()
    
    # Base tightness: (base_high - base_low) / base_low * 100
    out["base_tightness_pct"] = ((out["base_high"] - out["base_low"]) / out["base_low"]) * 100.0

    # Proximity of base to 10 EMA
    out["base_to_ema10_pct"] = ((out["base_high"] - out["ema_10"].shift(1)) / out["ema_10"].shift(1)) * 100.0

    # Extension above 10 EMA today
    out["extension_10ema_pct"] = ((out["close"] - out["ema_10"]) / out["ema_10"]) * 100.0

    # 52-Week High & Proximity (252 trading days)
    out["high_52w"] = out["high"].rolling(window=252, min_periods=min(50, len(out))).max()
    out["dist_52w_high_pct"] = ((out["close"] - out["high_52w"]) / out["high_52w"]) * 100.0

    return out


class OliverKellBacktester:
    def __init__(
        self,
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 1.25,
        max_position_size_pct: float = 15.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        base_len: int = 5,
        max_base_tightness_pct: float = 8.0,
        min_rvol: float = 1.2,
        exit_mode: str = "close_below_20ema",  # "close_below_20ema" or "close_below_10ema"
        use_exhaustion_exit: bool = True,
        exhaustion_extension_pct: float = 15.0,
        max_loss_pct: float = 8.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        universe_csv: str = "data/nifty500.csv",
        cache_dir: str = "data/cache/daily_candles",
        use_market_regime: bool = True,
        within_52w_pct: Optional[float] = None,
    ):
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.base_len = base_len
        self.max_base_tightness_pct = max_base_tightness_pct
        self.min_rvol = min_rvol
        self.exit_mode = exit_mode
        self.use_exhaustion_exit = use_exhaustion_exit
        self.exhaustion_extension_pct = exhaustion_extension_pct
        self.max_loss_pct = max_loss_pct
        self.start_date = start_date
        self.end_date = end_date
        self.universe_csv = universe_csv
        self.cache_dir = cache_dir
        self.use_market_regime = use_market_regime
        self.within_52w_pct = within_52w_pct

        self.symbol_industry_map: Dict[str, str] = {}
        self._load_universe()

    def _load_universe(self):
        if os.path.exists(self.universe_csv):
            try:
                df = pd.read_csv(self.universe_csv)
                for _, row in df.iterrows():
                    sym = str(row.get("symbol", row.get("Symbol", ""))).strip()
                    sec = str(row.get("industry", row.get("Industry", "Unknown"))).strip()
                    if sym:
                        self.symbol_industry_map[sym] = sec
            except Exception:
                pass

    def run(self, raw_dfs: Dict[str, pd.DataFrame]) -> Tuple[Dict, List[SimTrade], pd.DataFrame]:
        # Precompute indicators for all stocks
        stock_dfs = {}
        all_dts = set()
        for sym, df in raw_dfs.items():
            d = compute_kell_indicators(df, base_len=self.base_len)
            stock_dfs[sym] = d
            all_dts.update(d["dt"].tolist())

        # Load Nifty 500 Index for Market Regime Filter
        index_regime = {}
        idx_file = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(idx_file) and self.use_market_regime:
            try:
                idf = pd.read_csv(idx_file)
                idf["dt"] = pd.to_datetime(idf["date"]).dt.tz_localize(None)
                idf = idf.sort_values("dt").reset_index(drop=True)
                idf["ema_50"] = idf["close"].ewm(span=50, adjust=False).mean()
                for _, r in idf.iterrows():
                    index_regime[r["dt"]] = bool(r["close"] >= r["ema_50"])
            except Exception:
                pass

        sorted_dates = sorted(list(all_dts))
        start_dt = pd.to_datetime(self.start_date)
        end_dt = pd.to_datetime(self.end_date) if self.end_date else sorted_dates[-1]
        sim_dates = [d for d in sorted_dates if start_dt <= d <= end_dt]

        if not sim_dates:
            return {}, [], pd.DataFrame()

        # Build fast lookup map
        stock_date_maps = {sym: df.set_index("dt") for sym, df in stock_dfs.items()}

        cash = self.initial_capital
        positions = {}  # sym -> dict
        closed_trades: List[SimTrade] = []
        equity_curve: List[dict] = []

        pending_exits = {}   # sym -> reason
        pending_entries = [] # list of dicts

        for current_idx, current_dt in enumerate(sim_dates):
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
                            )
                        )
            pending_exits.clear()

            # -------------------------------------------------------------
            # STEP B: Execute Pending Entries at Today's OPEN
            # -------------------------------------------------------------
            current_equity = cash + sum(
                pos["qty"] * float(stock_date_maps[s].loc[current_dt]["close"])
                if s in stock_date_maps and current_dt in stock_date_maps[s].index
                else pos["invested"]
                for s, pos in positions.items()
            )

            for cand in pending_entries:
                sym = cand["symbol"]
                if sym in positions:
                    continue
                if len(positions) >= self.max_positions or cash < 5000:
                    break

                sec = self.symbol_industry_map.get(sym, "Unknown")
                curr_sec_count = sum(1 for p in positions.values() if p["sector"] == sec)
                if curr_sec_count >= self.max_per_sector:
                    continue

                if sym in stock_date_maps and current_dt in stock_date_maps[sym].index:
                    row = stock_date_maps[sym].loc[current_dt]
                    open_px = float(row["open"])
                    stop_px = cand["stop_loss"]

                    if open_px <= stop_px:
                        continue

                    # Risk sizing: 1.25% risk per trade
                    risk_amount = current_equity * (self.risk_per_trade_pct / 100.0)
                    risk_per_share = open_px - stop_px
                    qty = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

                    # Cap at 15% equity
                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    qty_cap = int(max_alloc / open_px) if open_px > 0 else 0
                    qty = min(qty, qty_cap)

                    # Cash affordability
                    max_affordable = int(cash / open_px) if open_px > 0 else 0
                    qty = min(qty, max_affordable)

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
                        "stop_loss": stop_px,
                        "sector": sec,
                    }

            pending_entries.clear()

            # -------------------------------------------------------------
            # STEP C: Intraday Stop Loss & EOD Exit Evaluation
            # -------------------------------------------------------------
            # 1. Check intraday stop losses
            intraday_exits = []
            for sym, pos in list(positions.items()):
                if sym in stock_date_maps and current_dt in stock_date_maps[sym].index:
                    row = stock_date_maps[sym].loc[current_dt]
                    low_px = float(row["low"])
                    open_px = float(row["open"])
                    close_px = float(row["close"])

                    # If low touched or breached stop loss
                    if low_px <= pos["stop_loss"]:
                        exit_px = min(pos["stop_loss"], open_px)
                        exit_val = pos["qty"] * exit_px
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_days = (current_dt - pos["entry_dt"]).days

                        cash += exit_val
                        closed_trades.append(
                            SimTrade(
                                symbol=sym,
                                entry_date=pos["entry_date"],
                                exit_date=date_str,
                                entry_price=pos["entry_price"],
                                exit_price=exit_px,
                                quantity=pos["qty"],
                                invested=pos["invested"],
                                exit_val=exit_val,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                holding_days=holding_days,
                                exit_reason="Base Stop Loss (Hit Low)",
                            )
                        )
                        intraday_exits.append(sym)
                    elif (close_px - pos["entry_price"]) / pos["entry_price"] * 100.0 <= -self.max_loss_pct:
                        # Hard loss stop
                        exit_val = pos["qty"] * close_px
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_days = (current_dt - pos["entry_dt"]).days

                        cash += exit_val
                        closed_trades.append(
                            SimTrade(
                                symbol=sym,
                                entry_date=pos["entry_date"],
                                exit_date=date_str,
                                entry_price=pos["entry_price"],
                                exit_price=close_px,
                                quantity=pos["qty"],
                                invested=pos["invested"],
                                exit_val=exit_val,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                holding_days=holding_days,
                                exit_reason=f"Hard Stop (-{self.max_loss_pct}%)",
                            )
                        )
                        intraday_exits.append(sym)

            for sym in intraday_exits:
                del positions[sym]

            # 2. Check EOD signals for exits to execute tomorrow Open
            for sym, pos in positions.items():
                if sym in stock_date_maps and current_dt in stock_date_maps[sym].index:
                    row = stock_date_maps[sym].loc[current_dt]
                    close_px = float(row["close"])
                    ema10 = float(row["ema_10"])
                    ema20 = float(row["ema_20"])
                    ext10 = float(row["extension_10ema_pct"])
                    pnl_unrealized_pct = ((close_px - pos["entry_price"]) / pos["entry_price"]) * 100.0

                    # Check Exhaustion Extension (Climax Profit Take)
                    if self.use_exhaustion_exit and (ext10 >= self.exhaustion_extension_pct) and (pnl_unrealized_pct >= 15.0):
                        pending_exits[sym] = f"Exhaustion Extension (+{ext10:.1f}% > 10EMA)"
                    # Check EMA violation
                    elif self.exit_mode == "close_below_20ema" and close_px < ema20:
                        pending_exits[sym] = "Close < 20 EMA"
                    elif self.exit_mode == "close_below_10ema" and close_px < ema10:
                        pending_exits[sym] = "Close < 10 EMA"

            # -------------------------------------------------------------
            # STEP D: Record Equity Curve
            # -------------------------------------------------------------
            invested_val = sum(
                pos["qty"] * float(stock_date_maps[s].loc[current_dt]["close"])
                if s in stock_date_maps and current_dt in stock_date_maps[s].index
                else pos["invested"]
                for s, pos in positions.items()
            )
            total_eq = cash + invested_val
            equity_curve.append({
                "date": date_str,
                "cash": cash,
                "invested": invested_val,
                "equity": total_eq,
                "open_positions": len(positions),
            })

            # If last date, exit
            if current_idx >= len(sim_dates) - 1:
                break

            # -------------------------------------------------------------
            # STEP E: Scan for "Base 'n Break" Candidates on Day T
            # -------------------------------------------------------------
            is_bull_regime = index_regime.get(current_dt, True)
            if not is_bull_regime:
                continue

            available_slots = self.max_positions - (len(positions) - len(pending_exits))
            if available_slots <= 0 or cash < 5000:
                continue

            candidates = []
            for sym, df_map in stock_date_maps.items():
                if sym in positions or sym in pending_exits:
                    continue
                if current_dt not in df_map.index:
                    continue

                row = df_map.loc[current_dt]
                close_px = float(row["close"])
                open_px = float(row["open"])

                # Filter 1: Price >= 100
                if close_px < 100.0:
                    continue

                # Filter 1b: 52-Week High Proximity (if enabled)
                if self.within_52w_pct is not None:
                    dist_52w = float(row["dist_52w_high_pct"])
                    if np.isnan(dist_52w) or dist_52w < -self.within_52w_pct:
                        continue

                # Filter 2: Uptrend (Close > 10 EMA > 20 EMA)
                ema10 = float(row["ema_10"])
                ema20 = float(row["ema_20"])
                if not (close_px > ema10 and ema10 > ema20):
                    continue

                # Filter 3: Base Tightness (e.g. <= 8% or 10%)
                base_tightness = float(row["base_tightness_pct"])
                if np.isnan(base_tightness) or base_tightness > self.max_base_tightness_pct:
                    continue

                # Filter 4: Base Proximity to 10 EMA (not overextended before base breakout)
                base_to_ema10 = float(row["base_to_ema10_pct"])
                if np.isnan(base_to_ema10) or base_to_ema10 > 6.0:
                    continue

                # Filter 5: Breakout over Base High
                base_high = float(row["base_high"])
                if close_px <= base_high:
                    continue

                # Filter 6: Volume Confirmation (RVOL >= min_rvol)
                rvol = float(row["rvol"])
                if rvol < self.min_rvol:
                    continue

                # Bullish candle
                if close_px <= open_px:
                    continue

                # Stop loss at base low
                base_low = float(row["base_low"])
                stop_loss = base_low

                # Hard stop cap (-8% max risk)
                if (close_px - stop_loss) / close_px > (self.max_loss_pct / 100.0):
                    stop_loss = close_px * (1.0 - self.max_loss_pct / 100.0)

                breakout_pct = ((close_px - base_high) / base_high) * 100.0
                score = breakout_pct * rvol

                candidates.append({
                    "symbol": sym,
                    "score": score,
                    "breakout_pct": breakout_pct,
                    "rvol": rvol,
                    "stop_loss": stop_loss,
                    "close": close_px,
                })

            if candidates:
                candidates.sort(key=lambda x: x["score"], reverse=True)
                pending_entries = candidates[:available_slots]

        # Close all remaining positions at end date
        final_dt = sim_dates[-1]
        final_date_str = final_dt.strftime("%Y-%m-%d")
        for sym, pos in list(positions.items()):
            close_px = float(stock_date_maps[sym].loc[final_dt]["close"]) if sym in stock_date_maps and final_dt in stock_date_maps[sym].index else pos["entry_price"]
            exit_val = pos["qty"] * close_px
            pnl = exit_val - pos["invested"]
            pnl_pct = (pnl / pos["invested"]) * 100.0
            holding_days = (final_dt - pos["entry_dt"]).days

            cash += exit_val
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
                )
            )

        df_eq = pd.DataFrame(equity_curve)
        metrics = self._calculate_metrics(closed_trades, df_eq)
        return metrics, closed_trades, df_eq

    def _calculate_metrics(self, trades: List[SimTrade], df_eq: pd.DataFrame) -> Dict:
        if not trades or df_eq.empty:
            return {}

        final_equity = df_eq["equity"].iloc[-1]
        total_pnl = final_equity - self.initial_capital
        total_ret_pct = (total_pnl / self.initial_capital) * 100.0

        # Drawdown
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["dd"] = (df_eq["equity"] - df_eq["peak"]) / df_eq["peak"] * 100.0
        max_dd = df_eq["dd"].min()

        # Wins & Losses
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0

        avg_win_pct = np.mean([t.pnl_pct for t in wins]) if wins else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in losses]) if losses else 0.0
        avg_holding = np.mean([t.holding_days for t in trades]) if trades else 0.0

        # Annualized return (CAGR)
        start_d = pd.to_datetime(self.start_date)
        end_d = pd.to_datetime(self.end_date) if self.end_date else pd.to_datetime(df_eq["date"].iloc[-1])
        days = max(1, (end_d - start_d).days)
        years = days / 365.25
        cagr = (((final_equity / self.initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if years > 0 and final_equity > 0 else 0.0

        return {
            "start_date": self.start_date,
            "end_date": str(end_d.date()),
            "initial_capital": self.initial_capital,
            "final_equity": final_equity,
            "total_pnl": total_pnl,
            "total_ret_pct": total_ret_pct,
            "cagr": cagr,
            "max_dd_pct": max_dd,
            "profit_factor": profit_factor,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "payout_ratio": abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0,
            "avg_holding_days": avg_holding,
        }


def run_benchmark():
    print("=========================================================================================")
    print("  OLIVER KELL SWING TRADING STRATEGY VS BASELINE DONCHIAN ENGINE BENCHMARK (NIFTY 500)")
    print("=========================================================================================")

    # Preload universe data once
    base_engine = PortfolioBacktester()
    raw_dfs = base_engine.load_universe_data(cache_dir="data/cache/daily_candles")
    print(f"Loaded {len(raw_dfs)} stock candle datasets from cache.\n")

    summary_rows = []

    for name, s_date, e_date in HORIZONS:
        print(f"--- Running Horizon: {name} ({s_date} to {e_date}) ---")

        # 1. Baseline Model
        base_bt = PortfolioBacktester(start_date=s_date, end_date=e_date)
        base_metrics = base_bt.run(raw_dfs)

        # 2. Oliver Kell Strategy (Exit on Close < 20 EMA, Exhaustion Exit at +15% > 10EMA)
        kell_bt = OliverKellBacktester(
            start_date=s_date,
            end_date=e_date,
            base_len=5,
            max_base_tightness_pct=8.0,
            min_rvol=1.2,
            exit_mode="close_below_20ema",
            use_exhaustion_exit=True,
            exhaustion_extension_pct=15.0,
        )
        kell_metrics, _, _ = kell_bt.run(raw_dfs)

        # 3. Oliver Kell Strategy Variant (Faster exit on Close < 10 EMA)
        kell_fast_bt = OliverKellBacktester(
            start_date=s_date,
            end_date=e_date,
            base_len=5,
            max_base_tightness_pct=8.0,
            min_rvol=1.2,
            exit_mode="close_below_10ema",
            use_exhaustion_exit=True,
            exhaustion_extension_pct=15.0,
        )
        kell_fast_metrics, _, _ = kell_fast_bt.run(raw_dfs)

        summary_rows.append({
            "Horizon": name,
            "Base Ret %": f"+{base_metrics['total_return_pct']:.2f}%",
            "Base CAGR": f"+{base_metrics['cagr_pct']:.2f}%",
            "Base MaxDD": f"{base_metrics['max_drawdown_pct']:.2f}%",
            "Base PF": f"{base_metrics['profit_factor']:.2f}",
            "Base WR%": f"{base_metrics['win_rate']:.1f}% ({base_metrics['total_trades']}T)",
            "Kell (20EMA) Ret%": f"{kell_metrics['total_ret_pct']:+.2f}%",
            "Kell CAGR": f"{kell_metrics['cagr']:+.2f}%",
            "Kell MaxDD": f"{kell_metrics['max_dd_pct']:.2f}%",
            "Kell PF": f"{kell_metrics['profit_factor']:.2f}",
            "Kell WR%": f"{kell_metrics['win_rate']:.1f}% ({kell_metrics['total_trades']}T)",
            "Kell (10EMA) Ret%": f"{kell_fast_metrics['total_ret_pct']:+.2f}%",
            "Kell (10EMA) MaxDD": f"{kell_fast_metrics['max_dd_pct']:.2f}%",
            "Kell (10EMA) PF": f"{kell_fast_metrics['profit_factor']:.2f}",
        })

    df_res = pd.DataFrame(summary_rows)
    print("\n" + tabulate(df_res, headers="keys", tablefmt="fancy_grid", showindex=False))

    # Save results
    out_csv = "data/cache/oliver_kell_benchmark_results.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved benchmark results to {out_csv}")
    return df_res


if __name__ == "__main__":
    run_benchmark()
