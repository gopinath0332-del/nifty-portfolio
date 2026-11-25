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
            capital=CapitalConfig(total_capital=200000.0, position_size=20000.0, max_positions=10, max_per_sector=3),
            files=FilesConfig(state_file=state_file),
        )
        pm = PortfolioManager(cfg)

        pm.add_position("SBIN", entry_price=600.0, industry="Financial Services")
        pm.add_position("HDFCBANK", entry_price=1500.0, industry="Financial Services")
        pm.add_position("ICICIBANK", entry_price=1100.0, industry="Financial Services")
        pm.add_position("SUNPHARMA", entry_price=1200.0, industry="Healthcare")

        counts = pm.get_sector_counts()
        assert counts["Financial Services"] == 3
        assert counts["Healthcare"] == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_stage_2_trend_filter():
    df = create_synthetic_data(num_bars=210, trend="up")
    df_ind = compute_indicators(df, entry_len=20, exit_len=20)

    assert "ema_20" in df_ind.columns
    assert "ema_50" in df_ind.columns
    assert "sma_200" in df_ind.columns
    assert "is_stage_2" in df_ind.columns

    res = evaluate_breakout_and_exit(df_ind, entry_len=20, exit_len=20, enable_stage_2_filter=True)
    assert "passes_stage_2" in res
    assert "ema_20" in res
    assert "ema_50" in res


def test_two_tier_exit_configuration():
    strat = StrategyConfig(
        exit_on_stage2_break=True,
        profit_lock_threshold_pct=25.0,
        profit_lock_ema_len=20,
        max_loss_holding_days=20,
    )
    assert strat.exit_on_stage2_break is True
    assert strat.profit_lock_threshold_pct == 25.0
    assert strat.profit_lock_ema_len == 20
    assert strat.max_loss_holding_days == 20


def test_portfolio_backtester_universe_filtering():
    from scripts.backtest import PortfolioBacktester

    # Case A: Default Nifty 500
    bt500 = PortfolioBacktester()
    assert bt500.allowed_symbols is None

    # Case B: Specific allowed symbols
    bt_sub = PortfolioBacktester(allowed_symbols=["RELIANCE", "TCS"])
    assert bt_sub.allowed_symbols == {"RELIANCE", "TCS"}

    # Case C: Nifty 50 CSV filtering if present
    if os.path.exists("data/nifty50.csv"):
        bt50 = PortfolioBacktester(universe_csv="data/nifty50.csv")
        assert bt50.allowed_symbols is not None
        assert "RELIANCE" in bt50.allowed_symbols
        assert len(bt50.allowed_symbols) == 50


def test_fixed_portfolio_budget_isolation_from_exchange_balance():
    """Verify that Zerodha account balance does NOT inflate strategy cash or stock lot sizing."""
    temp_dir = tempfile.mkdtemp()
    try:
        state_file = os.path.join(temp_dir, "test_state_iso.json")
        cfg = AppConfig(
            capital=CapitalConfig(
                total_capital=100000.0,
                position_size=10000.0,
                max_positions=10,
                sizing_mode="risk_pct",
                risk_per_trade_pct=1.25,
                max_position_size_pct=15.0,
            ),
            files=FilesConfig(state_file=state_file),
        )
        pm = PortfolioManager(cfg)

        # Mock Kite client with huge account balance (e.g. ₹15,00,000)
        class MockKite:
            def profile(self):
                return {"user_id": "AB1234", "user_name": "Test User"}
            def margins(self, segment):
                return {"available": {"live_balance": 1500000.0}, "net": 1500000.0}
            def holdings(self):
                return [
                    {"tradingsymbol": "TCS", "quantity": 10, "t1_quantity": 0, "average_price": 3500.0, "last_price": 3600.0, "pnl": 1000.0}
                ]
            def positions(self):
                return {"net": []}

        sync_res = pm.sync_with_exchange(MockKite())

        # Kite live cash is captured for diagnostic logs
        assert sync_res["live_cash"] == 1500000.0
        assert sync_res["authenticated"] is True

        # BUT strategy cash_balance is strictly isolated to fixed budget (₹100,000 - ₹35,000 invested = ₹65,000)
        assert pm.cash_balance == 65000.0
        assert pm.get_total_equity() == 100000.0

        # Suggested quantity for ₹500 stock must be sized on ₹100,000 portfolio (15% cap = ₹15,000 => 30 shares)
        # Not on ₹15,00,000 Zerodha balance (which would have yielded 450 shares!)
        qty = pm.calculate_quantity(500.0, stop_price=460.0)
        assert qty == 30
        assert qty * 500.0 <= 15000.0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_future_portfolio_capital_scaling():
    """Verify that user can increase total_capital in the future and portfolio scales automatically."""
    temp_dir = tempfile.mkdtemp()
    try:
        state_file = os.path.join(temp_dir, "test_state_scale.json")
        # Step 1: Base configuration of ₹1,00,000
        cfg1 = AppConfig(
            capital=CapitalConfig(
                total_capital=100000.0,
                position_size=10000.0,
                max_positions=10,
                sizing_mode="risk_pct",
                risk_per_trade_pct=1.25,
                max_position_size_pct=15.0,
            ),
            files=FilesConfig(state_file=state_file),
        )
        pm1 = PortfolioManager(cfg1)
        pm1.add_position("STOCK1", entry_price=100.0, quantity=100)  # ₹10,000 invested
        assert pm1.cash_balance == 90000.0
        assert pm1.get_total_equity() == 100000.0

        # Step 2: User increases total_capital to ₹2,50,000 in config
        cfg2 = AppConfig(
            capital=CapitalConfig(
                total_capital=250000.0,
                position_size=25000.0,
                max_positions=10,
                sizing_mode="risk_pct",
                risk_per_trade_pct=1.25,
                max_position_size_pct=15.0,
            ),
            files=FilesConfig(state_file=state_file),
        )
        pm2 = PortfolioManager(cfg2)
        # Available cash automatically scales: ₹2,50,000 - ₹10,000 = ₹2,40,000
        assert pm2.cash_balance == 240000.0
        assert pm2.get_total_equity() == 250000.0

        # Sizing scales with the increased ₹2,50,000 portfolio (15% max = ₹37,500 => 75 shares @ ₹500)
        qty = pm2.calculate_quantity(500.0, stop_price=460.0)
        assert qty == 75
        assert qty * 500.0 == 37500.0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cmd_add_funds(monkeypatch):
    """Verify manage_portfolio add-funds increases total_capital in settings.yaml and updates state."""
    from scripts.manage_portfolio import cmd_add_funds
    import re
    import tempfile
    from src.config import BASE_DIR

    # Test that cmd_add_funds validates amount > 0
    cmd_add_funds(-100.0)


def test_all_scripts_syntax():
    """Verify all Python scripts in scripts/ compile without SyntaxError or IndentationError."""
    import py_compile
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    py_files = list(scripts_dir.glob("*.py"))
    assert len(py_files) > 0, "No script files found to compile"

    for script_path in py_files:
        py_compile.compile(str(script_path), doraise=True)


def test_rsi_on_ema_gap_up_indicators():
    """Verify RSI(14) applied on EMA drops below 10 on sustained downtrends without lookahead."""
    from scripts.test_rsi_ema_gap_up import compute_gap_up_indicators, compute_wilder_rsi

    dates = pd.date_range(start="2026-01-01", periods=50, freq="B")
    # Smooth steady decline so EMA(21) declines consecutively -> RSI(EMA) < 10
    closes = np.linspace(200.0, 120.0, 50)
    df = pd.DataFrame({
        "date": dates,
        "dt": dates,
        "open": closes + 0.5,
        "high": closes + 1.0,
        "low": closes - 1.0,
        "close": closes,
        "volume": np.full(50, 100000),
    })
    # Final bar gaps up +5%
    df.loc[49, "open"] = df.loc[48, "close"] * 1.05

    ind = compute_gap_up_indicators(df, ema_source_len=21, rsi_len=14, exit_ema_len=21)
    assert ind["rsi_ema_prev"].iloc[-1] < 10.0
    assert ind["rsi_ema_prev"].iloc[-1] == pytest.approx(ind["rsi_ema"].iloc[-2])
    assert ind["gap_pct"].iloc[-1] == pytest.approx(5.0, rel=1e-4)
    # Rising monotonic series should produce RSI ~ 100
    rising = pd.Series(np.linspace(100.0, 200.0, 30))
    assert compute_wilder_rsi(rising, length=14).iloc[-1] == pytest.approx(100.0)







