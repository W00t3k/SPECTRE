# 👻 SPECTRE — Signal & Protocol Exploitation, Capture, Tracking, Recon Engine

Real-time Apple Continuity BLE scanner + WiFi radar in a single cyberpunk web dashboard.
Decodes every Apple BLE frame type using the **furiousMAC/continuity** spec and the
**hexway/apple_bleee** lookup tables.

> **For Raspberry Pi + offensive tooling (wifite / eaphammer) deployment, see [Pi Setup](#raspberry-pi-offensive-setup) below.**

---

## Features

| Feature | Detail |
|---|---|
| **BLE Continuity decoding** | Nearby Info, Nearby Action, AirPods/Beats, AirDrop, Handoff, Hotspot, HomeKit, Siri, Magic Switch, Find My, AirPlay |
| **Phone state** | 28 states — Lock Screen, Driving, Incoming Call, Outgoing Call, Music, Video… |
| **AirPods** | Model, L/R/Case battery %, charging status, color (White/Black/Rose Gold/Space Gray…), case open/closed/in-ear state (25 states) |
| **AirDrop** | SHA256 hash prefixes for Apple ID / phone / email with COPY buttons + hash2phone note |
| **HomeKit** | 28 category names (Lightbulb, Door Lock, IP Camera, Video Doorbell…) |
| **Hotspot** | Network type (LTE / 4G / 3G / EDGE / GPRS) |
| **Magic Switch** | Apple Watch wrist detection state |
| **Siri** | Device type (iPhone / iPad / MacBook / Apple Watch) |
| **WiFi Radar** | Spinning radar with ripple pings, RSSI bars, channel map, WPA3/Open badges |
| **LOST devices** | BLE devices ghost-out after 2 min and are labelled LOST |
| **Timeline** | RSSI history charts (WiFi + BLE), Nearby Info activity heatmap |
| **Export** | JSON/CSV download for WiFi, BLE, events |
| **Alerts** | Open WiFi, AirDrop, hotspot detection with macOS notifications |

---

## Requirements

### macOS
- macOS 12+ (Monterey or later) with Bluetooth
- Python 3.9+
- Bluetooth permission granted to Terminal / iTerm

### Raspberry Pi
- Raspberry Pi OS Bookworm (64-bit recommended)
- Python 3.9+
- **USB BLE dongle recommended** — better range + avoids Pi's power-limited built-in
  - Tested: Asus USB-BT500 (BT 5.0), Plugable USB-BT4LE, IOGEAR GBU521
  - Any CSR8510 / RTL8761B chipset USB dongle works
- The server **auto-detects USB dongles** and prefers them over the built-in UART adapter

---

## Quick Start (macOS)

```bash
cd "MACOS WIFIZ"
bash setup.sh     # creates .venv, installs deps, runs 150 regression tests
bash run.sh       # runs tests then starts server at http://localhost:5003
```

Open **http://localhost:5003** in your browser.

---

## Quick Start (Raspberry Pi)

```bash
# 1. Clone / copy files to Pi
scp -r "MACOS WIFIZ" pi@raspberrypi.local:~/rf-dashboard

# 2. SSH in
ssh pi@raspberrypi.local
cd ~/rf-dashboard

# 3. One-shot setup (installs bluez, creates venv, tests)
bash setup.sh

# 4. Launch (auto-brings up hci0)
bash run.sh

# 5. Open on any machine on same network:
#    http://raspberrypi.local:5003
```

For headless Pi auto-start on boot:
```bash
# Add to /etc/rc.local before exit 0:
cd /home/pi/rf-dashboard && bash run.sh &
```

Or use systemd:
```bash
sudo tee /etc/systemd/system/rfdashboard.service <<EOF
[Unit]
Description=RF Dashboard
After=bluetooth.target network.target

[Service]
WorkingDirectory=/home/pi/rf-dashboard
ExecStart=/home/pi/rf-dashboard/.venv/bin/python combined_server.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable rfdashboard
sudo systemctl start rfdashboard
```

---

## Run Tests Only

```bash
bash run.sh --test-only
# or directly:
.venv/bin/python test_ble.py
```

---

## Project Structure

```
MACOS WIFIZ/
├── combined_server.py        # Flask+SocketIO backend (WiFi + BLE)
├── ble_continuity_scanner.py # Standalone BLE scanner (port 5002)
├── wifi_web_server.py        # Standalone WiFi server (port 5001)
├── test_ble.py               # 150-test regression suite
├── setup.sh                  # One-shot installer (macOS + Pi)
├── run.sh                    # Zero-interaction launcher
├── static/
│   ├── dashboard.html        # Unified tabbed dashboard (WiFi+BLE)
│   ├── ble.html              # Standalone BLE dashboard
│   └── index.html            # Standalone WiFi radar
└── README.md
```

---

## BLE Frame Types Decoded

| Type | Hex | Source |
|---|---|---|
| AirPrint | 0x03 | Apple |
| AirDrop | 0x05 | furiousMAC + hexway |
| HomeKit | 0x06 | hexway |
| AirPods / Beats | 0x07 | furiousMAC + hexway |
| Siri | 0x08 | hexway |
| AirPlay Target | 0x09 | Apple |
| AirPlay Source | 0x0a | Apple |
| Magic Switch | 0x0b | hexway |
| Handoff | 0x0c | furiousMAC |
| Tethering Target | 0x0d | hexway |
| Tethering Source | 0x0e | hexway |
| Nearby Action | 0x0f | furiousMAC |
| Nearby Info | 0x10 | furiousMAC + hexway |
| Find My | 0x12 | Apple |

---

## Pi USB BLE Dongle Troubleshooting

```bash
# Check if dongle is detected by OS
lsusb | grep -i bluetooth

# List all HCI adapters (hci0=built-in, hci1=USB dongle typically)
hciconfig -a

# Manually bring up a specific adapter
sudo hciconfig hci1 up

# Check which adapter bleak will use
python3 -c "import asyncio; from bleak import BleakScanner; \
  async def s(): return await BleakScanner.discover(timeout=3.0); \
  print(asyncio.run(s()))"

# If permission denied without sudo, add user to bluetooth group:
sudo usermod -aG bluetooth $USER
# Then log out and back in

# Force a specific adapter (override auto-detect):
export BLE_ADAPTER=hci1   # set before running combined_server.py
```

If you have **two adapters** (built-in + USB dongle), the server automatically picks
the USB one. If you want to force a specific one, edit `combined_server.py` and set
`kwargs["adapter"] = "hci1"` at the top of `_ble_loop()`.

---

## References

- [furiousMAC/continuity](https://github.com/furiousMAC/continuity) — Continuity protocol RE
- [hexway/apple_bleee](https://github.com/hexway/apple_bleee) — BLE state decoding tables
- [bleak](https://github.com/hbldh/bleak) — Cross-platform BLE (CoreBluetooth on macOS, BlueZ on Pi)

---

## Raspberry Pi Offensive Setup

Deploy SPECTRE on a Pi alongside wifite + eaphammer for full passive+active recon.

### Hardware
- Raspberry Pi 4/5 running Kali Linux ARM
- **Alfa AWUS036ACH** or **AWUS036NHA** USB WiFi adapter (monitor mode capable)
- USB BLE dongle (CSR8510 / RTL8761B) for BLE scanning

### Install offensive tools (Kali Pi)
```bash
sudo apt update && sudo apt install -y wifite aircrack-ng reaver bully hcxtools hashcat eaphammer
```

### Deploy SPECTRE on Pi
```bash
scp -r "MACOS WIFIZ" pi@raspberrypi.local:~/spectre
ssh pi@raspberrypi.local
cd ~/spectre && bash setup.sh && bash run.sh
# Dashboard: http://raspberrypi.local:5003
```

### Enable monitor mode
```bash
sudo airmon-ng check kill
sudo airmon-ng start wlan1   # wlan1 = your Alfa adapter
# Creates wlan1mon
```

### Run wifite (WPA2-PSK / WPS targets)
```bash
sudo wifite -i wlan1mon --wpa --dict /usr/share/wordlists/rockyou.txt
```

### Run eaphammer (WPA2-Enterprise targets)
```bash
cd /opt/eaphammer
sudo ./eaphammer --cert-wizard
sudo ./eaphammer -i wlan1 --channel 6 --auth wpa-eap --essid "TargetCorp" --creds
```

### Autostart SPECTRE on boot
```bash
sudo tee /etc/systemd/system/spectre.service <<EOF
[Unit]
Description=SPECTRE RF Dashboard
After=bluetooth.target network.target

[Service]
WorkingDirectory=/home/pi/spectre
ExecStart=/home/pi/spectre/.venv/bin/python combined_server.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable spectre && sudo systemctl start spectre
```

---

## Legal

Educational and research use only. Only use on networks and devices you own or have explicit written permission to test.
