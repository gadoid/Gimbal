from pydantic import BaseModel, Field, model_validator, ConfigDict
from datetime import datetime
from typing import Any, Optional
from .resource import ResourceUnion
from .ref import RefBase
from .step import StepUnion
from .timepolicy import TimePolicyUnion, RecordPolicy
from .retrypolicy import RetryPolicy


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
    setup : list = Field(... ,description= "用例前置动作")
    teardown : list = Field(description= "用例后置动作")
    serviceDict : dict[str, str] = Field(description= "服务与URL映射关系")
    authDict : dict[str, Any] = Field(description= "认证信息字典")
    timePolicy : TimePolicyUnion = Field(default_factory=RecordPolicy, discriminator="kind", description="时间处理策略:超时检查或耗时记录")
    retry : Optional[RetryPolicy] = None # 定义重试策略

class Scenario(BaseModel): 
    """ 用例数据模型 """
    scenarioId : str = Field(..., description="场景，用例ID，前缀为sc" )  #  后续定义一个随机的Id生成器/工厂
    meta : Meta = Field(..., description="用例的元信息，用于管理用例")
    config : Config = Field(..., description="本次执行的配置信息")
    resource : dict[str , ResourceUnion] = Field(description="存放用例需要执行的相关资源信息")
    steps : list[StepUnion] = Field(..., description="存放具体的执行过程")


