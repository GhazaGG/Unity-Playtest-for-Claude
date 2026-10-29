// unity-playtest project adapter: how THIS game is played. drive.py runs it after prelude.cs and before every step.
// Fill in each TODO during recon, using the interaction path written down in .playtest/PROJECT.md.
// Use only the Pt* helpers and UnityEngine types. That keeps the adapter working inside a player build too, where
// eval cannot see the game's assemblies.
//
// The contract steps rely on:
//   PlayerGo()        the local player's GameObject
//   Teleport(pos)     move the player there (a harness shortcut: say so in the report)
//   Walk(pos)         walk there with the game's own movement; "reached ..." or "BLOCKED at ..."
//   Aim(pos)          turn the view so the interaction ray points at pos, then refresh the detector this frame
//   Press()           do exactly what the interact key does, and return a short result. With the Input System,
//                     steps press the real key with PtKey("E", 0f) instead; Press() is for setup and old projects
//   Status()          one line of game state used in every step's output
//   Refill()          top up timers that keep running while the agent thinks (stamina, oxygen, hunger...)

// TODO: the local player. With Netcode for GameObjects this is usually the local client's PlayerObject.
System.Func<UnityEngine.GameObject> PlayerGo = () =>
{
    var nmType = PtTypeOrNull("Unity.Netcode.NetworkManager, Unity.Netcode.Runtime");
    var nm = nmType != null ? PtGet(nmType, "Singleton") : null;
    if (nm != null && (bool)PtGet(nm, "IsListening"))
    {
        var client = PtGet(nm, "LocalClient");
        var playerObject = client != null ? PtGet(client, "PlayerObject") as UnityEngine.Component : null;
        if (playerObject != null) return playerObject.gameObject;
    }
    return UnityEngine.GameObject.FindWithTag("Player"); // offline scenes
};

// TODO: the components the input path uses. Write the full type names, assembly included. They are looked up only
// in Play Mode, so Edit Mode probes still run while these are TODO.
var ptPlayer = UnityEngine.Application.isPlaying ? PlayerGo() : null;
var ptLook = ptPlayer != null ? ptPlayer.GetComponent(PtType("TODO.PlayerLook, TODO.Assembly")) : null;
var ptDetector = ptPlayer != null ? ptPlayer.GetComponent(PtType("TODO.InteractionDetector, TODO.Assembly")) : null;
var ptInteractor = ptPlayer != null ? ptPlayer.GetComponent(PtType("TODO.PlayerInteractor, TODO.Assembly")) : null;

System.Action<UnityEngine.Vector3> Teleport = pos =>
{
    // A CharacterController overrides transform writes while it is enabled.
    var cc = ptPlayer.GetComponent<UnityEngine.CharacterController>();
    if (cc != null) cc.enabled = false;
    ptPlayer.transform.position = pos;
    if (cc != null) cc.enabled = true;
    UnityEngine.Physics.SyncTransforms();
    PtCall(ptDetector, "Detect", new object[0]); // or Status() shows the target from before the move
};

// TODO: the player's walk speed (from the movement script) and its movement call, if it is not a CharacterController.
var ptWalkSpeed = 4f;
System.Func<UnityEngine.Vector3, string> Walk = to =>
{
    // Walks toward `to` the way the movement code does, so walls, doors and gaps stop the player as they would stop a
    // person. Use it, not Teleport, to cross the thing under test.
    var cc = ptPlayer.GetComponent<UnityEngine.CharacterController>();
    var start = ptPlayer.transform.position;
    for (int i = 0; i < 300; i++) // up to 10 s of walking, 30 moves per second
    {
        var d = to - ptPlayer.transform.position;
        d.y = 0f;
        if (d.magnitude < 0.05f) break;
        var before = ptPlayer.transform.position;
        cc.Move(UnityEngine.Vector3.ClampMagnitude(d, ptWalkSpeed / 30f) + UnityEngine.Vector3.down * 0.1f);
        if ((ptPlayer.transform.position - before).sqrMagnitude < 1e-6f) break; // something solid stopped the player
    }
    UnityEngine.Physics.SyncTransforms();
    PtCall(ptDetector, "Detect", new object[0]);
    var left = to - ptPlayer.transform.position;
    left.y = 0f;
    return (left.magnitude < 0.1f ? "reached " : "BLOCKED at ") + ptPlayer.transform.position.ToString("F2")
        + " after " + UnityEngine.Vector3.Distance(start, ptPlayer.transform.position).ToString("F2") + " m";
};

System.Action<UnityEngine.Vector3> Aim = pos =>
{
    // TODO: match the game's look code. A common pattern turns the body for yaw and a camera pivot for pitch.
    var pivot = (UnityEngine.Transform)PtGet(ptLook, "CameraPivot");
    var d = pos - pivot.position;
    ptPlayer.transform.rotation = UnityEngine.Quaternion.Euler(0f, UnityEngine.Mathf.Atan2(d.x, d.z) * UnityEngine.Mathf.Rad2Deg, 0f);
    float pitch = -UnityEngine.Mathf.Atan2(d.y, new UnityEngine.Vector2(d.x, d.z).magnitude) * UnityEngine.Mathf.Rad2Deg;
    PtSet(ptLook, "_pitch", pitch); // so the look script does not snap back next frame
    pivot.localRotation = UnityEngine.Quaternion.Euler(pitch, 0f, 0f);
    UnityEngine.Physics.SyncTransforms();
    PtCall(ptDetector, "Detect", new object[0]); // refresh the target now; an unfocused Editor runs few frames
};

// TODO: the method the interact key calls. Call that method, not the target's own handler, so the game's checks run
// too: range, line of sight, and the networked request to the server.
System.Func<string> Press = () => "press=" + PtCall(ptInteractor, "TODO_Interact", new object[0]);

System.Func<string> Status = () =>
{
    if (ptPlayer == null) return "no player yet (menu, or still joining)"; // safe to poll before the session starts
    var target = PtGet(ptDetector, "CurrentTarget") as UnityEngine.Component;
    // TODO: add the state your checklist asserts on (score, money, round state, held item...).
    return "target=" + (target != null ? target.name : "-") + " pos=" + ptPlayer.transform.position.ToString("F2");
};

// TODO: or leave it empty if the game has no draining timer. It runs before every step, also before a session exists.
System.Action Refill = () =>
{
    if (ptPlayer == null) return;
    // e.g. var vitals = ptPlayer.GetComponent(PtType("MyGame.Vitals, MyGame.Runtime")); PtSet(vitals, "_stamina", PtGet(vitals, "_maxStamina"));
};
Refill();
