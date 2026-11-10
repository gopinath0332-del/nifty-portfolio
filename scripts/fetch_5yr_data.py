"""
scripts/fetch_5yr_data.py
=========================
Fetches and caches ~5.5 years (June 1, 2021 to Present) of daily candles
for all Nifty 500 constituents and the Nifty 500 Index from Zerodha Kite Connect.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
from kiteconnect import KiteConnect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.universe import UniverseManager

def fetch_5yr_universe():
    cfg = load_config()
    if not cfg.kite_api_key or not cfg.kite_access_token:
        print("Error: Kite credentials not configured.")
        return

    kc = KiteConnect(api_key=cfg.kite_api_key)
    kc.set_access_token(cfg.kite_access_token)

    um = UniverseManager(cfg, kc)
    universe = um.get_stocks_with_tokens()
    print(f"Loaded {len(universe)} stocks with mapped instrument tokens.")

    start_date = datetime(2021, 6, 1)
    end_date = datetime.now()

    cache_dir = Path("data/cache/daily_candles")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch Nifty 500 Index
    idx_token = cfg.market_regime.index_token
    idx_file = Path("data/cache/NIFTY500_INDEX.csv")
    print(f"Fetching Nifty 500 Index (Token: {idx_token}) from {start_date.strftime('%Y-%m-%d')}...")
    try:
        idx_data = kc.historical_data(idx_token, from_date=start_date, to_date=end_date, interval="day")
        if idx_data:
            df_idx = pd.DataFrame(idx_data)
            df_idx.to_csv(idx_file, index=False)
            print(f"✅ Saved Nifty 500 Index: {len(df_idx)} bars to {idx_file}")
    except Exception as e:
        print(f"Failed to fetch index: {e}")

    # 2. Fetch all stocks
    total = len(universe)
    success = 0
    errors = 0

    print(f"\nStarting download of {total} stocks from Kite Connect (rate limit: 3 req/sec)...")
    t0 = time.time()

    for idx, stock in enumerate(universe, 1):
        sym = stock.symbol
        token = stock.instrument_token
        if not token:
            continue

        out_path = cache_dir / f"{sym}_{token}.csv"
        try:
            candles = kc.historical_data(token, from_date=start_date, to_date=end_date, interval="day")
            if candles:
                df = pd.DataFrame(candles)
                df.to_csv(out_path, index=False)
                success += 1
            if idx % 25 == 0 or idx == total:
                elapsed = time.time() - t0
                rate = idx / elapsed if elapsed > 0 else 0
                print(f"[{idx}/{total}] Fetched {sym:<12} ({len(candles) if candles else 0} bars) | Rate: {rate:.1f} req/s | Elapsed: {elapsed:.0f}s")
        except Exception as e:
            errors += 1
            print(f"[{idx}/{total}] Error fetching {sym}: {e}")

        # Rate limit to ~2.8 requests per second
        time.sleep(0.35)

    total_time = time.time() - t0
    print(f"\n🎉 Download Complete! Successfully fetched {success}/{total} stocks in {total_time:.1f}s (~{total_time/60:.1f} min). Errors: {errors}")

if __name__ == "__main__":
    fetch_5yr_universe()
