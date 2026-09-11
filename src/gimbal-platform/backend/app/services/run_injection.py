"""注入条目物化(spec v2 §8)— 平台层 patch,引擎零改动。

与 run_materialize.py 同纪律:纯函数、深拷贝进深拷贝出、执行链唯一物化语义。
assertion_registry 条目在 plate convert 之前落进 definition(vars 覆写 +
strategy patch),materialize_run_copy 其后照旧(services/users/carry)。
"""
import copy
from typing import Any, Callable


def entry_issues(
    entry: dict[str, Any],
    step_count: int,
    var_names: set[str],
    assert_targets_of: Callable[[int], set[str]],
) -> list[dict[str, Any]]:
    """悬空检测(前端 utils/assertion-registry.ts 的 Python 同构):
    stepIndex 越界 / injection.varName ∉ vars / override 无匹配。"""
    issues: list[dict[str, Any]] = []
    idxs = set()
    anchor = entry.get("anchor")
    if isinstance(anchor, dict) and isinstance(anchor.get("stepIndex"), int):
        idxs.add(anchor["stepIndex"])
    for a in entry.get("asserts") or []:
        if isinstance(a, dict) and isinstance(a.get("stepIndex"), int):
            idxs.add(a["stepIndex"])
    for si in idxs:
        if si < 0 or si >= step_count:
            issues.append({"kind": "step-oob", "stepIndex": si})
    for inj in entry.get("injection") or []:
        if isinstance(inj, dict) and inj.get("varName") not in var_names:
            issues.append({"kind": "var-unknown", "varName": inj.get("varName")})
    for a in entry.get("asserts") or []:
        if (isinstance(a, dict) and a.get("mode") == "override"
                and isinstance(a.get("stepIndex"), int)
                and 0 <= a["stepIndex"] < step_count
                and a.get("target") not in assert_targets_of(a["stepIndex"])):
            issues.append({"kind": "override-no-match",
                           "stepIndex": a["stepIndex"], "target": a.get("target")})
    return issues


def compose_injection_scenario(definition: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """基线 vars + injection 覆写 + asserts patch(override 改 expected /
    append 加条目);悬空项(越界/无匹配)静默跳过 — dispatcher 层已先经
    entry_issues 过滤死条目,此处双保险。

    injection.value 由用户显式编辑,**原样覆写不 coerce**(与数据集行的
    ``_coerce_row_value`` 相反:条目值类型由前端输入态保证)。
    """
    out = copy.deepcopy(definition)
    cfg = out.setdefault("config", {})
    vars_map = dict(cfg.get("vars") or {})
    for inj in entry.get("injection") or []:
        if isinstance(inj, dict) and isinstance(inj.get("varName"), str):
            vars_map[inj["varName"]] = inj.get("value")
    cfg["vars"] = vars_map

    steps = out.get("steps") or []
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
