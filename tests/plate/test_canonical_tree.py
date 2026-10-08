"""规范形守门(评审 R3):systems/ 真源树必须处于规范形。

渲染器对歧义标量强制双引号后,规范形定义随之收紧;历史文件若不重渲,
第一次 `plate review` / 任何回写都会把整个文件重写一遍(评审实测 154/155
偏离)。本守门锁住两件事:

1. ``render(parse(x)) == x`` —— 全树已是规范形(CI 入库闸门的一环,
   防再次引入手写非规范形);
2. 幂等 —— 规范形一轮回写后不再变化(往返字节稳定,第 5 节已定)。

手写新内容请先跑 `python -m gimbal_plate.cli check <系统>` 并让 plate
回写一次(或在 PR 里附带渲染后的结果)。
"""
from __future__ import annotations

from pathlib import Path

from gimbal_plate.dialect import parse_markdown, render

_REPO = Path(__file__).resolve().parents[2]


def _all_md() -> list[Path]:
    return sorted((_REPO / "systems").rglob("*.md"))


def test_systems_tree_is_canonical() -> None:
    files = _all_md()
    assert files, "systems/ 真源树缺失"
    drift: list[str] = []
    for md in files:
        text = md.read_text(encoding="utf-8")
        if render(parse_markdown(text, source=str(md))) != text:
            drift.append(md.as_posix())
    assert not drift, (
        f"{len(drift)} 个文件不是规范形(需全量重渲染;手写文件请先经 plate "
        f"回写): {drift[:5]}"
    )


def test_canonical_render_is_idempotent() -> None:
    """规范形再过一脑 parse→render 必须字节稳定。"""
    for md in _all_md():
        text = md.read_text(encoding="utf-8")
        once = render(parse_markdown(text, source=str(md)))
        assert render(parse_markdown(once, source=str(md))) == once, md
