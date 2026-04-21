#!/usr/bin/env python3
"""
SPECTRE CLI — full command-line interface for the SPECTRE RF dashboard.

Usage:
    python spectre.py <command> [options]

Commands:
    start           Start the SPECTRE dashboard server
    wifi            Dump live WiFi networks (from running server)
    ble             Dump live BLE devices (from running server)
    status          Show server status + counts
    sysinfo         Show system info (interfaces, USB)
    demo            Toggle demo mode on the running server
    inject-ble      Inject demo BLE devices
    inject-wifi     Inject demo WiFi networks
    interval        Get/set WiFi scan interval
    clear-ble       Clear BLE device list
    clear-events    Clear event log
    clear-alerts    Clear alerts
    export          Download and print WiFi/BLE/events as JSON
    monitor         Enable/disable WiFi adapter monitor mode (Linux/Pi)
    scan            Run a one-shot WiFi scan and print results
    watch           Live-tail event stream from the server

Run 'python spectre.py <command> --help' for per-command options.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
import urllib.error

# ─── ANSI colours ────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
MAG    = "\033[95m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

def c(text, *codes): return "".join(codes) + str(text) + RESET
def ok(msg):   print(c("✓", GREEN, BOLD), msg)
def err(msg):  print(c("✗", RED,   BOLD), msg, file=sys.stderr)
def info(msg): print(c("›", CYAN),  msg)
def warn(msg): print(c("⚠", YELLOW), msg)
def dim(msg):  print(c(msg, DIM))

BANNER = f"""
{MAG}{BOLD}  ███████╗██████╗ ███████╗ ██████╗████████╗██████╗ ███████╗{RESET}
{MAG}  ██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝{RESET}
{MAG}  ███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝█████╗  {RESET}
{MAG}  ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══╝  {RESET}
{MAG}{BOLD}  ███████║██║     ███████╗╚██████╗   ██║   ██║  ██║███████╗{RESET}
{MAG}{BOLD}  ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝{RESET}
{DIM}  Signal · Protocol · Exploitation · Capture · Tracking · Recon · Engine{RESET}
"""

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5003


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _url(host, port, path):
    return f"http://{host}:{port}{path}"

def _get(host, port, path, timeout=5):
    try:
        with urllib.request.urlopen(_url(host, port, path), timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        err(f"Cannot reach SPECTRE server at {host}:{port}  ({e.reason})")
        err("Is the server running?  Try:  python spectre.py start")
        sys.exit(1)

def _post_socket(host, port, event, data=None):
    """Fire a socket.io event via the simple HTTP socket.io REST shim we add below."""
    payload = json.dumps({"event": event, "data": data or {}}).encode()
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("SPECTRE_TOKEN", "")
    if token:
        headers["X-SPECTRE-Token"] = token
    req = urllib.request.Request(
        _url(host, port, "/api/emit"),
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        err(f"Cannot reach SPECTRE server at {host}:{port}  ({e.reason})")
        sys.exit(1)

def _rssi_bar(rssi):
    """Coloured ASCII signal bar."""
    norm = max(0, min(1, (rssi + 100) / 70))
    filled = round(norm * 10)
    bar = "█" * filled + "░" * (10 - filled)
    if rssi >= -55:   col = GREEN
    elif rssi >= -70: col = YELLOW
    else:             col = RED
    return c(bar, col) + f" {rssi}dBm"

def _sec_badge(sec):
    if sec in ("Open", "--", "NONE", ""):
        return c(f" {sec} ", RED, BOLD)
    if "WPA3" in sec:
        return c(f" {sec} ", GREEN, BOLD)
    return c(f" {sec} ", YELLOW)

def _band(ch):
    try:
        return c("5GHz", MAG) if int(ch) > 14 else c("2.4GHz", CYAN)
    except Exception:
        return c(str(ch), DIM)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_start(args):
    print(BANNER)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.sh")
    extra = []
    if args.port != DEFAULT_PORT:
        extra += ["--port", str(args.port)]
    if args.no_tests:
        # bypass tests by calling python directly
        py = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
        if not os.path.exists(py):
            py = sys.executable
        os.execv(py, [py, os.path.join(os.path.dirname(os.path.abspath(__file__)), "combined_server.py")])
    else:
        os.execv("/bin/bash", ["/bin/bash", script] + extra)


def cmd_status(args):
    data = _get(args.host, args.port, "/api/status")
    print(BANNER)
    print(c("  SERVER STATUS", BOLD, CYAN))
    print()
    rows = [
        ("Host",          f"{args.host}:{args.port}"),
        ("Demo mode",     c("ON", YELLOW, BOLD) if data.get("demo") else c("OFF", DIM)),
        ("WiFi networks", c(data.get("wifi_count", 0), CYAN, BOLD)),
        ("BLE devices",   c(data.get("ble_count",  0), BLUE, BOLD)),
        ("Events",        data.get("event_count", 0)),
        ("Alerts",        c(data.get("alert_count", 0), RED) if data.get("alert_count") else 0),
        ("Scan interval", c(f"{data.get('scan_interval', '?')}s", YELLOW)),
        ("Uptime",        data.get("uptime", "?")),
    ]
    for k, v in rows:
        print(f"  {c(k.ljust(18), DIM)}{v}")
    print()


def cmd_wifi(args):
    data = _get(args.host, args.port, "/api/status")
    nets = data.get("wifi", [])
    if not nets:
        warn("No WiFi networks in state. Run: python spectre.py scan")
        return
    nets.sort(key=lambda n: n.get("rssi", -999), reverse=True)
    print()
    print(c(f"  {'SSID':<26} {'BSSID':<20} {'SIG':>18}  {'CH':<5} {'BAND':<10} SECURITY", BOLD))
    print(c("  " + "─" * 90, DIM))
    for n in nets:
        ssid  = (n.get("ssid") or "<hidden>")[:25]
        bssid = n.get("bssid", "")
        rssi  = n.get("rssi", -999)
        ch    = str(n.get("channel", "?"))
        sec   = n.get("security", "?")
        demo  = c(" DEMO", DIM) if n.get("source") == "demo" else ""
        print(f"  {c(ssid, WHITE):<35} {c(bssid, DIM):<20} {_rssi_bar(rssi)}  {ch:<5} {_band(ch):<20} {_sec_badge(sec)}{demo}")
    print()
    print(f"  {c(len(nets), CYAN, BOLD)} networks  ·  "
          f"{c(sum(1 for n in nets if int(n.get('channel',0))>14), MAG)} on 5GHz  ·  "
          f"{c(sum(1 for n in nets if n.get('security') in ('Open','--','NONE','')), RED, BOLD)} open")
    print()


def cmd_ble(args):
    data = _get(args.host, args.port, "/api/status")
    devs = data.get("ble", [])
    if not devs:
        warn("No BLE devices in state. Try: python spectre.py inject-ble")
        return
    devs.sort(key=lambda d: d.get("rssi", -999), reverse=True)
    TYPE_ICONS = {
        0x07: "🎧", 0x10: "📱", 0x0f: "⚡", 0x05: "📡",
        0x0c: "🔄", 0x0d: "📶", 0x0e: "📶", 0x12: "📍",
        0x08: "🎤", 0x06: "🏠", 0x0b: "⌚",
    }
    print()
    print(c(f"  {'NAME':<28} {'ADDR':<22} {'SIG':>18}  FRAMES  TYPE", BOLD))
    print(c("  " + "─" * 88, DIM))
    for d in devs:
        name  = (d.get("name") or "Unknown")[:27]
        addr  = d.get("addr", "")
        rssi  = d.get("rssi", -999)
        fc    = d.get("frame_count", 0)
        lost  = d.get("lost", False)
        frames= d.get("frames", [])
        tids  = [f.get("type_id") for f in frames]
        icons = " ".join(TYPE_ICONS.get(t, "") for t in tids if t)
        ftypes= " ".join(f.get("type", "") for f in frames[:2])
        name_col = c(name, DIM) if lost else c(name, WHITE)
        lost_tag = c(" [LOST]", RED) if lost else ""
        print(f"  {name_col:<37}{lost_tag} {c(addr, DIM):<22} {_rssi_bar(rssi)}  {c(str(fc).rjust(3), CYAN)}  {icons} {c(ftypes, DIM)}")
        # extra decoded info
        for f in frames:
            tid = f.get("type_id")
            parts = []
            if tid == 0x10:
                if f.get("phone_state"): parts.append(c(f["phone_state"], YELLOW))
                if f.get("ios_version"): parts.append(c(f"iOS {f['ios_version']}", CYAN))
                if f.get("wifi_on") is not None:
                    parts.append(c("WiFi✓", GREEN) if f["wifi_on"] else c("WiFi✗", DIM))
            elif tid == 0x07:
                if f.get("model"):      parts.append(c(f["model"], BLUE))
                if f.get("status"):     parts.append(c(f["status"], DIM))
                L = f.get("left_bat")
                R = f.get("right_bat")
                C = f.get("case_bat")
                if L is not None: parts.append(c(f"L:{L*10}%", GREEN if L>6 else YELLOW if L>3 else RED))
                if R is not None: parts.append(c(f"R:{R*10}%", GREEN if R>6 else YELLOW if R>3 else RED))
                if C is not None: parts.append(c(f"case:{C*10}%", DIM))
            elif tid == 0x0f:
                if f.get("action"):      parts.append(c(f["action"], YELLOW))
                if f.get("device_class"):parts.append(c(f["device_class"], BLUE))
            elif tid == 0x0d or tid == 0x0e:
                if f.get("network_type"):parts.append(c(f["network_type"], YELLOW))
                if f.get("battery") is not None: parts.append(c(f"🔋{f['battery']}%", GREEN))
            elif tid == 0x08:
                if f.get("device_type"):parts.append(c(f["device_type"], CYAN))
                if f.get("os_version"): parts.append(c(f"os:{f['os_version']}", DIM))
            elif tid == 0x12:
                if f.get("status"):     parts.append(c(f["status"], RED))
            elif tid == 0x06:
                if f.get("category"):   parts.append(c(f["category"], MAG))
            if parts:
                print(f"    {c('└', DIM)} " + "  ".join(parts))
    print()
    total  = len(devs)
    lost   = sum(1 for d in devs if d.get("lost"))
    phones = sum(1 for d in devs if any(f.get("type_id")==0x10 for f in d.get("frames",[])))
    pods   = sum(1 for d in devs if any(f.get("type_id")==0x07 for f in d.get("frames",[])))
    print(f"  {c(total, CYAN, BOLD)} devices  ·  "
          f"{c(phones, YELLOW)} phones  ·  "
          f"{c(pods, BLUE)} airpods  ·  "
          f"{c(lost, RED)} lost")
    print()


def cmd_sysinfo(args):
    data = _get(args.host, args.port, "/api/system_info")
    print()
    print(c(f"  SYSTEM INFO", BOLD, CYAN))
    print()
    print(f"  {c('Hostname',DIM):<22} {c(data.get('hostname','?'), WHITE, BOLD)}")
    print(f"  {c('OS',DIM):<22} {data.get('os','?')}")
    print(f"  {c('Scan interval',DIM):<22} {c(str(data.get('wifi_scan_interval','?'))+'s', YELLOW)}")
    print()
    print(c("  NETWORK INTERFACES", BOLD))
    print(c("  " + "─" * 60, DIM))
    for iface in data.get("interfaces", []):
        up = iface.get("status") == "UP"
        col = GREEN if up else DIM
        ip  = iface.get("ip4") or iface.get("ip6") or "—"
        print(f"  {c(iface['iface']+':', col, BOLD):<22} {ip:<20} {c(iface.get('mac',''), DIM):<22} {c(iface['status'], col)}")
    print()
    print(c("  USB DEVICES", BOLD))
    print(c("  " + "─" * 60, DIM))
    usb = [u for u in data.get("usb", []) if u.get("name")]
    if not usb:
        dim("  (none detected)")
    for u in usb:
        spd = c(f"[{u['speed']}]", DIM) if u.get("speed") else ""
        print(f"  {c(u['name'], WHITE):<40} {c(u.get('vendor',''), DIM):<24} {spd}")
    print()


def cmd_demo(args):
    r = _post_socket(args.host, args.port, "toggle_demo")
    ok(f"Demo mode toggled  →  {r}")


def cmd_inject_ble(args):
    r = _post_socket(args.host, args.port, "inject_demo_ble")
    ok(f"Demo BLE devices injected  →  {r}")


def cmd_inject_wifi(args):
    r = _post_socket(args.host, args.port, "inject_demo_wifi")
    ok(f"Demo WiFi networks injected  →  {r}")


def cmd_interval(args):
    if args.seconds is None:
        data = _get(args.host, args.port, "/api/status")
        info(f"Current scan interval: {c(str(data.get('scan_interval','?'))+'s', YELLOW, BOLD)}")
    else:
        r = _post_socket(args.host, args.port, "set_interval", {"interval": args.seconds})
        ok(f"Scan interval set to {c(str(args.seconds)+'s', YELLOW, BOLD)}")


def cmd_clear_ble(args):
    r = _post_socket(args.host, args.port, "clear_ble")
    ok("BLE device list cleared")


def cmd_clear_events(args):
    r = _post_socket(args.host, args.port, "clear_events")
    ok("Event log cleared")


def cmd_clear_alerts(args):
    r = _post_socket(args.host, args.port, "clear_alerts")
    ok("Alerts cleared")


def cmd_export(args):
    endpoints = {
        "wifi":   "/export/wifi.json",
        "ble":    "/export/ble.json",
        "events": "/export/events.json",
    }
    target = args.type
    if target not in endpoints:
        err(f"Unknown export type '{target}'. Choose: wifi, ble, events")
        sys.exit(1)
    data = _get(args.host, args.port, endpoints[target])
    if args.output:
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2, default=str)
        ok(f"Saved {len(data)} records → {args.output}")
    else:
        print(json.dumps(data, indent=2, default=str))


def cmd_scan(args):
    """One-shot WiFi scan — calls airport directly, no server needed."""
    IS_MACOS = platform.system() == "Darwin"
    AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    if not IS_MACOS:
        err("One-shot scan requires macOS (airport CLI).")
        err("On Linux/Pi, start the server and use: python spectre.py wifi")
        sys.exit(1)
    if not os.path.exists(AIRPORT):
        err("airport not found — macOS only")
        sys.exit(1)
    info("Scanning for WiFi networks...")
    try:
        result = subprocess.run([AIRPORT, "-s"], capture_output=True, text=True, timeout=15)
        raw = result.stdout
    except subprocess.TimeoutExpired:
        err("Scan timed out")
        sys.exit(1)
    print()
    print(c("  RAW airport output:", DIM))
    print(c("  " + "─" * 80, DIM))
    for line in raw.strip().splitlines():
        print("  " + line)
    print()


def cmd_monitor(args):
    """Enable or disable monitor mode on a WiFi interface (Linux only)."""
    if platform.system() != "Linux":
        err("Monitor mode management is Linux/Pi only.")
        err("On macOS, use: airport -z (disassociate) then airport sniff <channel>")
        sys.exit(1)
    import re as _re
    iface = args.interface
    if not _re.fullmatch(r'[a-zA-Z0-9]+', iface):
        err(f"Invalid interface name '{iface}' — only alphanumeric characters allowed")
        sys.exit(1)
    action = args.action
    if action == "start":
        info(f"Killing interfering processes...")
        subprocess.run(["sudo", "airmon-ng", "check", "kill"], check=False)
        info(f"Starting monitor mode on {iface}...")
        r = subprocess.run(["sudo", "airmon-ng", "start", iface], capture_output=False)
        if r.returncode == 0:
            ok(f"Monitor mode enabled → {iface}mon")
            info(f"Use interface: {c(iface+'mon', CYAN, BOLD)}")
        else:
            err("airmon-ng failed — is aircrack-ng installed?")
    elif action == "stop":
        info(f"Stopping monitor mode on {iface}...")
        r = subprocess.run(["sudo", "airmon-ng", "stop", iface], capture_output=False)
        if r.returncode == 0:
            ok(f"Monitor mode stopped on {iface}")
        else:
            err("airmon-ng stop failed")
    elif action == "status":
        r = subprocess.run(["iwconfig"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            col = CYAN if "Monitor" in line else (DIM if not line.strip() else RESET)
            print(c(line, col))


def cmd_watch(args):
    """Poll the server status and live-tail new events."""
    info(f"Watching SPECTRE events at {args.host}:{args.port}  (Ctrl+C to stop)")
    print()
    seen_ids = set()
    try:
        while True:
            try:
                data = _get(args.host, args.port, "/api/status")
            except SystemExit:
                time.sleep(2)
                continue
            events = data.get("events", [])
            for ev in reversed(events):
                eid = ev.get("ts", "") + ev.get("name", "")
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    kind  = ev.get("kind", "")
                    name  = ev.get("name", "")
                    detail= ev.get("detail", "")
                    ts    = ev.get("ts", "")
                    kind_col = {
                        "BLE_NEW": BLUE, "BLE_LOST": RED, "WIFI_NEW": CYAN,
                        "WIFI_LOST": DIM, "ALERT": RED,
                    }.get(kind, MAG)
                    print(f"  {c(ts, DIM):<18} {c(kind.ljust(12), kind_col, BOLD)}  {c(name, WHITE):<30}  {c(detail, DIM)}")
            # also show a live counter line
            wc = data.get("wifi_count", 0)
            bc = data.get("ble_count", 0)
            print(c(f"\r  ● WiFi:{wc}  BLE:{bc}  events:{len(events)}   ", CYAN), end="", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        ok("Watch stopped.")


# ─── /api/status  +  /api/emit  — add these to combined_server.py ─────────────
# (the CLI calls these REST endpoints)

def _patch_server_check(host, port):
    """Quick check that /api/status exists on the target server."""
    try:
        _get(host, port, "/api/status", timeout=2)
        return True
    except SystemExit:
        return False


# ─── Arg parser ──────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="spectre",
        description=f"SPECTRE CLI — RF recon command-line interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--host",  default=DEFAULT_HOST, help=f"Server host (default: {DEFAULT_HOST})")
    p.add_argument("--port",  default=DEFAULT_PORT, type=int, help=f"Server port (default: {DEFAULT_PORT})")

    sub = p.add_subparsers(dest="command", metavar="command")

    # start
    ps = sub.add_parser("start", help="Start the SPECTRE server")
    ps.add_argument("--no-tests", action="store_true", help="Skip regression tests on startup")

    # status
    sub.add_parser("status", help="Show server status + counts")

    # wifi
    sub.add_parser("wifi", help="Show live WiFi networks")

    # ble
    sub.add_parser("ble", help="Show live BLE devices with full decoded info")

    # sysinfo
    sub.add_parser("sysinfo", help="Show system info (interfaces, USB devices)")

    # scan
    sub.add_parser("scan", help="One-shot WiFi scan via airport (macOS, no server needed)")

    # demo
    sub.add_parser("demo", help="Toggle demo mode on running server")

    # inject-ble
    sub.add_parser("inject-ble", help="Inject demo BLE devices into running server")

    # inject-wifi
    sub.add_parser("inject-wifi", help="Inject demo WiFi networks into running server")

    # interval
    pi = sub.add_parser("interval", help="Get or set WiFi scan interval")
    pi.add_argument("seconds", nargs="?", type=int, help="Interval in seconds (omit to just read)")

    # clear-ble
    sub.add_parser("clear-ble", help="Clear BLE device list on running server")

    # clear-events
    sub.add_parser("clear-events", help="Clear event log on running server")

    # clear-alerts
    sub.add_parser("clear-alerts", help="Clear alerts on running server")

    # export
    pe = sub.add_parser("export", help="Download WiFi/BLE/events as JSON")
    pe.add_argument("type", choices=["wifi","ble","events"], help="Data type to export")
    pe.add_argument("-o","--output", help="Save to file instead of stdout")

    # monitor
    pm = sub.add_parser("monitor", help="WiFi adapter monitor mode (Linux/Pi only)")
    pm.add_argument("action", choices=["start","stop","status"], help="Action")
    pm.add_argument("--interface", "-i", default="wlan1", help="WiFi interface (default: wlan1)")

    # watch
    pw = sub.add_parser("watch", help="Live-tail events from the running server")
    pw.add_argument("--interval", "-n", type=float, default=2.0, help="Poll interval in seconds")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.command is None:
        print(BANNER)
        parser.print_help()
        print()
        return

    dispatch = {
        "start":        cmd_start,
        "status":       cmd_status,
        "wifi":         cmd_wifi,
        "ble":          cmd_ble,
        "sysinfo":      cmd_sysinfo,
        "demo":         cmd_demo,
        "inject-ble":   cmd_inject_ble,
        "inject-wifi":  cmd_inject_wifi,
        "interval":     cmd_interval,
        "clear-ble":    cmd_clear_ble,
        "clear-events": cmd_clear_events,
        "clear-alerts": cmd_clear_alerts,
        "export":       cmd_export,
        "scan":         cmd_scan,
        "monitor":      cmd_monitor,
        "watch":        cmd_watch,
    }
    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
