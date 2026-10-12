"""A-5（2026-10-12）M2 对象池写入:plate 启动侧。

ensure_m2_pooled 的四条契约:
* 构件根未配置 → 计数 + 静默跳过(不炸启动);
* 演练目录(非 git 工作树)→ 写盘不提交;
* 根即工作树 → 提交构件分支,且重复启动幂等(无空提交);
* 探测按 toplevel == 根——祖先目录的杂散 .git 不得被向上发现
  (此前 ``--is-inside-work-tree`` 会把用户主目录当工作树扫)。

healthz 暴露 m2_pool 状态(owned 启动路径)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.release.release import ensure_m2_pooled

from ._release_fx import git, commit


def test_unconfigured_skips_and_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("PLATE_ARTIFACTS_PATH", raising=False)
    first = ensure_m2_pooled()
    assert first["status"] == "unconfigured"
    assert first["skips"] >= 1
    second = ensure_m2_pooled()
    assert second["skips"] == first["skips"] + 1


def test_plain_dir_writes_envelope_without_commit(tmp_path,
                                                  monkeypatch) -> None:
    from gimbal_plate.export.m2_schema import export_m2

    monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(tmp_path))
    out = ensure_m2_pooled()
    assert out["status"] == "pooled"
    assert out["commit"] is None            # 演练目录:只写盘不提交
    e = export_m2()
    env = tmp_path / "objects" / f"{e.m2_hash}.json"
    assert env.is_file()
    envelope = json.loads(env.read_text(encoding="utf-8"))
    assert envelope["type"] == "m2" and envelope["data"] == e.schema


def test_repo_root_commits_and_repeated_startup_is_noop(tmp_path,
                                                        monkeypatch) -> None:
    """生产形态:PLATE_ARTIFACTS_PATH = plate/artifacts 孤儿分支的 worktree
    检出(3.6/B3)。toplevel == 根 → 提交落构件分支;重复启动零感。"""
    from ._release_fx import init_artifacts_branch

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "_.md").write_text("x", encoding="utf-8")
    git(repo, "init", "-q")
    commit(repo, "init")
    art = init_artifacts_branch(repo, tmp_path / "art")
    monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))

    first = ensure_m2_pooled()
    assert first["status"] == "pooled"
    assert first["commit"], "根即工作树 → 必须落构件提交"
    assert first["commit"] == git(art, "rev-parse", "HEAD")
    assert git(art, "status", "--porcelain") == ""       # 不留脏树

    # 重复启动:对象已在分支上 → 无新提交、HEAD 不动、仍报 pooled
    second = ensure_m2_pooled()
    assert second["status"] == "pooled"
    assert second["commit"] == first["commit"]
    assert len(git(art, "log", "--oneline").splitlines()) == 2


def test_ancestor_stray_repo_is_not_discovered(tmp_path,
                                               monkeypatch) -> None:
    """探测收紧回归:artifacts 根不是仓库时,不得向上发现祖先仓库。

    背景:用户主目录可能存在杂散 .git(整目录误 init),旧探测
    ``--is-inside-work-tree`` 会把整个祖先当工作树 add/commit。
    """
    outer = tmp_path / "outer"
    art = outer / "art"
    art.mkdir(parents=True)
    git(outer, "init", "-q")
    (outer / "README.md").write_text("x", encoding="utf-8")
    commit(outer, "init")
    outer_head = git(outer, "rev-parse", "HEAD")
    outer_logs = len(git(outer, "log", "--oneline").splitlines())

    monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(art))
    out = ensure_m2_pooled()
    assert out["status"] == "pooled"
    assert out["commit"] is None            # art 非工作树 → 演练路径
    # 祖先仓库零污染:HEAD 不动、无新提交、已跟踪文件零改动零暂存
    # (art/ 本身在祖先树里是新目录,出现为 untracked 是布局使然;
    #  旧 bug 的危害是把祖先已跟踪文件 add+commit 进去)
    assert git(outer, "rev-parse", "HEAD") == outer_head
    assert len(git(outer, "log", "--oneline").splitlines()) == outer_logs
    assert git(outer, "diff", "HEAD") == ""


def test_healthz_exposes_m2_pool(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from gimbal_plate.http.app import create_app

    monkeypatch.setenv("PLATE_ARTIFACTS_PATH", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:         # 进 lifespan(owned 路径)
        body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["m2_pool"]["status"] == "pooled"
    assert body["m2_pool"]["hash"]
