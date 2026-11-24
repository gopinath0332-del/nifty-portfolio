"""
scripts/test_capital_infusion.py
================================
Backtest simulator for real-life capital infusion scenarios in Nifty 500:
1. Baseline: ₹1,00,000 initial capital, 0 additions
2. Monthly SIP: ₹1,00,000 initial + ₹10,000 added on the 1st trading day of every month
3. Quarterly Infusion: ₹1,00,000 initial + ₹25,000 added every 3 months
4. Milestone / Lumpsum: ₹1,00,000 initial + ₹1,00,000 lump sum added after 1 year

Evaluates:
- Total Capital Injected (Principal)
- Ending Equity & Net Profit (Rupees)
- XIRR (Annualized Money-Weighted Return)
- Max Drawdown (%)
- Trades & Sizing Evolution
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tabulate import tabulate

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest import PortfolioBacktester, SimTrade


def compute_xirr(cash_flows: List[Tuple[pd.Timestamp, float]]) -> float:
    """
    Calculate annualized internal rate of return (XIRR).
    cash_flows: list of (timestamp, amount) where outflows/deposits are negative and final value is positive.
    """
    if len(cash_flows) < 2:
        return 0.0

    d0 = cash_flows[0][0]

    def npv(rate: float) -> float:
        if rate <= -1.0:
            return float("inf")
        val = 0.0
        for dt, cf in cash_flows:
            years = (dt - d0).total_seconds() / (365.25 * 86400.0)
            val += cf / ((1.0 + rate) ** years)
        return val

    # Binary search / Bisection solver
    low, high = -0.999, 10.0
    # Check if bounds bracket zero
    val_low = npv(low)
    val_high = npv(high)
    if val_low * val_high > 0:
        # Fallback expansion
        for high_candidate in [50.0, 100.0, 500.0]:
            if npv(high_candidate) < 0:
                high = high_candidate
                break
        else:
            return 0.0

    for _ in range(120):
        mid = (low + high) / 2.0
        val = npv(mid)
        if abs(val) < 1e-3:
            return mid * 100.0
        if val > 0:
            low = mid
        else:
            high = mid
    return mid * 100.0


class InfusionBacktester(PortfolioBacktester):
    def run_with_infusions(
        self,
        stock_dfs: Dict[str, pd.DataFrame],
        infusion_mode: str = "none",
        infusion_amount: float = 10000.0,
        lumpsum_dates: Optional[Dict[str, float]] = None,
    ) -> Dict[str, object]:
        """
        Execute backtest while supporting dynamic capital additions.
        Modes:
          - 'none': standard baseline
          - 'monthly_sip': adds infusion_amount on the first trading day of every new calendar month
          - 'quarterly_sip': adds infusion_amount on the first trading day of Jan, Apr, Jul, Oct
          - 'lumpsum': adds amounts specified in lumpsum_dates { 'YYYY-MM-DD': amount }
        """
        all_dates = set()
        for sym, df in stock_dfs.items():
            all_dates.update(df["dt"].tolist())

        sorted_dates = sorted(list(all_dates))
        if self.start_date:
            start_ts = pd.Timestamp(self.start_date)
            sorted_dates = [d for d in sorted_dates if d >= start_ts]
        if self.end_date:
            end_ts = pd.Timestamp(self.end_date)
            sorted_dates = [d for d in sorted_dates if d <= end_ts]

        if not sorted_dates:
            return {}

        # Load Nifty 500 Index for Market Regime Filter
        index_regime_map = {}
        index_csv = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(index_csv) and self.use_market_regime:
            try:
                df_idx = pd.read_csv(index_csv)
                df_idx["dt"] = pd.to_datetime(df_idx["date"]).dt.tz_localize(None)
                df_idx = df_idx.sort_values("dt").reset_index(drop=True)
                df_idx["ema_50"] = df_idx["close"].ewm(span=self.index_ema_len, adjust=False).mean()
                for _, r in df_idx.iterrows():
                    index_regime_map[r["dt"]] = bool(r["close"] >= r["ema_50"])
            except Exception as e:
                print("Warning: Failed loading Nifty 500 index:", e)

        stock_date_maps = {}
        for sym, df in stock_dfs.items():
            stock_date_maps[sym] = df.set_index("dt")

        cash = self.initial_capital
        total_injected = self.initial_capital
        positions = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []
        cash_flows: List[Tuple[pd.Timestamp, float]] = [(sorted_dates[0], -self.initial_capital)]
        infusion_log: List[Tuple[str, float, float]] = []

        pending_exits = {}
        pending_entries = []
        seen_months = set()
        seen_quarters = set()

        for current_idx, current_dt in enumerate(sorted_dates):
            date_str = current_dt.strftime("%Y-%m-%d")
            month_key = (current_dt.year, current_dt.month)
            quarter_key = (current_dt.year, (current_dt.month - 1) // 3 + 1)

            # Check for capital infusions
            add_cash = 0.0
            if infusion_mode == "monthly_sip":
                # Skip the very first month if it starts on day 1 (already funded by initial capital)
                if month_key not in seen_months:
                    seen_months.add(month_key)
                    if current_idx > 0:
                        add_cash = infusion_amount

            elif infusion_mode == "quarterly_sip":
                if quarter_key not in seen_quarters:
                    seen_quarters.add(quarter_key)
                    if current_idx > 0:
                        add_cash = infusion_amount

            elif infusion_mode == "lumpsum" and lumpsum_dates:
                for ls_date_str, amt in lumpsum_dates.items():
                    ls_dt = pd.Timestamp(ls_date_str)
                    if current_dt >= ls_dt and ls_date_str not in seen_months:
                        seen_months.add(ls_date_str)
                        add_cash = amt
                        break

            if add_cash > 0:
                cash += add_cash
                total_injected += add_cash
                cash_flows.append((current_dt, -add_cash))
                infusion_log.append((date_str, add_cash, cash))

            # ---------------------------------------------------------
            # Step A: Execute PENDING EXITS at Today's OPEN
            # ---------------------------------------------------------
            for sym, reason in list(pending_exits.items()):
                if sym in positions and sym in stock_date_maps:
                    stk_map = stock_date_maps[sym]
                    if current_dt in stk_map.index:
                        row = stk_map.loc[current_dt]
                        open_px = float(row["open"])
                        pos = positions.pop(sym)
                        exit_val = open_px * pos["qty"]
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_days = (current_dt - pos["entry_dt"]).days

                        peak_h = max(pos.get("peak_high", pos["entry_price"]), open_px)
                        trough_l = min(pos.get("trough_low", pos["entry_price"]), open_px)
                        mfe_pct = ((peak_h - pos["entry_price"]) / pos["entry_price"]) * 100.0
                        mae_pct = ((trough_l - pos["entry_price"]) / pos["entry_price"]) * 100.0
                        mfe_pnl = (peak_h - pos["entry_price"]) * pos["qty"]
                        mae_pnl = (trough_l - pos["entry_price"]) * pos["qty"]
                        capture_ratio = (pnl / mfe_pnl * 100.0) if mfe_pnl > 0 and pnl > 0 else 0.0

                        cash += exit_val
                        closed_trades.append(
                            SimTrade(
                                symbol=sym,
                                entry_date=pos["entry_date"],
                                exit_date=date_str,
                                entry_price=pos["entry_price"],
                                exit_price=open_px,
                                quantity=pos["qty"],
                                invested=pos["invested"],
                                exit_val=exit_val,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                holding_days=holding_days,
                                exit_reason=reason,
                                remaining_margin=round(cash, 2),
                                mfe_pct=round(mfe_pct, 2),
                                mae_pct=round(mae_pct, 2),
                                mfe_pnl=round(mfe_pnl, 2),
                                mae_pnl=round(mae_pnl, 2),
                                capture_ratio=round(capture_ratio, 1),
                            )
                        )
            pending_exits.clear()

            # ---------------------------------------------------------
            # Step B: Execute PENDING ENTRIES at Today's OPEN
            # ---------------------------------------------------------
            open_pos_val = sum(
                float(stock_date_maps[s].loc[current_dt]["open"]) * p["qty"]
                for s, p in positions.items()
                if s in stock_date_maps and current_dt in stock_date_maps[s].index
            )
            current_equity = cash + open_pos_val

            available_slots = self.max_positions - len(positions)
            for entry_item in pending_entries:
                if available_slots <= 0:
                    break
                sym = entry_item[0]
                low_20_prev = entry_item[3] if len(entry_item) > 3 else 0.0

                if sym in positions or sym not in stock_date_maps:
                    continue

                sec = self.symbol_industry_map.get(sym, "Unknown")
                if self.max_per_sector > 0:
                    sec_count = sum(1 for p in positions.values() if p.get("industry") == sec)
                    if sec_count >= self.max_per_sector:
                        continue

                stk_map = stock_date_maps[sym]
                if current_dt in stk_map.index:
                    row = stk_map.loc[current_dt]
                    open_px = float(row["open"])
                    if open_px <= 0:
                        continue

                    if self.sizing_mode == "risk_pct":
                        hard_stop_px = open_px * (1.0 - self.max_loss_pct / 100.0)
                        stop_px = max(low_20_prev, hard_stop_px)
                        risk_per_share = max(open_px - stop_px, open_px * 0.02)
                        risk_budget = current_equity * (self.risk_per_trade_pct / 100.0)
                        qty = int(risk_budget // risk_per_share)

                        max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                        qty = min(qty, int(max_alloc // open_px))
                        qty = min(qty, int(cash // open_px))
                    else:
                        qty = int(self.position_size // open_px)

                    if qty <= 0:
                        continue

                    invested = qty * open_px
                    if cash >= invested:
                        cash -= invested
                        positions[sym] = {
                            "qty": qty,
                            "entry_price": open_px,
                            "entry_date": date_str,
                            "entry_dt": current_dt,
                            "entry_trading_idx": current_idx,
                            "invested": invested,
                            "remaining_margin": cash,
                            "industry": sec,
                            "peak_high": open_px,
                            "trough_low": open_px,
                        }
                        available_slots -= 1
            pending_entries.clear()

            # ---------------------------------------------------------
            # Step C: Evaluate TODAY'S SIGNALS on EOD CLOSE
            # ---------------------------------------------------------
            is_market_bullish = True
            if self.use_market_regime and index_regime_map:
                is_market_bullish = index_regime_map.get(current_dt, True)

            todays_candidates = []

            for sym, df_map in stock_date_maps.items():
                if current_dt not in df_map.index:
                    continue

                row = df_map.loc[current_dt]
                close = float(row["close"])
                high_20_prev = float(row.get(f"high_{self.entry_len}_prev", 0))
                low_20_prev = float(row.get(f"low_{self.exit_len}_prev", 0))
                dist_52w = float(row.get("dist_52w_high_pct", -999))
                rvol = float(row.get("rvol", 1.0))
                ema_50 = float(row.get("ema_50", 0.0))
                sma_200 = float(row.get("sma_200", 0.0))

                # Track MFE / MAE
                if sym in positions:
                    pos = positions[sym]
                    high_today = float(row.get("high", close))
                    low_today = float(row.get("low", close))
                    pos["peak_high"] = max(pos.get("peak_high", pos["entry_price"]), high_today)
                    pos["trough_low"] = min(pos.get("trough_low", pos["entry_price"]), low_today)

                    cur_pnl_pct = ((close - pos["entry_price"]) / pos["entry_price"]) * 100.0
                    hard_stop = pos["entry_price"] * (1.0 - self.max_loss_pct / 100.0)

                    # Tier 1 Profit-Lock
                    if self.profit_lock_threshold_pct > 0 and cur_pnl_pct >= self.profit_lock_threshold_pct:
                        p_ema = float(row.get(f"ema_{self.profit_lock_ema_len}", 0.0))
                        if p_ema > 0 and close < p_ema:
                            pending_exits[sym] = f"Profit-Lock < {self.profit_lock_ema_len}EMA (+{cur_pnl_pct:.1f}%)"
                            continue

                    # Tier 2 Stage 2 Break
                    if self.exit_on_stage2_break and ema_50 > 0 and close < ema_50:
                        pending_exits[sym] = "Stage 2 Exit (< 50 EMA)"
                        continue

                    # Tenure cut
                    days_held = current_idx - pos.get("entry_trading_idx", current_idx)
                    if self.max_loss_holding_days > 0 and days_held >= self.max_loss_holding_days and cur_pnl_pct < 0:
                        pending_exits[sym] = f"Tenure Loss Cut ({days_held}d, {cur_pnl_pct:.1f}%)"
                        continue

                    # Fallback channel low or hard stop
                    if close < low_20_prev or close < hard_stop:
                        reason = f"Hard Stop (-{self.max_loss_pct}%)" if close < hard_stop else f"Channel Exit ({self.exit_len}D Low)"
                        pending_exits[sym] = reason
                        continue

                # Entry filter
                if is_market_bullish and sym not in positions and sym not in pending_exits:
                    if self.use_stage_2:
                        if not (ema_50 > sma_200 and close > ema_50):
                            continue
                    if close < self.min_stock_price:
                        continue
                    if dist_52w >= -self.within_52w_pct and close > high_20_prev and high_20_prev > 0:
                        breakout_pct = ((close - high_20_prev) / high_20_prev) * 100.0
                        score = breakout_pct * rvol
                        todays_candidates.append((sym, 0, score, low_20_prev))

            # Sort entries
            todays_candidates.sort(key=lambda x: x[2], reverse=True)
            pending_entries = todays_candidates[:self.max_positions]

            # Record daily equity
            close_pos_val = sum(
                float(stock_date_maps[s].loc[current_dt]["close"]) * p["qty"]
                for s, p in positions.items()
                if s in stock_date_maps and current_dt in stock_date_maps[s].index
            )
            daily_equity = cash + close_pos_val
            equity_curve.append((current_dt, daily_equity, cash, len(positions)))

        # Close any lingering positions on the final day for accounting
        if sorted_dates:
            last_dt = sorted_dates[-1]
            last_date_str = last_dt.strftime("%Y-%m-%d")
            for sym, pos in list(positions.items()):
                if sym in stock_date_maps and last_dt in stock_date_maps[sym].index:
                    close_px = float(stock_date_maps[sym].loc[last_dt]["close"])
                    exit_val = close_px * pos["qty"]
                    pnl = exit_val - pos["invested"]
                    pnl_pct = (pnl / pos["invested"]) * 100.0
                    holding_days = (last_dt - pos["entry_dt"]).days
                    cash += exit_val
                    closed_trades.append(
                        SimTrade(
                            symbol=sym,
                            entry_date=pos["entry_date"],
                            exit_date=last_date_str,
                            entry_price=pos["entry_price"],
                            exit_price=close_px,
                            quantity=pos["qty"],
                            invested=pos["invested"],
                            exit_val=exit_val,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            holding_days=holding_days,
                            exit_reason="End of Backtest",
                        )
                    )
            positions.clear()

        # Equity DF
        df_eq = pd.DataFrame(equity_curve, columns=["dt", "equity", "cash", "num_pos"]).set_index("dt")
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["drawdown"] = ((df_eq["equity"] - df_eq["peak"]) / df_eq["peak"]) * 100.0

        ending_equity = cash
        net_profit = ending_equity - total_injected
        net_profit_pct = (net_profit / total_injected) * 100.0

        # Final cash flow for XIRR
        cash_flows.append((sorted_dates[-1], ending_equity))
        xirr_val = compute_xirr(cash_flows)

        max_dd = df_eq["drawdown"].min()
        total_trades = len(closed_trades)
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        avg_trade_size = (sum(t.invested for t in closed_trades) / total_trades) if total_trades > 0 else 0.0

        return {
            "mode": infusion_mode,
            "initial_capital": self.initial_capital,
            "total_injected": total_injected,
            "ending_equity": ending_equity,
            "net_profit": net_profit,
            "net_profit_pct": net_profit_pct,
            "xirr_pct": xirr_val,
            "max_drawdown_pct": max_dd,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "avg_trade_size": avg_trade_size,
            "num_infusions": len(infusion_log),
        }


def run_benchmark():
    horizons = [
        ("2026 YTD", "2026-01-01", "2026-11-09"),
        ("Last 12 Months", "2025-11-10", "2026-11-09"),
        ("Last 2 Years", "2024-11-11", "2026-11-09"),
        ("Last 5 Years", "2021-11-10", "2026-11-09"),
    ]

    print("\nLoading master stock data for Nifty 500...", flush=True)
    loader = InfusionBacktester()
    stock_dfs = loader.load_universe_data()
    print(f"Loaded {len(stock_dfs)} stocks.", flush=True)

    configs = [
        ("1. Baseline (Zero Injections)", "none", 0.0, None),
        ("2. Monthly SIP (+₹10k/month)", "monthly_sip", 10000.0, None),
        ("3. Monthly SIP (+₹20k/month)", "monthly_sip", 20000.0, None),
        ("4. Quarterly (+₹50k/quarter)", "quarterly_sip", 50000.0, None),
    ]

    all_results = []

    for h_name, start_d, end_d in horizons:
        print(f"\n=================== Horizon: {h_name} ({start_d} to {end_d}) ===================", flush=True)
        for label, mode, amt, lumpsum in configs:
            bt = InfusionBacktester(
                initial_capital=100000.0,
                start_date=start_d,
                end_date=end_d,
                entry_len=50,
                exit_len=20,
            )
            res = bt.run_with_infusions(
                stock_dfs,
                infusion_mode=mode,
                infusion_amount=amt,
                lumpsum_dates=lumpsum,
            )
            row = {
                "Horizon": h_name,
                "Model": label,
                "Initial": f"₹{res['initial_capital']:,.0f}",
                "Total Invested": f"₹{res['total_injected']:,.0f}",
                "Ending Equity": f"₹{res['ending_equity']:,.2f}",
                "Net Profit": f"+₹{res['net_profit']:,.2f}",
                "Net Return": f"{res['net_profit_pct']:+.2f}%",
                "XIRR": f"{res['xirr_pct']:.2f}%",
                "Max DD": f"{res['max_drawdown_pct']:.2f}%",
                "Profit Factor": f"{res['profit_factor']:.2f}",
                "Win Rate": f"{res['win_rate']:.1f}%",
                "Trades": res['total_trades'],
                "Avg Trade Size": f"₹{res['avg_trade_size']:,.0f}",
            }
            all_results.append(row)
            print(
                f"[{label}] Invested: ₹{res['total_injected']:,.0f} -> Ending: ₹{res['ending_equity']:,.2f} | "
                f"Net Profit: +₹{res['net_profit']:,.2f} ({res['net_profit_pct']:+.1f}%) | "
                f"XIRR: {res['xirr_pct']:.2f}% | Max DD: {res['max_drawdown_pct']:.2f}% | Trades: {res['total_trades']}",
                flush=True,
            )

    df_res = pd.DataFrame(all_results)
    print("\n\n========================= FULL MULTI-HORIZON COMPARATIVE MATRIX =========================")
    print(tabulate(df_res, headers="keys", tablefmt="github", showindex=False))


if __name__ == "__main__":
    run_benchmark()
