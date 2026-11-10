"""
src/config.py
=============
Configuration management for Nifty 500 Portfolio Engine.
Loads settings from config/settings.yaml and secrets from .env
(with support for KITE_ENV_PATH pointing to external .env files like nifty-strike-engine).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import dotenv_values, load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class CapitalConfig:
    total_capital: float = 200000.0
    position_size: float = 20000.0
    max_positions: int = 10


@dataclass
class StrategyConfig:
    entry_len: int = 20
    exit_len: int = 20
    enable_atr_stop: bool = False
    atr_len: int = 14
    atr_mult: float = 2.0


@dataclass
class FilterConfig:
    near_52w_high_enabled: bool = True
    within_52w_high_pct: float = 15.0
    min_stock_price: float = 20.0
    min_20d_avg_volume: int = 50000


@dataclass
class ExecutionConfig:
    schedule_time: str = "15:45"
    timezone: str = "Asia/Kolkata"
    product_type: str = "CNC"
    exchange: str = "NSE"


@dataclass
class FilesConfig:
    universe_csv: str = "data/nifty500.csv"
    state_file: str = "data/portfolio_state.json"
    cache_dir: str = "data/cache"


@dataclass
class AppConfig:
    capital: CapitalConfig = field(default_factory=CapitalConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    files: FilesConfig = field(default_factory=FilesConfig)

    # Secrets & runtime flags
    kite_api_key: str = ""
    kite_access_token: str = ""
    discord_webhook_url: str = ""
    live_order_placement: bool = False
    kite_env_path: str = ""


def load_config(config_path: str | Path | None = None, env_path: str | Path | None = None) -> AppConfig:
    """
    Load settings from YAML and secrets from .env.
    If KITE_ENV_PATH is specified in .env, values from that external .env
    (e.g., nifty-strike-engine/.env) will be merged for Zerodha authentication.
    """
    # 1. Load local .env
    local_env_file = Path(env_path) if env_path else BASE_DIR / ".env"
    if local_env_file.exists():
        load_dotenv(local_env_file, override=False)

    kite_env_path = os.getenv("KITE_ENV_PATH", "").strip()
    shared_env: Dict[str, str | None] = {}
    if kite_env_path:
        shared_file = Path(kite_env_path)
        if shared_file.exists():
            shared_env = dotenv_values(shared_file)
        else:
            # Also try relative to base dir if applicable
            alt_path = BASE_DIR / kite_env_path
            if alt_path.exists():
                shared_env = dotenv_values(alt_path)

    # 2. Extract API credentials:
    # If KITE_ENV_PATH is provided, prioritize credentials from that shared file
    # so morning auto_login token updates automatically reflect here.
    kite_api_key = (
        shared_env.get("KITE_API_KEY")
        or os.getenv("KITE_API_KEY")
        or ""
    ).strip()

    kite_access_token = (
        shared_env.get("KITE_ACCESS_TOKEN")
        or os.getenv("KITE_ACCESS_TOKEN")
        or ""
    ).strip()

    discord_webhook_url = (
        os.getenv("DISCORD_WEBHOOK_URL")
        or shared_env.get("DISCORD_WEBHOOK_URL")
        or ""
    ).strip()

    live_order_placement = os.getenv("LIVE_ORDER_PLACEMENT", "false").strip().lower() in ("true", "1", "yes")

    # 3. Load settings.yaml
    cfg_file = Path(config_path) if config_path else BASE_DIR / "config" / "settings.yaml"
    raw_cfg: Dict[str, Any] = {}
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f) or {}

    capital_data = raw_cfg.get("capital", {})
    strategy_data = raw_cfg.get("strategy", {})
    filter_data = raw_cfg.get("filters", {})
    exec_data = raw_cfg.get("execution", {})
    files_data = raw_cfg.get("files", {})

    return AppConfig(
        capital=CapitalConfig(
            total_capital=float(capital_data.get("total_capital", 200000.0)),
            position_size=float(capital_data.get("position_size", 20000.0)),
            max_positions=int(capital_data.get("max_positions", 10)),
        ),
        strategy=StrategyConfig(
            entry_len=int(strategy_data.get("entry_len", 20)),
            exit_len=int(strategy_data.get("exit_len", 20)),
            enable_atr_stop=bool(strategy_data.get("enable_atr_stop", False)),
            atr_len=int(strategy_data.get("atr_len", 14)),
            atr_mult=float(strategy_data.get("atr_mult", 2.0)),
        ),
        filters=FilterConfig(
            near_52w_high_enabled=bool(filter_data.get("near_52w_high_enabled", True)),
            within_52w_high_pct=float(filter_data.get("within_52w_high_pct", 15.0)),
            min_stock_price=float(filter_data.get("min_stock_price", 20.0)),
            min_20d_avg_volume=int(filter_data.get("min_20d_avg_volume", 50000)),
        ),
        execution=ExecutionConfig(
            schedule_time=str(exec_data.get("schedule_time", "15:45")),
            timezone=str(exec_data.get("timezone", "Asia/Kolkata")),
            product_type=str(exec_data.get("product_type", "CNC")),
            exchange=str(exec_data.get("exchange", "NSE")),
        ),
        files=FilesConfig(
            universe_csv=str(files_data.get("universe_csv", "data/nifty500.csv")),
            state_file=str(files_data.get("state_file", "data/portfolio_state.json")),
            cache_dir=str(files_data.get("cache_dir", "data/cache")),
        ),
        kite_api_key=kite_api_key,
        kite_access_token=kite_access_token,
        discord_webhook_url=discord_webhook_url,
        live_order_placement=live_order_placement,
        kite_env_path=kite_env_path,
    )

