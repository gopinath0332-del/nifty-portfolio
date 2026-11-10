"""
src/kite_client.py
==================
Initializes and validates the Zerodha KiteConnect client using access tokens
retrieved either directly or via the shared environment path (e.g. nifty-strike-engine).
"""

from __future__ import annotations

import logging
from typing import Optional

from kiteconnect import KiteConnect
from kiteconnect.exceptions import TokenException

from src.config import AppConfig

logger = logging.getLogger(__name__)


def get_kite_client(config: AppConfig, validate: bool = True) -> Optional[KiteConnect]:
    """
    Build and return an authenticated KiteConnect client instance.

    Parameters
    ----------
    config : AppConfig
        Application configuration containing API key and access token.
    validate : bool
        If True, tests the session by making a lightweight profile API call.

    Returns
    -------
    Optional[KiteConnect]
        Authenticated KiteConnect object, or None if credentials are missing or invalid.
    """
    if not config.kite_api_key or not config.kite_access_token:
        logger.warning(
            "Kite API key or access token is missing. Checked local .env and KITE_ENV_PATH=%s",
            config.kite_env_path,
        )
        return None

    kite = KiteConnect(api_key=config.kite_api_key)
    kite.set_access_token(config.kite_access_token)

    if validate:
        try:
            profile = kite.profile()
            user_id = profile.get("user_id", "Unknown")
            user_name = profile.get("user_name", "")
            logger.info("Successfully authenticated with Zerodha Kite as %s (%s)", user_id, user_name)
        except TokenException as e:
            logger.error(
                "Zerodha Kite access token has expired or is invalid! (%s). "
                "Please run auto_login in nifty-strike-engine or refresh token.",
                e,
            )
            return None
        except Exception as e:
            logger.error("Failed to validate KiteConnect session: %s", e)
            return None

    return kite

