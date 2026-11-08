"""grep 守卫(authz M2a S1.9):routers/services 禁止 visibility **列**
字面量比较(API 入参的 body.visibility 判定不在此列)。

visibility 列随 0043 删除;公共判定 = 公共项目谓词(project_id ==
zone.public_project_id)或近似(project_id is not None)。新增列比较
即红 —— 旧存量已在 S1.9 清零,本守卫进入终态(白名单恒空)。

豁免:``_ownership.py``/``zone.py``(谓词单点)。环境的 visibility 列
随 S2(0044)删除,原 ``environment.py`` 豁免一并退役。
"""
from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"

# 只匹配**属性/列比较**,不匹配 body.visibility(API 入参分支)。
# 第三条:属性对任意右值(变量也算)——S1.9 曾有 (r.visibility or
# "private") == visibility 形态逃过字面量两条,补齐
_SHAPES = (
    re.compile(r'\.\s*visibility\s*[=!]=\s*["\'](?:public|private)["\']'),
    re.compile(r'["\'](?:public|private)["\']\s*[=!]=\s*\w+\.visibility'),
    re.compile(r'\w+\.visibility\s*(?:or\s*[^=\n]+?)?[=!]='),
)

_EXEMPT_FILES = {"_ownership.py", "zone.py"}
_EXEMPT_LINE = re.compile(r'body\.visibility|TaskIn|body\.|\.model_fields')


def _scan():
    hits = set()
    for sub in ("routers", "services"):
        for py in sorted((_APP / sub).rglob("*.py")):
            if py.name in _EXEMPT_FILES:
                continue
            for i, line in enumerate(
                py.read_text(encoding="utf-8").splitlines(), 1
            ):
                if any(rx.search(line) for rx in _SHAPES):
                    if _EXEMPT_LINE.search(line):
                        continue  # API 入参分支,不是列比较
                    hits.add(
                        f"{py.relative_to(_APP).as_posix()}:{i}:{line.strip()}")
    return hits


def test_no_visibility_column_comparisons():
    """visibility 列比较清零(0043 后列不存在,比较即缺陷)。"""
    unknown = _scan()
    assert not unknown, (
        "visibility 列字面量比较(应走 project 谓词或 zone 派生):\n  "
        + "\n  ".join(sorted(unknown)))
