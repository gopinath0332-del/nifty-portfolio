#!/bin/sh
# ==============================================================================
# status.sh
# Status inspection script for Nifty 500 Portfolio Engine (POSIX sh & bash compatible)
# ==============================================================================

SERVICE_NAME="nifty-portfolio"
TIMER_NAME="nifty-portfolio.timer"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================================="
echo "📊 Nifty 500 Portfolio Engine Status"
echo "=========================================================="

echo ""
echo "--- 1. Systemd Timer (Schedule) ---"
sudo systemctl list-timers "$TIMER_NAME" --no-pager 2>/dev/null || true

echo ""
echo "--- 2. Last Execution Status ---"
sudo systemctl status "$SERVICE_NAME.service" --no-pager -n 5 2>/dev/null || true

echo ""
echo "--- 3. Live Exchange Holdings & Portfolio Status ---"
if [ -f "${APP_DIR}/venv/bin/python" ]; then
    "${APP_DIR}/venv/bin/python" "${APP_DIR}/scripts/manage_portfolio.py" list || true
else
    python3 "${APP_DIR}/scripts/manage_portfolio.py" list || true
fi

echo "=========================================================="

