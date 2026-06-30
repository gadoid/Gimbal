# Scenario / Suite skeleton

These are minimal schema-valid examples you can paste as a starting
point. They pass `Scenario.model_validate` / `Suite.model_validate`
(`src/gimbal/schema/scenario.py`) and run through `gimbal run launch
--dry-run` with exit 0.

## Minimal scenario (`scenario.yaml`)

```yaml
kind: scenario
scenarioId: sc-hello-001
meta:
  name: hello-world
  description: Minimal single-step GET scenario.
  module: examples
  priority: 1
  author: gimbal-runner
  owner: gimbal-runner
  tags: [smoke, hello]
  version: "1.0"
  createTime: "2026-01-01T00:00:00"
  expire: false
  requirementRef: []
config:
  services:
    demo: https://httpbin.org
  users:
    default:
      authType: bearer
      token: REPLACE_ME
  vars:
    greeting: hello
resource: {}
steps:
  - stepId: get-hello
    description: Fetch /get and assert status 200.
    services: demo
    request:
      method: GET
      path: /get
      headers:
        Authorization: ${auth.default.token}
    strategy:
      - kind: assertion
        target: status
        expected: 200
```

## Multi-step scenario with extract / assign

```yaml
kind: scenario
scenarioId: sc-login-query-001
meta:
  name: login-and-query
  description: Login then query, passing token via extract.
  module: examples
  priority: 2
  author: gimbal-runner
  owner: gimbal-runner
  tags: [smoke]
  version: "1.0"
  createTime: "2026-01-01T00:00:00"
  expire: false
  requirementRef: []
config:
  services:
    api: https://httpbin.org
  users:
    default:
      authType: bearer
      token: ${var.bootstrap_token}
  vars:
    bootstrap_token: REPLACE_ME
resource: {}
steps:
  - stepId: login
    description: Trade credentials for a token.
    services: api
    request:
      method: POST
      path: /post
      headers:
        Content-Type: application/json
      body:
        user: admin
    strategy:
      - kind: extract
        expression: $.json.url        # whatever the API returns
        var: session_token
        scope: scenario
      - kind: assertion
        target: status
        expected: 200
  - stepId: query
    description: Reuse the token from step 1.
    services: api
    request:
      method: GET
      path: /get
      headers:
        Authorization: Bearer ${var.session_token}
    strategy:
      - kind: assertion
        target: status
        expected: 200
```

## Suite (`suite.yaml`)

```yaml
kind: suite
suite:
  - kind: scenario
    scenarioId: sc-hello-001
    meta: { ... }            # full meta per scenario (omitted here for brevity)
    config: { ... }
    resource: {}
    steps: [ ... ]
  - kind: scenario
    scenarioId: sc-login-query-001
    meta: { ... }
    config: { ... }
    resource: {}
    steps: [ ... ]
```

## Templating namespaces

Inside `request.path`, `request.headers`, `request.body`, etc. the
preprocessor expands:

| Placeholder | Resolves from |
|---|---|
| `${var.<name>}` | CLI `--var` → scenario `config.vars` → var-file |
| `${auth.<user>.<field>}` | `config.users.<user>` |
| `${service.<name>}` | `config.services.<name>` (URL) |
| `${resource.<name>.<field>}` | `resource.<name>` block |

## Required top-level fields

`Scenario` (`src/gimbal/schema/scenario.py`):

- `kind: "scenario"` (literal discriminator)
- `scenarioId: str`
- `meta`: full `Meta` block (name, description, module, priority, author, owner, tags, version, createTime, expire, requirementRef)
- `config`: full `Config` block (setup, teardown, services, users, timePolicy, retry, vars)
- `resource: dict[str, ResourceUnion]`
- `steps: list[StepUnion]` (must be non-empty for a real run)

`Suite`:

- `kind: "suite"`
- `suite: list[Scenario]` (each item is a full scenario)

If you skip a field, pydantic will tell you exactly which one — read the
exit-2 stderr verbatim; it almost always names the missing key.

## Strategy kinds (common)

Inside `step.strategy` (executed in order during `VERIFYING`):

| Kind | Purpose |
|---|---|
| `assertion` | Compare `target` (`status`, `header.<name>`, `body.<jsonpath>`, ...) against `expected` |
| `extract` | Read `expression` (JSONPath) from response, store in `var`, optionally `scope: scenario\|step` |
| `assign` | Set a context var before request (`BEFORE_REQUEST` phase) |

The framework also understands Plugin-defined strategy kinds (registered
via `StrategyExecutor`). Stick to the three above unless you wrote the
executor yourself.