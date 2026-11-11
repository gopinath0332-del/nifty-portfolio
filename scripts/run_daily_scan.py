"""
scripts/run_daily_scan.py
=========================
Main entry point for daily strategy execution.
Scheduled to run at 15:45 IST (Monday to Friday).

Workflow:
  1. Loads configuration (.env and settings.yaml).
  2. Resolves Kite Connect credentials (via KITE_ENV_PATH if provided).
  3. Loads Nifty 500 universe and maps instrument tokens.
  4. Runs daily Donchian breakout scan + 52-week high filter.
  5. Evaluates exits on active positions.
  6. Ranks breakout candidates by Breakout% * RVOL and picks Top N for open slots.
  7. Dispatches rich actionable alerts to Discord.

CLI Flags:
  --limit N     : Limit scan to first N stocks (for fast testing).
  --use-cache   : Use cached daily candles if available (default True).
  --no-cache    : Force re-fetching of all historical candles from Zerodha.
  --no-discord  : Disable sending Discord notifications (console output only).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.discord_notifier import DiscordNotifier
from src.kite_client import get_kite_client
from src.market_data import MarketDataFetcher
from src.portfolio import PortfolioManager
from src.strategy import StrategyEngine
from src.universe import UniverseManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [daily_scan]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily_scan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nifty 500 Donchian Daily Breakout Scanner")
    parser.add_argument("--limit", type=int, default=None, help="Limit scan to first N stocks")
    parser.add_argument("--no-cache", action="store_true", help="Force fresh data from Kite API")
    parser.add_argument("--no-discord", action="store_true", help="Suppress Discord alerts")
    args = parser.parse_args()

    logger.info("==================================================")
    logger.info("Starting Nifty 500 Daily Portfolio Engine Scan")
    logger.info("==================================================")

    # 1. Load configuration
    config = load_config()

    # 2. Authenticate Kite
    kite = get_kite_client(config, validate=True)
    if not kite:
        msg = "Zerodha Kite authentication failed. Please verify credentials or run auto_login in nifty-strike-engine."
        logger.error(msg)
        if not args.no_discord and config.discord_webhook_url:
            notifier = DiscordNotifier(config.discord_webhook_url)
            notifier.notify_error(msg, context="Kite Connect Authentication")
        sys.exit(1)

    # 3. Initialize Universe & Market Data
    universe_mgr = UniverseManager(config, kite=kite)
    stocks = universe_mgr.get_stocks_with_tokens(refresh_cache=False)
    if not stocks:
        logger.error("No Nifty 500 stocks mapped with tokens. Exiting.")
        sys.exit(1)

    fetcher = MarketDataFetcher(config, kite=kite)
    portfolio = PortfolioManager(config)

    # Always sync live holdings and margins from Zerodha exchange before scanning
    logger.info("Synchronizing portfolio with live Zerodha Kite holdings and margins...")
    sync_res = portfolio.sync_with_exchange(kite)
    if sync_res.get("authenticated"):
        logger.info(
            "Live exchange sync successful: User %s | %d Demat holdings | Available Cash: ₹%s",
            sync_res.get("user_id"),
            sync_res.get("holdings_count", 0),
            f"{sync_res.get('live_cash', 0.0):,.2f}" if sync_res.get("live_cash") is not None else "N/A",
        )

    if config.live_order_placement:
        logger.info("⚡ LIVE_ORDER_PLACEMENT is ENABLED: Orders will be routed directly to exchange.")
    else:
        logger.info("🛡️ LIVE_ORDER_PLACEMENT is DISABLED: Order execution is in Safety Mode. Generating actionable Discord alerts for manual execution.")

    strategy = StrategyEngine(config, portfolio=portfolio, fetcher=fetcher)

    # 4. Run Strategy Scan
    result = strategy.run_daily_scan(
        universe=stocks,
        use_cache=not args.no_cache,
        max_stocks_to_scan=args.limit,
    )

    # 5. Fetch live CMPs from exchange for active positions to compute summary
    current_prices = {}
    if portfolio.positions:
        try:
            q_syms = [f"NSE:{s}" for s in portfolio.positions.keys()]
            quotes = kite.quote(q_syms)
            for s in portfolio.positions.keys():
                q_key = f"NSE:{s}"
                if q_key in quotes:
                    current_prices[s] = float(quotes[q_key].get("last_price", 0.0))
        except Exception as e:
            logger.warning("Could not fetch batch quotes from Kite: %s. Falling back to candle close.", e)
            for sym in portfolio.positions.keys():
                token = next((s.instrument_token for s in stocks if s.symbol == sym), None)
                if token:
                    df = fetcher.fetch_daily_candles(token, sym, days=10, use_cache=True)
                    if df is not None and not df.empty:
                        current_prices[sym] = float(df["close"].iloc[-1])

    summary = portfolio.get_portfolio_summary(current_prices=current_prices)

    # 6. Console Output
    print("\n" + "=" * 60)
    print(f"SCAN RESULTS — {result.scan_date}")
    print(f"Total Scanned: {result.total_scanned} | Breakouts Found: {result.total_breakouts_found}")
    print(f"Exits: {len(result.exits)} | Recommended Buys: {len(result.recommended_entries)}")
    print("=" * 60)

    if result.exits:
        print("\n🔴 EXITS TO CLOSE (Sell on Kite):")
        for ex in result.exits:
            print(f"  • {ex.symbol:<10} | Close: ₹{ex.close_price:.2f} | 20D Low: ₹{ex.low_20_level:.2f} | PnL: ₹{ex.pnl:+.2f} ({ex.pnl_pct:+.2f}%)")

    if result.recommended_entries:
        print("\n🟢 RECOMMENDED BUYS (Allocation: ₹20,000 each):")
        for cand in result.recommended_entries:
            print(f"  #{cand.rank:<2} {cand.symbol:<10} | CMP: ₹{cand.close_price:>8.2f} | Qty: {cand.suggested_qty:<3} (₹{cand.investment_amount:>8.2f}) | 20D High: ₹{cand.high_20_level:.2f} (+{cand.breakout_pct:.1f}%) | 52W Dist: {cand.dist_52w_pct:+.1f}% | RVOL: {cand.rvol:.1f}x | Score: {cand.composite_score:.1f}")

    if result.runner_ups:
        print(f"\n📋 RUNNER-UP BREAKOUTS ({len(result.runner_ups)}):")
        for cand in result.runner_ups[:10]:
            print(f"  #{cand.rank:<2} {cand.symbol:<10} | CMP: ₹{cand.close_price:>8.2f} | Score: {cand.composite_score:.1f} | RVOL: {cand.rvol:.1f}x")

    print("\n📊 PORTFOLIO SUMMARY:")
    print(f"  • Portfolio Value: ₹{summary['total_portfolio_value']:,.2f}")
    print(f"  • Cash Balance:    ₹{summary['cash_balance']:,.2f}")
    print(f"  • Holdings:        {summary['active_count']}/{summary['max_positions']} stocks ({summary['open_slots']} open slots)")
    print(f"  • Unrealized P&L:  ₹{summary['unrealized_pnl']:+,.2f}")
    print("=" * 60 + "\n")

    # 7. Send Discord Notification
    if not args.no_discord and config.discord_webhook_url:
        notifier = DiscordNotifier(config.discord_webhook_url)
        notifier.notify_scan_results(result, summary)
        logger.info("Dispatched scan notifications to Discord.")


if __name__ == "__main__":
    main()

