"""
scratch/test_kell_52w.py
========================
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest import PortfolioBacktester
from scripts.test_oliver_kell import OliverKellBacktester

base_engine = PortfolioBacktester()
raw_dfs = base_engine.load_universe_data(cache_dir="data/cache/daily_candles")

print("=== OLIVER KELL: 52W HIGH vs NO 52W HIGH ===")
for s_date, e_date, label in [("2026-01-01", "2026-11-09", "2026 YTD"), ("2021-11-10", "2026-11-09", "Last 5 Years")]:
    k_pure = OliverKellBacktester(start_date=s_date, end_date=e_date, within_52w_pct=None)
    m_pure, _, _ = k_pure.run(raw_dfs)

    k_52w = OliverKellBacktester(start_date=s_date, end_date=e_date, within_52w_pct=10.0)
    m_52w, _, _ = k_52w.run(raw_dfs)

    print(f"\n[{label}]")
    print(f"  WITHOUT 52W (Pure Kell): Return: {m_pure['total_ret_pct']:+.2f}%, MaxDD: {m_pure['max_dd_pct']:.2f}%, WR: {m_pure['win_rate']:.1f}%, PF: {m_pure['profit_factor']:.2f}, Trades: {m_pure['total_trades']}")
    print(f"  WITH 52W High (<=10%):   Return: {m_52w['total_ret_pct']:+.2f}%, MaxDD: {m_52w['max_dd_pct']:.2f}%, WR: {m_52w['win_rate']:.1f}%, PF: {m_52w['profit_factor']:.2f}, Trades: {m_52w['total_trades']}")
