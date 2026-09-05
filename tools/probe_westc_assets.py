#!/usr/bin/env python3
import os
import paramiko
from pathlib import Path

LOCAL_ENV = Path(__file__).resolve().parent / "westc.local.env"
env = {}
for line in LOCAL_ENV.read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

files = [
    "/root/autodl-tmp/shelf_bottle_head.mp4",
    "/root/autodl-tmp/shelf_bottle_hand.mp4",
    "/root/autodl-tmp/shelf_bottle_checkout.mp4",
    "/root/autodl-tmp/shelf_bottle_panorama.mp4",
]
cmds = [
    "for f in " + " ".join(files) + "; do echo === $f ===; ffprobe -v error -select_streams v:0 -show_entries stream=width,height,nb_frames,r_frame_rate,duration -of default=noprint_wrappers=1 $f 2>&1; ls -lh $f; done",
    "find /root/autodl-tmp -name 'trajectory*.json' -o -name 'trajectory.npz' 2>/dev/null | head -30",
    "find /root/autodl-tmp -path '*vla_demo*' -o -path '*triptych*' 2>/dev/null | head -30",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    env["WESTC_HOST"],
    port=int(env["WESTC_PORT"]),
    username=env["WESTC_USER"],
    password=env["WESTC_PASSWORD"],
    timeout=60,
)
for cmd in cmds:
    print(">>>", cmd[:120])
    _, o, e = c.exec_command(cmd, timeout=180)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
