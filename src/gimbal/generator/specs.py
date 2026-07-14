"""gimbal/generator/specs.py

7 个生成器的 Pydantic Spec + VarSpec 联合体（discriminated by 'kind'）。

设计要点：
  - 每个 Spec 用 extra='forbid'，拼写错误立即报错
  - 用 Literal 限定 enum 字段（charset / format）
  - 用 Field(ge=, le=) 限定数值范围
  - VarSpec = Annotated[Union[...], Field(discriminator="kind")]
  - ``SeqSpec`` 兼容 ``kind: "sequence"``（gimbal-platform 早期文档与历史
    yaml 一直用这个名字），自动规范化为 ``"seq"``，避免 union_tag_invalid。
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, ConfigDict, TypeAdapter, model_validator


class UuidSpec(BaseModel):
    """kind=uuid：32 位 hex"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["uuid"] = "uuid"


class RandomStrSpec(BaseModel):
    """kind=random_str：随机字符串"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["random_str"] = "random_str"
    length: int = Field(default=8, ge=1, le=1024, description="字符串长度")
    charset: Literal["alpha", "digit", "alnum"] = Field(default="alnum", description="字符集")


class RandomIntSpec(BaseModel):
    """kind=random_int：闭区间整数"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["random_int"] = "random_int"
    min: int = Field(default=0, description="下界（包含）")
    max: int = Field(default=100, description="上界（包含）")


class RandomDecimalSpec(BaseModel):
    """kind=random_decimal：闭区间小数"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["random_decimal"] = "random_decimal"
    min: float = Field(default=0.0, description="下界")
    max: float = Field(default=100.0, description="上界")
    places: int = Field(default=2, ge=0, le=10, description="小数位数")


class TimestampSpec(BaseModel):
    """kind=timestamp：当前时间 + 偏移"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["timestamp"] = "timestamp"
    format: Literal["epoch", "iso", "compact"] = Field(default="iso")
    offset_seconds: int = Field(default=0, description="相对 now 的偏移（正=未来）")


class NowSpec(BaseModel):
    """kind=now：当前时间（无偏移）"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["now"] = "now"
    format: Literal["epoch", "iso", "compact"] = Field(default="iso")


class SeqSpec(BaseModel):
    """kind=seq：自增序号 + 业务前缀"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["seq"] = "seq"
    prefix: str = Field(default="", description="业务前缀，如 'YWDD'")
    width: int = Field(default=6, ge=1, le=20, description="序号位数（不足补 0）")
    start: int = Field(default=1, description="起始值")

    @model_validator(mode="before")
    @classmethod
    def _accept_sequence_alias(cls, data: Any) -> Any:
        """Accept ``{"kind": "sequence", ...}`` as an alias for ``"seq"``.

        Background: gimbal-platform's old documentation and rendered
        yamls (pre-2026-07) used ``kind: sequence``.  This shim lets
        existing case files load without manual rewrites while the
        canonical key remains ``"seq"`` going forward.
        """
        if isinstance(data, dict) and data.get("kind") == "sequence":
            data = {**data, "kind": "seq"}
        return data


# ── 联合体（discriminated by 'kind'）──

_VarSpecUnion = Annotated[
    Union[
        UuidSpec,
        RandomStrSpec,
        RandomIntSpec,
        RandomDecimalSpec,
        TimestampSpec,
        NowSpec,
        SeqSpec,
    ],
    Field(discriminator="kind"),
]


class VarSpec:
    """VarSpec = discriminated union (by 'kind')，对外暴露 model_validate / model_dump。

    为什么是 class 而不是裸的 `Annotated[Union[...], Field(discriminator="kind")]`？
      - 裸 Annotated[...] 是 typing 构造，没有 model_validate 方法
      - 但下游调用方（Task 5 engine / Task 10 preprocessor）需要 `VarSpec.model_validate(dict)`
        这样的 BaseModel-like API 来校验 scenario.config.vars 里的 dict 项
      - 因此在 _VarSpecUnion 之上包一层 TypeAdapter，对外暴露 classmethod

    与 src/gimbal/schema/*Union 的差异：schema 那边是 TypeAdapter 包装在使用方
    （如 asset_materializer.py:65-74），这里选择在使用方直接调用更省事。

    Aliases: ``"sequence"`` is mapped to ``"seq"`` here BEFORE the union
    discriminator runs (per-model ``mode='before'`` validators fire AFTER
    the tag is selected, so they cannot catch an unknown tag).
    """
    _adapter: TypeAdapter = TypeAdapter(_VarSpecUnion)
    _KIND_ALIASES: dict[str, str] = {"sequence": "seq"}

    @classmethod
    def _normalize_kind(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("kind"), str):
            aliased = cls._KIND_ALIASES.get(data["kind"])
            if aliased is not None:
                data = {**data, "kind": aliased}
        return data

    @classmethod
    def model_validate(cls, data: Any) -> Any:
        return cls._adapter.validate_python(cls._normalize_kind(data))

    @classmethod
    def model_dump(cls, instance: BaseModel, **kwargs: Any) -> Any:
        return cls._adapter.dump_python(instance, **kwargs)
