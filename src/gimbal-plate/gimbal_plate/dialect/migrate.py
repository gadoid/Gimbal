"""dialect.migrate —— 存量 Python 实例 → Markdown 方言（批次 A1，第 5 节）。

这是对**已评审内容的格式转换**（非自动生成）：确定性脚本把现有
EndpointSpec ``model_dump`` → Markdown，等价校验作为评审依据（白名单见
 ``WHITELIST_NOTES``）。转换后信封一律 ``reviewed``（修订四：迁移内容
 = 已评审内容的格式转换）。

字段映射（6.2 已定）：
- ``api: ApiSpec`` → ``binding: HttpBinding``（protocol/method/path/headers/
  timeout_seconds/auth；``body_type`` 自 RequestSpec 移入）；
- ``responses`` 键 int → str（N1：键即 outcome，三位数字字符串）；
- 删除 ``version`` / ``updated_at``（8n：版本归 release，历史归 git）；
- ``consumes`` / ``produces`` 语义重定义为词条引用，存量 MIME 取值弃置
  → 空列表；``capability`` 缺省 None（语义标注属批次 E）。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.dialect import (
    Deliverable,
    EndpointSpec as NewEndpointSpec,
    Frontmatter,
    HttpBinding,
    Prose,
    Statement,
    Term,
    render,
)
from gimbal_plate.dialect.parser import Block
from gimbal_plate.schema.endpoint.api_spec import ApiSpec
from gimbal_plate.schema.endpoint.endpoint import (
    EndpointSpec as OldEndpointSpec,
)

WHITELIST_NOTES = (
    "version/updated_at 删除（8n）；consumes/produces 存量 MIME 弃置为空列表；"
    "responses 键 int→str（N1）；request.body_type 移入 binding；api→binding"
)


def convert_endpoint(old: OldEndpointSpec) -> NewEndpointSpec:
    """旧 EndpointSpec → 新 EndpointSpec（确定性映射，见模块 docstring）。"""
    api = old.api
    assert isinstance(api, ApiSpec)
    if api.protocol != "http":
        raise ValueError(
            f"{old.id}: 迁移仅支持 http（现状全量 http；protocol="
            f"{api.protocol!r} 的 Binding 属批次 C）"
        )
    body_type = old.request.body_type if old.request is not None else "json"
    return NewEndpointSpec.model_validate({
        "id": old.id,
        "system": old.system,
        "service": old.service,
        "name": old.name,
        "description": old.description,
        "capability": None,
        "consumes": [],   # 存量 MIME 取值弃置（已定，语义重定义为词条引用）
        "produces": [],
        "binding": {
            "protocol": "http",
            "method": api.method,
            "path": api.path,
            "headers": dict(api.headers),
            "timeout_seconds": api.timeout_seconds,
            "auth": api.auth,
            "body_type": body_type,
        },
        "request": (
            {"declarations": [d.model_dump() for d in old.request.declarations]}
            if old.request is not None else None
        ),
        "responses": {
            str(outcome): {
                "description": resp.description,
                "declarations": [d.model_dump() for d in resp.declarations],
            }
            for outcome, resp in old.responses.items()
        },
        "query_views": (
            [v.model_dump() for v in old.query_views]
            if old.query_views is not None else None
        ),
        "metadata": old.metadata.model_dump(),
    })


def endpoint_to_deliverable(ep: NewEndpointSpec) -> Deliverable:
    """新 EndpointSpec → 单接口交付物文件（type: endpoints，reviewed 信封）。"""
    return Deliverable(
        frontmatter=Frontmatter(
            id=ep.id, type="endpoints", system=ep.system, service=ep.service,
        ),
        nodes=[
            Prose(text=f"# {ep.name}"),
            Block(type="endpoint", review="reviewed", payload=ep),
        ],
        source=f"migrated:{ep.id}",
    )


def render_endpoint_markdown(ep: NewEndpointSpec) -> str:
    return render(endpoint_to_deliverable(ep))


def equivalent(
    old: OldEndpointSpec, parsed_ep: NewEndpointSpec
) -> tuple[bool, list[str]]:
    """等价校验：转换结果 vs Markdown 重解析结果（语义比较）。

    双方都投影到新形状的 canonical payload（键序 = 定义序、排除默认值、
    判别 tag 恒序列化）后全等比较；白名单差异已在 ``convert_endpoint``
    内归一（见 ``WHITELIST_NOTES``）。
    """
    diffs: list[str] = []
    a = convert_endpoint(old).model_dump(mode="json", exclude_defaults=True)
    b = parsed_ep.model_dump(mode="json", exclude_defaults=True)
    if a != b:
        keys = sorted(set(a) | set(b))
        for k in keys:
            if a.get(k) != b.get(k):
                diffs.append(f"{old.id}: 字段 {k!r} 不等")
    return not diffs, diffs


_ = (Statement, Term, Any)
