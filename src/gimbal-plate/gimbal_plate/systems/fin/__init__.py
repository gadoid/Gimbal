"""fin 系统(V3 试点)。

聚合 fin 系统的入口:导出 META_TEMPLATE / CONFIG_TEMPLATE(阶段 3)与
ALL_ENDPOINTS(阶段 1)的统一入口。
"""
from gimbal_plate.systems.fin.defaults import CONFIG_TEMPLATE, META_TEMPLATE

__all__ = [
    "META_TEMPLATE",
    "CONFIG_TEMPLATE",
]
