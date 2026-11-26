# 🤖 AI Agent Guidelines & Repository Architecture
## Nifty 500 Automated Momentum & Donchian Trend-Following Engine

Welcome to the **Nifty 500 Portfolio Engine**. This repository is an institutional-grade, automated trading and backtesting system built for Indian Equities (NSE Nifty 500 universe) via Kite Connect (Zerodha).

---

### 🚨 CARDINAL RULES FOR AI AGENTS (MANDATORY)

1. **NEVER RUN `git commit` UNDER ANY CIRCUMSTANCES:**
   - The user explicitly requires: *"never ever commit the changes. i will commit the changes manually"*.
   - All code, configuration, documentation, and test changes must remain in the working directory (unstaged or staged) for manual review.
2. **SELF-UPDATING RULE (ALWAYS KEEP `AGENTS.md` UPDATED):**
   - Whenever any strategy logic, configuration schema, indicator calculation, risk sizing rule, script, or workflow is added, modified, or optimized, **YOU MUST UPDATE THIS `AGENTS.md` FILE IN THE SAME TURN**.
   - Ensure subsequent agent sessions immediately inherit the latest system context and findings.
3. **RUN TESTS BEFORE COMPLETING ANY TASK:**
   - Always run `python -m pytest tests/` and verify that all unit tests pass (100% green).
   - All entrypoint scripts in `scripts/` are strictly compiled and validated via automated pytest (`test_all_scripts_syntax`) to prevent deployment indentation or syntax regressions.
   - If changes affect indicators, portfolio management, or configuration, add or update corresponding unit tests in `tests/test_strategy.py`.
4. **PORTFOLIO CAPITAL BASELINE:**
   - The active baseline capital is **₹2,00,000 INR** (`total_capital: 200000.0` in `config/settings.yaml`).

---

### 📈 CORE STRATEGY SPECIFICATION (OPTIMAL PARAMETERS)

The system runs an optimized **Turtle System 2** trend-following model with strict risk management:

| Component | Rule / Parameter | Reason & Impact |
| :--- | :--- | :--- |
| **Breakout Entry** | **50-Day Donchian High** (`entry_len: 50`) | Captures primary stage-2 trend breakouts before stock is overextended. |
| **52-Week High Proximity** | **Within 10% of 52W High** (`within_52w_high_pct: 10.0`) | Ensures the stock is in a secular multi-quarter bull run (no deep pullbacks). |
| **Stage 2 Trend Filter** | **$Price > 50\text{ EMA} > 200\text{ SMA}$** (`stage_2_trend_enabled: true`) | Eliminates counter-trend dead-cat bounces in declining secular bear stocks. |
| **Minimum Stock Price** | **$Price \ge ₹100$** (`min_stock_price: 100.0`) | Eliminates low-liquidity micro-caps and erratic sub-₹100 penny stocks. |
| **Maximum Stock Price** | **Disabled** (`max_stock_price: null`) | Optional upper price filter kept disabled; `15%` max allocation cap naturally skips stocks exceeding slot budget while retaining leaders like `TRENT` / `EICHERMOT` / `DIVISLAB`. |
| **Volume Liquidity** | **20-Day Avg Volume $\ge 50,000$** shares | Ensures institutional liquidity for zero-slippage market execution. |
| **Ranking Score** | **$\text{Breakout } \% \times \text{RVOL}$** | Breaks ties by prioritizing the strongest price momentum backed by volume. |
| **Market Regime Filter** | **Nifty 500 Index $\ge 50\text{ EMA}$** | Prevents opening new long positions when the broad market is in a downtrend. |
| **Profit-Lock Exit (Tier 1)**| **Unrealized Gain $\ge +25\%$ & Close $< 20\text{ EMA}$** (`profit_lock_threshold_pct: 25.0`) | Locks in profits on mature winners at trend exhaustion rather than round-tripping gains. |
| **Partial Profit-Taking**  | **Book 50% at Unrealized Gain $\ge +30\%$** (`partial_tp_enabled: true`, `partial_tp_threshold_pct: 30.0`, `partial_tp_fraction: 0.5`) | De-risks mature winners and recycles cash into fresh breakouts without closing the slot; improves Sharpe and compresses drawdowns across all horizons. |
| **Stage 2 Exit (Tier 2)**   | **Close $< 50\text{ EMA}$** (`exit_on_stage2_break: true`) | Systematic structural exit when intermediate Stage 2 uptrend is broken. |
| **Tenure Loss Cut**        | **Held $\ge 20$ Trading Days & $P\&L < 0$** (`max_loss_holding_days: 20`) | Prunes stagnant positions that fail to ignite after 1 month, recycling capital into fresh leaders. |
| **Channel Exit Fallback**  | **20-Day Donchian Low** (`exit_len: 20`) | Fallback trailing exit for channel preservation. |
| **Hard Loss Stop** | **-8.0% Stop Loss** (`max_loss_stop_pct: 8.0`) | Caps maximum loss per trade if a false breakout reverses immediately. |
| **Position Sizing** | **Dynamic Risk-Based (1.25% Risk / Trade)** | Position size adapts dynamically: $\text{Qty} = \frac{\text{Equity} \times 1.25\%}{\text{Open} - \text{Stop}}$. |
| **Position Allocation Cap**| **Max 15% Capital per Stock** (`max_position_size_pct: 15.0`) | Prevents over-concentration in any single stock. |
| **Portfolio Capacity** | **Max 10 Concurrent Positions** (`max_positions: 10`) | Maintains optimal portfolio diversification and cash utilization. |
| **Sector Diversification** | **Max 3 Stocks per Sector** (`max_per_sector: 3`) | Optimal thematic capture: allows riding up to 3 leaders in monster secular themes without correlated contagion. |

---

### 📂 REPOSITORY ARCHITECTURE

```
nifty-portfolio/
├── AGENTS.md                  # This file - Core rules, architecture, and agent instructions
├── GEMINI.md                  # Pointer to AGENTS.md for Gemini/Antigravity discovery
├── STRATEGY.md                # Dedicated Entry/Exit conditions, ranking, and sizing specification
├── main.py                    # Production daily scanner and execution runner
├── config/
│   └── settings.yaml          # Active strategy & portfolio parameters
├── src/
│   ├── config.py              # Strongly-typed Dataclass configuration loader
│   ├── logger.py              # Multi-target rotating file logger & global unhandled crash handler
│   ├── indicators.py          # Vectorized calculations (50D, 20D, 52W, 50 EMA, 200 SMA, RVOL, ATR)
│   ├── strategy.py            # Daily scanner engine, signal generation & candidate ranking
│   ├── portfolio.py           # Portfolio state manager, risk-based sizing, sector tracking
│   ├── market_data.py         # Kite Connect historical candle fetcher & caching layer
│   ├── universe.py            # Nifty 500 universe loader and token mapping
│   ├── discord_notifier.py    # Discord webhook execution alerts & daily reports
│   └── orders.py              # Kite order placement with safety dry-run checks
├── logs.sh                    # Interactive CLI utility for log inspection and live debugging on Pi
├── restart.sh                 # Safe service restart script with --now trigger
├── status.sh                  # Live exchange, systemd, and log error status inspector
├── stop.sh                    # Service shutdown utility
├── scripts/
│   ├── backtest.py            # Chronological portfolio simulation engine & terminal reporter
│   ├── generate_html_report.py# Interactive Chart.js backtest report generator
│   ├── test_nifty50_vs_nifty500.py # Comprehensive Nifty 50 vs Nifty 500 multi-horizon benchmark
│   ├── test_oliver_kell.py    # Oliver Kell Swing Trading strategy multi-horizon benchmark
│   ├── test_darvas_box.py     # Darvas Box & Screener.in multi-horizon benchmark
│   ├── test_capital_infusion.py # Real-life capital addition & SIP compounding multi-horizon benchmark
│   ├── test_fixed_vs_dynamic.py # Fixed Sizing vs Dynamic Profit Compounding benchmark
│   ├── test_rsi_ema_gap_up.py # RSI(14) on EMA < 10 Gap-Up strategy benchmark
│   ├── test_vcp.py            # Volatility Contraction Pattern (VCP) multi-horizon benchmark
│   ├── test_ema200_rsi30.py   # 200 EMA + RSI(30) crossover multi-horizon benchmark
│   └── test_notification.py   # Discord webhook layout test & live alert dispatcher
├── tests/
│   ├── test_strategy.py       # Pytest unit tests for strategy modules
│   └── test_notifier.py       # Pytest unit tests for Discord message formatting
└── data/
    ├── nifty500.csv           # Master Nifty 500 constituent list with sector metadata
    ├── nifty50.csv            # Official Nifty 50 constituent list with sector metadata
    ├── portfolio_state.json   # Live portfolio state (open positions, cash, slots)
    └── cache/                 # Cached daily candle CSVs for all 500 stocks + index
```

---

### 🛠️ WORKFLOWS & COMMON COMMANDS

1. **Run Standard Backtest (2026 YTD):**
   ```powershell
   python scripts/backtest.py --start 2026-01-01
   ```
2. **Run 12-Month Backtest (Nov 2025 to Nov 2026):**
   ```powershell
   python scripts/backtest.py --start 2025-11-01 --end 2026-11-10
   ```
3. **Generate Interactive HTML Backtest Report:**
   ```powershell
   python scripts/generate_html_report.py --start 2026-01-01 --out backtest_report_2026.html
   ```
4. **Run Unit Tests:**
   ```powershell
   python -m pytest tests/
   ```
5. **Run Daily Post-Market Scan & Update:**
   ```powershell
   python scripts/run_daily_scan.py
   ```
6. **Check Live Exchange & Portfolio Status:**
   ```bash
   ./status.sh  # or: python scripts/manage_portfolio.py list
   ```
7. **Add Capital / Monthly SIP to Strategy Budget:**
   ```bash
   python scripts/manage_portfolio.py add-funds 10000
   ```
8. **Inspect & Follow Logs on Raspberry Pi:**
   ```bash
   ./logs.sh          # View recent scan logs and warning/error alerts
   ./logs.sh -f       # Follow live scan output in real time (tail -f)
   ./logs.sh -e       # View dedicated error log and full stack traces
   ./logs.sh -j       # Inspect systemd journal logs (journalctl)
   ./logs.sh --clear  # Safely truncate logs to free up disk space
   ```
8. **Test Discord Alert Formatting & Webhook:**
   ```powershell
   python scripts/test_notification.py
   ```
9. **Run Nifty 50 vs. Nifty 500 Benchmark Comparison:**
   ```powershell
   python scripts/test_nifty50_vs_nifty500.py
   # Or run standalone Nifty 50 backtest:
   python scripts/backtest.py --universe nifty50 --start 2026-01-01
   ```
10. **Run Oliver Kell Swing Strategy Multi-Horizon Benchmark:**
   ```powershell
   python scripts/test_oliver_kell.py
   ```
11. **Run Darvas Box & Screener.in Multi-Horizon Benchmark:**
   ```powershell
   python scripts/test_darvas_box.py
   ```
12. **Run Capital Infusion & SIP Multi-Horizon Benchmark:**
   ```powershell
   python scripts/test_capital_infusion.py
   ```
13. **Run Fixed Sizing vs. Dynamic Profit Compounding Benchmark:**
   ```powershell
   python scripts/test_fixed_vs_dynamic.py
   ```
14. **Run RSI(14) on EMA < 10 Gap-Up Benchmark:**
   ```powershell
   python scripts/test_rsi_ema_gap_up.py
   ```
15. **Run Volatility Contraction Pattern (VCP) Multi-Horizon Benchmark:**
   ```powershell
   python scripts/test_vcp.py
   ```
16. **Run 200 EMA + RSI(30) Crossover Multi-Horizon Benchmark:**
   ```powershell
   python scripts/test_ema200_rsi30.py
   ```

---

### 🪵 PRODUCTION LOGGING & ERROR DEBUGGING ON RASPBERRY PI

The engine incorporates a resilient multi-target logging architecture (`src/logger.py`) specifically engineered for headless 24/7 Raspberry Pi production environments:

1. **Dual Rotating File Handlers & Systemd Isolation (MicroSD Wear & Permission Safety)**:
   - `logs/daily_scan.log`: Complete audit trail of daily scanner runs, Kite exchange synchronization, candidate scores, and portfolio rebalances. Rotates at **10 MB** with **5 backup generations** (`daily_scan.log.1` ... `.5`), guaranteeing that log files never exceed 50 MB or exhaust the Pi's MicroSD card storage.
   - `logs/errors.log`: Dedicated error sink capturing only `WARNING`, `ERROR`, and `CRITICAL` entries with exact timestamps, module names, function names, line numbers, and full Python tracebacks. Rotates at **5 MB** with **5 backups**.
   - `deploy/nifty-portfolio.service` uses `StandardOutput=journal` and `StandardError=journal` so `systemd` never creates root-owned log files in `logs/` or double-writes alongside Python's `RotatingFileHandler`.
   - `setup_logger()` gracefully falls back to console/journal logging if a log file raises `OSError` / `PermissionError` so the daily scan is never aborted at startup.
2. **Global Unhandled Exception Hook (`sys.excepthook`)**:
   - Any uncaught crash, network failure, or API timeout is intercepted before the Python interpreter exits.
   - The full stack trace is automatically flushed to `logs/errors.log` and dispatched immediately to Discord as an emergency alert (`🚨 CRITICAL ERROR`), enabling instant notification on mobile without having to SSH into the Pi.
3. **Interactive Debug CLI (`./logs.sh`)**:
   - View recent logs: `./logs.sh` (shows last 35 lines + highlights if any errors exist).
   - Real-time tail: `./logs.sh -f` (live follow).
   - Dedicated error inspection: `./logs.sh -e` (shows `logs/errors.log`).
   - Live error tail: `./logs.sh -ef`.
   - Systemd integration: `./logs.sh -j` (queries `journalctl -u nifty-portfolio.service -n 50 --no-pager`).
   - Space management: `./logs.sh --clear` (safely truncates log files without breaking open file descriptors).
4. **Enhanced `status.sh` Diagnostic**:
   - Running `./status.sh` automatically scans `logs/errors.log` and flags any recent issues.

---

### 📱 INSTITUTIONAL RETRO RECEIPT DISCORD NOTIFICATION ARCHITECTURE

The daily alerts (`src/discord_notifier.py`) use a retro Bloomberg Terminal receipt design engineered specifically for mobile Discord viewports:
1. **⚡ Narrow 27-Character Monospace Receipt Boxes (Zero Wrapping Guarantee)**:
   - All ASCII receipt tables are strictly bounded to **27 characters wide** (`┌─────────────────────────┐`).
   - Fits comfortably inside iOS and Android mobile Discord viewports without wrapping mid-line or fragmenting columns.
   - Summarizes ticker, suggested quantity, CMP (or P&L%), and total capital required in a compact order ticket.
2. **Compact 1-Liner Technical Setup Notes**:
   - Technical indicators (Breakout %, Pivot, RVOL, Composite Momentum Score) render as concise bullet notes directly beneath the receipt box.
   - Runners-up are placed in a subtle subtext watchlist (`-# Watchlist: ...`).
3. **📊 Minimalist Portfolio Summary Card**:
   - Replaced multi-box embed fields with a unified single-card view: narrow 27-character holdings receipt sorted by **P&L% descending** accompanied by key equity, cash, and P&L metrics.

---

### 🏛️ LIVE EXCHANGE INTEGRATION & SAFETY PRINCIPLE

1. **`LIVE_ORDER_PLACEMENT=false` (Safety Mode):**
   - **Only order placement to the exchange is disabled.** The engine will never route automated buy/sell orders without explicit permission.
   - **All other data is ALWAYS collected live from the exchange (Zerodha Kite):**
     - Live available cash & equity margins via `kite.margins("equity")` (captured for diagnostic reporting).
     - Live Demat holdings via `kite.holdings()`.
     - Live open delivery positions via `kite.positions()`.
     - Live CMP quotes via `kite.quote()`.
2. **Fixed Portfolio Budget Isolation & Sizing (₹2,00,000 Baseline):**
   - **Strategy Cash Isolation:** Sizing and available cash are strictly governed by the dedicated strategy budget (`total_capital: 200000.0` in `config/settings.yaml`), completely isolated from Zerodha's overall account cash.
   - **No Account Balance Contamination:** External funds in the user's Zerodha account (e.g. ₹5,00,000 or ₹10,00,000) are NEVER used to size positions. `kite.margins("equity")` is logged purely for diagnostics.
   - **Automatic Scaling:** If the user wishes to increase the portfolio value in the future, simply update `total_capital` in `config/settings.yaml` (e.g. `250000.0`). Available cash and suggested lot counts scale proportionately without code changes.
   - **Cash Reconciliation:** Strategy cash is dynamically maintained as: $\text{Cash} = \max(0, \text{Total Capital} + \text{Realized P&L} - \text{Total Invested})$.
3. **Exchange Synchronization & Live-Scan Parity:**
   - Both `status.sh` and `run_daily_scan.py` automatically call `PortfolioManager.sync_with_exchange(kite)` to reconcile strategy state with real account Demat holdings, eliminating stale or dummy local JSON values.
   - `sync_with_exchange` reconciles exits even when all Demat holdings are closed (`exchange_stocks == {}`), populates missing `industry` metadata from `data/nifty500.csv` for sector-cap enforcement, records partial quantity trims cleanly, and captures live LTP on external exits.
   - `MarketDataFetcher.fetch_daily_candles` validates cache freshness against the latest trading day and incrementally fetches missing bars from Kite rather than serving stale `>= 250`-row CSVs.
   - `StrategyEngine.run_daily_scan` computes mark-to-market equity and sequentially deducts recommended buy allocations from projected cash (including proceeds from today's full/partial exits) so total recommended capital never exceeds available strategy cash.
4. **Shell Script Compatibility:**
   - `status.sh` and `restart.sh` are strictly POSIX-compliant (`sh` and `bash` compatible) using `"$0"` directory resolution to prevent `Bad substitution` errors on Debian/Raspberry Pi OS (`dash`).

---

### 📊 LATEST BENCHMARK METRICS (4-HORIZON COMPARATIVE MATRIX)

| Performance & Margin Metric | 2026 YTD (Current Year) | Last 12 Months (Nov 25 – Nov 26) | Last 2 Years (Nov 24 – Nov 26) | Last 5 Years (Nov 21 – Nov 26) |
| :--- | :--- | :--- | :--- | :--- |
| **Date Window** | 2026-01-01 to 2026-11-09 | 2025-11-10 to 2026-11-09 | 2024-11-11 to 2026-11-09 | 2021-11-10 to 2026-11-09 |
| **Starting Capital** | ₹1,00,000.00 | ₹1,00,000.00 | ₹1,00,000.00 | ₹1,00,000.00 |
| **Ending Equity** | **₹1,39,914.82** | **₹1,49,842.37** | **₹1,79,420.33** | **₹5,25,896.64** |
| **Net Profit** | +₹39,914.82 | +₹49,842.37 | +₹79,420.33 | +₹4,25,896.64 |
| **Total Net Return** | **+39.91%** | **+49.84%** | **+79.42%** | **+425.90%** |
| **Annualized Return (CAGR)**| **+49.07%** | **+50.57%** | **+34.66%** | **+40.08%** |
| **Max Drawdown (%)** | **-11.72%** (₹13.5k) | **-11.31%** (₹13.7k) | **-12.81%** (₹18.2k) | **-29.53%** (₹51.5k) |
| **Profit Factor** | **2.87** | **3.24** | **2.99** | **2.82** |
| **Sharpe Ratio ($R_f=6.5\%$)** | **1.79** | **1.79** | **1.29** | **1.37** |
| **Sortino Ratio** | **2.88** | **2.59** | **1.74** | **1.75** |
| **Calmar Ratio** | **4.19** | **4.47** | **2.71** | **1.36** |
| **Trades (Wins / Losses)** | 46 (17W / 29L) | 57 (24W / 33L) | 102 (48W / 54L) | 288 (126W / 162L) |
| **Win Rate** | 36.96% | 42.11% | 47.06% | 43.75% |
| **Avg Winner / Avg Loser** | +25.24% / -7.53% | +22.53% / -6.29% | +17.62% / -5.67% | +21.07% / -6.38% |
| **Win/Loss Payout Ratio** | **3.35x** | **3.58x** | **3.11x** | **3.30x** |
| **Avg Holding Period** | 44.2 days | 45.7 days | 48.9 days | 47.0 days |
| **Avg Active Invested Margin** | ₹83,307 (72.1%) | ₹90,112 (76.1%) | ₹91,118 (73.2%) | ₹1,91,089 (79.9%) |
| **Peak Margin Deployed** | ₹1,39,722 (99.99%) | ₹1,50,069 (99.99%) | ₹1,79,598 (99.99%) | ₹5,25,880 (99.99%) |
| **Avg Remaining Cash Cushion** | ₹33,076 | ₹29,938 | ₹32,736 | ₹48,417 |
| **Min Remaining Margin (Buffer)** | ₹8.17 | ₹2.58 | ₹7.75 | ₹1.73 |
| **Avg Invested Margin / Trade** | ₹10,057 | ₹10,226 | ₹11,499 | ₹22,744 |
| **Avg Rem Margin at Entry** | ₹16,190 | ₹15,861 | ₹13,806 | ₹20,419 |

---

#### MAE / MFE (Maximum Adverse & Favorable Excursion) Insights
- **Average Peak Profit (MFE) on Winners:** **+38.43%** (Realized: **+21.05%**)
- **Exit Capture Efficiency:** **44.6%** (Two-tier exit dynamically locks in peak profits when momentum breaks 20 EMA, while allowing Stage 2 trends to compound).
- **Average Adverse Drawdown (MAE) on Winners:** **-3.93%**
- **Deepest Drawdown (Max MAE) in a Winner:** **-12.67%**
- **Adverse Drawdown Distribution on Winners:**
  - `0% to -2%`: 27.8% (Immediate launch)
  - `-2% to -4%`: 29.6% (Mild noise)
  - `-4% to -6%`: 22.6% (Standard consolidation)
  - `-6% to -8%`: 20.0% (Deep retest near stop)
- **Conclusion:** Young positions need room to consolidate (42.6% of eventual winners dip below -4% MAE). Once in mature profit ($\ge +25\%$), the 20 EMA trailing exit protects accumulated gains, while the 20-day tenure cut recycles stagnant capital into fresh breakouts. Margin sizing keeps available cash buffer safe without over-leveraging.

---

### 🔬 WEEKLY TIMEFRAME RESEARCH & BENCHMARK COMPARISON

A comprehensive backtest was conducted comparing the **Daily Baseline** against two weekly operational modes across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots):
1. **Weekly Literal (50w/20w)**: Direct translation of parameters to weekly bars (50-week Donchian High Breakout, 20-week Low Exit, 50-week EMA Stage 2, 20-week Tenure Cut).
2. **Weekly Equivalent (10w/4w)**: Horizon-normalized weekly model (10-week Breakout $\approx$ 50 trading days, 4-week Exit $\approx$ 20 trading days, 10-week EMA / 40-week SMA Stage 2 $\approx$ Weinstein/Minervini 50d/200d equivalent, 4-week Tenure Cut $\approx$ 20 days).

| Metric | 2026 YTD | Last 12 Months | Last 2 Years | Last 5 Years |
| :--- | :--- | :--- | :--- | :--- |
| **Daily Baseline Return** | **+39.91%** (CAGR 49.1%) | **+49.84%** (CAGR 50.6%) | **+79.42%** (CAGR 34.7%) | **+425.90%** (CAGR 40.1%) |
| **Weekly Equivalent (10w/4w) Return** | **+36.72%** (CAGR 42.4%) | **+54.18%** (CAGR 52.9%) | **+35.97%** (CAGR 16.4%) | **+361.13%** (CAGR 35.0%) |
| **Weekly Literal (50w/20w) Return** | **+10.51%** (CAGR 12.0%) | **+46.85%** (CAGR 45.8%) | **-0.89%** (CAGR -0.4%) | **+33.16%** (CAGR 5.8%) |
| **Daily Baseline Max DD** | -11.72% | -11.31% | **-12.81%** | -29.53% |
| **Weekly Equivalent Max DD** | **-9.49%** | **-10.36%** | -23.56% | **-29.15%** |
| **Weekly Literal Max DD** | -10.59% | -9.96% | -26.66% | -34.14% |
| **Daily Baseline Win Rate** | 36.96% | 42.11% | **47.06%** | 43.75% |
| **Weekly Equivalent Win Rate** | **61.36%** | **54.90%** | 45.83% | **44.40%** |
| **Weekly Literal Win Rate** | 41.38% | 43.33% | 28.30% | 31.45% |
| **Daily Baseline Profit Factor** | 2.87 | 3.24 | **2.99** | **2.82** |
| **Weekly Equivalent Profit Factor** | **3.75** | **5.37** | 1.96 | 2.52 |
| **Weekly Literal Profit Factor** | 1.71 | 4.09 | 0.98 | 1.36 |
| **Trades (Daily vs W-Eq vs W-Lit)** | 46 vs 44 vs 29 | 57 vs 51 vs 30 | 102 vs 96 vs 53 | 288 vs 232 vs 124 |

#### Key Research Takeaways:
1. **Weekly Equivalent (10w/4w) is highly viable & robust:**
   - Outperformed Daily in the **Last 12 Months (+54.18% vs +49.84%)** with higher win rate (**54.9% vs 42.1%**) and lower drawdown (**-10.36% vs -11.31%**).
   - Achieved an outstanding **61.36% win rate** in 2026 YTD with a lower drawdown (-9.49%).
   - Across 5 Years, compounded capital from ₹1.00L to **₹4.61 Lakhs (+361.13%, 35.0% CAGR)**, operating with ~20% fewer trades and zero intraday noise.
2. **Weekly Literal (50w/20w) suffers from excessive lag:**
   - 50 weeks (~1 full year) is too slow for swing momentum in Indian equities; entry occurs when the primary trend is already overextended, resulting in severe whipsaws in 2-year choppy regimes (-0.89% return).
3. **Daily remains superior for multi-year compounding:**
   - Daily (+425.90% over 5 years, +79.42% over 2 years) captures quick intraday/daily breakout acceleration and cuts failing trades within days rather than waiting for Friday closes, protecting capital during prolonged corrective regimes like late 2024.



---

### 🔬 RISING 200 SMA ENTRY FILTER RESEARCH & BENCHMARK COMPARISON

A rigorous multi-horizon backtest was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) comparing the **Baseline Stage 2 Filter** against explicit **Rising 200 SMA** entry conditions:
1. **Baseline**: Price > 50 EMA > 200 SMA
2. **200 SMA Rising (1-day slope)**: SMA_200[t] > SMA_200[t-1]
3. **200 SMA Rising (20-day / 1-month slope - Minervini Template)**: SMA_200[t] > SMA_200[t-20]

| Metric & Horizon | Baseline (Price > 50 EMA > 200 SMA) | 200 SMA Rising (1-Day Slope) | 200 SMA Rising (20-Day / 1-Mo Slope) |
| :--- | :--- | :--- | :--- |
| **2026 YTD Return** | **+39.91%** (CAGR 49.1%) | **+39.91%** (CAGR 49.1%) | **+36.95%** (CAGR 45.3%) |
| **Last 12M Return** | **+49.84%** (CAGR 50.6%) | **+49.84%** (CAGR 50.6%) | **+41.98%** (CAGR 42.6%) |
| **Last 2Y Return** | **+79.42%** (CAGR 34.7%) | **+79.42%** (CAGR 34.7%) | **+76.70%** (CAGR 33.6%) |
| **Last 5Y Return** | **+425.90%** (CAGR 40.1%) | **+425.90%** (CAGR 40.1%) | **+305.42%** (CAGR 32.9%) |
| **5-Year Ending Equity** | **₹5,25,896.64** | **₹5,25,896.64** | **₹4,05,420.00** (-₹1.20L profit drag) |
| **2026 YTD Max DD** | -11.72% | -11.72% | **-10.61%** |
| **5-Year Max DD** | **-29.53%** | **-29.53%** | -30.39% |
| **5-Year Profit Factor** | **2.82** | **2.82** | **2.49** |
| **5-Year Total Trades** | 288 (126W / 162L) | 288 (126W / 162L) | 300 (121W / 179L) |
| **5-Year Win Rate** | **43.75%** | **43.75%** | **40.33%** |

#### Key Takeaways:
1. **1-Day Slope is Mathematically Redundant**:
   - Because our baseline already demands a 50-day Donchian High breakout within 10% of 52W high and Price > 50 EMA > 200 SMA, the price entering the 200 SMA calculation window is virtually always substantially higher than the price exiting it (Close_t > Close_t-200). The 200 SMA is already sloping upward at the exact moment of entry.
2. **20-Day Slope Introduces Significant Lag and Opportunity Drag**:
   - Demanding that 200 SMA has already been rising for 20 trading days (~1 month) penalizes the highest-velocity turnaround leaders emerging from deep stage 1 bases.
   - It delays entry into early monster leaders, reduces 5-year compounding by **120.48% (₹1.20 Lakhs)**, lowers the 5-year win rate from 43.8% to 40.3%, and degrades Profit Factor from 2.82 to 2.49.
3. **Recommendation**:
   - Retain the baseline filter: Price > 50 EMA > 200 SMA. It inherently guarantees an upward momentum trajectory without introducing harmful trend lag.

---

### 🔬 DONCHIAN ENTRY LOOKBACK RESEARCH (50-DAY VS 55-DAY BENCHMARK)

A multi-horizon backtest was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) comparing the **Baseline 50-Day Donchian Entry** (`entry_len = 50`) against a **55-Day Donchian Entry** (`entry_len = 55`):

| Metric & Horizon | Baseline (50-Day Donchian High) | Experimental (55-Day Donchian High) | Variance / Impact |
| :--- | :--- | :--- | :--- |
| **2026 YTD Return** | **+39.91%** (CAGR 49.07%) | **+39.91%** (CAGR 49.07%) | Identical performance |
| **2026 YTD Max DD** | **-11.72%** | **-11.72%** | Identical |
| **2026 YTD Trades (WR %)** | 46 trades (37.0% WR) | 46 trades (37.0% WR) | Identical |
| **Last 12M Return** | **+49.84%** (CAGR 50.57%) | **+49.84%** (CAGR 50.57%) | Identical performance |
| **Last 12M Max DD** | **-11.31%** | **-11.31%** | Identical |
| **Last 12M Trades (WR %)** | 57 trades (42.1% WR) | 57 trades (42.1% WR) | Identical |
| **Last 2Y Return** | **+79.42%** (CAGR 34.66%) | **+79.39%** (CAGR 34.65%) | -0.03% (Marginal difference) |
| **Last 2Y Max DD** | -12.81% | **-12.23%** | +0.58% DD improvement |
| **Last 2Y Trades (WR %)** | 102 trades (47.1% WR) | 100 trades (48.0% WR) | 2 fewer trades |
| **Last 5Y Return** | **+425.90%** (CAGR 40.08%) | **+355.63%** (CAGR 36.06%) | **-70.27% drag (-₹70,267)** |
| **5-Year Ending Equity** | **₹5,25,896.64** | **₹4,55,629.50** | **-₹70,267 profit reduction** |
| **5-Year Max DD** | -29.53% | **-29.40%** | Comparable (-0.13% variance) |
| **5-Year Profit Factor** | **2.82** | 2.49 | -0.33 degradation |
| **5-Year Win Rate** | **43.75%** (126W / 162L) | 41.14% (123W / 176L) | -2.61% lower win rate |
| **5-Year Trades** | 288 trades | 299 trades | +11 trades |

#### Key Analytical Findings:
1. **Short-to-Medium Horizons (1–2 Years):**
   - In 2026 YTD and the Last 12 Months, `entry_len = 50` and `entry_len = 55` yield identical performance (+39.91% and +49.84% respectively) across identical trades. When stocks break out near 52-week highs in strong market regimes, the 50-day and 55-day channel highs are practically coincident.
   - In the 2-Year window, the return is nearly identical (+79.42% vs +79.39%), with drawdown slightly lower (-12.23% vs -12.81%).
2. **Long-Term Compounding Drag (5 Years):**
   - Over a 5-year multi-cycle period, `entry_len = 55` introduces an unnecessary 1-week execution lag (11 trading weeks vs 10 trading weeks / 2.5 calendar months).
   - Waiting for 55 days enters breakouts later at a higher, more extended price. This reduces the upside margin on runaway winners and causes earlier stops on minor consolidations, lowering the 5-year win rate from 43.8% to 41.1% and the Profit Factor from 2.82 down to 2.49.
   - As a result, 5-year capital compounding drops from **₹5,25,897 (+425.9%)** down to **₹4,55,630 (+355.6%)**, representing a **₹70,267 profit penalty**.
3. **Recommendation:**
   - **Keep `entry_len = 50` as the standard baseline**. It strikes the optimal balance between filtering out noise and entering stage-2 momentum trends before price becomes overextended.

---

### 🔬 VOLATILITY CONTRACTION / BASE TIGHTNESS (VCP) RESEARCH & BENCHMARK

A comprehensive multi-horizon study was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) testing the hypothesis that **breakouts emerging from tight, low-volatility consolidations (VCP / Base Tightness) improve win rates or reduce drawdowns**.

Six quantitative formulations of pre-breakout contraction were benchmarked against the **Baseline** across all 4 standard horizons:
1. **Baseline**: 50D Breakout, within 10% of 52W High, Price > 50 EMA > 200 SMA (No VCP filter)
2. **ATR Compression 90%**: Short ATR (10d) / Long ATR (50d) $\le 0.90$ leading into breakout
3. **ATR Compression 85%**: Short ATR (10d) / Long ATR (50d) $\le 0.85$ leading into breakout
4. **Tight 10D Base ($\le 10\%$)**: 10-day price spread leading into breakout $\le 10.0\%$ of price
5. **Tight 10D Base ($\le 12\%$)**: 10-day price spread leading into breakout $\le 12.0\%$ of price
6. **Range Compression Ratio**: 10-day range / 50-day channel range $\le 0.50$
7. **Low Volatility (Normalized ATR)**: 14-day ATR $\le 3.5\%$ of price

| Model / Filter Variant | 2026 YTD Return (Max DD) | 1-Year Return (Max DD) | 2-Year Return (Max DD) | 5-Year Return (Max DD) | 5-Year Profit Factor | 5-Year Win Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline (No VCP Filter)** | **+39.91%** (-11.7%) | **+49.84%** (-11.3%) | **+79.42%** (-12.8%) | **+425.90%** (-29.5%) | **2.82** | **43.75%** (126W/162L) |
| **ATR Compression ($\le 0.90$)** | -1.95% (-8.9%) | -1.16% (-8.8%) | +17.65% (-8.1%) | +171.37% (-14.7%) | 2.60 | 42.02% (79W/109L) |
| **ATR Compression ($\le 0.85$)** | -2.06% (-5.6%) | -4.59% (-8.0%) | +1.14% (-8.1%) | +96.44% (-8.8%) | 2.32 | 38.71% (48W/76L) |
| **Tight 10D Base ($\le 10\%$)** | +1.88% (-11.8%) | +12.19% (-12.0%) | +16.84% (-11.7%) | +91.57% (-27.0%) | 1.66 | 37.13% (101W/171L) |
| **Tight 10D Base ($\le 12\%$)** | +15.87% (-10.0%) | +20.55% (-14.3%) | +33.87% (-13.2%) | +130.34% (-28.3%) | 2.01 | 35.89% (103W/184L) |
| **Range Ratio ($\le 0.50$)** | +8.99% (-14.6%) | +22.70% (-9.7%) | +6.99% (-22.3%) | +74.40% (-31.6%) | 1.38 | 37.38% (114W/191L) |
| **Low ATR% ($\le 3.5\%$)** | +12.45% (-10.1%) | +21.54% (-12.7%) | +45.76% (-14.4%) | +109.05% (-30.8%) | 1.77 | 39.72% (112W/170L) |

#### Key Analytical Findings:
1. **Severe Performance Destruction Across All Horizons:**
   - Every single volatility contraction / base tightness variant drastically underperforms the baseline across all 4 timeframes.
   - In 2026 YTD and the Last 12 Months, strict ATR compression actually turned profitable regimes into **net losing performances** (-1.95% and -1.16% vs +39.91% and +49.84% in the baseline).
   - Over 5 years, requiring tight bases or ATR compression slashed total return from **+425.90% down to between +74% and +171%**, representing an opportunity loss of over **₹2.5 Lakhs to ₹3.5 Lakhs**.
2. **Structural Market Mechanics (Why VCP Fails on Stage 2 Trend Following):**
   - **True Momentum Leaders are Dynamic, Not Dormant**: In high-growth Indian equities, institutional accumulation actively expands volatility and daily ranges as the stock approaches 52-week highs. Forcing an arbitrary tight consolidation filter filters out the strongest secular multibaggers (the 50%+ and 100%+ runners that generate the vast majority of portfolio gains).
   - **Adverse Selection Bias**: Restricting entries to low-volatility / tight ranges selects sluggish, low-beta, defensive stocks or range-bound names that lack aggressive institutional accumulation. When they finally "break out", they lack momentum velocity and frequently fail, depressing the win rate from 43.8% down to 35-38%.
3. **Recommendation:**
   - **DO NOT implement Volatility Contraction or Base Tightness entry filters.**
   - Retain the baseline filter: Price > 50 EMA > 200 SMA within 10% of 52W High. It allows high-momentum leaders to be captured naturally without artificial volatility penalties.

---

### 🔬 NIFTY 50 VS. NIFTY 500 UNIVERSE RESEARCH & BENCHMARK COMPARISON

A rigorous multi-horizon comparative backtest was conducted comparing the identical **Turtle System 2** trend-following strategy across the **Nifty 500 master universe** (500 stocks) and the **Nifty 50 large-cap universe** (50 stocks) under identical portfolio sizing rules (Starting Capital: ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots, 3 per sector):

| Metric & Horizon | 2026 YTD (Current Year) | Last 12 Months | Last 2 Years | Last 5 Years |
| :--- | :--- | :--- | :--- | :--- |
| **Date Window** | 2026-01-01 to 2026-11-09 | 2025-11-10 to 2026-11-09 | 2024-11-11 to 2026-11-09 | 2021-11-10 to 2026-11-09 |
| **Nifty 500 Total Return** | **+39.91%** | **+49.84%** | **+79.42%** | **+425.90%** |
| **Nifty 50 Total Return** | **-10.60%** | **-4.10%** | **-4.55%** | **+53.08%** |
| **Performance Variance (Delta)** | **-50.51% drag** | **-53.94% drag** | **-83.97% drag** | **-372.82% drag (-₹3.73 Lakhs)** |
| **Nifty 500 Ending Equity** | **₹1,39,914.82** | **₹1,49,842.37** | **₹1,79,420.33** | **₹5,25,896.64** |
| **Nifty 50 Ending Equity** | **₹89,399.37** | **₹95,895.60** | **₹95,451.73** | **₹1,53,081.31** |
| **Nifty 500 CAGR** | **+49.07%** | **+50.57%** | **+34.66%** | **+40.08%** |
| **Nifty 50 CAGR** | -12.47% | -4.15% | -2.34% | +9.03% |
| **Nifty 500 Max Drawdown** | **-11.72%** | **-11.31%** | **-12.81%** | -29.53% |
| **Nifty 50 Max Drawdown** | -12.84% | -11.76% | -13.07% | **-14.73%** |
| **Nifty 500 Profit Factor** | **2.87** | **3.24** | **2.99** | **2.82** |
| **Nifty 50 Profit Factor** | 0.25 | 0.60 | 0.79 | 1.49 |
| **Nifty 500 Sharpe ($R_f=6.5\%$)** | **1.79** | **1.79** | **1.29** | **1.37** |
| **Nifty 50 Sharpe** | -1.78 | -0.95 | -0.81 | 0.25 |
| **Nifty 500 Win Rate** | **37.0%** (17W / 29L) | **42.1%** (24W / 33L) | **47.1%** (48W / 54L) | **43.8%** (126W / 162L) |
| **Nifty 50 Win Rate** | 22.0% (9W / 32L) | 24.4% (11W / 34L) | 27.9% (24W / 62L) | 33.9% (81W / 158L) |
| **Nifty 500 Avg Win / Avg Loss** | **+25.24% / -7.53%** | **+22.53% / -6.29%** | **+17.62% / -5.67%** | **+21.07% / -6.38%** |
| **Nifty 50 Avg Win / Avg Loss** | +4.92% / -4.54% | +5.94% / -4.21% | +8.18% / -4.33% | +15.70% / -4.41% |
| **Nifty 500 Win/Loss Ratio** | **3.35x** | **3.58x** | **3.11x** | **3.30x** |
| **Nifty 50 Win/Loss Ratio** | 1.08x | 1.41x | 1.89x | **3.56x** |
| **Nifty 500 Avg Active Margin** | ₹83,307 (72.1%) | ₹90,112 (76.1%) | ₹91,118 (73.2%) | ₹1,91,089 (79.9%) |
| **Nifty 50 Avg Active Margin** | ₹51,443 (55.0%) | ₹60,030 (60.2%) | ₹59,457 (59.4%) | ₹90,786 (67.5%) |
| **Nifty 500 Peak Margin Deployed** | ₹1,39,722 (100%) | ₹1,50,069 (100%) | ₹179,598 (100%) | ₹5,25,880 (100%) |
| **Nifty 50 Peak Margin Deployed** | ₹100,244 (100%) | ₹104,230 (100%) | ₹105,931 (100%) | ₹1,71,473 (100%) |

---

#### 🔍 Critical Analytical Drivers of Nifty 50 Underperformance

1. **The "Fat Right Tail" (Multibagger Asymmetry) is Absent in Mega Caps:**
   - Donchian trend following and momentum investing are fundamentally **convex, fat-tailed strategies**. They tolerate a sub-50% win rate because a small cluster of massive runaway winners (+50%, +100%, +200%) covers all smaller losses and powers overall portfolio compounding.
   - In Nifty 500, broad secular leaders (e.g. defense, capital goods, power, electronics manufacturing) deliver sustained explosive momentum. In 2026 YTD and the Last 12M, Nifty 500 average winning trades yielded **+25.24%** and **+22.53%**.
   - In Nifty 50, mega caps (e.g. Reliance, TCS, HDFC Bank, Infosys, ITC) rarely stage multi-month explosive rallies. The average winner in Nifty 50 was only **+4.92% (2026 YTD)** and **+5.94% (Last 12M)**. Without explosive right-tail expansion, standard trading frictions and whipsaw stops erode equity.
2. **Heavy Mean Reversion & Institutional Algo Dominance in Nifty 50:**
   - Nifty 50 stocks are the most liquid, institutional, and derivatives-heavy securities on the NSE. They are dominated by institutional arbitrage, options market makers, and mean-reversion algorithms.
   - Breakouts beyond 50-day Donchian highs in Nifty 50 frequently trigger immediate institutional profit-taking and mean-reversion, leading to high false-break rates. Consequently, Nifty 50 win rates collapse to **22.0% in 2026 YTD** and **24.4% in 12M** (vs. 37.0% and 42.1% in Nifty 500).
3. **Severe Breadth & Cash Drag Constraint:**
   - In a 50-stock universe with strict Stage 2 uptrend filters (Price > 50 EMA > 200 SMA and within 10% of 52W High), there are frequently only 2 to 5 stocks meeting the setup at any given time.
   - With 10 portfolio slots available, Nifty 50 operated at an average margin utilization of only **55% to 60%** (cash cushion hovered at ~₹40,000 idle out of ₹1,00,000).
   - In contrast, Nifty 500 consistently deployed **72% to 80%** of capital into high-velocity trend leaders, maximizing capital compounding velocity.
4. **Strategic Conclusion:**
   - **The Donchian / Stage-2 momentum engine must remain deployed on the Nifty 500 universe.**
   - Restricting the strategy to Nifty 50 converts a top-quartile market-beating system (+425.9% 5Y CAGR 40.1%) into a stagnant, underperforming model (+53.1% 5Y CAGR 9.0%, and net negative over 1-year and 2-year horizons).

---

### 🔬 DUAL-TIMEFRAME SWING TRADING RESEARCH & BENCHMARK ("APEX SWING")

A comprehensive multi-horizon study was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) designing and backtesting an institutional **Dual-Timeframe Swing Trading Strategy ("Apex Swing")** leveraging both **Weekly** (Macro Trend & Stage 2 Filter) and **Daily** (Tactical Timing & Squeeze Breakout) candle datasets.

#### Strategy Specification
1. **Weekly Macro Filter (The Compass)**:
   - Weinstein Stage 2: $10\text{ WEMA} > 30\text{ WEMA}$ and Weekly Close $> 10\text{ WEMA}$.
   - Momentum Power Zone: $\text{Weekly RSI}(14) \ge 50.0$.
   - Zero lookahead bias: Shifted strictly by 1 completed week (`shift(1)`).
2. **Daily Tactical Setups**:
   - **Setup A (20 EMA Pullback Bounce - "The Trampoline")**:
     - Daily Stage 2 ($\text{Close} > 50\text{ EMA} > 200\text{ SMA}$).
     - Low touched within $1.5\%$ of $20\text{ EMA}$ in last 3 days.
     - Day $T$ triggers green reversal candle closing in upper $40\%$ of range with $\text{RVOL} \ge 1.20$.
   - **Setup B (TTM Volatility Squeeze & Pocket Pivot - "The Spring")**:
     - Bollinger Bands ($20, 2.0$) inside Keltner Channels ($20, 1.5\text{ ATR}$) within last 5 days.
     - Price breaks above 20-day high with Pocket Pivot ($\text{Volume} > \text{max down-volume in 10 days}$) and $\text{RVOL} \ge 1.25$.
     - Proximity to 52-week high within $15\%$.
3. **4-Tier Asymmetric Exits**:
   - **Initial Stop**: $\max(\text{Swing Low}, \text{Entry} - 1.5 \times \text{ATR}_{14})$ (hard capped at max $-5.5\%$).
   - **Target 1 Derisk**: At $+2R$ profit, sell $50\%$ position and move Stop Loss on remaining $50\%$ to Breakeven ($\text{Entry Price}$).
   - **Runner Trailing**: Exit remaining $50\%$ when Daily Close $< 10\text{ EMA}$.
   - **Climax Exit**: Daily $\text{RSI} \ge 78.0$ and Price $\ge 1.08 \times 20\text{ EMA}$ (blow-off top).
   - **Stagnation Time Stop**: Held $\ge 12$ trading days and position P&L is $< +1R$ (prunes dead money).

---

#### 📊 4-Horizon Comparative Performance Matrix: Apex Swing vs. Baseline Donchian

| Performance Metric | 2026 YTD | Last 12 Months | Last 2 Years | Last 5 Years |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline Donchian Ending Equity** | **₹1,39,914.82** | **₹1,49,842.37** | **₹1,79,420.33** | **₹5,25,896.64** |
| **Apex Swing Ending Equity** | ₹1,06,695.14 | ₹1,23,521.38 | ₹1,23,931.36 | ₹2,68,869.72 |
| **Baseline Donchian Return %** | **+39.91%** | **+49.84%** | **+79.42%** | **+425.90%** |
| **Apex Swing Return %** | +6.70% | +23.52% | +23.93% | +168.87% |
| **Baseline Donchian CAGR %** | **49.07%** | **50.57%** | **34.66%** | **40.08%** |
| **Apex Swing CAGR %** | 8.01% | 23.84% | 11.54% | 22.24% |
| **Baseline Donchian Max DD %** | -11.72% | -11.31% | **-12.81%** | -29.53% |
| **Apex Swing Max DD %** | **-9.46%** | **-8.03%** | -14.06% | **-21.04%** |
| **Baseline Donchian Win Rate %** | 37.0% (17W / 29L) | 42.1% (24W / 33L) | 47.1% (48W / 54L) | 43.8% (126W / 162L) |
| **Apex Swing Win Rate %** | **55.2%** (80W / 65L) | **56.5%** (108W / 83L)| **50.5%** (184W / 180L)| **57.1%** (623W / 469L) |
| **Baseline Profit Factor** | **2.87** | **3.24** | **2.99** | **2.82** |
| **Apex Swing Profit Factor** | 1.07 | 1.42 | 1.21 | 1.38 |
| **Baseline Total Trades** | 46 trades | 57 trades | 102 trades | 288 trades |
| **Apex Swing Total Trades** | **145 trades** | **191 trades** | **364 trades** | **1,092 trades** |
| **Baseline Avg Holding Period** | 44.2 days | 45.7 days | 48.9 days | 47.0 days |
| **Apex Swing Avg Holding Period**| **14.3 days** | **13.4 days** | **13.3 days** | **13.4 days** |

---

#### 🔬 Setup Component Attribution (Last 12 Months)

| Swing Mode | Total Return % | Win Rate % | Profit Factor | Total Trades | Max Drawdown % | Avg Holding Days |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Setup A: 20 EMA Pullback Bounce** | +20.34% | 55.9% | 1.46 | 188 | **-5.97%** | 13.7 days |
| **Setup B: Volatility Squeeze Breakout**| +19.71% | **59.2%** | **1.49** | 147 | **-5.68%** | 14.2 days |
| **Apex Swing (Combined A + B)** | **+23.52%** | 56.5% | 1.42 | 191 | -8.03% | **13.4 days** |

---

#### 💡 Key Strategic Takeaways:
1. **Dramatic Win Rate Surge (Psychological Edge)**:
   - Apex Swing lifts the strategy win rate from the baseline's **37%–44% up to 55%–59%** across all market cycles.
   - The Volatility Squeeze setup achieved an impressive **59.2% win rate** with only **-5.68% max drawdown** over 12 months.
2. **Swift Holding Period (True Swing Velocity)**:
   - Average holding time dropped from **47 days to ~13.4 days** (a ~70% reduction in capital lockup).
   - High trade frequency (1,092 trades over 5 years vs. 288) ensures dynamic capital turnover and continuous redeployment into fresh setups.
3. **Smooth Equity Curve & Low Drawdown**:
   - The 5-year maximum drawdown dropped by **8.49 percentage points** (from **-29.53% down to -21.04%**).
   - The 12-month drawdown was capped at **-8.03%** (and sub-6% on individual setups).
4. **The Structural Trade-Off (Compounding vs. Velocity)**:
   - Because swing trading locks in profits at $+2R$ and aggressively cuts positions at 12–14 days, it deliberately truncates the "far-right tail" (the rare $+80\%$ to $+120\%$ multi-month runaway compounders like Cupid, Ather, or Inox India).
   - As a consequence, 5-year total return is **+168.87% (22.24% CAGR)** for Apex Swing vs. **+425.90% (40.08% CAGR)** for the Donchian trend follower.
5. **Practical Recommendation**:
   - **For High-Frequency, Low-Drawdown Swing Traders**: Apex Swing (especially Setup B Squeeze Breakout) is ideal for traders who prioritize a **near-60% win rate, sub-6% to -9% drawdowns, and 2-week fast capital recycling**.
   - **For Long-Term Wealth Compounding**: The Baseline Donchian Stage 2 model remains optimal for maximizing total multi-year net worth by capturing monster secular trends.

---

### 🔬 CHARTINK SUPERTREND(7, 3) + RSI>60 + 20/200 SMA BENCHMARK

A comprehensive backtest was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) implementing and testing the user's **Chartink Scanner Strategy** across 4 standard horizons:
- **Entry Rules**:
  1. `Daily SMA(Close, 20) > Daily SMA(Close, 200)` (Golden Cross / Bullish Regime)
  2. `Daily Close > Daily SMA(Close, 20)` (Price above 20-day mean)
  3. `Daily Close > Daily Supertrend(7, 3)` (Bullish Supertrend Regime)
  4. `Daily RSI(14) > 60` (Bullish Momentum Power Zone)
  5. `Daily Volume > 100,000` (Liquidity Filter)
- **Exit Variations Tested**:
  - **Exit A**: Pure Supertrend(7, 3) Flip (Close < Supertrend)
  - **Exit B**: 20 SMA Breakdown (Close < 20 SMA)
  - **Exit C**: Tiered Profit-Lock (+25% gain & Close < 20 EMA, or Supertrend Flip)

| Strategy & Exit Model | 2026 YTD | Last 12 Months | Last 2 Years | Last 5 Years |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline Donchian (2-Tier Exit)** | **+39.91%** (CAGR 49.1%) | **+49.84%** (CAGR 50.6%) | **+79.42%** (CAGR 34.7%) | **+425.90%** (CAGR 40.1%) |
| **Chartink (Supertrend Flip Exit)** | **+26.52%** (CAGR 32.3%) | **+38.98%** (CAGR 39.5%) | **+28.62%** (CAGR 13.7%) | **+354.62%** (CAGR 36.0%) |
| **Chartink (20 SMA Breakdown Exit)**| +9.58% (CAGR 11.5%) | +11.02% (CAGR 11.2%) | +26.38% (CAGR 12.7%) | +233.54% (CAGR 27.7%) |
| **Chartink (Tiered +25% Lock Exit)**| +22.62% (CAGR 27.4%) | +33.34% (CAGR 33.8%) | +31.35% (CAGR 14.9%) | +327.56% (CAGR 27.2%) |
| **Baseline Donchian Max DD %** | -11.72% | -11.31% | **-12.81%** | -29.53% |
| **Chartink (Supertrend Flip) Max DD**| **-7.79%** | **-11.14%** | -18.67% | **-18.64%** |
| **Chartink (20 SMA Breakdown) Max DD**| -11.04% | -11.12% | -14.90% | -23.51% |
| **Chartink (Supertrend Flip) Win Rate**| **50.0%** (16W / 16L) | **51.3%** (20W / 19L) | **43.4%** (33W / 43L) | **46.7%** (93W / 106L) |
| **Baseline Donchian Win Rate** | 37.0% (17W / 29L) | 42.1% (24W / 33L) | 47.1% (48W / 54L) | 43.8% (126W / 162L) |
| **Chartink (Supertrend Flip) Profit Factor**| **3.38** | **3.00** | 1.73 | **2.93** |
| **Baseline Donchian Profit Factor** | 2.87 | 3.24 | **2.99** | 2.82 |
| **Chartink (Supertrend Flip) Trades**| 32 trades | 39 trades | 76 trades | 199 trades |
| **Baseline Donchian Trades** | 46 trades | 57 trades | 102 trades | 288 trades |
| **Chartink (Supertrend Flip) Avg Hold**| 66.3 days | 70.7 days | 66.4 days | 72.0 days |
| **Baseline Donchian Avg Hold** | 44.2 days | 45.7 days | 48.9 days | 47.0 days |

#### Key Analytical Findings:
1. **The Chartink Scanner with Supertrend Flip is Highly Robust**:
   - Compounded initial ₹1.00L capital to **₹4,54,615.57 (+354.62% / 36.0% CAGR)** over 5 years.
   - Outperformed in risk-adjusted metrics by slashing 5-year Max Drawdown from **-29.53% down to -18.64%** (nearly 11 percentage points lower drawdown).
   - In 2026 YTD, achieved a **50.0% win rate**, **3.38 Profit Factor**, and only **-7.79% Max Drawdown**.
2. **Supertrend Flip is Far Superior to 20 SMA Breakdown**:
   - Exiting on `Close < 20 SMA` prematurely cuts winning positions during normal consolidation pullbacks (average hold 23–25 days), dropping 5-year return from +354.6% down to +233.5%.
   - Trailing with `Supertrend(7, 3)` allows stocks to breathe through minor consolidations while providing a strict trailing stop when volatility reverses.
3. **Comparison with Baseline Donchian**:
   - The Baseline Donchian generates higher ultimate compounding (+425.9% vs +354.6%) because the 50-day Donchian High enters earlier at the base breakout rather than waiting for RSI > 60 and SMA 20 > 200 crossover.
   - However, the Chartink Supertrend strategy provides a significantly **smoother equity curve with a sub-19% multi-year drawdown**, making it an exceptional alternative for risk-sensitive trend and momentum traders.
4. **52-Week High Proximity Filter Study on Chartink Supertrend**:
   - In medium horizons (Last 12 Months and Last 2 Years), adding a 52-Week High proximity filter improves performance:
     - **Last 12 Months**: 52W High ($\le 15\%$) increased return from **+38.98% to +42.51%** and boosted Profit Factor from **3.00 to 3.47**.
     - **Last 2 Years**: 52W High ($\le 10\%$) increased return from **+28.62% to +34.08%** and compressed Max Drawdown from **-18.67% down to -14.90%**.
   - However, across a **5-Year multi-cycle horizon**, Pure Chartink without 52W filter generated **+354.62%** vs **+272.15%** with 52W High ($\le 10\%$). This occurs because $SMA(20) > SMA(200)$ captures early stage-2 turnaround leaders emerging from deep bear market bottoms when they are still 20–35% below their all-time 52-week highs. Requiring 52W high proximity delays entry into these early turnaround multi-baggers.

---

### 🔬 HYPER-MOMENTUM SCANNER (RSI>70, MFI>70, CCI>110, VOL 2X) BENCHMARK

A multi-horizon backtest was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) implementing the **Hyper-Momentum Scanner** with **Supertrend(7, 3) Flip Exit**:
- **Entry Rules**:
  1. `RSI(14) >= 70.0` (Extreme Price Velocity)
  2. `Money Flow Index (MFI 14) >= 70.0` (Volume-Weighted Institutional Inflow)
  3. `Commodity Channel Index (CCI 14) >= 110.0` (Cyclical Expansion)
  4. `Volume > 2.0 * SMA_10(Volume)` (2x Volume Ignition)
  5. `Price > EMA(10)`
  6. `Price % Change >= 1.0%`
  7. `Price >= 10.0` (and $\ge 100$ liquidity filter)
- **Exit Rule**:
  - `Supertrend(7, 3) Flip` (Close < Supertrend or Bearish flip)

| Metric & Horizon | Baseline Donchian (50D Breakout) | Chartink Supertrend (RSI>60, 20SMA) | Hyper-Momentum (RSI>70, MFI>70, CCI>110) |
| :--- | :--- | :--- | :--- |
| **2026 YTD Return** | **+39.91%** (CAGR 49.1%) | +26.52% (CAGR 32.3%) | +17.09% (CAGR 20.6%) |
| **Last 12M Return** | **+49.84%** (CAGR 50.6%) | +38.98% (CAGR 39.5%) | +24.23% (CAGR 24.6%) |
| **Last 2Y Return** | **+79.42%** (CAGR 34.7%) | +28.62% (CAGR 13.7%) | +21.42% (CAGR 10.4%) |
| **Last 5Y Return** | **+425.90%** (CAGR 40.1%) | +354.62% (CAGR 36.0%) | +226.63% (CAGR 27.2%) |
| **5-Year Ending Equity** | **₹5,25,896.64** | ₹4,54,615.57 | ₹3,26,632.67 |
| **5-Year Max DD %** | -29.53% | **-18.64%** | -22.19% |
| **5-Year Win Rate %** | 43.8% (126W / 162L) | 46.7% (93W / 106L) | **50.8%** (91W / 88L) |
| **5-Year Profit Factor** | 2.82 | **2.93** | 2.41 |
| **5-Year Total Trades** | 288 trades | 199 trades | 179 trades |
| **Average Holding Days**| 47.0 days | 72.0 days | 75.3 days |

#### Key Analytical Takeaways:
1. **The Overbought Exhaustion Trap**:
   - Requiring $RSI \ge 70$, $MFI \ge 70$, and $CCI \ge 110$ simultaneously with $2x$ volume creates an **extreme climax/blow-off filter**.
   - Entering when all three momentum oscillators are at peak overbought levels forces the strategy to buy right into short-term exhaustion tops.
   - Often, within 2–5 days after entry, institutional profit-taking triggers a sharp mean-reversion pullback before the trend can resume.
2. **Lag Compared to Earlier Momentum Filters**:
   - The earlier Chartink strategy (`RSI > 60`, `SMA 20 > 200`) delivered **+354.62%** over 5 years.
   - By pushing the threshold higher to $RSI \ge 70$, $MFI \ge 70$, and $CCI \ge 110$, return dropped to **+226.63%** (a **₹1.28 Lakhs performance penalty**).
3. **Conclusion**:
   - Extreme oscillator filters ($> 70$ or $> 110$) suffer from buying late in the impulse wave.
   - For momentum breakouts, entering early at the base breakout (Donchian High) or moderate momentum ($RSI > 60$) produces significantly superior multi-year compounding.

---

### 🔬 OLIVER KELL SWING TRADING ("BASE 'N BREAK") BENCHMARK & RESEARCH

A comprehensive multi-horizon backtest was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 slots) implementing **Oliver Kell's 2020 US Investing Championship (+941.1%) Swing Trading Strategy**:
- **Core EMAs**: 10 EMA (fast momentum) and 20 EMA (trend backbone).
- **Trend Alignment**: Price > 10 EMA > 20 EMA + Nifty 500 Market Regime Filter (Index > 50 EMA).
- **"Base 'n Break" Setup**:
  1. Compact 3-to-7-day base (tightness $\le 8.0\%$).
  2. Base formed near 10/20 EMA support.
  3. Breakout over Base High with volume expansion ($RVOL \ge 1.2$).
  4. Initial stop loss placed at the low of the consolidation base.
- **Exits Evaluated**:
  - **Variant A (Kell 20 EMA Exit)**: Close below 20 EMA (or Exhaustion Extension profit-taking $\ge +15\%$ above 10 EMA).
  - **Variant B (Kell 10 EMA Exit)**: Faster momentum exit on Close below 10 EMA.

| Metric & Horizon | Baseline Donchian (50D High, 2-Tier Exit) | Oliver Kell (Base 'n Break, 20 EMA Exit) | Oliver Kell Fast (Base 'n Break, 10 EMA Exit) |
| :--- | :--- | :--- | :--- |
| **2026 YTD Return** | **+39.91%** (CAGR 49.1%) | +18.47% (CAGR 22.0%) | +11.53% (CAGR 13.5%) |
| **2026 YTD Max Drawdown**| -11.72% | **-6.47%** (Sub-7% DD) | -7.38% |
| **2026 YTD Win Rate** | 37.0% (46 trades) | **47.6%** (63 trades) | 44.4% (81 trades) |
| **Last 12M Return** | **+49.84%** (CAGR 50.6%) | +25.67% (CAGR 25.8%) | +16.47% (CAGR 16.5%) |
| **Last 12M Max Drawdown**| -11.31% | **-6.73%** | -8.20% |
| **Last 12M Win Rate** | 42.1% (57 trades) | **47.6%** (82 trades) | 42.7% (103 trades) |
| **Last 2Y Return** | **+79.42%** (CAGR 34.7%) | +27.21% (CAGR 12.8%) | +5.43% (CAGR 2.6%) |
| **Last 2Y Max Drawdown** | -12.81% | **-11.07%** | -18.27% |
| **Last 2Y Profit Factor** | **2.99** | 1.50 | 1.08 |
| **Last 5Y Return** | **+425.90%** (CAGR 40.1%) | +96.69% (CAGR 14.5%) | +42.52% (CAGR 7.3%) |
| **5-Year Ending Equity** | **₹5,25,896.64** | ₹1,96,691.80 | ₹1,42,520.10 |
| **5-Year Max Drawdown** | -29.53% | **-21.10%** | **-18.97%** |
| **5-Year Profit Factor** | **2.82** | 1.48 | 1.19 |
| **5-Year Total Trades** | 288 trades | 418 trades | 522 trades |
| **5-Year Win Rate** | **43.8%** | 34.4% | 32.2% |

#### Key Analytical Takeaways:
1. **Outstanding Drawdown Compression (Capital Preservation Edge)**:
   - The primary strength of Oliver Kell's 20 EMA exit is **unparalleled drawdown control**:
     - 2026 YTD Max Drawdown was slashed from **-11.72% down to -6.47%**.
     - 12-Month Max Drawdown was contained to **-6.73%**.
     - Multi-year 5-year Max Drawdown was compressed from **-29.53% down to -21.10%**.
   - For swing traders who cannot tolerate double-digit portfolio drawdowns, Oliver Kell's tight EMA stops offer a very gentle equity curve.
2. **The "Short-Leash" Premature Exit Drag on Multi-Baggers**:
   - Why did the Baseline beat Kell by **+425.9% vs +96.7%** over 5 years?
   - In the Indian stock market (Nifty 500), leading stage-2 momentum stocks frequently experience 3-to-5-day routine base consolidations or brief intraday touches below the 20 EMA before continuing their 100% to 300% multi-month secular runs.
   - Oliver Kell's rule exits immediately when daily close violates the 20 EMA (average hold time is just 14–22 days). As a result, winning trades are terminated too early, missing the monster second and third stage legs.
   - Baseline Donchian allows runners to breathe using the broader 50-day Donchian structure and 50 EMA stage-2 filter, capturing the massive right tail of returns.
3. **The 10 EMA Exit is Too Hyperactive for Daily Swings**:
   - Exiting on `Close < 10 EMA` generates 522 trades over 5 years and experiences severe whipsaws during choppy sideways regimes, dropping 5-year CAGR to just +7.3%.
4. **52-Week High Proximity Significantly Upgrades Oliver Kell**:
   - When Oliver Kell is coupled with the **Within 10% of 52-Week High filter**, 5-year return jumps from **+96.69% to +160.71% (+64% profit increase)**, 5-year Max Drawdown drops from **-21.10% down to -15.69%**, and win rate rises from **34.4% to 41.2%**.

---

### 🔬 WEEKLY MOMENTUM BREAKOUT (CHARTINK) & DUAL EXIT BENCHMARK

A comprehensive multi-horizon study was conducted across the Nifty 500 universe (capital ₹1,00,000, 10 slots, max 15% allocation cap, max 3 per sector) testing the **Weekly Momentum Breakout Scanner**:
- **Timeframe**: Weekly bars (`W-FRI` resampled from daily candles).
- **Scanner Entry Conditions**:
  1. `Weekly Close > 1 week ago High` ($Close_W > High_{W-1}$)
  2. `Weekly % Change > 5%` ($\Delta\%_W > 5.0\%$)
  3. `1 week ago Close > 2 weeks ago High` ($Close_{W-1} > High_{W-2}$)
  4. Institutional price filter: $Close \ge ₹100$
- **Exit Variations Evaluated**:
  1. **Exit 1 (Supertrend Flip)**: Close below Weekly Supertrend(10, 3) line.
  2. **Exit 1 Alt (Supertrend 7, 3 Flip)**: Close below Weekly Supertrend(7, 3) line.
  3. **Exit 2A (Prev Week Low)**: Weekly Close < Previous Week Low ($Close_W < Low_{W-1}$).
  4. **Exit 2B (Prev Week Close)**: Weekly Close < Previous Week Close ($Close_W < Close_{W-1}$).
  5. **Exit 1 + Protective Stop**: Supertrend(10, 3) Flip with -8% emergency hard stop.
  6. **Enhanced Weekly Model**: Supertrend(10, 3) + -8% Stop + Within 10% of 52-Week High.

| Metric & Horizon | Baseline (Daily 50D, 2-Tier Exit) | Exit 1: ST(10,3) Flip | Exit 1 Alt: ST(7,3) Flip | Exit 2A: Close < Prev Low | Exit 2B: Close < Prev Close | Exit 1 + -8% Stop |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026 YTD Return** | **+39.91%** (CAGR 49.1%) | -2.24% (CAGR -2.6%) | -4.26% (CAGR -4.9%) | -15.68% (CAGR -17.9%)| -8.27% (CAGR -9.5%) | +4.13% (CAGR 4.8%) |
| **2026 YTD Max DD** | **-11.72%** | -14.05% | -13.92% | -25.88% | -17.53% | -14.02% |
| **2026 YTD Win Rate** | 37.0% (46 trades) | 15.4% (13 trades) | 8.3% (12 trades) | 29.9% (77 trades) | **37.3%** (166 trades)| 12.5% (32 trades) |
| **Last 12M Return** | **+49.84%** (CAGR 50.6%) | +20.66% (CAGR 20.7%)| +18.95% (CAGR 19.0%)| -11.98% (CAGR -12.0%)| -8.36% (CAGR -8.4%) | +11.87% (CAGR 11.9%)|
| **Last 12M Max DD** | -11.31% | -14.80% | -13.69% | -25.30% | -17.54% | **-10.07%** |
| **Last 12M Win Rate** | **42.1%** (57 trades) | 28.6% (14 trades) | 25.0% (12 trades) | 29.1% (86 trades) | 35.1% (191 trades)| 13.6% (22 trades) |
| **Last 2Y Return** | **+79.42%** (CAGR 34.7%) | +10.56% (CAGR 5.2%) | -12.67% (CAGR -6.5%)| -21.03% (CAGR -11.1%)| -14.08% (CAGR -7.3%)| +8.97% (CAGR 4.4%) |
| **Last 2Y Max DD** | **-12.81%** | -25.45% | -27.13% | -27.05% | -19.97% | -19.63% |
| **Last 2Y Profit Factor** | **2.99** | 0.88 | 0.39 | 0.71 | 0.85 | 0.63 |
| **Last 5Y Return** | **+425.90%** (CAGR 40.1%) | +127.62% (CAGR 17.8%)| +40.62% (CAGR 7.0%)| +94.32% (CAGR 14.1%)| +3.60% (CAGR 0.7%) | **+233.23%** (CAGR 27.1%)|
| **5-Year Ending Equity** | **₹5,25,896.64** | ₹2,27,615.46 | ₹1,40,620.15 | ₹1,94,315.11 | ₹1,03,603.72 | **₹3,33,228.76** |
| **5-Year Max DD** | **-29.53%** | -42.25% | -39.78% | -39.81% | -34.12% | -33.62% |
| **5-Year Profit Factor** | **2.82** | 2.03 | 1.24 | 1.21 | 1.01 | **2.15** |
| **5-Year Win Rate** | **43.8%** (288 trades) | 39.3% (84 trades) | 30.9% (81 trades) | 36.6% (432 trades) | 35.2% (1,039 trades)| 29.7% (111 trades) |
| **Avg Holding Duration** | 47.0 days | 29.5 weeks (~7 mos) | 29.8 weeks (~7 mos) | 5.5 weeks (~1.3 mos) | 2.0 weeks (~14 days)| 21.4 weeks (~5 mos) |

---

#### 🔍 Critical Analytical Insights & Mechanics:

1. **The "Whipsaw Meat-Grinder" of Exit 2B (Close < Prev Week Close)**:
   - Exiting immediately when the current weekly candle closes below the prior week's close produces severe whipsaw losses (+3.60% across 5 years, -14.08% over 2 years, -8.27% in 2026 YTD).
   - **Reason**: Natural, healthy momentum advances rarely advance in a straight line for 15 consecutive weeks without a single red week. After 2 consecutive expansion weeks (>5%), stocks frequently print an inside or slight pause week before resuming. Exit 2B sells right at the pullback dip, incurring high churn (1,039 trades) and transaction drag.
2. **Exit 2A (Close < Prev Week Low) Exits Too Early on Standard Base Retests**:
   - Exit 2A improves slightly over 2B (+94.32% over 5 years), but suffered net losses in 2026 YTD (-15.68%) and the last 2 years (-21.03%).
   - Normal base breakouts retest the pivot zone, causing weekly closes to dip just under the prior breakout week's low before launching into major secular uptrends.
3. **Exit 1 (Supertrend Flip) Captures Monster Multi-Baggers but Lacks Early Downside Armor**:
   - Supertrend(10, 3) lets runners compound over an average of **29.5 weeks (~7 months)**, turning ₹1.00L into **₹2.28 Lakhs (+127.62%)** over 5 years.
   - However, in bear markets or sudden corrections, weekly Supertrend lags significantly, resulting in a steep **-42.25% Max Drawdown**.
4. **The Power of the Hybrid Protective Stop (Supertrend + -8% Hard Stop)**:
   - When weekly Supertrend(10, 3) is paired with an **-8% protective stop loss**, 5-year compounding leaps from **+127.6% to +233.23% (₹3,33,229)**, and Max Drawdown is compressed from **-42.25% down to -33.62%**.
   - It cuts false breakouts early while allowing genuine multi-month trends to compound safely.
5. **Enhanced Weekly Model (Adding 52-Week High Proximity $\le 10\%$)**:
   - When the weekly scanner is restricted to stocks within 10% of their 52-week high with the -8% protective stop:
     - 5-Year Return reaches **+250.79% (₹3,50,790 ending equity)**.
     - 5-Year Max Drawdown drops to **-30.78%**.
     - Profit Factor rises to **2.28**.
6. **Comparison with Repository Baseline**:
   - While the weekly Supertrend model with protective stops is a viable low-maintenance weekly system (+233.2% 5Y return, ~20 trades/year), the **Daily 50D Baseline (+425.90%, -29.5% DD)** remains superior because daily execution captures intraday pivot acceleration and executes the two-tier profit lock (+25% gain & 20 EMA break) with zero weekly lag.

---

### 🔬 WEEKLY 10 EMA / 20 EMA CROSSOVER STRATEGY BENCHMARK & RESEARCH

A comprehensive multi-horizon study was conducted across the Nifty 500 universe (capital ₹1,00,000, 10% equal allocation per slot, max 10 concurrent slots, max 3 stocks per sector, minimum stock price ₹100) backtesting the user's **Weekly EMA Crossover Strategy**:
- **Timeframe**: Weekly (resampled Friday close bars from daily candles).
- **Entry Condition**: Weekly 10 EMA crosses above Weekly 20 EMA ($EMA_{10}[W] > EMA_{20}[W]$ and $EMA_{10}[W-1] \le EMA_{20}[W-1]$).
- **Exit Condition**: Weekly 10 EMA crosses below Weekly 20 EMA ($EMA_{10}[W] < EMA_{20}[W]$ and $EMA_{10}[W-1] \ge EMA_{20}[W-1]$).
- **Execution Timing**: Signals generated at Friday close $W$, executed at Monday open $W+1$.

#### Multi-Horizon Benchmark Matrix (All 4 Standard Horizons):

| Metric & Horizon | Baseline (Daily 50D Donchian) | Pure Weekly 10/20 EMA Cross | Weekly 10/20 Cross + -8% Stop | Weekly 10/20 Cross + Fast Exit (Close < 20 EMA) | Weekly 10/20 Cross + Market Regime | Weekly 10/20 Cross + 52W High Filter + -8% Stop |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026 YTD Return** | **+39.91%** (CAGR 49.1%) | -6.59% (CAGR -7.6%) | -11.93% (CAGR -13.7%) | -11.30% (CAGR -12.9%) | -14.21% (CAGR -16.2%) | -5.65% (CAGR -6.5%) |
| **2026 YTD Max DD** | **-11.72%** | -16.82% | -19.92% | -14.38% | -17.56% | -14.28% |
| **2026 YTD Win Rate** | **37.0%** (46 trades) | 10.7% (28 trades) | 7.7% (39 trades) | 28.6% (49 trades) | 3.7% (27 trades) | 15.6% (32 trades) |
| **2026 YTD Profit Factor** | **2.87** | 0.10 | 0.10 | 0.53 | 0.01 | 0.11 |
| **Last 12M Return** | **+49.84%** (CAGR 50.6%) | +13.44% (CAGR 13.4%) | -2.54% (CAGR -2.5%) | -1.83% (CAGR -1.8%) | +9.87% (CAGR 9.9%) | -4.39% (CAGR -4.4%) |
| **Last 12M Max DD** | -11.31% | -13.79% | **-10.83%** | -14.60% | -12.72% | -17.98% |
| **Last 12M Win Rate** | **42.1%** (57 trades) | 19.0% (21 trades) | 13.8% (29 trades) | 27.1% (48 trades) | 15.0% (20 trades) | 16.7% (30 trades) |
| **Last 12M Profit Factor** | **3.24** | 0.24 | 0.19 | 0.91 | 0.15 | 0.23 |
| **Last 2Y Return** | **+79.42%** (CAGR 34.7%) | -19.51% (CAGR -10.3%) | -4.07% (CAGR -2.1%) | -20.58% (CAGR -10.9%) | -7.45% (CAGR -3.8%) | +7.28% (CAGR 3.6%) |
| **Last 2Y Max DD** | **-12.81%** | -24.55% | -16.45% | -25.65% | -23.89% | -16.67% |
| **Last 2Y Win Rate** | **47.1%** (102 trades) | 27.1% (48 trades) | 21.7% (60 trades) | 25.7% (105 trades) | 12.5% (40 trades) | 26.0% (50 trades) |
| **Last 2Y Profit Factor** | **2.99** | 0.39 | 0.57 | 0.60 | 0.19 | 0.77 |
| **Last 5Y Return** | **+425.90%** (CAGR 40.1%) | +142.10% (CAGR 19.3%)| +140.88% (CAGR 19.1%)| +38.54% (CAGR 6.7%) | +125.52% (CAGR 17.6%)| +94.10% (CAGR 14.1%) |
| **5-Year Ending Equity** | **₹5,25,896.64** | ₹2,42,099.18 | ₹2,40,875.56 | ₹1,38,539.79 | ₹2,25,524.02 | ₹1,94,104.32 |
| **5-Year Max DD** | -29.53% | -26.19% | **-26.18%** | -33.61% | -32.49% | -25.23% |
| **5-Year Win Rate** | **43.8%** (288 trades) | 33.0% (94 trades) | 26.4% (110 trades) | 31.6% (215 trades) | 27.2% (81 trades) | 28.2% (110 trades) |
| **5-Year Profit Factor** | **2.82** | 2.12 | 1.53 | 1.25 | 1.58 | 1.60 |
| **5-Year Payout Ratio** | 3.30x | **6.63x** | 5.83x | 3.27x | 7.94x | 5.40x |
| **Average Holding Period** | 47.0 days | 25.5 weeks (~6 mos) | 21.3 weeks (~5 mos) | 11.4 weeks (~2.8 mos)| 26.3 weeks (~6.5 mos)| 21.0 weeks (~5 mos) |

---

#### 🔍 Quantitative Mechanics & Failure Modes of Weekly EMA Crossover:

1. **The Double-Lag Problem (Late Entry + Late Exit)**:
   - **Entry Lag**: A weekly 10 EMA requires roughly 10 weeks of data (~50 trading days), and 20 EMA requires 20 weeks (~100 trading days). When 10 EMA crosses above 20 EMA, the underlying stock has already been advancing for 6 to 12 weeks and is frequently **+30% to +60% above its breakout base**. You are buying near the peak of the primary wave.
   - **Exit Lag**: When the stock reverses into a distribution phase or correction, the price must plunge substantially and remain depressed for multiple weeks before the weekly 10 EMA crosses below the 20 EMA. Winners regularly surrender 20% to 35% of their accumulated profits before the death cross confirms.
2. **Brutal Whipsaws in Range-Bound / Rotational Regimes (2024–2026)**:
   - In consolidating or choppy market environments (such as 2024 to 2026), moving average crossovers produce catastrophic false breakouts:
     - 2026 YTD Win Rate plunged to **10.7%** (only 3 winners out of 28 trades) with a net return of **-6.59%**.
     - Last 2 Years produced a **-19.51% net loss** with a win rate of **27.1%** and a dismal Profit Factor of **0.39**.
3. **Monster Trend Exploitation in Strong Secular Bull Regimes (5-Year Horizon)**:
   - Despite low win rates (33.0%), the strategy achieved **+142.10%** over 5 years (CAGR +19.26%) turning ₹1.00L into ₹2.42 Lakhs.
   - This was driven entirely by an extraordinary **6.63x Payout Ratio** (Average Winner: +58.4% vs Average Loser: -8.8%). When a stock entered a monster secular multi-year bull run (e.g. HAL, Trent, BEL in 2021-2023), holding the position for 6 to 12 months generated massive compound gains.
4. **Why "Faster Exit" (Close < 20 EMA) Fails**:
   - Exiting on weekly Close < 20 EMA cut 5-year return from **+142.1% down to +38.54%** and increased trades from 94 to 215.
   - Normal, healthy trend pullbacks routinely test or dip slightly beneath the 20 EMA on weekly closes before resuming higher. Selling on every dip causes chronic churn and premature shakeouts of top winners.
5. **Why Baseline Daily 50D Donchian Crushes Weekly EMA Crossover**:
   - The Baseline generates **+425.90% vs +142.10%** across 5 years, **+79.42% vs -19.51%** over 2 years, and **+39.91% vs -6.59%** in 2026 YTD.
   - **Key Reason**: The Baseline enters at the exact initiation of the breakout (50-day Donchian High), protects downside immediately with an -8% stop loss and 20-day tenure cut, and locks in profits on mature winners via the two-tier profit lock (+25% gain & 20 EMA break) rather than waiting for a sluggish moving average death cross.

---

### 🔬 WEEKLY CCI + 200 EMA + SUPERTREND STRATEGY BENCHMARK & RESEARCH

A comprehensive multi-horizon research study was conducted across the Nifty 500 universe (capital ₹1,00,000, 10% allocation per slot, max 10 concurrent slots, max 3 stocks per sector, minimum stock price ₹100) investigating the user's **Weekly CCI + 200 EMA + Supertrend Strategy**:
- **Timeframe**: Weekly (resampled Friday close bars from daily candles).
- **Entry Condition**:
  1. Commodity Channel Index (CCI) crosses above -100 ($CCI[W] > -100$ and $CCI[W-1] \le -100$).
  2. Price above 200 EMA ($Close > EMA_{200}$ / 40-week equivalent).
- **Exit Dilemma & Research Investigation**:
  The user asked: *"exit when supertrend indicator show sell signal (sometimes supertrend is sell in when cci shows entry) or suggesst me a exit idea ."*
- **Execution Timing**: Signals generated at Friday close $W$, executed at Monday open $W+1$.

---

#### 🚨 The Quantitative Conflict: CCI > -100 vs. Supertrend Direction
- **Empirical Discovery**: When Weekly CCI crosses above -100, **71.5% of the time, the Weekly Supertrend is ALREADY in a SELL (-1) state**!
- **Root Cause**: CCI crossing above -100 is an *anticipatory oversold bounce* setup (the stock suffered a sharp prior drawdown that pushed CCI below -100 and flipped Supertrend to red/sell). As the price starts to tick up, CCI crosses above -100 while the price remains well beneath the upper Supertrend resistance band.
- **Consequence for Exit Rules**:
  1. If exiting naively when "Supertrend is SELL", the strategy immediately exits on the next candle (churning positions with 0% win rate).
  2. If using a **Latched Supertrend Flip** (waiting for Supertrend to first flip to BUY, then exiting on SELL), weak bounces that fail to reach the upper band remain open indefinitely, exposing capital to severe drawdowns unless protected by a hard stop loss.

---

#### 📊 4-Horizon Comparative Performance Matrix:

| Strategy Variant | 2026 YTD Return (DD) | Last 12M Return (DD) | Last 2Y Return (DD) | Last 5Y Return (DD) | 5Y Ending Equity | 5Y Profit Factor | 5Y Win Rate | 5Y Payout |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline: Daily 50D Donchian** | **+39.91%** (-11.7%) | **+49.84%** (-11.3%) | **+79.42%** (-12.8%) | **+425.90%** (-29.5%) | **₹5,25,896.64** | **2.82** | **43.8%** | **3.30x** |
| **Var 1: Raw Supertrend Flip (No Stop)** | +13.93% (-12.2%) | -5.75% (-12.1%) | -4.42% (-25.2%) | +176.52% (-29.3%) | ₹2,76,517.60 | 3.91 | 50.0% | 6.01x |
| **Var 2: Supertrend Flip + -8% Stop** | -5.81% (-10.8%) | -8.42% (-15.9%) | -18.64% (-19.2%) | +127.58% (-31.3%) | ₹2,27,576.15 | 2.03 | 26.8% | 9.53x |
| **Var 3: Supertrend Confluence (Buy Filter)**| -9.14% (-10.5%) | -9.93% (-12.6%) | -23.14% (-25.2%) | +84.79% (-34.8%) | ₹1,84,785.52 | 1.91 | 20.3% | 10.00x |
| **Var 4: CCI Mean Reversion Exit (+8% Stop)**| -5.20% (-8.7%) | -6.65% (-12.0%) | -9.67% (-15.6%) | +49.90% (-17.9%) | ₹1,49,897.78 | 1.32 | **52.3%** | 1.27x |
| **Var 5: Weekly Close < 20 EMA (+8% Stop)** | -10.66% (-12.6%) | -13.28% (-16.8%) | -17.44% (-21.5%) | +64.62% (-27.9%) | ₹1,64,621.72 | 1.51 | 29.3% | 4.99x |
| **Var 6: 2-Tier Profit Lock (+25% & 10 EMA)**| -11.43% (-12.6%) | -14.06% (-16.8%) | -16.48% (-19.7%) | +62.27% (-22.8%) | ₹162,271.60 | 1.51 | 30.7% | 3.93x |

---

#### 💡 Suggested Exit Ideas & Performance Insights:

1. **Why Pure Supertrend Exit Without Stop Loss Is Fragile**:
   - While Var 1 achieved +176.5% over 5 years (riding monster multi-year trends where Supertrend eventually flipped to BUY), it suffered net losses in 2024-2026 (-5.75% in 12M, -4.42% in 2Y). When a stock does not flip to BUY, it sits in the portfolio absorbing severe losses.
2. **Suggested Exit Idea A — CCI Mean Reversion Exhaustion (Var 4)**:
   - *Logic*: Since entry captures an oversold bounce ($CCI > -100$), exit when momentum becomes exhausted: Weekly CCI crosses above $+100$ and then drops below $+100$, or reaches $+150$.
   - *Outcome*: Produces the highest win rate (**52.3% over 5 years**) and lowest maximum drawdown (**-17.90%**), with average winner $+11.8\%$ and average loser $-9.3\%$.
3. **Suggested Exit Idea B — Supertrend Confluence (Var 3)**:
   - *Logic*: Eliminate the conflict by only entering when CCI crosses above -100 **AND Supertrend is already in BUY (+1)**.
   - *Outcome*: Generates massive asymmetric winners ($+98.5\%$ average gain), but win rate is low ($20.3\%$) because many breakouts already occurred before Supertrend confirmed.
4. **Conclusion vs. Baseline**:
   - The **Daily 50D Donchian Baseline (+425.90%, -29.5% DD, 2.82 Profit Factor)** significantly outperforms all Weekly CCI variations.
   - The Baseline enters at the exact structural pivot (50-day Donchian High), uses dynamic risk sizing ($1.25\%$ risk per trade), cuts stagnant dead money after 20 days, and locks in profits on mature winners at $+25\%$ gain via the 20 EMA rule.

---

### 🔬 DARVAS BOX & SCREENER.IN MOMENTUM STRATEGY RESEARCH & BENCHMARK

A comprehensive multi-horizon study was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 concurrent slots, max 3 stocks per sector) investigating the **Darvas Box Momentum Strategy** and the modern **Screener.in Momentum Query**:
- **Screener.in Conditions Tested**:
  1. *Within 10% of 52-Week High*: `(High_52W - Close) / High_52W * 100 < 10`
  2. *At Least 2x from 52-Week Low*: `Close >= 2.0 * Low_52W` (100% gain from 52W low)
  3. *Liquidity Filter*: Daily Volume $\ge 1,00,000$ shares & 20D Volume SMA $\ge 1,00,000$
  4. *Volume Expansion*: Breakout bar $\text{RVOL} \ge 1.5$
  5. *Box Formations*:
     - **Classic Nicolas Darvas State Machine (3-Day Pivot)**: Requires high to hold for 3 consecutive days without violation to lock Box Top, followed by pullback low holding 3 days to lock Box Bottom. Dynamic step-ladder trailing stop tracks each newly established higher box bottom.
     - **20-Day Donchian Box**: 20-day high breakout + 20-day low box bottom stop.
     - **Tight 20-Day Box**: Same + Box Tightness $\le 15\%$ (volatility contraction).

---

#### 📊 4-Horizon Comparative Performance Matrix:

| Strategy Variant | 2026 YTD Return (DD) | Last 12M Return (DD) | Last 2Y Return (DD) | Last 5Y Return (DD) | 5Y Ending Equity | 5Y Profit Factor | 5Y Win Rate | 5Y Sharpe |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline (50D Donchian, 2-Tier Exit)** | +34.67% (-12.4%) | +50.78% (-12.6%) | +74.88% (-12.8%) | **+424.27%** (-29.7%) | **₹5,24,265.49** | **2.88** | **46.8%** | **1.33** |
| **Baseline + 2x 52W Low Filter** | +27.73% (-10.7%) | +35.36% (-15.6%) | **+91.80%** (-13.8%) | +326.09% (-22.3%) | ₹4,26,085.80 | 2.61 | 39.6% | 1.18 |
| **Classic Darvas State Machine (3-Day Pivot)** | **+36.21%** (**-6.3%**) | +34.49% (-14.0%) | +69.80% (-13.8%) | +405.13% (**-17.2%**) | ₹5,05,134.67 | 2.29 | 44.1% | **1.33** |
| **Golden Hybrid + Adaptive 1.5x Low** | +32.72% (-9.2%) | **+57.21%** (**-9.7%**) | +60.97% (-14.4%) | +274.89% (-28.0%) | ₹3,74,892.35 | 2.17 | 38.0% | 1.08 |
| **Golden Hybrid (50D + Close $\ge 70\%$ + Darvas)**| +26.51% (-11.7%) | +29.79% (-12.9%) | +38.95% (-16.3%) | +192.90% (-30.2%) | ₹2,92,900.55 | 1.88 | 39.0% | 0.85 |
| **Screener 20D Box (RVOL $\ge 1.5$, 2x Low)** | +35.25% (-11.0%) | +23.20% (-15.7%) | +56.80% (-14.9%) | +177.56% (-26.6%) | ₹2,77,562.47 | 1.85 | 34.4% | 0.76 |
| **Screener 20D Box Tight ($\le 15\%$)** | +12.41% (-7.1%) | +9.68% (-12.9%) | +13.31% (-12.8%) | +107.04% (-18.9%) | ₹2,07,044.23 | 2.06 | 42.0% | 0.61 |

---

#### 💡 Key Quantitative Findings & Practical Insights:

1. **Classic Darvas 3-Day State Machine Slashes Drawdown by Nearly Half (-17.2% vs -29.7%)**:
   - The true **Nicolas Darvas 3-day pivot box** with a **step-ladder trailing stop** is a remarkably robust risk-managed model. Over 5 years, it compounded ₹1 Lakh to **₹5.05 Lakhs (+405.13%, 38.3% CAGR)** while containing maximum portfolio drawdown to just **-17.19%** (compared to -29.67% in the Baseline).
   - In 2026 YTD, the Classic Darvas model produced **+36.21% return with only -6.31% max drawdown**, delivering an exceptional Sharpe ratio (1.63).
   - *Why it works*: When a stock ascends into higher boxes, the step-ladder trailing stop progressively locks in profit at the floor of each new box without waiting for a broad moving average breakdown.
2. **Golden Hybrid + Adaptive 1.5x Low Outperforms in 12M Horizon (+57.21% vs +50.78%)**:
   - In the Last 12 Months, combining the 50D breakout with candle closing strength ($\ge 70\%$ of bar range) and requiring stocks to be $\ge 50\%$ above their 52W low achieved the highest 12M return (**+57.21%, CAGR 57.5%**) with single-digit drawdown (**-9.74%**) and a peak Sharpe of **1.95**.
   - However, over 5 years, Classic Darvas remains superior (+405.1% vs +274.9%) because Darvas's 3-day pivot rules inherently select consolidations with balanced risk/reward floors.
3. **Impact of the Screener.in "2x Above 52-Week Low" Filter (`Close >= 2.0 * Low_52W`)**:
   - In the **Last 2 Years**, adding the 2x 52W Low rule dramatically boosted returns from **+74.88% to +91.80%** and Profit Factor from 2.95 to 3.47, because it strictly concentrated capital in the fiercest momentum market leaders (stocks that had already doubled).
   - Over **5 Years**, however, requiring a stock to have already doubled from its 52W low resulted in a mild opportunity drag (+326.1% vs +424.3%), because it prevents entering monster turnarounds early in new bull cycles when stocks have only risen 40%–60% from cyclical bottoms.
4. **20-Day Box vs. 50-Day Donchian Breakout**:
   - A naive 20-day breakout generates higher whipsaws in Indian mid-caps (win rate drops to 34%–37%), whereas the 50-day breakout provides the necessary structural filter to confirm genuine Stage 2 accumulation.
5. **Tight Base Filter ($\le 15\%$) Destroys Compounding**:
   - Forcing boxes to be $\le 15\%$ tight reduced 5-year returns from +424% down to +107%, confirming our earlier Volatility Contraction research: top momentum leaders often exhibit wider consolidation bases before exploding to new highs.

---

### 🔬 CAPITAL INFUSION & SIP COMPOUNDING RESEARCH (REAL-LIFE CAPITAL ADDITIONS)

A rigorous multi-horizon backtest was conducted (`scripts/test_capital_infusion.py`) across the Nifty 500 universe simulating real-life capital additions over time. The engine dynamically scales position sizing ($\text{Risk Budget} = \text{Total Equity} \times 1.25\%$, $\text{Max Position} = \text{Total Equity} \times 15\%$) as cash is infused.

Tested Models (Starting Capital: ₹1,00,000):
1. **Baseline (Zero Injections)**: Pure trading profits compound without any added capital.
2. **Monthly SIP (+₹10,000/month)**: Adding ₹10,000 on the 1st trading day of each month.
3. **Monthly SIP (+₹20,000/month)**: Adding ₹20,000 on the 1st trading day of each month.
4. **Quarterly Infusion (+₹50,000/quarter)**: Adding ₹50,000 at the start of each quarter.

#### 📊 4-Horizon Comparative Performance & Capital Scaling Matrix:

| Horizon | Model | Initial | Total Invested | Ending Equity | Net Profit | Net Return | XIRR | Max DD | Profit Factor | Win Rate | Trades | Avg Trade Size |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026 YTD** | Baseline (Zero Injections) | ₹1,00,000 | ₹1,00,000 | **₹1,41,745.68** | +₹41,745.68 | +41.75% | 50.44% | -8.82% | 3.47 | 43.9% | 57 | ₹10,327 |
| **2026 YTD** | Monthly SIP (+₹10k/mo) | ₹1,00,000 | ₹2,00,000 | **₹2,63,108.89** | +₹63,108.89 | +31.55% | **53.28%** | **-8.42%** | 3.70 | 51.0% | 51 | ₹17,669 |
| **2026 YTD** | Monthly SIP (+₹20k/mo) | ₹1,00,000 | ₹3,00,000 | **₹3,95,568.56** | +₹95,568.56 | +31.86% | **62.53%** | **-8.33%** | **4.51** | **52.8%** | 53 | ₹22,274 |
| **2026 YTD** | Quarterly (+₹50k/qtr) | ₹1,00,000 | ₹2,50,000 | **₹3,26,009.37** | +₹76,009.37 | +30.40% | 58.62% | -8.20% | 4.49 | 47.2% | 53 | ₹17,989 |
| **Last 12M** | Baseline (Zero Injections) | ₹1,00,000 | ₹1,00,000 | **₹1,50,324.18** | +₹50,324.18 | +50.32% | 50.53% | -10.06% | 3.46 | 48.5% | 68 | ₹10,803 |
| **Last 12M** | Monthly SIP (+₹10k/mo) | ₹1,00,000 | ₹2,20,000 | **₹2,96,941.37** | +₹76,941.37 | +34.97% | 50.25% | **-8.74%** | 3.51 | 52.4% | 63 | ₹18,969 |
| **Last 12M** | Monthly SIP (+₹20k/mo) | ₹1,00,000 | ₹3,40,000 | **₹4,65,586.77** | +₹1,25,586.77| +36.94% | **61.18%** | **-8.91%** | **4.08** | 50.0% | 64 | ₹25,108 |
| **Last 12M** | Quarterly (+₹50k/qtr) | ₹1,00,000 | ₹3,00,000 | **₹3,97,066.41** | +₹97,066.41 | +32.36% | 51.40% | -8.85% | 3.39 | 50.0% | 66 | ₹22,417 |
| **Last 2Y** | Baseline (Zero Injections) | ₹1,00,000 | ₹1,00,000 | **₹1,81,527.39** | +₹81,527.39 | +81.53% | 34.87% | -11.18% | 3.66 | 51.4% | 109 | ₹12,424 |
| **Last 2Y** | Monthly SIP (+₹10k/mo) | ₹1,00,000 | ₹3,40,000 | **₹5,62,709.56** | +₹2,22,709.56| +65.50% | **44.93%** | **-8.88%** | 3.37 | 50.9% | 112 | ₹30,556 |
| **Last 2Y** | Monthly SIP (+₹20k/mo) | ₹1,00,000 | ₹5,80,000 | **₹9,14,983.29** | +₹3,34,983.29| +57.76% | **44.82%** | **-9.01%** | 3.39 | 51.4% | 109 | ₹47,264 |
| **Last 2Y** | Quarterly (+₹50k/qtr) | ₹1,00,000 | ₹5,00,000 | **₹7,67,736.31** | +₹2,67,736.31| +53.55% | 40.73% | -10.17% | 3.05 | 50.5% | 109 | ₹39,959 |
| **Last 5Y** | Baseline (Zero Injections) | ₹1,00,000 | ₹1,00,000 | **₹6,61,631.63** | +₹5,61,631.63| +561.63% | 45.96% | -29.53% | 3.80 | 49.3% | 288 | ₹26,024 |
| **Last 5Y** | Monthly SIP (+₹10k/mo) | ₹1,00,000 | ₹7,00,000 | **₹23,38,351.36**| +₹16,38,351.36| +234.05% | **44.40%** | **-13.18%** | 3.48 | 45.9% | 292 | ₹80,936 |
| **Last 5Y** | Monthly SIP (+₹20k/mo) | ₹1,00,000 | ₹13,00,000 | **₹39,90,426.34**| +₹26,90,426.34| +206.96% | **43.79%** | **-12.85%** | 3.46 | 46.4% | 295 | ₹1,35,295 |
| **Last 5Y** | Quarterly (+₹50k/qtr) | ₹1,00,000 | ₹1,10,000 | **₹34,54,566.14**| +₹23,54,566.14| +214.05% | 44.13% | -24.72% | 3.41 | 44.2% | 301 | ₹1,13,250 |

#### 💡 Key Quantitative Findings & Practical Insights:

1. **Drawdown Dampening (The Biggest Psychological Advantage)**:
   - In the Baseline 5-year run, the maximum portfolio drawdown was **-29.53%**.
   - With a systematic **Monthly SIP (+₹10k/mo)**, the maximum drawdown dropped by more than half to **-13.18%** (and **-12.85%** for +₹20k/mo).
   - *Why*: Adding cash periodically provides regular dry powder during market consolidations, cushioning portfolio equity drops and allowing the system to enter the earliest leaders of the subsequent market recovery.
2. **Massive Absolute Wealth Generation at Consistent ~44% XIRR**:
   - Starting with ₹1 Lakh and adding ₹10,000/month (total principal ₹7.0 Lakhs) compounded to **₹23.38 Lakhs (+₹16.38 Lakhs net profit)** over 5 years.
   - Adding ₹20,000/month (total principal ₹13.0 Lakhs) compounded to **₹39.90 Lakhs (+₹26.90 Lakhs net profit)**.
   - The money-weighted annualized return (**XIRR: ~44%–45%**) remains remarkably rock-solid regardless of the amount added.
3. **Seamless Dynamic Position Sizing Without Overtrading**:
   - Total trade count remained nearly constant (~288 to 295 trades over 5 years). The system does **not** churn or overtrade when extra capital is injected; it simply sizes up each trade proportionately.
   - Average trade size naturally grew from **₹10,000** at launch to **₹30,000–₹47,000** by Year 2, and reached **₹80,000–₹1,35,000** by Year 5.

---

### 🔬 FIXED SIZING VS DYNAMIC PROFIT COMPOUNDING BENCHMARK

A comparative multi-horizon backtest (`scripts/test_fixed_vs_dynamic.py`) was conducted across the Nifty 500 universe with starting capital ₹1,00,000 (0 external additions) comparing:
1. **Fixed Sizing (Profits Kept Idle / Withdrawn)**: Every trade receives a flat ₹10,000 (10 slots). Profits accumulate in cash but are **never** reinvested into larger trade sizes.
2. **Fixed Risk on Initial ₹1L**: Trade risk is pegged to the initial ₹1L (₹1,250 risk / max ₹15k per trade). Profits are not compounded into larger lot sizes.
3. **Dynamic Compounding (Current System Baseline)**: Reinvests 100% of realized profits. Sizing continuously adapts to current total equity ($\text{Risk Budget} = \text{Equity} \times 1.25\%$, $\text{Max Allocation} = \text{Equity} \times 15\%$).

#### 📊 4-Horizon Comparative Matrix:

| Horizon | Model | Ending Equity | Net Profit | Total Return | CAGR | Max DD | Profit Factor | Win Rate | Trades |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026 YTD** | Fixed Sizing (Flat ₹10k/stock) | ₹1,31,454.74 | +₹31,454.74 | +31.45% | 38.42% | **-8.69%** | 2.46 | 45.7% | 46 |
| **2026 YTD** | Fixed Risk on Initial ₹1L | ₹1,45,335.60 | +₹45,335.60 | +45.34% | 55.96% | -9.28% | **3.55** | 43.3% | 30 |
| **2026 YTD** | **Dynamic Compounding (Reinvest All)** | ₹1,37,459.11 | +₹37,459.11 | +37.46% | 45.96% | -8.80% | 2.84 | 46.5% | 43 |
| **Last 12M** | Fixed Sizing (Flat ₹10k/stock) | ₹1,42,702.61 | +₹42,702.61 | +42.70% | 43.32% | **-8.64%** | **3.29** | 49.1% | 55 |
| **Last 12M** | Fixed Risk on Initial ₹1L | ₹1,39,659.32 | +₹39,659.32 | +39.66% | 40.22% | -10.51% | 2.47 | 40.9% | 44 |
| **Last 12M** | **Dynamic Compounding (Reinvest All)** | ₹1,40,543.23 | +₹40,543.23 | +40.54% | 41.12% | -10.08% | 2.59 | 36.8% | 57 |
| **Last 2Y** | Fixed Sizing (Flat ₹10k/stock) | ₹1,46,874.35 | +₹46,874.35 | +46.87% | 21.62% | -12.94% | 2.25 | 45.5% | 112 |
| **Last 2Y** | Fixed Risk on Initial ₹1L | ₹1,87,391.30 | +₹87,391.30 | +87.39% | 37.67% | **-11.93%** | **3.15** | 48.3% | 89 |
| **Last 2Y** | **Dynamic Compounding (Reinvest All)** | ₹1,79,864.55 | +₹79,864.55 | +79.86% | 34.83% | -12.81% | 3.01 | 46.2% | 104 |
| **Last 5Y** | Fixed Sizing (Flat ₹10k/stock) | ₹2,44,614.63 | +₹1,44,614.63| +144.61% | 19.92% | **-28.68%** | 2.36 | 44.1% | 306 |
| **Last 5Y** | Fixed Risk on Initial ₹1L | ₹3,04,570.20 | +₹2,04,570.20| +204.57% | 25.38% | -29.49% | 2.49 | 43.4% | 258 |
| **Last 5Y** | **Dynamic Compounding (Reinvest All)** | **₹5,67,659.24** | **+₹4,67,659.24**| **+467.66%** | **42.27%** | -29.53% | **3.09** | 44.6% | 289 |

#### 💡 Key Takeaways:
1. **Geometric Compounding Generates +₹3.23 Lakhs More Wealth Over 5 Years**:
   - In Fixed Sizing, leaving profits idle produced **₹2.45 Lakhs** (+₹1.45L profit).
   - Dynamic Compounding produced **₹5.68 Lakhs** (+₹4.68L profit) — a **+223% higher net gain**!
   - As portfolio equity doubles from ₹1.0L to ₹2.0L, the engine automatically doubles the position allocation (from ₹15k to ₹30k per stock). When a secular winner surges +40% or +60%, the rupee gains are twice as large.
2. **Short-Term (1-Year) Parity**:
   - Over 12 to 18 months, the difference between fixed and dynamic sizing is minor (₹1.42L vs ₹1.40L) because total equity has not yet doubled.
   - The exponential explosion of dynamic compounding becomes dominant after Month 24, when the base equity expands significantly.
3. **Conclusion**:
   - The engine's active configuration (`sizing_mode: "risk_pct"`) is mathematically optimal for multi-year compounding.

---

### 🔬 RSI(14) ON EMA < 10 GAP-UP STRATEGY BENCHMARK & RESEARCH

A multi-horizon backtest (`scripts/test_rsi_ema_gap_up.py`) was conducted across the Nifty 500 universe (capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 concurrent slots, max 3 per sector, `Prev Close >= ₹100`, `20D Avg Vol >= 50,000`) testing the **RSI-on-EMA Gap-Up Strategy**:
- **Indicator**: `RSI(14)` applied to `EMA(close)` (TradingView `Source: EMA`) instead of raw `Close`. Tested with both `EMA(21)` and TradingView default `EMA(9)`.
- **Entry (Zero Lookahead)**: Prior day `RSI_on_EMA[t-1] < 10.0` AND Day `t` opens on a gap up (`Open[t] > Close[t-1]`). Buy at `Open[t]`.
- **Stop Loss**: Gap distance `Open[t] - Close[t-1]` $\implies$ `Stop Price = Close[t-1]` (previous day's close / gap-fill level), checked intraday (`Low <= Stop`) and on gap-downs (`Open <= Stop`).
- **21 EMA Exit Modes**:
  - **Unlatched (Raw)**: Exit at next day's open whenever `Close < 21 EMA`.
  - **Latched (Reclaim-then-Break)**: Hold with the Gap-Fill Stop (`Prev Close`) until price closes $\ge 21\text{ EMA}$, then exit at next day's open when `Close < 21 EMA`.

#### 📊 4-Horizon Comparative Performance Matrix:

| Strategy Variant | 2026 YTD Return (DD) | Last 12M Return (DD) | Last 2Y Return (DD) | Last 5Y Return (DD) | 5Y Ending Equity | 5Y PF | 5Y Win Rate | 5Y Avg Hold |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline (50D Donchian, 2-Tier)** | **+37.46%** (**-8.8%**) | **+40.54%** (**-10.1%**) | **+79.86%** (**-12.8%**) | **+467.66%** (-29.5%) | **₹5,67,659.24** | **3.09** | **44.6%** (289T) | 47.0d |
| **Var 1: Raw EMA21 (Gap>0, Unlatched)** | +6.06% (-13.2%) | -8.07% (-22.1%) | -29.21% (-43.3%) | -54.49% (-60.4%) | ₹45,506.22 | 0.83 | 19.4% (4,993T) | 1.8d |
| **Var 2: Raw EMA9 (Gap>0, Unlatched)** | -16.73% (-20.3%) | -24.22% (-27.5%) | -30.31% (-38.3%) | -38.98% (-45.3%) | ₹61,021.76 | 0.88 | 19.8% (5,280T) | 0.8d |
| **Var 3: EMA21 (Gap>0, Latched 21EMA)** | +6.49% (-15.6%) | -3.68% (-21.8%) | -19.42% (-34.8%) | -33.24% (-45.6%) | ₹66,756.19 | 0.86 | 12.4% (3,286T) | 3.5d |
| **Var 4: EMA21 (Gap>=2%, Latched)** | +20.68% (-14.5%) | +14.92% (-14.6%) | +15.92% (-18.4%) | +48.40% (-26.7%) | ₹1,48,402.28 | 1.15 | 26.5% (756T) | 8.7d |
| **Var 5: EMA21 (Gap>=2%, Latched+Reg)** | +4.75% (-9.3%) | +1.08% (-12.9%) | +22.93% (-13.9%) | +50.53% (**-14.0%**) | ₹1,50,528.61 | 1.41 | 30.2% (311T) | 10.7d |
| **Var 6: EMA9 (Gap>=2%, Latched)** | -2.12% (-13.9%) | -4.27% (-15.6%) | -1.59% (-16.9%) | +20.72% (-24.7%) | ₹1,20,724.79 | 1.10 | 25.3% (462T) | 7.7d |

#### 🔍 Key Quantitative Findings & Failure Mechanics:

1. **The Oversold-Exit Paradox (`83%`–`96%` Still Below 21 EMA on Entry Day)**:
   - Because `RSI(14)` on an EMA only drops below `10` during a sustained multi-week downtrend, **83.0%** of `EMA(21)` gap-ups (and **95.8%** of `EMA(9)` gap-ups) STILL close **below the 21 EMA** on the gap-up day itself.
   - An unlatched `Close < 21 EMA` exit therefore liquidates almost every survivor on Day 1–2 (`0.8d`–`1.8d` average hold), generating ~5,000+ churn trades and `-38.98%` to `-54.49%` 5-year losses.
2. **The Micro-Gap Stop-Out Trap (Median Gap is Only `+0.49%`)**:
   - Counting any `Open > Prev Close` includes tiny `+0.1%` to `+0.5%` gaps whose Gap-Fill Stop (`Prev Close`) sits inside normal opening noise. Across 5 years, **73%–84%** of un-filtered trades get stopped out intraday at `Low <= Prev Close`.
3. **Filtering for Meaningful Gaps (`Gap >= 2%`) + Latched 21 EMA Turns the Strategy Profitable**:
   - Requiring `Gap >= +2.0%` + Latched 21 EMA (`Var 4`) flips 5-year performance from `-54.49%` to **+48.40%** (`+20.68%` in 2026 YTD, `PF 1.15`, `26.5%` win rate, `3.16x` payout ratio).
   - Adding the Nifty 500 `>= 50 EMA` Regime Filter (`Var 5`) improves 5-year return slightly to **+50.53%**, cuts 5-year Max Drawdown nearly in half from **-26.66% to -13.97%**, and raises Profit Factor to **1.41** (`30.2%` win rate), though it still trails the **Baseline 50D Donchian (+467.66%, PF 3.09)** by a wide margin because buying beaten-down downtrend bounces has lower follow-through than buying Stage-2 breakouts near 52-week highs.

---

### 🔬 VOLATILITY CONTRACTION PATTERN (VCP) BENCHMARK & RESEARCH

A multi-horizon backtest (`scripts/test_vcp.py`) was conducted across the Nifty 500 universe (496 cached stocks, capital ₹1,00,000, 1.25% risk/trade, max 15% allocation cap, max 10 concurrent slots, max 3 per sector, `Close >= ₹100`, `20D Avg Vol >= 50,000`, Nifty 500 `>= 50 EMA` regime filter, Day T close signal $\to$ Day T+1 open execution):
- **Prior Uptrend**: Cross-sectional Relative Strength Rank $\ge 70$ across Nifty 500 + Stage 2 (`Close > 50 EMA > 200 SMA`).
- **The Base**: 3+ weeks consolidation (`20D` or `30D` window), base depth $\le 35\%$.
- **Contractions**: 2nd half `ATR%` $\le 0.9 \times$ 1st half `ATR%`.
- **Volume Dry-Up**: 2nd half avg volume $\le 0.9 \times$ 1st half avg volume.
- **Breakout**: Fresh close above base pivot (`Close[t] > Pivot` and `Close[t-1] <= Pivot`).

| Horizon | Baseline (50D Donchian) | VCP-20D (2-Tier Exit) | VCP-20D Strict (RVOL$\ge$1.2 + Range + UpVol) | VCP-30D (2-Tier Exit) | VCP-20D (20 EMA Trail) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2026 YTD** | **+35.55%** (-8.23% DD, PF 2.39) | -1.53% (-12.79% DD, PF 0.94, 54T) | +2.21% (PF 1.14, 40.9% WR, 44T) | **+33.45%** (**PF 3.78**) | -3.06% (-9.40% DD) |
| **Last 12 Months** | **+51.68%** (-8.35% DD, PF 3.22) | +5.16% (-8.46% DD, PF 1.17, 66T) | +9.04% (PF 1.48, 40.4% WR, 52T) | **+41.79%** (**PF 3.69**) | -2.45% (-11.23% DD) |
| **Last 2 Years** | **+87.65%** (-9.39% DD, PF 2.88) | -6.76% (-15.69% DD, PF 0.86, 107T) | +6.73% (PF 1.17, 40.2% WR, 92T) | **+52.31%** (PF 2.51) | +5.16% (-14.57% DD) |
| **Last 5 Years** | **+418.30%** (-29.72% DD, PF 2.79) | +99.35% (-23.17% DD, PF 1.43, 303T) | +21.14% (PF 1.13, 36.2% WR, 287T) | **+138.09%** (PF 1.86) | +10.53% (-40.04% DD) |

#### 🔍 Key Takeaways:
1. **Base Duration Matters Enormously (`30D` vs `20D`)**: Extending the VCP base from 20 trading days (4 weeks) to 30 trading days (6 weeks) jumped returns from **-1.53% to +33.45% (YTD)** and **+5.16% to +41.79% (12M)** with an exceptional **3.78 / 3.69 Profit Factor**. Short 20-day bases catch minor pullbacks rather than true institutional consolidations.
2. **2-Tier Exit Outperforms Pure 20 EMA Trail**: Using the repository's 2-tier exit + 20-day tenure cut outperformed a pure `Close < 20 EMA` trail across every horizon (`+99.35%` vs `+10.53%` over 5 years).
3. **Baseline 50D Donchian Remains Superior**: While `VCP-30D` achieves higher Profit Factor in 2026 YTD (`3.78` vs `2.39`) and Last 12M (`3.69` vs `3.22`), the Baseline 50D Donchian Engine delivers higher total returns across all 4 horizons (`+418.30%` vs `+138.09%` over 5 years) because requiring simultaneous 2nd-half ATR% and volume contraction filters out many high-momentum Stage-2 leaders that break out on expanding volatility.

---

### 🔬 200 EMA + RSI(30) CROSSOVER STRATEGY BENCHMARK & RESEARCH

A multi-horizon backtest (`scripts/test_ema200_rsi30.py`) was conducted across the Nifty 500 universe (496 cached stocks, capital ₹1,00,000, max 10 concurrent slots, max 3 per sector, `Close >= ₹100`, `20D Avg Vol >= 50,000`, Day T close signal $\to$ Day T+1 open execution):
- **Entry Rule**: `Close > 200 EMA` AND `RSI` crosses above `30` (`RSI[t-2] <= 30` and `RSI[t-1] > 30`).
- **Exit Rule**: `RSI` crosses below `30` (either unlatched, or latched so `RSI` must first rise above `50` before the `30` cross-below exit arms) OR `Close < 200 EMA`.

| Strategy Variant | 2026 YTD Return (DD) | Last 12M Return (DD) | Last 2Y Return (DD) | Last 5Y Return (DD) | 5Y Ending Equity | 5Y PF | 5Y Win Rate | 5Y Avg Hold |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline (50D Donchian)** | **+35.55%** (**-8.23%**) | **+51.68%** (**-8.35%**) | **+87.65%** (**-9.39%**) | **+418.30%** (-29.72%) | **₹5,18,302.11** | **2.79** | **44.6%** (298T) | 46.2d |
| **Var 1: Unlatched (`RSI14 >30`)** | +17.19% (-8.28%) | +8.74% (-11.25%) | -5.62% (-25.69%) | +87.58% (-30.01%) | ₹1,87,580.12 | 1.36 | 18.7% (198T) | 62.6d |
| **Var 2: Latched `50->30` (Exact)** | +17.48% (-8.24%) | +8.75% (-11.26%) | -3.96% (-25.55%) | +42.41% (-43.83%) | ₹1,42,409.73 | 1.08 | 16.6% (199T) | 60.4d |
| **Var 3: Latched `50->30` + 15% -8% SL** | +29.19% (-9.89%) | -1.21% (-12.09%) | +0.17% (-19.91%) | +42.15% (-30.39%) | ₹1,42,152.54 | 1.17 | 18.6% (204T) | 53.1d |
| **Var 4: Latched `50->30` + Regime** | +5.11% (-3.83%) | -0.90% (-8.78%) | -4.88% (-13.94%) | +50.92% (**-25.36%**) | ₹1,50,917.05 | 1.53 | 19.8% (96T) | 75.2d |
| **Var 5: `RSI2` Latched `50->30`** | +23.37% (-15.09%) | +18.78% (-17.42%) | +44.05% (-19.93%) | +129.08% (-30.02%) | ₹2,29,082.73 | 1.24 | 41.9% (1,479T) | 11.3d |

#### 🔍 Key Takeaways:
1. **Effect of `50 -> 30` Latch on `RSI(14)`**:
   - Slightly improves 2026 YTD (`+17.48%` vs `+17.19%`), 12M (`+8.75%` vs `+8.74%`), and 2Y (`-3.96%` vs `-5.62%`), but hurts 5Y (`+42.41%` vs `+87.58%`, Max DD `-43.83%` vs `-30.01%`) because failed bounces that never reach RSI 50 are forced to hold until `Close < 200 EMA` (`84.9%` of exits vs `58.1%` unlatched).
2. **Effect of `50 -> 30` Latch on `RSI(2)`**:
   - Transforms `RSI(2)` from negative/flat in recent horizons (`-3.16%` YTD, `-3.48%` 12M, `+0.54%` 2Y) to **+23.37% (YTD)**, **+18.78% (12M)**, **+44.05% (2Y)**, and **+129.08% (5Y)** by giving short-term mean-reversion bounces room to reach `RSI(2) > 50` before arming the exit.
3. **Significantly Trails Baseline 50D Donchian**:
   - Across all 4 horizons, all variants trail the Baseline 50D Donchian Engine (`+418.30%` 5Y, `PF 2.79`, `44.6%` WR).
4. **Volume Confirmation (`RVOL >= 1.2x / 1.5x`)**:
   - On `RSI(14)` Latched `50->30`, adding `RVOL >= 1.2x` cuts 5Y Max Drawdown sharply from **-43.83% to -28.12%** and improves 5Y Win Rate (`16.6%` $\to$ `21.1%`) and Profit Factor (`1.08` $\to$ `1.32`), though total returns drop slightly (`+39.11%` vs `+42.41%` over 5Y; `+6.78%` vs `+17.48%` YTD) due to fewer entries (`133` vs `199` trades over 5Y).
   - On `RSI(2)` Latched `50->30`, `RVOL >= 1.2x` cuts 5Y Max DD (`-30.02%` $\to$ `-24.22%`) and edges 5Y return up (`+129.08%` $\to$ `+130.26%`), but hurts 2026 YTD (`+23.37%` $\to$ `-2.05%`) and 12M (`+18.78%` $\to$ `-0.35%`).










