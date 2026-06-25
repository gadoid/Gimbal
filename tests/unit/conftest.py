"""PR-0.1 引入:tests/unit 的 conftest。

职责:
  1. 把 print+assert 脚本风格文件暂排除出 pytest 收集(collect_ignore_glob)。
     这些文件顶层 assert + 偶有 sys.exit(1),在 import 时执行,会破坏 pytest 收集。
     排除后仍可手动 python tests/unit/test_xxx.py 跑(保留原 print+assert 行为)。

  2. 透传 sys.path 设置(由根 conftest.py 已注入,本 conftest 不重复)。

排除清单(对应盘点结果):
  - test_asset_materializer.py
  - test_collector_plugin.py
  - test_defect_fixes.py            ← 含 sys.exit(1) 是核心问题
  - test_local_fs_store.py
  - test_plugin_event_integration.py
  - test_resolver_list_body.py
  - test_response_body_extract_plugin.py
"""
from __future__ import annotations

# 暂排除的 print+assert 脚本风格文件(顶层执行,不在 def test_ 函数里)
# 这些文件保留供手动运行:
#     python tests/unit/test_asset_materializer.py
# 后续 PR-0.3 渐进转 pytest,届时从此清单移除
collect_ignore_glob = [
    "test_asset_materializer.py",
    "test_collector_plugin.py",
    "test_defect_fixes.py",
    "test_local_fs_store.py",
    "test_plugin_event_integration.py",
    "test_resolver_list_body.py",
    "test_response_body_extract_plugin.py",
]

# 已 pytest 化的子目录默认走 collector,不需要 collect_ignore
# 它们被 [tool.pytest.ini_options].testpaths 显式列出,确保被 pytest 发现
