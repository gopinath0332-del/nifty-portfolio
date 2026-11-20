"""
scripts/test_weekly_ema_crossover.py
====================================
Comprehensive Multi-Horizon Backtest of Weekly 10 EMA / 20 EMA Crossover Strategy
on the Nifty 500 Universe.

User Strategy Definition:
  - Timeframe: Weekly (resampled W-FRI from daily candles)
  - Entry Condition: 10 EMA crosses above 20 EMA (Golden Cross)
  - Exit Condition: 10 EMA crosses below 20 EMA (Death Cross)

Benchmarked Strategy Variants:
  1. Pure Weekly 10/20 EMA Crossover (Raw user rules, no stop loss)
  2. Weekly 10/20 EMA Cross + Hard Stop (-8%)
  3. Weekly 10/20 EMA Cross + Hard Stop (-12%)
  4. Weekly 10/20 EMA Cross + Faster Exit: Weekly Close < 20 EMA
  5. Weekly 10/20 EMA Cross + Market Regime Filter (Nifty 500 Weekly 10 EMA >= 20 EMA)
  6. Comparison against Baseline (Daily 50-Day Donchian with 2-tier profit lock)

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


def load_and_enrich_weekly_ema_data() -> Dict[str, pd.DataFrame]:
    """Load daily candles, resample to weekly (W-FRI), and compute 10 & 20 EMA + indicators."""
    print("Loading and converting universe into Weekly candles for EMA Crossover...")
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

        if len(w) < 25:
            continue

        # Compute 10 EMA and 20 EMA on weekly closes
        w["ema_10"] = w["close"].ewm(span=10, adjust=False).mean()
        w["ema_20"] = w["close"].ewm(span=20, adjust=False).mean()

        # Shifted values for crossover detection
        w["ema_10_prev"] = w["ema_10"].shift(1)
        w["ema_20_prev"] = w["ema_20"].shift(1)

        # Crossover signals:
        # Cross above (Golden Cross): current ema_10 > ema_20 AND previous ema_10 <= ema_20
        w["cross_above"] = (w["ema_10"] > w["ema_20"]) & (w["ema_10_prev"] <= w["ema_20_prev"])

        # Cross below (Death Cross): current ema_10 < ema_20 AND previous ema_10 >= ema_20
        w["cross_below"] = (w["ema_10"] < w["ema_20"]) & (w["ema_10_prev"] >= w["ema_20_prev"])

        # Weekly % Change & RVOL
        w["pct_change"] = ((w["close"] - w["close"].shift(1)) / w["close"].shift(1)) * 100.0
        w["vol_sma_10"] = w["volume"].rolling(10, min_periods=5).mean()
        w["rvol"] = np.where(w["vol_sma_10"] > 0, w["volume"] / w["vol_sma_10"], 1.0)

        # Spread % between 10 EMA and 20 EMA
        w["ema_spread_pct"] = ((w["ema_10"] - w["ema_20"]) / w["ema_20"]) * 100.0

        # Weekly 52-Week High (52 weeks)
        w["high_52w"] = w["high"].rolling(52, min_periods=min(20, len(w))).max()
        w["dist_52w_high_pct"] = ((w["close"] - w["high_52w"]) / w["high_52w"]) * 100.0

        # Institutional price filter: Close >= 100
        w["valid_price"] = w["close"] >= 100.0

        weekly_dfs[sym] = w

    print(f"Loaded and converted {len(weekly_dfs)} stocks into weekly EMA datasets.")
    return weekly_dfs


class WeeklyEMABacktester:
    def __init__(
        self,
        exit_rule: str = "crossover",       # "crossover", "crossover_stop", "close_below_20ema"
        max_loss_pct: Optional[float] = None, # e.g. 8.0, 12.0
        min_price: float = 100.0,
        initial_capital: float = 100000.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        allocation_pct: float = 10.0,       # 10% per slot (10 slots = 100% capacity)
        max_position_size_pct: float = 15.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        use_market_regime: bool = False,
        within_52w_pct: Optional[float] = None,
        ranking_method: str = "rvol_momentum", # "rvol_momentum", "ema_spread", "dist_52w"
    ):
        self.exit_rule = exit_rule
        self.max_loss_pct = max_loss_pct
        self.min_price = min_price
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.allocation_pct = allocation_pct
        self.max_position_size_pct = max_position_size_pct
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None
        self.use_market_regime = use_market_regime
        self.within_52w_pct = within_52w_pct
        self.ranking_method = ranking_method

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

        # Nifty 500 Weekly Market Regime (Index 10 EMA >= 20 EMA)
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
                index_regime_map[r["dt"]] = bool(r["ema_10"] >= r["ema_20"])

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
                ema_10 = float(row["ema_10"])
                ema_20 = float(row["ema_20"])
                cross_above = bool(row["cross_above"])
                cross_below = bool(row["cross_below"])
                pct_chg = float(row.get("pct_change", 0.0))
                rvol = float(row.get("rvol", 1.0))
                ema_spread = float(row.get("ema_spread_pct", 0.0))
                dist_52w = float(row.get("dist_52w_high_pct", -100.0))

                # Check Exits for active positions
                if sym in positions:
                    entry_px = positions[sym]["entry_price"]
                    unrealized_pnl_pct = ((close - entry_px) / entry_px) * 100.0

                    # 1. Hard Stop (if specified)
                    if self.max_loss_pct is not None and close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                        pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"

                    # 2. Exit Rule: Weekly Close < 20 EMA
                    elif self.exit_rule == "close_below_20ema":
                        if close < ema_20:
                            pending_exits[sym] = "Close < 20 EMA"

                    # 3. Exit Rule: 10 EMA Cross Below 20 EMA (Pure Crossover)
                    elif self.exit_rule in ("crossover", "crossover_stop"):
                        if cross_below or (ema_10 < ema_20):
                            pending_exits[sym] = "10 EMA < 20 EMA Cross"

                # Check Entries
                elif is_market_bullish:
                    # Entry condition: 10 EMA crosses above 20 EMA
                    if cross_above and (close >= self.min_price):
                        if self.within_52w_pct is not None and dist_52w < -self.within_52w_pct:
                            continue
                        if self.ranking_method == "rvol_momentum":
                            score = pct_chg * rvol
                        elif self.ranking_method == "ema_spread":
                            score = ema_spread
                        elif self.ranking_method == "dist_52w":
                            score = dist_52w
                        else:
                            score = pct_chg
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
    weekly_dfs = load_and_enrich_weekly_ema_data()

    # Baseline daily loader for comparison
    from scripts.backtest import PortfolioBacktester
    bt_loader = PortfolioBacktester(entry_len=50, exit_len=20)
    base_dfs = bt_loader.load_universe_data()

    all_horizon_rows = []

    for h_name, start_d, end_d in HORIZONS:
        print(f"\n================================================================================")
        print(f"Running Multi-Horizon Benchmark: {h_name} ({start_d} to {end_d})")
        print(f"================================================================================")

        # 0. Baseline Daily Donchian Model
        bt_base = PortfolioBacktester(
            initial_capital=100000.0,
            entry_len=50,
            exit_len=20,
            start_date=start_d,
            end_date=end_d,
        )
        base_res = bt_base.run(base_dfs)

        # 1. Weekly 10/20 EMA Cross (Pure Crossover)
        bt_pure = WeeklyEMABacktester(
            exit_rule="crossover",
            max_loss_pct=None,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_pure = bt_pure.run(weekly_dfs)

        # 2. Weekly 10/20 EMA Cross + -8% Hard Stop
        bt_stop8 = WeeklyEMABacktester(
            exit_rule="crossover_stop",
            max_loss_pct=8.0,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_stop8 = bt_stop8.run(weekly_dfs)

        # 3. Weekly 10/20 EMA Cross + -12% Hard Stop
        bt_stop12 = WeeklyEMABacktester(
            exit_rule="crossover_stop",
            max_loss_pct=12.0,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_stop12 = bt_stop12.run(weekly_dfs)

        # 4. Weekly 10/20 EMA Cross + Faster Exit (Close < 20 EMA)
        bt_close20 = WeeklyEMABacktester(
            exit_rule="close_below_20ema",
            max_loss_pct=None,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_close20 = bt_close20.run(weekly_dfs)

        # 5. Weekly 10/20 EMA Cross + Market Regime Filter (Index Weekly 10 EMA >= 20 EMA)
        bt_regime = WeeklyEMABacktester(
            exit_rule="crossover",
            max_loss_pct=None,
            use_market_regime=True,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_regime = bt_regime.run(weekly_dfs)

        # 6. Weekly 10/20 EMA Cross + Fast Exit (Close < 20 EMA) + -8% Stop
        bt_fast_stop = WeeklyEMABacktester(
            exit_rule="close_below_20ema",
            max_loss_pct=8.0,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_fast_stop = bt_fast_stop.run(weekly_dfs)

        # 7. Weekly 10/20 EMA Cross + Within 15% 52W High (Leader Filter)
        bt_52w = WeeklyEMABacktester(
            exit_rule="crossover",
            within_52w_pct=15.0,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_52w = bt_52w.run(weekly_dfs)

        # 8. Weekly 10/20 EMA Cross + Within 15% 52W High + -8% Stop
        bt_52w_stop = WeeklyEMABacktester(
            exit_rule="crossover_stop",
            within_52w_pct=15.0,
            max_loss_pct=8.0,
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        res_52w_stop = bt_52w_stop.run(weekly_dfs)

        runs = [
            ("Baseline (Daily 50D Donchian)", "2-Tier Profit Lock & Stage 2", base_res, f"{base_res['avg_holding_days']:.1f}d"),
            ("Weekly 10/20 EMA Cross (Pure)", "10 EMA < 20 EMA Cross", res_pure, f"{res_pure['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA Cross + -8% Stop", "10 EMA < 20 EMA or -8% Stop", res_stop8, f"{res_stop8['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA Cross + -12% Stop", "10 EMA < 20 EMA or -12% Stop", res_stop12, f"{res_stop12['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA Cross + Fast Exit", "Weekly Close < 20 EMA", res_close20, f"{res_close20['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA Cross + Market Regime", "Pure Cross + Index 10 EMA >= 20 EMA", res_regime, f"{res_regime['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA + Fast Exit + Stop", "Close < 20 EMA or -8% Stop", res_fast_stop, f"{res_fast_stop['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA + 52W High Filter", "Pure Cross & Within 15% 52W High", res_52w, f"{res_52w['avg_holding_weeks']:.1f}w"),
            ("Weekly 10/20 EMA + 52W High + Stop", "Within 15% 52W High & -8% Stop", res_52w_stop, f"{res_52w_stop['avg_holding_weeks']:.1f}w"),
        ]

        table_data = []
        for strat, exit_name, r, hold_str in runs:
            payout = r.get("win_loss_payout")
            if payout is None:
                payout = abs(r["avg_win_pct"] / r["avg_loss_pct"]) if r.get("avg_loss_pct", 0) != 0 else 0.0
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
                "Payout Ratio": f"{payout:.2f}x",
                "Trades": r['total_trades'],
                "Avg Hold": hold_str,
            }
            table_data.append(row)
            all_horizon_rows.append(row)

        print(tabulate(
            pd.DataFrame(table_data)[["Strategy", "Exit Condition", "Ending Equity", "Return %", "CAGR %", "Max DD %", "Win Rate %", "Profit Factor", "Payout Ratio", "Trades", "Avg Hold"]],
            headers="keys",
            tablefmt="github",
            showindex=False,
        ))

    return all_horizon_rows


if __name__ == "__main__":
    run_benchmark()
