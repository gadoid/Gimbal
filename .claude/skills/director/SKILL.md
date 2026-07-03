---
name: director
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

### Platform & encoding (READ FIRST)

The pipeline is **encoding-fragile on Windows**. Python 3.14's default
`sys.stdout.encoding` is GBK, and the lint/assemble scripts `print()`
Unicode characters (em dash `——`, ellipsis `…`, etc.) that GBK cannot
represent. When that happens mid-run, the I/O error handler
**silently replaces characters already loaded into memory** (the
parsed request bodies) with U+FFFD (`\ufffd`). The contaminated
strings then land in `scenario.json` via `json.dump(ensure_ascii=False)`
— the final file looks like mojibake in every Chinese field even
though every stage reported `[OK]`. The `UnicodeDecodeError: ... byte
0xa1` you may see in stderr is a *symptom* of this; the contamination
that just happened is the real problem.

**Always export these in your shell BEFORE running any stage**:

```bash
# bash / WSL / macOS / Linux
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
```

```bat
:: Windows cmd
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
```

```powershell
# Windows PowerShell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

All `python scripts/...` commands in Stages 0–4 and Final lint
inherit these. The scripts themselves open files with
`encoding="utf-8"` correctly, so this single env var is enough.

**Verify before continuing.** If the first stage's stdout shows
`UnicodeDecodeError: ... byte 0xa1` or you see U+FFFD replacement
characters (rendered as `?` or empty boxes) where a Chinese field
should be, the env vars did not take effect — **stop and re-export**,
do not proceed (a contaminated `scenario.json` will be produced and
you will not notice the issue until you re-read the file later). On
Linux/macOS the env vars are no-ops and the commands run unchanged.

**Working directory convention (cleanup contract):** every intermediate this
pipeline produces — `flow.json`, `flow.md`, `script.json`, and the assemble
sidecars (`*.capture_map.json`, `*.synthetic_steps.json`) — goes into a
dedicated work directory `_director_work/` next to where you run, NOT
alongside the user's inputs or the final output. The commands below already
reflect this. After the final lint passes and the scenario has been delivered,
**delete `_director_work/` entirely** (see the Cleanup step after Final lint).
The user's inputs (capture ndjson, scaffold) and the reference files are never
touched; the only file that survives the run is the final `scenario.json`.
If any stage FAILS and you stop, leave the work dir in place — the
intermediates are exactly what's needed to debug — and tell the user it was
kept and where.

### Stage 0 — `analyze_flow.py` (剪辑链, always run first)

> **Encoding note**: `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` must
> be exported in this shell before the next command (see
> "Platform & encoding" above). If you forgot, fix and re-run.

```bash
mkdir -p _director_work
python scripts/analyze_flow.py <capture>.ndjson \
    --scaffold <scaffold>.json \
    --catalog references/lookup_catalog.json \
    --noise-keys references/noise-keys.json \
    --value-blacklist references/common-values-blacklist.json \
    --out _director_work/flow.json --md _director_work/flow.md
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

**How dedup and lineage resolution actually work (read before trusting a
`dup_of`):**

- A value's *producer* is resolved to the NEAREST PRECEDING response that
  contains it, not the first time it ever appeared in the capture. A
  re-queried list/detail endpoint that happens to return the same literal id
  twice (e.g. an audit array whose element-0 semantics drift after a mutation)
  still gets its own producer edge for whatever consumes it afterward — it is
  never silently re-wired back to an unrelated earlier occurrence.
- A `KEEP` record is only ever flagged `dup_of` another if (a) it's not
  wired to any dynamic lineage var (a mutation that consumes an extract/assign
  is exempt from dedup entirely — its literal body only LOOKS identical in the
  capture; at replay the assign injects a different value each occurrence,
  e.g. the double-audit case, `audit_ids[0]` = `audit_id` vs `audit_id_2`), and
  (b) no OTHER mutation ran between the two occurrences (a GET repeated right
  after a POST that changed the very resource it reads is a legitimate
  re-check, not noise). A mutation with NO dynamic wiring and a truly identical
  literal body — e.g. an accidental UI double-click captured in the session —
  still gets flagged `dup_of`, which is the correct signal to catch it. Only
  successful mutations on the business host count as boundary events; a failed
  (HTTP ≥400) or business-error mutation didn't actually change state, so it
  never protects two otherwise-identical calls from being flagged duplicates.
- HTTP-failed records (status ≥ 400) are dropped outright and excluded from
  lineage entirely — they never anchor an extract. A 200 whose JSON envelope
  looks like a business-level failure (`code` present and not 0/200) is kept
  but flagged in `business_code_warnings` for a quick manual look.
- Endpoint verbs are classified three ways: read (READ_SUFFIX tail), mutation
  (MUTATION_VERBS match), or UNKNOWN — and an unknown verb is treated as a
  possible mutation, never silently degraded to a droppable read. The failure
  asymmetry drives this: wrongly keeping a read costs one redundant replay
  request; wrongly dropping a mutation amputates the business flow (the
  historical case: a 3-stage `assetPush` endpoint — action=check/audit/submit,
  empty responses, no new ids — whose verb wasn't in the list, so all three
  state-changing calls were classified "pure read, no downstream dependency"
  and dropped). Unknowns are kept with a `[WARN] unrecognized verb` reason and
  collected in `unclassified_verbs` (flow.json + a flow.md section) — when one
  shows up, classify it properly by extending MUTATION_VERBS or READ_SUFFIX in
  `analyze_flow.py` and re-run, rather than hand-flipping decisions each time.
- Every lineage `extract` expression that indexes into a response array is
  checked for replay fragility and reported in `positional_extract_risks`
  (array length, matched position, sibling discriminator fields). `risk:
  "high"` (array len > 1 or position > 0) is exactly the shape that breaks
  when the array's order/content differs at replay time — review these before
  trusting `[0]`-style extracts, especially on any endpoint queried more than
  once in the flow (audit lists are the canonical case).
- A value produced at multiple points is either CANONICALIZED to one shared
  var (a stable whole-flow entity like `order_id`, queried from many
  different endpoints or re-queried idempotently — merged onto its single
  best producer, reported in `canonicalized_values`) or left as separate
  per-occurrence vars and flagged in `value_reuse_suspects` (the SAME
  endpoint re-queried with a mutation in between still returning the SAME
  value — looks like an entity that should have changed but didn't, e.g. a
  stale `audit_id`). The gate is deliberately conservative: only a value
  colliding through an array-indexed path after a same-endpoint mutation is
  treated as suspect; everything else merges. This is what turns 18 separate
  `order_id_1..order_id_18` extracts (some from fragile positional paths)
  into one `order_id`, matching how a human would script it by hand, while
  still refusing to silently merge a stale-id bug shape.
- "id-shaped" (what makes a value a lineage/gap candidate at all) covers
  snowflake ids, order-no-like tokens, and any `_id`/`_no`/`_sn`-named field
  whose value is alnum plus `_`/`-` (so business codes like `bl_no =
  "GIMBAL_TEST_35"` are visible). Canonical UUIDs (`8-4-4-4-12` hex) are
  explicitly excluded even when the field name matches — a UUID is the
  standard shape of a CLIENT-generated correlation id (a form-row key, an
  idempotency key) that no backend query endpoint will ever return; treating
  it as id-shaped would turn it into a permanently unresolvable `open_gap`.
  It stays literal, untouched, exactly as captured.

### Stage 1 — `script_init.py` (剪辑链, mechanical fold)

> **Encoding note**: `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` must
> be exported in this shell (see "Platform & encoding" above).

```bash
python scripts/script_init.py _director_work/flow.json --capture <capture>.ndjson \
    --scaffold <scaffold>.json --out _director_work/script.json
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

  > **Encoding note**: `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` must
  > be exported in this shell (see "Platform & encoding" above).

  ```bash
  python scripts/script_gap_resolve.py _director_work/script.json --list
  python scripts/script_gap_resolve.py _director_work/script.json \
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

> **Encoding note**: `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` must
> be exported in this shell (see "Platform & encoding" above).

```bash
python scripts/script_lint.py _director_work/script.json
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
- **advisory**: any surviving `positional_extract_risks` entry marked `high`
  whose producer step is still kept with that same extract expression gets a
  warning (not a violation) — a nudge to confirm the array index is actually
  stable before trusting it through to assemble.

Exit code 0 = clean. Fix every violation before assembling.

### Stage 4 — `script_assemble.py` (发版链, mechanical, the only templating stage)

> **Encoding note**: `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` must
> be exported in this shell (see "Platform & encoding" above).

```bash
python scripts/script_assemble.py _director_work/script.json --scaffold <scaffold>.json \
    --value-blacklist references/common-values-blacklist.json \
    --auth-user <user> --out _director_work/scenario.json
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
sidecar listing their final positions. It also always emits a
`*.capture_map.json` sidecar (final step position → source capture line
index, `null` for synthetic steps) — pass this to `validate_scenario.py
--capture-map` for exact response matching instead of the legacy per-path
occurrence-counting fallback, which mismatches as soon as a repeated path's
kept-vs-dropped occurrences don't line up 1:1 with capture order (e.g. the
first of two identical-looking calls got dropped, the second kept).

### Final lint — `validate_scenario.py`

> **Encoding note**: `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` must
> be exported in this shell (see "Platform & encoding" above).

```bash
python scripts/validate_scenario.py _director_work/scenario.json --capture <capture>.ndjson \
    --capture-map _director_work/scenario.capture_map.json \
    --skip-extract-verify-positions $(python -c "import json;print(','.join(map(str,json.load(open('_director_work/scenario.synthetic_steps.json'))['synthetic_step_positions'])))")
```

Checks the fully assembled scenario: static/dynamic split, single-write rule,
dangling assigns, header hygiene, auth templating, and (for non-synthetic
steps) that every extract path actually resolves against the real capture.
Exit code 0 = pass. The `--skip-extract-verify-positions` argument is only
needed when a `scenario.synthetic_steps.json` sidecar exists (i.e. gaps were
resolved); omit it otherwise.

### Cleanup — mandatory last step (only after the final lint passes)

Deliver the final scenario out of the work dir, then remove ALL
intermediates:

```bash
mv _director_work/scenario.json ./scenario.json
rm -rf _director_work
```

What this removes: `flow.json`, `flow.md`, `script.json`, and the assemble
sidecars (`scenario.capture_map.json`, `scenario.synthetic_steps.json`) —
everything the pipeline created for its own use. The sidecars have done
their one job (feeding the final lint) by this point; they carry no runtime
meaning for GIMBAL's loader. What this must NEVER remove: the user's capture
ndjson, the scaffold, anything under `references/`, or the delivered
`scenario.json`.

Two exceptions to cleaning up:
- **Any stage failed and you're stopping** — keep `_director_work/` (it IS
  the debugging state) and tell the user it was left in place and why.
- **The user explicitly asked to keep intermediates** (e.g. wants to inspect
  `flow.md` or audit `script.json`) — skip the `rm`, say where things are.

**Output ONLY the scenario JSON object** when returning to the user — no
Markdown fences, no prose — so it can be fed straight into GIMBAL's loader.
If the person explicitly wants to review the reasoning first, print the
`flow.md`/lint summary before the JSON, separated by a line `===SCENARIO===`
(read `flow.md` BEFORE the cleanup step deletes it, or fold cleanup after
the printout).

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
