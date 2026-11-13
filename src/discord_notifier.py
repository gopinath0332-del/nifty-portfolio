"""
src/discord_notifier.py
=======================
Sends institutional-grade, highly readable Discord embeds for manual order execution:
  - 🟢 Buy Signals: Instant Order Execution Sheet + Compact Setup Cards
  - 🔴 Exit Signals: Fast Sell Execution Sheet + Breakdown Trigger Cards
  - 📊 Daily Portfolio Summary: 6-Metric KPI Tiles + Monospace Monitored Holdings Table
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

    def send_embed(
        self,
        title: str,
        description: str,
        color: int,
        fields: Optional[List[Dict[str, Any]]] = None,
        footer: Optional[str] = None,
    ) -> bool:
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
            fields = self._build_exit_fields(result.exits)
            self.send_embed(
                title=f"🔴 EXIT SIGNALS — {len(result.exits)} Position(s) to Close [{today_str}]",
                description=(
                    "⚡ **Action Required:** Place CNC Market SELL orders on Zerodha Kite.\n"
                    "The following positions triggered systematic exit conditions:"
                ),
                color=COLOR_EXIT,
                fields=fields,
            )

        # ------------------------------------------------------------------
        # 2. Buy Signals (Top Recommended Entries)
        # ------------------------------------------------------------------
        if result.recommended_entries:
            fields = self._build_buy_fields(result.recommended_entries, result.runner_ups)
            footer_text = f"Top {len(result.recommended_entries)} picked for available slots • Momentum Rank (Breakout% × RVOL)"
            self.send_embed(
                title=f"🟢 BUY SIGNALS — {len(result.recommended_entries)} Top Breakout(s) [{today_str}]",
                description=(
                    f"🎯 **{result.total_breakouts_found} breakouts found** across Nifty 500 near 52W High.\n"
                    f"Recommended top **{len(result.recommended_entries)}** for your open portfolio slots:"
                ),
                color=COLOR_BUY,
                fields=fields,
                footer=footer_text,
            )
        elif result.open_slots_before > 0:
            self.send_embed(
                title=f"⚪ NO BREAKOUT SIGNALS TODAY [{today_str}]",
                description=(
                    f"Scanned {result.total_scanned} Nifty 500 stocks. No stocks passed 50-Day Breakout + 52-Week High filter.\n"
                    f"**Open Slots available:** {result.open_slots_after}/10"
                ),
                color=COLOR_SUMMARY,
            )

        # ------------------------------------------------------------------
        # 3. Daily Portfolio Summary
        # ------------------------------------------------------------------
        self.notify_portfolio_summary(portfolio_summary, scan_date=today_str)

    def _build_exit_fields(self, exits: List[ExitSignal]) -> List[Dict[str, Any]]:
        """Construct monospace order execution sheet and compact exit cards."""
        fields: List[Dict[str, Any]] = []

        # Monospace execution table
        header = f"{'TICKER':<10} {'QTY':>4} {'CMP':>9} {'ENTRY':>9} {'P&L %':>8} {'P&L (Rs)':>9}"
        sep = "-" * len(header)
        table_lines = [header, sep]
        for ex in exits:
            table_lines.append(
                f"{ex.symbol:<10} {ex.quantity:>4} {ex.close_price:>9.2f} {ex.entry_price:>9.2f} {ex.pnl_pct:>+7.2f}% {ex.pnl:>+9,.0f}"
            )
        table_lines.append(sep)

        fields.append({
            "name": "⚡ Quick Order Execution (CNC Market Sell)",
            "value": "```text\n" + "\n".join(table_lines) + "\n```",
            "inline": False,
        })

        # Compact exit cards
        for ex in exits:
            pnl_symbol = "🟢" if ex.pnl >= 0 else "🔴"
            reason = ex.exit_reason or "20-Day Low Breakdown"
            fields.append({
                "name": f"{pnl_symbol} Sell: {ex.symbol} ({ex.quantity} shares)",
                "value": (
                    f"▸ **P&L:** {pnl_symbol} ₹{ex.pnl:+,.2f} ({ex.pnl_pct:+.2f}%)\n"
                    f"▸ **Prices:** CMP: ₹{ex.close_price:,.2f}  |  Entry: ₹{ex.entry_price:,.2f}\n"
                    f"▸ **Reason:** {reason} (Pivot: ₹{ex.low_20_level:,.2f})\n"
                    f"-# 💡 Action: Sell CNC Market on Kite"
                ),
                "inline": False,
            })

        return fields

    def _build_buy_fields(
        self,
        recommended: List[EntryCandidate],
        runner_ups: List[EntryCandidate],
    ) -> List[Dict[str, Any]]:
        """Construct quick order placement sheet and compact setup cards."""
        fields: List[Dict[str, Any]] = []

        # 1. Monospace Quick Execution Sheet (for instant punching in Zerodha Kite)
        header = f"{'#':<2} {'TICKER':<10} {'QTY':>4} {'CMP':>9} {'INVEST':>9} {'BREAKOUT':>9}"
        sep = "-" * len(header)
        sheet_lines = [header, sep]
        total_est = sum(c.investment_amount for c in recommended)
        total_qty = sum(c.suggested_qty for c in recommended)

        for c in recommended:
            sheet_lines.append(
                f"{c.rank:<2} {c.symbol:<10} {c.suggested_qty:>4} {c.close_price:>9.2f} {c.investment_amount:>9,.0f} {c.breakout_pct:>+8.2f}%"
            )
        sheet_lines.append(sep)
        sheet_lines.append(f"{'TOTAL':<17} {total_qty:>4} {'':>9} {total_est:>9,.0f}")

        fields.append({
            "name": "⚡ Quick Order Placement (CNC Market Buy)",
            "value": "```text\n" + "\n".join(sheet_lines) + "\n```",
            "inline": False,
        })

        # 2. Compact Technical Setup Cards
        for c in recommended:
            fields.append({
                "name": f"🟢 #{c.rank} BUY: {c.symbol} • Suggested: {c.suggested_qty} shares",
                "value": (
                    f"▸ **Investment:** ₹{c.investment_amount:,.2f} *(Allocation: ~₹20k)*\n"
                    f"▸ **Price Setup:** CMP: ₹{c.close_price:,.2f}  |  Breakout: +{c.breakout_pct:.2f}% (Pivot: ₹{c.high_20_level:,.2f})\n"
                    f"▸ **Momentum:** RVOL: **{c.rvol:.2f}x**  |  52W Dist: **{c.dist_52w_pct:+.2f}%**  |  Score: **{c.composite_score:.2f}**\n"
                    f"-# 💡 Action: Buy CNC Market on Kite"
                ),
                "inline": False,
            })

        # 3. Runners-Up cleanly formatted
        if runner_ups:
            ru_items = [f"**{c.symbol}** ({c.composite_score:.1f})" for c in runner_ups[:6]]
            fields.append({
                "name": "📋 Other Breakout Candidates (Runners-Up)",
                "value": " • ".join(ru_items) + ("..." if len(runner_ups) > 6 else ""),
                "inline": False,
            })

        return fields

    def notify_portfolio_summary(self, summary: Dict[str, Any], scan_date: Optional[str] = None) -> None:
        """Send daily summary of holdings, cash, and P&L with sleek KPI tiles and monospace table."""
        today_str = scan_date or datetime.now().strftime("%Y-%m-%d")

        total_val = summary.get("total_portfolio_value", 0.0)
        cash = summary.get("cash_balance", 0.0)
        invested = summary.get("total_invested", 0.0)
        unrealized = summary.get("unrealized_pnl", 0.0)
        realized = summary.get("realized_pnl", 0.0)
        active_count = summary.get("active_count", 0)
        max_pos = summary.get("max_positions", 10)
        open_slots = summary.get("open_slots", max_pos - active_count)

        unrealized_pct = (unrealized / invested * 100.0) if invested > 0 else 0.0
        pnl_symbol = "🟢" if unrealized >= 0 else "🔴"
        pnl_sign = "+" if unrealized >= 0 else ""

        # 6 Sleek KPI Embed Tiles (renders as 3x2 grid on desktop, crisp cards on mobile)
        fields: List[Dict[str, Any]] = [
            {
                "name": "💼 Portfolio Value",
                "value": f"**₹{total_val:,.2f}**",
                "inline": True,
            },
            {
                "name": "💵 Cash Available",
                "value": f"**₹{cash:,.2f}**",
                "inline": True,
            },
            {
                "name": "📊 Active Slots",
                "value": f"**{active_count}/{max_pos}** ({open_slots} open)",
                "inline": True,
            },
            {
                "name": "📈 Unrealized P&L",
                "value": f"{pnl_symbol} **{pnl_sign}₹{unrealized:,.2f}** ({pnl_sign}{unrealized_pct:.2f}%)",
                "inline": True,
            },
            {
                "name": "📦 Total Invested",
                "value": f"₹{invested:,.2f}",
                "inline": True,
            },
            {
                "name": "💰 Realized P&L",
                "value": f"₹{realized:+,.2f}",
                "inline": True,
            },
        ]

        # Monospace Holdings Table
        positions = summary.get("positions", [])
        if positions:
            sorted_pos = sorted(positions, key=lambda p: p.get("pnl_pct", 0.0), reverse=True)

            header = f"{'TICKER':<10} {'QTY':>4} {'CMP':>9} {'P&L %':>8} {'P&L (Rs)':>9}"
            sep = "-" * len(header)
            table_lines = [header, sep]

            for p in sorted_pos:
                table_lines.append(
                    f"{p['symbol']:<10} {p['quantity']:>4} {p['cmp']:>9.2f} {p['pnl_pct']:>+7.2f}% {p['pnl']:>+9,.0f}"
                )
            table_lines.append(sep)
            table_lines.append(
                f"{'TOTAL':<15} {active_count:>4} {'':>5} {unrealized_pct:>+7.2f}% {unrealized:>+9,.0f}"
            )

            fields.append({
                "name": f"📋 Current Holdings ({active_count} Stocks • Sorted by Return)",
                "value": "```text\n" + "\n".join(table_lines) + "\n```",
                "inline": False,
            })
        else:
            fields.append({
                "name": "📋 Current Holdings",
                "value": "*No active positions. 100% Cash buffer.*",
                "inline": False,
            })

        self.send_embed(
            title=f"📊 DAILY PORTFOLIO SUMMARY — {today_str}",
            description="Institutional trend-following portfolio snapshot and active Demat positions.",
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
