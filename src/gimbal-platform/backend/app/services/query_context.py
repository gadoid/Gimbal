"""查询取数上下文解析器。

rows 路由的前提(query_views.py 路由 docstring)——「service_url 由
前端按 authored config.services 求值后传入,后端无集中 resolver」——
已不成立(ADR-0003 #13):config.services 的地址面已退役,新场景恒空
⇒ 恒 ``service_url_required``。本模块把执行链同款
解析接到查询面,**复用既有单源,不建第二套规则**:

* 读权限:表 B scenario.read(与 GET /scenarios/{id}/draft 同判;
  不可读同 404 scenario_not_found,不泄露存在性);
* 执行标签:``env_chain.resolve_execution_tag``(身份 > 项目默认 >
  平台默认;混拼 409,与派发侧硬拦同口径);
* 地址:``service_aliases.deployment_urls`` 部署表单源(authz M2a S6);
* 查询身份兜底:方案绑定(``schemeId`` 解析,§7.1)→ 账户组合垫底 →
  步骤服务的生效别名(``effective_alias``);步骤直接身份声明
  (``${auth.<tag>}`` 模板 ∪ ``call.user`` 直引,§7.2)单源优先,
  多个直接身份无法唯一判定 → 422 ``query_identity_ambiguous``
  (§7.3,不取第一个);显式 ``query_alias`` 在路由层先行覆盖;
* ``owner_id`` = 当前查询执行人:个人凭证按调用者 ``user.id`` 装载,
  与派发侧 ``prepare_exec`` 同口径;项目凭证另经成员闸走场景项目池。
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
    owner_id: int             # 个人凭证池归属:当前查询执行人
    query_alias: str | None   # 缺省查询别名(显式 query_alias 优先)
    project_id: "int | None" = None  # §7.4 池通道:场景所属项目(credentialSource=project 消费)


async def resolve_query_context(
    db: AsyncSession, *, user, scenario_id: str, step_index: int,
    scheme_id: str | None = None,
    query_alias_override: str | None = None,
    service_url_override: str | None = None,
) -> QueryContext:
    """已保存场景 + 步骤位 → 查询地址与身份(全链服务端解析)。

    未保存草稿没有稳定 scenario_id —— 调用方(前端)应先保存再查
    (01-04 §5.2 推荐路径);本函数只受理已保存场景。

    方案感知(账户组合 §7.1,2026-11-25 批 3):绑定基础从「定义级」
    改为「schemeId 解析 + 组合垫底」—— 查询视角 = 执行视角的既有裁定;
    **未保存编辑态不参与**:后端只认库中方案行(schemeId 解析到已保存
    内容;跨场景/已删回落默认方案,resolve_for_run 同款),编排器在
    方案 dirty 时提示前端处理(不强制先保存)。
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
    # 生效身份(§7.1):schemeId 解析 → 方案绑定 → 组合垫底 →
    # effective_alias;raw 不吃任何方案配方。垫底机械半边与执行面同源。
    from . import account_combo as _ac
    from .run_materialize import referenced_services
    from .run_params import RAW_SCHEME_ID
    from .scheme_store import normalized, resolve_for_run

    scheme = (None if scheme_id == RAW_SCHEME_ID else
              await resolve_for_run(db, row.scenario_id, scheme_id))
    scheme_payload = normalized(scheme.payload if scheme is not None else {})
    combo = await _ac.scheme_combo(db, scheme_payload)
    bindings = _ac.pad_bindings(
        scheme_payload.get("serviceBindings") or {}, combo)
    # 步骤直接身份声明(§7.2):${auth.*} 模板 ∪ call.user 直引,后端
    # 单源扫描器(执行面同款)—— 前端 headers-only 扫描补齐项;
    # 多个直接身份无法唯一判定 → 422 不猜测(§7.3,显式 query_alias
    # 在路由层先行覆盖,不进本判定)。
    from .auth_ref_scan import step_auth_refs

    declared = step_auth_refs(step if isinstance(step, dict) else {})
    if query_alias_override is not None:
        alias = query_alias_override
    else:
        if len(set(declared)) > 1:
            raise QueryContextError(
                "query_identity_ambiguous",
                f"步骤 #{step_index} 声明了多个直接身份"
                f"({'、'.join(dict.fromkeys(declared))}),无法唯一判定"
                "查询身份 —— 请显式指定 query_alias 或收敛步骤身份")
        alias = declared[0] if declared else effective_alias(svc, bindings)
    try:
        await _ac.referenced_combo_gate(
            db, combo, referenced_services([step]),
            {**bindings, svc: {"alias": alias}})
    except _ac.ComboIdentityMissing as e:
        raise QueryContextError(
            "identity_combo_missing", e.message, status=409) from e
    if service_url_override is not None:
        if not service_url_override.startswith(("http://", "https://")):
            raise QueryContextError(
                "service_url_invalid",
                f"显式查询地址不是 http(s): {service_url_override!r}")
        return QueryContext(
            service=svc, service_url=service_url_override,
            owner_id=user.id, query_alias=alias,
            project_id=row.project_id)
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
        service=svc, service_url=url, owner_id=user.id,
        query_alias=alias, project_id=row.project_id)
