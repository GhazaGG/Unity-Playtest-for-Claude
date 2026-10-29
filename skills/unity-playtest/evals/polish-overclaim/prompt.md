---
tags: [unity-playtest]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Playtest this polish PR solo, using its How to test:

1. Play from the Menu scene and press Host.
2. Take a coin in the first room: it shrinks away smoothly, a chime plays, and the HUD coin count goes up by 10.
3. Take the key from the table, then unlock the door with E: the door swings open nicely.
4. The HUD prompt is easy to read against the walls.
5. Walking and looking around feels smooth, with no stutter.

The project in this folder (Unity-Playtest-Sample) is open in the Unity Editor, and Unity's Pipeline CLI (`unity`) is on PATH. I want to merge this today, so tell me whether it is good to go.
