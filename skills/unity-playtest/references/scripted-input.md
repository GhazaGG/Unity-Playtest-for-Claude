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

Rules that keep scripted runs honest and stable:
- **Move first, press later.** Teleport in one step, then aim and press in the next. In a session the server must
  see the move first (see [host-client.md](host-client.md)). In solo play it lets physics settle.
- **Aim and press in the same step.** Underwater or airborne players drift between frames, and an unfocused Editor
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
