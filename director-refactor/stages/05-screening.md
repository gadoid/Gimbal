# Stage 5 — validate + review

Two sub-stages. **(5a)** is mechanical linter; **(5b)** is the model's final review that the linter can't make.

## Input
- `<capture>.scenario.json` from stage 4.
- `--capture <capture>.ndjson` (optional) — verify extract paths resolve against real responses.
- `--script <capture>.script.json` (optional) — cross-check the assembled step sequence against every step the script committed to (`order` non-null). Catches silent drops / duplicates / reorders in assembly.
- `--process-ids a,b,c` (optional) — extend the default process-id set.

## Output
- Exit code 0 (clean) or 1 (violations). stdout lists violations + warnings.
- The final scenario is **ready for GIMBAL's loader** if exit 0.

## Mechanical vs Judgment
- **Mechanical (5a)**:
  - `static/dynamic` rule: a name that is an `extract` target must never also be a `config.var`. Process ids (`order_id`, `order_no`, `order_sub_id`, `audit_id`, `receive_account_id`, `finance_id`, `apply_id`, `batch_id`, `confirm_id`, …) are dynamic-only.
  - `single-write rule`: a scenario-scope `extract` target may be written only once. Use `scope: step` or distinct names (`<var>_pen`) for repeated captures.
  - `dangling assign`: every `assign.source` must have an earlier `extract.target`.
  - `path resolve`: every `extract.expression` must resolve against a real response (with `--capture`).
  - `auth templated`: `Authorization` must be `${auth.<user>.token}`, not a raw captured token.
  - `header hygiene`: warn on browser/transport headers.
  - `status assertion`: warn if no `$.response_status` assertion.
  - `completeness vs script` (with `--script`): every script-committed step appears in the scenario in the same order.
- **Judgment (5b)**:
  - Does this ordered chain tell a coherent business story end-to-end?
  - Is each kept step there for a reason?
  - Reorder or re-curate the script and re-assemble if not.

## Boundaries / Edge Cases
- `--capture` path-matching uses `path + occurrence_count`, not strict `idx`. May mis-resolve when same path appears multiple times and one occurrence was collapsed or dropped.
- Process-id list is hard-coded (`DEFAULT_PROCESS_IDS`) and extended via `--process-ids`. Domain-specific dynamic ids not in this list rely on the "extract target" check to catch the static/dynamic collision.
- The `--script` completeness check keys on `idx`/`order`; if a synthetic inserted-lookup step's `order` collides with a real step's, ordering will be ambiguous.

## Open Questions
- TBD