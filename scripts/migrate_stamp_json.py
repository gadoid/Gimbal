"""8m 存量迁移：catalog_versions 旧形状戳 → binding 形状 + shape_hash。

处理（设计 8m 已定「迁移」；评审 P0-6）：
- spec_json: api{...} → binding（body_type 并入、version/updated_at 删除、
  responses 键 int→str）
- version 列: semver → 该端点当前形状的 shape_hash（首见基线口径 ——
  迁移即基线，diff 归零；语义字段标注期间 hash 稳定,不触发风暴）
- 退役端点戳（order_dispatch / order_add_demo，S1-0 B3 移除）: 删除
用法: python scripts/migrate_stamp_json.py [--db postgresql+asyncpg://gimbal:gimbal@127.0.0.1:15432/gimbal]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src" / "gimbal-plate"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

RETIRED = {"fin.order_entrust.order_dispatch", "fin.order.order_add_demo",
           "fin.order_entrust.order_confirm"}  # order_confirm 已并入 order_add(2026-09-06)


def convert_spec(old: dict) -> dict | None:
    """弃用(旧戳遗留键太多,改用真源树重写)。保留作回退参考。"""
    api = old.get("api") or old.get("binding")
    if not api:
        return None
    binding = {k: v for k, v in api.items() if k != "service"}
    binding.setdefault("protocol", "http")
    req = old.get("request") or {}
    if "body_type" in req:
        binding.setdefault("body_type", req.pop("body_type"))
    responses = {
        str(k): {kk: vv for kk, vv in v.items() if kk != "status"}
        for k, v in (old.get("responses") or {}).items()
    }
    new = {
        "id": old["id"], "system": old["system"], "service": old["service"],
        "name": old["name"],
        "binding": binding,
        "responses": responses,
        "metadata": old.get("metadata") or {},
    }
    if old.get("description"):
        new["description"] = old["description"]
    if old.get("capability"):
        new["capability"] = old["capability"]
    if req:
        new["request"] = req
    if old.get("query_views") is not None:
        new["query_views"] = old["query_views"]
    return new


async def main(db_url: str) -> int:
    """以 systems/ 真源为权威重写整份戳。

    spec_json = /full item 形状,version = shape_hash;
    语义 = 迁移即首见基线(diff 归零)。
    """
    from gimbal_plate.dialect import EndpointSpec, parse_markdown
    from gimbal_plate.dialect.canonical import shape_hash
    from gimbal_plate.http.views import EndpointDetailView

    tree: dict[str, EndpointSpec] = {}
    for md in sorted((_REPO / "systems").rglob("*.md")):
        d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        for b in d.blocks("endpoint"):
            for m in b.models():
                if isinstance(m, EndpointSpec):
                    tree[m.id] = m
    engine = create_async_engine(db_url)
    migrated = deleted = skipped = 0
    async with engine.begin() as conn:
        rows = (await conn.execute(
            text("SELECT endpoint_id, version, spec_json FROM catalog_versions")
        )).mappings().all()
        for row in rows:
            eid = row["endpoint_id"]
            if eid in RETIRED:
                await conn.execute(text(
                    "DELETE FROM catalog_versions WHERE endpoint_id = :e"),
                    {"e": eid})
                deleted += 1
                continue
            ep = tree.get(eid)
            if ep is None:
                print(f"  ! {eid}: 真源树中不存在且不在退役名单 — 保留旧戳")
                skipped += 1
                continue
            item = EndpointDetailView.from_spec(ep).model_dump(
                mode="json", exclude_none=True)
            h = shape_hash(ep)
            await conn.execute(text(
                "UPDATE catalog_versions SET version = :v, spec_json = :s "
                "WHERE endpoint_id = :e"),
                {"v": h, "s": json.dumps(item, ensure_ascii=False), "e": eid})
            migrated += 1
    await engine.dispose()
    print(f"8m 迁移完成: {migrated} 迁移 / {deleted} 删除(退役端点) / {skipped} 跳过")
    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=(
        "postgresql+asyncpg://gimbal:gimbal@127.0.0.1:15432/gimbal"))
    raise SystemExit(asyncio.run(main(ap.parse_args().db)))
