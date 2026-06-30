# Script Schema Reference (`script.json`)

The **script** is Director's intermediate object — the bridge between the
analysis half (initial-cut + scripting) and the assembly half (gap-resolution +
assembly). It captures, **as data**, every judgment the model makes about a
capture so that:

- those judgments are auditable after the fact (why a record was kept/dropped),
- the final assembly step becomes mechanical (no model judgment needed), and
- gap resolution has one place to record what was decided for each missing id.

`flow.json` (from `analyze_flow.py`) is record-centric and keyed by `idx`.
The script is **step-centric**: it folds `records`, `lineage`,
`missing_producers`, and `bulk_extract_candidates` into one entry per kept
record, plus a top-level gap list. It is produced by `script_init.py`, edited by
the model during scripting and gap-resolution, checked by `script_lint.py`, and
consumed by `script_assemble.py`.

> Loading order matters: this file defines the shape all three scripts agree on.
> `scenario-schema.md` defines what assembly finally emits. Read both before
> touching script code.

## Top-level

```jsonc
{
  "kind": "script",
  "source_capture": "<path to the .ndjson this was derived from>",
  "business_host": "<host analyze_flow picked>",
  "golden_ref": "<path to the golden e2e.json, for config fallback at assembly>",
  "steps": [ <step>, ... ],        // one per record (kept AND dropped, see below)
  "open_gaps": [ <gap>, ... ]      // ids consumed but not produced in capture
}
```

`source_capture`, `business_host`, `golden_ref` are filled by `script_init.py`
from its inputs / CLI args. The model does not edit them.

## Step

One entry per record in the capture. **Dropped records are retained** (with
`status: "dropped"` and a reason) so the script is a complete audit trail of
what the capture contained and why each record did or didn't make the cut.

```jsonc
{
  "idx": 12,                       // the record's idx in flow.json — the join key
  "order": 3,                      // execution order among KEPT steps; null for dropped
  "status": "kept",                // "kept" | "dropped" | "collapsed"
  "role": "mutation",              // "mutation" | "context_fetch" | null (dropped)
  "method": "POST",
  "path": "/api/order/order/orderAdd",
  "decision_reason": "state-changing mutation; produces order_id",   // free text
  "collapsed_into": null,          // when status=="collapsed", the idx it duplicates
  "bindings": {
    "extracts": [
      {
        "var": "order_id",                              // scenario variable name
        "expression": "$.response_body.data.order_id",  // verified producer path
        "scope": "scenario"                             // "scenario" | "step"
      }
    ],
    "assigns": [
      {
        "var": "order_id",                              // must match an upstream extract var
        "target": "$.request_body.order_id"             // where to inject
      }
    ]
  }
}
```

### Field rules

- **`idx`** — copied verbatim from `flow.json`; the immutable join key back to
  the raw record. Assembly re-reads the raw request/response by this idx.
- **`status`** — `script_init.py` sets `kept` for every record `analyze_flow`
  marked KEEP and `dropped` for every DROP. The model may flip a `kept` step to
  `dropped` (judged noise) or `collapsed` (a true duplicate of another kept
  step), but should **not** flip a `dropped` step to `kept` without re-checking
  the capture — dropped records carry no verified bindings.
- **`order`** — dense 0-based sequence over `kept` steps only, in capture order
  unless the model reorders for producer-before-consumer correctness. `null`
  for dropped/collapsed.
- **`role`** — `mutation` for state-changing calls; `context_fetch` for a
  read/detail/list kept only because it produces a downstream id. `init`
  pre-fills this from `analyze_flow`'s reason text; the model corrects it.
- **`decision_reason`** — free text (lenient mode). No reason code is required.
  It exists for human/AI audit, never parsed by assembly.
- **`bindings.extracts[]`** — `init` seeds these from `flow.json.lineage`
  (each edge whose `producer_idx == this.idx`). `expression` MUST be a path
  that `analyze_flow` verified against a real response — never hand-invent one.
  Honor the **single-write rule** from `scenario-schema.md`: a scenario-scope
  `var` is written once; a second capture of the same value uses `scope: step`
  or a distinct name (`order_sub_id_pen`).
- **`bindings.assigns[]`** — `init` seeds these from lineage edges whose
  `consumer_idx == this.idx`. Every `assign.var` must resolve to some upstream
  `extract.var` (on an earlier-ordered step) OR to a resolved gap (see below).

## Gap

An id a request consumes that no earlier response in the capture produced.
`script_init.py` lifts these from `flow.json.missing_producers`. Resolution is
recorded **in place** by adding a `resolution` object during gap-resolution.

```jsonc
{
  "field": "order_id",             // the consumed id's field name
  "value": "327441944651235328",   // the concrete value seen in the request
  "consumer_idx": 8,               // which step needs it (join back to steps[].idx)
  "status": "unresolved",          // "unresolved" | "resolved_lookup" | "resolved_static" | "accepted_var"
  "candidates": [                  // from catalog / analyze_flow suggestions; advisory
    {
      "endpoint": "/api/order/orderEntrust/orderPage",
      "path": "$.response_body.data.data[*].order_id",
      "inputs": ["bl_no"]
    }
  ],
  "resolution": null               // filled by the model — see below
}
```

### Resolution shapes (model writes one of these into `resolution`)

A gap is resolved exactly one of three ways:

1. **Insert a context-fetch step** (`status: "resolved_lookup"`): the model picks
   a candidate, and a NEW step is added to `steps[]` for that lookup endpoint
   with an `extract` of the chosen `field`. The gap's `resolution` records the
   inserted step's idx and which candidate was used:
   ```jsonc
   "resolution": { "kind": "lookup", "inserted_idx": 100, "candidate_index": 0 }
   ```
   Inserted steps use synthetic idx values ≥ 100 (above any real record idx) so
   they never collide with capture indices. They carry `role: "context_fetch"`,
   their own `bindings.extracts`, and any `assigns` for the inputs they need.

2. **Run-constant static var** (`status: "resolved_static"` / `"accepted_var"`):
   the id is a pre-known test input (`bl_no`, a selected master-data id), so it
   belongs in `config.vars` and the consumer references `${var.x}`. No new step.
   ```jsonc
   "resolution": { "kind": "static", "var": "bl_no" }
   ```

3. **Left open** (`status: "unresolved"`): only valid as an intermediate state.
   `script_lint.py` flags any gap still `unresolved` once scripting is "done".

> Never fall back to a static var for an id the business process *generates*
> (`order_id`, `audit_id`, `receive_account_id`, …). Those must be either
> produced by a kept step or resolved via an inserted lookup. The static path is
> only for genuinely run-constant inputs. This mirrors the two-namespace rule in
> `scenario-schema.md`.

## What `script_lint.py` checks (lenient mode)

Structural completeness only — it does NOT judge whether the kept set is the
"right" business flow (that's the model's job, re-verified at final screening):

- every `kept`/`collapsed` step has a valid `idx` present in the source flow;
- `order` is a dense 0-based sequence over kept steps with no gaps/dups;
- `collapsed` steps name a real `collapsed_into` idx that is itself `kept`;
- every `assign.var` resolves to an earlier `extract.var` or a `resolved_*` gap
  (no dangling assigns);
- no scenario-scope `extract.var` is written more than once (single-write rule);
- every gap is resolved (`status != "unresolved"`); each `resolution` is a
  well-formed shape above and, for `kind: "lookup"`, `inserted_idx` exists in
  `steps[]`.

Lint does NOT check: whether a `decision_reason` is "good", whether a dropped
record should have been kept, or whether an extract path is semantically the
right id — those are model judgments, caught (if at all) at final screening by
`validate_scenario.py` plus the model's own review.

## Relationship to the other references

- `flow.json` — `script_init.py`'s input. Record-centric, keyed by `idx`.
- `scenario-schema.md` — what `script_assemble.py` finally emits. The script's
  `bindings` map directly onto that file's `extract`/`assign`/`assertion`
  strategy blocks; every kept step still gets the mandatory `assert_status_200`.
- `lookup-catalog.md` / `lookup_catalog.json` — source of gap `candidates`.
