---
tags: [unity-playtest]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Playtest the door-and-key feature solo, using the How to test from the PR:

1. Play from the Menu scene and press Host.
2. Without the key, look at the door: the HUD says Locked, and E does nothing.
3. Take the key from the table with E.
4. Press E on the door: it swings open.
5. Walk through the doorway into the second room and take a coin there.

The project in this folder (Unity-Playtest-Sample) is open in the Unity Editor, and Unity's Pipeline CLI (`unity`) is on PATH. Tell me what passes and what doesn't.
