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
| **Channel Exit** | **20-Day Donchian Low** (`exit_len: 20`) | Trailing exit that lets multi-bagger runners compound while protecting profits. |
| **Hard Loss Stop** | **-8.0% Stop Loss** (`max_loss_stop_pct: 8.0`) | Caps maximum loss per trade if a false breakout reverses immediately. |
| **Position Sizing** | **Dynamic Risk-Based (1.25% Risk / Trade)** | Position size adapts dynamically: $\text{Qty} = \frac{\text{Equity} \times 1.25\%}{\text{Open} - \text{Stop}}$. |
| **Position Allocation Cap**| **Max 15% Capital per Stock** (`max_position_size_pct: 15.0`) | Prevents over-concentration in any single stock. |
| **Portfolio Capacity** | **Max 10 Concurrent Positions** (`max_positions: 10`) | Maintains optimal portfolio diversification and cash utilization. |
| **Sector Diversification** | **Max 2 Stocks per Sector** (`max_per_sector: 2`) | Prevents correlated sector blowouts during thematic sell-offs. |

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
│   ├── indicators.py          # Vectorized calculations (50D, 20D, 52W, 50 EMA, 200 SMA, RVOL, ATR)
│   ├── strategy.py            # Daily scanner engine, signal generation & candidate ranking
│   ├── portfolio.py           # Portfolio state manager, risk-based sizing, sector tracking
│   ├── market_data.py         # Kite Connect historical candle fetcher & caching layer
│   ├── universe.py            # Nifty 500 universe loader and token mapping
│   ├── notifier.py            # Discord webhook execution alerts & daily reports
│   └── orders.py              # Kite order placement with safety dry-run checks
├── scripts/
│   ├── backtest.py            # Chronological portfolio simulation engine & terminal reporter
│   └── generate_html_report.py# Interactive Chart.js backtest report generator
├── tests/
│   └── test_strategy.py       # Pytest unit tests for all strategy modules
└── data/
    ├── nifty500.csv           # Master Nifty 500 constituent list with sector metadata
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
   python main.py
   ```

---

### 📊 LATEST BENCHMARK METRICS

#### 1. 5-Year Historical Performance (June 2021 – June 2026)
- **Starting Capital:** ₹1,00,000.00
- **Ending Capital:** **₹2,38,970.50** (+138.97% Net Return)
- **Annualized Return (CAGR):** **+19.03% p.a.**
- **Profit Factor:** **1.63**
- **Max Drawdown:** **-24.84%** (experienced during the broad 2022 global market correction)
- **Sharpe Ratio ($R_f=6.5\%$):** **0.63** | **Sortino Ratio:** **0.80** | **Calmar Ratio:** **0.77**
- **Trades Executed:** 207 (82 Wins / 125 Losses)
- **Win Rate:** **39.6%** | **Win/Loss Ratio:** **2.92x** (+23.93% average winner vs -8.19% average loser)
- **Average Holding Period:** 62.0 days

#### 2. MAE / MFE (Maximum Adverse & Favorable Excursion) Insights
- **Average Peak Profit (MFE) on Winners:** **+49.30%** (Realized: **+23.93%**)
- **Exit Capture Efficiency:** **40.4%** (Trailing 20-day low preserves multi-hundred percent runs while systematically locking profits on momentum exhaustion).
- **Average Adverse Drawdown (MAE) on Winners:** **-4.32%**
- **Deepest Drawdown (Max MAE) in a Winner:** **-15.61%** (Gap-down recovery)
- **Adverse Drawdown Distribution on Winners:**
  - `0% to -2%`: 24.4% (Immediate launch)
  - `-2% to -4%`: 29.3% (Mild noise)
  - `-4% to -6%`: 24.4% (Standard consolidation)
  - `-6% to -8%`: 22.0% (Deep retest of breakout level before secular markup)
- **Conclusion:** The -8% hard loss stop provides optimal breathing room: tighter stops (e.g., -4% or -5%) would chop out over **46% of all eventual mega-winners** (`TITAGARH` +240%, `OIL` +175%, `POWERINDIA` +54%, `WELCORP` +68%).

#### 3. 12-Month Performance (Nov 2025 – Nov 2026)
- **12-Month Return:** **+42.98%** (Ending Equity: ₹1,42,975 on ₹1,00,000)
- **2026 YTD Return:** **+40.54%** (Ending Equity: ₹1,40,540 on ₹1,00,000)
- **Max Drawdown:** **-10.82%**
- **Annualized Sharpe Ratio ($R_f=6.5\%$):** **1.47 (12M) / 1.73 (2026 YTD)**
- **Sortino Ratio:** **2.13 (12M) / 2.82 (2026 YTD)**
- **Profit Factor:** **2.55 (12M) / 3.21 (2026 YTD)**
- **Win Rate:** **39.0%** | **Win/Loss Payout:** **3.22x** (+20.5% winner vs -6.4% loser)

