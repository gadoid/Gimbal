"""测试假引擎缝(B6③,2026-11-23)。

legacy 链退役后生产代码不再有「逐 case CLI launch」入口;测试里
monkeypatch 的假引擎(``launch(case_path, **kw) -> LaunchResult``,
可选发 on_event/on_log 回调、写 case 工件)统一落位到本模块 ——
conftest 的 ShimServerSession.run_case 以 legacy 同款 kwargs 委托
``_fake_engine.launch``,用例按需替换之。

未替换而命中 = 用例缺假引擎布景,显式报错(不静默跑真引擎)。
"""
from __future__ import annotations

from typing import Any


async def launch(*_args: Any, **_kwargs: Any):  # noqa: ANN201 — 测试缝
    """占位:被命中即说明用例没装假引擎(应 monkeypatch 本函数)。"""
    raise RuntimeError(
        "tests._fake_engine.launch 被裸调:用例未安装假引擎 —— 请在布景里 "
        "monkeypatch.setattr(_fake_engine, \"launch\", <fake>)")
