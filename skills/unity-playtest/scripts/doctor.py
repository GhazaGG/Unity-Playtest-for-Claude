#!/usr/bin/env python3
"""Check that a Unity project is ready for unity-playtest, and that a run left nothing behind.

Usage:
  doctor.py [--project DIR]          check, before and after a run
  doctor.py [--project DIR] --init   also create the self-ignoring .playtest/ folder with templates
  doctor.py --init --from DIR        take PROJECT.md and adapter.cs from DIR (a map shared by several worktrees)
  doctor.py --save DIR               copy this project's PROJECT.md and adapter.cs to DIR for the next worktree

Exits 1 when a check FAILs; WARN lines do not change the exit code. Python 3.8+, stdlib only.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
# The project-specific files that recon writes; every working copy of one game can share them.
MAP_FILES = ("PROJECT.md", "adapter.cs")
RUNTIME_CONFIG = Path("ProjectSettings/Packages/com.unity.pipeline/RuntimePipelineConfig.json")


def find_project(start):
    path = Path(start).resolve()
    for candidate in [path, *path.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").is_file():
            return candidate
    return None


def editor_row(listing, project):
    """The `unity pipeline list` row whose Path column is this project, as cells, or []. An exact match: one project
    path can be a prefix of another (MyGame and MyGame-B)."""
    # Columns: Project, Path, PID, Running, Pipeline, Version, Update, Port, Server Reachable, Safe Mode
    want = str(Path(project).resolve()).rstrip("\\/").lower()
    for line in listing.splitlines():
        cells = line.split("\t")
        if len(cells) > 1 and cells[1].strip().rstrip("\\/").lower() == want:
            return cells
    return []


def init_workspace(project, shared=None):
    """.playtest/ with a .gitignore of '*': git ignores the folder and everything in it, and the project's own
    .gitignore stays untouched. With `shared`, the map files come from there unless this copy already filled them in."""
    work = project / ".playtest"
    for sub in ("steps", "shots", "builds"):
        (work / sub).mkdir(parents=True, exist_ok=True)
    ignore = work / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# unity-playtest output: never committed.\n*\n", encoding="utf-8")
    for name in ("PROJECT.md", "CHECKLIST.md", "REPORT.md", "adapter.cs"):
        target = work / name
        if not target.exists() and (TEMPLATES / name).is_file():
            target.write_text((TEMPLATES / name).read_text(encoding="utf-8"), encoding="utf-8")
    if shared is not None:
        for name in MAP_FILES:
            source, target = Path(shared) / name, work / name
            if source.is_file() and (not target.exists() or is_template(target)):
                shutil.copyfile(source, target)
    return work


def is_template(path):
    template = TEMPLATES / path.name
    return template.is_file() and path.read_text(encoding="utf-8") == template.read_text(encoding="utf-8")


def save_map(project, dest):
    """Copy the filled-in map files to `dest`; returns the names copied. Templates are skipped, so an empty map never
    overwrites a good one."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for name in MAP_FILES:
        source = project / ".playtest" / name
        if source.is_file() and not is_template(source):
            shutil.copyfile(source, dest / name)
            saved.append(name)
    return saved


def leftovers(project):
    """(level, message) for things a playtest run must not leave behind."""
    found = []
    config = project / RUNTIME_CONFIG
    if config.is_file():
        try:
            settings = json.loads(config.read_text(encoding="utf-8"))
            # enableInBuilds up to Pipeline 0.8; enableInDevelopmentBuilds / enableInReleaseBuilds from 0.9
            enabled = any(v is True for k, v in settings.items() if k.startswith("enableIn") and k.endswith("Builds"))
        except (ValueError, AttributeError):
            enabled = None
        if enabled:
            found.append(("FAIL", f"{RUNTIME_CONFIG} turns the runtime on for builds: they now ship the Pipeline runtime. "
                                  "Turn it off (settings.runtime_pipeline set; set_runtime_pipeline_settings before 0.9) and delete the file if the run created it."))
    player_settings = project / "ProjectSettings" / "ProjectSettings.asset"
    # Pipeline 0.9 keeps the toggle as a scripting define instead of the config file.
    if player_settings.is_file() and "ENABLE_RUNTIME_PIPELINE" in player_settings.read_text(encoding="utf-8", errors="replace"):
        found.append(("FAIL", "ProjectSettings.asset defines ENABLE_RUNTIME_PIPELINE: builds now ship the Pipeline runtime. "
                              "Turn it off (settings.runtime_pipeline set with false)."))
    if (project / "Assets" / "Temp").exists():
        found.append(("WARN", "Assets/Temp exists: usually a screenshot taken with --save_path. Delete it through the "
                              "Editor (delete_asset --asset Assets/Temp --confirm true)."))
    pipeline_settings = project / "Assets" / "Settings" / "Pipeline"
    if pipeline_settings.is_dir() and not any(p.suffix != ".meta" for p in pipeline_settings.rglob("*") if p.is_file()):
        found.append(("WARN", "Assets/Settings/Pipeline is empty: left by a Pipeline build. Delete it through the Editor."))
    return found


def git_changes(project):
    if not shutil.which("git"):
        return []
    done = subprocess.run(["git", "-C", str(project), "status", "--porcelain"], capture_output=True, text=True)
    if done.returncode != 0:
        return []
    watched = ("Assets/", "ProjectSettings/", "Packages/")
    return [line for line in done.stdout.splitlines() if line[3:].startswith(watched)]


def pipeline_version(project):
    manifest = project / "Packages" / "manifest.json"
    if not manifest.is_file():
        return None
    deps = json.loads(manifest.read_text(encoding="utf-8")).get("dependencies", {})
    return deps.get("com.unity.pipeline")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=".")
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--from", dest="shared", metavar="DIR", help="with --init: shared PROJECT.md and adapter.cs")
    parser.add_argument("--save", metavar="DIR", help="copy the filled-in PROJECT.md and adapter.cs to DIR")
    args = parser.parse_args(argv)

    project = find_project(args.project)
    if project is None:
        print("FAIL no Unity project found (ProjectSettings/ProjectVersion.txt)")
        return 1
    failed = False

    def report(level, message):
        nonlocal failed
        failed |= level == "FAIL"
        print(f"{level:4} {message}")

    version = re.search(r"m_EditorVersion:\s*(\S+)", (project / "ProjectSettings/ProjectVersion.txt").read_text())
    report("OK", f"Unity project {project} (Editor {version.group(1) if version else 'unknown'})")

    exe = shutil.which("unity")
    report("OK" if exe else "FAIL", f"unity CLI: {exe}" if exe else "unity CLI not on PATH (see references/pipeline-cheatsheet.md)")

    pipeline = pipeline_version(project)
    report("OK" if pipeline else "FAIL",
           f"com.unity.pipeline {pipeline}" if pipeline else "com.unity.pipeline is not in Packages/manifest.json")

    if exe:
        listing = subprocess.run([exe, "pipeline", "list", "--no-banner"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout
        cells = editor_row(listing, project)
        if not cells:
            report("WARN", "no open Editor for this project: open it before Editor or Play Mode steps")
        elif len(cells) > 8 and cells[8].strip().lower() == "true":
            report("OK", "Editor open and Pipeline server reachable")
        else:
            report("WARN", "Editor found but Pipeline server not reachable yet (still loading, or a domain reload)")

    if args.init:
        work = init_workspace(project, args.shared)
        report("OK", f"workspace {work} (git ignores it through its own .gitignore)")
        if args.shared:
            filled = [n for n in MAP_FILES if not is_template(work / n)]
            report("OK" if filled else "WARN", f"map from {args.shared}: {', '.join(filled)}" if filled
                   else f"no filled-in map in {args.shared}: do recon, then doctor.py --save {args.shared}")
        if not TEMPLATES.is_dir():  # a marketplace that runs this script on its own, away from the skill's files
            report("WARN", "templates are not next to doctor.py: write the skill's templates/*.md, templates/adapter.cs"
                           f" and scripts/prelude.cs into {work} yourself")
    elif not (project / ".playtest" / ".gitignore").is_file():
        report("WARN", "no .playtest/ yet: run doctor.py --init")

    if args.save:
        saved = save_map(project, args.save)
        report("OK" if saved else "WARN", f"map saved to {args.save}: {', '.join(saved)}" if saved
               else "nothing to save: PROJECT.md and adapter.cs are still the templates")

    for level, message in leftovers(project):
        report(level, message)
    changes = git_changes(project)
    if changes:
        report("WARN", "uncommitted changes under Assets/, ProjectSettings/ or Packages/ (check that the run did not make them):")
        for line in changes[:20]:
            print(f"       {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
