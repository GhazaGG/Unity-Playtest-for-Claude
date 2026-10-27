# Layer 1: Editor probes

Probes read the open scene and never save it. Run them with `unity command eval_file --file <probe>.cs`. Or put them in
`.playtest/steps/` and run them through `drive.py`; outside Play Mode the adapter's player lookup just returns null.

Each probe below returns one line per finding. Compare the result with what the checklist expects.

Probes are cheap and catch a lot. Start every run with them, and add a screenshot so a person can see what the numbers
describe.

## Scene inventory

```csharp
var sb = new System.Text.StringBuilder();
var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
sb.AppendLine(scene.path + " roots: " + string.Join(", ", System.Linq.Enumerable.Select(scene.GetRootGameObjects(), g => g.name)));
return sb.ToString();
```

## Objects stuck inside colliders

A dynamic body that starts inside a static collider gets pushed out on the first physics step. It can launch, or make
a loud impact sound, as soon as the session starts.

```csharp
var sb = new System.Text.StringBuilder();
UnityEngine.Physics.SyncTransforms();
var all = UnityEngine.Object.FindObjectsByType<UnityEngine.Collider>(UnityEngine.FindObjectsSortMode.None);
foreach (var body in UnityEngine.Object.FindObjectsByType<UnityEngine.Rigidbody>(UnityEngine.FindObjectsSortMode.None))
{
    if (body.isKinematic) continue;
    foreach (var mine in body.GetComponentsInChildren<UnityEngine.Collider>())
        foreach (var other in all)
        {
            if (mine.isTrigger || other.isTrigger || other.attachedRigidbody == body) continue;
            if (UnityEngine.Physics.ComputePenetration(mine, mine.transform.position, mine.transform.rotation,
                    other, other.transform.position, other.transform.rotation, out _, out var depth) && depth > 0.01f)
                sb.AppendLine(body.name + " is " + depth.ToString("F3") + " m inside " + other.name);
        }
}
return sb.Length == 0 ? "no dynamic body starts inside a collider" : sb.ToString();
```

To pick a free spot for a moved object, run the same check at the candidate position. Revert the move, or do it on a
copy, if the probe must not change the scene.

## Spots the game checks before spawning something

When a feature spawns into a slot only "if nothing solid is there", run the game's own check, with the game's own
radius and layers, on every slot. A slot that is blocked from the start makes the feature fail silently. Read the
private fields through `UnityEditor.SerializedObject`:

```csharp
var sb = new System.Text.StringBuilder();
UnityEngine.Physics.SyncTransforms();
foreach (var spawner in UnityEngine.Object.FindObjectsByType<UnityEngine.MonoBehaviour>(UnityEngine.FindObjectsSortMode.None))
{
    if (spawner.GetType().Name != "TODO_SpawnerType") continue;
    var so = new UnityEditor.SerializedObject(spawner);
    var spots = so.FindProperty("TODO_spots");
    var radius = so.FindProperty("TODO_radius").floatValue;
    for (int i = 0; i < spots.arraySize; i++)
    {
        var spot = (UnityEngine.Transform)spots.GetArrayElementAtIndex(i).objectReferenceValue;
        var near = UnityEngine.Physics.OverlapSphere(spot.position, 0.5f, ~0, UnityEngine.QueryTriggerInteraction.Ignore);
        sb.AppendLine(spot.name + " blocked=" + UnityEngine.Physics.CheckSphere(spot.position, radius, ~0, UnityEngine.QueryTriggerInteraction.Ignore)
            + " nearest: " + string.Join(", ", System.Array.ConvertAll(near, c => c.name + "@" + UnityEngine.Vector3.Distance(c.ClosestPoint(spot.position), spot.position).ToString("F2"))));
    }
}
return sb.ToString();
```

A small margin, such as 2 cm between the check radius and a wall, is worth a permanent EditMode test in the project.
Suggest one to the user.

## Missing references

```csharp
var sb = new System.Text.StringBuilder();
foreach (var mb in UnityEngine.Object.FindObjectsByType<UnityEngine.MonoBehaviour>(UnityEngine.FindObjectsSortMode.None))
{
    if (mb == null) { sb.AppendLine("missing script on an object"); continue; }
    var so = new UnityEditor.SerializedObject(mb);
    var it = so.GetIterator();
    while (it.NextVisible(true))
        if (it.propertyType == UnityEditor.SerializedPropertyType.ObjectReference && it.objectReferenceValue == null
            && it.objectReferenceInstanceIDValue != 0)
            sb.AppendLine(mb.name + "." + mb.GetType().Name + "." + it.propertyPath + " points to a missing object");
}
return sb.Length == 0 ? "no broken references" : sb.ToString();
```

Empty fields that are optional are not reported. Only references to objects that no longer exist are.

## Build settings and the menu's level

```csharp
return string.Join(", ", System.Linq.Enumerable.Select(UnityEditor.EditorBuildSettings.scenes, s => s.path + (s.enabled ? "" : " (off)")));
```

To read a value in another scene, open it additively, read it, and close it without saving:
`EditorSceneManager.OpenScene(path, OpenSceneMode.Additive)`, then `CloseScene(scene, true)`.

## Network prefab list (Netcode for GameObjects)

```csharp
var list = UnityEditor.AssetDatabase.LoadAssetAtPath<Unity.Netcode.NetworkPrefabsList>("Assets/TODO/DefaultNetworkPrefabs.asset");
return string.Join(", ", System.Linq.Enumerable.Select(list.PrefabList, p => p.Prefab != null ? p.Prefab.name : "null"));
```

Also check that scene-placed `NetworkObject`s have unique, non-zero `GlobalObjectIdHash` values: read them through
`SerializedObject`, property `GlobalObjectIdHash`.

## Console baseline

Run `unity command console_status` before the run and note the warnings that already exist, so they are not reported
as new.
