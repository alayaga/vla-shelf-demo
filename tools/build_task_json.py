#!/usr/bin/env python3
"""Build assets/meta/task.json from pi05_retail_sync test/info.json."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 20
VLA_PHASES = {"ARM_RAISE", "GRASP_CLOSE", "PLACE", "RELEASE"}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = (
    ROOT.parent / "AutoDL" / "pi05_retail_sync" / "test" / "info.json"
)
OUT = ROOT / "assets" / "meta" / "task.json"


def control(phase: str) -> str:
    return "vla" if phase in VLA_PHASES else "code"


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--info", type=Path, default=DEFAULT_SRC)
    args = ap.parse_args()
    src = args.info
    if not src.exists():
        exported = ROOT / "assets" / "meta" / "info.json"
        if exported.exists():
            src = exported
        else:
            raise SystemExit(f"info.json not found: {args.info}")
    info = json.loads(src.read_text(encoding="utf-8"))
    phase_spans = info["phase_spans"]
    phases = []
    for name, span in phase_spans.items():
        start, end = int(span[0]), int(span[1])
        phases.append(
            {
                "id": name,
                "label_zh": name.replace("_", " "),
                "control": control(name),
                "step_start": start,
                "step_end": end,
                "time_start": round(start / FPS, 4),
                "time_end": round(end / FPS, 4),
            }
        )
    phases.sort(key=lambda p: p["step_start"])

    div = info["division"]
    segments = [
        {
            "id": "code_pre_grasp",
            "label_zh": "Code · 导航到站",
            "control": "code",
            "step_start": div["code_pre_grasp"]["start"],
            "step_end": div["code_pre_grasp"]["end"],
            "time_start": round(div["code_pre_grasp"]["start"] / FPS, 4),
            "time_end": round(div["code_pre_grasp"]["end"] / FPS, 4),
        },
        {
            "id": "vla_grasp",
            "label_zh": "VLA · 抓取",
            "control": "vla",
            "step_start": div["vla_grasp"]["start"],
            "step_end": div["vla_grasp"]["end"],
            "time_start": round(div["vla_grasp"]["start"] / FPS, 4),
            "time_end": round(div["vla_grasp"]["end"] / FPS, 4),
        },
        {
            "id": "code_transport",
            "label_zh": "Code · 搬运",
            "control": "code",
            "step_start": 212,
            "step_end": 908,
            "time_start": round(212 / FPS, 4),
            "time_end": round(908 / FPS, 4),
        },
        {
            "id": "vla_place",
            "label_zh": "VLA · 放置",
            "control": "vla",
            "step_start": div["vla_place"]["start"],
            "step_end": div["vla_place"]["end"],
            "time_start": round(div["vla_place"]["start"] / FPS, 4),
            "time_end": round(div["vla_place"]["end"] / FPS, 4),
        },
    ]

    payload = {
        "title": "SmartRetail Shelf Bottle — Hybrid VLA Demo",
        "bottle_name": info["bottle_name"],
        "seed": info["seed"],
        "fps": FPS,
        "total_steps": info["steps"],
        "total_time_s": round(info["steps"] / FPS, 4),
        "cameras": info["cameras"],
        "instructions": {
            "grasp": "Pick up the water bottle from the shelf.",
            "place": "Place the water bottle onto the checkout counter.",
        },
        "result": info.get("result", {}),
        "phases": phases,
        "segments": segments,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
