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
from retail_store.shelf_bottle.shelf_task_env import BOTTLE_TASK_ENV_ID
from retail_store.shelf_bottle.shelf_task_solver import ShelfBottleSolver, SolverPhase

for rm in [None, "rgb_array"]:
    for rb in ["cpu", "none"]:
        try:
            kwargs = dict(
                obs_mode="state_dict",
                reward_mode="none",
                control_mode="pd_joint_pos",
                sim_backend="cpu",
                render_backend=rb,
                num_envs=1,
            )
            if rm is not None:
                kwargs["render_mode"] = rm
            env = gym.make(BOTTLE_TASK_ENV_ID, **kwargs)
            env.reset(seed=1001, options=dict(reconfigure=True, bottle_name="shelf_B_water_bottle_1_2_4", robot_xy=[0.05,1.4], robot_yaw=0.0))
            solver = ShelfBottleSolver(env, debug=False, record_trajectory=True, video_cameras=())
            result = solver.solve(max_steps=2000)
            print("OK", rm, rb, result.phase, result.total_steps, len(solver.trajectory))
            env.close()
            break
        except Exception as e:
            print("FAIL", rm, rb, type(e).__name__, str(e)[:100])
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(env["WESTC_HOST"], port=int(env["WESTC_PORT"]), username=env["WESTC_USER"], password=env["WESTC_PASSWORD"], timeout=60)
sftp = c.open_sftp()
with sftp.file("/tmp/probe_no_render.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, o, e = c.exec_command(f"cd /root/autodl-tmp && PYTHONPATH=/root/autodl-tmp {PY} -u /tmp/probe_no_render.py", timeout=900)
print(o.read().decode("utf-8", errors="replace"))
print(e.read().decode("utf-8", errors="replace")[-3000:])
c.close()
