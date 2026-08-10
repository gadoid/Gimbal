"""fin 系统的系统级公共信息。

本模块集中托管 fin 系统所有"非敏感、跨子模块共享"的常量,
作为 fin 子树的 single source of truth,供:

- ``fin.meta``     构造 Meta 默认模板时读取
- ``fin.config``   构造 Config 默认模板时读取
- ``fin.endpoint.*`` 18 个 endpoint 文件构造 EndpointSpec 时读取
- ``http.app`` lifespan 自检时校验 system 字段

设计原则:

- **常量,不是工厂**: 所有导出均为 ``Final[...]`` 不可变值,
  调用方直接 import + 引用,不在 system_info 层做组合/合并。
- **零敏感信息**: 任何含凭据、生产地址的内容(用户密码 / 业务 vars)
  均不属于本模块,留在 ``fin.config``。
- **system 字段双重身份**: ``FIN_SYSTEM`` 同时是 EndpointSpec.system 的
  取值,也是该系统下所有 EndpointSpec.id 的 prefix 锚点。
  ``http.app`` lifespan 自检通过 ``str.startswith`` 校验 id 前缀,
  详情见 ``docs/adr/0001-endpoint-id-system-prefix.md``。

导出分类:

- A. 系统身份: FIN_SYSTEM
- B. 默认值(供 endpoint / meta 读取): FIN_DEFAULT_VERSION 等
- C. Meta 模板字符串(供 meta.py 拼接): FIN_META_NAME_TEMPLATE 等
- D. 锚点(供 meta.py 冻结 createTime): FIN_CREATE_TIME_ANCHOR
- E. 资源清单(供 config.py / app lifespan 引用): FIN_SERVICES_URLS
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Final


# ── A. 系统身份 ────────────────────────────────────────────────
# 同时作为 EndpointSpec.system 取值,以及 EndpointSpec.id 的 prefix 锚点。
FIN_SYSTEM: Final[str] = "fin"


# ── B. 默认值(供 endpoint / meta / config 读取) ──────────────────
FIN_DEFAULT_VERSION: Final[str] = "1.0.0"
FIN_DEFAULT_MODULE: Final[str] = "fin"
FIN_DEFAULT_OWNER: Final[str] = "fin-team"
FIN_DEFAULT_AUTHOR: Final[str] = "fin-team"
FIN_DEFAULT_PRIORITY: Final[int] = 1
FIN_DEFAULT_TAGS: Final[tuple[str, ...]] = ("fin",)


# ── C. Meta 模板字符串(供 fin.meta 拼接) ─────────────────────────
# 含 ``{system}`` 占位符,运行时由 ``str.format(system=FIN_SYSTEM)`` 注入。
FIN_META_NAME_TEMPLATE: Final[str] = "{system}-default-case"
FIN_META_DESCRIPTION_TEMPLATE: Final[str] = "{system} 系统用例默认元信息模板"


# ── D. 锚点(供 fin.meta 冻结 createTime) ──────────────────────────
# 固定 UTC 时间戳,便于 round-trip 测试断言一致。
FIN_CREATE_TIME_ANCHOR: Final[datetime] = datetime(
    2026, 8, 4, 0, 0, 0, tzinfo=timezone.utc,
)


# ── E. 资源清单(供 fin.config / app lifespan 引用) ────────────────
# 各服务测试环境 URL;生产 URL 由调用方在 overrides 中注入。
FIN_SERVICES_URLS: Final[dict[str, str]] = {
    "settlement":     "https://test-api.example.com/fin/settlement",
    "account":        "https://test-api.example.com/fin/account",
    "order_entrust":  "https://test-api.example.com/fin/order-entrust",
    "order":          "https://test-api.example.com/fin/order",
    "order_fee":      "https://test-api.example.com/fin/order-fee",
    "audit":          "https://test-api.example.com/fin/audit",
}


__all__ = [
    # A. 系统身份
    "FIN_SYSTEM",
    # B. 默认值
    "FIN_DEFAULT_VERSION",
    "FIN_DEFAULT_MODULE",
    "FIN_DEFAULT_OWNER",
    "FIN_DEFAULT_AUTHOR",
    "FIN_DEFAULT_PRIORITY",
    "FIN_DEFAULT_TAGS",
    # C. Meta 模板
    "FIN_META_NAME_TEMPLATE",
    "FIN_META_DESCRIPTION_TEMPLATE",
    # D. 锚点
    "FIN_CREATE_TIME_ANCHOR",
    # E. 资源清单
    "FIN_SERVICES_URLS",
]