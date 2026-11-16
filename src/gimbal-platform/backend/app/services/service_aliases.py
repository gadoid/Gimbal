"""service_aliases 读写(服务画像方案 §4.1;重构 2026-11-16 切身份条目)。

模块名保留(``service_aliases``,40+ 引用点零改),底座已换
``service_identities``:别名 = 「某环境某服务以什么身份登录」的引用
声明(条目),slot/kind 字段退役 —— 注入键 = 条目名(slot=alias 口径
规约延续),kind 升服务主档(services.kind)。

注册校验**强约束**(2026-09-20 拍板,口径延续):plate 态 ``alias_name``
必须通过 ``derive_base`` 落回已知服务集(目录 ∪ 主档)才可登记;
不可达且主档无此服务 → 校验恒失败。external 态不经目录派生
(base_service 显式指向主档 external 服务)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete as sa_delete, func, or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from ..models.service import Service
from ..models.service_identity import ServiceIdentity
from . import service_names

if TYPE_CHECKING:
    from .env_chain import EnvChoice


class UnknownBaseService(Exception):
    """条目无法派生回已知服务集(裸声明 / plate 不可达且主档未登记)。"""


def identity_out(row: ServiceIdentity, *, kind: str = "plate",
                 env_id: int | None = None) -> dict:
    """条目行 → API 形状(字段名沿旧别名契约,前端零适配):
    ``slot`` = 条目名(取用键,规约延续);``kind`` 自服务主档带出。"""
    return {
        "aliasName": row.alias_name,
        "baseService": row.base_service,
        "slot": row.alias_name,
        "kind": kind,
        "envId": row.env_id if env_id is None else env_id,
        "refMode": row.ref_mode,
        "refUsername": row.ref_username or None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


# 兼容别名(旧调用方):alias_out 需 kind —— 无主档 join 的调用点一律
# 先经 _kind_of 批量带出
async def _kinds_of(db: AsyncSession, base_services: set[str]) -> dict[str, str]:
    if not base_services:
        return {}
    rows = (await db.execute(
        select(Service.name, Service.kind).where(Service.name.in_(base_services))
    )).all()
    return {name: (kind or "plate") for name, kind in rows}


async def list_aliases(
    db: AsyncSession, *, base: str | None = None, q: str | None = None,
    page: int = 1, page_size: int = 100,
) -> tuple[list[dict], int]:
    """M4(§6.3):q(alias/base/display 子串)+ base 精确 + Page 信封。
    返回 (当前页 dicts, 全量 total)。"""
    stmt = select(ServiceIdentity)
    if base is not None:
        stmt = stmt.where(ServiceIdentity.base_service == base)
    if q:
        stmt = stmt.where(or_(
            ServiceIdentity.alias_name.ilike(f"%{q}%"),
            ServiceIdentity.base_service.ilike(f"%{q}%"),
            ServiceIdentity.display.ilike(f"%{q}%"),
        ))
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = (await db.execute(
        stmt.order_by(ServiceIdentity.alias_name)
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    kinds = await _kinds_of(db, {r.base_service for r in rows})
    return ([identity_out(r, kind=kinds.get(r.base_service, "plate"))
             for r in rows], int(total))


async def _default_env_id(db: AsyncSession) -> int:
    """条目 env 必填(§1.3)的兜底:导入等无环境上下文的调用方落平台
    默认环境(环境链末位同款语义);无默认环境 → 明确拒绝。"""
    from ..models.environment import Environment

    env_id = (await db.execute(
        select(Environment.id).where(Environment.is_default.is_(True))
    )).scalar()
    if env_id is None:
        raise ValueError(
            "no_environment: 身份条目必须挂环境 —— 请先建环境并指定默认"
            "(或调用方显式传 env_id)")
    return env_id


async def create_alias_in_transaction(
    db: AsyncSession, *, alias_name: str, slot: str | None = None,
    kind: str = "plate",
    base_service: str | None = None,
    catalog_names: "set[str] | None" = None,
    env_id: int | None = None,
    ref_mode: str = "default",
    ref_username: str = "",
    display: str = "",
) -> ServiceIdentity:
    """Insert a new identity **without committing**(导入 W2/T2:建条目+写
    carry+建场景单事务落库,场景导入 v2.3 方案 §6)。

    校验行为与 :func:`create_alias` 一致(kind/derive_base/env 兜底);
    **提交与错误映射是调用方的责任**——alias_name 唯一,撞车的
    IntegrityError 在事务边界由调用方统一映射(如 ``alias_name_taken``)
    并回滚。返回**未 refresh** 的 row。

    ``slot`` 参数仅为签名兼容(条目模型无槽;忽略);``catalog_names``
    为调用方在事务外预取的 plate 目录集合(P7-④:plate 调用不进事务)。
    """
    _ = slot  # 退役参数:注入键 = 条目名(规约延续)
    if env_id is None:
        env_id = await _default_env_id(db)
    if kind == "external":
        # external 不派生 —— base_service 必须是主档登记的第三方服务
        # (重构:校验源从 plate 目录切主档,external 不受可达性影响)
        if not base_service:
            raise ValueError(
                "base_service_required: kind=external 须显式选择 base_service"
                "(主档登记的第三方服务名;不再派生 alias_name)")
        svc = await db.get(Service, base_service)
        if svc is None or svc.kind not in ("external", "integration"):
            raise UnknownBaseService(
                f"unknown_base_service: {base_service!r} 不在服务主档的"
                "第三方服务内(external 条目须指向主档 external 服务;"
                "sut 服务请建 plate 条目)")
        base = base_service
    elif kind == "plate":
        # sut 派生候选 = plate 目录 sut 子集 ∪ 主档 plate 行
        # (重构:主档注册簿参与派生域)
        from . import plate_client

        if catalog_names is not None:
            names = set(catalog_names)
        else:
            entries = await plate_client.catalog_service_entries(refresh=True)
            names = {e["name"] for e in entries if e.get("kind") == "sut"}
        names |= set((await db.execute(
            select(Service.name).where(Service.kind == "plate"))).scalars())
        base = service_names.derive_base(alias_name, names)
        if base is None:
            # 强约束:含 plate 不可达且主档未登记场景
            raise UnknownBaseService(
                f"unknown_base_service: {alias_name!r} 不落在已知服务集内"
                "(裸声明不猜;plate 不可达且主档未登记时恢复后再登记;"
                "第三方服务请先在主档登记再建 external 条目)")
    else:
        raise ValueError(f"invalid_kind: {kind!r} (plate | external)")
    row = ServiceIdentity(
        alias_name=alias_name, base_service=base, env_id=env_id,
        ref_mode=ref_mode or "default", ref_username=ref_username or "",
        display=display or "")
    db.add(row)
    return row


async def create_alias(
    db: AsyncSession, *, alias_name: str, slot: str | None = None,
    kind: str = "plate",
    base_service: str | None = None,
    env_id: int | None = None,
    ref_mode: str = "default",
    ref_username: str = "",
    display: str = "",
) -> dict:
    """提交包装器(W2/T2):条目路由用;导入流水线走
    :func:`create_alias_in_transaction` 自管事务。"""
    row = await create_alias_in_transaction(
        db, alias_name=alias_name, slot=slot, kind=kind,
        base_service=base_service, env_id=env_id,
        ref_mode=ref_mode, ref_username=ref_username, display=display)
    await db.commit()
    await db.refresh(row)  # server_default 时间列:刷新防异步懒加载
    kind_of = (await db.get(Service, row.base_service))
    return identity_out(row, kind=(kind_of.kind if kind_of else "plate"))


async def classify_services(
    db: AsyncSession, services: list[str],
) -> dict[str, list[str]]:
    """步骤 ``service`` 键 → 三态分类(P1.0 判定链;W7 入库分桶/
    W11 徽标与保存告警的数据源;重构:kind 自服务主档)。

    命中顺序:``alias_name`` 条目精确命中 → 其 base 的主档 kind;
    服务名在主档 → 主档 kind。两边都未命中 → ``unknown``(保存告警
    口径:提示接入 plate 或在主档登记 external)。
    """
    out: dict[str, list[str]] = {"plate": [], "external": [], "unknown": []}
    if not services:
        return out
    uniq = list(dict.fromkeys(services))
    id_bases = dict((await db.execute(
        select(ServiceIdentity.alias_name, ServiceIdentity.base_service)
        .where(ServiceIdentity.alias_name.in_(uniq)))).all())
    names = set(uniq) | set(id_bases.values())
    kinds = dict((await db.execute(
        select(Service.name, Service.kind).where(Service.name.in_(names))
    )).all())

    def _one(svc: str) -> str:
        base = id_bases.get(svc, svc)
        k = kinds.get(base)
        if k in ("external", "integration"):
            return "external"
        if k == "plate":
            return "plate"
        return "unknown"

    for svc in uniq:
        out[_one(svc)].append(svc)
    return out


async def patch_alias(
    db: AsyncSession, alias_name: str, *, slot: str | None = ...,
    base_service: str | None = ...,
    kind: str | None = None,
    ref_mode: str | None = None,
    ref_username: str | None = None,
    display: str | None = None,
) -> dict:
    """条目 patch:``ref_mode``/``ref_username``/``display`` 可改;
    ``base_service`` 仅 external 可改(重指主档第三方服务);``slot``
    签名兼容(忽略);``kind`` 由主档承载(条目不再可改 —— 转型走
    主档对账)。
    """
    _ = slot
    row = await db.get(ServiceIdentity, alias_name)
    if row is None:
        raise KeyError(f"alias_not_found: {alias_name}")
    svc = await db.get(Service, row.base_service)
    svc_kind = (svc.kind if svc else "plate")
    if base_service is not ...:
        if svc_kind != "external":
            raise ValueError(
                "base_service_immutable: 仅 external 条目可设置 base_service")
        target = await db.get(Service, base_service)
        if target is None or target.kind not in ("external", "integration"):
            raise ValueError(
                f"kind_mismatch: base_service={base_service!r} 须指向主档"
                "第三方服务(external/integration)")
        row.base_service = base_service
    if kind is not None and kind != svc_kind:
        raise ValueError(
            f"kind_transition_invalid: kind 由服务主档承载({svc_kind!r}),"
            "条目不再可改 —— 转型走主档对账")
    if ref_mode is not None:
        if ref_mode not in ("default", "username"):
            raise ValueError(f"invalid_ref_mode: {ref_mode!r} (default | username)")
        row.ref_mode = ref_mode
    if ref_username is not None:
        row.ref_username = ref_username
    if display is not None:
        row.display = display
    await db.commit()
    await db.refresh(row)
    return identity_out(row, kind=svc_kind)


async def delete_alias(db: AsyncSession, alias_name: str) -> None:
    await db.execute(sa_delete(ServiceIdentity).where(
        ServiceIdentity.alias_name == alias_name))
    await db.commit()


def effective_alias(svc: str, bindings: dict | None) -> str:
    """服务键的生效别名(authz M2a S6:``serviceBindings`` = 服务键 →
    别名):绑定选了别名取之,否则服务键自身 —— 槽位默认与 carry 别名键
    的**唯一**换名口径(地址不经此:同基础服务校验保证部署地址一致)。"""
    b = (bindings or {}).get(svc)
    alias = b.get("alias") if isinstance(b, dict) else None
    return alias if isinstance(alias, str) and alias else svc


class BindingAliasInvalid(ValueError):
    """绑定选择的别名不存在 / 与服务键不同基础服务(调用方映射 422)。"""

    def __init__(self, code: str, message: str, *, service: str,
                 alias: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.service = service
        self.alias = alias


async def validate_binding_aliases(
    db: AsyncSession, bindings: dict | None,
) -> None:
    """绑定选择的条目须存在,且与服务键同基础服务(服务键的基础服务 =
    其条目行 ``base_service``,非条目即自身)—— 选条目只换身份 / carry
    条目键,不许借道改地址(地址只由环境决定)。"""
    pairs = {svc: effective_alias(svc, bindings)
             for svc in (bindings or {})}
    pairs = {s: a for s, a in pairs.items() if a != s}
    if not pairs:
        return
    names = set(pairs) | set(pairs.values())
    base_of = dict((await db.execute(
        select(ServiceIdentity.alias_name, ServiceIdentity.base_service).where(
            ServiceIdentity.alias_name.in_(names)))).all())
    for svc, alias in pairs.items():
        if alias not in base_of:
            raise BindingAliasInvalid(
                "binding_alias_unknown", f"别名 {alias!r} 不存在",
                service=svc, alias=alias)
        if base_of[alias] != base_of.get(svc, svc):
            raise BindingAliasInvalid(
                "binding_alias_mismatch",
                f"别名 {alias!r} 不属于服务 {svc!r} 的基础服务"
                f"({base_of[alias]} ≠ {base_of.get(svc, svc)})",
                service=svc, alias=alias)


async def credential_alias_hits(
    db: AsyncSession, steps: list,
    bindings: dict[str, dict] | None = None,
) -> dict[str, str]:
    """别名表凭证默认命中(raw 服务键 → 槽位;authz M2a S6:按服务键的
    **生效别名**取槽位 —— 方案选了 ``fin → fin-maker`` 就吃 ``fin-maker``
    声明的槽)。查表失败降级 {}(别名默认是增强,不是前置条件)。订阅
    内容指纹同消费本函数。"""
    from .run_materialize import referenced_services
    eff = {svc: effective_alias(svc, bindings)
           for svc in referenced_services(steps or [])}
    try:
        hits = await credential_aliases_for(db, sorted(set(eff.values())))
    except Exception:  # noqa: BLE001
        logger.warning("service_aliases: credential default lookup failed; skipped")
        return {}
    hits = hits or {}
    return {svc: hits[a] for svc, a in eff.items() if a in hits}


async def exec_auth_aliases(
    db: AsyncSession, steps: list,
    bindings: dict[str, dict] | None = None,
    *,
    extra_scan_nodes: list | None = None,
) -> list[str]:
    """执行凭证注入清单 —— **五个装载入口的唯一实现,算法不得漂移**
    (N1 归一 + 评审 §3.1A:单场景执行/集成/导出经 ``run_prepare.prepare_
    exec``,Suite 编排与 Suite 预检经 ``run_prepare.graph_auth_aliases``
    直接调用):

    ``${auth.<name>.*}`` 模板扫描(auth_ref_scan,definition steps
    **+ config.setup/teardown 条目**,webhook v4 §3.2 —— setup 引用的
    凭证此前既不进清单也不注入,令牌范围与运行时注入同时生效)
    ∪ 别名声明槽位(``credential_alias_hits``,按绑定选中的生效别名)。
    去重保序。方案绑定 authAlias 一源随 S6 退役。
    """
    from .auth_ref_scan import scan_auth_aliases
    nodes = list(steps or [])
    if extra_scan_nodes:
        nodes.extend(extra_scan_nodes)
    hits = await credential_alias_hits(db, nodes, bindings)
    return list(dict.fromkeys([*scan_auth_aliases(nodes), *hits.values()]))


def setup_teardown_nodes(definition: dict) -> list:
    """``config.setup`` / ``config.teardown`` 条目(策略形态,不是 step,
    无 call.service —— 不进别名集,但 ``params`` 可含 ``${auth.*}``,
    扫描源须并入;§3.2/D30)。"""
    cfg = (definition or {}).get("config") or {}
    out: list = []
    for slot in ("setup", "teardown"):
        entries = cfg.get(slot)
        if isinstance(entries, list):
            out.extend(e for e in entries if isinstance(e, dict))
    return out


async def exec_auth_aliases_of_definition(
    db: AsyncSession, definition: dict,
    bindings: dict[str, dict] | None = None,
) -> list[str]:
    """定义级注入清单(steps ∪ setup/teardown 扫描;§3.2 唯一口径)。"""
    return await exec_auth_aliases(
        db, (definition or {}).get("steps") or [], bindings,
        extra_scan_nodes=setup_teardown_nodes(definition or {}))


async def credential_aliases_for(
    db: AsyncSession, raw_names: list[str],
) -> dict[str, str]:
    """执行期读:条目名 → 精确命中(重构:条目存在即声明身份,注入键 =
    条目名 —— 旧「别名可空槽」语义随条目化退役,迁移已补齐全量声明)。

    只做精确命中;绑定选条目的换名在调用方(``credential_alias_hits``
    按生效别名查)。凭证按执行者本人池子解析(resolve_exec_auths)。
    """
    if not raw_names:
        return {}
    rows = (await db.execute(
        select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name.in_(raw_names)))).scalars().all()
    return {name: name for name in rows}


async def slot_lookup_overrides(
    db: AsyncSession, steps: list,
    bindings: dict[str, dict] | None = None,
    alias_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """执行配置绑定的取用换槽映射(分层②,§5 注入表):{声明槽位(注入
    标签,场景引用) → 池取用槽位}。

    槽位解析序:别名声明(缺省)> 执行配置绑定(覆盖)> 池内同槽默认
    行(最终账号)。覆盖只换**池内命中哪条** —— 注入标签(场景步骤
    ``call.user``/``${auth.*}`` 引用的声明槽位)不变,场景零改动可跑。
    ``${auth.X}`` 模板直引槽位的标签不受别名键覆盖影响(无别名关系)。
    """
    if not alias_overrides:
        return {}
    from .run_materialize import referenced_services
    eff = {svc: effective_alias(svc, bindings)
           for svc in referenced_services(steps or [])}
    hits = await credential_aliases_for(db, sorted(set(eff.values())))
    out: dict[str, str] = {}
    for _svc, alias in eff.items():
        label = hits.get(alias)
        lookup = alias_overrides.get(alias)
        if label and lookup and lookup != label and label not in out:
            out[label] = lookup
    return out


async def base_urls_for(
    db: AsyncSession, raw_names: list[str],
    *, env: "EnvChoice | None" = None,
) -> dict[str, str]:
    """执行期读:raw 服务键 → 地址 —— services 物化优先级链「场景
    声明 > **③** > 缺口引擎报错」的数据源。

    authz M2a S6:**部署表单源** —— 服务键 → 基础服务 → 本次环境的部署
    地址(``env_chain.deployment_urls``);无环境(环境链全空)= 无 ③。
    别名自带 ``base_url`` 与影子期合并规则随别名瘦身退役(0047)。

    优先级裁决在唯一组装点 ``materialize_run_copy._apply_services``,
    本函数只提供数据。
    """
    if not raw_names or env is None or env.env_id is None:
        return {}
    from .env_chain import deployment_urls
    return await deployment_urls(db, raw_names, env.env_id)
