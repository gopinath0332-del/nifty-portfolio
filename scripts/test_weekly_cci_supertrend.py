"""
scripts/test_weekly_cci_supertrend.py
=====================================
Comprehensive Multi-Horizon Backtest of Weekly CCI + 200 EMA + Supertrend Strategy
on the Nifty 500 Universe.

User Strategy Definition:
  - Timeframe: Weekly (resampled W-FRI from daily candles)
  - Entry Condition:
      1. Commodity Channel Index (CCI) crosses above -100 (CCI[t] > -100 and CCI[t-1] <= -100)
      2. Price > 200 EMA
  - Exit Condition & Research Problem:
      "exit when supertrend indicator show sell signal (sometimes supertrend is sell in when cci shows entry) or suggesst me a exit idea ."

Tested Strategy Variants:
  1. Var 1 (Raw Supertrend Flip): Wait for Supertrend to turn BUY, then exit on first SELL flip. (No stop loss)
  2. Var 2 (Supertrend Flip + Hard Stop): Supertrend SELL flip (latched) + -8.0% hard stop.
  3. Var 3 (Supertrend Confluence): Enter only when CCI crosses -100 AND Supertrend is BUY (or turns BUY); exit on Supertrend SELL flip + -8% stop.
  4. Var 4 (CCI Exhaustion Mean Reversion): Exit when CCI crosses above +100 and drops below +100 + -8% stop.
  5. Var 5 (Weekly Moving Average Exit): Exit when Weekly Close < 20 EMA + -8% stop.
  6. Var 6 (Institutional 2-Tier Profit-Lock): -8% stop; if gain >= +25%, exit when Close < 10 EMA; otherwise Supertrend SELL flip.
  7. Comparison against Baseline (Daily 50-Day Donchian with 2-tier profit lock).

Horizons:
  - 2026 YTD (2026-01-01 to 2026-11-09)
  - Last 12 Months (2025-11-10 to 2026-11-09)
  - Last 2 Years (2024-11-11 to 2026-11-09)
  - Last 5 Years (2021-11-10 to 2026-11-09)
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


def compute_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Compute exact TradingView / Chartink Supertrend(period, multiplier)."""
    hl2 = (df["high"] + df["low"]) / 2.0
    hl = df["high"] - df["low"]
    hcp = (df["high"] - df["close"].shift(1)).abs()
    lcp = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    n = len(df)
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    direction = np.ones(n)

    close = df["close"].values
    bu = basic_upper.values
    bl = basic_lower.values

    start_idx = period
    final_upper[:start_idx] = bu[:start_idx]
    final_lower[:start_idx] = bl[:start_idx]
    supertrend[:start_idx] = bl[:start_idx]

    for i in range(start_idx, n):
        # Lower band
        if bl[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = bl[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Upper band
        if bu[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = bu[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Direction & Supertrend
        if direction[i - 1] == 1:
            if close[i] < final_lower[i]:
                direction[i] = -1
                supertrend[i] = final_upper[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lower[i]
        else:
            if close[i] > final_upper[i]:
                direction[i] = 1
                supertrend[i] = final_lower[i]
            else:
                direction[i] = -1
                supertrend[i] = final_upper[i]

    df[f"supertrend_{period}_{int(multiplier)}"] = supertrend
    df[f"supertrend_dir_{period}_{int(multiplier)}"] = direction
    return df


def compute_cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Compute Commodity Channel Index (CCI)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    sma_tp = tp.rolling(period, min_periods=period).mean()
    # Mean absolute deviation
    mad = tp.rolling(period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    # Avoid division by zero
    mad = mad.replace(0, np.nan)
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci


def load_and_enrich_weekly_data(
    cci_period: int = 20,
    st_period: int = 10,
    st_multiplier: float = 3.0,
) -> Dict[str, pd.DataFrame]:
    """Load daily candles, resample to weekly (W-FRI), and compute indicators."""
    print(f"Loading universe & computing Weekly CCI({cci_period}) + 200 EMA + Supertrend({st_period}, {st_multiplier})...")
    files = glob.glob("data/cache/daily_candles/*.csv")
    weekly_dfs = {}

    for f in files:
        base = os.path.basename(f)
        sym = base.split("_")[0]

        df = pd.read_csv(f)
        if len(df) < 60:
            continue

        df["dt"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.sort_values("dt").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Compute Daily 200 EMA mapped to weekly close
        df["daily_ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
        daily_ema_map = df.set_index("dt")["daily_ema_200"].to_dict()

        # Resample to weekly ending on Friday
        w = df.set_index("dt").resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna().reset_index()

        if len(w) < 30:
            continue

        # 1. EMAs
        w["ema_10"] = w["close"].ewm(span=10, adjust=False).mean()
        w["ema_20"] = w["close"].ewm(span=20, adjust=False).mean()
        w["ema_40"] = w["close"].ewm(span=40, adjust=False).mean()    # 40-week EMA ~= 200-day EMA
        w["ema_200"] = w["close"].ewm(span=200, adjust=False).mean()  # 200-week EMA
        w["daily_ema_200"] = w["dt"].map(daily_ema_map).bfill()

        # 2. CCI
        w["cci"] = compute_cci(w, period=cci_period)
        w["cci_prev"] = w["cci"].shift(1)
        # Entry signal: CCI crosses above -100
        w["cci_cross_above_neg100"] = (w["cci"] > -100.0) & (w["cci_prev"] <= -100.0)

        # CCI overbought reversal: drops below +100 after being above +100
        w["cci_cross_below_pos100"] = (w["cci"] < 100.0) & (w["cci_prev"] >= 100.0)

        # 3. Supertrend
        w = compute_supertrend(w, period=st_period, multiplier=st_multiplier)
        w["st_dir"] = w[f"supertrend_dir_{st_period}_{int(st_multiplier)}"]
        w["st_val"] = w[f"supertrend_{st_period}_{int(st_multiplier)}"]
        w["st_dir_prev"] = w["st_dir"].shift(1)
        w["st_flip_sell"] = (w["st_dir"] == -1) & (w["st_dir_prev"] == 1)
        w["st_flip_buy"] = (w["st_dir"] == 1) & (w["st_dir_prev"] == -1)

        # 4. Weekly % Change & RVOL
        w["pct_change"] = ((w["close"] - w["close"].shift(1)) / w["close"].shift(1)) * 100.0
        w["vol_sma_10"] = w["volume"].rolling(10, min_periods=5).mean()
        w["rvol"] = np.where(w["vol_sma_10"] > 0, w["volume"] / w["vol_sma_10"], 1.0)

        # 5. Distance to 52-Week High (52 weeks)
        w["high_52w"] = w["high"].rolling(52, min_periods=min(20, len(w))).max()
        w["dist_52w_high_pct"] = ((w["close"] - w["high_52w"]) / w["high_52w"]) * 100.0

        # Institutional filter: close >= 100
        w["valid_price"] = w["close"] >= 100.0

        weekly_dfs[sym] = w

    print(f"Loaded and enriched {len(weekly_dfs)} stocks.")
    return weekly_dfs


class WeeklyCCISupertrendBacktester:
    def __init__(
        self,
        exit_mode: str = "latched_supertrend",  # latched_supertrend, latched_supertrend_stop, supertrend_confluence, cci_exhaustion, close_below_20ema, tiered_profit_lock
        ema_filter_type: str = "40w_or_daily",  # "40w_or_daily", "weekly_200"
        initial_capital: float = 100000.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        allocation_pct: float = 10.0,
        max_position_size_pct: float = 15.0,
        max_loss_pct: Optional[float] = 8.0,
        profit_lock_threshold_pct: float = 25.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        use_market_regime: bool = True,
        min_price: float = 100.0,
    ):
        self.exit_mode = exit_mode
        self.ema_filter_type = ema_filter_type
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.allocation_pct = allocation_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_loss_pct = max_loss_pct
        self.profit_lock_threshold_pct = profit_lock_threshold_pct
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None
        self.use_market_regime = use_market_regime
        self.min_price = min_price

        self.symbol_industry_map: Dict[str, str] = {}
        if os.path.exists("data/nifty500.csv"):
            try:
                df_u = pd.read_csv("data/nifty500.csv")
                for _, r in df_u.iterrows():
                    self.symbol_industry_map[str(r["Symbol"]).strip()] = str(r["Industry"]).strip()
            except Exception:
                pass

    def run(self, weekly_dfs: Dict[str, pd.DataFrame]) -> Dict:
        # Collect all unique weekly dates
        all_dates = set()
        for df in weekly_dfs.values():
            all_dates.update(df["dt"])

        sorted_weeks = sorted(list(all_dates))
        if self.start_date:
            sorted_weeks = [d for d in sorted_weeks if d >= self.start_date]
        if self.end_date:
            sorted_weeks = [d for d in sorted_weeks if d <= self.end_date]

        if not sorted_weeks:
            raise ValueError("No weekly dates in backtest range.")

        # Nifty 500 Weekly Market Regime (Index Close >= 40 EMA or 50 EMA)
        index_regime_map = {}
        index_csv = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(index_csv):
            df_idx = pd.read_csv(index_csv)
            df_idx["dt"] = pd.to_datetime(df_idx["date"]).dt.tz_localize(None)
            df_idx = df_idx.sort_values("dt").reset_index(drop=True)
            w_idx = df_idx.set_index("dt").resample("W-FRI").agg({
                "open": "first", "high": "max", "low": "min", "close": "last"
            }).dropna().reset_index()
            w_idx["ema_10"] = w_idx["close"].ewm(span=10, adjust=False).mean()
            w_idx["ema_20"] = w_idx["close"].ewm(span=20, adjust=False).mean()
            for _, r in w_idx.iterrows():
                index_regime_map[r["dt"]] = bool(r["close"] >= r["ema_20"])

        weekly_date_maps = {sym: df.set_index("dt") for sym, df in weekly_dfs.items()}

        cash = self.initial_capital
        positions = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []

        pending_exits = {}   # sym -> reason
        pending_entries = [] # (sym, score)

        for week_idx, current_w_dt in enumerate(sorted_weeks):
            date_str = current_w_dt.strftime("%Y-%m-%d")

            # ---------------------------------------------------------
            # Step A: Execute PENDING EXITS at Open of this week
            # ---------------------------------------------------------
            for sym, reason in list(pending_exits.items()):
                if sym in positions and sym in weekly_date_maps:
                    w_map = weekly_date_maps[sym]
                    if current_w_dt in w_map.index:
                        row = w_map.loc[current_w_dt]
                        open_px = float(row["open"])
                        pos = positions.pop(sym)

                        exit_val = pos["qty"] * open_px
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_weeks = week_idx - pos["entry_week_idx"]

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
                                holding_days=holding_weeks * 7,
                                exit_reason=reason,
                            )
                        )
            pending_exits.clear()

            # ---------------------------------------------------------
            # Step B: Execute PENDING ENTRIES at Open of this week
            # ---------------------------------------------------------
            open_pos_val = sum(
                float(weekly_date_maps[s].loc[current_w_dt]["open"]) * p["qty"]
                for s, p in positions.items()
                if s in weekly_date_maps and current_w_dt in weekly_date_maps[s].index
            )
            current_equity = cash + open_pos_val
            available_slots = self.max_positions - len(positions)

            for sym, score in pending_entries:
                if available_slots <= 0:
                    break
                if sym in positions or sym not in weekly_date_maps:
                    continue

                sec = self.symbol_industry_map.get(sym, "Unknown")
                if self.max_per_sector > 0:
                    sec_count = sum(1 for p in positions.values() if p.get("industry") == sec)
                    if sec_count >= self.max_per_sector:
                        continue

                w_map = weekly_date_maps[sym]
                if current_w_dt in w_map.index:
                    row = w_map.loc[current_w_dt]
                    open_px = float(row["open"])
                    if open_px <= 0:
                        continue

                    target_alloc = current_equity * (self.allocation_pct / 100.0)
                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    alloc = min(target_alloc, max_alloc)
                    qty = int(min(alloc, cash) // open_px)

                    if qty <= 0:
                        continue

                    invested = qty * open_px
                    if cash >= invested:
                        cash -= invested
                        positions[sym] = {
                            "qty": qty,
                            "entry_price": open_px,
                            "entry_date": date_str,
                            "entry_dt": current_w_dt,
                            "entry_week_idx": week_idx,
                            "invested": invested,
                            "industry": sec,
                            "st_turned_buy": bool(row["st_dir"] == 1), # track if Supertrend reached BUY
                            "max_profit_pct": 0.0,
                        }
                        available_slots -= 1
            pending_entries.clear()

            # ---------------------------------------------------------
            # Step C: Evaluate THIS WEEK'S CANDLE at Close
            # ---------------------------------------------------------
            is_market_bullish = True
            if self.use_market_regime and index_regime_map:
                is_market_bullish = index_regime_map.get(current_w_dt, True)

            todays_candidates = []

            for sym, w_map in weekly_date_maps.items():
                if current_w_dt not in w_map.index:
                    continue

                row = w_map.loc[current_w_dt]
                close = float(row["close"])
                st_dir = int(row["st_dir"])
                st_flip_sell = bool(row["st_flip_sell"])
                cci = float(row["cci"]) if pd.notna(row["cci"]) else 0.0
                cci_cross = bool(row["cci_cross_above_neg100"])
                cci_cross_below_100 = bool(row["cci_cross_below_pos100"])
                ema_10 = float(row["ema_10"])
                ema_20 = float(row["ema_20"])
                ema_40 = float(row["ema_40"])
                ema_200 = float(row["ema_200"])
                daily_ema_200 = float(row["daily_ema_200"])
                pct_chg = float(row.get("pct_change", 0.0))
                rvol = float(row.get("rvol", 1.0))
                dist_52w = float(row.get("dist_52w_high_pct", -100.0))

                # Check 200 EMA Filter
                if self.ema_filter_type == "weekly_200":
                    above_200_ema = close > ema_200
                else:
                    above_200_ema = (close > ema_40) or (close > daily_ema_200)

                # -----------------------------
                # Check Exits for active positions
                # -----------------------------
                if sym in positions:
                    pos = positions[sym]
                    entry_px = pos["entry_price"]
                    unrealized_pnl_pct = ((close - entry_px) / entry_px) * 100.0
                    pos["max_profit_pct"] = max(pos["max_profit_pct"], unrealized_pnl_pct)

                    # Update latched Supertrend status: did it turn BUY?
                    if st_dir == 1:
                        pos["st_turned_buy"] = True

                    # 1. Hard Stop Loss (if enabled)
                    if self.max_loss_pct is not None and close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                        pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"

                    # 2. Exit Mode: Latched Supertrend Flip (Var 1 & Var 2)
                    elif self.exit_mode in ("latched_supertrend", "latched_supertrend_stop"):
                        if pos["st_turned_buy"] and (st_dir == -1 or st_flip_sell):
                            pending_exits[sym] = "Supertrend Sell Flip"

                    # 3. Exit Mode: Supertrend Confluence (Var 3)
                    elif self.exit_mode == "supertrend_confluence":
                        if st_dir == -1 or st_flip_sell:
                            pending_exits[sym] = "Supertrend Sell Flip"

                    # 4. Exit Mode: CCI Exhaustion Mean Reversion (Var 4)
                    elif self.exit_mode == "cci_exhaustion":
                        if cci_cross_below_100 or cci > 150.0:
                            pending_exits[sym] = "CCI Exhaustion / Mean Reversion"
                        elif pos["st_turned_buy"] and (st_dir == -1 or st_flip_sell):
                            pending_exits[sym] = "Supertrend Sell Flip"

                    # 5. Exit Mode: Weekly Close < 20 EMA (Var 5)
                    elif self.exit_mode == "close_below_20ema":
                        if close < ema_20:
                            pending_exits[sym] = "Close < 20 EMA"

                    # 6. Exit Mode: Tiered Profit Lock (Var 6)
                    elif self.exit_mode == "tiered_profit_lock":
                        # Tier 1: If unrealized gain >= threshold, tighten exit to Close < 10 EMA
                        if pos["max_profit_pct"] >= self.profit_lock_threshold_pct and close < ema_10:
                            pending_exits[sym] = f"Profit Lock (+{self.profit_lock_threshold_pct:.0f}% & Close < 10 EMA)"
                        # Tier 2: Supertrend Sell Flip (latched) or Close < 20 EMA
                        elif pos["st_turned_buy"] and (st_dir == -1 or st_flip_sell):
                            pending_exits[sym] = "Supertrend Sell Flip"
                        elif close < ema_20:
                            pending_exits[sym] = "Close < 20 EMA"

                # -----------------------------
                # Check Entries
                # -----------------------------
                elif is_market_bullish:
                    # User Condition: CCI crosses above -100 AND Price > 200 EMA
                    entry_cond = cci_cross and above_200_ema and (close >= self.min_price)

                    # For Var 3: only enter if Supertrend is already BUY
                    if self.exit_mode == "supertrend_confluence":
                        entry_cond = entry_cond and (st_dir == 1)

                    if entry_cond:
                        # Composite ranking: RVOL * % gain, prioritized by distance to 52W high
                        score = (pct_chg * rvol) + (dist_52w * 0.1)
                        todays_candidates.append((sym, score))

            todays_candidates.sort(key=lambda x: x[1], reverse=True)
            pending_entries = todays_candidates

            # ---------------------------------------------------------
            # Step D: Mark-to-market at Week Close
            # ---------------------------------------------------------
            open_pos_value = 0.0
            for sym, pos in positions.items():
                if sym in weekly_date_maps and current_w_dt in weekly_date_maps[sym].index:
                    c = float(weekly_date_maps[sym].loc[current_w_dt]["close"])
                    open_pos_value += c * pos["qty"]
                else:
                    open_pos_value += pos["invested"]
            total_equity = cash + open_pos_value
            equity_curve.append((current_w_dt, total_equity, cash, len(positions)))

        # Summary Metrics
        df_eq = pd.DataFrame(equity_curve, columns=["date", "equity", "cash", "positions"]).set_index("date")
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["drawdown"] = (df_eq["equity"] - df_eq["peak"]) / df_eq["peak"] * 100.0

        ending_equity = df_eq["equity"].iloc[-1]
        total_return_pct = ((ending_equity - self.initial_capital) / self.initial_capital) * 100.0
        max_drawdown_pct = df_eq["drawdown"].min()

        weekly_returns = df_eq["equity"].pct_change().dropna()
        rf_weekly = (1.0 + 0.065) ** (1.0 / 52.0) - 1.0
        excess_returns = weekly_returns - rf_weekly
        sharpe = float(excess_returns.mean() / excess_returns.std() * np.sqrt(52.0)) if excess_returns.std() > 0 else 0.0

        downside_returns = excess_returns[excess_returns < 0]
        sortino = float(excess_returns.mean() / downside_returns.std() * np.sqrt(52.0)) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0.0

        years = max((sorted_weeks[-1] - sorted_weeks[0]).days / 365.25, 0.1)
        cagr = ((ending_equity / self.initial_capital) ** (1.0 / years) - 1.0) * 100.0 if ending_equity > 0 else -100.0
        calmar = abs(cagr / max_drawdown_pct) if max_drawdown_pct < 0 else 0.0

        winners = [t for t in closed_trades if t.pnl > 0]
        losers = [t for t in closed_trades if t.pnl <= 0]
        total_trades = len(closed_trades)
        win_rate = (len(winners) / total_trades * 100.0) if total_trades > 0 else 0.0

        total_gain = sum(t.pnl for t in winners)
        total_loss = abs(sum(t.pnl for t in losers))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.0 if total_gain > 0 else 0.0)

        avg_win_pct = np.mean([t.pnl_pct for t in winners]) if winners else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in losers]) if losers else 0.0
        payout_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0

        return {
            "ending_equity": ending_equity,
            "total_return_pct": total_return_pct,
            "cagr": cagr,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "winners": len(winners),
            "losers": len(losers),
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "payout_ratio": payout_ratio,
            "closed_trades": closed_trades,
            "equity_curve": df_eq,
        }


_BASELINE_STOCK_DFS = None

def get_baseline_stock_dfs(tester: PortfolioBacktester) -> Dict[str, pd.DataFrame]:
    global _BASELINE_STOCK_DFS
    if _BASELINE_STOCK_DFS is None:
        _BASELINE_STOCK_DFS = tester.load_universe_data()
    return _BASELINE_STOCK_DFS


def run_baseline_benchmark(start_date: str, end_date: str) -> Dict:
    """Run baseline Daily 50D Donchian strategy."""
    tester = PortfolioBacktester(
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000.0,
        risk_per_trade_pct=1.25,
        max_positions=10,
        max_per_sector=3,
        entry_len=50,
        exit_len=20,
        within_52w_pct=10.0,
        use_stage_2=True,
        max_loss_pct=8.0,
        max_loss_holding_days=20,
        exit_on_stage2_break=True,
        profit_lock_threshold_pct=25.0,
    )
    stock_dfs = get_baseline_stock_dfs(tester)
    res = tester.run(stock_dfs)
    return {
        "ending_equity": res["ending_equity"],
        "total_return_pct": res["total_return_pct"],
        "cagr": res.get("cagr_pct", 0.0),
        "max_drawdown_pct": res["max_drawdown_pct"],
        "sharpe": res.get("sharpe_ratio", 0.0),
        "sortino": res.get("sortino_ratio", 0.0),
        "calmar": res.get("calmar_ratio", 0.0),
        "profit_factor": res["profit_factor"],
        "total_trades": res["total_trades"],
        "win_rate": res.get("win_rate", 0.0),
        "avg_win_pct": res.get("avg_win_pct", 0.0),
        "avg_loss_pct": res.get("avg_loss_pct", 0.0),
        "payout_ratio": abs(res["avg_win_pct"] / res["avg_loss_pct"]) if res.get("avg_loss_pct") else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-Horizon Backtest of Weekly CCI + Supertrend Strategies")
    parser.add_argument("--horizon", choices=["ytd", "12m", "2y", "5y", "all"], default="all")
    parser.add_argument("--cci-period", type=int, default=20, help="CCI period (default: 20)")
    parser.add_argument("--st-period", type=int, default=10, help="Supertrend period (default: 10)")
    parser.add_argument("--st-multiplier", type=float, default=3.0, help="Supertrend multiplier (default: 3.0)")
    args = parser.parse_args()

    weekly_dfs = load_and_enrich_weekly_data(
        cci_period=args.cci_period,
        st_period=args.st_period,
        st_multiplier=args.st_multiplier,
    )

    selected_horizons = HORIZONS
    if args.horizon == "ytd":
        selected_horizons = [HORIZONS[0]]
    elif args.horizon == "12m":
        selected_horizons = [HORIZONS[1]]
    elif args.horizon == "2y":
        selected_horizons = [HORIZONS[2]]
    elif args.horizon == "5y":
        selected_horizons = [HORIZONS[3]]

    variants = [
        ("Var 1: Raw Supertrend (No Stop)", "latched_supertrend", None, "40w_or_daily"),
        ("Var 2: Supertrend + Hard Stop (-8%)", "latched_supertrend_stop", 8.0, "40w_or_daily"),
        ("Var 3: Supertrend Confluence (Buy Filter)", "supertrend_confluence", 8.0, "40w_or_daily"),
        ("Var 4: CCI Mean Reversion Exit (+8% Stop)", "cci_exhaustion", 8.0, "40w_or_daily"),
        ("Var 5: Weekly Close < 20 EMA (+8% Stop)", "close_below_20ema", 8.0, "40w_or_daily"),
        ("Var 6: 2-Tier Profit Lock (+25% & 10 EMA)", "tiered_profit_lock", 8.0, "40w_or_daily"),
    ]

    for h_name, start_d, end_d in selected_horizons:
        print(f"\n{'=' * 110}")
        print(f"BENCHMARK HORIZON: {h_name.upper()} ({start_d} to {end_d})")
        print(f"{'=' * 110}")

        table_rows = []

        # 1. Run Baseline Strategy
        print("Running Baseline (Daily 50D Donchian)...")
        b_res = run_baseline_benchmark(start_d, end_d)
        table_rows.append([
            "Baseline: Daily 50D Donchian",
            f"₹{b_res['ending_equity']:,.2f}",
            f"{b_res['total_return_pct']:+.2f}%",
            f"{b_res['cagr']:+.2f}%",
            f"{b_res['max_drawdown_pct']:.2f}%",
            f"{b_res['profit_factor']:.2f}",
            f"{b_res['win_rate']:.1f}%",
            f"{b_res['total_trades']}",
            f"{b_res['avg_win_pct']:+.1f}% / {b_res['avg_loss_pct']:.1f}%",
            f"{b_res['payout_ratio']:.2f}x",
            f"{b_res['sharpe']:.2f}",
        ])

        # 2. Run Strategy Variants
        for v_name, exit_mode, max_loss, ema_filter in variants:
            bt = WeeklyCCISupertrendBacktester(
                exit_mode=exit_mode,
                ema_filter_type=ema_filter,
                initial_capital=100000.0,
                max_positions=10,
                max_per_sector=3,
                allocation_pct=10.0,
                max_position_size_pct=15.0,
                max_loss_pct=max_loss,
                profit_lock_threshold_pct=25.0,
                start_date=start_d,
                end_date=end_d,
                use_market_regime=True,
            )
            r = bt.run(weekly_dfs)
            table_rows.append([
                v_name,
                f"₹{r['ending_equity']:,.2f}",
                f"{r['total_return_pct']:+.2f}%",
                f"{r['cagr']:+.2f}%",
                f"{r['max_drawdown_pct']:.2f}%",
                f"{r['profit_factor']:.2f}",
                f"{r['win_rate']:.1f}%",
                f"{r['total_trades']}",
                f"{r['avg_win_pct']:+.1f}% / {r['avg_loss_pct']:.1f}%",
                f"{r['payout_ratio']:.2f}x",
                f"{r['sharpe']:.2f}",
            ])

        headers = [
            "Strategy Configuration",
            "Ending Equity",
            "Return %",
            "CAGR",
            "Max DD",
            "Profit Fac",
            "Win Rate",
            "Trades",
            "Avg W/L %",
            "Payout",
            "Sharpe",
        ]
        print(tabulate(table_rows, headers=headers, tablefmt="grid"))


if __name__ == "__main__":
    main()
