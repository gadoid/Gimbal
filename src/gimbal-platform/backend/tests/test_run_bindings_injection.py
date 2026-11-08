"""serviceBindings 注入 + 模板扫描驱动注入清单(spec §5/§6)。

capture 读 case.json(_patch_launch_capture),断言物化结果:绑定 url
覆盖 services、绑定 authAlias 注入 users、steps 里的 ${auth.*} 引用
即使无绑定也进注入清单。PlateMock 用 echo 行为(converted 带 steps)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


_AUTH_STEP = {
    "kind": "step",
    "call": {"service": "fin-service", "path": "/x",
            "headers": {"Authorization": "${auth.qa1.token}"}},
}


async def _seed_pool_auth(username: str, alias: str = "qa1") -> None:
    """S5 失败即中止:注入清单的槽位须在执行人池 —— 测试种一行。"""
    from app.core import db as db_module
    from app.core.security import fernet_encrypt
    from app.models.auth_session import AuthSession as _AS
    from sqlalchemy import select as _sel, text as _txt

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(_txt(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()
        s.add(_AS(owner_id=uid, alias=alias, url="http://auth",
                  username_enc=fernet_encrypt("u"),
                  password_enc=fernet_encrypt("p"),
                  slot=alias, is_default=True))
        await s.commit()


async def _seed_scenario(client, headers) -> None:
    r = await client.post("/api/scenarios", headers=headers,
                          json=_draft(steps=[_AUTH_STEP]))
    assert r.status_code in (200, 201), r.text


async def _last_config_json() -> dict:
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(Execution.id.desc()))
              ).scalars().first()
        return ex.config_json


async def test_binding_url_and_auth_materialized(client, plate_mock: PlateMock,
                                                 monkeypatch):
    """serviceBindings {url, authAlias} → case.json services 物化 +
    config_json 留痕 injectedAuths/serviceBindings。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"authAlias": "qa1", "url": "https://bound"}},
    ))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    cfg = cases[0]["config"]
    assert cfg["services"]["fin-service"] == "https://bound"
    # S5 起注入槽必须在执行人池(缺 = 整单拒发);在池 → users 注入 qa1
    assert "qa1" in (cfg.get("users") or {})

    config_json = await _last_config_json()
    assert config_json["serviceBindings"]["fin-service"]["authAlias"] == "qa1"
    assert config_json["injectedAuths"] == ["qa1"]      # 扫描 ∪ 绑定
    # 旧键退役(两种历史写法都兜住;实际键名以 :368-383 现码为准,删除后均过)
    for gone in ("prefix", "mergePolicy", "injectCredentials",
                 "execAuthAlias", "exec_auth_alias"):
        assert gone not in config_json


async def test_template_scan_without_binding_injects(client, plate_mock: PlateMock,
                                                     monkeypatch):
    """steps 引用 ${auth.qa1.token}(无绑定)→ qa1 仍进注入清单留痕。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    config_json = await _last_config_json()
    assert config_json["injectedAuths"] == ["qa1"]
    assert config_json["serviceBindings"] == {}


async def test_legacy_payload_fields_silently_ignored(client, plate_mock: PlateMock,
                                                      monkeypatch):
    """旧客户端发 auths/prefix/mergePolicy → 不 422,仅失效(spec §6)。"""
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    payload = _run_payload(dataSetIds=[])
    payload.update({"auths": ["qa1"], "prefix": "T-1",
                    "mergePolicy": "override", "injectCredentials": False})
    r = await client.post("/api/runs", headers=bob, json=payload)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert (cfg.get("vars") or {}).get("order_no_prefix") is None   # prefix 失效


async def test_missing_auth_slot_refuses_dispatch(client, plate_mock: PlateMock):
    """S5 失败即中止:注入清单的槽位不在执行人池 → 整单 409
    auth_aliases_missing(此前告警继续、执行期步骤级报错)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "missauth")
    await _seed_scenario(client, bob)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"authAlias": "qa-none"}}))
    assert r.status_code == 409, r.text
    assert "auth_aliases_missing" in r.text
    assert "qa-none" in r.text
