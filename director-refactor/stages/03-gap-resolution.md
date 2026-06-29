# Stage 3 — gap-resolution (+ lint)

Resolve each entry in `open_gaps` by editing `script.json` in place, then run `script_lint.py` for structural completeness.

## Input
- `<capture>.script.json` from stage 2 (with `open_gaps[*].resolution = null`).

## Output
- `<capture>.script.json` (resolved) — every `open_gaps[*].status` is `resolved_lookup` / `resolved_static` / `accepted_var`, never `unresolved`.
- For `resolved_lookup`: a **new step** was inserted (synthetic idx ≥ 100) with `role: "context_fetch"`, an `extract` at the catalog path, and any `assigns` for its inputs.

## Mechanical vs Judgment
- **Judgment**: picking the resolution per gap.
  - Run-constant input (e.g. `bl_no`, selected master-data id, fixed `*_time`/`*_date`) → `{"kind":"static","var":"<name>"}`. Becomes a `config.var`. Consumer references `${var.x}`.
  - Business-process id the capture never produced (e.g. `order_id` because listing was skipped) → **must not** fall back to a var. Insert a context-fetch step from the id-resolution source (catalog, MCP, ...). Record `{"kind":"lookup","inserted_idx":<new>,"candidate_index":<i>}`.
  - **Never** route process-generated ids (`order_id`, `audit_id`, `receive_account_id`, …) through a static var.
- **Mechanical**:
  - `script_lint.py` checks: idx present, dense order, valid `collapsed_into`, no dangling assigns (respecting order), no scenario-scope var written more than once (single-write rule), every gap resolved with a well-formed resolution, lookup `inserted_idx` exists.
  - `bulk_extract_candidates` are advisory — wire an extract of `$.response_body.data` only if the data is actually consumed downstream.

## Boundaries / Edge Cases
- The id-resolution source is pluggable: currently a local catalog, may become Plate/EndpointSpec MCP. Decision logic does not change.
- A static var name must never collide with an `extract` target (enforced later by `validate_scenario.py`).
- Inserted lookup steps carry synthetic idx ≥ 100 so they never collide with capture indices.

## Open Questions
- TBD