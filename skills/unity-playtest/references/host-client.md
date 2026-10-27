# Layers 3 and 4: host + client sessions and adversarial checks

The setup: the Editor runs the host (typed access, screenshots), and a local development build runs the client (driven
through the Pipeline runtime in the player). Both run on one machine with simulated latency. This setup finds
replication gaps, races and missing server validation, which a solo run cannot.

## 1. Build the client (ask the user first)

The build needs the Pipeline runtime inside the player. That is a project setting, and a build that has it must never be
shared. Say both things to the user, and get a yes before going on.

1. `unity command set_runtime_pipeline_settings --settings '{"enableInBuilds": true}' --confirm true`
2. `unity command build --target <StandaloneWindows64|StandaloneOSX|StandaloneLinux64> --outputPath .playtest/builds/client/<Game>.exe --options '["Development"]' --confirm true`
3. Poll `unity command build_status` until `completed`, and check `result` is `Succeeded`.
4. Turn the setting off **right away**, whether or not the build succeeded:
   `unity command set_runtime_pipeline_settings --settings '{"enableInBuilds": false}' --confirm true`
5. Run `git status` and `doctor.py`, then revert what the build touched:
   - `ProjectSettings/Packages/com.unity.pipeline/RuntimePipelineConfig.json`: delete it if the run created it.
   - `ProjectSettings/ProjectSettings.asset` gaining a `preloadedAssets` entry (the Input System actions asset):
     restore it with `git checkout -- ProjectSettings/ProjectSettings.asset`. First check in the Editor that
     `PlayerSettings.GetPreloadedAssets()` is back to what it was.
   - An empty `Assets/Settings/Pipeline` folder: `delete_asset --asset Assets/Settings --confirm true`, if that folder
     did not exist before.

Building into `.playtest/builds/` keeps the binary out of git, even in projects whose `.gitignore` has no `Builds/` rule.

## 2. Start both peers

- Launch the client windowed and small, with its own log:
  `<Game>.exe -screen-fullscreen 0 -screen-width 960 -screen-height 540 -logFile .playtest/builds/client.log`
- Wait until `.unity-pipeline-runtime-port` appears next to the exe. From then on, call it with
  `--runtime-path .playtest/builds/client`. `drive.py --player .playtest/builds/client` does this for you.
- **Latency.** Prefer the project's own test switch, if PROJECT.md lists one (for example a send delay per peer). Set
  it at runtime on both peers, before the host starts and before the client joins, so no scene file changes. 60 ms per
  peer gives about 120 ms RTT.
- Start the host in the Editor (Play the menu scene, then call the host method). Then join from the client by calling
  its join method in a step.
- Wait until the host lists 2 clients **and** the client's `PlayerGo()` is non-null.

## 3. Drive the client

Client steps run through the same `drive.py`, prelude and adapter, with `--player`:

```
python <skill>/scripts/drive.py --player .playtest/builds/client client_go_to_shop wait:1.5 client_press_shop wait:2 client_status
python <skill>/scripts/drive.py host_status
```

- **Move, wait, then act.** The server validates against its own copy of the client's player, and that copy is about one
  RTT behind (plus interpolation). A client that teleports and presses in the same step is refused, because the server
  still sees it at the old place. That is correct server behaviour, so it is a harness failure, not a game bug.
  Teleport, wait about 1.5 s, then aim and press **without** teleporting again.
- **Check every case on both peers.** Read the state on the host (`drive.py host_status`) and on the client
  (`drive.py --player ... client_status`): money, round state, who holds what, what is visible.
- **Hidden versus gone.** A sold or despawned scene object may be deactivated rather than destroyed. Use
  `PtFindAny(name)` and `PtState(go)`, which tell `visible`, `hidden` and `gone` apart, and check late joiners too.
- **Refill timers** on the client as well. `Refill()` runs at the start of every step.

## 4. Session cases worth automating

| Case | What to check on each peer |
|---|---|
| Host-only action from the client | No prompt or target on the client; host state unchanged |
| A state change made by the host | The same value on the client after about 1 s |
| An item held by the client when the round ends | Counted on the host; the client's hand is free; no exception on either peer |
| A purchase by the client | Shared money down on both peers; the item exists on both |
| Wear or equip by the client | Visible on the client's player from the host's view; stats changed on the client |
| Client leaves while holding or wearing something | The host releases it (back on the rack, dropped) |
| Join in the middle of a round | The late joiner sees the current state; objects removed earlier are not there |

## 5. Adversarial intents (layer 4)

A normal client cannot send these, because its own detector or range check stops it first. Bypass the client-side
check and call the client's request method directly, then check that the server refuses:
- **Too far:** teleport the client 6 m away, wait for the server to see it, then call the request with the target.
- **Through a wall:** stand within range but behind solid geometry, then call the request.
- **Not allowed:** a host-only action, or a target already held by someone else.

The server must leave the state unchanged. Report a forged intent that succeeds as a security bug.

## 6. Leave and rejoin

- Use the game's **in-session leave**, the one that returns to the menu. A "cancel connecting" call shuts the transport
  down but can leave the client stuck in the level scene.
- Unity Transport's simulator, used for latency, holds the client's disconnect packet in its send queue, and the packet
  is lost when the transport shuts down. The host then notices only after its disconnect timeout (30 s by default). In
  the tested setup (UTP 2.x), the host also refused every new connection after that. Rejoin tests with simulated
  latency therefore need a fresh host. Report this as a test-tool limit. Without simulated latency, leave and rejoin
  behave normally.

## 7. Clean up

Stop Play Mode. Close the client (kill the process if `quit` does not answer). Run `doctor.py`. Keep the build only if
the user wants to reuse it, and remind them that it has the runtime enabled and must not be shared.
