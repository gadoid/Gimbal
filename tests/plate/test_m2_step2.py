"""M2 步骤 2 验收（M2 方案 v2.4 §4/§9；开发计划 T1.3）。

覆盖：导出规则 E1–E7、gen/check 漂移守卫、compat 不兼容守卫、M2 信封
入构件池、框架 dim HTTP 面、语料迁移函数、生成物可用性。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.export.m2_schema import export_m2


class TestExportRules:
    def test_e1_defaults(self) -> None:
        e = export_m2()
        meta = e.schema["$defs"]["Meta"]["properties"]
        assert meta["tags"]["default"] == []
        assert meta["plate"]["default"] == {}

    def test_e2_closedness(self) -> None:
        e = export_m2()
        defs = e.schema["$defs"]
        assert defs["Step"]["additionalProperties"] is False
        assert defs["Call"]["additionalProperties"] is True   # 唯一开放

    def test_e3_varnames(self) -> None:
        e = export_m2()
        scope = e.schema["$defs"]["Scope"]
        assert scope["x-enum-varnames"][:2] == ["FRAMEWORK", "SUITE"]

    def test_e6_hash_stable(self) -> None:
        a, b = export_m2(), export_m2()
        assert a.m2_hash == b.m2_hash and len(a.m2_hash) == 64
        assert "title" not in {k for k in a.schema if k != "$defs"}

    def test_e7_literal_fields(self) -> None:
        e = export_m2()
        for name in ("mode", "op", "metric", "bracket"):
            assert name in e.literal_fields, name


class TestGenCheck:
    def test_gen_then_check_then_drift(self, tmp_path, monkeypatch) -> None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "gen_m2_t", Path(__file__).resolve().parents[2]
            / "scripts" / "gen_m2.py")
        gm = importlib.util.module_from_spec(spec)
        sys.modules["gen_m2_t"] = gm
        spec.loader.exec_module(gm)
        monkeypatch.setattr(gm, "SCHEMA_JSON", tmp_path / "m2.schema.json")
        monkeypatch.setattr(gm, "EXECUTOR_M2", tmp_path / "exec_m2.py")
        monkeypatch.setattr(gm, "PLATFORM_M2", tmp_path / "plat_m2.py")
        assert gm.main(["gen", "--targets", "schema,py"]) == 0
        schema = json.loads((tmp_path / "m2.schema.json").read_text("utf-8"))
        assert "$defs" in schema
        for name in ("exec_m2.py", "plat_m2.py"):
            text = (tmp_path / name).read_text(encoding="utf-8")
            assert "禁止手改" in text and "m2_hash" in text
            assert "RunUnion" in text                     # G7
        # 漂移守卫：改一字节 → check 非零；恢复 → 通过
        target = tmp_path / "exec_m2.py"
        raw = target.read_bytes()
        target.write_bytes(raw + b"\n# drift\n")
        assert gm.main(["check", "--targets", "schema,py"]) == 1
        target.write_bytes(raw)
        assert gm.main(["check", "--targets", "schema,py"]) == 0

    def test_envelope_written_to_pool(self, tmp_path, monkeypatch) -> None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "gen_m2_e", Path(__file__).resolve().parents[2]
            / "scripts" / "gen_m2.py")
        gm = importlib.util.module_from_spec(spec)
        sys.modules["gen_m2_e"] = gm
        spec.loader.exec_module(gm)
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(tmp_path))
        assert gm.main(["gen", "--targets", "envelope"]) == 0
        e = export_m2()
        env_path = tmp_path / "objects" / f"{e.m2_hash}.json"
        assert env_path.is_file()
        envelope = json.loads(env_path.read_text(encoding="utf-8"))
        assert envelope["type"] == "m2" and envelope["data"] == e.schema


class TestCompat:
    def test_find_incompatibilities(self) -> None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "gen_m2_c", Path(__file__).resolve().parents[2]
            / "scripts" / "gen_m2.py")
        gm = importlib.util.module_from_spec(spec)
        sys.modules["gen_m2_c"] = gm
        spec.loader.exec_module(gm)
        base = {"$defs": {"Meta": {
            "properties": {"name": {"type": "string"},
                           "gone": {"type": "string"},
                           "priority": {"type": "integer"}},
            "required": ["name"]}}}
        cur = {"$defs": {"Meta": {
            "properties": {"name": {"type": "string"},
                           "priority": {"type": "number"}},
            "required": ["name", "priority"]}}}
        problems = gm._find_incompatibilities(base, cur)
        assert any("gone" in p and "删除" in p for p in problems)
        assert any("priority" in p and "必填" in p for p in problems)
        assert any("priority" in p and "类型" in p for p in problems)
        # 加法兼容：新增字段/新枚举值/新 $defs 不报
        ok = gm._find_incompatibilities(
            base, {"$defs": {"Meta": dict(base["$defs"]["Meta"],
                                          properties=dict(
                                              base["$defs"]["Meta"]["properties"],
                                              extra={"type": "string"})),
                              "New": {"properties": {}}}})
        assert ok == []


class TestFrameworkDim:
    def test_m2_and_ext_routes(self, http_client, monkeypatch,
                               tmp_path) -> None:
        r = http_client.get("/api/m2")
        assert r.status_code == 200
        data = r.json()["data"]
        h = data["m2_hash"]
        assert data["m2_generation"] == 2 and len(h) == 64   # gen2:Call.auth(Y1)
        # 当前 hash 直取；缺 hash → 404 m2_not_found（构件根指空目录）
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(tmp_path))
        assert http_client.get(f"/api/m2/{h}").status_code == 200
        miss = http_client.get("/api/m2/" + "0" * 64)
        assert miss.status_code == 404
        assert miss.json()["error"]["code"] == "m2_not_found"
        ext = http_client.get("/api/ext")
        assert ext.status_code == 200 and isinstance(ext.json()["data"], list)

    def test_generated_runtime_module_validates(self) -> None:
        import gimbal.schema._m2 as m2
        s = m2.Scenario.model_validate({
            "kind": "scenario", "scenarioId": "sc-m2",
            "meta": {"name": "n", "plate": {"fin": "1.0#1"}},
            "config": {}, "resource": {},
            "steps": [{"endpoint": "fin.a.a", "call": {"protocol": "http"},
                       "strategy": [{"kind": "extract",
                                     "expression": "$.a", "target": "t"}]}],
        })
        assert s.meta.plate == {"fin": "1.0#1"}
        assert s.steps[0].endpoint == "fin.a.a"
        assert m2.Scope("scenario").name == "SCENARIO"


class TestMigrate:
    def test_legacy_shapes_migrated(self) -> None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "gen_m2_m", Path(__file__).resolve().parents[2]
            / "scripts" / "gen_m2.py")
        gm = importlib.util.module_from_spec(spec)
        sys.modules["gen_m2_m"] = gm
        spec.loader.exec_module(gm)
        migrated = gm.migrate_definition({
            "meta": {"name": "n", "scenarioId": "x", "updateTime": 1},
            "steps": [{
                "id": "s0", "field_states": {"a": "t"},
                "api": {"kind": "api", "path": "/x",
                        "view_hints": {"endpoint_id": "fin.a.a"}},
                "strategy": []}],
        })
        step = migrated["steps"][0]
        assert step["call"] == {"kind": "call", "path": "/x",
                                "protocol": "http"}
        assert step["endpoint"] == "fin.a.a"
        assert "id" not in step and "field_states" not in step
        assert "scenarioId" not in migrated["meta"]
