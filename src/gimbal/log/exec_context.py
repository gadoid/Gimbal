"""log/exec_context.py — 执行上下文标签（P1-01，可观测性底座）。

九个标签在四个执行边界设置（进入设置、退出恢复；contextvar 协程/线程安全）：

    run        Engine.run 边界（= framework_ctx.run_id）
    unit       单元边界（Plan 单元 id；线程池单元线程各自隔离）
    attempt    尝试边界（"{n_runs 序号}.{attempt 序号}"，如 "2.3"）
    scenario   场景边界（scenarioId）
    step       步骤边界（step_id）
    module     场景 meta.module（随 scenario 边界）
    service    调用服务（step.call.service，随 step 边界）
    protocol   协议名（调用边界）
    endpoint   端点标识（call.view_hints.endpoint_id，调用边界；无则不设）

边界语义（防线程复用串标签）：进入某边界时，**更深层边界的标签全部清空**
——单元线程池复用线程时，上一单元残留的 step/scenario 等标签不会泄漏到
下一单元（下一单元未执行到该层时读到的是"无"而不是旧值）。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

# 标签名 → 所属边界（浅 → 深）
_BOUNDARY_ORDER = ("run", "unit", "attempt", "scenario", "step", "call")

_LABEL_TO_BOUNDARY: dict[str, str] = {
    "run": "run",
    "unit": "unit",
    "attempt": "attempt",
    "scenario": "scenario",
    "module": "scenario",
    "step": "step",
    "service": "step",
    "protocol": "call",
    "endpoint": "call",
}

EXEC_LABEL_NAMES: tuple[str, ...] = tuple(_LABEL_TO_BOUNDARY)

_VARS: dict[str, ContextVar[Optional[str]]] = {
    name: ContextVar(f"_EXEC_{name}", default=None) for name in _LABEL_TO_BOUNDARY
}


def _deeper_labels(boundary: str) -> tuple[str, ...]:
    """比 boundary 更深的边界所辖标签名。"""
    idx = _BOUNDARY_ORDER.index(boundary)
    deeper = set(_BOUNDARY_ORDER[idx + 1:])
    return tuple(n for n, b in _LABEL_TO_BOUNDARY.items() if b in deeper)


def exec_labels() -> dict[str, str]:
    """当前上下文的全部已设标签（未设的不出现）。"""
    return {name: var.get() for name, var in _VARS.items() if var.get() is not None}


def _enter(labels: dict[str, str], boundary: str | None):
    """应用标签 + 清空更深层标签；返回恢复用的 token 列表。"""
    tokens: list[tuple[str, object]] = []
    if boundary is not None:
        for name in _deeper_labels(boundary):
            tokens.append((name, _VARS[name].set(None)))
    for name, value in labels.items():
        if name not in _VARS:
            raise KeyError(f"未知执行上下文标签: {name!r}（合法: {EXEC_LABEL_NAMES}）")
        tokens.append((name, _VARS[name].set(str(value))))
    return tokens


def _exit(tokens) -> None:
    for name, token in reversed(tokens):
        _VARS[name].reset(token)


def bind_exec_context(labels: dict[str, str], *, boundary: str | None = None):
    """非 with 形态：立即生效，返回可调用 undo（线程函数内不便用 with 时用）。"""
    tokens = _enter(labels, boundary)
    return lambda: _exit(tokens)


def exec_context(**labels: str) -> "_ExecContext":
    """with 形态：进入设置、退出恢复。

    ``_boundary`` 关键字声明本次进入的边界（run/unit/attempt/scenario/
    step/call），进入时清空更深层标签；缺省不清空（纯叠加，测试/特殊
    场景用）。
    """
    boundary = labels.pop("_boundary", None)
    return _ExecContext(labels, boundary)


class _ExecContext:
    def __init__(self, labels: dict[str, str], boundary: str | None) -> None:
        self._labels = labels
        self._boundary = boundary
        self._tokens: list | None = None

    def __enter__(self) -> dict[str, str]:
        """进入：应用标签，返回进入后的标签快照。"""
        self._tokens = _enter(self._labels, self._boundary)
        return exec_labels()

    def __exit__(self, *exc) -> None:
        if self._tokens is not None:
            _exit(self._tokens)
            self._tokens = None
