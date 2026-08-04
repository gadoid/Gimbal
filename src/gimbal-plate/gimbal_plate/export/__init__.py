"""gimbal_plate.export —— 面向不同消费者的导出模块。

按 V3 PLATE_V3_DESIGN.md §4:每个消费者一个独立模块,输入统一是 EndpointSpec
(以及 systems/ 下的默认模板),不影响 schema/ 与 systems/。

当前实装:
    gimbal.py     → gimbal 可执行 dict(原 case/exporter.py)

未实装(按计划延后):
    platform.py / apidoc.py / mcp.py / mock.py
"""
