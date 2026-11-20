"""
scripts/test_swing_strategy.py
==============================
Institutional Dual-Timeframe (Weekly + Daily) Swing Trading Strategy Engine & Benchmark.
Compares the Apex Swing Strategy against the Baseline Donchian Trend Following model
across 4 standard horizons: 2026 YTD, Last 12 Months, Last 2 Years, and Last 5 Years.
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.indicators import compute_indicators

HORIZONS = [
    ("2026 YTD", "2026-01-01", "2026-11-09"),
    ("Last 12 Months", "2025-11-10", "2026-11-09"),
    ("Last 2 Years", "2024-11-11", "2026-11-09"),
    ("Last 5 Years", "2021-11-10", "2026-11-09"),
]


@dataclass
class SwingTrade:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    invested: float
    exit_val: float
    pnl: float
    pnl_pct: float
    holding_days: int
    exit_reason: str
    trade_type: str = "FULL"  # "PARTIAL_T1", "RUNNER", or "FULL"


def enrich_dual_timeframe_data(
    stock_dfs: Dict[str, pd.DataFrame],
    index_csv: str = "data/cache/NIFTY500_INDEX.csv"
) -> Dict[str, pd.DataFrame]:
    """
    Enrich daily stock data with Weekly indicators (10 WEMA, 30 WEMA, Weekly RSI, Weekly RS)
    and Daily swing indicators (TTM Squeeze, 10 EMA, 20 EMA, 50 EMA, 200 SMA, ATR14).
    All weekly indicators are strictly shifted by 1 week to avoid lookahead bias.
    """
    print("Precomputing Dual-Timeframe (Weekly + Daily) indicators across all stocks...")
    
    # 1. Load and prepare Nifty 500 Index weekly data for RS calculation
    df_idx = pd.read_csv(index_csv)
    df_idx["dt"] = pd.to_datetime(df_idx["date"]).dt.tz_localize(None)
    df_idx = df_idx.sort_values("dt").reset_index(drop=True)
    
    # Weekly index
    idx_w = df_idx.set_index("dt").resample("W-FRI").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna().reset_index()
    idx_w["idx_w_close"] = idx_w["close"]
    
    enriched = {}
    
    for sym, df in stock_dfs.items():
        d = df.copy()
        if len(d) < 50:
            continue
            
        d["dt"] = pd.to_datetime(d["date"]).dt.tz_localize(None)
        d = d.sort_values("dt").reset_index(drop=True)
        
        # ----------------------------------------------------
        # A. WEEKLY TIMEFRAME INDICATORS
        # ----------------------------------------------------
        w = d.set_index("dt").resample("W-FRI").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna().reset_index()
        
        w["w_ema_10"] = w["close"].ewm(span=10, adjust=False).mean()
        w["w_ema_30"] = w["close"].ewm(span=30, adjust=False).mean()
        
        # Weekly RSI(14)
        delta_w = w["close"].diff()
        gain_w = delta_w.clip(lower=0)
        loss_w = -delta_w.clip(upper=0)
        avg_gain_w = gain_w.ewm(alpha=1.0/14, min_periods=14, adjust=False).mean()
        avg_loss_w = loss_w.ewm(alpha=1.0/14, min_periods=14, adjust=False).mean()
        rs_w = avg_gain_w / avg_loss_w.replace(0, np.nan)
        w["w_rsi_14"] = 100.0 - (100.0 / (1.0 + rs_w))
        
        # Weekly Relative Strength vs Nifty 500
        w = pd.merge_asof(w, idx_w[["dt", "idx_w_close"]], on="dt", direction="backward")
        w["rs_ratio"] = w["close"] / w["idx_w_close"].replace(0, np.nan)
        w["rs_sma_10"] = w["rs_ratio"].rolling(10, min_periods=5).mean()
        w["w_rs_outperforming"] = w["rs_ratio"] > w["rs_sma_10"]
        
        # Weekly Stage 2 Alignment
        w["w_is_stage_2"] = (w["close"] > w["w_ema_10"]) & (w["w_ema_10"] > w["w_ema_30"]) & (w["w_rsi_14"] >= 50.0)
        
        # Shift weekly indicators by 1 completed week to guarantee zero lookahead bias
        w_cols_to_shift = ["w_ema_10", "w_ema_30", "w_rsi_14", "w_is_stage_2", "w_rs_outperforming"]
        for c in w_cols_to_shift:
            w[f"{c}_prev"] = w[c].shift(1)
            
        # Merge back to daily
        d = pd.merge_asof(
            d,
            w[["dt"] + [f"{c}_prev" for c in w_cols_to_shift]],
            on="dt",
            direction="backward"
        )
        
        # ----------------------------------------------------
        # B. DAILY SWING INDICATORS
        # ----------------------------------------------------
        # Fast Moving Averages
        d["ema_10"] = d["close"].ewm(span=10, adjust=False).mean()
        d["ema_20"] = d["close"].ewm(span=20, adjust=False).mean()
        d["ema_50"] = d["close"].ewm(span=50, adjust=False).mean()
        d["sma_200"] = d["close"].rolling(200, min_periods=100).mean()
        d["daily_stage_2"] = (d["close"] > d["ema_50"]) & (d["ema_50"] > d["sma_200"])
        
        # ATR 14
        hl = d["high"] - d["low"]
        hcp = (d["high"] - d["close"].shift(1)).abs()
        lcp = (d["low"] - d["close"].shift(1)).abs()
        tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        d["tr"] = tr
        d["atr_14"] = tr.ewm(alpha=1.0/14, min_periods=14, adjust=False).mean()
        
        # Daily RSI 14
        delta_d = d["close"].diff()
        gain_d = delta_d.clip(lower=0)
        loss_d = -delta_d.clip(upper=0)
        avg_gain_d = gain_d.ewm(alpha=1.0/14, min_periods=14, adjust=False).mean()
        avg_loss_d = loss_d.ewm(alpha=1.0/14, min_periods=14, adjust=False).mean()
        rs_d = avg_gain_d / avg_loss_d.replace(0, np.nan)
        d["daily_rsi"] = 100.0 - (100.0 / (1.0 + rs_d))
        
        # 20-Day Bollinger Bands (2.0 std)
        d["bb_mid"] = d["close"].rolling(20, min_periods=20).mean()
        d["bb_std"] = d["close"].rolling(20, min_periods=20).std()
        d["bb_upper"] = d["bb_mid"] + 2.0 * d["bb_std"]
        d["bb_lower"] = d["bb_mid"] - 2.0 * d["bb_std"]
        
        # 20-Day Keltner Channels (1.5 * ATR14)
        d["kc_upper"] = d["ema_20"] + 1.5 * d["atr_14"]
        d["kc_lower"] = d["ema_20"] - 1.5 * d["atr_14"]
        
        # TTM Volatility Squeeze condition (Bollinger Bands inside Keltner Channels)
        d["is_squeeze"] = (d["bb_upper"] < d["kc_upper"]) & (d["bb_lower"] > d["kc_lower"])
        # Squeeze active recently (within last 5 days)
        d["squeeze_recent"] = d["is_squeeze"].rolling(5, min_periods=1).max().astype(bool)
        
        # Donchian 20-day & 50-day Highs/Lows
        d["high_20"] = d["high"].rolling(20, min_periods=20).max()
        d["high_20_prev"] = d["high_20"].shift(1)
        d["low_10"] = d["low"].rolling(10, min_periods=10).min()
        d["low_10_prev"] = d["low_10"].shift(1)
        d["high_50"] = d["high"].rolling(50, min_periods=50).max()
        d["high_50_prev"] = d["high_50"].shift(1)
        
        # 52-Week High & distance
        d["high_52w"] = d["high"].rolling(252, min_periods=50).max()
        d["dist_52w_pct"] = ((d["close"] - d["high_52w"]) / d["high_52w"]) * 100.0
        
        # RVOL (20-day Volume SMA)
        d["vol_sma_20"] = d["volume"].rolling(20, min_periods=10).mean()
        d["rvol"] = np.where(d["vol_sma_20"] > 0, d["volume"] / d["vol_sma_20"], 1.0)
        
        # Pocket Pivot Volume check: volume > max down volume of last 10 days
        down_vol = np.where(d["close"] < d["open"], d["volume"], 0)
        d["max_down_vol_10"] = pd.Series(down_vol, index=d.index).rolling(10, min_periods=1).max()
        d["is_pocket_pivot"] = (d["volume"] > d["max_down_vol_10"].shift(1)) & (d["rvol"] >= 1.25)
        
        # 20 EMA Pullback touch in last 3 days
        touched_20_ema = (d["low"] <= d["ema_20"] * 1.015) & (d["low"] >= d["ema_20"] * 0.96)
        d["touched_20_ema_recent"] = touched_20_ema.rolling(3, min_periods=1).max().astype(bool)
        
        enriched[sym] = d
        
    print(f"Enriched {len(enriched)} stocks successfully.")
    return enriched


class SwingStrategyBacktester:
    def __init__(
        self,
        strategy_mode: str = "apex_swing",  # "baseline", "pullback_swing", "squeeze_swing", "apex_swing"
        initial_capital: float = 100000.0,
        max_positions: int = 10,
        max_per_sector: int = 3,
        risk_per_trade_pct: float = 1.25,
        max_position_size_pct: float = 15.0,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        use_partial_tp: bool = True,       # Sell 50% at +2R and move SL to BE
        target_r_multiple: float = 2.0,     # +2R Take Profit
        trailing_ema_len: int = 10,        # Trail on 10 EMA
        max_holding_days: int = 12,        # Stagnation time stop (12 days)
        hard_stop_loss_pct: float = 5.5,   # Capped at -5.5%
        climax_rsi: float = 78.0,          # Blow-off top exit
    ):
        self.strategy_mode = strategy_mode
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_per_sector = max_per_sector
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.start_date = pd.to_datetime(start_date).tz_localize(None) if start_date else None
        self.end_date = pd.to_datetime(end_date).tz_localize(None) if end_date else None
        self.use_partial_tp = use_partial_tp
        self.target_r_multiple = target_r_multiple
        self.trailing_ema_len = trailing_ema_len
        self.max_holding_days = max_holding_days
        self.hard_stop_loss_pct = hard_stop_loss_pct
        self.climax_rsi = climax_rsi
        
        # Sector map
        self.symbol_industry_map: Dict[str, str] = {}
        if os.path.exists("data/nifty500.csv"):
            try:
                df_u = pd.read_csv("data/nifty500.csv")
                for _, r in df_u.iterrows():
                    self.symbol_industry_map[str(r["Symbol"]).strip()] = str(r["Industry"]).strip()
            except Exception:
                pass

    def run(self, stock_dfs: Dict[str, pd.DataFrame]) -> Dict:
        # Collect unique trading dates
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
        closed_trades: List[SwingTrade] = []
        equity_curve: List[Tuple[pd.Timestamp, float, float, int]] = []
        
        pending_exits = {}    # sym -> (reason, exit_fraction)
        pending_entries = []  # (sym, close, score, stop_price)
        
        for current_idx, current_dt in enumerate(sorted_dates):
            date_str = current_dt.strftime("%Y-%m-%d")
            
            # ---------------------------------------------------------
            # Step A: Execute PENDING EXITS at Open
            # ---------------------------------------------------------
            for sym, exit_info in list(pending_exits.items()):
                reason, fraction = exit_info
                if sym in positions and sym in stock_date_maps:
                    stk_map = stock_date_maps[sym]
                    if current_dt in stk_map.index:
                        row = stk_map.loc[current_dt]
                        open_px = float(row["open"])
                        pos = positions[sym]
                        
                        shares_to_sell = int(pos["qty"] * fraction) if fraction < 1.0 else pos["qty"]
                        if shares_to_sell <= 0:
                            shares_to_sell = pos["qty"]
                            
                        exit_val = shares_to_sell * open_px
                        cost_basis = shares_to_sell * pos["entry_price"]
                        pnl = exit_val - cost_basis
                        pnl_pct = (pnl / cost_basis) * 100.0 if cost_basis > 0 else 0.0
                        holding_days = (current_dt - pos["entry_dt"]).days
                        
                        cash += exit_val
                        trade_type = "PARTIAL_T1" if fraction < 1.0 else ("RUNNER" if pos.get("t1_taken", False) else "FULL")
                        
                        closed_trades.append(
                            SwingTrade(
                                symbol=sym,
                                entry_date=pos["entry_date"],
                                exit_date=date_str,
                                entry_price=pos["entry_price"],
                                exit_price=open_px,
                                quantity=shares_to_sell,
                                invested=cost_basis,
                                exit_val=exit_val,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                holding_days=holding_days,
                                exit_reason=reason,
                                trade_type=trade_type
                            )
                        )
                        
                        if fraction >= 1.0 or shares_to_sell >= pos["qty"]:
                            positions.pop(sym)
                        else:
                            # Keep remaining shares as runner
                            pos["qty"] -= shares_to_sell
                            pos["invested"] -= cost_basis
                            pos["t1_taken"] = True
                            # Move stop to breakeven
                            pos["stop_price"] = max(pos["stop_price"], pos["entry_price"])
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
                suggested_stop = entry_item[3]
                
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
                        
                    # Calculate dynamic risk-based quantity
                    hard_stop = open_px * (1.0 - self.hard_stop_loss_pct / 100.0)
                    actual_stop = max(suggested_stop, hard_stop)
                    risk_per_share = max(open_px - actual_stop, open_px * 0.02)
                    risk_budget = current_equity * (self.risk_per_trade_pct / 100.0)
                    qty = int(risk_budget // risk_per_share)
                    
                    # Allocation cap (e.g. max 15%)
                    max_alloc = current_equity * (self.max_position_size_pct / 100.0)
                    qty = min(qty, int(max_alloc // open_px))
                    qty = min(qty, int(cash // open_px))
                    
                    if qty <= 0:
                        continue
                        
                    invested = qty * open_px
                    if cash >= invested:
                        cash -= invested
                        target_1_px = open_px + self.target_r_multiple * risk_per_share
                        positions[sym] = {
                            "qty": qty,
                            "entry_price": open_px,
                            "entry_date": date_str,
                            "entry_dt": current_dt,
                            "entry_trading_idx": current_idx,
                            "invested": invested,
                            "stop_price": actual_stop,
                            "risk_per_share": risk_per_share,
                            "target_1_px": target_1_px,
                            "industry": sec,
                            "t1_taken": False,
                            "peak_high": open_px,
                        }
                        available_slots -= 1
            pending_entries.clear()
            
            # ---------------------------------------------------------
            # Step C: Evaluate TODAY'S SIGNALS on EOD Close
            # ---------------------------------------------------------
            is_market_bullish = index_regime_map.get(current_dt, True)
            todays_candidates = []
            
            for sym, df_map in stock_date_maps.items():
                if current_dt not in df_map.index:
                    continue
                row = df_map.loc[current_dt]
                close = float(row["close"])
                high = float(row["high"])
                low = float(row["low"])
                open_c = float(row["open"])
                rvol = float(row.get("rvol", 1.0))
                atr14 = float(row.get("atr_14", close * 0.02))
                ema_10 = float(row.get("ema_10", 0.0))
                ema_20 = float(row.get("ema_20", 0.0))
                daily_rsi = float(row.get("daily_rsi", 50.0))
                
                # Check Exits for active positions
                if sym in positions:
                    pos = positions[sym]
                    trading_days_held = current_idx - pos["entry_trading_idx"]
                    pos["peak_high"] = max(pos.get("peak_high", pos["entry_price"]), high)
                    unrealized_pnl_pct = ((close - pos["entry_price"]) / pos["entry_price"]) * 100.0
                    
                    # 1. Stop Loss breach (Close or Low < stop_price)
                    if close <= pos["stop_price"]:
                        pending_exits[sym] = (f"Stop Loss Hit (₹{pos['stop_price']:.1f})", 1.0)
                        
                    # 2. Hard Stop (-5.5%)
                    elif self.hard_stop_loss_pct > 0 and close <= pos["entry_price"] * (1.0 - self.hard_stop_loss_pct / 100.0):
                        pending_exits[sym] = (f"Hard Stop (-{self.hard_stop_loss_pct:.1f}%)", 1.0)
                        
                    # 3. Target 1 Partial Take Profit (+2R)
                    elif self.use_partial_tp and not pos["t1_taken"] and close >= pos["target_1_px"]:
                        pending_exits[sym] = (f"Target 1 (+2R @ ₹{pos['target_1_px']:.1f})", 0.5)
                        
                    # 4. Climax / Blow-Off Top Exhaustion (RSI >= 78 and > 8% above 20 EMA)
                    elif daily_rsi >= self.climax_rsi and ema_20 > 0 and close >= ema_20 * 1.08:
                        pending_exits[sym] = (f"Climax Exhaustion (RSI {daily_rsi:.1f})", 1.0)
                        
                    # 5. Trailing Exit for Runner (Close < 10 EMA if T1 was taken)
                    elif pos["t1_taken"] and ema_10 > 0 and close < ema_10:
                        pending_exits[sym] = (f"Runner Trailing Exit (Close < {self.trailing_ema_len} EMA)", 1.0)
                        
                    # 6. Dead Money / Stagnation Time Stop (12 days held and < +1R profit)
                    elif trading_days_held >= self.max_holding_days and close < pos["entry_price"] + pos["risk_per_share"]:
                        pending_exits[sym] = (f"Stagnation Time Stop ({trading_days_held}d held, P&L {unrealized_pnl_pct:.1f}%)", 1.0)
                        
                # Check Entries (Market must be bullish >= 50 EMA)
                elif is_market_bullish:
                    # Basic hygiene filters
                    is_liquid = close >= 100.0 and float(row.get("vol_sma_20", 0)) >= 50000
                    if not is_liquid:
                        continue
                        
                    w_stage_2 = bool(row.get("w_is_stage_2_prev", False))
                    d_stage_2 = bool(row.get("daily_stage_2", False))
                    dist_52w = float(row.get("dist_52w_pct", -999.0))
                    
                    is_candidate = False
                    score = 0.0
                    stop_px = close - 1.5 * atr14
                    
                    # -------------------------------------------------------------
                    # Strategy Mode 1: 20 EMA Pullback Bounce (Trampoline)
                    # -------------------------------------------------------------
                    if self.strategy_mode in ("pullback_swing", "apex_swing"):
                        touched_20 = bool(row.get("touched_20_ema_recent", False))
                        green_candle = close > open_c
                        close_upper_half = (close - low) >= 0.40 * max(high - low, 0.01)
                        bounce_trigger = close > ema_20 and green_candle and close_upper_half and rvol >= 1.20
                        
                        if w_stage_2 and d_stage_2 and touched_20 and bounce_trigger:
                            is_candidate = True
                            # Stop below recent 3-day low or 1.5 ATR
                            stop_px = max(low * 0.99, close - 1.5 * atr14)
                            score = rvol * (close / ema_20) * 10.0
                            
                    # -------------------------------------------------------------
                    # Strategy Mode 2: Volatility Squeeze & Pocket Pivot Breakout
                    # -------------------------------------------------------------
                    if self.strategy_mode in ("squeeze_swing", "apex_swing") and not is_candidate:
                        squeeze_recent = bool(row.get("squeeze_recent", False))
                        high_20_prev = float(row.get("high_20_prev", 0.0))
                        breakout_20 = close > high_20_prev and high_20_prev > 0
                        pocket_pivot = bool(row.get("is_pocket_pivot", False))
                        near_52w = dist_52w >= -15.0
                        
                        if squeeze_recent and breakout_20 and pocket_pivot and near_52w and d_stage_2:
                            is_candidate = True
                            breakout_pct = ((close - high_20_prev) / high_20_prev) * 100.0
                            stop_px = max(float(row.get("low_10_prev", close * 0.95)), close - 1.5 * atr14)
                            score = breakout_pct * rvol * 2.0
                            
                    if is_candidate:
                        todays_candidates.append((sym, close, score, stop_px))
                        
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
            
        # Summary metrics
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
            "avg_hold_days": avg_hold_days,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "closed_trades": closed_trades,
            "equity_df": df_eq
        }


def run_benchmark():
    # 1. Load baseline universe data
    from scripts.backtest import PortfolioBacktester
    bt_loader = PortfolioBacktester(entry_len=50, exit_len=20)
    base_dfs = bt_loader.load_universe_data()
    print(f"Loaded {len(base_dfs)} baseline stock DataFrames.")
    
    # Enrich with weekly and daily indicators
    enriched_dfs = enrich_dual_timeframe_data(base_dfs)
    
    results = []
    
    for h_name, start_d, end_d in HORIZONS:
        print(f"\n=======================================================")
        print(f"Running Multi-Horizon Benchmark: {h_name} ({start_d} to {end_d})")
        print(f"=======================================================")
        
        # 1. Baseline Donchian Trend Following
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
            "Horizon": h_name,
            "Ending Equity": f"₹{base_res['ending_equity']:,.2f}",
            "Return %": f"{base_res['total_return_pct']:+.2f}%",
            "CAGR %": f"{base_res['cagr_pct']:.2f}%",
            "Max DD %": f"{base_res['max_drawdown_pct']:.2f}%",
            "Win Rate %": f"{base_res['win_rate']:.1f}%",
            "Profit Factor": f"{base_res['profit_factor']:.2f}",
            "Trades": base_res['total_trades'],
            "Avg Hold Days": f"{base_res['avg_holding_days']:.1f}d",
            "Sharpe": f"{base_res['sharpe_ratio']:.2f}",
        })
        
        # 2. Apex Swing (Dual-Timeframe Pullback + Squeeze with Asymmetric Exits)
        bt_swing = SwingStrategyBacktester(
            strategy_mode="apex_swing",
            initial_capital=100000.0,
            start_date=start_d,
            end_date=end_d,
            use_partial_tp=True,
            target_r_multiple=2.0,
            trailing_ema_len=10,
            max_holding_days=12,
            hard_stop_loss_pct=5.5,
        )
        swing_res = bt_swing.run(enriched_dfs)
        results.append({
            "Strategy": "Apex Swing (Dual-Timeframe Squeeze & Pullback)",
            "Horizon": h_name,
            "Ending Equity": f"₹{swing_res['ending_equity']:,.2f}",
            "Return %": f"{swing_res['total_return_pct']:+.2f}%",
            "CAGR %": f"{swing_res['cagr_pct']:.2f}%",
            "Max DD %": f"{swing_res['max_drawdown_pct']:.2f}%",
            "Win Rate %": f"{swing_res['win_rate']:.1f}%",
            "Profit Factor": f"{swing_res['profit_factor']:.2f}",
            "Trades": swing_res['total_trades'],
            "Avg Hold Days": f"{swing_res['avg_hold_days']:.1f}d",
            "Sharpe": f"{swing_res['sharpe']:.2f}",
        })
        
    df_res = pd.DataFrame(results)
    print("\n\n" + "=" * 90)
    print("📊 COMPREHENSIVE BENCHMARK RESULTS: APEX SWING VS BASELINE DONCHIAN")
    print("=" * 90)
    print(tabulate(df_res, headers="keys", tablefmt="fancy_grid", showindex=False))
    
    out_csv = "data/cache/swing_strategy_benchmark_results.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved benchmark results to {out_csv}")


if __name__ == "__main__":
    run_benchmark()
