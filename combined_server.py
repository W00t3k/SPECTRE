#!/usr/bin/env python3
"""
SPECTRE — Signal & Protocol Exploitation, Capture, Tracking, Recon Engine
Unified WiFi + Apple Continuity BLE passive recon dashboard.

Platforms: macOS (airport CLI + CoreBluetooth via bleak)
           Raspberry Pi / Linux (bleak over HCI adapter, no airport)

Run:  .venv/bin/python combined_server.py
      python3 combined_server.py          (Pi, system bleak)

Dashboard: http://localhost:5003
"""

import asyncio
import threading
import subprocess
import time
import os
import re
import json
import csv
import io
import random
import platform
from flask import Flask, send_from_directory, jsonify, Response
from flask_socketio import SocketIO, emit
from core.identity import record_device, get_all_identities, get_identity_timeline, get_identity_hashes, set_identity_label, get_stats as identity_stats
from core.fingerprint import DeviceCorrelator
from core.apple_ble_tables import (
    APPLE_MFR, MSG_TYPES, NEARBY_ACTIONS, NEARBY_INFO_ACTIONS, PHONE_STATES,
    AIRPODS_MODELS, AIRPODS_STATUS, AIRPODS_COLORS, HOMEKIT_CATEGORY,
    SIRI_DEVICE, DEVICE_CLASS, MAGIC_SW_WRIST, HOTSPOT_NET, IOS_VERSION,
    DEVICES_MODELS, decode_continuity,
)

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False
    print("[!] bleak not available — BLE scanning disabled")

IS_MACOS = platform.system() == "Darwin"
IS_PI    = os.path.exists("/proc/device-tree/model")

AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
WIFI_SCAN_INTERVAL = 6   # seconds  (mutable at runtime via set_interval)

app = Flask(__name__, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = os.environ.get("SPECTRE_SECRET", os.urandom(32).hex())
_API_TOKEN = os.environ.get("SPECTRE_TOKEN", "")  # optional: set to require CLI auth
_CORS_ORIGIN = os.environ.get("SPECTRE_ORIGIN", "*")  # lock down with SPECTRE_ORIGIN env var on untrusted networks
socketio = SocketIO(app, cors_allowed_origins=_CORS_ORIGIN, async_mode="threading")

# ═══════════════════════════════════════════════════════════════════════════
# SHARED STATE
# ═══════════════════════════════════════════════════════════════════════════
_lock          = threading.Lock()   # guards _wifi_networks, _ble_devices, _wifi_history, _ble_history
_ev_lock       = threading.Lock()   # guards _events (separate to avoid deadlock)
_al_lock       = threading.Lock()   # guards _alerts
_wifi_networks = {}   # bssid → dict
_ble_devices   = {}   # addr  → dict
_events        = []   # unified event log (max 300)
_alerts        = []   # alert log (max 50)
_wifi_history  = {}   # bssid → [(ts, rssi), ...]  (last 60 samples)
_ble_history   = {}   # addr  → [(ts, rssi), ...]
_demo_mode     = False
_correlator    = DeviceCorrelator()
_notif_muted   = False   # mute macOS notifications via GUI or CLI

MAX_HISTORY = 60   # samples per device


def _push_history(store, key, rssi):
    if key not in store:
        store[key] = []
    store[key].append((time.time(), rssi))
    if len(store[key]) > MAX_HISTORY:
        store[key].pop(0)


def _add_event(evtype, source, name, detail="", rssi=None):
    """Thread-safe. Never call while holding _lock."""
    ev = {
        "ts":     time.strftime("%H:%M:%S"),
        "epoch":  time.time(),
        "type":   evtype,
        "source": source,
        "name":   name,
        "detail": detail,
        "rssi":   rssi,
    }
    with _ev_lock:
        _events.insert(0, ev)
        while len(_events) > 300:
            _events.pop()
    return ev


def _add_alert(kind, name, detail):
    """Thread-safe. Never call while holding _lock."""
    al = {"ts": time.strftime("%H:%M:%S"), "kind": kind, "name": name, "detail": detail}
    with _al_lock:
        _alerts.insert(0, al)
        while len(_alerts) > 50:
            _alerts.pop()
    # Notify and emit outside any lock
    _notify_macos(kind, name, detail)
    socketio.emit("alert", al)


_SAFE_NOTIF = re.compile(r'[^\w\s\-\.\:\@\#\%\+\=\[\]\(\)\/]')

def _sanitise_notif(s):
    """Strip characters that could escape an osascript string literal."""
    return _SAFE_NOTIF.sub('', str(s))[:80]

def _notify_macos(title, subtitle, body):
    """Fire a native macOS notification via osascript (respects _notif_muted)."""
    if _notif_muted:
        return
    try:
        t = _sanitise_notif(title)
        s = _sanitise_notif(subtitle)
        b = _sanitise_notif(body)
        script = f'display notification "{b}" with title "{t}" subtitle "{s}"'
        subprocess.run(["osascript", "-e", script],
                       capture_output=True, timeout=3)
    except Exception:
        pass


def _emit_all():
    with _lock:
        wifi = list(_wifi_networks.values())
        ble  = list(_ble_devices.values())
        wh   = {k: v[-30:] for k, v in _wifi_history.items()}
        bh   = {k: v[-30:] for k, v in _ble_history.items()}
    with _ev_lock:
        evs = _events[:100]
    with _al_lock:
        als = _alerts[:20]
    socketio.emit("update", {
        "wifi":         wifi,
        "ble":          ble,
        "events":       evs,
        "alerts":       als,
        "wifi_history": wh,
        "ble_history":  bh,
        "ts":           time.strftime("%H:%M:%S"),
        "demo":         _demo_mode,
    })


# ═══════════════════════════════════════════════════════════════════════════
# WIFI SCANNER
# ═══════════════════════════════════════════════════════════════════════════
def _parse_airport(raw):
    networks = []
    for line in raw.splitlines()[1:]:
        line = line.rstrip()
        if not line.strip():
            continue
        m = re.search(r'([\da-f]{2}(?::[\da-f]{2}){5})', line, re.I)
        if not m:
            continue
        bssid = m.group(1)
        ssid  = line[:m.start()].strip() or "<hidden>"
        rest  = line[m.end():].split()
        try:
            rssi     = int(rest[0])
            channel  = rest[1].split(',')[0]
            security = rest[4] if len(rest) > 4 else "?"
        except (IndexError, ValueError):
            rssi, channel, security = -80, "?", "?"
        networks.append({
            "ssid": ssid, "bssid": bssid, "rssi": rssi,
            "channel": channel, "security": security,
            "last_seen": time.time(),
        })
    return networks or None


def _wifi_scan_loop():
    global _demo_mode
    while True:
        try:
            if os.path.exists(AIRPORT):
                r = subprocess.run([AIRPORT, "-s"], capture_output=True, text=True, timeout=12)
                nets = _parse_airport(r.stdout)
            else:
                nets = None
        except Exception:
            nets = None

        # Compute new state and diff outside the lock first
        pending_events  = []
        pending_alerts  = []
        with _lock:
            prev_keys = set(_wifi_networks.keys())
            if nets:
                _demo_mode = False
                new_nets = {n["bssid"]: n for n in nets}
            else:
                _demo_mode = True
                new_nets = {k: dict(v, rssi=max(-95, min(-35, v["rssi"] + random.randint(-3, 3))),
                                    last_seen=time.time())
                            for k, v in _wifi_networks.items()}

            for bssid, net in new_nets.items():
                _push_history(_wifi_history, bssid, net["rssi"])
                if bssid not in prev_keys:
                    pending_events.append(("NEW", "WIFI", net["ssid"],
                                           f"CH:{net['channel']} {net['security']} {net['rssi']}dBm",
                                           net["rssi"]))
                    if net["security"] in ("Open", "--", "NONE"):
                        pending_alerts.append(("⚠ OPEN WIFI", net["ssid"],
                                               f"Unencrypted network on CH {net['channel']}"))
                elif net["rssi"] < -88 and _wifi_networks.get(bssid, {}).get("rssi", 0) >= -88:
                    pending_events.append(("WEAK", "WIFI", net["ssid"],
                                           f"{net['rssi']}dBm", net["rssi"]))

            for bssid in prev_keys:
                if bssid not in new_nets:
                    pending_events.append(("LOST", "WIFI",
                                           _wifi_networks[bssid].get("ssid", bssid), "", None))

            _wifi_networks.clear()
            _wifi_networks.update(new_nets)

        # Fire events/alerts outside _lock to prevent deadlock
        for args in pending_events:
            _add_event(*args)
        for args in pending_alerts:
            _add_alert(*args)

        _emit_all()
        time.sleep(WIFI_SCAN_INTERVAL)  # global — updated live by set_interval


# ═══════════════════════════════════════════════════════════════════════════
# BLE / CONTINUITY DECODER
# All tables and decode_continuity() are imported from apple_ble_tables.py
# ═══════════════════════════════════════════════════════════════════════════



def _name_from_frames(device_name, frames):
    """Derive the best human-readable name from BLE advertisement frames."""
    if device_name:
        return device_name
    for f in frames:
        t = f["type_id"]
        if t == 0x07 and f.get("model"):       return f["model"]           # AirPods / Beats model
        if t == 0x08 and f.get("device_type"): return f["device_type"]     # Siri (HomePod etc.)
        if t == 0x0f and f.get("device_class"):return f["device_class"]    # Nearby Action device class
        if t == 0x06 and f.get("category"):    return f"HomeKit {f['category']}"
        if t == 0x0d:                          return "iPhone Hotspot"
        if t == 0x0e:                          return "iPhone Tethering"
        if t == 0x12:                          return "Find My Accessory"
        if t == 0x0c:                          return "Handoff"
        if t == 0x0f:                          return "Nearby Action"
        if t == 0x10:                                                      # Nearby Info → phone
            ios = f.get("ios_version", "")
            return f"iPhone/iPad ({ios})" if ios else "iPhone/iPad"
        if t == 0x05:                          return "AirDrop"
        if t == 0x09:                          return "AirPlay Target"
        if t == 0x0a:                          return "AirPlay Source"
        if t == 0x0b:                          return "Magic Switch"
    return "Apple Device"


def _on_ble_adv(device: BLEDevice, adv: AdvertisementData):
    if APPLE_MFR not in adv.manufacturer_data:
        return
    raw    = adv.manufacturer_data[APPLE_MFR]
    frames = decode_continuity(raw)
    if not frames:
        return
    rssi = adv.rssi or -100
    addr = device.address
    name = _name_from_frames(device.name, frames)
    ts   = time.time()

    with _lock:
        is_new = addr not in _ble_devices
        entry  = _ble_devices.get(addr, {})
        old_frames = {f["type_id"] for f in entry.get("frames", [])}
        new_frame_types = {f["type_id"] for f in frames}

        _push_history(_ble_history, addr, rssi)

        entry.update({
            "addr": addr, "name": name, "rssi": rssi,
            "last_seen": ts, "frames": frames,
            "raw_hex": raw.hex(),
            "frame_count": entry.get("frame_count", 0) + 1,
        })

        # Battery history for AirPods
        for f in frames:
            if f["type_id"] == 0x07:
                if "bat_history" not in entry:
                    entry["bat_history"] = []
                entry["bat_history"].append({
                    "ts": ts,
                    "L": f.get("left_bat"), "R": f.get("right_bat"),
                    "C": f.get("case_bat"),
                })
                if len(entry["bat_history"]) > 60:
                    entry["bat_history"].pop(0)

        _ble_devices[addr] = entry

    # Identity engine — runs outside _lock
    identity = record_device(addr, name, rssi, frames)
    # Attach fp_id back to the live device entry
    with _lock:
        if addr in _ble_devices:
            _ble_devices[addr]["fp_id"]      = identity["fp_id"]
            _ble_devices[addr]["threat"]     = identity["threat"]
            _ble_devices[addr]["seen_total"] = identity["seen_count"]
            _ble_devices[addr]["label"]      = identity["label"]

    # All _add_event / _add_alert calls happen outside _lock
    if is_new:
        desc = ", ".join(f["type"] for f in frames)
        _add_event("BLE_NEW", "BLE", name, desc, rssi)
        # Re-appearance alert — only MEDIUM/HIGH or real named devices
        _GENERIC = {"Find My Accessory","Apple Device","Handoff","AirDrop",
                    "Nearby Action","iPhone Tethering","iPhone Hotspot"}
        if identity["is_return"] and (identity["threat"] != "LOW" or name not in _GENERIC):
            _add_alert("👁 KNOWN DEVICE RETURNED",
                       name,
                       f"Seen {identity['seen_count']}x  •  Threat: {identity['threat']}")
        for f in frames:
            if f["type_id"] == 0x05:
                hashes = identity.get("hashes", [])
                h_str = "  ".join(f"{h['type']}: {h['hash']}" for h in hashes)
                _add_alert("📡 AirDrop Detected", name, h_str or "Hashes captured")
            elif f["type_id"] == 0x0f and f.get("action") == "WiFi Password Share":
                _add_alert("🔑 WiFi Password Share", name, "Device offering WiFi credentials")
            elif f["type_id"] == 0x0d:
                _add_alert("📶 Hotspot Detected", name,
                           f"Battery: {f.get('battery','?')}%")
        if identity["threat"] == "HIGH":
            _add_alert("🎯 HIGH-VALUE TARGET", name,
                       "AirDrop hashes captured  •  run: python tools/rainbow.py <hash>")
    elif new_frame_types - old_frames:
        added = ", ".join(MSG_TYPES.get(t, f"0x{t:02x}") for t in (new_frame_types - old_frames))
        _add_event("BLE_UPD", "BLE", name, f"New: {added}", rssi)

    _emit_all()


BLE_DEVICE_TTL = 120   # seconds before a BLE device is marked LOST

def _reap_lost_ble():
    """Mark BLE devices as lost after TTL, remove after 2x TTL."""
    while True:
        time.sleep(30)
        now = time.time()
        pending_events = []
        with _lock:
            for addr, dev in list(_ble_devices.items()):
                age = now - dev.get("last_seen", 0)
                if age > BLE_DEVICE_TTL * 2:
                    _ble_devices.pop(addr, None)
                    pending_events.append(("LOST", "BLE", dev.get("name", addr),
                                           "Device no longer visible", None))
                elif age > BLE_DEVICE_TTL and not dev.get("lost"):
                    dev["lost"] = True
                    pending_events.append(("LOST", "BLE", dev.get("name", addr),
                                           f"Signal lost ({int(age)}s ago)", None))
                elif age <= BLE_DEVICE_TTL and dev.get("lost"):
                    dev["lost"] = False
        # Fire events outside _lock
        for args in pending_events:
            _add_event(*args)


def _pick_ble_adapter():
    """
    Linux/Pi: find the best HCI adapter.
    Prefers USB dongles (Bus: USB) over built-in UART adapters.
    Returns adapter string like 'hci0' or None (let bleak pick default).
    """
    try:
        r = subprocess.run(["hciconfig", "-a"], capture_output=True, text=True, timeout=5)
        output = r.stdout
        # Parse blocks: hci0: ... Bus: USB / UART
        adapters = re.findall(r'(hci\d+).*?Bus:\s*(\w+)', output, re.S)
        if not adapters:
            # Fallback: just grab first hciX
            m = re.search(r'(hci\d+)', output)
            return m.group(1) if m else None
        usb = [(a, b) for a, b in adapters if b.upper() == "USB"]
        chosen = usb[0][0] if usb else adapters[0][0]
        print(f"[BLE] Adapters found: {adapters}  →  using {chosen}")
        # Ensure adapter is up
        if re.fullmatch(r'hci\d+', chosen):
            subprocess.run(["sudo", "hciconfig", chosen, "up"], capture_output=True)
        return chosen
    except Exception as e:
        print(f"[BLE] Adapter probe failed: {e}")
        return None


async def _ble_loop():
    kwargs = {}
    env_adapter = os.environ.get("BLE_ADAPTER")
    if env_adapter:
        kwargs["adapter"] = env_adapter
        print(f"[BLE] BLE_ADAPTER override → {env_adapter}")
    elif not IS_MACOS:
        adapter = _pick_ble_adapter()
        if adapter:
            kwargs["adapter"] = adapter
    retry = 0
    while True:
        try:
            scanner = BleakScanner(detection_callback=_on_ble_adv, **kwargs)
            await scanner.start()
            print(f"[BLE] Scanner active (adapter={kwargs.get('adapter','default')})")
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            retry += 1
            wait = min(30, 5 * retry)
            print(f"[BLE] Scanner error (attempt {retry}): {e} — retry in {wait}s")
            await asyncio.sleep(wait)


def _ble_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_ble_loop())


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM INFO
# ═══════════════════════════════════════════════════════════════════════════
def _get_system_info():
    info = {}
    try:
        info["hostname"] = subprocess.check_output(["hostname"], text=True).strip()
    except Exception:
        info["hostname"] = "unknown"
    try:
        info["os"] = platform.platform()
    except Exception:
        info["os"] = "unknown"
    # macOS system_profiler for USB
    usb_devices = []
    if IS_MACOS:
        try:
            raw = subprocess.check_output(
                ["system_profiler", "SPUSBDataType", "-json"],
                text=True, timeout=8)
            spdata = json.loads(raw)
            items = spdata.get("SPUSBDataType", [])
            def _flatten(node):
                name = node.get("_name","")
                vendor = node.get("manufacturer","")
                product_id = node.get("product_id","")
                vendor_id = node.get("vendor_id","")
                speed = node.get("device_speed","")
                usb_devices.append({"name":name,"vendor":vendor,
                    "product_id":product_id,"vendor_id":vendor_id,"speed":speed})
                for sub in node.get("_items",[]):
                    _flatten(sub)
            for item in items:
                _flatten(item)
        except Exception as e:
            usb_devices = [{"name":f"Error: {e}","vendor":"","product_id":"","vendor_id":"","speed":""}]
    # Network interfaces
    net_ifaces = []
    try:
        raw = subprocess.check_output(["ifconfig"], text=True, timeout=5)
        for block in re.split(r'\n(?=\S)', raw):
            iface_m = re.match(r'^(\S+):', block)
            if not iface_m: continue
            iface = iface_m.group(1)
            ip4 = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', block)
            ip6 = re.search(r'inet6 ([0-9a-f:]+)', block)
            mac = re.search(r'ether ([0-9a-f:]{17})', block)
            status = "UP" if "UP" in block else "DOWN"
            net_ifaces.append({"iface":iface,
                "ip4": ip4.group(1) if ip4 else "",
                "ip6": ip6.group(1) if ip6 else "",
                "mac": mac.group(1) if mac else "",
                "status": status})
    except Exception:
        pass
    info["usb"] = usb_devices
    info["interfaces"] = net_ifaces
    info["wifi_scan_interval"] = WIFI_SCAN_INTERVAL
    info["demo_mode"] = _demo_mode
    return info


# ═══════════════════════════════════════════════════════════════════════════
# DEMO WIFI DATA
# ═══════════════════════════════════════════════════════════════════════════
DEMO_WIFI = [
    {"ssid":"Linksys_Home",   "bssid":"aa:bb:cc:11:22:33","rssi":-45,"channel":"6",  "security":"WPA2"},
    {"ssid":"NETGEAR-5G",     "bssid":"aa:bb:cc:44:55:66","rssi":-62,"channel":"36", "security":"WPA3"},
    {"ssid":"Starbucks_Guest","bssid":"de:ad:be:ef:00:01","rssi":-78,"channel":"1",  "security":"Open"},
    {"ssid":"ATT-WiFi-2.4",   "bssid":"de:ad:be:ef:00:02","rssi":-55,"channel":"11", "security":"WPA2"},
    {"ssid":"MyHome_EXT",     "bssid":"de:ad:be:ef:00:03","rssi":-68,"channel":"6",  "security":"WPA2"},
    {"ssid":"TP-LINK_A1B2",   "bssid":"de:ad:be:ef:00:04","rssi":-82,"channel":"44", "security":"WPA2"},
    {"ssid":"xfinitywifi",    "bssid":"de:ad:be:ef:00:05","rssi":-90,"channel":"1",  "security":"Open"},
    {"ssid":"<hidden>",       "bssid":"de:ad:be:ef:00:06","rssi":-71,"channel":"6",  "security":"WPA2"},
    {"ssid":"Office_Corp",    "bssid":"ca:fe:ba:be:00:01","rssi":-50,"channel":"149","security":"WPA3"},
    {"ssid":"Galaxy_Hotspot", "bssid":"ca:fe:ba:be:00:02","rssi":-66,"channel":"6",  "security":"WPA2"},
    {"ssid":"CafeWiFi_Free",  "bssid":"ca:fe:ba:be:00:03","rssi":-74,"channel":"11", "security":"Open"},
    {"ssid":"SmartHome_IoT",  "bssid":"ca:fe:ba:be:00:04","rssi":-58,"channel":"100","security":"WPA2"},
]


def _load_demo_wifi():
    ts = time.time()
    with _lock:
        for n in DEMO_WIFI:
            _wifi_networks[n["bssid"]] = dict(n, last_seen=ts)
            _push_history(_wifi_history, n["bssid"], n["rssi"])


# ═══════════════════════════════════════════════════════════════════════════
# DEMO BLE DATA
# ═══════════════════════════════════════════════════════════════════════════
DEMO_BLE = [
    {"addr":"aa:bb:cc:11:22:01","name":"AirPods Pro",  "rssi":-52,"frames":[
        {"type_id":0x07,"type":"AirPods","model":"AirPods Pro (2nd Gen)",
         "left_bat":7,"right_bat":8,"case_bat":9,"left_charging":False,
         "right_charging":False,"case_charging":True,"status":"Both In Case",
         "color":"White","raw":"0710"}],"frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:02","name":"iPhone/iPad (18.3)","rssi":-61,"frames":[
        {"type_id":0x10,"type":"Nearby Info","phone_state":"Screen Active",
         "ios_version":"18.3","wifi_on":True,"airdrop_status":1,"raw":"1005"}],
     "frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:03","name":"AirDrop","rssi":-74,"frames":[
        {"type_id":0x05,"type":"AirDrop","phone":"2a3b","apple_id":"c4d5","email":"","raw":"0512"}],
     "frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:04","name":"Nearby Action","rssi":-68,"frames":[
        {"type_id":0x0f,"type":"Nearby Action","action":"Setup New iPhone",
         "device_class":"iPhone","wifi_on":True,"raw":"0f08"}],"frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:05","name":"iPhone Hotspot","rssi":-80,"frames":[
        {"type_id":0x0d,"type":"Hotspot","network_type":"LTE","battery":72,
         "display_on":False,"raw":"0d06"}],"frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:06","name":"Handoff","rssi":-59,"frames":[
        {"type_id":0x0c,"type":"Handoff","sequence":42,"raw":"0c08"}],
     "frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:07","name":"Find My Accessory","rssi":-88,"frames":[
        {"type_id":0x12,"type":"Find My","status":"Separated","raw":"1203"}],
     "frame_count":1,"lost":True},
    {"addr":"aa:bb:cc:11:22:08","name":"HomePod mini","rssi":-55,"frames":[
        {"type_id":0x08,"type":"Siri","device_type":"HomePod mini",
         "battery":None,"active":False,"os_version":"17.4","raw":"0808"}],
     "frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:09","name":"HomeKit Lock","rssi":-66,"frames":[
        {"type_id":0x06,"type":"HomeKit","category":"Door Lock","raw":"0603"}],
     "frame_count":1,"lost":False},
    {"addr":"aa:bb:cc:11:22:0a","name":"AirPods Max","rssi":-47,"frames":[
        {"type_id":0x07,"type":"AirPods","model":"AirPods Max",
         "left_bat":6,"right_bat":6,"case_bat":None,"left_charging":False,
         "right_charging":False,"case_charging":False,"status":"In Ear","color":"Space Gray","raw":"0710"}],
     "frame_count":1,"lost":False},
]


def _load_demo_ble():
    ts = time.time()
    with _lock:
        for d in DEMO_BLE:
            entry = dict(d, last_seen=ts)
            _ble_devices[d["addr"]] = entry
            _push_history(_ble_history, d["addr"], d["rssi"])


# ═══════════════════════════════════════════════════════════════════════════
# FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "dashboard.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/export/wifi.json")
def export_wifi_json():
    with _lock:
        data = list(_wifi_networks.values())
    return Response(json.dumps(data, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment;filename=wifi_scan.json"})


@app.route("/export/wifi.csv")
def export_wifi_csv():
    with _lock:
        data = list(_wifi_networks.values())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["ssid","bssid","rssi","channel","security","last_seen"])
    w.writeheader()
    for net in data:
        w.writerow({k: net.get(k,"") for k in w.fieldnames})
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=wifi_scan.csv"})


@app.route("/export/ble.json")
def export_ble_json():
    with _lock:
        data = list(_ble_devices.values())
    return Response(json.dumps(data, indent=2, default=str),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment;filename=ble_scan.json"})


@app.route("/export/events.json")
def export_events_json():
    with _ev_lock:
        data = list(_events)
    return Response(json.dumps(data, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment;filename=events.json"})


@app.route("/api/system_info")
def api_system_info():
    return jsonify(_get_system_info())


# ── Identity Engine API ──────────────────────────────────────────────────────
@app.route("/api/identities")
def api_identities():
    return jsonify({
        "stats":      identity_stats(),
        "identities": get_all_identities(200),
    })


@app.route("/api/identities/<fp_id>")
def api_identity_detail(fp_id):
    return jsonify({
        "timeline": get_identity_timeline(fp_id, 100),
        "hashes":   get_identity_hashes(fp_id),
    })


@app.route("/api/identities/<fp_id>/label", methods=["POST"])
def api_identity_label(fp_id):
    from flask import request as flask_request
    body = flask_request.get_json(force=True) or {}
    label = str(body.get("label", ""))[:64]
    set_identity_label(fp_id, label)
    with _lock:
        for dev in _ble_devices.values():
            if dev.get("fp_id") == fp_id:
                dev["label"] = label
    return jsonify({"ok": True})


@app.route("/api/correlate")
def api_correlate():
    with _lock:
        devs = dict(_ble_devices)
    clusters = _correlator.correlate(devs)
    return jsonify({"clusters": clusters})


_start_time = time.time()

@app.route("/api/status")
def api_status():
    with _lock:
        wifi  = list(_wifi_networks.values())
        ble   = list(_ble_devices.values())
    with _ev_lock:
        events = list(_events)
    with _al_lock:
        alerts = list(_alerts)
    uptime_s = int(time.time() - _start_time)
    h, r = divmod(uptime_s, 3600); m, s = divmod(r, 60)
    return jsonify({
        "demo":           _demo_mode,
        "wifi_count":     len(wifi),
        "ble_count":      len(ble),
        "event_count":    len(events),
        "alert_count":    len(alerts),
        "scan_interval":  WIFI_SCAN_INTERVAL,
        "uptime":         f"{h:02d}:{m:02d}:{s:02d}",
        "wifi":           wifi,
        "ble":            ble,
        "events":         events[-200:],
        "alerts":         alerts[-50:],
    })


@app.route("/api/emit", methods=["POST"])
def api_emit():
    """REST shim so the CLI can fire socket events without a full socket.io client."""
    from flask import request as flask_request
    if _API_TOKEN:
        auth = flask_request.headers.get("X-SPECTRE-Token", "")
        if auth != _API_TOKEN:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
    body  = flask_request.get_json(force=True) or {}
    event = body.get("event","")
    data  = body.get("data",{})
    handlers = {
        "toggle_demo":     on_toggle_demo,
        "inject_demo_ble": on_inject_demo_ble,
        "inject_demo_wifi":on_inject_demo_wifi,
        "clear_ble":       on_clear_ble,
        "clear_events":    on_clear_events,
        "clear_alerts":    on_clear_alerts,
        "toggle_mute":     on_toggle_mute,
    }
    if event == "set_interval":
        global WIFI_SCAN_INTERVAL
        try:
            v = int(data.get("interval", 6))
            WIFI_SCAN_INTERVAL = max(2, min(60, v))
        except Exception:
            pass
        _emit_all()
        return jsonify({"ok": True, "interval": WIFI_SCAN_INTERVAL})
    fn = handlers.get(event)
    if fn:
        fn()
        return jsonify({"ok": True, "event": event})
    return jsonify({"ok": False, "error": f"Unknown event: {event}"}), 400


# ═══════════════════════════════════════════════════════════════════════════
# SOCKETIO EVENTS
# ═══════════════════════════════════════════════════════════════════════════
@socketio.on("connect")
def on_connect():
    with _lock:
        wifi = list(_wifi_networks.values())
        ble  = list(_ble_devices.values())
        wh   = {k: v[-30:] for k, v in _wifi_history.items()}
        bh   = {k: v[-30:] for k, v in _ble_history.items()}
    with _ev_lock:
        evs = _events[:100]
    with _al_lock:
        als = _alerts[:20]
    emit("update", {
        "wifi": wifi, "ble": ble, "events": evs, "alerts": als,
        "wifi_history": wh, "ble_history": bh,
        "ts": time.strftime("%H:%M:%S"), "demo": _demo_mode,
    })


@socketio.on("request_wifi_scan")
def on_wifi_scan():
    if os.path.exists(AIRPORT):
        try:
            r = subprocess.run([AIRPORT, "-s"], capture_output=True, text=True, timeout=12)
            nets = _parse_airport(r.stdout)
            if nets:
                pending_ev = []
                with _lock:
                    prev = set(_wifi_networks.keys())
                    for n in nets:
                        _push_history(_wifi_history, n["bssid"], n["rssi"])
                        if n["bssid"] not in prev:
                            pending_ev.append(("NEW", "WIFI", n["ssid"],
                                               f"CH:{n['channel']} {n['security']}",
                                               n["rssi"]))
                    _wifi_networks.clear()
                    for n in nets:
                        _wifi_networks[n["bssid"]] = n
                for args in pending_ev:
                    _add_event(*args)
        except Exception as e:
            print(f"[scan err] {e}")
    _emit_all()


@socketio.on("clear_ble")
def on_clear_ble():
    with _lock:
        _ble_devices.clear()
        _ble_history.clear()
    _emit_all()


@socketio.on("clear_events")
def on_clear_events():
    with _ev_lock:
        _events.clear()
    _emit_all()


@socketio.on("clear_alerts")
def on_clear_alerts():
    with _al_lock:
        _alerts.clear()
    _emit_all()


@socketio.on("inject_demo_ble")
def on_inject_demo_ble():
    _load_demo_ble()
    _emit_all()


@socketio.on("inject_demo_wifi")
def on_inject_demo_wifi():
    _load_demo_wifi()
    _emit_all()


@socketio.on("set_interval")
def on_set_interval(data):
    global WIFI_SCAN_INTERVAL
    try:
        v = int(data.get("interval", 6))
        WIFI_SCAN_INTERVAL = max(2, min(60, v))
    except Exception:
        pass
    emit("interval_ack", {"interval": WIFI_SCAN_INTERVAL})


@socketio.on("toggle_mute")
def on_toggle_mute():
    global _notif_muted
    _notif_muted = not _notif_muted
    socketio.emit("mute_state", {"muted": _notif_muted})


@socketio.on("toggle_demo")
def on_toggle_demo():
    global _demo_mode
    _demo_mode = not _demo_mode
    if _demo_mode:
        _load_demo_wifi()
        _load_demo_ble()
    _emit_all()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    _load_demo_wifi()
    _load_demo_ble()

    # WiFi scanner thread
    wt = threading.Thread(target=_wifi_scan_loop, daemon=True)
    wt.start()

    # BLE scanner + reaper threads
    if BLE_AVAILABLE:
        bt = threading.Thread(target=_ble_thread, daemon=True)
        bt.start()
        rt = threading.Thread(target=_reap_lost_ble, daemon=True)
        rt.start()
        print(f"[BLE] Starting scanner (macOS={IS_MACOS} pi={IS_PI})...")
    else:
        print("[BLE] bleak not available — BLE tab will be empty")

    print()
    print("  ██████╗██████╗ ███████╗██████╗ ███████╗██████╗ ███████╗")
    print("  ██╔════╝██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗██╔════╝")
    print("  ███████╗██████╔╝█████╗  ██████╔╝█████╗  ██████╔╝█████╗  ")
    print("  ╚════██║██╔══██╗██╔══╝  ██╔══██╗██╔══╝  ██╔══██╗██╔══╝  ")
    print("  ██████╔╝██║  ██║███████╗██║  ██║███████╗██║  ██║███████╗")
    print("  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝")
    print()
    print("  Signal • Protocol • Exploitation • Capture • Tracking • Recon • Engine")
    print(f"  Dashboard → http://localhost:5003")
    print()
    socketio.run(app, host="0.0.0.0", port=5003,
                 debug=False, allow_unsafe_werkzeug=True)
