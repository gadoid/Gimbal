"""管线中间表示(IR):S1..S4 各阶段的流通货币。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


@dataclass
class RuleEntry:
    """Validator 规则行(含被注释行:active=False 但 zh 仍有值)。"""
    key: str
    rules: str
    zh: str = ""
    active: bool = True

    def parts(self) -> list[str]:
        return [p.strip() for p in self.rules.split("|") if p.strip()]

    def hard_required(self) -> bool:
        """require → 值非空(强校验)。"""
        return any(p == "require" for p in self.parts())

    def soft_present(self) -> bool:
        """仅 present → 键要在、值可空(过滤语义;需结合 read 判读)。"""
        return (not self.hard_required()
                and any(p == "present" for p in self.parts()))

    def required(self) -> bool:
        """require|present → 值非空(v1 直译口径,保留给对照)。"""
        return any(p in ("require", "present") for p in self.parts())

    def must_include(self) -> bool:
        """exist → 键必须在(值可空)。"""
        return any(p == "exist" for p in self.parts())

    def enum_values(self) -> list[str] | None:
        for p in self.parts():
            if p.startswith("in:"):
                return [v.strip() for v in p[3:].split(",") if v.strip()]
        return None

    def max_length(self) -> int | None:
        for p in self.parts():
            if p.startswith("length_max:"):
                return int(p.split(":", 1)[1])
        return None


@dataclass
class Read:
    """S2b 键读标记。via ∈ getData|subscript|isset;origin ∈ request|service。"""
    key: str
    default: str | None = None
    via: str = ""
    origin: str = "request"   # 根层(控制器/Validator/持请求直调)=request


@dataclass
class ActionIR:
    module: str
    controller: str          # 类名去 Controller(OrderEntrust)
    action: str
    # S1 填:规则绑定与静态校验/服务调用边
    ruleset: tuple[str, str] | None = None     # (Validator 类名, 属性名如 orderAddRules)
    validator_checks: list[str] = field(default_factory=list)   # checkXxx 方法名
    callees: list[tuple[str, str]] = field(default_factory=list)  # (类名, 方法名)
    # S2 填
    rules: list[RuleEntry] = field(default_factory=list)
    reads: dict[str, Read] = field(default_factory=dict)
    method: str = "POST"
    # S2c 填:FE 无 URL 命中时 method 为假设值(v1 恒 POST 的缺口)
    method_assumed: bool = True
    # S1 尾道:同名控制器跨模块(Policy@Customer/Home)时 id 加模块前缀防撞
    module_scoped: bool = False

    @property
    def path(self) -> str:
        c = self.controller[0].lower() + self.controller[1:]
        return f"/api/{self.module.lower()}/{c}/{self.action}"

    @property
    def id(self) -> str:
        ctrl = (f"{snake(self.module)}_{snake(self.controller)}"
                if self.module_scoped else snake(self.controller))
        return f"fin.{ctrl}.{snake(self.action)}"

    @property
    def const_name(self) -> str:
        return snake(self.controller).upper() + "_" + snake(self.action).upper()


@dataclass
class FieldIR:
    """S3 语义富化 + S4 状态赋值后的单字段全貌。"""
    key: str
    read: bool = False
    required: bool = False
    must_include: bool = False
    zh: str = ""
    zh_source: str = ""            # rule|column|derived|enum|""
    type_: str = "string"
    enum_values: list | None = None
    enum_candidate: str = ""      # T3.2:挂载来源 Enum 类名(报告追溯)
    default: object = None
    col_comment: str = ""
    col_type: str = ""
    tables: list[str] = field(default_factory=list)
    # S4 赋值
    state: str = "carry"
    value_source: tuple[str, str] | None = None   # (view, column)
    flags: list[str] = field(default_factory=list)  # needs_capture:value_source 等
    # S2c 前端面(高置信 form/payload;label 中置信仅 zh 兜底)
    fe_zh: str = ""
    fe_type: str = ""            # 前端控件类型原词(select/upload/...)
    fe_confidence: str = ""      # high|medium|""
    example: str = ""            # FE payload 字面量值(可空串=有键无值)
    # T5.3 行容器:foreach + paramVerification 分组检测命中
    container: bool = False      # 容器条目(type=array,emit 时带 children)
    children: list = field(default_factory=list)   # 子 FieldIR(模板态 path)
