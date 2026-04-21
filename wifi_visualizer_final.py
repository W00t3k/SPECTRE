#!/usr/bin/env python3
import sys
import os
import signal
import time
import subprocess
from scapy.all import *

def handle_sigint(sig, frame):
    print("\n\n[*] Capturing stopped.")
    print("[*] Please reconnect to Wi-Fi manually.")
    sys.exit(0)

def beacon_callback(pkt):
    """
    Checks for Beacon frames manually (since BPF filters fail on macOS).
    """
    if pkt.haslayer(Dot11Beacon):
        info = pkt.info
        try:
            ssid = info.decode('utf-8').strip()
        except:
            ssid = "Hidden"
        
        bssid = pkt[Dot11].addr3
        
        channel = "Unknown"
        if pkt.haslayer(Dot11Elt) and pkt[Dot11Elt].ID == 3:
            channel = pkt[Dot11Elt].info[0]
            
        rssi = "N/A"
        if pkt.haslayer(RadioTap):
            rssi = pkt[RadioTap].dBm_AntSignal
            
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {bssid} | CH:{channel} | SIG:{rssi}dBm | SSID:{ssid}")

def main():
    if os.geteuid() != 0:
        print("[!] Error: This script requires sudo privileges.")
        sys.exit(1)
        
    print("[*] Step 1: Disconnecting from Wi-Fi to enable listening mode...")
    try:
        # This command puts the Wi-Fi card in passive listening mode
        subprocess.run(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-z'], check=True)
        print("[*] Step 2: Wi-Fi disconnected. Starting Capture...")
    except Exception as e:
        print(f"[!] Error disconnecting: {e}")
        print("[!] Try running this manually first:")
        print("sudo /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -z")
        sys.exit(1)

    print("[*] Press Ctrl+C to stop.")
    print("-" * 60)
    
    signal.signal(signal.SIGINT, handle_sigint)
    
    try:
        # NO filter argument here to avoid Libpcap compilation errors on macOS
        # We filter in Python instead
        sniff(iface='en0', prn=beacon_callback, store=0)
    except Exception as e:
        print(f"[!] Error during sniffing: {e}")
        print("[!] Ensure 'airport -z' was successful above.")

if __name__ == "__main__":
    main()