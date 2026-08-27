"""generators dim —— 生成器语法的服务化(第 9 个 dim,语法级)。

对齐 strategy_dim 先例(2026-08-17):items 不是数据实例,而是从
plate 镜像 spec(``schema/generator.py``)内省出的 kind 描述符 ——
回答"生成器有哪些 kind、每个 kind 有哪些参数"。生成器实例照旧存在
scenario 的 ``config.vars`` 里,归平台/用户管;plate 只暴露语法
(结构权威源),永不执行。

权威源约定(双权威,同 strategy):引擎 ``src/gimbal/generator/specs.py``
是执行权威源;镜像手工同步,
``tests/plate/test_generator_dim.py::test_p7_mirror_matches_engine_specs``
防漂移。

依赖方向: http → schema(只读内省),不触碰 no-reverse-import 锁。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gimbal_plate.schema.generator import (
    NowSpec,
    RandomDecoratedSpec,
    RandomDecimalSpec,
    RandomIntSpec,
    RandomStrSpec,
    SeqSpec,
    TimeOffsetSpec,
    TimestampSpec,
    UuidSpec,
)

# kind 清单: 引擎 build_default_registry() 注册的 9 个规范 kind。
# ``sequence`` 是引擎侧历史别名(SeqSpec 内规范化为 seq),目录只列规范名。
_KIND_MODELS: dict[str, type] = {
    "uuid": UuidSpec,
    "random_str": RandomStrSpec,
    "random_int": RandomIntSpec,
    "random_decimal": RandomDecimalSpec,
    "timestamp": TimestampSpec,
    "now": NowSpec,
    "seq": SeqSpec,
    "random_decorated": RandomDecoratedSpec,
    "time_offset": TimeOffsetSpec,
}

# kind 元数据: (中文 summary, 说明, 示例 spec)。schema 不编码这三者,
# 在此单一维护 —— 与 strategy_dim._KIND_LABELS 同一拍板。
_KIND_META: dict[str, tuple[str, str, dict[str, Any]]] = {
    "uuid": (
        "UUID",
        "生成 32 位十六进制 UUID 字符串。无参数,声明 {\"kind\": \"uuid\"} 即可。",
        {"kind": "uuid"},
    ),
    "random_str": (
        "随机字符串",
        "按字符集生成定长随机字符串。charset: alpha=纯字母 / digit=纯数字 / alnum=字母数字。",
        {"kind": "random_str", "length": 8, "charset": "alnum"},
    ),
    "random_int": (
        "闭区间随机整数",
        "生成 [min, max] 闭区间内的随机整数。",
        {"kind": "random_int", "min": 0, "max": 100},
    ),
    "random_decimal": (
        "闭区间随机小数",
        "生成 [min, max] 闭区间内的随机小数;places 控制小数位数(0-10)。",
        {"kind": "random_decimal", "min": 0.0, "max": 100.0, "places": 2},
    ),
    "timestamp": (
        "格式化时间戳",
        "按 format 输出时间(默认 iso=ISO-8601);offset_seconds 相对当前时间偏移;"
        "base/base_format 可锚定自定义基准时间。",
        {"kind": "timestamp", "format": "iso", "offset_seconds": 0},
    ),
    "now": (
        "当前时间",
        "按 format 输出当前时间:epoch=Unix 秒 / iso=ISO-8601 / compact=紧凑数字串。"
        "比 timestamp 更轻,无偏移与基准参数。",
        {"kind": "now", "format": "iso"},
    ),
    "seq": (
        "自增序号",
        "执行内自增序号:prefix 前缀 + width 位零填充,从 start 起。"
        "引擎历史别名 sequence 会规范化为 seq,目录只列规范名。",
        {"kind": "seq", "prefix": "BL", "width": 6, "start": 1},
    ),
    "random_decorated": (
        "装饰随机串",
        "head + 随机串 + tail,段间以 separator 连接 —— 适合业务单号"
        "(如 GIMBAL728-XXXXXX)。",
        {
            "kind": "random_decorated", "length": 6, "charset": "alnum",
            "head": "GIMBAL728", "tail": "", "separator": "-",
        },
    ),
    "time_offset": (
        "偏移时间戳",
        "以 unit 粒度把基准时间(默认当前)向 direction 偏移 value 步,生成对应时间戳;"
        "单位覆盖 milliseconds 到 years 八种。",
        {"kind": "time_offset", "unit": "days", "value": 30, "direction": "future"},
    ),
}


def _prop_type(prop: dict[str, Any]) -> str:
    """JSON Schema 属性 → 参数类型字符串。

    Literal 字段内联 ``enum`` + ``type``;``str | None`` 可选字段产出
    ``anyOf: [{type: string}, {type: null}]`` —— 取非 null 分支。
    """
    if "enum" in prop:
        return "string"
    t = prop.get("type")
    if isinstance(t, str):
        return t
    for sub in prop.get("anyOf", []):
        st = sub.get("type")
        if isinstance(st, str) and st != "null":
            return st
    return "string"


def _params_from_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """从镜像 spec 的 JSON Schema 派生参数描述符(剔除 kind 判别字段)。

    ge/le → minimum/maximum → min/max;全部字段有默认值 ⇒ required 恒 False
    (如实暴露,管理页表单按默认值渲染)。
    """
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    out: list[dict[str, Any]] = []
    for name, prop in props.items():
        if name == "kind" or not isinstance(prop, dict):
            continue
        out.append(
            {
                "name": name,
                "type": _prop_type(prop),
                "required": name in required,
                "default": prop.get("default"),
                "enum": prop["enum"] if "enum" in prop else None,
                "min": prop.get("minimum"),
                "max": prop.get("maximum"),
                "description": str(prop.get("description") or ""),
            }
        )
    return out


@dataclass(frozen=True)
class _KindDescriptor:
    kind: str
    summary: str
    description: str
    params: list[dict[str, Any]]
    example: dict[str, Any]


def _descriptor_for(kind: str) -> _KindDescriptor | None:
    model = _KIND_MODELS.get(kind)
    if model is None:
        return None
    summary, description, example = _KIND_META[kind]
    return _KindDescriptor(
        kind=kind,
        summary=summary,
        description=description,
        params=_params_from_schema(model.model_json_schema()),
        example=example,
    )


class GeneratorIndex:
    """BaseIndex 实现 —— items 是 kind 描述符(语法级 dim,非数据)。

    ``list_for_system`` 无视 system 参数返回全量: 生成器语法是全局的
    (同 strategy 先例)。``registry`` 形参仅为对齐 BaseIndex 构造约定,
    内省不依赖它。
    """

    def __init__(self, registry: Any = None) -> None:  # noqa: ARG002
        self._descriptors: dict[str, _KindDescriptor] = {
            k: d for k in _KIND_MODELS if (d := _descriptor_for(k)) is not None
        }

    def list_global(self, *, filters: dict[str, Any] | None = None) -> list[_KindDescriptor]:
        return list(self._descriptors.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[_KindDescriptor]:
        return list(self._descriptors.values())

    def get(self, item_id: str) -> _KindDescriptor | None:
        return self._descriptors.get(item_id)

    def to_view(self, item: _KindDescriptor) -> dict[str, Any]:
        return {"kind": item.kind, "summary": item.summary}
