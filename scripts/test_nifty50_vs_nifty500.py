"""
scripts/test_nifty50_vs_nifty500.py
===================================
Benchmarking the Turtle System 2 Trend-Following Strategy:
Nifty 50 Universe vs. Nifty 500 Master Universe across 4 Standard Horizons:
  - 2026 YTD (2026-01-01 to 2026-11-09)
  - Last 12 Months (2025-11-10 to 2026-11-09)
  - Last 2 Years (2024-11-11 to 2026-11-09)
  - Last 5 Years (2021-11-10 to 2026-11-09)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from tabulate import tabulate

from src.config import load_config
from scripts.backtest import PortfolioBacktester

HORIZONS = [
    ("2026 YTD", "2026-01-01", "2026-11-09"),
    ("Last 12M", "2025-11-10", "2026-11-09"),
    ("Last 2Y", "2024-11-11", "2026-11-09"),
    ("Last 5Y", "2021-11-10", "2026-11-09"),
]

UNIVERSES = [
    ("Nifty 500", "data/nifty500.csv"),
    ("Nifty 50", "data/nifty50.csv"),
]


def run_benchmark():
    cfg = load_config()

    print("========================================================================")
    print("  NIFTY 50 vs. NIFTY 500 PORTFOLIO STRATEGY BENCHMARK")
    print("========================================================================")

    # Pre-load universe datasets
    loaded_data = {}
    for u_name, u_path in UNIVERSES:
        print(f"\n[Data Load] Loading candles for {u_name} from {u_path}...", flush=True)
        bt = PortfolioBacktester(
            entry_len=cfg.strategy.entry_len,
            exit_len=cfg.strategy.exit_len,
            universe_csv=u_path,
        )
        dfs = bt.load_universe_data()
        loaded_data[u_name] = (dfs, u_path)
        print(f" -> Successfully loaded {len(dfs)} stocks with precomputed indicators for {u_name}.", flush=True)

    results = []

    for h_name, start, end in HORIZONS:
        print(f"\n========================================================================")
        print(f"  HORIZON: {h_name} ({start} to {end})")
        print(f"========================================================================")

        for u_name, _ in UNIVERSES:
            dfs, u_path = loaded_data[u_name]

            bt = PortfolioBacktester(
                initial_capital=cfg.capital.total_capital,
                position_size=cfg.capital.position_size,
                max_positions=cfg.capital.max_positions,
                max_per_sector=cfg.capital.max_per_sector,
                within_52w_pct=cfg.filters.within_52w_high_pct,
                entry_len=cfg.strategy.entry_len,
                exit_len=cfg.strategy.exit_len,
                use_market_regime=cfg.market_regime.enabled,
                index_ema_len=cfg.market_regime.ema_len,
                max_loss_pct=cfg.strategy.max_loss_stop_pct,
                sizing_mode=cfg.capital.sizing_mode,
                risk_per_trade_pct=cfg.capital.risk_per_trade_pct,
                max_position_size_pct=cfg.capital.max_position_size_pct,
                use_stage_2=cfg.filters.stage_2_trend_enabled,
                min_stock_price=cfg.filters.min_stock_price,
                exit_on_stage2_break=cfg.strategy.exit_on_stage2_break,
                profit_lock_threshold_pct=cfg.strategy.profit_lock_threshold_pct,
                profit_lock_ema_len=cfg.strategy.profit_lock_ema_len,
                max_loss_holding_days=cfg.strategy.max_loss_holding_days,
                start_date=start,
                end_date=end,
                universe_csv=u_path,
            )

            res = bt.run(dfs)

            wl_ratio = abs(res['avg_win_pct'] / res['avg_loss_pct']) if res['avg_loss_pct'] != 0 else 0.0

            row = {
                "Universe": u_name,
                "Horizon": h_name,
                "Start Date": start,
                "End Date": end,
                "Start Capital": f"₹{res.get('starting_capital', 100000.0):,.2f}",
                "Ending Equity": f"₹{res['ending_equity']:,.2f}",
                "Net Profit": f"{res['net_profit']:+,.2f}",
                "Ending Equity Raw": res['ending_equity'],
                "Total Return %": f"{res['total_return_pct']:+.2f}%",
                "Total Return Raw": res['total_return_pct'],
                "CAGR %": f"{res.get('cagr_pct', 0.0):.2f}%",
                "Max DD %": f"{res['max_drawdown_pct']:.2f}%",
                "Profit Factor": f"{res['profit_factor']:.2f}",
                "Sharpe": f"{res.get('sharpe_ratio', 0.0):.2f}",
                "Sortino": f"{res.get('sortino_ratio', 0.0):.2f}",
                "Calmar": f"{res.get('calmar_ratio', 0.0):.2f}",
                "Win Rate %": f"{res.get('win_rate', 0.0):.1f}%",
                "Total Trades": res["total_trades"],
                "Wins/Losses": f"{res.get('winning_trades', 0)}W / {res.get('losing_trades', 0)}L",
                "Win/Loss Ratio": f"{wl_ratio:.2f}x",
                "Avg Win %": f"{res.get('avg_win_pct', 0.0):+.2f}%",
                "Avg Loss %": f"{res.get('avg_loss_pct', 0.0):.2f}%",
                "Avg Hold Days": f"{res.get('avg_holding_days', 0.0):.1f}d",
                # Capital & Margin
                "Avg Invested Margin": f"₹{res.get('avg_invested_margin', 0.0):,.2f} ({res.get('avg_margin_util_pct', 0.0):.1f}%)",
                "Peak Invested Margin": f"₹{res.get('peak_invested_margin', 0.0):,.2f} ({res.get('peak_margin_util_pct', 0.0):.1f}%)",
                "Avg Cash Cushion": f"₹{res.get('avg_remaining_margin', 0.0):,.2f}",
                "Min Cash Buffer": f"₹{res.get('min_remaining_margin', 0.0):,.2f}",
                "Avg Trade Invested": f"₹{res.get('avg_trade_invested', 0.0):,.2f}",
                "Avg Rem Margin at Entry": f"₹{res.get('avg_trade_remaining_margin', 0.0):,.2f}",
                # MAE / MFE
                "Avg MFE Win %": f"+{res.get('avg_mfe_win', 0.0):.2f}%",
                "Avg MAE Win %": f"{res.get('avg_mae_win', 0.0):.2f}%",
                "Max MAE Winner %": f"{res.get('max_mae_winner', 0.0):.2f}%",
                "Capture Ratio %": f"{res.get('avg_capture_ratio', 0.0):.1f}%",
            }
            results.append(row)

            print(
                f"[{u_name:<10} | {h_name:<8}] Return: {res['total_return_pct']:>+7.2f}% | "
                f"CAGR: {res.get('cagr_pct', 0.0):>5.2f}% | Max DD: {res['max_drawdown_pct']:>6.2f}% | "
                f"PF: {res['profit_factor']:>4.2f} | Trades: {res['total_trades']:>3} "
                f"({res.get('winning_trades', 0)}W/{res.get('losing_trades', 0)}L, WR: {res.get('win_rate', 0.0):>4.1f}%) | "
                f"Avg Win: {res.get('avg_win_pct', 0.0):>+6.2f}% / Avg Loss: {res.get('avg_loss_pct', 0.0):>5.2f}%",
                flush=True
            )

    df_res = pd.DataFrame(results)
    out_csv = "data/cache/nifty50_vs_nifty500_results.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\n[Output] Saved full benchmark results to {out_csv}")

    # Print Comparative Matrix Table
    print("\n" + "=" * 95)
    print("  COMPARATIVE PERFORMANCE MATRIX: NIFTY 50 vs. NIFTY 500")
    print("=" * 95)
    summary_cols = [
        "Universe", "Horizon", "Ending Equity", "Total Return %", "CAGR %",
        "Max DD %", "Profit Factor", "Sharpe", "Total Trades", "Win Rate %",
        "Win/Loss Ratio", "Avg Win %", "Avg Loss %", "Avg Hold Days"
    ]
    print(tabulate(df_res[summary_cols], headers=summary_cols, tablefmt="fancy_grid", showindex=False))

    print("\n" + "=" * 95)
    print("  MARGIN & CAPITAL ALLOCATION COMPARISON")
    print("=" * 95)
    margin_cols = [
        "Universe", "Horizon", "Avg Invested Margin", "Peak Invested Margin",
        "Avg Cash Cushion", "Min Cash Buffer", "Avg Trade Invested"
    ]
    print(tabulate(df_res[margin_cols], headers=margin_cols, tablefmt="grid", showindex=False))


if __name__ == "__main__":
    run_benchmark()
