"""
scripts/manage_portfolio.py
===========================
CLI management utility to inspect, record manual trades, and sync portfolio state.

Commands:
  python scripts/manage_portfolio.py list
      Display current holdings, cash, P&L and available slots in a formatted table.

  python scripts/manage_portfolio.py buy --symbol SYMBOL --price PRICE [--qty QTY] [--stop STOP]
      Record a manual buy order into portfolio_state.json. If qty omitted, calculates floor(20000/price).

  python scripts/manage_portfolio.py sell --symbol SYMBOL --price PRICE [--reason REASON]
      Record a manual sell/exit into trade history and free up a portfolio slot.

  python scripts/manage_portfolio.py sync
      Automatically sync active portfolio state with actual Zerodha Demat holdings (kite.holdings()).

  python scripts/manage_portfolio.py history
      Show historical closed trades and cumulative P&L.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tabulate import tabulate

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.kite_client import get_kite_client
from src.portfolio import PortfolioManager


def cmd_list(portfolio: PortfolioManager, kite=None) -> None:
    current_prices = {}
    if kite and portfolio.positions:
        try:
            symbols = [f"NSE:{s}" for s in portfolio.positions.keys()]
            quotes = kite.quote(symbols)
            for s in portfolio.positions.keys():
                q_key = f"NSE:{s}"
                if q_key in quotes:
                    current_prices[s] = float(quotes[q_key].get("last_price", 0.0))
        except Exception:
            pass

    summary = portfolio.get_portfolio_summary(current_prices)

    print("\n" + "=" * 75)
    print("CURRENT PORTFOLIO STATUS")
    print("=" * 75)
    print(f"Total Budget:    ₹{summary['total_capital']:,.2f}")
    print(f"Portfolio Value: ₹{summary['total_portfolio_value']:,.2f}")
    print(f"Total Invested:  ₹{summary['total_invested']:,.2f}")
    print(f"Cash Balance:    ₹{summary['cash_balance']:,.2f}")
    print(f"Holdings:        {summary['active_count']}/{summary['max_positions']} stocks ({summary['open_slots']} slots open)")
    print(f"Unrealized P&L:  ₹{summary['unrealized_pnl']:+,.2f}")
    print(f"Realized P&L:    ₹{summary['realized_pnl']:+,.2f}")
    print("=" * 75)

    if not summary["positions"]:
        print("\nNo active positions. All 10 slots are available.\n")
        return

    table_data = []
    for p in summary["positions"]:
        table_data.append([
            p["symbol"],
            p["entry_date"],
            f"₹{p['entry_price']:,.2f}",
            p["quantity"],
            f"₹{p['invested']:,.2f}",
            f"₹{p['cmp']:,.2f}",
            f"₹{p['current_value']:,.2f}",
            f"₹{p['pnl']:+,.2f} ({p['pnl_pct']:+.2f}%)",
            f"₹{p['stop_exit_level']:,.2f}" if p["stop_exit_level"] else "N/A",
        ])

    headers = ["Symbol", "Entry Date", "Entry Price", "Qty", "Invested", "CMP", "Current Val", "P&L", "Exit Level"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid") + "\n")


def cmd_buy(portfolio: PortfolioManager, symbol: str, price: float, qty: int | None, stop: float) -> None:
    symbol = symbol.upper().strip()
    pos = portfolio.add_position(
        symbol=symbol,
        entry_price=price,
        quantity=qty,
        stop_exit_level=stop,
    )
    if pos:
        print(f"✅ Successfully recorded BUY for {pos.symbol}:")
        print(f"   Quantity: {pos.quantity} shares @ ₹{pos.entry_price:,.2f} = ₹{pos.invested_amount:,.2f}")
        print(f"   Remaining Cash: ₹{portfolio.cash_balance:,.2f} | Open Slots: {portfolio.open_slots}/10\n")
    else:
        print(f"❌ Failed to add position {symbol}. Check if stock is already held or portfolio is full.\n")


def cmd_sell(portfolio: PortfolioManager, symbol: str, price: float, reason: str) -> None:
    symbol = symbol.upper().strip()
    trade = portfolio.close_position(
        symbol=symbol,
        exit_price=price,
        exit_reason=reason,
    )
    if trade:
        pnl_str = f"₹{trade.pnl:+,.2f} ({trade.pnl_pct:+.2f}%)"
        print(f"✅ Successfully recorded EXIT for {trade.symbol}:")
        print(f"   Sold: {trade.quantity} shares @ ₹{trade.exit_price:,.2f}")
        print(f"   P&L:  {pnl_str} | Reason: {trade.exit_reason}")
        print(f"   New Cash Balance: ₹{portfolio.cash_balance:,.2f} | Open Slots: {portfolio.open_slots}/10\n")
    else:
        print(f"❌ Stock {symbol} not found in active portfolio.\n")


def cmd_sync(portfolio: PortfolioManager, kite) -> None:
    if not kite:
        print("❌ Cannot sync with Demat holdings: KiteConnect authentication unavailable.")
        return

    try:
        holdings = kite.holdings()
        print(f"Found {len(holdings)} holdings in Zerodha Demat account.")

        synced_count = 0
        for h in holdings:
            sym = h.get("tradingsymbol", "")
            qty = int(h.get("quantity", 0)) + int(h.get("t1_quantity", 0))
            avg_price = float(h.get("average_price", 0.0))

            if qty > 0 and sym not in portfolio.positions and len(portfolio.positions) < portfolio.max_positions:
                portfolio.add_position(
                    symbol=sym,
                    entry_price=avg_price,
                    quantity=qty,
                    notes="Auto-synced from Kite Demat holdings",
                )
                synced_count += 1
                print(f"  + Added Demat holding: {sym} x{qty} @ ₹{avg_price:.2f}")

        print(f"✅ Sync complete. Added {synced_count} positions. Active portfolio has {len(portfolio.positions)}/10 stocks.\n")
    except Exception as e:
        print(f"❌ Error syncing with Kite Demat holdings: {e}")


def cmd_history(portfolio: PortfolioManager) -> None:
    if not portfolio.trade_history:
        print("\nNo closed trades in history yet.\n")
        return

    table_data = []
    total_pnl = 0.0
    for t in portfolio.trade_history:
        total_pnl += t.pnl
        table_data.append([
            t.symbol,
            t.entry_date,
            t.exit_date,
            f"₹{t.entry_price:,.2f}",
            f"₹{t.exit_price:,.2f}",
            t.quantity,
            f"₹{t.invested_amount:,.2f}",
            f"₹{t.pnl:+,.2f}",
            f"{t.pnl_pct:+.2f}%",
            t.exit_reason,
        ])

    headers = ["Symbol", "Entry", "Exit", "Buy Price", "Sell Price", "Qty", "Invested", "P&L (₹)", "P&L (%)", "Reason"]
    print("\n" + "=" * 90)
    print("CLOSED TRADES HISTORY")
    print("=" * 90)
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print(f"\nCumulative Realized P&L: ₹{total_pnl:+,.2f}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nifty Portfolio CLI Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list
    subparsers.add_parser("list", help="List current portfolio holdings and summary")

    # buy
    buy_parser = subparsers.add_parser("buy", help="Record a manual buy order")
    buy_parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. RELIANCE)")
    buy_parser.add_argument("--price", type=float, required=True, help="Execution buy price")
    buy_parser.add_argument("--qty", type=int, default=None, help="Quantity (default: ₹20k / price)")
    buy_parser.add_argument("--stop", type=float, default=0.0, help="Initial stop exit level")

    # sell
    sell_parser = subparsers.add_parser("sell", help="Record a manual exit order")
    sell_parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. RELIANCE)")
    sell_parser.add_argument("--price", type=float, required=True, help="Execution sell price")
    sell_parser.add_argument("--reason", default="20-Day Low Channel Breakdown", help="Exit reason")

    # sync
    subparsers.add_parser("sync", help="Sync portfolio with Zerodha Demat holdings")

    # history
    subparsers.add_parser("history", help="Show closed trades history")

    args = parser.parse_args()

    config = load_config()
    portfolio = PortfolioManager(config)

    kite = None
    if args.command in ("list", "sync"):
        kite = get_kite_client(config, validate=False)

    if args.command == "list" or not args.command:
        cmd_list(portfolio, kite)
    elif args.command == "buy":
        cmd_buy(portfolio, args.symbol, args.price, args.qty, args.stop)
    elif args.command == "sell":
        cmd_sell(portfolio, args.symbol, args.price, args.reason)
    elif args.command == "sync":
        cmd_sync(portfolio, kite)
    elif args.command == "history":
        cmd_history(portfolio)


if __name__ == "__main__":
    main()

