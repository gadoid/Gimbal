"""query-views rows 路由 —— 组合期取数解释器入口(spec §4.1)。

CurrentUser 鉴权(个人凭证属于当前查询人,不是场景作者;项目凭证
另经场景所属普通项目的成员闸)。

地址来源双通道二选一:
* **上下文通道**(推荐,前端默认):``scenarioId + stepIndex`` →
  ``query_context.resolve_query_context`` 服务端按执行链同款解析
  (步骤服务 → 生效身份 → 标签链 → 部署表);前提「service_url 由
  前端按 authored config.services 求值传入」已不成立(ADR-0003
  #13;新场景 config.services 恒空 ⇒ 恒 service_url_required);
* **显式覆盖通道**:`service_url` 直传保留(调试/私有 SUT 直连),
  给定时跳过上下文解析。两通道都缺 → ``query_context_required``。
"""
from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthSession
from app.core.db import get_db
from app.core.deps import CurrentUser
from app.services import query_context, query_view_runner
from app.services.run_prepare import _materialize_identities, _resolve_identities

router = APIRouter(prefix="/query-views", tags=["query-views"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _loader(db: DbSession, cred_project_id: int | None = None):
    """凭证装载闭包:runner 在凭证闸内按需调用(黑名单键在它之前
    已降级 —— 绝不急切装载,保持"401 拉黑不打 DB"语义)。

    重构 + §8.3:``alias`` = 身份条目名 → 条目 ref → 账户(取用不
    校验标签 —— 同标签优先 → system 唯一;解不到 = None,与旧缺行
    同语义)。

    账户组合 §7.4(批 3):``cred_project_id`` 池通道(缺省 = 执行
    身份个人池;项目场景 + credentialSource=project 经成员闸 →
    项目池)—— 与执行链 ``_pool_clause`` 同源互斥口径;多候选账户
    无唯一命中 → 422 ``query_identity_ambiguous``(不猜测,旧口径
    静默降级 None 会误导成「凭证未配置」)。"""
    async def load(owner_id: int, alias: str) -> AuthSession | None:
        picked, _miss, amb = await _resolve_identities(
            db, owner_id, [alias], cred_project_id=cred_project_id)
        if amb:
            from app.services.query_view_runner import QueryViewError
            raise QueryViewError(
                "query_identity_ambiguous",
                f"查询凭证 {alias!r} 命中多候选账户(同引用多行且无同"
                "标签唯一命中),请调整条目环境标签或清理同名账户",
                status=422)
        if not picked:
            return None
        resolved = await _materialize_identities(db, picked)
        r = resolved.get(alias)
        if r is None:
            return None
        return AuthSession(
            url=r.url,
            username=r.username,
            password=r.password,
        )
    return load


@router.get("")
async def list_views(user: CurrentUser) -> dict:
    """索引代理(§13.3):前端参数段消费 query_params;复用 runner 的
    plate memo + 熔断,零新增状态。"""
    items = await query_view_runner.fetch_query_view_index()
    return {"items": items}


@router.get("/{name}/rows")
async def get_rows(
    name: str,
    user: CurrentUser,
    db: DbSession,
    refresh: bool = False,
    service_url: str = "",
    query_alias: str | None = None,
    service: str | None = None,
    params: str = "",
    # 01-04 上下文通道:已保存场景 + 步骤位(与 service_url 显式覆盖
    # 二选一;都不给 → query_context_required)
    scenario_id: Annotated[str | None, Query(alias="scenarioId")] = None,
    step_index: Annotated[int | None, Query(alias="stepIndex", ge=0)] = None,
    # 账户组合 §7.1(批 3):方案感知 —— 前端传当前生效方案;缺省回落
    # 默认方案(resolve_for_run 同款);**未保存编辑态不参与** —— 后端
    # 只认库中方案行,方案 dirty 提示是前端面(§12.6 口径)。
    scheme_id: Annotated[str | None, Query(alias="schemeId")] = None,
    # 账户组合 §7.4:凭证池通道(与执行链 credentialSource 同形);
    # project → 成员闸后走场景所属项目池,缺省个人池(当前查询人名下)。
    credential_source: Annotated[str | None,
                                 Query(alias="credentialSource")] = None,
) -> dict:
    # ── 上下文与地址覆盖:有场景上下文就解析身份/方案/池;显式 URL
    # 只覆盖地址,不绕过组合 fail-closed 与项目池成员闸。────────────
    if credential_source not in (None, "personal", "project"):
        raise HTTPException(status_code=422, detail={
            "code": "credential_source_invalid",
            "msg": "credentialSource 只能是 personal / project"})
    has_context = scenario_id is not None or step_index is not None
    if has_context and (scenario_id is None or step_index is None):
        raise HTTPException(status_code=422, detail={
            "code": "query_context_required",
            "msg": "场景上下文须同时传 scenarioId + stepIndex"})
    if not has_context and not service_url:
        raise HTTPException(status_code=422, detail={
            "code": "query_context_required",
            "msg": "缺少查询上下文:请传 scenarioId + stepIndex"
                   "(前端已保存场景),或显式 service_url(直连覆盖)"})
    if credential_source == "project" and not has_context:
        raise HTTPException(status_code=422, detail={
            "code": "credential_source_invalid",
            "msg": "项目凭证须提供场景上下文(scenarioId + stepIndex)"})

    ctx_owner_id, ctx_service, ctx_pool = user.id, service, None
    if has_context:
        try:
            ctx = await query_context.resolve_query_context(
                db, user=user, scenario_id=scenario_id,
                step_index=step_index, scheme_id=scheme_id,
                query_alias_override=query_alias,
                service_url_override=service_url or None)
        except query_context.QueryContextError as e:
            raise HTTPException(
                status_code=e.status,
                detail={"code": e.code, "msg": e.message}) from e
        service_url = ctx.service_url
        ctx_owner_id = ctx.owner_id
        ctx_service = ctx.service
        query_alias = ctx.query_alias
        if credential_source == "project":
            from app.services.zone import can_use_project_credentials

            ctx_pool = ctx.project_id
            if not await can_use_project_credentials(
                    db, user.id, ctx_pool):
                raise HTTPException(status_code=422, detail={
                    "code": "credential_source_invalid",
                    "msg": "项目凭证只能用于你所在普通项目的场景"})
    click: dict[str, Any] | None = None
    if params:
        try:
            parsed = json.loads(params)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params", "msg": "params 非合法 JSON"}) from e
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params", "msg": "params 须为 JSON 对象"})
        # §13.7 手工逃生口:参数值须为标量 —— dict/list/null 会污染下游序列化
        # (httpx 在 GET 上会把非标量 repr 字符串化)。
        if any(not isinstance(v, (str, int, float, bool))
               for v in parsed.values()):
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params",
                        "msg": "params 值须为标量(str/int/float/bool)"})
        click = {str(k): v for k, v in parsed.items()}
    try:
        r = await query_view_runner.fetch_rows(
            name, refresh=refresh, service_url=service_url,
            owner_id=ctx_owner_id, query_alias=query_alias,
            service=ctx_service,
            load_credential=_loader(db, ctx_pool), click_params=click,
            cred_pool=ctx_pool)
    except query_view_runner.QueryViewError as e:
        raise HTTPException(status_code=e.status,
                            detail={"code": e.code, "msg": e.message}) from e
    return {"view": r.view, "rows": r.rows, "truncated": r.truncated,
            "fetched_at": r.fetched_at, "cached": r.cached, "stale": r.stale}
