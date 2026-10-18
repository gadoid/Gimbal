"""批0 特征化基线(plate 侧)—— B3 / B5(实施计划 v1.1 §2 B 串)。

只钉现状、不改行为:
- B3:`/convert` 对裸线声明(`<line>` 无 ``#``)现状**照收**,重投影 resolve
  到该线最新修订;`resolve_effective` 对裸线拒绝(测试执行路径今天就不收)。
  **预期变更点:b1-6**(声明闸对齐拒,422 missing_revision)—— 届时本文件
  相关断言在同一提交翻转(提交信息注明「基线翻转:b1-6」);
  `resolve_effective` 拒裸线一条**不预期变更**(D-K:missing_revision 是声明
  域政策,parse_ref 裸线保留 line-kind)。
- B5:两种代际常量现值 + 已发版构件回读水合 —— 为批1「不升代际」与
  「存量回读缺省 sut」断言打底。**不预期变更**。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gimbal_plate.http import create_app
from gimbal_plate.loader import load_registry
from gimbal_plate.release import read as release_read
from gimbal_plate.release.release import M2_VERSION, release_system
from tests.plate._release_fx import commit, make_repo, write_endpoint


def _minimal_scenario(endpoint: str, plate: dict[str, str]) -> dict:
    return {
        "kind": "scenario",
        "scenarioId": "sc_b0_b3",
        "meta": {"name": "b0-b3", "system": ["fin"], "plate": plate},
        "config": {},
        "resource": {},
        "steps": [{
            "kind": "step",
            "endpoint": endpoint,
            "call": {"kind": "call", "service": "fin-service"},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }],
    }


class TestB3BareLineDeclaration:
    """裸线声明现状:B3 —— 预期变更点 b1-6(声明闸对齐拒)。"""

    def test_convert_bare_line_resolves_line_latest(self, tmp_path, monkeypatch):
        """裸线 ``"1.0"`` 声明照收,重投影取该线**最新**修订(#2 的 /a2)。"""
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        write_endpoint(fin, "a", reviewed=True, path="/a2")
        commit(repo, "change path -> /a2")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))

        app = create_app(registry=load_registry([repo / "systems"]))
        with TestClient(app) as client:
            resp = client.post(
                "/api/scenario/action/convert",
                json={"consumer": "gimbal",
                      "scenario": _minimal_scenario("fin.a.a", {"fin": "1.0"})},
            )
        # 现状:裸线声明被接受(批1 b1-6 起改为 422 missing_revision)
        assert resp.status_code == 200, resp.text
        step = resp.json()["data"]["converted"]["steps"][0]
        assert step["call"]["path"] == "/a2", "裸线应 resolve 到线最新修订的 binding"

    def test_resolve_effective_rejects_bare_line(self, tmp_path):
        """`resolve_effective` 开头即要求 revision —— 裸线 invalid_ref(不预期变更)。"""
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        with pytest.raises(release_read.ReleaseReadError) as ei:
            release_read.resolve_effective(art, "fin", "1.0", [])
        assert ei.value.code == "invalid_ref"
        assert "<line>#<n>" in ei.value.message


class TestB5GenerationAndReadback:
    """代际常量 + 已发版回读:B5 —— 不预期变更。"""

    def test_generation_constants_pinned(self):
        from gimbal.schema import M2_GENERATION

        assert M2_GENERATION == 2, "用例侧代际(批1 验收「未变」断言的基线)"
        assert M2_VERSION == "2", "知识侧代际(批1 验收「未变」断言的基线)"

    def test_released_revision_roundtrip_hydrates(self, tmp_path):
        """发版 → 快照回读 → 服务经模型水合(存量无 kind 字段的现状底)。"""
        from gimbal_plate.schema.service_definition import ServiceDefinition

        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        snap = release_read.load_snapshot(art, "fin", "1.0", 1)
        reg = snap.registry()
        sd = reg.iter_services_global()[0]
        assert sd.name == "fin-service"
        assert sd.version == "1.0.0"
        # 现状:模型尚无 kind 字段(b1-1 起存在且缺省 sut —— 届时同提交翻转)
        assert "kind" not in ServiceDefinition.model_fields
