---
type: llm
focus: trace
weight: 1
---

The report names the cause: the coin stays spawned for its 0.25 s collect animation and Interact has no already-taken check, so each request in that window awards the coin.
