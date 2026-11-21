#!/bin/sh
# ==============================================================================
# logs.sh
# Production log inspector and debugging utility for Raspberry Pi / Linux.
# Usage:
#   ./logs.sh                 # Show recent daily scan logs and error warnings
#   ./logs.sh -f              # Follow daily scan log live (tail -f)
#   ./logs.sh -e              # View errors and stack traces (logs/errors.log)
#   ./logs.sh -ef             # Follow errors log live
#   ./logs.sh -j              # Inspect systemd journal logs (journalctl)
#   ./logs.sh -n 100          # Show last 100 lines of daily scan log
#   ./logs.sh --clear         # Safely truncate log files to free disk space
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="${APP_DIR}/logs"
SCAN_LOG="${LOGS_DIR}/daily_scan.log"
ERROR_LOG="${LOGS_DIR}/errors.log"
SERVICE_NAME="nifty-portfolio"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

show_help() {
    echo "Nifty 500 Portfolio Engine — Log & Debug Utility"
    echo ""
    echo "Usage: ./logs.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  (no args)          Show last 35 lines of daily scan log"
    echo "  -f, --follow       Follow daily scan log live (tail -f)"
    echo "  -e, --errors       View dedicated errors and exception traces"
    echo "  -ef, --follow-err  Follow error log live"
    echo "  -j, --journal      View systemd service journal (journalctl)"
    echo "  -n <lines>         Show last N lines (default: 35)"
    echo "  --clear            Safely truncate log files to release disk space"
    echo "  -h, --help         Show this help message"
}

case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    --clear)
        echo "Truncating log files in $LOGS_DIR..."
        : > "$SCAN_LOG" 2>/dev/null || true
        : > "$ERROR_LOG" 2>/dev/null || true
        echo "✅ Log files truncated."
        exit 0
        ;;
    -f|--follow)
        if [ ! -f "$SCAN_LOG" ]; then
            touch "$SCAN_LOG"
        fi
        echo "==> Following live scan log ($SCAN_LOG)... (Ctrl+C to stop)"
        exec tail -f "$SCAN_LOG"
        ;;
    -ef|--follow-err)
        if [ ! -f "$ERROR_LOG" ]; then
            touch "$ERROR_LOG"
        fi
        echo "==> Following live error log ($ERROR_LOG)... (Ctrl+C to stop)"
        exec tail -f "$ERROR_LOG"
        ;;
    -e|--errors)
        echo "=========================================================="
        echo "🚨 DEDICATED ERROR LOG ($ERROR_LOG)"
        echo "=========================================================="
        if [ -s "$ERROR_LOG" ]; then
            tail -n "${2:-50}" "$ERROR_LOG"
        else
            echo "✅ No errors recorded in $ERROR_LOG."
        fi
        echo "=========================================================="
        exit 0
        ;;
    -j|--journal)
        echo "=========================================================="
        echo "📋 SYSTEMD JOURNAL LOGS ($SERVICE_NAME.service)"
        echo "=========================================================="
        sudo journalctl -u "$SERVICE_NAME.service" -n "${2:-50}" --no-pager
        echo "=========================================================="
        exit 0
        ;;
    -n)
        LINES="${2:-35}"
        if [ -f "$SCAN_LOG" ]; then
            tail -n "$LINES" "$SCAN_LOG"
        else
            echo "Log file $SCAN_LOG does not exist yet."
        fi
        exit 0
        ;;
    *)
        LINES=35
        echo "=========================================================="
        echo "📋 RECENT DAILY SCAN LOGS (Last $LINES lines)"
        echo "=========================================================="
        if [ -f "$SCAN_LOG" ]; then
            tail -n "$LINES" "$SCAN_LOG"
        else
            echo "No logs found at $SCAN_LOG yet."
        fi
        echo "=========================================================="

        # Also alert if errors.log has entries
        if [ -s "$ERROR_LOG" ]; then
            ERR_COUNT=$(wc -l < "$ERROR_LOG" | tr -d ' ')
            echo ""
            echo "⚠️  ATTENTION: $ERR_COUNT line(s) recorded in $ERROR_LOG."
            echo "    Showing latest errors (last 10 lines):"
            echo "----------------------------------------------------------"
            tail -n 10 "$ERROR_LOG"
            echo "----------------------------------------------------------"
            echo "To view all errors: ./logs.sh -e"
        fi
        echo ""
        echo "Quick commands:"
        echo "  Live tail:    ./logs.sh -f"
        echo "  View errors:  ./logs.sh -e"
        echo "  Systemd log:  ./logs.sh -j"
        echo "=========================================================="
        ;;
esac
