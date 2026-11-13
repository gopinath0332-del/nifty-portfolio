"""
src/discord_notifier.py
=======================
Sends retro-style monospace receipt trade alerts (Bloomberg Terminal style)
optimized specifically for mobile Discord screens (strictly 27 characters wide,
guaranteed zero wrapping on iOS and Android).
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

RECEIPT_WIDTH = 27
INNER_WIDTH = RECEIPT_WIDTH - 2  # 25 characters inside borders


def _format_box_line(text: str) -> str:
    """Pad or truncate string to fit exactly inside a 27-char box."""
    truncated = text[:INNER_WIDTH - 2]
    return f"│ {truncated:<{INNER_WIDTH - 2}} │"


def _build_receipt_box(title: str, col_header: str, rows: List[str], footer: str) -> str:
    """Construct a clean retro terminal ASCII receipt."""
    top = "┌" + "─" * INNER_WIDTH + "┐"
    mid = "├" + "─" * INNER_WIDTH + "┤"
    bot = "└" + "─" * INNER_WIDTH + "┘"

    lines = [
        top,
        _format_box_line(title),
        mid,
        _format_box_line(col_header),
        mid,
    ]
    for r in rows:
        lines.append(_format_box_line(r))
    lines.append(mid)
    lines.append(_format_box_line(footer))
    lines.append(bot)

    return "\n".join(lines)


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
        Send comprehensive daily scan results in retro receipt style:
        1. Exit receipt (if any positions need closing).
        2. Buy receipt (if open slots exist and breakouts found).
        3. Portfolio summary receipt.
        """
        today_str = result.scan_date

        # ------------------------------------------------------------------
        # 1. Exit Signals
        # ------------------------------------------------------------------
        if result.exits:
            exit_desc = self._build_exit_receipt(result.exits)
            self.send_embed(
                title=f"🔴 EXIT SIGNALS — {len(result.exits)} to Close [{today_str}]",
                description=exit_desc,
                color=COLOR_EXIT,
            )

        # ------------------------------------------------------------------
        # 2. Buy Signals (Top Recommended Entries)
        # ------------------------------------------------------------------
        if result.recommended_entries:
            buy_desc = self._build_buy_receipt(result.recommended_entries, result.runner_ups)
            self.send_embed(
                title=f"🟢 BUY SIGNALS — {len(result.recommended_entries)} Orders [{today_str}]",
                description=buy_desc,
                color=COLOR_BUY,
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

    def _build_exit_receipt(self, exits: List[ExitSignal]) -> str:
        """Build narrow 27-char exit receipt box + concise trigger notes."""
        rows = [
            f"{ex.symbol[:9]:<9} {ex.quantity:>4} {ex.pnl_pct:>+7.1f}%"
            for ex in exits
        ]
        box = _build_receipt_box(
            title=f"SELL ORDERS ({len(exits)})",
            col_header=f"{'TICKER':<9} {'QTY':>4} {'P&L %':>8}",
            rows=rows,
            footer="ACTION: SELL CNC (KITE)",
        )

        detail_lines = []
        for ex in exits:
            pnl_symbol = "🟢" if ex.pnl >= 0 else "🔴"
            reason = ex.exit_reason or "Stage 2 Breakdown"
            detail_lines.append(
                f"• `{ex.symbol}`: CMP ₹{ex.close_price:,.1f} | P&L: {pnl_symbol} ₹{ex.pnl:+,.0f} ({reason})"
            )

        return f"```text\n{box}\n```\n" + "\n".join(detail_lines)

    def _build_buy_receipt(
        self,
        recommended: List[EntryCandidate],
        runner_ups: List[EntryCandidate],
    ) -> str:
        """Build narrow 27-char buy order receipt box + compact setup bullet list."""
        rows = [
            f"{c.symbol[:9]:<9} {c.suggested_qty:>4} {c.close_price:>8.1f}"
            for c in recommended
        ]
        total_est = sum(c.investment_amount for c in recommended)
        box = _build_receipt_box(
            title=f"BUY ORDERS ({len(recommended)} SLOTS)",
            col_header=f"{'TICKER':<9} {'QTY':>4} {'CMP':>8}",
            rows=rows,
            footer=f"TOT: Rs {int(total_est):,} (CNC)",
        )

        setup_lines = []
        for c in recommended:
            setup_lines.append(
                f"• `{c.symbol}`: +{c.breakout_pct:.1f}% BO (₹{c.high_20_level:,.0f}) | RVOL {c.rvol:.1f}x | Sc {c.composite_score:.1f}"
            )

        desc = f"```text\n{box}\n```\n" + "\n".join(setup_lines)
        if runner_ups:
            ru_text = ", ".join(f"**{c.symbol}**" for c in runner_ups[:5])
            desc += f"\n\n-# 📋 Watchlist: {ru_text}"

        return desc

    def notify_portfolio_summary(self, summary: Dict[str, Any], scan_date: Optional[str] = None) -> None:
        """Send daily summary in retro terminal receipt format."""
        today_str = scan_date or datetime.now().strftime("%Y-%m-%d")

        active_count = summary.get("active_count", 0)
        max_pos = summary.get("max_positions", 10)
        total_val = summary.get("total_portfolio_value", 0.0)
        cash = summary.get("cash_balance", 0.0)
        invested = summary.get("total_invested", 0.0)
        unrealized = summary.get("unrealized_pnl", 0.0)
        unrealized_pct = (unrealized / invested * 100.0) if invested > 0 else 0.0
        pnl_symbol = "🟢" if unrealized >= 0 else "🔴"
        pnl_sign = "+" if unrealized >= 0 else ""

        positions = summary.get("positions", [])
        if positions:
            sorted_pos = sorted(positions, key=lambda p: p.get("pnl_pct", 0.0), reverse=True)
            rows = [
                f"{p['symbol'][:9]:<9} {p['quantity']:>4} {p['pnl_pct']:>+7.1f}%"
                for p in sorted_pos
            ]
            box = _build_receipt_box(
                title=f"PORTFOLIO ({active_count}/{max_pos} SLOTS)",
                col_header=f"{'TICKER':<9} {'QTY':>4} {'P&L %':>8}",
                rows=rows,
                footer=f"P&L: {pnl_sign}{unrealized_pct:.1f}% (Rs {int(unrealized):+,})",
            )
            table_part = f"```text\n{box}\n```"
        else:
            table_part = "*No active positions. 100% Cash buffer.*"

        stats = (
            f"💼 **Equity:** ₹{total_val:,.0f}  |  💵 **Cash:** ₹{cash:,.0f}\n"
            f"📦 **Invested:** ₹{invested:,.0f}  |  📈 **Unrealized:** {pnl_symbol} {pnl_sign}₹{unrealized:,.0f} ({pnl_sign}{unrealized_pct:.1f}%)"
        )

        desc = f"{table_part}\n{stats}"

        self.send_embed(
            title=f"📊 PORTFOLIO SUMMARY [{today_str}]",
            description=desc,
            color=COLOR_SUMMARY,
        )

    def notify_error(self, message: str, context: str = "") -> None:
        """Send an error or token alert to Discord."""
        self.send_embed(
            title="⚠️ ALERT: Portfolio Engine Notification",
            description=f"**Context:** {context}\n\n**Details:** {message}",
            color=COLOR_WARNING,
        )
