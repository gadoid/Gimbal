"""场景导入流水线(W3/W4,场景导入 v2.3 方案):precheck 析出 + 单事务落库。

覆盖:析出三分支(复用/映射/新建)、P5「有接管者才清除」不变量、
敏感路径不进 carry、config.users 清空、URL 清除条件、ID 重铸、
mapping_stale、user 角色 403、体积门、格式判别。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.composer_scenario import ComposerScenario
from app.models.permission import AuditLog
from app.models.service_alias import ServiceAlias
from app.services import carry_store, scenario_import
from app.services.scenario_store import definition_from_payload

from .helpers import register_and_login
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401

_SCENARIO_ID = "sc-imp-1"


def _bundle(sid: str = _SCENARIO_ID, plate: dict | None = None) -> dict:
    """可执行形态测试文件:两服务(fin-service=目录内 / fin-service-qa=别名式)
    + carry 面字面值(remark/appCode 非敏感,api_token 敏感)+ ${auth.qa1} 引用
    + config.services 源 URL + config.users 导出人明文。"""
    return {
        "kind": "step",  # 顶层杂键:可执行产物可能带,不参与判别
        "scenarioId": sid,
        "meta": {
            "scenarioId": sid, "name": "Import", "module": "order",
            "priority": 1, "system": ["fin"],
            "plate": plate if plate is not None else {"fin": "1.0#1"},
        },
        "steps": [
            {"kind": "step", "endpoint": "fin.ep1",
             "call": {"service": "fin-service",
                      "headers": {"Authorization": "${auth.qa1.token}"}},
             "request": {"kind": "request", "body": {
                 "remark": "压测-张三", "appCode": "TRACE-V2",
                 "api_token": "sk-live", "keep_me": "always"}}},
            {"kind": "step", "endpoint": "fin.ep1",
             "call": {"service": "fin-service-qa", "headers": {}},
             "request": {"kind": "request", "body": {
                 "remark": "压测-李四", "api_token": "sk-qa"}}},
        ],
        "config": {
            "services": {"fin-service": "https://src",
                         "fin-service-qa": "https://src-qa"},
            "users": {"qa1": {"username": "src-user", "password": "src-pass"}},
        },
    }


def _mock_faces(pm: PlateMock) -> None:
    pm.behaviour = "echo"
    pm.services = [{"name": "fin-service"}]
    pm.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.remark", "state": "carry", "type": "string"},
        {"path": "$.appCode", "state": "carry", "type": "string"},
        {"path": "$.api_token", "state": "carry", "type": "string"},
    ]}}}


async def _stored_definition(sid: str) -> dict:
    async with db_module.SessionLocal() as db:
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        return definition_from_payload(row.payload or {})


# ── precheck ────────────────────────────────────────────────────────


async def test_precheck_analysis_branches(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"},
            updated_by_id=None, updated_by_name="seed")
        await db.commit()

    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": _bundle()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["blocking"] is False
    assert body["idConflict"] is False
    assert body["workingDeclarations"] == []
    assert body["authRefs"] == [{"tag": "qa1", "inMyPool": False}]

    by_key = {s["serviceKey"]: s for s in body["services"]}
    # fin-service(目录内,本机有部分值):remark 命中、appCode/api_token
    # 本机缺 → 路径级判"映射"(P7-⑤),缺值路径保留字面值
    fs = by_key["fin-service"]
    assert fs["suggestion"] == "map"
    assert fs["fieldsToAlias"] == 1          # 仅 remark 有本机接管者
    assert fs["fieldsKeptLiteral"] == 2      # appCode + api_token(敏感)
    assert fs["sensitivePaths"] == ["$.api_token"]
    # fin-service-qa(本机无):create;derive_base 落回 fin-service 可原样登记
    qa = by_key["fin-service-qa"]
    assert qa["suggestion"] == "create"
    assert qa["fieldsToAlias"] == 1          # remark(非敏感)
    assert qa["fieldsKeptLiteral"] == 1      # api_token(敏感,不进 carry)
    assert qa["createNameAvailable"] is True


async def test_precheck_reuse_when_all_matched(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service",
            {"$.remark": "压测-张三", "$.appCode": "TRACE-V2",
             "$.api_token": "sk-live"},
            updated_by_id=None, updated_by_name="seed")
        await db.commit()
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": _bundle()})
    by_key = {s["serviceKey"]: s for s in r.json()["services"]}
    assert by_key["fin-service"]["suggestion"] == "reuse"
    assert by_key["fin-service"]["fieldsToAlias"] == 3


async def test_precheck_blocking_missing_revision(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": _bundle(plate={"fin": "1.0#9"})})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["blocking"] is True
    # 缺失给可选集(PlateMock 缺省 /lines/{line}/revisions 回 [#1,#2])
    assert body["availableRevisions"].get("1.0") == ["1.0#1", "1.0#2"]


async def test_precheck_bad_bundle_422(client, plate_mock: PlateMock):
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": {"scenarioId": "sc-x"}})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_file"


# ── land ────────────────────────────────────────────────────────────


async def test_land_create_branch(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(),
        "mappings": [{"serviceKey": "fin-service-qa",
                      "decision": "create"}],
    })
    assert r.status_code == 201, r.text
    assert r.json() == {"scenarioId": _SCENARIO_ID, "idMode": "keep"}

    async with db_module.SessionLocal() as db:
        alias = (await db.execute(select(ServiceAlias).where(
            ServiceAlias.alias_name == "fin-service-qa"))).scalar_one()
        assert alias.owner_user_id is not None      # 个人默认登记
        # carry 只写非敏感路径的文件值(api_token 不落库,P7-②)
        binds = await carry_store.get_bindings(db, "fin-service-qa")
        assert binds == {"$.remark": "压测-李四"}
        audits = (await db.execute(select(AuditLog).where(
            AuditLog.resource_id == "fin-service-qa"))).scalars().all()
        assert {a.action for a in audits} >= {"alias.write", "carry.write"}

    defn = await _stored_definition(_SCENARIO_ID)
    step2 = defn["steps"][1]
    # P5:remark 有接管者(新别名)→ 清除;api_token 敏感未接管 → 字面值保留
    assert step2["request"]["body"] == {"api_token": "sk-qa"}
    # step1 未映射 → 原样(含字面值)
    assert defn["steps"][0]["request"]["body"]["remark"] == "压测-张三"
    # P2:config.users 清空;别名无 base_url → 源 URL 保留(不变量)
    assert "users" not in (defn.get("config") or {})
    assert defn["config"]["services"]["fin-service"] == "https://src"
    assert defn["config"]["services"]["fin-service-qa"] == "https://src-qa"


async def test_land_map_branch_never_deletes_uncovered(
        client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"},
            updated_by_id=None, updated_by_name="seed")
        await db.commit()
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(),
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}],
    })
    assert r.status_code == 201, r.text
    defn = await _stored_definition(_SCENARIO_ID)
    body = defn["steps"][0]["request"]["body"]
    # remark 本机有值 → 清除(本机为准);appCode/api_token 本机缺 → 保留
    assert "remark" not in body
    assert body["appCode"] == "TRACE-V2" and body["api_token"] == "sk-live"
    # 不向已有别名补值:fin-service 绑定仍只有 remark
    async with db_module.SessionLocal() as db:
        binds = await carry_store.get_bindings(db, "fin-service")
        assert binds == {"$.remark": "压测-张三"}


async def test_land_url_cleared_only_with_base_url(
        client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as db:
        db.add(ServiceAlias(alias_name="fin-service", base_service="fin-service",
                            base_url="https://local", owner_user_id=None))
        await db.commit()
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(), "mappings": []})
    assert r.status_code == 201, r.text
    defn = await _stored_definition(_SCENARIO_ID)
    services = defn["config"]["services"]
    # 别名有 base_url → 清;fin-service-qa 无别名 → 保留源 URL
    assert "fin-service" not in services
    assert services["fin-service-qa"] == "https://src-qa"


async def test_land_id_conflict_and_new_mode(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    # 第一次导入落库
    r1 = await client.post("/api/scenarios/import", headers=bob,
                           json={"bundle": _bundle(), "mappings": []})
    assert r1.status_code == 201, r1.text
    # 同 ID 再导(keep)→ 409 现状语义
    r2 = await client.post("/api/scenarios/import", headers=bob,
                           json={"bundle": _bundle(), "mappings": []})
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "scenario_id_exists"
    # new 模式:newId 回传(P4/R7)→ 201 且最终 ID = 回传值
    r3 = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(), "mappings": [],
        "idMode": "new", "newId": "sc-import-abc123"})
    assert r3.status_code == 201, r3.text
    assert r3.json()["scenarioId"] == "sc-import-abc123"
    defn = await _stored_definition("sc-import-abc123")
    assert defn["scenarioId"] == "sc-import-abc123"
    # newId 格式非法 → 422
    r4 = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(), "mappings": [], "idMode": "new",
        "newId": "Bad_ID"})
    assert r4.status_code == 422


async def test_land_mapping_stale(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    # "映射到已有"但本机不存在该服务 → 落库重算拒绝(mapping_stale)
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(),
        "mappings": [{"serviceKey": "fin-service-qa", "decision": "map"}]})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "mapping_stale"
    # 整体回滚:场景/别名/carry 均无残留
    async with db_module.SessionLocal() as db:
        assert (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == _SCENARIO_ID))
        ).scalar_one_or_none() is None


async def test_import_user_role_403(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    await register_and_login(client, "admin0", "admin0pass123")  # 首个= admin
    plain = await register_and_login(client, "plainuser", "pw123456")  # role=user
    for path, kwargs in (
        ("/api/scenarios/import/precheck", {"json": {"bundle": _bundle()}}),
        ("/api/scenarios/import",
         {"json": {"bundle": _bundle(), "mappings": []}}),
    ):
        r = await client.post(path, headers=plain, **kwargs)
        assert r.status_code == 403, (path, r.status_code)


# ── 一致性判定 + 按步骤清除(合入评估 §1 修复,Codfish 规则)──────
#
# 矩阵:同一服务多个步骤、各步骤取值不一致 / 模板混用 / 同名 form 字段 /
# 无锚点步骤 —— 三种决策(create/reuse/map)下都不得改写或删除任何步
# 骤的字面值;只有各步取值一致的路径才交给别名接管,且只从各步**自己
# carry 面**上清除。


def _multi_bundle(sid: str = "sc-imp-multi", svc: str = "fin-service-qa",
                  s1_remark="B") -> dict:
    """四步骤文件:s0/s1 同端点(ep1,remark 属 carry 面)取值不一致;
    s2 另一端点(ep2,remark 是 **form** 字段);s3 无锚点原始调用。"""
    return {
        "scenarioId": sid,
        "meta": {
            "scenarioId": sid, "name": "Multi", "module": "order",
            "priority": 1, "system": ["fin"], "plate": {"fin": "1.0#1"},
        },
        "steps": [
            {"kind": "step", "endpoint": "fin.ep1",
             "call": {"service": svc, "headers": {}},
             "request": {"kind": "request", "body": {
                 "remark": "A", "other": "keep"}}},
            {"kind": "step", "endpoint": "fin.ep1",
             "call": {"service": svc, "headers": {}},
             "request": {"kind": "request", "body": {"remark": s1_remark}}},
            {"kind": "step", "endpoint": "fin.ep2",
             "call": {"service": svc, "headers": {}},
             "request": {"kind": "request", "body": {
                 "remark": "ep2-business"}}},
            {"kind": "step",
             "call": {"service": svc, "method": "POST", "path": "/raw"},
             "request": {"kind": "request", "body": {
                 "remark": "raw-step"}}},
        ],
        "config": {"services": {svc: "https://src"}},
    }


def _multi_faces(pm: PlateMock) -> None:
    pm.behaviour = "echo"
    pm.services = [{"name": "fin-service"}]
    pm.fulls = {
        "fin.ep1": {"request": {"declarations": [
            {"path": "$.remark", "state": "carry", "type": "string"}]}},
        "fin.ep2": {"request": {"declarations": [
            {"path": "$.remark", "state": "form", "type": "string"}]}},
    }


async def _remarks(sid: str) -> list:
    """落库后各步骤 body 的 remark 观测(None = 键不存在)。"""
    defn = await _stored_definition(sid)
    out = []
    for st in defn.get("steps") or []:
        body = (st.get("request") or {}).get("body") or {}
        out.append(body.get("remark", "<保留:键不存在>"))
    return out


async def test_inconsistent_values_never_taken_over__create(
        client, plate_mock: PlateMock):
    """取值不一致(A/B):create 也不接管 —— 四步骤 remark 全部原样,
    新别名零 carry 条目;预检把该路径列进 inconsistentPaths。"""
    _multi_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": _multi_bundle()})
    by_key = {s["serviceKey"]: s for s in r.json()["services"]}
    qa = by_key["fin-service-qa"]
    assert qa["suggestion"] == "create"
    assert qa["fieldsToAlias"] == 0
    assert qa["inconsistentPaths"] == ["$.remark"]

    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _multi_bundle(),
        "mappings": [{"serviceKey": "fin-service-qa",
                      "decision": "create"}]})
    assert r.status_code == 201, r.text
    assert await _remarks("sc-imp-multi") == ["A", "B", "ep2-business",
                                              "raw-step"]
    async with db_module.SessionLocal() as db:
        binds = await carry_store.get_bindings(db, "fin-service-qa")
        assert binds == {}


async def test_inconsistent_values_never_taken_over__map_and_reuse(
        client, plate_mock: PlateMock):
    """map/reuse 同守:本机有值的别名不统一覆盖取值不一致的各步骤
    (旧缺陷:map 会把各步统一改写成 carry 值)。"""
    _multi_faces(plate_mock)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service",
            {"$.remark": "A"},
            updated_by_id=None, updated_by_name="seed")
        await db.commit()
    bob = await register_and_login(client, "admin0", "admin0pass123")
    for decision in ("map", "reuse"):
        sid = f"sc-imp-m-{decision}"
        bundle = _multi_bundle(sid, svc="fin-service")
        r = await client.post("/api/scenarios/import", headers=bob, json={
            "bundle": bundle,
            "mappings": [{"serviceKey": "fin-service",
                          "decision": decision}]})
        assert r.status_code == 201, (decision, r.text)
        assert await _remarks(sid) == ["A", "B", "ep2-business",
                                       "raw-step"], decision


async def test_template_literal_mix_kept(client, plate_mock: PlateMock):
    """模板与字面值混用:不进接管集,模板与字面值都原样保留。"""
    _multi_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    bundle = _multi_bundle(s1_remark="${vars.t}")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": bundle})
    qa = {s["serviceKey"]: s for s in r.json()["services"]}["fin-service-qa"]
    assert qa["inconsistentPaths"] == ["$.remark"]
    assert qa["fieldsToAlias"] == 0

    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": bundle,
        "mappings": [{"serviceKey": "fin-service-qa",
                      "decision": "create"}]})
    assert r.status_code == 201, r.text
    assert await _remarks("sc-imp-multi") == ["A", "${vars.t}",
                                              "ep2-business", "raw-step"]


async def test_consistent_values_cleared_only_from_own_carry_face(
        client, plate_mock: PlateMock):
    """正控:各步取值一致(A/A)才接管,且只清 carry 面上该清的步骤
    —— ep2 的 form remark 与无锚点步骤的 remark 不在面内,永不清。"""
    _multi_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    bundle = _multi_bundle(s1_remark="A")
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": bundle,
        "mappings": [{"serviceKey": "fin-service-qa",
                      "decision": "create"}]})
    assert r.status_code == 201, r.text
    assert await _remarks("sc-imp-multi") == [
        "<保留:键不存在>", "<保留:键不存在>", "ep2-business", "raw-step"]
    # 非 face 字段不受牵连;carry 写的是一致值
    defn = await _stored_definition("sc-imp-multi")
    assert defn["steps"][0]["request"]["body"] == {"other": "keep"}
    async with db_module.SessionLocal() as db:
        binds = await carry_store.get_bindings(db, "fin-service-qa")
        assert binds == {"$.remark": "A"}


async def test_consistent_values_reuse_and_map(client, plate_mock: PlateMock):
    """一致值 × reuse/map:接管集按决策过滤,清除同样只落在锚点步骤。"""
    _multi_faces(plate_mock)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "A"},
            updated_by_id=None, updated_by_name="seed")
        await db.commit()
    bob = await register_and_login(client, "admin0", "admin0pass123")
    for decision in ("map", "reuse"):
        sid = f"sc-imp-c-{decision}"
        r = await client.post("/api/scenarios/import", headers=bob, json={
            "bundle": _multi_bundle(sid, svc="fin-service", s1_remark="A"),
            "mappings": [{"serviceKey": "fin-service",
                          "decision": decision}]})
        assert r.status_code == 201, (decision, r.text)
        assert await _remarks(sid) == [
            "<保留:键不存在>", "<保留:键不存在>",
            "ep2-business", "raw-step"], decision


async def test_precheck_inconsistent_listed_for_ui(client, plate_mock: PlateMock):
    """预检/落库共用同一计算:确认界面看到的 inconsistentPaths 就是
    落库保留的(取值摘要一并给出)。"""
    _multi_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import/precheck", headers=bob,
                          json={"bundle": _multi_bundle()})
    qa = {s["serviceKey"]: s for s in r.json()["services"]}["fin-service-qa"]
    assert qa["inconsistentPaths"] == ["$.remark"]
    assert qa["fieldsKeptLiteral"] == 1   # remark(不一致)
    assert qa["sensitivePaths"] == []


# ── 体积门(服务函数直测,N3:解析前拒绝)─────────────────────────


class _FakeRequest:
    """体积门桩:headers + chunk 列表(stream() 逐块产出,记录已消费
    块数以断言「超限即中止」);body() 兼容旧的整读路径。"""

    def __init__(self, headers: dict, body: bytes, chunk_size: int = 1024):
        self.headers, self._body = headers, body
        self.chunks = [body[i:i + chunk_size]
                       for i in range(0, len(body), chunk_size)] or [b""]
        self.consumed = 0

    async def stream(self):
        for c in self.chunks:
            self.consumed += 1
            yield c

    async def body(self) -> bytes:
        return self._body


async def test_read_bundle_size_gate():
    req = _FakeRequest({"content-length": str(6 * 1024 * 1024)}, b"x")
    try:
        await scenario_import.read_bundle(req)
        raise AssertionError("expected payload_too_large")
    except scenario_import.ImportRejected as e:
        assert (e.code, e.http) == ("payload_too_large", 413)
    # 无 content-length 头时按流式累计复核(超限即弃读中止)
    req2 = _FakeRequest({}, b"x" * (7 * 1024 * 1024), chunk_size=1024 * 1024)
    try:
        await scenario_import.read_bundle(req2)
        raise AssertionError("expected payload_too_large")
    except scenario_import.ImportRejected as e:
        assert e.code == "payload_too_large"
    assert req2.consumed < len(req2.chunks)   # 第 6 块越限后不再读(共 7 块)


async def test_read_bundle_small_stream_ok():
    req = _FakeRequest({}, b'{"bundle": 1}')
    assert await scenario_import.read_bundle(req) == {"bundle": 1}
    assert req.consumed == len(req.chunks)


# ── 落库竞态与复验(合入评估 §3)────────────────────────────────────


async def test_land_alias_name_race_409(client, plate_mock: PlateMock):
    """§3-1:别名主键冲突(同请求内两服务同名双建 / 预检后被人抢注)
    → 409 alias_name_taken(前端自愈链已挂该 code),事务回滚零残留。"""
    _mock_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    # land 对 alias_names 快照的占用检查挡不住「同一请求内」的两条同名
    # create 映射:首插未提交即撞主键,IntegrityError 须映射 409 而非 500
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(),
        "mappings": [
            {"serviceKey": "fin-service-qa", "decision": "create",
             "createName": "fin-service-qa"},
            {"serviceKey": "fin-service", "decision": "create",
             "createName": "fin-service-qa"},
        ]})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "alias_name_taken"
    # 整体回滚:场景无残留、首插的别名也随回滚消失
    async with db_module.SessionLocal() as db:
        assert (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == _SCENARIO_ID))
        ).scalar_one_or_none() is None
        assert (await db.execute(select(ServiceAlias).where(
            ServiceAlias.alias_name == "fin-service-qa"))
        ).scalar_one_or_none() is None


async def test_land_rechecks_rewritten_definition(client, plate_mock: PlateMock,
                                                  monkeypatch):
    """§3-3:改写后的 definition 落库前再 convert 复验 —— 第二次 convert
    被拒 → 422 convert_rejected,零落库。"""
    _mock_faces(plate_mock)
    bob = await register_and_login(client, "admin0", "admin0pass123")
    calls = {"n": 0}
    real_convert = scenario_import.plate_client.convert

    async def _convert(definition, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:   # 复验那次:改写后的形态
            raise scenario_import.plate_client.PlateRejectedError(
                code="invalid_action", message="rewritten shape rejected")
        return await real_convert(definition, *a, **kw)

    monkeypatch.setattr(scenario_import.plate_client, "convert", _convert)
    r = await client.post("/api/scenarios/import", headers=bob, json={
        "bundle": _bundle(), "mappings": []})
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "convert_rejected"
    assert "接管改写后校验失败" in r.json()["detail"]["message"]
    assert calls["n"] == 2   # 原文件一次 + 改写后复验一次
    async with db_module.SessionLocal() as db:
        assert (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == _SCENARIO_ID))
        ).scalar_one_or_none() is None
