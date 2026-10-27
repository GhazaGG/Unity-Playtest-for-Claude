# Playtest report: <feature or PR>

Branch and commit: <branch @ sha> · Unity <version> · Date: <date>

Setup:
- Solo: Editor Play Mode, started in code from `<menu scene>`.
- Session: host in the Editor, client from a local development build, <N> ms simulated latency per peer.
- Harness shortcuts used: teleport, <timer> refill, <anything else>.

## Summary
- Passed: <n> · Failed: <n> · Skipped: <n> · Needs a human: <n>
- One sentence on the most important finding.

## Findings

### F1: <short title> (<severity: bug / race / design / test-tool limit>)
- **Case:** <checklist ID>
- **What happens:** <observed behaviour, with the state lines that prove it>
- **Expected:** <expected behaviour>
- **Repro:** <steps a person can follow in the Editor>
- **Cause (if found):** <file:line and why>
- **Fix or proposal:** <what changed, or what to decide>

## Excluded as harness artefacts
- <failure, and why it was the harness and not the game, e.g. "teleport then press in one step: the server copy had not moved yet">

## Still needs a human
- <case ID: exactly what to look, listen or feel for>

## Cleanup
- Play Mode stopped, client closed, `git status` clean (doctor.py output: <OK / warnings>).
- Temporary settings reverted: <list, or "none">.
