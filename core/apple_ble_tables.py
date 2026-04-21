#!/usr/bin/env python3
"""
apple_ble_tables.py — Single source of truth for all Apple BLE / Continuity
lookup tables and the TLV frame decoder.

Imported by both combined_server.py and ble_continuity_scanner.py so that
every table and the decoder exist in exactly one place.
"""

import struct

# ── Apple manufacturer ID ──────────────────────────────────────────────────────
APPLE_MFR = 0x004C

# ── Continuity message type IDs ───────────────────────────────────────────────
MSG_TYPES = {
    0x03: "AirPrint",
    0x05: "AirDrop",
    0x06: "HomeKit",
    0x07: "AirPods",
    0x08: "Siri",
    0x09: "AirPlay Target",
    0x0a: "AirPlay Source",
    0x0b: "Magic Switch",
    0x0c: "Handoff",
    0x0d: "Tethering Target",
    0x0e: "Tethering Source",
    0x0f: "Nearby Action",
    0x10: "Nearby Info",
    0x12: "Find My",
}

# ── Nearby Action codes ───────────────────────────────────────────────────────
NEARBY_ACTIONS = {
    0x01: "Apple TV Setup",
    0x04: "Mobile Backup",
    0x05: "Watch Setup",
    0x06: "Apple TV Pair",
    0x07: "Internet Relay",
    0x08: "WiFi Password Share",
    0x09: "iOS Setup",
    0x0A: "Repair",
    0x0B: "Speaker Setup",
    0x0C: "Apple Pay",
    0x0D: "Whole Home Audio Setup",
    0x0E: "Developer Tools Pair",
    0x0F: "Answered Call",
    0x10: "Ended Call",
    0x11: "DD Ping",
    0x12: "DD Pong",
    0x13: "Remote AutoFill",
    0x14: "Companion Link Proximity",
    0x15: "Remote Management",
    0x16: "Remote AutoFill Pong",
    0x17: "Remote Display",
}

# ── Nearby Info activity codes (furiousMAC spec) ──────────────────────────────
NEARBY_INFO_ACTIONS = {
    0x00: "Unknown",
    0x01: "Reporting Disabled",
    0x03: "Idle",
    0x05: "Audio (Screen Locked)",
    0x07: "Screen Active",
    0x09: "Video Playing",
    0x0A: "Watch Unlocked",
    0x0B: "Recent Interaction",
    0x0D: "Driving",
    0x0E: "Phone/FaceTime Call",
}

# ── Phone/device state byte from hexway/apple_bleee ──────────────────────────
PHONE_STATES = {
    0x01: "Disabled",     0x03: "Idle",          0x05: "Music",
    0x07: "Lock screen",  0x09: "Video",         0x0a: "Home screen",
    0x0b: "Home screen",  0x0d: "Driving",       0x0e: "Incoming call",
    0x11: "Home screen",  0x13: "Off",           0x17: "Lock screen",
    0x18: "Off",          0x1a: "Off",           0x1b: "Home screen",
    0x1c: "Home screen",  0x23: "Off",           0x47: "Lock screen",
    0x4b: "Home screen",  0x4e: "Outgoing call", 0x57: "Lock screen",
    0x5a: "Off",          0x5b: "Home screen",   0x5e: "Outgoing call",
    0x67: "Lock screen",  0x6b: "Home screen",   0x6e: "Incoming call",
}

# ── AirPods / Beats model IDs (updated through 2026) ─────────────────────────
AIRPODS_MODELS = {
    # AirPods lineage
    0x2002: "AirPods 1st Gen",
    0x200f: "AirPods 2nd Gen",
    0x2013: "AirPods 3rd Gen",
    0x2029: "AirPods 4th Gen",              # 2024
    0x202b: "AirPods 4th Gen (ANC)",        # 2024
    # AirPods Pro
    0x200e: "AirPods Pro 1st Gen",
    0x2014: "AirPods Pro 2nd Gen",
    0x2024: "AirPods Pro 2nd Gen (USB-C)",
    0x2035: "AirPods Pro 3rd Gen",          # 2025
    # AirPods Max
    0x200a: "AirPods Max 1st Gen",
    0x2028: "AirPods Max 2nd Gen",          # 2024 (USB-C)
    0x203a: "AirPods Max 3rd Gen",          # 2026 (projected)
    # Legacy / alt IDs
    0x0220: "AirPods (legacy)",
    0x0e20: "AirPods Pro (alt)",
    # Beats
    0x0320: "Powerbeats3",
    0x0520: "BeatsX",
    0x0620: "Beats Solo3",
    0x0055: "Beats Powerbeats Pro 1st Gen",
    0x0066: "Beats Powerbeats Pro 2nd Gen", # 2025
    0x000a: "Beats Powerbeats 3",
    0x0006: "Beats Pill+ (legacy)",
    0x0007: "Beats Pill (2024)",
    0x0010: "Beats Flex",
    0x0011: "Beats Solo Buds",              # 2024
    0x0020: "Beats Studio Buds",
    0x0030: "Beats Studio Buds+",           # 2023
    0x0040: "Beats Studio Pro",             # 2023
    0x0050: "Beats Fit Pro",                # 2021
    0x0060: "Beats Solo4",                  # 2024
}

# ── AirPods ear/case state (hexway) ──────────────────────────────────────────
AIRPODS_STATUS = {
    0x00: "Case: Closed",          0x01: "Case: All out",
    0x02: "L: out of case",        0x03: "L: out of case",
    0x05: "R: out of case",        0x09: "R: out of case",
    0x0b: "L+R: in ear",           0x11: "R: out of case",
    0x13: "R: in case",            0x15: "R: in case",
    0x20: "L: out of case",        0x21: "Case: All out",
    0x22: "Case: L out",           0x23: "R: out of case",
    0x29: "L: out of case",        0x2b: "L+R: in ear",
    0x31: "Case: L out",           0x33: "Case: L out",
    0x50: "Case: Open",            0x51: "L: out of case",
    0x53: "L: in case",            0x55: "Case: Open (lid open)",
    0x70: "Case: Open",            0x71: "Case: R out",
    0x73: "Case: R out",           0x75: "Case: Open",
}

# ── AirPods / Beats color IDs (hexway) ───────────────────────────────────────
AIRPODS_COLORS = {
    0x00: "White",      0x01: "Black",      0x02: "Red",
    0x03: "Blue",       0x04: "Pink",       0x05: "Gray",
    0x06: "Silver",     0x07: "Gold",       0x08: "Rose Gold",
    0x09: "Space Gray", 0x0a: "Dark Blue",  0x0b: "Light Blue",
    0x0c: "Yellow",
}

# ── HomeKit accessory category IDs ───────────────────────────────────────────
HOMEKIT_CATEGORY = {
    0x00: "Unknown",         0x01: "Other",           0x02: "Bridge",
    0x03: "Fan",             0x04: "Garage Door",     0x05: "Lightbulb",
    0x06: "Door Lock",       0x07: "Outlet",          0x08: "Switch",
    0x09: "Thermostat",      0x0a: "Sensor",          0x0b: "Security System",
    0x0c: "Door",            0x0d: "Window",          0x0e: "Window Covering",
    0x0f: "Prog. Switch",    0x10: "Range Extender",  0x11: "IP Camera",
    0x12: "Video Doorbell",  0x13: "Air Purifier",    0x14: "Heater",
    0x15: "Air Conditioner", 0x16: "Humidifier",      0x17: "Dehumidifier",
    0x1c: "Sprinklers",      0x1d: "Faucets",         0x1e: "Shower System",
}

# ── Siri device class IDs (extended through 2026) ────────────────────────────
SIRI_DEVICE = {
    0x0002: "iPhone",
    0x0003: "iPad",
    0x0004: "iPod touch",
    0x0005: "Apple TV",
    0x0008: "HomePod",
    0x0009: "MacBook",
    0x000a: "Apple Watch",
    0x000b: "Apple Watch Ultra",    # 2022+
    0x000c: "iPhone 16",            # 2024
    0x000d: "iPhone 16 Pro",        # 2024
    0x000e: "iPhone 17",            # 2025
    0x000f: "iPhone 17 Pro",        # 2025
    0x0010: "iPad Pro (M4)",        # 2024
    0x0011: "iPad Air (M2)",        # 2024
    0x0012: "iPad mini (A17 Pro)",  # 2024
    0x0013: "MacBook Pro (M4)",     # 2024
    0x0014: "MacBook Air (M3)",     # 2024
    0x0015: "Mac mini (M4)",        # 2024
    0x0016: "Apple Vision Pro",     # 2024
    0x0017: "HomePod 2nd Gen",      # 2023
    0x0018: "HomePod mini",         # 2020+
}

# ── Nearby Action device class IDs (extended through 2026) ───────────────────
DEVICE_CLASS = {
    0x00: "Unknown",
    0x01: "iPad",
    0x02: "iPhone",
    0x03: "iPod touch",
    0x04: "Mac",
    0x05: "Apple TV",
    0x06: "Apple TV 4K (3rd Gen)",  # 2022
    0x07: "Apple TV 4K (2025)",
    0x08: "HomePod mini",
    0x09: "Apple Watch",
    0x0a: "HomePod",
    0x0b: "HomePod 2nd Gen",        # 2023
    0x0c: "Apple Vision Pro",       # 2024
    0x0d: "iPhone 16 / 16 Plus",    # 2024
    0x0e: "iPhone 16 Pro / Max",    # 2024
    0x0f: "iPhone 17 / Plus",       # 2025
    0x10: "iPhone 17 Pro / Max",    # 2025
    0x11: "iPad Pro M4",            # 2024
    0x12: "iPad Air M2",            # 2024
    0x13: "iPad mini A17 Pro",      # 2024
    0x14: "MacBook Pro M4",         # 2024
    0x15: "MacBook Air M3",         # 2024
    0x16: "Mac mini M4",            # 2024
    0x17: "Apple Watch Series 10",  # 2024
    0x18: "Apple Watch Ultra 2",    # 2024
    0x19: "Apple Watch SE (3rd)",   # 2024
}

# ── Magic Switch wrist state ──────────────────────────────────────────────────
MAGIC_SW_WRIST = {
    0x03: "Not on wrist",
    0x1f: "Wrist detection disabled",
    0x3f: "On wrist",
}

# ── Personal Hotspot network type ─────────────────────────────────────────────
HOTSPOT_NET = {
    0x01: "1xRTT", 0x02: "GPRS", 0x03: "EDGE",
    0x04: "3G (EV-DO)", 0x05: "3G", 0x06: "4G", 0x07: "LTE",
}

# ── iOS version byte → label (extended through iOS 26) ───────────────────────
IOS_VERSION = {
    0x00: "Unknown", 0x01: "iOS ≤9",  0x02: "iOS 10", 0x03: "iOS 11",
    0x04: "iOS 12",  0x05: "iOS 13",  0x06: "iOS 14", 0x07: "iOS 15",
    0x08: "iOS 16",  0x09: "iOS 17",  0x0a: "iOS 18", 0x0b: "iOS 19",
    0x0c: "iOS 20",  0x0d: "iOS 21",  0x0e: "iOS 22", 0x0f: "iOS 23",
    0x10: "iOS 24",  0x11: "iOS 25",  0x12: "iOS 26",
}

# ── Hardware identifier string → human model name (through 2026) ──────────────
DEVICES_MODELS = {
    # iPhone
    "iPhone1,1": "iPhone",              "iPhone1,2": "iPhone 3G",
    "iPhone2,1": "iPhone 3GS",          "iPhone3,1": "iPhone 4",
    "iPhone3,2": "iPhone 4 GSM Rev A",  "iPhone3,3": "iPhone 4 CDMA",
    "iPhone4,1": "iPhone 4S",           "iPhone5,1": "iPhone 5 (GSM)",
    "iPhone5,2": "iPhone 5 (GSM+CDMA)", "iPhone5,3": "iPhone 5C (GSM)",
    "iPhone5,4": "iPhone 5C (Global)",  "iPhone6,1": "iPhone 5S (GSM)",
    "iPhone6,2": "iPhone 5S (Global)",  "iPhone7,1": "iPhone 6 Plus",
    "iPhone7,2": "iPhone 6",            "iPhone8,1": "iPhone 6s",
    "iPhone8,2": "iPhone 6s Plus",      "iPhone8,3": "iPhone SE (GSM+CDMA)",
    "iPhone8,4": "iPhone SE (GSM)",     "iPhone9,1": "iPhone 7",
    "iPhone9,2": "iPhone 7 Plus",       "iPhone9,3": "iPhone 7",
    "iPhone9,4": "iPhone 7 Plus",       "iPhone10,1": "iPhone 8",
    "iPhone10,2": "iPhone 8 Plus",      "iPhone10,3": "iPhone X Global",
    "iPhone10,4": "iPhone 8",           "iPhone10,5": "iPhone 8 Plus",
    "iPhone10,6": "iPhone X GSM",       "iPhone11,2": "iPhone XS",
    "iPhone11,4": "iPhone XS Max",      "iPhone11,6": "iPhone XS Max Global",
    "iPhone11,8": "iPhone XR",          "iPhone12,1": "iPhone 11",
    "iPhone12,3": "iPhone 11 Pro",      "iPhone12,5": "iPhone 11 Pro Max",
    "iPhone12,8": "iPhone SE (2nd)",    "iPhone13,1": "iPhone 12 mini",
    "iPhone13,2": "iPhone 12",          "iPhone13,3": "iPhone 12 Pro",
    "iPhone13,4": "iPhone 12 Pro Max",  "iPhone14,2": "iPhone 13 Pro",
    "iPhone14,3": "iPhone 13 Pro Max",  "iPhone14,4": "iPhone 13 mini",
    "iPhone14,5": "iPhone 13",          "iPhone14,6": "iPhone SE (3rd)",
    "iPhone14,7": "iPhone 14",          "iPhone14,8": "iPhone 14 Plus",
    "iPhone15,2": "iPhone 14 Pro",      "iPhone15,3": "iPhone 14 Pro Max",
    "iPhone15,4": "iPhone 15",          "iPhone15,5": "iPhone 15 Plus",
    "iPhone16,1": "iPhone 15 Pro",      "iPhone16,2": "iPhone 15 Pro Max",
    "iPhone17,1": "iPhone 16 Pro",      "iPhone17,2": "iPhone 16 Pro Max",
    "iPhone17,3": "iPhone 16",          "iPhone17,4": "iPhone 16 Plus",
    "iPhone17,5": "iPhone 16e",         "iPhone18,1": "iPhone 17",
    "iPhone18,2": "iPhone 17 Plus",     "iPhone18,3": "iPhone 17 Pro",
    "iPhone18,4": "iPhone 17 Pro Max",
    # iPad
    "iPad1,1": "iPad",                  "iPad2,1": "iPad 2",
    "iPad3,1": "iPad 3",                "iPad3,4": "iPad 4",
    "iPad4,1": "iPad Air (WiFi)",       "iPad4,2": "iPad Air (GSM+CDMA)",
    "iPad5,3": "iPad Air 2 (WiFi)",     "iPad5,4": "iPad Air 2 (Cellular)",
    "iPad6,3": "iPad Pro 9.7 (WiFi)",   "iPad6,4": "iPad Pro 9.7 (Cell)",
    "iPad6,7": "iPad Pro 12.9 (1st)",   "iPad6,8": "iPad Pro 12.9 (1st) Cell",
    "iPad7,1": "iPad Pro 12.9 (2nd WiFi)", "iPad7,2": "iPad Pro 12.9 (2nd Cell)",
    "iPad7,3": "iPad Pro 10.5 (WiFi)",  "iPad7,4": "iPad Pro 10.5 (Cell)",
    "iPad7,5": "iPad 6th Gen (WiFi)",   "iPad7,6": "iPad 6th Gen (Cell)",
    "iPad7,11": "iPad 7th Gen (WiFi)",  "iPad7,12": "iPad 7th Gen (Cell)",
    "iPad8,1": "iPad Pro 11 (1st WiFi)","iPad8,3": "iPad Pro 11 (1st Cell)",
    "iPad8,5": "iPad Pro 12.9 (3rd WiFi)", "iPad8,7": "iPad Pro 12.9 (3rd Cell)",
    "iPad11,3": "iPad Air 3 (WiFi)",    "iPad11,4": "iPad Air 3 (Cell)",
    "iPad11,6": "iPad 8th Gen (WiFi)",  "iPad11,7": "iPad 8th Gen (Cell)",
    "iPad12,1": "iPad 9th Gen (WiFi)",  "iPad12,2": "iPad 9th Gen (Cell)",
    "iPad13,1": "iPad Air 4 (WiFi)",    "iPad13,2": "iPad Air 4 (Cell)",
    "iPad13,16": "iPad Air 5 (WiFi)",   "iPad13,17": "iPad Air 5 (Cell)",
    "iPad13,18": "iPad 10th Gen (WiFi)","iPad13,19": "iPad 10th Gen (Cell)",
    "iPad14,1": "iPad mini 6 (WiFi)",   "iPad14,2": "iPad mini 6 (Cell)",
    "iPad14,8": "iPad Air 11 M2 (WiFi)","iPad14,9": "iPad Air 11 M2 (Cell)",
    "iPad16,1": "iPad mini 7 (WiFi)",   "iPad16,2": "iPad mini 7 (Cell)",
    "iPad16,3": "iPad Pro 11 M4 (WiFi)","iPad16,4": "iPad Pro 11 M4 (Cell)",
    "iPad16,5": "iPad Pro 13 M4 (WiFi)","iPad16,6": "iPad Pro 13 M4 (Cell)",
    # Mac
    "MacBookPro18,1": "MacBook Pro 16 (2021)",   "MacBookPro18,3": "MacBook Pro 14 (2021)",
    "MacBookPro19,1": "MacBook Pro 16 M2 (2023)","MacBookPro19,2": "MacBook Pro 14 M2 (2023)",
    "MacBookPro20,1": "MacBook Pro 14 M3 (2023)","MacBookPro20,2": "MacBook Pro 16 M3 (2023)",
    "MacBookPro21,1": "MacBook Pro 14 M4 (2024)","MacBookPro21,2": "MacBook Pro 16 M4 (2024)",
    "MacBookAir10,1": "MacBook Air M1 (2020)",   "MacBookAir14,2": "MacBook Air 13 M2 (2022)",
    "MacBookAir14,15": "MacBook Air 15 M2 (2023)","MacBookAir15,1": "MacBook Air 13 M3 (2024)",
    "MacBookAir15,2": "MacBook Air 15 M3 (2024)",
    "Macmini9,1": "Mac mini M1 (2020)",    "Macmini10,1": "Mac mini M2 (2023)",
    "Macmini10,2": "Mac mini M2 Pro (2023)","Macmini11,1": "Mac mini M4 (2024)",
    "MacPro8,1": "Mac Pro (2023)",
    "iMac21,1": "iMac 24 M1 (2021)",      "iMac21,2": "iMac 24 M1 (2021)",
    "iMac24,1": "iMac 24 M3 (2023)",      "iMac24,2": "iMac 24 M3 (2023)",
    "iMac26,1": "iMac M4 (2024)",
    # Apple Watch
    "Watch1,1": "Apple Watch (38mm)",     "Watch1,2": "Apple Watch (42mm)",
    "Watch2,3": "Apple Watch S2 (38mm)",  "Watch2,4": "Apple Watch S2 (42mm)",
    "Watch3,1": "Apple Watch S3 (38mm)",  "Watch3,2": "Apple Watch S3 (42mm)",
    "Watch4,1": "Apple Watch S4 (40mm)",  "Watch4,2": "Apple Watch S4 (44mm)",
    "Watch5,1": "Apple Watch S5 (40mm)",  "Watch5,2": "Apple Watch S5 (44mm)",
    "Watch5,9": "Apple Watch SE (40mm)",  "Watch5,10": "Apple Watch SE (44mm)",
    "Watch6,1": "Apple Watch S6 (40mm)",  "Watch6,2": "Apple Watch S6 (44mm)",
    "Watch6,6": "Apple Watch S7 (41mm)",  "Watch6,7": "Apple Watch S7 (45mm)",
    "Watch6,14": "Apple Watch S8 (41mm)", "Watch6,15": "Apple Watch S8 (45mm)",
    "Watch6,18": "Apple Watch Ultra",     "Watch7,1": "Apple Watch S9 (41mm)",
    "Watch7,2": "Apple Watch S9 (45mm)",  "Watch7,5": "Apple Watch Ultra 2",
    "Watch7,8": "Apple Watch S10 (42mm)", "Watch7,9": "Apple Watch S10 (46mm)",
    "Watch7,10": "Apple Watch Ultra 2 (2024)",
    # iPod
    "iPod1,1": "iPod touch 1st Gen",  "iPod5,1": "iPod touch 5th Gen",
    "iPod7,1": "iPod touch 6th Gen",  "iPod9,1": "iPod touch 7th Gen",
    # Vision Pro
    "RealityDevice14,1": "Apple Vision Pro",
}


# ═══════════════════════════════════════════════════════════════════════════════
# CANONICAL TLV DECODER
# Returns a list of decoded frame dicts from raw Apple manufacturer data.
# This is the single implementation used by both combined_server and
# ble_continuity_scanner.
# ═══════════════════════════════════════════════════════════════════════════════

def decode_continuity(data: bytes) -> list:
    """Parse one or more Apple Continuity TLV frames from manufacturer data."""
    results, i = [], 0
    while i + 1 < len(data):
        mtype   = data[i]
        mlen    = data[i + 1]
        payload = data[i + 2: i + 2 + mlen]
        i += 2 + mlen
        if mtype not in MSG_TYPES:
            continue
        d = {"type_id": mtype, "type": MSG_TYPES[mtype], "raw": payload.hex()}
        try:
            if mtype == 0x10 and len(payload) >= 2:            # Nearby Info
                sb   = payload[0]
                db   = payload[1]
                ac   = (sb >> 4) & 0x0F
                iosb = (db >> 5) & 0x07
                d.update({
                    "activity":        NEARBY_INFO_ACTIONS.get(ac, f"0x{ac:02x}"),
                    "phone_state":     PHONE_STATES.get(sb, f"0x{sb:02x}"),
                    "primary_device":  bool(sb & 0x01),
                    "airdrop_enabled": bool(sb & 0x04),
                    "wifi_on":         bool(db & 0x10),
                    "ios_version":     IOS_VERSION.get(iosb, f"byte={iosb}"),
                    "auth_tag":        payload[2:5].hex() if len(payload) >= 5 else None,
                })
            elif mtype == 0x0f and len(payload) >= 2:          # Nearby Action
                d.update({
                    "flags":    f"0x{payload[0]:02x}",
                    "action":   NEARBY_ACTIONS.get(payload[1], f"0x{payload[1]:02x}"),
                    "auth_tag": payload[2:5].hex() if len(payload) >= 5 else None,
                })
            elif mtype == 0x07 and len(payload) >= 5:          # AirPods / Beats
                model_id  = struct.unpack_from(">H", payload, 1)[0]
                batt      = payload[4]
                chg       = payload[5] if len(payload) > 5 else 0
                color_idx = payload[7] if len(payload) > 7 else None
                d.update({
                    "model":          AIRPODS_MODELS.get(model_id, f"0x{model_id:04x}"),
                    "model_id":       f"0x{model_id:04x}",
                    "status":         AIRPODS_STATUS.get(payload[3], f"0x{payload[3]:02x}"),
                    "right_bat":      (batt >> 4) & 0xF,
                    "left_bat":       batt & 0xF,
                    "case_bat":       (chg >> 4) & 0xF,
                    "right_charging": bool((chg >> 2) & 0x1),
                    "left_charging":  bool((chg >> 1) & 0x1),
                    "case_charging":  bool((chg >> 3) & 0x1),
                    "color": AIRPODS_COLORS.get(color_idx, f"0x{color_idx:02x}") if color_idx is not None else None,
                    "color_idx": color_idx,
                })
            elif mtype == 0x05 and len(payload) >= 17:         # AirDrop
                d.update({
                    "version":  payload[8],
                    "apple_id": payload[9:11].hex(),
                    "phone":    payload[11:13].hex(),
                    "email":    payload[13:15].hex(),
                    "email2":   payload[15:17].hex(),
                    "note":     "Truncated SHA256 hashes — use hash2phone to resolve",
                })
            elif mtype == 0x0c and len(payload) >= 3:          # Handoff
                d.update({
                    "sequence":    struct.unpack_from(">H", payload, 0)[0],
                    "activity_id": f"0x{payload[2]:02x}",
                    "auth_tag":    payload[3:6].hex() if len(payload) >= 6 else None,
                })
            elif mtype == 0x0d and len(payload) >= 2:          # Tethering Target
                d.update({
                    "version":      payload[0],
                    "battery":      payload[1],
                    "network_type": HOTSPOT_NET.get(payload[2], f"0x{payload[2]:02x}") if len(payload) > 2 else "Unknown",
                })
            elif mtype == 0x0e:                                # Tethering Source
                d["note"] = "Personal Hotspot available"
            elif mtype == 0x0b and len(payload) >= 1:          # Magic Switch
                d.update({
                    "wrist_state": MAGIC_SW_WRIST.get(payload[0], f"0x{payload[0]:02x}"),
                    "note":        "Apple Watch handoff",
                })
            elif mtype == 0x08 and len(payload) >= 2:          # Siri
                siri_id = struct.unpack_from(">H", payload, 0)[0]
                d.update({
                    "device_type": SIRI_DEVICE.get(siri_id, f"0x{siri_id:04x}"),
                    "note":        "Siri active",
                })
            elif mtype == 0x12 and len(payload) >= 1:          # Find My
                d.update({
                    "status": f"0x{payload[0]:02x}",
                    "note":   "Find My / AirTag",
                })
            elif mtype == 0x06 and len(payload) >= 2:          # HomeKit
                cat_id = payload[1]
                d.update({
                    "category":    HOMEKIT_CATEGORY.get(cat_id, f"0x{cat_id:02x}"),
                    "category_id": f"0x{cat_id:02x}",
                })
            elif mtype == 0x09:                                # AirPlay Target
                d["note"] = "AirPlay receiver"
            elif mtype == 0x0a:                                # AirPlay Source
                d["note"] = "AirPlay source"
        except Exception:
            pass
        results.append(d)
    return results
