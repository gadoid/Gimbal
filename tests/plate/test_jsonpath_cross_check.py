"""T5.1（M2 §7）：JSONPath 三份实现对拍测试。

三份实现（执行器 818 行 / plate 809 行 / 平台 810 行）按 M2 §7 维持
镜像 + 对拍。以执行器版为基准，另两份对同一语料逐断言结果一致。

导入策略：plate 的 conftest 已把 `src/` 加入 sys.path（gimbal_plate
可导入）；执行器通过 `gimbal.utils.jsonpath` 导入（src/gimbal 在
pyproject 的 dev-mode-dirs 中）；平台通过 `app.services.jsonpath`
导入（backend 路径由测试自行追加）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from gimbal.utils.jsonpath import get_all as exec_get_all  # noqa: E402
from gimbal_plate.utils.jsonpath import get_all as plate_get_all  # noqa: E402

try:
    from app.services.jsonpath import get_all as platform_get_all  # noqa: E402
except ImportError:
    platform_get_all = None

# 语料：覆盖常用 JSONPath 语法
CORPUS = [
    ("$.a.b", {"a": {"b": 42}}),
    ("$.a.b.c", {"a": {"b": {"c": "deep"}}}),
    ("$.a[0]", {"a": [10, 20, 30]}),
    ("$.a[2]", {"a": [10, 20, 30]}),
    ("$.a[*]", {"a": [10, 20, 30]}),
    ("$.a.b[*]", {"a": {"b": ["x", "y"]}}),
    ("$.a..b", {"a": {"b": 1, "c": {"b": 2}}}),
    ("$.a[?(@.x>1)]", {"a": [{"x": 1}, {"x": 2}, {"x": 3}]}),
    ("$.a[?(@.x==2)].y", {"a": [{"x": 2, "y": "hit"}, {"x": 3, "y": "miss"}]}),
    ("$.missing", {"a": 1}),
    ("$.a.b.c.d", {"a": {"b": {}}}),
    ("$", {"a": 1, "b": [2, 3]}),
    ("$.a[0].b", {"a": [{"b": "nested"}]}),
]

# plate 与执行器对比（必跑）
IMPLS: dict[str, object] = {"plate": plate_get_all}
if platform_get_all is not None:
    IMPLS["platform"] = platform_get_all


class TestJsonPathCrossCheck:
    """各实现对同一语料的输出必须与执行器版一致。"""

    @pytest.mark.parametrize("impl_name", list(IMPLS))
    @pytest.mark.parametrize("expr,data", CORPUS)
    def test_matches_executor(self, impl_name: str, expr: str, data: dict):
        fn = IMPLS[impl_name]
        # get_all(data, path) — data 在前
        exec_result = list(exec_get_all(data, expr))
        other_result = list(fn(data, expr))
        assert other_result == exec_result, (
            f"expr={expr!r} impl={impl_name}: "
            f"executor={exec_result} {impl_name}={other_result}")
