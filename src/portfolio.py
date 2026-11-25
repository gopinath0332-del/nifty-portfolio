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
    partial_taken: bool = False


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
    """Manages portfolio allocation based on fixed strategy capital (e.g. ₹2,00,000 baseline)."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.state_file = BASE_DIR / config.files.state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.total_capital: float = float(config.capital.total_capital)
        self.max_positions: int = int(config.capital.max_positions)
        self.position_size: float = float(config.capital.position_size or (self.total_capital / max(1, self.max_positions)))
        self.cash_balance: float = self.total_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeRecord] = []
        self.last_scan_date: Optional[str] = None
        self._symbol_industry_map: Dict[str, str] = self._load_symbol_industries()

        self.load_state()

    def _load_symbol_industries(self) -> Dict[str, str]:
        """Load symbol -> industry mapping from universe CSV for sector tracking."""
        mapping: Dict[str, str] = {}
        try:
            import csv
            universe_path = BASE_DIR / self.config.files.universe_csv
            if universe_path.exists():
                with open(universe_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        sym = str(row.get("Symbol", "")).strip().upper()
                        ind = str(row.get("Industry", "")).strip()
                        if sym and ind:
                            mapping[sym] = ind
        except Exception as e:
            logger.debug("Could not load sector mapping from universe CSV: %s", e)
        return mapping

    def _reconcile_cash(self) -> None:
        """
        Reconcile cash balance strictly against the strategy's fixed portfolio budget
        (config.capital.total_capital) rather than external Zerodha account balances.
        """
        total_invested = sum(pos.invested_amount for pos in self.positions.values())
        realized_pnl = sum(t.pnl for t in self.trade_history)
        self.cash_balance = round(max(0.0, self.total_capital + realized_pnl - total_invested), 2)

    def load_state(self) -> None:
        """Load portfolio state from JSON file."""
        if not self.state_file.exists():
            self.save_state()
            return

        # Always enforce baseline configuration from settings.yaml
        self.total_capital = float(self.config.capital.total_capital)
        self.max_positions = int(self.config.capital.max_positions)
        self.position_size = float(self.config.capital.position_size or (self.total_capital / max(1, self.max_positions)))

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.last_scan_date = data.get("last_scan_date")

            self.positions = {}
            for sym, pos_data in data.get("positions", {}).items():
                ind = pos_data.get("industry", "") or self._symbol_industry_map.get(sym, "")
                self.positions[sym] = Position(
                    symbol=pos_data["symbol"],
                    entry_date=pos_data["entry_date"],
                    entry_price=float(pos_data["entry_price"]),
                    quantity=int(pos_data["quantity"]),
                    invested_amount=float(pos_data["invested_amount"]),
                    stop_exit_level=float(pos_data.get("stop_exit_level", 0.0)),
                    notes=pos_data.get("notes", ""),
                    industry=ind,
                    partial_taken=bool(pos_data.get("partial_taken", False)),
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

            # Reconcile cash balance to guarantee isolation from external Zerodha cash
            self._reconcile_cash()

            logger.info("Loaded portfolio state: %d active positions, cash=₹%.2f (budget=₹%.2f)", len(self.positions), self.cash_balance, self.total_capital)
        except Exception as e:
            logger.error("Error loading portfolio state from %s: %s", self.state_file, e)

    def sync_with_exchange(self, kite: Any) -> Dict[str, Any]:
        """
        Synchronize portfolio state directly with Zerodha Kite Connect:
          1. Fetches live margins & available cash from kite.margins('equity').
          2. Fetches live Demat holdings from kite.holdings().
          3. Fetches live CNC day/net positions from kite.positions().
          4. Reconciles active positions with actual exchange holdings.
        """
        result: Dict[str, Any] = {
            "authenticated": False,
            "live_cash": None,
            "equity_margin": None,
            "holdings_count": 0,
            "positions_synced": 0,
            "positions_closed": 0,
            "user_id": None,
            "user_name": None,
            "error": None,
        }
        if not kite:
            return result

        try:
            # 1. Profile / Authentication verification
            profile = kite.profile()
            result["authenticated"] = True
            result["user_id"] = profile.get("user_id", "Unknown")
            result["user_name"] = profile.get("user_name", "")

            # 2. Fetch Live Margins (Available Cash) from Exchange for reporting/diagnostics
            try:
                margins = kite.margins("equity")
                live_cash = float(margins.get("available", {}).get("live_balance", 0.0) or margins.get("net", 0.0))
                result["live_cash"] = live_cash
                result["equity_margin"] = float(margins.get("net", 0.0))
                # Strategy operates strictly on a dedicated fixed portfolio budget (config.capital.total_capital).
                # Zerodha total account cash is kept for reporting only and NOT assigned to cash_balance.
                if live_cash < self.cash_balance:
                    logger.warning(
                        "Zerodha account available cash (₹%.2f) is lower than strategy portfolio cash (₹%.2f). "
                        "Ensure sufficient account funds before executing new entries.",
                        live_cash,
                        self.cash_balance,
                    )
            except Exception as e:
                logger.warning("Could not fetch equity margins from Kite: %s", e)

            # 3. Fetch Live Demat Holdings & CNC Positions from Exchange
            exchange_stocks: Dict[str, Dict[str, Any]] = {}
            holdings_ok = False
            positions_ok = False

            # A. Holdings (Settled Demat + T1 unsettled)
            try:
                demat_holdings = kite.holdings() or []
                holdings_ok = True
                for h in demat_holdings:
                    sym = str(h.get("tradingsymbol", "")).strip().upper()
                    qty = int(h.get("quantity", 0)) + int(h.get("t1_quantity", 0))
                    if qty > 0 and sym:
                        exchange_stocks[sym] = {
                            "symbol": sym,
                            "quantity": qty,
                            "average_price": float(h.get("average_price", 0.0)),
                            "last_price": float(h.get("last_price", 0.0)),
                            "pnl": float(h.get("pnl", 0.0)),
                            "source": "Demat Holdings",
                        }
            except Exception as e:
                logger.warning("Could not fetch Demat holdings from Kite: %s", e)

            # B. Net Positions (e.g. fresh CNC buys executed today not yet in Demat)
            try:
                pos_resp = kite.positions() or {}
                positions_ok = True
                net_positions = pos_resp.get("net", []) or []
                for p in net_positions:
                    sym = str(p.get("tradingsymbol", "")).strip().upper()
                    prod = str(p.get("product", ""))
                    qty = int(p.get("quantity", 0))
                    if prod == "CNC" and qty > 0 and sym:
                        if sym in exchange_stocks:
                            exchange_stocks[sym]["quantity"] += qty
                        else:
                            exchange_stocks[sym] = {
                                "symbol": sym,
                                "quantity": qty,
                                "average_price": float(p.get("average_price", 0.0)),
                                "last_price": float(p.get("last_price", 0.0)),
                                "pnl": float(p.get("pnl", 0.0)),
                                "source": "Today CNC Order",
                            }
            except Exception as e:
                logger.warning("Could not fetch open positions from Kite: %s", e)

            result["holdings_count"] = len(exchange_stocks)

            # 4. Reconcile with strategy portfolio (run even when exchange_stocks is empty if API calls succeeded)
            today_str = datetime.now().strftime("%Y-%m-%d")

            if holdings_ok and positions_ok:
                missing_syms = [s for s in self.positions.keys() if s not in exchange_stocks]
                ltp_prices: Dict[str, float] = {}
                if missing_syms:
                    try:
                        ltp_resp = kite.ltp([f"NSE:{s}" for s in missing_syms]) or {}
                        for s in missing_syms:
                            key = f"NSE:{s}"
                            if key in ltp_resp and ltp_resp[key].get("last_price"):
                                ltp_prices[s] = float(ltp_resp[key]["last_price"])
                    except Exception:
                        pass

                # Close positions no longer held on exchange
                for sym in missing_syms:
                    logger.info("Stock %s sold on exchange. Reconciling exit.", sym)
                    pos = self.positions.pop(sym)
                    exit_price = ltp_prices.get(sym, pos.entry_price)
                    exit_amount = round(exit_price * pos.quantity, 2)
                    pnl = round(exit_amount - pos.invested_amount, 2)
                    pnl_pct = round((pnl / pos.invested_amount) * 100.0, 2) if pos.invested_amount > 0 else 0.0
                    trade = TradeRecord(
                        symbol=sym,
                        entry_date=pos.entry_date,
                        exit_date=today_str,
                        entry_price=pos.entry_price,
                        exit_price=exit_price,
                        quantity=pos.quantity,
                        invested_amount=pos.invested_amount,
                        exit_amount=exit_amount,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason="Sold externally on Zerodha Exchange",
                    )
                    self.trade_history.append(trade)
                    result["positions_closed"] += 1

                # Add / update existing positions from exchange
                for sym, ex_data in exchange_stocks.items():
                    ind = self._symbol_industry_map.get(sym, "")
                    if sym in self.positions:
                        pos = self.positions[sym]
                        if not pos.industry and ind:
                            pos.industry = ind

                        new_qty = ex_data["quantity"]
                        if 0 < new_qty < pos.quantity:
                            sold_qty = pos.quantity - new_qty
                            sell_px = ex_data["last_price"] if ex_data["last_price"] > 0 else pos.entry_price
                            sold_cost = round(pos.entry_price * sold_qty, 2)
                            exit_amt = round(sell_px * sold_qty, 2)
                            pnl = round(exit_amt - sold_cost, 2)
                            pnl_pct = round((pnl / sold_cost) * 100.0, 2) if sold_cost > 0 else 0.0
                            self.trade_history.append(
                                TradeRecord(
                                    symbol=sym,
                                    entry_date=pos.entry_date,
                                    exit_date=today_str,
                                    entry_price=pos.entry_price,
                                    exit_price=sell_px,
                                    quantity=sold_qty,
                                    invested_amount=sold_cost,
                                    exit_amount=exit_amt,
                                    pnl=pnl,
                                    pnl_pct=pnl_pct,
                                    exit_reason="Partial Profit-Take / External Trim",
                                )
                            )
                            pos.partial_taken = True

                        pos.quantity = new_qty
                        if ex_data["average_price"] > 0:
                            pos.entry_price = ex_data["average_price"]
                        pos.invested_amount = round(pos.entry_price * pos.quantity, 2)
                    else:
                        if len(self.positions) < self.max_positions:
                            avg_px = ex_data["average_price"]
                            qty = ex_data["quantity"]
                            invested = round(avg_px * qty, 2)
                            self.positions[sym] = Position(
                                symbol=sym,
                                entry_date=today_str,
                                entry_price=avg_px,
                                quantity=qty,
                                invested_amount=invested,
                                notes=f"Auto-synced from {ex_data['source']}",
                                industry=ind,
                            )
                            result["positions_synced"] += 1

            self._reconcile_cash()
            self.save_state()
            return result

        except Exception as e:
            logger.error("Error during exchange synchronization: %s", e)
            result["error"] = str(e)
            return result

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

    def get_total_equity(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Return total portfolio equity (cash + market value if current_prices given, else invested amount)."""
        if current_prices:
            open_val = sum(
                current_prices.get(sym, pos.entry_price) * pos.quantity
                for sym, pos in self.positions.items()
            )
            return round(self.cash_balance + open_val, 2)
        invested = sum(pos.invested_amount for pos in self.positions.values())
        return round(self.cash_balance + invested, 2)

    def calculate_quantity(
        self,
        price: float,
        stop_price: Optional[float] = None,
        current_equity: Optional[float] = None,
        available_cash: Optional[float] = None,
    ) -> int:
        """
        Calculate quantity of shares.
        If sizing_mode == 'risk_pct':
            Risk Amount = Equity * (risk_per_trade_pct / 100)
            Risk Per Share = max(price - stop_price, price * 0.02)
            Quantity = floor(Risk Amount / Risk Per Share)
            Capped by max_position_size_pct and available cash balance.
        Otherwise:
            Quantity = floor(position_size / price)
        """
        if price <= 0:
            return 0

        eq = current_equity if current_equity is not None else self.get_total_equity()
        cash_cap = self.cash_balance if available_cash is None else available_cash

        if getattr(self.config.capital, "sizing_mode", "fixed") == "risk_pct":
            risk_pct = getattr(self.config.capital, "risk_per_trade_pct", 1.25)
            max_alloc_pct = getattr(self.config.capital, "max_position_size_pct", 15.0)

            # Determine stop distance (capped at max 8% stop)
            effective_stop = stop_price if stop_price is not None and stop_price > 0 else (price * 0.92)
            risk_per_share = max(price - effective_stop, price * 0.02)

            risk_budget = eq * (risk_pct / 100.0)
            qty = int(risk_budget // risk_per_share)

            # Cap by max position allocation (e.g. 15% of equity = ₹30,000 on ₹2,00,000)
            max_pos_budget = eq * (max_alloc_pct / 100.0)
            qty = min(qty, int(max_pos_budget // price))

            # Cap by available cash in strategy portfolio
            qty = min(qty, int(cash_cap // price))
            return max(0, qty)
        else:
            alloc = min(self.position_size, cash_cap)
            return max(0, int(alloc // price))

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
        self._reconcile_cash()
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
        self._reconcile_cash()
        self.save_state()
        logger.info("Closed position: %s @ ₹%.2f (PnL: ₹%.2f / %.2f%%) - Reason: %s", symbol, exit_price, pnl, pnl_pct, exit_reason)
        return trade

    def partial_close_position(
        self,
        symbol: str,
        exit_price: float,
        fraction: float = 0.5,
        exit_date: Optional[str] = None,
        exit_reason: str = "Partial Profit-Take (50% @ +30%)",
    ) -> Optional[TradeRecord]:
        """Partially close an active position (e.g. book 50% profits at +30%) and recycle cash."""
        if symbol not in self.positions:
            logger.warning("Cannot partial-exit %s: stock not found in active portfolio.", symbol)
            return None

        pos = self.positions[symbol]
        trim_qty = int(pos.quantity * fraction)
        if trim_qty <= 0 or trim_qty >= pos.quantity:
            logger.warning("Cannot partial-exit %s (qty=%d, fraction=%.2f): invalid trim quantity %d.", symbol, pos.quantity, fraction, trim_qty)
            return None

        today_str = exit_date or datetime.now().strftime("%Y-%m-%d")
        trim_cost = round(pos.entry_price * trim_qty, 2)
        exit_amount = round(exit_price * trim_qty, 2)
        pnl = round(exit_amount - trim_cost, 2)
        pnl_pct = round((pnl / trim_cost) * 100.0, 2) if trim_cost > 0 else 0.0

        pos.quantity -= trim_qty
        pos.invested_amount = round(pos.entry_price * pos.quantity, 2)
        pos.partial_taken = True

        trade = TradeRecord(
            symbol=symbol,
            entry_date=pos.entry_date,
            exit_date=today_str,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=trim_qty,
            invested_amount=trim_cost,
            exit_amount=exit_amount,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
        )
        self.trade_history.append(trade)
        self._reconcile_cash()
        self.save_state()
        logger.info(
            "Partial exit: %s x%d @ ₹%.2f (Remaining: %d | PnL: ₹%.2f / %.2f%%)",
            symbol,
            trim_qty,
            exit_price,
            pos.quantity,
            pnl,
            pnl_pct,
        )
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

