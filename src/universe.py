"""
src/universe.py
===============
Manages the Nifty 500 stock universe, loads symbols from CSV,
and maps NSE symbols to Zerodha Kite instrument tokens.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from kiteconnect import KiteConnect

from src.config import BASE_DIR, AppConfig

logger = logging.getLogger(__name__)


@dataclass
class StockInfo:
    symbol: str
    company_name: str
    industry: str
    instrument_token: Optional[int] = None


class UniverseManager:
    """Manages Nifty 500 universe and instrument token resolution."""

    def __init__(self, config: AppConfig, kite: Optional[KiteConnect] = None):
        self.config = config
        self.kite = kite
        self.csv_path = BASE_DIR / config.files.universe_csv
        self.cache_dir = BASE_DIR / config.files.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.instruments_cache_file = self.cache_dir / "nse_instruments.json"

    def load_nifty500_symbols(self) -> List[StockInfo]:
        """Load Nifty 500 stock symbols and metadata from CSV."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Nifty 500 CSV not found at: {self.csv_path}")

        df = pd.read_csv(self.csv_path)
        stocks: List[StockInfo] = []
        for _, row in df.iterrows():
            sym = str(row.get("Symbol", "")).strip()
            if not sym or sym.lower() == "nan":
                continue
            stocks.append(
                StockInfo(
                    symbol=sym,
                    company_name=str(row.get("Company Name", sym)).strip(),
                    industry=str(row.get("Industry", "")).strip(),
                )
            )
        logger.info("Loaded %d stocks from Nifty 500 universe list", len(stocks))
        return stocks

    def get_instrument_tokens(self, refresh_cache: bool = False) -> Dict[str, int]:
        """
        Fetch or load cached mapping of NSE tradingsymbol -> instrument_token.
        """
        if not refresh_cache and self.instruments_cache_file.exists():
            try:
                with open(self.instruments_cache_file, "r", encoding="utf-8") as f:
                    token_map = json.load(f)
                    logger.info("Loaded %d instrument tokens from cache", len(token_map))
                    return {k: int(v) for k, v in token_map.items()}
            except Exception as e:
                logger.warning("Failed to load instrument cache: %s. Re-fetching.", e)

        if not self.kite:
            logger.warning("No KiteConnect client provided to fetch instrument tokens.")
            return {}

        logger.info("Fetching fresh NSE instruments list from Zerodha...")
        try:
            instruments = self.kite.instruments(self.config.execution.exchange)
            token_map: Dict[str, int] = {}
            for inst in instruments:
                sym = inst.get("tradingsymbol")
                token = inst.get("instrument_token")
                segment = inst.get("segment")
                # Filter equity cash market instruments (NSE / NSE_EQ)
                if sym and token and (segment in ("NSE", "NSE_EQ") or inst.get("instrument_type") == "EQ"):
                    token_map[sym] = int(token)

            with open(self.instruments_cache_file, "w", encoding="utf-8") as f:
                json.dump(token_map, f)

            logger.info("Cached %d NSE equity instrument tokens", len(token_map))
            return token_map
        except Exception as e:
            logger.error("Error fetching instruments from Zerodha: %s", e)
            return {}

    def get_stocks_with_tokens(self, refresh_cache: bool = False) -> List[StockInfo]:
        """Return list of Nifty 500 stocks mapped with their instrument tokens."""
        stocks = self.load_nifty500_symbols()
        token_map = self.get_instrument_tokens(refresh_cache=refresh_cache)

        mapped: List[StockInfo] = []
        unmapped = 0
        for stock in stocks:
            token = token_map.get(stock.symbol)
            if token:
                stock.instrument_token = token
                mapped.append(stock)
            else:
                unmapped += 1

        if unmapped > 0:
            logger.warning("%d stocks in Nifty 500 list could not be mapped to NSE instrument tokens", unmapped)
        logger.info("Universe ready with %d mapped Nifty 500 stocks", len(mapped))
        return mapped

