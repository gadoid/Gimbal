"""background_tasks — lifespan 轻量循环任务注册表(评审 E8)。

平台无周期任务基建;此前 lifespan 已挂「草稿清理」(Suite 重构第 1
步,小时级),外部系统集成再加 15s 调度循环 —— 与其让 lifespan 长成
面条,不如收敛为一个注册表:每个任务声明名字/周期/协程,supervisor
统一循环、异常隔离、优雅停止。
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from loguru import logger


class BackgroundTask:
    def __init__(self, name: str, interval_s: float,
                 fn: Callable[[], Awaitable]) -> None:
        self.name = name
        self.interval_s = interval_s
        self.fn = fn


_REGISTRY: list[BackgroundTask] = []
_TASKS: list[asyncio.Task] = []


def register(name: str, interval_s: float, fn: Callable[[], Awaitable]) -> None:
    """幂等注册(同名覆盖);start_all 启动已注册任务。"""
    _REGISTRY[:] = [t for t in _REGISTRY if t.name != name]
    _REGISTRY.append(BackgroundTask(name, interval_s, fn))


async def _loop(t: BackgroundTask) -> None:
    while True:
        await asyncio.sleep(t.interval_s)
        try:
            await t.fn()
        except Exception as e:  # noqa: BLE001 — 单拍失败不杀循环
            logger.warning("background task {}: tick failed: {}", t.name, e)


def start_all() -> None:
    stop_all()
    for t in _REGISTRY:
        _TASKS.append(asyncio.create_task(_loop(t), name=f"bg:{t.name}"))


def stop_all() -> None:
    for task in _TASKS:
        task.cancel()
    _TASKS.clear()


def registered() -> list[str]:
    return [t.name for t in _REGISTRY]
