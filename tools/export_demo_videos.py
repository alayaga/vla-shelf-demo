#!/usr/bin/env python3
"""
Run on westc (read-only on retail_store). Writes only to /tmp/vla_web_demo/.

Exports three independent camera mp4s + trajectory.json + manifest.json + info.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import cv2
import gymnasium as gym
import numpy as np

import retail_store  # noqa: F401
import retail_store.shelf_bottle.shelf_task_env  # noqa: F401
from retail_store.camera_utils import robot_arm_sensor_configs
from retail_store.shelf_bottle.shelf_task_env import BOTTLE_TASK_ENV_ID
from retail_store.shelf_bottle.shelf_task_solver import ShelfBottleSolver, SolverPhase

OUT = Path("/tmp/vla_web_demo")
HEAD_SIZE = 640
HAND_SIZE = 640
BOTTLE = "shelf_B_water_bottle_1_2_4"
SEED = 1001
FPS = 20
TRAJ_STRIDE = 1
VLA_PHASES = {"ARM_RAISE", "GRASP_CLOSE", "PLACE", "RELEASE"}


def to_u8(frame):
    x = np.asarray(frame)
    if hasattr(x, "cpu"):
        x = x.cpu().numpy()
    if x.dtype != np.uint8:
        if float(np.max(x)) <= 1.5:
            x = (x * 255.0).clip(0, 255).astype(np.uint8)
        else:
            x = x.clip(0, 255).astype(np.uint8)
    if x.ndim == 4:
        x = x[0]
    if x.shape[-1] == 4:
        x = x[..., :3]
    return x


def yaw_from_pose(pose):
    """pose: [x,y,z,qw,qx,qy,qz] or longer; return yaw."""
    p = np.asarray(pose, dtype=np.float64).reshape(-1)
    if p.size >= 7:
        qw, qx, qy, qz = p[3], p[4], p[5], p[6]
    else:
        return 0.0
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return float(math.atan2(siny_cosp, cosy_cosp))


def write_mp4(path: Path, frames: list[np.ndarray], fps: int = FPS) -> tuple[int, int]:
    if not frames:
        raise RuntimeError(f"no frames for {path}")
    h, w = frames[0].shape[:2]
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        tmp = path.with_suffix(".tmp.avi")
        writer = cv2.VideoWriter(
            str(tmp), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h)
        )
        for f in frames:
            writer.write(cv2.cvtColor(to_u8(f), cv2.COLOR_RGB2BGR))
        writer.release()
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(tmp),
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tmp.unlink(missing_ok=True)
    else:
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)
        )
        for f in frames:
            writer.write(cv2.cvtColor(to_u8(f), cv2.COLOR_RGB2BGR))
        writer.release()
    return w, h


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def phase_spans(phases):
    phases = np.asarray(phases).astype(str)
    spans = {}
    for p in set(phases.tolist()):
        idx = np.flatnonzero(phases == p)
        spans[p] = (int(idx[0]), int(idx[-1]))
    return spans


def first_transition(phases, from_phase, to_phase):
    phases = np.asarray(phases).astype(str)
    for i in range(1, len(phases)):
        if phases[i - 1] == from_phase and phases[i] == to_phase:
            return i
    return None


def traj_row(row):
    base_pose = np.asarray(row["base_pose"], dtype=np.float64).reshape(-1)
    bottle_pose = np.asarray(row["bottle_pose"], dtype=np.float64).reshape(-1)
    phase = str(row["phase"])
    return {
        "step": int(row["step"]),
        "phase": phase,
        "control": "vla" if phase in VLA_PHASES else "code",
        "base": [
            float(base_pose[0]),
            float(base_pose[1]),
            yaw_from_pose(base_pose),
        ],
        "arm_qpos": [float(x) for x in np.asarray(row["arm_qpos"]).reshape(-1)[:6]],
        "gripper": float(np.mean(row["gripper_qpos"])),
        "bottle": [
            float(bottle_pose[0]),
            float(bottle_pose[1]),
            float(bottle_pose[2]),
        ],
    }


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    env = gym.make(
        BOTTLE_TASK_ENV_ID,
        obs_mode="state_dict",
        reward_mode="none",
        control_mode="pd_joint_pos",
        render_mode="rgb_array",
        sim_backend="cpu",
        render_backend="gpu",
        num_envs=1,
        sensor_configs=robot_arm_sensor_configs(HEAD_SIZE, HAND_SIZE),
    )

    result = None
    solver = None
    for attempt in range(1, 10):
        seed = SEED + attempt - 1
        env.reset(
            seed=seed,
            options=dict(
                reconfigure=True,
                bottle_name=BOTTLE,
                robot_xy=[0.05, 1.4],
                robot_yaw=0.0,
            ),
        )
        solver = ShelfBottleSolver(
            env,
            debug=True,
            record_trajectory=True,
            video_cameras=("fetch_head", "fetch_hand", "checkout_camera"),
            video_interval=1,
        )
        result = solver.solve(max_steps=2000)
        print(
            f"attempt{attempt} phase={result.phase} success={result.success} "
            f"grasp={result.grasp_success} place={result.placement_success} "
            f"steps={result.total_steps}"
        )
        if str(result.phase).endswith("SUCCESS") or result.phase == SolverPhase.SUCCESS:
            break

    if result is None or solver is None:
        raise SystemExit("NO_SOLVER")

    cam_ids = ("fetch_head", "fetch_hand", "checkout_camera")
    heads = solver.video_frames.get("fetch_head", [])
    hands = solver.video_frames.get("fetch_hand", [])
    scenes = solver.video_frames.get("checkout_camera", [])
    if not heads or not hands or not scenes:
        raise SystemExit(
            f"missing video frames head={len(heads)} hand={len(hands)} scene={len(scenes)}"
        )

    n = min(len(heads), len(hands), len(scenes), len(solver.trajectory))
    bundles = {
        "fetch_head": heads[:n],
        "fetch_hand": hands[:n],
        "checkout_camera": scenes[:n],
    }

    manifest = {}
    for cam_id, frames in bundles.items():
        out_path = OUT / "videos" / f"{cam_id}.mp4"
        w, h = write_mp4(out_path, frames, FPS)
        manifest[cam_id] = {
            "width": w,
            "height": h,
            "fps": FPS,
            "duration_s": round(n / FPS, 4),
            "frames": n,
            "sha256": sha256_file(out_path),
        }
        print(f"WROTE {out_path} {w}x{h} frames={n}")

    phases = np.array([solver.trajectory[i]["phase"] for i in range(n)], dtype=object)
    spans = phase_spans(phases)

    nav_end = spans.get("NAV_TO_GRASP", (0, 0))[1]
    arm_raise_start = spans.get("ARM_RAISE", (nav_end + 1, nav_end + 1))[0]
    t = first_transition(phases, "NAV_TO_GRASP", "ARM_RAISE")
    if t is not None:
        code_pre_end = t - 1
        grasp_vla_start = t
    else:
        code_pre_end = nav_end
        grasp_vla_start = arm_raise_start

    grasp_attached = np.array(
        [bool(solver.trajectory[i].get("grasp_attached", False)) for i in range(n)]
    )
    att_idx = np.flatnonzero(grasp_attached)
    if att_idx.size:
        grasp_vla_end = int(att_idx[0])
    else:
        grasp_vla_end = spans.get("GRASP_CLOSE", (grasp_vla_start, grasp_vla_start))[1]

    place_vla_start = spans.get("PLACE", (0, 0))[0]
    rel_start, rel_end = spans.get("RELEASE", (place_vla_start, place_vla_start))
    place_vla_end = rel_end
    for ti in range(rel_start, rel_end + 1):
        gq = np.asarray(solver.trajectory[ti].get("gripper_qpos", [0.05]))
        if float(np.mean(gq)) > 0.03:
            place_vla_end = ti
            break

    traj_frames = [
        traj_row(solver.trajectory[i])
        for i in range(0, n, TRAJ_STRIDE)
    ]
    traj_payload = {
        "fps": FPS,
        "stride": TRAJ_STRIDE,
        "total_steps": int(result.total_steps),
        "frames": traj_frames,
    }
    (OUT / "trajectory.json").write_text(
        json.dumps(traj_payload, indent=2), encoding="utf-8"
    )

    info = {
        "bottle_name": BOTTLE,
        "seed": SEED,
        "steps": int(result.total_steps),
        "n_frames": n,
        "phase_spans": {k: list(v) for k, v in spans.items()},
        "division": {
            "code_pre_grasp": {
                "start": 0,
                "end": int(code_pre_end),
                "phases": "through NAV_TO_GRASP (drive-in complete, before ARM_RAISE)",
            },
            "vla_grasp": {
                "start": int(grasp_vla_start),
                "end": int(grasp_vla_end),
                "phases": "ARM_RAISE + GRASP_CLOSE until grasp_attached",
            },
            "code_transport": {
                "phases": "RETRACT_OUT + CARRY_RAISE + NAV_TO_CHECKOUT"
            },
            "vla_place": {
                "start": int(place_vla_start),
                "end": int(place_vla_end),
                "phases": "PLACE + RELEASE until gripper opens",
            },
        },
        "cameras": list(cam_ids),
        "result": {
            "phase": str(result.phase),
            "success": bool(result.success),
            "grasp_success": bool(result.grasp_success),
            "placement_success": bool(result.placement_success),
        },
    }
    (OUT / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    durs = [manifest[c]["duration_s"] for c in cam_ids]
    if max(durs) - min(durs) > 0.1:
        raise SystemExit(f"duration mismatch: {durs}")

    print("EXPORT_OK", json.dumps({"steps": n, "manifest": manifest}, ensure_ascii=False))
    env.close()


if __name__ == "__main__":
    main()
