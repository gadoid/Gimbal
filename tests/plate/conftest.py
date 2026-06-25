"""tests/plate 的 conftest。

职责:
  1. 让 tests/plate/ 下的测试能 import Plate
  2. 不放 collect_ignore_glob —— 本目录所有测试都已是 pytest 函数

sys.path 注入由 tests/conftest.py(根)统一处理,本 conftest 不重复。
"""
from __future__ import annotations

# 根 conftest.py 已把 src/ 加入 sys.path,本 conftest 不再重复
# tests/plate/test_*.py 直接 from Plate import ... 即可解析
