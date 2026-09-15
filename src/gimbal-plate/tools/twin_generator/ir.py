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

    def required(self) -> bool:
        """require|present → 值非空(present 的 status 豁免分支按非空对待)。"""
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
    """S2b 键读标记。via ∈ getData|subscript|isset。"""
    key: str
    default: str | None = None
    via: str = ""


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

    @property
    def path(self) -> str:
        c = self.controller[0].lower() + self.controller[1:]
        return f"/api/{self.module.lower()}/{c}/{self.action}"

    @property
    def id(self) -> str:
        return f"fin.{snake(self.controller)}.{snake(self.action)}"

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
    default: object = None
    col_comment: str = ""
    col_type: str = ""
    tables: list[str] = field(default_factory=list)
    # S4 赋值
    state: str = "carry"
    value_source: tuple[str, str] | None = None   # (view, column)
    flags: list[str] = field(default_factory=list)  # needs_capture:value_source 等
