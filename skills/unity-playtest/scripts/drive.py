#!/usr/bin/env python3
"""Run playtest steps against the Unity Editor, or a player build, through the Unity Pipeline CLI.

Usage:
  drive.py [--project DIR] [--player BUILD_DIR] STEP [STEP ...]

A STEP is one of:
  NAME         runs .playtest/steps/NAME.cs, after prelude.cs and .playtest/adapter.cs
  wait:SEC     sleeps for SEC seconds (a float is fine)
  ready        waits until the Editor is idle: not compiling, no domain reload (Editor only)
  cap:NAME     saves the Game view to .playtest/shots/NAME.png (Editor only)
  scene:NAME   saves the Scene view to .playtest/shots/NAME.png (Editor only)

Every step prints one line: [NAME] followed by the step's result or the CLI error. Screenshots are taken inline
and decoded here. capture_*_view --save_path is never used, because it writes into Assets/.
Python 3.8+, stdlib only.
"""
import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PRELUDE = Path(__file__).resolve().parent / "prelude.cs"


def find_project(start):
    """The nearest folder at or above `start` that holds ProjectSettings/ProjectVersion.txt."""
    path = Path(start).resolve()
    for candidate in [path, *path.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").is_file():
            return candidate
    sys.exit(f"No Unity project at or above {path} (looked for ProjectSettings/ProjectVersion.txt).")


def parse(raw):
    """Pipeline CLI output (--result-only JSON) to (ok, value). The value is the result or an error message."""
    raw = (raw or "").strip()
    try:
        data = json.loads(raw)
    except ValueError:
        return False, raw[:800] or "(no output)"
    if isinstance(data, dict) and data.get("success") is False:
        errors = data.get("errors") or [{"message": data.get("error", "")}]
        return False, "; ".join(str(e.get("message", "")) for e in errors).strip() or raw[:800]
    return True, data


def unity(args, player=None, timeout=90):
    exe = shutil.which("unity")
    if not exe:
        sys.exit("The `unity` CLI is not on PATH. See references/pipeline-cheatsheet.md.")
    cmd = [exe, "command"]
    if player:
        cmd += ["--runtime-path", str(player)]  # the folder holding .unity-pipeline-runtime-port
    cmd += list(args) + ["--no-banner", "--result-only"]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s: {' '.join(args[:1])}"
    return parse(done.stdout or done.stderr)


def build_source(step_body, adapter_text):
    """prelude + adapter + step + return. The order matters: the step uses names from both."""
    return "\n".join([PRELUDE.read_text(encoding="utf-8"), adapter_text, step_body, "return sb.ToString();", ""])


def find_image(data):
    """capture_*_view returns the PNG as base64 under a key that differs by version; take the longest string."""
    if not isinstance(data, dict):
        return None
    strings = [v for v in data.values() if isinstance(v, str) and len(v) > 1000]
    return max(strings, key=len) if strings else None


def run_step(step, work, player):
    if step.startswith("wait:"):
        time.sleep(float(step[5:]))
        return None
    if step == "ready":
        if player:
            return "[ready] skipped: Editor only"
        for _ in range(120):
            ok, data = unity(["editor_status"])
            if ok and isinstance(data, dict) and data.get("status") == "ready" and not data.get("compiling") \
                    and not data.get("domainReloadInProgress"):
                return "[ready] Editor ready, play mode " + str(data.get("playMode"))
            time.sleep(1)
        return "[ready] gave up after 120 s"
    for prefix, command in (("cap:", "capture_game_view"), ("scene:", "capture_scene_view")):
        if step.startswith(prefix):
            name = step[len(prefix):]
            if player:
                return f"[{name}] skipped: players have no {command}"
            ok, data = unity([command])
            image = find_image(data) if ok else None
            if not image:
                return f"[{name}] capture failed: {data if not ok else 'no image in result'}"
            out = work / "shots" / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(image))
            return f"[{name}] saved {out}"
    step_file = work / "steps" / f"{step}.cs"
    if not step_file.is_file():
        return f"[{step}] no such step file: {step_file}"
    adapter = work / "adapter.cs"
    source = build_source(step_file.read_text(encoding="utf-8"),
                          adapter.read_text(encoding="utf-8") if adapter.is_file() else "")
    run_file = work / "_run.cs"
    run_file.write_text(source, encoding="utf-8")
    ok, data = unity(["eval_file", "--file", str(run_file), "--timeout", "30"], player)
    if ok and isinstance(data, dict):
        data = data.get("result")
    return f"[{step}] {data}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=".", help="Unity project folder (default: search upwards from here)")
    parser.add_argument("--player", help="player build folder that holds .unity-pipeline-runtime-port")
    parser.add_argument("steps", nargs="+")
    args = parser.parse_args(argv)
    work = find_project(args.project) / ".playtest"
    if not work.is_dir():
        sys.exit(f"{work} does not exist yet. Run: python doctor.py --init")
    for step in args.steps:
        line = run_step(step, work, args.player)
        if line:
            print(line, flush=True)


if __name__ == "__main__":
    main()
