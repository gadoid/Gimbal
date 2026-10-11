"""RS0 主体验收：版本模型 v1.4 3.1–3.6（开发计划 T1.6 主体）。

覆盖 Release v4.4 12.5 的 RS0 验收门（单测可承载的部分）：
双修订空 corrections、binding 修订含 corrections、main 上为旧线发修订被
祖先校验拒绝、草稿 finding 降 warnings、脏树被拒、维护分支发版后构件
分支可见（hash 自校验）。
"""
from __future__ import annotations

import json
from pathlib import Path

from gimbal_plate.release.release import (
    latest_revision_manifest,
    release_system,
    resolve_artifacts_root,
)

from tests.plate._release_fx import (
    commit,
    git,
    init_artifacts_branch,
    make_repo,
    write_endpoint,
    write_system_md,
)


def _manifest(art: Path, line: str, n: int) -> dict:
    return json.loads(
        (art / "fin" / "lines" / line / str(n) / "manifest.json")
        .read_text(encoding="utf-8"))


class TestFirstRevision:
    def test_manifest_and_envelope(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        head = git(repo, "rev-parse", "HEAD")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert r.success, r.message
        assert r.revision == "1.0#1"
        m = r.manifest
        assert m["line"] == "1.0" and m["revision"] == 1
        assert m["line_scheme"] == "free" and m["line_service"] is None
        assert m["source_commit"] == head
        assert m["previous_revision"] is None
        # 对象信封 {"type","data"}（F1 修复）+ shape_hash
        ep = next(e for e in m["objects"] if e["type"] == "endpoint")
        assert ep["review"] == "reviewed" and ep["shape_hash"]
        obj = json.loads((art / "objects" / f"{ep['hash']}.json")
                         .read_text(encoding="utf-8"))
        assert obj["type"] == "endpoint" and obj["data"]["id"] == "fin.a.a"
        # call 投影入对象池（manifest 记 hash）
        ph = m["call_projections"]["fin.a.a"]
        proj = json.loads((art / "objects" / f"{ph}.json")
                          .read_text(encoding="utf-8"))
        assert proj["type"] == "call"
        assert proj["data"]["method"] == "GET" and proj["data"]["path"] == "/a"
        # 构件分支提交（提交信息 = <系统>@<line>#<n>）
        log = git(art, "log", "--format=%s", "-1")
        assert log == "fin@1.0#1"

    def test_hash_self_check_after_pull(self, tmp_path: Path) -> None:
        """构件分支可见性（B6/RS0 门）：manifest 与对象在构件分支上，
        hash 与重新水合的对象自洽。"""
        _, fin, art = make_repo(tmp_path)
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert r.success
        m = _manifest(art, "1.0", 1)
        from gimbal_plate.dialect import EndpointSpec, object_hash
        for e in m["objects"]:
            envelope = json.loads(
                (art / "objects" / f"{e['hash']}.json").read_text("utf-8"))
            assert envelope["type"] == e["type"]
            if e["type"] == "endpoint":
                assert object_hash(
                    EndpointSpec.model_validate(envelope["data"])) == e["hash"]


class TestRevisions:
    def test_second_revision_only_review_change(self, tmp_path: Path) -> None:
        """第二个修订只改评审状态 → corrections 为空（RS0 门）。"""
        repo, fin, art = make_repo(tmp_path)
        write_endpoint(fin, "d", reviewed=False, path="/d")
        commit(repo, "add draft endpoint")
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        # draft → reviewed(评审完成),接口结构未动
        write_endpoint(fin, "d", reviewed=True, path="/d")
        commit(repo, "review")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert r.success, r.message
        assert r.revision == "1.0#2"
        assert r.manifest["corrections"] == []
        assert r.manifest["previous_revision"] == 1
        assert all(e["review"] == "reviewed" for e in r.manifest["objects"])

    def test_binding_change_lists_corrections(self, tmp_path: Path) -> None:
        """binding 变化 → corrections 含该接口（RS0 门）。"""
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art, signed_by="t").success
        write_endpoint(fin, "a", reviewed=True, path="/a2")   # 改 binding.path
        commit(repo, "change path")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert r.success
        assert r.manifest["corrections"] == ["fin.a.a"]

    def test_same_content_pool_not_growing(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        r1 = release_system(fin, artifacts_root=art, signed_by="t1")
        pool = {p.name for p in (art / "objects").glob("*.json")}
        r2 = release_system(fin, artifacts_root=art, signed_by="t2")
        assert r1.success and r2.success and r2.revision == "1.0#2"
        assert {p.name for p in (art / "objects").glob("*.json")} == pool


class TestGateGrading:
    def test_draft_finding_downgraded_to_warnings(self, tmp_path: Path) -> None:
        """草稿对象上的 finding 不挡发版,写入 warnings（D-4/RS0 门）。"""
        repo, fin, art = make_repo(tmp_path)
        # 草稿端点引用不存在的词条 → S2 落在草稿块内 → 告警
        write_endpoint(fin, "d", reviewed=False, path="/d",
                       extra="\ncapability: cap.no.such")
        commit(repo, "draft with dangling ref")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert r.success, r.message
        assert any(w["rule"] == "S2" for w in r.manifest["warnings"])

    def test_reviewed_finding_blocks(self, tmp_path: Path) -> None:
        """已评审对象上的引用问题阻塞（S2 或引用闭包,先到者拦截）。"""
        repo, fin, art = make_repo(tmp_path)
        write_endpoint(fin, "b", reviewed=True, path="/b",
                       extra="\ncapability: cap.no.such")
        commit(repo, "reviewed with dangling ref")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert not r.success
        assert ("引用闭包" in r.message) or ("发布闸门未过" in r.message)


class TestGitGates:
    def test_dirty_tree_rejected(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        write_endpoint(fin, "a", reviewed=True, path="/dirty")  # 不提交
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert not r.success
        assert "未提交变更" in r.message

    def test_line_not_declared_rejected(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(tmp_path)
        write_system_md(fin, line="1.0")
        # 重写为无 line 的入口
        (fin / "system.md").write_text(
            "---\ntype: system\nsystem: fin\n---\n\n# fin\n",
            encoding="utf-8")
        commit(repo, "drop line")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert not r.success
        assert "未声明版本线" in r.message

    def test_predecessor_without_revision_rejected(self, tmp_path: Path) -> None:
        repo, fin, art = make_repo(
            tmp_path, line="2.0", extra="\npredecessor_line: '1.0'")
        r = release_system(fin, artifacts_root=art, signed_by="t")
        assert not r.success
        assert "predecessor_line" in r.message

    def test_old_line_on_main_rejected_and_maint_branch_visible(
            self, tmp_path: Path) -> None:
        """维护分支发修订 → 构件分支可见;main 上为旧线发修订被拒(3.3)。"""
        repo, fin, art = make_repo(tmp_path)
        assert release_system(fin, artifacts_root=art,
                              signed_by="t").success          # 1.0#1 @ main
        base = git(repo, "rev-parse", "HEAD")
        # main 进入下一条版本线(2.2:先拉维护分支再合入)
        git(repo, "branch", "plate/fin/1.0", base)
        write_system_md(fin, "2.0", extra="\npredecessor_line: '1.0'")
        commit(repo, "bump line to 2.0")
        r2 = release_system(fin, artifacts_root=art, signed_by="t")
        assert r2.success and r2.revision == "2.0#1"          # predecessor 已有修订
        # 维护分支上继续发 1.0 的修订
        maint = tmp_path / "maint"
        git(repo, "worktree", "add", str(maint), "plate/fin/1.0")
        write_endpoint(maint / "systems" / "fin", "a",
                       reviewed=True, path="/a1")
        commit(maint, "fix on maintenance branch")
        r3 = release_system(maint / "systems" / "fin",
                            artifacts_root=art, signed_by="t")
        assert r3.success and r3.revision == "1.0#2"
        # 构件分支上两条线并存(维护分支的修订对构件分支可见)
        assert latest_revision_manifest(art, "fin", "1.0")[0] == 2
        assert latest_revision_manifest(art, "fin", "2.0")[0] == 1
        # main 上把 line 改回 1.0 再发 → 旧线最近修订在维护分支上,
        # 不是 main HEAD 的祖先 → 拒绝
        write_system_md(fin, "1.0")
        commit(repo, "revert to old line on main")
        r4 = release_system(fin, artifacts_root=art, signed_by="t")
        assert not r4.success
        assert "祖先" in r4.message


class TestResolveArtifactsRoot:
    def test_missing_env_fails_fast(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("PLATE_ARTIFACTS_PATH", raising=False)
        try:
            resolve_artifacts_root()
        except RuntimeError as e:
            assert "PLATE_ARTIFACTS_PATH" in str(e)
        else:
            raise AssertionError("未配置构件根应报错(B2)")

    def test_env_respected(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(tmp_path))
        assert resolve_artifacts_root() == tmp_path
