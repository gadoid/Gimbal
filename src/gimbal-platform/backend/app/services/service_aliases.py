"""service_aliases 读写(服务画像方案 §4.1;基础层,无 UI)。

注册校验**强约束**(2026-09-20 拍板):``alias_name`` 必须通过
``derive_base`` 落回 Plate 目录才可登记;plate 不可达 → 目录空集 →
校验恒失败 → **Plate 宕机期间不能登记新别名**。不做「空集放行 +
unverified 标记」的松绑 —— 空枪别名会静默漏 carry/凭证注入,比暂时
登记不了更糟;登记是低频配置操作,等 Plate 恢复再登。

三态接入例外(P1.0/2026-10-12):``kind="external"`` 的第三方服务
**不经目录派生**(别名即服务本体,base_service = alias_name)——
强约束只约束受管(plate)态;external 无契约面,不存在空枪问题。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete as sa_delete, func, or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from ..models.service_alias import ServiceAlias
from . import service_names

if TYPE_CHECKING:
    from .env_chain import EnvChoice


class UnknownBaseService(Exception):
    """别名无法派生回 Plate 目录(裸声明 / plate 不可达)。"""


def alias_out(row: ServiceAlias) -> dict:
    # authz M2a S6:地址/环境/属主字段随别名瘦身移除(地址见部署表)
    return {
        "aliasName": row.alias_name,
        "baseService": row.base_service,
        "slot": row.slot,
        # 三态接入(P1.0):plate | external(第三方,无版本管理)
        "kind": row.kind or "plate",
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_aliases(
    db: AsyncSession, *, base: str | None = None, q: str | None = None,
    page: int = 1, page_size: int = 100,
) -> tuple[list[dict], int]:
    """M4(§6.3):q(alias/base/slot 子串)+ base 精确 + Page 信封。
    返回 (当前页 dicts, 全量 total)。"""
    stmt = select(ServiceAlias)
    if base is not None:
        stmt = stmt.where(ServiceAlias.base_service == base)
    if q:
        stmt = stmt.where(or_(
            ServiceAlias.alias_name.ilike(f"%{q}%"),
            ServiceAlias.base_service.ilike(f"%{q}%"),
            ServiceAlias.slot.ilike(f"%{q}%"),
        ))
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = (await db.execute(
        stmt.order_by(ServiceAlias.alias_name)
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return ([alias_out(r) for r in rows], int(total))


async def create_alias_in_transaction(
    db: AsyncSession, *, alias_name: str, slot: str | None = None,
    kind: str = "plate",
    base_service: str | None = None,
    catalog_names: "set[str] | None" = None,
) -> ServiceAlias:
    """Insert a new alias **without committing**(导入 W2/T2:建别名+写
    carry+建场景单事务落库,场景导入 v2.3 方案 §6)。

    校验行为与 :func:`create_alias` 一致(kind/derive_base);
    **提交与错误映射是调用方的责任**——alias_name 是主键,撞车的
    IntegrityError 在事务边界由调用方统一映射(如 ``alias_name_taken``)
    并回滚。返回**未 refresh** 的 row。

    ``catalog_names``:调用方在**事务外**预取的 plate 目录集合
    (P7-④:plate 调用不进事务);None = 本函数自取(提交包装器路径,
    行为等价旧版)。
    """
    if kind == "external":
        # b2-8(归一 v1.0 §1.6/D-M):external 不派生 —— 接收并校验显式
        # base_service(①存在于 plate 目录 ②所指系统 kind=integration;
        # 校验数据 = 唯一访问件扁平名视图,过滤只在此消费)。
        if not base_service:
            raise ValueError(
                "base_service_required: kind=external 须显式选择 base_service"
                "(第三方服务在 plate 的服务名;不再派生 alias_name)")
        from . import plate_client

        entries = await plate_client.catalog_service_entries(refresh=True)
        hit = next((e for e in entries if e["name"] == base_service), None)
        if hit is None:
            raise UnknownBaseService(
                f"unknown_base_service: {base_service!r} 不在 plate 目录"
                "(external 别名须指向已入库的第三方服务)")
        if hit.get("kind") != "integration":
            raise ValueError(
                f"kind_mismatch: base_service={base_service!r} 的系统是 "
                f"{hit.get('kind')!r}(external 别名须指向 kind=integration "
                "的系统;sut 服务请建 plate 别名)")
        base = base_service
    elif kind == "plate":
        # b2-8:sut 派生候选 = sut 子集(sut 过滤唯一出口,§1.6/§6.1;
        # catalog_names 兼容导入事务外预取的全量集合,向后兼容)
        from . import plate_client

        if catalog_names is not None:
            names = catalog_names
        else:
            entries = await plate_client.catalog_service_entries(refresh=True)
            names = {e["name"] for e in entries if e.get("kind") == "sut"}
        base = service_names.derive_base(alias_name, names)
        if base is None:
            # 强约束:含 plate 不可达(空目录)场景,区分两种原因给排查线索
            raise UnknownBaseService(
                f"unknown_base_service: {alias_name!r} 不落在 plate 服务目录内"
                "(裸声明不猜;plate 不可达时目录为空,恢复后再登记;"
                "第三方服务请用 kind=external 登记)")
    else:
        raise ValueError(f"invalid_kind: {kind!r} (plate | external)")
    row = ServiceAlias(
        alias_name=alias_name, base_service=base, slot=slot, kind=kind)
    db.add(row)
    return row


async def create_alias(
    db: AsyncSession, *, alias_name: str, slot: str | None = None,
    kind: str = "plate",
    base_service: str | None = None,
) -> dict:
    """提交包装器(W2/T2):别名路由用;导入流水线走
    :func:`create_alias_in_transaction` 自管事务。"""
    row = await create_alias_in_transaction(
        db, alias_name=alias_name, slot=slot, kind=kind,
        base_service=base_service)
    await db.commit()
    await db.refresh(row)  # server_default 时间列:刷新防异步懒加载
    return alias_out(row)


async def classify_services(
    db: AsyncSession, services: list[str],
) -> dict[str, list[str]]:
    """步骤 ``service`` 键 → 三态分类(P1.0 判定链;W7 入库分桶/
    W11 徽标与保存告警的数据源)。

    命中顺序:``alias_name`` 精确命中 → 该行 kind;否则
    ``base_service`` 精确命中 → 该 base 的 kind(base 维度应同态,
    混态取 plate 保守)。两边都未命中 → ``unknown``(保存告警口径:
    提示接入 plate 或登记 external 别名)。
    """
    out: dict[str, list[str]] = {"plate": [], "external": [], "unknown": []}
    if not services:
        return out
    uniq = list(dict.fromkeys(services))
    rows = (await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.base_service,
               ServiceAlias.kind).where(
            or_(ServiceAlias.alias_name.in_(uniq),
                ServiceAlias.base_service.in_(uniq))
        )
    )).all()
    by_alias = {a: k for a, _, k in rows}
    by_base: dict[str, set[str]] = {}
    for _, b, k in rows:
        by_base.setdefault(b, set()).add(k or "plate")

    def _one(svc: str) -> str:
        if svc in by_alias:
            return by_alias[svc] or "plate"
        if svc in by_base:
            # base 维度混态取 plate 保守(external 误标 plate 只影响
            # 统计口径,反向会静默漏 external 桶)
            return "plate" if "plate" in by_base[svc] else "external"
        return "unknown"

    for svc in uniq:
        out[_one(svc)].append(svc)
    return out


async def patch_alias(
    db: AsyncSession, alias_name: str, *, slot: str | None = ...,
    base_service: str | None = ..., kind: str | None = None,
) -> dict:
    """b2-8(归一 v1.0 §1.6):``base_service`` 仅 external 可改(重指向
    integration 系统);``kind`` 仅支持 external→plate(前提:base_service
    所指系统已是 sut —— 支撑 integration 原地转 sut 的升级路径 §1.8)。
    """
    row = await db.get(ServiceAlias, alias_name)
    if row is None:
        raise KeyError(f"alias_not_found: {alias_name}")
    if base_service is not ...:
        if row.kind != "external":
            raise ValueError(
                "base_service_immutable: 仅 external 别名可设置 base_service")
        from . import plate_client

        entries = await plate_client.catalog_service_entries(refresh=True)
        hit = next((e for e in entries if e["name"] == base_service), None)
        if hit is None or hit.get("kind") != "integration":
            raise ValueError(
                f"kind_mismatch: base_service={base_service!r} 须指向 "
                "kind=integration 的系统")
        row.base_service = base_service
    if kind is not None:
        if not (row.kind == "external" and kind == "plate"):
            raise ValueError(
                f"kind_transition_invalid: {row.kind!r} → {kind!r}"
                "(仅支持 external → plate)")
        from . import plate_client

        entries = await plate_client.catalog_service_entries(refresh=True)
        hit = next((e for e in entries
                    if e["name"] == (row.base_service or "")), None)
        if hit is None or hit.get("kind") != "sut":
            raise ValueError(
                "kind_transition_precondition: base_service 所指系统须已"
                "转为 sut(integration 原地升级,归一 v1.0 §1.8)")
        row.kind = "plate"
    if slot is not ...:
        row.slot = slot
    await db.commit()
    await db.refresh(row)
    return alias_out(row)


async def delete_alias(db: AsyncSession, alias_name: str) -> None:
    await db.execute(sa_delete(ServiceAlias).where(
        ServiceAlias.alias_name == alias_name))
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
    """绑定选择的别名须存在,且与服务键同基础服务(服务键的基础服务 =
    其别名行 ``base_service``,非别名即自身)—— 选别名只换槽位 / carry
    别名键,不许借道改地址(地址只由环境决定)。"""
    pairs = {svc: effective_alias(svc, bindings)
             for svc in (bindings or {})}
    pairs = {s: a for s, a in pairs.items() if a != s}
    if not pairs:
        return
    names = set(pairs) | set(pairs.values())
    base_of = dict((await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.base_service).where(
            ServiceAlias.alias_name.in_(names)))).all())
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
    """执行期读:别名名 → 别名表精确命中的声明槽位。

    只做精确命中;绑定选别名的换名在调用方(``credential_alias_hits``
    按生效别名查)。凭证按执行者本人池子解析(resolve_exec_auths)。

    """
    if not raw_names:
        return {}
    rows = (await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.slot).where(
            ServiceAlias.alias_name.in_(raw_names),
            ServiceAlias.slot.is_not(None),
        )
    )).all()
    return {name: slot for name, slot in rows if slot}


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
