"""
scripts/backfill_2yr_data.py
============================
Fetches and caches 2 years (~750 days, ~500 trading bars) of daily OHLCV candles
from Zerodha Kite for all Nifty 500 stocks.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.kite_client import get_kite_client
from src.market_data import MarketDataFetcher
from src.universe import UniverseManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [backfill]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill")


def main() -> None:
    config = load_config()
    kite = get_kite_client(config, validate=True)
    if not kite:
        logger.error("Kite authentication failed. Check credentials.")
        sys.exit(1)

    universe_mgr = UniverseManager(config, kite=kite)
    stocks = universe_mgr.get_stocks_with_tokens(refresh_cache=False)
    logger.info("Starting 2-year candle backfill for %d Nifty 500 stocks...", len(stocks))

    fetcher = MarketDataFetcher(config, kite=kite)
    # Ensure cache directory exists
    fetcher.cache_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0
    start_time = time.time()

    for i, stock in enumerate(stocks, 1):
        if not stock.instrument_token:
            continue

        cache_file = fetcher.cache_dir / f"{stock.symbol}_{stock.instrument_token}.csv"

        # Check if already has >= 480 rows
        if cache_file.exists():
            try:
                import pandas as pd
                df = pd.read_csv(cache_file)
                if len(df) >= 480:
                    success_count += 1
                    if i % 50 == 0:
                        logger.info("Progress: %d/%d stocks checked (cached: %d)...", i, len(stocks), success_count)
                    continue
            except Exception:
                pass

        # Fetch 750 calendar days (~500 trading bars)
        df = fetcher.fetch_daily_candles(
            instrument_token=stock.instrument_token,
            symbol=stock.symbol,
            days=750,
            use_cache=False,  # Force fetch from Kite to get full 2 years
        )

        if df is not None and not df.empty:
            df.to_csv(cache_file, index=False)
            success_count += 1
        else:
            fail_count += 1

        if i % 25 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(stocks) - i) / rate if rate > 0 else 0
            logger.info("Progress: %d/%d (%.1f%%) | Success: %d | Fail: %d | ETA: %.0fs", i, len(stocks), (i/len(stocks))*100, success_count, fail_count, eta)

    total_time = time.time() - start_time
    logger.info("Backfill complete in %.1f seconds. Successfully cached: %d | Failed: %d", total_time, success_count, fail_count)


if __name__ == "__main__":
    main()

