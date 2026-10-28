# Playtest checklist: coin pickup, host + client at ~120 ms

> Produced by unity-playtest on [Unity-Playtest-Sample](https://github.com/GhazaGG/Unity-Playtest-Sample) (eval run, 2026-10-28). Unedited except for local paths.

Branch and commit: main @ 00b469c · Unity 6000.3.25f1 · Date: 2026-10-28

The **Layer** column says how the case can be checked:
- `probe`: read in the Editor, without playing;
- `solo`: scripted Play Mode;
- `session`: host + client;
- `adversarial`: a forged client intent;
- `human`: feel, sound or visuals, which only a person can judge.

The **By** column says who verified the result: `script`, `human`, or `script+human`.

| ID | Layer | Steps | Expected | Result | By | Notes |
|----|-------|-------|----------|--------|----|-------|
| A1 | probe | Host in Play Mode, Level01 loaded; list coins (name, position, value, active) and the ScoreBoard | Coins present and active, score 0 | pass | script | 6 coins (10 each) + key, all visible and spawned, score 0. Aside: Coin_A4 (-8.15, 0.6, -2) sits inside Wall_West; not tested |
| S1 | session | Host in Editor, client from dev build, SendDelayMs on both peers; client joins | Host lists 2 clients; client has a PlayerObject; measured RTT ~120 ms | pass | script | SendDelayMs 25 on both; host clients=2, client clientId=1 with player; GetCurrentRtt 122-148 ms over 9 samples, median 132 |
| S2 | session | Host walks (teleport) next to a coin, aims, presses E path | Score +value on host and client; coin hidden on both | pass | script | Coin_A1 at 1.83 m: "sent Coin_A1"; score 0 -> 10 on host and client; Coin_A1 hidden on both; shot 01 |
| S3 | session | Client teleports next to another coin, waits 1.5 s, aims, presses E path | Score +value on host and client; coin hidden on both | pass | script | Coin_A2 at 1.83 m: "sent Coin_A2"; score 10 -> 20 on host and client; Coin_A2 hidden on both; shot 02 |
| S4 | session | Client stands across the room from a coin, aims at it, presses E path | Client says "nothing in reach"; score and coin unchanged on both | pass | script | 7.51 m from Coin_A3: "nothing in reach"; score 20 and Coin_A3 visible on both |
| C1 | adversarial | Client across the room (> 3 m) calls `InteractServerRpc(coin)` directly | Server refuses; score unchanged and coin visible on both | fail | script | Host saw client at (-1.00, 0.05, -4.50), 7.51 m away; server accepted: score 20 -> 30, Coin_A3 despawned on both (F1) |
| C2 | adversarial | Client within 3 m of a coin but behind a wall calls `InteractServerRpc(coin)` | Server refuses | fail | script | No coin sits within 3 m behind a wall, so used Coin_B1 3.84 m away through Divider_North, door locked, no key; server accepted: score 30 -> 40, Coin_B1 despawned on both (F1) |
| D1 | human | Pick up coins as host and as client at ~120 ms | Coin sound plays, HUD count updates without feeling laggy or double-counting, coin disappears cleanly | | | Not run: needs a person |

Results are `pass`, `fail` or `skip`. Leave the cell empty for "not run". Never fill in a `human` row from a script.
