#!/usr/bin/env python3
"""
SSID Visualizer GUI - macOS Wi-Fi Network Scanner
Animated radar + live network table + signal bars
Uses macOS `airport` CLI for real scans (no root required)
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
import subprocess
import threading
import time
import math
import random
import colorsys
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────────────
AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
SCAN_INTERVAL = 4          # seconds between real scans
RADAR_FPS     = 60         # animation frames/sec
RADAR_SPEED   = 1.5        # degrees per frame

BG        = "#05050A"
PANEL_BG  = "#0A0F1A"
GRID      = "#0F1E2D"
CYAN      = "#00FFC8"
MAGENTA   = "#FF0096"
YELLOW    = "#FFE000"
TEXT      = "#B4C8DC"
DIM       = "#3A4A5A"
GREEN     = "#00FF88"
RED       = "#FF4040"
WHITE     = "#E8F0FF"

CHANNEL_COLORS_24 = "#00FFC8"
CHANNEL_COLORS_5  = "#FF0096"

SSID_DEMOS = [
    ("Linksys_Home",    "aa:bb:cc:11:22:33", -45, 6,  "WPA2"),
    ("NETGEAR-5G",      "aa:bb:cc:44:55:66", -62, 36, "WPA3"),
    ("Starbucks_Guest", "de:ad:be:ef:00:01", -78, 1,  "Open"),
    ("ATT-WiFi-2.4",    "de:ad:be:ef:00:02", -55, 11, "WPA2"),
    ("MyHome_EXT",      "de:ad:be:ef:00:03", -68, 6,  "WPA2"),
    ("TP-LINK_A1B2",    "de:ad:be:ef:00:04", -82, 44, "WPA2"),
    ("xfinitywifi",     "de:ad:be:ef:00:05", -90, 1,  "Open"),
    ("HiddenNet",       "<hidden>",          -71, 6,  "WPA2"),
    ("Office_Corp",     "ca:fe:ba:be:00:01", -50, 149,"WPA3"),
    ("Galaxy_Hotspot",  "ca:fe:ba:be:00:02", -66, 6,  "WPA2"),
]


def rssi_to_color(rssi):
    """Map RSSI to a color: green (strong) → yellow → red (weak)."""
    try:
        val = int(rssi)
    except (ValueError, TypeError):
        return DIM
    # -30 (excellent) to -90 (terrible)
    norm = max(0.0, min(1.0, (val + 90) / 60.0))   # 0=weak, 1=strong
    if norm > 0.6:
        return GREEN
    elif norm > 0.3:
        return YELLOW
    else:
        return RED


def rssi_to_bars(rssi, max_bars=5):
    try:
        val = int(rssi)
    except (ValueError, TypeError):
        return 0
    norm = max(0.0, min(1.0, (val + 90) / 60.0))
    return max(1, round(norm * max_bars))


def channel_band(ch):
    try:
        return "5GHz" if int(ch) > 14 else "2.4GHz"
    except (ValueError, TypeError):
        return "2.4GHz"


# ── Airport Scanner ──────────────────────────────────────────────────────────
class AirportScanner:
    def __init__(self, callback):
        self._cb  = callback
        self._run = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._run:
            data = self._scan()
            if data:
                self._cb(data)
            time.sleep(SCAN_INTERVAL)

    def _scan(self):
        try:
            result = subprocess.run(
                [AIRPORT, "-s"],
                capture_output=True, text=True, timeout=10
            )
            return self._parse(result.stdout)
        except Exception:
            return None

    def _parse(self, raw):
        networks = []
        for line in raw.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                # airport -s columns: SSID  BSSID  RSSI  CHANNEL  HT  CC  SECURITY
                # SSID may contain spaces; BSSID is always xx:xx:xx:xx:xx:xx
                bssid_idx = None
                for i, p in enumerate(parts):
                    if len(p) == 17 and p.count(':') == 5:
                        bssid_idx = i
                        break
                if bssid_idx is None:
                    continue
                ssid    = " ".join(parts[:bssid_idx]) or "<hidden>"
                bssid   = parts[bssid_idx]
                rssi    = int(parts[bssid_idx + 1])
                channel = parts[bssid_idx + 2].split(',')[0]
                security = parts[bssid_idx + 6] if bssid_idx + 6 < len(parts) else "?"
                networks.append({
                    "ssid": ssid, "bssid": bssid, "rssi": rssi,
                    "channel": channel, "security": security,
                    "last_seen": time.time()
                })
            except (IndexError, ValueError):
                continue
        return networks if networks else None

    def stop(self):
        self._run = False


# ── Main App ─────────────────────────────────────────────────────────────────
class SSIDVisualizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ SSID Visualizer — WiFi Radar")
        self.configure(bg=BG)
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.resizable(True, True)

        self._networks = {}      # bssid → dict
        self._lock = threading.Lock()
        self._radar_angle = 0.0
        self._trails = []        # list of (angle, alpha, bssid_or_None)
        self._blips = {}         # bssid → (x, y, age)
        self._use_demo = False
        self._scan_count = 0

        self._build_ui()
        self._load_demo_data()
        self._start_scanner()
        self._animate_radar()
        self._schedule_table_refresh()

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_top_bar()
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=1)

        self._build_radar(content)
        self._build_table(content)
        self._build_signal_bars(content)
        self._build_channel_map(content)

    def _build_top_bar(self):
        bar = tk.Frame(self, bg=PANEL_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        title_font = tkfont.Font(family="Menlo", size=18, weight="bold")
        tk.Label(bar, text="⚡ SSID VISUALIZER", font=title_font,
                 bg=PANEL_BG, fg=CYAN).pack(side="left", padx=20, pady=10)

        self._status_var = tk.StringVar(value="● SCANNING…")
        tk.Label(bar, textvariable=self._status_var,
                 font=("Menlo", 11), bg=PANEL_BG, fg=GREEN).pack(side="left", padx=10)

        self._count_var = tk.StringVar(value="Networks: 0")
        tk.Label(bar, textvariable=self._count_var,
                 font=("Menlo", 11), bg=PANEL_BG, fg=TEXT).pack(side="left", padx=20)

        self._mode_var = tk.StringVar(value="MODE: LIVE")
        tk.Label(bar, textvariable=self._mode_var,
                 font=("Menlo", 10), bg=PANEL_BG, fg=MAGENTA).pack(side="right", padx=20)

        self._time_var = tk.StringVar()
        tk.Label(bar, textvariable=self._time_var,
                 font=("Menlo", 11), bg=PANEL_BG, fg=DIM).pack(side="right", padx=8)
        self._tick_clock()

    def _tick_clock(self):
        self._time_var.set(time.strftime("  %H:%M:%S  "))
        self.after(1000, self._tick_clock)

    # ── Radar canvas ─────────────────────────────────────────────────────────
    def _build_radar(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG, bd=0)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=4)

        tk.Label(frame, text="▣  RADAR SWEEP", font=("Menlo", 10, "bold"),
                 bg=PANEL_BG, fg=CYAN).pack(anchor="w", padx=10, pady=(6, 0))

        self._radar_canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        self._radar_canvas.pack(fill="both", expand=True, padx=6, pady=6)

    def _draw_radar(self):
        c = self._radar_canvas
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return

        cx, cy = W // 2, H // 2
        R = min(cx, cy) - 10

        # Grid rings
        for i in range(1, 5):
            r = R * i // 4
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=GRID, width=1)
            label_r = r - 4
            c.create_text(cx + label_r, cy,
                          text=f"{-90 + 15 * i}dBm",
                          font=("Menlo", 7), fill=DIM, anchor="w")

        # Crosshairs
        c.create_line(cx - R, cy, cx + R, cy, fill=GRID, width=1)
        c.create_line(cx, cy - R, cx, cy + R, fill=GRID, width=1)
        # Diagonals
        off = int(R * 0.707)
        c.create_line(cx - off, cy - off, cx + off, cy + off, fill=GRID, width=1, dash=(2, 6))
        c.create_line(cx - off, cy + off, cx + off, cy - off, fill=GRID, width=1, dash=(2, 6))

        # Sweep trail (fading sectors)
        num_trails = 40
        for i in range(num_trails):
            a_deg  = self._radar_angle - i * 2.0
            alpha  = max(0, 1.0 - i / num_trails)
            extent = 2.5
            r_hex  = int(alpha * 0)
            g_hex  = int(alpha * 255)
            b_hex  = int(alpha * 100)
            color  = f"#{r_hex:02x}{g_hex:02x}{b_hex:02x}"
            if alpha < 0.02:
                continue
            a_rad = math.radians(a_deg - 90)
            x1 = cx + int(R * math.cos(a_rad))
            y1 = cy + int(R * math.sin(a_rad))
            c.create_arc(cx - R, cy - R, cx + R, cy + R,
                         start=90 - a_deg, extent=-extent,
                         fill=color, outline="", style=tk.PIE)

        # Sweep line
        a_rad = math.radians(self._radar_angle - 90)
        x1 = cx + int(R * math.cos(a_rad))
        y1 = cy + int(R * math.sin(a_rad))
        c.create_line(cx, cy, x1, y1, fill=CYAN, width=2)

        # Blips
        with self._lock:
            nets = list(self._networks.values())

        used_angles = set()
        for idx, net in enumerate(nets):
            bssid = net["bssid"]
            rssi  = net.get("rssi", -80)
            try:
                rssi_val = int(rssi)
            except (ValueError, TypeError):
                rssi_val = -80

            # Stable angle based on bssid hash
            angle_deg = (hash(bssid) % 360)
            # Radial distance: stronger signal → closer to center
            dist_norm = max(0.1, min(0.95, (rssi_val + 100) / 70.0))
            dist = R * (1.0 - dist_norm + 0.1)

            brad = math.radians(angle_deg - 90)
            bx = cx + int(dist * math.cos(brad))
            by = cy + int(dist * math.sin(brad))

            # Check if sweep is near this blip
            sweep_diff = abs((self._radar_angle - angle_deg) % 360)
            if sweep_diff < 8:
                glow_alpha = 1.0 - sweep_diff / 8.0
                gr = int(glow_alpha * 255)
                gg = int(glow_alpha * 255)
                glow_c = f"#{gr:02x}{gg:02x}00"
                c.create_oval(bx - 12, by - 12, bx + 12, by + 12,
                              fill="", outline=glow_c, width=2)

            color = rssi_to_color(rssi_val)
            c.create_oval(bx - 5, by - 5, bx + 5, by + 5,
                          fill=color, outline=WHITE, width=1)

            # Label
            ssid = net.get("ssid", "?")
            label = ssid[:14] + "…" if len(ssid) > 14 else ssid
            c.create_text(bx + 8, by - 8, text=label,
                          font=("Menlo", 8), fill=WHITE, anchor="w")

        # Center dot
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=CYAN, outline=WHITE, width=1)
        c.create_text(cx, cy + R + 8, text="YOU", font=("Menlo", 8), fill=DIM)

    # ── Network Table ────────────────────────────────────────────────────────
    def _build_table(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=4)

        tk.Label(frame, text="▣  LIVE NETWORK FEED", font=("Menlo", 10, "bold"),
                 bg=PANEL_BG, fg=CYAN).pack(anchor="w", padx=10, pady=(6, 0))

        cols = ("SSID", "BSSID", "RSSI", "SIG", "CH", "BAND", "SEC")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Radar.Treeview",
                        background=BG,
                        foreground=TEXT,
                        fieldbackground=BG,
                        rowheight=26,
                        font=("Menlo", 10))
        style.configure("Radar.Treeview.Heading",
                        background=PANEL_BG,
                        foreground=CYAN,
                        font=("Menlo", 10, "bold"),
                        relief="flat")
        style.map("Radar.Treeview",
                  background=[("selected", "#162030")],
                  foreground=[("selected", CYAN)])

        tv_frame = tk.Frame(frame, bg=BG)
        tv_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self._tree = ttk.Treeview(tv_frame, columns=cols, show="headings",
                                  style="Radar.Treeview")
        widths = {"SSID": 180, "BSSID": 150, "RSSI": 60, "SIG": 80, "CH": 45, "BAND": 65, "SEC": 65}
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=widths.get(col, 80), anchor="center")
        self._tree.column("SSID", anchor="w")

        sb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Tag colors
        self._tree.tag_configure("strong",  foreground=GREEN)
        self._tree.tag_configure("medium",  foreground=YELLOW)
        self._tree.tag_configure("weak",    foreground=RED)
        self._tree.tag_configure("hidden",  foreground=DIM)
        self._tree.tag_configure("open",    foreground=MAGENTA)

    def _refresh_table(self):
        with self._lock:
            nets = sorted(self._networks.values(),
                          key=lambda n: int(n.get("rssi", -100)), reverse=True)

        existing = {self._tree.item(i)["values"][1]: i
                    for i in self._tree.get_children()}

        seen_bssids = set()
        for net in nets:
            bssid   = net["bssid"]
            ssid    = net.get("ssid", "?")
            rssi    = net.get("rssi", "?")
            channel = net.get("channel", "?")
            sec     = net.get("security", "?")
            band    = channel_band(channel)
            bars    = rssi_to_bars(rssi)
            bar_str = "█" * bars + "░" * (5 - bars)
            tag     = "strong" if bars >= 4 else ("medium" if bars >= 2 else "weak")
            if ssid in ("<hidden>", "Hidden", ""):
                tag = "hidden"
            if sec == "Open" or sec == "--":
                tag = "open"

            values = (ssid, bssid, f"{rssi}dBm", bar_str, channel, band, sec)
            seen_bssids.add(bssid)

            if bssid in existing:
                self._tree.item(existing[bssid], values=values, tags=(tag,))
            else:
                self._tree.insert("", "end", values=values, tags=(tag,))

        # Remove stale entries
        for bssid, iid in existing.items():
            if bssid not in seen_bssids:
                self._tree.delete(iid)

        self._count_var.set(f"Networks: {len(nets)}")

    def _schedule_table_refresh(self):
        self._refresh_table()
        self.after(500, self._schedule_table_refresh)

    # ── Signal Bar Chart ─────────────────────────────────────────────────────
    def _build_signal_bars(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))

        tk.Label(frame, text="▣  SIGNAL STRENGTH", font=("Menlo", 10, "bold"),
                 bg=PANEL_BG, fg=CYAN).pack(anchor="w", padx=10, pady=(6, 0))

        self._bar_canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, height=130)
        self._bar_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self._bar_canvas.bind("<Configure>", lambda e: self._draw_bars())

    def _draw_bars(self):
        c = self._bar_canvas
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return

        with self._lock:
            nets = sorted(self._networks.values(),
                          key=lambda n: int(n.get("rssi", -100)), reverse=True)[:20]

        if not nets:
            c.create_text(W // 2, H // 2, text="No networks", fill=DIM, font=("Menlo", 12))
            return

        pad_l, pad_r, pad_t, pad_b = 6, 6, 8, 22
        n = len(nets)
        bar_w = max(8, (W - pad_l - pad_r) // n - 2)
        chart_h = H - pad_t - pad_b

        # Range lines
        for rssi_mark in [-90, -75, -60, -45]:
            norm = max(0, min(1.0, (rssi_mark + 100) / 70.0))
            y = pad_t + chart_h - int(chart_h * norm)
            c.create_line(pad_l, y, W - pad_r, y, fill=GRID, dash=(4, 4), width=1)
            c.create_text(pad_l + 2, y - 4, text=f"{rssi_mark}", fill=DIM,
                          font=("Menlo", 7), anchor="w")

        for i, net in enumerate(nets):
            rssi = net.get("rssi", -100)
            try:
                rssi_val = int(rssi)
            except (ValueError, TypeError):
                rssi_val = -100
            norm  = max(0.0, min(1.0, (rssi_val + 100) / 70.0))
            bh    = max(2, int(chart_h * norm))
            x     = pad_l + i * (bar_w + 2)
            y_top = pad_t + chart_h - bh
            y_bot = pad_t + chart_h

            color = rssi_to_color(rssi_val)

            # Glow effect
            for gw in range(3, 0, -1):
                gc = "#001A10" if color == GREEN else ("#1A1000" if color == YELLOW else "#1A0000")
                c.create_rectangle(x - gw, y_top - gw, x + bar_w + gw, y_bot,
                                   fill="", outline=gc, width=1)
            c.create_rectangle(x, y_top, x + bar_w, y_bot, fill=color, outline="")

            # SSID label
            ssid = net.get("ssid", "?")
            label = ssid[:5] if len(ssid) > 5 else ssid
            c.create_text(x + bar_w // 2, y_bot + 3, text=label,
                          font=("Menlo", 7), fill=TEXT, anchor="n",
                          angle=35)

    # ── Channel Map ──────────────────────────────────────────────────────────
    def _build_channel_map(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

        tk.Label(frame, text="▣  CHANNEL USAGE MAP", font=("Menlo", 10, "bold"),
                 bg=PANEL_BG, fg=CYAN).pack(anchor="w", padx=10, pady=(6, 0))

        self._ch_canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, height=130)
        self._ch_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self._ch_canvas.bind("<Configure>", lambda e: self._draw_channel_map())

    def _draw_channel_map(self):
        c = self._ch_canvas
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return

        with self._lock:
            nets = list(self._networks.values())

        # Group by channel
        ch_count: dict = defaultdict(int)
        ch_rssi:  dict = defaultdict(list)
        for net in nets:
            ch = str(net.get("channel", "?"))
            ch_count[ch] += 1
            try:
                ch_rssi[ch].append(int(net["rssi"]))
            except (KeyError, ValueError, TypeError):
                pass

        channels_24 = [str(c) for c in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
                       if str(c) in ch_count]
        channels_5  = sorted([ch for ch in ch_count if ch not in
                               [str(i) for i in range(1, 15)]],
                              key=lambda x: int(x) if x.isdigit() else 999)

        pad_l, pad_r, pad_t, pad_b = 6, 6, 8, 24
        all_chs = channels_24 + channels_5
        if not all_chs:
            c.create_text(W // 2, H // 2, text="No channels", fill=DIM, font=("Menlo", 12))
            return

        n       = len(all_chs)
        bar_w   = max(12, (W - pad_l - pad_r) // n - 3)
        chart_h = H - pad_t - pad_b
        max_cnt = max(ch_count.values()) if ch_count else 1

        sep_x = None
        for i, ch in enumerate(all_chs):
            is_5 = ch in channels_5
            color = CHANNEL_COLORS_5 if is_5 else CHANNEL_COLORS_24
            cnt = ch_count[ch]
            norm = cnt / max_cnt
            bh = max(4, int(chart_h * norm))
            x = pad_l + i * (bar_w + 3)
            y_top = pad_t + chart_h - bh
            y_bot = pad_t + chart_h

            if is_5 and sep_x is None:
                sep_x = x - 4

            # Bar
            c.create_rectangle(x, y_top, x + bar_w, y_bot, fill=color, outline="")
            # Count label
            c.create_text(x + bar_w // 2, y_top - 3, text=str(cnt),
                          font=("Menlo", 8, "bold"), fill=WHITE, anchor="s")
            # Channel label
            c.create_text(x + bar_w // 2, y_bot + 3, text=ch,
                          font=("Menlo", 7), fill=TEXT, anchor="n")

        # Separator between 2.4 and 5 GHz
        if sep_x:
            c.create_line(sep_x, pad_t, sep_x, pad_t + chart_h, fill=DIM, dash=(4, 4))
            c.create_text(sep_x - 4, pad_t + 2, text="2.4GHz",
                          font=("Menlo", 7), fill=CHANNEL_COLORS_24, anchor="e")
            c.create_text(sep_x + 4, pad_t + 2, text="5GHz",
                          font=("Menlo", 7), fill=CHANNEL_COLORS_5, anchor="w")

    # ── Data sources ─────────────────────────────────────────────────────────
    def _load_demo_data(self):
        """Pre-populate with demo data so UI isn't empty on launch."""
        with self._lock:
            for ssid, bssid, rssi, ch, sec in SSID_DEMOS:
                self._networks[bssid] = {
                    "ssid": ssid, "bssid": bssid, "rssi": rssi,
                    "channel": str(ch), "security": sec,
                    "last_seen": time.time()
                }
        self._mode_var.set("MODE: DEMO+LIVE")
        self._use_demo = True

    def _start_scanner(self):
        try:
            import os
            if os.path.exists(AIRPORT):
                self._scanner = AirportScanner(self._on_scan_result)
                self._status_var.set("● SCANNING…")
            else:
                self._status_var.set("⚠ DEMO MODE")
                self._mode_var.set("MODE: DEMO")
        except Exception:
            self._status_var.set("⚠ DEMO MODE")
            self._mode_var.set("MODE: DEMO")

    def _on_scan_result(self, networks):
        self._scan_count += 1
        ts = time.strftime("%H:%M:%S")
        self.after(0, lambda: self._status_var.set(f"● LAST SCAN: {ts}"))
        if not networks:
            return
        with self._lock:
            # Replace demo data on first real scan
            if self._use_demo:
                self._networks.clear()
                self._use_demo = False
                self.after(0, lambda: self._mode_var.set("MODE: LIVE"))
            for net in networks:
                self._networks[net["bssid"]] = net

    # ── Animation loop ───────────────────────────────────────────────────────
    def _animate_radar(self):
        self._radar_angle = (self._radar_angle + RADAR_SPEED) % 360
        self._draw_radar()
        self._draw_bars()
        self._draw_channel_map()
        self.after(int(1000 / RADAR_FPS), self._animate_radar)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SSIDVisualizer()
    app.mainloop()
