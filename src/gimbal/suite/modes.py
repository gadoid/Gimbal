"""suite/modes.py — 编排模式 desugar（v2 §编译管线 desugar 阶段，批次 C）。

四模式（mode 表，经泛型 Registry 注册；新增模式 = 注册一个 desugar 函数）：

  - aggregate：无依赖并行（声明 needs → CompileError）
  - compose：显式 needs DAG（原样保留）
  - fanout：首单元为源，其余全部 need 它
  - chain：按声明顺序线性（from_node/to_node 切片）

输入是（shared 塌缩后的）UnitDecl 列表 + Control；输出是执行态 Unit 列表
（id = ref / shared key，needs 已按模式语义填好）。bind（连线）在
compiler/pipeline 的 bind 阶段，不在本层。
"""
from __future__ import annotations

from typing import Callable

from gimbal.compiler.errors import CompileError
from gimbal.core.registry import Registry
from gimbal.log import get_logger
from gimbal.schema.plan import Unit, UnitPolicy
from gimbal.schema.scenario import Control, UnitDecl

logger = get_logger(__name__)

DesugarFn = Callable[[list[UnitDecl], Control | None], list[Unit]]


def _to_unit(decl: UnitDecl, needs: list[str]) -> Unit:
    policy = UnitPolicy(**(decl.policy_kwargs or {}))
    return Unit(id=decl.ref, scenario=decl.scenario, inputs=dict(decl.inputs),
                needs=needs, shared_key=decl.shared, policy=policy)


def _slice_chain_refs(decls: list[UnitDecl], control: Control | None) -> list[UnitDecl]:
    """chain 的 from_node/to_node 切片（含两端）。"""
    if control is None or (control.from_node is None and control.to_node is None):
        return decls
    refs = [d.ref for d in decls]
    start = refs.index(control.from_node) if control.from_node is not None else 0
    end = refs.index(control.to_node) if control.to_node is not None else len(refs) - 1
    if start > end:
        raise CompileError(
            f"chain 切片非法: from_node={control.from_node!r} 在 to_node={control.to_node!r} 之后"
        )
    return decls[start:end + 1]


def desugar_aggregate(decls: list[UnitDecl], control: Control | None) -> list[Unit]:
    for d in decls:
        if d.needs:
            raise CompileError(
                f"aggregate 模式不允许声明 needs（单元 {d.ref!r} 声明了 {d.needs}）；"
                "需要依赖请用 compose/fanout/chain"
            )
    return [_to_unit(d, []) for d in decls]


def desugar_compose(decls: list[UnitDecl], control: Control | None) -> list[Unit]:
    return [_to_unit(d, list(d.needs)) for d in decls]


def desugar_fanout(decls: list[UnitDecl], control: Control | None) -> list[Unit]:
    if len(decls) == 1:
        # control.only 闭包可能只剩源单元自身（无汇可扇出），合法退化
        return [_to_unit(decls[0], [])]
    if len(decls) < 2:
        raise CompileError("fanout 模式至少需要 2 个单元（1 源 + ≥1 汇）")
    source, *sinks = decls
    for d in decls:
        if d.needs:
            raise CompileError(
                f"fanout 模式不允许声明 needs（首单元即源；单元 {d.ref!r} 声明了 {d.needs}）"
            )
    units = [_to_unit(source, [])]
    units += [_to_unit(d, [source.ref]) for d in sinks]
    return units


def desugar_chain(decls: list[UnitDecl], control: Control | None) -> list[Unit]:
    sliced = _slice_chain_refs(decls, control)
    for d in decls:
        if d.needs:
            raise CompileError(
                f"chain 模式不允许声明 needs（顺序即依赖；单元 {d.ref!r} 声明了 {d.needs}）"
            )
    units: list[Unit] = []
    for i, d in enumerate(sliced):
        units.append(_to_unit(d, [sliced[i - 1].ref] if i > 0 else []))
    if control is not None and control.from_node is not None and sliced:
        logger.info(
            "[modes] chain 从 {} 切片：跳过的上游输出须由 --var 提供，bind 会校验输入满足",
            [d.ref for d in decls][: decls.index(sliced[0])],
        )
    return units


# ── mode 表（泛型 Registry；新增模式即注册）─────────────────

MODE_REGISTRY: Registry[DesugarFn] = Registry("mode")
MODE_REGISTRY.register("aggregate", desugar_aggregate)
MODE_REGISTRY.register("compose", desugar_compose)
MODE_REGISTRY.register("fanout", desugar_fanout)
MODE_REGISTRY.register("chain", desugar_chain)


def build_default_mode_registry() -> Registry[DesugarFn]:
    return MODE_REGISTRY
