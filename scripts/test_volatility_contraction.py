"""
scripts/test_volatility_contraction.py
=======================================
Multi-horizon backtest investigating Volatility Contraction / Base Tightness Filters.
Tests the hypothesis that breakouts emerging from tight, low-volatility consolidations
yield higher profit factors, better win rates, or reduced drawdowns.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scripts.backtest import PortfolioBacktester

HORIZONS = [
    ("2026 YTD", "2026-01-01", "2026-11-09"),
    ("1 Year", "2025-11-10", "2026-11-09"),
    ("2 Years", "2024-11-11", "2026-11-09"),
    ("5 Years", "2021-11-10", "2026-11-09"),
]

def load_and_enrich_data():
    """Load baseline universe DataFrames and enrich with volatility contraction indicators."""
    bt_loader = PortfolioBacktester(entry_len=50, exit_len=20)
    base_dfs = bt_loader.load_universe_data()
    print(f"Loaded {len(base_dfs)} stock DataFrames. Precomputing VCP indicators...")

    enriched_dfs = {}
    for sym, df in base_dfs.items():
        d = df.copy()

        # True range already computed in indicators, let's verify or compute
        if "tr" not in d.columns:
            hl = d["high"] - d["low"]
            hcp = (d["high"] - d["close"].shift(1)).abs()
            lcp = (d["low"] - d["close"].shift(1)).abs()
            d["tr"] = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)

        # 1. Short ATR (10) vs Long ATR (50)
        d["atr_10"] = d["tr"].ewm(alpha=1.0 / 10, min_periods=10, adjust=False).mean()
        d["atr_50"] = d["tr"].ewm(alpha=1.0 / 50, min_periods=50, adjust=False).mean()
        d["atr_ratio"] = d["atr_10"] / d["atr_50"]
        # Look at the day BEFORE breakout (pre-breakout compression)
        d["atr_ratio_prev"] = d["atr_ratio"].shift(1)

        # 2. 10-day base range as % of price leading into breakout
        high_10 = d["high"].rolling(10, min_periods=10).max()
        low_10 = d["low"].rolling(10, min_periods=10).min()
        d["range_10_pct_prev"] = ((high_10.shift(1) - low_10.shift(1)) / d["close"].shift(1)) * 100.0

        # 3. 50-day channel range leading into breakout
        high_50 = d["high"].rolling(50, min_periods=50).max()
        low_50 = d["low"].rolling(50, min_periods=50).min()
        d["range_50_pct_prev"] = ((high_50.shift(1) - low_50.shift(1)) / d["close"].shift(1)) * 100.0

        # Range compression ratio (10d range / 50d range)
        d["range_ratio_prev"] = np.where(d["range_50_pct_prev"] > 0, d["range_10_pct_prev"] / d["range_50_pct_prev"], 1.0)

        # 4. Normalized ATR (ATR 14 / Close %) leading into breakout
        if "atr_14" in d.columns:
            d["norm_atr_prev"] = (d["atr_14"].shift(1) / d["close"].shift(1)) * 100.0
        else:
            d["norm_atr_prev"] = (d["atr_10"].shift(1) / d["close"].shift(1)) * 100.0

        enriched_dfs[sym] = d

    return enriched_dfs

def run_benchmarks():
    enriched_dfs = load_and_enrich_data()

    # Define filter conditions to test
    # (name, condition_func)
    variants = [
        ("Baseline (No VCP Filter)", lambda d: pd.Series(True, index=d.index)),
        ("VCP: ATR Compression (ATR10/ATR50 <= 0.90)", lambda d: d["atr_ratio_prev"] <= 0.90),
        ("VCP: ATR Compression (ATR10/ATR50 <= 0.85)", lambda d: d["atr_ratio_prev"] <= 0.85),
        ("VCP: Tight 10D Base (10D Range <= 10%)", lambda d: d["range_10_pct_prev"] <= 10.0),
        ("VCP: Tight 10D Base (10D Range <= 12%)", lambda d: d["range_10_pct_prev"] <= 12.0),
        ("VCP: Range Compression (10D/50D Range <= 0.50)", lambda d: d["range_ratio_prev"] <= 0.50),
        ("VCP: Low ATR% (ATR14/Close <= 3.5%)", lambda d: d["norm_atr_prev"] <= 3.5),
    ]

    results = []

    for var_name, filter_fn in variants:
        print(f"\n================ Running: {var_name} ================", flush=True)

        # Apply filter to copies of DataFrames by adjusting is_stage_2 (which acts as an entry gate without touching exits)
        mod_dfs = {}
        for sym, df in enriched_dfs.items():
            d = df.copy()
            cond = filter_fn(d)
            # Pass through entry gate: only allow entry if baseline stage 2 AND vcp condition met
            d["is_stage_2"] = d["is_stage_2"] & cond
            mod_dfs[sym] = d

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
                "Variant": var_name,
                "Horizon": h_name,
                "End Equity": f"Rs.{res['ending_equity']:,.2f}",
                "Ending Equity Raw": res['ending_equity'],
                "Total Return %": f"{res['total_return_pct']:+.2f}%",
                "Total Return Raw": res['total_return_pct'],
                "CAGR %": f"{res.get('cagr_pct', 0.0):.2f}%",
                "Max DD %": f"{res['max_drawdown_pct']:.2f}%",
                "Profit Factor": f"{res['profit_factor']:.2f}",
                "Win Rate %": f"{res.get('win_rate', 0.0):.1f}%",
                "Trades": res["total_trades"],
                "Wins/Losses": f"{res.get('winning_trades', 0)}W / {res.get('losing_trades', 0)}L",
                "Win/Loss Ratio": f"{wl_ratio:.2f}x",
                "Avg Win %": f"{res.get('avg_win_pct', 0.0):+.2f}%",
                "Avg Loss %": f"{res.get('avg_loss_pct', 0.0):.2f}%",
                "Avg Hold Days": f"{res.get('avg_holding_days', 0.0):.1f}d",
            }
            results.append(row)
            print(f"[{var_name} | {h_name}] Return: {res['total_return_pct']:+.2f}% | CAGR: {res.get('cagr_pct', 0.0):.2f}% | Max DD: {res['max_drawdown_pct']:.2f}% | PF: {res['profit_factor']:.2f} | Trades: {res['total_trades']} (WR: {res.get('win_rate', 0.0):.1f}%)", flush=True)

    res_df = pd.DataFrame(results)
    print("\n\nFULL SUMMARY TABLE:")
    cols_to_print = ["Variant", "Horizon", "End Equity", "Total Return %", "CAGR %", "Max DD %", "Profit Factor", "Win Rate %", "Trades", "Win/Loss Ratio"]
    print(res_df[cols_to_print].to_string(index=False))

    res_df.to_csv("data/cache/volatility_contraction_results.csv", index=False)
    print("\nSaved detailed results to data/cache/volatility_contraction_results.csv")

if __name__ == "__main__":
    run_benchmarks()
