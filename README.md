# unity-playtest: Claude can't play your Unity game. Now it can test it.

> **v0.1, private preview.** It has been tested by hand on one real Unity 6 + Netcode project. A public sample project and proper evals come in v0.2. See [DESIGN.md](DESIGN.md).

Claude can compile your project and run your unit tests, but it can't play your game. The bugs that reach review usually live in scenes, timing, physics and networking.

**unity-playtest** is a Claude Code skill that turns your feature's "How to test" into evidence. It drives the running Unity Editor, and a local development build, through Unity's own Pipeline CLI.

- **Editor probes.** Finds objects stuck in colliders, blocked spawn spots, missing references, and prefabs missing from the network list, and takes Scene view screenshots.
- **Scripted Play Mode.** Plays through your game's real input path: aim at the target, let your interaction detector pick it, then call the same method the key press calls. It checks state and takes Game view screenshots.
- **Host + client.** Runs the Editor as host and a development build as client, with simulated latency, and checks every step on both peers. It also sends intents a real client couldn't send, such as from too far away or through a wall, to prove your server rejects them.
- **Honest report.** A checklist with pass, fail and skip. Each case says whether a script or a human verified it. Feel, sound and visuals are never marked passed by a script.

On its first real project, a Unity 6 + Netcode co-op game, it found three bugs that tests and code review had missed. They are listed in [DESIGN.md](DESIGN.md#proof-it-is-worth-it).

## Requirements

- Unity 6 with `com.unity.pipeline` (tested 0.8.0-exp.1) and the `unity` CLI
- Claude Code
- For host + client: Netcode for GameObjects 2.x with Unity Transport 2.x (other stacks: adapter notes welcome)
- Tested on Windows

## Install

In Claude Code:

```
/plugin marketplace add GhazaGG/Unity-Playtest-for-Claude
/plugin install unity-playtest@unity-playtest
```

Or copy `skills/unity-playtest/` into `~/.claude/skills/`.

## Use

Open your project in the Unity Editor, then just ask:

> playtest the door-and-key feature from this PR's "How to test"

> before I push, check Level01 for objects stuck in colliders and broken references

> run host + client with 120 ms latency and make sure a client can't pick things up from across the room

The first time, Claude runs `doctor.py --init`. That checks your setup and creates `.playtest/` in your project, a folder
that ignores itself in git, so nothing it writes shows up in `git status`. Then it maps how your game's interact key
works into `.playtest/adapter.cs`, so scripted presses take the same code path a player's key press does.

It asks before anything that changes project settings: the host + client run needs a development build with the
Pipeline runtime turned on for a moment. Claude turns it off again and reverts what the build touched.

You can run the scripts yourself too:

```bash
python skills/unity-playtest/scripts/doctor.py --project path/to/YourUnityProject
python skills/unity-playtest/scripts/drive.py --project path/to/YourUnityProject ready my_step wait:1 cap:after
```

## What it will not do

- Judge feel, sound or looks. Those cases come back as "needs a human", with what to check.
- Install packages, or edit `.unity`, `.prefab` or `.meta` files by hand. Everything goes through the Editor.
- Leave a runtime-enabled build or a changed setting behind. `doctor.py` fails if it does.

## License

MIT
