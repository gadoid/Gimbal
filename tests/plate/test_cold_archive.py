"""W25(P4.1):RS5 冷化判定查询测试(Release v4.4 §9 / T5.2)。

``release/cold_archive.py`` 此前全仓零测试引用。判定语义(R10):
「仍被引用」的修订不出现在冷化清单 ——
1. 被任一场景 meta.plate 引用的已验证修订本身;
2. 已验证修订与线内最新修订**之间**的全部中间修订(D-5 可用集合:
   结构「改了又改回」可能让中间修订成为生效修订);
3. 被执行记录 plate_pins 钉住的修订。
"""
from __future__ import annotations

from gimbal_plate.release.cold_archive import list_cold_archivable
from gimbal_plate.release.release import release_system

from tests.plate._release_fx import make_repo, write_endpoint, commit


def _release_n(fin, art, n: int) -> None:
    """连发 n 个修订(夹具基线已含 1 个端点,可直接重复发版)。"""
    for _ in range(n):
        assert release_system(
            fin, artifacts_root=art, signed_by="t").success


def _revisions(rows: list[dict], system: str = "fin") -> list[str]:
    return sorted(r["revision"] for r in rows if r["system"] == system)


def test_referenced_revision_and_closure_not_cold(tmp_path):
    """场景引用 1.0#2(最新 #3)→ #2 与「之间」的 #3 受保护,#1 可冷化。"""
    repo, fin, art = make_repo(tmp_path)
    _release_n(fin, art, 3)

    rows = list_cold_archivable(
        art, referenced_revisions={"fin": ["1.0#2"]},
        pinned_revisions={})
    assert _revisions(rows) == ["1.0#1"]


def test_referenced_latest_siblings_all_protected(tmp_path):
    """引用 #1 而最新 #3 → 闭包覆盖到最新,清单为空(D-5 语义)。"""
    repo, fin, art = make_repo(tmp_path)
    _release_n(fin, art, 3)

    rows = list_cold_archivable(
        art, referenced_revisions={"fin": ["1.0#1"]},
        pinned_revisions={})
    assert _revisions(rows) == []


def test_pinned_by_execution_plate_pins(tmp_path):
    """执行记录 plate_pins 钉住 #1 → 不进清单(钉不住「之间」:只保护本身)。"""
    repo, fin, art = make_repo(tmp_path)
    _release_n(fin, art, 3)

    rows = list_cold_archivable(
        art, referenced_revisions={},
        pinned_revisions={"fin": ["1.0#1"]})
    # pin 只保护修订本身(R10 第 3 条无「之间」闭包)
    assert _revisions(rows) == ["1.0#2", "1.0#3"]


def test_working_refs_ignored(tmp_path):
    """working 引用不构成保护(未钉修订不是已验证修订)。"""
    repo, fin, art = make_repo(tmp_path)
    _release_n(fin, art, 2)

    rows = list_cold_archivable(
        art, referenced_revisions={"fin": ["working"]},
        pinned_revisions={"fin": ["working"]})
    assert _revisions(rows) == ["1.0#1", "1.0#2"]


def test_unreferenced_system_fully_cold(tmp_path):
    """无任何引用 → 全部修订可冷化;摘要带 manifest 字段。"""
    repo, fin, art = make_repo(tmp_path)
    _release_n(fin, art, 2)

    rows = list_cold_archivable(
        art, referenced_revisions={}, pinned_revisions={})
    assert _revisions(rows) == ["1.0#1", "1.0#2"]
    row = rows[0]
    assert row["system"] == "fin" and row["revision"] == "1.0#1"
    assert row["signed_by"] == "t" and row["released_at"]
    assert isinstance(row["summary"], dict)


def test_second_line_cold_archivable_while_first_referenced(tmp_path):
    """多线:被引用的线受保护,另一条无引用线整体可冷化。"""
    repo, fin, art = make_repo(tmp_path, line="1.0")
    _release_n(fin, art, 1)
    # 第二条线 2.0:换线声明后发一版
    from tests.plate._release_fx import write_system_md
    write_system_md(fin, "2.0")
    commit(repo, "line 2.0")
    assert release_system(fin, artifacts_root=art, signed_by="t").success

    rows = list_cold_archivable(
        art, referenced_revisions={"fin": ["1.0#1"]},
        pinned_revisions={})
    assert _revisions(rows) == ["2.0#1"]
