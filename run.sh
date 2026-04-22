#!/usr/bin/env bash
# run.sh — zero-interaction launcher for macOS and Raspberry Pi
# Usage: bash run.sh [--port 5003] [--test-only] [--skip-tests]
set -euo pipefail

PORT=5003
TEST_ONLY=0
SKIP_TESTS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)       PORT="$2"; shift 2 ;;
        --test-only)  TEST_ONLY=1; shift ;;
        --skip-tests) SKIP_TESTS=1; shift ;;
        *) echo "[!] Unknown flag: $1"; shift ;;
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
if [[ "$SKIP_TESTS" -eq 0 ]]; then
    echo "[*] Running regression tests..."
    if ! "$PYTHON" core/test_ble.py; then
        echo "[!] Tests failed — aborting launch. Fix errors first."
        echo "[!] Use --skip-tests to bypass (not recommended)."
        exit 1
    fi
else
    echo "[*] Skipping regression tests (--skip-tests)."
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
echo "═══════════════════════════════════════════════════════════"
echo "  SPECTRE — Signal & Protocol Exploitation, Capture,"
echo "               Tracking, Recon Engine"
echo ""
echo "  Dashboard  →  http://localhost:$PORT"
echo "  CLI help   →  python spectre.py --help"
echo "  Quick cmds →  python spectre.py wifi"
echo "               python spectre.py ble"
echo "               python spectre.py status"
echo "═══════════════════════════════════════════════════════════"

exec "$PYTHON" combined_server.py --port "$PORT"
