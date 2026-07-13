---
name: gimbal-query-field-verify
description: >-
  Given ONE list/search endpoint, produce ONLY the `steps[]` array of a
  GIMBAL scenario in the user's step-shape (kind:"step" + api + request.body +
  strategy[assertion,extract]). The remaining scenario fields
  (kind/scenarioId/meta/config/resource) come entirely from a user-supplied
  scenario scaffold — this skill reads but never writes the scaffold. Use
  whenever the user wants to verify "every queryable field on this list endpoint
  actually filters", turn HTML form fields + traffic samples into per-field
  steps with the count-shrinks / anchor / first-page-row / negative assertion
  set, or generate a `steps.json` file that slots cleanly into an existing
  scenario via `jq . + {steps: …}`, or mentions 查询字段校验, ajaxGetList,
  "我有一份 scenario.json 但要往里灌查询用例", or query-field coverage on a
  list endpoint.
---

# GIMBAL: Query Field Verification (查询字段校验)

Turn one list/search endpoint's query surface into a **steps-only** GIMBAL
artifact that proves every queryable field actually filters. The skill's
**only** job is to produce the `steps` array; everything around it
(`kind` / `scenarioId` / `meta` / `config` / `resource`) is owned by
the user's scenario.json and is never touched.

## Hard contract with the user's scenario

| Concern | Owned by | Notes |
|---|---|---|
| `kind`, `scenarioId`, `meta.*` | **user's scenario.json** | the skill never reads or writes them |
| `config.{setup,teardown,services,users,vars,timePolicy,retry}` | **user's scenario.json** | the skill reads `config.services` (1 key) and `config.users` (1 key) only to resolve `service` name + token-tpl hint, never to copy |
| `resource` | **user's scenario.json** | the skill does not read it |
| `steps[].api.{method,path,headers,timeout}` | **inherited from user's `steps[0].api`** | deep-copied untouched per emitted step |
| `steps[].api.service` | skill writes | resolved from `--service-name` or first `config.services` key |
| `steps[].request.body` baseline defaults | **skill writes**, preserves every key from baseline URL | non-empty defaults (e.g. `order_terminated_shutout_status=1`) and empty-but-present defaults (e.g. `search_company=""`) both kept |
| `steps[].strategy[]` | **skill writes** | ① HTTP 200 + ② count_shrinks + ③ anchor_present + ④ first-page rows_match + (optional ⑤ negative_count==0) + extract `response_body` |
| `steps.json` top-level | skill emits `{"steps":[...]}` only | caller splices via `jq -s '.[0] + {steps: (.[0].steps + .[1].steps)}'` |

## Inputs

| Input | Provided as | Purpose |
|---|---|---|
| **form HTML** | `form.html` (DevTools "save as") | `<select>` options → ENUM value maps; `display:none` containers → HIDDEN |
| **baseline URL + baseline response** | URL string + captured JSON body | baseline body keys + non-empty defaults + baseline_count + auth surface |
| **auth/keys/names baseline response** | `{auth:{c1:{...}}, keys:[...], names:[...]}` | NO_AUTH classification + Chinese name recovery |
| **name-overrides.json** | `references/name-overrides.json` (long-lived data asset) | param→response_field mismatch fixes; edit, do NOT re-derive |
| **user's scenario.json (scaffold)** | a complete GIMBAL scenario with `steps:[]`, everything else filled | template source + final-shell target; the skill reads only `steps[0].api` and `config.services/users` |

## Scaffold seeding contract

The scaffold **must** carry exactly one seed step with `enabled: false`
(or no `strategy[]` at all), so that:

1. `steps[0].api` exists for `build_scenario.py` to read the api
   template — but the engine skips it at run time (no HTTP fired, no
   assertion evaluated).
2. The seed step does **not** introduce a duplicate `extract response_body`
   into the merged scenario. If the seed's `strategy[]` already
   contains an extract with `name == "extract_response_body"`, the
   skill suppresses its own emit; otherwise it adds one per emitted
   step.

Why: the seed step is purely a template carrier. If it ran, the
baseline URL would be hit as a real HTTP call (often returning a 404
when the user supplied a placeholder path), and the first ① assertion
would abort the entire scenario before any of the 19 emitted steps
get a chance to run. Worse, if both the seed and the emitted steps
each carry an `extract_response_body`, the same response is hoisted
into `vars.response_body` twice per step — a noisy duplicate.

**Authoring the seed step** (the `scs_seed.json` shape used internally):

```jsonc
"steps": [
  {
    "kind": "step",
    "description": "<endpoint> baseline (seed; inert)",
    "enabled": false,                                // ← skip at run time
    "api": { "method": "GET", "path": "...", "headers": {...}, "timeout": 30 },
    "request": { "kind": "request", "body": { /* baseline defaults */ } },
    "strategy": []                                   // ← empty; no extract
  }
]
```

The user's real `scenario.json` (not the seed copy) does NOT need to
follow this template — but if it does carry one inert step with the
right `api`, `build_scenario.py` can be run without a separate seed.

## Workflow

```
form.html + baseline URL + baseline response + auth JSON
                + scaffold + name-overrides.json
                           │
                           ▼
   Stage 1 — parse_form.py            → mapping.json + mapping.md
       │
       ▼
   Stage 2 — sample_fields.py         → samples.json + samples.md
       │
       ▼
   Stage 3 — build_scenario.py        → cases.json + steps.json + coverage.md
       │                                (steps-only; scaffold untouched)
       ▼
   jq -s '.[0] + {steps: (.[0].steps + .[1].steps)}' \
       <scaffold.json> <steps.json> > scenario.json
       │
       ▼
   python -m gimbal run launch scenario.json
```

### Stage 1 — `parse_form.py` (分类)

```bash
python scripts/parse_form.py \
    --html form.html \
    --url  "<baseline URL>" \
    --auth-json baseline_auth_keys.json \
    --overrides references/name-overrides.json \
    --out mapping.json --md mapping.md
```

Each request param pulled from the baseline URL is classified into exactly
one bucket, in this order:

| Status | Rule | Effect |
|---|---|---|
| `EXCLUDED` | in `references/excluded-params.json` (currently `page`, `size`, `order_ids`, `bulk_query_type`, `bulk_shutout_status`, `bulk_query`, `batch_exchange_query`) | excluded from TESTABLE analysis |
| `DATE_RANGE` | request-side `search_time[<name>]` form-key on URL | pre-mapped; granularity `date`/`datetime` from overrides (default `date`) |
| `HIDDEN` | `display:none` `<div id=...>` in form markup | not currently queryable |
| `NO_AUTH` | gating role flag false / missing in auth JSON | "no cases in this env", reported |
| `ENUM` | `<select>` with options captured | value_map stored |
| `FUZZY` | in `references/builtin-fuzzy.json` OR overrides provide `response_fields` | placeholder says "模糊搜索覆盖多个字段" |
| `EXACT` | plain text/number input; `param == response_field` | per-param equal match |
| `UNMAPPED` | none of the above could resolve a `response_field` | **must** be fixed by editing `name-overrides.json` and re-running |

UNMAPPED must be 0 before Stage 2. See `references/mapping-schema.md`
for the full `mapping.json` schema and assertion rules; see
`references/name-overrides.json` for the long-lived overrides asset.

> **Encoding note (Windows)**: export `PYTHONIOENCODING=utf-8` and
> `PYTHONUTF8=1` before running any stage. Without these, Chinese fields
> in the captured response silently get U+FFFD replacement. See
> `references/mapping-schema.md` for details.

### Stage 2 — `sample_fields.py` (采样)

```bash
python scripts/sample_fields.py \
    --mapping mapping.json \
    --url "<baseline URL, re-fire with the seed cookie>" \
    --header "$(cat cookies.txt)" \
    --max-rows 100 --per-field 5 \
    --out samples.json --md samples.md
```

For every TESTABLE field, paginate ≤100 rows and collect up to 5 distinct
canonical samples. Per sample:

- `row_id` — row primary key (`id`), used as anchor for ③
- `order_id` — any `*_id`/`*_no`/`*_sn` field in the row, used as
  `--positive-anchors` follow-up
- `canon` — canonical form (numeric for amounts, ISO date for dates,
  label for ENUMs)
- `value` — raw display value; `query_code` — backend-encoded value

`samples.json` carries `baseline_count` (the seed-page count that ②'s
`<` compares against). Any TESTABLE field with `status != "SAMPLED"`
becomes a coverage gap and is reported in `coverage.md`.

### Stage 3 — `build_scenario.py` (装订 steps)

```bash
python scripts/build_scenario.py \
    --mapping mapping.json \
    --samples samples.json \
    --url "<baseline URL>" \
    --scaffold "<user's scenario.json with steps:[]>" \
    [--only param1,param2,...] \
    --out steps.json --cases cases.json --report-md coverage.md
```

Reads scaffold's `steps[0].api` template (method / path / headers /
timeout) and resolves `api.service` from `config.services`. Never
modifies the scaffold. Emits each (field × sample) → one step:

```jsonc
{
  "kind": "step",
  "description": "查询[<中文名>]=<display-value>",
  "api": { "kind": "api", "service": <resolved>,
           "method": <from scaffold>, "path": <from scaffold>,
           "headers": <deepcopy from scaffold>, "timeout": 30 },
  "request": { "kind": "request",
               "body": <all baseline keys + this-case override> },
  "strategy": [
    ① assert_http_status_eq_200    (abort)
    ② assert_count_shrinks         (count < or <= baseline_count)
    ③ assert_anchor_present        (anchor ∈ list[*].id)
    ④ assert_first_page_rows_match (canonicalized, page_size=5)
    (optional ⑤ assert_negative_count_zero)
    extract response_body          (after_request, scenario scope)
  ]
}
```

ENUM cardinality ≤3 → ② operator is `<=`, otherwise `<` (same rule as
v1; survives Stages 1→2→3 unchanged). DATE_RANGE pairs emit two `body`
entries (start, end) in order. Empty-but-present string defaults are
preserved. `--only` whitelist: any TESTABLE param not listed is
recorded as `EXCLUDED_BY_USER` in `coverage.md` and not emitted as a
step.

`--emit full` is a **legacy** mode: it deep-copies `kind/config/resource`
from the scaffold, splices `steps`, and writes a single scenario.json.
This exists so old callers can still get a complete file — the
preferred path is the caller-side `jq` one-liner in Stage 4.

### Stage 4 — splice (caller-side)

```bash
jq -s '.[0] + {steps: (.[0].steps + .[1].steps)}' \
   "<user scenario.json>" steps.json > scenario.json

python -m gimbal run launch scenario.json
```

Read-only on step structure / wiring / assertions; write-only on
splice-into-scaffold. `Authorization` / `Cookie` templating is the
scaffold's job (`config.users.<name>.token`); the skill inherits
whatever headers the scaffold already ships.

If you want extra wiring on top (e.g. a per-step `extract` for a
custom variable) — that's a hand-edit on `scenario.json` after the
`jq` splice, NOT a job for this skill.

## Cleanup

Stages 1–3 keep `mapping.json`, `samples.json`, `cases.json`,
`coverage.md`, `steps.json` next to the user's inputs. The user's
**scaffold**, `form.html`, baseline response, and `references/` files
are never touched. After Stage 4 you can delete `samples.json` /
`mapping.json` if you want a clean directory.

Two exceptions:
- **Any stage failed and you're stopping** — keep `mapping.json`,
  `samples.json`, `coverage.md` (they ARE the debugging state).
- **The user explicitly asked to keep intermediates** — skip the
  cleanup.

## Reference files

- `references/mapping-schema.md` — `mapping.json`/`samples.json`
  fields, status taxonomy, 4-assertion exact predicates, canonicalization
  examples. **This is the contract for Stages 1–2.**
- `references/step-schema.md` — `steps.json` schema (yhr shape). **This
  is the contract for Stages 3–4.**
- `references/name-overrides.json` — long-lived data asset; sticky per-
  endpoint param→response_field mismatches. Edit, never re-derive.
- `references/canonicalization.md` — what `samples[].canon` vs
  `samples[].value` mean, and per-category canonical-form rules. Short.
- `references/excluded-params.json` — index of the current `EXCLUDED`
  param set. **Note**: `scripts/parse_form.py` keeps its own hardcoded
  copy of this list; edits to the JSON alone don't take effect until
  the corresponding constant in the script is updated.
- `references/builtin-fuzzy.json` — index of the current `BUILTIN_FUZZY`
  map. **Note**: same dual-source caveat as `excluded-params.json`.

## Scripts

- `scripts/parse_form.py` — Stage 1, mechanical form↔URL classification.
- `scripts/sample_fields.py` — Stage 2, mechanical canonical-sample
  collection per TESTABLE field.
- `scripts/build_scenario.py` — Stage 3, mechanical fold into
  `cases.json` + `steps.json` + `coverage.md`.

The Stage 4 splice is a one-liner `jq` and is not a script in this
skill — by design: it writes back into the user's own scaffold file
and is therefore out of skill scope.

## Output contract

The skill produces `steps.json` containing `{"steps": [...]}` and
nothing else. Return format to the calling model:

```jsonc
{ "steps": [ <step>, <step>, … ] }
```

When the user asks for a debug-rich reply, also surface `cases.json`
(durable) and `coverage.md` (report scaffold; the table's PASS/FAIL
columns stay empty for the user to fill in after `gimbal run launch`).
