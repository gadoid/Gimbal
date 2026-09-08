"""schema.endpoint.query_view —— 取数视图注记与字段绑定(spec 2026-09-07 §3.1/§3.2)。

QueryView 是普通端点定义上的行集视图注记:method/path/请求缺省全部复用端点
声明(单一真源),本注记只补固定过滤预设(params)与行集提取呈现(items/label)。
ValueSource 是字段绑定:字段值可经视图组合期查询得到,选择后钉字面量落 body。
词表封闭(§4.3):v1 仅 items 提取 + label/列投影,无 transforms 键。
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:  # 仅类型引用,运行时零依赖(避免与 endpoint/io_spec 循环 import)
    from gimbal_plate.schema.endpoint.endpoint import EndpointSpec

# view name 标识符规则:与 io_spec _NAME_RE 同式(四重身份 §3.5,命名不可变)
_QV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class QueryView(BaseModel):
    """端点作为取数配方时的行集视图(§3.1)。

    params 是声明缺省(default ▸ example 链)之上的固定过滤预设
    (如 entrust_status=1 的"待委托"视图);GET → querystring /
    POST → JSON body 由解释器按端点 ApiSpec 分流(§4.2)。
    """

    model_config = ConfigDict(extra="forbid")

    name: str                              # 全局唯一(跨端点);四重身份见 §3.5
    params: dict[str, Any] | None = None
    items: str                             # 响应行集 JSONPath,如 '$.data.list[*]'
    label: str                             # 选择器显示列(行内键)

    @model_validator(mode="after")
    def _validate(self) -> "QueryView":
        if not _QV_NAME_RE.match(self.name):
            raise ValueError(
                f"QueryView.name={self.name!r} 须为 ASCII 标识符"
                f"([A-Za-z_][A-Za-z0-9_]*,命名不可变 §3.5)"
            )
        if not self.items.startswith("$."):
            raise ValueError(
                f"QueryView.items={self.items!r} 须为 JSONPath 形态($. 开头)"
            )
        if not self.label:
            raise ValueError("QueryView.label 不可为空(选择器显示列)")
        return self


class ValueSource(BaseModel):
    """字段绑定(§3.2):view=查询身份(查哪张表),group=选择身份(哪次业务占用)。

    group 空 = 缺省取 view name(单一用途场景零配置零行为变化);
    同 view 多角色时各赋不同 group(建议 `<view>#<role>`)拆独立选择器。
    group 是纯前端消歧机制:不进解释器语义/场景产物/徽标(§3.2 可见性边界)。
    """

    model_config = ConfigDict(extra="forbid")

    view: str         # QueryView.name(全局唯一引用)
    column: str = ""  # 行内取值列;空 = label 列(N=1 退化)
    group: str = ""   # 显式分组键;空 = 缺省取 view name

    @model_validator(mode="after")
    def _validate(self) -> "ValueSource":
        if not self.view:
            raise ValueError("ValueSource.view 不可为空(QueryView.name 引用)")
        return self


def resolve_view_params(
    spec: "EndpointSpec", view: QueryView
) -> tuple[dict[str, Any], list[str]]:
    """view.params ▸ 声明 default ▸ 声明 example 的 per-key 合成(§4.2)。

    返回 (merged, missing_required):
    - view.params 覆盖同名声明键、追加未声明键(如 entrust_status 未声明则追加);
    - 声明键取 default(非 None)否则 example(非 None);
    - 双 None:必填键 → missing_required(端点构造期拒,§3.3⑤);
      可选键 → 不携带(缺省不携带)。
    "缺" = default 与 example 双 None;空串/0/false 是合法值,不算缺。
    键 = 顶层声明 path 去掉 '$.' 前缀。
    """
    merged: dict[str, Any] = dict(view.params or {})
    missing: list[str] = []
    if spec.request is not None:
        for entry in spec.request.declarations:
            key = entry.path[2:] if entry.path.startswith("$.") else entry.path
            if key in merged:
                continue
            if entry.default is not None:
                merged[key] = entry.default
            elif entry.example is not None:
                merged[key] = entry.example
            elif entry.required:
                missing.append(key)
    return merged, missing
