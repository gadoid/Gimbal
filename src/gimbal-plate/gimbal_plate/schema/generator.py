"""plate 侧生成器 spec 镜像 —— 常量池目录的内省源(2026-08-26)。

权威源约定(双权威手工同步,同 strategy):
引擎 ``src/gimbal/generator/specs.py`` 是执行权威源;本文件是其字段/
约束/默认值的 1:1 镜像,仅供 ``http/generator_dim.py`` 内省出 kind
参数描述符 —— plate 永不执行生成器,生成器实例照旧存在 scenario 的
``config.vars`` 里。引擎变更时手工同步本文件;
``tests/plate/test_generator_dim.py::test_p7_mirror_matches_engine_specs``
是失效触发器。

镜像规则:
- 只镜像字段/类型/约束/默认值,不镜像 validator(SeqSpec 的
  ``sequence`` 别名规范化属引擎行为,目录只列规范 kind);
- ``extra="forbid"`` 与引擎一致(未知参数引擎侧报错,目录如实反映);
- 描述文案是 plate 侧说明,不追求与引擎 docstring 逐字一致。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UuidSpec(BaseModel):
    """uuid — 32 位十六进制 UUID 字符串(无参数)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["uuid"]


class RandomStrSpec(BaseModel):
    """random_str — 定长随机字符串(charset: alpha/digit/alnum)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_str"]
    length: int = Field(default=8, ge=1, le=1024, description="随机串长度")
    charset: Literal["alpha", "digit", "alnum"] = Field(
        default="alnum", description="字符集"
    )


class RandomIntSpec(BaseModel):
    """random_int — [min, max] 闭区间随机整数。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_int"]
    min: int = Field(default=0, description="下界(含)")
    max: int = Field(default=100, description="上界(含)")


class RandomDecimalSpec(BaseModel):
    """random_decimal — [min, max] 闭区间随机小数。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_decimal"]
    min: float = Field(default=0.0, description="下界(含)")
    max: float = Field(default=100.0, description="上界(含)")
    places: int = Field(default=2, ge=0, le=10, description="小数位数")


class TimestampSpec(BaseModel):
    """timestamp — 格式化时间戳(可偏移/可锚定基准)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["timestamp"]
    format: str = Field(default="iso", description="输出格式,iso=ISO-8601")
    offset_seconds: int = Field(default=0, description="相对当前时间的偏移秒数")
    base: str | None = Field(default=None, description="自定义基准时间")
    base_format: str | None = Field(default=None, description="基准时间的解析格式")


class NowSpec(BaseModel):
    """now — 当前时间(epoch 秒 / iso / compact)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["now"]
    format: Literal["epoch", "iso", "compact"] = Field(
        default="iso", description="输出格式"
    )


class SeqSpec(BaseModel):
    """seq — 执行内自增序号(引擎历史别名 sequence 规范化为 seq)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["seq"]
    prefix: str = Field(default="", description="序号前缀")
    width: int = Field(default=6, ge=1, le=20, description="零填充宽度")
    start: int = Field(default=1, description="起始值")


class RandomDecoratedSpec(BaseModel):
    """random_decorated — head + 随机串 + tail,段间 separator 连接。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_decorated"]
    length: int = Field(default=8, ge=1, le=1024, description="随机段长度")
    charset: Literal["alpha", "digit", "alnum"] = Field(
        default="alnum", description="随机段字符集"
    )
    head: str = Field(default="", description="头部装饰段")
    tail: str = Field(default="", description="尾部装饰段")
    separator: str = Field(default="", description="段间连接符")


class TimeOffsetSpec(BaseModel):
    """time_offset — 以 unit 粒度向 direction 偏移 value 步的时间戳。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["time_offset"]
    unit: Literal[
        "milliseconds", "seconds", "minutes", "hours",
        "days", "weeks", "months", "years",
    ] = Field(default="seconds", description="偏移单位")
    value: int = Field(default=0, description="偏移量")
    direction: Literal["future", "past"] = Field(
        default="future", description="偏移方向"
    )
    base: str | None = Field(default=None, description="自定义基准时间")
    base_format: str | None = Field(default=None, description="基准时间的解析格式")
