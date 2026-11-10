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
| **Channel Exit Fallback**  | **20-Day Donchian Low** (`exit_len: 20`) | Fallback trailing exit for channel preservation. |
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
- **Ending Capital:** **₹3,43,441.58** (+243.44% Net Return)
- **Annualized Return (CAGR):** **+27.99% p.a.**
- **Profit Factor:** **2.04**
- **Max Drawdown:** **-19.21%** (reduced from -24.84% via early Stage 2 & Profit Lock exits)
- **Sharpe Ratio ($R_f=6.5\%$):** **1.03** | **Sortino Ratio:** **1.34** | **Calmar Ratio:** **1.46**
- **Trades Executed:** 257 (115 Wins / 142 Losses)
- **Win Rate:** **44.7%** | **Win/Loss Ratio:** **2.74x** (+21.05% average winner vs -7.67% average loser)
- **Exit Capture Efficiency:** **44.6%**
- **Average Holding Period:** 49.9 days

#### 2. MAE / MFE (Maximum Adverse & Favorable Excursion) Insights
- **Average Peak Profit (MFE) on Winners:** **+38.43%** (Realized: **+21.05%**)
- **Exit Capture Efficiency:** **44.6%** (Two-tier exit dynamically locks in peak profits when momentum breaks 20 EMA, while allowing Stage 2 trends to compound).
- **Average Adverse Drawdown (MAE) on Winners:** **-3.93%**
- **Deepest Drawdown (Max MAE) in a Winner:** **-12.67%**
- **Adverse Drawdown Distribution on Winners:**
  - `0% to -2%`: 27.8% (Immediate launch)
  - `-2% to -4%`: 29.6% (Mild noise)
  - `-4% to -6%`: 22.6% (Standard consolidation)
  - `-6% to -8%`: 20.0% (Deep retest near stop)
- **Conclusion:** Young positions need room to consolidate (42.6% of eventual winners dip below -4% MAE). Once in mature profit ($\ge +25\%$), the 20 EMA trailing exit protects accumulated gains.

#### 3. 12-Month Performance (Nov 2025 – Nov 2026)
- **12-Month Return:** **+48.27%** (Ending Equity: ₹1,48,270 on ₹1,00,000)
- **Max Drawdown:** **-13.31%**
- **Annualized Sharpe Ratio ($R_f=6.5\%$):** **1.73**
- **Sortino Ratio:** **2.83** | **Calmar Ratio:** **3.61**
- **Profit Factor:** **2.60**
- **Win Rate:** **42.6%** | **Win/Loss Payout:** **2.88x** (+20.0% winner vs -6.9% loser)

