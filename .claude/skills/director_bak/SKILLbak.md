---
name: director
description: >-
  Direct a real captured business flow into a schema-valid, data-driven GIMBAL
  test scenario. Takes Prism/mitmproxy ndjson traffic (each line
  {ts, method, host, path, headers, body, response}) plus a golden e2e.json and
  produces an ordered, denoised, context-wired scenario that replays end-to-end.
  Use this whenever the user wants to turn a real business flow / traffic capture
  / ndjson / FlowSession dump into a GIMBAL scenario or test case, "distill" or
  "denoise" captured requests into an ordered API chain, generate extract/assign
  context-passing between steps, or mentions GIMBAL scenario generation, the
  Director skill, 流量转用例, 抓包生成测试, ndjson 蒸馏, or 顺序接口数据驱动用例.
  Trigger even if they only provide the ndjson and a reference scenario without
  saying "skill" or "Director".
---

# Director

Direct a real captured business flow into ONE GIMBAL scenario: an ordered chain
of API calls, denoised and sanitized, wired together with `extract`/`assign` so
it replays end-to-end.

The work runs as a film cut: raw footage (the capture) becomes a **script**
(an explicit, auditable intermediate object) before it becomes the final cut
(the scenario). The script is the heart of this skill — it turns every judgment
into data, so the mechanical stages need no further judgment and every decision
stays auditable.

You are given two inputs:
- **the capture** — a `*.ndjson` (one JSON record per line). Bodies in `body`
  and `response.body` are JSON *strings* that must be parsed.
- **the golden** — an `e2e.json` (or similar) GIMBAL scenario. Authoritative for
  **schema, field names, strategy semantics, and step granularity** — but NOT
  for step selection. Which steps survive and which ids flow between them are
  **derived from the capture**, not copied from the golden.

The hard, deterministic work — classifying hundreds of records and tracing which
response field feeds which later request — is done by the bundled scripts. Your
judgment is needed in exactly two places: **scripting** (which steps to keep) and
**gap-resolution** (how to supply ids the capture never produced). Everything
else is mechanical.

## The five stages

```
  capture.ndjson
       |  (1) initial cut      analyze_flow.py        -> flow.json   [mechanical]
       v
  flow.json
       |  (2) init             script_init.py         -> script.json [mechanical]
       |  (2) scripting        you edit script.json                  [JUDGMENT]
       |  (3) gap-resolution   you edit script.json (catalog)        [JUDGMENT]
       |      lint             script_lint.py                        [mechanical]
       v
  script.json  (all judgment now baked in as data)
       |  (4) assembly         script_assemble.py     -> scenario.json [mechanical]
       v
  scenario.json
       |  (5) screening        validate_scenario.py + your review    [mechanical+review]
       v
  final scenario
```

### (1) Initial cut — `analyze_flow.py`

```bash
python scripts/analyze_flow.py <capture>.ndjson \
    --business-host <host> \
    --catalog references/lookup_catalog.json \
    --out <capture>.flow.json --md <capture>.flow.md
```

Omit `--business-host` to auto-pick the most frequent host (everything else is
flagged cross-domain noise). `--catalog` pre-fills a lookup suggestion for any id
a request consumes that no earlier response produced. The script emits a
keep/drop classification, a path-frequency table, a **value-lineage graph**
(verified response->request id paths = your `extract`->`assign` candidates),
`missing_producers`, and `bulk_extract_candidates`. Read `flow.md` for the human
view. **This stage is purely mechanical — do not hand-edit `flow.json`.**

### (2) Init + scripting — build and curate the script

First fold the flow into a script skeleton (mechanical):

```bash
python scripts/script_init.py <capture>.flow.json \
    --capture <capture>.ndjson --golden <golden>.json \
    --out <capture>.script.json
```

`script_init.py` creates one step per record (KEEP->`kept`, DROP->`dropped`,
both retained for audit), seeds `bindings.extracts`/`assigns` from the verified
lineage, assigns a dense `order` over kept steps, and lifts `missing_producers`
into top-level `open_gaps` with catalog candidates. See
`references/script-schema.md` for the exact shape.

Then **apply judgment by editing `script.json` directly** (lenient mode — free
text reasons, no rigid codes):

- **Keep** every state-changing business call (mutation verbs).
- **Keep** a read/detail/list call ONLY as a `context_fetch` if it produces an
  id a later kept step consumes.
- **Drop** pure UI-population reads with no downstream dependency (enums,
  dictionaries, dropdown/user/customer lists, audit browsing) — flip the step's
  `status` to `dropped` with a `decision_reason`.
- **Collapse duplicates**: where init carried a `[dup_of N]` hint, set
  `status: "collapsed"` and `collapsed_into: N` on the pure repeat — but never
  collapse a step that produces a downstream-consumed id.
- The id heuristic can over-match (e.g. `code`, `file_id`, a query-only detail
  call). Drop a producer whose value is never genuinely needed downstream.

**A capture may be a partial flow.** It can stop early or omit steps the golden
contains. Generate only what the traffic supports — never invent a step or id to
"complete" the golden. Coverage gaps vs the golden are expected and correct when
the underlying request is simply absent.

### (3) Gap-resolution — supply ids the capture never produced

Each entry in `open_gaps` is an id consumed by a request that no earlier
response produced. Resolve **each one** by writing a `resolution` (see
`references/script-schema.md` for the three shapes), then set its `status`:

- **Run-constant input** (`bl_no`, a selected master-data id, a `*_time`/`*_date`)
  -> `{"kind": "static", "var": "<name>"}`. The value becomes a `config.var` and
  the consumer references `${var.<name>}`. Assembly handles the templating.
- **A business-process id that simply wasn't captured** (e.g. `order_id` because
  the listing call was skipped) -> you may **not** fall back to a var. Insert a
  context-fetch step from the **id resolution source** (currently
  `references/lookup-catalog.md`): pick a candidate endpoint whose outputs
  include the needed id and whose inputs you already hold, add it as a new step
  with a synthetic idx (> any real idx), give it `role: "context_fetch"`, an
  `extract` at the catalog path, and any `assigns` for its inputs; then record
  `{"kind": "lookup", "inserted_idx": <new idx>, "candidate_index": <i>}`.

> The id-resolution source is currently the local catalog. The decision logic
> here (candidate trustworthy -> insert step; none -> static or open) does not
> change if that source is later swapped for a Plate/EndpointSpec MCP query.

**Never** route a process-generated id (`order_id`, `audit_id`,
`receive_account_id`, ...) through a static var. Those must be produced by a kept
step or by an inserted lookup. This mirrors the two-namespace rule in
`references/scenario-schema.md`.

For `bulk_extract_candidates` (whole-list/object `data` responses the scalar
graph can't see), wire an `extract` of `$.response_body.data` ONLY when that data
is actually consumed downstream. Treat them as advisory; do not auto-wire all.

Then check structural completeness (mechanical):

```bash
python scripts/script_lint.py <capture>.script.json
```

It flags unresolved gaps, dangling assigns, double-written scenario vars, broken
collapse targets, and non-dense ordering. Fix every violation. Lint does **not**
judge whether your kept set is the right business flow — that is verified at
screening.

### (4) Assembly — `script_assemble.py`

```bash
python scripts/script_assemble.py <capture>.script.json --out <scenario>.json
```

Mechanical: walks kept steps in `order`, re-reads each raw request body by idx,
sanitizes headers (templates auth, strips browser noise), emits strategy blocks
from bindings (mandatory `assert_status_200` + extracts + assigns), seeds
`config.vars` from static gap resolutions and templates those values into the
bodies, and copies `meta`/`config`/`resource` from the golden (config fallback).
**No judgment here** — everything was decided in the script.

### (5) Screening — validate, then review

```bash
python scripts/validate_scenario.py <scenario>.json \
    --capture <capture>.ndjson --script <capture>.script.json
```

The linter enforces the static/dynamic split, no dangling assigns, extract paths
that resolve against real responses, templated auth, status assertions, **and**
(with `--script`) that every step the script committed to (`order` is non-null)
actually reached the scenario in the same order — this is what catches assembly
silently dropping a step (e.g. a `context_fetch` or an inserted lookup that
`script_assemble.py` failed to carry through). Fix every violation. Then do a
final **human/model review** the linter can't: does this ordered chain tell a
coherent business story end-to-end? Is each kept step there for a reason?
Reorder or re-curate the script and re-assemble if not.

**Output the final scenario JSON** — top-level shape identical to the golden
(`kind/scenarioId/meta/config/resource/steps`), valid JSON, ready for GIMBAL's
loader / Pydantic validation.

## Reference files

- `references/script-schema.md` — the `script.json` contract: step shape,
  bindings, gaps, the three resolution kinds, and exactly what `script_lint.py`
  checks. **Read this before editing any script.json.**
- `references/scenario-schema.md` — final scenario field shapes, the three
  strategy kinds, templating, header sanitization, config fallback, the
  static/dynamic two-namespace rule, variable naming. Read before reasoning about
  assembly output.
- `references/lookup-catalog.md` — id resolution source ("to get id X, query
  endpoint Y, extract at path Z"), mined from real traffic. Consult it during
  gap-resolution. `references/lookup_catalog.json` is the machine-readable form
  passed to `analyze_flow.py --catalog`.

## Scripts

- `scripts/analyze_flow.py` — (1) initial cut (run, don't reimplement).
- `scripts/script_init.py` — (2) fold flow.json into a script.json skeleton.
- `scripts/script_lint.py` — structural-completeness check on script.json.
- `scripts/script_assemble.py` — (4) assemble a resolved script into a scenario.
- `scripts/validate_scenario.py` — (5) lint the finished scenario: static/dynamic
  split, dangling assigns, extract-path resolution, auth templating, status
  assertions, and (with `--script`) step-sequence completeness against
  `script.json`'s committed order.
- `scripts/build_lookup_catalog.py` — extend the catalog from new captures:
  `python scripts/build_lookup_catalog.py NEW.ndjson --merge
  references/lookup_catalog.json --out references/lookup_catalog.json --md
  references/lookup-catalog.md`. Run as the API surface grows.