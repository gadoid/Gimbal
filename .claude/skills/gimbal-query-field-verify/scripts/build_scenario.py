#!/usr/bin/env python3
"""build_scenario.py (v2 — gimbal-query-field-verify, yhr step shape only)

Stage 3 of gimbal-query-field-verify. Mechanical fold: samples.json →
steps.json (the only artifact this skill emits), plus cases.json (durable)
and coverage.md (report scaffold).

Inputs:
  * mapping.json   — Stage 1 output
  * samples.json   — Stage 2 output
  * scaffold       — a user-provided GIMBAL scenario JSON with `steps: []`
                      and kind/scenarioId/meta/config/resource filled.

The scaffold is read-only. The skill reads `steps[0].api` (the api
template: method, path, headers, timeout) and resolves `api.service`
from `config.services` (or --service-name). The skill writes
`kind`/`scenarioId`/`meta`/`config`/`resource` nowhere — those are
the scaffold owner's responsibility.

Default emit is steps-only: `{"steps": [...]}`. Pass --emit full to
splice the steps into the scaffold and write a complete scenario.json
(Legacy mode for old callers; the preferred path is the caller-side
`jq` one-liner in SKILL.md "Stage 4").

Usage:
  python build_scenario.py \
      --mapping mapping.json --samples samples.json \
      --url    "<baseline URL>" \
      --scaffold <user scenario.json> \
      [--only param1,param2,...] \
      [--emit {steps-only|full}]    # default: steps-only
      [--service-name KEY]            # default: first under config.services
      [--user-name    KEY]            # informational only (not injected)
      --out steps.json
      --cases cases.json
      --report-md coverage.md
"""
from __future__ import annotations

import argparse, copy, datetime, json, sys
from urllib.parse import urlsplit, parse_qsl

LOW_CARD_RELAX = 3           # ENUM cardinality ≤ this → ② uses <=
PAGE_SIZE = 5                # ④ first-page window
NEG_DATE = "1970-01-01"


# ---------- body templating (no scaffold mutation) ----------------------

def baseline_body_pairs(url):
    """Baseline body as {key: str}. Blank strings preserved —
    empty-but-present defaults (`search_company=""`) must survive
    because the PHP/ThinkPHP backend treats a missing key as
    inheriting the previous filter.

    Trailing `[]` is stripped from array-typed keys (e.g.
    `search_time[charge_pay_date][]` → `search_time[charge_pay_date]`)
    so that DATE_RANGE / multi-select overrides can replace the empty
    baseline value under the SAME key (a Python list under
    `search_time[charge_pay_date]`) — otherwise we'd end up with two
    keys (`...[]` and the no-bracket form) in the body and the form
    serializer would emit both, muddying the request.

    URL parsing order is dropped (the yhr harness re-serialises by
    key anyway)."""
    sp = urlsplit(url)
    out = {}
    for k, v in parse_qsl(sp.query, keep_blank_values=True):
        # normalise `foo[]` → `foo` so override keys (no `[]`) collide
        k = k[:-2] if k.endswith("[]") else k
        # last-write-wins for genuinely duplicated keys (rare)
        out[k] = v
    return out


def body_for_case(baseline, override):
    """Merge baseline + this-case override → dict. Override keys replace
    the baseline value. List-valued overrides (DATE_RANGE [start, end],
    multi-select `service_types=[1,2]`) are kept as a Python list under
    the SAME key — the yhr form serializer expands `key=[v1,v2]` into
    `key[]=v1&key[]=v2` (or `key=v1&key=v2`), matching the PHP/ThinkPHP
    array convention used in the captured baseline URL. Overriding a
    list-typed field overwrites the baseline single value (which is the
    expected behaviour — empty `search_company=""` must NOT survive
    when this case is filtering by `service_types`)."""
    out = dict(baseline)
    for k, v in override.items():
        out[k] = v
    return out


# ---------- override + negative construction (mirror sample_fields) -----

def build_query_override(entry, sample):
    """Return this case's OVERRIDE body map {key: value|list-of-values}."""
    p, cat = entry["param"], entry["category"]
    if cat == "DATE_RANGE":
        d = sample["canon"][:10]
        if entry.get("granularity") == "datetime":
            return {p: [f"{d} 00:00:00", f"{d} 23:59:59"]}
        return {p: [d, d]}
    if entry.get("multi"):
        return {p: sample["query_code"]}
    return {p: sample["query_code"]}


def negative_value(entry, sample):
    """Construct a value guaranteed to return 0 rows. ENUMs have a closed
    domain so we skip ⑤ for them."""
    if entry["category"] == "DATE_RANGE":
        return NEG_DATE
    if entry["category"] == "ENUM":
        return None
    return f"{sample['query_code']}_NOTEXIST_gimbal"


def scaffold_has_response_body_extract(scaffold):
    """True iff the emitted steps do NOT need their own `extract
    response_body` strategy — i.e. some upstream mechanism already
    hoists `response_body` into scope.

    Two conditions trigger this:
      1. Any step in the scaffold's `steps[]` already carries a strategy
         with `kind == "extract"` and `target == "response_body"`.
      2. The `gimbal-response-body-extract` plugin is the default-on
         (it lives at plugins/response_body_extract/), so every step's
         scratch will already have `response_body` after the HTTP call.
         Without this gate, the skill's emit would add a redundant
         extract AND it would collide with itself across steps (the
         extract tries to promote to scope=scenario on every step, but
         the second step's promotion is REJECTED — the framework throws
         `PromotionRejected` for already-set vars without
         `allow_overwrite=True`).
    """
    for st in (scaffold.get("steps") or []):
        for strat in (st.get("strategy") or []):
            if (strat.get("kind") == "extract"
                    and strat.get("target") == "response_body"):
                return True
    # Default: assume the plugin is active (it ships in this repo at
    # plugins/response_body_extract/ and is wired into bootstrap as a
    # built-in). The plugin writes at step scope; our assertions read
    # from step scratch — both are compatible without any extract
    # strategy in the emitted step.
    return True


# ---------- step emission (yhr schema, scaffold-derived template) ------

def emit_step(case, baseline, api_template, *, emit_extract=True):
    """Build the yhr-shape step dict for one (param, sample) case.

    `emit_extract=False` skips the trailing `extract response_body`
    strategy — used when the scaffold already carries one (dedupe;
    see `scaffold_has_response_body_extract`)."""
    e = case["expect"]
    count_op = "le" if e["count_op"] == "le" else "lt"
    body = body_for_case(baseline, case["query_override"])
    desc = f"查询[{case['cn_name'] or case['param']}]={e['rows_display_value']}"

    api = copy.deepcopy(api_template)   # inherited from scaffold.steps[0]
    api.setdefault("kind", "api")
    api.setdefault("timeout", 30)

    strategy = [
        # ① HTTP 200 — abort on mismatch (otherwise ②/③ silently
        #    pass the "no list" state — the canonical backend-error
        #    smell).
        {
            "kind": "assertion",
            "name": "assert_http_status_eq_200",
            "phase": "verifying",
            "order": 0,
            "enabled": True,
            "onFailure": "abort",
            "target": "$.response_status",
            "operator": "eq",
            "expected": 200,
            "message": f"{desc} 应返回200",
            "soft": False,
        },
        # ② count shrinks (engine enum names: lt / lte; not < / <=)
        #    onFailure=continue: we want to see all per-field verdicts
        #    even when the count check fails (a non-shrinking count is
        #    itself the verdict we want to record).
        {
            "kind": "assertion",
            "name": "assert_count_shrinks",
            "phase": "verifying",
            "order": 1,
            "enabled": True,
            "onFailure": "continue",
            "target": "$.response_body.count",
            "operator": "lte" if count_op == "le" else "lt",
            "expected": e["count_baseline"],
            "message": "①count_shrinks: 相等意味着过滤参数被后端忽略",
            "soft": True,
        },
        # ③ anchor present (engine supports `contains` against a list[*] target)
        #    onFailure=continue: ANCHOR may legitimately be filtered out
        #    by a different filter dimension (the row exists in the DB
        #    but doesn't match THIS filter) — that's a real verdict, not
        #    a step-level abort condition.
        {
            "kind": "assertion",
            "name": "assert_anchor_present",
            "phase": "verifying",
            "order": 2,
            "enabled": True,
            "onFailure": "continue",
            "target": "$.response_body.list[*].id",
            "operator": "contains",
            "expected": e["anchor_row_id"],
            "message": "②anchor_present: 已知记录必须可查到",
            "soft": True,
        },
        # ④ row-match decomposed into one `contains` assertion per
        #    response_field against list[*].<field>. The engine has no
        #    row-by-row comparator (the schema/AssertOperator.SCHEMA enum
        #    member has no _evaluate() handler), so we fall back to N
        #    contains() calls — each fires on the entire list[*].<field>
        #    array and asserts the canonical value appears at least once.
        #    ENUM (closed-domain) gets a contains check; FUZZY (substring
        #    match) also gets contains; DATE_RANGE gets a gte+ lte pair
        #    on the date field — but DATE_RANGE comparison is non-trivial
        #    and engine-side there is no between() operator, so we emit
        #    a contains against the YYYY-MM-DD substring.
    ]

    response_fields = (case.get("response_fields")
                       or ([case["response_field"]] if case.get("response_field") else []))
    for idx, rf in enumerate(response_fields):
        strategy.append({
            "kind": "assertion",
            "name": f"assert_field_{rf}_contains_canon",
            "phase": "verifying",
            "order": 3 + idx,
            "enabled": True,
            # onFailure=continue: a fuzzy search (e.g. `wd=...`) may match
            # a row through one column (order_no) but NOT another (bl_no).
            # Each per-field verdict is independent — we want the full
            # picture, not a hard-stop on the first miss.
            "onFailure": "continue",
            "target": f"$.response_body.list[*].{rf}",
            "operator": "contains",
            "expected": e["rows_canon_value"],
            "message": f"③rows_match: 首页 list[*].{rf} 应包含 {e['rows_display_value']}",
            "soft": True,
        })

    # ⑤ negative — only when meaningful (non-enum categories).
    if case.get("negative"):
        strategy.append({
            "kind": "assertion",
            "name": "assert_negative_count_zero",
            "phase": "verifying",
            "order": 3 + len(response_fields),
            "enabled": True,
            "onFailure": "continue",
            "target": "$.response_body.count",
            "operator": "eq",
            "expected": 0,
            "message": "④negative: 不存在的值应返回 0 条",
            "soft": True,
        })

    # ⑥ extract response_body — only if the scaffold doesn't already
    #    hoist it (see scaffold_has_response_body_extract). Without
    #    this gate, every emitted step would re-emit an extract that
    #    overwrites the same `vars.response_body` slot the seed step
    #    has already populated.
    if emit_extract:
        strategy.append({
            "kind": "extract",
            "name": "extract_response_body",
            "phase": "after_request",
            "order": 0,
            "enabled": True,
            "onFailure": "abort",
            "expression": "$.response_body",
            "target": "response_body",
            "required": True,
            "default": None,
            "scope": "scenario",
        })

    return {
        "kind": "step",
        "description": desc,
        "api": api,
        "request": {"kind": "request",
                    # body is a dict; list-valued keys (DATE_RANGE
                    # [start,end], multi-select) survive as lists and
                    # are expanded by the form serializer at request
                    # time. Single-value keys stay as strings.
                    "body": body},
        "strategy": strategy,
    }


# ---------- driver -------------------------------------------------------

def _first_key(d):
    for k in d or {}:
        return k
    return None


def _parse_only(spec):
    if not spec:
        return None
    return {x.strip() for x in spec.split(",") if x.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--samples", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--scaffold", required=True,
                    help="user-provided GIMBAL scenario JSON. Read-only: "
                         "the script uses steps[0].api and config.services/"
                         "config.users for resolution but NEVER writes back.")
    ap.add_argument("--emit", choices=["steps-only", "full"],
                    default="steps-only")
    ap.add_argument("--service-name",
                    help="config.services key (default: first)")
    ap.add_argument("--user-name",
                    help="config.users key (informational; not injected "
                         "into api.headers)")
    ap.add_argument("--only", default=None,
                    help="comma-separated whitelist of params; TESTABLE "
                         "params not listed are recorded as "
                         "EXCLUDED_BY_USER in coverage.md")
    ap.add_argument("--out", default="steps.json")
    ap.add_argument("--cases", default="cases.json")
    ap.add_argument("--report-md", default="coverage.md")
    args = ap.parse_args()

    mapping = json.load(open(args.mapping, encoding="utf-8"))
    samples = json.load(open(args.samples, encoding="utf-8"))
    scaffold = json.load(open(args.scaffold, encoding="utf-8"))

    B = samples["baseline_count"]
    by_param = {p["param"]: p for p in mapping["params"]}
    baseline = baseline_body_pairs(args.url)

    # ---- service resolution from scaffold (read-only) ----------------
    services = (scaffold.get("config") or {}).get("services") or {}
    service_name = args.service_name or _first_key(services)
    if not service_name:
        sys.exit("scaffold has no config.services; pass --service-name")

    # ---- api template (deep-copy, read-only) ------------------------
    try:
        api_template = copy.deepcopy(scaffold["steps"][0]["api"])
    except (KeyError, IndexError, TypeError) as exc:
        sys.exit(f"scaffold.steps[0].api missing or malformed: {exc}")
    api_template["service"] = service_name

    # ---- optional whitelist -----------------------------------------
    only = _parse_only(args.only)

    # ---- bake the case table ----------------------------------------
    cases, skipped = [], []
    for param, bucket in samples["fields"].items():
        entry = by_param[param]
        # Accept either legacy "SAMPLED" (from sample_fields.py) or
        # "REAL_SAMPLED" (from sample_from_real.py). Both signal "we
        # have at least one canon-anchored sample ready for assertion".
        if bucket["status"] not in ("SAMPLED", "REAL_SAMPLED"):
            skipped.append({"param": param, "cn_name": entry.get("cn_name", ""),
                            "reason": f"NO_SAMPLE(scanned="
                                      f"{bucket.get('scanned', '?')})"})
            continue
        if only is not None and param not in only:
            skipped.append({"param": param, "cn_name": entry.get("cn_name", ""),
                            "reason": "EXCLUDED_BY_USER(--only)"})
            continue
        vm_size = len(entry.get("value_map", {}) or {})
        count_op = "<=" if (entry["category"] == "ENUM"
                            and vm_size <= LOW_CARD_RELAX) else "<"
        for i, s in enumerate(bucket["samples"]):
            cq = s.get("canon")
            if cq in (None, ""):
                continue
            neg = negative_value(entry, s)
            cases.append({
                "case_id": f"{param}__{i}",
                "param": param,
                "cn_name": entry.get("cn_name", ""),
                "category": entry["category"],
                "response_field": entry.get("response_field"),
                "response_fields": entry.get("response_fields") or [],
                "query_override": build_query_override(entry, s),
                "expect": {
                    "count_op": "le" if count_op == "<=" else "lt",
                    "count_baseline": B,
                    "anchor_row_id": s["row_id"],
                    "anchor_order_id": s["order_id"],
                    "rows_display_value": str(s["value"]).strip(),
                    "rows_canon_value": s["canon"],
                },
                "negative": ({"query_value": neg, "expect_count": 0}
                             if neg else None),
            })

    json.dump({"generated": datetime.datetime.now().astimezone().isoformat(),
               "baseline_url": args.url, "baseline_count": B,
               "page_size": PAGE_SIZE, "cases": cases},
              open(args.cases, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    emit_extract = not scaffold_has_response_body_extract(scaffold)
    steps = [emit_step(c, baseline, api_template,
                       emit_extract=emit_extract) for c in cases]

    if args.emit == "steps-only":
        # Default. ONLY steps. Caller owns the surrounding scaffold.
        out_payload = {"steps": steps}
    else:
        # Legacy. Splice steps into the scaffold's surrounding shell.
        # The caller MUST pass a TEMPLATE scaffold (not their hand-curated
        # production scenario) when using this mode.
        scenario = copy.deepcopy(scaffold)
        scenario["steps"] = steps
        scenario.setdefault("meta", {})
        meta = scenario["meta"]
        meta["source"] = "gimbal-query-field-verify skill (v2)"
        meta.setdefault("baseline_count", B)
        out_payload = scenario

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)

    testable = [p for p in mapping["params"] if p["status"] == "TESTABLE"]
    covered = {c["param"] for c in cases}
    with open(args.report_md, "w", encoding="utf-8") as f:
        f.write(f"# 查询字段校验覆盖报告 — {mapping['endpoint']}\n\n")
        f.write(f"- 可测字段(分母): {len(testable)}\n")
        f.write(f"- 有样本、已生成用例: {len(covered)} "
                f"({len(covered)}/{len(testable)} = "
                f"{100 * len(covered) // max(len(testable), 1)}%)\n")
        f.write(f"- 用例行数: {len(cases)} (字段×互异样本)\n")
        f.write(f"- baseline_count: {B}, 首页校验窗口 size={PAGE_SIZE}\n\n")
        f.write("## 用户场景文件不写字段(skill 不 emit)\n\n")
        f.write("- `kind`\n- `scenarioId`\n- `meta.*`\n"
                "- `config.{setup,teardown,services,users,vars,timePolicy,retry}`\n"
                "- `resource`\n\n")
        f.write("## 覆盖明细(执行后回填 PASS/FAIL)\n\n")
        f.write("| 字段 | 中文名 | 类别 | 样本数 | ① | ② | ③ | ④ |\n"
                "|---|---|---|---|---|---|---|---|\n")
        seen = set()
        for c in cases:
            if c["param"] in seen:
                continue
            seen.add(c["param"])
            n = sum(1 for x in cases if x["param"] == c["param"])
            f.write(f"| `{c['param']}` | {c['cn_name']} | {c['category']} "
                    f"| {n} | | | | |\n")
        f.write(f"\n## 跳过清单 ({len(skipped)})——数据缺口或被 --only 排除\n\n")
        for s in skipped:
            f.write(f"- `{s['param']}` {s['cn_name']}: {s['reason']}\n")
        others = [p for p in mapping["params"]
                  if p["status"] != "TESTABLE"]
        f.write(f"\n## 不在分母的参数 ({len(others)})\n\n")
        for p in others:
            f.write(f"- `{p['param']}` [{p['status']}] "
                    f"{p.get('cn_name', '')}\n")
    print(f"emit={args.emit} cases={len(cases)} steps={len(steps)} "
          f"fields_covered={len(covered)}/{len(testable)} "
          f"skipped={len(skipped)} out={args.out}"
          + ("  [extract_response_body suppressed — scaffold already has one]"
             if not emit_extract else ""))


if __name__ == "__main__":
    main()
