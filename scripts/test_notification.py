"""
scripts/test_notification.py
============================
Quick test script to verify Discord webhook connectivity and embed formatting.
Supports:
  - Default: Sends a realistic mock of Exit Signals, Buy Signals, and Portfolio Summary.
  - Quick connectivity ping.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.discord_notifier import DiscordNotifier
from src.strategy import EntryCandidate, ExitSignal, ScanResult


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Discord notification formatting")
    parser.add_argument("--ping-only", action="store_true", help="Send only a minimal test ping")
    args = parser.parse_args()

    config = load_config()
    webhook_url = config.discord_webhook_url
    if not webhook_url:
        print("❌ Error: DISCORD_WEBHOOK_URL is not set in .env")
        sys.exit(1)

    print(f"Connecting to Discord webhook: {webhook_url[:45]}...")
    notifier = DiscordNotifier(webhook_url)

    if args.ping_only:
        success = notifier.send_embed(
            title="🔔 TEST PING: Nifty 500 Donchian Portfolio Engine",
            description="Discord webhook connectivity test passed.",
            color=0x10B981,
        )
        if success:
            print("✅ Discord test ping delivered!")
        else:
            print("❌ Failed to deliver ping.")
        return

    # Simulate realistic scan results matching your exact Discord setup
    mock_scan_result = ScanResult(
        scan_date="2026-11-13",
        open_slots_before=4,
        open_slots_after=4,
        exits=[
            ExitSignal(
                symbol="IPCALAB",
                company_name="Ipca Laboratories Ltd",
                close_price=1905.00,
                entry_price=1962.90,
                quantity=5,
                low_20_level=1797.00,
                exit_reason="20-Day Low Breakdown",
                pnl=-289.50,
                pnl_pct=-2.95,
            )
        ],
        recommended_entries=[
            EntryCandidate(
                symbol="GABRIEL",
                company_name="Gabriel India Ltd",
                industry="Auto Components",
                close_price=1620.00,
                suggested_qty=16,
                investment_amount=25920.00,
                high_20_level=1557.80,
                breakout_pct=3.99,
                rvol=11.78,
                high_52w=1690.00,
                dist_52w_pct=-4.14,
                composite_score=47.04,
                rank=1,
            ),
            EntryCandidate(
                symbol="CUPID",
                company_name="Cupid Ltd",
                industry="Healthcare",
                close_price=385.90,
                suggested_qty=71,
                investment_amount=27398.90,
                high_20_level=368.95,
                breakout_pct=4.59,
                rvol=3.56,
                high_52w=389.00,
                dist_52w_pct=-0.80,
                composite_score=16.36,
                rank=2,
            ),
            EntryCandidate(
                symbol="KALYANKJIL",
                company_name="Kalyan Jewellers",
                industry="Consumer Discretionary",
                close_price=713.90,
                suggested_qty=38,
                investment_amount=27128.20,
                high_20_level=689.00,
                breakout_pct=3.61,
                rvol=4.51,
                high_52w=717.00,
                dist_52w_pct=-0.43,
                composite_score=16.31,
                rank=3,
            ),
            EntryCandidate(
                symbol="PAYTM",
                company_name="One 97 Communications",
                industry="Fintech",
                close_price=1922.00,
                suggested_qty=14,
                investment_amount=26908.00,
                high_20_level=1855.50,
                breakout_pct=3.58,
                rvol=3.18,
                high_52w=1922.00,
                dist_52w_pct=0.00,
                composite_score=11.39,
                rank=4,
            ),
        ],
        runner_ups=[
            EntryCandidate(symbol="NAVINFLUOR", company_name="", industry="", close_price=3400.0, suggested_qty=5, investment_amount=17000.0, high_20_level=3300.0, breakout_pct=3.0, rvol=2.5, high_52w=3500.0, dist_52w_pct=-2.8, composite_score=6.8, rank=5),
            EntryCandidate(symbol="MOTILALOFS", company_name="", industry="", close_price=650.0, suggested_qty=30, investment_amount=19500.0, high_20_level=630.0, breakout_pct=3.1, rvol=2.1, high_52w=660.0, dist_52w_pct=-1.5, composite_score=6.7, rank=6),
            EntryCandidate(symbol="PRESTIGE", company_name="", industry="", close_price=1750.0, suggested_qty=11, investment_amount=19250.0, high_20_level=1700.0, breakout_pct=2.9, rvol=2.2, high_52w=1780.0, dist_52w_pct=-1.6, composite_score=6.5, rank=7),
            EntryCandidate(symbol="PHOENIXLTD", company_name="", industry="", close_price=1620.0, suggested_qty=12, investment_amount=19440.0, high_20_level=1580.0, breakout_pct=2.5, rvol=1.9, high_52w=1650.0, dist_52w_pct=-1.8, composite_score=4.7, rank=8),
            EntryCandidate(symbol="ABCAPITAL", company_name="", industry="", close_price=220.0, suggested_qty=90, investment_amount=19800.0, high_20_level=215.0, breakout_pct=2.3, rvol=1.7, high_52w=225.0, dist_52w_pct=-2.2, composite_score=4.0, rank=9),
        ],
        total_scanned=500,
        total_breakouts_found=21,
    )

    mock_summary = {
        "total_portfolio_value": 189073.07,
        "total_invested": 71913.05,
        "cash_balance": 111679.27,
        "unrealized_pnl": 5480.75,
        "realized_pnl": 0.0,
        "active_count": 7,
        "max_positions": 10,
        "open_slots": 3,
        "positions": [
            {"symbol": "PNB", "quantity": 85, "cmp": 141.79, "pnl": 1556.0, "pnl_pct": 14.82, "invested": 10496.15},
            {"symbol": "PETRONET", "quantity": 35, "cmp": 335.00, "pnl": 1088.0, "pnl_pct": 10.23, "invested": 10637.0},
            {"symbol": "UNIONBANK", "quantity": 55, "cmp": 204.40, "pnl": 969.0, "pnl_pct": 9.43, "invested": 10273.0},
            {"symbol": "MOTHERSON", "quantity": 65, "cmp": 165.83, "pnl": 827.0, "pnl_pct": 8.31, "invested": 9951.95},
            {"symbol": "NUVAMA", "quantity": 6, "cmp": 1886.20, "pnl": 798.0, "pnl_pct": 7.59, "invested": 10519.2},
            {"symbol": "BHEL", "quantity": 25, "cmp": 431.20, "pnl": 559.0, "pnl_pct": 5.47, "invested": 10221.0},
            {"symbol": "IPCALAB", "quantity": 5, "cmp": 1899.70, "pnl": -316.0, "pnl_pct": -3.22, "invested": 9814.5},
        ],
    }

    print("Dispatching upgraded high-readability Discord alert embeds...")
    notifier.notify_scan_results(mock_scan_result, mock_summary)
    print("✅ All 3 upgraded embeds sent! Check your Discord channel.")


if __name__ == "__main__":
    main()
