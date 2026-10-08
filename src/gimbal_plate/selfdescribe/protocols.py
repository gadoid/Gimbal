"""selfdescribe.protocols —— 执行器协议自描述收回 plate（批次 C，D5 改判）。

D5（已改判）：binding 模型随批次 C 收回 plate——协议的 binding 模型属于
框架自描述，真源 = plate，契约测试防漂移（本模块即镜像 + 测试对拍）。

批次 C 的「复制」纪律：plate **不 import** gimbal（无反向依赖，
test_v3_no_reverse_import 守卫），以契约测试比对两侧 JSON Schema ——
漂移即红，评审重钉。首个成员：http（唯一内置协议；D9 第二协议时按
「执行器注册适配器 + plate 加 Binding 类型 + export 加映射」扩展）。
"""
from __future__ import annotations

from typing import Any

# http 协议自描述（与执行器 HttpCallParams / dialect HttpBinding 对拍）
HTTP_PROTOCOL: dict[str, Any] = {
    "protocol": "http",
    "label": "HTTP 请求",
    "binding_schema": {
        # 与 dialect.HttpBinding 字段一一对应（extra=forbid）
        "protocol": {"type": "string", "const": "http"},
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        },
        "path": {"type": "string", "pattern": "^/"},
        "headers": {"type": "object", "additionalProperties": {"type": "string"}},
        "timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 600},
        "auth": {
            "type": "string",
            "enum": ["none", "bearer", "basic", "cookie", "custom"],
        },
        "body_type": {
            "type": "string",
            "enum": ["none", "json", "form", "multipart", "raw", "binary"],
        },
    },
    "call_schema": {
        # 执行器侧 params（gimbal/protocols/builtin/http.py HttpCallParams;
        # service/user/view_hints 为平台/执行环境注入面,非 binding 映射）
        "method": {"type": "string"},
        "path": {"type": "string"},
        "headers": {"type": "object"},
        "timeout": {"type": "number"},
        "service": {"type": "string", "injected": "执行环境 services 映射"},
        "user": {"type": "string", "injected": "按 user 标签的凭证解析"},
        "view_hints": {"type": "object", "injected": "平台扩展;执行忽略"},
    },
    "export_mapping": {
        # binding → call 投影（6.2；timeout_seconds → timeout，service 取外壳）
        "timeout_seconds": "timeout",
        "passthrough": ["method", "path", "headers"],
        "from_shell": ["service", "protocol"],
    },
    "success_rule": "任意 2xx；成功基准 = 数值最小的已声明 2xx",
    "locator": ["method", "path"],
    "side_effect_free": "method == GET",
}

KNOWN_PROTOCOLS: dict[str, dict[str, Any]] = {"http": HTTP_PROTOCOL}


def protocol_descriptors() -> list[dict[str, Any]]:
    """协议目录（框架自描述 dim 的数据源）。"""
    return [
        {
            "protocol": p["protocol"],
            "label": p["label"],
            "locator": p["locator"],
            "success_rule": p["success_rule"],
            "side_effect_free": p["side_effect_free"],
        }
        for p in KNOWN_PROTOCOLS.values()
    ]
