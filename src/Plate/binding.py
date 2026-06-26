"""字段绑定(PR-D2 / PLATE_DESIGN §2.2 + §3.5)。

职责:声明性字段绑定,描述"端点 A 依赖端点 B 的某个字段"。
本模块**只**定义数据类 + 校验,不规定"如何注入/调用顺序"——那是 PR-D4
及 service 编排的事。

设计要点(对应 PLATE_DESIGN §2.2 + §3.5):
  * **声明性 vs 命令性**:只描述"取哪儿→注入哪儿",不描述"如何注入"
    "何时调用"。这避免和"调用编排"耦合。
  * **logical path 复用 PR-D1**:`from_path` / `to_path` 都是 logical schema
    path(空 tuple 表示整个 body)。PR-D1 的 ``resolve_logical_path`` 必装。
  * **transform 暂不解析**:`transform` 是描述性字符串,本模块**不**做语义
    执行;只通过 ``_KNOWN_TRANSFORMS`` 白名单防拼写错误。
  * **@final + frozen=True** + ``tuple`` 字段:不可变 + 可哈希,可让
    ``EndpointSpec`` 整体作 dict key(后续 spec dedup 用)。

业务价值:
  * 让 AI skill 知道"调 B 之前必须先调 A"
  * 让 CT 主动保活排探测顺序
  * 让 Mock server 自动按依赖注入请求体
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import final


# ════════════════════════════════════════════════════════════════════════════
# transform 白名单
# ════════════════════════════════════════════════════════════════════════════


_KNOWN_TRANSFORMS: frozenset[str] = frozenset(
    {
        "identity",          # 直接赋值,无转换
        "int->str",          # int → str(典型:order_id 注入到下游 string 字段)
        "str->int",          # str → int
        "iso8601->epoch",    # 时间戳转换
        "epoch->iso8601",    # 反向
    }
)


# ════════════════════════════════════════════════════════════════════════════
# FieldBinding
# ════════════════════════════════════════════════════════════════════════════


@final
@dataclass(frozen=True)
class FieldBinding:
    """声明性字段绑定:从 ``from_path`` 取出值,注入到 ``to_path``。

    对应设计:PLATE_DESIGN.md §2.2 + §3.5

    关键约束:
      * ``from_path`` / ``to_path`` 是 logical schema path(空 tuple 表示整个 body)
      * 仅描述依赖关系,不规定调用顺序/注入时机
      * ``transform`` 是描述性字符串,本模块**不**解析语义(白名单校验)
      * ``required=True``(默认):注入失败硬错;``False``:静默跳过
    """

    from_path: tuple[str, ...]
    to_path: tuple[str, ...]
    required: bool = True
    transform: str | None = None

    # ── 序列化(PR-2.0)──
    #
    # tuple → list(JSON 数组无 tuple 概念)
    # 反序列化 list → tuple

    def to_dict(self) -> dict:
        """序列化为 dict。

        字段约定:
          from_path/to_path 是 list(不是 tuple,JSON 不区分)
          其余字段直传
        """
        return {
            "from_path": list(self.from_path),
            "to_path": list(self.to_path),
            "required": self.required,
            "transform": self.transform,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FieldBinding":
        """从 dict 反序列化。严格不容错。"""
        if not isinstance(d, dict):
            raise TypeError(
                f"FieldBinding.from_dict: 期望 dict,实际 {type(d).__name__}"
            )
        for required in ("from_path", "to_path"):
            if required not in d:
                raise KeyError(
                    f"FieldBinding.from_dict: 缺失字段 {required!r}"
                )
        from_path = d["from_path"]
        to_path = d["to_path"]
        if not isinstance(from_path, (list, tuple)):
            raise TypeError(
                f"FieldBinding.from_dict: from_path 必须是 list/tuple,"
                f"实际 {type(from_path).__name__}"
            )
        if not isinstance(to_path, (list, tuple)):
            raise TypeError(
                f"FieldBinding.from_dict: to_path 必须是 list/tuple,"
                f"实际 {type(to_path).__name__}"
            )
        return cls(
            from_path=tuple(from_path),
            to_path=tuple(to_path),
            required=bool(d.get("required", True)),
            transform=d.get("transform"),
        )


__all__ = [
    "FieldBinding",
    "_KNOWN_TRANSFORMS",
]
