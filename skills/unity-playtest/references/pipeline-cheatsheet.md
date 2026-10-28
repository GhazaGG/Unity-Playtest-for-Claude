# Unity Pipeline CLI cheatsheet

These commands were tested with Unity 6000.3 and `com.unity.pipeline` 0.9.1-exp.1 and 0.8.0-exp.1. The package is
experimental, so check the exact parameters with `unity command --detail full --query <name>` when something is
rejected.

**Pipeline 0.9 renamed the commands into groups** (`unity command script eval`). The old flat names fail with "No
command named 'eval'... It was renamed". The tables give the 0.9 name first and the 0.8 name after it. `unity pipeline
list` shows the installed version. `drive.py` works with both.

Add `--no-banner --result-only` to get plain JSON back. `drive.py` does that for you.

- Pass parameters as named flags (`--settings '{...}' --confirm true`), after the command name. A positional JSON
  argument is accepted and silently ignored.
- On 0.9, `--omit-nulls` after the command name drops null fields and saves tokens.
- With more than one Editor open, add `--project-path <project>` to every call. Without it the CLI guesses from the
  working directory, and right after entering Play Mode it has answered from the other Editor.
- In `console status`, trust `groundTruth`; its `counts` block can disagree.

## Find and inspect the Editor

| Goal | 0.9 command | 0.8 command |
|---|---|---|
| Is the Editor open and reachable? | `unity pipeline list` (TSV: Project, Path, PID, Running, Pipeline, Version, Update, Port, **Server Reachable**, Safe Mode) | same |
| List tools the Editor offers | `unity list` | same |
| Parameters of one tool | `unity command --detail full --query <name>` | same |
| Idle? Compiling? Playing? | `editor status` | `editor_status` |
| Console without pulling entries | `console status` | `console_status` |
| Console entries | `console get` | `console` |
| Clear console | `console clear` | `clear_console` |
| Quit the Editor | `script eval --code 'UnityEditor.EditorApplication.Exit(0); return "";'` | `eval --code ...` |

Wait for `compiling: false` and `domainReloadInProgress: false` in the status. `status` is `ready` in Edit Mode but
`playing` in Play Mode. On 0.9 it also reports `playerLoopTicking` (whether Play Mode frames advance) and
`runInBackground`. Quitting with `Exit(0)` makes the call error, because the Editor is gone.

The Pipeline server answers only once the Editor has finished loading. Right after an Editor start or a domain
reload, `unity list` fails with "Pipeline server isn't reachable". Poll it.

## Scenes and code

| Goal | 0.9 command | 0.8 command |
|---|---|---|
| Open a scene | `scene open --path Assets/Scenes/X.unity` | `open_scene` |
| Open scenes and dirty state | `scene list_open` | `list_open_scenes` |
| Run C# | `script eval --code '<statements; return value;>'` | `eval` |
| Run C# from a file | `script eval_file --file <abs path> --timeout 30` | `eval_file` |
| Delete an asset (through the Editor) | `asset delete --asset <path> --confirm true` | `delete_asset` |

About `eval`:
- It takes statements and a `return`. Use fully qualified type names, because `using` directives are not accepted.
- To refresh after editing files on disk: `UnityEditor.AssetDatabase.Refresh(); return "ok";`, then wait for ready.
- A main-thread timeout ("Main thread operation timed out after 5000ms") right after opening a scene means the Editor
  is still busy. Wait for ready, then retry.

## Play Mode

| Goal | 0.9 command | 0.8 command |
|---|---|---|
| Enter or exit | `editor.playmode start`, `editor.playmode stop` | `editor_play`, `editor_stop` |
| Wait | poll the status for `playMode: playing` or `playMode: stopped` | same |
| Game view image | `capture game_view`, base64 inline | `capture_game_view` |
| Scene view image | `capture scene_view`, base64 inline | `capture_scene_view` |

Never pass `--save_path` to the capture commands. The path must be inside the project and the file is written under
`Assets/`, which leaves an asset and a `.meta` behind. `drive.py cap:NAME` and `scene:NAME` decode the inline image into
`.playtest/shots/`.

To frame the Scene view before a capture:
```csharp
var sv = UnityEditor.SceneView.lastActiveSceneView;
sv.LookAt(new UnityEngine.Vector3(x, y, z), UnityEngine.Quaternion.Euler(pitchDeg, yawDeg, 0f), size, false, true);
sv.Repaint(); return "ok";
```

## Tests

| Goal | 0.9 command | 0.8 command |
|---|---|---|
| EditMode, synchronous | `test run --mode EditMode --timeout 600` | `run_tests` |
| PlayMode | `test run --mode PlayMode --async_tests true`, then poll `test status` until `completed` | `run_tests`, `test_status` |
| Editor closed instead | `Unity -batchmode -nographics -projectPath <p> -runTests -testPlatform PlayMode -testResults <xml> -logFile <log>`, without `-quit` | same |

PlayMode over HTTP must be async: entering Play Mode reloads the domain and drops a synchronous request.

## Builds

| Goal | 0.9 command | 0.8 command |
|---|---|---|
| Current build settings | `build get_settings` | `get_build_settings` |
| Runtime settings | `settings.runtime_pipeline get` | `get_runtime_pipeline_settings` |
| Enable the runtime in builds (**ask the user first**) | `settings.runtime_pipeline set --settings '{"enableInDevelopmentBuilds": true}' --confirm true` | `set_runtime_pipeline_settings --settings '{"enableInBuilds": true}' --confirm true` |
| Development build | `build run --target StandaloneWindows64 --outputPath .playtest/builds/client/Game.exe --options '["Development"]' --confirm true` | `build` with the same flags |
| Wait | poll `build status` until `completed`, then read `result` and `totalErrors` | `build_status` |
| Disable again | the same `set` with `false` | the same `set` with `false`, and delete `ProjectSettings/Packages/com.unity.pipeline/RuntimePipelineConfig.json` if the run created it |

On 0.9 the runtime toggle is a scripting define (`ENABLE_RUNTIME_PIPELINE_DEV`), so turning it on starts a recompile.
Wait for ready, and check the build afterwards: `<Game>_Data/Managed/Unity.Pipeline.dll` must exist. A build started
during the reload completes with `result: Unknown` and `platform: NoTarget`, and a build that started before the define
took effect succeeds without the runtime.

After every build, run `git status` and `doctor.py`, then revert the side effects listed in [pitfalls.md](pitfalls.md).

## Talking to a player build

- A player with the runtime writes `.unity-pipeline-runtime-port` next to its exe, usually 20 to 30 s after launch.
- Target it with `unity command --runtime-path <folder that holds that file> <command>`. Pass the folder, not the file.
- Runtime commands on 0.9: `script eval`, `script eval_file`, `console get`, `console status`, `console clear`,
  `runtime simulate_key`, `runtime simulate_pointer`, `runtime set_time_scale`, `runtime set_target_frame_rate`,
  `runtime status`, `runtime quit`. On 0.8 they are the flat names (`eval`, `runtime_status`, `quit`, ...).
- There is no `capture` command in a player. `drive.py --player <build> cap:NAME` takes the picture through
  `ScreenCapture` instead.
- Player-side `eval` cannot see the game's assemblies, and `#r` is refused. Use `prelude.cs` (reflection) and an
  adapter written with `PtType`, `PtGet`, `PtSet` and `PtCall`.
