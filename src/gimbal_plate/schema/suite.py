"""M2 SuiteGraph 家族（M2 方案 v2.4 §2 A 类 / §9.1；步骤 1 定义形态）。

SuiteGraph 及其子结构从执行器 ``gimbal/schema/scenario.py`` /
``plan.py`` 收编（A 类：被编写、被存储、跨组件传递）。``Plan`` /
``Unit`` / ``UnitPolicy`` 是编译产物（D 类），留在执行器；被编写的
``PlanPolicy`` 随 A 类进 M2。``subscribe`` 暂保持 executor 形态
（list[dict]，编译期 SUBSCRIBE_INVALID 校验）——SubscribeRule 的
校验收编随生成物替换一并做（步骤 3/4）。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .scenario import Scenario


class PlanPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parallel: int = Field(default=1, ge=1, le=64, description="单元级并发上限；1=串行")
    fail_fast: Optional[bool] = Field(default=None, description="None=沿用全局配置")
    timeout: Optional[float] = Field(default=None, description="整个 Plan 的超时（秒）")


class Control(BaseModel):
    """执行控制（only + chain 切片）。"""

    model_config = ConfigDict(extra="forbid")

    only: Optional[list[str]] = Field(default=None, description="只执行这些 ref 及其传递依赖闭包")
    from_node: Optional[str] = Field(default=None, description="chain 起点（含）")
    to_node: Optional[str] = Field(default=None, description="chain 终点（含）")


class UnitDecl(BaseModel):
    """编排套件中的单元声明。"""

    model_config = ConfigDict(extra="forbid")

    ref: str
    scenario: Scenario
    needs: list[str] = Field(default_factory=list)
    shared: Optional[str] = Field(default=None, description="shared 去重键")
    inputs: dict[str, Any] = Field(default_factory=dict, description="字面量注入（scenario vars）")
    outputs: Optional[list[str]] = Field(default=None, description="显式输出；None=静态分析推导")
    map: dict[str, str] = Field(default_factory=dict, description="连线改名：上游输出名 → 本地输入名")
    repeat: int = Field(default=1, ge=1, le=64, description="编译期展开份数（单元 id=ref#k）")
    policy_kwargs: dict[str, Any] = Field(default_factory=dict, description="UnitPolicy 覆盖项")


class NamedParams(BaseModel):
    """具名参数块（metrics / plugins 声明共享形态）。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="度量/插件名（注册表键）")
    params: dict[str, Any] = Field(default_factory=dict, description="参数（按注册表 params 模型校验）")


class CheckSelector(BaseModel):
    """横切断言的选择器。"""

    model_config = ConfigDict(extra="forbid")

    refs: list[str] = Field(default_factory=list, description="命中的单元 ref")
    bracket: Optional[Literal["before", "after", "main"]] = Field(
        default=None, description="限定括号段；None=main 主体")
    tags: list[str] = Field(default_factory=list, description="按 meta.tags 命中")


class CheckDecl(BaseModel):
    """横切断言声明——命中单元在编译期追加这条策略到其策略列表尾。"""

    model_config = ConfigDict(extra="forbid")

    on: CheckSelector = Field(default_factory=CheckSelector)
    strategy: dict[str, Any] = Field(..., description="断言策略（StrategyUnion dict 形态）")


class GateDecl(BaseModel):
    """判定门——suite 判定阶段按聚合度量做整体通过/失败。"""

    model_config = ConfigDict(extra="forbid")

    metric: Literal["pass_rate", "fail_count", "total",
                    "avg_duration_ms", "max_duration_ms"] = Field(...)
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte"] = Field(default="gte")
    value: float = Field(..., description="阈值")


class SuiteGraph(BaseModel):
    """编排套件（kind=graph，唯一 suite 形态）。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["graph"] = "graph"
    mode: Literal["aggregate", "compose", "fanout", "chain"] = "compose"
    before: list[UnitDecl] = Field(default_factory=list)
    units: list[UnitDecl] = Field(..., min_length=1)
    after: list[UnitDecl] = Field(default_factory=list)
    control: Optional[Control] = None
    policy: Optional[PlanPolicy] = None
    subscribe: Optional[list[dict]] = Field(
        default=None, description="声明式订阅规格（编译期校验）")
    checks: list[CheckDecl] = Field(default_factory=list)
    gates: list[GateDecl] = Field(default_factory=list)
    metrics: list[NamedParams] = Field(default_factory=list)
    plugins: list[NamedParams] = Field(default_factory=list)
