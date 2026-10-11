"""RS1 读取侧验收（版本模型 v1.4 §7 / Release v4.4 §4；开发计划 T1.7）。

覆盖 Release v4.4 12.5 的 RS1 门：修订快照与 hash 校验、ref、版本线与
修订列表、差异（六类变化的变化部位）、生效修订（仅评审状态变化前进、
结构变化停住、改了又改回越过中间修订）、维护分支修订经构件分支被服务
装载（HTTP 层）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.release import read as rr
from gimbal_plate.release.release import release_system

from tests.plate._release_fx import commit, make_repo, write_endpoint


def _ep_md(name: str, *, service: str = "fin-service", path: str = "/a",
           req: tuple[tuple[str, str], ...] | None = None,
           resp: tuple[str, ...] = ("200",),
           desc: str = "") -> str:
    req_yaml = ""
    if req:
        req_yaml = "request:\n  declarations:\n" + "".join(
            f"  - name: {n}\n    path: {p}\n    type: string\n"
            f"    required: true\n" for n, p in req)
    resp_yaml = "responses:\n" + "".join(
        f'  "{r}": {{}}\n' for r in resp)
    desc_yaml = f"description: {desc}\n" if desc else ""
    return (
        f"---\nid: fin.a.{name}\ntype: endpoints\nsystem: fin\n---\n\n"
        f"# {name}\n\n```gimbal:endpoint\nreview: reviewed\n"
        f"id: fin.a.{name}\nsystem: fin\nservice: {service}\nname: {name}\n"
        + desc_yaml +
        f"binding:\n  protocol: http\n  method: GET\n  path: {path}\n"
        + req_yaml + resp_yaml + "```\n")


class TestReadBasics:
    def test_parse_ref(self) -> None:
        assert rr.parse_ref("working") == ("working", None, None)
        assert rr.parse_ref("") == ("working", None, None)
        assert rr.parse_ref("1.0") == ("line", "1.0", None)
        assert rr.parse_ref("1.0#3") == ("revision", "1.0", 3)
        with pytest.raises(rr.ReleaseReadError):
            rr.parse_ref("1.0#x")
        with pytest.raises(rr.ReleaseReadError):
            rr.parse_ref("#3")

    def test_list_lines_and_revisions(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        lines = rr.list_lines(art, "fin")
        assert len(lines) == 1
        assert lines[0]["line"] == "1.0" and lines[0]["revisions"] == 2
        assert lines[0]["latest"] == "1.0#2"
        assert lines[0]["line_scheme"] == "free"
        revs = rr.list_revisions(art, "fin", "1.0")
        assert [r["revision"] for r in revs] == ["1.0#1", "1.0#2"]

    def test_snapshot_hydration_and_hash_check(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        snap = rr.load_snapshot(art, "fin", "1.0", 1)
        assert "fin.a.a" in snap.endpoints
        assert snap.services and snap.services[0]["name"] == "fin-service"
        assert snap.projections["fin.a.a"]["path"] == "/a"
        assert snap.manifest["line"] == "1.0"
        # 查询面:修订注册表可当 working 注册表用(snapshot_id 带修订)
        reg = snap.registry()
        assert reg.snapshot_id == "fin@1.0#1"   # type: ignore[attr-defined]
        spec = reg.index_for("endpoint")
        assert spec is not None and spec.index.get("fin.a.a") is not None

    def test_corrupt_object_detected(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        m = rr.load_manifest(art, "fin", "1.0", 1)
        entry = next(e for e in m["objects"] if e["type"] == "endpoint")
        obj = art / "objects" / f"{entry['hash']}.json"
        data = json.loads(obj.read_text(encoding="utf-8"))
        data["data"]["name"] = "tampered"
        obj.write_text(json.dumps(data, ensure_ascii=False),
                       encoding="utf-8")
        with pytest.raises(rr.ReleaseReadError) as ei:
            rr.load_snapshot(art, "fin", "1.0", 1)
        assert ei.value.code == "release_corrupt"

    def test_m2_generation_gate(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        mp = art / "fin" / "lines" / "1.0" / "1" / "manifest.json"
        m = json.loads(mp.read_text(encoding="utf-8"))
        m["m2_version"] = "0"
        mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(rr.ReleaseReadError) as ei:
            rr.load_snapshot(art, "fin", "1.0", 1)
        assert ei.value.code == "release_m2_incompatible"


def _parts_after_change(tmp_path: Path, base: dict, changed: dict) -> dict:
    repo, fin, art = make_repo(tmp_path)
    ep = fin / "endpoints" / "fin.a.a.md"
    ep.write_text(_ep_md("a", **base), encoding="utf-8")
    commit(repo, "base")
    assert release_system(fin, artifacts_root=art, signed_by="t").success
    ep.write_text(_ep_md("a", **changed), encoding="utf-8")
    commit(repo, "change")
    r2 = release_system(fin, artifacts_root=art, signed_by="t")
    assert r2.success, r2.message
    d = rr.diff_snapshots(rr.load_snapshot(art, "fin", "1.0", 1),
                          rr.load_snapshot(art, "fin", "1.0", 2))
    return d["changed"]["endpoint.fin.a.a"]["parts"]


class TestDiffParts:
    """RS1 门:六类变化给出正确的变化部位(Release 4.3)。"""

    def test_description_only(self, tmp_path: Path) -> None:
        # description 属于对象 hash、不属于 shape → 部位 = description_only
        parts = _parts_after_change(
            tmp_path, dict(path="/a", desc="x"), dict(path="/a", desc="y"))
        assert parts == {"description_only": True}

    def test_path_change(self, tmp_path: Path) -> None:
        parts = _parts_after_change(tmp_path, dict(path="/a"),
                                    dict(path="/b"))
        assert set(parts) == {"binding"}
        assert "path_placeholders" not in parts["binding"]

    def test_placeholder_rename(self, tmp_path: Path) -> None:
        parts = _parts_after_change(tmp_path, dict(path="/a/{uid}"),
                                    dict(path="/a/{user_id}"))
        assert "binding" in parts
        assert parts["binding"]["path_placeholders"] == {
            "from": ["uid"], "to": ["user_id"]}

    def test_request_change(self, tmp_path: Path) -> None:
        parts = _parts_after_change(
            tmp_path, dict(path="/a", req=(("uid", "$.uid"),)),
            dict(path="/a", req=(("uid", "$.uid"), ("tok", "$.tok"))))
        assert set(parts) == {"request"}

    def test_response_rename(self, tmp_path: Path) -> None:
        parts = _parts_after_change(
            tmp_path, dict(path="/a", resp=("200",)),
            dict(path="/a", resp=("201",)))
        assert set(parts) == {"responses"}

    def test_service_change(self, tmp_path: Path) -> None:
        parts = _parts_after_change(tmp_path, dict(path="/a"),
                                    dict(path="/a", service="svc-x"))
        assert set(parts) == {"service"}


class TestResolveEffective:
    """RS1 门 / 版本模型 4.2(D-5 可用集合语义)。"""

    def _repo_with_two_endpoints(self, tmp_path: Path):
        repo, fin, art = make_repo(tmp_path)
        write_endpoint(fin, "b", reviewed=False, path="/b")
        commit(repo, "add draft b")
        assert release_system(fin, artifacts_root=art,
                              signed_by="t").success          # 1.0#1
        return repo, fin, art

    def test_review_only_advances(self, tmp_path: Path) -> None:
        repo, fin, art = self._repo_with_two_endpoints(tmp_path)
        write_endpoint(fin, "b", reviewed=True, path="/b")
        commit(repo, "review b")
        assert release_system(fin, artifacts_root=art,
                              signed_by="t").success          # 1.0#2
        out = rr.resolve_effective(art, "fin", "1.0#1", ["fin.a.a"])
        assert out["effective"] == "1.0#2"
        assert out["changed_endpoints"] == []

    def test_structure_change_stops_then_revert_skips(self, tmp_path: Path) -> None:
        repo, fin, art = self._repo_with_two_endpoints(tmp_path)
        # 1.0#2:无关接口评审完成 → 生效前进
        write_endpoint(fin, "b", reviewed=True, path="/b")
        commit(repo, "review b")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        # 1.0#3:用到的 fin.a.a 结构变化 → 生效停在 1.0#2
        write_endpoint(fin, "a", reviewed=True, path="/a2")
        commit(repo, "change a")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        out3 = rr.resolve_effective(art, "fin", "1.0#1", ["fin.a.a"])
        assert out3["effective"] == "1.0#2"
        assert out3["changed_endpoints"] == ["fin.a.a"]
        # 1.0#4:结构改回 → 可用集合越过 #3,生效 = 1.0#4(D-5)
        write_endpoint(fin, "a", reviewed=True, path="/a")
        commit(repo, "revert a")
        r4 = release_system(fin, artifacts_root=art, signed_by="t")
        assert r4.success and r4.revision == "1.0#4"
        out4 = rr.resolve_effective(art, "fin", "1.0#1", ["fin.a.a"])
        assert out4["effective"] == "1.0#4"
        assert out4["available"] == [1, 2, 4]
        assert out4["changed_endpoints"] == []

    def test_invalid_verified_ref(self, tmp_path: Path) -> None:
        repo, fin, art = self._repo_with_two_endpoints(tmp_path)
        with pytest.raises(rr.ReleaseReadError) as ei:
            rr.resolve_effective(art, "fin", "1.0", ["fin.a.a"])
        assert ei.value.code == "invalid_ref"


class TestHTTPSurface:
    """修订经构件分支被服务装载(HTTP 层,RS1 门)。"""

    def test_lines_manifest_diff_projection_resolve(
            self, tmp_path: Path, http_client, monkeypatch) -> None:
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        write_endpoint(fin, "a", reviewed=True, path="/a2")
        commit(repo, "change")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))

        r = http_client.get("/api/system/fin/lines")
        assert r.status_code == 200
        assert r.json()["data"]["items"][0]["latest"] == "1.0#2"

        r = http_client.get("/api/system/fin/revisions/1.0/1")
        assert r.status_code == 200
        assert r.json()["data"]["item"]["revision"] == 1

        r = http_client.get("/api/system/fin/revisions/9.9/1")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "release_not_found"

        # 差异(%23 = '#'):path 变化 → binding 部位
        r = http_client.get("/api/system/fin/diff/1.0%231/1.0%232")
        assert r.status_code == 200
        item = r.json()["data"]["item"]
        assert "binding" in item["changed"]["endpoint.fin.a.a"]["parts"]

        # ref 感知的 system 作用域查询(修订注册表,非 working)
        r = http_client.get("/api/systems/fin/endpoint/full?ref=1.0%231")
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["data"]["items"]]
        assert ids == ["fin.a.a"]          # 修订里只有这一个接口

        # 投影查询(4.8):按修订返回
        r = http_client.get("/api/endpoint/fin.a.a/projection?ref=1.0%231")
        assert r.status_code == 200
        assert r.json()["data"]["item"]["path"] == "/a"

        # 生效修订解析(4.4):#2 改了 a 的结构 → 停在 #1
        r = http_client.post("/api/system/action/resolve", json={
            "meta_plate": {"fin": "1.0#1"},
            "endpoints": {"fin": ["fin.a.a"]},
        })
        assert r.status_code == 200
        out = r.json()["data"]["item"]["fin"]
        assert out["effective"] == "1.0#1"
        assert out["changed_endpoints"] == ["fin.a.a"]

        # 取数视图按修订(4.7):ref + system → 从修订端点建索引
        r = http_client.get("/api/query-views?ref=1.0%231&system=fin")
        assert r.status_code == 200
        assert r.json()["data"]["ref"] == "1.0#1"
        # ref 缺 system → 400
        r = http_client.get("/api/query-views?ref=1.0%231")
        assert r.status_code == 400

    def test_ref_unknown_revision_404(self, tmp_path: Path, http_client,
                                      monkeypatch) -> None:
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))
        r = http_client.get("/api/systems/fin/endpoint/full?ref=7.7%237")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "release_not_found"
