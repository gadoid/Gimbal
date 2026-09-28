"""core/decisions.py — 拦截决策（v2 §拦截 hook，v2.1 批次 E）。

hook 是同步拦截点，返回**唯一**决策类型；不承担观察（观察走事件）。
拦截者通过 ``return Decision(...)`` 返回决策（S-3 起异常通道退役；
未返回 / 返回 None = continue）。

五个拦截点（v2 表格；批次 E 接入四个，STRATEGY_BEFORE 复用现有
dispatcher STOP→SKIP 语义）：

  STEP_BEFORE     step 进入 BEFORE_REQUEST 前     CONTINUE / SKIP / ABORT
  CALL_BEFORE     render 之后、send 之前          CONTINUE（可带 patch）/ ABORT
  CALL_AFTER      send 之后、AFTER_REQUEST 前     CONTINUE / ABORT（RETRY 留后）
  STRATEGY_BEFORE 单条策略执行前                  CONTINUE / SKIP（现状已支持）
  STEP_FAILED     step 失败后（ScenarioRunner 层）CONTINUE / RETRY / SKIP / ABORT

裁决记录（v2.1 §一 #2）：不设 ``by: human`` 字段语义负担——
``source="human"`` 由 debugger 会话发出的决策自动标记；人工 RETRY 后通过
记 **repaired**（不计正常通过率）。多个拦截者按注册顺序串行，第一个非
continue 的决策生效（HookRegistry 的 STOP 即此语义）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from gimbal.log import get_logger

logger = get_logger(__name__)


@dataclass
class Decision:
    """拦截决策。"""

    action: str = "continue"                 # continue | retry | skip | abort
    patch: Optional[dict] = None             # 仅 CALL_BEFORE：请求补丁
    # 仅 STEP_BEFORE：注入 scratch 变量后继续（debugger write 命令，P1-10）
    write: Optional[dict] = None
    source: str = "auto"                     # auto | human（debugger 会话）
    note: str = ""

    @property
    def is_human(self) -> bool:
        return self.source == "human"


def effective(decisions: "list[Any]") -> Decision:
    """决策聚合（S-3）：首个**有内容**的决策生效。

    "有内容" = action != "continue"，**或** continue 但携带载荷
    （write/patch——debugger 的 write/patch 命令即 continue+载荷）；
    空 / 全部纯 continue → continue。
    """
    for d in decisions:
        if isinstance(d, Decision) and (
            d.action != "continue" or d.write or d.patch
        ):
            return d
    return Decision()


def ask_decision(hook_registry: Any, point: Any, payload: dict) -> Decision:
    """在拦截点询问决策（S-3）：trigger 收集 handler 返回的 Decision，
    首个非 continue 生效；无决策 / 全 continue = continue。

    point 接受 HookPoint 枚举、枚举名（"CALL_BEFORE_SEND"）或 value
    （"call.before_send"），自动归一化。
    """
    if hook_registry is None:
        return Decision()
    point = _normalize_point(point)
    try:
        decisions = hook_registry.trigger(point, payload)
    except Exception:  # noqa: BLE001
        logger.exception("[Decision] 拦截点触发异常，按 continue 处理: {}", point)
        return Decision()
    return effective(decisions)


def _normalize_point(point: Any) -> Any:
    """字符串 → HookPoint（先按枚举名，再按 value；失败原样返回）。"""
    if not isinstance(point, str):
        return point
    try:
        from gimbal.core.hooks import HookPoint
        try:
            return HookPoint[point]
        except KeyError:
            return HookPoint(point)
    except (ValueError, ImportError):
        return point
