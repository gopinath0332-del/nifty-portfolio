"""
scripts/backtest.py
===================
Portfolio-level historical backtest simulator for the 20-Day Donchian Breakout
with 52-Week High Trend Filter across the Nifty 500 universe.

Simulates:
  - Starting Capital: ₹2,00,000
  - Position Sizing: ₹20,000 per stock (Max 10 concurrent positions)
  - Date Range: 2026-01-01 to Present
  - Realistic Execution: Signal generated on Day T close, executed on Day T+1 Open
  - Exits on 20-Day Low breakdown
  - Tie-breaking: Top candidates by Breakout% * RVOL
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tabulate import tabulate

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.indicators import compute_indicators


@dataclass
class SimTrade:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    invested: float
    exit_val: float
    pnl: float
    pnl_pct: float
    holding_days: int
    exit_reason: str


class PortfolioBacktester:
    def __init__(
        self,
        initial_capital: float = 200000.0,
        position_size: float = 20000.0,
        max_positions: int = 10,
        within_52w_pct: float = 10.0,
        entry_len: int = 20,
        exit_len: int = 20,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.max_positions = max_positions
        self.within_52w_pct = within_52w_pct
        self.entry_len = entry_len
        self.exit_len = exit_len
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None

    def load_universe_data(self, cache_dir: str = "data/cache/daily_candles") -> Dict[str, pd.DataFrame]:
        """Load and precompute indicators for all cached stock candles."""
        files = glob.glob(os.path.join(cache_dir, "*.csv"))
        stock_dfs = {}

        for f in files:
            try:
                base = os.path.basename(f)
                sym = base.split("_")[0]
                df = pd.read_csv(f)
                if len(df) < max(self.entry_len, self.exit_len) + 10:
                    continue

                # Standardize dates
                df["dt"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
                df = df.sort_values("dt").reset_index(drop=True)

                # Precompute indicators
                df = compute_indicators(
                    df,
                    entry_len=self.entry_len,
                    exit_len=self.exit_len,
                    lookback_52w=252,
                )
                stock_dfs[sym] = df
            except Exception:
                continue

        return stock_dfs

    def run(self, stock_dfs: Dict[str, pd.DataFrame]) -> Dict:
        """Run day-by-day chronological portfolio simulation."""
        # 1. Collect all unique trading dates across all stocks within start/end range
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

        # Build quick date -> row lookup per stock
        stock_date_maps = {}
        for sym, df in stock_dfs.items():
            stock_date_maps[sym] = df.set_index("dt")

        # Portfolio state
        cash = self.initial_capital
        positions = {}  # sym -> {qty, entry_price, entry_date, entry_dt}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []  # (date, total_equity, cash, num_positions)

        # Pending orders for execution next day at open
        pending_exits = {}   # sym -> reason
        pending_entries = [] # list of (sym, suggested_qty, score)

        for current_dt in sorted_dates:
            date_str = current_dt.strftime("%Y-%m-%d")

            # ---------------------------------------------------------
            # Step A: Execute PENDING EXITS at Today's OPEN
            # ---------------------------------------------------------
            for sym, reason in list(pending_exits.items()):
                if sym in positions and sym in stock_date_maps:
                    stk_map = stock_date_maps[sym]
                    if current_dt in stk_map.index:
                        row = stk_map.loc[current_dt]
                        open_px = float(row["open"])
                        pos = positions.pop(sym)
                        exit_val = open_px * pos["qty"]
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

            # ---------------------------------------------------------
            # Step B: Execute PENDING ENTRIES at Today's OPEN
            # ---------------------------------------------------------
            available_slots = self.max_positions - len(positions)
            for sym, _, score in pending_entries:
                if available_slots <= 0:
                    break
                if sym in positions or sym not in stock_date_maps:
                    continue

                stk_map = stock_date_maps[sym]
                if current_dt in stk_map.index:
                    row = stk_map.loc[current_dt]
                    open_px = float(row["open"])
                    if open_px <= 0:
                        continue

                    qty = int(self.position_size // open_px)
                    if qty <= 0:
                        continue

                    invested = qty * open_px
                    if cash >= invested:
                        cash -= invested
                        positions[sym] = {
                            "qty": qty,
                            "entry_price": open_px,
                            "entry_date": date_str,
                            "entry_dt": current_dt,
                            "invested": invested,
                        }
                        available_slots -= 1
            pending_entries.clear()

            # ---------------------------------------------------------
            # Step C: Evaluate TODAY'S SIGNALS on EOD CLOSE
            # ---------------------------------------------------------
            todays_candidates = []

            for sym, df_map in stock_date_maps.items():
                if current_dt not in df_map.index:
                    continue

                row = df_map.loc[current_dt]
                close = float(row["close"])
                high_20_prev = float(row.get(f"high_{self.entry_len}_prev", 0))
                low_20_prev = float(row.get(f"low_{self.exit_len}_prev", 0))
                high_52w = float(row.get("high_52w", 0))
                dist_52w = float(row.get("dist_52w_high_pct", -999))
                rvol = float(row.get("rvol", 1.0))

                # 1. Check Exit for active positions
                if sym in positions:
                    # Close < 20-Day Low of previous bars
                    if close < low_20_prev:
                        pending_exits[sym] = "20-Day Low Breakdown"

                # 2. Check Breakout Entry
                else:
                    is_breakout = close > high_20_prev
                    passes_52w = dist_52w >= -self.within_52w_pct
                    is_liquid = close >= 20.0 and float(row.get("vol_sma_20", 0)) >= 50000

                    if is_breakout and passes_52w and is_liquid:
                        breakout_pct = ((close - high_20_prev) / high_20_prev) * 100.0
                        score = breakout_pct * max(rvol, 0.1)
                        todays_candidates.append((sym, close, score))

            # Rank candidates by composite score and queue for next day open
            todays_candidates.sort(key=lambda x: x[2], reverse=True)
            pending_entries = todays_candidates

            # ---------------------------------------------------------
            # Step D: Mark-to-Market Portfolio Equity at Close
            # ---------------------------------------------------------
            open_pos_value = 0.0
            for sym, pos in positions.items():
                if sym in stock_date_maps and current_dt in stock_date_maps[sym].index:
                    c = float(stock_date_maps[sym].loc[current_dt]["close"])
                    open_pos_value += c * pos["qty"]
                else:
                    open_pos_value += pos["invested"]

            total_equity = cash + open_pos_value
            equity_curve.append((current_dt, total_equity, cash, len(positions)))

        # ---------------------------------------------------------
        # Final Summary & Statistics
        # ---------------------------------------------------------
        df_eq = pd.DataFrame(equity_curve, columns=["date", "equity", "cash", "positions"]).set_index("date")
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["drawdown"] = (df_eq["equity"] - df_eq["peak"]) / df_eq["peak"] * 100.0

        ending_equity = df_eq["equity"].iloc[-1]
        total_return_pct = ((ending_equity - self.initial_capital) / self.initial_capital) * 100.0
        max_drawdown_pct = df_eq["drawdown"].min()
        max_drawdown_amount = (df_eq["peak"] - df_eq["equity"]).max()

        # Trade metrics
        total_trades = len(closed_trades)
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        avg_trade_pnl = (sum(t.pnl for t in closed_trades) / total_trades) if total_trades > 0 else 0.0
        avg_trade_pct = (sum(t.pnl_pct for t in closed_trades) / total_trades) if total_trades > 0 else 0.0
        avg_win_pct = (sum(t.pnl_pct for t in wins) / len(wins)) if wins else 0.0
        avg_loss_pct = (sum(t.pnl_pct for t in losses) / len(losses)) if losses else 0.0
        avg_holding = (sum(t.holding_days for t in closed_trades) / total_trades) if total_trades > 0 else 0.0

        best_trade = max(closed_trades, key=lambda t: t.pnl_pct) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.pnl_pct) if closed_trades else None

        # Monthly returns
        df_monthly = df_eq["equity"].resample("ME").last().to_frame()
        df_monthly["prev"] = df_monthly["equity"].shift(1).fillna(self.initial_capital)
        df_monthly["return_pct"] = ((df_monthly["equity"] - df_monthly["prev"]) / df_monthly["prev"]) * 100.0

        return {
            "start_date": sorted_dates[0].strftime("%Y-%m-%d"),
            "end_date": sorted_dates[-1].strftime("%Y-%m-%d"),
            "initial_capital": self.initial_capital,
            "ending_equity": ending_equity,
            "net_profit": ending_equity - self.initial_capital,
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "max_drawdown_amount": max_drawdown_amount,
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "avg_trade_pnl": avg_trade_pnl,
            "avg_trade_pct": avg_trade_pct,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "avg_holding_days": avg_holding,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "closed_trades": closed_trades,
            "open_positions": positions,
            "equity_df": df_eq,
            "monthly_df": df_monthly,
        }


def print_backtest_report(res: Dict) -> None:
    print("\n" + "=" * 70)
    print(" 📈 NIFTY 500 DONCHIAN BREAKOUT PORTFOLIO BACKTEST REPORT")
    print(f" Period: {res['start_date']} to {res['end_date']} (2026 YTD)")
    print("=" * 70)

    perf_data = [
        ["Initial Capital", f"₹{res['initial_capital']:,.2f}"],
        ["Ending Portfolio Value", f"₹{res['ending_equity']:,.2f}"],
        ["Net Profit (₹)", f"₹{res['net_profit']:+,.2f}"],
        ["Total Return (%)", f"{res['total_return_pct']:+.2f}%"],
        ["Max Drawdown (%)", f"{res['max_drawdown_pct']:.2f}% (₹{res['max_drawdown_amount']:,.2f})"],
        ["Profit Factor", f"{res['profit_factor']:.2f}"],
        ["Total Closed Trades", f"{res['total_trades']}"],
        ["Winning Trades", f"{res['winning_trades']} ({res['win_rate']:.1f}%)"],
        ["Losing Trades", f"{res['losing_trades']} ({100 - res['win_rate']:.1f}%)"],
        ["Average Trade Return", f"{res['avg_trade_pct']:+.2f}% (₹{res['avg_trade_pnl']:+,.2f})"],
        ["Average Winner", f"{res['avg_win_pct']:+.2f}%"],
        ["Average Loser", f"{res['avg_loss_pct']:+.2f}%"],
        ["Win / Loss Ratio", f"{abs(res['avg_win_pct'] / res['avg_loss_pct']):.2f}" if res['avg_loss_pct'] != 0 else "N/A"],
        ["Average Holding Period", f"{res['avg_holding_days']:.1f} days"],
    ]
    print(tabulate(perf_data, tablefmt="fancy_grid"))

    if res["best_trade"]:
        bt = res["best_trade"]
        print(f"\n🌟 Best Trade:  {bt.symbol:<10} | {bt.pnl_pct:+.2f}% (+₹{bt.pnl:,.2f}) | {bt.entry_date} to {bt.exit_date} ({bt.holding_days}d)")
    if res["worst_trade"]:
        wt = res["worst_trade"]
        print(f"⚠️ Worst Trade: {wt.symbol:<10} | {wt.pnl_pct:+.2f}% (₹{wt.pnl:,.2f}) | {wt.entry_date} to {wt.exit_date} ({wt.holding_days}d)")

    # Monthly breakdown table
    monthly_rows = []
    for dt, row in res["monthly_df"].iterrows():
        m_str = dt.strftime("%B %Y")
        monthly_rows.append([m_str, f"₹{row['equity']:,.2f}", f"{row['return_pct']:+.2f}%"])
    print("\n📅 MONTHLY PERFORMANCE (2026):")
    print(tabulate(monthly_rows, headers=["Month", "End Equity", "Monthly Return"], tablefmt="grid"))

    # Top 10 Trades
    print("\n🏆 TOP 10 WINNING TRADES:")
    top_trades = sorted(res["closed_trades"], key=lambda t: t.pnl, reverse=True)[:10]
    top_rows = [
        [t.symbol, t.entry_date, t.exit_date, f"₹{t.entry_price:.1f}", f"₹{t.exit_price:.1f}", t.quantity, f"₹{t.pnl:+,.1f}", f"{t.pnl_pct:+.1f}%", f"{t.holding_days}d"]
        for t in top_trades
    ]
    print(tabulate(top_rows, headers=["Symbol", "Entry", "Exit", "Buy Px", "Sell Px", "Qty", "P&L (₹)", "P&L (%)", "Days"], tablefmt="grid"))
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Nifty 500 Donchian Portfolio")
    parser.add_argument("--start", default="2026-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--within-52w", type=float, default=10.0, help="52W High threshold pct (default: 10.0)")
    args = parser.parse_args()

    cfg = load_config()
    backtester = PortfolioBacktester(
        initial_capital=cfg.capital.total_capital,
        position_size=cfg.capital.position_size,
        max_positions=cfg.capital.max_positions,
        within_52w_pct=args.within_52w,
        entry_len=cfg.strategy.entry_len,
        exit_len=cfg.strategy.exit_len,
        start_date=args.start,
        end_date=args.end,
    )

    print(f"Loading cached Nifty 500 stock data...")
    stock_dfs = backtester.load_universe_data()
    print(f"Loaded {len(stock_dfs)} stocks with valid data. Running backtest simulation...")

    res = backtester.run(stock_dfs)
    print_backtest_report(res)


if __name__ == "__main__":
    main()
