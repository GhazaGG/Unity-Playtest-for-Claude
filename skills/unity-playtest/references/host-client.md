# Layers 3 and 4: host + client sessions and adversarial checks

The setup: the Editor runs the host (typed access, screenshots), and a local development build runs the client (driven
through the Pipeline runtime in the player). Both run on one machine with simulated latency. This setup finds
replication gaps, races and missing server validation, which a solo run cannot.

## 1. Build the client (ask the user first)

The build needs the Pipeline runtime inside the player. That is a project setting, and a build that has it must never be
shared. Say both things to the user, and get a yes before going on. A request that already allows the build counts
as the yes.

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
- Wait until `.unity-pipeline-runtime-port` appears next to the exe. The first start can take 30 s or more; poll for
  the file for up to a minute before calling it a failure. From then on, call it with
  `--runtime-path .playtest/builds/client`. `drive.py --player .playtest/builds/client` does this for you.
- **Latency.** Prefer the project's own test switch, if PROJECT.md lists one (for example a send delay per peer). Set
  it at runtime on both peers, before the host starts and before the client joins, so no scene file changes. The
  setting is not the round trip: measure it on the host with
  `NetworkManager.NetworkConfig.NetworkTransport.GetCurrentRtt(clientId)` and report the measured value. On two
  projects the same "send delay per peer" gave about 2x and about 4x the setting, so start at about a quarter of the
  target round trip per peer, take five or more samples, and adjust once. Report the median and the range. If the
  project has no switch, say so and ask before adding one; NGO 2.x's `SetDebugSimulatorParameters` no longer does
  anything.
- **One host per port.** `StartHost` fails ("Failed to bind") while another Editor or an old client build already
  hosts on the same port. Close it, or give this run another port on the transport in Play Mode memory only.
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

### Late joiners

Change the state on the host first (open, take, buy, start the round), and only then start the client and join.
Compare on both peers the networked value **and** what it drives: `IsOpen` and the hinge's rotation, a `Taken` flag
and whether the object is active. A late joiner receives current values without a change event, so code that only
reacts to `OnValueChanged` leaves its world stale while the value itself reads correctly. Reading only the value
misses exactly that bug.

Players have no capture command. `drive.py --player <build> cap:NAME` asks the player to save its own screen with
`ScreenCapture.CaptureScreenshot` and waits for the file. Take the host's `cap:` from the same spot and angle when the
two pictures are meant to be compared.

### Races

Two peers have to act within a few frames of each other, and two `drive.py` calls started together land a few hundred
milliseconds apart. Schedule the action instead: `PtAt(key, isoUtc, action)` in the prelude runs it on the first frame
after a UTC time, and both peers on one machine share the clock.

1. Write a host step and a client step that schedule the same action for one time about 4 s ahead. Write both files
   from one small Python script, so they get the same time (in Git Bash, `$(python ...)` keeps a trailing `\r` that
   breaks the C# string):

   ```python
   import datetime as d
   at = (d.datetime.now(d.timezone.utc) + d.timedelta(seconds=4)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
   for side in ("h", "c"):
       open(f".playtest/steps/race_{side}.cs", "w").write(
           f'var ptCoin = PtFind("Coin_2"); PtAt("race1", "{at}", () => {{ Aim(PtCenter(ptCoin)); return Press(); }}); sb.Append("scheduled");\n')
   ```
2. Start both steps together and wait for both: `drive.py race_h & drive.py --player <build> race_c & wait`.
3. A few seconds later, read `PtKept("race1")` and the state on both peers. Each line says how late its action ran;
   on one PC both usually run within 10 ms of the time.
4. **Map the window.** Repeat with the client's time later by 100, 200, 300 ms. The offset where the bug stops is the
   size of the window, a number a fix can be checked against. The client's request reaches the server about half a
   round trip after it runs, so add that when you turn offsets into a window on the server.
5. **Check the cause, not only the symptom.** Repeat once with latency off. If it still happens, latency only makes it
   likelier in play (players act on a picture that is older); it is not the cause.

Each try often uses up what was raced for (a coin, a door). Count your tries per target, and if you reset a target with
a harness shortcut on the host, say so.

### Measuring a feel number

A design note like "the client sees the door open within 0.25 s" is measurable; whether it *feels* quick is not.

- Measure on the peer the sentence is about. "The client sees" means the client's own frames, not the host's.
- In one step, start `PtWatch(key, cond)` and then act. `cond` reads what the screen shows (a rotation, a scale, an
  active flag), not the networked value. Read `PtKept(key)` in a later step: seconds and frames from the action to the
  first frame that shows the change.
- Take five or more samples, and give the median, the range and the measured round trip next to them. A one-shot
  feature needs a reset between samples, which is a harness shortcut: say so.
- Note the peer's frame rate while measuring. An unfocused Editor runs few frames and inflates every number.
- The number leaves out the input device, the display and the look of the change. Write that the felt delay is for a
  person to judge.

## 5. Adversarial intents (layer 4)

A normal client cannot send these, because its own detector or range check stops it first. Bypass the client-side
check and call the client's request method directly, then check that the server refuses.

With NGO, the request usually takes a `NetworkObjectReference`. In a player, eval cannot see the type, so build it by
reflection:

```csharp
var ptRefType = PtType("Unity.Netcode.NetworkObjectReference, Unity.Netcode.Runtime");
var ptTargetNo = PtFind("Coin_B2").GetComponent(PtType("Unity.Netcode.NetworkObject, Unity.Netcode.Runtime")); // TODO: the target
var ptRef = System.Activator.CreateInstance(ptRefType, new object[] { ptTargetNo });
sb.Append("sent=" + PtCall(ptInteractor, "TODO_RequestServerRpc", new object[] { ptRef }) + " " + Status());
```

**Prove the request arrived before you call it refused.** A default or empty reference, a wrong overload or an RPC
that was never sent looks exactly like a server that refused. Send one legal request the same way first and see the
state change; only then does "nothing changed" mean "refused".

Cases:
- **Too far:** teleport the client 6 m away, wait for the server to see it, then call the request with the target.
- **Through a wall:** stand within range but behind solid geometry, then call the request. If no target sits within
  range behind a wall, say that the case cannot tell a missing wall check from a missing range check.
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

Stop Play Mode. Close the client (kill the process if `quit` does not answer), then confirm no client process is
left (pitfall 21). Run `doctor.py`. Delete the build unless the user wants to reuse it; if it stays, remind them that
it has the runtime enabled and must not be shared. Keep the rest of `.playtest/` (it is git-ignored and the next run
reuses the map and the adapter).
