"""systems.common.config —— 系统无关的 Config 默认模板工厂。

提供 ``common_config_template(**overrides) -> Config``:
- 返回 schema.Config 的实例(不是子类)
- 提供 Config 字段的最低公共默认(空 services/users/vars、默认 TimePolicy)
- 调用方覆盖 services / users / vars / setup / teardown / retry 等

注意:AuthSession 与具体业务耦合,不在 common 默认值里给,留给系统层
注入(避免 common 反向依赖任何具体系统的账号约定)。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema import Config
from gimbal_plate.schema.time_policy import RecordPolicy


def common_config_template(**overrides: Any) -> Config:
    """构造系统无关的 Config 默认模板。

    最低公共默认:
        - setup=[] / teardown=[]
        - services={} / users={} / vars={}
        - timePolicy=RecordPolicy(记录模式,不强制超时)
        - retry=None

    调用方负责填入该系统的 services(域名→URL)、users(账号池)、
    vars(业务占位变量)、setup/teardown(如 DB 准备/清理)等。
    """
    defaults: dict[str, Any] = {
        "setup": [],
        "teardown": [],
        "services": {},
        "users": {},
        "timePolicy": RecordPolicy(),
        "retry": None,
        "vars": {},
    }
    defaults.update(overrides)
    return Config(**defaults)


__all__ = ["common_config_template"]