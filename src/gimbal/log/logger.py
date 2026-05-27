"""gimbal/logging/logger.py

get_logger() — 模块级日志获取入口。
bound_logger() — 注入运行时上下文（run_id / scenario_id / step_id）的绑定日志器。

使用模式
--------
1. 模块级静态 logger（最常见）::

    from gimbal.logging import get_logger
    logger = get_logger(__name__)

    def do_something():
        logger.info("开始处理: value={}", value)

2. 运行时绑定上下文（Engine / ScenarioRunner / StepRunner）::

    from gimbal.logging import bound_logger
    log = bound_logger(run_id="abc-123", scenario_id="sc-001")
    log.info("Scenario 执行开始")
    # 输出 JSON 时，run_id / scenario_id 自动出现在 JSON 字段中

3. contextvar 自动注入（可选，高级用法）::

    with log_context(run_id="abc", scenario_id="sc-001"):
        logger.info("自动携带上下文，无需显式传递")

设计说明
--------
- get_logger() 返回的是 loguru logger 本身（同一个全局对象），
  name 参数通过 opt(depth=1) + bind(name=name) 实现模块级名称注入。
  这与 stdlib logging.getLogger(__name__) 语义对齐，但底层共享同一 sink 管道。
- loguru 没有 logging.Logger 实例树，所有 logger 都是同一个 Logger 对象的视图。
  bound_logger() 返回的是 logger.bind(**context) 的结果，是一个轻量视图。
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

from loguru import logger as _root_logger


# ContextVar 存储当前协程/线程的上下文字段
_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("_LOG_CONTEXT", default={})


def get_logger(name: str) -> Any:
    """获取带模块名的 loguru logger 视图。

    Parameters
    ----------
    name:
        通常传 ``__name__``，与 stdlib logging.getLogger(__name__) 习惯一致。

    Returns
    -------
    loguru.Logger
        绑定了 name 字段的 logger 视图。在彩色/纯文本格式下，name 显示在
        ``module:function:line`` 位置；在 JSON 模式下，显示为 ``"logger"`` 字段。

    Examples
    --------
    ::

        logger = get_logger(__name__)
        logger.info("启动完成")
        logger.debug("变量: x={x}, y={y}", x=x, y=y)
        logger.warning("配置缺失，使用默认值: key={}", key)
        logger.error("HTTP 请求失败: url={url} status={status}", url=url, status=code)
        logger.exception("未预期异常")   # 自动附加当前异常信息
    """
    return _root_logger.bind(name=name)


def bound_logger(**context: Any) -> Any:
    """创建携带运行时上下文的 logger 视图。

    传入的 key-value 对将注入到每条日志记录的 ``extra`` 字段，
    在 JSON 模式下作为顶层字段输出，便于日志平台过滤和关联。

    Parameters
    ----------
    **context:
        任意键值对，常用字段：
        - ``run_id``      — 本次 Engine.run() 的唯一 ID
        - ``suite_id``    — 当前 Suite ID
        - ``scenario_id`` — 当前 Scenario ID
        - ``step_id``     — 当前 Step ID

    Returns
    -------
    loguru.Logger
        绑定了上下文字段的 logger 视图。

    Examples
    --------
    ::

        log = bound_logger(run_id=framework_ctx.run_id, scenario_id=sid)
        log.info("执行开始")
        log.warning("断言失败: target={target}", target=spec.target)
    """
    # 合并 ContextVar 中的基础上下文（若通过 log_context() 设置过）
    base = _LOG_CONTEXT.get()
    merged = {**base, **context}
    return _root_logger.bind(**merged)


@contextmanager
def log_context(**context: Any) -> Generator[None, None, None]:
    """上下文管理器：在 with 块内自动注入日志字段。

    使用 Python contextvars，协程/线程安全。
    适合在执行层（ScenarioRunner / StepRunner）的调用栈顶部注入，
    使整个调用链内的所有 get_logger() 调用都自动携带上下文。

    Examples
    --------
    ::

        with log_context(run_id="abc-123", scenario_id="sc-001"):
            # 在此 with 块内调用的所有模块级 logger 都会携带 run_id 和 scenario_id
            step_runner.run(step, scenario_ctx, idx)
    """
    old = _LOG_CONTEXT.get()
    token = _LOG_CONTEXT.set({**old, **context})
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)