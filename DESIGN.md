# unity-playtest: design

Status: draft v0.1, for review before the skill is written.

## 1. The problem

Claude can compile a Unity project and run its unit tests, but it cannot play the game. It cannot see the screen, hold a key, walk to a door, or tell that a co-op session broke when a second player joined.

So AI-assisted Unity work stops at "the code compiles and the tests pass". The expensive part is left to people:
- open the Editor;
- walk through every step of "How to test";
- start a second instance for host + client;
- write down what happened.

Most bugs that reach review live exactly there: in scenes, timing, physics, and networking, not in pure functions.

## 2. What the skill does

`unity-playtest` turns a feature's manual test plan into evidence. It drives the running Unity Editor, and a development build, through Unity's own Pipeline CLI (`com.unity.pipeline`). It also says plainly which results came from a script and which still need a human.

It works in five layers. Each one is cheaper and more reliable than the next.

| Layer | What Claude does | Typical catches |
|---|---|---|
| 1. Editor probes | Reads the open scene through the Editor API. Checks collider overlaps, free spawn spots, serialized references, build scene list, network prefab list, and the console. Takes Scene view screenshots. | Objects spawned inside walls, missing references, a prefab missing from the network list |
| 2. Scripted Play Mode | Enters Play Mode and starts the session in code. Drives the player through the **game's own input path**: aim at the target, let the interaction detector pick it, then call the same method the key press calls. Reads state and takes Game view screenshots. | Wrong state transitions, money or score math, UI text, shop rules |
| 3. Host + client | Builds a local development player with the Pipeline runtime, runs it as the client, and adds transport latency on both peers. Drives the client through reflection. Checks the result on **both** peers. | Replication gaps, race conditions, late-join state, server validation |
| 4. Adversarial checks | Sends intents a normal client cannot send, such as interacting from too far away or through a wall, and checks that the server refuses them. | Missing server-side validation |
| 5. Report | A checklist where every case is marked pass, fail or skip, plus findings with reproduction steps. Each case says whether a script or a human verified it. | n/a |

### Proof it is worth it

In its first run, on a private Unity 6 + Netcode for GameObjects co-op game, this workflow found three real bugs that unit tests and code review had missed:
1. Selling a scene-placed networked object destroyed it. NGO warns that late joiners can then keep a ghost copy.
2. The fix for (1) caused a regression: the player holding the object kept "carrying" the now-hidden object.
3. A race in session play. "Everyone is back at base" ended the round before the client-held item had registered in the scoring trigger on the host, so the item was not counted.

It also gave numbers for design questions, such as how long a timed resource lasts in the hardest area and at what force a physics rope snaps.

## 3. Non-goals

- **Replacing human playtesting.** Feel, sound, readability and fun stay human work. The skill reports them as "needs a human", never as passed.
- **Being another Unity-to-AI bridge.** It uses Unity's own Pipeline CLI. Teams that use an MCP bridge can map the same steps onto it later.
- **CI or device farms.** It is for a developer with the Editor open on their own machine.
- **Other engines in v1.** Only Unity has been proven. Godot and Unreal can come later, if people ask.

## 4. Requirements

- Unity 6 (tested on 6000.3) with `com.unity.pipeline` installed (tested 0.8.0-exp.1, an experimental package, so commands may change).
- The Unity CLI (`unity`) on PATH, and Claude Code.
- Layer 3 needs a networking package. It was tested with Netcode for GameObjects 2.x and Unity Transport 2.x; other stacks need their own adapter notes.
- Tested on Windows. macOS and Linux should work but are not tested yet; this is stated in the README.

## 5. Workflow the skill teaches

### Phase 0: recon (once per project)
- Detect Unity (`ProjectSettings/ProjectVersion.txt`) and the Pipeline package. Find the Editor with `unity pipeline list`, or open it.
- Find the project's **interaction path**: how a key press becomes an action (detector, interactor, input action). Find its session entry points (start host, join, leave).
- Write `playtest/PROJECT.md`, a short map of these. The next runs reuse it, the way game-sfx keeps `SOUND_STYLE.md`.

### Phase 1: checklist
- Build test cases from the issue's acceptance criteria or the PR's "How to test". Give each case an ID, the steps, the expected result, and a column for **scriptable / needs human**.
- Store it as `playtest/CHECKLIST.md`. JSON is optional, for tools.

### Phase 2: Editor probes
Pipeline `eval` snippets that only read, and never save scenes:
- scene inventory;
- `Physics.ComputePenetration` on each dynamic object;
- the same overlap check the game itself uses, run on each spawn or shop spot;
- serialized reference checks;
- build settings and network prefab list;
- console baseline.

Scene view screenshots are taken at chosen camera poses and inspected.

### Phase 3: scripted solo play
- Enter Play Mode, start the session in code, and wait until the player exists.
- Use step files on top of a shared **prelude** with these helpers:
  - `tp` teleports the player;
  - `aim` points the camera at a target;
  - `press` triggers the detector and the action in the same frame;
  - `status` prints one line of state.
- After each step, check the state and capture the Game view.

### Phase 4: host + client
- Temporarily enable the Pipeline runtime in builds, make a Development build into a git-ignored folder, then turn the setting off again. Revert the build's side effects (see pitfalls).
- Start the host in the Editor and launch the client build. Set transport latency on both peers at runtime, so no scene is changed.
- Drive the client with a reflection prelude, because player-side eval has no references to game assemblies.
- Move first, wait for replication, then act, so a lagging server copy does not reject a valid action.
- Check every case on both peers. Add the adversarial cases from layer 4.

### Phase 5: report and cleanup
- Fill in the checklist. Write findings with repro steps, and **exclude failures caused by the harness**, while saying why they were excluded.
- Stop Play Mode, close the client, check `git status` is clean, and revert temporary assets and settings.

## 6. Pitfalls catalog

This is the core value of the skill. Each item cost real time once.

1. **Screenshots land in `Assets/`.** `capture_scene_view --save_path` must point inside the project, and the image is written under `Assets/`. Copy it out, then delete it through the Editor (`delete_asset`), not the file system.
2. **PlayMode tests cannot run synchronously over HTTP.** Entering Play Mode reloads the domain and drops the request. Use `run_tests --mode PlayMode --async_tests true`, then poll `test_status`.
3. **Player-side `eval` has no references to game assemblies, and `#r` is refused.** Reach game types through `Type.GetType("Ns.Type, Assembly")` and reflection helpers.
4. **The player runtime has a smaller command set.** It has `eval`, `eval_file`, `console`, `simulate_key`, `simulate_pointer` and `set_timescale`. It has no `run_script` and no `capture_game_view`.
5. **`--runtime-path` takes the folder** that contains `.unity-pipeline-runtime-port`, not the file itself.
6. **Builds leave side effects.**
   - Enabling the runtime in builds writes `ProjectSettings/Packages/com.unity.pipeline/RuntimePipelineConfig.json`.
   - A build can leave the Input System actions asset in `preloadedAssets`, and can create an empty `Assets/Settings/Pipeline`.
   - Revert all of these, and never share a build that has the runtime enabled.
7. **The main thread is busy right after a scene opens.** `eval` then times out at 5 s. Wait for `editor_status` to report `ready`, then retry.
8. **An unfocused Editor runs slowly.** Fixed sleeps become flaky. Do the detector refresh and the press in the same `eval`.
9. **A teleport followed by an immediate client action is rejected by server validation**, because the server's copy of the player has not moved yet. This is correct behaviour, not a game bug. Move, wait, then act, without teleporting again.
10. **Gameplay timers keep running while the agent thinks.** Stamina, hunger or day timers will knock the player out between steps. Refill them in the harness, and say so in the report.
11. **Prelude names collide with step names.** A lambda local and a top-level variable with the same name break C# (CS0136). Keep prelude locals unusual.
12. **Stacked branches.** A type from a later branch does not exist on an earlier one, so keep the prelude branch-agnostic and use reflection for optional members.
13. **Simulated transport latency drops disconnects.** The client's disconnect packet dies in its simulator queue, so the host only notices after the disconnect timeout. In the tested setup, the host then refused every new connection. Use a fresh host for rejoin tests, and report it as a test-tool limit, not a game bug.
14. **Use the game's real "leave" path.** A "cancel connecting" call is not "leave session", and the wrong one leaves the client stuck in the level.
15. **Warnings caused by the harness are not game bugs.** One example is setting velocity on a kinematic body while teleporting a held object. Filter them out, and say so.
16. **Honesty labels.** Never mark feel, audio or visual-quality cases as passed from a script. Mark them "needs a human" and say exactly what to check.

## 7. Repo layout

```text
Unity-Playtest-for-Claude/
├── .claude-plugin/
│   ├── marketplace.json        # marketplace "unity-playtest", plugin source "./"
│   └── plugin.json             # name unity-playtest, version bumped on each release
├── skills/unity-playtest/
│   ├── SKILL.md                # workflow, when to use, under 500 lines
│   ├── references/
│   │   ├── pipeline-cheatsheet.md   # commands, arguments and quirks that actually worked
│   │   ├── editor-probes.md         # read-only C# snippets for layer 1
│   │   ├── scripted-input.md        # the aim, detect and press pattern, and how to map it to a project
│   │   ├── host-client.md           # dev build, runtime, latency, reflection client, adversarial cases
│   │   └── pitfalls.md              # section 6, kept current
│   ├── scripts/
│   │   ├── drive.py                 # runs step files plus a prelude against the Editor or a player (stdlib only)
│   │   ├── prelude_editor.cs        # tp, aim, press and status helpers, typed
│   │   ├── prelude_player.cs        # the same helpers through reflection
│   │   └── doctor.py                # checks the CLI, Editor, Pipeline package and git status before and after a run
│   └── templates/
│       ├── PROJECT.md               # interaction and session map of a project
│       ├── CHECKLIST.md             # test-case table
│       └── REPORT.md                # findings and summary
├── examples/                   # a sample checklist and report, and a GIF for the README
├── README.md
├── DESIGN.md                   # this file
└── LICENSE                     # MIT
```

Scripts are Python stdlib, the same as game-sfx, so they run the same on Windows, macOS and Linux without bash quirks.

## 8. Testing the skill itself

Following skill-creator, the evals are realistic prompts, each run with and without the skill.

1. "Before I push, check `Level01` for objects stuck in colliders and missing references." (layer 1)
2. "Playtest the door-and-key feature from this PR's How to test, solo." (layers 2 and 5)
3. "Run host + client with 120 ms latency for the pickup feature, and check that a client cannot pick up from across the room." (layers 3 and 4)

Grading checks objective facts:
- the skill used the game's input path, not direct state edits;
- harness failures were excluded;
- feel cases were marked "needs a human";
- the project was left clean.

These evals need a **small public sample Unity project** with a door, a key, a pickup and NGO session start and join. That is milestone v0.2.

## 9. Launch plan (for stars)

- **README**:
  - a one-line hook ("Claude can't play your game. Now it can test it.");
  - a 20-second GIF of a host + client run;
  - a "bugs it found" section;
  - install in two commands;
  - a "what it will not do" section.
- **Topics**: `claude-code`, `claude-skill`, `unity`, `unity3d`, `playtesting`, `game-testing`, `qa`, `netcode`.
- **Where to post**: r/Unity3D, r/gamedev, r/ClaudeAI, the Unity Discussions forum, and pull requests to "awesome Claude Code" lists.
- **Credibility**: the honest limits section, a pinned Unity and Pipeline version table, and a changelog.

## 10. Safety and privacy

- No code, names or assets from any private project. Examples use the sample project only.
- Pipeline listens only on localhost with a bearer token. The skill never turns on "Allow Browser Clients" and never ships a build with the runtime enabled.
- Editor probes only read. Scripted runs never save scenes. Cleanup checks `git status` and reverts the side effects listed in section 6.

## 11. Milestones

| Version | Content |
|---|---|
| v0.1 | SKILL.md, references, `drive.py` with both preludes, `doctor.py`, templates. Tested by hand on one project. Repo stays private. |
| v0.2 | Public sample Unity project, three evals with and without the skill, examples, and the README GIF. |
| v0.3 | Description tuned for triggering (skill-creator loop). Make the repo public and launch. |

## 12. Open questions

1. Should the sample project live in this repo (`sample/`), or in a separate repo to keep this one light? A Unity project with `Library/` ignored is about 1 to 5 MB.
2. Should the checklist also come as an interactive page (pass, fail and notes buttons), or is Markdown enough for v0.1?
3. Should the README name the game the bugs were found in, or keep it anonymous? Anonymous is the default.
