# Stage 4 — script_assemble

Mechanical: turn the resolved `script.json` into a final GIMBAL `scenario.json`. No judgment — every decision is already baked into the script.

## Input
- `<capture>.script.json` (resolved).
- (Implicit) reads `source_capture` to re-fetch raw bodies by idx.
- (Implicit) reads `golden_ref` for `meta`/`config`/`resource` (config fallback) and to pick the auth user.

## Output
- `<capture>.scenario.json`:
  ```jsonc
  {
    "kind": "scenario",
    "scenarioId": "<goldenId>_from_capture",
    "meta": { ... copied from golden ... },
    "config": { ... copied from golden, +vars seeded from gap static resolutions ... },
    "resource": { ... copied from golden ... },
    "steps": [
      { kind: "step",
        api: { kind: "api", service, method, path,
               headers: { Authorization: "${auth.<user>.token}" }, timeout: 30 },
        request: { kind: "request", body: <parsed captured, sanitized & templated> },
        strategy: [ assert_status_200, ...extracts, ...assigns ]
      }, ...
    ]
  }
  ```

## Mechanical vs Judgment
- **Mechanical**:
  - Walks kept steps in `order`.
  - Re-reads each step's raw request body by idx from `source_capture`.
  - Sanitizes headers: keeps `Authorization` (templated to `${auth.<user>.token}`), strips browser/transport noise (`Host`, `Connection`, `Content-Length`, `Cookie`, `Origin`, `Referer`, `User-Agent`, `Accept-*`, `sec-ch-ua*`, `Sec-Fetch-*`).
  - Emits mandatory `assert_status_200` plus one strategy block per binding.
  - For static-gap vars, injects `${var.x}` template at the assign target in the body (no runtime `assign` strategy).
  - For synthetic inserted-lookup steps (no raw record), reads `request_body` / `headers` / `path` / `method` from the step itself.
  - Seeds `config.vars` from `open_gaps[*].resolution.kind=="static"`.
- **Judgment**: none. (All judgments already in the script.)

## Boundaries / Edge Cases
- `service` is taken as the first entry of `golden.config.services` — if golden has multiple services and the capture spans more than one, the script currently labels every step with the same service.
- Static var injection uses a tiny regex to walk `$.request_body.a.b[0].c` paths. Targets not present in the body are silently skipped (the value will be filled at runtime only if GIMBAL has its own templating pass).
- The `assert_status_200` strategy is generated for **every** kept step regardless of expected status code.

## Open Questions
- TBD