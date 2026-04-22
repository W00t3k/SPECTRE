#!/usr/bin/env bash
# pi-setup.sh — run ONCE on the Raspberry Pi to install SPECTRE dependencies
# Usage: bash pi-setup.sh [--no-service] [--port 5003]
#
#   --no-service   Skip creating the systemd service (run manually with run.sh)
#   --port         Port for the dashboard (default: 5003)

set -euo pipefail

INSTALL_SERVICE=1
PORT=5003
WORK_DIR="$HOME/spectre"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-service) INSTALL_SERVICE=0; shift ;;
        --port)       PORT="$2";         shift 2 ;;
        *) echo "[!] Unknown flag: $1";  shift ;;
    esac
done

echo "═══════════════════════════════════════════════════════════"
echo "  SPECTRE  →  Raspberry Pi setup"
echo "═══════════════════════════════════════════════════════════"

# ── System packages ─────────────────────────────────────────
echo "[*] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    bluetooth bluez bluez-tools \
    libglib2.0-dev \
    wireless-tools iw \
    git curl

# ── Bluetooth setup ─────────────────────────────────────────
echo "[*] Enabling Bluetooth service..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sudo rfkill unblock bluetooth 2>/dev/null || true
for hci in $(ls /sys/class/bluetooth/ 2>/dev/null); do
    sudo hciconfig "$hci" up 2>/dev/null || true
done

# ── Give Python BLE raw socket access without sudo ──────────
PY3=$(which python3)
echo "[*] Granting BLE capabilities to $PY3..."
sudo setcap 'cap_net_raw,cap_net_admin+eip' "$PY3" || \
    echo "[!] setcap failed — you may need to run BLE scanner as root"

# ── Python venv + deps ──────────────────────────────────────
if [[ ! -d "$WORK_DIR" ]]; then
    echo "[*] Work dir $WORK_DIR not found — clone from bare repo first."
    echo "    Run deploy-to-pi.sh --init from your Mac."
    exit 1
fi

cd "$WORK_DIR"
echo "[*] Creating Python virtual environment..."
python3 -m venv .venv
echo "[*] Installing Python dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

echo "[*] Running regression tests..."
if .venv/bin/python core/test_ble.py; then
    echo "[✓] Tests passed."
else
    echo "[!] Tests failed — check output above. Server may still work."
fi

# ── Optional: systemd service ───────────────────────────────
if [[ "$INSTALL_SERVICE" -eq 1 ]]; then
    echo "[*] Installing systemd service (auto-start on boot)..."
    SERVICE_FILE="/etc/systemd/system/spectre.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<SERVICE
[Unit]
Description=SPECTRE Signal Dashboard
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
ExecStart=$WORK_DIR/.venv/bin/python combined_server.py --port $PORT
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

    sudo systemctl daemon-reload
    sudo systemctl enable spectre
    sudo systemctl start spectre
    echo "[✓] Service installed and started."
    echo "    Status:  sudo systemctl status spectre"
    echo "    Logs:    journalctl -u spectre -f"
    echo "    Restart: sudo systemctl restart spectre"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓  Pi setup complete!"
echo ""
echo "  Dashboard → http://$(hostname -I | awk '{print $1}'):$PORT"
echo ""
if [[ "$INSTALL_SERVICE" -eq 0 ]]; then
echo "  To run:   cd $WORK_DIR && bash run.sh --skip-tests"
fi
echo "  To update: git push pi main  (from your Mac)"
echo "═══════════════════════════════════════════════════════════"
