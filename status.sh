#!/bin/bash
# ==============================================================================
# status.sh
# Status inspection script for Nifty 500 Portfolio Engine
# ==============================================================================

SERVICE_NAME="nifty-portfolio"
TIMER_NAME="nifty-portfolio.timer"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "📊 Nifty 500 Portfolio Engine Status"
echo "=========================================================="

echo ""
echo "--- 1. Systemd Timer (Schedule) ---"
sudo systemctl list-timers "$TIMER_NAME" --no-pager || true

echo ""
echo "--- 2. Last Execution Status ---"
sudo systemctl status "$SERVICE_NAME.service" --no-pager -n 5 || true

echo ""
echo "--- 3. Current Portfolio Holdings ---"
if [ -f "${APP_DIR}/venv/bin/python" ]; then
    "${APP_DIR}/venv/bin/python" "${APP_DIR}/scripts/manage_portfolio.py" list || true
else
    python3 "${APP_DIR}/scripts/manage_portfolio.py" list || true
fi

echo "=========================================================="

