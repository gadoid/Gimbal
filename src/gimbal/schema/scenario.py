from pydantic import BaseModel, Field, model_validator, ConfigDict
from datetime import datetime
from typing import Any, Optional, Literal, Annotated, Union
from .resource import ResourceUnion
from .step import StepUnion
from .timepolicy import TimePolicyUnion, RecordPolicy
from .retrypolicy import RetryPolicy
from .setup import SetupUnion
from .teardown import TeardownUnion
from .auth import AuthSession

class Meta(BaseModel):
    """ 用例信息配置模型 """
    name : str = Field(..., description= "用例名")
    description : str = Field(... , description= "用例信息描述")
    module : str = Field(..., description= "用例所属的业务模块")
    priority : int = Field(..., description= "用例等级描述")  # 描述用例等级 需要对应的工厂方法
    author : str = Field(..., description= "用例作者") 
    owner : str = Field(..., description= "维护人/执行人")
    tags : list[str] = Field(..., description= "用例标签")  # 后续定义对应的工厂方法
    version : str = Field(description= "用例版本号") 
    createTime : datetime = Field(description= "创建时间")
    expire : bool = Field(description= "过期标志位")
    requirementRef : list[str] = Field(description= "需求，用例关联链接")

class Config(BaseModel):
    """ 用例执行配置模型 """
    setup : list[SetupUnion] = Field(default_factory=list , description= "用例前置动作")
    teardown : list[TeardownUnion] = Field(default_factory=list , description= "用例后置动作")
    services : dict[str, str] = Field(default_factory=dict,description= "服务与URL映射关系")
    users : dict[str,AuthSession] = Field(default_factory=dict, description= "认证信息字典")
    timePolicy : TimePolicyUnion = Field(default_factory=RecordPolicy, description="时间处理策略:超时检查或耗时记录")
    retry : Optional[RetryPolicy] = None # 定义重试策略
    # ── 新增：scenario 级变量声明 ──
    vars : dict[str, Any] = Field(
        default_factory=dict,
        description="变量声明；字面量或生成式 spec dict；CLI --var 优先级更高"
    )

class Scenario(BaseModel):
    """ 用例数据模型 """
    kind : Literal["scenario"] = "scenario"
    scenarioId : str = Field(..., description="场景，用例ID，前缀为sc" )  #  后续定义一个随机的Id生成器/工厂
    meta : Meta = Field(..., description="用例的元信息，用于管理用例")
    config : Config = Field(..., description="本次执行的配置信息")
    resource : dict[str , ResourceUnion] = Field(description="存放用例需要执行的相关资源信息")
    steps : list[StepUnion] = Field(..., description="存放具体的执行过程")

# v2.1 批次 F-2b：嵌入式 Suite（kind=suite 的 list[Scenario] 形态）已删除——
# 编排统一走 SuiteGraph（kind=graph，四模式 desugar + PlanPolicy）。
# 存量 suite 文件经 scripts/migrate_legacy_case.py 迁移为 graph aggregate。

class Control(BaseModel):
    """ 执行控制（v2 §shared 与 control；批次 C 落地 only + chain 切片）。 """
    only : Optional[list[str]] = Field(default=None, description="只执行这些 ref 及其传递依赖闭包")
    from_node : Optional[str] = Field(default=None, description="chain 起点（含）")
    to_node : Optional[str] = Field(default=None, description="chain 终点（含）")

class UnitDecl(BaseModel):
    """ 编排套件中的单元声明（v2.1 批次 C）。 """
    ref : str
    scenario : Scenario
    needs : list[str] = Field(default_factory=list)
    shared : Optional[str] = Field(default=None, description="shared 去重键")
    inputs : dict[str, Any] = Field(default_factory=dict, description="字面量注入（scenario vars）")
    outputs : Optional[list[str]] = Field(default=None, description="显式输出；None=静态分析推导")
    map : dict[str, str] = Field(default_factory=dict, description="连线改名: 上游输出名 → 本地输入名")
    repeat : int = Field(default=1, ge=1, le=64, description="编译期展开份数（单元 id=ref#k；v2.1 批次 D）")
    policy_kwargs : dict[str, Any] = Field(default_factory=dict, description="UnitPolicy 覆盖项(n_runs/retry/lock)")

from .plan import PlanPolicy as PlanPolicyRef  # noqa: E402 — SuiteGraph 前置

class SuiteGraph(BaseModel):
    """ 编排套件（v2 §2 desugar 源形态；kind=graph，v2.1 F-2b 起唯一 suite 形态）。 """
    kind : Literal["graph"] = "graph"
    mode : Literal["aggregate","compose","fanout","chain"] = "compose"
    before : list[UnitDecl] = Field(default_factory=list)
    units : list[UnitDecl] = Field(..., min_length=1)
    after : list[UnitDecl] = Field(default_factory=list)
    control : Optional[Control] = None
    policy : Optional[PlanPolicyRef] = None

RunUnion = Annotated[
    Union[Scenario,SuiteGraph],
    Field(discriminator="kind")
]

if __name__ == "__main__":
    from .resource import Mock
    from .step import Step
    from .call import Call
    from .request import Request


