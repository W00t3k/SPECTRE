#!/usr/bin/env python3
"""
core/identity.py — SPECTRE Identity Engine

Persistent cross-session tracking of:
  - AirDrop SHA256 hashes (phone, Apple ID, email)
  - Re-appearance detection and alerting
  - Per-identity timeline (when/where/RSSI)
  - Multi-frame device fingerprinting
  - SQLite-backed store (spectre_identities.db)
"""

import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Optional

DB_PATH = os.environ.get(
    "SPECTRE_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spectre_identities.db")
)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS identities (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        fp_id         TEXT UNIQUE NOT NULL,   -- fingerprint ID (SHA256 of key fields)
        first_seen    REAL NOT NULL,
        last_seen     REAL NOT NULL,
        seen_count    INTEGER DEFAULT 1,
        label         TEXT DEFAULT '',        -- operator-assigned name
        threat_level  TEXT DEFAULT 'LOW',     -- LOW / MEDIUM / HIGH
        notes         TEXT DEFAULT '',
        raw_json      TEXT DEFAULT '{}'       -- latest full frame JSON
    );

    CREATE TABLE IF NOT EXISTS sightings (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        fp_id      TEXT NOT NULL,
        ts         REAL NOT NULL,
        rssi       INTEGER,
        addr       TEXT,
        location   TEXT DEFAULT '',
        frame_json TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS hashes (
        hash       TEXT PRIMARY KEY,          -- 3-byte hex from AirDrop (e.g. 'a3b2c1')
        hash_type  TEXT NOT NULL,             -- 'phone' | 'apple_id' | 'email'
        fp_id      TEXT NOT NULL,
        first_seen REAL NOT NULL,
        resolved   TEXT DEFAULT ''            -- cracked value if known
    );

    CREATE INDEX IF NOT EXISTS idx_sightings_fp ON sightings(fp_id);
    CREATE INDEX IF NOT EXISTS idx_sightings_ts ON sightings(ts);
    CREATE INDEX IF NOT EXISTS idx_hashes_fp    ON hashes(fp_id);
    """)
    conn.commit()


# ── Fingerprinting ────────────────────────────────────────────────────────────

def _make_fp_id(frames: list, addr: str) -> str:
    """
    Build a stable fingerprint ID from the most persistent identifiers
    found in BLE advertisement frames.

    Priority:
      1. AirDrop hashes (most stable — survive MAC randomisation)
      2. AirPods model + color (physical device)
      3. Nearby Info iOS version + activity byte combo
      4. Fallback: addr (least stable, randomises)
    """
    keys = []

    for f in frames:
        tid = f.get("type_id")
        if tid == 0x05:  # AirDrop
            for field in ("phone", "apple_id", "email"):
                v = f.get(field, "")
                if v:
                    keys.append(f"airdrop:{field}:{v}")
        elif tid == 0x07:  # AirPods
            model = f.get("model", "")
            color = f.get("color", "")
            if model:
                keys.append(f"airpods:{model}:{color}")
        elif tid == 0x10:  # Nearby Info
            ios = f.get("ios_version", "")
            act = f.get("activity", "")
            if ios and act:
                keys.append(f"nearby:{ios}:{act}")
        elif tid == 0x08:  # Siri / HomePod
            dt = f.get("device_type", "")
            os_v = f.get("os_version", "")
            if dt:
                keys.append(f"siri:{dt}:{os_v}")

    if not keys:
        keys.append(f"addr:{addr}")

    raw = "|".join(sorted(keys))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _threat_level(seen_count: int, has_airdrop: bool, has_hotspot: bool) -> str:
    if has_airdrop:
        return "HIGH"   # has personally identifying hashes
    if has_hotspot or seen_count >= 5:
        return "MEDIUM"
    return "LOW"


# ── Public API ────────────────────────────────────────────────────────────────

def record_device(addr: str, name: str, rssi: int, frames: list) -> dict:
    """
    Called every time a BLE device is seen.
    Returns a dict with:
      - fp_id: fingerprint ID
      - is_new: True if first ever sighting
      - is_return: True if seen before (cross-session)
      - seen_count: total sightings
      - label: operator label if set
      - hashes: list of AirDrop hash dicts
    """
    now = time.time()
    fp_id = _make_fp_id(frames, addr)

    has_airdrop  = any(f.get("type_id") == 0x05 for f in frames)
    has_hotspot  = any(f.get("type_id") == 0x0d for f in frames)
    airdrop_hashes = []

    for f in frames:
        if f.get("type_id") == 0x05:
            for field in ("phone", "apple_id", "email"):
                v = f.get(field, "")
                if v:
                    airdrop_hashes.append({"hash": v, "type": field})

    raw_json = json.dumps({
        "addr": addr, "name": name, "rssi": rssi,
        "frames": [{"type_id": f.get("type_id"), "type": f.get("type")} for f in frames]
    })

    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT id, seen_count, first_seen, label FROM identities WHERE fp_id=?",
            (fp_id,)
        ).fetchone()

        is_new    = row is None
        is_return = (not is_new) and (now - row["first_seen"] > 300)  # seen before, different session

        if is_new:
            threat = _threat_level(1, has_airdrop, has_hotspot)
            conn.execute(
                """INSERT INTO identities
                   (fp_id, first_seen, last_seen, seen_count, threat_level, raw_json)
                   VALUES (?,?,?,1,?,?)""",
                (fp_id, now, now, threat, raw_json)
            )
            seen_count = 1
            label = ""
        else:
            seen_count = row["seen_count"] + 1
            threat = _threat_level(seen_count, has_airdrop, has_hotspot)
            label = row["label"] or ""
            conn.execute(
                """UPDATE identities
                   SET last_seen=?, seen_count=?, threat_level=?, raw_json=?
                   WHERE fp_id=?""",
                (now, seen_count, threat, raw_json, fp_id)
            )

        # Record sighting
        conn.execute(
            "INSERT INTO sightings (fp_id, ts, rssi, addr, frame_json) VALUES (?,?,?,?,?)",
            (fp_id, now, rssi, addr, raw_json)
        )

        # Store hashes
        for h in airdrop_hashes:
            conn.execute(
                """INSERT OR IGNORE INTO hashes
                   (hash, hash_type, fp_id, first_seen) VALUES (?,?,?,?)""",
                (h["hash"], h["type"], fp_id, now)
            )

        conn.commit()

    return {
        "fp_id":      fp_id,
        "is_new":     is_new,
        "is_return":  is_return,
        "seen_count": seen_count,
        "label":      label,
        "threat":     threat,
        "hashes":     airdrop_hashes,
    }


def get_all_identities(limit: int = 200) -> list:
    """Return all tracked identities, most recent first."""
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT fp_id, first_seen, last_seen, seen_count,
                      label, threat_level, notes, raw_json
               FROM identities
               ORDER BY last_seen DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_identity_timeline(fp_id: str, limit: int = 100) -> list:
    """Return sighting timeline for a specific fingerprint."""
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT ts, rssi, addr, location, frame_json
               FROM sightings WHERE fp_id=?
               ORDER BY ts DESC LIMIT ?""",
            (fp_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def get_identity_hashes(fp_id: str) -> list:
    """Return all AirDrop hashes associated with a fingerprint."""
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT hash, hash_type, first_seen, resolved FROM hashes WHERE fp_id=?",
            (fp_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def set_identity_label(fp_id: str, label: str):
    """Operator-assign a name/label to a fingerprint."""
    with _lock:
        conn = _get_conn()
        conn.execute("UPDATE identities SET label=? WHERE fp_id=?", (label, fp_id))
        conn.commit()


def set_hash_resolved(hash_val: str, resolved: str):
    """Store a cracked/resolved value for an AirDrop hash."""
    with _lock:
        conn = _get_conn()
        conn.execute("UPDATE hashes SET resolved=? WHERE hash=?", (resolved, hash_val))
        conn.commit()


def get_stats() -> dict:
    """Quick stats for the status bar."""
    with _lock:
        conn = _get_conn()
        total   = conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0]
        high    = conn.execute("SELECT COUNT(*) FROM identities WHERE threat_level='HIGH'").fetchone()[0]
        medium  = conn.execute("SELECT COUNT(*) FROM identities WHERE threat_level='MEDIUM'").fetchone()[0]
        hashes  = conn.execute("SELECT COUNT(*) FROM hashes").fetchone()[0]
        returns = conn.execute(
            "SELECT COUNT(*) FROM identities WHERE seen_count > 1"
        ).fetchone()[0]
    return {
        "total": total, "high": high, "medium": medium,
        "hashes": hashes, "returns": returns
    }
