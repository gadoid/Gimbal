# Stage 1 — analyze_flow

Turns raw `*.ndjson` traffic into a **record-centric** report (`flow.json` + human-readable `flow.md`). Purely mechanical: no model judgment, every emitted JSONPath verified against the actual response body.

## Input
- `<capture>.ndjson`  (required) — one JSON record per line. Each record:
  `{ts, method, host, path, headers, body, response: {status, headers, body}}`.
  Bodies (`body`, `response.body`) are JSON *strings* that must be parsed.
- `--business-host <host>` (optional) — explicit business host. Omit to auto-pick the most frequent host; everything else is flagged cross-domain noise.
- `--catalog <lookup_catalog.json>` (optional) — pre-fills lookup suggestions for any id a request consumes that no earlier response produced.
- `--out` / `--md` (optional) — output paths. Defaults to `<capture>.flow.json` / `<capture>.flow.md`.

## Output
- `<capture>.flow.json`:
  ```jsonc
  {
    "summary": { total_records, business_host, unique_paths,
                 kept, dropped, lineage_edges,
                 var_candidates, context_fetch_candidates },
    "host_counts": { <host>: <n>, ... },
    "path_frequency": [[path, count], ...],            // noise ranking
    "records": [                                      // one entry per ndjson line
      { idx, path, method, status, decision: "KEEP"|"DROP",
        reason, dup_of? }, ... ],
    "lineage": [                                      // verified value-lineage edges
      { value, producer_idx, producer_path,           // $.response_body...
        consumer_idx, consumer_path, field }, ... ],
    "bulk_extract_candidates": [                      // advisory
      { idx, path, expression: "$.response_body.data", shape } ],
    "missing_producers": [                            // consumed-but-not-produced
      { value, consumer_idx, field, occurrence_count, occurrence_steps,
        suggestions: [{endpoint, path, inputs}, ...],
        static_constant_candidate: bool }, ... ]
  }
  ```
- `<capture>.flow.md` — human view: kept steps, lineage edges, var candidates, missing producers, dropped-path frequency.

## Mechanical vs Judgment
- **Mechanical**: everything in `flow.json`. The script does not invent JSONPaths; every `producer_path` / `consumer_path` is verified by walking the actual parsed body.
- **Judgment deferred to stage 2/3**: which KEEP steps to actually keep, which DROPs to flip, how to resolve `missing_producers`.

## Boundaries / Edge Cases
- Cross-domain traffic (anything not on `business_host`) → unconditionally DROP.
- Pure UI-population reads with no downstream id producer → DROP, but **still seed a `lineage` edge if they happen to produce an id a later step consumes** (via `producer_emits`).
- Duplicate calls (same path + identical request body) → flagged with `dup_of` only if the record has **no producer role** (so an id-producer that legitimately re-extracts at a different flow stage is never mislabeled as a dup).
- A snowflake that appears in *every* request with no producer (e.g. `bl_no`) → marked `static_constant_candidate: true` if it occurs in ≥2 distinct steps **and** has no catalog match. This is the signal to promote to `config.vars` later, not insert a lookup.
- An id with no producer, no catalog match, single occurrence → genuine missing-producer: needs a context-fetch step in stage 3.

## Open Questions
- TBD