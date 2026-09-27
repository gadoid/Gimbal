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

from typing import Union

from gimbal.compiler.analysis import ScenarioAnalysis, analyze_scenario
from gimbal.compiler.errors import CompileError
from gimbal.log import get_logger
from gimbal.schema.plan import Plan, PlanPolicy, Unit, UnitPolicy
from gimbal.schema.scenario import Control, Scenario, SuiteGraph, UnitDecl

logger = get_logger(__name__)

__all__ = ["CompileError", "compile_target", "validate_plan", "analyze_scenario"]


# ── 入口 ─────────────────────────────────────────────────────

def compile_target(target: Union[Scenario, SuiteGraph]) -> Plan:
    """把 Scenario / SuiteGraph 编译为 Plan。

    v2.1 批次 F-2b：嵌入式 Suite（list[Scenario]）已删除——其 aggregate
    语义由 SuiteGraph(mode=aggregate) 承接（迁移脚本 suite→graph）。
    """
    if isinstance(target, Scenario):
        return _implicit_plan(target)
    if isinstance(target, SuiteGraph):
        return _graph_plan(target)
    raise CompileError(
        f"无法编译的目标类型: {type(target).__name__}"
        "（嵌入式 Suite 已删除，请用 graph 或经迁移脚本转换）"
    )


# ── 批次 B：scenario / 嵌入式 suite ──────────────────────────

def _implicit_plan(scenario: Scenario) -> Plan:
    """单场景 → 隐式 aggregate Plan（单单元）。"""
    plan = Plan(
        units=[Unit(id=scenario.scenarioId, scenario=scenario)],
        policy=PlanPolicy(),
        suite_id="__default__",
        suite_name="Default Suite",
        implicit=True,
        mode="aggregate",
    )
    logger.debug("[compiler] 单场景 → 隐式 Plan: unit={}", plan.units[0].id)
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


def _expand_repeat(decls: list[UnitDecl]) -> list[UnitDecl]:
    """repeat 编译期展开：ref（repeat=N）→ ref#1..ref#N。

    - 展开后 needs 引用原 ref 的单元 → 依赖其**全部变体**（fan-in）；
      变体间同输出名在 bind 命中多变体时按同名冲突处理（用 map 或引用具体 #k 消歧）。
    - repeat=1 不展开（id 保持 ref，无后缀——与既有行为一致）。
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
    if expanded_ids:
        for d in out:
            d.needs = [
                n for need in d.needs
                for n in expanded_ids.get(need, [need])
            ]
        logger.info("[compiler] repeat 展开: {}", expanded_ids)
    return out


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
    """SuiteGraph → Plan：control → shared 塌缩 → desugar（mode 表）→ bind。"""
    from gimbal.suite.modes import build_default_mode_registry

    _check_refs_unique({"before": graph.before, "units": graph.units, "after": graph.after})

    for bracket in ("before", "after"):
        for d in getattr(graph, bracket):
            if d.needs:
                raise CompileError(f"{bracket} 括号单元 {d.ref!r} 不允许声明 needs（按定义先行/必达）")

    before = [d.model_copy(deep=True) for d in graph.before]
    after = [d.model_copy(deep=True) for d in graph.after]
    units_decl = [d.model_copy(deep=True) for d in graph.units]

    # 0. repeat 编译期展开（批次 D 三种乘法之一；先于闭包，闭包按变体计算）
    units_decl = _expand_repeat(units_decl)

    # 1. control.only 闭包（只作用于主体单元；按模式隐含依赖）
    units_decl = _control_closure(units_decl, graph.control, graph.mode)

    # 2. shared 塌缩（三段分别塌缩；ref 全局重映射）
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

    # 3. desugar：mode 表查表（主体单元按模式填 needs；括号单元无 needs）
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
    after_units = [Unit(id=d.ref, scenario=d.scenario, inputs=dict(d.inputs),
                        shared_key=d.shared) for d in after]
    before_units = [Unit(id=d.ref, scenario=d.scenario, inputs=dict(d.inputs),
                         shared_key=d.shared) for d in before]

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

def validate_plan(plan: Plan) -> list[str]:
    """全图校验；返回错误清单（空 = 通过）。"""
    # 乘法组合语义见 scheduler/plan.py docstring 与 v2.1 实施案批次 D：
    # repeat(编译期, ref#k) × n_runs(运行期重复) × retry(失败重跑)；
    # n_runs/retry 的取值域由 UnitPolicy schema（ge 约束）保证。
    errors: list[str] = []
    if plan.mode not in ("aggregate", "compose", "fanout", "chain"):
        errors.append(f"未知 mode: {plan.mode!r}")
    return errors
