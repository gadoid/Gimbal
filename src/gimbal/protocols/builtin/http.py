"""protocols/builtin/http.py — http 协议执行器的规范化入口。

实现本体在 `gimbal/strategy/builtin/call.py` 的 CallExecutor（协议中立化
时原地升级为 ProtocolExecutor 第一员；类名 / kind="_call" / 模块 logger
三处历史契约不动，插件与既有测试零改动）。本模块只提供规范化别名，
供按 `gimbal.protocols.builtin` 路径引用的代码使用。
"""
from gimbal.strategy.builtin.call import CallExecutor as HttpProtocolExecutor

__all__ = ["HttpProtocolExecutor"]
