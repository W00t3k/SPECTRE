#!/usr/bin/env python3
import sys
import os
import signal
import time
from scapy.all import *

# List to store captured SSIDs to avoid excessive scrolling
captured_ssids = set()

def handle_sigint(sig, frame):
    print("\n\n[*] Capturing stopped.")
    sys.exit(0)

def beacon_callback(pkt):
    """
    Callback function for each captured packet.
    We filter for Dot11 Beacon frames.
    """
    # Check if it's a Beacon frame
    if pkt.haslayer(Dot11Beacon):
        info = pkt.info
        # Try to decode SSID (handles null bytes)
        try:
            ssid = info.decode('utf-8').strip()
        except:
            ssid = "Hidden"
        
        # Get BSSID (Source MAC)
        bssid = pkt[Dot11].addr3
        
        # Get Channel from DS Parameter Set
        if pkt.haslayer(Dot11Elt) and pkt[Dot11Elt].ID == 3:
            channel = pkt[Dot11Elt].info[0]
        else:
            channel = "Unknown"
            
        # Get Signal Strength (RSSI) from radiotap header if present
        if pkt.haslayer(RadioTap):
            rssi = pkt[RadioTap].dBm_AntSignal
        else:
            rssi = "N/A"
            
        # Visual Output
        timestamp = time.strftime("%H:%M:%S")
        
        # Format the output
        if ssid == "Hidden":
            print(f"[{timestamp}] {bssid} | CH:{channel} | SIG:{rssi}dBm | SSID:[HIDDEN]")
        else:
            print(f"[{timestamp}] {bssid} | CH:{channel} | SIG:{rssi}dBm | SSID:{ssid}")
            
        # Keep track of unique SSIDs seen (optional, for stats)
        if ssid != "Hidden":
            captured_ssids.add(ssid)

def main():
    if os.geteuid() != 0:
        print("[!] Error: This script requires sudo privileges.")
        sys.exit(1)
        
    print("[*] Starting Wi-Fi Beacon Visualizer...")
    print("[!] Note: macOS does not support full monitor mode.")
    print("[*] Press Ctrl+C to stop.")
    print("-" * 60)
    
    # Register Ctrl+C handler
    signal.signal(signal.SIGINT, handle_sigint)
    
    try:
        # IMPORTANT: 
        # 1. iface=None lets Scapy choose the default interface (usually en0)
        # 2. store=0 saves memory by not storing packets
        # 3. filter='type mgt subtype beacon' limits the capture to beacons only
        # 4. We DO NOT set promiscuous=True because macOS blocks it.
        sniff(iface=None, prn=beacon_callback, filter="type mgt subtype beacon", store=0)
    except Exception as e:
        print(f"[!] Error during sniffing: {e}")
        print("[!] Ensure your Wi-Fi is on and you have permissions.")
        print("[!] On macOS, you may need to use 'airport -z' to disconnect first.")

if __name__ == "__main__":
    main()