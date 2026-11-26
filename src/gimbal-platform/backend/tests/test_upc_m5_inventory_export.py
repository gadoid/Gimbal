"""UPC M5 前置件回归:场景清单导出保护(§5 台账顺序
「先场景清单导出保护,再重建 dev 库」的「先」件)。

* 全保真:属主视角导出 —— 敏感列随包(保护 ≠ 脱敏;§14.2 的脱敏
  谓词对属主不生效);
* 清单完备:计数/归属/摘要 manifest,二次导出摘要确定(对账基准);
* 保护是真的:导出的包经既有 §14.2 恢复 API 圆满回放(重建后全清单
  恢复的可行性证明);
* 对照校验:verify_inventory 抓缺包/摘要漂移;
* 只读:导出不写目标库(服务纪律,测试以二次导出同结果侧面钉)。
"""
from __future__ import annotations

import json

from httpx import AsyncClient

from app.core import db as db_module
from app.services.scenario_inventory import export_inventory, verify_inventory
from tests.helpers import default_space_id, make_draft, mk_normal_project, \
    register_and_login


async def _seed(client: AsyncClient, tag: str):
    """两属主、两场景:私有空间带敏感列数据集 + 普通项目场景。"""
    h_a = await register_and_login(client, f"m5a_{tag}", "pw123456")
    uid_a = (await client.get("/api/auth/me", headers=h_a)).json()["user"]["id"]
    h_b = await register_and_login(client, f"m5b_{tag}", "pw123456")
    uid_b = (await client.get("/api/auth/me", headers=h_b)).json()["user"]["id"]
    pid = await mk_normal_project(f"m5-{tag}-proj", {f"m5a_{tag}": "admin",
                                                     f"m5b_{tag}": "member"})
    # 私有空间场景 + 敏感列数据集 + 回归方案
    draft = make_draft(f"sc-m5{tag}a", vars_map={"user": 1, "org": 1,
                                                 "password": ""})
    r = await client.post("/api/scenarios", headers=h_a, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/api/scenarios/sc-m5{tag}a/data-sets",
                          headers=h_a,
                          json={"name": "敏感", "rows": [
                              {"user": "u1", "password": "s3cret",
                               "org": "A"}]})
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/api/scenarios/sc-m5{tag}a/run-schemes",
                          headers=h_a,
                          json={"name": "回归", "isDefault": False,
                                "dataSetSelection": [], "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {
                                    "step_from": None, "step_to": None,
                                    "n_runs": 1, "parallel": 1,
                                    "subscribe": None}})
    assert r.status_code == 201, r.text
    # 普通项目场景(另一成员建)
    r = await client.post(f"/api/scenarios?projectId={pid}", headers=h_b,
                          json=make_draft(f"sc-m5{tag}b", vars_map={"x": 0}))
    assert r.status_code in (200, 201), r.text
    return uid_a, uid_b, pid


async def test_inventory_export_full_fidelity_and_manifest(
        client: AsyncClient, tmp_path):
    """全保真 + 清单完备 + 确定性:敏感列随包、计数/归属正确、
    二次导出摘要一致(重建对账基准)。"""
    uid_a, uid_b, pid = await _seed(client, "fv")
    out = tmp_path / "inv"
    async with db_module.SessionLocal() as s:
        m1 = await export_inventory(s, out)
        m2 = await export_inventory(s, out)   # 只读:同库两次同结果
    assert m1["scenarioCount"] == m2["scenarioCount"] == 2
    assert m1["exportedCount"] == 2
    assert m1["datasetCount"] == 1 and m1["schemeCount"] >= 3  # 含默认方案钩子
    items = {i["scenarioId"]: i for i in m1["items"]}
    a = items["sc-m5fva"]
    assert a["ownerId"] == uid_a
    assert a["datasetCount"] == 1 and a["exported"]
    b = items["sc-m5fvb"]
    assert b["ownerId"] == uid_b and b["projectId"] == pid \
        and b["projectKind"] == "normal"
    # 全保真:敏感列在包里(属主视角;脱敏谓词对属主不生效)
    bundle = json.loads((out / a["bundleFile"]).read_text(encoding="utf-8"))
    assert bundle["datasets"][0]["rows"][0]["password"] == "s3cret"
    # 确定性:两轮摘要逐场景一致
    assert [i["digest"] for i in m1["items"]] == \
        [i["digest"] for i in m2["items"]]


async def test_inventory_bundle_roundtrip_restorable(
        client: AsyncClient, tmp_path):
    """保护是真的:导出的包经既有 §14.2 恢复 API 在新项目圆满回放
    (重建后全清单恢复的可行性证明)。"""
    uid_a, _uid_b, _pid = await _seed(client, "rt")
    out = tmp_path / "inv"
    async with db_module.SessionLocal() as s:
        manifest = await export_inventory(s, out)
    a = next(i for i in manifest["items"]
             if i["scenarioId"] == "sc-m5rta")
    bundle = json.loads((out / a["bundleFile"]).read_text(encoding="utf-8"))

    h_r = await register_and_login(client, "m5_rt_restorer", "pw123456")
    uid_r = (await client.get("/api/auth/me", headers=h_r)).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        space_r = await default_space_id(s, uid_r)
        await s.commit()
    r = await client.post(f"/api/projects/{space_r}/asset-bundles",
                          headers=h_r, json=bundle)
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["datasets"] >= 1
    assert report["blockedSchemes"] == []
    # 恢复报告对照导出侧计数(恢复报告 = 台账 M5 出口条件之一)
    assert report["datasets"] == a["datasetCount"]


async def test_inventory_verify_catches_tamper_and_missing(
        client: AsyncClient, tmp_path):
    """对照校验:包体篡改/缺失 → verify_inventory 如实报告非 ok;
    原样目录 → ok(恢复后对账面)。"""
    await _seed(client, "vf")
    out = tmp_path / "inv"
    async with db_module.SessionLocal() as s:
        manifest = await export_inventory(s, out)
    report = await verify_inventory(out)
    assert report["ok"] is True, report

    a = next(i for i in manifest["items"]
             if i["scenarioId"] == "sc-m5vfa")
    p = out / a["bundleFile"]
    bundle = json.loads(p.read_text(encoding="utf-8"))
    bundle["datasets"] = []          # 篡改:清数据集
    p.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    report = await verify_inventory(out)
    assert report["ok"] is False
    assert a["scenarioId"] in report["digestMismatch"]

    p.unlink()                       # 缺包
    report = await verify_inventory(out)
    assert a["scenarioId"] in report["missing"]
