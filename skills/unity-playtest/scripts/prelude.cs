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
