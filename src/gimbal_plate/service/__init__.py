"""gimbal_plate.service —— 服务层纯函数(V3.1)。

本包在 V3.1 架构重构中由"被测服务定义容器"重新定义为"服务层纯函数"。

职责:
    - 接受 schema/* 的不可变数据,产出计算结果(字典 / 路径列表 / 映射表)
    - 不依赖 FastAPI / Request / Response(便于测试与跨场景复用)
    - 不依赖 systems/(只通过 schema/ 表达领域知识)

当前实装(原 http/_services/,V3.1 迁移):
    field_defaults.py        —— A5 计算字段默认值
    paths_resolver.py        —— B1 JSONPath 路径解析(DFS)
    failed_resolver.py       —— B2 failed_criteria × assertable_fields 关联
    system_from_service.py   —— B3 service 名反查 system

设计约束(V3 §1):
    这些函数是"纯函数 + 显式输入",保持与 protocol 解耦。
"""
from gimbal_plate.service.field_defaults import compute_field_defaults
from gimbal_plate.service.paths_resolver import resolve_paths
from gimbal_plate.service.failed_resolver import resolve_failed_criteria
from gimbal_plate.service.system_from_service import system_from_service

__all__ = [
    "compute_field_defaults",
    "resolve_paths",
    "resolve_failed_criteria",
    "system_from_service",
]