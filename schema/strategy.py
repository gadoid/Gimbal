from pydantic import BaseModel, Field , ConfigDict
from typing import Any , Optional , Literal, Union, Annotated, List, Dict
from enum import Enum

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

class ExtractSource(str, Enum):
    RESPONSE_BODY = "response_body"
    RESPONSE_HEADER = "response_header"
    REQUEST_BODY = "request_body"
    REQUEST_HEADER = "request_header"

class Strategy(BaseModel) :
    type : str 
    name : Optional[str] = None             
    phase : Optional[str] = None           # 处理的阶段
    order : int = 0   # 执行顺序
    enabled : bool = True  # 是否启动
    on_failure : FailurePolicy = FailurePolicy.ABORT  #失败处理策略
    timeout : Optional[float] = None   # 策略执行超时
    # condition : Optional[str] = None   # 条件表达式
    tags : List[str] = [] # 标签

class Extract(Strategy) :
    type : Literal["extract"] = "extract"   
    source : ExtractSource  # 提取源 枚举类
    expression : str # 提取路径
    target : str # 写入上下文中的字段信息
    scope : Scope = Scope.SCENARIO # 提取后注入到对应的作用域
    default : Optional[Any] = None # 提取失败的默认值
    required : bool = True # 提取失败是否抛出异常

class Assign(Strategy) :
    type : Literal["assign"] = "assign"
    source : Any # 路径或者值
    target : str # 模板路径
    scope: Scope = Scope.SCENARIO # 如果source为空则从对应的作用域检查是否存在同名字段提取数据
    default : Optional[Any] = None # 提取失败，注入的默认值
    required : bool = True # 注入失败是否抛出异常

class Assertion(Strategy) :
    type : Literal["assertion"] = "assertion"
    target : str # 断言的目标字段
    operator : AssertOperator # 断言的比较符
    expected : Any = None # 断言的比较值
    message : Optional[str] = None # 断言失败信息
    soft: bool = False # 软断言

StrategyUnion = Annotated[
    Union[Extract, Assign, Assertion],
    Field(discriminator="type")
]

# class Composite(Strategy) :
#     pass

# class Sql(Strategy) :
#     type : Literal["sql"] = "sql"
#     source : 

# class Poll(Strategy) :
#     pass

# class Chaos(Strategy) :
#     pass