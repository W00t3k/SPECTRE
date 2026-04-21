#!/usr/bin/env python3
"""
Apple Continuity BLE Scanner
Decodes Apple's proprietary Continuity protocol from BLE advertisement data.
Uses bleak (CoreBluetooth) — no root required on macOS.

Message types decoded (per furiousMAC/continuity):
  0x05  AirDrop
  0x07  Proximity Pairing (AirPods)
  0x0f  Nearby Action
  0x10  Nearby Info
  0x02  iBeacon / Find My
  0x09  AirPlay Target
  0x0a  AirPlay Source
  0x0b  MagicSwitch
  0x0c  Handoff
  0x0d  Tethering Target
  0x0e  Tethering Source
  0x06  HomeKit

Run via the venv:
  .venv/bin/python ble_continuity_scanner.py
Then open: http://localhost:5002
"""

import asyncio
import threading
import time
import json
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit
import os
from apple_ble_tables import (
    APPLE_MFR, MSG_TYPES, NEARBY_ACTIONS, NEARBY_INFO_ACTIONS, PHONE_STATES,
    AIRPODS_MODELS, DEVICE_CLASS, IOS_VERSION, decode_continuity,
)

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("[!] bleak not installed. Run: .venv/bin/pip install bleak")
    raise

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = Flask(__name__, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = "ble-continuity-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── shared state ──────────────────────────────────────────────────────────────
_devices   = {}   # addr → dict (last decoded frame)
_events    = []   # last 200 events
_lock      = threading.Lock()


def _name_from_frames(device_name, frames):
    """Derive the best human-readable name from BLE advertisement frames."""
    if device_name:
        return device_name
    for f in frames:
        t = f["type_id"]
        if t == 0x07 and f.get("model"):        return f["model"]
        if t == 0x08 and f.get("device_type"):  return f["device_type"]
        if t == 0x0f and f.get("device_class"): return f["device_class"]
        if t == 0x06 and f.get("category"):     return f"HomeKit {f['category']}"
        if t == 0x0d:                           return "iPhone Hotspot"
        if t == 0x0e:                           return "iPhone Tethering"
        if t == 0x12:                           return "Find My Accessory"
        if t == 0x0c:                           return "Handoff"
        if t == 0x10:
            ios = f.get("ios_version", "")
            return f"iPhone/iPad ({ios})" if ios else "iPhone/iPad"
        if t == 0x05:                           return "AirDrop"
        if t == 0x09:                           return "AirPlay Target"
        if t == 0x0a:                           return "AirPlay Source"
        if t == 0x0b:                           return "Magic Switch"
    return "Apple Device"


# ── BLE advertisement callback ────────────────────────────────────────────────
def _on_advertisement(device: BLEDevice, adv: AdvertisementData):
    mfr_data = adv.manufacturer_data
    if APPLE_MFR not in mfr_data:
        return

    raw = mfr_data[APPLE_MFR]
    frames = decode_continuity(raw)
    if not frames:
        return

    rssi = adv.rssi if adv.rssi is not None else -100
    ts   = time.time()
    addr = device.address

    name = _name_from_frames(device.name, frames)
    with _lock:
        entry = _devices.get(addr, {})
        entry.update({
            "addr":      addr,
            "name":      name,
            "rssi":      rssi,
            "last_seen": ts,
            "frames":    frames,
            "raw_hex":   raw.hex(),
            "frame_count": entry.get("frame_count", 0) + 1,
        })
        _devices[addr] = entry

        # Event log entry for new message types
        for f in frames:
            event = {
                "ts":    time.strftime("%H:%M:%S", time.localtime(ts)),
                "addr":  addr,
                "name":  name,
                "type":  f["type"],
                "rssi":  rssi,
                "detail": _event_detail(f),
            }
            _events.insert(0, event)
        while len(_events) > 200:
            _events.pop()

    socketio.emit("ble_update", _build_payload())


def _event_detail(f: dict) -> str:
    t = f["type_id"]
    if t == 0x10:
        return f"Activity: {f.get('activity','?')} | WiFi: {f.get('wifi_on','?')} | iOS: {f.get('ios_version','?')}"
    if t == 0x0f:
        return f"Action: {f.get('action','?')}"
    if t == 0x07:
        return f"Model: {f.get('model','?')} | L:{f.get('left_bat','?')} R:{f.get('right_bat','?')}"
    if t == 0x05:
        return f"AirDrop hash apple_id={f.get('apple_id','?')}"
    if t == 0x0c:
        return f"Handoff seq={f.get('sequence','?')}"
    if t == 0x0d:
        return f"Hotspot bat={f.get('battery','?')}"
    return f.get("note", "")


def _build_payload() -> dict:
    with _lock:
        return {
            "devices": list(_devices.values()),
            "events":  _events[:80],
            "ts":      time.strftime("%H:%M:%S"),
        }


# ── Async BLE scan loop ───────────────────────────────────────────────────────
async def _ble_scan_loop():
    print("[BLE] Starting CoreBluetooth scanner…")
    scanner = BleakScanner(detection_callback=_on_advertisement)
    await scanner.start()
    print("[BLE] Scanning for Apple Continuity frames — open http://localhost:5002")
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await scanner.stop()


def _ble_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_ble_scan_loop())


# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "ble.html")


@socketio.on("connect")
def on_connect():
    emit("ble_update", _build_payload())


@socketio.on("clear")
def on_clear():
    with _lock:
        _devices.clear()
        _events.clear()
    socketio.emit("ble_update", _build_payload())


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=_ble_thread, daemon=True)
    t.start()
    print("[*] Open http://localhost:5002")
    socketio.run(app, host="0.0.0.0", port=5002, debug=False, allow_unsafe_werkzeug=True)
