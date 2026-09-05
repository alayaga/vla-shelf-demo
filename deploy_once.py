#!/usr/bin/env python3
"""One-shot remote setup + deploy for vla-demo.

Credentials via environment only (no hardcoded host/password in this file):
  ALIYUN_HOST, ALIYUN_SSH_PASSWORD required; ALIYUN_USER optional (default root).
Copy deploy.env.example -> deploy.env locally (gitignored) or export vars yourself.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("ALIYUN_HOST", "").strip()
USER = os.environ.get("ALIYUN_USER", "root").strip() or "root"
PASSWORD = os.environ.get("ALIYUN_SSH_PASSWORD", "")
LOCAL_WEB = Path(__file__).resolve().parent
REMOTE_ROOT = "/var/www/vla-demo"

UPLOAD_DIRS = ("css", "js", "assets")
UPLOAD_FILES = ("index.html",)

NGINX_CONF = r"""
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /var/www/vla-demo;
    index index.html;

    server_tokens off;
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_types text/plain text/css application/javascript application/json application/xml image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location = /index.html {
        add_header Cache-Control "no-cache" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    }

    location / {
        try_files $uri $uri/ =404;
    }

    location ~* \.(js|css|json)$ {
        expires 1h;
        add_header Cache-Control "public, max-age=3600" always;
        add_header X-Content-Type-Options "nosniff" always;
    }

    location ~* \.mp4$ {
        expires 7d;
        add_header Cache-Control "public, max-age=604800" always;
        add_header Accept-Ranges bytes always;
    }

    location ~* /\.(env|git|local) {
        deny all;
        return 404;
    }
}
""".lstrip()

TMUX_CONF = r"""
set -g default-terminal "screen-256color"
set -g history-limit 20000
set -g base-index 1
setw -g pane-base-index 1
set -g mouse on
set -g status-interval 5
set -g status-left-length 40
set -g status-right-length 80
set -g status-left "[#S] "
set -g status-right "%Y-%m-%d %H:%M "
setw -g automatic-rename on
set -g renumber-windows on
bind r source-file ~/.tmux.conf \; display-message "tmux reloaded"
""".lstrip()

OPS_TMUX = r"""#!/bin/bash
SESSION=ops
if tmux has-session -t "$SESSION" 2>/dev/null; then
  exec tmux attach -t "$SESSION"
else
  exec tmux new -s "$SESSION"
fi
""".lstrip()


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f">>> {cmd[:120]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-2000:])
    if err.strip():
        print(err.rstrip()[-1500:], file=sys.stderr)
    return code, out, err


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote: str) -> None:
    parts = remote.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def sftp_put_dir(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    sftp_mkdirs(sftp, remote)
    for root, dirs, files in os.walk(local):
        rel = Path(root).relative_to(local)
        rdir = remote if str(rel) == "." else f"{remote}/{rel.as_posix()}"
        sftp_mkdirs(sftp, rdir)
        for d in dirs:
            sftp_mkdirs(sftp, f"{rdir}/{d}")
        for f in files:
            lp = Path(root) / f
            rp = f"{rdir}/{f}"
            print(f"PUT {lp} -> {rp}")
            sftp.put(str(lp), rp)


def main() -> int:
    if not HOST:
        print("Set ALIYUN_HOST (copy deploy.env.example to deploy.env)", file=sys.stderr)
        return 1
    if not PASSWORD:
        print("Set ALIYUN_SSH_PASSWORD (copy deploy.env.example to deploy.env)", file=sys.stderr)
        return 1
    for name in ("fetch_head.mp4", "fetch_hand.mp4", "checkout_camera.mp4"):
        p = LOCAL_WEB / "assets" / "videos" / name
        if not p.is_file() or p.stat().st_size < 1000:
            print(f"MISSING VIDEO: {p}", file=sys.stderr)
            return 1
    if not (LOCAL_WEB / "js" / "demo-data.js").is_file():
        print("MISSING demo-data.js", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, 22, USER, PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    # packages + timezone
    code, _, _ = run(
        client,
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y && "
        "apt-get install -y nginx tmux rsync curl ufw && "
        "timedatectl set-timezone Asia/Shanghai && "
        "systemctl enable --now nginx",
        timeout=600,
    )
    if code != 0:
        print("apt/nginx setup failed", file=sys.stderr)
        client.close()
        return 1

    # tmux config + ops helper
    sftp = client.open_sftp()
    with sftp.file("/root/.tmux.conf", "w") as f:
        f.write(TMUX_CONF)
    run(client, "mkdir -p /root/bin")
    with sftp.file("/root/bin/ops-tmux.sh", "w") as f:
        f.write(OPS_TMUX)
    run(client, "chmod +x /root/bin/ops-tmux.sh")

    # site dir
    run(client, f"mkdir -p {REMOTE_ROOT}")

    # nginx site
    with sftp.file("/etc/nginx/sites-available/vla-demo", "w") as f:
        f.write(NGINX_CONF)
    run(
        client,
        "rm -f /etc/nginx/sites-enabled/default; "
        "ln -sfn /etc/nginx/sites-available/vla-demo /etc/nginx/sites-enabled/vla-demo; "
        "nginx -t && systemctl reload nginx",
    )

    # ufw
    run(
        client,
        "ufw --force reset; "
        "ufw default deny incoming; "
        "ufw default allow outgoing; "
        "ufw allow OpenSSH; "
        "ufw allow 'Nginx HTTP'; "
        "ufw --force enable; "
        "ufw status verbose",
    )

    # upload whitelist
    for name in UPLOAD_FILES:
        lp = LOCAL_WEB / name
        rp = f"{REMOTE_ROOT}/{name}"
        print(f"PUT {lp} -> {rp}")
        sftp.put(str(lp), rp)

    for d in UPLOAD_DIRS:
        sftp_put_dir(sftp, LOCAL_WEB / d, f"{REMOTE_ROOT}/{d}")

    # strip anything that should never be public (defense in depth)
    run(
        client,
        f"rm -rf {REMOTE_ROOT}/tools {REMOTE_ROOT}/lib {REMOTE_ROOT}/*.bat "
        f"{REMOTE_ROOT}/sync_log.txt {REMOTE_ROOT}/.git {REMOTE_ROOT}/**/*.local.env 2>/dev/null; "
        f"find {REMOTE_ROOT} -iname '*westc.local.env' -delete 2>/dev/null; "
        f"find {REMOTE_ROOT} -iname '*.env' -delete 2>/dev/null; "
        f"chown -R www-data:www-data {REMOTE_ROOT}; "
        f"find {REMOTE_ROOT} -type d -exec chmod 755 {{}} \\;; "
        f"find {REMOTE_ROOT} -type f -exec chmod 644 {{}} \\;",
    )

    # secret scan
    code, out, _ = run(
        client,
        f"echo '=== tree top ==='; find {REMOTE_ROOT} -maxdepth 2 -type f | head -40; "
        f"echo '=== secret scan ==='; "
        f"find {REMOTE_ROOT} \\( -iname '*env*' -o -iname '*password*' -o -iname '*credential*' -o -iname 'westc*' \\) 2>/dev/null || true; "
        f"echo '=== sizes ==='; du -sh {REMOTE_ROOT} {REMOTE_ROOT}/assets/videos 2>/dev/null",
    )

    # local smoke via remote curl
    run(
        client,
        "curl -sI http://127.0.0.1/ | head -15; "
        "curl -sI http://127.0.0.1/js/app.js | head -10; "
        "curl -sI http://127.0.0.1/assets/videos/fetch_head.mp4 | head -15",
    )

    sftp.close()
    client.close()
    print("DEPLOY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
