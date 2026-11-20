"""
scripts/test_chartink_supertrend.py
===================================
Backtesting the User's Chartink Strategy:
  Entry Conditions:
    1. Daily SMA(Close, 20) > Daily SMA(Close, 200)
    2. Daily Close > Daily SMA(Close, 20)
    3. Daily Close > Daily Supertrend(7, 3)
    4. Daily RSI(14) > 60
    5. Daily Volume > 100,000
    
  Tests 3 Exit Variations:
    - Exit A: Pure Supertrend Flip (Daily Close < Supertrend)
    - Exit B: 20 SMA Breakdown (Daily Close < 20 SMA)
    - Exit C: Supertrend Flip + Hard Stop (-8%) + Profit-Lock at +25% (Institutional Tiered)
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tabulate import tabulate

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest import PortfolioBacktester, SimTrade

HORIZONS = [
    ("2026 YTD", "2026-01-01", "2026-11-09"),
    ("Last 12 Months", "2025-11-10", "2026-11-09"),
    ("Last 2 Years", "2024-11-11", "2026-11-09"),
    ("Last 5 Years", "2021-11-10", "2026-11-09"),
]


def compute_supertrend(df: pd.DataFrame, period: int = 7, multiplier: float = 3.0) -> pd.DataFrame:
    """Compute exact TradingView / Chartink Supertrend(7, 3)."""
    hl2 = (df["high"] + df["low"]) / 2.0
    hl = df["high"] - df["low"]
    hcp = (df["high"] - df["close"].shift(1)).abs()
    lcp = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    n = len(df)
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    direction = np.ones(n)

    close = df["close"].values
    bu = basic_upper.values
    bl = basic_lower.values

    start_idx = period
    final_upper[:start_idx] = bu[:start_idx]
    final_lower[:start_idx] = bl[:start_idx]
    supertrend[:start_idx] = bl[:start_idx]

    for i in range(start_idx, n):
        # Lower band
        if bl[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = bl[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Upper band
        if bu[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = bu[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Direction & Supertrend
        if direction[i - 1] == 1:
            if close[i] < final_lower[i]:
                direction[i] = -1
                supertrend[i] = final_upper[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lower[i]
        else:
            if close[i] > final_upper[i]:
                direction[i] = 1
                supertrend[i] = final_lower[i]
            else:
                direction[i] = -1
                supertrend[i] = final_upper[i]

    df["supertrend"] = supertrend
    df["supertrend_dir"] = direction
    return df


def load_and_enrich_chartink_data() -> Dict[str, pd.DataFrame]:
    """Load cached daily candles and compute all indicators for the Chartink strategy."""
    print("Loading and enriching universe with Chartink indicators...")
    files = glob.glob("data/cache/daily_candles/*.csv")
    stock_dfs = {}

    for f in files:
        base = os.path.basename(f)
        sym = base.split("_")[0]

        df = pd.read_csv(f)
        if len(df) < 220:
            continue

        df["dt"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.sort_values("dt").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 1. 20 SMA & 200 SMA
        df["sma_20"] = df["close"].rolling(20, min_periods=20).mean()
        df["sma_200"] = df["close"].rolling(200, min_periods=100).mean()

        # 2. RSI(14)
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

        # 3. Supertrend(7, 3)
        df = compute_supertrend(df, period=7, multiplier=3.0)

        # 4. Volume condition & Moving average of volume
        df["vol_sma_20"] = df["volume"].rolling(20, min_periods=10).mean()
        df["rvol"] = np.where(df["vol_sma_20"] > 0, df["volume"] / df["vol_sma_20"], 1.0)
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()

        # Check Chartink Entry Conditions:
        # 1. SMA(20) > SMA(200)
        # 2. Close > SMA(20)
        # 3. Close > Supertrend(7, 3) (i.e. direction == 1)
        # 4. RSI(14) > 60
        # 5. Volume > 100,000
        df["chartink_signal"] = (
            (df["sma_20"] > df["sma_200"])
            & (df["close"] > df["sma_20"])
            & (df["supertrend_dir"] == 1)
            & (df["rsi_14"] > 60.0)
            & (df["volume"] > 100000.0)
            & (df["close"] >= 100.0)
        )
        
        # Fresh crossover signal (became true today) or continuation
        df["chartink_fresh_signal"] = df["chartink_signal"] & (~df["chartink_signal"].shift(1).fillna(False))

        stock_dfs[sym] = df

    print(f"Loaded and enriched {len(stock_dfs)} stocks.")
    return stock_dfs


class ChartinkBacktester:
    def __init__(
        self,
        exit_mode: str = "supertrend",  # "supertrend", "sma_20", "tiered"
        initial_capital: float = 100000.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        risk_per_trade_pct: float = 1.25,
        max_position_size_pct: float = 15.0,
        max_loss_pct: float = 8.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        use_market_regime: bool = True,
    ):
        self.exit_mode = exit_mode
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_loss_pct = max_loss_pct
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None
        self.use_market_regime = use_market_regime

        self.symbol_industry_map: Dict[str, str] = {}
        if os.path.exists("data/nifty500.csv"):
            try:
                df_u = pd.read_csv("data/nifty500.csv")
                for _, r in df_u.iterrows():
                    self.symbol_industry_map[str(r["Symbol"]).strip()] = str(r["Industry"]).strip()
            except Exception:
                pass

    def run(self, stock_dfs: Dict[str, pd.DataFrame]) -> Dict:
        all_dates = set()
        for df in stock_dfs.values():
            all_dates.update(df["dt"])

        sorted_dates = sorted(list(all_dates))
        if self.start_date:
            sorted_dates = [d for d in sorted_dates if d >= self.start_date]
        if self.end_date:
            sorted_dates = [d for d in sorted_dates if d <= self.end_date]

        if not sorted_dates:
            raise ValueError("No dates in backtest range.")

        # Nifty 500 Market Regime
        index_regime_map = {}
        index_csv = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(index_csv):
            df_idx = pd.read_csv(index_csv)
            df_idx["dt"] = pd.to_datetime(df_idx["date"]).dt.tz_localize(None)
            df_idx = df_idx.sort_values("dt").reset_index(drop=True)
            df_idx["ema_50"] = df_idx["close"].ewm(span=50, adjust=False).mean()
            for _, r in df_idx.iterrows():
                index_regime_map[r["dt"]] = bool(r["close"] >= r["ema_50"])

        stock_date_maps = {sym: df.set_index("dt") for sym, df in stock_dfs.items()}

        cash = self.initial_capital
        positions = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []

        pending_exits = {}   # sym -> reason
        pending_entries = [] # (sym, close, score, supertrend_val)

        for current_idx, current_dt in enumerate(sorted_dates):
            date_str = current_dt.strftime("%Y-%m-%d")

            # ---------------------------------------------------------
            # Step A: Execute PENDING EXITS at Open
            # ---------------------------------------------------------
            for sym, reason in list(pending_exits.items()):
                if sym in positions and sym in stock_date_maps:
                    stk_map = stock_date_maps[sym]
                    if current_dt in stk_map.index:
                        row = stk_map.loc[current_dt]
                        open_px = float(row["open"])
                        pos = positions.pop(sym)

                        exit_val = pos["qty"] * open_px
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_days = (current_dt - pos["entry_dt"]).days

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
                            )
                        )
            pending_exits.clear()

            # ---------------------------------------------------------
            # Step B: Execute PENDING ENTRIES at Open
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
                st_val = entry_item[3]

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

                    hard_stop = open_px * (1.0 - self.max_loss_pct / 100.0)
                    stop_px = max(st_val, hard_stop)
                    risk_per_share = max(open_px - stop_px, open_px * 0.02)
                    risk_budget = current_equity * (self.risk_per_trade_pct / 100.0)
                    qty = int(risk_budget // risk_per_share)

                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    qty = min(qty, int(max_alloc // open_px))
                    qty = min(qty, int(cash // open_px))

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
                            "industry": sec,
                        }
                        available_slots -= 1
            pending_entries.clear()

            # ---------------------------------------------------------
            # Step C: Evaluate TODAY'S SIGNALS on EOD Close
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
                sma_20 = float(row.get("sma_20", 0.0))
                sma_200 = float(row.get("sma_200", 0.0))
                supertrend = float(row.get("supertrend", 0.0))
                st_dir = float(row.get("supertrend_dir", 1.0))
                rsi_14 = float(row.get("rsi_14", 50.0))
                ema_20 = float(row.get("ema_20", 0.0))
                rvol = float(row.get("rvol", 1.0))

                # Check Exits for active positions
                if sym in positions:
                    entry_px = positions[sym]["entry_price"]
                    unrealized_pnl_pct = ((close - entry_px) / entry_px) * 100.0

                    # 1. Hard Stop
                    if self.max_loss_pct > 0 and close <= entry_px * (1.0 - self.max_loss_pct / 100.0):
                        pending_exits[sym] = f"Hard Stop (-{self.max_loss_pct:.0f}%)"

                    # 2. Exit Mode logic
                    elif self.exit_mode == "supertrend":
                        # Exit when close falls below Supertrend or direction flips to -1
                        if st_dir == -1 or close < supertrend:
                            pending_exits[sym] = "Supertrend Flip (Bearish)"
                    elif self.exit_mode == "sma_20":
                        # Exit when close falls below 20 SMA
                        if close < sma_20:
                            pending_exits[sym] = "20 SMA Breakdown"
                    elif self.exit_mode == "tiered":
                        # Tiered: Profit-lock at +25% & Close < 20 EMA, or Supertrend Flip
                        if unrealized_pnl_pct >= 25.0 and ema_20 > 0 and close < ema_20:
                            pending_exits[sym] = f"Profit Lock (+{unrealized_pnl_pct:.1f}% & Close < 20 EMA)"
                        elif st_dir == -1 or close < supertrend:
                            pending_exits[sym] = "Supertrend Flip (Bearish)"

                # Check Entries
                elif is_market_bullish:
                    passes_filter = bool(row.get("chartink_signal", False))
                    fresh_signal = bool(row.get("chartink_fresh_signal", False))

                    if passes_filter:
                        # Rank by RSI * RVOL
                        score = rsi_14 * rvol * (1.5 if fresh_signal else 1.0)
                        todays_candidates.append((sym, close, score, supertrend))

            todays_candidates.sort(key=lambda x: x[2], reverse=True)
            pending_entries = todays_candidates

            # Step D: Mark-to-market
            open_pos_value = 0.0
            for sym, pos in positions.items():
                if sym in stock_date_maps and current_dt in stock_date_maps[sym].index:
                    c = float(stock_date_maps[sym].loc[current_dt]["close"])
                    open_pos_value += c * pos["qty"]
                else:
                    open_pos_value += pos["invested"]
            total_equity = cash + open_pos_value
            equity_curve.append((current_dt, total_equity, cash, len(positions)))

        # Summary Metrics
        df_eq = pd.DataFrame(equity_curve, columns=["date", "equity", "cash", "positions"]).set_index("date")
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["drawdown"] = (df_eq["equity"] - df_eq["peak"]) / df_eq["peak"] * 100.0

        ending_equity = df_eq["equity"].iloc[-1]
        total_return_pct = ((ending_equity - self.initial_capital) / self.initial_capital) * 100.0
        max_drawdown_pct = df_eq["drawdown"].min()

        daily_returns = df_eq["equity"].pct_change().dropna()
        rf_daily = (1.0 + 0.065) ** (1.0 / 252.0) - 1.0
        excess_returns = daily_returns - rf_daily
        sharpe = float(excess_returns.mean() / excess_returns.std() * np.sqrt(252.0)) if excess_returns.std() > 0 else 0.0

        downside = excess_returns[excess_returns < 0]
        sortino = float(excess_returns.mean() / downside.std() * np.sqrt(252.0)) if len(downside) > 0 and downside.std() > 0 else 0.0

        n_days = max(len(df_eq), 1)
        ann_return = ((ending_equity / self.initial_capital) ** (252.0 / n_days) - 1.0) * 100.0
        calmar = abs(ann_return / max_drawdown_pct) if max_drawdown_pct != 0 else 0.0

        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0

        total_gain = sum(t.pnl for t in wins)
        total_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else 0.0

        avg_win_pct = np.mean([t.pnl_pct for t in wins]) if wins else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in losses]) if losses else 0.0
        payout_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0
        avg_hold_days = np.mean([t.holding_days for t in closed_trades]) if closed_trades else 0.0

        return {
            "ending_equity": ending_equity,
            "total_return_pct": total_return_pct,
            "cagr_pct": ann_return,
            "max_drawdown_pct": max_drawdown_pct,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "total_trades": len(closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_loss_payout": payout_ratio,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "avg_holding_days": avg_hold_days,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "closed_trades": closed_trades,
            "equity_df": df_eq,
        }


def run_benchmark():
    stock_dfs = load_and_enrich_chartink_data()

    # Baseline loader for comparison
    from scripts.backtest import PortfolioBacktester
    bt_loader = PortfolioBacktester(entry_len=50, exit_len=20)
    base_dfs = bt_loader.load_universe_data()

    results = []

    for h_name, start_d, end_d in HORIZONS:
        print(f"\n=======================================================")
        print(f"Running Multi-Horizon Benchmark: {h_name} ({start_d} to {end_d})")
        print(f"=======================================================")

        # 1. Baseline Donchian Model
        bt_base = PortfolioBacktester(
            initial_capital=100000.0,
            entry_len=50,
            exit_len=20,
            start_date=start_d,
            end_date=end_d,
        )
        base_res = bt_base.run(base_dfs)
        results.append({
            "Strategy": "Baseline (50D Donchian Trend)",
            "Exit Model": "2-Tier Profit Lock & Stage 2",
            "Horizon": h_name,
            "Ending Equity": f"₹{base_res['ending_equity']:,.2f}",
            "Return %": f"{base_res['total_return_pct']:+.2f}%",
            "CAGR %": f"{base_res['cagr_pct']:.2f}%",
            "Max DD %": f"{base_res['max_drawdown_pct']:.2f}%",
            "Win Rate %": f"{base_res['win_rate']:.1f}%",
            "Profit Factor": f"{base_res['profit_factor']:.2f}",
            "Trades": base_res['total_trades'],
            "Avg Hold Days": f"{base_res['avg_holding_days']:.1f}d",
        })

        # 2. Chartink Strategy: Exit A (Pure Supertrend Flip)
        bt_st = ChartinkBacktester(
            exit_mode="supertrend",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        st_res = bt_st.run(stock_dfs)
        results.append({
            "Strategy": "Chartink (Supertrend+RSI>60+20SMA)",
            "Exit Model": "Supertrend(7,3) Flip",
            "Horizon": h_name,
            "Ending Equity": f"₹{st_res['ending_equity']:,.2f}",
            "Return %": f"{st_res['total_return_pct']:+.2f}%",
            "CAGR %": f"{st_res['cagr_pct']:.2f}%",
            "Max DD %": f"{st_res['max_drawdown_pct']:.2f}%",
            "Win Rate %": f"{st_res['win_rate']:.1f}%",
            "Profit Factor": f"{st_res['profit_factor']:.2f}",
            "Trades": st_res['total_trades'],
            "Avg Hold Days": f"{st_res['avg_holding_days']:.1f}d",
        })

        # 3. Chartink Strategy: Exit B (20 SMA Breakdown)
        bt_sma = ChartinkBacktester(
            exit_mode="sma_20",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        sma_res = bt_sma.run(stock_dfs)
        results.append({
            "Strategy": "Chartink (Supertrend+RSI>60+20SMA)",
            "Exit Model": "Close < 20 SMA Breakdown",
            "Horizon": h_name,
            "Ending Equity": f"₹{sma_res['ending_equity']:,.2f}",
            "Return %": f"{sma_res['total_return_pct']:+.2f}%",
            "CAGR %": f"{sma_res['cagr_pct']:.2f}%",
            "Max DD %": f"{sma_res['max_drawdown_pct']:.2f}%",
            "Win Rate %": f"{sma_res['win_rate']:.1f}%",
            "Profit Factor": f"{sma_res['profit_factor']:.2f}",
            "Trades": sma_res['total_trades'],
            "Avg Hold Days": f"{sma_res['avg_holding_days']:.1f}d",
        })

        # 4. Chartink Strategy: Exit C (Tiered Profit-Lock + Supertrend Flip)
        bt_tiered = ChartinkBacktester(
            exit_mode="tiered",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
        )
        tiered_res = bt_tiered.run(stock_dfs)
        results.append({
            "Strategy": "Chartink (Supertrend+RSI>60+20SMA)",
            "Exit Model": "Tiered (+25% Lock & ST Flip)",
            "Horizon": h_name,
            "Ending Equity": f"₹{tiered_res['ending_equity']:,.2f}",
            "Return %": f"{tiered_res['total_return_pct']:+.2f}%",
            "CAGR %": f"{tiered_res['cagr_pct']:.2f}%",
            "Max DD %": f"{tiered_res['max_drawdown_pct']:.2f}%",
            "Win Rate %": f"{tiered_res['win_rate']:.1f}%",
            "Profit Factor": f"{tiered_res['profit_factor']:.2f}",
            "Trades": tiered_res['total_trades'],
            "Avg Hold Days": f"{tiered_res['avg_holding_days']:.1f}d",
        })

    df_res = pd.DataFrame(results)
    print("\n\n" + "=" * 100)
    print("📊 COMPREHENSIVE BENCHMARK: CHARTINK SUPERTREND STRATEGY VS. BASELINE DONCHIAN")
    print("=" * 100)
    print(tabulate(df_res, headers="keys", tablefmt="fancy_grid", showindex=False))

    out_csv = "data/cache/chartink_supertrend_results.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved benchmark results to {out_csv}")


if __name__ == "__main__":
    run_benchmark()
