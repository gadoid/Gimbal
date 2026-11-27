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
* 查询身份:显式 ``query_alias`` > 步骤直接身份 > 步骤服务生效别名
  (``effective_alias`` —— 执行视角 = 查询视角的既有裁定不变;
  headers ``${auth.<tag>}`` 引用由前端解析后经 ``query_alias`` 显式
  点名,同时也是多直接身份的消歧通路);
* ``owner_id`` = 场景属主:查询凭证按**执行身份**装载(与派发侧
  prepare_exec 同视角 —— 成员查询项目场景,用的也是场景执行身份)。

组合 v4 §7.1(方案感知,随 UPC M3 执行装配接入):绑定基础从定义级
改为「schemeId 解析 + 组合垫底」(查询视角 = 执行视角);§20.3 装配闸
(blocked 不进装配);步骤多直接身份且未显式点名不猜测(422
``query_identity_ambiguous``,复用 ``auth_ref_scan.step_auth_refs``
—— 含 ``call.user`` 直引;显式 ``query_alias`` 点名即消歧)。
**未保存编辑态不参与**:后端只认库中方案行。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.auth_ref_scan import step_auth_refs
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
    query_alias: str | None   # 查询身份(显式点名 > 步骤直接身份 > 生效别名)
    project_id: "int | None" = None   # 凭证池通道(S8 项目池资格判定)


async def resolve_query_context(
    db: AsyncSession, *, user, scenario_id: str, step_index: int,
    scheme_id: "str | None" = None,
    query_alias: "str | None" = None,
) -> QueryContext:
    """已保存场景 + 步骤位 → 查询地址与身份(全链服务端解析)。

    未保存草稿没有稳定 scenario_id —— 调用方(前端)应先保存再查
    (01-04 §5.2 推荐路径);本函数只受理已保存场景。

    ``scheme_id``(组合 v4 §7.1,方案感知):前端传当前生效方案;
    缺省/跨场景/已删经 ``resolve_for_run`` 回落默认方案(与执行面同款
    回落);未保存编辑态不参与 —— 解析到的是库中方案行的上一次保存
    内容。blocked 方案先于一切身份/标签/地址解析拒绝(§20.3,与执行
    面同码 409);查询 L1/单飞键随 (view, 凭证) 不串台(见 runner)。

    ``query_alias``(调用方显式点名):身份优先级最高(显式 > 步骤直接
    身份 > 生效别名),**同时是 §7.1 多直接身份的消歧手段** —— 给了
    显式别名就按它走,不再因步骤声明多直接身份 422(错误文案
    "请改用明确的 query_alias" 指的就是这条通路)。
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

    # ── §20.3 统一装配闸(UPC M3,查询面接入方案感知后适用)──────
    # 方案解析与执行面同源(resolve_for_run 回落);blocked 先于任何
    # 身份/标签/地址/凭证解析(该面虽不解密,下游 loader 会 —— 闸
    # 在解析入口统一拒)。
    from ..services.account_combo import scheme_bindings_with_combo
    from ..services import scheme_store
    scheme = await scheme_store.resolve_for_run(db, scenario_id, scheme_id)
    if scheme is not None and scheme.repair_status == "blocked":
        raise QueryContextError(
            "scheme_repair_required",
            "运行方案处于待修复状态(组合依赖受阻),请先在方案修复"
            "入口完成修复(§20.3)", status=409)

    # ── 步骤直接身份(§7.1 点 2/3):step_auth_refs 复用(${auth.*}
    #    模板 ∪ call.user 直引)。多直接身份且调用方未点名 → 422,不取
    #    第一个(前端 headers 首命中就是「取第一个」,这里替它挡住;
    #    显式 query_alias 是文案指名的消歧通路,先行短路)。
    direct_refs = step_auth_refs(step)
    if len(direct_refs) > 1 and not query_alias:
        raise QueryContextError(
            "query_identity_ambiguous",
            f"步骤 #{step_index} 声明了多个直接身份({direct_refs}),"
            "单身份取数无法唯一判定,请改用明确的 query_alias 语义或"
            "拆分步骤", status=422)

    # ── 生效绑定(§7.1:方案 serviceBindings + 组合垫底;方案行
    #    缺席(场景无方案)回落定义级 legacy)──────────────────────
    if scheme is not None:
        bindings = await scheme_bindings_with_combo(db, scheme)
    else:
        bindings = (definition.get("config") or {}).get("serviceBindings")

    if query_alias:
        alias = query_alias        # 显式点名(消歧;优先级最高)
    elif len(direct_refs) == 1:
        alias = direct_refs[0]     # 步骤声明的直接身份优先(执行视角)
    else:
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
        query_alias=alias, project_id=row.project_id)
