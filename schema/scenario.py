from pydantic import BaseModel, Field, model_validator, ConfigDict
from datetime import datetime
from typing import Any, Optional, Literal , Union , Annotated
from .resource import Resource
from .strategy import StrategyUnion
from .ref import Ref

class Api(BaseModel) :
    pass

class Step(BaseModel):
    """ 单步骤数据模型 """
    api : Api = Field(..., description= "当前步骤的接口请求信息")
    request : dict = Field(..., description= "当前步骤的请求体信息")
    strategy : list[StrategyUnion] = Field(... , description= "当前步骤需要执行的策略集")

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
    requirementRef : list[Ref] = Field(description= "需求，用例关联链接")

class TimeoutStrategy(BaseModel):
    """超时模式:执行器检查每一步是否超时,超时抛异常"""
    mode: Literal["timeout"] = "timeout"
    seconds: int = Field(description="超时阈值(秒)")

class RecordStrategy(BaseModel):
    """记录模式:不检查超时,但记录实际耗时到运行结果"""
    mode: Literal["record"] = "record"

class RetryPolicy(BaseModel):
    """ 重试策略配置模型 """
    maxAttempts : int = Field(1,description= "最大尝试次数")
    backoffSeconds : float = Field(20, description= "退避基础时长")
    retryOn : list[str] = Field(description= "触发重试的条件标签") # 定义一组error code

class Config(BaseModel):
    """ 用例执行配置模型 """
    setup : list = Field(... ,description= "用例前置动作")
    teardown : list = Field(description= "用例后置动作")
    serviceDict : dict[str, str] = Field(description= "服务与URL映射关系")
    authDict : dict[str, Any] = Field(description= "认证信息字典")
    timeStrategy : Union[TimeoutStrategy, RecordStrategy] = Field(default_factory=RecordStrategy, discriminator="mode", description="时间处理策略:超时检查或耗时记录")
    retry : RetryPolicy =  None # 定义重试策略

ResourceUnion = Annotated[
    Union[Resource,Ref],
    Field(discriminator="kind")
]

StepUnion = Annotated[
    Union[Step,Ref],
    Field(discriminator="kind")
]

class Scenario(BaseModel): 
    """ 用例数据模型 """
    scenarioId : str = Field(..., description="场景，用例ID，前缀为sc" )  #  后续定义一个随机的Id生成器/工厂
    meta : Meta = Field(..., description="用例的元信息，用于管理用例")
    config : Config = Field(..., description="本次执行的配置信息")
    resource : dict[str , Union[Resource, Ref]] = Field(description="存放用例需要执行的相关资源信息")
    steps : list[StepUnion] = Field(..., description="存放具体的执行过程")


