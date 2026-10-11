"""M2 RunOptions（M2 方案 v2.4 §2.3 / §9.2；步骤 1 定义形态）。

承接执行能力 D1：执行指令结构定义归 plate，RunScheme 存实例，CLI
``--plan`` 是快捷写法。只收「测试活动语义」的参数；``halt_at`` 并入
``step_to``（CLI 已把 ``--step-to`` 映射为 halt_at）；对 SuiteGraph，
``n_runs`` / ``parallel`` 覆盖 graph 自带 policy（沿用 server 现语义，
规则写进字段说明，平台与 CLI 不各自解释）。数据集选择、服务绑定、
认证注入属平台物化输入，不进 RunOptions（Q4：D1「数据集」本次不纳入）。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .subscribe import SubscribeRule


class DebugSpec(BaseModel):
    """调试装载配置（随 RunOptions 进 M2；会话命令是运行时接口，留在执行器）。"""

    model_config = ConfigDict(extra="forbid")

    pause: Literal["none", "on_failure", "every_step"] = "on_failure"
    breakpoints: list[str] = Field(default_factory=list)
    wait_timeout: float | None = Field(
        default=None, description="暂停等待上限（秒），超时按 abort")


class RunOptions(BaseModel):
    """执行指令（测试活动语义）。"""

    model_config = ConfigDict(extra="forbid")

    step_from: int | None = None
    step_to: int | None = None      # 取代 halt_at
    n_runs: int = Field(1, ge=1, le=64, description="对 SuiteGraph 覆盖 graph policy")
    parallel: int = Field(1, ge=1, le=64)
    debug: Optional[DebugSpec] = Field(
        default=None, description="调试装载；约束：单单元且 n_runs=1")
    subscribe: Optional[list[SubscribeRule]] = None
