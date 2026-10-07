"""迁移等价校验（A1，第 5 节：转换结果以等价校验作为评审依据）。

对全部 149 个存量接口（S1-0 B3 后：fin 23 + platform 126，原 151）：
old EndpointSpec → convert → render Markdown → parse → 与 convert 结果
canonical 全等。白名单：version/updated_at 删除、MIME 弃置、键 int→str、
body_type 移入 binding（见 migrate.WHITELIST_NOTES）。
"""
from __future__ import annotations

import pytest

from gimbal_plate.dialect import EndpointSpec, parse_markdown, render
from gimbal_plate.dialect.migrate import (
    WHITELIST_NOTES,
    convert_endpoint,
    endpoint_to_deliverable,
    equivalent,
    render_endpoint_markdown,
)
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS as FIN_ENDPOINTS
from gimbal_plate.systems.platform.endpoint import (
    ALL_ENDPOINTS as PLATFORM_ENDPOINTS,
)

ALL_OLD = [*FIN_ENDPOINTS, *PLATFORM_ENDPOINTS]


def test_endpoint_inventory() -> None:
    """迁移覆盖面：S1-0 后全量 149（fin 23 + platform 126）。"""
    assert len(FIN_ENDPOINTS) == 23
    assert len(PLATFORM_ENDPOINTS) == 126
    assert len(ALL_OLD) == 149


@pytest.mark.parametrize("old", ALL_OLD, ids=[e.id for e in ALL_OLD])
def test_migrate_roundtrip_equivalent(old) -> None:
    """单接口等价：convert → Markdown → parse ≡ convert（canonical 全等）。"""
    converted = convert_endpoint(old)
    md = render_endpoint_markdown(converted)
    parsed = parse_markdown(md, source=f"migrated:{old.id}.md")
    (block,) = parsed.blocks("endpoint")
    assert block.review == "reviewed", "迁移内容信封一律 reviewed（修订四）"
    ep = block.payload
    assert isinstance(ep, EndpointSpec)
    ok, diffs = equivalent(old, ep)
    assert ok, f"等价校验失败(白名单: {WHITELIST_NOTES}): {diffs}"


def test_migration_idempotent_render() -> None:
    """生成的 Markdown 是规范形：再渲染字节不动。"""
    for old in ALL_OLD[:20]:  # 抽样 20 个足以锁幂等
        r1 = render_endpoint_markdown(convert_endpoint(old))
        r2 = render(parse_markdown(r1, source="r1"))
        assert r1 == r2, f"{old.id} 迁移产物非规范形"


def test_migration_whitelist_normalization() -> None:
    """白名单归一抽检：version/updated_at/MIME 不出现于产物。"""
    old = next(e for e in ALL_OLD if e.id == "fin.order.order_add")
    md = render_endpoint_markdown(convert_endpoint(old))
    for absent in ("version:", "updated_at:", "application/json"):
        assert absent not in md, f"迁移产物不应含 {absent!r}"
    ep = parse_markdown(md).blocks("endpoint")[0].payload
    assert ep.consumes == [] and ep.produces == []
    assert set(ep.responses) == {str(k) for k in old.responses}


def test_migration_hash_stable_across_instances() -> None:
    """内容寻址前提：同内容两次转换 hash 相同（旧栈的 updated_at 陷阱已除）。"""
    from gimbal_plate.dialect import object_hash, shape_hash

    old = ALL_OLD[0]
    h1 = (object_hash(convert_endpoint(old)), shape_hash(convert_endpoint(old)))
    h2 = (object_hash(convert_endpoint(old)), shape_hash(convert_endpoint(old)))
    assert h1 == h2


_ = endpoint_to_deliverable  # 公开 API 完整性
