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


WORKING = "working"

# ── ref 类别分类器(归一方案 v1.0 §1.4/D-K,平台侧唯一原语) ─────────
# 与 plate parse_ref 对称(两侧分进程不可 import,契约测试锁定分类表:
# tests/fixtures/ref-decl-domain.json,由测试读取、生产代码不读)。
# 分类分两个域,不得混用:
#   声明域(meta.plate 声明/执行副本//convert 入参):合法 {WORKING,
#   INTEGRATION, PIN},非法 INVALID + reason(record_value=integration@…
#   是执行记录值;missing_revision=裸线,声明必须带修订号;malformed=
#   其余形状非法);
#   记录域(plate_pins 及其下游):integration@<标识> 归 INTEGRATION
#   (台账比对正是拿记录值对声明值,只认裸值则修法落不了地)。

UNDECLARED = "UNDECLARED"
INTEGRATION = "INTEGRATION"
PIN = "PIN"
INVALID = "INVALID"


def ref_category(ref: str) -> str:
    """声明域分类:``UNDECLARED | WORKING | INTEGRATION | PIN | INVALID``。

    INVALID 时另行提供 ``invalid_reason()``(平台预检按 reason 映射文案,
    不得自带前缀/形状字面判断 —— 门禁③拦)。
    """
    ref = str(ref or "").strip()
    if not ref:
        return UNDECLARED
    if ref == WORKING:
        return WORKING
    if ref == "integration":
        return INTEGRATION
    if ref.startswith("integration@"):
        return INVALID  # reason: record_value
    if "#" in ref:
        line, _, n = ref.rpartition("#")
        if not line or not n.isdigit():
            return INVALID  # reason: malformed
        return PIN
    if ref:
        return INVALID  # reason: missing_revision(裸线:声明须带修订号)
    return UNDECLARED  # pragma: no cover — unreachable,空串已early-return


def invalid_reason(ref: str) -> str | None:
    """INVALID 声明的 reason 码(与 plate 侧一致);非 INVALID 返回 None。"""
    ref = str(ref or "").strip()
    if ref.startswith("integration@"):
        return "record_value"
    if "#" in ref:
        line, _, n = ref.rpartition("#")
        if not line or not n.isdigit():
            return "malformed"
        return None  # 合法 PIN
    return "missing_revision"


def record_category(value: str) -> str:
    """记录域分类(``plate_pins`` 值):integration@<标识> 归 INTEGRATION。

    仅平台单侧(后端入口;前端另有 types/plate.ts 判定函数,两侧共享
    ref-record-domain.json 样例锁定);不进 plate 契约测试 —— 否则会
    反向要求 plate 接受追溯态声明。
    """
    value = str(value or "").strip()
    if value.startswith("integration@"):
        return INTEGRATION
    return ref_category(value)


def anchored_systems(payload: dict | None) -> set[str]:
    """锚点步骤引用的系统集（``endpoint`` 首段）。"""
    from .scenario_store import steps_from_payload  # 延迟导入防环(b2-3)

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
    from .scenario_store import definition_from_payload  # 延迟导入防环(b2-3)

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
    # b2-6(归一方案 v1.0 §1.8/D-H):integration 声明在按修订查评审之前
    # 短路 —— 现状拿 "integration" 会走到 revision_objects 抛未捕获的
    # PlateRejectedError(invalid_ref),而非分桶结果。
    integration = sorted(
        s for s in endpoints_used if ref_category(meta_plate.get(s)) == INTEGRATION)
    working = sorted(
        s for s in endpoints_used
        if (not meta_plate.get(s) or ref_category(meta_plate.get(s)) == WORKING)
        and s not in integration)
    if working:
        return False, "working", {"working_systems": working}
    if integration:
        # 归 external 桶不计入(证据单列,与未登记服务同桶不同证)
        return False, "external", {
            "external_services": [], "unknown_services": [],
            "integration_systems": integration,
        }

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


def merge_resolve_effective(
    meta_plate: dict, plate_pins: dict, resolve_result: dict,
) -> None:
    """b2.5(归一 v1.0 §1.5/b2-4,抽为可测):resolve 结果回写分流。

    PIN:写 ``plate_pins`` **并**写执行副本(执行按具体修订取投影);
    INTEGRATION:**只写 ``plate_pins``**,执行副本保持声明值
    ``integration`` —— ``integration@<标识>`` 是记录值,写副本则
    ``/convert`` 声明域 422,整条执行失败。working/空 effective 不写。
    """
    for sys_, info in (resolve_result or {}).items():
        eff = info.get('effective', '') if isinstance(info, dict) else ''
        if not eff or record_category(eff) not in (PIN, INTEGRATION):
            continue
        plate_pins[sys_] = eff
        if sys_ in meta_plate and record_category(eff) == PIN:
            meta_plate[sys_] = eff


async def graph_pins_with_identity(
    g_pins: dict, resolver,
) -> dict:
    """b2.5(归一 v1.0 §1.5/b2-4,抽为可测):图执行台账的标识补取。

    图执行链不经 resolve,INTEGRATION 会记成裸值丢标识 —— 对其补调
    ``resolver({系统: integration})`` 取 ``integration@<标识>``,结果只进
    台账(不动执行副本);失败不阻断(台账性质)。返回**新 dict**。
    """
    out = dict(g_pins or {})
    integ = [k for k, v in out.items() if ref_category(v) == INTEGRATION]
    if not integ:
        return out
    try:
        res = await resolver({k: out[k] for k in integ})
        for k in integ:
            eff = (res.get(k) or {}).get('effective', '')
            if eff:
                out[k] = eff
    except Exception:  # noqa: BLE001 — 台账性质,失败保留裸值
        pass
    return out
