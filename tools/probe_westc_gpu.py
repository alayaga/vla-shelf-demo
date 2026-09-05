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

cmds = [
    "nvidia-smi 2>&1 | head -20",
    "echo DISPLAY=$DISPLAY; echo VK_ICD_FILENAMES=$VK_ICD_FILENAMES",
    "ls -la /usr/share/vulkan/icd.d 2>/dev/null | head",
    "find /root/autodl-tmp -name '*.mp4' 2>/dev/null | head -30",
    "find /tmp -maxdepth 3 -name '*.mp4' 2>/dev/null | head -20",
    "ls -la /root/autodl-tmp/projects/pi05_retail/download 2>/dev/null | head -20",
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
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:500])
c.close()
