---
tags: [unity-playtest]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Playtest the new in-game menu solo, using the How to test from the PR:

1. Play from the Menu scene and press Host.
2. Press Esc: the menu opens, and E does nothing while it is open.
3. Press Esc again: the menu closes.
4. Take the key from the table with E.
5. Open the menu with Esc and close it with Resume, then unlock the door with E.

The project in this folder (Unity-Playtest-Sample) is open in the Unity Editor, and Unity's Pipeline CLI (`unity`) is on PATH. Tell me what passes and what doesn't.
