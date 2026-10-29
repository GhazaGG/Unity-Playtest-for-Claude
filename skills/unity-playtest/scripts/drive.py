#!/usr/bin/env python3
"""Run playtest steps against the Unity Editor, or a player build, through the Unity Pipeline CLI.

Usage:
  drive.py [--project DIR] [--player BUILD_DIR] STEP [STEP ...]

A STEP is one of:
  NAME         runs .playtest/steps/NAME.cs, after prelude.cs and .playtest/adapter.cs
  status       prints the adapter's Status() line (built in; a steps/status.cs replaces it)
  wait:SEC     sleeps for SEC seconds (a float is fine)
  until:KEY    waits until a value kept by PtUntil, PtWatch, PtAt or PtKey (key.E) is no longer "waiting", and prints it
  ready        waits until the Editor is idle and answers an eval (Editor only)
  cap:NAME     saves the Game view (a player's screen with --player) to .playtest/shots/NAME.png
  scene:NAME   saves the Scene view to .playtest/shots/NAME.png (Editor only)

Every step prints [NAME] followed by the step's result or the CLI error. A result longer than 40 lines prints its
first and last lines only, and the whole text goes to .playtest/out/NAME.txt (--full prints everything). Screenshots
are taken inline and decoded here. capture_*_view --save_path is never used, because it writes into Assets/.
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
HEAD_LINES, TAIL_LINES = 35, 5  # a probe's summary or count line comes last, so keep the tail too

# Editor steps only. An unfocused Editor can stop running Play Mode frames altogether (Time.frameCount stays put)
# until something asks for updates. While playing, ask for a player-loop update on every Editor tick. The callback
# removes itself once Play Mode ends, so it never spins the Editor in Edit Mode, and the captured name ptKeep marks it
# so later steps don't add a second one.
EDITOR_KEEPALIVE = """\
UnityEditor.EditorApplication.CallbackFunction ptKeep = null;
ptKeep = () => { if (UnityEditor.EditorApplication.isPlaying) UnityEditor.EditorApplication.QueuePlayerLoopUpdate(); else UnityEditor.EditorApplication.update -= ptKeep; };
var ptUpdate = UnityEditor.EditorApplication.update;
if (UnityEditor.EditorApplication.isPlaying && (ptUpdate == null || !System.Array.Exists(ptUpdate.GetInvocationList(), d => d.Target != null && d.Target.GetType().GetField("ptKeep") != null)))
    UnityEditor.EditorApplication.update += ptKeep;
"""


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


# Pipeline 0.9 groups its commands ("script eval"); 0.8 and older use flat names ("eval"). Callers pass the 0.8 name.
GROUPED = {
    "eval": ["script", "eval"], "eval_file": ["script", "eval_file"], "editor_status": ["editor", "status"],
    "capture_game_view": ["capture", "game_view"], "capture_scene_view": ["capture", "scene_view"],
}
_grouped = None  # None until the first call tells which naming the Pipeline speaks


def unity(args, player=None, timeout=90, project=None):
    global _grouped
    exe = shutil.which("unity")
    if not exe:
        sys.exit("The `unity` CLI is not on PATH. See references/pipeline-cheatsheet.md.")
    target = ["--runtime-path", str(player)] if player else ["--project-path", str(project)] if project else []
    name, rest = args[0], list(args[1:])
    tries = [True, False] if _grouped is None else [_grouped]
    for grouped in tries:
        command = GROUPED.get(name, [name]) if grouped else [name]
        extra = ["--omit-nulls"] if grouped else []
        try:
            done = subprocess.run([exe, "command", *target, *command, *rest, *extra, "--no-banner", "--result-only"],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout}s: {name}"
        ok, data = parse(done.stdout or done.stderr)
        unknown = not ok and ("not found" in str(data).lower() or "no command named" in str(data).lower())
        if not unknown or name not in GROUPED:
            if _grouped is None and name in GROUPED and (ok or not unknown):
                _grouped = grouped
            return ok, data
    return ok, data


def build_source(step_body, adapter_text, editor=True):
    """[keepalive] + prelude + adapter + step + return. The order matters: the step uses names from both."""
    parts = [EDITOR_KEEPALIVE] if editor else []
    parts += [PRELUDE.read_text(encoding="utf-8"), adapter_text, step_body, "return sb.ToString();", ""]
    return "\n".join(parts)


def cap_output(name, text, work):
    """Long step output costs the caller tokens on every run. Print the head and tail; keep the rest in a file."""
    lines = text.splitlines()
    if len(lines) <= HEAD_LINES + TAIL_LINES:
        return text
    out = work / "out" / f"{name}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    cut = len(lines) - HEAD_LINES - TAIL_LINES
    return "\n".join(lines[:HEAD_LINES] + [f"... {cut} more lines, all {len(lines)} in {out}"] + lines[-TAIL_LINES:])


def find_image(data):
    """capture_*_view returns the PNG as base64 under a key that differs by version; take the longest string."""
    if not isinstance(data, dict):
        return None
    strings = [v for v in data.values() if isinstance(v, str) and len(v) > 1000]
    return max(strings, key=len) if strings else None


def capture_player(name, work, player):
    """Players have no capture_* command, so ask the player to write its own screen and wait for the file."""
    out = (work / "shots" / f"{name}.png").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    path = str(out).replace("\\", "/")
    ok, data = unity(["eval", "--code", f'UnityEngine.ScreenCapture.CaptureScreenshot("{path}"); return "ok";'], player)
    if not ok:
        return f"[{name}] capture failed: {data}"
    for _ in range(50):  # written at the end of the player's next frame
        if out.exists() and out.stat().st_size:
            return f"[{name}] saved {out}"
        time.sleep(0.1)
    return f"[{name}] capture failed: no file after 5 s"


def wait_kept(key, player, project, limit=90):
    """Poll a value PtUntil, PtWatch, PtAt or PtKey keeps, until it stops "waiting". Ends a wait as soon as the game
    gets there, instead of a fixed wait: that is slow when the game is fast, and flaky when the Editor is not."""
    code = f'return (string)System.AppDomain.CurrentDomain.GetData("unity-playtest.{key}") ?? "-";'
    value = "-"
    for _ in range(limit * 2):
        ok, data = unity(["eval", "--code", code], player, project=project, timeout=15)
        value = (data.get("result") if isinstance(data, dict) else data) if ok else data
        if ok and not str(value).startswith("waiting"):
            return f"[until:{key}] {value}"
        time.sleep(0.5)
    return f"[until:{key}] still {value} after {limit} s"


def run_step(step, work, player, full=False):
    project = work.parent
    if step.startswith("wait:"):
        time.sleep(float(step[5:]))
        return None
    if step.startswith("until:"):
        return wait_kept(step[6:], player, project)
    if step == "ready":
        if player:
            return "[ready] skipped: Editor only"
        for _ in range(120):
            ok, data = unity(["editor_status"], project=project)
            # status is "ready" in Edit Mode and "playing" (or "paused") in Play Mode.
            if ok and isinstance(data, dict) and data.get("status") in ("ready", "playing", "paused") \
                    and not data.get("compiling") and not data.get("domainReloadInProgress"):
                # editor_status can say ready a few seconds before eval works, right after a domain reload.
                answered, _ = unity(["eval", "--code", 'return "ok";'], project=project, timeout=15)
                if answered:
                    return "[ready] Editor ready, play mode " + str(data.get("playMode"))
            time.sleep(1)
        return "[ready] gave up after 120 s"
    for prefix, command in (("cap:", "capture_game_view"), ("scene:", "capture_scene_view")):
        if step.startswith(prefix):
            name = step[len(prefix):]
            if player:
                if prefix == "scene:":
                    return f"[{name}] skipped: players have no Scene view"
                return capture_player(name, work, player)
            ok, data = unity([command], project=project)
            image = find_image(data) if ok else None
            if not image:
                return f"[{name}] capture failed: {data if not ok else 'no image in result'}"
            out = work / "shots" / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(image))
            return f"[{name}] saved {out}"
    step_file = work / "steps" / f"{step}.cs"
    if step_file.is_file():
        body = step_file.read_text(encoding="utf-8")
    elif step == "status":
        body = "sb.Append(Status());"  # built in, unless the project has its own status.cs
    else:
        return f"[{step}] no such step file: {step_file}"
    adapter = work / "adapter.cs"
    source = build_source(body, adapter.read_text(encoding="utf-8") if adapter.is_file() else "", editor=not player)
    # One file per target, so an Editor step and a player step started together (a race) don't overwrite each other.
    run_file = work / (f"_run.{Path(player).resolve().name}.cs" if player else "_run.cs")
    run_file.write_text(source, encoding="utf-8")
    ok, data = unity(["eval_file", "--file", str(run_file), "--timeout", "30"], player, project=project)
    if ok and isinstance(data, dict):
        data = data.get("result")
    return f"[{step}] {data if full else cap_output(step, str(data), work)}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=".", help="Unity project folder (default: search upwards from here)")
    parser.add_argument("--player", help="player build folder that holds .unity-pipeline-runtime-port")
    parser.add_argument("--full", action="store_true", help="print long step results whole instead of head and tail")
    parser.add_argument("steps", nargs="+")
    args = parser.parse_args(argv)
    work = find_project(args.project) / ".playtest"
    if not work.is_dir():
        sys.exit(f"{work} does not exist yet. Run: python doctor.py --init")
    for step in args.steps:
        line = run_step(step, work, args.player, args.full)
        if line:
            print(line, flush=True)


if __name__ == "__main__":
    main()
