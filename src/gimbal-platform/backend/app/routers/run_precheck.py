"""POST /api/run/precheck — 执行器批量预检(执行设计 §1.6)。

入参是 ``{scenarioId, schemeId}`` **对**的列表 — 要检的本来就不是用例,
是"这条用例配上这个方案能不能跑"。每条返回::

    {scenarioId, schemeId, found, schemeValid,
     deadDatasetIds, danglingEntryIds, unboundServices}

两个收益(设计 §1.6):失效判定有**服务端唯一实现**(前端不用再抄一份;
悬空判定复用 run_dispatcher.filter_injection_entries — 与 dispatch 跳过
逻辑同一份代码),以及队列 N 条不必各装配一次(每条装配是 4 个并行请求
+ 凭证池)。方案引用的数据集被删的正确说法是「这个方案跑不了,换一个
方案就能跑」— 判定绑定在「用例 × 方案」上,不是用例状态(§1.4)。

读侧口径:场景按 ``can_read_scenario_row`` 收紧(authz W6 起含引用 ——
被分享人本就可跑;不可读 = ``found:false``,不泄露存在性);预检不产生
任何执行副作用。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import principal_or_user
from ._ownership import can_read_scenario_row
from ..models import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..services import run_dispatcher, scenario_store, scheme_store
from ..services.access_token import Principal
from ..services.run_dispatcher import definition_from_payload
from ..services.run_materialize import referenced_services

router = APIRouter(prefix="/run", tags=["runs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
PrincipalIn = Annotated[Principal, Depends(principal_or_user)]

_MAX_BATCH = 20


class PrecheckItem(BaseModel):
    """「这条用例 × 这个方案」预检入参(执行设计 §1.6)。"""

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId", min_length=3, max_length=128)
    scheme_id: str = Field(alias="schemeId", min_length=1, max_length=128)


class PrecheckResult(BaseModel):
    """单条预检结论。字段全部是「这条方案配置」的事实,不是用例状态。"""

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId")
    scheme_id: str = Field(alias="schemeId")
    # false = 场景不可读 / 不存在。此时其余字段无意义(不泄露存在性)。
    found: bool = True
    # 方案本体存在(方案被删 → 不可跑,前端提示去工作台重建)
    scheme_found: bool = Field(default=True, alias="schemeFound")
    # 以上任一不成立即 False — 「这个方案跑不了,换一个方案就能跑」
    scheme_valid: bool = Field(default=True, alias="schemeValid")
    # 方案引用但已删的数据集(换方案可解)
    dead_dataset_ids: list[str] = Field(default_factory=list, alias="deadDatasetIds")
    # dispatch 侧同口径判死的注入条目 id(执行时会被跳过)
    dangling_entry_ids: list[str] = Field(default_factory=list, alias="danglingEntryIds")
    # steps 引用了、但声明 URL 与绑定 URL 双缺的 service(引擎会显式报错)
    unbound_services: list[str] = Field(default_factory=list, alias="unboundServices")
    # webhook v4 §5.3:令牌范围缺项(按 §3.3 分类:未授权 / 已删除);
    # 令牌路径自动以当前令牌预检,JWT 可传 tokenId 预检自己可管理的令牌
    scope_missing: list[dict] = Field(default_factory=list, alias="scopeMissing")
    # §7.1 范围外目标(直连地址/内置认证/白名单外策略,只记录不拦截)
    out_of_scope_targets: list[dict] = Field(
        default_factory=list, alias="outOfScopeTargets")
    # authz W6 预检告警(N9/E2):内置凭证主规则生效后,被分享人经
    # 引用执行不再带走作者凭证 —— 三条件同时满足才列出(钉「不吵」):
    # ① 执行人 ≠ 场景属主;② 场景 config.users 非空;③ 这些用户
    # (别名)在执行人自己的认证会话里解析不到。值为解析不到的别名
    # 清单;空 = 无告警
    builtin_auth_shadowed: list[str] = Field(
        default_factory=list, alias="builtinAuthShadowed")


@router.post("/precheck", response_model=list[PrecheckResult])
async def precheck_run(
    principal: PrincipalIn,
    db: DbSession,
    items: Annotated[list[PrecheckItem], Field(max_length=_MAX_BATCH)],
    token_id: Annotated[int | None, Query(alias="tokenId", ge=1)] = None,
) -> list[PrecheckResult]:
    """批量预检:队列 N 条一次发回判定面,逐条独立结论(一条 404 不连坐)。

    webhook v4 §5.3:``tokenId`` 查询参数把每条方案按**该令牌的范围**做
    预检(缺项 + 范围外目标);令牌路径(``Authorization: Bearer gtk_``)
    不传即自动以当前令牌预检。JWT 只能预检自己可管理的令牌
    (``can_manage``;user 角色仅限自己的个人令牌)。"""
    from ..services import access_token as at_svc

    user = principal.user
    token = principal.token if principal.is_token else None
    if token is None and token_id is not None:
        from ..models.access_token import AccessToken
        token = await db.get(AccessToken, token_id)
        if token is None or not at_svc.can_manage(user, token):
            token = None      # 不可管理 = 当作没传(不带范围预检,不 404 连坐;
                              # §5.3:JWT 只能预检自己可管理的令牌)
    out: list[PrecheckResult] = []
    for item in items:
        scen_row = await scenario_store.get_row(db, item.scenario_id)
        # authz W6:读闸升为 ref-aware(can_read_scenario_row)—— 引用
        # 被分享人本就可跑(§7.6),预检的 found 与内置凭证告警都应
        # 服务到他们;纯判会把 ref 读者当「不存在」。
        if scen_row is None or not await can_read_scenario_row(
                db, user, scen_row):
            out.append(PrecheckResult(
                scenario_id=item.scenario_id, scheme_id=item.scheme_id, found=False,
                scheme_found=False, scheme_valid=False,
            ))
            continue
        one = await _precheck_one(
            db, scen_row, item, token=token,
            user_id=user.id if user is not None else None)
        one.builtin_auth_shadowed = await builtin_auth_shadowed(
            user.id if user is not None else None, scen_row)
        out.append(one)
    return out


async def builtin_auth_shadowed(executor_id: int | None,
                                scen_row) -> list[str]:
    """authz W6 预检告警(N9/E2):三条件同时满足才告警(防噪)。

    ① 执行人 ≠ 场景属主(内置凭证主规则生效面);② 场景 config.users
    非空;③ 这些用户(别名)在执行人自己的认证会话里解析不到 —— 主规则
    已把作者凭证当空,执行人自己又没有,跑起来必在认证段失败,提前说
    清。任一不满足 = 空清单。单场景预检与 suite 预检(validate)共用。
    """
    from ..core import db as _dbm
    from ..services import run_prepare as _rp

    if (executor_id is None or scen_row.owner_id is None
            or executor_id == scen_row.owner_id):
        return []                       # ① 不满足(含令牌匿名面兜底)
    users = _rp.built_in_user_aliases(scen_row.payload)
    if not users:
        return []                       # ② 不满足
    # 只收会话工厂(N1-6):开独立短会话做快照读,不与请求会话混
    resolved = await _rp.resolve_exec_auths(
        _dbm.SessionLocal, executor_id, sorted(users))
    return sorted(set(users) - {a.alias for a in resolved})   # ③


async def _precheck_one(
    db: AsyncSession, scen: ComposerScenario, item: PrecheckItem,
    *, token: "Any | None" = None, user_id: int | None = None,
) -> PrecheckResult:
    result = PrecheckResult(scenario_id=item.scenario_id, scheme_id=item.scheme_id)
    raw_payload = scen.payload or {}

    # ── 方案本体 ──────────────────────────────────────────────────
    try:
        scheme = await scheme_store.get_row(db, scen.scenario_id, item.scheme_id)
    except KeyError:
        result.scheme_found = False
        result.scheme_valid = False
        return result
    payload: dict[str, Any] = scheme_store.normalized(scheme.payload)
    selection = payload.get("dataSetSelection") or []
    entry_ids = payload.get("injectionEntryIds") or []
    bindings = payload.get("serviceBindings") or {}

    # ── 数据集存在性(方案引用 × 本场景名下)─────────────────────
    ds_ids = sorted({s.get("datasetId") for s in selection
                     if isinstance(s, dict) and s.get("datasetId")})
    if ds_ids:
        rows = (await db.execute(
            select(ComposerDataSet.dataset_id).where(
                ComposerDataSet.scenario_id == scen.scenario_id,
                ComposerDataSet.dataset_id.in_(ds_ids),
            )
        )).scalars().all()
        result.dead_dataset_ids = sorted(set(ds_ids) - set(rows))

    # ── 注入条目悬空判定(dispatch 唯一实现,§1.6)────────────────
    _, dangling, _degraded = await run_dispatcher.filter_injection_entries(
        raw_payload, [str(e) for e in entry_ids]
    )
    result.dangling_entry_ids = dangling

    # ── 未落点的服务引用(steps 引用 × 三层地址链皆缺)──────────
    steps = definition_from_payload(raw_payload).get("steps") or []
    declared = (definition_from_payload(raw_payload).get("config") or {}).get("services")
    declared = declared if isinstance(declared, dict) else {}
    # N1-7:与执行期地址三层链同口径 —— ①绑定 url > ②authored 声明 >
    # ③ service_aliases.base_url > ④缺口引擎报错。预检此前只判 ①②,
    # 会被③层补上的服务误报 unbound(预检拦了、执行能跑 —— 口径漂移)。
    # 落点判定共用 run_materialize.service_url_resolved(物化 _apply_
    # services 同一实现,规则不第二份重写);③层命中按需查询(只查
    # ①② 后仍有缺口的候选,不整表拉)。
    from ..services.run_materialize import service_url_resolved
    candidates = [
        svc for svc in referenced_services(steps)
        if not service_url_resolved(svc, declared=declared,
                                    bindings=bindings, alias_base_urls={})
    ]
    if candidates:
        try:
            from ..services import service_aliases
            from ..services.env_chain import resolve_environment
            # S2.1:③ 层按执行同链的环境(方案 > 项目默认 > 个人偏好 >
            # 默认环境;预检看方案,无本次显式位)
            _env = await resolve_environment(
                db, scheme_env=payload.get("environmentId"),
                project_id=scen.project_id, user_id=user_id)
            alias_urls = await service_aliases.base_urls_for(
                db, candidates, env=_env)
        except Exception:  # noqa: BLE001 — 查表失败退回①②口径(不误放行)
            alias_urls = {}
        candidates = [s for s in candidates if not service_url_resolved(
            s, declared=declared, bindings=bindings, alias_base_urls=alias_urls)]
    result.unbound_services = candidates

    # ── webhook v4 §5.3:令牌范围预检(缺项分类 + 范围外目标)─────
    if token is not None:
        from ..services import access_token as at_svc
        used = await at_svc.used_sets_for_definition(
            db, definition_from_payload(raw_payload), bindings)
        missing = await at_svc.check_scope(db, token, token.user_id, used)
        if missing:
            result.scope_missing = [
                {"kind": m.kind, "name": m.name, "deleted": m.deleted}
                for m in missing]
            result.scheme_valid = False
        result.out_of_scope_targets = used.out_of_scope["targets"]

    result.scheme_valid = result.scheme_valid and not (
        result.dead_dataset_ids or result.dangling_entry_ids)
    return result

