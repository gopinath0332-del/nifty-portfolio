#!/bin/bash
# ==============================================================================
# restart.sh
# Restart script for Nifty 500 Portfolio Engine on Raspberry Pi / Linux
# ==============================================================================

SERVICE_NAME="nifty-portfolio"
TIMER_NAME="nifty-portfolio.timer"

echo "=========================================================="
echo "🔄 Restarting Nifty 500 Portfolio Engine..."
echo "=========================================================="

sudo systemctl daemon-reload

# 1. Restart and ensure daily timer is enabled & active (Mon-Fri 15:45 IST)
if systemctl list-unit-files | grep -q "^$TIMER_NAME"; then
    echo "Restarting $TIMER_NAME..."
    sudo systemctl restart "$TIMER_NAME"
    sudo systemctl enable "$TIMER_NAME" 2>/dev/null || true
    echo "✅ $TIMER_NAME restarted and enabled."
else
    echo "WARNING: $TIMER_NAME not found in systemd units."
fi

# 2. Check if user wants to trigger an immediate scan now
if [ "${1:-}" == "--now" ] || [ "${1:-}" == "--scan" ]; then
    echo ""
    echo "⚡ Triggering immediate portfolio scan ($SERVICE_NAME.service)..."
    sudo systemctl start "$SERVICE_NAME.service"
    sleep 3
    echo ""
    echo "Recent Execution Logs:"
    sudo journalctl -u "$SERVICE_NAME.service" -n 25 --no-pager
fi

# 3. Show Timer Status and Next Run Time
echo ""
echo "Timer Schedule Status:"
sudo systemctl list-timers "$TIMER_NAME" --no-pager || true

echo ""
echo "=========================================================="
echo "To view live logs: sudo journalctl -u $SERVICE_NAME.service -f"
echo "To trigger manual scan: ./restart.sh --now"
echo "=========================================================="

