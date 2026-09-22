"""用户偏好通用读写(GET /api/me/preferences + PUT .../{key})回归。

白名单是这张表不变成杂物间的唯一屏障,所以三条都要钉:白名单外的键拒读
拒写、形态不符拒收、归属硬隔离。另外「空值是有效值」这条必须成立 ——
常驻席全部取消 = ``{"ids": []}``,与"从没存过"(GET 不回这个键)是两回事,
前端首帧要区分播种还是尊重空。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import register_and_login

_LAYOUT = {"order": ["follows", "recent-runs"], "sizes": {"follows": "M", "recent-runs": "S"}}


async def _mk(client: AsyncClient, name: str) -> dict:
    return await register_and_login(client, name, f"{name}-pass-123")


async def _get(client: AsyncClient, hdr: dict) -> dict:
    r = await client.get("/api/me/preferences", headers=hdr)
    assert r.status_code == 200
    return r.json()["items"]


async def test_empty_until_written(client: AsyncClient):
    hdr = await _mk(client, "pref_new")
    assert await _get(client, hdr) == {}


async def test_put_then_get_roundtrip(client: AsyncClient):
    hdr = await _mk(client, "pref_layout")
    r = await client.put(
        "/api/me/preferences/workbench.layout", headers=hdr,
        json={"value": _LAYOUT})
    assert r.status_code == 200
    assert r.json() == {"key": "workbench.layout", "value": _LAYOUT}
    assert await _get(client, hdr) == {"workbench.layout": _LAYOUT}


async def test_empty_value_is_stored_and_distinct_from_absent(client: AsyncClient):
    hdr = await _mk(client, "pref_empty")
    r = await client.put(
        "/api/me/preferences/follows.pinned", headers=hdr, json={"value": {"ids": []}})
    assert r.status_code == 200
    items = await _get(client, hdr)
    assert items == {"follows.pinned": {"ids": []}}   # 存了空 ≠ 没存


async def test_unknown_key_rejected_on_both_ends(client: AsyncClient):
    hdr = await _mk(client, "pref_stray")
    r = await client.put(
        "/api/me/preferences/devtools.cache", headers=hdr, json={"value": {"a": 1}})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "unknown_pref_key"
    assert await _get(client, hdr) == {}


async def test_value_shape_validated(client: AsyncClient):
    hdr = await _mk(client, "pref_shape")
    bad = [
        ("workbench.layout", {"order": ["a"], "sizes": {"a": "XL"}}),   # 尺寸值域
        ("workbench.layout", {"order": [""]}),                            # 空 id
        ("workbench.layout", "not-an-object"),                            # 整体形态
        ("timeline.colors", {"execution": "x" * 200}),                    # 单值过长
        ("follows.pinned", {"ids": [f"s{i}" for i in range(21)]}),        # 超上限
    ]
    for key, value in bad:
        r = await client.put(f"/api/me/preferences/{key}", headers=hdr, json={"value": value})
        assert r.status_code == 422, f"{key}={value} 本该被拒"
        assert r.json()["detail"]["code"] == "bad_pref_value"
    assert await _get(client, hdr) == {}   # 一次都没落库


async def test_preferences_do_not_leak_across_users(client: AsyncClient):
    owner = await _mk(client, "pref_a")
    other = await _mk(client, "pref_b")
    await client.put(
        "/api/me/preferences/timeline.colors", headers=owner,
        json={"value": {"execution": "var(--avatar-5)",
                        "scenario": "var(--avatar-3)", "adaptation": "var(--avatar-4)"}})
    assert "timeline.colors" not in await _get(client, other)
    # 另一个人写同名键不覆盖对方,各存各行
    r = await client.put(
        "/api/me/preferences/timeline.colors", headers=other,
        json={"value": {"execution": "var(--avatar-1)",
                        "scenario": "var(--avatar-2)", "adaptation": "var(--avatar-3)"}})
    assert r.status_code == 200
    assert await _get(client, owner) == {
        "timeline.colors": {"execution": "var(--avatar-5)", "scenario": "var(--avatar-3)",
                            "adaptation": "var(--avatar-4)"}}


async def test_requires_auth(client: AsyncClient):
    assert (await client.get("/api/me/preferences")).status_code in (401, 403)
    assert (await client.put(
        "/api/me/preferences/workbench.layout",
        json={"value": _LAYOUT})).status_code in (401, 403)
