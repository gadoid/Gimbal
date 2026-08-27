"""systems.fin.scenario —— fin 系统的 Scenario 默认模板工厂。

Phase α(ADR 0002 §D-D6):M6 grammar 的 scenario dim 仅暴露 minimal view
(``scenario_id`` + ``name`` + ``systems``),但 ``Scenario`` 本身要求
``meta`` / ``config`` / ``resource`` / ``steps`` 都必须提供合法值。

本工厂构造一个最小可校验的 Scenario,所有重字段(meta / config / steps)
都从 ``fin_meta_template`` / ``fin_config_template`` / 空步骤列表派生,
调用方可用 kwargs 覆盖。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema.scenario import Scenario
from gimbal_plate.systems.fin.config import fin_config_template
from gimbal_plate.systems.fin.meta import fin_meta_template


def fin_scenario_template(**overrides: Any) -> Scenario:
    """构造 fin 系统的默认 Scenario(Phase α 烟测用)。

    默认值:
    - scenarioId = "sc-fin-default"
    - meta       = fin_meta_template()(system=[FIN_SYSTEM])
    - config     = fin_config_template()
    - resource   = {}(Phase α 不暴露 resource,通过 endpoint 配置覆盖)
    - steps      = []  (Phase α 不做执行)
    """
    defaults: dict[str, Any] = {
        "scenarioId": "sc-fin-default",
        "meta": fin_meta_template(),
        "config": fin_config_template(),
        "resource": {},
        "steps": [],
    }
    return Scenario(**{**defaults, **overrides})


__all__ = ["fin_scenario_template"]