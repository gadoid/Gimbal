---
name: gimbal-traffic-to-scenario
description: >-
  Convert captured API traffic (Prism/mitmproxy ndjson, where each line is
  {ts, method, host, path, headers, body, response}) into a schema-valid,
  data-driven GIMBAL test scenario — WITHOUT depending on a golden example
  scenario for runtime judgment. Use this whenever the user wants to turn a
  real business flow / traffic capture / ndjson / FlowSession dump into a
  GIMBAL scenario or test case, "distill" or "denoise" captured requests
  into an ordered API chain, generate extract/assign context-passing between
  steps, or mentions GIMBAL scenario generation, Director skill, 流量转用例,
  抓包生成测试, ndjson 蒸馏, 剪辑链, 发版链, or 顺序接口数据驱动用例. Trigger
  even if they only provide the ndjson and a scenario scaffold without saying
  "skill".
---

# Director: Traffic → Scenario

Turn a real captured business flow into ONE GIMBAL scenario: an ordered chain
of API calls that is denoised, sanitized, and wired together with
`extract`/`assign` so it replays end-to-end.

## The two-chain architecture

The pipeline is split into two chains with exactly one shared artifact
between them: the **standard `steps` array** (ordered, wiring-complete,
literal-valued, no external info injected).

- **剪辑链 (cutting chain)** — capture → `steps`. Decides which requests
  survive, in what order, and how their internal response→request lineage
  wires together. Never touches token/var/resource injection. Stages 0–3
  below.
- **发版链 (release chain)** — `steps` → final `scenario.json`. Injects
  everything that was decided *before* the capture ever happened — `config`,
  `resource`, the auth token — into the steps it's handed. Read-only on
  structure/ordering/wiring; write-only on values. Stage 4 below.

This split exists so the two chains evolve independently: swapping where
`config`/`resource` come from (e.g. once Plate can supply them) never touches
the cutting chain's judgment logic, and changing how gaps get resolved never
touches the assemble stage.

**There is no golden-example dependency anywhere in this pipeline.** What
counts as "external input" (and therefore out of scope for the cutting
chain) comes entirely from a **scenario scaffold** you supply up front — a
scenario JSON with `kind/scenarioId/meta/config/resource` already decided
and `steps: []`. The scaffold doubles as the shell the final scenario gets
assembled into, so the same file is both the first input and the structural
basis of the last output.

## Inputs

- **the capture** — a `*.ndjson` (one JSON record per line). Bodies in
  `body` and `response.body` are JSON *strings* that must be parsed.
- **the scaffold** — a scenario JSON with `steps: []` but `config.vars`,
  `config.users`, `config.services`, `resource`, and `meta` already decided.
  This is the *only* source of truth for "what is externally declared input"
  — there is no fallback to a golden example.

## Workflow

### Stage 0 — `analyze_flow.py` (剪辑链, always run first)

```bash
python scripts/analyze_flow.py <capture>.ndjson \
    --scaffold <scaffold>.json \
    --catalog references/lookup_catalog.json \
    --noise-keys references/noise-keys.json \
    --value-blacklist references/common-values-blacklist.json \
    --out flow.json --md flow.md
```

Omit `--business-host` to auto-pick the most frequent host. This script
classifies every request-side scalar leaf into exactly one bucket, in this
order:

1. **noise** — the field's *name* (last JSONPath segment) hits
   `references/noise-keys.json` (e.g. `request_no`, `trace_id`) → excluded
   from all lineage analysis, regardless of value.
2. **external** — the field's *value* matches something declared in the
   scaffold's `config.vars`/`resource` (after the length floor `--min-value-len`,
   default 4, and `references/common-values-blacklist.json` filter out
   short/common values like `"1"`, `"USD"` that would over-match). Recorded
   under `ignored_external`; **left completely alone** — no extract, no
   assign, no placeholder, the literal value just stays. Injecting the real
   value back in is the assemble stage's job, by an independent value scan
   against the same scaffold.
3. **dynamic_lineage** — id-shaped value, real producer found in an earlier
   response within this capture → becomes an `extract`/`assign` candidate.
4. **gap** — id-shaped value, no producer in this capture, not external
   either → a genuinely missing internal link. If a catalog is supplied, the
   script suggests a query endpoint per gap.
5. **literal** — everything else. No policy, kept as-is.

Read `flow.md` for the human-readable view.

### Stage 1 — `script_init.py` (剪辑链, mechanical fold)

```bash
python scripts/script_init.py flow.json --capture <capture>.ndjson \
    --scaffold <scaffold>.json --out script.json
```

Folds `flow.json` into `script.json`, the file the model edits directly
during scripting. Pre-fills `bindings.extracts`/`bindings.assigns` from the
already-verified lineage graph (one `extract` per producer-step-and-var pair,
even if multiple consumers need it) and turns `missing_producers` into
`open_gaps`. Nothing here is judgment — see `references/script-schema.md`
for the exact field shapes.

### Stage 2 — scripting (剪辑链, the ONLY judgment stage)

Edit `script.json` directly:

- **keep/drop/collapse**: flip a step's `decision`. Default decisions from
  flow.json already collapse exact duplicates (`dup_of` set → `drop`); apply
  judgment on top — keep a context-fetch read only if it truly produces a
  downstream id, drop a producer whose value the consumer doesn't really need.
  **A capture may be a partial flow** — generate only what the traffic
  supports, never invent a step to "complete" some imagined full flow.
- **bulk_extract_candidates**: for any genuinely needed, hand-add an entry
  to that step's `bindings.extracts` (e.g. `{"var": "confirm_list",
  "expression": "$.response_body.data", "scope": "scenario"}`). Don't
  auto-wire all of them — most are noise.
- **resolve every open_gap** via the dedicated tool (never by hand):

  ```bash
  python scripts/script_gap_resolve.py script.json --list
  python scripts/script_gap_resolve.py script.json \
      --gap-index 0 --var order_id --candidate-index 0 \
      --request-body '{"bl_no": "GIMBAL_TEST_35"}'
  ```

  This inserts a synthetic context-fetch step, wires its extract, adds the
  matching assign on the consumer, and marks the gap resolved — all
  atomically, because forgetting any one of those four edits is this
  pipeline's single most common historical bug class. **Use a real literal
  test value in `--request-body`, never `${var.x}` templating** — see why in
  `references/script-schema.md`. **Pick a variable name that doesn't collide
  with an existing lineage var** — `script_lint.py` will catch a collision,
  but a clear distinct name (`order_id_sub`, not `order_id`) avoids rework.

### Stage 3 — `script_lint.py` (剪辑层终检)

```bash
python scripts/script_lint.py script.json
```

Checks both directions, looking ONLY at `script.json` (no opinion about
config/resource/templating — that's out of scope for this layer):

- **该做的做了**: no open gaps remain; every extract is actually consumed by
  a downstream assign; every assign has an earlier producing extract; no
  var is extracted twice without a distinct name; steps run
  producer-before-consumer.
- **不该做的没做**: no `${...}` templating has leaked into any step's
  `request_body`/`headers` (that would mean the scope boundary already
  failed); no field already classified `ignored_external` got rescued into
  internal wiring.

Exit code 0 = clean. Fix every violation before assembling.

### Stage 4 — `script_assemble.py` (发版链, mechanical, the only templating stage)

```bash
python scripts/script_assemble.py script.json --scaffold <scaffold>.json \
    --value-blacklist references/common-values-blacklist.json \
    --auth-user <user> --out scenario.json
```

Read-only on everything the cutting chain decided (step order, wiring,
which steps survive); write-only on values:

- runs its **own** value-match pass against the scaffold (the same rule as
  stage 0, applied independently — the two chains never share a value→name
  mapping, only the same matching logic) and replaces every matching literal
  with `${var.<name>}` / a resource reference,
- **unconditionally** overwrites every step's `Authorization` header to
  `${auth.<user>.token}` regardless of its captured or placeholder value —
  auth injection is name-matched on the header key, never value-matched,
  and applies identically to real and synthetic steps,
- strips browser/transport noise headers,
- builds each step's `strategy` array (status assertion + extract/assign
  from `bindings`),
- embeds the finished `steps` into the scaffold's `kind/scenarioId/meta/
  config/resource` shell.

Synthetic steps (inserted by `script_gap_resolve.py`) have no backing
capture record by design; the script emits a `*.synthetic_steps.json`
sidecar listing their final positions.

### Final lint — `validate_scenario.py`

```bash
python scripts/validate_scenario.py scenario.json --capture <capture>.ndjson \
    --skip-extract-verify-positions $(python -c "import json;print(','.join(map(str,json.load(open('scenario.synthetic_steps.json'))['synthetic_step_positions'])))")
```

Checks the fully assembled scenario: static/dynamic split, single-write rule,
dangling assigns, header hygiene, auth templating, and (for non-synthetic
steps) that every extract path actually resolves against the real capture.
Exit code 0 = pass.

**Output ONLY the scenario JSON object** when returning to the user — no
Markdown fences, no prose — so it can be fed straight into GIMBAL's loader.
If the person explicitly wants to review the reasoning first, print the
`flow.md`/lint summary before the JSON, separated by a line `===SCENARIO===`.

## Reference files

- `references/script-schema.md` — full field contract for `script.json`,
  shared by `script_init.py`/`script_gap_resolve.py`/`script_lint.py`/
  `script_assemble.py`. Read it before scripting.
- `references/scenario-schema.md` — final `scenario.json` field shapes
  (strategy kinds, templating conventions, two-namespace static/dynamic
  rule). Read it before assembling/reviewing output.
- `references/noise-keys.json` — field-name exclusion list (key-based, value
  doesn't matter). Extend it when a new transport/audit field shows up.
- `references/common-values-blacklist.json` — value-match exclusion list
  (used by both `analyze_flow.py` and `script_assemble.py`, independently).
  Extend it when a short/common value starts over-matching.
- `references/lookup-catalog.md` / `references/lookup_catalog.json` — id
  resolution catalog ("to get id X, query endpoint Y, extract at path Z"),
  consulted for gap candidates. Regenerate/extend with
  `scripts/build_lookup_catalog.py` as the API surface grows.

## Scripts

- `scripts/analyze_flow.py` — Stage 0, mechanical capture analysis.
- `scripts/script_init.py` — Stage 1, mechanical fold into script.json.
- `scripts/script_gap_resolve.py` — Stage 2 tool, atomic gap resolution.
- `scripts/script_lint.py` — Stage 3, 剪辑层终检.
- `scripts/script_assemble.py` — Stage 4, 发版链, mechanical assembly.
- `scripts/validate_scenario.py` — final lint on the assembled scenario.
- `scripts/build_lookup_catalog.py` — regenerate/extend the lookup catalog.
