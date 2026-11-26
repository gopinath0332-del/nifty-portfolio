# Nifty 500 Momentum & Donchian Trend-Following Strategy

This document specifies the exact **Entry Conditions**, **Exit Conditions**, **Candidate Ranking**, and **Position Sizing & Portfolio Constraints** implemented in `src/strategy.py`, `src/indicators.py`, `src/portfolio.py`, and configured via `config/settings.yaml`.

---

## 1. Execution Flow Overview

Each daily post-market scan (`15:45 IST`) runs in four sequential phases:
1. **Phase 1 — Exit Evaluation:** Check all active positions against full and partial exit rules.
2. **Phase 2 — Market Regime Filter:** Check whether the broad market (`NIFTY 500`) is in a bullish regime.
3. **Phase 3 — Entry Scan:** Scan the Nifty 500 universe for qualifying breakout candidates.
4. **Phase 4 — Ranking & Allocation:** Rank candidates by composite momentum score, enforce sector and slot limits, and size positions sequentially against projected cash.

---

## 2. Entry Conditions

New breakout entries are only evaluated when the **Market Regime Filter** is bullish (or disabled).

### A. Market Regime Gate
* **Rule:** `NIFTY 500 Close >= 50 EMA` (`market_regime.enabled: true`, `index_token: 268041`, `ema_len: 50`).
* **Behavior if Bearish:** If `NIFTY 500 Close < 50 EMA`, all new breakout entries are paused (`stocks_to_scan = []`). Existing positions continue to be monitored for exits.

### B. Universe & Holding Exclusion
* **Universe:** NSE Nifty 500 constituents (`data/nifty500.csv`).
* **Duplicate Guard:** Stocks already held in the portfolio are skipped unless they are undergoing a **full exit** on the same scan day.
* **Minimum History:** Requires at least `max(entry_len, exit_len) + 1` daily candles (`51` trading days with `entry_len: 50`).

### C. Technical Entry Filters (All Must Pass)
1. **50-Day Donchian Breakout** (`entry_len: 50`)
   * `Close > previous 50-day rolling High` (`high_50_prev`).
   * `breakout_pct = ((Close - high_50_prev) / high_50_prev) * 100`.
2. **52-Week High Proximity** (`near_52w_high_enabled: true`, `within_52w_high_pct: 10.0`)
   * `Close` must be within `10.0%` of its 252-day high (`dist_52w_high_pct >= -10.0`).
3. **Stage 2 Trend Alignment** (`stage_2_trend_enabled: true`)
   * `Close > 50 EMA > 200 SMA` (Stan Weinstein / Mark Minervini Stage 2 uptrend).
4. **Minimum Stock Price** (`min_stock_price: 100.0`)
   * `Close >= ₹100.00`.
5. **Maximum Stock Price** (`max_stock_price: null`)
   * Optional upper cap (currently disabled; the `15%` allocation cap naturally filters out stocks whose single-share price exceeds the slot budget).
6. **Minimum Liquidity** (`min_20d_avg_volume: 50000`)
   * `20-day Average Volume (vol_sma_20) >= 50,000` shares.

---

## 3. Candidate Ranking, Sector Cap & Position Sizing

### A. Composite Ranking Score
Qualifying candidates are sorted descending by:
$$\text{Composite Score} = \text{Breakout \%} \times \max(\text{RVOL}, 0.1)$$
where $\text{RVOL} = \frac{\text{Volume}}{\text{20-Day Avg Volume}}$ (defaults to `1.0` if `vol_sma_20 <= 0`).

### B. Dynamic Risk-Based Position Sizing (`sizing_mode: "risk_pct"`)
* **Portfolio Equity:** Mark-to-market equity (`mtm_equity`), using live/latest closes for active holdings plus cash.
* **Projected Cash:** `cash_balance + proceeds from today's full and partial exits`, decremented sequentially as each recommended buy is allocated.
* **Stop Price:**
  $$\text{Stop} = \max\left(\text{20-Day Low}_{[t-1]},\; \text{Close} \times (1 - 0.08)\right)$$
* **Risk Per Share:** $\max(\text{Close} - \text{Stop},\; \text{Close} \times 0.02)$ (minimum `2%` risk floor).
* **Quantity:**
  $$\text{Qty} = \min\left(\left\lfloor \frac{\text{Equity} \times 1.25\%}{\text{Risk Per Share}} \right\rfloor,\; \left\lfloor \frac{\text{Equity} \times 15.0\%}{\text{Close}} \right\rfloor,\; \left\lfloor \frac{\text{Remaining Cash}}{\text{Close}} \right\rfloor\right)$$
  Candidates with `Qty <= 0` are skipped.

### C. Capacity & Diversification Caps
* **Max Concurrent Positions:** `10` (`max_positions: 10`). Effective open slots include slots freed by same-day full exits (partial exits recycle cash only, not slots).
* **Max Stocks per Sector:** `3` (`max_per_sector: 3`), tracked via `industry` metadata from `data/nifty500.csv`.

---

## 4. Exit Conditions

Active positions are evaluated daily in **strict priority order** (the first matching condition triggers):

### Full Exits (Sell 100% of Position & Free Slot)
1. **Hard Stop Loss** (`max_loss_stop_pct: 8.0`)
   * **Trigger:** `Close <= Entry Price * (1 - 0.08)` (`-8.0%` from entry price).
2. **Tenure Loss Cut** (`max_loss_holding_days: 20`)
   * **Trigger:** `Trading Days Held >= 20` **and** `Unrealized P&L % < 0%`.
   * **Purpose:** Prunes stagnant/losing trades after ~1 month to recycle capital.
3. **Profit-Lock Exit** (`profit_lock_threshold_pct: 25.0`, `profit_lock_ema_len: 20`)
   * **Trigger:** `Unrealized P&L % >= +25.0%` **and** `Close < 20 EMA`.
   * **Purpose:** Locks in gains on extended winners when short-term momentum breaks.
4. **Stage 2 Trend Breakdown** (`exit_on_stage2_break: true`)
   * **Trigger:** `Close < 50 EMA`.
   * **Purpose:** Exits when the intermediate Stage 2 uptrend is violated.
5. **Channel Exit Fallback** (`exit_len: 20`)
   * **Trigger:** `Close < previous 20-day rolling Low` (`low_20_prev`).

### Partial Exit (Trim 50% & Keep Slot Open)
6. **Partial Profit-Taking** (`partial_tp_enabled: true`, `partial_tp_threshold_pct: 30.0`, `partial_tp_fraction: 0.5`)
   * **Trigger:** None of the full exits above triggered, `partial_taken == False`, `Quantity >= 2`, and `Unrealized P&L % >= +30.0%`.
   * **Action:** Sells `floor(Quantity * 0.5)` shares (`0 < trim_qty < Quantity`), recycles cash for new entries, and keeps the remaining shares open in the same slot.

---

## 5. Active Configuration Reference (`config/settings.yaml`)

| Parameter | Value | Description |
| :--- | :--- | :--- |
| `capital.total_capital` | `200000.0` | Dedicated strategy budget (₹2,00,000 INR) |
| `capital.sizing_mode` | `"risk_pct"` | Dynamic risk-based sizing |
| `capital.risk_per_trade_pct` | `1.25` | Risk 1.25% of portfolio equity per trade |
| `capital.max_position_size_pct` | `15.0` | Max 15% of equity per stock |
| `capital.max_positions` | `10` | Max 10 concurrent holdings |
| `capital.max_per_sector` | `3` | Max 3 holdings per industry/sector |
| `strategy.entry_len` | `50` | 50-day Donchian High breakout |
| `strategy.exit_len` | `20` | 20-day Donchian Low fallback exit |
| `strategy.max_loss_stop_pct` | `8.0` | -8.0% hard stop loss |
| `strategy.exit_on_stage2_break` | `true` | Exit on `Close < 50 EMA` |
| `strategy.profit_lock_threshold_pct` | `25.0` | Profit-lock threshold (+25%) |
| `strategy.profit_lock_ema_len` | `20` | Profit-lock trailing EMA (20 EMA) |
| `strategy.partial_tp_enabled` | `true` | Enable one-time partial profit-taking |
| `strategy.partial_tp_threshold_pct` | `30.0` | Partial profit-take threshold (+30%) |
| `strategy.partial_tp_fraction` | `0.5` | Sell 50% of shares on partial trigger |
| `strategy.max_loss_holding_days` | `20` | Cut losing positions held >= 20 trading days |
| `filters.within_52w_high_pct` | `10.0` | Must be within 10% of 52-week high |
| `filters.stage_2_trend_enabled` | `true` | Require `Close > 50 EMA > 200 SMA` |
| `filters.min_stock_price` | `100.0` | Minimum stock price ₹100 |
| `filters.min_20d_avg_volume` | `50000` | Minimum 20-day avg volume 50,000 |
| `market_regime.enabled` | `true` | Require `NIFTY 500 >= 50 EMA` for new buys |
