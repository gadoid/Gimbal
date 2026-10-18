"""服务目录聚合端点(M5,PG迁移方案 §7 M5-1 / 债 11)。

前端 `utils/catalog-services.ts` 原直连 plate `/api/endpoint?per_page=500`
在浏览器侧聚合(服务画像页/服务信息管理页/工作台卡三处)—— 超 500 静默
丢 + 每个浏览器一份全量。收编:平台后端代理拉取 + 聚合 + 30s TTL 进程
缓存,一次请求供给三处。
"""
from __future__ import annotations

import time
from fastapi import APIRouter
from pydantic import BaseModel

from ..core.deps import CurrentUser
from ..services import plate_client

router = APIRouter(prefix="/catalog", tags=["catalog"])

_TTL_SEC = 30.0

_cache: dict[str, object] = {"at": 0.0, "payload": None}


class CatalogServiceRow(BaseModel):
    name: str
    system: str
    endpointCount: int
    kind: str = "sut"  # b2-7:由端点行带出(归一 v1.0 §3.1/§3.4)


class CatalogEndpointRef(BaseModel):
    id: str
    service: str


class CatalogServicesOut(BaseModel):
    services: list[CatalogServiceRow]
    """endpoint_id → service 映射(适配中心「看影响面」跳线索板用)。"""
    endpoints: list[CatalogEndpointRef]
    """plate 目录是否可达(不可达 → 空集 + reachable=False,面板据此降级)。"""
    plateReachable: bool = True


async def _fetch_and_aggregate() -> CatalogServicesOut:
    """b2-7(归一 v1.0 §3.3):经 plate_client 唯一访问件取聚合行(带 kind)。"""
    rows = await plate_client.catalog_service_rows()
    if not rows:
        return CatalogServicesOut(services=[], endpoints=[],
                                  plateReachable=False)
    services = [CatalogServiceRow(**r) for r in rows]
    endpoint_refs = []
    for it in await plate_client.plate_endpoints_light():
        if it.get("id") and it.get("service"):
            endpoint_refs.append(CatalogEndpointRef(
                id=str(it["id"]), service=str(it["service"])))
    return CatalogServicesOut(services=services, endpoints=endpoint_refs)

    by_service: dict[str, CatalogServiceRow] = {}
    endpoint_refs: list[CatalogEndpointRef] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        service = str(it.get("service") or "")
        system = str(it.get("system") or "")
        if not service or not system:
            continue
        row = by_service.get(service)
        if row is None:
            by_service[service] = CatalogServiceRow(
                name=service, system=system, endpointCount=1)
        else:
            row.endpointCount += 1
        if it.get("id"):
            endpoint_refs.append(CatalogEndpointRef(
                id=str(it["id"]), service=service))
    return CatalogServicesOut(
        services=sorted(by_service.values(), key=lambda r: r.name),
        endpoints=endpoint_refs,
    )


async def _cached_payload() -> CatalogServicesOut:
    """30s TTL。降级结果(plate 不可达)不进缓存 —— 恢复后立刻可见。"""
    now = time.monotonic()
    if _cache["payload"] is not None and now - float(_cache["at"]) < _TTL_SEC:
        return _cache["payload"]  # type: ignore[return-value]
    payload = await _fetch_and_aggregate()
    if payload.plateReachable:
        _cache["payload"] = payload
        _cache["at"] = now
    return payload


def reset_catalog_cache_for_tests() -> None:
    _cache["payload"] = None
    _cache["at"] = 0.0


@router.get("/services", response_model=CatalogServicesOut)
async def get_catalog_services(
    user: CurrentUser,
) -> CatalogServicesOut:
    """服务目录聚合(30s TTL 缓存)。"""
    return await _cached_payload()
