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

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    env["WESTC_HOST"],
    port=int(env["WESTC_PORT"]),
    username=env["WESTC_USER"],
    password=env["WESTC_PASSWORD"],
    timeout=60,
)
candidates = [
    "/root/autodl-tmp/.venv-maniskill/bin/python",
    "/root/autodl-tmp/.venv-lerobot/bin/python",
    "/root/miniconda3/bin/python",
]
for py in candidates:
    cmd = (
        f"cd /root/autodl-tmp && PYTHONPATH=/root/autodl-tmp {py} -c "
        "'import numpy,gymnasium,cv2; import retail_store; print(\"OK\")' 2>&1"
    )
    _, o, e = c.exec_command(cmd, timeout=180)
    out = (o.read() + e.read()).decode("utf-8", errors="replace").strip()
    print(py, "->", out)
c.close()
