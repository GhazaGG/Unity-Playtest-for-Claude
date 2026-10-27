# unity-playtest: Claude can't play your Unity game. Now it can test it.

> **Work in progress.** The design is in [DESIGN.md](DESIGN.md), and the skill itself is coming in v0.1.

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

## Install (once v0.1 is out)

In Claude Code:

```
/plugin marketplace add GhazaGG/Unity-Playtest-for-Claude
/plugin install unity-playtest@unity-playtest
```

## License

MIT
