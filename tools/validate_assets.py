#!/usr/bin/env python3
"""Validate assets/meta/manifest.json against local video files."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "assets" / "meta" / "manifest.json"
VIDEOS = ROOT / "assets" / "videos"
CAMS = ("fetch_head", "fetch_hand", "checkout_camera")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not META.exists():
        print("MISSING", META)
        return 1
    manifest = json.loads(META.read_text(encoding="utf-8"))
    durs = []
    for cam in CAMS:
        if cam not in manifest:
            print(f"FAIL missing manifest entry: {cam}")
            return 1
        mp4 = VIDEOS / f"{cam}.mp4"
        if not mp4.exists():
            print(f"FAIL missing video: {mp4}")
            return 1
        meta = manifest[cam]
        digest = sha256(mp4)
        if meta.get("sha256") and meta["sha256"] != digest:
            print(f"WARN sha256 mismatch {cam}")
        durs.append(float(meta["duration_s"]))
        print(f"OK {cam} {meta['width']}x{meta['height']} {meta['duration_s']}s")
    if max(durs) - min(durs) > 0.1:
        print("FAIL duration mismatch", durs)
        return 1
    traj = ROOT / "assets" / "trajectory.json"
    if not traj.exists():
        print("FAIL missing trajectory.json")
        return 1
    print("VALIDATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
