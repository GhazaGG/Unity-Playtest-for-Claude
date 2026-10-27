# Playtest map: <project name>

Written once during recon and reused by later runs. Keep it short, and update it when the code changes.

## Engine and tools
- Unity: <version from ProjectSettings/ProjectVersion.txt>
- com.unity.pipeline: <version>
- Networking: <none | Netcode for GameObjects x.y + Unity Transport x.y | other>
- Session scene (what Play from the menu loads): <scene path>
- Start in Play Mode from: <menu scene path>

## Interaction path (what the interact key does)
- Input action: <asset and action name, e.g. Player/Interact>
- Read in: <Type.Method>, which on press calls <Type.Method>
- Target picked by: <detector type and method, ray origin, max distance>
- Networked request (if any): <client method, then server RPC, then the server-side validation>
- Look: <yaw on which transform, pitch on which transform, and the field that stores pitch>
- Movement: <CharacterController / Rigidbody, so how to teleport safely>

## Session entry points
- Start host: <Type.Method(args)>
- Join: <Type.Method(ip, port)>
- Leave (the in-game leave, not "cancel connect"): <Type.Method>
- Simulated latency, if the project has it: <field or setting, e.g. a send delay in ms per peer>

## Timers that drain while the agent thinks
- <name: field to refill, or "none">

## State worth asserting
- <e.g. round state, score or money, held item, inventory count, report text>

## Harness notes
- <anything learned the hard way in this project>
