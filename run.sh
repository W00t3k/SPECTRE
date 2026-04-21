#!/usr/bin/env bash
# run.sh — zero-interaction launcher for macOS and Raspberry Pi
# Usage: bash run.sh [--port 5003] [--test-only]
set -euo pipefail

PORT=5003
TEST_ONLY=0

for arg in "$@"; do
    case "$arg" in
        --port) shift; PORT="$1" ;;
        --test-only) TEST_ONLY=1 ;;
    esac
done

OS="$(uname -s)"
VENV=".venv"
PYTHON="$VENV/bin/python"

# ── Auto-install if venv missing ────────────────────────────
if [[ ! -f "$PYTHON" ]]; then
    echo "[*] Virtual environment not found — running setup.sh first..."
    bash setup.sh
fi

# ── Regression tests ────────────────────────────────────────
echo "[*] Running regression tests..."
if ! "$PYTHON" test_ble.py; then
    echo "[!] Tests failed — aborting launch. Fix errors first."
    exit 1
fi

if [[ "$TEST_ONLY" -eq 1 ]]; then
    echo "[*] --test-only flag set, not starting server."
    exit 0
fi

# ── macOS: request Bluetooth permission if needed ───────────
if [[ "$OS" == "Darwin" ]]; then
    # CoreBluetooth permission check — triggers prompt if needed
    echo "[*] Checking Bluetooth permission (macOS)..."
    "$PYTHON" - <<'PYCHECK'
import sys, platform
if platform.system() == "Darwin":
    try:
        import subprocess
        r = subprocess.run(["defaults","read","com.apple.Bluetooth","ControllerPowerState"],
                           capture_output=True, text=True)
        if "1" not in r.stdout:
            print("[!] Bluetooth may be off — check System Settings > Bluetooth")
    except Exception:
        pass
PYCHECK
fi

# ── Pi: ensure all BLE adapters are up ──────────────────────
if [[ "$OS" == "Linux" ]]; then
    echo "[*] Bringing up Bluetooth adapters..."
    sudo rfkill unblock bluetooth 2>/dev/null || true
    for hci in $(ls /sys/class/bluetooth/ 2>/dev/null); do
        sudo hciconfig "$hci" up 2>/dev/null || true
    done
    echo "[*] Active adapters:"
    hciconfig 2>/dev/null | grep -E "^hci|BD Address|Bus:" || echo "    (none found)"
fi

# ── Launch ──────────────────────────────────────────────────
echo "═══════════════════════════════════════"
echo " Starting RF Dashboard on port $PORT"
echo " Open: http://localhost:$PORT"
echo "═══════════════════════════════════════"

exec "$PYTHON" combined_server.py
