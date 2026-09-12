"""注入条目物化(spec v3 §3)— 平台层 patch,引擎/plate 零改动。

与 run_materialize.py 同纪律:纯函数、深拷贝进深拷贝出、执行链唯一物化语义。
assertion_registry 条目在 plate convert 之前落进 definition(steps[si].strategy
追加 Assign 直补 + asserts patch),materialize_run_copy 其后照旧。
值注入与数据集 vars 注入完全解耦(正交叠加):compose 不触碰 config.vars。
"""
import copy
from typing import Any, Callable

from .jsonpath import exists


def entry_issues(
    entry: dict[str, Any],
    step_count: int,
    body_of: Callable[[int], Any],
    assert_targets_of: Callable[[int], set[str]],
) -> list[dict[str, Any]]:
    """悬空检测(前端 utils/assertion-registry.ts 的 Python 同构,spec v3 §2):
    旧形状条目(无 path)/ stepIndex 越界 / path 不落在该步 request body
    字段树(jsonpath.exists;str body 无可索引字段恒不可解析)/ override
    无匹配。"""
    issues: list[dict[str, Any]] = []
    path = entry.get("path")
    if not isinstance(path, dict):
        # v2 旧形状(anchor+injection)或残缺条目:全量 issue → skip(spec v3 §8)
        return [{"kind": "legacy-entry"}]
    si = path.get("stepIndex")
    jp = path.get("jsonpath")
    if not isinstance(si, int) or si < 0 or si >= step_count:
        issues.append({"kind": "step-oob", "stepIndex": si})
    elif not isinstance(jp, str) or not exists(body_of(si) or {}, jp):
        issues.append({"kind": "path-unresolvable", "stepIndex": si, "jsonpath": jp})
    for a in entry.get("asserts") or []:
        if isinstance(a, dict) and isinstance(a.get("stepIndex"), int):
            asi = a["stepIndex"]
            if asi < 0 or asi >= step_count:
                issues.append({"kind": "step-oob", "stepIndex": asi})
            elif a.get("mode") == "override" and a.get("target") not in assert_targets_of(asi):
                issues.append({"kind": "override-no-match",
                               "stepIndex": asi, "target": a.get("target")})
    return issues


def compose_injection_scenario(definition: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Assign 直补 + asserts patch(spec v3 §3)。config.vars 零触碰 —
    数据集行值合入在 _compose_scenario(与 Assign 正交叠加,偏离最后生效:
    字段恰为模板串时被字面量整体替换,该 case 内行值对此字段不再起效)。
    悬空项静默跳过 — dispatcher 层已先经 entry_issues 过滤,此处双保险。
    value 由用户显式编辑,原样覆写不 coerce(引擎 _resolve_source_value
    对非模板 source 直通)。
    """
    out = copy.deepcopy(definition)
    steps = out.get("steps") or []
    path = entry.get("path")
    if isinstance(path, dict):
        si = path.get("stepIndex")
        jp = path.get("jsonpath")
        if (isinstance(si, int) and 0 <= si < len(steps)
                and isinstance(jp, str) and jp.startswith("$")):
            # $.amount → $.request_body.amount;根 "$" → $.request_body
            target = "$.request_body" + (jp[1:] if jp != "$" else "")
            steps[si].setdefault("strategy", []).append(
                {"kind": "assign", "source": entry.get("value"), "target": target})
    for a in entry.get("asserts") or []:
        if not isinstance(a, dict):
            continue
        si = a.get("stepIndex")
        if not isinstance(si, int) or si < 0 or si >= len(steps):
            continue
        strat = steps[si].setdefault("strategy", [])
        if a.get("mode") == "override":
            for st in strat:
                if (isinstance(st, dict) and st.get("kind") == "assertion"
                        and st.get("target") == a.get("target")):
                    st["expected"] = a.get("expected")
        else:
            strat.append({"kind": "assertion", "target": a.get("target", ""),
                          "operator": a.get("operator", "eq"), "expected": a.get("expected")})
    return out
