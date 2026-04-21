#!/usr/bin/env bash
# setup.sh — one-shot dependency installer for macOS and Raspberry Pi
# Usage: bash setup.sh
set -euo pipefail

VENV=".venv"
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "═══════════════════════════════════════"
echo " RF Dashboard — Setup"
echo " OS: $OS  ARCH: $ARCH"
echo "═══════════════════════════════════════"

# ── System packages (Pi/Linux only) ─────────────────────────
if [[ "$OS" == "Linux" ]]; then
    echo "[*] Installing system packages..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        bluetooth bluez bluez-tools libbluetooth-dev \
        libglib2.0-dev pkg-config rfkill usbutils

    echo "[*] Unblocking bluetooth via rfkill..."
    sudo rfkill unblock bluetooth 2>/dev/null || true

    echo "[*] Enabling bluetooth service..."
    sudo systemctl enable bluetooth
    sudo systemctl restart bluetooth
    sleep 2

    echo "[*] Bringing up all HCI adapters..."
    for hci in $(ls /sys/class/bluetooth/ 2>/dev/null); do
        echo "    → $hci up"
        sudo hciconfig "$hci" up 2>/dev/null || true
    done

    # List detected BLE adapters
    echo "[*] Detected Bluetooth adapters:"
    hciconfig -a 2>/dev/null | grep -E "^hci|Bus:|BD Address" || echo "    (none detected yet)"

    # Give current user access to bluetooth socket without sudo
    if ! groups "$USER" | grep -q bluetooth; then
        echo "[*] Adding $USER to bluetooth group..."
        sudo usermod -aG bluetooth "$USER"
        echo "[!] You may need to log out/in for group change to take effect."
    fi
fi

# ── macOS: check Homebrew python ────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    if ! command -v python3 &>/dev/null; then
        echo "[!] python3 not found. Install via: brew install python3"
        exit 1
    fi
fi

# ── Virtual environment ─────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv "$VENV"
fi

PIP="$VENV/bin/pip"
PYTHON="$VENV/bin/python"

echo "[*] Upgrading pip..."
"$PIP" install --quiet --upgrade pip

echo "[*] Installing Python dependencies..."
"$PIP" install --quiet \
    flask \
    flask-socketio \
    "bleak>=0.21" \
    simple-websocket

# Pi needs dbus-python for BlueZ backend
if [[ "$OS" == "Linux" ]]; then
    "$PIP" install --quiet dbus-python || true
fi

echo "[*] Running regression tests..."
"$PYTHON" test_ble.py

echo ""
echo "═══════════════════════════════════════"
echo " Setup complete!"
echo " Run:  bash run.sh"
echo "═══════════════════════════════════════"
