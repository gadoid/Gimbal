"""data_sets 面(authz W3 空白模块补齐,dev-plan W3 测试项)。

此前散在 test_scenario_composer_api 的所有权负例只覆盖普通用户;
本文件钉 W3 收窄后的矩阵:
* 本人 CRUD 正常;
* admin/super_admin 列表 = 自己场景的 + 引用的(:92 全量分支已删,
  他人数据集不可见 —— 跨用户披露面收口);
* 他人私有场景的数据集读/写/删一律 404(不泄露);
* 场景公开后数据集随场景可读(读随父场景可见性),写仍属主单判。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def _mk_scenario_with_ds(client: AsyncClient, h, sid: str) -> str:
    draft = make_draft(sid, vars_map={"amount": 100})
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post(
        f"/api/scenarios/{sid}/data-sets", headers=h,
        json={"name": "ds", "rows": [{"amount": 1}, {"amount": 2}]},
    )
    assert r.status_code == 201, r.text
    return r.json()["datasetId"]


class TestOwnerCrud:
    async def test_owner_full_cycle(self, client: AsyncClient):
        h = await role_headers(client, "ds_own")
        ds_id = await _mk_scenario_with_ds(client, h, "sc-ds-1")
        rows = (await client.get("/api/data-sets", headers=h)).json()
        assert [d["datasetId"] for d in rows] == [ds_id]
        assert rows[0]["rowCount"] == 2
        assert (await client.get(
            f"/api/data-sets/{ds_id}", headers=h)).status_code == 200
        r = await client.put(
            f"/api/data-sets/{ds_id}", headers=h,
            json={"name": "ds", "rows": [{"amount": 9}]})
        assert r.status_code == 200 and r.json()["rowCount"] == 1
        assert (await client.delete(
            f"/api/data-sets/{ds_id}", headers=h)).status_code == 204


class TestAdminNarrowed:
    async def test_admin_list_excludes_others(self, client: AsyncClient):
        """:92 分支翻转:super_admin 曾全量直返,现在与普通用户同镜头。"""
        h_owner = await role_headers(client, "ds_aown")
        await _mk_scenario_with_ds(client, h_owner, "sc-ds-a")
        for role in ("admin", "super_admin"):
            h = await role_headers(client, f"ds_{role}", role=role)
            assert (await client.get(
                "/api/data-sets", headers=h)).json() == [], role
            assert (await client.get(
                "/api/data-sets?scenarioId=sc-ds-a",
                headers=h)).json() == [], role

    async def test_admin_cannot_read_or_write_others_private_dataset(
            self, client: AsyncClient):
        h_owner = await role_headers(client, "ds_pown")
        ds_id = await _mk_scenario_with_ds(client, h_owner, "sc-ds-p")
        h = await role_headers(client, "ds_psup", role="super_admin")
        assert (await client.get(
            f"/api/data-sets/{ds_id}", headers=h)).status_code == 404
        assert (await client.put(
            f"/api/data-sets/{ds_id}", headers=h,
            json={"name": "ds", "rows": []})).status_code == 404
        assert (await client.delete(
            f"/api/data-sets/{ds_id}", headers=h)).status_code == 404
        # 直建到他人私有场景 → 404
        assert (await client.post(
            "/api/scenarios/sc-ds-p/data-sets", headers=h,
            json={"name": "x", "rows": []})).status_code == 404


class TestPublicScenarioReadThrough:
    async def test_public_scenario_dataset_readable_but_not_writable(
            self, client: AsyncClient):
        """读随父场景可见性(公开 ⇒ 数据集可读);写仍属主单判。"""
        h_owner = await role_headers(client, "ds_uown")
        ds_id = await _mk_scenario_with_ds(client, h_owner, "sc-ds-u")
        assert (await client.post(
            "/api/scenarios/sc-ds-u/publish", headers=h_owner)).status_code == 200

        h_other = await role_headers(client, "ds_uoth", role="user")
        r = await client.get(f"/api/data-sets/{ds_id}", headers=h_other)
        assert r.status_code == 200, r.text
        # 列表是「自有 ∨ 引用闭包」镜头(§7.4),公共父场景不进闭包:
        # 单读可及、列表不铺开 —— 现状口径,钉住防漂移
        listed = (await client.get(
            "/api/data-sets?scenarioId=sc-ds-u", headers=h_other)).json()
        assert listed == []
        # 公开 ≠ 可写:非属主(含 admin)改/删 → 403
        h_admin = await role_headers(client, "ds_uadm", role="admin")
        assert (await client.put(
            f"/api/data-sets/{ds_id}", headers=h_admin,
            json={"name": "ds", "rows": []})).status_code == 403
        assert (await client.delete(
            f"/api/data-sets/{ds_id}", headers=h_admin)).status_code == 403
