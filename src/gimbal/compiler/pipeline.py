"""compiler/pipeline.py — 编译管线（v2 §编译管线；批次 B 截断版 + 批次 C 编排）。

七个阶段（load → normalize → patch → desugar → expand → bind → validate）；
``compile`` / ``validate`` / ``resolve`` 都是它的不同截断。

批次 B（已落地）：
  - Scenario → 隐式 aggregate Plan；嵌入式 Suite → aggregate Plan；
  - patch 截断：Suite.execution → PlanPolicy；validate：乘法未支持项。

批次 C（本文件新增 graph 管线）：
  - SuiteGraph（kind=graph）→ control.only 闭包 → shared 塌缩（key 身份 +
    生效定义一致性）→ mode desugar（mode 表查表）→ bind（静态分析三形态
    输入面 × 上游输出，map 改名，同名冲突/输入不满足报错）→ validate（循环、
    输入满足、needs 引用存在）；
  - expand（数据集/repeat 变体展开）与五层 patch 叠加仍留批次 D/后置。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from gimbal.compiler.analysis import ScenarioAnalysis, analyze_scenario
from gimbal.compiler.errors import CompileError
from gimbal.log import get_logger
from gimbal.schema.plan import Plan, PlanPolicy, Unit, unit_policy_from
from gimbal.schema.scenario import Control, Scenario, SuiteGraph, UnitDecl

logger = get_logger(__name__)

__all__ = ["CompileError", "compile_target", "compile_plan", "validate_plan",
           "analyze_scenario", "p_load", "p_normalize", "p_patch", "p_desugar",
           "p_expand", "p_bind", "p_validate"]


# ── 入口 ─────────────────────────────────────────────────────

def compile_target(
    target: Union[Scenario, SuiteGraph],
    protocols: "Any | None" = None,
) -> Plan:
    """把 Scenario / SuiteGraph 编译为 Plan。

    v2.1 批次 F-2b：嵌入式 Suite（list[Scenario]）已删除——其 aggregate
    语义由 SuiteGraph(mode=aggregate) 承接（迁移脚本 suite→graph）。

    protocols（S-1）：用于编译期校验 step.call 协议字段的协议注册表。
    严格度跟随注册表来源：
      - 显式传入（Engine 运行时，权威注册表）→ 未注册协议即 CompileError；
      - 缺省（内置注册表；库直调 / 无 bootstrap 的 compile CLI）→ 只校验
        已知协议的字段，插件协议不在内置表内、运行期由 Engine 路径收口。
    """
    _validate_call_fields(target, protocols)
    if isinstance(target, Scenario):
        return _implicit_plan(target)
    if isinstance(target, SuiteGraph):
        return _graph_plan(target)
    raise CompileError(
        f"无法编译的目标类型: {type(target).__name__}"
        "（嵌入式 Suite 已删除，请用 graph 或经迁移脚本转换）"
    )


def _validate_call_fields(
    target: Union[Scenario, SuiteGraph],
    protocols: "Any | None" = None,
) -> None:
    """normalize 期协议字段校验（v2 §normalize）：未知协议 / 未知字段 → CompileError。

    Call 是开放模型（extra="allow"），协议自有字段的合法性由各协议的
    params_model（extra="forbid"）在编译期收口——注册新协议不改 Call。
    protocols 缺省时用内置注册表且**不**对未注册协议报错（见 compile_target
    docstring 的严格度规则）。
    """
    from pydantic import ValidationError

    strict = protocols is not None
    if protocols is None:
        from gimbal.protocols.registry import build_default_protocol_registry
        protocols = build_default_protocol_registry()

    scenarios: list[Scenario] = []
    if isinstance(target, Scenario):
        scenarios.append(target)
    else:  # SuiteGraph：括号与主体全部单元的场景
        for decl in [*target.before, *target.units, *target.after]:
            if getattr(decl, "scenario", None) is not None:
                scenarios.append(decl.scenario)

    for sc in scenarios:
        for idx, step in enumerate(sc.steps):
            call = getattr(step, "call", None)
            if call is None:
                continue
            proto = call.protocol
            if protocols.resolve(proto) is None:
                if strict:
                    raise CompileError(
                        f"step[{idx}] call 引用未注册的协议: {proto!r}"
                        f"（已注册: {protocols.protocols()}）"
                    )
                continue  # 非权威注册表：插件协议留给运行期收口
            params_model = protocols.params_of(proto)
            if params_model is None:
                continue  # 开放协议：注册时未声明参数模型，不做字段校验
            try:
                params_model.model_validate(call.extra_fields())
            except ValidationError as exc:
                raise CompileError(
                    f"step[{idx}] call 协议 {proto!r} 字段校验失败"
                    f"（未知字段或类型不符）: {exc.error_count()} 处 —— {exc.errors()[0].get('loc')}"
                ) from exc


# ── 批次 B：scenario / 嵌入式 suite ──────────────────────────

def _implicit_plan(scenario: Scenario) -> Plan:
    """单场景 → 隐式 aggregate Plan（单单元）。"""
    plan = Plan(
        # P1-12：config.retry → UnitPolicy 映射（无编排覆盖项）
        units=[Unit(id=scenario.scenarioId, scenario=scenario,
                    policy=unit_policy_from(scenario))],
        policy=PlanPolicy(),
        suite_id="__default__",
        suite_name="Default Suite",
        implicit=True,
        mode="aggregate",
    )
    logger.debug("[compiler] 单场景 → 隐式 Plan: unit={}", plan.units[0].id)
    return plan


# ── 七阶段公共入口（S-4：load / normalize / patch + compile_plan）──


def p_load(raw: dict) -> Union[Scenario, SuiteGraph]:
    """七阶段之一 load：raw dict → Scenario / SuiteGraph（kind 判别）。

    纯函数：只做模型校验，无 I/O；文件读取由 CLI 层完成。
    """
    kind = raw.get("kind")
    if kind == "scenario":
        return Scenario.model_validate(raw)
    if kind == "graph":
        return SuiteGraph.model_validate(raw)
    raise CompileError(
        f"无法识别的目标 kind: {kind!r}（合法: scenario / graph）"
    )


def p_normalize(target: Union[Scenario, SuiteGraph],
                protocols: "Any | None" = None) -> Union[Scenario, SuiteGraph]:
    """七阶段之二 normalize：不变量校验（协议字段 / 结构不变量）。

    api→call 归一化在 Step 校验期（schema/step.py）完成、setup/teardown
    展开在 LifecycleEntry（批次 B/P1-12）；本阶段收口协议自有字段的
    合法性（S-1 编译期校验）。返回原 target（校验不通过抛 CompileError）。
    """
    _validate_call_fields(target, protocols)
    return target


def p_patch(layers: list[dict]) -> dict:
    """七阶段之三 patch：五层合并代数（源 → suite 补丁 → 单元补丁 →
    调用参数 → 生效副本；标量后层覆盖前层）。

    规则（纯函数）：
      - dict 深合并（后层的键覆盖同名键，嵌套 dict 递归合并）；
      - 标量（含 str）后层覆盖；
      - list 按 index 覆盖（后层 list[i] 覆盖前层 list[i]；多出的保留，
        缺短的以前层补齐）。
    """
    if not layers:
        return {}

    def merge(base: dict, override: dict) -> dict:
        out = dict(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge(out[k], v)
            elif isinstance(v, list) and isinstance(out.get(k), list):
                merged = list(out[k])
                for i, item in enumerate(v):
                    if i < len(merged):
                        if isinstance(item, dict) and isinstance(merged[i], dict):
                            merged[i] = merge(merged[i], item)
                        else:
                            merged[i] = item
                    else:
                        merged.append(item)
                out[k] = merged
            else:
                out[k] = v
        return out

    result: dict = {}
    for layer in layers:
        result = merge(result, layer or {})
    return result


def compile_plan(raw: Union[dict, Scenario, SuiteGraph],
                 protocols: "Any | None" = None) -> Plan:
    """七阶段编排：load → normalize → patch → desugar → expand → bind → validate。

    raw 为 dict 时经 p_load 解析；已校验的模型直入 normalize。
    （patch 阶段的五层叠加在 schema 补丁层落地前为恒等——合并代数经
    p_patch 单测钉死，供调用参数/编排补丁接线。）
    """
    target = p_load(raw) if isinstance(raw, dict) else raw
    p_normalize(target, protocols)
    plan = compile_target(target, protocols)
    errors = p_validate(plan)
    if errors:
        raise CompileError("; ".join(errors))
    return plan


# ── 批次 C：编排套件（SuiteGraph）───────────────────────────

def _check_refs_unique(decls_by_bracket: dict[str, list[UnitDecl]]) -> None:
    seen: set[str] = set()
    for bracket, decls in decls_by_bracket.items():
        for d in decls:
            if not d.ref:
                raise CompileError(f"{bracket} 中存在空 ref")
            if d.ref in seen:
                raise CompileError(f"ref 重复: {d.ref!r}")
            seen.add(d.ref)


def _implied_needs(mode: str, decls: list[UnitDecl]) -> dict[str, list[str]]:
    """按模式语义推导的依赖边（control.only 闭包的计算依据）。

    compose: 显式 needs；chain: 前驱；fanout: 汇→源；aggregate: 无。
    """
    if mode == "compose":
        return {d.ref: list(d.needs) for d in decls}
    if mode == "chain":
        return {d.ref: ([decls[i - 1].ref] if i > 0 else []) for i, d in enumerate(decls)}
    if mode == "fanout" and decls:
        source = decls[0].ref
        return {d.ref: ([source] if d.ref != source else []) for d in decls}
    return {d.ref: [] for d in decls}


def _control_closure(units: list[UnitDecl], control: Control | None,
                     mode: str) -> list[UnitDecl]:
    """control.only = 目标 + 传递依赖闭包（make 语义；按模式隐含依赖计算）。"""
    if control is None or not control.only:
        return units
    implied = _implied_needs(mode, units)
    keep: set[str] = set()
    stack = [r for r in control.only]
    while stack:
        ref = stack.pop()
        if ref in keep:
            continue
        if ref not in implied:
            raise CompileError(f"control.only 引用了不存在的 ref: {ref!r}")
        keep.add(ref)
        stack.extend(implied[ref])
    kept = [d for d in units if d.ref in keep]
    logger.info("[compiler] control.only 闭包: {} → {}", [d.ref for d in units], sorted(keep))
    return kept


# 七阶段之五：expand —— repeat 编译期展开（S-4 抽出为纯函数 + 上限闸）
_MAX_EXPANDED_UNITS = 4096


def p_expand(decls: list[UnitDecl]) -> list[UnitDecl]:
    """repeat 编译期展开：ref（repeat=N）→ ref#1..ref#N；上限闸 4096 单元。

    - 展开后 needs 引用原 ref 的单元 → 依赖其**全部变体**（fan-in）；
      变体间同输出名在 bind 命中多变体时按同名冲突处理（用 map 或引用具体 #k 消歧）。
    - repeat=1 不展开（id 保持 ref，无后缀——与既有行为一致）。
    - 展开后总量（含未展开单元）超过 4096 → CompileError（计划清单上限闸，
      防数据集 × repeat × 注入变体的乘法爆炸）。
    """
    expanded_ids: dict[str, list[str]] = {}
    out: list[UnitDecl] = []
    for d in decls:
        if d.repeat <= 1:
            out.append(d)
            continue
        variants = [f"{d.ref}#{k}" for k in range(1, d.repeat + 1)]
        expanded_ids[d.ref] = variants
        for k, vid in enumerate(variants, start=1):
            out.append(d.model_copy(update={"ref": vid, "repeat": 1}))
    if len(out) > _MAX_EXPANDED_UNITS:
        raise CompileError(
            f"expand 展开 后单元数 {len(out)} 超上限 {_MAX_EXPANDED_UNITS}"
            "（repeat × 变体乘法上限闸）"
        )
    if expanded_ids:
        for d in out:
            d.needs = [
                n for need in d.needs
                for n in expanded_ids.get(need, [need])
            ]
        logger.info("[compiler] repeat 展开: {}", expanded_ids)
    return out


# _expand_repeat 历史别名（S-4 前调用方；compile 内部一律走 p_expand）
_expand_repeat = p_expand


def _effective_definition(decl: UnitDecl) -> dict:
    """单元的生效定义：scenario 全量 dump + 影响执行的全部声明字段。

    用于 shared 塌缩的一致性比较（review P0-6：此前只比 scenario，
    inputs/policy_kwargs 等差异会被静默丢弃）。不含 ref（身份）、
    needs（图结构，塌缩后重映射）、shared（塌缩键本身，按构造双方相等）。
    """
    return {
        "scenario": decl.scenario.model_dump(),
        "inputs": decl.inputs,
        "outputs": decl.outputs,
        "policy_kwargs": decl.policy_kwargs,
        "map": decl.map,
        "repeat": decl.repeat,
    }


def _collapse_shared(decls: list[UnitDecl], bracket: str) -> tuple[list[UnitDecl], dict[str, str]]:
    """shared 塌缩：同 key 的声明合并为一份（首个代表），needs 引用重映射。

    一致性硬校验：同 key 的生效定义（scenario 全量 dump + inputs/outputs/
    policy_kwargs/map/repeat）必须完全一致，首个差异字段计入报错。
    返回 (塌缩后的 decls, ref 重映射表 {被塌缩 ref → 代表 ref})。
    """
    remap: dict[str, str] = {}
    by_key: dict[str, UnitDecl] = {}
    out: list[UnitDecl] = []
    for d in decls:
        if d.shared is None:
            out.append(d)
            continue
        if d.shared not in by_key:
            by_key[d.shared] = d
            out.append(d)
            continue
        rep = by_key[d.shared]
        rep_defn = _effective_definition(rep)
        defn = _effective_definition(d)
        if defn != rep_defn:
            diff = next(k for k in defn if defn[k] != rep_defn[k])
            raise CompileError(
                f"shared key={d.shared!r} 的生效定义不一致"
                f"（{rep.ref!r} vs {d.ref!r}，差异字段 {diff!r}）；"
                "同 key 的依赖条目要求生效定义完全一致"
            )
        remap[d.ref] = rep.ref
        logger.debug("[compiler] shared 塌缩: {} → {} (key={})", d.ref, rep.ref, d.shared)
    return out, remap


def _remap_needs(decls: list[UnitDecl], remap: dict[str, str]) -> None:
    for d in decls:
        d.needs = [remap.get(n, n) for n in d.needs]


def _validate_needs_refs(units: list[Unit], ref_pool: set[str]) -> None:
    for u in units:
        for n in u.needs:
            if n == u.id:
                raise CompileError(f"单元 {u.id!r} 不能 needs 自己")
            if n not in ref_pool:
                raise CompileError(f"单元 {u.id!r} 的 needs 引用了不存在的 ref: {n!r}")


def _ancestors(unit_id: str, needs_map: dict[str, list[str]]) -> set[str]:
    """needs 的传递闭包（不含自身）。"""
    seen: set[str] = set()
    stack = list(needs_map.get(unit_id, []))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(needs_map.get(n, []))
    return seen


def _check_acyclic(needs_map: dict[str, list[str]]) -> None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in needs_map}
    cycle: list[str] = []

    def visit(node: str) -> bool:
        color[node] = GRAY
        for dep in needs_map.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                cycle.extend([dep, node])
                return False
            if color[dep] == WHITE and not visit(dep):
                return False
        color[node] = BLACK
        return True

    for n in needs_map:
        if color[n] == WHITE:
            if not visit(n):
                raise CompileError(f"依赖存在循环: {' → '.join(reversed(cycle))}")


def _graph_plan(graph: SuiteGraph) -> Plan:
    """SuiteGraph → Plan（S-4 起为七阶段编排壳：desugar → expand → bind）。"""
    expanded = p_desugar(graph)
    return p_bind(graph, expanded)


# ── 七阶段之四：desugar —— 括号校验 + 模式隐含依赖解析 ─────────


@dataclass
class _ExpandedDecls:
    """p_desugar 的产物：三段声明（深拷贝、已展开/闭包/塌缩）+ 重映射表。"""
    before: list[UnitDecl]
    units: list[UnitDecl]
    after: list[UnitDecl]
    remap: dict[str, str]



def p_desugar(graph: SuiteGraph) -> "_ExpandedDecls":
    """desugar 纯函数：结构校验 + 深拷贝 + repeat 展开 + control 闭包 +
    shared 塌缩，产出三段声明与重映射表（不构造 Unit/Plan）。

    模式语义（compose/chain/fanout 的隐含依赖）由 mode 表在 p_bind 阶段
    查表应用；本阶段产出的是"哪些主体单元参与编排"的闭包结果。
    """
    _check_refs_unique({"before": graph.before, "units": graph.units, "after": graph.after})

    for bracket in ("before", "after"):
        for d in getattr(graph, bracket):
            if d.needs:
                raise CompileError(f"{bracket} 括号单元 {d.ref!r} 不允许声明 needs（按定义先行/必达）")

    before = [d.model_copy(deep=True) for d in graph.before]
    after = [d.model_copy(deep=True) for d in graph.after]
    units_decl = [d.model_copy(deep=True) for d in graph.units]

    # repeat 编译期展开（批次 D 三种乘法之一；先于闭包，闭包按变体计算）
    units_decl = p_expand(units_decl)

    # control.only 闭包（只作用于主体单元；按模式隐含依赖）
    units_decl = _control_closure(units_decl, graph.control, graph.mode)

    # shared 塌缩（三段分别塌缩；ref 全局重映射）
    all_remap: dict[str, str] = {}
    collapsed: list[tuple[str, list[UnitDecl]]] = []
    for bracket, decls in (("before", before), ("units", units_decl), ("after", after)):
        deduped, remap = _collapse_shared(decls, bracket)
        all_remap.update(remap)
        collapsed.append((bracket, deduped))
    for _, decls in collapsed:
        _remap_needs(decls, all_remap)
    before = dict(collapsed)["before"]
    units_decl = dict(collapsed)["units"]
    after = dict(collapsed)["after"]
    if not units_decl:
        raise CompileError("control.only 闭包后主体单元为空")
    return _ExpandedDecls(before=before, units=units_decl, after=after, remap=all_remap)


# ── 七阶段之六：bind —— mode 表 + 静态分析连线 ───────────────


def p_bind(graph: SuiteGraph, expanded: "_ExpandedDecls") -> Plan:
    """bind 纯函数：mode 表填 needs → 引用校验 → 静态分析连线 → Plan。"""
    from gimbal.suite.modes import build_default_mode_registry

    before, units_decl, after = expanded.before, expanded.units, expanded.after

    # mode 表查表（主体单元按模式填 needs；括号单元无 needs）
    mode_table = build_default_mode_registry()
    try:
        _, desugar = mode_table.get(graph.mode)
    except KeyError as exc:
        raise CompileError(str(exc)) from exc
    main_units = desugar(units_decl, graph.control)

    # needs 引用存在性（可引用 before 与主体 ref）
    ref_pool = {d.ref for d in before} | {u.id for u in main_units}
    _validate_needs_refs(main_units, ref_pool)
    for u in main_units:
        for dep in u.needs:
            if dep in {d.ref for d in after}:
                raise CompileError(f"单元 {u.id!r} 不能依赖 after 括号单元 {dep!r}")
    # P1-12：括号单元同样映射 scenario config.retry（场景自带的重试声明
    # 在任何执行位置生效；编排 policy_kwargs 不作用于括号——既有行为）
    after_units = [Unit(id=d.ref, scenario=d.scenario, inputs=dict(d.inputs),
                        shared_key=d.shared,
                        policy=unit_policy_from(d.scenario)) for d in after]
    before_units = [Unit(id=d.ref, scenario=d.scenario, inputs=dict(d.inputs),
                         shared_key=d.shared,
                         policy=unit_policy_from(d.scenario)) for d in before]

    # 4. bind：静态分析连线（主体 + after；before 无 needs 但其输出可被依赖）
    decl_by_ref = {d.ref: d for d in [*before, *units_decl, *after]}
    outputs_map: dict[str, set[str]] = {}
    analysis_map: dict[str, ScenarioAnalysis] = {}
    consumer_maps: dict[str, dict[str, str]] = {}
    for unit in [*main_units, *after_units, *before_units]:
        decl = decl_by_ref[unit.id]
        analysis = analyze_scenario(decl.scenario)
        analysis_map[unit.id] = analysis
        outputs_map[unit.id] = set(decl.outputs) if decl.outputs is not None else analysis.outputs
        consumer_maps[unit.id] = dict(decl.map or {})

    needs_map: dict[str, list[str]] = {u.id: list(u.needs) for u in main_units + after_units}
    _check_acyclic(needs_map)

    after_ids = {u.id for u in after_units}
    wiring: dict[str, dict[str, str]] = {}
    after_optional: set[str] = set()
    for unit in main_units + after_units:
        analysis = analysis_map[unit.id]
        literal_keys = set(unit.inputs.keys())
        hard = analysis.inputs - literal_keys
        soft = analysis.optional_inputs - literal_keys
        ancestors = _ancestors(unit.id, needs_map) | {
            u.id for u in before_units   # 括号先行，输出恒可用
        }
        if unit.id in after_ids:
            # P0-5：after 必达（业务清理）——主体输出恒可见，无须 needs 声明
            # （清理单元引用主体提取的 orderId 之类不再"输入不满足"）；
            # 同名歧义仍按 map 改名消解，主体未产出的名运行期注入 None 兜底
            ancestors |= {u.id for u in main_units}
        consumer_map = consumer_maps.get(unit.id, {})
        wires: dict[str, str] = {}
        for name in sorted(hard | soft):
            candidates: list[tuple[str, str]] = []
            for anc in sorted(ancestors):
                for out in sorted(outputs_map.get(anc, set())):
                    presented = consumer_map.get(out, out)
                    if presented == name:
                        candidates.append((anc, out))
            if len(candidates) > 1:
                raise CompileError(
                    f"单元 {unit.id!r} 的输入 {name!r} 命中多个上游输出: "
                    f"{[f'{a}.{o}' for a, o in candidates]}；请用 map 改名消除歧义"
                )
            if not candidates:
                if name in hard:
                    if unit.id in after_ids:
                        # P0-5：after 单元硬输入无上游供给 → 不 CompileError，
                        # 单元 id 记 after_optional 成文（运行期缺失注入 None）
                        after_optional.add(unit.id)
                        continue
                    raise CompileError(
                        f"单元 {unit.id!r} 的输入 {name!r} 无上游供给（输入不满足）；"
                        "检查连线/needs，或经 inputs/--var 提供"
                        "（chain from_node 切片时跳过的上游输出须显式提供）"
                    )
                continue  # 软输入（config.vars 有默认）：允许无上游
            wires[name] = f"{candidates[0][0]}:{candidates[0][1]}"
        if wires:
            wiring[unit.id] = wires

    plan = Plan(
        units=main_units,
        before=before_units,
        after=after_units,
        policy=graph.policy or PlanPolicy(),
        wiring=wiring,
        after_optional=after_optional,
        suite_id="__graph__",
        suite_name="Graph",
        implicit=False,
        mode=graph.mode,
    )
    logger.info(
        "[compiler] Graph → Plan: mode={} units={} before={} after={} wiring={}",
        graph.mode, len(main_units), len(before_units), len(after_units),
        {k: sorted(v.keys()) for k, v in wiring.items()},
    )
    return plan


# ── validate ─────────────────────────────────────────────────

def p_validate(plan: Plan) -> list[str]:
    """七阶段之七 validate：五项独立防线（返回错误清单,空 = 通过）。

    1. mode 合法；2. 依赖无环（bind 期已抛,此处为独立复查）；
    3. needs 引用存在且无自环；4. unit id 唯一；5. wiring 目标格式合法
    （unit_id:output 名；引用的 unit 存在）。
    users 标签存在性属运行期预认证（C7）/dry-run 校验,不在此层。
    乘法组合语义见 scheduler/plan.py docstring（repeat × n_runs × retry）；
    n_runs/retry 取值域由 UnitPolicy schema（ge 约束）保证。
    """
    errors: list[str] = []
    # 1. mode
    if plan.mode not in ("aggregate", "compose", "fanout", "chain"):
        errors.append(f"未知 mode: {plan.mode!r}")
    all_units = [*plan.before, *plan.units, *plan.after]
    # 4. unit id 唯一
    ids = [u.id for u in all_units]
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        errors.append(f"unit id 重复: {dup}")
    by_id = {u.id: u for u in all_units}
    # 3. needs 引用存在 + 无自环
    for u in plan.units:
        for n in u.needs:
            if n == u.id:
                errors.append(f"单元 {u.id!r} 不能 needs 自己")
            elif n not in by_id:
                errors.append(f"单元 {u.id!r} 的 needs 引用了不存在的 ref: {n!r}")
    # 2. 依赖无环（独立复查；bind 期 _check_acyclic 已保证）
    needs_map = {u.id: list(u.needs) for u in [*plan.units, *plan.after]}
    try:
        _check_acyclic(needs_map)
    except CompileError as exc:
        errors.append(f"依赖存在循环: {exc}")
    # 5. wiring 目标格式与引用
    for uid, wires in (plan.wiring or {}).items():
        if uid not in by_id:
            errors.append(f"wiring 引用了不存在的单元: {uid!r}")
        for name, target in wires.items():
            if ":" not in target or target.split(":", 1)[0] not in by_id:
                errors.append(
                    f"wiring {uid}.{name} 的目标 {target!r} 非法（应为 unit_id:output）"
                )
    return errors


# 历史入口别名（compile/validate/resolve CLI 用）
validate_plan = p_validate
