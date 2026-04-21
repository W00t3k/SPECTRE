#!/usr/bin/env python3
"""
SSID Visualizer Web Server
Flask + SocketIO backend — streams real Wi-Fi scan data to the browser UI.
Run with:  python3 wifi_web_server.py
Then open:  http://localhost:5001
"""

import subprocess
import threading
import time
import os
import re
import random
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
SCAN_INTERVAL = 5  # seconds

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = Flask(__name__, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = "wifi-viz-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── shared state ─────────────────────────────────────────────────────────────
_networks = {}   # bssid → dict
_lock = threading.Lock()
_scanner_running = False

# ── airport scanner ───────────────────────────────────────────────────────────
def _scan_once():
    try:
        result = subprocess.run(
            [AIRPORT, "-s"],
            capture_output=True, text=True, timeout=12
        )
        return _parse_airport(result.stdout)
    except Exception as e:
        print(f"[scan error] {e}")
        return None


def _parse_airport(raw):
    networks = []
    for line in raw.splitlines()[1:]:
        line = line.rstrip()
        if not line.strip():
            continue
        # Find BSSID (xx:xx:xx:xx:xx:xx)
        m = re.search(r'([\da-f]{2}(?::[\da-f]{2}){5})', line, re.I)
        if not m:
            continue
        bssid_start = m.start()
        bssid = m.group(1)
        ssid = line[:bssid_start].strip() or "<hidden>"
        rest = line[m.end():].split()
        try:
            rssi    = int(rest[0])
            channel = rest[1].split(',')[0]
            security = rest[5] if len(rest) > 5 else "?"
        except (IndexError, ValueError):
            rssi, channel, security = -80, "?", "?"
        networks.append({
            "ssid":     ssid,
            "bssid":    bssid,
            "rssi":     rssi,
            "channel":  channel,
            "security": security,
            "last_seen": time.time()
        })
    return networks or None


def _scanner_loop():
    global _scanner_running
    _scanner_running = True
    while _scanner_running:
        nets = _scan_once()
        if nets:
            with _lock:
                _networks.clear()
                for n in nets:
                    _networks[n["bssid"]] = n
            _push_update(source="live")
        time.sleep(SCAN_INTERVAL)


def _push_update(source="live"):
    with _lock:
        payload = {
            "networks": list(_networks.values()),
            "source":   source,
            "ts":       time.strftime("%H:%M:%S")
        }
    socketio.emit("update", payload)


# ── demo data fallback ────────────────────────────────────────────────────────
DEMO = [
    {"ssid": "Linksys_Home",    "bssid": "aa:bb:cc:11:22:33", "rssi": -45, "channel": "6",   "security": "WPA2"},
    {"ssid": "NETGEAR-5G",      "bssid": "aa:bb:cc:44:55:66", "rssi": -62, "channel": "36",  "security": "WPA3"},
    {"ssid": "Starbucks_Guest", "bssid": "de:ad:be:ef:00:01", "rssi": -78, "channel": "1",   "security": "Open"},
    {"ssid": "ATT-WiFi-2.4",    "bssid": "de:ad:be:ef:00:02", "rssi": -55, "channel": "11",  "security": "WPA2"},
    {"ssid": "MyHome_EXT",      "bssid": "de:ad:be:ef:00:03", "rssi": -68, "channel": "6",   "security": "WPA2"},
    {"ssid": "TP-LINK_A1B2",    "bssid": "de:ad:be:ef:00:04", "rssi": -82, "channel": "44",  "security": "WPA2"},
    {"ssid": "xfinitywifi",     "bssid": "de:ad:be:ef:00:05", "rssi": -90, "channel": "1",   "security": "Open"},
    {"ssid": "<hidden>",        "bssid": "de:ad:be:ef:00:06", "rssi": -71, "channel": "6",   "security": "WPA2"},
    {"ssid": "Office_Corp",     "bssid": "ca:fe:ba:be:00:01", "rssi": -50, "channel": "149", "security": "WPA3"},
    {"ssid": "Galaxy_Hotspot",  "bssid": "ca:fe:ba:be:00:02", "rssi": -66, "channel": "6",   "security": "WPA2"},
    {"ssid": "CafeWiFi_Free",   "bssid": "ca:fe:ba:be:00:03", "rssi": -74, "channel": "11",  "security": "Open"},
    {"ssid": "SmartHome_IoT",   "bssid": "ca:fe:ba:be:00:04", "rssi": -58, "channel": "100", "security": "WPA2"},
]


def _load_demo():
    with _lock:
        for n in DEMO:
            _networks[n["bssid"]] = dict(n, last_seen=time.time())


def _wiggle_demo():
    """Randomly drift RSSI values to animate demo data."""
    with _lock:
        for net in _networks.values():
            net["rssi"] = max(-95, min(-35, net["rssi"] + random.randint(-3, 3)))
    _push_update(source="demo")


# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ── SocketIO events ───────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    with _lock:
        nets = list(_networks.values())
    emit("update", {"networks": nets, "source": "init", "ts": time.strftime("%H:%M:%S")})


@socketio.on("request_scan")
def on_request_scan():
    nets = _scan_once()
    if nets:
        with _lock:
            _networks.clear()
            for n in nets:
                _networks[n["bssid"]] = n
        _push_update(source="live")
    else:
        _push_update(source="demo")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _load_demo()

    # Start real scanner if airport exists
    if os.path.exists(AIRPORT):
        print("[*] airport found — starting live scanner...")
        t = threading.Thread(target=_scanner_loop, daemon=True)
        t.start()
        # Also wiggle demo occasionally until first real scan
        def _demo_wiggle_until_live():
            time.sleep(2)
            for _ in range(10):
                time.sleep(2)
                with _lock:
                    src = next(iter(_networks.values()), {}).get("last_seen", 0)
                _wiggle_demo()
        threading.Thread(target=_demo_wiggle_until_live, daemon=True).start()
    else:
        print("[!] airport not found — running in DEMO mode")
        def _demo_loop():
            while True:
                time.sleep(3)
                _wiggle_demo()
        threading.Thread(target=_demo_loop, daemon=True).start()

    print("[*] Open http://localhost:5001 in your browser")
    socketio.run(app, host="0.0.0.0", port=5001, debug=False, allow_unsafe_werkzeug=True)
