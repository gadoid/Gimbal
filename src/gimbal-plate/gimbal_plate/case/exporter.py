"""DEPRECATED: 此位置已迁移到 ``gimbal_plate.export.gimbal``。

V3 PLATE_V3_DESIGN.md §4 第一条:面向不同消费者的转换独立成模块。
``gimbal_plate.export.gimbal`` 是 V3 起的正式入口;此文件仅作向后兼容,
保留旧 import 路径可继续工作。

新代码请使用:
    from gimbal_plate.export.gimbal import (
        EndpointCaseExporter,
        EndpointCase,
        EndpointCaseDataset,
    )
"""
from gimbal_plate.export.gimbal import (  # noqa: F401
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
)

__all__ = ["EndpointCase", "EndpointCaseDataset", "EndpointCaseExporter"]
