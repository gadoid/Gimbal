"""gimbal_plate.systems —— 被测系统的实例数据(组合,不派生)。

按 V3 PLATE_V3_DESIGN.md §3:每个被测系统一个子目录,目录内是 EndpointSpec
实例、body 模型、默认模板;全程不动 schema/ 与 export/。

当前已注册系统:fin(系统服务名 fin,见各子目录的 system 字段)。
"""
