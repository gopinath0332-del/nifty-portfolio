"""
scripts/test_vcp.py
===================
Multi-Horizon Backtester for the Volatility Contraction Pattern (VCP) Strategy
across the Nifty 500 universe.

VCP Conditions (from specification):
  1. Prior Uptrend (Market Leader):
     - Cross-sectional Relative Strength (RS) Rank >= 70 across Nifty 500
       before/at the base (computed from weighted 3M/6M/9M/12M returns).
     - Optional Stage 2 trend filter: Close > 50 EMA > 200 SMA.
  2. The Base:
     - Pause of 3+ weeks (default 20 or 30 trading days prior to breakout).
     - Base depth <= 35%: (Base High - Base Low) / Base High <= 0.35.
  3. Contractions (Tightening):
     - 2nd half ATR% <= 0.9 * 1st half ATR% (where ATR% = TR / Close or ATR14 / Close).
     - Optional: 2nd half price range <= 1st half price range.
  4. Volume Dry-Up:
     - 2nd half average volume <= 0.9 * 1st half average volume.
     - Optional: Up-day volume >= Down-day volume in the base.
  5. The Pivot:
     - Ceiling at the top of the base: Pivot = max(High) over the base window.
  6. Breakout:
     - Fresh close above the pivot: Close[t] > Pivot and Close[t-1] <= Pivot.
     - Optional breakout RVOL filter (e.g. RVOL >= 1.2).
  7. Risk & Exits:
     - Dynamic risk-based sizing: 1.25% equity risk per trade, max 15% allocation,
       max 10 concurrent positions, max 3 per sector.
     - Realistic execution: Signal at Day T Close -> Execute at Day T+1 Open.
     - Compares VCP variants against the repository's Baseline Donchian Engine
       across 4 standard horizons (2026 YTD, Last 12M, Last 2Y, Last 5Y).
"""

from __future__ import annotations

import os
import sys
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


def compute_vcp_indicators(df: pd.DataFrame, base_len: int = 20) -> pd.DataFrame:
    """Precompute trend, ATR%, volume dry-up, and VCP base metrics for a single stock."""
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    prev_close = out["close"].shift(1)

    # Trend indicators
    out["ema_20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema_50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["sma_200"] = out["close"].rolling(window=200, min_periods=min(100, len(out))).mean()
    out["is_stage_2"] = (out["close"] > out["ema_50"]) & (out["ema_50"] > out["sma_200"])

    # 52-Week High & 20D Donchian Low (for optional fallback exit)
    out["high_52w"] = out["high"].rolling(window=252, min_periods=min(50, len(out))).max()
    out["low_20_prev"] = out["low"].shift(1).rolling(window=20, min_periods=20).min()

    # True Range & ATR % (daily TR / Close, and 14-day ATR / Close)
    tr1 = out["high"] - out["low"]
    tr2 = (out["high"] - prev_close).abs()
    tr3 = (out["low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["tr_pct"] = np.where(out["close"] > 0, tr / out["close"], np.nan)
    out["atr_14"] = tr.rolling(window=14, min_periods=14).mean()
    out["atr_pct_14"] = np.where(out["close"] > 0, out["atr_14"] / out["close"], np.nan)

    # Volume metrics
    out["vol_sma_20"] = out["volume"].rolling(window=20, min_periods=10).mean()
    out["rvol"] = np.where(out["vol_sma_20"] > 0, out["volume"] / out["vol_sma_20"], 1.0)

    # Up-day vs Down-day volume for buying/selling balance inside base
    is_up = out["close"] >= prev_close
    out["up_vol"] = np.where(is_up, out["volume"], 0.0)
    out["down_vol"] = np.where(~is_up, out["volume"], 0.0)

    # IBD-style weighted RS raw score (for cross-sectional ranking across universe)
    r63 = out["close"] / out["close"].shift(63) - 1.0
    r126 = out["close"] / out["close"].shift(126) - 1.0
    r189 = out["close"] / out["close"].shift(189) - 1.0
    r252 = out["close"] / out["close"].shift(252) - 1.0
    out["rs_raw"] = 0.4 * r63 + 0.2 * r126 + 0.2 * r189 + 0.2 * r252
    # Fallback to 6M return when < 252 bars exist
    out["rs_raw"] = out["rs_raw"].fillna(r126).fillna(r63)

    # Base window: [t - base_len, t - 1] (shifted by 1 so pivot is strictly prior to today)
    half = max(5, base_len // 2)
    h_shift1 = out["high"].shift(1)
    l_shift1 = out["low"].shift(1)
    v_shift1 = out["volume"].shift(1)
    atr_shift1 = out["tr_pct"].shift(1)

    # Full base high (Pivot), base low, and base depth
    out["vcp_pivot"] = h_shift1.rolling(window=base_len, min_periods=base_len).max()
    out["vcp_base_low"] = l_shift1.rolling(window=base_len, min_periods=base_len).min()
    out["vcp_base_depth_pct"] = np.where(
        out["vcp_pivot"] > 0,
        ((out["vcp_pivot"] - out["vcp_base_low"]) / out["vcp_pivot"]) * 100.0,
        100.0,
    )

    # 2nd half (most recent `half` days before t) vs 1st half (preceding `half` days)
    out["atr_pct_2nd"] = atr_shift1.rolling(window=half, min_periods=half).mean()
    out["atr_pct_1st"] = atr_shift1.shift(half).rolling(window=half, min_periods=half).mean()

    out["vol_2nd"] = v_shift1.rolling(window=half, min_periods=half).mean()
    out["vol_1st"] = v_shift1.shift(half).rolling(window=half, min_periods=half).mean()

    # Range contraction: 2nd half range % vs 1st half range %
    h_2nd = h_shift1.rolling(window=half, min_periods=half).max()
    l_2nd = l_shift1.rolling(window=half, min_periods=half).min()
    out["range_2nd_pct"] = np.where(h_2nd > 0, ((h_2nd - l_2nd) / h_2nd) * 100.0, 100.0)
    out["low_2nd"] = l_2nd

    h_1st = h_shift1.shift(half).rolling(window=half, min_periods=half).max()
    l_1st = l_shift1.shift(half).rolling(window=half, min_periods=half).min()
    out["range_1st_pct"] = np.where(h_1st > 0, ((h_1st - l_1st) / h_1st) * 100.0, 100.0)

    # Buying vs Selling volume in the base
    up_sum = out["up_vol"].shift(1).rolling(window=base_len, min_periods=base_len).sum()
    dn_sum = out["down_vol"].shift(1).rolling(window=base_len, min_periods=base_len).sum()
    out["base_up_ge_down_vol"] = up_sum >= dn_sum

    return out


def compute_universe_rs_ranks(stock_dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Compute cross-sectional RS percentile rank (0-100) across all stocks per date."""
    rs_series = {}
    for sym, df in stock_dfs.items():
        if "rs_raw" in df.columns:
            s = df.set_index("dt")["rs_raw"]
            rs_series[sym] = s

    rs_panel = pd.DataFrame(rs_series)
    rs_rank_panel = rs_panel.rank(axis=1, pct=True) * 100.0

    updated = {}
    for sym, df in stock_dfs.items():
        d = df.copy()
        if sym in rs_rank_panel.columns:
            rank_map = rs_rank_panel[sym]
            d["rs_rank"] = d["dt"].map(rank_map)
        else:
            d["rs_rank"] = np.nan
        updated[sym] = d
    return updated


class VCPBacktester:
    def __init__(
        self,
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 1.25,
        max_position_size_pct: float = 15.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        base_len: int = 20,
        min_rs_rank: float = 70.0,
        max_base_depth_pct: float = 35.0,
        atr_contraction_ratio: float = 0.9,
        vol_dryup_ratio: float = 0.9,
        require_range_contraction: bool = False,
        require_up_vol_dom: bool = False,
        require_stage_2: bool = True,
        min_rvol: float = 1.0,
        min_stock_price: float = 100.0,
        min_vol_sma_20: float = 50000.0,
        max_loss_pct: float = 8.0,
        stop_mode: str = "tight_low",  # "tight_low" (2nd half low capped at -8%) or "hard_8"
        exit_mode: str = "repo_2tier",  # "repo_2tier" or "ema20_trail" or "ema50_trail"
        use_market_regime: bool = True,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        universe_csv: str = "data/nifty500.csv",
    ):
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.base_len = base_len
        self.min_rs_rank = min_rs_rank
        self.max_base_depth_pct = max_base_depth_pct
        self.atr_contraction_ratio = atr_contraction_ratio
        self.vol_dryup_ratio = vol_dryup_ratio
        self.require_range_contraction = require_range_contraction
        self.require_up_vol_dom = require_up_vol_dom
        self.require_stage_2 = require_stage_2
        self.min_rvol = min_rvol
        self.min_stock_price = min_stock_price
        self.min_vol_sma_20 = min_vol_sma_20
        self.max_loss_pct = max_loss_pct
        self.stop_mode = stop_mode
        self.exit_mode = exit_mode
        self.use_market_regime = use_market_regime
        self.start_date = start_date
        self.end_date = end_date
        self.universe_csv = universe_csv

        self.symbol_industry_map: Dict[str, str] = {}
        self._load_universe()

    def _load_universe(self):
        if os.path.exists(self.universe_csv):
            try:
                df = pd.read_csv(self.universe_csv)
                for _, row in df.iterrows():
                    sym = str(row.get("symbol", row.get("Symbol", ""))).strip()
                    sec = str(row.get("industry", row.get("Industry", "Unknown"))).strip()
                    if sym:
                        self.symbol_industry_map[sym] = sec
            except Exception:
                pass

    def prepare_data(self, raw_dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        stock_dfs = {sym: compute_vcp_indicators(df, base_len=self.base_len) for sym, df in raw_dfs.items()}
        return compute_universe_rs_ranks(stock_dfs)

    def run(self, prepared_dfs: Dict[str, pd.DataFrame]) -> Tuple[Dict, List[SimTrade], pd.DataFrame]:
        all_dts = set()
        for df in prepared_dfs.values():
            all_dts.update(df["dt"].tolist())

        # Market Regime Filter: Nifty 500 >= 50 EMA
        index_regime = {}
        idx_file = "data/cache/NIFTY500_INDEX.csv"
        if os.path.exists(idx_file) and self.use_market_regime:
            try:
                idf = pd.read_csv(idx_file)
                idf["dt"] = pd.to_datetime(idf["date"]).dt.tz_localize(None)
                idf = idf.sort_values("dt").reset_index(drop=True)
                idf["ema_50"] = idf["close"].ewm(span=50, adjust=False).mean()
                for _, r in idf.iterrows():
                    index_regime[r["dt"]] = bool(r["close"] >= r["ema_50"])
            except Exception:
                pass

        sorted_dates = sorted(list(all_dts))
        start_dt = pd.to_datetime(self.start_date)
        end_dt = pd.to_datetime(self.end_date) if self.end_date else sorted_dates[-1]
        sim_dates = [d for d in sorted_dates if start_dt <= d <= end_dt]

        if not sim_dates:
            return {}, [], pd.DataFrame()

        # Pre-index each stock's DataFrame into fast dict[dt -> tuple] for O(1) lookup
        # Columns needed: (open, low, close, ema_20, ema_50, low_20_prev, vol_sma_20,
        #                  rs_rank, is_stage_2, vcp_pivot, vcp_base_depth_pct,
        #                  atr_pct_1st, atr_pct_2nd, vol_1st, vol_2nd,
        #                  range_1st_pct, range_2nd_pct, base_up_ge_down_vol,
        #                  rvol, low_2nd, prev_close)
        stock_fast: Dict[str, Dict[pd.Timestamp, tuple]] = {}
        for sym, df in prepared_dfs.items():
            d = df.copy()
            d["prev_close_bar"] = d["close"].shift(1)
            cols = [
                "open", "low", "close", "ema_20", "ema_50", "low_20_prev",
                "vol_sma_20", "rs_rank", "is_stage_2", "vcp_pivot",
                "vcp_base_depth_pct", "atr_pct_1st", "atr_pct_2nd",
                "vol_1st", "vol_2nd", "range_1st_pct", "range_2nd_pct",
                "base_up_ge_down_vol", "rvol", "low_2nd", "prev_close_bar",
            ]
            arr = d[cols].to_numpy()
            dts = d["dt"].tolist()
            stock_fast[sym] = {dts[i]: tuple(arr[i]) for i in range(len(dts))}

        cash = self.initial_capital
        positions: Dict[str, dict] = {}
        closed_trades: List[SimTrade] = []
        equity_curve: List[dict] = []

        pending_exits: Dict[str, str] = {}
        pending_partial_exits: Dict[str, Tuple[float, str]] = {}
        pending_entries: List[dict] = []

        for current_dt in sim_dates:
            date_str = current_dt.strftime("%Y-%m-%d")

            # STEP A1: Execute Pending Full Exits at Today's OPEN
            for sym, reason in list(pending_exits.items()):
                if sym in positions and sym in stock_fast:
                    bar = stock_fast[sym].get(current_dt)
                    if bar is not None:
                        open_px = float(bar[0])
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

            # STEP A2: Execute Pending Partial Profit-Taking at Today's OPEN
            for sym, (frac, reason) in list(pending_partial_exits.items()):
                if sym in positions and sym in stock_fast:
                    bar = stock_fast[sym].get(current_dt)
                    if bar is not None:
                        pos = positions[sym]
                        if not pos.get("partial_taken", False) and pos["qty"] >= 2:
                            open_px = float(bar[0])
                            sell_qty = max(1, int(pos["qty"] * frac))
                            if sell_qty < pos["qty"]:
                                sold_invested = pos["invested"] * (sell_qty / pos["qty"])
                                exit_val = sell_qty * open_px
                                pnl = exit_val - sold_invested
                                pnl_pct = (pnl / sold_invested) * 100.0
                                holding_days = (current_dt - pos["entry_dt"]).days

                                cash += exit_val
                                pos["qty"] -= sell_qty
                                pos["invested"] -= sold_invested
                                pos["partial_taken"] = True

                                closed_trades.append(
                                    SimTrade(
                                        symbol=sym,
                                        entry_date=pos["entry_date"],
                                        exit_date=date_str,
                                        entry_price=pos["entry_price"],
                                        exit_price=open_px,
                                        quantity=sell_qty,
                                        invested=sold_invested,
                                        exit_val=exit_val,
                                        pnl=pnl,
                                        pnl_pct=pnl_pct,
                                        holding_days=holding_days,
                                        exit_reason=reason,
                                    )
                                )
            pending_partial_exits.clear()

            # STEP B: Execute Pending Entries at Today's OPEN
            current_equity = cash
            for s, pos in positions.items():
                b = stock_fast.get(s, {}).get(current_dt)
                current_equity += pos["qty"] * float(b[2]) if b is not None else pos["invested"]

            for cand in pending_entries:
                sym = cand["symbol"]
                if sym in positions:
                    continue
                if len(positions) >= self.max_positions or cash < 5000:
                    break

                sec = self.symbol_industry_map.get(sym, "Unknown")
                curr_sec_count = sum(1 for p in positions.values() if p["sector"] == sec)
                if curr_sec_count >= self.max_per_sector:
                    continue

                bar = stock_fast.get(sym, {}).get(current_dt)
                if bar is not None:
                    open_px = float(bar[0])
                    stop_px = cand["stop_loss"]

                    if self.stop_mode == "hard_8":
                        stop_px = open_px * (1.0 - self.max_loss_pct / 100.0)
                    else:
                        hard_stop = open_px * (1.0 - self.max_loss_pct / 100.0)
                        stop_px = max(stop_px, hard_stop)

                    if open_px <= stop_px:
                        continue

                    risk_amount = current_equity * (self.risk_per_trade_pct / 100.0)
                    risk_per_share = open_px - stop_px
                    qty = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    qty = min(qty, int(max_alloc / open_px) if open_px > 0 else 0)
                    qty = min(qty, int(cash / open_px) if open_px > 0 else 0)

                    if qty <= 0:
                        continue

                    inv = qty * open_px
                    cash -= inv
                    positions[sym] = {
                        "symbol": sym,
                        "qty": qty,
                        "entry_price": open_px,
                        "invested": inv,
                        "entry_date": date_str,
                        "entry_dt": current_dt,
                        "stop_loss": stop_px,
                        "sector": sec,
                        "days_held": 0,
                        "partial_taken": False,
                    }
            pending_entries.clear()

            # STEP C: Intraday Stop Loss & EOD Exit Evaluation
            for sym, pos in list(positions.items()):
                bar = stock_fast.get(sym, {}).get(current_dt)
                if bar is not None:
                    pos["days_held"] += 1
                    open_px = float(bar[0])
                    low_px = float(bar[1])
                    close_px = float(bar[2])

                    # 1. Intraday hard stop loss
                    if low_px <= pos["stop_loss"]:
                        exit_px = min(pos["stop_loss"], open_px)
                        exit_val = pos["qty"] * exit_px
                        pnl = exit_val - pos["invested"]
                        pnl_pct = (pnl / pos["invested"]) * 100.0
                        holding_days = (current_dt - pos["entry_dt"]).days

                        cash += exit_val
                        positions.pop(sym)
                        closed_trades.append(
                            SimTrade(
                                symbol=sym,
                                entry_date=pos["entry_date"],
                                exit_date=date_str,
                                entry_price=pos["entry_price"],
                                exit_price=exit_px,
                                quantity=pos["qty"],
                                invested=pos["invested"],
                                exit_val=exit_val,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                holding_days=holding_days,
                                exit_reason="Stop Loss (-8%)",
                            )
                        )
                        continue

                    # 2. EOD Trailing / Structural Exits
                    unr_pct = ((close_px - pos["entry_price"]) / pos["entry_price"]) * 100.0
                    ema_20 = float(bar[3])
                    ema_50 = float(bar[4])
                    low_20_prev = bar[5]

                    if self.exit_mode == "repo_2tier":
                        if unr_pct >= 25.0 and close_px < ema_20:
                            pending_exits[sym] = "Profit-Lock (20 EMA)"
                        elif close_px < ema_50:
                            pending_exits[sym] = "Stage 2 Break (50 EMA)"
                        elif not pd.isna(low_20_prev) and close_px < float(low_20_prev):
                            pending_exits[sym] = "20D Donchian Low"
                        elif pos["days_held"] >= 20 and unr_pct < 0:
                            pending_exits[sym] = "Tenure Cut (20D)"
                        elif not pos.get("partial_taken", False) and unr_pct >= 30.0:
                            pending_partial_exits[sym] = (0.5, "Partial TP (+30%)")
                    elif self.exit_mode == "ema20_trail":
                        if close_px < ema_20:
                            pending_exits[sym] = "Close < 20 EMA"
                    elif self.exit_mode == "ema50_trail":
                        if close_px < ema_50:
                            pending_exits[sym] = "Close < 50 EMA"

            # Record Daily Equity
            eod_equity = cash
            for s, pos in positions.items():
                b = stock_fast.get(s, {}).get(current_dt)
                eod_equity += pos["qty"] * float(b[2]) if b is not None else pos["invested"]
            equity_curve.append({"date": current_dt, "equity": eod_equity, "cash": cash})

            # STEP D: EOD VCP Entry Scanner
            if self.use_market_regime and not index_regime.get(current_dt, True):
                continue

            available_slots = self.max_positions - (len(positions) - len(pending_exits))
            if available_slots <= 0:
                continue

            candidates = []
            for sym, stk_map in stock_fast.items():
                if sym in positions or sym in pending_exits:
                    continue
                bar = stk_map.get(current_dt)
                if bar is None:
                    continue

                close_px = float(bar[2])
                if close_px < self.min_stock_price:
                    continue

                vol_sma_20 = bar[6]
                if pd.isna(vol_sma_20) or float(vol_sma_20) < self.min_vol_sma_20:
                    continue

                # 1. Prior Uptrend: RS >= 70 & optional Stage 2
                rs_rank = bar[7]
                if pd.isna(rs_rank) or float(rs_rank) < self.min_rs_rank:
                    continue
                if self.require_stage_2 and not bool(bar[8]):
                    continue

                # 2. The Base: 3+ weeks, never deeper than 35%
                pivot = bar[9]
                base_depth = bar[10]
                if pd.isna(pivot) or pd.isna(base_depth) or float(base_depth) > self.max_base_depth_pct:
                    continue

                # 3. Contractions: 2nd half ATR% <= 0.9x 1st half ATR%
                atr_1 = bar[11]
                atr_2 = bar[12]
                if pd.isna(atr_1) or pd.isna(atr_2) or float(atr_1) <= 0:
                    continue
                if float(atr_2) > self.atr_contraction_ratio * float(atr_1):
                    continue

                if self.require_range_contraction:
                    if float(bar[16]) > float(bar[15]):
                        continue

                # 4. Volume Dry-Up: 2nd half vol <= 0.9x 1st half vol
                v_1 = bar[13]
                v_2 = bar[14]
                if pd.isna(v_1) or pd.isna(v_2) or float(v_1) <= 0:
                    continue
                if float(v_2) > self.vol_dryup_ratio * float(v_1):
                    continue

                if self.require_up_vol_dom and not bool(bar[17]):
                    continue

                # 5 & 6. Pivot & Breakout: Close > Pivot (fresh breakout: prev close <= pivot)
                pivot_f = float(pivot)
                if close_px <= pivot_f:
                    continue

                prev_close = bar[20]
                if not pd.isna(prev_close) and float(prev_close) > pivot_f:
                    continue

                rvol = float(bar[18]) if not pd.isna(bar[18]) else 1.0
                if rvol < self.min_rvol:
                    continue

                breakout_pct = ((close_px - pivot_f) / pivot_f) * 100.0
                score = float(rs_rank) * (1.0 + breakout_pct / 100.0) * min(rvol, 3.0)

                low_2nd = bar[19]
                stop_loss = float(low_2nd) if not pd.isna(low_2nd) else close_px * 0.92

                candidates.append({
                    "symbol": sym,
                    "score": score,
                    "stop_loss": stop_loss,
                    "close": close_px,
                })

            if candidates:
                candidates.sort(key=lambda x: x["score"], reverse=True)
                pending_entries = candidates[:available_slots]

        # Close remaining positions at end date
        final_dt = sim_dates[-1]
        final_date_str = final_dt.strftime("%Y-%m-%d")
        for sym, pos in list(positions.items()):
            b = stock_fast.get(sym, {}).get(final_dt)
            close_px = float(b[2]) if b is not None else pos["entry_price"]
            exit_val = pos["qty"] * close_px
            pnl = exit_val - pos["invested"]
            pnl_pct = (pnl / pos["invested"]) * 100.0
            holding_days = (final_dt - pos["entry_dt"]).days
            cash += exit_val
            closed_trades.append(
                SimTrade(
                    symbol=sym,
                    entry_date=pos["entry_date"],
                    exit_date=final_date_str,
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

        df_eq = pd.DataFrame(equity_curve)
        metrics = self._calculate_metrics(closed_trades, df_eq)
        return metrics, closed_trades, df_eq

    def _calculate_metrics(self, trades: List[SimTrade], df_eq: pd.DataFrame) -> Dict:
        if df_eq.empty:
            return {
                "total_ret_pct": 0.0,
                "cagr": 0.0,
                "max_dd_pct": 0.0,
                "profit_factor": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "sharpe": 0.0,
            }

        final_equity = float(df_eq["equity"].iloc[-1])
        total_pnl = final_equity - self.initial_capital
        total_ret_pct = (total_pnl / self.initial_capital) * 100.0

        df_eq["peak"] = df_eq["equity"].cummax()
        df_eq["dd"] = (df_eq["equity"] - df_eq["peak"]) / df_eq["peak"] * 100.0
        max_dd = float(df_eq["dd"].min())

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        start_d = pd.to_datetime(self.start_date)
        end_d = pd.to_datetime(self.end_date) if self.end_date else pd.to_datetime(df_eq["date"].iloc[-1])
        days = max(1, (end_d - start_d).days)
        years = days / 365.25
        cagr = (((final_equity / self.initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if years > 0 and final_equity > 0 else 0.0

        daily_ret = df_eq["equity"].pct_change().dropna()
        rf_daily = 0.065 / 252.0
        sharpe = (
            ((daily_ret.mean() - rf_daily) / daily_ret.std()) * np.sqrt(252.0)
            if len(daily_ret) > 1 and daily_ret.std() > 0
            else 0.0
        )

        return {
            "final_equity": final_equity,
            "total_ret_pct": total_ret_pct,
            "cagr": cagr,
            "max_dd_pct": max_dd,
            "profit_factor": profit_factor,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "sharpe": sharpe,
            "avg_win_pct": float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0,
            "avg_loss_pct": float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0,
        }


def run_benchmark():
    print("=" * 95)
    print("  VOLATILITY CONTRACTION PATTERN (VCP) VS BASELINE DONCHIAN ENGINE (NIFTY 500)")
    print("=" * 95)

    base_engine = PortfolioBacktester()
    raw_dfs = base_engine.load_universe_data(cache_dir="data/cache/daily_candles")
    print(f"Loaded {len(raw_dfs)} stock candle datasets from cache.")

    # Precompute VCP indicators + cross-sectional RS rank once per base length
    print("Precomputing VCP indicators & cross-sectional RS ranks (20D & 30D bases)...")
    vcp_20_prep = VCPBacktester(base_len=20).prepare_data(raw_dfs)
    vcp_30_prep = VCPBacktester(base_len=30).prepare_data(raw_dfs)

    summary_rows = []

    for name, s_date, e_date in HORIZONS:
        print(f"--- Running Horizon: {name} ({s_date} to {e_date}) ---")

        # 1. Baseline Donchian Engine
        base_bt = PortfolioBacktester(start_date=s_date, end_date=e_date)
        base_m = base_bt.run(raw_dfs)

        # 2. VCP Spec (20D / 4W Base, RS>=70, Depth<=35%, ATR<=0.9x, Vol<=0.9x, Repo 2-Tier Exit)
        vcp20_bt = VCPBacktester(
            base_len=20,
            min_rs_rank=70.0,
            max_base_depth_pct=35.0,
            atr_contraction_ratio=0.9,
            vol_dryup_ratio=0.9,
            require_stage_2=True,
            min_rvol=1.0,
            exit_mode="repo_2tier",
            start_date=s_date,
            end_date=e_date,
        )
        vcp20_m, _, _ = vcp20_bt.run(vcp_20_prep)

        # 3. VCP Spec + RVOL >= 1.2 + Range Contraction (20D Base)
        vcp20_strict_bt = VCPBacktester(
            base_len=20,
            min_rs_rank=70.0,
            max_base_depth_pct=35.0,
            atr_contraction_ratio=0.9,
            vol_dryup_ratio=0.9,
            require_range_contraction=True,
            require_up_vol_dom=True,
            require_stage_2=True,
            min_rvol=1.2,
            exit_mode="repo_2tier",
            start_date=s_date,
            end_date=e_date,
        )
        vcp20_strict_m, _, _ = vcp20_strict_bt.run(vcp_20_prep)

        # 4. VCP 30D (6W Base) + Repo 2-Tier Exit
        vcp30_bt = VCPBacktester(
            base_len=30,
            min_rs_rank=70.0,
            max_base_depth_pct=35.0,
            atr_contraction_ratio=0.9,
            vol_dryup_ratio=0.9,
            require_stage_2=True,
            min_rvol=1.0,
            exit_mode="repo_2tier",
            start_date=s_date,
            end_date=e_date,
        )
        vcp30_m, _, _ = vcp30_bt.run(vcp_30_prep)

        # 5. VCP 20D Pure 20 EMA Trail (Classic Swing Exit)
        vcp20_ema_bt = VCPBacktester(
            base_len=20,
            min_rs_rank=70.0,
            max_base_depth_pct=35.0,
            atr_contraction_ratio=0.9,
            vol_dryup_ratio=0.9,
            require_stage_2=True,
            min_rvol=1.0,
            exit_mode="ema20_trail",
            start_date=s_date,
            end_date=e_date,
        )
        vcp20_ema_m, _, _ = vcp20_ema_bt.run(vcp_20_prep)

        summary_rows.append({
            "Horizon": name,
            "Base Ret": f"+{base_m['total_return_pct']:.2f}%",
            "Base DD": f"{base_m['max_drawdown_pct']:.2f}%",
            "Base PF": f"{base_m['profit_factor']:.2f}",
            "VCP-20D Ret": f"{vcp20_m['total_ret_pct']:+.2f}%",
            "VCP-20D DD": f"{vcp20_m['max_dd_pct']:.2f}%",
            "VCP-20D PF": f"{vcp20_m['profit_factor']:.2f}",
            "VCP-20D WR": f"{vcp20_m['win_rate']:.1f}% ({vcp20_m['total_trades']}T)",
            "VCP-Strict Ret": f"{vcp20_strict_m['total_ret_pct']:+.2f}%",
            "VCP-Strict PF": f"{vcp20_strict_m['profit_factor']:.2f}",
            "VCP-Strict WR": f"{vcp20_strict_m['win_rate']:.1f}% ({vcp20_strict_m['total_trades']}T)",
            "VCP-30D Ret": f"{vcp30_m['total_ret_pct']:+.2f}%",
            "VCP-30D PF": f"{vcp30_m['profit_factor']:.2f}",
            "VCP-20EMA Ret": f"{vcp20_ema_m['total_ret_pct']:+.2f}%",
            "VCP-20EMA DD": f"{vcp20_ema_m['max_dd_pct']:.2f}%",
        })

    df_res = pd.DataFrame(summary_rows)
    print("\n" + tabulate(df_res, headers="keys", tablefmt="fancy_grid", showindex=False))

    out_csv = "data/cache/vcp_benchmark_results.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved VCP benchmark results to {out_csv}")
    return df_res


if __name__ == "__main__":
    run_benchmark()
