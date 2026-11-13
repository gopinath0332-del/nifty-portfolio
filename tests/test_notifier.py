"""
tests/test_notifier.py
======================
Unit tests for DiscordNotifier retro receipt formatting.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.discord_notifier import DiscordNotifier, RECEIPT_WIDTH, _build_receipt_box
from src.strategy import EntryCandidate, ExitSignal, ScanResult


@pytest.fixture
def mock_notifier():
    return DiscordNotifier(webhook_url="https://discord.com/api/webhooks/dummy/dummy")


def test_build_receipt_box_width():
    rows = [
        f"{'MCX':<9} {7:>4} {3724.7:>8.1f}",
        f"{'ANGELONE':<9} {81:>4} {349.6:>8.1f}",
    ]
    box = _build_receipt_box(
        title="BUY ORDERS (2 SLOTS)",
        col_header=f"{'TICKER':<9} {'QTY':>4} {'CMP':>8}",
        rows=rows,
        footer="TOT: Rs 54,395 (CNC)",
    )
    lines = box.split("\n")
    for l in lines:
        assert len(l) == RECEIPT_WIDTH, f"Line '{l}' length is {len(l)}, expected {RECEIPT_WIDTH}"


def test_build_exit_receipt(mock_notifier):
    exits = [
        ExitSignal(
            symbol="IPCALAB",
            company_name="Ipca Laboratories",
            close_price=1905.00,
            entry_price=1962.90,
            quantity=5,
            low_20_level=1797.00,
            exit_reason="20-Day Low Breakdown",
            pnl=-289.50,
            pnl_pct=-2.95,
        )
    ]
    desc = mock_notifier._build_exit_receipt(exits)
    assert "IPCALAB" in desc
    assert "SELL ORDERS (1)" in desc
    assert "ACTION: SELL CNC (KITE)" in desc


def test_build_buy_receipt(mock_notifier):
    recommended = [
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
        )
    ]
    runners = [
        EntryCandidate(
            symbol="NAVINFLUOR",
            company_name="Navin Fluorine",
            industry="Chemicals",
            close_price=3400.00,
            suggested_qty=5,
            investment_amount=17000.00,
            high_20_level=3300.00,
            breakout_pct=3.03,
            rvol=2.5,
            high_52w=3500.00,
            dist_52w_pct=-2.8,
            composite_score=6.8,
            rank=2,
        )
    ]
    desc = mock_notifier._build_buy_receipt(recommended, runners)
    assert "GABRIEL" in desc
    assert "BUY ORDERS (1 SLOTS)" in desc
    assert "Watchlist: **NAVINFLUOR**" in desc


def test_notify_scan_results_dispatches_embeds(mock_notifier):
    with patch.object(mock_notifier, "send_embed", return_value=True) as mock_send:
        scan_res = ScanResult(
            scan_date="2026-11-13",
            open_slots_before=4,
            open_slots_after=3,
            exits=[
                ExitSignal(
                    symbol="IPCALAB",
                    company_name="Ipca Laboratories",
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
                )
            ],
            total_scanned=500,
            total_breakouts_found=21,
        )
        summary = {
            "total_portfolio_value": 189073.07,
            "total_invested": 71913.05,
            "cash_balance": 111679.27,
            "unrealized_pnl": 5480.75,
            "realized_pnl": 0.0,
            "active_count": 1,
            "max_positions": 10,
            "open_slots": 9,
            "positions": [
                {"symbol": "GABRIEL", "quantity": 16, "cmp": 1620.00, "pnl": 1000.0, "pnl_pct": 3.86, "invested": 25920.0}
            ],
        }

        mock_notifier.notify_scan_results(scan_res, summary)
        assert mock_send.call_count == 3
