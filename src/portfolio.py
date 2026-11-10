"""
src/portfolio.py
================
Manages persistent portfolio state, positions, cash, capital allocation,
and trade history in data/portfolio_state.json.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import BASE_DIR, AppConfig

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    entry_date: str
    entry_price: float
    quantity: int
    invested_amount: float
    stop_exit_level: float = 0.0
    notes: str = ""
    industry: str = ""


@dataclass
class TradeRecord:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    invested_amount: float
    exit_amount: float
    pnl: float
    pnl_pct: float
    exit_reason: str


class PortfolioManager:
    """Manages 10-stock portfolio allocation of ₹2,00,000 (₹20,000 per stock)."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.state_file = BASE_DIR / config.files.state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.total_capital: float = config.capital.total_capital
        self.position_size: float = config.capital.position_size
        self.max_positions: int = config.capital.max_positions
        self.cash_balance: float = self.total_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeRecord] = []
        self.last_scan_date: Optional[str] = None

        self.load_state()

    def load_state(self) -> None:
        """Load portfolio state from JSON file."""
        if not self.state_file.exists():
            self.save_state()
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.total_capital = float(data.get("total_capital", self.config.capital.total_capital))
            self.position_size = float(data.get("position_size", self.config.capital.position_size))
            self.max_positions = int(data.get("max_positions", self.config.capital.max_positions))
            self.cash_balance = float(data.get("cash_balance", self.total_capital))
            self.last_scan_date = data.get("last_scan_date")

            self.positions = {}
            for sym, pos_data in data.get("positions", {}).items():
                self.positions[sym] = Position(
                    symbol=pos_data["symbol"],
                    entry_date=pos_data["entry_date"],
                    entry_price=float(pos_data["entry_price"]),
                    quantity=int(pos_data["quantity"]),
                    invested_amount=float(pos_data["invested_amount"]),
                    stop_exit_level=float(pos_data.get("stop_exit_level", 0.0)),
                    notes=pos_data.get("notes", ""),
                    industry=pos_data.get("industry", ""),
                )

            self.trade_history = []
            for tr_data in data.get("trade_history", []):
                self.trade_history.append(
                    TradeRecord(
                        symbol=tr_data["symbol"],
                        entry_date=tr_data["entry_date"],
                        exit_date=tr_data["exit_date"],
                        entry_price=float(tr_data["entry_price"]),
                        exit_price=float(tr_data["exit_price"]),
                        quantity=int(tr_data["quantity"]),
                        invested_amount=float(tr_data["invested_amount"]),
                        exit_amount=float(tr_data["exit_amount"]),
                        pnl=float(tr_data["pnl"]),
                        pnl_pct=float(tr_data["pnl_pct"]),
                        exit_reason=tr_data.get("exit_reason", ""),
                    )
                )

            logger.info("Loaded portfolio state: %d active positions, cash=₹%.2f", len(self.positions), self.cash_balance)
        except Exception as e:
            logger.error("Error loading portfolio state from %s: %s", self.state_file, e)

    def save_state(self) -> None:
        """Save portfolio state to JSON file."""
        data = {
            "total_capital": self.total_capital,
            "position_size": self.position_size,
            "max_positions": self.max_positions,
            "cash_balance": round(self.cash_balance, 2),
            "positions": {sym: asdict(pos) for sym, pos in self.positions.items()},
            "trade_history": [asdict(tr) for tr in self.trade_history],
            "last_scan_date": self.last_scan_date,
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Portfolio state saved to %s", self.state_file)

    @property
    def open_slots(self) -> int:
        """Number of open stock slots remaining (out of 10)."""
        return max(0, self.max_positions - len(self.positions))

    def get_total_equity(self) -> float:
        """Return total portfolio equity (cash + invested amount in open positions)."""
        invested = sum(pos.invested_amount for pos in self.positions.values())
        return self.cash_balance + invested

    def calculate_quantity(
        self,
        price: float,
        stop_price: Optional[float] = None,
        current_equity: Optional[float] = None,
    ) -> int:
        """
        Calculate quantity of shares.
        If sizing_mode == 'risk_pct':
            Risk Amount = Equity * (risk_per_trade_pct / 100)
            Risk Per Share = max(price - stop_price, price * 0.02)
            Quantity = floor(Risk Amount / Risk Per Share)
            Capped by max_position_size_pct and cash balance.
        Otherwise:
            Quantity = floor(position_size / price)
        """
        if price <= 0:
            return 0

        eq = current_equity if current_equity is not None else self.get_total_equity()

        if getattr(self.config.capital, "sizing_mode", "fixed") == "risk_pct":
            risk_pct = getattr(self.config.capital, "risk_per_trade_pct", 2.0)
            max_alloc_pct = getattr(self.config.capital, "max_position_size_pct", 20.0)

            # Determine stop distance (capped at max 8% stop)
            effective_stop = stop_price if stop_price is not None and stop_price > 0 else (price * 0.92)
            risk_per_share = max(price - effective_stop, price * 0.02)

            risk_budget = eq * (risk_pct / 100.0)
            qty = int(risk_budget // risk_per_share)

            # Cap by max position allocation (e.g. 20% of equity = ₹20,000 on ₹1,00,000)
            max_pos_budget = eq * (max_alloc_pct / 100.0)
            qty = min(qty, int(max_pos_budget // price))

            # Cap by available cash
            qty = min(qty, int(self.cash_balance // price))
            return max(0, qty)
        else:
            return max(0, int(self.position_size // price))

    def get_sector_counts(self) -> Dict[str, int]:
        """Return the count of active positions in each industry/sector."""
        counts: Dict[str, int] = {}
        for p in self.positions.values():
            sec = p.industry or "Unknown"
            counts[sec] = counts.get(sec, 0) + 1
        return counts

    def add_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: Optional[int] = None,
        entry_date: Optional[str] = None,
        stop_exit_level: float = 0.0,
        notes: str = "",
        industry: str = "",
    ) -> Optional[Position]:
        """Add a newly bought stock to active positions."""
        if symbol in self.positions:
            logger.warning("Stock %s is already in portfolio. Skipping duplicate entry.", symbol)
            return None

        if len(self.positions) >= self.max_positions:
            logger.warning("Portfolio is at full capacity (%d/%d stocks). Cannot add %s.", len(self.positions), self.max_positions, symbol)
            return None

        if quantity is None or quantity <= 0:
            quantity = self.calculate_quantity(entry_price)

        if quantity <= 0:
            logger.warning("Calculated quantity for %s at ₹%.2f is 0. Share price exceeds position size.", symbol, entry_price)
            return None

        invested = round(entry_price * quantity, 2)
        today_str = entry_date or datetime.now().strftime("%Y-%m-%d")

        pos = Position(
            symbol=symbol,
            entry_date=today_str,
            entry_price=entry_price,
            quantity=quantity,
            invested_amount=invested,
            stop_exit_level=stop_exit_level,
            notes=notes,
            industry=industry,
        )
        self.positions[symbol] = pos
        self.cash_balance = max(0.0, self.cash_balance - invested)
        self.save_state()
        logger.info("Added position: %s x%d @ ₹%.2f (Total: ₹%.2f)", symbol, quantity, entry_price, invested)
        return pos

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_date: Optional[str] = None,
        exit_reason: str = "20-Day Low Channel Breakdown",
    ) -> Optional[TradeRecord]:
        """Close an active position and record trade history."""
        if symbol not in self.positions:
            logger.warning("Cannot exit %s: stock not found in active portfolio.", symbol)
            return None

        pos = self.positions.pop(symbol)
        today_str = exit_date or datetime.now().strftime("%Y-%m-%d")
        exit_amount = round(exit_price * pos.quantity, 2)
        pnl = round(exit_amount - pos.invested_amount, 2)
        pnl_pct = round((pnl / pos.invested_amount) * 100.0, 2) if pos.invested_amount > 0 else 0.0

        trade = TradeRecord(
            symbol=symbol,
            entry_date=pos.entry_date,
            exit_date=today_str,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            invested_amount=pos.invested_amount,
            exit_amount=exit_amount,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
        )
        self.trade_history.append(trade)
        self.cash_balance += exit_amount
        self.save_state()
        logger.info("Closed position: %s @ ₹%.2f (PnL: ₹%.2f / %.2f%%) - Reason: %s", symbol, exit_price, pnl, pnl_pct, exit_reason)
        return trade

    def get_portfolio_summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Generate current portfolio summary including unrealized PnL."""
        prices = current_prices or {}
        total_invested = sum(p.invested_amount for p in self.positions.values())
        current_market_value = 0.0

        position_details = []
        for sym, pos in self.positions.items():
            cmp = prices.get(sym, pos.entry_price)
            mkt_val = round(cmp * pos.quantity, 2)
            current_market_value += mkt_val
            unrealized_pnl = round(mkt_val - pos.invested_amount, 2)
            unrealized_pnl_pct = round((unrealized_pnl / pos.invested_amount) * 100.0, 2) if pos.invested_amount > 0 else 0.0

            position_details.append({
                "symbol": sym,
                "entry_date": pos.entry_date,
                "entry_price": pos.entry_price,
                "cmp": cmp,
                "quantity": pos.quantity,
                "invested": pos.invested_amount,
                "current_value": mkt_val,
                "pnl": unrealized_pnl,
                "pnl_pct": unrealized_pnl_pct,
                "stop_exit_level": pos.stop_exit_level,
            })

        total_value = round(self.cash_balance + current_market_value, 2)
        total_unrealized_pnl = round(current_market_value - total_invested, 2)
        total_realized_pnl = sum(t.pnl for t in self.trade_history)

        return {
            "total_capital": self.total_capital,
            "total_portfolio_value": total_value,
            "cash_balance": round(self.cash_balance, 2),
            "total_invested": round(total_invested, 2),
            "unrealized_pnl": total_unrealized_pnl,
            "realized_pnl": round(total_realized_pnl, 2),
            "active_count": len(self.positions),
            "open_slots": self.open_slots,
            "max_positions": self.max_positions,
            "positions": position_details,
        }

