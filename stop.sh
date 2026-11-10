#!/bin/bash
# ==============================================================================
# stop.sh
# Stop script for Nifty 500 Portfolio Engine on Raspberry Pi / Linux
# ==============================================================================

SERVICE_NAME="nifty-portfolio"
TIMER_NAME="nifty-portfolio.timer"

echo "=========================================================="
echo "🛑 Stopping Nifty 500 Portfolio Engine..."
echo "=========================================================="

# 1. Stop and disable the daily timer so it stops triggering at 15:45 IST
if systemctl list-unit-files | grep -q "^$TIMER_NAME"; then
    echo "Stopping $TIMER_NAME..."
    sudo systemctl stop "$TIMER_NAME"
    echo "✅ $TIMER_NAME stopped."
else
    echo "WARNING: $TIMER_NAME not found in systemd."
fi

# 2. Stop the service if currently in progress
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
    echo "Stopping active scan ($SERVICE_NAME.service)..."
    sudo systemctl stop "$SERVICE_NAME.service"
    echo "✅ $SERVICE_NAME.service stopped."
fi

# 3. Check current status
sleep 1
echo ""
echo "Current Timer Status:"
sudo systemctl status "$TIMER_NAME" --no-pager || true

echo ""
echo "=========================================================="
echo "Engine stopped. Daily 15:45 IST scans are paused."
echo "To restart: ./restart.sh or sudo systemctl start $TIMER_NAME"
echo "=========================================================="

