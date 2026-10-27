# Pitfalls

Each of these cost real time in a real run. Check this list when something fails in a way that does not make sense.

| # | Symptom | Cause | What to do |
|---|---|---|---|
| 1 | A new `Assets/Temp/` folder with PNG files and `.meta` files | `capture_*_view --save_path` writes under `Assets/` | Take images inline (`drive.py cap:` and `scene:`). Delete leftovers through the Editor: `delete_asset --asset Assets/Temp --confirm true` |
| 2 | PlayMode `run_tests` returns 0 tests and "cannot run synchronously over HTTP" | Entering Play Mode reloads the domain and drops the request | `run_tests --mode PlayMode --async_tests true`, then poll `test_status` |
| 3 | Player-side eval: "The type or namespace name 'MyGame' could not be found"; `#r is only allowed in scripts` | Player eval has no references to game assemblies | Use `prelude.cs`, with `PtType("Ns.Type, Assembly")`, `PtGet`, `PtSet` and `PtCall` |
| 4 | "No command named 'run_script' / 'capture_game_view'" from a player | The player runtime has a smaller command set | Use `eval`/`eval_file`; take screenshots from the Editor peer only |
| 5 | "No Pipeline runtime instance found at ...port" | `--runtime-path` was given the file | Pass the folder that holds `.unity-pipeline-runtime-port` |
| 6 | After a build: changes in `ProjectSettings/`, a new `ProjectSettings/Packages/`, an empty `Assets/Settings/Pipeline` | The Pipeline and Input System build hooks | Revert them (see host-client.md, step 1.5), and never share a runtime-enabled build |
| 7 | "Main thread operation timed out after 5000ms" | The Editor is busy (scene opening, import, domain reload) | Poll `editor_status` until `ready`, then retry |
| 8 | Steps flaky only while the user works in another window | An unfocused Editor runs few frames per second | Do detect and press in one eval; use generous waits; poll for the state |
| 9 | A client's valid action is refused, but the same action works when played by hand | Teleport then immediate action: the server's copy of the client has not moved yet | Teleport, wait about 1.5 s, then act without teleporting again |
| 10 | The player suddenly respawns at the start, or a round ends by itself | A gameplay timer (stamina, oxygen, hunger) ran out while the agent was thinking | Refill it in `Refill()` and say so in the report. Measure the real duration separately; it is useful design data |
| 11 | `CS0136: a local named 'x' cannot be declared in this scope` | A step reuses a name declared in the prelude or the adapter | Rename the step's variable; the prelude uses `Pt*` names for this reason |
| 12 | A step fails to compile on one branch but not another | A type or member exists only on a later branch (stacked PRs) | Use `PtTypeOrNull` and reflection for optional members |
| 13 | After a client leaves with simulated latency: the host still lists it for 30 s, and new joins fail | The transport simulator drops the disconnect packet on shutdown | Rejoin tests need a fresh host; report it as a test-tool limit |
| 14 | After "leave", the client stays in the level and joining fails | The wrong method was called (for example "cancel connect" instead of "leave session") | Use the in-session leave that returns to the menu |
| 15 | Warnings like "Setting linear velocity of a kinematic body" | The harness teleported a held, kinematic object | Not a game bug. Skip velocity writes on kinematic bodies, and leave them out of the report |
| 16 | Tempting to write "feels good: pass" | Scripts cannot judge feel, sound or visuals | Mark those cases `human`, and say exactly what to look or listen for |
| 17 | "PlayerObject is null" right after join | The client is connected but still loading the level scene | Poll until the level scene is active **and** `PlayerGo()` is non-null |
| 18 | Reflection returns null for `LocalClient` or another member you know exists | `Type.GetProperty` misses fields, and some members are fields or live on a base class | Use `PtGet`, which tries properties and fields up the type hierarchy |
