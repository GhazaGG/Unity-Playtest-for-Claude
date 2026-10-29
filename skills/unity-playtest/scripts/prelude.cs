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
// "LeftShift"); the key goes down now and up after holdSeconds, and never in the same frame. The result is kept under
// "key." + key once the key is up. Projects on the old Input Manager cannot get keys this way; use Press() there.
System.Func<string, float, string> PtKey = (key, holdSeconds) =>
{
    var ptInput = PtTypeOrNull("UnityEngine.InputSystem.InputSystem, Unity.InputSystem");
    if (ptInput == null) return "no Input System package: use Press()";
    var ptKeyboard = PtGet(PtType("UnityEngine.InputSystem.Keyboard, Unity.InputSystem"), "current");
    if (ptKeyboard == null) return "no keyboard device";
    var ptKeyEnum = PtType("UnityEngine.InputSystem.Key, Unity.InputSystem");
    var ptStateType = PtType("UnityEngine.InputSystem.LowLevel.KeyboardState, Unity.InputSystem");
    var ptDown = System.Array.CreateInstance(ptKeyEnum, 1);
    ptDown.SetValue(System.Enum.Parse(ptKeyEnum, key, true), 0);
    System.Reflection.MethodInfo ptQueue = null;
    foreach (var ptM in ptInput.GetMethods())
        if (ptM.Name == "QueueStateEvent" && ptM.IsGenericMethodDefinition) ptQueue = ptM.MakeGenericMethod(ptStateType);
    System.Action<object> ptSend = ptState => ptQueue.Invoke(null, new object[] { ptKeyboard, ptState, -1.0 });
    ptSend(System.Activator.CreateInstance(ptStateType, new object[] { ptDown }));
    var ptStart = UnityEngine.Time.realtimeSinceStartupAsDouble;
    var ptFrames = 0;
    UnityEngine.Events.UnityAction tick = null;
    tick = () =>
    {
        // Two frames at least: the press is read in the first input update, the release in a later one.
        if (++ptFrames < 2 || UnityEngine.Time.realtimeSinceStartupAsDouble - ptStart < holdSeconds) return;
        UnityEngine.Application.onBeforeRender -= tick;
        // ponytail: every key up, so two overlapping PtKey calls end together; track held keys if a case needs chords
        ptSend(System.Activator.CreateInstance(ptStateType));
        PtKeep("key." + key, "released after " + (UnityEngine.Time.realtimeSinceStartupAsDouble - ptStart).ToString("F3") + " s, " + ptFrames + " frames");
    };
    PtKeep("key." + key, "waiting");
    UnityEngine.Application.onBeforeRender += tick;
    return "key " + key + " down";
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
