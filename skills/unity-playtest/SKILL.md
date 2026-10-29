---
name: unity-playtest
description: Playtest a Unity game for real. Probe scenes in the open Editor, play the feature in Play Mode through the game's own input path, run host + client sessions with simulated latency, and report pass/fail with evidence, all through Unity's Pipeline CLI (com.unity.pipeline). Use whenever the user wants a Unity feature, scene, PR or bug fix tested, playtested, QA'd, smoke-tested or verified in the Editor or in multiplayer, asks "does this actually work in game", or wants a test checklist run, even if they never say "playtest". Not for only running the unit test suite, checking compile errors, or writing test code.
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

Both Python scripts are stdlib-only and run on Python 3.8+. If they run apart from this folder (some marketplaces
run each script on its own), write `scripts/prelude.cs` and the `templates/` files into `.playtest/` after
`doctor.py --init`; `drive.py` then reads the prelude from there.

Read the reference that matches the layer you are on. Do not read them all up front:
- [pipeline-cheatsheet.md](references/pipeline-cheatsheet.md): exact CLI commands and their quirks
- [editor-probes.md](references/editor-probes.md): layer 1, scene checks with ready-made C# probes
- [scripted-input.md](references/scripted-input.md): layer 2, playing through the real input path, and the adapter
- [host-client.md](references/host-client.md): layers 3 and 4, the client build, latency, both-peer checks, forged intents
- [pitfalls.md](references/pitfalls.md): read this when anything fails in a way that does not make sense

## Fast path: one question, or probes only

Most requests are small: "is anything stuck in this scene", "what speed does the player get carrying X", "which
scenes are in the build". For those, the full run below costs more tokens than the answer is worth. Skip:
- the recon, `PROJECT.md` and the adapter;
- `CHECKLIST.md` and `REPORT.md`;
- every reference except [editor-probes.md](references/editor-probes.md). Open the cheatsheet only if a command is
  rejected.

"Stuck in colliders" also means spawn points: they have no collider, so the overlap probe cannot see them, and a
player who spawns there is stuck. Run the spawn point probe too.

Run `doctor.py --init` if `.playtest/` does not exist yet, write one step file per question, run it with `drive.py`,
and answer in the chat: the numbers, how you got them, and what only a person can judge. If the question needs Play
Mode, enter it, read the values in a step, and stop Play Mode again. Take no screenshot unless the answer is about
what something looks like.

Use the full run (Step 0 onwards) when the request is a checklist, a PR's "How to test", several cases, or a host +
client session.

## Step 0: set up (once per project)

Pipeline 0.9 renamed the CLI commands into groups (`unity command script eval`, `editor status`, `build run`). The
references use the 0.9 names, and [pipeline-cheatsheet.md](references/pipeline-cheatsheet.md) maps them to 0.8.
`drive.py` handles both.


1. Run `python <skill>/scripts/doctor.py --init` from the project. It:
   - checks the `unity` CLI, the `com.unity.pipeline` package and whether the Editor is reachable;
   - creates `.playtest/`, a folder that ignores itself in git (its own `.gitignore` is `*`), so nothing the
     playtest writes ever shows up in `git status`;
   - copies the templates into `.playtest/`.

   If the package or CLI is missing, tell the user what to install and stop. Do not add packages yourself.

   **Several working copies of one game** (git worktrees, one per task): keep one map for all of them. Run
   `doctor.py --init --from <shared dir>` to take `PROJECT.md` and `adapter.cs` from there, and
   `doctor.py --save <shared dir>` after recon or after you correct them. If the user or the project's agent
   instructions name a shared dir, use it.
2. If `.playtest/PROJECT.md` is still the template, do recon:
   - find how the interact key becomes an action;
   - find how a session starts, joins and leaves;
   - list the timers that drain while you think.

   Fill in `PROJECT.md` and `.playtest/adapter.cs`, following [scripted-input.md](references/scripted-input.md). This is
   the only project-specific code. Later runs reuse it. A probe-only run does not need the adapter.

## Step 1: write the checklist

Turn the issue's acceptance criteria, or the PR's "How to test", into `.playtest/CHECKLIST.md`, using the template.
Give every case a layer:
- `probe`, `solo`, `session` or `adversarial` when a script can check it;
- `human` when only a person can judge it (feel, sound, look, fun).

Show the user the list before running long sessions, so they can add the case they actually worry about. If nobody
can answer (an agent working alone), go ahead with the probe and solo cases, and run session cases only when the
request or the standing permissions in `PROJECT.md` allow them.

## Step 2: probes (layer 1)

If the change touched code, run the project's own test suite first (cheatsheet: `test run`) and stop on a failure:
a playtest of a broken build wastes the whole run. Never run tests while Play Mode is on, yours or the user's
(pitfall 35).

Open the scene and run the read-only probes that fit the feature:
- objects inside colliders;
- spots the game checks before spawning;
- missing references;
- build scene list;
- network prefab list;
- console baseline.

Probes never save scenes. Take a Scene view screenshot (`drive.py scene:NAME`) only of what a probe flagged, and
only when the numbers alone do not settle it.

## Step 3: solo play (layer 2)

- Enter Play Mode from the menu scene and start the session in code. Wait until the player exists.
- Run one step per action with `drive.py`, and read the `Status()` line after each one.
- With the Input System, press the case under test with `PtKey`, not `Press()`, so the game's own key reading runs.
- Wait for a state with `PtUntil` and `until:KEY`, not with a fixed `wait:`.
- Take a Game view capture (`cap:NAME`) only for a case whose pass depends on what the player sees, and look at it.
  State lines prove the rest.
- Rules:
  - teleport and press in separate steps;
  - aim and press in the same step;
  - cross doorways, gaps and ramps with `Walk()`, never with `Teleport()`;
  - assert on state, and confirm with the picture.

## Step 4: host + client (layer 3)

This needs a development build with the Pipeline runtime enabled. That is a temporary project setting, and the build
must never be shared. **Ask the user first**, unless the request or the standing permissions in `PROJECT.md` already
allow the build; then say what you turn on and that you turn it off again. With no one to ask and no permission,
skip the session cases and list them as skipped.

Then follow [host-client.md](references/host-client.md):
- build into `.playtest/builds/`, turn the setting off again, and revert the build's side effects;
- start the host in the Editor and the client from the build, with latency on both peers;
- check every session case on **both** peers;
- move the client, wait for the server to see it, then act;
- **late joiners:** change the state first, then join, and compare what the value drives (a rotation, a visible
  object), not only the value;
- **races:** make both peers act at one moment with `PtAt`, and map the window by offsetting one of them;
- **feel numbers** ("the client sees it within 0.25 s"): time them on that peer's own frames with `PtWatch`, take five
  or more samples, and report the median, the range and the measured round trip.

## Step 5: forged intents (layer 4)

From the client, call the request method directly:
- from too far away;
- from behind a wall;
- for a host-only action.

The server must refuse every one. A forged intent that succeeds is a security finding.

## Step 6: report and clean up

Fill in `.playtest/REPORT.md` and the checklist's Result and By columns (if the file cannot be written, give the
report as text). Then:
- **Each failure needs evidence and a repro a person can follow.** Give the state lines, the screenshot, and the cause
  if you found it. If the user wants a fix, fix it in the project and run the failing case again.
- **Leave harness artefacts out of the failure count, but list them.** Examples: a refused action after a same-step
  teleport, a timer that ran out while you were thinking, kinematic velocity warnings.
- **Never mark a `human` case as passed.** Write exactly what the person should look, listen or feel for.
- **Clean up:** stop Play Mode, close the client, delete runtime builds, reopen the scene that was open before, and
  run `doctor.py`. It must report no FAIL, and no change under `Assets/`, `ProjectSettings/` or `Packages/` that the
  run made. Keep the rest of `.playtest/`: it is git-ignored, and the next run reuses it.

Give the user the short summary (passed, failed, needs a human, findings) and the path to the report.
`.playtest/` is git-ignored, so the report never reaches the team by itself: when the work goes into a PR, paste the
report's "For the PR" block into the PR description, in the project's own sections if it has them.

## Keep the token cost down

The user pays for every line you read. A playtest repeats the same calls many times, so small leaks add up.
- **Screenshots are the most expensive output.** One image costs about as much as a page of text. Take them only
  where the rules above say so, and never "just to see".
- **Long step output is cut.** `drive.py` prints the first 35 and last 5 lines of a long result and keeps the whole
  text in `.playtest/out/<step>.txt`. Search that file for what you need instead of rerunning with `--full`. Write
  probes so the summary line comes last.
- **Polls return big JSON.** Print only the fields you check: `status`, `result` and `totalErrors` from
  `build status`; the counts and the names of failed tests from `test status`. On Pipeline 0.9, add `--omit-nulls`. For example, pipe the call through
  `python -c "import json,sys; d=json.load(sys.stdin); print(d.get('status'), d.get('result'), d.get('totalErrors'))"`.
- **Console:** read `console status` first, and pull entries only when the counts show something new.
- **Discovery commands** (`unity list`, `--detail full`) only when a command is rejected.
- **Read each reference once.** Do not reread a file that is already in the conversation.

## Ground rules

- **Through the Editor only.** Change assets with the Editor API (eval, `asset delete`). Never hand-edit `.unity`,
  `.prefab`, `.asset` or `.meta` files, and never move or delete under `Assets/` from the file system.
- **Read before you change.** Probes and scripted runs must not save scenes. Before any change to project settings,
  say what changes and why, get a yes, and revert it afterwards.
- **Security.**
  - Pipeline listens on localhost with a token kept in `Library/`; never copy that token anywhere.
  - Never turn on "Allow Browser Clients".
  - Never share or commit a build with the runtime enabled.
- **Honesty.** Say "verified by script" or "verified by a person", never just "tested". A scripted run is a strong
  smoke test. It is not a playtest of feel.
