#!/usr/bin/env python3
"""Build the Agensi listing zip: SKILL.md at the root, with the skill's references, scripts and templates.

Usage: python tools/package_agensi.py   ->   dist/unity-playtest-<version>-agensi.zip

The evals stay out (they spell out the sample's planted bugs). The listing fields Agensi reads from the frontmatter
are added to the zipped SKILL.md only, so the repo's SKILL.md keeps the plain name + description that skill loaders
validate. Python 3.8+, stdlib only.
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "unity-playtest"
KEEP = ("references", "scripts", "templates")

LISTING = """summary: Claude playtests your Unity game through Unity's Pipeline CLI, presses real keys, runs host + client with latency, and reports pass/fail without overclaiming.
version: {version}
tags: [unity, game-testing, playtesting, qa, multiplayer]
keywords: [unity, unity3d, playtest, play mode, netcode, input system, pipeline cli, game qa]
use_cases:
  - Run a PR's "How to test" in Play Mode and get pass/fail with evidence
  - Find objects stuck in colliders, blocked spawn points and missing references in a scene
  - Test host + client sessions with latency, late joiners and races (Netcode for GameObjects)
  - Check that the server refuses forged client requests
docs_url: https://github.com/GhazaGG/Unity-Playtest-for-Claude
"""


def skill_md(version):
    """SKILL.md with the listing fields added just before the closing --- of its frontmatter."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    end = text.index("\n---", 3)
    return text[:end] + "\n" + LISTING.format(version=version).rstrip("\n") + text[end:]


def main():
    version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    out = ROOT / "dist" / f"unity-playtest-{version}-agensi.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("SKILL.md", skill_md(version))
        z.write(ROOT / "LICENSE", "LICENSE")
        for folder in KEEP:
            for path in sorted((SKILL / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    z.write(path, path.relative_to(SKILL).as_posix())
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    print(f"{out} ({out.stat().st_size // 1024} KB, {len(names)} files)")
    for name in names:
        print("  " + name)


if __name__ == "__main__":
    main()
