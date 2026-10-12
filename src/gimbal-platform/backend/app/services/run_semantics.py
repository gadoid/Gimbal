"""版本模型执行语义判定（§6 预览口径；W5/A-2 与 W6/A-4 共用）。

预览口径（《Plate 版本模型》§6）：场景**受管系统**中任一 working
（显式声明 ``"working"`` 或锚点系统未钉修订）即预览执行 —— 不计入
入库标准、集成任务拒绝触发。受管系统 = 锚点步骤 ``endpoint`` 首段
（存储侧既有惯例，strip_binding_fields / run_dispatcher 同款）；
无锚点步骤（external 第三方 / 手写原始调用）不参与判定 —— 三态
接入模型下 external 不触发预览（缺口收口计划 §0 裁定 1/4）。

调试执行不改变预览语义：钉了精确修订的调试不是预览。旧口径
``is_preview = bool(req.debug)`` 已废（2026-10-12，A-2）。
"""
from __future__ import annotations

from .scenario_store import definition_from_payload, steps_from_payload

WORKING = "working"


def anchored_systems(payload: dict | None) -> set[str]:
    """锚点步骤引用的系统集（``endpoint`` 首段）。"""
    out: set[str] = set()
    for step in steps_from_payload(payload):
        eid = step.get("endpoint") if isinstance(step, dict) else None
        if isinstance(eid, str) and eid:
            out.add(eid.split(".")[0])
    return out


def working_preview(payload: dict | None) -> bool:
    """任一受管系统 working（显式声明或未钉修订）→ 预览执行。

    无锚点步骤 / 全部受管系统都钉了精确修订 → 正式执行。
    """
    declared = (((definition_from_payload(payload) or {}).get("meta") or {})
                .get("plate"))
    declared = declared if isinstance(declared, dict) else {}
    for sysname in anchored_systems(payload):
        ref = declared.get(sysname)
        if not ref or ref == WORKING:
            return True
    return False
