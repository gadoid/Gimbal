"""查询取数上下文解析器(01-04 修复批,2026-11-24)。

rows 路由的旧前提 —— 「service_url 由前端按 authored config.services
求值后传入,后端无集中 resolver」(query_views.py 路由 docstring,
2026-09-07 spec)—— 随 D2 环境退役失效:config.services 的地址面已
退役,新场景恒空 ⇒ 恒 ``service_url_required``。本模块把执行链同款
解析接到查询面,**复用既有单源,不建第二套规则**:

* 读权限:表 B scenario.read(与 GET /scenarios/{id}/draft 同判;
  不可读同 404 scenario_not_found,不泄露存在性);
* 执行标签:``env_chain.resolve_execution_tag``(身份 > 项目默认 >
  平台默认;混拼 409,与派发侧硬拦同口径);
* 地址:``service_aliases.deployment_urls`` 部署表单源(authz M2a S6);
* 查询身份兜底:步骤服务的生效别名(``effective_alias`` —— 执行视角
  = 查询视角的既有裁定不变;headers ``${auth.<tag>}`` 引用仍由前端
  解析后经 ``query_alias`` 显式覆盖,此处只做缺省);
* ``owner_id`` = 场景属主:查询凭证按**执行身份**装载(与派发侧
  prepare_exec 同视角 —— 成员查询项目场景,用的也是场景执行身份)。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.env_chain import (
    EnvMixed, deployment_urls, resolve_execution_tag,
)
from ..services.scenario_store import definition_from_payload, get_row
from ..services.service_aliases import effective_alias


class QueryContextError(Exception):
    """上下文解析失败;路由层翻译为 HTTP(detail={code, msg})。

    (``self.code = code`` 单赋值形态是 gen_api_contract 的 coded-exc
    发现判据 —— 保持该形态,错误码才进契约快照。)
    """

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class QueryContext:
    """rows 调用面所需的最小解析产物。"""

    service: str              # 步骤服务键(service_mismatch 校验面)
    service_url: str          # 当前执行标签的部署地址
    owner_id: int             # 查询凭证装载按场景执行身份
    query_alias: str | None   # 缺省查询别名(显式 query_alias 优先)


async def resolve_query_context(
    db: AsyncSession, *, user, scenario_id: str, step_index: int,
) -> QueryContext:
    """已保存场景 + 步骤位 → 查询地址与身份(全链服务端解析)。

    未保存草稿没有稳定 scenario_id —— 调用方(前端)应先保存再查
    (01-04 §5.2 推荐路径);本函数只受理已保存场景。
    """
    from ..routers._ownership import can_read_scenario_row

    row = await get_row(db, scenario_id)
    if row is None or not await can_read_scenario_row(db, user, row):
        # 不可读与不存在同 404(不泄露存在性,draft 读闸同款)
        raise QueryContextError(
            "scenario_not_found", f"场景不存在或不可读: {scenario_id}",
            status=404)
    definition = definition_from_payload(row.payload)
    steps = definition.get("steps") or []
    if not isinstance(step_index, int) or not 0 <= step_index < len(steps):
        raise QueryContextError(
            "query_context_required",
            f"步骤上下文无效: stepIndex={step_index!r}(steps={len(steps)})")
    step = steps[step_index]
    call = step.get("call") if isinstance(step, dict) else None
    svc = call.get("service") if isinstance(call, dict) else None
    if not isinstance(svc, str) or not svc:
        raise QueryContextError(
            "step_service_required",
            f"步骤 #{step_index} 没有服务绑定(call.service 为空)")
    # 生效身份(绑定换名口径同执行链):定义级 serviceBindings 单源
    bindings = (definition.get("config") or {}).get("serviceBindings")
    alias = effective_alias(svc, bindings)
    # 执行标签:身份 > 项目默认 > 平台默认;条目缺行不参与标签判定
    try:
        tag = await resolve_execution_tag(
            db, identity_names=[alias], project_id=row.project_id)
    except EnvMixed as e:
        # 混拼 = 同一执行必须同一地址/登录口的既有不变量;派发侧 409
        # 硬拦,查询面同口径(静默选边会打到错误环境的部署地址)。
        raise QueryContextError("environment_mixed", str(e), status=409) from e
    if tag.env_id is None:
        raise QueryContextError(
            "deployment_url_missing",
            f"服务 {svc} 无部署地址:环境链全空(身份/项目/平台默认皆未配)")
    urls = await deployment_urls(db, [svc], tag.env_id)
    url = urls.get(svc)
    if not url:
        raise QueryContextError(
            "deployment_url_missing",
            f"服务 {svc} 在环境 #{tag.env_id} 无部署地址(部署表缺行)")
    if not url.startswith(("http://", "https://")):
        raise QueryContextError(
            "service_url_invalid",
            f"服务 {svc} 的部署地址不是 http(s): {url!r}")
    return QueryContext(
        service=svc, service_url=url, owner_id=row.owner_id,
        query_alias=alias)
