"""systems.fin.defaults —— fin 系统的默认 Meta / Config 实例(单一导入入口)。

薄封装层,委托给 fin/meta.py 与 fin/config.py 的工厂函数。

为何用薄封装而不是直接导出 fin_meta_template() 的调用结果:
- 把"实例化时机"放在 defaults 层:首次 import 时计算并冻结,后续 round-trip
  测试断言稳定
- 调用方仍可通过 from systems.fin.meta import fin_meta_template 获取工厂,
  自行传入覆盖项生成自定义副本
"""
from __future__ import annotations

from gimbal_plate.schema import Config, Meta

from gimbal_plate.systems.fin.config import fin_config_template
from gimbal_plate.systems.fin.meta import fin_meta_template


META_TEMPLATE: Meta = fin_meta_template()
"""fin 系统的默认 Meta 模板(冻结)。"""

CONFIG_TEMPLATE: Config = fin_config_template()
"""fin 系统的默认 Config 模板(冻结)。"""


__all__ = ["META_TEMPLATE", "CONFIG_TEMPLATE"]