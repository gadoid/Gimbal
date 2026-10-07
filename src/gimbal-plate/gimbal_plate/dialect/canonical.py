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


def canonical_bytes(model: BaseModel) -> bytes:
    """规范序列化字节流（hash 的输入；紧凑、无排序、utf-8）。"""
    return json.dumps(
        canonical_payload(model), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def object_hash(model: BaseModel) -> str:
    """对象 hash：sha256(规范序列化)。内容寻址单位（构件去重、release 差异）。"""
    return hashlib.sha256(canonical_bytes(model)).hexdigest()


def shape_projection(spec: EndpointSpec) -> dict[str, Any]:
    """形状投影：只留 binding 与请求 / 响应声明树（不含语义与展示字段）。"""
    proj: dict[str, Any] = {"binding": spec.binding.model_dump(mode="json")}
    if spec.request is not None and spec.request.declarations:
        proj["request"] = {"declarations": [
            d.model_dump(mode="json", exclude_defaults=True)
            for d in spec.request.declarations
        ]}
    if spec.responses:
        # 键序：结果键排序（dict 键来自文件声明序，投影侧统一排序保证
        # 同一形状集合不同书写序不产生不同 shape_hash）
        proj["responses"] = {
            outcome: {
                "declarations": [
                    d.model_dump(mode="json", exclude_defaults=True)
                    for d in resp.declarations
                ]
            }
            for outcome, resp in sorted(spec.responses.items())
        }
    return proj


def shape_hash(spec: EndpointSpec) -> str:
    """形状 hash：适配中心的变更检测信号（≠ 戳内指纹即 pending）。

    序列化纪律同 ``canonical_bytes``（紧凑、无排序、排除默认值）；与
    对象 hash 的差异仅在覆盖面（投影而非整对象）。
    """
    payload = shape_projection(spec)
    # binding 内部键序 = 模型定义序（model_dump 保序），无需排序
    data = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
