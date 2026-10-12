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
    """任一受管系统 working(显式声明或未钉修订)→ 预览执行。

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


async def assess_baseline(
    db,
    *,
    meta_plate: dict,
    endpoints_used: dict[str, list[str] | set[str]],
    unanchored_services: list[str],
    review_lookup=None,
) -> tuple[bool, str | None, dict]:
    """入库标准判定(版本模型 4.3 / A-3 / W7)。

    eligible = 无受管系统 working ∧ 钉定修订下用到的接口全部已评审 ∧
    无 external 服务。返回 ``(eligible, 首要阻塞原因, 证据)``;阻塞
    短路(working > unreviewed > external),证据只含已收集部分。
    ``review_lookup(system, ref) -> {对象id: review}`` 可注入(测试);
    缺省 plate_client.revision_objects(修订 manifest.objects 已带逐
    对象 review —— plate 侧零改动,W8 侦察结论)。

    unknown 服务(未登记别名)按 external 阻塞(保守:未登记 = 未受管,
    无契约可验证),证据里单列 ``unknown_services``。
    """
    working = sorted(
        s for s in endpoints_used
        if not meta_plate.get(s) or meta_plate.get(s) == WORKING)
    if working:
        return False, "working", {"working_systems": working}

    if review_lookup is None:
        from . import plate_client
        review_lookup = plate_client.revision_objects
    unreviewed: dict[str, list[str]] = {}
    for sys_, ids in endpoints_used.items():
        ref = meta_plate.get(sys_) or ""
        if not ref or ref == WORKING:
            continue          # 已被 working 拦,不再触 plate
        reviews = await review_lookup(sys_, ref)
        bad = sorted(eid for eid in ids if reviews.get(eid) != "reviewed")
        if bad:
            unreviewed[sys_] = bad
    if unreviewed:
        return False, "unreviewed", {"unreviewed_endpoints": unreviewed}

    from .service_aliases import classify_services
    classified = await classify_services(db, unanchored_services)
    if classified["external"] or classified["unknown"]:
        return False, "external", {
            "external_services": classified["external"],
            "unknown_services": classified["unknown"],
        }
    return True, None, {}
