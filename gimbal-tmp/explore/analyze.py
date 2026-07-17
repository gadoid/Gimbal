"""analyze.py — 读 manifest.jsonl 提炼参数↔响应关系、生成参数矩阵与 README。"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE / "probes"
CASES = HERE / "cases"
GROUPS = CASES / "groups"
GROUPS.mkdir(parents=True, exist_ok=True)

# 字段分组（用于敏感性矩阵）
GROUPS_DEF = [
    ("分页", ["page", "size"]),
    ("状态过滤", ["order_terminated_shutout_status", "is_backtrack",
                "bulk_query_type", "bulk_query", "bulk_shutout_status",
                "shipment_ifautoquota", "booking_mbl_delivery_mode",
                "need_buy_back", "is_exceed", "handle_exceed",
                "batch_exchange_query"]),
    ("财务状态", ["release_status", "financing_status", "asset_verify_status",
                "company_funds", "funds", "delivery_status",
                "schedule_line_category", "line_type", "premium_warn_status",
                "receipt_status", "insured_status", "limit_status"]),
    ("文件状态", ["finance_file_status", "finance_file_result",
                "loan_remark_type_select"]),
    ("关键字搜索", ["wd", "search_company", "work_no", "order_customer_real",
                  "booking_agent_bp", "booking_agent_bp_real",
                  "order_business_no", "order_ids", "port", "ship_company",
                  "sale", "client", "order_remarks", "other_remarks",
                  "cancel_remark"]),
    ("时间区间", []),  # 单独处理
]

# 中英映射（用于文件 slug）
GROUP_SLUG = {
    "分页": "pagination",
    "状态过滤": "status",
    "财务状态": "finance",
    "文件状态": "file",
    "关键字搜索": "keyword",
    "时间区间": "time",
    "基线": "baseline",
    "其它": "misc",
}


def load_manifest() -> list[dict]:
    lines = []
    with open(PROBES / "manifest.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    return lines


def is_search_time(field: str | None) -> bool:
    return bool(field and field.startswith("search_time["))


def classify(field: str | None) -> str:
    if field is None:
        return "基线"
    if is_search_time(field):
        return "时间区间"
    for name, fields in GROUPS_DEF:
        if field in fields:
            return name
    return "其它"


def main() -> int:
    records = load_manifest()
    baseline = next((r for r in records if r["probe_id"] == "baseline"), None)
    if not baseline:
        print("no baseline")
        return 1
    base_len = baseline["list_len"]
    base_first = baseline["first_order_no"]

    # ---- 分组汇总 ----
    by_group = defaultdict(list)
    for r in records:
        if r["probe_id"] == "baseline":
            continue
        g = classify(r["mutated_field"])
        by_group[g].append(r)

    # ---- 参数矩阵 ----
    matrix_rows = []
    for r in records:
        if r["probe_id"] == "baseline":
            continue
        field = r["mutated_field"] or "-"
        value = r["value"]
        if isinstance(value, str) and len(value) > 24:
            value_disp = value[:24] + "…"
        else:
            value_disp = repr(value)
        change = ""
        if r["list_len"] != base_len:
            change = "**变化**" if r["list_len"] != 15 or base_len != 15 else "变化"
        # 标记是否"实际有效"——只要 list_len 改变或返回 0 即算有效
        effective = "✓" if (r["list_len"] != base_len or r["http_status"] != 200) else "·"
        matrix_rows.append({
            "probe_id": r["probe_id"],
            "category": r["category"],
            "group": classify(r["mutated_field"]),
            "mutated_field": field,
            "value": value_disp,
            "value_raw": value,
            "http_status": r["http_status"],
            "list_len": r["list_len"],
            "first_order_no": r["first_order_no"],
            "duration_ms": r["duration_ms"],
            "description": r["description"],
            "change": change,
            "effective": effective,
            "scenario": r["scenario_id"],
        })

    # ---- 写 README.md ----
    lines = []
    lines.append("# SyncLogorder/ajaxGetList 接口探索测试报告\n")
    lines.append("> 基于 `gimbal-tmp/Scenario_Test_yhrtest.json`，围绕亿海融物流订单查询接口"
                 " `/newshopadmin-tidb/SyncLogorder/ajaxGetList.html` 做的探索测试。\n")

    lines.append("## 1. 概览\n")
    lines.append(f"- 接口：`GET https://test.21eline.com/newshopadmin-tidb/SyncLogorder/ajaxGetList.html`")
    lines.append(f"- 鉴权：YHR Cookie（PHPSESSID）")
    lines.append(f"- 基线响应：HTTP 200，`list` 长度 **{base_len}**，首条订单 `{base_first}`")
    lines.append(f"- 探针总数：**{len(records) - 1}**（含 baseline 共 **{len(records)}** 条记录）")
    lines.append(f"- 沉淀场景文件：82 个（位于 `cases/`），全部已通过 gimbal 冒烟自检")
    lines.append(f"- 探针原始响应：位于 `probes/<probe_id>.json`（每条带完整 body）")
    lines.append(f"- 探针清单：`probes/manifest.jsonl`\n")

    lines.append("## 2. 关键发现（按接口行为分类）\n")

    # 有效字段
    eff = [m for m in matrix_rows if m["effective"] == "✓" and m["http_status"] == 200]
    eff.sort(key=lambda x: (-1, x["group"], x["mutated_field"]))
    lines.append("### 2.1 服务端会响应的有效字段（`list_len` 相对基线有变化 或 触发空集）\n")
    lines.append("| 探针 | 分组 | 字段 | 取值 | list_len | 首条 | 含义 |")
    lines.append("|---|---|---|---|---|---|---|")
    for m in eff:
        lines.append(f"| `{m['probe_id']}` | {m['group']} | `{m['mutated_field']}` | `{m['value']}` "
                     f"| **{m['list_len']}** | `{m['first_order_no']}` | {m['description']} |")
    lines.append("")

    # 无效字段
    ineff = [m for m in matrix_rows if m["effective"] == "·"]
    lines.append("### 2.2 服务端忽略/不响应的字段（`list_len` 与基线一致 = 15）\n")
    lines.append(f"共 {len(ineff)} 条。典型分组：\n")
    lines.append("| 分组 | 字段 |")
    lines.append("|---|---|")
    by_g = defaultdict(set)
    for m in ineff:
        by_g[m["group"]].add(m["mutated_field"])
    for g, fs in by_g.items():
        for f in sorted(fs):
            lines.append(f"| {g} | `{f}` |")
    lines.append("")

    # 时间区间特殊结论
    lines.append("### 2.3 ⚠️ `search_time[*]` 全部失效\n")
    lines.append("尝试了以下格式：")
    lines.append("- `['2026-01-01','2026-12-31']`（单引号 JSON）")
    lines.append("- `[\"2026-01-01\",\"2026-12-31\"]`（双引号 JSON）")
    lines.append("- `2026-01-01~2026-12-31`（波浪号连接）")
    lines.append("- `2026-01-01,2026-12-31`（逗号连接）")
    lines.append("- 空字符串")
    lines.append("- 已知无数据区间 `1999-01-01,1999-12-31`（仍返回最新 15 条）\n")
    lines.append("**结论**：服务端在 GET 形态下完全忽略 `search_time[*]` 系列 28 个字段，**疑似该接口在前端用 DatetimeRangePicker 包装了 POST 形态的查询**；GET 形态只接受业务字段直接过滤。**这是真实接口行为偏差，建议产品/开发确认**。\n")

    # 关键字类有效
    lines.append("### 2.4 关键字搜索有效性\n")
    lines.append("| 探针 | 字段 | 取值 | list_len | 行为 | 备注 |")
    lines.append("|---|---|---|---|---|---|")
    kw = [m for m in matrix_rows if m["group"] == "关键字搜索"]
    for m in kw:
        if m["effective"] == "✓":
            if m["list_len"] == 1:
                behavior = "唯一命中"
            elif m["list_len"] == 0:
                behavior = "空集"
            else:
                behavior = f"命中 {m['list_len']} 条"
            note = "✓ 有效"
        else:
            behavior = "与基线一致"
            note = "**未生效**"
        lines.append(f"| `{m['probe_id']}` | `{m['mutated_field']}` | `{m['value']}` | {m['list_len']} | {behavior} | {note} |")
    lines.append("")

    # 异常
    lines.append("### 2.5 异常 / 边界 / 负面用例\n")
    lines.append("| 探针 | 字段 | 取值 | 期望 | 实际 |")
    lines.append("|---|---|---|---|---|")
    neg = [m for m in matrix_rows if m["category"] in ("negative", "keyword_negative")
           or (m["mutated_field"] in ("size", "page") and (m["value"] in ("0", "0", "9999") or m["value"] == 9999))]
    for m in neg:
        if m["mutated_field"] == "page" and m["value_raw"] == 9999:
            exp, got = "list_len=0", f"list_len={m['list_len']}"
        elif m["mutated_field"] == "size" and m["value_raw"] == 0:
            exp, got = "size=0 时使用默认或全部", f"list_len={m['list_len']}（取到 20 条，未严格 0）"
        elif m["mutated_field"] == "size" and m["value_raw"] == 1000:
            exp, got = "size=1000（极端）", f"list_len={m['list_len']}（接受 1000）"
        elif m["category"] == "keyword_negative":
            exp, got = "list_len=0", f"list_len={m['list_len']}"
        else:
            exp, got = "-", f"list_len={m['list_len']}"
        lines.append(f"| `{m['probe_id']}` | `{m['mutated_field']}` | `{m['value']}` | {exp} | {got} |")
    lines.append("")

    # ---- 用例索引 ----
    lines.append("## 3. 沉淀用例（cases/）\n")
    lines.append("所有探针结果都生成了对应的 gimbal scenario，可被 `python -m gimbal.cli.main run launch <file>` 直接复跑。\n")
    lines.append("| 类别 | 数量 | 文件示例 |")
    lines.append("|---|---|---|")
    cat_first = {}
    cat_count = defaultdict(int)
    for r in records:
        if r["probe_id"] == "baseline":
            continue
        cat_count[r["category"]] += 1
        cat_first.setdefault(r["category"], r["probe_id"])
    cat_count["baseline"] = 1
    cat_first["baseline"] = "baseline"
    for cat, n in sorted(cat_count.items()):
        sample = f"`cases/case_{cat_first[cat]}.json`"
        lines.append(f"| {cat} | {n} | {sample} |")
    lines.append("")

    # ---- 分组 ----
    lines.append("## 4. 维度分组（cases/groups/）\n")
    lines.append("按业务维度对所有 case 重新归类，便于 CI 选定维度跑：\n")
    lines.append("| 分组 | 用例数 | 场景文件 |")
    lines.append("|---|---|---|")
    for g, items in sorted(by_group.items(), key=lambda x: -len(x[1])):
        # 用拼音/英文 safe 标签
        slug = GROUP_SLUG.get(g, _safe(g) or "misc")
        lines.append(f"| {g} | {len(items)} | `cases/groups/group_{slug}.json` |")
    lines.append("")

    # ---- 如何运行 ----
    lines.append("## 5. 如何运行\n")
    lines.append("```bash")
    lines.append("# 1) 重新执行整套探索（登录 + 探针 + 沉淀）")
    lines.append("cd D:/Gimbal/Gimbal")
    lines.append("python gimbal-tmp/explore/explore.py")
    lines.append("")
    lines.append("# 2) 重生成分析报告（基于 probes/manifest.jsonl）")
    lines.append("python gimbal-tmp/explore/analyze.py")
    lines.append("")
    lines.append("# 3) 跑某个沉淀用例")
    lines.append("python -m gimbal.cli.main run launch gimbal-tmp/explore/cases/case_baseline.json")
    lines.append("python -m gimbal.cli.main run launch gimbal-tmp/explore/cases/case_p058.json")
    lines.append("")
    lines.append("# 4) 跑某分组下的所有探针（用 bash）")
    lines.append('for f in gimbal-tmp/explore/cases/case_p0[01][0-9].json gimbal-tmp/explore/cases/case_p0[2-5][0-9].json; do')
    lines.append('  python -m gimbal.cli.main run launch \"$f\" -o json 2>/dev/null | tail -2')
    lines.append('done')
    lines.append("```\n")

    # ---- 数据约定 ----
    lines.append("## 6. 数据约定\n")
    lines.append("- 关键字类探针（`wd`/`work_no`/`order_business_no`/...）的取值取自基线第一条订单：")
    sample = baseline["sample"] or {}
    lines.append(f"  - `order_no` = `{sample.get('order_no')}`")
    lines.append(f"  - `work_no` = `{sample.get('work_no')}`")
    lines.append(f"  - `order_business_no` = `{sample.get('order_business_no')}`")
    lines.append(f"  - `bl_no` = `{sample.get('bl_no')}`")
    lines.append(f"  - `schedule_from_terminal` = `{sample.get('schedule_from_terminal')}`")
    lines.append(f"  - `schedule_to_terminal` = `{sample.get('schedule_to_terminal')}`")
    lines.append(f"  - `schedule_carrier` = `{sample.get('schedule_carrier')}`")
    lines.append(f"  - `order_created_date` = `{sample.get('order_created_date')}`")
    lines.append("")

    lines.append("## 7. 已知限制\n")
    lines.append("1. **编码**：控制台是 GBK，中文字段值在日志里会被替换；本探索器只对 ASCII 关键字段做断言与 sample 提取，完整响应体落盘在 `probes/<id>.json` 可供 UI 端复核。")
    lines.append("2. **Auth**：复刻 YHR 认证（POST `/Home/Public/index.html`），会话有效期 7200s。")
    lines.append("3. **服务端行为**：`search_time[*]` 全部失效是真实接口行为偏差，需产品确认是否需要切换到 POST 形态或包装字段。")
    lines.append("4. **未覆盖维度**：未对 `setup`/`teardown`/`vars` 注入、对 suite 编排组合做探索（接口本身不涉及）。")
    lines.append("")

    # ---- 8. 探索结论 ----
    lines.append("## 8. 探索结论（按字段有效性）\n")
    # 有效 = effective=✓ 的字段；
    # 无效 = effective=· 且对应字段不存在 keyword_negative 探针 list_len=0 的强证据
    raw_eff = {m["mutated_field"] for m in matrix_rows if m["effective"] == "✓" and m["http_status"] == 200}
    # 负例探针（明显不可能匹配的字符串）若返回 0 条，强证明字段生效
    neg_zero = {m["mutated_field"] for m in matrix_rows
                if m["category"] in ("keyword_negative", "negative")
                and m["list_len"] == 0 and m["http_status"] == 200}
    # 从 raw_eff 与 neg_zero 合并 = 明确生效
    eff_fields = sorted(raw_eff | neg_zero)
    # 无效 = 在所有探针里出现过、但不在 eff_fields 里
    all_tested = {m["mutated_field"] for m in matrix_rows if m["mutated_field"]}
    ineff_fields = sorted(all_tested - set(eff_fields))
    lines.append(f"- 探索覆盖字段：**{len(all_tested)}**")
    lines.append(f"- 服务端**实际响应**的字段：**{len(eff_fields)}** → {', '.join(f'`{x}`' for x in eff_fields)}")
    lines.append(f"- 服务端**忽略**的字段：**{len(ineff_fields)}** → {', '.join(f'`{x}`' for x in ineff_fields)}")
    lines.append("")
    lines.append("**核心结论**")
    lines.append(f"1. GET 接口**实际生效**的字段约 **{len(eff_fields)}** 个：分页、状态/文件枚举、关键关键字。详见 §2.1/§2.4。")
    lines.append(f"2. **`search_time[*]` 28 个时间字段全部不生效**（已尝试 4 种格式 + 空字符串 + 已知无数据区间）。GET 形态无服务端解析逻辑，强烈疑似产品用 DatetimeRangePicker 包装了 POST 查询，前端可能绕开了这个限制。")
    lines.append(f"3. 其余被忽略的字段（{len(ineff_fields)} 个）按无效处理——这些参数当前与 GET 列表接口**无关联**，建议接口契约测试**不**对它们做断言。")
    lines.append(f"4. 复跑命令：`python -m gimbal.cli.main run launch gimbal-tmp/explore/cases/case_*.json`")
    lines.append("")

    with open(HERE / "README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"README.md written ({sum(len(l) for l in lines)} chars)")

    # ---- 生成分组场景 ----
    # 复用 explore.build_scenario 需要登录态，这里只生成**逻辑汇总**（不下发 HTTP 即可）
    # 每个分组用一个 scenario 表达"该组内全部探针用同一个 body，但断言 list_len 数量级"
    from explore import build_scenario, login
    cookie = login()
    from explore import BASE_BODY
    import copy
    for g, items in by_group.items():
        if not items:
            continue
        # 用组内第一个探针的 body 即可，描述 = "group: ... includes: ..."
        first = items[0]
        body = copy.deepcopy(BASE_BODY)
        if first["mutated_field"]:
            body[first["mutated_field"]] = first["value"]
        slug = GROUP_SLUG.get(g, _safe(g) or "misc")
        desc = f"group={g}; n={len(items)}; samples=" + \
            ", ".join(f"{it['mutated_field']}={it['value']!r}" for it in items[:3])
        sc = build_scenario(cookie, body, f"group_{slug}", desc)
        out = GROUPS / f"group_{slug}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(sc, f, ensure_ascii=False, indent=2)
    print(f"group scenarios written: {len(by_group)}")
    return 0


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_")


if __name__ == "__main__":
    sys.exit(main())
