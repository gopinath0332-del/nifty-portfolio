"""
scripts/test_fixed_vs_dynamic.py
================================
Compares Fixed Position Sizing (Profits NOT reinvested / Fixed ₹10k per trade)
vs. Dynamic Compounding (Profits fully reinvested: Sizing scales with Current Equity).

Starting Capital: ₹1,00,000 (0 external additions)
Horizons: 2026 YTD, Last 12M, Last 2 Years, Last 5 Years
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from tabulate import tabulate

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest import PortfolioBacktester, SimTrade


def run_fixed_vs_dynamic_benchmark():
    horizons = [
        ("2026 YTD", "2026-01-01", "2026-11-09"),
        ("Last 12 Months", "2025-11-10", "2026-11-09"),
        ("Last 2 Years", "2024-11-11", "2026-11-09"),
        ("Last 5 Years", "2021-11-10", "2026-11-09"),
    ]

    print("\nLoading master stock data for Nifty 500...", flush=True)
    loader = PortfolioBacktester()
    stock_dfs = loader.load_universe_data()
    print(f"Loaded {len(stock_dfs)} stocks.", flush=True)

    models = [
        ("1. Fixed Sizing (No Reinvestment: Flat ₹10k/stock)", "fixed", 10000.0, 1.25, 15.0),
        ("2. Fixed Risk on Initial ₹1L (Fixed ₹1,250 risk/trade)", "fixed_initial_equity", 10000.0, 1.25, 15.0),
        ("3. Dynamic Compounding (Current Baseline: Reinvest All Profits)", "risk_pct", 10000.0, 1.25, 15.0),
    ]

    results = []

    for h_name, start_d, end_d in horizons:
        print(f"\n=================== Horizon: {h_name} ({start_d} to {end_d}) ===================", flush=True)

        for label, mode, pos_size, risk_pct, max_pos_pct in models:
            if mode == "fixed_initial_equity":
                # Custom run: risk sizing based on initial capital ₹100k, not dynamic equity
                bt = PortfolioBacktester(
                    initial_capital=100000.0,
                    start_date=start_d,
                    end_date=end_d,
                    entry_len=50,
                    exit_len=20,
                    sizing_mode="fixed",
                    position_size=15000.0,
                )
            else:
                bt = PortfolioBacktester(
                    initial_capital=100000.0,
                    start_date=start_d,
                    end_date=end_d,
                    entry_len=50,
                    exit_len=20,
                    sizing_mode=mode,
                    position_size=pos_size,
                    risk_per_trade_pct=risk_pct,
                    max_position_size_pct=max_pos_pct,
                )

            res = bt.run(stock_dfs)
            row = {
                "Horizon": h_name,
                "Model": label,
                "Ending Equity": f"₹{res['ending_equity']:,.2f}",
                "Net Profit": f"+₹{(res['ending_equity'] - 100000.0):,.2f}",
                "Total Return": f"{res['total_return_pct']:+.2f}%",
                "CAGR": f"{res.get('cagr_pct', 0.0):.2f}%",
                "Max DD": f"{res['max_drawdown_pct']:.2f}%",
                "Profit Factor": f"{res['profit_factor']:.2f}",
                "Win Rate": f"{res.get('win_rate', 0.0):.1f}%",
                "Trades": res["total_trades"],
                "Avg Trade Size": f"₹{res.get('avg_trade_size', 0.0):,.0f}" if 'avg_trade_size' in res else "-",
            }
            results.append(row)
            print(
                f"[{label}] End Equity: ₹{res['ending_equity']:,.2f} | "
                f"Net Return: {res['total_return_pct']:+.2f}% (CAGR: {res.get('cagr_pct', 0.0):.2f}%) | "
                f"Max DD: {res['max_drawdown_pct']:.2f}% | PF: {res['profit_factor']:.2f} | Trades: {res['total_trades']}",
                flush=True,
            )

    df_res = pd.DataFrame(results)
    print("\n\n========================= FULL COMPARATIVE MATRIX: FIXED VS DYNAMIC COMPOUNDING =========================")
    print(tabulate(df_res, headers="keys", tablefmt="github", showindex=False))


if __name__ == "__main__":
    run_fixed_vs_dynamic_benchmark()
