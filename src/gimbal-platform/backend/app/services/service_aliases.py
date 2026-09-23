"""service_aliases 读写(服务画像方案 §4.1;基础层,无 UI)。

注册校验**强约束**(2026-09-20 拍板):``alias_name`` 必须通过
``derive_base`` 落回 Plate 目录才可登记;plate 不可达 → 目录空集 →
校验恒失败 → **Plate 宕机期间不能登记新别名**。不做「空集放行 +
unverified 标记」的松绑 —— 空枪别名会静默漏 carry/凭证注入,比暂时
登记不了更糟;登记是低频配置操作,等 Plate 恢复再登。
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, func, or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.service_alias import ServiceAlias
from . import service_names


class UnknownBaseService(Exception):
    """别名无法派生回 Plate 目录(裸声明 / plate 不可达)。"""


def alias_out(row: ServiceAlias) -> dict:
    return {
        "aliasName": row.alias_name,
        "baseService": row.base_service,
        "baseUrl": row.base_url,
        "groupTag": row.group_tag,
        "credentialAlias": row.credential_alias,
        "ownerUserId": row.owner_user_id,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_aliases(
    db: AsyncSession, *, base: str | None = None, q: str | None = None,
    page: int = 1, page_size: int = 100,
) -> tuple[list[dict], int]:
    """M4(§6.3):q(alias/base 子串)+ base 精确 + Page 信封。
    返回 (当前页 dicts, 全量 total)。"""
    stmt = select(ServiceAlias)
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
    )).scalars().all()
    return [alias_out(r) for r in rows], int(total)


async def create_alias(
    db: AsyncSession, *, alias_name: str, group_tag: str | None = None,
    credential_alias: str | None = None, owner_user_id: int | None = None,
    base_url: str | None = None,
) -> dict:
    base = service_names.derive_base(
        alias_name, await service_names.catalog_service_names())
    if base is None:
        # 强约束:含 plate 不可达(空目录)场景,区分两种原因给排查线索
        raise UnknownBaseService(
            f"unknown_base_service: {alias_name!r} 不落在 plate 服务目录内"
            "(裸声明不猜;plate 不可达时目录为空,恢复后再登记)")
    row = ServiceAlias(
        alias_name=alias_name, base_service=base, group_tag=group_tag,
        credential_alias=credential_alias, owner_user_id=owner_user_id,
        base_url=base_url,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)  # server_default 时间列:刷新防异步懒加载
    return alias_out(row)


async def patch_alias(
    db: AsyncSession, alias_name: str, *, group_tag: str | None = ...,
    credential_alias: str | None = ..., base_url: str | None = ...,
) -> dict:
    row = await db.get(ServiceAlias, alias_name)
    if row is None:
        raise KeyError(f"alias_not_found: {alias_name}")
    if group_tag is not ...:
        row.group_tag = group_tag
    if credential_alias is not ...:
        row.credential_alias = credential_alias
    if base_url is not ...:
        row.base_url = base_url
    await db.commit()
    await db.refresh(row)
    return alias_out(row)


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
