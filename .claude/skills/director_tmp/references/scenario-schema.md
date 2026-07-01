# GIMBAL Scenario Schema Reference

Load this when assembling the final scenario JSON. It defines the exact
field shapes; the golden `e2e.json` the user supplies is the authoritative
example — when in doubt, mirror it.

## Top-level

```jsonc
{
  "kind": "scenario",
  "scenarioId": "<string>",
  "meta": { ... },              // copy/adapt from golden
  "config": { ... },           // copy from golden unless traffic dictates
  "resource": {},              // copy from golden
  "steps": [ <step>, ... ]     // DERIVED from traffic
}
```

## Two variable namespaces (static vs dynamic) — CRITICAL, READ FIRST

GIMBAL resolves values in two distinct phases. Do not mix them. Misplacing
a single value (e.g. putting `order_id` in `config.vars` instead of wiring
it through `extract`/`assign`) is the single most common scenario bug.

1. **Static — `${var.x}` / `${auth.x.token}`**: substituted from `config.vars`
   / `config.users` **before the run starts**. Use ONLY for test inputs known
   ahead of time and constant for the whole run: `bl_no`, account/login,
   and master-data ids you merely *select* (customer/policy/supplier/carrier/
   country id). These never change as the flow executes.

2. **Dynamic — scenario context via `extract` → `assign`**: a value produced
   by one step's response (`extract` `target` = a context variable) and
   injected into a later request **at runtime** (`assign` `source: $.x` →
   `target: $.request_body...`). Use for every value the business process
   *generates or mutates* as it runs.

**Hard rule:** any id created/changed during the flow — `order_id`, `order_no`,
`order_sub_id`, `order_sub_no`, `order_fee_real_id`, `audit_id`,
`receive_account_id`, `finance_id`, `apply_id`, `batch_id`, … — is **dynamic**.
It MUST be wired through `extract`/`assign` and MUST NOT be placed in
`config.vars` or referenced as `${var.<that id>}`. A name that appears as an
`extract` target must never also be a `config.var`. Run
`scripts/validate_scenario.py` to enforce this mechanically.

Rule of thumb: if the value is the same on every run → `${var.x}`. If it is
born from a response during the run → `extract`/`assign`.

## Step

```jsonc
{
  "kind": "step",
  "api": {
    "kind": "api",
    "service": "<service name from config.services>",
    "method": "POST",
    "path": "/api/...",
    "headers": { "Authorization": "${auth.<user>.token}" },
    "timeout": 30
  },
  "request": {
    "kind": "request",
    "body": { ...parsed captured payload, sanitized & templated... }
  },
  "strategy": [ <assertion|extract|assign>, ... ]
}
```

Prefer `api.kind="api"` (explicit service/method/path). Use
`api.kind="api_ref"` with `{"ref": "<module>/<name>"}` only when a matching
ModelRegistry/EndpointSpec contract is known to exist.

## Strategy kinds

All three share: `kind`, `name`, `phase`, `order`, `enabled` (true),
`onFailure` ("abort"), and usually `scope` ("scenario").

### assertion — verify the response

```jsonc
{
  "kind": "assertion",
  "name": "assert_status_200",
  "phase": "verifying",
  "order": 0,
  "enabled": true,
  "onFailure": "abort",
  "target": "$.response_status",
  "operator": "eq",
  "expected": 200,
  "message": "<human message>",
  "soft": false
}
```

Every kept step gets at minimum this status assertion.

### extract — pull a value out of the response into a scenario variable

```jsonc
{
  "kind": "extract",
  "name": "extract_<var>",
  "phase": "after_request",
  "order": 0,
  "enabled": true,
  "onFailure": "abort",
  "expression": "$.response_body.data.<path>",  // MUST resolve in the real response
  "target": "<var>",                            // scenario variable name
  "required": true,
  "default": null,
  "scope": "scenario"
}
```

`$.response_body` is the parsed JSON body of the response
(i.e. the captured `response.body` string, json-decoded).

**`scope` — where the value lives:**
- `scenario` — written into shared scenario context; visible to every later
  step. Use for ids that downstream steps consume.
- `step` — transient, local to the current step; discarded afterward. Use when
  you only need the value to verify or transform *within this step*.

**Single-write rule (scenario scope):** a scenario-scope `target` may be
written **only once** in the whole scenario. Extracting again to the same name
overwrites the earlier value, so a later `assign` may read the wrong one. If the
same kind of value is captured at multiple points, either (a) use `scope: step`
for the transient one, or (b) store under a **distinct name** — the golden uses
suffixes like `order_fee_real_id_pen`, `order_sub_id_pen` for a second capture.
The linter flags any scenario field written more than once.

### assign — write a scenario variable into the next request before it fires

```jsonc
{
  "kind": "assign",
  "name": "assign_<field>",
  "phase": "before_request",
  "order": 0,
  "enabled": true,
  "onFailure": "abort",
  "source": "$.<var>",                          // scenario variable (from an extract)
  "target": "$.request_body.<path>",            // where to inject it
  "scope": "scenario"
}
```

**Pairing rule:** every `assign.source` ($.var) must have a matching upstream
`extract.target` (var) on an earlier step. No dangling references.

## Templating conventions

- `${var.<name>}`   — value from `config.vars`
- `${auth.<user>.token}` — bearer token for a user in `config.users`
- Captured `Authorization` / `Admin-Token` / `Cookie` → replace with
  `${auth.<user>.token}` (pick the user defined in `config.users`).

## Header sanitization

Keep only functional headers (typically just `Authorization`). **Delete** all
browser/transport noise:
`Host, Connection, Content-Length, Cookie, Origin, Referer, User-Agent,
Accept, Accept-Encoding, Accept-Language, sec-ch-ua*, Sec-Fetch-*`.

## config fallback ("未声明即沿用 e2e")

If a value can't be derived from traffic, copy it verbatim from the golden
scenario: `meta`, `config.services`, `config.users`, `config.vars`,
`config.timePolicy`, `config.retry`, `config.setup`, `config.teardown`,
`resource`. Adapt only `meta.name/description/createTime` and `scenarioId`
to reflect the new capture when appropriate.

## Variable naming

Name **dynamic context variables** (extract targets, referenced by assign
`source: $.x`) after their semantic role, not the step:
`order_id`, `order_no`, `order_sub_id`, `order_fee_real_id`, `finance_id_usd`,
`bank_id_cny`, `audit_id`, `receive_account_id`, `receive_invoice_id`,
`apply_id`, `batch_id`, `confirm_list`. Reuse the same name across producer
and all consumers. These are runtime context, NOT `config.vars` — see the
two-namespace rule above.
