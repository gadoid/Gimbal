"""Endpoint catalog proxy — Platform → Plate.

The V3 composer front-end needs the full ``declarations`` shape for
each endpoint so it can render the request body form correctly.  The
canonical view lives on Plate (``GET /api/endpoint/{id}/full``); this
module proxies the call so the front-end can hit a single API surface
(Platform) and not have to know the Plate URL.

与 strategy_catalog.py 共用错误映射 helper 与 plate_client 的进程级
AsyncClient 单例(共享连接池,MockTransport 测试替换随之生效)。
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.deps import CurrentUser
from ..services.endpoint_declarations import declared_paths_of
from ..services.field_state_resolution import validate_field_states
from ..services.plate_client import get_client, get_endpoint_full
from ..services.run_injection import injectable_universe
from .strategy_catalog import proxy_error, unavailable

router = APIRouter(prefix="/endpoint-catalog", tags=["endpoint-catalog"])


class ResolvePathsRequest(BaseModel):
    """B1 路径推断入参 — 透传 plate resolve-paths action 的 body。"""

    response_body_sample: Any
    path_prefix: Optional[str] = None


class FieldStatesValidateRequest(BaseModel):
    """§3.5 配置编辑校验入参:step 的 field_states 增量(可空)。"""

    field_states: dict[str, str] = Field(default_factory=dict)


@router.get("/{endpoint_id:path}/full")
async def get_full_endpoint(
    user: CurrentUser,
    endpoint_id: str,
) -> dict:
    """Proxy ``GET {plate}/api/endpoint/{id}/full``.

    走 ``plate_client.get_endpoint_full`` —— 与 dispatch 侧**同一条缓存条目**,
    故编辑器浏览与 dispatch 判定看到的是**同一份快照**(阶段二·① I)。超时随之
    统一为那条软取的 3s(``DECLARED_PATHS_TIMEOUT_SEC``),不再是
    ``PLATE_TIMEOUT_SEC`` 的 30s。

    返回 = plate 的 item **原样** + 一个后端算好的 ``declared_surface``:
    声明侧可注入面的**扁平字符串集合**(归一化、容器前缀、模板形态全部展开)。
    前端据此不再自己算声明半(§2.2)。item 另有消费者(候选树 UI),故**只增
    字段、不裁 item**;展开成新 dict 而非就地改 —— 缓存里那份 item 是进程级
    共享只读面(``EndpointFull.item`` 的契约)。

    ``declared_surface`` 为 ``None`` ⇒ 该端点的**声明面**不可解析(降级),前端
    从严只认 body 面。**不用 [] 冒充**:空目录(真无声明,给 ``["$"]``)与降级
    是两件事。契约 item 本身不可得时本路由直接 502/404,客户端看不到这个字段。
    """
    res = await get_endpoint_full(endpoint_id)
    if res.item is None:
        # 状态映射:plate 404 → endpoint_not_found;拿到响应但信封无 item →
        # plate_invalid_envelope;其余(连接失败 / 5xx)→ unavailable。
        # 必须嵌在 item is None 里:刷新失败时旧快照仍在回退窗内 ⇒ item 是好的
        # 而 status 可能是那次失败的 404 —— 无条件映射会把「健康的旧契约服务」
        # 报成「端点不存在」。
        if res.status == 404:
            raise HTTPException(status_code=404, detail={
                "code": "endpoint_not_found", "message": "endpoint not found"})
        if res.status is not None and res.status < 500:
            raise HTTPException(status_code=502, detail={
                "code": "plate_invalid_envelope",
                "message": f"no item in response ({res.reason})"})
        raise HTTPException(status_code=502, detail={
            "code": "plate_unavailable", "message": res.reason})

    paths = await declared_paths_of(endpoint_id)
    # 降级判定在 injectable_universe 之前:它对 None 与 () 不加区分(run_injection
    # 明文),先算会把降级错报成「只有 $」。
    surface = None if paths is None else sorted(injectable_universe(None, paths))
    return {**res.item, "declared_surface": surface}


@router.post("/resolve-paths")
async def resolve_paths(user: CurrentUser, body: ResolvePathsRequest) -> list[dict]:
    """Proxy ``POST {plate}/api/endpoint/action/resolve-paths``.

    B1 路径推断: 响应样本 → 候选 JSONPath(数组展开下标),供编排页
    策略路径字段(assertion.target / extract.expression)点选 — 替代
    断言面缺失时的静默猜测。action 名是连字符(fin 系统
    endpoint dim 注册名)。解 ``data.paths`` 返回数组(前端下拉直接用)。
    """
    client = get_client()
    try:
        resp = await client.post(
            "/api/endpoint/action/resolve-paths",
            json={
                "response_body_sample": body.response_body_sample,
                "path_prefix": body.path_prefix,
            },
        )
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(resp, context="resolve-paths")

    paths = (resp.json().get("data") or {}).get("paths")
    if not isinstance(paths, list):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no paths in response"},
        )
    return paths


@router.post("/{endpoint_id:path}/field-states/validate")
async def validate_step_field_states(
    user: CurrentUser,
    endpoint_id: str,
    body: FieldStatesValidateRequest,
) -> dict:
    """§3.5 配置编辑校验:plate 目录 + step.field_states 增量 → 合成态裁决。

    编辑器在改字段状态时调用:``errors`` 非空 = 拒(树一致性),
    ``warnings`` 仅提示(required 落 carry / DESCRIPTIVE 进 form /
    目录外 stale path)。校验跑在合成态上 —— 目录本身一致但增量
    破坏整传一致性同样拒。目录拉取复用 /full 代理语义(错误映射
    同款:plate 不可达 502 / 404 endpoint_not_found)。
    """
    client = get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(
            resp,
            context=endpoint_id,
            not_found_code="endpoint_not_found",
            not_found_msg="endpoint not found",
        )
    item = (resp.json().get("data") or {}).get("item")
    if not isinstance(item, dict):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope",
                    "message": "no item in response"},
        )
    decls = ((item.get("request") or {}).get("declarations")) or []
    return validate_field_states(decls, body.field_states)
