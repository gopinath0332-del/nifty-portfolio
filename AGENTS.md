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
   - If changes affect indicators, portfolio management, or configuration, add or update corresponding unit tests in `tests/test_strategy.py`.
4. **PORTFOLIO CAPITAL BASELINE:**
   - The active baseline capital is **₹1,00,000 INR** (`total_capital: 100000.0` in `config/settings.yaml`).

---

### 📈 CORE STRATEGY SPECIFICATION (OPTIMAL PARAMETERS)

The system runs an optimized **Turtle System 2** trend-following model with strict risk management:

| Component | Rule / Parameter | Reason & Impact |
| :--- | :--- | :--- |
| **Breakout Entry** | **50-Day Donchian High** (`entry_len: 50`) | Captures primary stage-2 trend breakouts before stock is overextended. |
| **52-Week High Proximity** | **Within 10% of 52W High** (`within_52w_high_pct: 10.0`) | Ensures the stock is in a secular multi-quarter bull run (no deep pullbacks). |
| **Stage 2 Trend Filter** | **$Price > 50\text{ EMA} > 200\text{ SMA}$** (`stage_2_trend_enabled: true`) | Eliminates counter-trend dead-cat bounces in declining secular bear stocks. |
| **Minimum Stock Price** | **$Price \ge ₹100$** (`min_stock_price: 100.0`) | Eliminates low-liquidity micro-caps and erratic sub-₹100 penny stocks. |
| **Volume Liquidity** | **20-Day Avg Volume $\ge 50,000$** shares | Ensures institutional liquidity for zero-slippage market execution. |
| **Ranking Score** | **$\text{Breakout } \% \times \text{RVOL}$** | Breaks ties by prioritizing the strongest price momentum backed by volume. |
| **Market Regime Filter** | **Nifty 500 Index $\ge 50\text{ EMA}$** | Prevents opening new long positions when the broad market is in a downtrend. |
| **Profit-Lock Exit (Tier 1)**| **Unrealized Gain $\ge +25\%$ & Close $< 20\text{ EMA}$** (`profit_lock_threshold_pct: 25.0`) | Locks in profits on mature winners at trend exhaustion rather than round-tripping gains. |
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
7. **Inspect & Follow Logs on Raspberry Pi:**
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

---

### 🪵 PRODUCTION LOGGING & ERROR DEBUGGING ON RASPBERRY PI

The engine incorporates a resilient multi-target logging architecture (`src/logger.py`) specifically engineered for headless 24/7 Raspberry Pi production environments:

1. **Dual Rotating File Handlers (MicroSD Wear & Space Protection)**:
   - `logs/daily_scan.log`: Complete audit trail of daily scanner runs, Kite exchange synchronization, candidate scores, and portfolio rebalances. Rotates at **10 MB** with **5 backup generations** (`daily_scan.log.1` ... `.5`), guaranteeing that log files never exceed 50 MB or exhaust the Pi's MicroSD card storage.
   - `logs/errors.log`: Dedicated error sink capturing only `WARNING`, `ERROR`, and `CRITICAL` entries with exact timestamps, module names, function names, line numbers, and full Python tracebacks. Rotates at **5 MB** with **5 backups**.
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
2. **Fixed Portfolio Budget Isolation & Sizing (₹1,00,000 Baseline):**
   - **Strategy Cash Isolation:** Sizing and available cash are strictly governed by the dedicated strategy budget (`total_capital: 100000.0` in `config/settings.yaml`), completely isolated from Zerodha's overall account cash.
   - **No Account Balance Contamination:** External funds in the user's Zerodha account (e.g. ₹5,00,000 or ₹10,00,000) are NEVER used to size positions. `kite.margins("equity")` is logged purely for diagnostics.
   - **Automatic Scaling:** If the user wishes to increase the portfolio value in the future, simply update `total_capital` in `config/settings.yaml` (e.g. `200000.0`). Available cash and suggested lot counts scale proportionately without code changes.
   - **Cash Reconciliation:** Strategy cash is dynamically maintained as: $\text{Cash} = \max(0, \text{Total Capital} + \text{Realized P&L} - \text{Total Invested})$.
3. **Exchange Synchronization:**
   - Both `status.sh` and `run_daily_scan.py` automatically call `PortfolioManager.sync_with_exchange(kite)` to reconcile strategy state with real account Demat holdings, eliminating stale or dummy local JSON values.
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







