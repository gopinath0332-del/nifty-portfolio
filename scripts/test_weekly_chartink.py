"""
scripts/test_weekly_chartink.py
===============================
Backtesting the User's Weekly Momentum Breakout Strategy on Nifty 500:
  Timeframe: Weekly (resampled W-FRI from daily candles)

  Entry Conditions (from Chartink Scanner):
    1. Weekly Close > 1 week ago High (Close[W] > High[W-1])
    2. Weekly % Change > 5% ((Close[W] - Close[W-1]) / Close[W-1] * 100 > 5.0)
    3. 1 week ago Close > 2 weeks ago High (Close[W-1] > High[W-2])
    4. Close >= 100 (institutional price filter)

  Exit Conditions:
    - Exit 1: Supertrend Flip (Weekly Supertrend(10, 3) and Supertrend(7, 3))
    - Exit 2A: Close below Previous Week Low (Close[W] < Low[W-1])
    - Exit 2B: Close below Previous Week Close (Close[W] < Close[W-1])
    - Exit 3: Hybrid (Supertrend Flip + -8% Hard Stop)
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


def load_and_enrich_weekly_data(st_period: int = 10, st_multiplier: float = 3.0) -> Dict[str, pd.DataFrame]:
    """Load daily candles, resample to weekly W-FRI bars, and compute all weekly indicators."""
    print("Loading and converting universe into Weekly candles...")
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

        # 1. Weekly % Change
        w["pct_change"] = ((w["close"] - w["close"].shift(1)) / w["close"].shift(1)) * 100.0

        # 2. Previous week High / Low / Close
        w["prev_high"] = w["high"].shift(1)
        w["prev_low"] = w["low"].shift(1)
        w["prev_close"] = w["close"].shift(1)
        w["prev2_high"] = w["high"].shift(2)

        # 3. Supertrend(10, 3) and Supertrend(7, 3)
        w = compute_supertrend(w, period=10, multiplier=3.0)
        w = compute_supertrend(w, period=7, multiplier=3.0)

        # 4. Weekly Volume SMA
        w["vol_sma_10"] = w["volume"].rolling(10, min_periods=5).mean()
        w["rvol"] = np.where(w["vol_sma_10"] > 0, w["volume"] / w["vol_sma_10"], 1.0)

        # 5. Weekly 52-Week High (52 weeks)
        w["high_52w"] = w["high"].rolling(52, min_periods=min(20, len(w))).max()
        w["dist_52w_high_pct"] = ((w["close"] - w["high_52w"]) / w["high_52w"]) * 100.0

        # Entry Conditions from Scanner:
        # 1. Weekly Close > 1 week ago High
        # 2. Weekly % Change > 5%
        # 3. 1 week ago Close > 2 weeks ago High
        w["signal"] = (
            (w["close"] > w["prev_high"])
            & (w["pct_change"] > 5.0)
            & (w["prev_close"] > w["prev2_high"])
            & (w["close"] >= 100.0)
        )

        weekly_dfs[sym] = w

    print(f"Loaded and converted {len(weekly_dfs)} stocks into weekly candles.")
    return weekly_dfs


class WeeklyBacktester:
    def __init__(
        self,
        exit_mode: str = "supertrend_10_3",  # "supertrend_10_3", "supertrend_7_3", "prev_low", "prev_close", "supertrend_hard_stop"
        initial_capital: float = 100000.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        allocation_pct: float = 10.0,      # 10% allocation per position (max 10 slots = 100%)
        max_position_size_pct: float = 15.0,
        max_loss_pct: Optional[float] = None, # Optional hard stop (e.g. 8.0)
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        use_market_regime: bool = False,
    ):
        self.exit_mode = exit_mode
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.allocation_pct = allocation_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_loss_pct = max_loss_pct
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None
        self.use_market_regime = use_market_regime

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

        # Weekly index regime (Nifty 500 Index resampled weekly)
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
            for _, r in w_idx.iterrows():
                index_regime_map[r["dt"]] = bool(r["close"] >= r["ema_10"])

        weekly_date_maps = {sym: df.set_index("dt") for sym, df in weekly_dfs.items()}

        cash = self.initial_capital
        positions = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []

        pending_exits = {}   # sym -> reason
        pending_entries = [] # (sym, close, score)

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
                low = float(row["low"])
                prev_high = float(row.get("prev_high", 0.0))
                prev_low = float(row.get("prev_low", 0.0))
                prev_close = float(row.get("prev_close", 0.0))
                st_10_3 = float(row.get("supertrend_10_3", 0.0))
                st_dir_10_3 = float(row.get("supertrend_dir_10_3", 1.0))
                st_7_3 = float(row.get("supertrend_7_3", 0.0))
                st_dir_7_3 = float(row.get("supertrend_dir_7_3", 1.0))
                pct_chg = float(row.get("pct_change", 0.0))
                rvol = float(row.get("rvol", 1.0))

                # Check Exits for active positions
                if sym in positions:
                    entry_px = positions[sym]["entry_price"]
                    unrealized_pnl_pct = ((close - entry_px) / entry_px) * 100.0

                    # 1. Hard Stop (if specified)
                    if self.max_loss_pct is not None and close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                        pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"

                    # 2. Exit Mode: Supertrend(10, 3) Flip
                    elif self.exit_mode == "supertrend_10_3":
                        if st_dir_10_3 == -1 or close < st_10_3:
                            pending_exits[sym] = "Supertrend(10,3) Flip"

                    # 3. Exit Mode: Supertrend(7, 3) Flip
                    elif self.exit_mode == "supertrend_7_3":
                        if st_dir_7_3 == -1 or close < st_7_3:
                            pending_exits[sym] = "Supertrend(7,3) Flip"

                    # 4. Exit Mode 2A: Close < Previous Week Low
                    elif self.exit_mode == "prev_low":
                        if prev_low > 0 and close < prev_low:
                            pending_exits[sym] = "Close < Prev Week Low"

                    # 5. Exit Mode 2B: Close < Previous Week Close
                    elif self.exit_mode == "prev_close":
                        if prev_close > 0 and close < prev_close:
                            pending_exits[sym] = "Close < Prev Week Close"

                    # 6. Exit Mode: Hybrid Supertrend + Hard Stop
                    elif self.exit_mode == "supertrend_hard_stop":
                        if st_dir_10_3 == -1 or close < st_10_3:
                            pending_exits[sym] = "Supertrend(10,3) Flip"

                # Check Entries
                elif is_market_bullish:
                    passes_filter = bool(row.get("signal", False))
                    if passes_filter:
                        # Rank by Weekly % Change * RVOL
                        score = pct_chg * rvol
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

        downside = excess_returns[excess_returns < 0]
        sortino = float(excess_returns.mean() / downside.std() * np.sqrt(52.0)) if len(downside) > 0 and downside.std() > 0 else 0.0

        n_weeks = max(len(df_eq), 1)
        ann_return = ((ending_equity / self.initial_capital) ** (52.0 / n_weeks) - 1.0) * 100.0
        calmar = abs(ann_return / max_drawdown_pct) if max_drawdown_pct != 0 else 0.0

        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0

        total_gain = sum(t.pnl for t in wins)
        total_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else 0.0

        avg_win_pct = np.mean([t.pnl_pct for t in wins]) if wins else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in losses]) if losses else 0.0
        payout_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0
        avg_hold_weeks = np.mean([t.holding_days / 7.0 for t in closed_trades]) if closed_trades else 0.0

        return {
            "ending_equity": ending_equity,
            "total_return_pct": total_return_pct,
            "cagr_pct": ann_return,
            "max_drawdown_pct": max_drawdown_pct,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "total_trades": len(closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_loss_payout": payout_ratio,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "avg_holding_weeks": avg_hold_weeks,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "closed_trades": closed_trades,
            "equity_df": df_eq,
        }


def run_benchmark():
    weekly_dfs = load_and_enrich_weekly_data()

    # Baseline daily loader for comparison
    from scripts.backtest import PortfolioBacktester
    bt_loader = PortfolioBacktester(entry_len=50, exit_len=20)
    base_dfs = bt_loader.load_universe_data()

    all_horizon_rows = []

    for h_name, start_d, end_d in HORIZONS:
        print(f"\n=======================================================")
        print(f"Running Multi-Horizon Benchmark: {h_name} ({start_d} to {end_d})")
        print(f"=======================================================")

        # 0. Baseline Daily Donchian Model
        bt_base = PortfolioBacktester(
            initial_capital=100000.0,
            entry_len=50,
            exit_len=20,
            start_date=start_d,
            end_date=end_d,
        )
        base_res = bt_base.run(base_dfs)

        # 1. Weekly Strategy: Exit 1 - Supertrend(10, 3) Flip
        bt_st10 = WeeklyBacktester(
            exit_mode="supertrend_10_3",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_st10 = bt_st10.run(weekly_dfs)

        # 2. Weekly Strategy: Exit 1 - Supertrend(7, 3) Flip
        bt_st7 = WeeklyBacktester(
            exit_mode="supertrend_7_3",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_st7 = bt_st7.run(weekly_dfs)

        # 3. Weekly Strategy: Exit 2A - Close < Prev Week Low
        bt_prev_low = WeeklyBacktester(
            exit_mode="prev_low",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_prev_low = bt_prev_low.run(weekly_dfs)

        # 4. Weekly Strategy: Exit 2B - Close < Prev Week Close
        bt_prev_close = WeeklyBacktester(
            exit_mode="prev_close",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_prev_close = bt_prev_close.run(weekly_dfs)

        # 5. Weekly Strategy: Exit 1 + Hard Stop (-8%)
        bt_st_stop = WeeklyBacktester(
            exit_mode="supertrend_hard_stop",
            max_loss_pct=8.0,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_st_stop = bt_st_stop.run(weekly_dfs)

        runs = [
            ("Baseline (Daily 50D)", "2-Tier Profit Lock & Stage 2", base_res, f"{base_res['avg_holding_days']:.1f}d"),
            ("Weekly Idea: Exit 1", "Supertrend(10,3) Flip", res_st10, f"{res_st10['avg_holding_weeks']:.1f}w"),
            ("Weekly Idea: Exit 1 (Alt)", "Supertrend(7,3) Flip", res_st7, f"{res_st7['avg_holding_weeks']:.1f}w"),
            ("Weekly Idea: Exit 2A", "Close < Prev Week Low", res_prev_low, f"{res_prev_low['avg_holding_weeks']:.1f}w"),
            ("Weekly Idea: Exit 2B", "Close < Prev Week Close", res_prev_close, f"{res_prev_close['avg_holding_weeks']:.1f}w"),
            ("Weekly Idea: Exit 1 + Stop", "ST(10,3) + -8% Stop", res_st_stop, f"{res_st_stop['avg_holding_weeks']:.1f}w"),
        ]

        table_data = []
        for strat, exit_name, r, hold_str in runs:
            row = {
                "Strategy": strat,
                "Exit Condition": exit_name,
                "Horizon": h_name,
                "Ending Equity": f"₹{r['ending_equity']:,.2f}",
                "Return %": f"{r['total_return_pct']:+.2f}%",
                "CAGR %": f"{r['cagr_pct']:.2f}%",
                "Max DD %": f"{r['max_drawdown_pct']:.2f}%",
                "Win Rate %": f"{r['win_rate']:.1f}%",
                "Profit Factor": f"{r['profit_factor']:.2f}",
                "Trades": r['total_trades'],
                "Avg Hold": hold_str,
            }
            table_data.append(row)
            all_horizon_rows.append(row)

        print(tabulate(pd.DataFrame(table_data)[["Strategy", "Exit Condition", "Ending Equity", "Return %", "CAGR %", "Max DD %", "Win Rate %", "Profit Factor", "Trades", "Avg Hold"]], headers="keys", tablefmt="github", showindex=False))

    return all_horizon_rows


if __name__ == "__main__":
    run_benchmark()
