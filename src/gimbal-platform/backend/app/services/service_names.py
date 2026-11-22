"""服务名别名推导(spec §4.2;重构 2026-11-16 校验源扩主档)—— 前端
service-alias.ts deriveBase 的后端移植。

别名 = <目录服务名>-<后缀>;切分点固定在最后一个 "-",base 必须落在
已知服务名集合内才生效(裸声明不猜)。

已知集合(重构后两级):
* plate 目录(:func:`catalog_service_names`,纯 plate 包装);
* **服务主档**(:func:`known_service_names` = 目录 ∪ ``services``
  注册簿)—— external 行不受 plate 可达性影响,主档是平台侧权威;
  别名/条目校验、导入映射、重锚定等**平台侧校验一律用此单源**。
"""
from __future__ import annotations

from sqlalchemy import select as sa_select


def derive_base(key: str, catalog_names: set[str]) -> str | None:
    """key ∈ 目录 → key;否则最后 "-" 切分,base ∈ 目录 → base;否则 None。

    前后端双头契约(2026-11-22):前端逐字镜像在
    ``frontend/src/utils/service-alias.ts deriveBase`` —— 两侧必须
    同步改动(见彼侧 docstring)。"""
    if not key:
        return None
    if key in catalog_names:
        return key
    i = key.rfind("-")
    if i <= 0:
        return None
    base = key[:i]
    return base if base in catalog_names else None


async def catalog_service_names() -> set[str]:
    """plate 目录服务名集合(**全量**,b2-7 起经 plate_client 唯一访问件)。

    六个消费方中:别名校验/导入映射/导入重锚定须全量;carry 按 D-M
    落地。**过滤不得下沉到本函数**(sut 过滤唯一出口在别名创建派生点,
    归一 v1.0 §1.6/§6.1)。带 kind 的扁平行视图见
    ``plate_client.catalog_service_entries``。
    """
    from . import plate_client

    return {e["name"] for e in await plate_client.catalog_service_entries()
            if e.get("name")}


async def known_service_names(db) -> set[str]:
    """平台侧已知服务名 = plate 目录 ∪ 服务主档(重构 §2.2 校验单源)。

    plate 不可达 → 目录降级空集,主档行仍在(注册簿自足);主档登记
    即权威 —— external 服务(不在 plate 目录)同样可作 base。
    """
    from ..models.service import Service

    registered = set((await db.execute(sa_select(Service.name))).scalars())
    return registered | await catalog_service_names()


async def resolve_base_with_aliases(db, key: str) -> str | None:
    """基名解析(重构:身份条目优先):**先查条目表
    ``service_identities.base_service``**(external 显式值/sut 已派生
    值),未登记的裸服务键再走目录 ``derive_base``(目录 ∪ 主档)。

    sut 行为不变约束(批0 基线 B10):sut 条目的 base_service 即创建时
    derive_base 派生值,两路结果一致;外部条目不守 ``<服务名>-<后缀>``
    规约,条目表优先是其唯一解析途径。
    """
    from ..models.service_identity import ServiceIdentity  # 延迟导入防环

    hit = (await db.execute(
        sa_select(ServiceIdentity.base_service)
        .where(ServiceIdentity.alias_name == key))).scalar_one_or_none()
    if hit:
        return hit
    names = await known_service_names(db)
    return derive_base(key, names) if names else None
