# Playtest checklist: <feature or PR>

Branch and commit: <branch @ sha> · Unity <version> · Date: <date>

The **Layer** column says how the case can be checked:
- `probe`: read in the Editor, without playing;
- `solo`: scripted Play Mode;
- `session`: host + client;
- `adversarial`: a forged client intent;
- `human`: feel, sound or visuals, which only a person can judge.

The **By** column says who verified the result: `script`, `human`, or `script+human`.

| ID | Layer | Steps | Expected | Result | By | Notes |
|----|-------|-------|----------|--------|----|-------|
| A1 | probe | Open `<scene>`; list the objects the feature needs | All present, none inside colliders | | | |
| B1 | solo | Play from `<menu>`, start the session | Player spawns at `<place>`; HUD shows `<text>` | | | |
| C1 | session | Client tries `<host-only action>` | Refused; state unchanged on both peers | | | |
| C2 | adversarial | Client sends `<intent>` from 6 m away and from behind a wall | Server refuses both | | | |
| D1 | human | `<feel question>` | `<what good feels like>` | | | |

Results are `pass`, `fail` or `skip`. Leave the cell empty for "not run". Never fill in a `human` row from a script.
