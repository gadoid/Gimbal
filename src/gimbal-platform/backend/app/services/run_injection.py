"""注入条目物化(spec v3 §3)— 平台层 patch,引擎/plate 零改动。

与 run_materialize.py 同纪律:纯函数、深拷贝进深拷贝出、执行链唯一物化语义。
assertion_registry 条目在 plate convert 之前落进 definition(steps[si].strategy
追加 Assign 直补 + asserts patch),materialize_run_copy 其后照旧。
值注入与数据集 vars 注入完全解耦(正交叠加):compose 不触碰 config.vars。
"""
import copy
from typing import Any, Callable

from .jsonpath import exists


def _is_context_readable(source: Any) -> bool:
    """引擎会把这两类字符串当**引用**解析,而不是字面量
    (gimbal/strategy/builtin/utils.py:63-106 `_resolve_source_value`):
    * ``"$.*"`` — scope 落到 STEP/SCENARIO(Assign 默认 SCENARIO)时按
      JSONPath 从场景上下文读(jsonpath 查不到 → None);
    * 整串 ``"${...}"`` — 按变量名从上下文读(读不到 → None)。
    其余字符串与全部非字符串(含 dict/list)一律原样直通。"""
    if not isinstance(source, str):
        return False
    if source.startswith("$."):
        return True
    return source.startswith("${") and source.endswith("}")


def _assign_strategy(value: Any, target: str) -> dict[str, Any]:
    """偏离值 → Assign 策略 dict(spec v3 §3:引擎/plate 零改动)。

    用户 value 的语义是「原样覆写不 coerce」,但引擎对上面两类字符串
    优先做上下文解析:解析不到得 None,而 `required` 默认 True 时
    Assign 直接 FAILED(assign.py:35-45),BEFORE_REQUEST 失败即
    **整步不发请求**(statemachine/states.py:63-69)。故这两类形状
    额外带上 `default`(=该字面量)与 `required: false` —— assign.py
    的顺序是先 default 后 required,解析不到时落字面量而非失败,解析
    得到时 default 不参与。其余情形不带键:Assign 基座字段全取默认
    (spec §3)。

    残留边界一(引擎语义所限,记录不兜):上下文里**恰好存在**同名
    JSONPath/变量时解析命中,该 value 被上下文值覆写而非字面量。
    编辑器对此有可见提示(AssertionRegistryEditor「上下文引用形」)。

    残留边界二(不可修,不是本函数能兜的):JSON null 偏离值无法送达
    引擎 —— plate 导出 `model_dump(exclude_none=True)`(export/gimbal.py
    `GimbalScenarioExporter.render`)把 `source: None` 整键丢弃,而引擎
    `Assign.source` 是必填 → 该 case 加载即 `Scenario.model_validate`
    失败。此处不置 `required: false`(改不了结局,只把「单步失败」
    伪装成成功);编辑器对 null 值显形警告。
    """
    st: dict[str, Any] = {"kind": "assign", "source": value, "target": target}
    if _is_context_readable(value):
        st["default"] = value
        st["required"] = False
    return st


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
    value 由用户显式编辑,原样覆写不 coerce —— 引擎 `_resolve_source_value`
    只对**非字符串**直通,字符串里 "$.*" 与整串 "${...}" 会被当上下文引用
    解析,见 `_assign_strategy`(default/required 兜底 + 两条残留边界)。
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
                _assign_strategy(entry.get("value"), target))
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
