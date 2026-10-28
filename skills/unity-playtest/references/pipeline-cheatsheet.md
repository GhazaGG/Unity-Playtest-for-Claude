# Unity Pipeline CLI cheatsheet

These commands were tested with Unity 6000.3 and `com.unity.pipeline` 0.8.0-exp.1. The package is experimental, so check
the exact parameters with `unity command --detail full --query <name>` when something is rejected.

Add `--no-banner --result-only` to get plain JSON back. `drive.py` does that for you.

- Pass parameters as named flags (`--settings '{...}' --confirm true`). A positional JSON argument is accepted and
  silently ignored.
- With more than one Editor open, add `--project-path <project>` to every call. Without it the CLI guesses from the
  working directory, and right after entering Play Mode it has answered from the other Editor.
- In `console_status`, trust `groundTruth`; its `counts` block can disagree.

## Find and inspect the Editor

| Goal | Command |
|---|---|
| Is the Editor open and reachable? | `unity pipeline list` (TSV: Project, Path, PID, Running, Pipeline, Version, Update, Port, **Server Reachable**, Safe Mode) |
| List tools the Editor offers | `unity list` |
| Parameters of one tool | `unity command --detail full --query <name>` |
| Idle? Compiling? Playing? | `unity command editor_status`, then wait for `compiling: false` and `domainReloadInProgress: false`. `status` is `ready` in Edit Mode but `playing` in Play Mode |
| Console without pulling entries | `unity command console_status` (counts, `compilationFailed`) |
| Console entries | `unity command console` |
| Clear console | `unity command clear_console` |
| Quit the Editor | `unity command eval --code 'UnityEditor.EditorApplication.Exit(0); return "";'` (the call errors because the Editor is gone; a `delayCall` version never runs in an idle Editor) |

The Pipeline server answers only once the Editor has finished loading. Right after an Editor start or a domain
reload, `unity list` fails with "Pipeline server isn't reachable". Poll it.

## Scenes and code

| Goal | Command |
|---|---|
| Open a scene | `unity command open_scene --path Assets/Scenes/X.unity` |
| Open scenes and dirty state | `unity command list_open_scenes` |
| Run C# | `unity command eval --code '<statements; return value;>'` |
| Run C# from a file | `unity command eval_file --file <abs path> --timeout 30` |
| Refresh after editing files on disk | `unity command eval --code 'UnityEditor.AssetDatabase.Refresh(); return "ok";'`, then wait for ready |
| Delete an asset (through the Editor) | `unity command delete_asset --asset <path> --confirm true` |

About `eval`:
- It takes statements and a `return`. Use fully qualified type names, because `using` directives are not accepted.
- A main-thread timeout ("Main thread operation timed out after 5000ms") right after `open_scene` means the Editor is still
  busy. Wait for `editor_status` ready, then retry.

## Play Mode

| Goal | Command |
|---|---|
| Enter or exit | `unity command editor_play`, `unity command editor_stop` |
| Wait | poll `editor_status` for `playMode: playing` or `playMode: stopped` |
| Game view image | `unity command capture_game_view`, which returns base64 inline |
| Scene view image | `unity command capture_scene_view`, which returns base64 inline |

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

| Goal | Command |
|---|---|
| EditMode, synchronous | `unity command run_tests --mode EditMode --timeout 600` |
| PlayMode | `unity command run_tests --mode PlayMode --async_tests true`, then poll `unity command test_status` until `completed` |
| Editor closed instead | `Unity -batchmode -nographics -projectPath <p> -runTests -testPlatform PlayMode -testResults <xml> -logFile <log>`, without `-quit` |

PlayMode over HTTP must be async: entering Play Mode reloads the domain and drops a synchronous request.

## Builds

| Goal | Command |
|---|---|
| Current build settings | `unity command get_build_settings` |
| Runtime settings | `unity command get_runtime_pipeline_settings` |
| Enable the runtime in builds (**ask the user first**) | `unity command set_runtime_pipeline_settings --settings '{"enableInBuilds": true}' --confirm true` |
| Development build | `unity command build --target StandaloneWindows64 --outputPath .playtest/builds/client/Game.exe --options '["Development"]' --confirm true` |
| Wait | poll `unity command build_status` until `completed`, then read `result` and `totalErrors` |
| Disable again | `set_runtime_pipeline_settings --settings '{"enableInBuilds": false}' --confirm true`, and delete `ProjectSettings/Packages/com.unity.pipeline/RuntimePipelineConfig.json` if the run created it |

After every build, run `git status` and `doctor.py`, then revert the side effects listed in [pitfalls.md](pitfalls.md).

## Talking to a player build

- A player with the runtime writes `.unity-pipeline-runtime-port` next to its exe.
- Target it with `unity command --runtime-path <folder that holds that file> <command>`. Pass the folder, not the file.
- Runtime commands: `eval`, `eval_file`, `console`, `console_status`, `clear_console`, `simulate_key`, `simulate_pointer`,
  `set_timescale`, `set_target_framerate`, `log`, `runtime_status`, `quit`. There is no `run_script` and no `capture_*`;
  `drive.py --player <build> cap:NAME` takes the picture through `ScreenCapture` instead.
- Player-side `eval` cannot see the game's assemblies, and `#r` is refused. Use `prelude.cs` (reflection) and an
  adapter written with `PtType`, `PtGet`, `PtSet` and `PtCall`.
