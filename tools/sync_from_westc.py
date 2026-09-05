#!/usr/bin/env python3
"""
从远程只读同步演示素材：在远端 /tmp 运行导出脚本，再 scp 到本地。

凭据仅来自环境变量或 tools/westc.local.env（已被 gitignore，切勿提交）：
  WESTC_HOST / WESTC_PORT / WESTC_USER / WESTC_PASSWORD / WESTC_PYTHON
模板见 tools/westc.local.env.example。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
EXPORT = Path(__file__).resolve().parent / "export_demo_videos.py"
FALLBACK = Path(__file__).resolve().parent / "export_fallback_bundle.py"
LOCAL_ENV = Path(__file__).resolve().parent / "westc.local.env"
REMOTE_EXPORT = "/tmp/export_demo_videos.py"
REMOTE_FALLBACK = "/tmp/export_fallback_bundle.py"
REMOTE_OUT = "/tmp/vla_web_demo"
LOCAL_VIDEOS = ROOT / "assets" / "videos"
LOCAL_META = ROOT / "assets" / "meta"


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
PY = os.environ.get("WESTC_PYTHON", "").strip()


def connect() -> paramiko.SSHClient:
    if not HOST or not PORT_RAW or not USER or not PASSWORD:
        raise SystemExit(
            "请设置 WESTC_HOST / WESTC_PORT / WESTC_USER / WESTC_PASSWORD "
            "（可复制 tools/westc.local.env.example 为 westc.local.env，切勿提交）。"
        )
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=int(PORT_RAW), username=USER, password=PASSWORD, timeout=60)
    return c


def remote_python_cmd(remote: str) -> str:
    if not PY:
        raise SystemExit(
            "请设置 WESTC_PYTHON（可在 westc.local.env 中填写，切勿提交）。"
        )
    remote_root = os.environ.get("WESTC_REMOTE_ROOT", "").strip()
    if remote_root:
        return f"cd {remote_root} && PYTHONPATH={remote_root} {PY} -u {remote}"
    return f"{PY} -u {remote}"


def run_remote_script(client: paramiko.SSHClient, local: Path, remote: str, label: str) -> str:
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write(local.read_text(encoding="utf-8"))
    sftp.close()

    cmd = remote_python_cmd(remote)
    print(f">>> {label}", flush=True)
    _, stdout, stderr = client.exec_command(cmd, timeout=3600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    return out, err, code


def run_export(client: paramiko.SSHClient) -> str:
    out, err, code = run_remote_script(
        client, EXPORT, REMOTE_EXPORT, "running export on westc (writes only /tmp/vla_web_demo/)"
    )
    if code != 0 or "EXPORT_OK" not in out:
        print("export unavailable (likely no GPU render); trying fallback bundle", flush=True)
        out, err, code = run_remote_script(
            client,
            FALLBACK,
            REMOTE_FALLBACK,
            "running fallback bundle (existing mp4 + trajectory.npz)",
        )
        if code != 0 or "FALLBACK_OK" not in out:
            raise SystemExit("export and fallback both failed on westc")
    return out


def scp_tree(sftp: paramiko.SFTPClient, remote: str, local: Path) -> None:
    local.mkdir(parents=True, exist_ok=True)
    for name in sftp.listdir(remote):
        r = f"{remote}/{name}"
        l = local / name
        try:
            sftp.stat(r)
            mode = sftp.stat(r).st_mode
            if (mode & 0o170000) == 0o040000:
                scp_tree(sftp, r, l)
            else:
                print(f"GET {r} -> {l}", flush=True)
                sftp.get(r, str(l))
        except OSError:
            sftp.get(r, str(l))


def validate_manifest(manifest: dict) -> None:
    cams = ("fetch_head", "fetch_hand", "checkout_camera")
    durs = []
    for cam in cams:
        if cam not in manifest:
            raise ValueError(f"missing camera in manifest: {cam}")
        meta = manifest[cam]
        for key in ("width", "height", "fps", "duration_s", "sha256"):
            if key not in meta:
                raise ValueError(f"{cam} missing {key}")
        durs.append(float(meta["duration_s"]))
    if max(durs) - min(durs) > 0.1:
        raise ValueError(f"duration mismatch: {durs}")


def main() -> int:
    client = connect()
    try:
        run_export(client)
        sftp = client.open_sftp()
        LOCAL_VIDEOS.mkdir(parents=True, exist_ok=True)
        LOCAL_META.mkdir(parents=True, exist_ok=True)

        for fname in ("trajectory.json", "manifest.json", "info.json"):
            r = f"{REMOTE_OUT}/{fname}"
            l = ROOT / "assets" / fname if fname == "trajectory.json" else LOCAL_META / fname
            print(f"GET {r} -> {l}", flush=True)
            sftp.get(r, str(l))

        scp_tree(sftp, f"{REMOTE_OUT}/videos", LOCAL_VIDEOS)
        sftp.close()

        manifest = json.loads((LOCAL_META / "manifest.json").read_text(encoding="utf-8"))
        validate_manifest(manifest)

        build = Path(__file__).resolve().parent / "build_task_json.py"
        if build.exists():
            import subprocess

            subprocess.run([sys.executable, str(build)], check=True)

        embed = Path(__file__).resolve().parent / "embed_demo_data.py"
        if embed.exists():
            import subprocess

            subprocess.run([sys.executable, str(embed)], check=True)

        print("SYNC_OK", flush=True)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
