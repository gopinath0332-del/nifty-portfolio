"""
Scratch script to benchmark 200 SMA rising conditions across all 4 standard horizons.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from scripts.backtest import PortfolioBacktester

HORIZONS = [
    ("2026 YTD", "2026-01-01", "2026-11-09"),
    ("1 Year", "2025-11-10", "2026-11-09"),
    ("2 Years", "2024-11-11", "2026-11-09"),
    ("5 Years", "2021-11-10", "2026-11-09"),
]

def load_base_dfs():
    bt = PortfolioBacktester()
    return bt.load_universe_data()

def run_tests():
    base_dfs = load_base_dfs()
    print(f"Loaded {len(base_dfs)} stock DataFrames.")

    modes = [
        ("Baseline (Close > 50 EMA > 200 SMA)", 0),
        ("200 SMA Rising (1-day slope)", 1),
        ("200 SMA Rising (20-day / 1-Mo slope)", 20),
    ]

    results = []

    for label, shift_days in modes:
        mod_dfs = {}
        for sym, df in base_dfs.items():
            d = df.copy()
            if shift_days > 0:
                rising = d["sma_200"] > d["sma_200"].shift(shift_days)
                d["is_stage_2"] = d["is_stage_2"] & rising
            mod_dfs[sym] = d

        print(f"\n================ Running Mode: {label} ================", flush=True)
        for h_name, start, end in HORIZONS:
            bt = PortfolioBacktester(
                start_date=start,
                end_date=end,
                entry_len=50,
                exit_len=20,
                use_stage_2=True,
                within_52w_pct=10.0,
            )
            res = bt.run(mod_dfs)
            wl_ratio = abs(res['avg_win_pct'] / res['avg_loss_pct']) if res['avg_loss_pct'] != 0 else 0.0
            row = {
                "Mode": label,
                "Horizon": h_name,
                "End Equity": f"Rs.{res['ending_equity']:,.2f}",
                "Total Return %": f"{res['total_return_pct']:+.2f}%",
                "CAGR %": f"{res.get('cagr_pct', 0.0):.2f}%",
                "Max DD %": f"{res['max_drawdown_pct']:.2f}%",
                "Profit Factor": f"{res['profit_factor']:.2f}",
                "Win Rate %": f"{res.get('win_rate', 0.0):.1f}%",
                "Trades": res["total_trades"],
                "Wins/Losses": f"{res.get('winning_trades', 0)}W / {res.get('losing_trades', 0)}L",
                "Win/Loss Ratio": f"{wl_ratio:.2f}x",
            }
            results.append(row)
            print(f"[{label} | {h_name}] Return: {res['total_return_pct']:+.2f}% | CAGR: {res.get('cagr_pct', 0.0):.2f}% | Max DD: {res['max_drawdown_pct']:.2f}% | PF: {res['profit_factor']:.2f} | Trades: {res['total_trades']} (WR: {res.get('win_rate', 0.0):.1f}%)", flush=True)

    res_df = pd.DataFrame(results)
    print("\n\nFULL SUMMARY TABLE:")
    print(res_df.to_string(index=False))

    # Save to a temporary CSV for easy inspection
    res_df.to_csv("data/cache/rising_200_sma_results.csv", index=False)
    print("\nSaved results to data/cache/rising_200_sma_results.csv")

if __name__ == "__main__":
    run_tests()
