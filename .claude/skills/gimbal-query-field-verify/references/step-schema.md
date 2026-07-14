# Step Schema — yhr Shape

Defines the exact field shape every step in [steps.json](steps.json)
satisfies. The reference example is
[gimbal-tmp/Scenario_Test_yhrtest.json](../../../../gimbal-tmp/Scenario_Test_yhrtest.json).

## Top of `steps.json`

```jsonc
{
  "steps": [
    { <step>, <step>, … }
  ]
}
```

That's the entire content. `kind / scenarioId / meta / config /
resource` never appear in this file — they belong to the user's
scaffold and are spliced back via `jq -s '.[0] + {steps: …}'`.

## How `steps[0].api` flows from the scaffold

The skill reads `scaffold.steps[0].api` exactly **once** and
deep-copies it into every emitted step's `api` (only `service` is
overwritten). Whatever `headers` the scaffold ships is what every
emitted step gets — typically `Cookie: ${auth.<user>.token}` and
`Content-Type: application/x-www-form-urlencoded`. The skill never
constructs or rewrites a header.

| Field on `api`        | Source                                               |
|-----------------------|------------------------------------------------------|
| `kind`                | `setdefault("api")` if scaffold didn't set it        |
| `service`             | `--service-name` or `scaffold.config.services` first |
| `method`              | inherited from scaffold                              |
| `path`                | inherited from scaffold                              |
| `headers`             | inherited (deepcopy) from scaffold                   |
| `timeout`             | inherited or 30 default                              |

## How `request.body` is built

Every emitted step's body is the **full baseline URL query**, with this
case's target param(s) overridden using the canonical query code.

- Non-empty defaults (e.g. `order_terminated_shutout_status: 1`) are
  preserved across every emitted step.
- Empty-but-present strings (e.g. `search_company: ""`) are preserved —
  the PHP/ThinkPHP backend treats missing as inheriting the previous
  filter, so a fully-blank form must explicitly send `""` for every
  field-level param.
- DATE_RANGE param pairs emit as two `body` entries in `start, end`
  order (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS` granularity).
- The current override exists in `case.query_override` (built by
  `build_query_override`); the body-assembly helper
  `body_for_case` does the merge. `--only` does **not** alter the body
  template — it just excludes fields from emission.

## Step

```jsonc
{
  "kind": "step",
  "description": "查询[<中文名>]=<display-value>",
  "api": { …see table above… },
  "request": {
    "kind": "request",
    "body": { …full baseline + override… }
  },
  "strategy": [
    ① <assertion_http_status_eq_200>,
    ② <assertion_count_shrinks>,
    ③ <assertion_anchor_present>,
    ④ <assertion_first_page_rows_match>,
    (optional ⑤ <assertion_negative_count_zero>),
    <extract_response_body>
  ]
}
```

## Strategy kinds

All share: `kind`, `name`, `phase`, `order`, `enabled`, `onFailure`,
usually `scope` (for `extract`).

### ① assertion — HTTP 200

```jsonc
{
  "kind": "assertion",
  "name": "assert_http_status_eq_200",
  "phase": "verifying", "order": 0, "enabled": true, "onFailure": "abort",
  "target": "$.response_status", "operator": "eq", "expected": 200,
  "message": "查询[<中文名>]=<display-value> 应返回200",
  "soft": false
}
```

Every step gets this. `onFailure: "abort"` is required — without it,
②/③ silently pass the "empty list" state which is the canonical
backend-error smell.

### ② assertion — count shrinks

```jsonc
{
  "kind": "assertion",
  "name": "assert_count_shrinks",
  "phase": "verifying", "order": 1, "enabled": true, "onFailure": "abort",
  "target": "$.response_body.count",
  "operator": "lt",                 // "lte" if ENUM cardinality <= 3
  "expected": <baseline_count>,
  "message": "①count_shrinks: 相等意味着过滤参数被后端忽略",
  "soft": false
}
```

Engine enum names are `lt` / `lte` (NOT the literal `<` / `<=`); the
pydantic `AssertOperator` enum rejects the raw symbols with
`type=enum, input_value='<'`. ENUM cardinality relaxation:
`len(value_map) <= 3` → `lte`, otherwise `lt`.

### ③ assertion — anchor present

```jsonc
{
  "kind": "assertion",
  "name": "assert_anchor_present",
  "phase": "verifying", "order": 2, "enabled": true, "onFailure": "abort",
  "target": "$.response_body.list[*].id",
  "operator": "contains",
  "expected": "<anchor_row_id>",
  "message": "②anchor_present: 已知记录必须可查到",
  "soft": false
}
```

The row used at Stage 2 to learn the field value must be in
`response_body.list[*].id` of the filtered response.

### ④ assertion — first-page rows match

The skill emits **one `contains` assertion per `response_field`**,
each at order `3 + idx`, against `list[*].<field>` with the canonical
value as `expected`. This is the engine-supported fallback for the
originally-planned `row_match` operator — `AssertOperator.SCHEMA` has
no `_evaluate()` handler in `strategy/builtin/utils.py` and falls into
the `Unknown operator` branch, so a custom operator can't be added
from this skill side.

```jsonc
{
  "kind": "assertion",
  "name": "assert_field_<f>_contains_canon",
  "phase": "verifying", "order": 3, "enabled": true, "onFailure": "abort",
  "target": "$.response_body.list[*].<f>",
  "operator": "contains",
  "expected": "<canon-value>",
  "message": "③rows_match: 首页 list[*].<f> 应包含 <display-value>",
  "soft": false
}
```

For `response_fields = ["order_no","bl_no"]` (FUZZY case) the skill
emits two assertions — order 3 (`list[*].order_no`) and order 4
(`list[*].bl_no`) — each `contains` against its respective field.
For single-field (most ENUMs / DATE_RANGE) there is exactly one
assertion at order 3.

The combined effect approximates "every row in the first page has
`field == canon`": if a single non-matching row slips in, the
contains assertion still passes (only needs the value to appear at
least once) — so ④ is a *necessary but not sufficient* filter check,
not a per-row exactness proof. Tightening this to per-row equality
requires an engine-side comparator, which is out of skill scope.

### ⑤ assertion — negative count zero (optional)

```jsonc
{
  "kind": "assertion",
  "name": "assert_negative_count_zero",
  "phase": "verifying", "order": 4, "enabled": true, "onFailure": "abort",
  "target": "$.response_body.count",
  "operator": "eq", "expected": 0,
  "message": "④negative: 不存在的值应返回 0 条",
  "soft": false
}
```

Only emitted for non-ENUM categories. ENUM has a closed domain, so
this would just become another ENUM case.

### extract — response body

```jsonc
{
  "kind": "extract",
  "name": "extract_response_body",
  "phase": "after_request", "order": 0, "enabled": true, "onFailure": "abort",
  "expression": "$.response_body",
  "target": "response_body",
  "required": true, "default": null, "scope": "scenario"
}
```

`scope: "scenario"` is correct here: every step's body lands in
scenario context so ②/③ can resolve `$.response_body.count` and
`$.response_body.list[*].id`. **A single emit per step is enough**;
do not hand-add a second `extract_response_body` to a step emitted
by this skill.

**Dedupe rule (engine-side)**: the skill detects whether the scaffold
seed step (or any other step the user shipped) already carries a
strategy with `kind == "extract"` and `target == "response_body"`.
If so, the skill's own emit is suppressed — the same `vars.response_body`
slot would otherwise be overwritten twice per step (once by the
seed-inherited extract, once by the emitted one), creating a noisy
duplicate that costs an extra round-trip in the `extract_response_body`
plugin without changing the asserted values.

The detection key is `target == "response_body"` (not the strategy
`name`), so the dedupe survives renaming of the user's existing
extract.

## Failure-triage hierarchy

When a step fails, look at the assertion order to triage:

| Failed | Likely cause | Action |
|---|---|---|
| ① | backend error or auth failure | check captured body, do not retry |
| ② count == baseline_count | **filter param ignored by backend** (the canonical "input wired but server drops it" bug) | report as the highest-value finding |
| ③ anchor not in list | data drift (anchor order moved/died) or filter too aggressive | inspect anchor |
| ④ rows don't match | mapping-table bug (value→code) or semantic-filter mismatch | suspect mapping first |

## What this skill does NOT emit

- `${var.x}` / `${auth.x.token}` template substitution inside steps —
  literals only; templating belongs to the scaffold.
- Asset / context-passing wiring (`extract.target` other than
  `response_body`); that's hand-added on `scenario.json` after the
  Stage-4 `jq` splice.
- Token / header sanitization — those come from the scaffold's
  `config.users.<name>.token` and the scaffold's `steps[0].api.headers`.
