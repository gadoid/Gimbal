from pydantic import BaseModel, Field, model_validator, ConfigDict
from datetime import datetime
from typing import Any, Optional, Literal, Annotated, Union
from .resource import ResourceUnion
from .ref import RefBase
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
    requirementRef : list[RefBase] = Field(description= "需求，用例关联链接")

class Config(BaseModel):
    """ 用例执行配置模型 """
    setup : list[SetupUnion] = Field(default_factory=list , description= "用例前置动作")
    teardown : list[TeardownUnion] = Field(default_factory=list , description= "用例后置动作")
    serviceDict : dict[str, str] = Field(default_factory=dict,description= "服务与URL映射关系")
    authDict : dict[str, dict[str,AuthSession]] = Field(default_factory=dict, description= "认证信息字典")
    timePolicy : TimePolicyUnion = Field(default_factory=RecordPolicy, description="时间处理策略:超时检查或耗时记录")
    retry : Optional[RetryPolicy] = None # 定义重试策略

class Scenario(BaseModel):
    """ 用例数据模型 """
    kind : Literal["scenario"] = "scenario"
    scenarioId : str = Field(..., description="场景，用例ID，前缀为sc" )  #  后续定义一个随机的Id生成器/工厂
    meta : Meta = Field(..., description="用例的元信息，用于管理用例")
    config : Config = Field(..., description="本次执行的配置信息")
    resource : dict[str , ResourceUnion] = Field(description="存放用例需要执行的相关资源信息")
    steps : list[StepUnion] = Field(..., description="存放具体的执行过程")

class ScenarioRef(RefBase) :
    kind : Literal["scenario_ref"] = "scenario_ref"

class Suite(BaseModel):
    kind : Literal["suite"] = "suite"
    suite : list[Scenario] = Field(..., description="scenario集合，暂时使用列表实现" )

class SuiteRef(RefBase) :
    kind : Literal["suite_ref"] = "suite_ref"

RunUnion = Annotated[
    Union[Scenario,ScenarioRef,Suite,SuiteRef],
    Field(discriminator="kind")
]

if __name__ == "__main__":
    from .resource import Mock
    from .step import Step
    from .api import Api
    from .request import Request

    # 测试 Meta 实例化
    meta = Meta(
        name="test_scenario",
        description="测试场景",
        module="user_module",
        priority=1,
        author="tester",
        owner="developer",
        tags=["smoke", "regression"],
        version="1.0.0",
        createTime=datetime.now(),
        expire=False,
        requirementRef=[]
    )
    print(f"Meta 测试: name={meta.name}, module={meta.module}")

    # 测试 Config 实例化
    config = Config(
        serviceDict={"user-service": "http://localhost:8080"},
        authDict={"token": "test_token"}
    )
    print(f"Config 测试: serviceDict={config.serviceDict}")

    # 测试 Scenario 实例化
    scenario = Scenario(
        scenarioId="sc_001",
        meta=meta,
        config=config,
        resource={"mock1": Mock(name="mock1", image="nginx", config={}, portMapping={})},
        steps=[
            Step(
                api=Api(service="test", method="GET", path="/test"),
                request=Request(body={}),
                strategy=[]
            )
        ]
    )
    print(f"Scenario 测试: scenarioId={scenario.scenarioId}, steps count={len(scenario.steps)}")


