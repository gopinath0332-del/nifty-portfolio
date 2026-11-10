"""
src/indicators.py
=================
Vectorized indicator calculations for 20-day Donchian High/Low,
52-Week High, 20-day Volume Average, Relative Volume (RVOL), and ATR.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_indicators(
    df: pd.DataFrame,
    entry_len: int = 20,
    exit_len: int = 20,
    lookback_52w: int = 252,
    atr_len: int = 14,
) -> pd.DataFrame:
    """
    Calculate all required strategy indicators on an OHLCV DataFrame.

    Required columns: ['date', 'open', 'high', 'low', 'close', 'volume']
    """
    if len(df) < max(entry_len, exit_len):
        return df

    out = df.copy()

    # Ensure numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # 1. 20-Day Donchian High & Low
    # Note: rolling max/min over 'high' and 'low'
    out[f"high_{entry_len}"] = out["high"].rolling(window=entry_len, min_periods=entry_len).max()
    out[f"low_{exit_len}"] = out["low"].rolling(window=exit_len, min_periods=exit_len).min()

    # Previous candle values (matching Pine script highestHigh[1] and lowestLow[1])
    out[f"high_{entry_len}_prev"] = out[f"high_{entry_len}"].shift(1)
    out[f"low_{exit_len}_prev"] = out[f"low_{exit_len}"].shift(1)

    # 2. 52-Week High (252 trading days)
    # min_periods set to 50 so newer listings can still compute available lookback
    out["high_52w"] = out["high"].rolling(window=lookback_52w, min_periods=min(50, len(out))).max()
    out["high_52w_prev"] = out["high_52w"].shift(1)

    # Distance from 52-Week High in %: ((Close - 52w_High) / 52w_High) * 100 (e.g. -3.5%)
    out["dist_52w_high_pct"] = ((out["close"] - out["high_52w"]) / out["high_52w"]) * 100.0

    # 3. 20-Day Average Volume & Relative Volume (RVOL)
    out["vol_sma_20"] = out["volume"].rolling(window=20, min_periods=10).mean()
    # If avg volume is 0 or NaN, rvol is 1.0
    out["rvol"] = np.where(out["vol_sma_20"] > 0, out["volume"] / out["vol_sma_20"], 1.0)

    # 4. ATR (Average True Range) using Wilder's RMA method (matching TradingView ta.atr)
    high_low = out["high"] - out["low"]
    high_close_prev = (out["high"] - out["close"].shift(1)).abs()
    low_close_prev = (out["low"] - out["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    out["tr"] = tr
    # Wilder's smoothing (alpha = 1 / atr_len)
    out[f"atr_{atr_len}"] = tr.ewm(alpha=1.0 / atr_len, min_periods=atr_len, adjust=False).mean()

    # 5. Stage 2 Trend Filter: 50 EMA and 200 SMA (Price > 50 EMA > 200 SMA)
    out["ema_50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["sma_200"] = out["close"].rolling(window=200, min_periods=min(100, len(out))).mean()
    out["is_stage_2"] = (out["close"] > out["ema_50"]) & (out["ema_50"] > out["sma_200"])

    return out


def evaluate_breakout_and_exit(
    df: pd.DataFrame,
    entry_len: int = 20,
    exit_len: int = 20,
    within_52w_pct: float = 15.0,
    enable_52w_filter: bool = True,
    enable_stage_2_filter: bool = False,
) -> dict:
    """
    Evaluate the latest daily candle for Breakout Entry and Channel Exit signals.

    Returns
    -------
    dict:
        {
            'close': float,
            'prev_close': float,
            'high_20_prev': float,
            'low_20_prev': float,
            'high_52w': float,
            'dist_52w_high_pct': float,
            'rvol': float,
            'avg_volume_20': float,
            'is_breakout': bool,
            'is_channel_exit': bool,
            'passes_52w_filter': bool,
            'is_stage_2': bool,
            'passes_stage_2': bool,
            'breakout_pct': float,
            'composite_score': float,
        }
    """
    if len(df) < max(entry_len, exit_len) + 1:
        return {"error": "Insufficient historical candles for indicator lookback"}

    latest = df.iloc[-1]

    close = float(latest["close"])
    volume = float(latest.get("volume", 0))
    high_20_prev = float(latest[f"high_{entry_len}_prev"])
    low_20_prev = float(latest[f"low_{exit_len}_prev"])
    high_52w = float(latest["high_52w"])
    dist_52w_pct = float(latest["dist_52w_high_pct"])
    rvol = float(latest["rvol"])
    vol_sma_20 = float(latest["vol_sma_20"])
    is_stage_2 = bool(latest.get("is_stage_2", False))

    # 1. Breakout condition: Close > entry_len-day High[1]
    is_breakout = close > high_20_prev

    # 2. Channel Exit condition: Close < exit_len-day Low[1]
    is_channel_exit = close < low_20_prev

    # 3. 52-Week High filter: Close within 10-15% of 52W High (i.e. dist_52w_pct >= -within_52w_pct)
    passes_52w_filter = True
    if enable_52w_filter:
        passes_52w_filter = dist_52w_pct >= -within_52w_pct

    # 4. Stage 2 Trend Filter: Price > 50 EMA > 200 SMA
    passes_stage_2 = is_stage_2 if enable_stage_2_filter else True

    # 5. Breakout % above entry_len-day high
    breakout_pct = 0.0
    if is_breakout and high_20_prev > 0:
        breakout_pct = ((close - high_20_prev) / high_20_prev) * 100.0

    # 6. Composite Ranking Score: Breakout% * RVOL
    # Higher score = stronger breakout conviction & institutional volume
    composite_score = breakout_pct * max(rvol, 0.1)

    return {
        "close": close,
        "volume": volume,
        "high_20_prev": high_20_prev,
        "low_20_prev": low_20_prev,
        "high_52w": high_52w,
        "dist_52w_high_pct": dist_52w_pct,
        "rvol": rvol,
        "vol_sma_20": vol_sma_20,
        "is_breakout": is_breakout,
        "is_channel_exit": is_channel_exit,
        "passes_52w_filter": passes_52w_filter,
        "is_stage_2": is_stage_2,
        "passes_stage_2": passes_stage_2,
        "breakout_pct": breakout_pct,
        "composite_score": composite_score,
    }

