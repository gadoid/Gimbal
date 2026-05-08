
from pydantic import BaseModel, Field 
from typing import Literal , Annotated, Union
from .strategy import StrategyUnion
from .ref import RefBase
from .api import ApiUnion
from .request import RequestUnion

class Step(BaseModel):
    """ 单步骤数据模型 """
    kind : Literal["step"] = "step"
    api : ApiUnion = Field(..., description= "当前步骤的接口请求信息")
    request : RequestUnion = Field(..., description= "当前步骤的请求体信息")
    strategy : list[StrategyUnion] = Field(... , description= "当前步骤需要执行的策略集")

class StepRef(RefBase) :
    kind : Literal["step_ref"] = "step_ref"

StepUnion = Annotated[
    Union[Step, StepRef],
    Field(discriminator="kind")
]