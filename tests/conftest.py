"""测试根 conftest,集中管理 sys.path。

设计动机:
  现有 print+assert 脚本风格测试文件,每个都重复:
      sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
  这让"从仓库根跑 pytest"与"从 tests/<dir> 单独跑"出现路径不一致。
  本 conftest 在 pytest 启动时把 src/ 加入 sys.path,所有测试文件不再需要
  重复 sys.path 注入。

业务核心(Plate)的 import 由 tests/plate/conftest.py 单独管理,
本 conftest 只放通用 setup。
"""
from __future__ import annotations

import os
import sys

# 让 "from Plate import ..." 能解析
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
