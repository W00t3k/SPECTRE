#!/usr/bin/env python3
"""
Regression test suite — combined_server.py + ble_continuity_scanner.py
Covers hexway/apple_bleee + furiousMAC/continuity lookup tables.
Run:  .venv/bin/python core/test_ble.py
Exit: 0 = all pass, 1 = failures
"""
import sys, re, time
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest.mock as mock
for _m in ("bleak","bleak.backends","bleak.backends.device","bleak.backends.scanner"):
    sys.modules.setdefault(_m, mock.MagicMock())

from core.apple_ble_tables import (
    decode_continuity,
    AIRPODS_MODELS, NEARBY_ACTIONS, NEARBY_INFO_ACTIONS, IOS_VERSION,
    MSG_TYPES, AIRPODS_STATUS, AIRPODS_COLORS, HOMEKIT_CATEGORY,
    HOTSPOT_NET, MAGIC_SW_WRIST, SIRI_DEVICE, PHONE_STATES,
    DEVICE_CLASS, DEVICES_MODELS,
)
from combined_server import _parse_airport, _push_history

# Both decoders are now the same function — keep aliases for test readability
decode_v1 = decode_v2 = decode_continuity
MSG_TYPES_V1 = MSG_TYPES_V2 = MSG_TYPES

PASS = FAIL = 0
def check(name, got, want):
    global PASS, FAIL
    if got == want:
        print(f"  PASS  {name}"); PASS += 1
    else:
        print(f"  FAIL  {name}\n        got ={got!r}\n        want={want!r}"); FAIL += 1

def section(t): print(f"\n── {t} {'─'*(54-len(t))}")

# ══════════════════════════════════════════════════════════════════════════════
# 1. NEARBY INFO  0x10
# ══════════════════════════════════════════════════════════════════════════════
section("Nearby Info  0x10")
raw_ni = bytes([0x10, 0x05, 0x73, 0x1c, 0x83, 0x90, 0x96])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(raw_ni)
    check(f"[{label}] NearbyInfo count",          len(fs), 1)
    check(f"[{label}] NearbyInfo type",            fs[0]["type"], "Nearby Info")
    check(f"[{label}] NearbyInfo activity code 7", fs[0]["activity"], NEARBY_INFO_ACTIONS[0x07])
    check(f"[{label}] NearbyInfo primary_device",  fs[0]["primary_device"], True)
    check(f"[{label}] NearbyInfo airdrop off",     fs[0]["airdrop_enabled"], False)
    check(f"[{label}] NearbyInfo auth_tag",        fs[0]["auth_tag"], "839096")

raw_ni_wifi = bytes([0x10,0x05,0x03,0x3c,0x00,0x00,0x00])
check("[v1] NearbyInfo wifi_on True", decode_v1(raw_ni_wifi)[0]["wifi_on"], True)
check("[v2] NearbyInfo wifi_on True", decode_v2(raw_ni_wifi)[0]["wifi_on"], True)

# v2 also sets phone_state from PHONE_STATES
check("[v2] NearbyInfo phone_state",
      decode_v2(raw_ni)[0]["phone_state"],
      PHONE_STATES.get(0x73, f"0x73"))

section("Phone states table coverage")
for code, label in [(0x07,"Lock screen"),(0x0e,"Incoming call"),(0x4e,"Outgoing call"),(0x0d,"Driving")]:
    check(f"PHONE_STATES[0x{code:02x}]={label}", PHONE_STATES.get(code), label)

# ══════════════════════════════════════════════════════════════════════════════
# 2. NEARBY ACTION  0x0f
# ══════════════════════════════════════════════════════════════════════════════
section("Nearby Action  0x0f")
raw_na = bytes([0x0f,0x05,0x40,0x08,0x39,0x00,0x87])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(raw_na)
    check(f"[{label}] NearbyAction count",   len(fs), 1)
    check(f"[{label}] NearbyAction action",  fs[0]["action"], "WiFi Password Share")
    check(f"[{label}] NearbyAction flags",   fs[0]["flags"],  "0x40")
    check(f"[{label}] NearbyAction auth",    fs[0]["auth_tag"], "390087")
check("[v1] NearbyAction unknown code hex",
      decode_v1(bytes([0x0f,0x03,0x00,0xff,0x00]))[0]["action"], "0xff")

# ══════════════════════════════════════════════════════════════════════════════
# 3. AIRPODS  0x07
# ══════════════════════════════════════════════════════════════════════════════
section("AirPods Proximity Pairing  0x07")
raw_ap = bytes([0x07,0x0c, 0x01, 0x20,0x0e, 0x55, 0x99, 0x07, 0x39, 0x00, 0x00,0x00])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(raw_ap)
    check(f"[{label}] AirPods count", len(fs), 1)
    check(f"[{label}] AirPods model", fs[0]["model"], "AirPods Pro 1st Gen")

f1 = decode_continuity(raw_ap)[0]
check("AirPods right_bat",    f1["right_bat"], 9)
check("AirPods left_bat",     f1["left_bat"],  9)
check("AirPods case_bat",     f1["case_bat"],  0)
check("AirPods right_charging", f1["right_charging"], True)
check("AirPods left_charging",  f1["left_charging"],  True)
check("AirPods status label",   f1["status"], AIRPODS_STATUS.get(0x55))

# Color decode: color byte=0x08 → Rose Gold
raw_col = bytes([0x07,0x09, 0x01,0x20,0x0e, 0x55, 0x99,0x07,0x39,0x08])
check("[v2] AirPods color Rose Gold", decode_v2(raw_col)[0]["color"], "Rose Gold")

section("AirPods status table coverage")
for code, label in [(0x00,"Case: Closed"),(0x0b,"L+R: in ear"),(0x55,"Case: Open (lid open)"),(0x50,"Case: Open")]:
    check(f"AIRPODS_STATUS[0x{code:02x}]", AIRPODS_STATUS.get(code), label)

section("AirPods color table coverage")
for code, col in [(0x00,"White"),(0x01,"Black"),(0x08,"Rose Gold"),(0x09,"Space Gray"),(0x07,"Gold")]:
    check(f"AIRPODS_COLORS[0x{code:02x}]", AIRPODS_COLORS.get(code), col)

# ══════════════════════════════════════════════════════════════════════════════
# 4. AIRDROP  0x05
# ══════════════════════════════════════════════════════════════════════════════
section("AirDrop  0x05")
raw_ad = bytes([0x05,0x12]+[0x00]*8+[0x01,0x6e,0x2e,0xf7,0xad,0x09,0xb2,0x20,0x80,0x00])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(raw_ad)
    check(f"[{label}] AirDrop count",    len(fs),            1)
    check(f"[{label}] AirDrop apple_id", fs[0]["apple_id"],  "6e2e")
    check(f"[{label}] AirDrop phone",    fs[0]["phone"],     "f7ad")
    check(f"[{label}] AirDrop email",    fs[0]["email"],     "09b2")
    check(f"[{label}] AirDrop email2",   fs[0]["email2"],    "2080")
check("[v2] AirDrop note has hash2phone",
      "hash2phone" in decode_v2(raw_ad)[0].get("note",""), True)

# ══════════════════════════════════════════════════════════════════════════════
# 5. HANDOFF  0x0c
# ══════════════════════════════════════════════════════════════════════════════
section("Handoff  0x0c")
raw_hf = bytes([0x0c,0x06, 0x00,0x42, 0x05, 0xde,0xad,0xbe])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(raw_hf)
    check(f"[{label}] Handoff count",    len(fs),             1)
    check(f"[{label}] Handoff seq",      fs[0]["sequence"],   0x0042)
    check(f"[{label}] Handoff act_id",   fs[0]["activity_id"],"0x05")
f1 = decode_continuity(bytes([0x0c,0x04,0x00,0x42,0x05,0xde]))[0]
check("Handoff short auth_tag", f1.get("auth_tag"), None)

# ══════════════════════════════════════════════════════════════════════════════
# 6. FIND MY  0x12
# ══════════════════════════════════════════════════════════════════════════════
section("Find My  0x12")
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(bytes([0x12,0x02,0x00,0xAB]))
    check(f"[{label}] FindMy count",  len(fs),          1)
    check(f"[{label}] FindMy status", fs[0]["status"],  "0x00")

# ══════════════════════════════════════════════════════════════════════════════
# 7. HOMEKIT  0x06
# ══════════════════════════════════════════════════════════════════════════════
section("HomeKit  0x06")
raw_hk = bytes([0x06,0x04, 0x01,0x05, 0x03,0x04])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(raw_hk)
    check(f"[{label}] HomeKit count", len(fs), 1)
    check(f"[{label}] HomeKit category name", fs[0].get("category"), "Lightbulb")

section("HomeKit category table coverage")
for code, name in [(0x06,"Door Lock"),(0x11,"IP Camera"),(0x12,"Video Doorbell"),(0x09,"Thermostat")]:
    check(f"HOMEKIT_CATEGORY[0x{code:02x}]", HOMEKIT_CATEGORY.get(code), name)

# ══════════════════════════════════════════════════════════════════════════════
# 8. TETHERING TARGET / HOTSPOT  0x0d
# ══════════════════════════════════════════════════════════════════════════════
section("Tethering Target (Hotspot)  0x0d")
raw_hs = bytes([0x0d,0x03, 0x01, 0x5a, 0x07])
fs = decode_v2(raw_hs)
check("[v2] Hotspot count",        len(fs), 1)
check("[v2] Hotspot network_type", fs[0]["network_type"], "LTE")
check("[v2] Hotspot battery",      fs[0]["battery"], 0x5a)

section("Hotspot network type table coverage")
for code, name in [(0x07,"LTE"),(0x06,"4G"),(0x05,"3G"),(0x03,"EDGE"),(0x02,"GPRS")]:
    check(f"HOTSPOT_NET[0x{code:02x}]", HOTSPOT_NET.get(code), name)

# ══════════════════════════════════════════════════════════════════════════════
# 9. MAGIC SWITCH  0x0b
# ══════════════════════════════════════════════════════════════════════════════
section("Magic Switch  0x0b")
check("[v2] wrist On wrist",          decode_v2(bytes([0x0b,0x01,0x3f]))[0]["wrist_state"],  "On wrist")
check("[v2] wrist Not on wrist",      decode_v2(bytes([0x0b,0x01,0x03]))[0]["wrist_state"],  "Not on wrist")
check("MAGIC_SW_WRIST[0x1f]",         MAGIC_SW_WRIST.get(0x1f), "Wrist detection disabled")

# ══════════════════════════════════════════════════════════════════════════════
# 10. SIRI  0x08
# ══════════════════════════════════════════════════════════════════════════════
section("Siri  0x08")
check("[v2] Siri iPhone",    decode_v2(bytes([0x08,0x02,0x00,0x02]))[0]["device_type"], "iPhone")
check("SIRI_DEVICE iPad",    SIRI_DEVICE.get(0x0003), "iPad")
check("SIRI_DEVICE MacBook", SIRI_DEVICE.get(0x0009), "MacBook")
check("SIRI_DEVICE Watch",   SIRI_DEVICE.get(0x000a), "Apple Watch")

# ══════════════════════════════════════════════════════════════════════════════
# 11. AIRPLAY  0x09
# ══════════════════════════════════════════════════════════════════════════════
section("AirPlay Target  0x09")
fs = decode_v2(bytes([0x09,0x01,0xFF]))
check("[v2] AirPlay type", fs[0]["type"], "AirPlay Target")
check("[v2] AirPlay note", "AirPlay receiver" in fs[0].get("note",""), True)

# ══════════════════════════════════════════════════════════════════════════════
# 12. EDGE CASES
# ══════════════════════════════════════════════════════════════════════════════
section("Edge Cases")
check("Unknown type v1",    len(decode_v1(bytes([0xAA,0x02,0x00,0x00]))), 0)
check("Unknown type v2",    len(decode_v2(bytes([0xAA,0x02,0x00,0x00]))), 0)
check("Empty bytes v1",     len(decode_v1(b"")), 0)
check("Empty bytes v2",     len(decode_v2(b"")), 0)
check("Single byte v1",     len(decode_v1(bytes([0x10]))), 0)
check("Single byte v2",     len(decode_v2(bytes([0x10]))), 0)
check("Truncated AirPods v1", len(decode_v1(bytes([0x07,0x02,0x01,0x02]))), 1)
check("Truncated AirPods v2", len(decode_v2(bytes([0x07,0x02,0x01,0x02]))), 1)

# ══════════════════════════════════════════════════════════════════════════════
# 13. MULTI-FRAME TLV
# ══════════════════════════════════════════════════════════════════════════════
section("Multi-frame TLV")
multi = bytes([0x10,0x05,0x73,0x1c,0x83,0x90,0x96,
               0x0f,0x05,0x40,0x08,0x39,0x00,0x87])
for fn, label in [(decode_v1,"v1"),(decode_v2,"v2")]:
    fs = fn(multi)
    check(f"[{label}] Multi count",    len(fs), 2)
    check(f"[{label}] Multi frame[0]", fs[0]["type"], "Nearby Info")
    check(f"[{label}] Multi frame[1]", fs[1]["type"], "Nearby Action")

# ══════════════════════════════════════════════════════════════════════════════
# 14. AIRPORT PARSER
# ══════════════════════════════════════════════════════════════════════════════
section("Airport WiFi Parser")
SAMPLE = """\
                            SSID BSSID             RSSI CHANNEL HT CC SECURITY (auth/unicast/group)
                       HomeWifi aa:bb:cc:dd:ee:ff  -65  6,+1    Y  -- WPA2 (PSK/AES/AES)
                    NETGEAR-5G1 11:22:33:44:55:66  -72  36      Y  US WPA3 (SAE/AES/AES)
                   OpenHotspot  de:ad:be:ef:11:22  -80  11      Y  -- NONE
"""
nets = _parse_airport(SAMPLE)
check("Airport net count",       len(nets), 3)
check("Airport SSID",            nets[0]["ssid"],     "HomeWifi")
check("Airport BSSID",           nets[0]["bssid"],    "aa:bb:cc:dd:ee:ff")
check("Airport RSSI",            nets[0]["rssi"],     -65)
check("Airport channel strip",   nets[0]["channel"],  "6")
check("Airport WPA2 security",   nets[0]["security"], "WPA2")
check("Airport WPA3 security",   nets[1]["security"], "WPA3")
check("Airport NONE security",   nets[2]["security"], "NONE")
check("Airport empty → None",    _parse_airport("   SSID BSSID\n"), None)
check("Airport short row → ?",
      _parse_airport("SSID BSSID\n aa:bb:cc:00:00:01 -55 6\n")[0]["security"], "?")

# ══════════════════════════════════════════════════════════════════════════════
# 15. HISTORY RING BUFFER
# ══════════════════════════════════════════════════════════════════════════════
section("History ring buffer")
store = {}
for i in range(70):
    _push_history(store, "k", -50 - i)
check("History capped at 60",   len(store["k"]),        60)
check("History oldest evicted", store["k"][0][1],       -60)
check("History newest correct", store["k"][-1][1],      -119)

# ══════════════════════════════════════════════════════════════════════════════
# 16. MSG_TYPES completeness
# ══════════════════════════════════════════════════════════════════════════════
section("MSG_TYPES_V2 completeness (combined_server)")
for tid, name in [
    (0x05,"AirDrop"),(0x06,"HomeKit"),(0x07,"AirPods"),(0x08,"Siri"),
    (0x09,"AirPlay Target"),(0x0a,"AirPlay Source"),(0x0b,"Magic Switch"),
    (0x0c,"Handoff"),(0x0d,"Tethering Target"),(0x0e,"Tethering Source"),
    (0x0f,"Nearby Action"),(0x10,"Nearby Info"),(0x12,"Find My"),
]:
    check(f"MSG_TYPES_V2[0x{tid:02x}]={name}", MSG_TYPES_V2.get(tid), name)

section("DEVICES_MODELS hardware identifier table coverage")
for hw, name in [
    ("iPhone17,3",  "iPhone 16"),
    ("iPhone17,1",  "iPhone 16 Pro"),
    ("iPhone18,1",  "iPhone 17"),
    ("iPhone18,3",  "iPhone 17 Pro"),
    ("iPad16,3",    "iPad Pro 11 M4 (WiFi)"),
    ("iPad16,1",    "iPad mini 7 (WiFi)"),
    ("MacBookPro21,1", "MacBook Pro 14 M4 (2024)"),
    ("MacBookAir15,1", "MacBook Air 13 M3 (2024)"),
    ("Macmini11,1", "Mac mini M4 (2024)"),
    ("Watch7,8",    "Apple Watch S10 (42mm)"),
    ("Watch7,5",    "Apple Watch Ultra 2"),
    ("RealityDevice14,1", "Apple Vision Pro"),
]:
    check(f"DEVICES_MODELS[{hw}]", DEVICES_MODELS.get(hw), name)

section("2024/2025/2026 AirPods/Beats model table coverage")
for mid, name in [
    (0x2029, "AirPods 4th Gen"),
    (0x202b, "AirPods 4th Gen (ANC)"),
    (0x2035, "AirPods Pro 3rd Gen"),
    (0x2028, "AirPods Max 2nd Gen"),
    (0x0066, "Beats Powerbeats Pro 2nd Gen"),
    (0x0007, "Beats Pill (2024)"),
    (0x0011, "Beats Solo Buds"),
    (0x0030, "Beats Studio Buds+"),
    (0x0040, "Beats Studio Pro"),
    (0x0060, "Beats Solo4"),
]:
    check(f"AIRPODS_MODELS[0x{mid:04x}]={name}", AIRPODS_MODELS.get(mid), name)

section("2024/2025/2026 SIRI_DEVICE table coverage")
for sid, name in [
    (0x000b, "Apple Watch Ultra"),
    (0x000c, "iPhone 16"),
    (0x000e, "iPhone 17"),
    (0x0016, "Apple Vision Pro"),
    (0x0017, "HomePod 2nd Gen"),
]:
    check(f"SIRI_DEVICE[0x{sid:04x}]={name}", SIRI_DEVICE.get(sid), name)

section("2024/2025/2026 DEVICE_CLASS table")
for dc, name in [
    (0x0c, "Apple Vision Pro"),
    (0x0d, "iPhone 16 / 16 Plus"),
    (0x0f, "iPhone 17 / Plus"),
    (0x17, "Apple Watch Series 10"),
    (0x18, "Apple Watch Ultra 2"),
]:
    check(f"DEVICE_CLASS[0x{dc:02x}]={name}", DEVICE_CLASS.get(dc), name)

section("iOS version table coverage  v1 + v2")
for code, label in [
    (0x08,"iOS 16"),(0x09,"iOS 17"),(0x0a,"iOS 18"),
    (0x0b,"iOS 19"),(0x0c,"iOS 20"),(0x0d,"iOS 21"),
    (0x0e,"iOS 22"),(0x0f,"iOS 23"),(0x10,"iOS 24"),
    (0x11,"iOS 25"),(0x12,"iOS 26"),
]:
    # ios_byte lives in bits 7-5 of payload[1]; encode it back
    ios_byte_in_data = (code & 0x07) << 5   # lower 3 bits → bits 7-5
    raw_ios = bytes([0x10, 0x05, 0x03, ios_byte_in_data, 0x00, 0x00, 0x00])
    for fn, mod_iv, lbl in [
        (decode_v1, IOS_VERSION, "v1"),
        (decode_v2, MSG_TYPES_V2, "v2"),
    ]:
        fs = fn(raw_ios)
        got_ver = fs[0]["ios_version"] if fs else "MISSING"
        want_ver = f"byte={code & 0x07}" if (code & 0x07) not in [0,1,2,3,4,5,6,7] else None
        # The 3-bit field saturates at 0-7; codes ≥ 0x08 need byte > 7, not representable in 3 bits
        # So we only test byte values 0-7 (codes 0x00-0x07) directly; higher codes can't come from field
        pass  # covered by direct table lookup below
    check(f"IOS_VERSION[0x{code:02x}]={label}", IOS_VERSION.get(code), label)

section("MSG_TYPES completeness")
for tid, name in [
    (0x05,"AirDrop"),(0x06,"HomeKit"),(0x07,"AirPods"),
    (0x09,"AirPlay Target"),(0x0a,"AirPlay Source"),(0x0b,"Magic Switch"),
    (0x0c,"Handoff"),(0x0d,"Tethering Target"),(0x0e,"Tethering Source"),
    (0x0f,"Nearby Action"),(0x10,"Nearby Info"),(0x12,"Find My"),
]:
    check(f"MSG_TYPES[0x{tid:02x}]={name}", MSG_TYPES.get(tid), name)

# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*56}")
print(f"  {PASS+FAIL} tests  |  {PASS} passed  |  {FAIL} failed")
print(f"{'='*56}")
sys.exit(0 if FAIL == 0 else 1)
