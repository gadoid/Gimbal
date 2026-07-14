#!/usr/bin/env python3
"""parse_form.py — probe & map: form HTML + baseline URL + baseline response
→ mapping.json (the reviewable judgment boundary).

Three sources are cross-referenced:
  * baseline URL      → the complete param universe + non-empty defaults
  * form HTML         → value maps (code↔label), multi-select flags, hidden flags
  * baseline response → auth block (per-account queryability), keys/names
                        (response_field ↔ 中文名)

Usage:
  python parse_form.py --html form.html --url "https://…?page=1&…" \
      --auth-json baseline_response.json \
      [--overrides name-overrides.json] --out mapping.json --md mapping.md
"""
import argparse, json, re, sys
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qsl

EXCLUDED_PARAMS = {
    "page", "size", "order_ids", "bulk_query_type", "bulk_shutout_status",
    "bulk_query", "batch_exchange_query",
}
# params that are meta/global fuzzy search boxes; still testable, category FUZZY.
# placeholder text → response fields is resolved via overrides or the built-in map.
BUILTIN_FUZZY = {
    "wd":               ["order_no", "bl_no"],          # 按 订单号/提单号查询
    "port":             ["schedule_from_terminal", "schedule_to_terminal"],
    "search_company":   ["order_customer", "social_code"],
    "work_no":          ["work_no"],
    "order_customer_real": ["order_customer_real"],
    "booking_agent_bp": ["booking_agent_bp"],
    "booking_agent_bp_real": ["booking_agent_bp_real"],
    "order_business_no": ["order_business_no"],
}


class FormParser(HTMLParser):
    """Extract per-container: select options (value→label), multiple flag,
    hidden flag. Container id is the nearest ancestor div[id]."""

    def __init__(self):
        super().__init__()
        self.containers = {}          # id → {"multi":bool,"hidden":bool,"options":{}}
        self._div_stack = []          # (id_or_None, hidden)
        self._cur_container = None
        self._in_select = False
        self._select_multi = False
        self._opt_value = None
        self._opt_text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            hid = "display: none" in a.get("style", "") or \
                  "display:none" in a.get("style", "")
            self._div_stack.append((a.get("id"), hid))
            if a.get("id"):
                self._cur_container = a["id"]
                self.containers.setdefault(
                    a["id"], {"multi": False, "hidden": False, "options": {}})
                if hid:
                    self.containers[a["id"]]["hidden"] = True
        elif tag == "select" and self._cur_container:
            self._in_select = True
            self._select_multi = "multiple" in a
            self.containers[self._cur_container]["multi"] |= self._select_multi
        elif tag == "option" and self._in_select:
            self._opt_value = a.get("value", "")
            self._opt_text = []

    def handle_endtag(self, tag):
        if tag == "div" and self._div_stack:
            self._div_stack.pop()
            self._cur_container = next(
                (i for i, _ in reversed(self._div_stack) if i), None)
        elif tag == "select":
            self._in_select = False
        elif tag == "option" and self._opt_value is not None:
            label = "".join(self._opt_text).strip()
            if self._opt_value != "" and self._cur_container:
                self.containers[self._cur_container]["options"][
                    self._opt_value] = label
            self._opt_value = None

    def handle_data(self, data):
        if self._opt_value is not None:
            self._opt_text.append(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--auth-json", required=True,
                    help="a baseline response containing auth/keys/names")
    ap.add_argument("--overrides", default=None,
                    help="name-overrides.json: param → response_field(s)")
    ap.add_argument("--out", default="mapping.json")
    ap.add_argument("--md", default="mapping.md")
    args = ap.parse_args()

    # --- sources -----------------------------------------------------------
    fp = FormParser()
    fp.feed(open(args.html, encoding="utf-8").read())

    resp = json.load(open(args.auth_json, encoding="utf-8"))
    auth = {}
    for v in resp.get("auth", {}).values():   # {"c1": {...}} — merge all roles
        auth.update(v)
    keys, names = resp.get("keys", []), resp.get("names", [])
    field_cn = dict(zip(keys, names))
    field_set = set(keys)

    overrides = json.load(open(args.overrides, encoding="utf-8")) \
        if args.overrides else {}

    split = urlsplit(args.url)
    endpoint = f"{split.scheme}://{split.netloc}{split.path}"
    qsl = parse_qsl(split.query, keep_blank_values=True)
    baseline_defaults = {k: v for k, v in qsl
                         if v != "" and k not in ("page", "size")}

    # collapse search_time[x] / param[] to canonical param names, keep order
    seen, params_in_order = set(), []
    date_params = set()
    for k, _ in qsl:
        base = k[:-2] if k.endswith("[]") else k
        m = re.fullmatch(r"search_time\[([^\]]+)\]", base)
        if m:
            base = f"search_time[{m.group(1)}]"
            date_params.add(base)
        if base not in seen:
            seen.add(base)
            params_in_order.append(base)

    # container id → param name is 1:1 in this codebase except a few UI ids;
    # allow overrides to remap ("service"→param "service", etc.)
    containers = fp.containers

    out_params = []
    for p in params_in_order:
        entry = {"param": p}
        ov = overrides.get(p, {})

        # ---- category & value_map ----
        if p in date_params:
            f = re.fullmatch(r"search_time\[([^\]]+)\]", p).group(1)
            entry.update(category="DATE_RANGE", response_field=f,
                         granularity=ov.get("granularity", "date"))
        elif p in EXCLUDED_PARAMS:
            entry.update(category="EXCLUDED")
        else:
            c = containers.get(ov.get("container", p))
            if c and c["options"]:
                entry["category"] = "ENUM"
                entry["multi"] = c["multi"]
                entry["value_map"] = {k: v for k, v in c["options"].items()
                                      if k != "null"}
                if "null" in c["options"]:
                    entry["has_null_option"] = True   # NULL_QUERY variant exists
            elif p in BUILTIN_FUZZY or "response_fields" in ov:
                entry["category"] = "FUZZY"
                entry["response_fields"] = ov.get("response_fields",
                                                  BUILTIN_FUZZY.get(p, []))
            else:
                entry["category"] = "EXACT"

        # ---- response_field resolution ----
        if "response_field" not in entry and entry["category"] != "FUZZY":
            rf = ov.get("response_field") or (p if p in field_set else None)
            if rf:
                entry["response_field"] = rf

        # ---- cn_name ----
        rf = entry.get("response_field") or \
             (entry.get("response_fields") or [None])[0]
        entry["cn_name"] = ov.get("cn_name") or field_cn.get(rf, "")

        # ---- status ----
        c = containers.get(ov.get("container", p))
        if entry["category"] == "EXCLUDED":
            entry["status"] = "EXCLUDED"
        elif c and c["hidden"]:
            entry["status"] = "HIDDEN"
        elif auth and not auth.get(ov.get("auth_key", p), False) \
                and p not in date_params:
            # date params are gated by a single time_type/interval auth flag
            entry["status"] = "NO_AUTH"
        elif entry["category"] != "FUZZY" and "response_field" not in entry:
            entry["status"] = "UNMAPPED"
        elif entry["category"] == "FUZZY" and not entry["response_fields"]:
            entry["status"] = "UNMAPPED"
        else:
            entry["status"] = "TESTABLE"
        entry["source"] = {"auth": auth.get(p, None),
                           "hidden": bool(c and c["hidden"]),
                           "mapped_by": "override" if p in overrides
                           else ("same_name" if entry.get("response_field") == p
                                 else "builtin")}
        out_params.append(entry)

    mapping = {"endpoint": endpoint, "baseline_url": args.url,
               "baseline_defaults": baseline_defaults, "params": out_params}
    json.dump(mapping, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # ---- human review view ----
    by_status = {}
    for e in out_params:
        by_status.setdefault(e["status"], []).append(e)
    with open(args.md, "w", encoding="utf-8") as f:
        f.write(f"# mapping review — {endpoint}\n\n")
        for st in ("UNMAPPED", "TESTABLE", "NO_AUTH", "HIDDEN", "EXCLUDED"):
            rows = by_status.get(st, [])
            f.write(f"## {st} ({len(rows)})\n\n")
            for e in rows:
                vm = f" · {len(e.get('value_map', {}))} options" \
                    if e.get("value_map") else ""
                rf = e.get("response_field") or \
                    "/".join(e.get("response_fields", [])) or "?"
                f.write(f"- `{e['param']}` → `{rf}` "
                        f"[{e['category']}] {e.get('cn_name','')}{vm}\n")
            f.write("\n")
        if by_status.get("UNMAPPED"):
            f.write("> **UNMAPPED must be resolved (edit name-overrides.json, "
                    "re-run) before sampling.**\n")
    n_un = len(by_status.get("UNMAPPED", []))
    print(f"params={len(out_params)} testable="
          f"{len(by_status.get('TESTABLE', []))} unmapped={n_un}")
    sys.exit(1 if n_un else 0)


if __name__ == "__main__":
    main()
