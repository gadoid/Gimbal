"""变更适配编排(spec §5):目录 diff / 影响查询 / 批次生命周期。

plate 目录是接口契约权威;本模块把"plate 现状"与平台基线戳
(``catalog_versions``)对齐,产出待适配/异常清单,并编排适配批次
(存档 → 草案 → 逐条应用 → 完成/回滚)。
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.catalog_version import CatalogVersion
from ..models.composer_data_set import ComposerDataSet
from ..models.scenario_endpoint_ref import ScenarioEndpointRef
from . import plate_client
from .plate_client import PlateUnavailableError


# ─── plate 目录拉取(M6 语法路由,信封 {ok, dim, data})──────────
async def _plate_list_endpoints() -> list[dict]:
    """GET /api/endpoint → data.items(轻量视图,自带 version/updated_at)。"""
    client = plate_client.get_client()
    try:
        resp = await client.get("/api/endpoint")
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code != 200:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        raise PlateUnavailableError("plate_unavailable: no items in response")
    return [it for it in items if isinstance(it, dict)]


async def _plate_full_endpoint(endpoint_id: str) -> dict | None:
    """GET /api/endpoint/{id}/full → data.item;plate 404 → None(端点已下架)。"""
    client = plate_client.get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    item = (resp.json().get("data") or {}).get("item")
    if not isinstance(item, dict):
        raise PlateUnavailableError("plate_unavailable: no item in response")
    return item


# ─── 版本/时间比较 ────────────────────────────────────────────────
def _semver_key(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(p) for p in version.strip().split("."))
    except ValueError:
        return None


def _semver_gt(a: str, b: str) -> bool:
    """a 严格高于 b。双侧可解析 → 元组数值比较;否则退化为字典序,
    且仅"确实不同"才算前进(避免怪版本号误报 pending)。"""
    ka, kb = _semver_key(a), _semver_key(b)
    if ka is not None and kb is not None:
        return ka > kb
    return a != b and a > b


def _parse_dt(value) -> datetime | None:
    """plate 侧 ISO 时间(可带 Z / +00:00)→ naive-UTC;解析失败 → None。"""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _utcnow() -> datetime:
    """naive-UTC(与 _parse_dt 同基准;SQLite CURRENT_TIMESTAMP 亦为 UTC)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── 检测:目录 diff(spec §5.1)─────────────────────────────────
async def catalog_diff(db: AsyncSession) -> dict:
    """全量拉取 plate 目录,逐 endpoint 对戳。

    * 首见(库内无戳)→ 拉全量 spec 落基线戳 + spec_json(幂等,
      不算待适配、不建批次);列表有但 /full 404 → full_unavailable 异常;
    * plate version 严格高于戳 → pending;
    * version 相同但 plate updated_at > synced_at → C12「忘 bump」异常;
    * 库内有戳但 plate 列表无此 endpoint → missing_on_plate 异常。

    基线落库是写副作用,末尾单次 commit —— 路由层因此用 POST。
    """
    items = await _plate_list_endpoints()
    stamps: dict[str, CatalogVersion] = {
        row.endpoint_id: row
        for row in (await db.execute(select(CatalogVersion))).scalars()
    }
    pending: list[dict] = []
    anomalies: list[dict] = []
    baselined = 0
    for it in sorted(items, key=lambda x: str(x.get("id") or "")):
        eid = str(it.get("id") or "")
        ver = str(it.get("version") or "")
        if not eid:
            continue
        stamp = stamps.pop(eid, None)
        if stamp is None:
            full = await _plate_full_endpoint(eid)
            if full is None:  # 列表有、full 404:plate 自身状态不一致
                anomalies.append({
                    "endpointId": eid, "reason": "full_unavailable",
                    "detail": "plate list has endpoint but /full returned 404",
                })
                continue
            db.add(CatalogVersion(
                endpoint_id=eid, version=ver,
                spec_json=full, synced_at=_utcnow(),
            ))
            baselined += 1
            continue
        if _semver_gt(ver, stamp.version):
            pending.append({
                "endpointId": eid,
                "fromVersion": stamp.version, "toVersion": ver,
            })
            continue
        updated = _parse_dt(it.get("updated_at"))
        if ver == stamp.version and updated is not None and updated > stamp.synced_at:
            anomalies.append({
                "endpointId": eid, "reason": "updated_without_bump",
                "detail": (
                    f"plate updated_at {updated.isoformat()}"
                    f" > synced_at {stamp.synced_at.isoformat()}"
                ),
            })
    for eid in sorted(stamps):  # 库内残留、plate 已下架
        anomalies.append({
            "endpointId": eid, "reason": "missing_on_plate",
            "detail": "catalog stamp exists but plate no longer lists this endpoint",
        })
    await db.commit()
    return {"pending": pending, "anomalies": anomalies, "baselinedNow": baselined}


# ─── 影响查询(spec §5.2)────────────────────────────────────────
async def impact(
    db: AsyncSession, endpoint_id: str, field_name: str | None = None
) -> list[dict]:
    """endpoint(可选再按 field)→ 受影响清单条目(spec §5.2)。

    直填字段同样命中(索引行按字段键存在,与值是否模板无关);
    via_var 条目按数据集行实际含键(内存列存在性,D5 —— 不建
    dataset_columns 表)配对;无数据集命中时仍出一条 datasetId=None
    (变量默认值通路,D9 基线 = 直填 ∪ vars 扁平值)。
    """
    stmt = select(ScenarioEndpointRef).where(
        ScenarioEndpointRef.endpoint_id == endpoint_id
    )
    if field_name:
        stmt = stmt.where(ScenarioEndpointRef.field_name == field_name)
    stmt = stmt.order_by(
        ScenarioEndpointRef.scenario_id, ScenarioEndpointRef.step_index,
        ScenarioEndpointRef.source, ScenarioEndpointRef.field_name,
    )
    refs = (await db.execute(stmt)).scalars().all()
    if not refs:
        return []
    scenario_ids = sorted({r.scenario_id for r in refs})
    ds_rows = (await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.scenario_id.in_(scenario_ids)
        )
    )).scalars().all()
    by_scenario: dict[str, list[ComposerDataSet]] = {}
    for d in ds_rows:
        by_scenario.setdefault(d.scenario_id, []).append(d)

    out: list[dict] = []
    for r in refs:
        entry = {
            "scenarioId": r.scenario_id, "stepIndex": r.step_index,
            "source": r.source, "field": r.field_name, "viaVar": r.via_var,
            "datasetId": None, "datasetColumn": None,
        }
        if not r.via_var:  # 直填
            out.append(entry)
            continue
        entry["datasetColumn"] = r.via_var
        hit_any = False
        for d in by_scenario.get(r.scenario_id, []):
            if any(isinstance(row, dict) and r.via_var in row
                   for row in (d.rows or [])):
                out.append({**entry, "datasetId": d.dataset_id})
                hit_any = True
        if not hit_any:  # 变量默认值通路(vars 扁平值),不挂数据集
            out.append(entry)
    return out
