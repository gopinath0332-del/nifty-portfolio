"""
src/discord_notifier.py
=======================
Sends rich, actionable Discord embeds for manual order execution:
  - 🟢 Buy Signals with suggested quantity (₹20,000 allocation) and CMP
  - 🔴 Exit Signals with breakdown price and P&L
  - 📊 Daily Portfolio Summary & open slots
  - ⚠️ System and Token Alerts
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from src.strategy import EntryCandidate, ExitSignal, ScanResult

logger = logging.getLogger(__name__)

# Discord embed color constants
COLOR_BUY = 0x10B981      # Emerald Green
COLOR_EXIT = 0xF43F5E     # Rose Red / Amber
COLOR_SUMMARY = 0x3B82F6  # Royal Blue
COLOR_WARNING = 0xF59E0B  # Amber
COLOR_ERROR = 0xDC2626    # Crimson


class DiscordNotifier:
    """Dispatches formatted actionable trade alerts to Discord webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip()

    def send_embed(self, title: str, description: str, color: int, fields: Optional[List[Dict[str, Any]]] = None, footer: Optional[str] = None) -> bool:
        """Send a formatted embed to Discord webhook."""
        if not self.webhook_url:
            logger.warning("Discord webhook URL is empty. Alert not sent: %s", title)
            return False

        payload: Dict[str, Any] = {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                    "fields": fields or [],
                    "timestamp": datetime.utcnow().isoformat(),
                    "footer": {
                        "text": footer or "Nifty 500 Donchian Portfolio Engine • Pi 5"
                    },
                }
            ]
        }

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                logger.info("Discord alert sent: %s", title)
                return True
            else:
                logger.error("Discord webhook responded with code %d: %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.error("Failed to send Discord alert: %s", e)
            return False

    def notify_scan_results(self, result: ScanResult, portfolio_summary: Dict[str, Any]) -> None:
        """
        Send comprehensive daily scan results:
        1. Exit alerts (if any positions need closing).
        2. Buy recommendations (if open slots exist and breakouts found).
        3. Portfolio summary.
        """
        today_str = result.scan_date

        # ------------------------------------------------------------------
        # 1. Exit Signals
        # ------------------------------------------------------------------
        if result.exits:
            fields = []
            for ex in result.exits:
                pnl_symbol = "🟢" if ex.pnl >= 0 else "🔴"
                fields.append({
                    "name": f"Sell: {ex.symbol} ({ex.quantity} shares)",
                    "value": (
                        f"• **Close (CMP):** ₹{ex.close_price:,.2f}\n"
                        f"• **20-Day Low Breakdown:** ₹{ex.low_20_level:,.2f}\n"
                        f"• **Entry Price:** ₹{ex.entry_price:,.2f}\n"
                        f"• **P&L:** {pnl_symbol} ₹{ex.pnl:+,.2f} ({ex.pnl_pct:+.2f}%)\n"
                        f"• **Action:** Sell CNC Market on Kite"
                    ),
                    "inline": True,
                })

            self.send_embed(
                title=f"🔴 EXIT SIGNALS — {len(result.exits)} Position(s) to Close [{today_str}]",
                description="The following stocks closed below their 20-Day Low. Please place sell orders manually on Kite.",
                color=COLOR_EXIT,
                fields=fields,
            )

        # ------------------------------------------------------------------
        # 2. Buy Signals (Top Recommended Entries)
        # ------------------------------------------------------------------
        if result.recommended_entries:
            fields = []
            for cand in result.recommended_entries:
                fields.append({
                    "name": f"#{cand.rank} BUY: {cand.symbol} • Suggested: {cand.suggested_qty} shares",
                    "value": (
                        f"• **Close (CMP):** ₹{cand.close_price:,.2f}\n"
                        f"• **Est. Investment:** ₹{cand.investment_amount:,.2f} *(Allocation: ₹20k)*\n"
                        f"• **20-Day High Level:** ₹{cand.high_20_level:,.2f} (+{cand.breakout_pct:.2f}%)\n"
                        f"• **Dist. from 52W High:** {cand.dist_52w_pct:+.2f}%\n"
                        f"• **Relative Volume (RVOL):** {cand.rvol:.2f}x\n"
                        f"• **Composite Score:** {cand.composite_score:.2f}\n"
                        f"• **Action:** Buy CNC Market on Kite"
                    ),
                    "inline": False,
                })

            # Add runner-ups note if any
            footer_text = f"Top {len(result.recommended_entries)} picked for available slots."
            if result.runner_ups:
                runner_up_names = ", ".join(f"{c.symbol} ({c.composite_score:.1f})" for c in result.runner_ups[:5])
                fields.append({
                    "name": "📋 Other Breakout Candidates (Runners-Up)",
                    "value": f"{runner_up_names}..." if len(result.runner_ups) > 5 else runner_up_names,
                    "inline": False,
                })

            self.send_embed(
                title=f"🟢 BUY SIGNALS — {len(result.recommended_entries)} Top Breakout(s) [{today_str}]",
                description=(
                    f"**{result.total_breakouts_found} breakouts found** across Nifty 500 near 52W high.\n"
                    f"Recommended for your **{len(result.recommended_entries)} open slot(s)**:"
                ),
                color=COLOR_BUY,
                fields=fields,
                footer=footer_text,
            )
        elif result.open_slots_before > 0:
            # Open slots exist but no breakouts qualified
            self.send_embed(
                title=f"⚪ NO BREAKOUT SIGNALS TODAY [{today_str}]",
                description=f"Scanned {result.total_scanned} Nifty 500 stocks. No stocks passed 20-Day High breakout + 52-Week High filter.\n**Open Slots available:** {result.open_slots_after}/10",
                color=COLOR_SUMMARY,
            )

        # ------------------------------------------------------------------
        # 3. Daily Portfolio Summary
        # ------------------------------------------------------------------
        self.notify_portfolio_summary(portfolio_summary, scan_date=today_str)

    def notify_portfolio_summary(self, summary: Dict[str, Any], scan_date: Optional[str] = None) -> None:
        """Send daily summary of holdings, cash, and P&L."""
        today_str = scan_date or datetime.now().strftime("%Y-%m-%d")

        unrealized = summary.get("unrealized_pnl", 0.0)
        pnl_symbol = "🟢" if unrealized >= 0 else "🔴"
        active_count = summary.get("active_count", 0)
        max_pos = summary.get("max_positions", 10)
        open_slots = summary.get("open_slots", max_pos - active_count)

        desc = (
            f"• **Portfolio Value:** ₹{summary.get('total_portfolio_value', 0.0):,.2f}\n"
            f"• **Total Invested:** ₹{summary.get('total_invested', 0.0):,.2f}\n"
            f"• **Cash Balance:** ₹{summary.get('cash_balance', 0.0):,.2f}\n"
            f"• **Unrealized P&L:** {pnl_symbol} ₹{unrealized:+,.2f}\n"
            f"• **Realized P&L:** ₹{summary.get('realized_pnl', 0.0):+,.2f}\n"
            f"• **Holdings:** {active_count}/{max_pos} stocks ({open_slots} slots open)"
        )

        fields = []
        positions = summary.get("positions", [])
        if positions:
            holdings_lines = []
            for p in positions:
                sym = p["symbol"]
                qty = p["quantity"]
                cmp = p["cmp"]
                pnl = p["pnl"]
                pnl_pct = p["pnl_pct"]
                p_sym = "🟢" if pnl >= 0 else "🔴"
                holdings_lines.append(f"`{sym:<10}` x{qty:<3} @ ₹{cmp:>7.2f} | {p_sym} {pnl_pct:>+6.2f}% (₹{pnl:+,.0f})")

            # Split into chunks of 10 if necessary
            fields.append({
                "name": "Current Holdings",
                "value": "\n".join(holdings_lines),
                "inline": False,
            })

        self.send_embed(
            title=f"📊 DAILY PORTFOLIO SUMMARY — {today_str}",
            description=desc,
            color=COLOR_SUMMARY,
            fields=fields,
        )

    def notify_error(self, message: str, context: str = "") -> None:
        """Send an error or token alert to Discord."""
        self.send_embed(
            title="⚠️ ALERT: Portfolio Engine Notification",
            description=f"**Context:** {context}\n\n**Details:** {message}",
            color=COLOR_WARNING,
        )

