#!/usr/bin/env python3
"""探测远程 Python / 环境路径。凭据仅来自 westc.local.env 或环境变量。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

LOCAL_ENV = Path(__file__).resolve().parent / "westc.local.env"


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env(LOCAL_ENV)

HOST = os.environ.get("WESTC_HOST", "").strip()
PORT_RAW = os.environ.get("WESTC_PORT", "").strip()
USER = os.environ.get("WESTC_USER", "").strip()
PASSWORD = os.environ.get("WESTC_PASSWORD", "")

if not HOST or not PORT_RAW or not USER or not PASSWORD:
    raise SystemExit(
        "请设置 WESTC_HOST / WESTC_PORT / WESTC_USER / WESTC_PASSWORD "
        "（见 tools/westc.local.env.example，切勿提交真实凭据）。"
    )

CMDS = [
    "which python3 python 2>/dev/null",
    "ls /root/miniconda3/envs 2>/dev/null; ls /root/anaconda3/envs 2>/dev/null",
    "find /root -maxdepth 4 -path '*/bin/python' 2>/dev/null | head -20",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=int(PORT_RAW), username=USER, password=PASSWORD, timeout=60)
for cmd in CMDS:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
