"""schema/param_registry.py — 参数登记表(N3/定稿 D8,P3-08)。

每个可配置参数声明:级别(suite/unit/call)、合并方式(override/deep/
keyed)、允许来源(source/suite_patch/unit_patch/call_param/cli_var)、
作用范围。``p_patch`` 按登记表逐字段分派合并策略;值来源追踪
(``ValueSourceTrace``)记录「哪个层改了什么」。

五层补丁(D-04 定稿):
    L0 source        源场景 config(vars/setup/teardown/services/users)
    L1 suite_patch   graph 级补丁(C5 编排面)
    L2 unit_patch    单元 inputs(字面量注入)
    L3 call_param    调用参数(平台 RunRequest 下发面)
    L4 cli_var       CLI --var(N3 起从 extras 旁路并入本层)

登记表是**声明性**的(合并代数由 p_patch 单测钉死,登记表只决定每个
字段走哪种代数),运行期不可变。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ParamLevel(str, Enum):
    SUITE = "suite"
    UNIT = "unit"
    CALL = "call"


class ParamMerge(str, Enum):
    OVERRIDE = "override"    # 后层整名覆盖(vars 用此语义:dict 值整体换)
    DEEP = "deep"            # dict 深合并(services 等配置对象)
    KEYED = "keyed"          # 按 (kind, key) 身份合并(setup/teardown 表)


class ParamSource(str, Enum):
    SOURCE = "source"               # L0 源场景
    SUITE_PATCH = "suite_patch"     # L1 graph 级
    UNIT_PATCH = "unit_patch"       # L2 单元 inputs
    CALL_PARAM = "call_param"       # L3 调用参数
    CLI_VAR = "cli_var"             # L4 --var


# 层序(浅 → 深;后层覆盖前层)
LAYER_ORDER: tuple[ParamSource, ...] = (
    ParamSource.SOURCE,
    ParamSource.SUITE_PATCH,
    ParamSource.UNIT_PATCH,
    ParamSource.CALL_PARAM,
    ParamSource.CLI_VAR,
)


class ParamDecl(BaseModel):
    """单条参数登记:字段名 + 合并规则 + 允许来源。"""
    name: str                     # config 字段名(如 "vars" / "setup")
    level: ParamLevel
    merge: ParamMerge
    sources: tuple[ParamSource, ...]
    scope: str = "config"         # config / unit / call


class ValueSourceEntry(BaseModel):
    """值来源追踪的单条记录(N3:生效副本可产出「哪个层改了什么」)。"""
    param: str
    source: ParamSource
    old: Any = None
    new: Any = None


class ValueSourceTrace(BaseModel):
    """一次 p_patch 的值来源全集。"""
    entries: list[ValueSourceEntry] = Field(default_factory=list)

    def note(self, param: str, source: ParamSource,
             old: Any, new: Any) -> None:
        if old != new:
            self.entries.append(ValueSourceEntry(
                param=param, source=source, old=old, new=new))

    def summary(self) -> dict[str, str]:
        """param → 最终写入来源(最深层)。"""
        out: dict[str, str] = {}
        for e in self.entries:
            out[e.param] = e.source.value
        return out


# ── 登记表(全仓唯一;新增可配置字段必须在此登记)────────────────

PARAM_REGISTRY: dict[str, ParamDecl] = {
    d.name: d for d in [
        # vars:整名覆盖(dict 值整体换,不做部分深合并 —— 「整名覆盖」
        # 语义是 D8 定稿:半覆盖 dict 值会让生成式 spec 被拆坏)
        ParamDecl(name="vars", level=ParamLevel.SUITE, merge=ParamMerge.OVERRIDE,
                  sources=LAYER_ORDER),
        # setup/teardown:按 (kind,key) 身份合并
        ParamDecl(name="setup", level=ParamLevel.SUITE, merge=ParamMerge.KEYED,
                  sources=LAYER_ORDER),
        ParamDecl(name="teardown", level=ParamLevel.SUITE, merge=ParamMerge.KEYED,
                  sources=LAYER_ORDER),
        # services:深合并(同名服务键的字段级覆盖)
        ParamDecl(name="services", level=ParamLevel.SUITE, merge=ParamMerge.DEEP,
                  sources=LAYER_ORDER),
        # users:深合并(同名标签的字段级覆盖)
        ParamDecl(name="users", level=ParamLevel.SUITE, merge=ParamMerge.DEEP,
                  sources=LAYER_ORDER),
        # timePolicy/retry:整覆盖(策略对象不部分合并)
        ParamDecl(name="timePolicy", level=ParamLevel.SUITE,
                  merge=ParamMerge.OVERRIDE, sources=LAYER_ORDER),
        ParamDecl(name="retry", level=ParamLevel.SUITE,
                  merge=ParamMerge.OVERRIDE, sources=LAYER_ORDER),
    ]
}


def merge_of(field_name: str) -> ParamMerge:
    """字段名 → 合并策略(未登记字段默认 override)。"""
    decl = PARAM_REGISTRY.get(field_name)
    return decl.merge if decl else ParamMerge.OVERRIDE


def source_allowed(field_name: str, source: ParamSource) -> bool:
    """字段名 × 来源 → 是否允许写入(登记表拒未声明来源)。"""
    decl = PARAM_REGISTRY.get(field_name)
    if decl is None:
        return True    # 未登记字段不限制来源(自由补丁面)
    return source in decl.sources
