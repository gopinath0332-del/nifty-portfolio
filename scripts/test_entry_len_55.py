"""
Scratch script to benchmark entry_len = 50 vs entry_len = 55 across all 4 standard horizons.
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

def run_tests():
    entry_lens = [50, 55]
    results = []

    for el in entry_lens:
        print(f"\n================ Loading data for entry_len = {el} ================", flush=True)
        bt_loader = PortfolioBacktester(entry_len=el)
        stock_dfs = bt_loader.load_universe_data()
        print(f"Loaded {len(stock_dfs)} stock DataFrames for entry_len = {el}.", flush=True)

        for h_name, start, end in HORIZONS:
            bt = PortfolioBacktester(
                start_date=start,
                end_date=end,
                entry_len=el,
                exit_len=20,
                use_stage_2=True,
                within_52w_pct=10.0,
            )
            res = bt.run(stock_dfs)
            wl_ratio = abs(res['avg_win_pct'] / res['avg_loss_pct']) if res['avg_loss_pct'] != 0 else 0.0
            row = {
                "Entry Len": f"{el}-Day Donchian",
                "Horizon": h_name,
                "Start Date": start,
                "End Date": end,
                "End Equity": f"Rs.{res['ending_equity']:,.2f}",
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
                "Trades": res["total_trades"],
                "Wins/Losses": f"{res.get('winning_trades', 0)}W / {res.get('losing_trades', 0)}L",
                "Win/Loss Ratio": f"{wl_ratio:.2f}x",
                "Avg Win %": f"{res.get('avg_win_pct', 0.0):+.2f}%",
                "Avg Loss %": f"{res.get('avg_loss_pct', 0.0):.2f}%",
                "Avg Hold Days": f"{res.get('avg_holding_days', 0.0):.1f}d",
            }
            results.append(row)
            print(f"[entry_len={el} | {h_name}] Return: {res['total_return_pct']:+.2f}% | CAGR: {res.get('cagr_pct', 0.0):.2f}% | Max DD: {res['max_drawdown_pct']:.2f}% | PF: {res['profit_factor']:.2f} | Trades: {res['total_trades']} (WR: {res.get('win_rate', 0.0):.1f}%)", flush=True)

    res_df = pd.DataFrame(results)
    print("\n\nFULL SUMMARY TABLE:")
    cols_to_print = ["Entry Len", "Horizon", "End Equity", "Total Return %", "CAGR %", "Max DD %", "Profit Factor", "Win Rate %", "Trades", "Wins/Losses", "Win/Loss Ratio", "Avg Hold Days"]
    print(res_df[cols_to_print].to_string(index=False))

    res_df.to_csv("data/cache/entry_len_50_vs_55_results.csv", index=False)
    print("\nSaved detailed results to data/cache/entry_len_50_vs_55_results.csv")

if __name__ == "__main__":
    run_tests()
