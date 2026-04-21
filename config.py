# Application configuration settings for the WiFi visualizer.

# Screen settings
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 900
FPS = 45

# Colors
BACKGROUND_COLOR = (5, 5, 10)
GRID_COLOR = (15, 30, 45)
ACCENT_COLOR = (0, 255, 200)   # Cyan
ACCENT_ALT = (255, 0, 150)     # Magenta
DARK_ACCENT = (20, 255, 180)
TEXT_COLOR = (180, 200, 220)

# Simulation settings
NUM_NODES = 20
SPECTRUM_NUM_BARS = 30
SPECTRUM_BAR_WIDTH = 10
SPECTRUM_BAR_GAP = 5
SPECTRUM_HEIGHT = 200

# Additional future network simulation settings
MAX_NODES = 20
MIN_BUBBLE_RADIUS = 15
MAX_BUBBLE_RADIUS = 40
BUBBLE_SPEED = 2
NODE_DRIFT = 0.15
PULSE_SPEED_MIN = 0.15
PULSE_SPEED_MAX = 0.45
SCAN_LINE_SPEED = 70
BUBBLE_COLORS = [
    (255, 100, 100), (100, 255, 100), (100, 100, 255),
    (255, 255, 100), (255, 100, 255), (100, 255, 255),
    (200, 200, 255), (255, 150, 200)
]

SSID_BASES = [
    "Linksys", "NETGEAR", "TP-LINK", "Xfinity", "Spectrum", "ATTWiFi",
    "Home", "Office", "StarbucksWiFi", "FreeWiFi", "Guest", "MyHome",
    "MyNetwork", "Galaxy", "Office-Guest", "CafeWiFi", "CityWifi",
    "Apartment", "Apartment-Guest", "SmartHome", "IoT-Network"
]

SSID_SUFFIXES = [
    "", "5G", "_5G", "-5G", "-Guest", "_Home", "_EXT", "-EXT", "WiFi", "_WiFi"
]

# Real Wi-Fi scan settings (macOS only)
USE_REAL_SSIDS = True
WIFI_AIRPORT_PATH = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
