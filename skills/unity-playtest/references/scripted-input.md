# Layer 2: scripted Play Mode through the game's real input path

The point of a scripted run is to exercise the code a player's key press exercises:
- the detector's raycast;
- the range check;
- the "can interact" rules;
- the networked request;
- the server's validation.

Setting the end state directly ("door.Open()", "score += 100") proves nothing about the feature. Do it only to set up a
precondition, and say so in the report.

## 1. Find the path once, and write it in PROJECT.md

Search the project for where the interact input is read:
- `WasPressedThisFrame`, `performed +=`, `GetKeyDown`;
- the action name (often `Interact`, `Use` or `Fire`);
- `Physics.Raycast` in a component on the player.

Follow the call chain until it reaches a public or private method with no input dependency, such as `TryInteract()`,
`RequestGrab()` or `BeginInteraction(target)`. That method is `Press()`.

**With the Input System package, press the real key.** `PtKey("E", 0f)` puts the key down on the keyboard in the next
input update, so the game's own action map, binding and `WasPressedThisFrame` or `performed` callback run, and the key
comes up one update or more later. It works with the Editor and the client in the background; queued key events do not
(pitfall 34). Use it for the case under test, and `Press()` only for setup. It catches what `Press()` cannot: an action
map that a pause menu or cutscene left disabled, a wrong binding, a UI that eats the key, a hold that is too short.
`PtKey("E", 1.5f)` holds the key for 1.5 s, for hold-to-interact.

The key acts on a later frame, so the step cannot return its effect. Watch for it in the same step and wait in
`drive.py` (see "Wait for a state, not for a time" below).

A project on the old Input Manager (`Input.GetKeyDown`) cannot get key presses from the CLI at all, so calling the
method the key handler calls is the only way. Say so in the report: the line that reads the key itself is not
exercised.

Then find out how the target is chosen. Usually a detector raycasts from the camera every frame and stores
`CurrentTarget`. If it has a public `Detect()` or similar, the adapter calls it right after aiming, so the press uses a
target from this frame.

## 2. Write the adapter

Copy `templates/adapter.cs` to `.playtest/adapter.cs` (`doctor.py --init` does this) and fill in the TODOs:
- **PlayerGo:** with NGO, this is the local client's `PlayerObject`. Offline, use a tag or `FindAnyObjectByType`.
- **Teleport:** disable the `CharacterController` before writing `transform.position`, then enable it again. If the
  player holds something, move the held object to the hold point too, or the carry code may drop it as out of reach.
- **Aim:** match the look script. If it stores pitch in a field and re-applies it every frame, set that field too, or the
  view snaps back on the next frame.
- **Walk:** set the walk speed. The template moves a `CharacterController` with `Move`, the way the movement code does;
  a Rigidbody player needs its own version.
- **Press:** call the method from step 1 and return its result.
- **Status:** one line with the state the checklist asserts on (round state, score, held item, target name, position).
- **Refill:** the timers that would knock the player out while the agent thinks.

Write the adapter only with the prelude's reflection helpers, so it also runs inside a player build.

## 3. Write steps

A step file holds C# statements that append to `sb`. Keep each step to one action and the state after it:

```csharp
// .playtest/steps/press_door.cs
var door = PtFind("Door_A");
Aim(PtCenter(door));
sb.Append(Press() + " door=" + PtState(door) + " " + Status());
```

Run them in order, with waits between them:

```
python <skill>/scripts/drive.py ready go_to_door wait:1 press_door wait:1 status cap:door_open
```

`status` is built in: it prints `Status()`. A `steps/status.cs` of your own replaces it.

### Wait for a state, not for a time

`wait:1` is too long when the game is quick, and too short when the Editor is in the background. Instead, start
`PtUntil` in the step and let `drive.py until:KEY` poll it:

```csharp
// .playtest/steps/press_door_key.cs
var door = PtFind("Door_A");
Aim(PtCenter(door));
PtUntil("door", () => Status().Contains("door=open"), () => Status(), 5f);
sb.Append(PtKey("E", 0f));
```

```
python <skill>/scripts/drive.py press_door_key until:door until:key.E
```

`until:door` prints `0.120 s, 7 frames` when the door opened, or `TIMEOUT after 5.0 s, 300 frames: <Status()>`, so a
failure already shows the state it ended in. `until:key.E` shows that the key went down and came up again.

Rules that keep scripted runs honest and stable:
- **Walk across what you are testing.** Teleport gets the player near the feature; it must never carry them across a
  doorway, gap, ramp or bridge that the case is about. Use `Walk(target)` and assert that it says `reached`. A door
  that looks open in the screenshot can still block the way.
- **Move first, press later.** Teleport in one step, then aim and press in the next. In a session the server must
  see the move first (see [host-client.md](host-client.md)). In solo play it lets physics settle.
- **Aim and press in the same step.** Floating or airborne players drift between frames, and an unfocused Editor
  runs few frames per second.
- **Assert with state, confirm with a screenshot.** `cap:NAME` after the steps that change what a player sees (HUD,
  report, a door opening). Look at the picture before calling the case passed.
- **Do not judge feel.** A script can show that speed changed to 0.9; only a person can say whether it feels slower.
  Mark those rows `human`.

## 4. Start the session in code

Clicking menu buttons through `simulate_pointer` is fragile. Call the menu's own start method from a step, then wait
until the player exists and the level scene is active:

```csharp
var session = PtFindComponent(PtType("TODO.SessionManager, TODO.Assembly"));
sb.Append("host=" + PtCall(session, "TODO_StartHost", new object[0]));
```

Then poll a step that returns the active scene name and whether `PlayerGo()` is non-null.

## 5. Typical solo cases

- Spawn position and HUD text right after the start.
- A sample of positions at t=0, t=10 s and t=20 s: nothing that should rest is moving, and nothing launched.
- Each state change in the feature: start, progress, end, report.
- Rejections: not enough money, slot full, wrong item. The state must not change.
- Timers: how long a resource lasts in the hardest area. Useful numbers for the design.
- Response times: from a press to the first frame that shows the result. In one step, start
  `PtWatch("open1", () => <what the screen shows>)` and then `Press()`; read `PtKept("open1")` in a later step. Wall-clock
  waits between CLI calls are far too coarse for this. See "Measuring a feel number" in [host-client.md](host-client.md).
