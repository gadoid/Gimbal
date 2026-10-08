"""dialect.canonical —— 规范序列化与内容寻址 hash（批次 A1，7.1 / 7.2）。

规范序列化规则（修订九①，A1 实现前置，对象 hash / call 投影 hash /
shape_hash 三者共用）：

1. 键序 = M2 模型字段定义序（``model_dump`` 保序，不排序）；
2. **排除等于默认值的字段**（``exclude_defaults=True``）——P8 加法演进下
   新增带默认值的字段不改变未使用它的对象的 hash；否则每次加字段全部
   接口 hash 齐变（适配风暴 + 跨版本对象去重失效）；
3. JSON 紧凑定形（无空白分隔、ensure_ascii=False、utf-8）。

两种 hash（修订九②）：

- ``object_hash``：整对象，用于构件去重与 release 差异；仅存 manifest 与
  快照内存索引，不经 HTTP 暴露。
- ``shape_hash``：只覆盖影响用例值的部分（binding + request / responses
  的声明树），不含 description / metadata / capability / consumes /
  produces / query_views——语义标注不触发适配批次。endpoint id 变更不经
  hash（走 missing_on_plate / 首见基线路径）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

from .models import EndpointSpec


def canonical_payload(model: BaseModel) -> dict[str, Any]:
    """规范 payload：键序 = 模型定义序，排除等于默认值的字段。"""
    return model.model_dump(mode="json", exclude_defaults=True)


def _sorted_dicts(obj):
    """递归排序 dict 键（评审 P0-8：同一对象的 hash 不得依赖文件书写序）。

    模型字段序在各层由 model_dump 保序（键序=定义序的规范形原则不受影响
    ——排序只发生在 hash 输入层，渲染层保持模型定义序）。
    """
    if isinstance(obj, dict):
        return {k: _sorted_dicts(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_sorted_dicts(x) for x in obj]
    return obj


def canonical_bytes(model: BaseModel) -> bytes:
    """规范序列化字节流（hash 输入；紧凑、utf-8、dict 键全排序）。"""
    return json.dumps(
        _sorted_dicts(canonical_payload(model)),
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")


def object_hash(model: BaseModel) -> str:
    """对象 hash：sha256(规范序列化)。内容寻址单位（构件去重、release 差异）。"""
    return hashlib.sha256(canonical_bytes(model)).hexdigest()


# 声明条目中不参与 shape 的说明性字段（评审 P0-11，按评审建议拍板）：
# default / example 保留（影响用例取值）；description / ui_kind 剔除（纯展示）。
_DECL_SHAPE_EXCLUDE = {"description", "ui_kind"}


def _decl_shape(entries: list[Any]) -> list[dict[str, Any]]:
    """声明条目 → shape 投影（递归：嵌套 ``children`` 里的说明性字段同样
    剔除——评审 R8：此前只处理顶层，嵌套 description 改动照样触发适配
    pending，systems/ 有 46 个文件用到 children）。"""
    out: list[dict[str, Any]] = []
    for e in entries:
        d = {k: v for k, v in e.model_dump(mode="json", exclude_defaults=True).items()
             if k not in _DECL_SHAPE_EXCLUDE}
        if e.children:
            d["children"] = _decl_shape(e.children)
        out.append(d)
    return out


def shape_projection(spec: EndpointSpec) -> dict[str, Any]:
    """形状投影：只留 binding 与请求 / 响应声明树（不含语义与展示字段）。

    评审 P0-7：binding 段同样排除缺省值（修订九第①条对嵌套模型生效——
    否则给 Binding 加带默认值字段会改变全部接口的 shape_hash）。
    """
    proj: dict[str, Any] = {
        "binding": spec.binding.model_dump(mode="json", exclude_defaults=True)
    }
    if spec.request is not None and spec.request.declarations:
        proj["request"] = {"declarations": _decl_shape(spec.request.declarations)}
    if spec.responses:
        proj["responses"] = {
            outcome: {"declarations": _decl_shape(resp.declarations)}
            for outcome, resp in sorted(spec.responses.items())
        }
    return proj


def shape_hash(spec: EndpointSpec) -> str:
    """形状 hash：适配中心的变更检测信号（≠ 戳内指纹即 pending）。

    序列化纪律同 ``canonical_bytes``（紧凑、无排序、排除默认值）；与
    对象 hash 的差异仅在覆盖面（投影而非整对象）。
    """
    data = json.dumps(
        _sorted_dicts(shape_projection(spec)),
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
