# SPECTRE — Tools

Standalone utilities and legacy scripts. None are required to run the main SPECTRE dashboard.

| File | Description |
|---|---|
| `ble_continuity_scanner.py` | Standalone BLE-only server on port 5002 (pre-dates combined_server.py) |
| `wifi_web_server.py` | Standalone WiFi-only server on port 5001 (pre-dates combined_server.py) |
| `macos_beacon.py` | 802.11 beacon flood using Scapy (macOS, requires sudo + scapy) |
| `wifi_visualizer.py` | Passive Scapy beacon sniffer — prints SSIDs/RSSI to terminal |
| `wifi_visualizer_final.py` | Same as above but disconnects airport first for passive listening |
| `ssid_visualizer_gui.py` | Pygame-based animated WiFi visualiser (legacy, requires pygame) |
| `config.py` | Config constants for ssid_visualizer_gui.py |

## Run standalone servers

```bash
# BLE-only dashboard (port 5002)
.venv/bin/python tools/ble_continuity_scanner.py

# WiFi-only dashboard (port 5001)
.venv/bin/python tools/wifi_web_server.py
```

## Run beacon sniffer (macOS, requires scapy)

```bash
pip install scapy
sudo .venv/bin/python tools/wifi_visualizer_final.py
```

## Run beacon flood (macOS, requires scapy + sudo)

```bash
sudo .venv/bin/python tools/macos_beacon.py
```
