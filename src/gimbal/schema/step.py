
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


if __name__ == "__main__":
    from .api import Api
    from .request import Request
    from .strategy import Extract, StrategyPhase, Scope

    # 测试 Step 实例化
    step = Step(
        api=Api(service="test", method="GET", path="/test"),
        request=Request(body={}),
        strategy=[
            Extract(
                name="extract_token",
                phase=StrategyPhase.AFTER_REQUEST,
                expression="$.response_body.token",
                target="auth_token",
                scope=Scope.SCENARIO
            )
        ]
    )
    print(f"Step 测试: kind={step.kind}, strategy count={len(step.strategy)}")

    # 测试 StepRef 实例化
    step_ref = StepRef(ref="step_ref_1")
    print(f"StepRef 测试: ref={step_ref.ref}")