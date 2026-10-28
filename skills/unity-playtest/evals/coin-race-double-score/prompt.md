---
tags: [unity-playtest]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Playtesters on about 120 ms ping say the coin count sometimes jumps by 20 instead of 10 when two of them grab the same coin at once. Reproduce it in a real host + client session and tell me how often it happens and why. The project in this folder (Unity-Playtest-Sample) is open in the Unity Editor, and Unity's Pipeline CLI (`unity`) is on PATH. You may make a temporary development build for the client, with the Pipeline runtime if you need it, but leave the project the way you found it.
