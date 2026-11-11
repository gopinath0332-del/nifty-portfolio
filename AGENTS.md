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
   python scripts/run_daily_scan.py
   ```
6. **Check Live Exchange & Portfolio Status:**
   ```bash
   ./status.sh  # or: python scripts/manage_portfolio.py list
   ```

---

### 🏛️ LIVE EXCHANGE INTEGRATION & SAFETY PRINCIPLE

1. **`LIVE_ORDER_PLACEMENT=false` (Safety Mode):**
   - **Only order placement to the exchange is disabled.** The engine will never route automated buy/sell orders without explicit permission.
   - **All other data is ALWAYS collected live from the exchange (Zerodha Kite):**
     - Live available cash & equity margins via `kite.margins("equity")`.
     - Live Demat holdings via `kite.holdings()`.
     - Live open delivery positions via `kite.positions()`.
     - Live CMP quotes via `kite.quote()`.
2. **Exchange Synchronization:**
   - Both `status.sh` and `run_daily_scan.py` automatically call `PortfolioManager.sync_with_exchange(kite)` to reconcile strategy state with real account Demat holdings, eliminating stale or dummy local JSON values.
3. **Shell Script Compatibility:**
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
