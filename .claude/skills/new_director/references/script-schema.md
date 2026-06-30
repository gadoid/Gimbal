# `script.json` Field Contract

`script.json` is the only file the model edits directly during the scripting
stage (剪辑链 阶段2). It sits between `flow.json` (mechanical capture
analysis) and the final `scenario.json` (机械组装, 发版链 output). Four
scripts share this contract — if a field here changes shape, update all four:

- `script_init.py` — writes the initial skeleton (mechanical, from `flow.json`)
- `script_gap_resolve.py` — atomically resolves one `open_gaps` entry (the
  only tool allowed to insert a synthetic step)
- `script_lint.py` — checks internal consistency (mechanical, read-only,
  剪辑层终检 — knows nothing about config/resource/templating)
- `script_assemble.py` — consumes the finished file (mechanical, assumes all
  judgment is already complete; 发版链, the only place templating happens)

## Top level

```jsonc
{
  "kind": "script",
  "source_capture": "<path to the original .ndjson>",
  "business_host": "<from flow.json summary>",
  "scaffold_ref": "<path to the scenario scaffold — steps:[], config/resource decided>",
  "steps": [ <Step>, ... ],
  "open_gaps": [ <Gap>, ... ],
  "bulk_extract_candidates": [ ... ],   // carried verbatim from flow.json, advisory only
  "ignored_external": [ ... ]           // carried verbatim from flow.json, informational only
}
```

`bulk_extract_candidates` and `ignored_external` are **read-only carry-forward**
from `flow.json` — neither `script_assemble.py` nor `script_lint.py` mutate
them. `bulk_extract_candidates` exists so the model can see, during scripting,
which responses carry a whole list/object that might be consumed wholesale
downstream; if one is actually needed, wire it manually as a normal entry in
some step's `bindings.extracts`. `ignored_external` exists purely as an audit
trail of what analyze_flow.py already excluded and why — `script_lint.py`
uses it to flag suspicious re-derivation, but the model should never need to
act on it directly.

## Step

```jsonc
{
  "idx": 12,                  // original capture record index; synthetic steps use idx>=100
  "path": "/api/...",
  "method": "POST",
  "decision": "keep" | "drop",   // the ONLY field the model normally flips
  "reason": "<from flow.json, or a manual override reason>",
  "dup_of": null,                 // set if flow.json flagged this as a repeat of an earlier idx
  "synthetic": false,             // true only for steps inserted by script_gap_resolve.py
  "headers": { ... },             // raw captured headers (synthetic: model-supplied placeholder)
  "request_body": { ... },        // parsed request body, PLAIN LITERAL VALUES — never ${...}
  "bindings": {
    "extracts": [ { "var": "order_id", "expression": "$.response_body...", "scope": "scenario", "source_edge": true } ],
    "assigns":  [ { "var": "order_id", "target": "$.request_body...", "source_edge": true } ]
  },
  "notes": ""
}
```

**`request_body` must never contain `${...}` templating.** Real captured
steps already won't (their bodies are literal capture data). Synthetic steps
built by hand via `script_gap_resolve.py` must ALSO use plain literal test
values (e.g. the actual `bl_no` string), never a pre-templated reference —
value-matching against the scaffold happens uniformly for every step, real or
synthetic, at the assemble stage. `script_lint.py` rejects any `${...}` found
here as a scope-boundary leak: templating is 发版链's job, not 剪辑链's.

**`source_edge`** distinguishes a binding that came straight from the
verified lineage graph (`true`) from one a human/model added by hand — either
by wiring a `bulk_extract_candidates` entry or via `script_gap_resolve.py`
(`false`). This is informational, not enforced, but makes a script.json diff
easy to audit: every `source_edge: false` entry is a place a judgment call
was made.

## Gap

```jsonc
{
  "field": "order_id",
  "value": "327661182355767296",
  "consumer_idx": 29,
  "consumer_path": "$.request_body.select_list[0].amount_list[0].order_id",
  "candidates": [ { "endpoint": "/api/...", "path": "$.response_body...", "inputs": ["bl_no"] } ],
  "status": "open" | "resolved",
  "resolution": null | { "kind": "lookup", "var": "...", "synthetic_idx": 100, "endpoint": "...", "extract_expression": "..." }
}
```

A gap means exactly one thing in this design: **a value some request needs,
but no earlier response in this capture produced it, and it didn't match
anything declared in the scaffold's `config.vars`/`resource` either** (if it
had, `analyze_flow.py` would have classified it `ignored_external` instead
and it would never become a gap at all). There is therefore exactly one way
to resolve a gap — insert a context-fetch step — and `script_gap_resolve.py`
is the only tool allowed to do it, atomically (see that script's docstring
for the bug class this prevents). The model's only judgment is picking a
candidate (or a hand-built endpoint) and a **non-colliding** variable name —
`script_lint.py`'s single-write check will catch a name collision with an
existing lineage variable, but picking a clear distinct name up front
(`order_id_sub`, not reusing `order_id`) avoids the rework.

## Boundary the contract enforces

`script.json`, end to end, only ever describes the **cut**: which requests
survive, in what order, and how their response/request fields wire together.
It never describes how a value got into a request from *outside* the
capture's own response chain — that is `config.vars`/`resource`'s job, lives
in the scaffold, and is injected only once at `script_assemble.py` time. This
is the load-bearing invariant of the whole redesign: a finished, lint-clean
`script.json` should be assemblable against *any* scaffold that declares
the same external inputs, without re-running any judgment.
