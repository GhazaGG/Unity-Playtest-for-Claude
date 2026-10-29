// unity-playtest prelude. drive.py puts this file first, then the project adapter (.playtest/adapter.cs),
// then the step, then `return sb.ToString();`.
//
// Everything here goes through reflection, because eval inside a player build has no references to the game's
// assemblies. The same step files therefore run in the Editor and in a player.
// The names are long on purpose: a step that declares a variable with the same name as one in here breaks the
// C# compile (CS0136).
var sb = new System.Text.StringBuilder();
var PtFlags = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Static |
              System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic;

// "Namespace.Type, AssemblyName", e.g. "MyGame.PlayerController, MyGame.Runtime". Throws if missing.
System.Func<string, System.Type> PtType = name => System.Type.GetType(name, true);
// The same, but null when the type does not exist (a feature from another branch, an optional package).
System.Func<string, System.Type> PtTypeOrNull = name => System.Type.GetType(name, false);

// Read, write or call a member (field or property, public or not) on an object, or on a Type for static members.
System.Func<object, string, object> PtGet = (target, member) =>
{
    var type = target as System.Type ?? target.GetType();
    var instance = target is System.Type ? null : target;
    for (var t = type; t != null; t = t.BaseType)
    {
        var p = t.GetProperty(member, PtFlags); if (p != null) return p.GetValue(instance);
        var f = t.GetField(member, PtFlags); if (f != null) return f.GetValue(instance);
    }
    throw new System.MissingMemberException(type.Name, member);
};
System.Action<object, string, object> PtSet = (target, member, value) =>
{
    var type = target as System.Type ?? target.GetType();
    var instance = target is System.Type ? null : target;
    for (var t = type; t != null; t = t.BaseType)
    {
        var f = t.GetField(member, PtFlags); if (f != null) { f.SetValue(instance, value); return; }
        var p = t.GetProperty(member, PtFlags); if (p != null && p.CanWrite) { p.SetValue(instance, value); return; }
    }
    throw new System.MissingMemberException(type.Name, member);
};
System.Func<object, string, object[], object> PtCall = (target, method, args) =>
{
    var type = target as System.Type ?? target.GetType();
    var instance = target is System.Type ? null : target;
    for (var t = type; t != null; t = t.BaseType)
        foreach (var m in t.GetMethods(PtFlags))
            if (m.Name == method && m.GetParameters().Length == args.Length) return m.Invoke(instance, args);
    throw new System.MissingMethodException(type.Name, method);
};

// Scene lookups. PtFindAny also finds inactive objects, for example a sold item that was hidden.
System.Func<string, UnityEngine.GameObject> PtFind = name => UnityEngine.GameObject.Find(name);
System.Func<string, UnityEngine.GameObject> PtFindAny = name =>
{
    foreach (var go in UnityEngine.Resources.FindObjectsOfTypeAll<UnityEngine.GameObject>())
        if (go.name == name && go.scene.IsValid()) return go;
    return null;
};
System.Func<System.Type, UnityEngine.Object> PtFindComponent = type => UnityEngine.Object.FindAnyObjectByType(type);
System.Func<System.Type, UnityEngine.Object[]> PtFindComponents = type =>
    UnityEngine.Object.FindObjectsByType(type, UnityEngine.FindObjectsSortMode.InstanceID);

// The point to aim at: the centre of the first collider, else the transform position.
System.Func<UnityEngine.GameObject, UnityEngine.Vector3> PtCenter = go =>
{
    var c = go.GetComponent<UnityEngine.Collider>() ?? go.GetComponentInChildren<UnityEngine.Collider>();
    return c != null ? c.bounds.center : go.transform.position;
};
System.Func<UnityEngine.GameObject, string> PtState = go =>
    go == null ? "gone" : (go.activeInHierarchy ? "visible" : "hidden") + " at " + go.transform.position.ToString("F2");

// Frame-by-frame timing that outlives the step, for feel numbers and races. Both run on this peer's own frames, just
// before each frame renders, so they measure what this peer's screen shows. Results stay in the AppDomain under a
// key; read them in a later step with PtKept(key), or let drive.py wait for them with `until:KEY`.
//   PtUntil(key, cond, show, sec) notes the first frame where cond() is true: "0.153 s, 9 frames". After sec seconds
//                             it gives up with "TIMEOUT after 5.0 s, 300 frames: " + show(), the last value it saw.
//   PtWatch(key, cond)        the same, with 60 s and no last value, to time a feel number
//   PtAt(key, isoUtc, action) runs action on the first frame at or after a UTC time ("2026-01-31T12:00:05.000Z") and
//                             notes when it ran and its result. Peers on one machine share the clock, so the same
//                             time on two peers makes them act within a frame of each other.
System.Action<string, string> PtKeep = (key, value) => System.AppDomain.CurrentDomain.SetData("unity-playtest." + key, value);
System.Func<string, string> PtKept = key => (string)System.AppDomain.CurrentDomain.GetData("unity-playtest." + key) ?? "-";
System.Action<string, System.Func<bool>, System.Func<string>, float> PtUntil = (key, condition, show, seconds) =>
{
    var start = UnityEngine.Time.realtimeSinceStartupAsDouble;
    var frames = 0;
    UnityEngine.Events.UnityAction tick = null;
    tick = () =>
    {
        frames++;
        var elapsed = UnityEngine.Time.realtimeSinceStartupAsDouble - start;
        string result = null;
        try
        {
            if (condition()) result = elapsed.ToString("F3") + " s, " + frames + " frames";
            else if (elapsed >= seconds) result = "TIMEOUT after " + elapsed.ToString("F1") + " s, " + frames + " frames" + (show != null ? ": " + show() : "");
        }
        catch (System.Exception e) { result = "error: " + e.Message; }
        if (result == null) return;
        PtKeep(key, result);
        UnityEngine.Application.onBeforeRender -= tick;
    };
    PtKeep(key, "waiting");
    UnityEngine.Application.onBeforeRender += tick;
};
System.Action<string, System.Func<bool>> PtWatch = (key, condition) => PtUntil(key, condition, null, 60f);

// A real key press through the Input System, so the game's own key reading runs: its action map, its bindings,
// WasPressedThisFrame and performed callbacks. Press() skips all of that. key is a Key name ("E", "Space",
// "LeftShift"); the key goes down in the next input update and up after holdSeconds, and never in the same update. The
// result is kept under "key." + key once the key is up. Projects on the old Input Manager cannot get keys this way;
// use Press() there.
// The key is written straight into the keyboard's state right after each input update, just before the game's own
// Update reads it. Queued events would not do: while the Game view (Editor) or the window (player) has no focus, which
// is always the case for the agent, the Input System holds keyboard events back.
System.Func<string, float, string> PtKey = (key, holdSeconds) =>
{
    var ptInput = PtTypeOrNull("UnityEngine.InputSystem.InputSystem, Unity.InputSystem");
    if (ptInput == null) return "no Input System package: use Press()";
    var ptKeyboard = PtGet(PtType("UnityEngine.InputSystem.Keyboard, Unity.InputSystem"), "current");
    if (ptKeyboard == null) return "no keyboard device";
    if (!(bool)PtGet(ptKeyboard, "enabled")) PtCall(ptInput, "EnableDevice", new object[] { ptKeyboard }); // a player in the background
    var ptKeyEnum = PtType("UnityEngine.InputSystem.Key, Unity.InputSystem");
    var ptStateType = PtType("UnityEngine.InputSystem.LowLevel.KeyboardState, Unity.InputSystem");
    var ptInputState = PtType("UnityEngine.InputSystem.LowLevel.InputState, Unity.InputSystem");
    var ptDown = System.Array.CreateInstance(ptKeyEnum, 1);
    ptDown.SetValue(System.Enum.Parse(ptKeyEnum, key, true), 0);
    System.Reflection.MethodInfo ptChange = null; // InputState.Change<TState>(InputControl, TState, InputUpdateType, InputEventPtr)
    foreach (var ptM in ptInputState.GetMethods())
        if (ptM.Name == "Change" && ptM.IsGenericMethodDefinition && !ptM.GetParameters()[1].ParameterType.IsByRef)
            ptChange = ptM.MakeGenericMethod(ptStateType);
    var ptParams = ptChange.GetParameters();
    System.Action<object> ptWrite = ptState => ptChange.Invoke(null, new object[] { ptKeyboard, ptState,
        System.Activator.CreateInstance(ptParams[2].ParameterType), System.Activator.CreateInstance(ptParams[3].ParameterType) });
    var ptAfterUpdate = ptInput.GetEvent("onAfterUpdate");
    var ptStart = 0.0;
    var ptUpdates = 0;
    var ptReleasedAt = 0;
    System.Action ptHook = null;
    ptHook = () =>
    {
        try
        {
            var ptType = PtGet(ptInputState, "currentUpdateType").ToString();
            if (ptType == "Editor" || ptType == "BeforeRender") return; // only the updates the game reads from
            ptUpdates++;
            if (ptUpdates == 1) { ptStart = UnityEngine.Time.realtimeSinceStartupAsDouble; ptWrite(System.Activator.CreateInstance(ptStateType, new object[] { ptDown })); return; }
            if (ptReleasedAt == 0)
            {
                if (UnityEngine.Time.realtimeSinceStartupAsDouble - ptStart < holdSeconds) return;
                // ponytail: every key up, so two overlapping PtKey calls end together; track held keys if a case needs chords
                ptWrite(System.Activator.CreateInstance(ptStateType));
                ptReleasedAt = ptUpdates;
                return;
            }
            PtKeep("key." + key, "released after " + (UnityEngine.Time.realtimeSinceStartupAsDouble - ptStart).ToString("F3") + " s, " + (ptReleasedAt - 1) + " updates held");
        }
        catch (System.Exception e) { PtKeep("key." + key, "error: " + (e.InnerException ?? e).Message); }
        ptAfterUpdate.RemoveEventHandler(null, ptHook); // done, or failed: never left running every update
    };
    PtKeep("key." + key, "waiting");
    ptAfterUpdate.AddEventHandler(null, ptHook);
    return "key " + key + " queued";
};
System.Action<string, string, System.Func<string>> PtAt = (key, isoUtc, action) =>
{
    var when = System.DateTime.Parse(isoUtc, System.Globalization.CultureInfo.InvariantCulture,
        System.Globalization.DateTimeStyles.AdjustToUniversal | System.Globalization.DateTimeStyles.AssumeUniversal);
    UnityEngine.Events.UnityAction tick = null;
    tick = () =>
    {
        var now = System.DateTime.UtcNow;
        if (now < when) return;
        UnityEngine.Application.onBeforeRender -= tick;
        string result;
        try { result = action(); } catch (System.Exception e) { result = "error: " + e.Message; }
        PtKeep(key, "ran at " + now.ToString("HH:mm:ss.fff") + " UTC, " + (now - when).TotalMilliseconds.ToString("F0") + " ms late: " + result);
    };
    PtKeep(key, "waiting for " + when.ToString("HH:mm:ss.fff") + " UTC");
    UnityEngine.Application.onBeforeRender += tick;
};
