"""
src/market_data.py
==================
Rate-limited historical daily candle fetcher for Zerodha KiteConnect.
Implements token-bucket rate limiting (3 req/sec) and daily candle caching.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from kiteconnect import KiteConnect

from src.config import BASE_DIR, AppConfig

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetches and caches daily historical OHLCV data from Zerodha Kite."""

    def __init__(self, config: AppConfig, kite: Optional[KiteConnect] = None):
        self.config = config
        self.kite = kite
        self.cache_dir = BASE_DIR / config.files.cache_dir / "daily_candles"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Zerodha allows 3 requests/sec for historical data. Sleep 0.35s = ~2.8 req/sec.
        self.request_interval = 0.35
        self.last_request_time = 0.0

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self.last_request_time = time.time()

    def fetch_daily_candles(
        self,
        instrument_token: int,
        symbol: str,
        days: int = 365,
        use_cache: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch daily OHLCV candles for a given instrument.

        Parameters
        ----------
        instrument_token : int
            Kite instrument token.
        symbol : str
            Trading symbol for caching and logging.
        days : int
            Number of calendar days of history to fetch (default 365 days ~252 trading bars).
        use_cache : bool
            Whether to read from and update local CSV cache.

        Returns
        -------
        Optional[pd.DataFrame]
            DataFrame with columns ['date', 'open', 'high', 'low', 'close', 'volume'].
        """
        cache_file = self.cache_dir / f"{symbol}_{instrument_token}.csv"
        now = datetime.now()
        # Expected latest trading day (Friday on weekends)
        if now.weekday() == 5:
            expected_dt = now - timedelta(days=1)
        elif now.weekday() == 6:
            expected_dt = now - timedelta(days=2)
        else:
            expected_dt = now
        expected_date_str = expected_dt.strftime("%Y-%m-%d")

        cached_df: Optional[pd.DataFrame] = None
        last_cached_date: Optional[str] = None

        # Check cache freshness
        if use_cache and cache_file.exists():
            try:
                cached_df = pd.read_csv(cache_file)
                if not cached_df.empty and "date" in cached_df.columns:
                    last_cached_date = str(cached_df["date"].iloc[-1]).split(" ")[0].split("T")[0]
                    if last_cached_date >= expected_date_str:
                        return cached_df
            except Exception as e:
                logger.debug("Failed reading cache for %s: %s", symbol, e)
                cached_df = None
                last_cached_date = None

        if not self.kite:
            if cached_df is not None:
                return cached_df
            if cache_file.exists():
                return pd.read_csv(cache_file)
            return None

        to_date = now
        is_incremental = (
            use_cache
            and cached_df is not None
            and not cached_df.empty
            and last_cached_date is not None
            and len(cached_df) >= min(days // 2, 180)
        )
        if is_incremental:
            try:
                from_date = datetime.strptime(last_cached_date, "%Y-%m-%d") - timedelta(days=5)
            except ValueError:
                from_date = to_date - timedelta(days=days)
                is_incremental = False
        else:
            from_date = to_date - timedelta(days=days)

        self._wait_for_rate_limit()

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                records = self.kite.historical_data(
                    instrument_token=instrument_token,
                    from_date=from_date.strftime("%Y-%m-%d"),
                    to_date=to_date.strftime("%Y-%m-%d"),
                    interval="day",
                    continuous=False,
                    oi=False,
                )
                if not records:
                    return cached_df if cached_df is not None else None

                df = pd.DataFrame(records)
                # Standardize column names
                rename_map = {"date": "date", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}
                df = df[[c for c in rename_map.keys() if c in df.columns]]

                if is_incremental and cached_df is not None:
                    combined = pd.concat([cached_df, df], ignore_index=True)
                    combined["_date_key"] = combined["date"].astype(str).str.slice(0, 10)
                    combined = combined.drop_duplicates(subset=["_date_key"], keep="last")
                    combined = combined.sort_values("_date_key").drop(columns=["_date_key"]).reset_index(drop=True)
                    df = combined

                # Save to cache
                if use_cache:
                    df.to_csv(cache_file, index=False)

                return df
            except Exception as e:
                err_str = str(e).lower()
                if "too many requests" in err_str or "rate limit" in err_str:
                    sleep_time = attempt * 2.0
                    logger.warning("Rate limit hit fetching %s. Sleeping %.1fs (attempt %d/%d)", symbol, sleep_time, attempt, max_retries)
                    time.sleep(sleep_time)
                else:
                    logger.error("Error fetching historical candles for %s (%d): %s", symbol, instrument_token, e)
                    break

        return cached_df if cached_df is not None else None

