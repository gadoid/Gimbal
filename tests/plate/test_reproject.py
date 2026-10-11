"""RS2：call 按修订重投影（Release v4.4 §4.5；开发计划 T1.8）。

覆盖 RS2 验收门：同一场景改 `meta.plate` 后 convert 得到对应修订的 path；
存储中出现 binding 派生字段报错；追加 header 与 binding 同名报错；系统
未声明 / 修订不存在 / 接口不在修订中的错误码。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gimbal_plate.release import read as rr
from gimbal_plate.release.release import release_system
from gimbal_plate.release.reproject import (
    ReprojectError,
    _merge_call,
    reproject_raw,
)

from tests.plate._release_fx import commit, make_repo, write_endpoint


def _scenario(call: dict, plate: dict | None = None,
              endpoint: str | None = "fin.a.a") -> dict:
    meta: dict = {
        "name": "rs2", "description": "d", "module": "m", "priority": 1,
        "author": "t", "owner": "t", "tags": [], "version": "1",
        "createTime": "2026-10-10T00:00:00", "expire": False,
        "requirementRef": [], "system": ["fin"],
    }
    if plate is not None:
        meta["plate"] = plate
    return {
        "kind": "scenario", "scenarioId": "sc-rs2",
        "meta": meta,
        "config": {"users": {}, "setup": [], "teardown": [], "services": {},
                   "timePolicy": {"kind": "record"}, "retry": None, "vars": {}},
        "resource": {},
        "steps": [{"kind": "step", "description": "s", "call": call,
                   "request": {"kind": "request", "body": {}},
                   "strategy": [],
                   **({"endpoint": endpoint} if endpoint else {})}],
    }


# M3 定稿:锚点在 step.endpoint(不在 call 里);call 只存场景自有字段
OWN_CALL = {
    "kind": "call",
    "service": "fin-service",
    "user": "tester_a",
    "path_params": {"uid": "u1"},
    "headers": {"X-Extra": "1"},
}


def _released_repo(tmp_path: Path):
    repo, fin, art = make_repo(tmp_path)
    assert release_system(fin, artifacts_root=art, signed_by="t").success
    return repo, fin, art


class TestMergeRules:
    def test_merge_binding_from_projection_own_from_storage(self) -> None:
        proj = {"protocol": "http", "service": "fin-service",
                "timeout": 30.0, "method": "GET", "path": "/a",
                "headers": {"X-B": "b"}}
        out = _merge_call(dict(OWN_CALL), proj, "fin.a.a")
        assert out["method"] == "GET" and out["path"] == "/a"   # 派生取投影
        assert out["service"] == "fin-service" and out["user"] == "tester_a"
        assert out["path_params"] == {"uid": "u1"}
        assert out["headers"] == {"X-B": "b", "X-Extra": "1"}   # 追加并入
        assert "view_hints" not in out and "kind" not in out

    def test_binding_field_in_storage_rejected(self) -> None:
        with pytest.raises(ReprojectError) as ei:
            _merge_call({**OWN_CALL, "method": "GET"}, {}, "fin.a.a")
        assert ei.value.code == "binding_field_in_storage"

    def test_header_conflict_rejected(self) -> None:
        with pytest.raises(ReprojectError) as ei:
            _merge_call(dict(OWN_CALL),
                        {"headers": {"X-Extra": "b"}}, "fin.a.a")
        assert ei.value.code == "header_conflicts_binding"


class TestReprojectRaw:
    def test_revision_reproject_and_used_refs(self, tmp_path: Path) -> None:
        repo, fin, art = _released_repo(tmp_path)
        raw, used = reproject_raw(_scenario(dict(OWN_CALL),
                                            plate={"fin": "1.0#1"}),
                                  {"fin": "1.0#1"}, root=art)
        assert used == {"fin": "1.0#1"}
        call = raw["steps"][0]["call"]
        assert call["path"] == "/a" and call["method"] == "GET"
        assert call["service"] == "fin-service"

    def test_revision_change_changes_path(self, tmp_path: Path) -> None:
        """RS2 门:同一场景改 meta.plate 后 convert 得到对应修订的 path。"""
        repo, fin, art = _released_repo(tmp_path)
        write_endpoint(fin, "a", reviewed=True, path="/a2")
        commit(repo, "change path")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        raw, used = reproject_raw(_scenario(dict(OWN_CALL),
                                            plate={"fin": "1.0#2"}),
                                  {"fin": "1.0#2"}, root=art)
        assert raw["steps"][0]["call"]["path"] == "/a2"
        assert used == {"fin": "1.0#2"}

    def test_version_undeclared(self, tmp_path: Path) -> None:
        _, _, art = _released_repo(tmp_path)
        with pytest.raises(ReprojectError) as ei:
            reproject_raw(_scenario(dict(OWN_CALL)), {}, root=art)
        assert ei.value.code == "version_undeclared"

    def test_release_not_found(self, tmp_path: Path) -> None:
        _, _, art = _released_repo(tmp_path)
        with pytest.raises(rr.ReleaseReadError) as ei:
            reproject_raw(_scenario(dict(OWN_CALL)),
                          {"fin": "9.9#9"}, root=art)
        assert ei.value.code == "release_not_found"

    def test_endpoint_not_in_release(self, tmp_path: Path) -> None:
        _, _, art = _released_repo(tmp_path)
        with pytest.raises(ReprojectError) as ei:
            reproject_raw(_scenario(dict(OWN_CALL), endpoint="fin.a.zz"),
                          {"fin": "1.0#1"}, root=art)
        assert ei.value.code == "endpoint_not_in_release"

    def test_working_declaration_uses_working_tree(self, tmp_path: Path) -> None:
        from gimbal_plate.loader import load_registry

        repo, fin, art = _released_repo(tmp_path)
        reg = load_registry([repo / "systems"])
        raw, used = reproject_raw(
            _scenario(dict(OWN_CALL), plate={"fin": "working"}),
            {"fin": "working"}, root=art, working_registry=reg)
        assert used == {"fin": "working"}
        assert raw["steps"][0]["call"]["path"] == "/a"   # 当前树


class TestHTTPConvert:
    def test_convert_with_meta_plate(self, tmp_path: Path, http_client,
                                     monkeypatch) -> None:
        repo, fin, art = _released_repo(tmp_path)
        write_endpoint(fin, "a", reviewed=True, path="/a2")
        commit(repo, "change path")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))

        r = http_client.post("/api/scenario/action/convert", json={
            "consumer": "gimbal",
            "scenario": _scenario(dict(OWN_CALL), plate={"fin": "1.0#2"}),
        })
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["used"] == {"fin": "1.0#2"}
        converted_call = data["converted"]["steps"][0]["call"]
        assert converted_call["path"] == "/a2"

    def test_convert_error_codes(self, tmp_path: Path, http_client,
                                 monkeypatch) -> None:
        _, _, art = _released_repo(tmp_path)
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))
        # 接口不在修订 → 422 endpoint_not_in_release
        r = http_client.post("/api/scenario/action/convert", json={
            "consumer": "gimbal",
            "scenario": _scenario(
                dict(OWN_CALL), endpoint="fin.a.zz",
                plate={"fin": "1.0#1"}),
        })
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "endpoint_not_in_release"
        # 存储含派生字段 → 422 binding_field_in_storage
        r = http_client.post("/api/scenario/action/convert", json={
            "consumer": "gimbal",
            "scenario": _scenario({**OWN_CALL, "method": "GET"},
                                  plate={"fin": "1.0#1"}),
        })
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "binding_field_in_storage"
