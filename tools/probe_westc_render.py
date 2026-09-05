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

PY = env.get("WESTC_PYTHON", "/root/autodl-tmp/.venv-maniskill/bin/python")

SCRIPT = r'''
import gymnasium as gym
import retail_store  # noqa
import retail_store.shelf_bottle.shelf_task_env  # noqa
from retail_store.camera_utils import robot_arm_sensor_configs
from retail_store.shelf_bottle.shelf_task_env import BOTTLE_TASK_ENV_ID

for rb in ["cpu", "sapien_cpu", "gpu"]:
    try:
        env = gym.make(
            BOTTLE_TASK_ENV_ID,
            obs_mode="state_dict",
            reward_mode="none",
            control_mode="pd_joint_pos",
            render_mode="rgb_array",
            sim_backend="cpu",
            render_backend=rb,
            num_envs=1,
            sensor_configs=robot_arm_sensor_configs(64, 64),
        )
        env.reset(seed=1001, options=dict(reconfigure=True, bottle_name="shelf_B_water_bottle_1_2_4"))
        frame = env.render()
        print("OK", rb, getattr(frame, "shape", type(frame)))
        env.close()
    except Exception as e:
        print("FAIL", rb, type(e).__name__, str(e)[:120])
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    env["WESTC_HOST"],
    port=int(env["WESTC_PORT"]),
    username=env["WESTC_USER"],
    password=env["WESTC_PASSWORD"],
    timeout=60,
)
sftp = c.open_sftp()
with sftp.file("/tmp/probe_render.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, o, e = c.exec_command(
    f"cd /root/autodl-tmp && PYTHONPATH=/root/autodl-tmp {PY} -u /tmp/probe_render.py",
    timeout=600,
)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err.strip():
    print("ERR", err[-2000:])
c.close()
