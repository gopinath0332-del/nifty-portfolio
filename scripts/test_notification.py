"""
scripts/test_notification.py
============================
Quick test script to verify Discord webhook connectivity and embed formatting.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.discord_notifier import DiscordNotifier, COLOR_BUY, COLOR_SUMMARY


def main() -> None:
    config = load_config()
    webhook_url = config.discord_webhook_url
    if not webhook_url:
        print("❌ Error: DISCORD_WEBHOOK_URL is not set in .env")
        sys.exit(1)

    print(f"Testing Discord webhook: {webhook_url[:50]}...")
    notifier = DiscordNotifier(webhook_url)

    fields = [
        {
            "name": "#1 BUY: TATASTEEL • Suggested: 137 shares",
            "value": (
                "• **Close (CMP):** ₹145.20\n"
                "• **Est. Investment:** ₹19,892.40 *(Allocation: ₹20k)*\n"
                "• **20-Day High Level:** ₹142.00 (+2.25%)\n"
                "• **Dist. from 52W High:** -4.20% (Near Peak 🚀)\n"
                "• **Relative Volume (RVOL):** 2.45x\n"
                "• **Composite Score:** 5.51\n"
                "• **Action:** Buy CNC Market on Kite"
            ),
            "inline": False,
        },
        {
            "name": "📊 Portfolio Status",
            "value": "• **Holdings:** 1/10 stocks (9 open slots)\n• **Cash Available:** ₹1,80,107.60",
            "inline": False,
        }
    ]

    success = notifier.send_embed(
        title="🔔 TEST ALERT: Nifty 500 Donchian Portfolio Engine",
        description="This is a test notification confirming your Discord webhook is connected and ready for 3:45 PM daily breakout alerts.",
        color=COLOR_BUY,
        fields=fields,
    )

    if success:
        print("✅ Discord test alert sent successfully! Check your Discord channel.")
    else:
        print("❌ Failed to deliver Discord alert. Please check webhook URL.")


if __name__ == "__main__":
    main()

