"""导入重锚定(2026-10-15 #323 复盘):可执行形态 → 锚定存储形态。

导出产物是引擎可执行形态 —— reproject 在 convert 出口剥掉 step.endpoint,
call 携带 binding 派生的 protocol/method/path/timeout。原样落库后步骤无
锚点,dispatch 的 carry 降级门控(run_materialize._apply_carry)会把该服务
绑定表的**全部字段**按填缺失灌进每个请求体(#323:orderPage 被灌
customer_id → fin ES terms 400 → extract None 硬失败)。本模块在导入链
(precheck/land)把能反查到的无锚点步骤回填 endpoint,还原成与编排器保存
一致的形态;binding 派生字段不在此剥 —— create_in_transaction 的
strip_binding_fields 是剥离的唯一真源,锚点 + 剥离才能过 reproject 的
binding_field_in_storage 拒收。

反查口径(保守:错锚比不锚更糟):
* 只反查 meta.plate 已声明系统 —— 锚到未声明系统会被 enforce_meta_plate
  / convert 的 version_undeclared 闸拒收,锚了也执行不了;
* 候选 = 系统的 working 端点清单(轻视图 id/service/method/path);匹配 =
  method 忽略大小写 + path 精确 + service(call.service 直等,或经服务
  目录 derive_base 归一后相等);无 service 时按 method+path 匹配,多候
  选不猜(reason=ambiguous);
* 钉定修订(ref ≠ working)对命中候选再按 /full?ref= 复核 binding 的
  method/path 仍匹配 —— working 与钉定修订间漂移时不锚
  (reason=not_in_revision;404 同判);
* plate 网络故障(PlateUnavailableError)上抛 —— 导入链对可用性
  fail-fast(convert 同口径),静默不锚 = 落库后必踩降级门控;清单被
  PlateRejectedError 拒按空目录处理,逐条 reason=catalog_unavailable
  (precheck 可见,不阻塞 —— 手写裸调用文件是合法形态)。

ui.fieldStates 不在导出产物里,重锚定不重建(面回落目录共识默认;导出时
carry 已物化进 body,显式值优先级最高,行为等价)。
"""
from __future__ import annotations

from typing import Any

from . import plate_client, service_names


def _anchor_report_entry(
    index: int, service: str | None, method: str | None, path: str | None,
    endpoint: str | None, reason: str | None,
) -> dict:
    return {"index": index, "service": service, "method": method,
            "path": path, "endpoint": endpoint, "reason": reason}


def is_anchored(entry: dict) -> bool:
    """报告条目是否已锚的**唯一**判定:``reason is None``。

    不能按 ``endpoint`` 非空判 —— not_in_revision 条目也携带命中的候选
    ID(供人排查"差一点锚到了谁"),消费者(precheck 分组/回填脚本)曾
    因此把漂移步骤误报成已锚(#323 口径缺口,2026-10-15 实测发现)。
    """
    return entry.get("reason") is None


async def reanchor_import_definition(
    definition: dict,
) -> tuple[dict, list[dict]]:
    """无锚点可执行步骤按 (service, method, path) 反查回填 endpoint。

    返回 ``(新 definition, 报告)``;无待锚步骤时原对象原样返回
    (同一引用,调用方可做身份断言)。definition 不被就地修改。
    报告条目:{index, service, method, path, endpoint, reason};
    已锚与否**只看 reason**(None = 已锚,见 :func:`is_anchored`)——
    ``endpoint`` 在 not_in_revision 时也携带被拒的命中候选,仅供排查,
    不代表已锚;未锚原因:not_in_catalog / ambiguous / not_in_revision /
    catalog_unavailable。
    """
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    steps = definition.get("steps")
    if not isinstance(meta_plate, dict) or not isinstance(steps, list):
        return definition, []

    pending: list[int] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("endpoint"):
            continue
        call = step.get("call")
        if not isinstance(call, dict):
            continue
        # 可执行形态才有 method/path(binding 派生字段);无此二者 =
        # 手写裸调用,无可反查的形状
        if (isinstance(call.get("method"), str) and call["method"]
                and isinstance(call.get("path"), str) and call["path"]):
            pending.append(i)
    if not pending:
        return definition, []

    listings: dict[str, list[dict] | None] = {}
    for system in meta_plate:
        try:
            listings[system] = await plate_client.list_system_endpoints(system)
        except plate_client.PlateRejectedError:
            listings[system] = None     # 清单被拒 = 该系统不可反查,不阻塞
    catalog = await service_names.catalog_service_names()

    report: list[dict] = []
    new_steps: list | None = None
    for i in pending:
        step = steps[i]
        call = step["call"]
        method: str = call["method"]
        path: str = call["path"]
        svc = call.get("service")
        svc = svc if isinstance(svc, str) and svc else None
        base = service_names.derive_base(svc, catalog) if svc else None

        matched: list[tuple[str, str]] = []   # (system, endpoint_id)
        for system, items in listings.items():
            if items is None:
                continue
            ref = meta_plate.get(system)
            if not isinstance(ref, str) or not ref:
                continue
            for it in items:
                if not isinstance(it, dict) or not it.get("id"):
                    continue
                if str(it.get("method") or "").upper() != method.upper():
                    continue
                if it.get("path") != path:
                    continue
                it_svc = it.get("service")
                if svc and it_svc != svc and it_svc != base:
                    continue
                matched.append((system, str(it["id"])))

        entry = _anchor_report_entry(i, svc, method, path, None, None)
        if all(v is None for v in listings.values()):
            entry["reason"] = "catalog_unavailable"
            report.append(entry)
            continue
        if not matched:
            entry["reason"] = "not_in_catalog"
            report.append(entry)
            continue
        if len({eid for _s, eid in matched}) > 1:
            entry["reason"] = "ambiguous"
            report.append(entry)
            continue

        system, eid = matched[0]
        ref = meta_plate.get(system)
        if ref and ref != "working":
            full: Any = await plate_client.get_endpoint_full_at(eid, ref)
            binding = (full or {}).get("binding") or {}
            if (full is None
                    or str(binding.get("method") or "").upper()
                    != method.upper()
                    or binding.get("path") != path):
                entry["reason"] = "not_in_revision"
                entry["endpoint"] = eid
                report.append(entry)
                continue

        if new_steps is None:
            new_steps = list(steps)
        new_steps[i] = {**step, "endpoint": eid}
        entry["endpoint"] = eid
        report.append(entry)

    if new_steps is None:
        return definition, report
    return {**definition, "steps": new_steps}, report
