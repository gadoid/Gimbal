"""GIMBAL Plate — 契约模型仓库(子系统)。

本包独立于 ``gimbal`` 主包,被 scenario 加载器与 mock server **按需消费**。
顶层只 re-export 单例 ``registry``,**不 import 任何子包**——保证"导入
Plate 不会破坏任何东西"的零侵入承诺(设计 §7)。

命名取自摄影史上的感光板(底片前身,"被测系统留存在测试系统中的底片"),
同时取 base plate(基座)之意,与 Gimbal(稳定取向)、Prism(折射分光)共同构成
光学—机械仪器命名链路。详细动机见 design/PLATE_DESIGN.md。
"""
from .core import BootstrapError, registry

__all__ = ["registry", "BootstrapError"]
