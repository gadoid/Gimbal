"""服务名别名推导(spec §4.2)—— 前端 service-alias.ts deriveBase 的后端移植。

别名 = <目录服务名>-<后缀>;切分点固定在最后一个 "-",base 必须落在目录
集合内才生效(裸声明不猜)。目录集合来自 plate services 列表;plate 不可达
→ 空集 → 全部裸声明(该 step 跳过填充 + 黄警,不阻塞执行)。
"""
from __future__ import annotations

import httpx

from .plate_client import get_client


def derive_base(key: str, catalog_names: set[str]) -> str | None:
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
    """目录服务名集合(**全量**,b2-7 起经 plate_client 唯一访问件)。

    六个消费方中:别名校验/导入映射/导入重锚定须全量;carry 按 D-M
    落地。**过滤不得下沉到本函数**(sut 过滤唯一出口在别名创建派生点,
    归一 v1.0 §1.6/§6.1)。带 kind 的扁平行视图见
    ``plate_client.catalog_service_entries``。
    """
    from . import plate_client

    return {e["name"] for e in await plate_client.catalog_service_entries()
            if e.get("name")}
