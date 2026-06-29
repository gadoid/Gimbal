# Stage 2 — script_init + scripting

Two sub-stages. **(2a)** is mechanical: fold `flow.json` into a step-centric `script.json` skeleton. **(2b)** is where the model applies judgment by editing the skeleton.

## Input
- `<capture>.flow.json` from stage 1.
- `<capture>.ndjson` — recorded into `source_capture` (so stage 4 can re-read raw bodies by idx); not parsed here.
- `<golden>.e2e.json` — recorded into `golden_ref` (so stage 4 can copy `meta`/`config`/`resource`); not parsed here.

## Output
- `<capture>.script.json` (skeleton):
  ```jsonc
  {
    "kind": "script",
    "source_capture": "<path>",
    "business_host": "<host>",
    "golden_ref": "<path>",
    "steps": [                                       // one per record, KEEP and DROP both retained
      { idx, order, status: "kept"|"dropped"|"collapsed",
        role: "mutation"|"context_fetch"|null,
        method, path, decision_reason, collapsed_into,
        bindings: { extracts: [...], assigns: [...] } }, ...
    ],
    "open_gaps": [                                   // lifted from missing_producers
      { field, value, consumer_idx, status: "unresolved",
        candidates: [...], resolution: null }, ...
    ]
  }
  ```

## Mechanical vs Judgment
- **Mechanical (2a)**: every kept record becomes a step with `order` (dense 0..N over kept steps); every lineage edge seeds exactly one `extract` (on producer) and one `assign` (on consumer); `dup_of` is carried as a `[dup_of N — review for collapse]` hint but **not auto-applied**.
- **Judgment (2b)**: the model edits the skeleton directly.
  - Keep every state-changing mutation.
  - Keep a read only if it produces an id a later kept step consumes.
  - Drop pure UI-population reads (`status: "dropped"` + `decision_reason`).
  - Collapse true duplicates (`status: "collapsed"` + `collapsed_into: <idx>`) — never collapse a producer.
  - Drop a producer whose value is never genuinely needed downstream.

## Boundaries / Edge Cases
- A capture may be partial. Coverage gaps vs the golden are expected and correct when the underlying request is simply absent. Never invent a step to "complete" the golden.
- Script retains dropped records (audit trail).
- `role` is seeded from `analyze_flow`'s reason text ("mutation verb" → mutation; "produces downstream id" → context_fetch). Model corrects.
- `decision_reason` is **free text, lenient mode** — no rigid codes required.

## Open Questions
- TBD