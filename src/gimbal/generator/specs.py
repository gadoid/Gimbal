"""gimbal/generator/specs.py

7 个生成器的 Pydantic Spec + VarSpec 联合体（discriminated by 'kind'）。

设计要点：
  - 每个 Spec 用 extra='forbid'，拼写错误立即报错
  - 用 Literal 限定 enum 字段（charset / format）
  - 用 Field(ge=, le=) 限定数值范围
  - VarSpec = Annotated[Union[...], Field(discriminator="kind")]
"""
from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, ConfigDict, TypeAdapter


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

    内部用 TypeAdapter 包装 _VarSpecUnion，对外提供与 BaseModel 一致的 model_validate 接口。
    """
    _adapter: TypeAdapter = TypeAdapter(_VarSpecUnion)

    @classmethod
    def model_validate(cls, data):
        return cls._adapter.validate_python(data)

    @classmethod
    def model_dump(cls, instance, **kwargs):
        return cls._adapter.dump_python(instance, **kwargs)
