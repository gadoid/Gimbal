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

from sqlalchemy import delete as sa_delete, func, or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.environment import Environment
from ..models.service_alias import ServiceAlias
from . import service_names


class UnknownBaseService(Exception):
    """别名无法派生回 Plate 目录(裸声明 / plate 不可达)。"""


def alias_out(
    row: ServiceAlias, *, environment_name: str | None = None,
) -> dict:
    return {
        "aliasName": row.alias_name,
        "baseService": row.base_service,
        "baseUrl": row.base_url,
        # V5(B):group_tag 已退役,归属环境经外键指向 environments
        "environmentId": row.environment_id,
        "environmentName": environment_name,
        "credentialAlias": row.credential_alias,
        "ownerUserId": row.owner_user_id,
        # 三态接入(P1.0):plate | external(第三方,无版本管理)
        "kind": row.kind or "plate",
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_aliases(
    db: AsyncSession, *, base: str | None = None, q: str | None = None,
    page: int = 1, page_size: int = 100,
) -> tuple[list[dict], int]:
    """M4(§6.3):q(alias/base 子串)+ base 精确 + Page 信封。
    返回 (当前页 dicts, 全量 total)。"""
    # V5(B):LEFT JOIN environments 带出环境名(展示/筛选用,id 不友好)
    stmt = select(ServiceAlias, Environment.name).outerjoin(
        Environment, ServiceAlias.environment_id == Environment.id)
    if base is not None:
        stmt = stmt.where(ServiceAlias.base_service == base)
    if q:
        stmt = stmt.where(or_(
            ServiceAlias.alias_name.ilike(f"%{q}%"),
            ServiceAlias.base_service.ilike(f"%{q}%"),
            ServiceAlias.credential_alias.ilike(f"%{q}%"),
        ))
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = (await db.execute(
        stmt.order_by(ServiceAlias.alias_name)
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    return ([alias_out(r, environment_name=n) for r, n in rows], int(total))


async def create_alias_in_transaction(
    db: AsyncSession, *, alias_name: str, environment_id: int | None = None,
    credential_alias: str | None = None, owner_user_id: int | None = None,
    base_url: str | None = None, kind: str = "plate",
    base_service: str | None = None,
    catalog_names: "set[str] | None" = None,
) -> ServiceAlias:
    """Insert a new alias **without committing**(导入 W2/T2:建别名+写
    carry+建场景单事务落库,场景导入 v2.3 方案 §6)。

    校验行为与 :func:`create_alias` 一致(kind/derive_base/environment);
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

        entries = await plate_client.catalog_service_entries()
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
            entries = await plate_client.catalog_service_entries()
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
    if environment_id is not None:
        env = await db.get(Environment, environment_id)
        if env is None:
            raise KeyError(
                f"environment_not_found: {environment_id}")
    row = ServiceAlias(
        alias_name=alias_name, base_service=base,
        environment_id=environment_id,
        credential_alias=credential_alias, owner_user_id=owner_user_id,
        base_url=base_url, kind=kind,
    )
    db.add(row)
    return row


async def create_alias(
    db: AsyncSession, *, alias_name: str, environment_id: int | None = None,
    credential_alias: str | None = None, owner_user_id: int | None = None,
    base_url: str | None = None, kind: str = "plate",
    base_service: str | None = None,
) -> dict:
    """提交包装器(W2/T2):既有调用方(别名路由/迁移脚本)行为零变化;
    导入流水线走 :func:`create_alias_in_transaction` 自管事务。"""
    row = await create_alias_in_transaction(
        db, alias_name=alias_name, environment_id=environment_id,
        credential_alias=credential_alias, owner_user_id=owner_user_id,
        base_url=base_url, kind=kind, base_service=base_service)
    await db.commit()
    await db.refresh(row)  # server_default 时间列:刷新防异步懒加载
    env_name = None
    if row.environment_id is not None:
        env = await db.get(Environment, row.environment_id)
        env_name = env.name if env else None
    return alias_out(row, environment_name=env_name)


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
    db: AsyncSession, alias_name: str, *, environment_id: int | None = ...,
    credential_alias: str | None = ..., base_url: str | None = ...,
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

        entries = await plate_client.catalog_service_entries()
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

        entries = await plate_client.catalog_service_entries()
        hit = next((e for e in entries
                    if e["name"] == (row.base_service or "")), None)
        if hit is None or hit.get("kind") != "sut":
            raise ValueError(
                "kind_transition_precondition: base_service 所指系统须已"
                "转为 sut(integration 原地升级,归一 v1.0 §1.8)")
        row.kind = "plate"
    if environment_id is not ...:
        if environment_id is not None:
            env = await db.get(Environment, environment_id)
            if env is None:
                raise KeyError(
                    f"environment_not_found: {environment_id}")
        row.environment_id = environment_id
    if credential_alias is not ...:
        row.credential_alias = credential_alias
    if base_url is not ...:
        row.base_url = base_url
    await db.commit()
    await db.refresh(row)
    env_name = None
    if row.environment_id is not None:
        env = await db.get(Environment, row.environment_id)
        env_name = env.name if env else None
    return alias_out(row, environment_name=env_name)


async def delete_alias(db: AsyncSession, alias_name: str) -> None:
    await db.execute(sa_delete(ServiceAlias).where(
        ServiceAlias.alias_name == alias_name))
    await db.commit()


async def credential_aliases_for(
    db: AsyncSession, raw_names: list[str],
) -> dict[str, str]:
    """执行期读:raw 服务键 → 别名表精确命中的 credential_alias。

    只做精确命中(方案 §4.1 三层的中间层);场景显式绑定的优先级
    裁决在调用方(run_dispatcher):同键已显式绑 authAlias 的不吃
    别名表默认。凭证按执行者本人池子解析(_resolve_exec_auths)。
    """
    if not raw_names:
        return {}
    rows = (await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.credential_alias).where(
            ServiceAlias.alias_name.in_(raw_names),
            ServiceAlias.credential_alias.is_not(None),
        )
    )).all()
    return {name: cred for name, cred in rows}


async def base_urls_for(
    db: AsyncSession, raw_names: list[str],
) -> dict[str, str]:
    """执行期读(F4 方案 B,2026-09-23 批次):raw 服务键 → 别名表
    精确命中的 base_url —— services 物化优先级链的第三层
    「显式绑定 > 场景声明 > **base_url** > 缺口引擎报错」的数据源。

    与 credential_aliases_for 同款形态(照抄结构,别处不得另开第二份
    查询实现);优先级裁决在唯一组装点
    ``materialize_run_copy._apply_services``,本函数只提供数据。
    """
    if not raw_names:
        return {}
    rows = (await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.base_url).where(
            ServiceAlias.alias_name.in_(raw_names),
            ServiceAlias.base_url.is_not(None),
        )
    )).all()
    return {name: url for name, url in rows if url}
