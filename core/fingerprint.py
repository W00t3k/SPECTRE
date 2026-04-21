#!/usr/bin/env python3
"""
core/fingerprint.py — SPECTRE Multi-Frame Device Fingerprinter

Correlates BLE advertisement frames across time to build
a persistent device fingerprint even when:
  - MAC address randomises every 15 minutes
  - AirDrop is not active
  - Device name is empty

Scoring model: each stable attribute contributes confidence points.
A fingerprint match threshold of 60+ points is considered HIGH confidence.

Score contributions:
  AirDrop hash match         → 100  (definitive identity)
  AirPods model + color      →  80  (physical device ID)
  iOS version + activity     →  50
  Siri device type + OS ver  →  50
  HomeKit category           →  40
  Hotspot network type       →  35
  RSSI proximity cluster     →  20  (same physical area)
  Temporal proximity (< 60s) →  15  (seen at same time)
"""

import time
from typing import Optional

MATCH_THRESHOLD = 60   # minimum score to call it a match


def score_frames(frames_a: list, frames_b: list,
                 rssi_a: int = None, rssi_b: int = None,
                 ts_a: float = None, ts_b: float = None) -> dict:
    """
    Compare two sets of BLE frames and return a similarity score dict.
    """
    score = 0
    reasons = []

    # Index by type_id
    idx_a = {f["type_id"]: f for f in frames_a}
    idx_b = {f["type_id"]: f for f in frames_b}

    # ── AirDrop hash match (0x05) ─────────────────────────────────────────
    if 0x05 in idx_a and 0x05 in idx_b:
        fa, fb = idx_a[0x05], idx_b[0x05]
        for field in ("phone", "apple_id", "email"):
            va, vb = fa.get(field, ""), fb.get(field, "")
            if va and vb and va == vb:
                score += 100
                reasons.append(f"AirDrop {field} hash match: {va}")

    # ── AirPods model + color (0x07) ──────────────────────────────────────
    if 0x07 in idx_a and 0x07 in idx_b:
        fa, fb = idx_a[0x07], idx_b[0x07]
        model_a, model_b = fa.get("model", ""), fb.get("model", "")
        color_a, color_b = fa.get("color", ""), fb.get("color", "")
        if model_a and model_a == model_b:
            score += 50
            reasons.append(f"AirPods model: {model_a}")
            if color_a and color_a == color_b:
                score += 30
                reasons.append(f"AirPods color: {color_a}")

    # ── Nearby Info iOS version + activity (0x10) ─────────────────────────
    if 0x10 in idx_a and 0x10 in idx_b:
        fa, fb = idx_a[0x10], idx_b[0x10]
        ios_a, ios_b = fa.get("ios_version", ""), fb.get("ios_version", "")
        act_a, act_b = fa.get("activity", ""), fb.get("activity", "")
        if ios_a and ios_a == ios_b:
            score += 30
            reasons.append(f"iOS version: {ios_a}")
            if act_a and act_a == act_b:
                score += 20
                reasons.append(f"Activity: {act_a}")

    # ── Siri / HomePod device type (0x08) ─────────────────────────────────
    if 0x08 in idx_a and 0x08 in idx_b:
        fa, fb = idx_a[0x08], idx_b[0x08]
        dt_a, dt_b = fa.get("device_type", ""), fb.get("device_type", "")
        os_a, os_b = fa.get("os_version", ""), fb.get("os_version", "")
        if dt_a and dt_a == dt_b:
            score += 35
            reasons.append(f"Siri device: {dt_a}")
            if os_a and os_a == os_b:
                score += 15
                reasons.append(f"OS version: {os_a}")

    # ── HomeKit category (0x06) ───────────────────────────────────────────
    if 0x06 in idx_a and 0x06 in idx_b:
        fa, fb = idx_a[0x06], idx_b[0x06]
        cat_a, cat_b = fa.get("category", ""), fb.get("category", "")
        if cat_a and cat_a == cat_b:
            score += 40
            reasons.append(f"HomeKit category: {cat_a}")

    # ── Hotspot network type (0x0d) ───────────────────────────────────────
    if 0x0d in idx_a and 0x0d in idx_b:
        fa, fb = idx_a[0x0d], idx_b[0x0d]
        nt_a, nt_b = fa.get("network_type", ""), fb.get("network_type", "")
        if nt_a and nt_a == nt_b:
            score += 35
            reasons.append(f"Hotspot type: {nt_a}")

    # ── RSSI proximity cluster ────────────────────────────────────────────
    if rssi_a is not None and rssi_b is not None:
        diff = abs(rssi_a - rssi_b)
        if diff <= 8:
            score += 20
            reasons.append(f"RSSI proximity: {rssi_a}/{rssi_b}dBm (Δ{diff})")
        elif diff <= 15:
            score += 8

    # ── Temporal proximity ────────────────────────────────────────────────
    if ts_a is not None and ts_b is not None:
        age = abs(ts_a - ts_b)
        if age < 60:
            score += 15
            reasons.append(f"Same timeframe: Δ{age:.0f}s")
        elif age < 300:
            score += 5

    confidence = "HIGH" if score >= 80 else "MEDIUM" if score >= MATCH_THRESHOLD else "LOW"

    return {
        "score":      score,
        "confidence": confidence,
        "match":      score >= MATCH_THRESHOLD,
        "reasons":    reasons,
    }


class DeviceCorrelator:
    """
    In-memory correlator that runs across all currently visible BLE devices.
    Finds clusters of devices that are likely the same physical person
    (e.g., iPhone + AirPods + Watch all belonging to one owner).
    """

    def __init__(self):
        self._clusters: list = []   # [{devices: [addr,...], score, fp_ids}]

    def correlate(self, ble_devices: dict) -> list:
        """
        Given the current dict of addr→device, return a list of
        correlated identity clusters.

        Each cluster = one probable person with all their devices.
        """
        devs = list(ble_devices.values())
        if len(devs) < 2:
            return []

        clusters = []
        visited = set()

        for i, dev_a in enumerate(devs):
            if dev_a["addr"] in visited:
                continue
            cluster = {
                "devices":    [dev_a["addr"]],
                "names":      [dev_a.get("name", dev_a["addr"])],
                "max_score":  0,
                "reasons":    [],
                "fp_ids":     [dev_a.get("fp_id", "")],
            }

            for j, dev_b in enumerate(devs):
                if i == j or dev_b["addr"] in visited:
                    continue
                result = score_frames(
                    dev_a.get("frames", []),
                    dev_b.get("frames", []),
                    rssi_a=dev_a.get("rssi"),
                    rssi_b=dev_b.get("rssi"),
                    ts_a=dev_a.get("last_seen"),
                    ts_b=dev_b.get("last_seen"),
                )
                if result["match"]:
                    cluster["devices"].append(dev_b["addr"])
                    cluster["names"].append(dev_b.get("name", dev_b["addr"]))
                    cluster["fp_ids"].append(dev_b.get("fp_id", ""))
                    cluster["max_score"] = max(cluster["max_score"], result["score"])
                    cluster["reasons"].extend(result["reasons"])
                    visited.add(dev_b["addr"])

            if len(cluster["devices"]) > 1:
                cluster["confidence"] = (
                    "HIGH" if cluster["max_score"] >= 80
                    else "MEDIUM"
                )
                clusters.append(cluster)
                visited.add(dev_a["addr"])

        return clusters
