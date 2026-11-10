#!/usr/bin/env bash
# ============================================================
# deploy/setup_pi.sh
# Production Setup for Nifty 500 Portfolio on Raspberry Pi 5
# ============================================================
set -euo pipefail

APP_DIR="${HOME}/nifty-portfolio"
SERVICE_NAME="nifty-portfolio"
USER_NAME="$(whoami)"

echo "==> Setting up Nifty 500 Portfolio Engine on Raspberry Pi 5..."
echo "==> User: ${USER_NAME} | Directory: ${APP_DIR}"

mkdir -p "${APP_DIR}/logs"
mkdir -p "${APP_DIR}/data/cache"

# Ensure timezone is Asia/Kolkata
echo "==> Verifying system timezone (Asia/Kolkata)..."
sudo timedatectl set-timezone Asia/Kolkata || true

# 1. Python virtual environment
if [ ! -d "${APP_DIR}/venv" ]; then
    echo "==> Creating Python virtual environment..."
    python3 -m venv "${APP_DIR}/venv"
fi

echo "==> Installing Python dependencies..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 2. Configure .env if not exists
if [ ! -f "${APP_DIR}/.env" ]; then
    echo "==> Creating .env from template..."
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    sed -i "s|KITE_ENV_PATH=.*|KITE_ENV_PATH=${HOME}/nifty-strike-engine/.env|g" "${APP_DIR}/.env"
    echo "==> Updated KITE_ENV_PATH to: ${HOME}/nifty-strike-engine/.env"
fi

# 3. Install and enable systemd service and timer
echo "==> Installing systemd service and timer..."
sudo cp "${APP_DIR}/deploy/${SERVICE_NAME}.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/${SERVICE_NAME}.timer" /etc/systemd/system/

# Adjust user and paths in service file if not 'pi'
if [ "${USER_NAME}" != "pi" ]; then
    sudo sed -i "s|User=pi|User=${USER_NAME}|g" "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo sed -i "s|/home/pi|${HOME}|g" "/etc/systemd/system/${SERVICE_NAME}.service"
fi

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.timer"
sudo systemctl start "${SERVICE_NAME}.timer"

echo "==> Systemd timer status:"
sudo systemctl status "${SERVICE_NAME}.timer" --no-pager || true

echo "============================================================"
echo "✅ Setup Complete!"
echo "• The scanner will automatically run Mon-Fri at 15:45 IST."
echo "• To trigger an immediate test scan:"
echo "    ${APP_DIR}/venv/bin/python ${APP_DIR}/scripts/run_daily_scan.py"
echo "• To test Discord alert:"
echo "    ${APP_DIR}/venv/bin/python ${APP_DIR}/scripts/test_notification.py"
echo "• To view portfolio status:"
echo "    ${APP_DIR}/venv/bin/python ${APP_DIR}/scripts/manage_portfolio.py list"
echo "============================================================"

