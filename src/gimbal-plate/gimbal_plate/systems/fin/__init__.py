"""fin 系统(V3 试点)。

聚合 fin 系统的入口:
- 模板入口: META_TEMPLATE / CONFIG_TEMPLATE(冻结的默认实例)
- 工厂入口: fin_meta_template / fin_config_template(可定制副本)
- 端点入口: ALL_ENDPOINTS(由 fin.endpoint 子包聚合)

调用方:
    from gimbal_plate.systems.fin import META_TEMPLATE        # 直接拿默认
    from gimbal_plate.systems.fin import fin_meta_template   # 拿工厂自定义
"""
from gimbal_plate.systems.fin.config import fin_config_template
from gimbal_plate.systems.fin.defaults import CONFIG_TEMPLATE, META_TEMPLATE
from gimbal_plate.systems.fin.meta import fin_meta_template

__all__ = [
    # 默认实例(冻结)
    "META_TEMPLATE",
    "CONFIG_TEMPLATE",
    # 工厂函数(可定制)
    "fin_meta_template",
    "fin_config_template",
]