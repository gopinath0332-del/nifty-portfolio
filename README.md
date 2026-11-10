# Nifty 500 Donchian Breakout Portfolio Engine

An automated daily swing trading portfolio engine for **Nifty 500 stocks** based on the **20-Day High Breakout (Long Only)** Donchian Channel strategy with a **52-Week High Trend Filter (within 15%)**, designed for Zerodha Kite Connect and deployment on a **Raspberry Pi 5**.

---

## 📈 Strategy Overview

1. **Universe:** Nifty 500 equity cash market (`NSE:SYMBOL`, CNC product type).
2. **Timeframe:** Daily candles (`day`).
3. **Execution Schedule:** **3:45 PM IST** daily (Monday to Friday) on finalized daily candles.
4. **Primary Trend Filter:** Stock must be **within 15% of its 52-Week High** (`Close >= 0.85 * 52W High`), ensuring you only trade institutional leaders in Stage-2 uptrends with minimal overhead resistance.
5. **Entry Signal:** `Close > 20-Day High[1]` (Close above the highest high of the previous 20 completed daily bars).
6. **Exit Signal:** `Close < 20-Day Low[1]` (Close below the lowest low of the previous 20 completed daily bars).
7. **Tie-Breaking Model:** When more stocks trigger breakouts than available slots:
   $$\text{Composite Score} = \left(\frac{\text{Close} - \text{High}_{20}[1]}{\text{High}_{20}[1]} \times 100\right) \times \left(\frac{\text{Volume}}{\text{Avg Volume}_{20}}\right)$$
   Ranks stocks with strong percentage breakouts backed by high relative volume (RVOL) at the top.
8. **Capital Allocation:**
   - **Total Budget:** ₹2,00,000 (INR 2 Lakhs)
   - **Position Allocation:** ₹20,000 per stock
   - **Max Portfolio Size:** 10 stocks
   - **Position Sizing:** `Quantity = floor(20,000 / CMP)`
9. **Execution Mode:** Actionable Discord alerts sent at 3:45 PM for manual order placement on Kite.

---

## 📁 Project Structure

```
d:\Workspace\nifty-portfolio/
├── .env.example                  # Environment configuration template
├── .env                          # Local secrets & KITE_ENV_PATH pointer
├── .gitignore                    # Git ignore file
├── requirements.txt              # Python dependencies
├── config/
│   └── settings.yaml             # Strategy, filters, capital, and file paths
├── data/
│   ├── nifty500.csv              # Official Nifty 500 stock universe
│   ├── portfolio_state.json      # Persistent holdings and trade history
│   └── cache/                    # Cached instrument tokens & daily candles
├── src/
│   ├── config.py                 # Configuration loader (.env + settings.yaml)
│   ├── kite_client.py            # Zerodha authentication via KITE_ENV_PATH
│   ├── universe.py               # Nifty 500 token mapping and universe manager
│   ├── market_data.py            # Rate-limited historical candle fetcher (3 req/sec)
│   ├── indicators.py             # 20-Day High/Low, 52W High, RVOL calculations
│   ├── strategy.py               # Signal generation & candidate ranking
│   ├── portfolio.py              # Portfolio state manager (10 slots, ₹20k sizing)
│   └── discord_notifier.py       # Rich actionable Discord embeds
├── scripts/
│   ├── run_daily_scan.py         # Main daily scanner (executed at 15:45 IST)
│   ├── manage_portfolio.py       # CLI tool to view, add, remove, or auto-sync holdings
│   └── test_notification.py      # Quick script to test Discord webhook
├── tests/
│   └── test_strategy.py          # Unit tests (100% pass)
└── deploy/
    ├── nifty-portfolio.service   # Systemd service unit for Raspberry Pi 5
    ├── nifty-portfolio.timer     # Systemd timer (Mon-Fri 15:45 IST)
    └── setup_pi.sh               # Raspberry Pi 5 automated setup script
```

---

## 🔑 Authentication with Zerodha Kite

Authentication is shared with `nifty-strike-engine` via `KITE_ENV_PATH`:
In `.env`:
```bash
# Windows:
KITE_ENV_PATH=D:\Workspace\nifty-strike-engine\.env

# Raspberry Pi 5:
# KITE_ENV_PATH=/home/pi/nifty-strike-engine/.env
```
Whenever `nifty-strike-engine` runs its morning `auto_login.py` script to generate a fresh `KITE_ACCESS_TOKEN`, `nifty-portfolio` automatically uses the same session with zero manual intervention.

---

## 🚀 Quick Start & Usage

### 1. Run the Daily Scan Manually
```bash
# Full scan of Nifty 500 universe with Discord alerts
python scripts/run_daily_scan.py

# Fast test scan limited to first 10 stocks without Discord alerts
python scripts/run_daily_scan.py --limit 10 --no-discord
```

### 2. Manage Portfolio Holdings via CLI
```bash
# View current portfolio holdings, live CMPs, cash, and P&L
python scripts/manage_portfolio.py list

# Record a manual buy execution (calculates ₹20k quantity automatically if omitted)
python scripts/manage_portfolio.py buy --symbol TATASTEEL --price 145.20

# Record a manual exit/sell
python scripts/manage_portfolio.py sell --symbol TATASTEEL --price 158.00

# Automatically sync active portfolio with Zerodha Demat holdings
python scripts/manage_portfolio.py sync

# View closed trade history and realized P&L
python scripts/manage_portfolio.py history
```

### 3. Service Control (Raspberry Pi 5)
```bash
# Restart the daily timer (Mon-Fri 15:45 IST)
./restart.sh

# Restart and trigger an immediate test scan
./restart.sh --now

# Stop the engine (pause scheduled scans)
./stop.sh

# Check timer schedule, recent logs, and portfolio holdings
./status.sh
```

### 4. Backtest & Generate Interactive HTML Report
```bash
# Run terminal backtest
python scripts/backtest.py --start 2026-01-01

# Generate standalone visual HTML report dashboard
python scripts/generate_html_report.py
```

### 5. Test Discord Notifications
```bash
python scripts/test_notification.py
```

### 5. Run Unit Tests
```bash
python -m pytest tests/test_strategy.py
```

---

## 🍓 Raspberry Pi 5 Production Deployment

1. Clone or copy `nifty-portfolio` to `/home/pi/nifty-portfolio`.
2. Run the automated setup script:
   ```bash
   cd ~/nifty-portfolio
   chmod +x deploy/setup_pi.sh
   ./deploy/setup_pi.sh
   ```
3. The setup script will:
   - Create Python virtual environment and install dependencies.
   - Set system timezone to `Asia/Kolkata`.
   - Install and start the `nifty-portfolio.timer` systemd service.
   - Run the scan automatically every Monday to Friday at **15:45 IST**.
4. Check timer status anytime:
   ```bash
   systemctl list-timers nifty-portfolio.timer
   journalctl -u nifty-portfolio.service -f
   ```

