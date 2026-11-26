"""评审二轮回归(资产包面):P1-1 导出脱敏 / P1-6 默认权威 /
P2-10 规范化先行 / P2-11 稳定幂等键 / P2-12 嵌套形状边界。

布景单源复用 test_upc_m2_domain(TestAssetBundleRoundtrip._seed_source
等),独立成文件避免单一模块过长。"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import default_space_id, register_and_login
from tests.test_upc_m2_domain import (  # noqa: F401  布景单源
    _mk_scheme, _uid,
)

# 复用 M2 模块的源场景布景(场景 sc-m2x + 数据集 + 默认/回归方案 + 组合)
from tests.test_upc_m2_domain import (  # noqa: F401
    TestAssetBundleRoundtrip as _SeedHost,
)


async def _seed_source(client: AsyncClient, tag: str):
    return await _SeedHost._seed_source(None, client, tag)  # type: ignore[arg-type]


async def _uid_b(client: AsyncClient, tag: str):
    h_b = await register_and_login(client, f"m2z_{tag}_b", "pw123456")
    return h_b, await _uid(client, f"m2z_{tag}_b")


async def _restore(client, h_b, uid_b, bundle):
    from app.core import db as db_module

    async with db_module.SessionLocal() as s:
        space_b = await default_space_id(s, uid_b)
        await s.commit()
    r = await client.post(f"/api/projects/{space_b}/asset-bundles",
                          headers=h_b, json=bundle)
    return r, space_b


class TestExportRedaction:
    """P1-1:导出传入调用者身份,非属主数据集行经脱敏单源剥敏感列。"""

    async def test_foreign_viewer_export_redacts_sensitive_columns(
            self, client: AsyncClient):
        from tests.helpers import make_draft, mk_normal_project

        h_own = await register_and_login(client, "m2x_rd_own", "pw123456")
        h_mem = await register_and_login(client, "m2x_rd_mem", "pw123456")
        pid = await mk_normal_project("m2x-red-proj", {
            "m2x_rd_own": "admin", "m2x_rd_mem": "member"})
        draft = make_draft("sc-m2red")
        # 敏感列同样须声明为变量(数据集列 ⊆ 标量声明变量的契约面)
        draft["definition"]["config"]["vars"] = {
            "user": 1, "org": 1, "password": ""}
        await client.post(f"/api/scenarios?projectId={pid}",
                          headers=h_own, json=draft)
        r = await client.post("/api/scenarios/sc-m2red/data-sets",
                              headers=h_own,
                              json={"name": "数据R", "rows": [
                                  {"user": "alice", "password": "s3cret",
                                   "org": "A"}]})
        assert r.status_code in (200, 201), r.text

        # 属主导出:敏感列原样
        r = await client.get("/api/scenarios/sc-m2red/asset-bundle",
                             headers=h_own)
        assert r.status_code == 200, r.text
        rows_own = r.json()["datasets"][0]["rows"]
        assert rows_own[0]["password"] == "s3cret"

        # 项目成员(非属主)导出:敏感列剥除,非敏感列保留
        r = await client.get("/api/scenarios/sc-m2red/asset-bundle",
                             headers=h_mem)
        assert r.status_code == 200, r.text
        rows_mem = r.json()["datasets"][0]["rows"]
        assert "password" not in rows_mem[0]
        assert rows_mem[0]["user"] == "alice"
        assert rows_mem[0]["org"] == "A"


class TestDefaultSchemeAuthority:
    """P1-6:defaultSchemeId 是唯一权威;包内默认标记冲突 422;
    报告与库内默认一致。"""

    async def test_conflict_and_authority(self, client: AsyncClient):
        h, _space, _combo, _ds, _qa = await _seed_source(client, "da")
        # 无选择的中立方案权威候选(回归方案带行选择,不可为默认)
        third_id = await _mk_scheme(client, h, "sc-m2x", "中立方案")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        h_b, uid_b = await _uid_b(client, "da")

        # 冲突腿:中立方案自带默认标记,defaultSchemeId 仍指原默认
        conflicting = dict(bundle)
        conflicting["schemes"] = [
            dict(s, isDefault=True) if s["schemeId"] == third_id else s
            for s in bundle["schemes"]]
        r, _sp = await _restore(client, h_b, uid_b, conflicting)
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "asset_bundle_default_conflict"

        # 权威腿:defaultSchemeId 改指中立方案(标记同步)→ 库内唯一
        # 默认 = 报告所指
        switched = dict(bundle)
        switched["defaultSchemeId"] = third_id
        switched["schemes"] = [
            dict(s, isDefault=(s["schemeId"] == third_id))
            for s in bundle["schemes"]]
        r, _sp = await _restore(client, h_b, uid_b, switched)
        assert r.status_code == 201, r.text
        report = r.json()
        sid = report["scenarioId"]
        assert report["defaultSchemeId"] is not None
        from sqlalchemy import select

        from app.core import db as db_module
        from app.models.composer_run_scheme import ComposerRunScheme

        async with db_module.SessionLocal() as s:
            rows = (await s.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == sid))).scalars().all()
            defaults = [x for x in rows if x.is_default]
            assert len(defaults) == 1
            assert defaults[0].scheme_id == report["defaultSchemeId"]
            assert defaults[0].name == "中立方案"


class TestNormalizeBeforeValidate:
    """P2-10:旧式 dataSetIds 先规范化再校验,默认候选不可绕过。"""

    async def test_legacy_dataset_ids_default_candidate_rejected(
            self, client: AsyncClient):
        h, _space, _combo, _ds, _qa = await _seed_source(client, "lg")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        tampered = dict(bundle)
        tampered["schemes"] = [
            dict(s, payload={"dataSetIds": ["ds-legacy"]})
            if s["schemeId"] == bundle["defaultSchemeId"] else s
            for s in bundle["schemes"]]
        h_b, uid_b = await _uid_b(client, "lg")
        r, _sp = await _restore(client, h_b, uid_b, tampered)
        assert r.status_code == 422, r.text
        assert (r.json()["detail"]["code"]
                == "asset_bundle_default_invalid")


class TestStableIdempotencyKey:
    """P2-11:缺省 packageId 由源场景 × 摘要派生稳定幂等键。"""

    async def test_missing_package_id_retries_converge(
            self, client: AsyncClient):
        from sqlalchemy import func, select

        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario
        from app.models.scenario_asset_import import ScenarioAssetImport

        h, _space, _combo, _ds, _qa = await _seed_source(client, "pk")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        bundle.pop("packageId", None)
        h_b, uid_b = await _uid_b(client, "pk")

        r1, space_b = await _restore(client, h_b, uid_b, bundle)
        assert r1.status_code == 201, r1.text
        sid1 = r1.json()["scenarioId"]
        r2, _sp = await _restore(client, h_b, uid_b, bundle)
        assert r2.status_code == 200, r2.text
        assert r2.json()["replayed"] is True
        assert r2.json()["scenarioId"] == sid1

        async with db_module.SessionLocal() as s:
            n_scen = (await s.execute(select(func.count()).select_from(
                ComposerScenario).where(
                ComposerScenario.project_id == space_b))).scalar_one()
            n_ledger = (await s.execute(select(func.count()).select_from(
                ScenarioAssetImport).where(
                ScenarioAssetImport.project_id == space_b))).scalar_one()
            assert n_scen == 1 and n_ledger == 1


class TestBundleShapeBoundary:
    """P2-12:嵌套形状错误统一 422(不再 500)。"""

    async def test_nested_shape_errors_are_422(self, client: AsyncClient):
        h, _space, _combo, _ds, _qa = await _seed_source(client, "sh")
        bundle = (await client.get(
            "/api/scenarios/sc-m2x/asset-bundle", headers=h)).json()
        h_b, uid_b = await _uid_b(client, "sh")

        def tampered(mut):
            b = dict(bundle)
            mut(b)
            return b

        cases = [
            ("scheme payload 非对象",
             lambda b: b["schemes"][0].__setitem__("payload", "nope")),
            ("comboDependencies 非映射",
             lambda b: b.__setitem__("comboDependencies", {"rs": "oops"})),
            ("comboIdMappings 值非正整数",
             lambda b: b.__setitem__("comboIdMappings", {"rs": "abc"})),
            ("datasets 元素非对象",
             lambda b: b.__setitem__("datasets", ["x"])),
            ("source 缺失",
             lambda b: b.__setitem__("source", None)),
            ("defaultSchemeId 非字符串",
             lambda b: b.__setitem__("defaultSchemeId", 7)),
        ]
        for name, mut in cases:
            r, _sp = await _restore(client, h_b, uid_b, tampered(mut))
            assert r.status_code == 422, f"{name}: {r.text}"
            assert r.json()["detail"]["code"] in (
                "asset_bundle_shape_invalid",
                "asset_bundle_source_missing",
                "asset_bundle_default_missing",
            ), f"{name}: {r.json()['detail']['code']}"
