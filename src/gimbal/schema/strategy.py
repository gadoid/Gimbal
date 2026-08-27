from pydantic import BaseModel, Field 
from typing import Any , Optional , Literal, Union, Annotated, List
from enum import Enum
from .ref import RefBase

class Scope(str, Enum):
    FRAMEWORK = "framework"
    SESSION = "session"
    SCENARIO = "scenario"
    STEP = "step"
    REQUEST = "request"

class AssertOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EXISTS  = "exists"
    EMPTY = "empty"
    LENGTH_EQ = "length_eq"
    SCHEMA = "schema"
    # JSON_EQUAL = "json_equal"
    # MATCHES = "matches"

class StrategyPhase(str, Enum):
    BEFORE_REQUEST = "before_request"   # SQL 注入数据、Assign 准备入参
    AFTER_REQUEST = "after_request"     # Extract 提取字段
    VERIFYING = "verifying"             # Assertion、DBChecker
    TEARDOWN = "teardown"               # SQL 清理、Chaos 恢复

class FailurePolicy(str, Enum):
    ABORT = "abort"          # 中止整个 step
    CONTINUE = "continue"    # 记录错误但继续
    WARN = "warn"            # 仅警告
    RETRY = "retry"          # 配合 retry 字段

class StrategyBase(BaseModel) :
    name : Optional[str] = None
    phase : Optional[StrategyPhase] = None           # 处理的阶段
    order : int = 0   # 执行顺序
    enabled : bool = True  # 是否启动
    onFailure : FailurePolicy = FailurePolicy.ABORT  #失败处理策略
    timeout : Optional[float] = None   # 策略执行超时
    # condition : Optional[str] = None   # 条件表达式
    tags : List[str] =  Field(default_factory=list)  # 标签

class Extract(StrategyBase) :
    kind : Literal["extract"] = "extract"
    # phase 缺省按 kind 落默认值：dispatch_phase 严格按 phase 过滤，
    # 不给默认时未声明 phase 的策略会被静默跳过（Composer 导出的
    # extract/断言曾因此全部不执行）。extract 提取响应字段 → post-response。
    phase : StrategyPhase = StrategyPhase.AFTER_REQUEST
    expression: str          # JSONPath，在 scratch 上导航
    target: str              # 写入目标的 key
    scope: Scope = Scope.STEP
    default: Optional[Any] = None
    required: bool = True

class Assign(StrategyBase) :
    kind : Literal["assign"] = "assign"
    # assign 准备入参 → pre-request（与 StrategyPhase 注释语义一致）。
    phase : StrategyPhase = StrategyPhase.BEFORE_REQUEST
    source : Any # 路径或者值
    target : str # 模板路径
    scope: Scope = Scope.SCENARIO # 如果source为空则从对应的作用域检查是否存在同名字段提取数据
    default : Optional[Any] = None # 提取失败，注入的默认值
    required : bool = True # 注入失败是否抛出异常

class Assertion(StrategyBase) :
    kind : Literal["assertion"] = "assertion"
    # 断言默认落 verifying 阶段；显式声明其它 phase 仍然生效（覆盖默认）。
    phase : StrategyPhase = StrategyPhase.VERIFYING
    target : str # 断言的目标字段
    operator : AssertOperator # 断言的比较符
    expected : Any = None # 断言的比较值
    message : Optional[str] = None # 断言失败信息
    soft: bool = False # 软断言

class StrategyRef(RefBase) : 
    kind : Literal["strategy_ref"] = "strategy_ref"


StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion, StrategyRef],
    Field(discriminator="kind")
]


if __name__ == "__main__":
    # 测试枚举类
    print(f"Scope 测试: {Scope.SCENARIO.value}")
    print(f"AssertOperator 测试: {AssertOperator.EQ.value}")
    print(f"StrategyPhase 测试: {StrategyPhase.BEFORE_REQUEST.value}")
    print(f"FailurePolicy 测试: {FailurePolicy.ABORT.value}")

    # 测试 StrategyBase 实例化
    strategy_base = StrategyBase(name="base_strategy")
    print(f"StrategyBase 测试: name={strategy_base.name}")

    # 测试 Extract 实例化
    extract = Extract(
        expression="$.response_body.data.id",
        target="data_id",
        scope=Scope.SCENARIO
    )
    print(f"Extract 测试: expression={extract.expression}, target={extract.target}")

    # 测试 Assign 实例化
    assign = Assign(
        source="fixed_value",
        target="output_field",
        scope=Scope.STEP
    )
    print(f"Assign 测试: source={assign.source}, target={assign.target}")

    # 测试 Assertion 实例化
    assertion = Assertion(
        target="response.status",
        operator=AssertOperator.EQ,
        expected=200
    )
    print(f"Assertion 测试: target={assertion.target}, operator={assertion.operator}")

    # 测试 StrategyRef 实例化
    strategy_ref = StrategyRef(ref="strategy_ref_1")
    print(f"StrategyRef 测试: ref={strategy_ref.ref}")