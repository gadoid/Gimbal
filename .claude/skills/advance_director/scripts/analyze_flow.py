#!/usr/bin/env python3
"""
analyze_flow.py — GIMBAL traffic preprocessor (Director, 剪辑链 阶段0).

Reads a Prism/mitmproxy ndjson capture and produces a deterministic
"scaffold" report that drives script_init.py / the scripting stage:

  1. path frequency table (helps spot UI-noise reads)
  2. value-lineage graph: which RESPONSE field produced an id that is later
     consumed by a REQUEST field  -> these become extract/assign candidates
  3. signal / noise classification per record, with a reason
  4. external-value matches: request fields whose VALUE matches something
     already declared in the scenario scaffold's config.vars/resource — these
     are NOT internal lineage and must be left untouched (no policy), because
     supplying them is the 发版链 (assemble stage)'s job, not the 剪辑链's.
  5. noise-key exclusions: fields whose NAME (not value) is pure transport/
     audit noise (request_no, trace_id, ...) and must never be treated as a
     producer or consumer regardless of value.

The script never invents JSONPaths: every path it emits is verified by
walking the actual parsed request/response body.

Usage:
    python analyze_flow.py CAPTURE.ndjson \\
        --scaffold scenario_scaffold.json \\
        --catalog references/lookup_catalog.json \\
        --noise-keys references/noise-keys.json \\
        --value-blacklist references/common-values-blacklist.json \\
        [--business-host HOST] [--min-value-len 4] \\
        [--out flow.json] [--md flow.md]

If --business-host is omitted, the most frequent host is treated as the
business host and everything else is flagged as cross-domain noise.

--scaffold is the scenario JSON the steps will eventually be assembled into
(kind/scenarioId/meta/config/resource already decided, steps: []). It is the
ONLY source of "what counts as external input" — there is no dependency on
a golden example scenario for this judgment.
"""
import argparse
import bisect
import json
import re
import sys
from collections import Counter, defaultdict

# Path last-segment verbs that indicate a state-changing business call.
MUTATION_VERBS = (
    "add", "edit", "submit", "execute", "confirm", "generate", "book",
    "batch", "writeoff", "apply", "allocation", "toggle", "lock", "del",
    "delete", "update", "create", "save", "cancel", "put", "push",
)

# Field-name patterns that look like identifiers worth tracing.
ID_KEY_RE = re.compile(r"(_id$|_ids$|_no$|_sn$|^id$|token$)", re.IGNORECASE)
# A value that is "id-shaped": long digit run (snowflake) or order-no-like token.
SNOWFLAKE_RE = re.compile(r"^\d{12,}$")
ORDERNO_RE = re.compile(r"^[A-Z]{2,}\d{6,}$")
# Canonical UUID shape — this is how CLIENT-generated correlation ids look
# (a frontend form-row key, an idempotency key, ...), never something a
# backend query endpoint returns. Treating it as id-shaped turns it into an
# unresolvable open_gap (no lookup candidate will ever exist for it) purely
# because its field name ends in _id. Exclude it outright; it stays literal.
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

DEFAULT_MIN_VALUE_LEN = 4


def load_records(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[warn] line {ln}: bad json ({e})", file=sys.stderr)
    return recs


def parse_body(raw):
    """Body / response.body arrive as JSON strings; parse best-effort."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None
    return None


def walk(node, prefix="$"):
    """Yield (jsonpath, value) for every scalar leaf in a nested structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{prefix}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, node


def last_key(jsonpath):
    return jsonpath.rsplit(".", 1)[-1].split("[")[0]


def is_id_value(key_path, value):
    """Heuristic: is this leaf an identifier we should trace?"""
    if value is None or isinstance(value, bool):
        return False
    sval = str(value)
    if sval in ("", "0", "1"):  # too ambiguous to anchor a lineage edge
        return False
    if UUID_RE.match(sval):    # client-generated correlation id, not a lookup target
        return False
    k = last_key(key_path)
    key_hit = bool(ID_KEY_RE.search(k))
    shape_hit = bool(SNOWFLAKE_RE.match(sval) or ORDERNO_RE.match(sval))
    if shape_hit:
        return True
    # NB: was `sval.isalnum()`, which silently excluded id-named fields whose
    # values contain '_' or '-' — e.g. bl_no = "GIMBAL_TEST_35". Such a value,
    # if not declared in the scaffold, then never surfaced as a gap either:
    # the replay would silently reuse the stale captured literal. The key is
    # already id-named (ID_KEY_RE hit), so allowing separators is low-risk.
    if key_hit and len(sval) >= 6 and re.fullmatch(r"[A-Za-z0-9_\-]+", sval):
        return True
    return False


def verb_of(path):
    seg = path.rstrip("/").rsplit("/", 1)[-1].lower()
    return seg


# A path whose tail ENDS in one of these is a read, even if it embeds a verb
# (e.g. realAmountEditDetail contains "edit" but is a detail read).
READ_SUFFIX = ("detail", "page", "list", "info", "view", "query", "part", "record")


def verb_class(path):
    """'read' | 'mutation' | 'unknown'.

    'unknown' is the load-bearing case: a last segment that neither looks
    like a read (READ_SUFFIX) nor matches MUTATION_VERBS. Historically this
    silently fell through to "not a mutation" — i.e. a droppable pure read —
    which is exactly how a 3-stage state-change endpoint (assetPush:
    action=check/audit/submit, empty responses, no downstream ids) got all
    three of its calls classified 'pure read, no downstream dependency' and
    dropped, silently amputating the flow. The failure asymmetry is stark:
    wrongly KEEPING a read costs one redundant request at replay; wrongly
    DROPPING a mutation breaks the business flow. So 'unknown' is treated as
    a possible mutation everywhere (kept, counts as a state boundary), and
    surfaced loudly so the verb list gets extended instead of the gap
    staying invisible.
    """
    seg = verb_of(path)
    if seg.endswith(READ_SUFFIX):
        return "read"
    if any(v in seg for v in MUTATION_VERBS):
        return "mutation"
    return "unknown"


def is_mutation(path):
    # "possibly state-changing": both confirmed mutations and unknowns.
    # Callers that need to distinguish use verb_class directly.
    return verb_class(path) != "read"


def load_json_or_empty(path, key_for_log):
    if not path:
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[warn] could not read {key_for_log} ({path}): {e}", file=sys.stderr)
        return None


def build_external_value_set(scaffold, blacklist_values, min_len):
    """Walk config.vars / resource in the scaffold; return the set of
    stringified leaf values that count as 'externally declared input',
    after applying the length floor and the common-values blacklist.
    Also returns value -> declared name(s), for reporting only.
    """
    if not scaffold:
        return set(), {}
    external = set()
    value_to_names = defaultdict(set)
    cfg_vars = (scaffold.get("config", {}) or {}).get("vars", {}) or {}
    for name, v in cfg_vars.items():
        sval = str(v)
        value_to_names[sval].add(f"var.{name}")
        if len(sval) >= min_len and sval not in blacklist_values:
            external.add(sval)
    resource = scaffold.get("resource", {}) or {}
    for jp, v in walk(resource, "$.resource"):
        if v is None or isinstance(v, bool):
            continue
        sval = str(v)
        value_to_names[sval].add(jp)
        if len(sval) >= min_len and sval not in blacklist_values:
            external.add(sval)
    return external, dict(value_to_names)


def field_of_path(jp):
    return jp.rsplit(".", 1)[-1].split("[")[0]


def positional_risk_of(resp, producer_path, noise_keys):
    """If producer_path passes through an array index, return
    (array_len, position, discriminators) for the INNERMOST array hop —
    discriminators are the matched element's scalar sibling fields
    (e.g. audit_type/audit_status next to the extracted audit_id).

    Why: an extract expression like $.response_body.data.audit[0].audit_id is
    POSITIONAL. It was verified against this capture, but at replay time the
    array's ordering/content can differ (new audit records appended, list
    re-sorted) and [0] silently resolves to the WRONG element — the exact
    OLD-vs-NEW audit_id drift bug. The pipeline can't fix this mechanically
    (GIMBAL extract expressions are plain JSONPaths), but it CAN tell the
    scripting stage which sibling fields uniquely identify the element that
    was actually consumed, so the model/human can (a) verify [0] is
    semantically stable, (b) swap in a filtered query endpoint, or (c) at
    minimum add a discriminator assertion on the same element.
    """
    body = producer_path.replace("$.response_body", "", 1)
    toks = re.findall(r"\.([A-Za-z0-9_]+)|\[(\d+)\]", body)
    arr_positions = [i for i, (k, ix) in enumerate(toks) if ix != ""]
    if not arr_positions:
        return None
    last_arr = arr_positions[-1]
    cur = resp
    try:
        for k, ix in toks[:last_arr]:
            cur = cur[k] if k else cur[int(ix)]
        pos = int(toks[last_arr][1])
        if not isinstance(cur, list):
            return None
        elem = cur[pos]
    except Exception:
        return None
    discriminators = {}
    if isinstance(elem, dict):
        for k, v in elem.items():
            if k in noise_keys or isinstance(v, (dict, list)) or v is None:
                continue
            discriminators[k] = v
            if len(discriminators) >= 8:
                break
    return len(cur), pos, discriminators


def is_failed(p):
    """HTTP-level failure. A failed response must never anchor lineage:
    extracting from it wires the scenario to an error envelope, and its
    request was very likely a retry/mis-fire the user corrected afterwards."""
    try:
        return p.get("status") is not None and int(p["status"]) >= 400
    except (TypeError, ValueError):
        return False


def business_code_suspect(resp):
    """Soft check: common {code: ...} envelope where code signals failure.
    Envelope conventions vary, so this only WARNS, never auto-drops."""
    if isinstance(resp, dict) and "code" in resp:
        if resp["code"] not in (0, 200, "0", "200", None):
            return resp["code"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ndjson")
    ap.add_argument("--business-host", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--catalog", default=None,
                    help="lookup_catalog.json; suggests a query endpoint for any "
                         "id consumed in a request but never produced in this capture")
    ap.add_argument("--scaffold", default=None,
                    help="scenario JSON with steps:[] but config/resource decided; "
                         "the source of truth for what counts as external input")
    ap.add_argument("--noise-keys", default=None,
                    help="noise-keys.json; field names excluded from lineage regardless of value")
    ap.add_argument("--value-blacklist", default=None,
                    help="common-values-blacklist.json; values excluded from external-value matching")
    ap.add_argument("--min-value-len", type=int, default=DEFAULT_MIN_VALUE_LEN,
                    help="minimum length for a value to participate in external-value matching")
    args = ap.parse_args()

    recs = load_records(args.ndjson)
    n = len(recs)

    host_counts = Counter(r.get("host", "") for r in recs)
    business_host = args.business_host or (host_counts.most_common(1)[0][0] if host_counts else "")

    scaffold = load_json_or_empty(args.scaffold, "scaffold")
    noise_keys_doc = load_json_or_empty(args.noise_keys, "noise-keys")
    noise_keys = set(noise_keys_doc.get("keys", [])) if noise_keys_doc else set()
    blacklist_doc = load_json_or_empty(args.value_blacklist, "value-blacklist")
    blacklist_values = set(blacklist_doc.get("values", [])) if blacklist_doc else set()

    external_values, value_to_names = build_external_value_set(
        scaffold, blacklist_values, args.min_value_len)

    # Pre-parse bodies.
    parsed = []
    for r in recs:
        parsed.append({
            "idx": len(parsed),
            "ts": r.get("ts"),
            "method": r.get("method"),
            "host": r.get("host"),
            "path": r.get("path"),
            "req": parse_body(r.get("body")),
            "resp": parse_body((r.get("response") or {}).get("body")),
            "status": (r.get("response") or {}).get("status"),
        })

    # Build producer index: value -> ALL (idx, jsonpath) occurrences seen in a
    # RESPONSE, in capture order. Noise keys are excluded here too — a noisy
    # field should never anchor a lineage edge even if it looks id-shaped.
    #
    # IMPORTANT: this used to keep only the EARLIEST occurrence ("earliest
    # wins"). That breaks flows where the SAME literal value legitimately (or,
    # via a real upstream business bug, illegitimately) reappears in a LATER
    # response — e.g. a list/detail endpoint that is re-queried after a
    # mutation, where the id at the same JSONPath happens to coincide with an
    # earlier occurrence. With "earliest wins", the later occurrence never
    # gets to be a *producer* for anything, so if its own consumer needs that
    # value, the edge gets silently wired back to the FIRST (chronologically
    # unrelated) occurrence instead of the one that actually preceded it — and
    # the later record then looks like a "pure read, no downstream dependency"
    # and gets collapsed as a dup of the first (see dup_seen below). This is
    # exactly the audit-list re-read bug class: two distinct audit workflows
    # sharing one GET endpoint whose repeated call gets flattened into one.
    #
    # Keeping every occurrence and, per consumer, picking the NEAREST
    # PRECEDING one (not the globally earliest) fixes both problems: the
    # later record becomes its own producer when something after it consumes
    # the value, so it survives dedup; and the wiring reflects what the
    # traffic actually did, bug-for-bug, rather than papering over a repeat.
    producers_all = defaultdict(list)  # value(str) -> [(idx, jsonpath), ...] in idx order
    for p in parsed:
        if p["resp"] is None or is_failed(p):
            continue
        for jp, val in walk(p["resp"], "$.response_body"):
            if last_key(jp) in noise_keys:
                continue
            if not is_id_value(jp, val):
                continue
            sval = str(val)
            producers_all[sval].append((p["idx"], jp))

    # A mutation only counts as a "state changed" boundary if it actually
    # succeeded on the business host — moved up here (was computed later)
    # because the value-canonicalization pass below needs it too.
    mutation_idxs = sorted(
        p["idx"] for p in parsed
        if is_mutation(p["path"]) and p["host"] == business_host and not is_failed(p)
    )

    def mutation_between(lo, hi):
        # any mutation-verb record with lo < idx < hi ?
        i = bisect.bisect_right(mutation_idxs, lo)
        return i < len(mutation_idxs) and mutation_idxs[i] < hi

    # For each request, classify every scalar leaf into exactly one bucket:
    #   noise        -> key hits noise-keys.json, excluded entirely
    #   external     -> value hits the scaffold's declared external-value set
    #   dynamic_lineage -> id-shaped value with a real earlier-response producer
    #   gap          -> id-shaped value with NO earlier-response producer
    #   literal      -> everything else (not even examined as lineage)
    lineage = []
    consumer_needs = defaultdict(list)
    producer_emits = defaultdict(list)
    ignored_external = []
    consumed_for_gap = defaultdict(list)  # value -> [(consumer_idx, field, consumer_path), ...]

    for p in parsed:
        if p["req"] is None or is_failed(p):
            continue
        for jp, val in walk(p["req"], "$.request_body"):
            k = last_key(jp)
            if k in noise_keys:
                continue
            sval = str(val)
            if sval in external_values:
                ignored_external.append({
                    "idx": p["idx"], "path": p["path"], "field": k,
                    "consumer_path": jp, "value": sval,
                    "declared_as": sorted(value_to_names.get(sval, [])),
                })
                continue  # never enters lineage/gap analysis
            if not is_id_value(jp, val):
                continue
            # NOTE: deliberately NOT deduping by value here. The same id-shaped
            # value commonly appears at MULTIPLE distinct JSONPaths within one
            # request (e.g. both $.order_id and $.supplier[0].order_id in the
            # same orderAdd body) and EVERY occurrence needs its own assign —
            # skipping repeats silently left the second occurrence on its
            # original captured literal, which is exactly the bug class that
            # produced a step-9 runtime failure from a step-4 wiring gap (see
            # references/script-schema.md). Duplicate EXTRACTs on the producer
            # side are still deduped, but at the (producer step, var) level in
            # script_init.py, which is the correct place for that dedup.
            #
            # A single response commonly repeats the SAME value at multiple
            # JSONPaths too (e.g. a top-level $.data.order_id next to a
            # nested $.data.supplier[0].order_id echoing the same order).
            # Walking dict/list order determines which one lands LAST in
            # producers_all for that idx, which is arbitrary w.r.t. stability
            # — among candidates tied on "nearest preceding idx", prefer the
            # least positionally-fragile path (a plain scalar over an
            # array-indexed one) so the extract this pipeline picks is the
            # same kind of source a human scripting the flow would pick.
            best_idx = None
            best_jps = []
            for cand_idx, cand_jp in producers_all.get(sval, []):
                if cand_idx >= p["idx"]:
                    break
                if best_idx is None or cand_idx > best_idx:
                    best_idx, best_jps = cand_idx, [cand_jp]
                elif cand_idx == best_idx:
                    best_jps.append(cand_jp)
            src = None
            if best_idx is not None:
                if len(best_jps) == 1:
                    src = (best_idx, best_jps[0])
                else:
                    def _path_stability(jp):
                        info = positional_risk_of(parsed[best_idx]["resp"], jp, noise_keys)
                        if info is None:
                            return 0
                        arr_len, pos, _ = info
                        return 2 if (arr_len > 1 or pos > 0) else 1
                    src = (best_idx, min(best_jps, key=_path_stability))
            if src:
                edge = {
                    "value": sval,
                    "producer_idx": src[0],
                    "producer_path": src[1],          # $.response_body...
                    "consumer_idx": p["idx"],
                    "consumer_path": jp,              # $.request_body...
                    "field": k,
                }
                lineage.append(edge)
                consumer_needs[p["idx"]].append(edge)
                producer_emits[src[0]].append(edge)
            else:
                consumed_for_gap[sval].append((p["idx"], k, jp))

    # ------------------------------------------------------------------
    # Value canonicalization: collapse a genuinely stable, whole-flow
    # identifier (order_id queried from 18 different steps, always the
    # same value) down to ONE producer/var instead of the per-occurrence
    # "nearest preceding producer" default — which is correct for
    # PROTECTING against coincidental value reuse (two different audits
    # that happen to share an id), but wrong for a value that's simply
    # the same real-world entity everywhere. Left unmerged, this produces
    # e.g. order_id_1..order_id_18, each independently extracted — some
    # from fragile positional paths ($.data.supplier[0].order_id, which
    # is null whenever that order has no supplier row) — so a single
    # missing array element aborts a step that a stable, once-extracted
    # order_id would have sailed through, exactly mirroring how a
    # hand-authored ("gold") scenario extracts order_id ONCE from a
    # reliable source and reuses it everywhere.
    #
    # The two situations look identical from "same string value showed up
    # at multiple producer occurrences" alone, so merging needs a gate,
    # not a blanket rule:
    #
    #   SUSPECT (never auto-merge) — two producer occurrences of the value
    #   came from the SAME endpoint (same request path), with a mutation
    #   in between. That's exactly the shape of "this endpoint was
    #   re-queried after something that should have changed what it
    #   returns, and coincidentally/buggily didn't" — the audit_id-reuse
    #   case. Collapsing these would silently mask a real replay risk
    #   (or a real backend bug) instead of surfacing it.
    #
    #   SAFE TO MERGE — every other multi-producer case: the value recurs
    #   across DIFFERENT endpoints (or the same endpoint with no mutation
    #   in between, i.e. genuinely idempotent re-reads), which is the
    #   normal signature of "this is just the same entity's id, queried
    #   again by unrelated business calls".
    #
    # For a safe group, the canonical producer is chosen by lowest
    # positional risk (prefer a scalar/non-array-indexed response field,
    # or a low-risk single-element array) and, among ties, the earliest
    # occurrence — mirroring what a human scripting the flow by hand would
    # naturally pick as "the" source of that id.
    value_groups = defaultdict(list)
    for e in lineage:
        value_groups[e["value"]].append(e)

    value_reuse_suspects = []
    canonicalized_values = []

    def _risk_rank(occ):
        # Primary key: is this occurrence HIGH risk (array len>1 or pos>0)?
        # Only HIGH-risk occurrences get passed over. A "low" risk occurrence
        # (single-element array at position 0) is treated the same as a
        # plain scalar for ranking purposes — both are trusted at their
        # NATURAL chronological position, so the earliest one wins. This
        # matters because the earliest occurrence is also the only choice
        # guaranteed to precede every consumer in the group (e.g. an
        # order-search endpoint queried once up front, whose own result the
        # SAME step then needs as input) — picking a later "prettier" path
        # over it can make the group unmergeable for no real safety benefit.
        idx, jp = occ
        info = positional_risk_of(parsed[idx]["resp"], jp, noise_keys)
        if info is None:
            high = 0
        else:
            arr_len, pos, _ = info
            high = 1 if (arr_len > 1 or pos > 0) else 0
        return (high, idx)

    for val, edges in value_groups.items():
        distinct_producers = sorted({(e["producer_idx"], e["producer_path"]) for e in edges})
        if len(distinct_producers) <= 1:
            continue  # already one shared producer, nothing to canonicalize

        suspect_pairs = []
        for i in range(len(distinct_producers)):
            for j in range(i + 1, len(distinct_producers)):
                idx_i, jp_i = distinct_producers[i]
                idx_j, jp_j = distinct_producers[j]
                if parsed[idx_i]["path"] != parsed[idx_j]["path"]:
                    continue
                if not mutation_between(min(idx_i, idx_j), max(idx_i, idx_j)):
                    continue
                # A plain scalar (no array index anywhere in the path) isn't
                # the shape that breaks on re-ordering/growth — it's a
                # top-level attribute of the SAME resource, expected to be
                # stable across re-queries regardless of what else in that
                # resource's sub-lists changed. Only an array-indexed path
                # (positional_risk_of returns non-None) carries the ordering/
                # growth risk that makes "same value again" suspicious.
                if positional_risk_of(parsed[idx_i]["resp"], jp_i, noise_keys) is None and \
                        positional_risk_of(parsed[idx_j]["resp"], jp_j, noise_keys) is None:
                    continue
                suspect_pairs.append([idx_i, idx_j])

        if suspect_pairs:
            value_reuse_suspects.append({
                "value": val,
                "producers": [{"idx": i, "path": parsed[i]["path"], "extract_path": jp}
                             for i, jp in distinct_producers],
                "suspect_pairs": suspect_pairs,
            })
            continue  # leave every edge on its originally-resolved producer

        canonical_idx, canonical_jp = min(distinct_producers, key=_risk_rank)
        # Only rewire edges the canonical producer can actually feed (must
        # strictly precede the consumer — e.g. the very step that FIRST
        # produced this value may itself have consumed it from an even
        # earlier producer to build its own request; that specific edge
        # can't be rewired to point at itself). Everything else in the
        # group still merges; only the edge(s) that would break causality
        # stay on their originally-resolved producer.
        rewired = [e for e in edges if canonical_idx < e["consumer_idx"]]
        if len(rewired) < 2:
            continue  # nothing meaningful to merge after excluding self-referential edges
        merged_from = sorted({(e["producer_idx"], e["producer_path"]) for e in rewired}
                             - {(canonical_idx, canonical_jp)})
        if not merged_from:
            continue  # everything eligible already shared the canonical producer
        for e in rewired:
            e["producer_idx"] = canonical_idx
            e["producer_path"] = canonical_jp
        canonicalized_values.append({
            "value": val,
            "canonical_producer_idx": canonical_idx,
            "canonical_producer_path": canonical_jp,
            "merged_from": [{"idx": i, "path": jp} for i, jp in merged_from],
        })

    # producer_emits was built against the PRE-canonicalization producer_idx
    # on each edge; rebuild it from the (possibly rewritten) lineage so
    # classification below sees the real, final producer of each value.
    producer_emits = defaultdict(list)
    for e in lineage:
        producer_emits[e["producer_idx"]].append(e)

    # Classify each record (keep/drop), unaffected by the value-matching work above.
    path_freq = Counter(p["path"] for p in parsed)
    rows = []
    business_code_warnings = []
    unclassified_verbs = {}   # verb segment -> {paths, idxs} for the flow.md report
    for p in parsed:
        reasons = []
        keep = False
        if p["host"] != business_host:
            rows.append({**_slim(p), "decision": "DROP", "reason": "cross-domain host (non-business)"})
            continue
        if is_failed(p):
            rows.append({**_slim(p), "decision": "DROP",
                         "reason": f"failed response (HTTP {p['status']}) — likely a retried/mis-fired "
                                   f"call; excluded from lineage entirely"})
            continue
        code = business_code_suspect(p["resp"])
        if code is not None:
            business_code_warnings.append({"idx": p["idx"], "path": p["path"], "code": code})
        vc = verb_class(p["path"])
        if vc == "mutation":
            keep = True
            reasons.append("mutation verb")
        elif vc == "unknown":
            # Not a recognized read, not a recognized mutation verb. Keep
            # conservatively: silently dropping an unrecognized mutation
            # amputates the flow (the assetPush check/audit/submit case),
            # while keeping an unrecognized read merely replays one extra
            # request. Surface it so the verb lists get extended.
            keep = True
            reasons.append(f"[WARN] unrecognized verb '{verb_of(p['path'])}' — kept "
                           f"conservatively as a possible state change; extend "
                           f"MUTATION_VERBS or READ_SUFFIX to classify it properly")
            u = unclassified_verbs.setdefault(verb_of(p["path"]), {"paths": set(), "idxs": []})
            u["paths"].add(p["path"])
            u["idxs"].append(p["idx"])
        if producer_emits.get(p["idx"]):
            keep = True
            fields = sorted({e["field"] for e in producer_emits[p["idx"]]})
            reasons.append("produces downstream id(s): " + ", ".join(fields))
        if not keep:
            reasons.append(f"pure read, no downstream dependency (path x{path_freq[p['path']]})")
        if code is not None and keep:
            reasons.append(f"[WARN] business code={code} in response — verify this call actually succeeded")
        rows.append({
            **_slim(p),
            "decision": "KEEP" if keep else "DROP",
            "reason": "; ".join(reasons),
        })
    unclassified_verbs = {k: {"paths": sorted(v["paths"]), "idxs": v["idxs"]}
                          for k, v in sorted(unclassified_verbs.items())}

    # Flag duplicate KEEP records (same path, identical request body) so the
    # caller can collapse pure repeats. BUT never flag a record that produces a
    # downstream-consumed id: re-queries at different flow stages legitimately
    # extract DIFFERENT ids and must survive.
    #
    # ALSO never flag a record as a dup if a mutation-verb (state-changing)
    # request happened between it and the earlier occurrence. Same
    # path+body is only evidence of "pure repeat" when nothing happened in
    # between to change server state; a GET replayed after a POST that
    # altered exactly the resource being read (e.g. orderDetail called again
    # right after auditExecute moved the order into its next audit stage) is
    # a legitimately DIFFERENT read even though the request looks identical —
    # collapsing it hides that the flow re-checked state mid-process, and
    # (combined with the producer_emits check above) is the root cause of the
    # "second audit gets folded away" bug: with the old earliest-wins producer
    # index this record's own new id often failed to register as a fresh
    # producer, so this mutation-boundary check is the necessary second line
    # of defense even after the producers_all fix above.
    # A mutation only counts as a "state changed" boundary if it actually
    # succeeded on the business host. A FAILED mutation (HTTP >=400, or a
    # business-code error) didn't change anything — treating it as a boundary
    # would wrongly keep two genuinely-identical reads apart. A mutation-verb
    # call on a non-business host (analytics/logging beacons sometimes use
    # verbs like "add") isn't a business-state change either.
    dup_seen = {}
    for row in rows:
        if row["decision"] != "KEEP":
            continue
        if producer_emits.get(row["idx"]):          # producer -> not a true dup
            continue
        # A MUTATION is never a candidate for silent collapse: replaying the
        # same state-changing call twice is a business event (two approvals,
        # two submits), not transport noise. Even with an identical body, the
        # second call usually targets state that the first call itself
        # changed — and its body is typically rewritten at runtime by an
        # assign anyway. Only pure reads are safe to collapse. This closes
        # the residual half of the double-audit bug: previously the second
        # auditExecute (identical literal body) was dup-collapsed even after
        # the producer-side fix, leaving a dead extract for the model to
        # rescue by hand.
        # Exempting mutations from dedup is only correct when the mutation's
        # body will actually DIVERGE at replay — i.e. it consumes a dynamic
        # lineage var via assign (consumer_needs), so its two occurrences
        # will get different values injected even though the CAPTURED
        # literal body looks identical (the double-audit case: same
        # audit_ids field name, different audit_id at replay). A mutation
        # with NO dynamic wiring at all and an identical literal body is a
        # genuinely different situation — most likely an accidental
        # double-click/double-submit captured in the session — and should
        # still be caught by the mutation_between check below, same as a
        # pure read. Blanket-exempting every mutation would silently hide
        # that signal and let the scenario replay a duplicate business
        # mutation with nothing flagging it for review.
        if is_mutation(row["path"]) and consumer_needs.get(row["idx"]):
            continue
        key = (row["path"], json.dumps(_req_of(parsed, row["idx"]), sort_keys=True, ensure_ascii=False))
        if key in dup_seen:
            prior_idx = dup_seen[key]
            if mutation_between(prior_idx, row["idx"]):
                row["reason"] += ("; " if row["reason"] else "") + \
                    f"repeat of idx={prior_idx} but a mutation ran in between — kept, not collapsed"
                dup_seen[key] = row["idx"]   # advance so a THIRD repeat compares against this one
            else:
                row["dup_of"] = prior_idx
        else:
            dup_seen[key] = row["idx"]

    # Soft hints: responses whose data is a non-empty list/object are candidates
    # for *wholesale* extraction (e.g. confirm_list, customer_file_list). The
    # scalar lineage graph cannot see these; the model must wire them by judgment.
    bulk_candidates = []
    for p in parsed:
        if p["resp"] is None:
            continue
        data = (p["resp"].get("data") if isinstance(p["resp"], dict) else None)
        if isinstance(data, list) and data:
            bulk_candidates.append({"idx": p["idx"], "path": p["path"],
                                    "expression": "$.response_body.data",
                                    "shape": f"list[{len(data)}]"})
        elif isinstance(data, dict) and any(isinstance(v, list) and v for v in data.values()):
            keys = [k for k, v in data.items() if isinstance(v, list) and v]
            bulk_candidates.append({"idx": p["idx"], "path": p["path"],
                                    "expression": "$.response_body.data",
                                    "shape": "dict with list fields: " + ", ".join(keys[:5])})

    # Missing-producer (gap) detection — ids consumed but produced nowhere in
    # this capture AND not matched to an external declaration. If a catalog is
    # supplied, suggest the query endpoint that could resolve each gap (insert
    # as a context-fetch step). This is now a PURELY internal concept: an id
    # the business process needs but this capture's traffic doesn't show how
    # to get. It is never "this should be a config.var" — that branch was
    # already removed upstream by the external-value match above.
    missing = []
    catalog = load_json_or_empty(args.catalog, "catalog")
    for val, occurrences in consumed_for_gap.items():
        first_idx, first_field, first_path = occurrences[0]
        entry = {"value": val, "consumer_idx": first_idx, "field": first_field,
                 "consumer_path": first_path,
                 "occurrences": [{"consumer_idx": ci, "field": f, "consumer_path": cp}
                                for ci, f, cp in occurrences],
                 "suggestions": []}
        if catalog:
            for r in catalog.get("resolution_index", {}).get(first_field, []):
                entry["suggestions"].append({"endpoint": r["endpoint"],
                                             "path": r["path"], "inputs": r["inputs"]})
        missing.append(entry)

    # Positional-extract risk pass: every lineage producer path that goes
    # through an array index is replay-fragile. Rank risk: an element at
    # position > 0, or an array with more than one element, is HIGH (the
    # exact audit[0] ordering-drift class); a single-element array is LOW
    # but still recorded — one element in THIS capture doesn't mean one at
    # replay time (a second audit record appearing is precisely how the
    # original bug manifested).
    positional_risks = []
    seen_risk = set()
    for e in lineage:
        key = (e["producer_idx"], e["producer_path"])
        if key in seen_risk:
            continue
        seen_risk.add(key)
        resp = parsed[e["producer_idx"]]["resp"]
        info = positional_risk_of(resp, e["producer_path"], noise_keys)
        if info is None:
            continue
        arr_len, pos, disc = info
        positional_risks.append({
            "producer_idx": e["producer_idx"],
            "producer_path": e["producer_path"],
            "field": e["field"],
            "array_len": arr_len,
            "position": pos,
            "risk": "high" if (arr_len > 1 or pos > 0) else "low",
            "element_discriminators": disc,
            "consumers": sorted({e2["consumer_idx"] for e2 in lineage
                                 if (e2["producer_idx"], e2["producer_path"]) == key}),
        })

    report = {
        "summary": {
            "total_records": n,
            "business_host": business_host,
            "unique_paths": len(path_freq),
            "kept": sum(1 for r in rows if r["decision"] == "KEEP"),
            "dropped": sum(1 for r in rows if r["decision"] == "DROP"),
            "lineage_edges": len(lineage),
            "external_matches": len(ignored_external),
            "open_gaps": len(missing),
            "scaffold_used": bool(scaffold),
            "noise_keys_loaded": len(noise_keys),
        },
        "host_counts": dict(host_counts),
        "path_frequency": path_freq.most_common(),
        "records": rows,
        "lineage": lineage,
        "bulk_extract_candidates": bulk_candidates,
        "missing_producers": missing,
        "ignored_external": ignored_external,
        "positional_extract_risks": positional_risks,
        "canonicalized_values": canonicalized_values,
        "value_reuse_suspects": value_reuse_suspects,
        "business_code_warnings": business_code_warnings,
        "unclassified_verbs": unclassified_verbs,
    }

    out_path = args.out or (args.ndjson.rsplit(".", 1)[0] + ".flow.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {out_path}")

    md_path = args.md or (args.ndjson.rsplit(".", 1)[0] + ".flow.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_md(report))
    print(f"[ok] wrote {md_path}")

    s = report["summary"]
    print(f"[summary] {s['kept']} keep / {s['dropped']} drop / "
          f"{s['lineage_edges']} lineage edges / {s['external_matches']} external matches / "
          f"{s['open_gaps']} open gaps over {s['total_records']} records")


def _slim(p):
    return {"idx": p["idx"], "path": p["path"], "method": p["method"], "status": p["status"]}


def _req_of(parsed, idx):
    return parsed[idx]["req"]


def render_md(report):
    s = report["summary"]
    out = []
    out.append("# Flow analysis\n")
    out.append(f"- records: **{s['total_records']}**  business host: `{s['business_host']}`")
    out.append(f"- keep: **{s['kept']}**  drop: **{s['dropped']}**  unique paths: {s['unique_paths']}")
    out.append(f"- lineage edges: **{s['lineage_edges']}**  "
               f"external matches: **{s['external_matches']}**  "
               f"open gaps: **{s['open_gaps']}**")
    out.append(f"- scaffold used: {s['scaffold_used']}  noise keys loaded: {s['noise_keys_loaded']}\n")

    out.append("## Kept steps (in order)\n")
    out.append("| idx | path | reason | dup_of |")
    out.append("|----:|------|--------|:------:|")
    for r in report["records"]:
        if r["decision"] == "KEEP":
            out.append(f"| {r['idx']} | `{r['path']}` | {r['reason']} | "
                       f"{r.get('dup_of','')} |")

    out.append("\n## Lineage edges (suggested extract -> assign)\n")
    out.append("| value | producer idx | extract expression | consumer idx | assign target |")
    out.append("|-------|:-----------:|--------------------|:-----------:|---------------|")
    for e in report["lineage"]:
        out.append(f"| `{e['value']}` | {e['producer_idx']} | `{e['producer_path']}` | "
                   f"{e['consumer_idx']} | `{e['consumer_path']}` |")

    ext = report.get("ignored_external", [])
    if ext:
        out.append("\n## External matches — left untouched, will be filled at assemble stage\n")
        out.append("| idx | field | consumer_path | value | declared as |")
        out.append("|----:|-------|----------------|-------|-------------|")
        for e in ext:
            out.append(f"| {e['idx']} | `{e['field']}` | `{e['consumer_path']}` | `{e['value']}` | "
                       f"{', '.join(e['declared_as'])} |")

    miss = report.get("missing_producers", [])
    if miss:
        out.append("\n## Open gaps — internal id with no producer in this capture\n")
        out.append("Insert a context-fetch step via script_gap_resolve.py.\n")
        out.append("| value | needed by idx | field | suggested lookup (endpoint -> path) |")
        out.append("|-------|:------------:|-------|--------------------------------------|")
        for m in miss:
            sug = m["suggestions"][0] if m["suggestions"] else None
            s2 = f"`{sug['endpoint']}` -> `{sug['path']}`" if sug else "_(none in catalog)_"
            out.append(f"| `{m['value']}` | {m['consumer_idx']} | `{m['field']}` | {s2} |")

    risks = report.get("positional_extract_risks", [])
    high = [r for r in risks if r["risk"] == "high"]
    if risks:
        out.append("\n## [WARN] Positional extract risks — array-index paths are replay-fragile\n")
        out.append("An extract like `data.audit[0].audit_id` is verified against THIS capture "
                   "only; at replay the array may be re-ordered or grown and `[0]` resolves to "
                   "the wrong element. For each: verify position stability, or replace with a "
                   "filtered query endpoint, or add an assertion on a discriminator field.\n")
        out.append("| risk | producer idx | extract path | array len | pos | element discriminators | consumers |")
        out.append("|------|:-----------:|--------------|:---------:|:---:|------------------------|-----------|")
        for r in sorted(risks, key=lambda x: (x["risk"] != "high", x["producer_idx"])):
            disc = ", ".join(f"{k}={v}" for k, v in list(r["element_discriminators"].items())[:5]) or "—"
            out.append(f"| {'**HIGH**' if r['risk']=='high' else 'low'} | {r['producer_idx']} | "
                       f"`{r['producer_path']}` | {r['array_len']} | {r['position']} | {disc} | "
                       f"{', '.join(map(str, r['consumers']))} |")

    cv = report.get("canonicalized_values", [])
    if cv:
        out.append("\n## Canonicalized values — merged to one stable producer/var\n")
        out.append("A value produced at multiple points across DIFFERENT endpoints (or the "
                   "same endpoint with no mutation in between) is treated as one stable "
                   "whole-flow entity: every consumer is rewired to the single least-risky "
                   "producer below, and the other producer occurrences lose their lineage "
                   "role (they'll likely drop as pure reads).\n")
        out.append("| value | canonical producer idx | canonical extract path | merged from |")
        out.append("|-------|:----------------------:|-------------------------|-------------|")
        for c in cv:
            merged = "; ".join(f"idx={m['idx']} `{m['path']}`" for m in c["merged_from"])
            out.append(f"| `{c['value']}` | {c['canonical_producer_idx']} | "
                       f"`{c['canonical_producer_path']}` | {merged} |")

    vrs = report.get("value_reuse_suspects", [])
    if vrs:
        out.append("\n## [WARN] Value reuse suspects — NOT merged, needs manual review\n")
        out.append("Same value produced twice by the SAME endpoint with a mutation in "
                   "between — looks like an entity that should have changed but didn't "
                   "(e.g. an already-processed record's id being returned again). Left as "
                   "separate producers/vars on purpose; verify this isn't a real bug before "
                   "wiring or merging by hand.\n")
        out.append("| value | producers | suspect pairs (idx, idx) |")
        out.append("|-------|-----------|---------------------------|")
        for s in vrs:
            prods = "; ".join(f"idx={p['idx']} `{p['path']}`" for p in s["producers"])
            pairs = ", ".join(f"({a},{b})" for a, b in s["suspect_pairs"])
            out.append(f"| `{s['value']}` | {prods} | {pairs} |")

    uv = report.get("unclassified_verbs", {})
    if uv:
        out.append("\n## [WARN] Unrecognized endpoint verbs — kept conservatively, extend verb lists\n")
        out.append("These path segments matched neither READ_SUFFIX nor MUTATION_VERBS. They "
                   "are KEPT as possible state changes (dropping an unrecognized mutation "
                   "amputates the flow; keeping an unrecognized read is cheap). Classify each "
                   "one: if it's a mutation, add its verb to MUTATION_VERBS; if it's a read, "
                   "add its suffix to READ_SUFFIX; then re-run.\n")
        out.append("| verb segment | paths | record idxs |")
        out.append("|--------------|-------|-------------|")
        for verb, info in uv.items():
            paths = "; ".join(f"`{p}`" for p in info["paths"])
            out.append(f"| `{verb}` | {paths} | {', '.join(map(str, info['idxs']))} |")

    bcw = report.get("business_code_warnings", [])
    if bcw:
        out.append("\n## [WARN] Suspicious business codes (HTTP 200 but envelope code != success)\n")
        out.append("| idx | path | code |")
        out.append("|----:|------|------|")
        for w in bcw:
            out.append(f"| {w['idx']} | `{w['path']}` | `{w['code']}` |")

    out.append("\n## Dropped paths (noise) — frequency\n")
    dropped_paths = Counter(r["path"] for r in report["records"] if r["decision"] == "DROP")
    out.append("| count | path |")
    out.append("|------:|------|")
    for path, c in dropped_paths.most_common():
        out.append(f"| {c} | `{path}` |")
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    main()
