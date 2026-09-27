from pydantic import BaseModel, Field
from typing import Literal , Optional
from .strategy import StrategyUnion
from .call import Call
from .request import RequestUnion

class Step(BaseModel):
    """ 单步骤数据模型。

    调用表达（v2.1 批次 F 定稿）：``call = {protocol, ...协议自有字段}``
    是唯一调用形态 —— api 语法糖已随双读期结束退役（存量用例经
    ``scripts/migrate_legacy_case.py`` 迁移，plate /convert 产出 call 形态）。
    ``request`` 是请求体载体（body 结构由协议定义解释）；
    非调用型协议步骤允许省略 request。
    """
    kind : Literal["step"] = "step"
    description : Optional[str] = Field(default=None, description= "步骤说明,描述此步骤的能力/意图,供人和 Agent CLI 参考;非必填")
    call : Call = Field(..., description= "协议中立调用:{protocol(必填), ...协议自有字段}")
    request : Optional[RequestUnion] = Field(default=None, description= "当前步骤的请求体信息;body 结构由协议定义")
    strategy : list[StrategyUnion] = Field(... , description= "当前步骤需要执行的策略集")

    @property
    def call_protocol(self) -> str:
        """当前步骤的协议名（protocol 必填，恒有值）。"""
        return self.call.protocol


StepUnion = Step


if __name__ == "__main__":
    from .strategy import Extract, StrategyPhase, Scope

    step = Step(
        description="获取测试 token 用于后续鉴权",
        call=Call(protocol="http", service="test", method="GET", path="/test"),
        strategy=[
            Extract(
                name="extract_token",
                phase=StrategyPhase.AFTER_REQUEST,
                expression="$.call.response.body.token",
                target="auth_token",
                scope=Scope.SCENARIO
            )
        ]
    )
    print(f"Step 测试: kind={step.kind}, protocol={step.call_protocol}, strategy count={len(step.strategy)}")
