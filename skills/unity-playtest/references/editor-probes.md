# Layer 1: Editor probes

Probes read the open scene and never save it. Each probe below is a **step body**: save it as
`.playtest/steps/<name>.cs` and run `drive.py <name>`. drive.py puts the prelude in front (which declares `sb`) and
`return sb.ToString();` after it. To run one with a raw `unity command eval_file` instead, add
`var sb = new System.Text.StringBuilder();` at the top and `return sb.ToString();` at the end.

In Edit Mode the adapter looks nothing up, so probes run before the adapter is filled in. A probe-only run does not
need the adapter at all.

Probes are cheap and catch a lot. Start every run with them, and add a screenshot so a person can see what the numbers
describe. They use `UnityEditor`, so they run in the Editor only, never with `--player`.

## Scene inventory

```csharp
var ptScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
sb.AppendLine(ptScene.path + " roots: " + string.Join(", ", System.Linq.Enumerable.Select(ptScene.GetRootGameObjects(), g => g.name)));
```

## Colliders inside other colliders

Covers static geometry, triggers and bodies alike: a pickup buried in a wall, a prop sunk into the floor, a body that
will be shoved out on the first physics step. Pairs where one collider is under the other's object (a door and its
own leaf) are skipped. Contacts shallower than 2 cm count as resting, not stuck.

```csharp
UnityEngine.Physics.SyncTransforms();
var ptSeen = new System.Collections.Generic.HashSet<string>();
var ptFound = 0;
foreach (var a in UnityEngine.Object.FindObjectsByType<UnityEngine.Collider>(UnityEngine.FindObjectsSortMode.None))
{
    if (!a.enabled) continue;
    var ab = a.bounds;
    foreach (var b in UnityEngine.Physics.OverlapBox(ab.center, ab.extents, UnityEngine.Quaternion.identity, ~0, UnityEngine.QueryTriggerInteraction.Collide))
    {
        if (b == a || a.transform.IsChildOf(b.transform) || b.transform.IsChildOf(a.transform)) continue;
        var key = a.GetInstanceID() < b.GetInstanceID() ? a.GetInstanceID() + ":" + b.GetInstanceID() : b.GetInstanceID() + ":" + a.GetInstanceID();
        if (!ptSeen.Add(key)) continue;
        if (!UnityEngine.Physics.ComputePenetration(a, a.transform.position, a.transform.rotation, b, b.transform.position, b.transform.rotation, out _, out var depth) || depth < 0.02f) continue;
        var bb = b.bounds;
        var buried = bb.Contains(ab.min) && bb.Contains(ab.max) ? " (" + a.name + " is fully inside)"
                   : ab.Contains(bb.min) && ab.Contains(bb.max) ? " (" + b.name + " is fully inside)" : "";
        sb.AppendLine(a.name + (a.isTrigger ? "(T)" : "") + " x " + b.name + (b.isTrigger ? "(T)" : "") + " depth=" + depth.ToString("F2") + buried);
        ptFound++;
    }
}
if (ptFound == 0) sb.AppendLine("no collider is more than 2 cm inside another");
```

Read the list with the design in mind: a trigger that is meant to overlap (a pickup radius resting on a table) is
fine; a visible object "fully inside" a wall or floor is a bug. Check a suspicious one with a Scene view screenshot.
Non-convex mesh colliders cannot be compared with each other (`ComputePenetration` returns false), so a level made of
mesh colliders needs a raycast check instead.

## Spawn points

Put the player's own capsule at every spawn point and see what it hits. Take the radius and height from the player
prefab's `CharacterController` or `CapsuleCollider`, and find the spawn points the way the spawn code does (a list on
a component, a tag, a name pattern):

```csharp
UnityEngine.Physics.SyncTransforms();
float ptRadius = 0.4f, ptHeight = 2f, ptCenterY = 1f; // TODO: from the player prefab
foreach (var t in UnityEngine.Object.FindObjectsByType<UnityEngine.Transform>(UnityEngine.FindObjectsSortMode.None))
{
    if (!t.name.StartsWith("Spawn") || t.childCount > 0) continue; // TODO: how the game finds its spawn points
    var bottom = t.position + UnityEngine.Vector3.up * (ptCenterY - ptHeight / 2f + ptRadius + 0.02f);
    var top = t.position + UnityEngine.Vector3.up * (ptCenterY + ptHeight / 2f - ptRadius);
    var hits = UnityEngine.Physics.OverlapCapsule(bottom, top, ptRadius, ~0, UnityEngine.QueryTriggerInteraction.Ignore);
    var ground = UnityEngine.Physics.Raycast(t.position + UnityEngine.Vector3.up * 0.1f, UnityEngine.Vector3.down, out var hit, 5f) ? hit.distance - 0.1f : -1f;
    sb.AppendLine(t.name + " " + t.position.ToString("F2") + (hits.Length == 0 ? " free" : " BLOCKED by " + string.Join(", ", System.Array.ConvertAll(hits, c => c.name)))
        + (ground < 0f ? ", no floor below" : ", floor " + ground.ToString("F2") + " m below"));
}
```

When a feature spawns into a slot only "if nothing solid is there", also run **the game's own check**, with its own
radius and layers (read private fields through `UnityEditor.SerializedObject`). A slot that is blocked from the start
makes the feature fail silently, and a 2 cm margin to a wall is worth a permanent EditMode test in the project.

## Colliders that don't move with the moving part

Doors, hatches, lifts and drawbridges move a child (a hinge, a pivot, a platform) at runtime. A collider on the same
object that is *not* under that child stays where it was: the door opens but the doorway stays blocked. This lists,
for every component that holds a reference to one of its own descendants, the colliders that will not follow it:

```csharp
var ptFound = 0;
foreach (var mb in UnityEngine.Object.FindObjectsByType<UnityEngine.MonoBehaviour>(UnityEngine.FindObjectsSortMode.None))
{
    var it = new UnityEditor.SerializedObject(mb).GetIterator();
    while (it.NextVisible(true))
    {
        if (it.propertyType != UnityEditor.SerializedPropertyType.ObjectReference) continue;
        var part = it.objectReferenceValue as UnityEngine.Transform;
        if (part == null || part == mb.transform || !part.IsChildOf(mb.transform)) continue;
        foreach (var c in mb.GetComponentsInChildren<UnityEngine.Collider>(true))
            if (!c.transform.IsChildOf(part) && !c.isTrigger)
            {
                sb.AppendLine(mb.GetType().Name + " on " + mb.name + " moves " + it.propertyPath + " (" + part.name + "), but solid collider on "
                    + c.name + " does not move with it: size " + c.bounds.size.ToString("F2"));
                ptFound++;
            }
    }
}
if (ptFound == 0) sb.AppendLine("every solid collider follows the part that moves");
```

A hit is not always a bug (a door frame can be meant to stay), but each one is worth one walk-through in Play Mode
with `Walk()` (see [scripted-input.md](scripted-input.md)).

## Missing references and missing scripts

Includes inactive objects. "Missing" means the field points at an object or asset that no longer exists; empty
optional fields are not reported.

```csharp
var ptScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
var ptFound = 0;
foreach (var root in ptScene.GetRootGameObjects())
    foreach (var t in root.GetComponentsInChildren<UnityEngine.Transform>(true))
    {
        var missing = UnityEditor.GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject);
        if (missing > 0) { sb.AppendLine(t.name + ": " + missing + " missing script(s)"); ptFound++; }
        foreach (var comp in t.GetComponents<UnityEngine.Component>())
        {
            if (comp == null) continue;
            var it = new UnityEditor.SerializedObject(comp).GetIterator();
            while (it.NextVisible(true))
                if (it.propertyType == UnityEditor.SerializedPropertyType.ObjectReference && it.objectReferenceValue == null
                    && it.objectReferenceInstanceIDValue != 0)
                {
                    sb.AppendLine(t.name + "." + comp.GetType().Name + "." + it.propertyPath + " points to a missing object");
                    ptFound++;
                }
        }
    }
if (ptFound == 0) sb.AppendLine("no missing references or scripts");
```

For a missing asset, find which file it was: the scene file has the GUID next to the field, and
`UnityEditor.AssetDatabase.GUIDToAssetPath(guid)` may still remember its old path.

## Build settings and network setup

```csharp
sb.AppendLine("build scenes: " + string.Join(", ", System.Linq.Enumerable.Select(UnityEditor.EditorBuildSettings.scenes, s => s.path + (s.enabled ? "" : " (off)"))));
var ptNoType = PtTypeOrNull("Unity.Netcode.NetworkObject, Unity.Netcode.Runtime");
if (ptNoType != null)
{
    var hashes = new System.Collections.Generic.Dictionary<uint, string>();
    foreach (UnityEngine.Component no in UnityEngine.Object.FindObjectsByType(ptNoType, UnityEngine.FindObjectsInactive.Include, UnityEngine.FindObjectsSortMode.None))
    {
        var hash = (uint)new UnityEditor.SerializedObject(no).FindProperty("GlobalObjectIdHash").longValue;
        if (hash == 0 || hashes.ContainsKey(hash)) sb.AppendLine("NetworkObject " + no.name + " hash " + hash + (hash == 0 ? " is zero" : " repeats " + hashes[hash]));
        else hashes[hash] = no.name;
    }
    sb.AppendLine(hashes.Count + " in-scene NetworkObjects checked");
    foreach (var guid in UnityEditor.AssetDatabase.FindAssets("t:NetworkPrefabsList"))
    {
        var path = UnityEditor.AssetDatabase.GUIDToAssetPath(guid);
        var list = UnityEditor.AssetDatabase.LoadMainAssetAtPath(path);
        var prefabs = (System.Collections.IEnumerable)PtGet(list, "PrefabList");
        var names = new System.Collections.Generic.List<string>();
        foreach (var p in prefabs) { var go = PtGet(p, "Prefab") as UnityEngine.Object; names.Add(go != null ? go.name : "null"); }
        sb.AppendLine(path + ": " + string.Join(", ", names));
    }
}
```

To read a value in another scene, open it additively, read it, and close it without saving:
`EditorSceneManager.OpenScene(path, OpenSceneMode.Additive)`, then `CloseScene(scene, true)`.

## Console baseline

Before the run, note what is already in the console, so it is not reported as new. Use the `groundTruth` numbers of
`unity command console_status`; the `counts` block can disagree with them. There are two lists, and each misses
something:
- `unity command console` keeps its own buffer since the Editor started. It can miss native errors.
- The Console window's list, read by the step below, has the native errors, but "Clear on Play" empties it when
  Play Mode starts, and a message logged a moment ago can take an Editor tick to appear.

Read both, and say which one an entry came from.

```csharp
var ptLogs = System.Type.GetType("UnityEditor.LogEntries, UnityEditor");
var ptEntry = System.Activator.CreateInstance(System.Type.GetType("UnityEditor.LogEntry, UnityEditor"));
var ptCount = (int)ptLogs.GetMethod("StartGettingEntries").Invoke(null, null);
try
{
    for (int i = 0; i < ptCount; i++)
    {
        ptLogs.GetMethod("GetEntryInternal").Invoke(null, new object[] { i, ptEntry });
        var text = (string)PtGet(ptEntry, "message");
        sb.AppendLine(text.Split('\n')[0]);
    }
}
finally { ptLogs.GetMethod("EndGettingEntries").Invoke(null, null); }
if (ptCount == 0) sb.AppendLine("console is empty");
```

## Scene view screenshots

- `drive.py scene:NAME` captures what the Scene view shows. Gizmos, icons and the selection outline are **not** in
  the image, so an empty object such as a spawn point does not show. Put the point of interest at the view's pivot,
  which is always the image centre, and say so in the report.
- Frame in one step and capture in the next. After `SceneView.LookAt`, the camera moves only on its next repaint.
- `LookAt(point, rotation, size)` puts the camera about `2 x size` from the point. To see an object buried in a wall,
  put the camera inside the wall: back faces are culled, so the camera sees what the wall hides.
- Note the Scene view camera and the selection before you change them, and put them back at the end.
