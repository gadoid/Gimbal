"""用户偏好通用读写(GET /api/me/preferences + PUT .../{key})回归。

白名单是这张表不变成杂物间的唯一屏障,所以三条都要钉:白名单外的键拒读
拒写、形态不符拒收、归属硬隔离。另外「空值是有效值」这条必须成立 ——
常驻席全部取消 = ``{"ids": []}``,与"从没存过"(GET 不回这个键)是两回事,
前端首帧要区分播种还是尊重空。
"""
from __future__ import annotations

from httpx import AsyncClient

from app.models.integration_task import IntegrationTask
from app.models.user import User
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
        ("pager.sizes", {"sizes": {"auths": 0}}),                         # 行数下界
        ("pager.sizes", {"sizes": {"auths": 501}}),                       # 行数上界
        ("pager.sizes", {"sizes": {"auths": "20"}}),                      # 非整数
        ("pager.sizes", {"sizes": {f"p{i}": 20 for i in range(65)}}),     # 页面键超上限
    ]
    for key, value in bad:
        r = await client.put(f"/api/me/preferences/{key}", headers=hdr, json={"value": value})
        assert r.status_code == 422, f"{key}={value} 本该被拒"
        assert r.json()["detail"]["code"] == "bad_pref_value"
    assert await _get(client, hdr) == {}   # 一次都没落库


async def test_pager_sizes_roundtrip(client: AsyncClient):
    """2026-09-23 分页批次:每页行数偏好走通用白名单键,整值覆盖。"""
    hdr = await _mk(client, "pref_pager")
    sizes = {"sizes": {"scenarios-mine": 50, "auths": 100}}
    r = await client.put(
        "/api/me/preferences/pager.sizes", headers=hdr, json={"value": sizes})
    assert r.status_code == 200
    assert await _get(client, hdr) == {"pager.sizes": sizes}
    # 整值覆盖:改一页不动另一页由前端合并,服务端只见最终整值
    r = await client.put(
        "/api/me/preferences/pager.sizes", headers=hdr,
        json={"value": {"sizes": {"auths": 20}}})
    assert r.status_code == 200
    assert await _get(client, hdr) == {"pager.sizes": {"sizes": {"auths": 20}}}


async def test_identity_card_shape_roundtrip(client: AsyncClient):
    """webhook v4 §4.3/D17:身份卡自定义 —— 统计/入口 ≤ 4,告警按类开关。"""
    hdr = await _mk(client, "pref_card")
    ok = {"stats": ["private_scenarios", "follows", "tokens", "auths"],
          "alerts": {"failed": True, "expired": False},
          "shortcuts": ["tokens", "notify"]}
    r = await client.put(
        "/api/me/preferences/identity.card", headers=hdr,
        json={"value": ok})
    assert r.status_code == 200
    assert await _get(client, hdr) == {"identity.card": ok}
    for bad in (
        {"stats": ["a", "b", "c", "d", "e"]},          # 统计超 4
        {"shortcuts": ["a", "b", "c", "d", "e"]},      # 入口超 4
        {"alerts": {"a": "maybe"}},                    # 开关非布尔(宽松词表外)
        {"stats": "tokens"},                           # 非列表
    ):
        r = await client.put(
            "/api/me/preferences/identity.card", headers=hdr,
            json={"value": {**ok, **bad}})
        assert r.status_code == 422, f"{bad} 本该被拒"
        assert r.json()["detail"]["code"] == "bad_pref_value"


async def test_notes_shape_roundtrip(client: AsyncClient):
    """webhook v4 §4.3/D18:便签 ≤ 20 条、每条 ≤ 200 字,整值覆盖。

    2026-11-05 评审 P1-2 回归钉:前端一直以驼峰 createdAt/doneAt 提交,
    此前无别名被静默丢弃(存成空串/None)。现在驼峰为出入形态,旧下划线
    存档读入兼容;未知字段 422(forbid),不再无声吞。"""
    hdr = await _mk(client, "pref_notes")
    ok = {"items": [
        {"id": "n1", "text": "查一下回调失败的三条", "done": False,
         "createdAt": "2026-11-04T10:00:00Z", "doneAt": None},
        {"id": "n2", "text": "续期 agent 令牌", "done": True,
         "createdAt": "2026-11-03T09:00:00Z",
         "doneAt": "2026-11-03T12:00:00Z"},
    ]}
    r = await client.put(
        "/api/me/preferences/notes", headers=hdr, json={"value": ok})
    assert r.status_code == 200
    assert r.json() == {"key": "notes", "value": ok}
    assert await _get(client, hdr) == {"notes": ok}
    # 旧下划线存档(修复前落库的形态)读入兼容 → 出侧归一成驼峰
    legacy = {"items": [{"id": "n3", "text": "旧档", "done": False,
                         "created_at": "2026-11-01T00:00:00Z",
                         "done_at": None}]}
    r = await client.put(
        "/api/me/preferences/notes", headers=hdr, json={"value": legacy})
    assert r.status_code == 200
    assert r.json()["value"]["items"][0]["createdAt"] == "2026-11-01T00:00:00Z"
    assert "created_at" not in r.json()["value"]["items"][0]
    # 回到驼峰主形态,后续断言不受 legacy 干扰
    await client.put("/api/me/preferences/notes", headers=hdr, json={"value": ok})
    for bad in (
        {"items": [{"id": f"n{i}", "text": "x"} for i in range(21)]},  # 超上限
        {"items": [{"id": "n", "text": "x" * 201}]},                    # 单条过长
        {"items": [{"id": "n", "text": ""}]},                           # 空文本
        {"items": [{"id": "n", "text": "ok", "done": "maybe"}]},        # 非布尔
        {"items": [{"id": "n", "text": "ok", "creatAt": "x"}]},         # 未知字段(forbid)
        {"items": [{"id": "n", "text": "ok"}], "sort": "asc"},          # 顶层未知字段
    ):
        r = await client.put(
            "/api/me/preferences/notes", headers=hdr,
            json={"value": bad})
        assert r.status_code == 422, f"{bad} 本该被拒"
        assert r.json()["detail"]["code"] == "bad_pref_value"
    # 拒收不落库:最后仍是上一份合法整值
    assert (await _get(client, hdr))["notes"] == ok


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


async def test_me_summary_200(client: AsyncClient):
    """webhook v4 P3 §3:/me/summary 统计与告警一次取回。

    回归钉:me_summary 曾把 `await db.execute(...).scalars()` 整链 await
    (对 coroutine 调 .scalars → 500,2026-11-05 修复)。"""
    from .inbound_fixtures import seed_platform_user
    await seed_platform_user()
    hdr = await _mk(client, "pref_summary")
    r = await client.get("/api/me/summary", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "stats" in body and "alerts" in body
    # 无令牌无任务的全新用户:统计键齐全,值为 0
    assert body["stats"].get("private_scenarios") == 0
    assert body["stats"].get("tokens") == 0


async def test_me_summary_platform_pause_fanout(client: AsyncClient):
    """2026-11-05 评审 P2-7 回归钉:平台模式任务的暂停告警对 member 可见
    (平台实例 holder 是系统用户,按 holder 过滤等于永不可见);告警深链
    到实例详情;auth_failed(凭证认证失败)在告警范围内;普通 user 角色
    不看平台暂停(与通知 fanout_members 的 member+ 口径一致)。"""
    from .inbound_fixtures import seed_platform_user, mk_task_pair
    from app.core.db import SessionLocal
    from sqlalchemy import update as sa_update

    await seed_platform_user()
    tpl_id, inst_id, _ = await mk_task_pair(
        name="平台探活", identity_mode="platform")
    async with SessionLocal() as s:
        await s.execute(sa_update(IntegrationTask).where(
            IntegrationTask.id == inst_id).values(
            state="paused", paused_reason="auth_failed"))
        await s.commit()

    member_hdr = await _mk(client, "pref_sum_fanout")
    async with SessionLocal() as s:
        await s.execute(sa_update(User).where(
            User.username == "pref_sum_fanout").values(role="member"))
        await s.commit()
    r = await client.get("/api/me/summary", headers=member_hdr)
    assert r.status_code == 200
    paused = [a for a in r.json()["alerts"]
              if a["class"] == "integration_paused"]
    assert paused, "member 应看到平台任务暂停告警"
    assert paused[0]["title"].startswith("平台探活")
    assert "凭证认证失败" in paused[0]["title"]
    assert paused[0]["link"] == f"/integrations/{inst_id}"

    # 普通 user(role=user)不看平台暂停:告警里没有这一类
    user_hdr = await register_and_login(
        client, "pref_sum_plain", "pref-sum-plain-pass-123")
    from app.core.db import SessionLocal as _S
    async with _S() as s:
        await s.execute(sa_update(User).where(
            User.username == "pref_sum_plain").values(role="user"))
        await s.commit()
    r = await client.get("/api/me/summary", headers=user_hdr)
    assert r.status_code == 200
    assert not [a for a in r.json()["alerts"]
                if a["class"] == "integration_paused"]
