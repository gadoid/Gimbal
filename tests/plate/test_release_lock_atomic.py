"""发版锁 + manifest 原子写(整体评审 2026-10-15 #7)。

- 并发两次发版:串行化,第二次的 previous_revision 指向第一次的产物;
- 锁文件与原子写临时文件不进构件分支提交;
- 只有编号目录、没有 manifest 的残留(发版中途崩溃)不被当作最新修订;
- 陈旧锁(持有进程已崩溃)超时后被清除,不永久阻塞发版;
- 锁被他人持有且未陈旧时,超时放弃并给出明确提示。
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from gimbal_plate.release import release as rel
from gimbal_plate.release.release import latest_revision_manifest, release_system

from tests.plate._release_fx import commit, git, make_repo, write_endpoint


def test_concurrent_releases_serialize(tmp_path: Path, monkeypatch) -> None:
    repo, fin, art = make_repo(tmp_path)
    # 放大竞态窗口:分配编号前停顿,无锁时两个线程会读到同一个 prev
    orig_mkdir = Path.mkdir

    def slow_mkdir(self, *a, **kw):
        if self.parent.name == "1.0" and self.name.isdigit():
            time.sleep(0.3)
        return orig_mkdir(self, *a, **kw)

    monkeypatch.setattr(Path, "mkdir", slow_mkdir)
    results: list = []

    def run() -> None:
        results.append(release_system(fin, artifacts_root=art, signed_by="t"))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r.success for r in results), [r.message for r in results]
    by_n = {r.manifest["revision"]: r.manifest for r in results}
    assert sorted(by_n) == [1, 2]
    assert by_n[1]["previous_revision"] is None
    assert by_n[2]["previous_revision"] == 1      # 不再基于陈旧的 prev
    assert not (art / "fin" / ".release.lock").exists()


def test_lock_and_tmp_not_committed(tmp_path: Path) -> None:
    repo, fin, art = make_repo(tmp_path)
    assert release_system(fin, artifacts_root=art, signed_by="t").success
    tracked = git(art, "ls-files").splitlines()
    assert not any(p.endswith(".release.lock") or p.endswith(".tmp")
                   for p in tracked), tracked


def test_orphan_revision_dir_ignored(tmp_path: Path) -> None:
    repo, fin, art = make_repo(tmp_path)
    assert release_system(fin, artifacts_root=art, signed_by="t").success
    # 模拟发版中途崩溃:编号目录已抢占、manifest 未落盘
    (art / "fin" / "lines" / "1.0" / "2").mkdir()
    n, _ = latest_revision_manifest(art, "fin", "1.0")
    assert n == 1
    # 下一次发版跳过残留编号,前驱仍指向真实的最新修订
    write_endpoint(fin, "b", path="/b")
    commit(repo, "add b")
    r = release_system(fin, artifacts_root=art, signed_by="t")
    assert r.success, r.message
    assert r.manifest["revision"] == 3
    assert r.manifest["previous_revision"] == 1


def test_stale_lock_is_cleared(tmp_path: Path, monkeypatch) -> None:
    repo, fin, art = make_repo(tmp_path)
    lock = art / "fin" / ".release.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("pid=dead\n", encoding="utf-8")
    old = time.time() - rel.RELEASE_LOCK_STALE_S - 10
    os.utime(lock, (old, old))
    r = release_system(fin, artifacts_root=art, signed_by="t")
    assert r.success, r.message
    assert not lock.exists()


def test_held_lock_times_out(tmp_path: Path, monkeypatch) -> None:
    repo, fin, art = make_repo(tmp_path)
    monkeypatch.setattr(rel, "RELEASE_LOCK_TIMEOUT_S", 0.5)
    lock = art / "fin" / ".release.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("pid=alive\n", encoding="utf-8")
    r = release_system(fin, artifacts_root=art, signed_by="t")
    assert not r.success
    assert "另有发版进行中" in r.message
    assert lock.exists()          # 他人的锁不被误删
