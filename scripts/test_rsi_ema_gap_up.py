"""
scripts/test_rsi_ema_gap_up.py
==============================
Comprehensive Multi-Horizon Backtester for the User's RSI-on-EMA Gap-Up Strategy
across the Nifty 500 universe.

Strategy Rules:
  1. Indicator: RSI(14) applied on EMA(close) instead of raw Close (matching TradingView
     RSI Inputs -> Length: 14, Source: EMA).
  2. Entry Condition (Zero Lookahead):
     - Prior day EOD RSI_on_EMA[t-1] < 10.0 (deeply oversold smoothed trend)
     - Current day opens on a Gap Up: Open[t] > Close[t-1] (or >= min_gap_pct)
     - Liquidity hygiene: Prev Close >= ₹100.0 and 20D Avg Volume >= 50,000
     - Buy at Open[t]
  3. Stop Loss:
     - Stoploss points = Open[t] - Close[t-1]
     - Stop Price = Open[t] - (Open[t] - Close[t-1]) = Close[t-1] (Previous Day Close)
     - Checked intraday (Low[t] <= Stop -> exit at Stop; Open[k] <= Stop -> exit at Open[k])
  4. Exit Rule:
     - Close the trade when price closes below the 21 EMA (Close < EMA_21).
     - Tested in two modes:
       a) Unlatched (Raw): Exit whenever Close < 21 EMA at EOD (next day Open).
       b) Latched (Reclaim-then-Break): Hold with Gap-Fill Stop until price closes >= 21 EMA,
          then exit when Close < 21 EMA.

Benchmarked against the Repository Baseline (50D Donchian Trend-Following Engine)
across all 4 standard horizons:
  - 2026 YTD
  - Last 12 Months
  - Last 2 Years
  - Last 5 Years
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
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


def compute_wilder_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Compute Wilder's RSI (matching TradingView ta.rsi) on any price or indicator series."""
    diff = series.diff()
    gain = diff.clip(lower=0.0)
    loss = (-diff).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = np.where(avg_loss == 0.0, np.where(avg_gain == 0.0, 50.0, 100.0), rsi)
    return pd.Series(rsi, index=series.index)


def compute_gap_up_indicators(
    df: pd.DataFrame,
    ema_source_len: int = 21,
    rsi_len: int = 14,
    exit_ema_len: int = 21,
) -> pd.DataFrame:
    """Precompute EMA source, RSI-on-EMA, 21 EMA exit line, and prior-day references."""
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["ema_src"] = out["close"].ewm(span=ema_source_len, adjust=False).mean()
    out["rsi_ema"] = compute_wilder_rsi(out["ema_src"], length=rsi_len)
    out["rsi_ema_prev"] = out["rsi_ema"].shift(1)

    out["ema_21"] = out["close"].ewm(span=exit_ema_len, adjust=False).mean()
    out["prev_close"] = out["close"].shift(1)
    out["vol_sma_20"] = out["volume"].rolling(window=20, min_periods=10).mean()
    out["prev_vol_sma_20"] = out["vol_sma_20"].shift(1)
    out["gap_pct"] = ((out["open"] - out["prev_close"]) / out["prev_close"]) * 100.0
    return out


def build_fast_date_maps(
    raw_dfs: Dict[str, pd.DataFrame],
    ema_source_len: int = 21,
    rsi_len: int = 14,
    exit_ema_len: int = 21,
) -> Tuple[Dict[str, Dict[pd.Timestamp, tuple]], set]:
    """Precompute indicators once and pack into {sym: {dt: tuple}} for O(1) lookup."""
    stock_date_maps: Dict[str, Dict[pd.Timestamp, tuple]] = {}
    all_dts = set()
    for sym, df in raw_dfs.items():
        d = compute_gap_up_indicators(
            df,
            ema_source_len=ema_source_len,
            rsi_len=rsi_len,
            exit_ema_len=exit_ema_len,
        )
        dts = d["dt"].tolist()
        all_dts.update(dts)
        tuples = zip(
            d["open"].astype(float).tolist(),
            d["low"].astype(float).tolist(),
            d["close"].astype(float).tolist(),
            d["prev_close"].fillna(0.0).astype(float).tolist(),
            d["rsi_ema_prev"].fillna(999.0).astype(float).tolist(),
            d["ema_21"].astype(float).tolist(),
            d["prev_vol_sma_20"].fillna(0.0).astype(float).tolist(),
            d["gap_pct"].fillna(-999.0).astype(float).tolist(),
        )
        stock_date_maps[sym] = dict(zip(dts, tuples))
    return stock_date_maps, all_dts


class RsiEmaGapUpBacktester:
    def __init__(
        self,
        ema_source_len: int = 21,
        rsi_len: int = 14,
        rsi_threshold: float = 10.0,
        exit_ema_len: int = 21,
        min_gap_pct: float = 0.0,
        latch_21ema_exit: bool = False,
        use_market_regime: bool = False,
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 1.25,
        max_position_size_pct: float = 15.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        min_stock_price: float = 100.0,
        min_20d_avg_vol: float = 50000.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        universe_csv: str = "data/nifty500.csv",
    ):
        self.ema_source_len = ema_source_len
        self.rsi_len = rsi_len
        self.rsi_threshold = rsi_threshold
        self.exit_ema_len = exit_ema_len
        self.min_gap_pct = min_gap_pct
        self.latch_21ema_exit = latch_21ema_exit
        self.use_market_regime = use_market_regime
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.min_stock_price = min_stock_price
        self.min_20d_avg_vol = min_20d_avg_vol
        self.start_date = pd.to_datetime(start_date).tz_localize(None)
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None

        self.symbol_industry_map: Dict[str, str] = {}
        if os.path.exists(universe_csv):
            try:
                df_u = pd.read_csv(universe_csv)
                for _, r in df_u.iterrows():
                    self.symbol_industry_map[str(r["Symbol"]).strip()] = str(r["Industry"]).strip()
            except Exception:
                pass

    def run(
        self,
        raw_dfs: Dict[str, pd.DataFrame],
        precomputed_maps: Optional[Dict[str, Dict[pd.Timestamp, tuple]]] = None,
        all_dts_pre: Optional[set] = None,
    ) -> Dict:
        if precomputed_maps is not None and all_dts_pre is not None:
            stock_date_maps = precomputed_maps
            all_dts = all_dts_pre
        else:
            stock_date_maps, all_dts = build_fast_date_maps(
                raw_dfs,
                ema_source_len=self.ema_source_len,
                rsi_len=self.rsi_len,
                exit_ema_len=self.exit_ema_len,
            )

        index_regime_map: Dict[pd.Timestamp, bool] = {}
        index_csv = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(index_csv) and self.use_market_regime:
            df_idx = pd.read_csv(index_csv)
            df_idx["dt"] = pd.to_datetime(df_idx["date"]).dt.tz_localize(None)
            df_idx = df_idx.sort_values("dt").reset_index(drop=True)
            df_idx["ema_50"] = df_idx["close"].ewm(span=50, adjust=False).mean()
            for _, r in df_idx.iterrows():
                index_regime_map[r["dt"]] = bool(r["close"] >= r["ema_50"])

        sorted_dates = sorted(list(all_dts))
        sim_dates = [d for d in sorted_dates if d >= self.start_date]
        if self.end_date is not None:
            sim_dates = [d for d in sim_dates if d <= self.end_date]

        if not sim_dates:
            raise ValueError("No trading dates found in simulation range.")

        cash = self.initial_capital
        positions: Dict[str, dict] = {}
        pending_exits: Dict[str, str] = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []

        # Tuple layout: (open, low, close, prev_close, rsi_ema_prev, ema_21, prev_vol_sma_20, gap_pct)
        for current_dt in sim_dates:
            date_str = current_dt.strftime("%Y-%m-%d")

            # ---------------------------------------------------------
            # Step A: Execute Pending EOD 21 EMA Exits at Today's OPEN
            # ---------------------------------------------------------
            for sym, reason in list(pending_exits.items()):
                if sym in positions:
                    tup = stock_date_maps[sym].get(current_dt)
                    if tup is not None:
                        open_px = tup[0]
                        pos = positions.pop(sym)
                        exit_val = open_px * pos["qty"]
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
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
                                holding_days=(current_dt - pos["entry_dt"]).days,
                                exit_reason=reason,
                            )
                        )
            pending_exits.clear()

            # ---------------------------------------------------------
            # Step B: Evaluate & Execute Gap-Up Entries at Today's OPEN
            # ---------------------------------------------------------
            open_pos_val = 0.0
            for s, p in positions.items():
                tup = stock_date_maps[s].get(current_dt)
                open_pos_val += tup[0] * p["qty"] if tup is not None else p["invested"]
            current_equity = cash + open_pos_val
            is_market_bullish = index_regime_map.get(current_dt, True) if self.use_market_regime else True

            if is_market_bullish and len(positions) < self.max_positions:
                candidates = []
                for sym, df_map in stock_date_maps.items():
                    if sym in positions:
                        continue
                    tup = df_map.get(current_dt)
                    if tup is None:
                        continue
                    open_px, _, _, prev_close, rsi_prev, _, prev_vol_sma, gap_pct = tup
                    if (
                        prev_close >= self.min_stock_price
                        and prev_vol_sma >= self.min_20d_avg_vol
                        and rsi_prev < self.rsi_threshold
                        and open_px > prev_close
                        and gap_pct >= self.min_gap_pct
                    ):
                        candidates.append((sym, open_px, prev_close, gap_pct))

                # Rank by strongest Gap-Up %
                candidates.sort(key=lambda x: x[3], reverse=True)

                for sym, open_px, prev_close, _ in candidates:
                    if len(positions) >= self.max_positions:
                        break
                    sec = self.symbol_industry_map.get(sym, "Unknown")
                    if self.max_per_sector > 0:
                        sec_count = sum(1 for p in positions.values() if p["industry"] == sec)
                        if sec_count >= self.max_per_sector:
                            continue

                    # Exact Stop Loss from user rule:
                    # stoploss points = Open - Prev Close => stop_px = Prev Close
                    stop_px = prev_close
                    risk_per_share = max(open_px - stop_px, open_px * 0.005)
                    risk_budget = current_equity * (self.risk_per_trade_pct / 100.0)
                    qty = int(risk_budget // risk_per_share)
                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    qty = min(qty, int(max_alloc // open_px), int(cash // open_px))
                    if qty <= 0:
                        continue

                    invested = qty * open_px
                    if cash >= invested:
                        cash -= invested
                        positions[sym] = {
                            "qty": qty,
                            "entry_price": open_px,
                            "stop_loss": stop_px,
                            "invested": invested,
                            "entry_date": date_str,
                            "entry_dt": current_dt,
                            "industry": sec,
                            "reclaimed_21ema": False,
                        }

            # ---------------------------------------------------------
            # Step C: Intraday Stop-Loss & EOD 21 EMA Exit Evaluation
            # ---------------------------------------------------------
            for sym, pos in list(positions.items()):
                tup = stock_date_maps[sym].get(current_dt)
                if tup is None:
                    continue
                open_px, low_px, close_px, _, _, ema_21, _, _ = tup
                stop_px = pos["stop_loss"]

                # 1. Gap-down open below stop (for positions held >= 1 day)
                if current_dt > pos["entry_dt"] and open_px <= stop_px:
                    positions.pop(sym)
                    exit_val = open_px * pos["qty"]
                    pnl = exit_val - pos["invested"]
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
                            pnl_pct=(pnl / pos["invested"]) * 100.0,
                            holding_days=(current_dt - pos["entry_dt"]).days,
                            exit_reason="Gap-Down Stop (< Prev Close)",
                        )
                    )
                    continue

                # 2. Intraday stop hit (Low <= Prev Close)
                if low_px <= stop_px:
                    positions.pop(sym)
                    exit_val = stop_px * pos["qty"]
                    pnl = exit_val - pos["invested"]
                    cash += exit_val
                    closed_trades.append(
                        SimTrade(
                            symbol=sym,
                            entry_date=pos["entry_date"],
                            exit_date=date_str,
                            entry_price=pos["entry_price"],
                            exit_price=stop_px,
                            quantity=pos["qty"],
                            invested=pos["invested"],
                            exit_val=exit_val,
                            pnl=pnl,
                            pnl_pct=(pnl / pos["invested"]) * 100.0,
                            holding_days=(current_dt - pos["entry_dt"]).days,
                            exit_reason="Gap-Fill Stop (Low <= Prev Close)",
                        )
                    )
                    continue

                # 3. EOD Close < 21 EMA Exit
                if self.latch_21ema_exit:
                    if close_px >= ema_21:
                        pos["reclaimed_21ema"] = True
                    elif pos["reclaimed_21ema"] and close_px < ema_21:
                        pending_exits[sym] = "21 EMA Breakdown (Reclaimed -> Lost)"
                else:
                    if close_px < ema_21:
                        pending_exits[sym] = "Close < 21 EMA"

            # ---------------------------------------------------------
            # Step D: Mark-to-Market Portfolio Equity at EOD
            # ---------------------------------------------------------
            open_pos_val = 0.0
            for s, p in positions.items():
                tup = stock_date_maps[s].get(current_dt)
                open_pos_val += tup[2] * p["qty"] if tup is not None else p["invested"]
            equity_curve.append((current_dt, cash + open_pos_val, cash, len(positions)))

        df_eq = pd.DataFrame(equity_curve, columns=["date", "equity", "cash", "positions"]).set_index("date")
        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["drawdown"] = (df_eq["equity"] - df_eq["peak"]) / df_eq["peak"] * 100.0

        ending_equity = float(df_eq["equity"].iloc[-1])
        total_return_pct = ((ending_equity - self.initial_capital) / self.initial_capital) * 100.0
        max_drawdown_pct = float(df_eq["drawdown"].min())

        daily_returns = df_eq["equity"].pct_change().dropna()
        rf_daily = (1.0 + 0.065) ** (1.0 / 252.0) - 1.0
        excess = daily_returns - rf_daily
        sharpe = float(excess.mean() / excess.std() * np.sqrt(252.0)) if len(excess) > 1 and excess.std() > 0 else 0.0

        n_days = max(len(df_eq), 1)
        cagr_pct = ((ending_equity / self.initial_capital) ** (252.0 / n_days) - 1.0) * 100.0 if ending_equity > 0 else -100.0

        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        total_trades = len(closed_trades)
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        avg_win_pct = float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0
        avg_loss_pct = float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0
        avg_hold = float(np.mean([t.holding_days for t in closed_trades])) if closed_trades else 0.0

        exit_counts = Counter(t.exit_reason for t in closed_trades)

        return {
            "start_date": sim_dates[0].strftime("%Y-%m-%d"),
            "end_date": sim_dates[-1].strftime("%Y-%m-%d"),
            "initial_capital": self.initial_capital,
            "ending_equity": ending_equity,
            "net_profit": ending_equity - self.initial_capital,
            "total_return_pct": total_return_pct,
            "cagr_pct": cagr_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": sharpe,
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "payout_ratio": abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0,
            "avg_holding_days": avg_hold,
            "exit_counts": dict(exit_counts),
            "closed_trades": closed_trades,
        }


def run_benchmark() -> pd.DataFrame:
    print("=" * 96)
    print("  RSI(14) ON EMA < 10 GAP-UP STRATEGY VS BASELINE DONCHIAN ENGINE (NIFTY 500)")
    print("=" * 96)

    base_loader = PortfolioBacktester()
    raw_dfs = base_loader.load_universe_data(cache_dir="data/cache/daily_candles")
    print(f"Loaded {len(raw_dfs)} Nifty 500 stocks from cache.", flush=True)

    # Precompute fast lookup maps once per EMA source length
    precomputed = {
        21: build_fast_date_maps(raw_dfs, ema_source_len=21, rsi_len=14, exit_ema_len=21),
        9: build_fast_date_maps(raw_dfs, ema_source_len=9, rsi_len=14, exit_ema_len=21),
    }

    variants = [
        ("Baseline (50D Donchian)", None),
        ("Var 1: Raw EMA21 (Gap>0, Unlatched)", dict(ema_source_len=21, min_gap_pct=0.0, latch_21ema_exit=False, use_market_regime=False)),
        ("Var 2: Raw EMA9  (Gap>0, Unlatched)", dict(ema_source_len=9,  min_gap_pct=0.0, latch_21ema_exit=False, use_market_regime=False)),
        ("Var 3: EMA21 (Gap>0, Latched 21EMA)", dict(ema_source_len=21, min_gap_pct=0.0, latch_21ema_exit=True,  use_market_regime=False)),
        ("Var 4: EMA21 (Gap>=2%, Latched)",     dict(ema_source_len=21, min_gap_pct=2.0, latch_21ema_exit=True,  use_market_regime=False)),
        ("Var 5: EMA21 (Gap>=2%, Latched+Reg)", dict(ema_source_len=21, min_gap_pct=2.0, latch_21ema_exit=True,  use_market_regime=True)),
        ("Var 6: EMA9  (Gap>=2%, Latched)",     dict(ema_source_len=9,  min_gap_pct=2.0, latch_21ema_exit=True,  use_market_regime=False)),
    ]

    rows = []
    five_yr_exit_stats = {}

    for horizon_name, s_date, e_date in HORIZONS:
        print(f"--- Running Horizon: {horizon_name} ({s_date} to {e_date}) ---", flush=True)
        for label, params in variants:
            if params is None:
                res = PortfolioBacktester(start_date=s_date, end_date=e_date).run(raw_dfs)
                payout = abs(res["avg_win_pct"] / res["avg_loss_pct"]) if res["avg_loss_pct"] != 0 else 0.0
                rows.append({
                    "Horizon": horizon_name,
                    "Strategy": label,
                    "End Equity": f"₹{res['ending_equity']:,.2f}",
                    "Return %": f"{res['total_return_pct']:+.2f}%",
                    "CAGR %": f"{res['cagr_pct']:+.2f}%",
                    "Max DD %": f"{res['max_drawdown_pct']:.2f}%",
                    "Sharpe": f"{res['sharpe_ratio']:.2f}",
                    "PF": f"{res['profit_factor']:.2f}",
                    "Win Rate": f"{res['win_rate']:.1f}% ({res['total_trades']}T)",
                    "Avg W / Avg L": f"+{res['avg_win_pct']:.1f}% / {res['avg_loss_pct']:.1f}%",
                    "Payout": f"{payout:.2f}x",
                    "Avg Hold": f"{res['avg_holding_days']:.1f}d",
                })
            else:
                maps, dts = precomputed[params["ema_source_len"]]
                res = RsiEmaGapUpBacktester(start_date=s_date, end_date=e_date, **params).run(
                    raw_dfs, precomputed_maps=maps, all_dts_pre=dts
                )
                rows.append({
                    "Horizon": horizon_name,
                    "Strategy": label,
                    "End Equity": f"₹{res['ending_equity']:,.2f}",
                    "Return %": f"{res['total_return_pct']:+.2f}%",
                    "CAGR %": f"{res['cagr_pct']:+.2f}%",
                    "Max DD %": f"{res['max_drawdown_pct']:.2f}%",
                    "Sharpe": f"{res['sharpe_ratio']:.2f}",
                    "PF": f"{res['profit_factor']:.2f}",
                    "Win Rate": f"{res['win_rate']:.1f}% ({res['total_trades']}T)",
                    "Avg W / Avg L": f"+{res['avg_win_pct']:.1f}% / {res['avg_loss_pct']:.1f}%",
                    "Payout": f"{res['payout_ratio']:.2f}x",
                    "Avg Hold": f"{res['avg_holding_days']:.1f}d",
                })
                if horizon_name == "Last 5 Years":
                    five_yr_exit_stats[label] = res["exit_counts"]

    df_res = pd.DataFrame(rows)
    print("\n" + tabulate(df_res, headers="keys", tablefmt="fancy_grid", showindex=False))

    print("\n📊 5-YEAR EXIT REASON BREAKDOWN:")
    for label, counts in five_yr_exit_stats.items():
        total = sum(counts.values())
        summary = ", ".join(f"{k}: {v} ({v / max(total, 1) * 100:.1f}%)" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
        print(f"  - {label:<36}: {summary}")

    out_csv = "data/cache/rsi_ema_gap_up_benchmark_results.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved benchmark results to {out_csv}")
    return df_res


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest RSI(14) on EMA < 10 Gap-Up Strategy")
    parser.add_argument("--horizon", choices=["all", "ytd", "12m", "2y", "5y"], default="all")
    args = parser.parse_args()
    if args.horizon != "all":
        mapping = {"ytd": 0, "12m": 1, "2y": 2, "5y": 3}
        global HORIZONS
        HORIZONS = [HORIZONS[mapping[args.horizon]]]
    run_benchmark()


if __name__ == "__main__":
    main()
