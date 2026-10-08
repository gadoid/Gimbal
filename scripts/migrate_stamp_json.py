"""8m 存量迁移：catalog_versions 旧形状戳 → binding 形状 + shape_hash。

处理（设计 8m 已定「迁移」；评审 P0-6 / 第三轮 R6）：
- spec_json: api{...} → binding（body_type 并入、version/updated_at 删除、
  responses 键 int→str）
- version 列: semver → 该端点当前形状的 shape_hash（首见基线口径 ——
  迁移即基线，diff 归零；语义字段标注期间 hash 稳定,不触发风暴）
- 退役端点戳（order_dispatch / order_add_demo，S1-0 B3 移除）: 删除

覆盖口径（第三轮 R6：不再无差别覆盖）：
- 非 hex 戳（旧 semver）→ 按首见基线重落；
- hex 戳 == 当前口径 hash → 已迁移，跳过；
- hex 戳 == 旧口径 hash（嵌套 children 说明字段未剔除版）→ 纯口径迁移，
  重写为当前口径 hash（R8 口径修正后的重跑路径）；
- 其余 hex 戳（真源已变化 = 真实待适配）→ **保留不动**并报告，避免抹掉
  本该 pending 的真实变更。

用法:
    python scripts/migrate_stamp_json.py --db "$GIMBAL_DB_URL" [--dry-run]
连接串不再有默认值（评审 R6：凭据不得进仓库）—— ``--db`` 或环境变量
``GIMBAL_DB_URL`` 二选一必填。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "src" / "gimbal-platform" / "backend"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

RETIRED = {"fin.order_entrust.order_dispatch", "fin.order.order_add_demo",
           "fin.order_entrust.order_confirm"}  # order_confirm 已并入 order_add(2026-09-06)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _is_hex_stamp(version: str) -> bool:
    return bool(_HEX64.match(version))


def _legacy_shape_hash(spec) -> str:
    """旧口径 shape_hash（第三轮 R8 修正前：声明条目只剔顶层说明字段，
    嵌套 children 的 description/ui_kind 仍进投影）。用于识别「口径迁移」
    与「真源已变化」——与 canonical 现行实现的差异仅 _decl_shape 的递归。"""
    from gimbal_plate.dialect.canonical import _sorted_dicts

    exclude = {"description", "ui_kind"}

    def flat(entries):
        return [
            {k: v for k, v in e.model_dump(mode="json", exclude_defaults=True).items()
             if k not in exclude}
            for e in entries
        ]

    proj: dict = {"binding": spec.binding.model_dump(mode="json", exclude_defaults=True)}
    if spec.request is not None and spec.request.declarations:
        proj["request"] = {"declarations": flat(spec.request.declarations)}
    if spec.responses:
        proj["responses"] = {
            o: {"declarations": flat(r.declarations)}
            for o, r in sorted(spec.responses.items())
        }
    data = json.dumps(_sorted_dicts(proj), ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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


async def main(db_url: str, *, dry_run: bool) -> int:
    """以 systems/ 真源为权威重写整份戳。

    spec_json = /full item 形状,version = shape_hash;
    语义 = 迁移即首见基线(diff 归零)。覆盖口径见模块 docstring。
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
    migrated = deleted = current = diverged = drift = missing = 0
    async with engine.connect() as conn:
        rows = (await conn.execute(
            text("SELECT endpoint_id, version, spec_json FROM catalog_versions")
        )).mappings().all()
        for row in rows:
            eid = row["endpoint_id"]
            if eid in RETIRED:
                if dry_run:
                    print(f"  would delete (retired): {eid}")
                else:
                    await conn.execute(text(
                        "DELETE FROM catalog_versions WHERE endpoint_id = :e"),
                        {"e": eid})
                deleted += 1
                continue
            ep = tree.get(eid)
            if ep is None:
                print(f"  ! {eid}: 真源树中不存在且不在退役名单 — 保留旧戳")
                missing += 1
                continue
            old_ver = str(row["version"] or "")
            new_h = shape_hash(ep)
            item = EndpointDetailView.from_spec(ep).model_dump(
                mode="json", exclude_none=True)
            if _is_hex_stamp(old_ver):
                if old_ver == new_h:
                    current += 1          # 已是当前口径
                    continue
                if old_ver != _legacy_shape_hash(ep):
                    # 戳既非当前口径、也非旧口径 ⇒ 真源在两次口径之间已
                    # 变化 —— 这是真实待适配,覆盖它等于抹掉一个 pending。
                    print(f"  ! {eid}: 戳与新旧口径均不符(真源已变化)— 保留")
                    diverged += 1
                    continue
            else:
                # 旧 semver 戳:重落前先字段比对(评审 N3)——旧 spec_json
                # 有形状缓存且与当前真源有漂移(删字段/增字段/改值域)时
                # 保留为待适配,不静默吞掉;无形状缓存则首见基线静默重落。
                old_spec = row["spec_json"] if isinstance(row["spec_json"], dict) else {}
                from app.services.adaptation_ops import (
                    diff_field_specs, spec_has_field_cache)
                if spec_has_field_cache(old_spec) and diff_field_specs(old_spec, item):
                    print(f"  ! {eid}: 旧戳形状有漂移(真实待适配)— 保留")
                    drift += 1
                    continue
            if dry_run:
                print(f"  would restamp {'(rehash)' if _is_hex_stamp(old_ver) else '(baseline)'}: "
                      f"{eid} {old_ver[:12] or old_ver!r} -> {new_h[:12]}")
                migrated += 1
                continue
            await conn.execute(text(
                "UPDATE catalog_versions SET version = :v, spec_json = :s "
                "WHERE endpoint_id = :e"),
                {"v": new_h, "s": json.dumps(item, ensure_ascii=False), "e": eid})
            migrated += 1
        if dry_run:
            await conn.rollback()
        else:
            await conn.commit()
    await engine.dispose()
    mode = " [dry-run]" if dry_run else ""
    print(f"8m 迁移{mode}: {migrated} 重落 / {deleted} 删除(退役) / "
          f"{current} 已当前 / {diverged} 真源已变(保留) / "
          f"{drift} 旧戳漂移(保留为待适配) / {missing} 缺真源(保留)")
    return 0 if (diverged == 0 and drift == 0 and missing == 0) else 1


if __name__ == "__main__":
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db", default=None,
        help="目标库连接串(必填,或经环境变量 GIMBAL_DB_URL 提供;无默认值)")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印将发生的变更,不写库")
    args = ap.parse_args()
    _db = args.db or os.environ.get("GIMBAL_DB_URL") or ""
    if not _db:
        print("error: 缺少数据库连接串 — 用 --db 或环境变量 GIMBAL_DB_URL 指定"
              "(不再提供带凭据的默认值)", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(_db, dry_run=args.dry_run)))
