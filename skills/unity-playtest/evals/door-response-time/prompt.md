---
tags: [unity-playtest]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Our design note says a client on about 120 ms ping should see the door start to open within 0.25 s of pressing E. Measure it in a real host + client session and tell me whether we meet it. The project in this folder (Unity-Playtest-Sample) is open in the Unity Editor, and Unity's Pipeline CLI (`unity`) is on PATH. You may make a temporary development build for the client, with the Pipeline runtime if you need it, but leave the project the way you found it.
