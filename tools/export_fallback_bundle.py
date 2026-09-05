#!/usr/bin/env python3
"""
Westc fallback when GPU render is unavailable.

Uses pre-rendered shelf_bottle_* mp4 (trimmed to target frames) and converts
a matching trajectory.npz if found under pi05_retail expert staging.
Writes only to /tmp/vla_web_demo/.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np

OUT = Path("/tmp/vla_web_demo")
FPS = 20
TARGET_FRAMES = 993
TARGET_DURATION = TARGET_FRAMES / FPS
VLA_PHASES = {"ARM_RAISE", "GRASP_CLOSE", "PLACE", "RELEASE"}

VIDEO_SOURCES = {
    "fetch_head": "/root/autodl-tmp/shelf_bottle_head.mp4",
    "fetch_hand": "/root/autodl-tmp/shelf_bottle_hand.mp4",
    "checkout_camera": "/root/autodl-tmp/shelf_bottle_checkout.mp4",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_wh(path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        text=True,
    ).strip()
    w, h = out.split("x")
    return int(w), int(h)


def trim_video(src: Path, dst: Path, frames: int = TARGET_FRAMES) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on westc")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dst),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def yaw_from_pose(pose):
    p = np.asarray(pose, dtype=np.float64).reshape(-1)
    if p.size >= 7:
        qw, qx, qy, qz = p[3], p[4], p[5], p[6]
        siny = 2.0 * (qw * qz + qx * qy)
        cosy = 1.0 - 2.0 * (qy * qy + qz * qz)
        return float(math.atan2(siny, cosy))
    return 0.0


def find_trajectory_npz() -> Path | None:
    roots = [
        Path("/root/autodl-tmp/projects/pi05_retail/data/raw/expert_full"),
        Path("/root/autodl-tmp/skill_staging"),
        Path("/root/autodl-tmp/skill_staging_dyn2"),
    ]
    best = None
    best_score = 10**9
    for root in roots:
        if not root.is_dir():
            continue
        for npz in root.rglob("trajectory.npz"):
            try:
                d = np.load(npz, allow_pickle=True)
                n = len(d["phases"])
            except Exception:
                continue
            score = abs(n - TARGET_FRAMES)
            if score < best_score:
                best_score = score
                best = npz
    return best


def npz_to_trajectory(npz_path: Path, n_frames: int) -> dict:
    d = np.load(npz_path, allow_pickle=True)
    phases = np.asarray(d["phases"]).astype(str)
    n = min(n_frames, len(phases))
    frames = []
    for i in range(n):
        phase = phases[i]
        base_pose = np.asarray(d["base_pose"][i]).reshape(-1)
        bottle_pose = np.asarray(d["bottle_pose"][i]).reshape(-1)
        arm_qpos = np.asarray(d["arm_qpos"][i]).reshape(-1)
        gripper = np.asarray(d["gripper_qpos"][i]).reshape(-1)
        frames.append(
            {
                "step": i,
                "phase": phase,
                "control": "vla" if phase in VLA_PHASES else "code",
                "base": [
                    float(base_pose[0]),
                    float(base_pose[1]),
                    yaw_from_pose(base_pose),
                ],
                "arm_qpos": [float(x) for x in arm_qpos[:6]],
                "gripper": float(np.mean(gripper)),
                "bottle": [
                    float(bottle_pose[0]),
                    float(bottle_pose[1]),
                    float(bottle_pose[2]),
                ],
            }
        )
    return {"fps": FPS, "stride": 1, "total_steps": n, "frames": frames, "source_npz": str(npz_path)}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "videos").mkdir(parents=True)

    manifest = {}
    for cam_id, src in VIDEO_SOURCES.items():
        src_path = Path(src)
        if not src_path.is_file():
            raise SystemExit(f"missing source video: {src}")
        dst = OUT / "videos" / f"{cam_id}.mp4"
        trim_video(src_path, dst, TARGET_FRAMES)
        w, h = ffprobe_wh(dst)
        manifest[cam_id] = {
            "width": w,
            "height": h,
            "fps": FPS,
            "duration_s": round(TARGET_FRAMES / FPS, 4),
            "frames": TARGET_FRAMES,
            "sha256": sha256_file(dst),
            "source": str(src_path),
        }
        print(f"WROTE {dst} {w}x{h}")

    npz = find_trajectory_npz()
    if npz is None:
        raise SystemExit("no trajectory.npz candidate found")
    traj = npz_to_trajectory(npz, TARGET_FRAMES)
    (OUT / "trajectory.json").write_text(json.dumps(traj, indent=2), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    info = {
        "bottle_name": "shelf_B_water_bottle_1_2_4",
        "seed": 1001,
        "steps": TARGET_FRAMES,
        "note": "fallback bundle from existing shelf_bottle_* mp4 + nearest trajectory.npz",
        "trajectory_source": str(npz),
    }
    (OUT / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("FALLBACK_OK", json.dumps({"npz": str(npz), "manifest": manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
