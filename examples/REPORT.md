# Coin pickup, host + client at about 130 ms

> Produced by unity-playtest on [Unity-Playtest-Sample](https://github.com/GhazaGG/Unity-Playtest-Sample) (eval run, 2026-10-28). Unedited except for local paths.

**Result:** pickups work normally, but there is a security bug. Both players see the coin count go up. But the server accepts a coin request from any distance and through walls. The client took a coin from 7.5 m across the room, and another from the locked room through a wall.

## How it ran
- **Host:** the Unity Editor. I entered Play Mode on `Menu.unity` and called `SessionMenu.Host()`.
- **Client:** a temporary development build with the Pipeline runtime. It called `SessionMenu.Join("127.0.0.1")`.
- **Latency:** the project's own `LatencySimulator` added a 25 ms send delay on each peer.
  - Host: I set `SendDelayMs` at runtime before hosting.
  - Client: I started the build with `-latency 25`.
- **Measured round trip:** the host's `GetCurrentRtt` read 122 to 148 ms over 9 samples, median 132 ms. That is a little above your 120 ms. I didn't restart both peers at a lower delay to get closer.
- **Shortcuts the script took instead of a person:**
  - teleporting the player;
  - setting the view angles directly;
  - "pressing E" by calling `PlayerInteractor.Interact()`, which is the method the E key calls;
  - forging a request by calling `InteractServerRpc` directly from the client.
- After each client move, the script waited 1.5 s and checked that the host had the client at the new position before acting.

## Results (all checked by script, not by a person)

| ID | Check | Result | Evidence |
|---|---|---|---|
| A1 | Level has its coins | pass | 6 coins (10 each) and the key, all present. Score 0 |
| S1 | Host and client connected with latency | pass | Host lists 2 clients. Client is clientId 1 and has its player. Round trip 122-148 ms |
| S2 | Host takes a coin, both see it | pass | Host 1.83 m from Coin_A1: `press=sent Coin_A1`. `score=10` on host and client. Coin_A1 hidden on both. Host HUD shows "Coins: 10" (shots/01) |
| S3 | Client takes a coin, both see it | pass | Client 1.83 m from Coin_A2: `press=sent Coin_A2`. `score=20` on host and client. Coin_A2 hidden on both. Host HUD shows "Coins: 20" (shots/02) |
| S4 | Client presses E at a coin across the room | pass | 7.51 m from Coin_A3: `press=nothing in reach`. Score stays 20 and the coin stays visible on both |
| C1 | Client forges a request for a coin across the room | **fail** | Host had the client at (-1.00, 0.05, -4.50), 7.51 m away. The server accepted: `score=20` became `score=30` on both, and Coin_A3 disappeared on both (shots/03, shots/04) |
| C2 | Client forges a request through a wall | **fail** | Client in room A at (-0.68, 0.08, 2.00). Check output: `lineOfSight=blocked by Divider_North doorOpen=False hasKey=False`. Coin_B1 is 3.84 m away in the locked room. The server accepted: `score=40` on both, and Coin_B1 disappeared on both |
| D1 | Feel: sound, HUD and delay | needs a person | Not judged |

About C2: no coin in Level01 is within 3 m of you with a wall in between. So this check also goes past the 3 m reach, and it can't separate a missing wall check from a missing range check.

## The bug
- **Where:** `Assets/Sample/Scripts/PlayerInteractor.cs`, lines 27-31.
- **What's wrong:** `InteractServerRpc` takes the target "as sent". The code comment says "the client already raycast from its own camera". `Pickup.Interact` (`Pickup.cs:19`) only checks `IsServer` and `IsSpawned`. The 3 m reach and the line of sight are checked only on the client, in `InteractionDetector`.
- **What a cheater can do:** a modified client can collect every coin in the level from anywhere, and the locked door doesn't stop it.
- **The key:** it goes through the same request, so it can very likely be taken from anywhere too. I didn't test this.

**Suggested fix (not applied, because you asked me to leave the project as I found it):** in `InteractServerRpc`, check the request against the server's copy of the player:
- the distance from the player's camera pivot to the closest point of the target's collider must be within the detector's 3 m, plus a small allowance for latency;
- a `Physics.Linecast` from the camera pivot to the target must not hit any solid object, ignoring trigger colliders and the player's own collider.

If either check fails, refuse the request. Then run C1 and C2 again. Tell me if you want me to make this fix.

## Left for a person (D1)
Play as host and as client at this latency and pick up a few coins. Check:
- the coin sound plays on both machines;
- the HUD goes up by exactly one coin each time;
- the coin vanishes cleanly;
- the delay between pressing E and the count changing doesn't feel laggy for the client.

## Other things I noticed
- **Not a game bug:** the Editor Console has 1 error, "Failed to handle /api/exec request: Thread was being aborted." It comes from the Pipeline server when Play Mode reloads scripts, not from the game. The client log has no errors.
- **Possible level bug, not tested:** Coin_A4 at (-8.15, 0.60, -2.00) sits inside Wall_West, which spans x -8.4 to -8.0. It may be impossible to pick up.

## Cleanup
- **Editor:** Play Mode is stopped. `Menu.unity` is open and unchanged, as before. The Editor is still open.
- **Client:** quit, and no `PlaytestSample` process is left. The build is deleted.
- **Build setting:** I turned on Pipeline's "enable in builds" setting for the build and turned it off right after.
- **Files the build created, now removed:**
  - `ProjectSettings/Packages/com.unity.pipeline/RuntimePipelineConfig.json`, deleted;
  - an empty `Assets/Settings/Pipeline` folder, deleted through the Editor.
- **Checked unchanged:**
  - the `ProjectSettings/*.asset` files (same hashes);
  - the preloaded assets list (still empty);
  - the Development Build checkbox (still off).
- **Final check:** `git status` is clean, and `doctor.py` reports all OK with no warnings.
- **Kept:** the git-ignored `.playtest/` folder: the project map, adapter, checklist, steps and screenshots. A later run can reuse it, and git never sees it.
