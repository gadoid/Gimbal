# Canonicalization — sample-side facts

Stage 2 writes two values per sample: `value` (raw display, what the
user types) and `canon` (canonical form, what the backend compares).
Stage 3 emits `expected_display` (= `value`) and `expected_canon` (= `canon`)
on assertion ④. The comparison rule between them depends on `category`.

## Per-category rules

| Category | sample.canon | assertion.predicate |
|---|---|---|
| `ENUM` | label (display) | `row[f] == sample.value` (label compares in label domain) |
| `EXACT` | raw text/number | `canon(row[f]) == sample.canon` |
| `FUZZY` | raw text | `any(sample.canon in canon(row[f]) for f in response_fields)` |
| `DATE_RANGE` (`date`) | `YYYY-MM-DD` | `YYYY-MM-DD <= parse_date(row[f]) <= YYYY-MM-DD` |
| `DATE_RANGE` (`datetime`) | `YYYY-MM-DD HH:MM:SS` | same, datetime precision |
| `DECIMAL` | numeric stripped of `$¥,` and leading zeros | `Decimal(row[f]) == Decimal(sample.canon)` |
| `NULL_QUERY` | (skipped in v1) | separate design |

## Things `sample.value` is, `sample.canon` is not

- `sample.value` may carry currency/separator/whitespace decorations
  the user typed; `sample.canon` is the same value re-rendered in a
  form the comparator can consume.
- Strip leading/trailing whitespace from `sample.value` before
  assertion ④ — sampled data has shown cases like `' 银小忠'`.
- The stub `"1970-01-01"` is the canonical negative value for any
  `DATE_RANGE`; `"<code>_NOTEXIST_gimbal"` is the negative for
  `EXACT` / `FUZZY` / `DECIMAL`.

## Cardinality & granularity rules (Stage 3 owns the application)

- ENUM: `len(value_map) <= 3` → assertion ② uses `<=`, otherwise `<`.
- DATE_RANGE: default `date`; `datetime` only when `name-overrides.json`
  flags the field (e.g. `search_time[asset_pass_time_first]`).
- FUZZY: both `response_field` and `response_fields` are preserved on
  the emitted step; the runtime reads `response_fields` if non-empty.

## Notes

- "Canonicalize" is local to the comparator. Never persist the
  canonical form to `samples.json` — `samples[].canon` is the
  comparator's input, not a re-encoded display value.
- The four-assertion triplet
  (count_shrinks / anchor_present / first-page rows_match) all read
  `samples[i].canon` consistently; mismatch in any direction means
  Stage 2 is wrong, not Stage 3.
