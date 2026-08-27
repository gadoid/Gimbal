"""systems.fin.resource —— fin 系统的 Resource 默认模板工厂。

Phase α(ADR 0002 §D-D4):M6 grammar 需要 Resource dim 至少有 1 条 seed,
以便 ``GET /api/resource`` 与 ``GET /api/systems/fin/resource`` 返回非空。
此处只暴露 ``fin_resource_template() -> Mock``,与 ``fin_config_template``
/ ``fin_meta_template`` 风格一致;调用方可用 kwargs 覆盖字段。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema.resource import Mock


def fin_resource_template(**overrides: Any) -> Mock:
    """构造 fin 系统的默认 Mock 资源(单元测试用 tidb 镜像)。

    默认值:
    - name        = "fin.tidb_test"
    - kind        = "mock"(由 Mock 字段决定)
    - image       = "pingcap/tidb:v7.1"
    - config      = {"region": "test"}
    - portMapping = {4000: 4000}
    """
    defaults: dict[str, Any] = {
        "name": "fin.tidb_test",
        "image": "pingcap/tidb:v7.1",
        "config": {"region": "test"},
        "portMapping": {4000: 4000},
    }
    return Mock(**{**defaults, **overrides})


__all__ = ["fin_resource_template"]