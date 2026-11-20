"""决策 1「引用即登记」保存/导入闸(阶段 0;identity-registry §2)+ 声明
侧同 base 闸(阶段 3;TOK-07 声明面收口)。

三态口径(off / audit / enforce)× 三挂载链(场景 create / PUT 更新 /
导入 land):

* off = 现状,无痕;audit = 保存成功 + 警告载体(场景 create/PUT 走
  ``X-Identity-Warnings`` 头,导入响应 dict 走 ``identityWarnings`` 键
  —— 两种载体前端阶段 2 选取器统一收口);enforce = 422
  ``identity_not_registered``;
* 已登记名放行(enforce 不误伤);
* enforce 拒收时导入的**单事务语义**:映射 create 出的条目随拒收一并
  回滚(库内无新条目、无场景行)。

阶段 3 同 base 步:已登记条目 base 须 == 所在步骤服务的基础服务
(``validate_binding_aliases`` 同口径);enforce 422
``identity_base_mismatch``,audit ``X-Identity-Base-Warnings`` 头 /
导入 ``identityBaseWarnings`` 键(独立载体,可与存在性告警同时成立);
未登记名不进本闸(存在闸业务),setup/teardown 无步骤锚点不比对。

运行方案保存无定义侧引用面,由 ``validate_binding_aliases`` 既有覆盖
(s60 绑定闸用例),不在此重复测。
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.models.composer_scenario import ComposerScenario
from app.models.service_identity import ServiceIdentity

from .helpers import make_draft, role_headers
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_import_pipeline import _bundle, _mock_faces, _seed_env


def _steps(auth_ref: str = "ghost") -> list[dict]:
    """fin.orders.get 最小步 + ``${auth.<X>.token}`` 模板引用(call.headers
    字符串值 —— auth_ref_scan 递归扫,与导入 bundle 的 Authorization 头
    同款形态)。"""
    auth_header = f"${{auth.{auth_ref}.token}}"
    return [{
        "kind": "step", "endpoint": "fin.orders.get",
        "call": {"service": "fin-service", "method": "GET", "path": "/o",
                 "headers": {"Authorization": auth_header}},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]


async def _seed_identity(alias: str, base: str = "fin") -> None:
    """种注册表条目(+默认环境/服务行;镜像 s60 口径)。"""
    from app.models import Environment, Service

    async with db_module.SessionLocal() as s:
        env = (await s.execute(select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        if (await s.execute(select(Service.id).where(
                Service.name == base))).scalar_one_or_none() is None:
            s.add(Service(name=base, system=base, kind="plate"))
        s.add(ServiceIdentity(alias_name=alias, base_service=base,
                              env_id=env, ref_mode="default"))
        await s.commit()


@pytest.mark.asyncio
async def test_off_mode_no_gate(client, plate_mock, monkeypatch):
    """off:未登记引用照常保存,无警告头(阶段 0 前现状;显式钉 off ——
    生产 .env 已置 audit,缺省不再是 off)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "off")
    h = await role_headers(client, "gate-off")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-off", steps=_steps()))
    assert r.status_code == 201, r.text
    assert "X-Identity-Warnings" not in r.headers


@pytest.mark.asyncio
async def test_audit_mode_warns_but_saves(client, plate_mock, monkeypatch):
    """audit:保存成功 + X-Identity-Warnings 头点名未登记引用。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "audit")
    h = await role_headers(client, "gate-audit")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-audit", steps=_steps()))
    assert r.status_code == 201, r.text
    warn = json.loads(r.headers["X-Identity-Warnings"])
    assert warn["code"] == "identity_not_registered"
    assert warn["identities"] == ["ghost"]


@pytest.mark.asyncio
async def test_enforce_mode_rejects(client, plate_mock, monkeypatch):
    """enforce:422 identity_not_registered,未落库。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    h = await role_headers(client, "gate-enf")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-enf", steps=_steps()))
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["code"] == "identity_not_registered"
    assert d["identities"] == ["ghost"]
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == "sc-gate-enf"))
        ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_enforce_allows_registered_same_base(
        client, plate_mock, monkeypatch):
    """enforce 下已登记名放行 —— 阶段 3 语义收紧:条目 base 须与步骤
    服务同源(seeding 服务键即 base);同源 → 201 无任何警告头。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    await _seed_identity("ghost-reg", base="fin-service")
    h = await role_headers(client, "gate-reg")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-reg", steps=_steps(auth_ref="ghost-reg")))
    assert r.status_code == 201, r.text
    assert "X-Identity-Warnings" not in r.headers
    assert "X-Identity-Base-Warnings" not in r.headers


@pytest.mark.asyncio
async def test_enforce_rejects_cross_base(client, plate_mock, monkeypatch):
    """enforce + 已登记条目跨 base(gitlab 条目注入 fin-service 步骤)
    → 422 identity_base_mismatch,refs 逐步骤定位,未落库。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    await _seed_identity("gitlab", base="gitlab")
    h = await role_headers(client, "gate-xbase")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-xbase", steps=_steps(auth_ref="gitlab")))
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["code"] == "identity_base_mismatch"
    ref = d["refs"][0]
    assert ref == {"index": 0, "service": "fin-service", "identity": "gitlab",
                   "identityBase": "gitlab", "serviceBase": "fin-service"}
    assert "gitlab" in d["message"]
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == "sc-gate-xbase"))
        ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_audit_base_warnings_header(client, plate_mock, monkeypatch):
    """audit + 跨 base 已登记条目 → 201 + X-Identity-Base-Warnings 头
    (refs 结构化);存在性头不出现(该引用已登记)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "audit")
    await _seed_identity("gitlab-a", base="gitlab")
    h = await role_headers(client, "gate-audit-xb")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-audit-xb", steps=_steps(auth_ref="gitlab-a")))
    assert r.status_code == 201, r.text
    assert "X-Identity-Warnings" not in r.headers
    warn = json.loads(r.headers["X-Identity-Base-Warnings"])
    assert warn["code"] == "identity_base_mismatch"
    assert warn["refs"][0]["identity"] == "gitlab-a"
    assert warn["refs"][0]["identityBase"] == "gitlab"


@pytest.mark.asyncio
async def test_audit_both_warnings_coexist(client, plate_mock, monkeypatch):
    """audit:未登记(ghost)+ 跨 base(gitlab)同时成立 → 两个头各自
    独立,互不吞并。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "audit")
    await _seed_identity("gitlab-b", base="gitlab")
    h = await role_headers(client, "gate-audit-both")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-audit-both", steps=_steps(auth_ref="gitlab-b") + _steps()))
    assert r.status_code == 201, r.text
    assert json.loads(
        r.headers["X-Identity-Warnings"])["identities"] == ["ghost"]
    assert json.loads(
        r.headers["X-Identity-Base-Warnings"])["refs"][0]["identity"] == \
        "gitlab-b"


@pytest.mark.asyncio
async def test_same_base_skips_unregistered_and_anchored_faces(
        client, plate_mock, monkeypatch):
    """扫描边界:未登记名不进同 base 闸(存在闸业务);call.user 直引
    **进**闸(跨 base 照拦);setup/teardown 模板引用无步骤锚点不比对
    (其存在性仍走存在闸)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "audit")
    await _seed_identity("gitlab-c", base="gitlab")
    h = await role_headers(client, "gate-scan-edge")
    steps = _steps()  # 未登记 ghost → 只进存在闸
    steps[0]["call"]["user"] = "gitlab-c"  # 跨 base 直引 → 进同 base 闸
    draft = make_draft("sc-gate-scan-edge", steps=steps)
    draft["definition"]["config"] = {"setup": [{
        "kind": "step", "endpoint": "fin.orders.get",
        "call": {"service": "fin-service", "method": "GET", "path": "/s",
                 "headers": {"Authorization": "${auth.gitlab-c.token}"}},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]}
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code == 201, r.text
    base_refs = json.loads(
        r.headers["X-Identity-Base-Warnings"])["refs"]
    # 唯一违规 = 步骤内 call.user;setup 内同条目模板引用不重复产生行
    assert [r0["identity"] for r0 in base_refs] == ["gitlab-c"]
    assert base_refs[0]["service"] == "fin-service"
    assert "X-Identity-Warnings" in r.headers  # ghost 走存在闸


@pytest.mark.asyncio
async def test_service_key_entry_base_lookup(client, plate_mock, monkeypatch):
    """步骤服务键本身有条目行时,svc base 取其行 base(非条目即自身
    回落不适用):条目 fin-m 挂 fin-service 行(base fin),引用条目
    base 也是 fin → 同源放行。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    await _seed_identity("fin-service", base="fin")   # 服务键同名条目行
    await _seed_identity("fin-m", base="fin")
    h = await role_headers(client, "gate-svckey")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-svckey", steps=_steps(auth_ref="fin-m")))
    assert r.status_code == 201, r.text
    assert "X-Identity-Base-Warnings" not in r.headers


@pytest.mark.asyncio
async def test_update_put_same_gate(client, plate_mock, monkeypatch):
    """PUT 更新同一道闸:off 建场景 → audit 更新带未登记引用 →
    200 + 头(存量未登记引用正是 audit 态要观测的对象,update 同警示)。"""
    h = await role_headers(client, "gate-put")
    r = await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-gate-put", steps=_steps()))
    assert r.status_code == 201, r.text
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "audit")
    r = await client.put("/api/scenarios/sc-gate-put", headers=h, json=make_draft(
        "sc-gate-put", steps=_steps()))
    assert r.status_code == 200, r.text
    warn = json.loads(r.headers["X-Identity-Warnings"])
    assert warn["identities"] == ["ghost"]


@pytest.mark.asyncio
async def test_import_audit_warns(client, plate_mock, monkeypatch):
    """导入同口径:audit 态 qa1(${auth.qa1.token} 未登记)随响应 dict
    的 identityWarnings 键返回;映射 create 出的 fin-service-qa 在闸前
    已入事务 → 算已登记,不进警告。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "audit")
    _mock_faces(plate_mock)
    h = await role_headers(client, "gate-imp-admin1", role="admin")
    await _seed_env()
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle(sid="sc-gate-imp-audit"),
        "mappings": [{"serviceKey": "fin-service-qa", "decision": "create"}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["identityWarnings"] == ["qa1"]


@pytest.mark.asyncio
async def test_import_enforce_rejects_and_rolls_back(
        client, plate_mock, monkeypatch):
    """enforce 态导入拒收;单事务语义 —— 映射 create 出的条目随拒收
    一并回滚(库内无 fin-service-qa、无场景行)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    _mock_faces(plate_mock)
    h = await role_headers(client, "gate-imp-admin2", role="admin")
    await _seed_env()
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle(sid="sc-gate-imp-enf"),
        "mappings": [{"serviceKey": "fin-service-qa", "decision": "create"}],
    })
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["code"] == "identity_not_registered"
    assert "qa1" in d["message"]
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name == "fin-service-qa"))
        ).scalar_one_or_none() is None
        assert (await s.execute(select(ComposerScenario.scenario_id).where(
            ComposerScenario.scenario_id == "sc-gate-imp-enf"))
        ).scalar_one_or_none() is None
