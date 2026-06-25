"""PR-0.1 引入:tests/integration 的 conftest。

职责:
  把 print+assert 脚本风格文件暂排除出 pytest 收集(collect_ignore_glob)。
  排除后仍可手动 python tests/integration/test_xxx.py 跑。

排除清单(对应盘点结果):
  - test_cli_run_wiring.py
  - test_defect_6_integration.py
  - test_preprocessor_vars.py
"""
from __future__ import annotations

# 暂排除的 print+assert 脚本风格文件
# 保留供手动运行,后续 PR-0.3 渐进转 pytest
collect_ignore_glob = [
    "test_cli_run_wiring.py",
    "test_defect_6_integration.py",
    "test_preprocessor_vars.py",
]
