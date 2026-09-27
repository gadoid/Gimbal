"""gimbal.protocols — 调用协议层（多协议编排，2026-09-27）。

状态机不再内置任何协议细节；每种调用协议以 ProtocolExecutor 的形式
注册进 ProtocolRegistry，状态机 _do_call 做三段式编排：
识别 protocol → build_spec → dispatcher 注册表分发。

扩展（注册一种新协议）：
    1. 实现 ProtocolExecutor 子类（protocol 名 + build_spec + execute）；
    2. 插件在 on_activate 里 ctx.register_protocol(MyProtocolExecutor())；
       或嵌入场景直接 build_default_protocol_registry().register(...)。
请求体数据结构由协议侧定义；协议内字段查询统一 JSONPath。
"""
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.registry import ProtocolRegistry, build_default_protocol_registry

__all__ = [
    "ProtocolCallContext",
    "ProtocolExecutor",
    "ProtocolRegistry",
    "build_default_protocol_registry",
]
