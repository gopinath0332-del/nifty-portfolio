"""
tests/test_strategy.py
======================
Unit tests for Donchian breakout strategy, indicators, and portfolio manager.
"""

import os
import shutil
import tempfile
import numpy as np
import pandas as pd
import pytest

from src.config import AppConfig, CapitalConfig, StrategyConfig, FilterConfig, FilesConfig
from src.indicators import compute_indicators, evaluate_breakout_and_exit
from src.portfolio import PortfolioManager


def create_synthetic_data(num_bars: int = 100, trend: str = "flat") -> pd.DataFrame:
    """Generate reproducible OHLCV DataFrame."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=num_bars, freq="B")

    base = 100.0
    prices = [base]
    for _ in range(num_bars - 1):
        drift = 0.5 if trend == "up" else (-0.5 if trend == "down" else 0.0)
        change = np.random.normal(loc=drift, scale=1.0)
        prices.append(max(10.0, prices[-1] + change))

    prices = np.array(prices)
    highs = prices + np.random.uniform(0.5, 2.0, num_bars)
    lows = prices - np.random.uniform(0.5, 2.0, num_bars)
    opens = prices - np.random.uniform(-0.5, 0.5, num_bars)
    closes = prices.copy()
    volumes = np.random.randint(50000, 200000, num_bars)

    return pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def test_indicator_calculations():
    df = create_synthetic_data(num_bars=60)
    df_ind = compute_indicators(df, entry_len=20, exit_len=20, lookback_52w=252)

    assert "high_20" in df_ind.columns
    assert "low_20" in df_ind.columns
    assert "high_20_prev" in df_ind.columns
    assert "low_20_prev" in df_ind.columns
    assert "high_52w" in df_ind.columns
    assert "rvol" in df_ind.columns

    # Verify high_20_prev matches high_20 shifted by 1
    assert df_ind["high_20_prev"].iloc[30] == df_ind["high_20"].iloc[29]
    assert df_ind["low_20_prev"].iloc[30] == df_ind["low_20"].iloc[29]


def test_breakout_detection():
    df = create_synthetic_data(num_bars=40)
    # Set the latest close to be above the 20-day high of previous 20 bars
    max_prev_high = df["high"].iloc[-21:-1].max()

    # Case A: Breakout
    df.iloc[-1, df.columns.get_loc("close")] = max_prev_high + 5.0
    df_ind = compute_indicators(df, entry_len=20, exit_len=20)
    res = evaluate_breakout_and_exit(df_ind, entry_len=20, exit_len=20)

    assert res["is_breakout"] is True
    assert res["breakout_pct"] > 0
    assert res["composite_score"] > 0

    # Case B: No Breakout
    df.iloc[-1, df.columns.get_loc("close")] = max_prev_high - 2.0
    df_ind = compute_indicators(df, entry_len=20, exit_len=20)
    res = evaluate_breakout_and_exit(df_ind, entry_len=20, exit_len=20)

    assert res["is_breakout"] is False
    assert res["breakout_pct"] == 0.0


def test_channel_exit_detection():
    df = create_synthetic_data(num_bars=40)
    min_prev_low = df["low"].iloc[-21:-1].min()

    # Case: Close below 20-day low of previous 20 bars
    df.iloc[-1, df.columns.get_loc("close")] = min_prev_low - 3.0
    df_ind = compute_indicators(df, entry_len=20, exit_len=20)
    res = evaluate_breakout_and_exit(df_ind, entry_len=20, exit_len=20)

    assert res["is_channel_exit"] is True


def test_52w_high_filter():
    df = create_synthetic_data(num_bars=60)
    # Simulate a stock that is 25% below its 52W high
    highest = 200.0
    df.iloc[10, df.columns.get_loc("high")] = highest
    df.iloc[-1, df.columns.get_loc("close")] = 140.0  # 30% below 200

    df_ind = compute_indicators(df, entry_len=20, exit_len=20)
    res = evaluate_breakout_and_exit(df_ind, within_52w_pct=15.0, enable_52w_filter=True)

    assert res["passes_52w_filter"] is False

    # Simulate stock within 5% of 52W high
    df.iloc[-1, df.columns.get_loc("close")] = 195.0  # 2.5% below 200
    df_ind = compute_indicators(df, entry_len=20, exit_len=20)
    res = evaluate_breakout_and_exit(df_ind, within_52w_pct=15.0, enable_52w_filter=True)

    assert res["passes_52w_filter"] is True


def test_portfolio_manager_sizing_and_limits():
    temp_dir = tempfile.mkdtemp()
    try:
        state_file = os.path.join(temp_dir, "test_state.json")
        cfg = AppConfig(
            capital=CapitalConfig(total_capital=200000.0, position_size=20000.0, max_positions=10),
            files=FilesConfig(state_file=state_file),
        )
        pm = PortfolioManager(cfg)

        # 1. Quantity sizing: ₹20,000 / ₹500 = 40 shares
        qty = pm.calculate_quantity(500.0)
        assert qty == 40

        # ₹20,000 / ₹3,000 = 6 shares
        qty2 = pm.calculate_quantity(3000.0)
        assert qty2 == 6

        # 2. Add position
        pos = pm.add_position("RELIANCE", entry_price=2500.0, quantity=8)
        assert pos is not None
        assert pos.symbol == "RELIANCE"
        assert pos.invested_amount == 20000.0
        assert pm.open_slots == 9
        assert pm.cash_balance == 180000.0

        # Duplicate check
        dup = pm.add_position("RELIANCE", entry_price=2600.0)
        assert dup is None

        # 3. Close position with profit
        trade = pm.close_position("RELIANCE", exit_price=2750.0)
        assert trade is not None
        assert trade.pnl == 2000.0  # (2750 - 2500) * 8 = 2000
        assert trade.pnl_pct == 10.0
        assert pm.open_slots == 10
        assert pm.cash_balance == 202000.0

        # 4. Fill to 10 stocks and test capacity limit
        for i in range(10):
            sym = f"STOCK_{i}"
            pm.add_position(sym, entry_price=100.0, quantity=200)

        assert pm.open_slots == 0
        overflow = pm.add_position("STOCK_11", entry_price=100.0, quantity=200)
        assert overflow is None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sector_diversification_tracking():
    temp_dir = tempfile.mkdtemp()
    try:
        state_file = os.path.join(temp_dir, "test_state_sec.json")
        cfg = AppConfig(
            capital=CapitalConfig(total_capital=200000.0, position_size=20000.0, max_positions=10, max_per_sector=2),
            files=FilesConfig(state_file=state_file),
        )
        pm = PortfolioManager(cfg)

        pm.add_position("SBIN", entry_price=600.0, industry="Financial Services")
        pm.add_position("HDFCBANK", entry_price=1500.0, industry="Financial Services")
        pm.add_position("SUNPHARMA", entry_price=1200.0, industry="Healthcare")

        counts = pm.get_sector_counts()
        assert counts["Financial Services"] == 2
        assert counts["Healthcare"] == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_stage_2_trend_filter():
    df = create_synthetic_data(num_bars=210, trend="up")
    df_ind = compute_indicators(df, entry_len=20, exit_len=20)

    assert "ema_50" in df_ind.columns
    assert "sma_200" in df_ind.columns
    assert "is_stage_2" in df_ind.columns

    res = evaluate_breakout_and_exit(df_ind, entry_len=20, exit_len=20, enable_stage_2_filter=True)
    assert "passes_stage_2" in res


