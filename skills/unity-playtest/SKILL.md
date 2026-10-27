---
name: unity-playtest
description: Playtest a Unity game for real. Probe scenes in the open Editor, play the feature in Play Mode through the game's own input path, run host + client sessions with simulated latency, and report pass/fail with evidence, all through Unity's Pipeline CLI (com.unity.pipeline). Use whenever the user wants a Unity feature, scene, PR or bug fix tested, playtested, QA'd, smoke-tested or verified in the Editor or in multiplayer, asks "does this actually work in game", or wants a test checklist run, even if they never say "playtest".
---

# Unity playtest

You cannot play the game. This skill replaces playing with four things:
- **probes** that read the open scene;
- **scripted play** through the same code path a key press takes;
- a **second peer**, a local development build, for host + client;
- a **report** that keeps what a script proved apart from what only a person can judge.

The scripts live next to this file:
- `scripts/drive.py` runs step files against the Editor or a player build;
- `scripts/doctor.py` checks the setup and catches leftovers;
- `scripts/prelude.cs` holds reflection helpers that every step gets.

Both Python scripts are stdlib-only and run on Python 3.8+.

Read the reference that matches the layer you are on. Do not read them all up front:
- [pipeline-cheatsheet.md](references/pipeline-cheatsheet.md): exact CLI commands and their quirks
- [editor-probes.md](references/editor-probes.md): layer 1, scene checks with ready-made C# probes
- [scripted-input.md](references/scripted-input.md): layer 2, playing through the real input path, and the adapter
- [host-client.md](references/host-client.md): layers 3 and 4, the client build, latency, both-peer checks, forged intents
- [pitfalls.md](references/pitfalls.md): read this when anything fails in a way that does not make sense

## Step 0: set up (once per project)

1. Run `python <skill>/scripts/doctor.py --init` from the project. It:
   - checks the `unity` CLI, the `com.unity.pipeline` package and whether the Editor is reachable;
   - creates `.playtest/`, a folder that ignores itself in git (its own `.gitignore` is `*`), so nothing the
     playtest writes ever shows up in `git status`;
   - copies the templates into `.playtest/`.

   If the package or CLI is missing, tell the user what to install and stop. Do not add packages yourself.
2. If `.playtest/PROJECT.md` is still the template, do recon:
   - find how the interact key becomes an action;
   - find how a session starts, joins and leaves;
   - list the timers that drain while you think.

   Fill in `PROJECT.md` and `.playtest/adapter.cs`, following [scripted-input.md](references/scripted-input.md). This is
   the only project-specific code. Later runs reuse it.

## Step 1: write the checklist

Turn the issue's acceptance criteria, or the PR's "How to test", into `.playtest/CHECKLIST.md`, using the template.
Give every case a layer:
- `probe`, `solo`, `session` or `adversarial` when a script can check it;
- `human` when only a person can judge it (feel, sound, look, fun).

Show the user the list before running long sessions, so they can add the case they actually worry about.

## Step 2: probes (layer 1)

Open the scene and run the read-only probes that fit the feature:
- objects inside colliders;
- spots the game checks before spawning;
- missing references;
- build scene list;
- network prefab list;
- console baseline.

Take a Scene view screenshot with `drive.py scene:NAME`, then look at it. Probes never save scenes.

## Step 3: solo play (layer 2)

- Enter Play Mode from the menu scene and start the session in code. Wait until the player exists.
- Run one step per action with `drive.py`, and read the `Status()` line after each one.
- Take Game view captures (`cap:NAME`) where the player would see a change, and look at them.
- Rules:
  - teleport and press in separate steps;
  - aim and press in the same step;
  - assert on state, and confirm with the picture.

## Step 4: host + client (layer 3)

This needs a development build with the Pipeline runtime enabled. That is a temporary project setting, and the build
must never be shared. **Ask the user first.**

Then follow [host-client.md](references/host-client.md):
- build into `.playtest/builds/`, turn the setting off again, and revert the build's side effects;
- start the host in the Editor and the client from the build, with latency on both peers;
- check every session case on **both** peers;
- move the client, wait for the server to see it, then act.

## Step 5: forged intents (layer 4)

From the client, call the request method directly:
- from too far away;
- from behind a wall;
- for a host-only action.

The server must refuse every one. A forged intent that succeeds is a security finding.

## Step 6: report and clean up

Fill in `.playtest/REPORT.md` and the checklist's Result and By columns. Then:
- **Each failure needs evidence and a repro a person can follow.** Give the state lines, the screenshot, and the cause
  if you found it. If the user wants a fix, fix it in the project and run the failing case again.
- **Leave harness artefacts out of the failure count, but list them.** Examples: a refused action after a same-step
  teleport, a timer that ran out while you were thinking, kinematic velocity warnings.
- **Never mark a `human` case as passed.** Write exactly what the person should look, listen or feel for.
- **Clean up:** stop Play Mode, close the client, and run `doctor.py`. It must report no FAIL, and no change under
  `Assets/`, `ProjectSettings/` or `Packages/` that the run made.

Give the user the short summary (passed, failed, needs a human, findings) and the path to the report.

## Ground rules

- **Through the Editor only.** Change assets with the Editor API (eval, `delete_asset`). Never hand-edit `.unity`,
  `.prefab`, `.asset` or `.meta` files, and never move or delete under `Assets/` from the file system.
- **Read before you change.** Probes and scripted runs must not save scenes. Before any change to project settings,
  say what changes and why, get a yes, and revert it afterwards.
- **Security.**
  - Pipeline listens on localhost with a token kept in `Library/`; never copy that token anywhere.
  - Never turn on "Allow Browser Clients".
  - Never share or commit a build with the runtime enabled.
- **Honesty.** Say "verified by script" or "verified by a person", never just "tested". A scripted run is a strong
  smoke test. It is not a playtest of feel.
