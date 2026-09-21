"""适配边界白名单(P1b/M2.5,权限方案 §0.3/§1.2 第五轮)。

「字段面可见、值面不可见」:operator 经适配 apply/rollback **写**他人
private 场景,却始终**没有**该场景的读权 —— 写入由字段级 op 驱动,
operator 永不获得场景全文;``before_json`` 是内部回滚数据,**永不出
API**。本测试把这条边界钉死:否则将来有人为做「回滚预览」把
before_json 开出去,边界就无声破了。
"""
from __future__ import annotations

import json

from httpx import AsyncClient

from tests.helpers import register_and_login, make_draft


async def test_before_json_never_leaks_and_snapshot_ref_is_whitelist(
    client: AsyncClient, plate,
):
    admin = await register_and_login(client, "boundary_admin", "admin-pass-123")
    # 受影响场景(admin 自建 —— 场景内容属于「值面」)
    r = await client.post(
        "/api/scenarios", headers=admin,
        json=make_draft("sc-boundary", system=["fin"]),
    )
    assert r.status_code == 201, r.text

    # 造一个含 before 存档的批次(直接落库,批次 API 走 plate 目录 mock)
    from app.core import db as db_module
    from app.models import AdaptationBatch, AdaptationOp, AdaptationSnapshot
    from datetime import datetime, timezone

    secret_payload = {
        "payload": {"definition": {"meta": {"name": "机密场景全文"},
                                   "steps": [{"id": "s1", "secret": "值面"}]}},
        "internal_note": "before_json 永不出 API",
    }
    async with db_module.SessionLocal() as s:
        s.add(AdaptationBatch(
            batch_id="bt-boundary", endpoint_id="fin.order.add",
            from_version="1.0.0", to_version="1.1.0", status="applying",
            operator_id=1, operator_name="boundary_admin"))
        s.add(AdaptationSnapshot(
            batch_id="bt-boundary", entity_type="scenario",
            entity_id="sc-boundary", before_json=secret_payload))
        s.add(AdaptationOp(
            batch_id="bt-boundary", scenario_id="sc-boundary",
            op_type="renameStepName", payload={"from": "s1", "to": "S1"},
            status="pending"))
        await s.commit()

    # 批次详情(含 snapshots 的唯一读面):SnapshotRef 白名单之外的字段
    # 一律不得出现
    r = await client.get("/api/adaptations/batches/bt-boundary", headers=admin)
    assert r.status_code == 200, r.text
    raw = json.dumps(r.json(), ensure_ascii=False)
    assert "before_json" not in raw and "beforeJson" not in raw
    assert "机密场景全文" not in raw and "值面" not in raw

    snaps = r.json().get("snapshots") or []
    assert snaps, "批次详情应含 SnapshotRef 列表"
    for snap in snaps:
        # 白名单:仅 entityType / entityId(§1.2 第五轮「已回读核实」)
        assert set(snap.keys()) <= {"entityType", "entityId"}, snap

    # schema 面断言:SnapshotRef 字段集即白名单本身
    from app.schemas.adaptations import SnapshotRef
    assert set(SnapshotRef.model_fields) == {"entity_type", "entity_id"}
