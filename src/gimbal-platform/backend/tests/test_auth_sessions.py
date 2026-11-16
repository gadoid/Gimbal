"""Tests for the /api/auths router(registry rework §1.4 账户实体化)。

Covers(P1-7 续期,布景按 conftest.seed_identity_fixture 四件套):
- list/create/get/patch/delete lifecycle(账户四元组 (pool,system,env,
  username) 唯一;首账户自动 is_default)
- password is encrypted at rest(never plaintext in DB or response);
  username 明文实体键
- cross-owner isolation: alice can't see/edit bob's accounts
- /test endpoint: 实例 login_url + 账户凭据(实例缺席明确报)+ 4xx
- set-default 端点与 patch is_default 的同域互斥
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models import AuthAccount, Environment

from .conftest import seed_identity_fixture
from .helpers import register_and_login


async def _seed_env(name: str = "测试") -> int:
    """API 测试的最低布景:一个环境行(账户 env 必填的外键落点)。"""
    factory = db_module.SessionLocal
    async with factory() as db:
        env = (await db.execute(
            select(Environment.id).where(Environment.name == name))
        ).scalar_one_or_none()
        if env is None:
            db.add(Environment(name=name, is_default=True))
            await db.commit()
            env = (await db.execute(
                select(Environment.id).where(Environment.name == name))
            ).scalar_one()
        return env


# ── lifecycle ────────────────────────────────────────────────────
async def test_list_initially_empty(client) -> None:
    auth = await register_and_login(client)
    r = await client.get("/api/auths", headers=auth)
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_create_requires_known_environment(client) -> None:
    """env 必填收紧(§1.4):环境不存在 → 404 code=environment_not_found。"""
    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": 999,
              "username": "u", "password": "p"},
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "environment_not_found"


async def test_create_then_list_returns_one(client) -> None:
    auth = await register_and_login(client)
    env = await _seed_env()

    r = await client.post(
        "/api/auths",
        headers=auth,
        json={
            "system": "fin-service",
            "envId": env,
            "username": "alice_user",
            "password": "s3cret",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "alice_user"
    assert body["system"] == "fin-service"
    assert body["envId"] == env
    assert body["isDefault"] is True  # 该 (system,env) 首账户即默认
    assert body["password_masked"] == "<REDACTED>"
    assert "password" not in body  # plaintext never leaks

    r = await client.get("/api/auths", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["page"] == 1
    items = body["items"]
    assert len(items) == 1
    assert items[0]["username"] == "alice_user"


async def test_password_is_encrypted_at_rest(client) -> None:
    """Direct DB introspection — the password column must NOT contain the plaintext."""
    auth = await register_and_login(client)
    env = await _seed_env()

    await client.post(
        "/api/auths",
        headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "alice_user", "password": "plaintext-pw-12345"},
    )

    factory = db_module.SessionLocal
    async with factory() as s:
        rows = (await s.execute(select(AuthAccount))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert "plaintext-pw-12345" not in row.password_enc
    # username 是账户实体键(进唯一键)—— 明文列,不再是密文
    assert row.username == "alice_user"
    # Fernet ciphertext is a base64 token starting with 'gAAA' typically.
    assert len(row.password_enc) > 32


# ── account tuple uniqueness ─────────────────────────────────────
async def test_account_tuple_must_be_unique(client) -> None:
    """同 (owner, system, env, username) 二次登记 → 409。"""
    auth = await register_and_login(client)
    env = await _seed_env()

    payload = {"system": "fin-service", "envId": env,
               "username": "u", "password": "p"}
    r1 = await client.post("/api/auths", headers=auth, json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/auths", headers=auth, json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()


async def test_same_account_different_owners_is_ok(client) -> None:
    """账户按池隔离:alice/bob 各自登记同 (system,env,username) 都行。"""
    a_auth = await register_and_login(client)
    b_auth = await register_and_login(client, "bob", "bobpass456")
    env = await _seed_env()

    for headers in (a_auth, b_auth):
        r = await client.post(
            "/api/auths",
            headers=headers,
            json={"system": "fin-service", "envId": env,
                  "username": "u", "password": "p"},
        )
        assert r.status_code == 201, r.text

    a_list = await client.get("/api/auths", headers=a_auth)
    b_list = await client.get("/api/auths", headers=b_auth)
    assert len(a_list.json()["items"]) == 1
    assert len(b_list.json()["items"]) == 1


# ── cross-owner isolation ─────────────────────────────────────────
async def test_cannot_get_other_owners_auth(client) -> None:
    a_auth = await register_and_login(client)
    env = await _seed_env()

    r = await client.post(
        "/api/auths", headers=a_auth,
        json={"system": "fin-service", "envId": env,
              "username": "u", "password": "p"},
    )
    alice_id = r.json()["id"]

    b_auth = await register_and_login(client, "bob", "bobpass456")

    r = await client.get(f"/api/auths/{alice_id}", headers=b_auth)
    assert r.status_code == 404, r.text
    r = await client.patch(
        f"/api/auths/{alice_id}", headers=b_auth, json={"token_type": "Basic"}
    )
    assert r.status_code == 404
    r = await client.delete(f"/api/auths/{alice_id}", headers=b_auth)
    assert r.status_code == 404


# ── patch ────────────────────────────────────────────────────────
async def test_patch_updates_password_and_token_type(client) -> None:
    auth = await register_and_login(client)
    env = await _seed_env()

    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    # 一处改密处处生效(决策 5):只重加密 password
    r = await client.patch(
        f"/api/auths/{aid}", headers=auth, json={"password": "new-pw-999"})
    assert r.status_code == 200
    r = await client.patch(
        f"/api/auths/{aid}", headers=auth, json={"token_type": "Basic"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "Basic"
    assert r.json()["username"] == "u"  # 实体键不可改


async def test_default_is_exclusive_per_system_env(client) -> None:
    """同 (system,env) 至多一个默认:patch isDefault 挤掉旧默认;
    set-default 端点同语义。"""
    auth = await register_and_login(client)
    env = await _seed_env()

    r1 = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "u1", "password": "p"})
    r2 = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "u2", "password": "p"})
    assert r1.json()["isDefault"] is True  # 首账户即默认
    assert r2.json()["isDefault"] is False

    r = await client.patch(f"/api/auths/{r2.json()['id']}", headers=auth,
                           json={"isDefault": True})
    assert r.status_code == 200
    items = (await client.get("/api/auths", headers=auth)).json()["items"]
    by_user = {i["username"]: i["isDefault"] for i in items}
    assert by_user == {"u1": False, "u2": True}

    # set-default 端点把默认换回 u1
    r = await client.post(
        f"/api/auths/{r1.json()['id']}/default", headers=auth)
    assert r.status_code == 200
    assert r.json()["isDefault"] is True
    items = (await client.get("/api/auths", headers=auth)).json()["items"]
    by_user = {i["username"]: i["isDefault"] for i in items}
    assert by_user == {"u1": True, "u2": False}


# ── delete ──────────────────────────────────────────────────────
async def test_delete_returns_204(client) -> None:
    auth = await register_and_login(client)
    env = await _seed_env()
    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "u", "password": "p"},
    )
    aid = r.json()["id"]
    r = await client.delete(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 204
    r = await client.get(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 404


# ── 重存/删除 = runner 凭证缓存复活钩子(§7.5 口径延续)─────────
async def test_patch_and_delete_drop_runner_credential(
    client, monkeypatch
) -> None:
    """重存/删除账户 → 按「引用该账户的身份条目名」drop_credential
    (查询视图的凭证解析按条目;条目 = seed 四件套的 alias)。"""
    from app.services import query_view_runner as run

    auth = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=auth)).json()["user"]["id"]
    factory = db_module.SessionLocal
    async with factory() as db:
        await seed_identity_fixture(
            db, alias="qa1", username="alice", password="p",
            service="fin-service", owner_id=uid)

    items = (await client.get("/api/auths", headers=auth)).json()["items"]
    assert len(items) == 1
    aid = items[0]["id"]
    assert items[0]["identityRefCount"] == 1  # 条目 qa1 ref 该账户

    calls: list[tuple[int, str]] = []
    monkeypatch.setattr(run, "drop_credential",
                        lambda o, a: calls.append((o, a)))

    r = await client.patch(f"/api/auths/{aid}", headers=auth,
                           json={"password": "new-pw-9"})
    assert r.status_code == 200
    assert calls == [(uid, "qa1")]

    r = await client.delete(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 204
    assert calls == [(uid, "qa1"), (uid, "qa1")]


# ── /test endpoint(拨测 = 实例 login_url + 账户凭据)────────────
async def test_test_endpoint_returns_token_preview(
    client, monkeypatch
) -> None:
    """Mock 同步 httpx.post(probe 经 to_thread 调认证器)验证 token 提取;
    登录口来自实例行(四件套 seed 的 login_url)。"""
    import httpx

    req = httpx.Request("POST", "https://x")

    def fake_post(*a: object, **kw: object) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "fake-token-abcdef123456"}, request=req
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    auth = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=auth)).json()["user"]["id"]
    factory = db_module.SessionLocal
    async with factory() as db:
        await seed_identity_fixture(
            db, alias="qa1", username="u", password="p",
            service="fin-service", owner_id=uid, login_url="https://x")
    aid = (await client.get("/api/auths", headers=auth)).json()["items"][0]["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status_code"] == 200
    assert "fake-token" in body["message"]


async def test_test_endpoint_instance_missing_reports_clearly(client) -> None:
    """实例缺席 = 配置缺失(§4.3):明确报,不回退业务地址。"""
    auth = await register_and_login(client)
    env = await _seed_env()
    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "no-instance-svc", "envId": env,
              "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "实例未配置登录口" in body["message"]


async def test_test_endpoint_4xx_returns_failure(
    client, monkeypatch
) -> None:
    """401 → raise_for_status 抛 HTTPStatusError → ok=False、status_code=None。

    迁移后 probe 失败路径不再透传 4xx 码(auth_probe.py 失败分支恒 None),
    前端弹框仅在 status_code 非空时显示 HTTP badge。
    """
    import httpx

    req = httpx.Request("POST", "https://x")

    def fake_post(*a: object, **kw: object) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad creds"}, request=req)

    monkeypatch.setattr(httpx, "post", fake_post)

    auth = await register_and_login(client)
    uid = (await client.get("/api/auth/me", headers=auth)).json()["user"]["id"]
    factory = db_module.SessionLocal
    async with factory() as db:
        await seed_identity_fixture(
            db, alias="qa1", username="u", password="p",
            service="fin-service", owner_id=uid, login_url="https://x")
    aid = (await client.get("/api/auths", headers=auth)).json()["items"][0]["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["status_code"] is None
    assert "网络/认证错误" in body["message"]


# ── unauthenticated ─────────────────────────────────────────────
async def test_endpoints_require_auth(client) -> None:
    """All endpoints (except via register) need a valid token."""
    r = await client.get("/api/auths")
    assert r.status_code == 401
    r = await client.post(
        "/api/auths",
        json={"system": "x", "envId": 1, "username": "x", "password": "x"},
    )
    assert r.status_code == 401


# ── GET detail + include_secrets ─────────────────────────────────
async def test_detail_without_secrets_keeps_password_masked(client) -> None:
    """不带 include_secrets 的详情:行为与改造前一致,不泄露明文。"""
    auth = await register_and_login(client)
    env = await _seed_env()
    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "u", "password": "s3cret"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 200
    assert "password" not in r.json()
    assert r.json()["password_masked"] == "<REDACTED>"


async def test_detail_with_secrets_returns_plaintext(client) -> None:
    """include_secrets=true:附解密后的明文 password(内网测试环境策略)。"""
    auth = await register_and_login(client)
    env = await _seed_env()
    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "alice_user", "password": "s3cret"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "alice_user"
    assert body["password"] == "s3cret"


async def test_detail_with_secrets_cross_owner_404(client) -> None:
    a_auth = await register_and_login(client)
    env = await _seed_env()
    r = await client.post(
        "/api/auths", headers=a_auth,
        json={"system": "fin-service", "envId": env,
              "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    b_auth = await register_and_login(client, "bob", "bobpass456")
    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=b_auth)
    assert r.status_code == 404


async def test_detail_with_secrets_rotation_422(
    client, monkeypatch
) -> None:
    """FERNET_KEY 轮换后的旧密文:严解密失败 → 422(带人话指引)。

    快照拷贝会把返回值当真值写进场景导出产物,所以这里不能像列表
    _safe_decrypt 那样降级为占位符 — 必须显式失败。
    """
    from app.routers import auth_sessions as router_mod

    def boom(_s: str) -> str:
        raise ValueError("key rotated")

    monkeypatch.setattr(router_mod, "fernet_decrypt", boom)

    auth = await register_and_login(client)
    env = await _seed_env()
    r = await client.post(
        "/api/auths", headers=auth,
        json={"system": "fin-service", "envId": env,
              "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=auth)
    assert r.status_code == 422
    assert "重新编辑保存" in r.json()["detail"]
