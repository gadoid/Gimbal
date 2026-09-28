"""tests/integration 的 conftest。

历史：PR-0.1 曾把 print+assert 脚本风格文件排除出 pytest 收集
（test_defect_6_integration.py / test_preprocessor_vars.py）。
2026-09-28 api→call 残留清理：后者已改写为正规 pytest 并入收集，
前者与 tests/unit/engine/test_per_step_service_url.py、
tests/unit/protocols/test_multi_protocol_step.py 的 #6 语义覆盖完全
重复，随 api 形态一并删除。
"""
