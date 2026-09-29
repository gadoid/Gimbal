"""log/category.py — 日志分类映射（P1-03）。

按 logger 名**静态**映射 category，全仓唯一映射表。日志记录（JsonSink）
与声明式订阅（logs.category 过滤）都经 ``categorize_logger`` 取值。

映射规则（先长后短，前缀匹配）：

    gimbal.protocols.* / gimbal.strategy.builtin.call → call
    gimbal.auth.*                                     → auth
    gimbal.strategy.*                                 → strategy
    gimbal.compiler.*                                 → compiler
    gimbal.scheduler.*                                → scheduler
    gimbal.plugins.*                                  → plugin
    gimbal.core.debugger                              → debug
    gimbal.core.runner / scenario_runner              → step   （状态机：run/单元/步骤生命周期推进）
    gimbal.preprocessor.*                             → resolve（预处理：模板渲染/vars/users 解析）
    gimbal.context.*                                  → context（上下文：channels/views/scratch 通道）
    其余（含经 InterceptHandler 桥接的第三方 stdlib 名）→ core
"""
from __future__ import annotations

# (前缀, category) —— 顺序敏感：更长的前缀先匹配
_PREFIX_MAP: tuple[tuple[str, str], ...] = (
    ("gimbal.strategy.builtin.call", "call"),
    ("gimbal.protocols.", "call"),
    ("gimbal.auth.", "auth"),
    ("gimbal.strategy.", "strategy"),
    ("gimbal.compiler.", "compiler"),
    ("gimbal.scheduler.", "scheduler"),
    ("gimbal.plugins.", "plugin"),
    ("gimbal.core.debugger", "debug"),
    ("gimbal.core.runner", "step"),
    ("gimbal.core.scenario_runner", "step"),
    ("gimbal.preprocessor.", "resolve"),
    ("gimbal.context.", "context"),
)

DEFAULT_CATEGORY = "core"

CATEGORIES: tuple[str, ...] = (
    "call", "auth", "strategy", "compiler", "scheduler", "plugin", "debug",
    "step", "resolve", "context", "core",
)


def categorize_logger(name: str | None) -> str:
    """logger 名 → category（未知/空名 → core）。"""
    if not name:
        return DEFAULT_CATEGORY
    for prefix, category in _PREFIX_MAP:
        if name == prefix or name.startswith(prefix):
            return category
    return DEFAULT_CATEGORY
