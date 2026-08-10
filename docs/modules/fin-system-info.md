# fin.system_info 模块

> fin 系统的"系统级公共信息"单一来源 — 集中托管所有非敏感、跨子模块共享的常量。

## 背景

在 `system_info` 出现之前,fin 系统的身份与默认值散布在 4 处:

1. `systems/fin/meta.py` 工厂函数硬编码 `system=["fin"]`、`tags=["fin"]`、`author="fin-team"` 等。
2. `systems/fin/config.py` 工厂函数硬编码 7 个 service URL、`tester_a`、5 个业务变量。
3. `systems/fin/endpoint/*.py` 18 个文件每个都重复写 `system="fin"`、`version="1.0.0"`。
4. `http/app.py` lifespan 直接 import `ALL_ENDPOINTS` 后注册,无任何 system 一致性校验。

这种"散点定义"导致两个具体问题:

- **契约无法机器校验**:有人把 `system="fin"` 改成 `system="finance"` 但忘了同步 endpoint 文件,
  或反之,运行时无人发现。
- **默认值散落**:改一处忘另一处的概率高(`"fin-team"` 出现了 2 次、`"1.0.0"` 出现了 19 次)。

## 目录结构

```
gimbal_plate/systems/fin/
├── __init__.py
├── system_info.py        # 本模块的承载文件(NEW)
├── meta.py               # fin_meta_template,从 system_info 派生
├── config.py             # fin_config_template,services 从 system_info 派生
├── defaults.py           # 冻结的默认实例(META_TEMPLATE / CONFIG_TEMPLATE)
├── models.py             # Pydantic 请求/响应模型
└── endpoint/
    ├── __init__.py       # ALL_ENDPOINTS 聚合
    └── *.py              # 18 个 endpoint 文件,system/version/metadata 从 system_info 派生
```

## 导出分类

`system_info.py` 全部导出均为 `Final[...]` 不可变值,共 12 个,分 5 类:

### A. 系统身份(1 个)

| 名称 | 类型 | 值 | 用途 |
|------|------|----|------|
| `FIN_SYSTEM` | `str` | `"fin"` | `EndpointSpec.system` 取值,同时是 `EndpointSpec.id` 的 prefix 锚点(详见 ADR 0001)。 |

### B. 默认值(6 个)

| 名称 | 类型 | 值 | 用途 |
|------|------|----|------|
| `FIN_DEFAULT_VERSION` | `str` | `"1.0.0"` | `EndpointSpec.version` 默认 |
| `FIN_DEFAULT_MODULE` | `str` | `"fin"` | `EndpointMetadata.module` |
| `FIN_DEFAULT_OWNER` | `str` | `"fin-team"` | `EndpointMetadata.owner` |
| `FIN_DEFAULT_AUTHOR` | `str` | `"fin-team"` | `Meta.author` |
| `FIN_DEFAULT_PRIORITY` | `int` | `1` | `Meta.priority` |
| `FIN_DEFAULT_TAGS` | `tuple[str, ...]` | `("fin",)` | `EndpointMetadata.tags` / `Meta.tags` |

### C. Meta 模板字符串(2 个)

含 `{system}` 占位符,运行时由 `str.format(system=FIN_SYSTEM)` 注入:

| 名称 | format 后 |
|------|-----------|
| `FIN_META_NAME_TEMPLATE` = `"{system}-default-case"` | `"fin-default-case"` |
| `FIN_META_DESCRIPTION_TEMPLATE` = `"{system} 系统用例默认元信息模板"` | `"fin 系统用例默认元信息模板"` |

### D. 锚点(1 个)

| 名称 | 类型 | 值 | 用途 |
|------|------|----|------|
| `FIN_CREATE_TIME_ANCHOR` | `datetime` | `2026-08-04 00:00:00 UTC` | `Meta.createTime`,固定 UTC 时间戳,便于 round-trip 测试断言一致。 |

### E. 资源清单(1 个 dict,含 6 项)

`FIN_SERVICES_URLS` — fin 系统 6 个服务的测试 URL,生产 URL 由调用方在 `fin_config_template(overrides=...)` 中注入:

```python
{
    "settlement":    "https://test-api.example.com/fin/settlement",
    "account":       "https://test-api.example.com/fin/account",
    "order_entrust": "https://test-api.example.com/fin/order-entrust",
    "order":         "https://test-api.example.com/fin/order",
    "order_fee":     "https://test-api.example.com/fin/order-fee",
    "audit":         "https://test-api.example.com/fin/audit",
}
```

## FIN_SYSTEM 的双重身份

`FIN_SYSTEM` 既作为 `EndpointSpec.system` 的取值,也是 `EndpointSpec.id` 的 prefix 锚点 —
这一约束由 schema 层强制:

```python
# src/gimbal-plate/gimbal_plate/schema/endpoint/endpoint.py
@model_validator(mode="after")
def _validate_integrity(self) -> "EndpointSpec":
    ...
    if not self.id.startswith(f"{self.system}."):
        raise ValueError(
            f"EndpointSpec.id={self.id!r} 必须以 system 字段 "
            f"'{self.system}' 作为 prefix,"
            f"完整期望 prefix='{self.system}.'"
        )
```

意味着:

- 任何客户系统拿到 `id="fin.audit.audit_page"` 后,无需先拉 system 列表就能反查归属:
  `id.split(".", 1)[0] == "fin"`。
- 若要新增第二个系统(如 `market`),需要在 `systems/market/` 下新建一个 `system_info.py`,
  并保证其 `FIN_SYSTEM="market"`(或 `MARKET_SYSTEM="market"`)与所有 endpoint id prefix 一致。

详见 [ADR 0001](../adr/0001-endpoint-id-system-prefix.md)。

## 使用模式

### 1. 在 endpoint 文件中

```python
from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE, FIN_DEFAULT_OWNER, FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION, FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec, EndpointMetadata, EndpointSpec, ResponseSpec,
)

AUDIT_AUDIT_PAGE: Final[EndpointSpec] = EndpointSpec(
    id="fin.audit.audit_page",
    system=FIN_SYSTEM,
    service="audit",
    name="分页查询审计单",
    api=ApiSpec(service="audit", method="POST", path="/api/audit/page"),
    responses={200: ResponseSpec(status=200, ...)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
```

### 2. 在 fin_meta_template 中

```python
def fin_meta_template(**overrides: Any) -> Meta:
    fin_defaults: dict[str, Any] = {
        "system":      [system_info.FIN_SYSTEM],
        "name":        system_info.FIN_META_NAME_TEMPLATE.format(
            system=system_info.FIN_SYSTEM,
        ),
        "description": system_info.FIN_META_DESCRIPTION_TEMPLATE.format(
            system=system_info.FIN_SYSTEM,
        ),
        "module":      system_info.FIN_DEFAULT_MODULE,
        "priority":    system_info.FIN_DEFAULT_PRIORITY,
        "author":      system_info.FIN_DEFAULT_AUTHOR,
        "owner":       system_info.FIN_DEFAULT_OWNER,
        "tags":        list(system_info.FIN_DEFAULT_TAGS),
        "createTime":  system_info.FIN_CREATE_TIME_ANCHOR,
    }
    return common_meta_template(**{**fin_defaults, **overrides})
```

### 3. 在 fin_config_template 中(仅 services 从 system_info 派生)

```python
def fin_config_template(**overrides: Any) -> Config:
    fin_defaults: dict[str, Any] = {
        "services": dict(system_info.FIN_SERVICES_URLS),  # ← 从 system_info
        "users": {  # 占位符密码,留在本地
            "tester_a": AuthSession(
                username="tester_a",
                password="${env.TEST_USER_A_PASSWORD}",
                domain="test",
            ),
        },
        "vars": {  # 业务占位变量,留在本地
            "fin_base_url": "...",
            ...
        },
    }
    return common_config_template(**{**fin_defaults, **overrides})
```

### 4. 在 http/app.py lifespan 中(自检)

```python
if getattr(app.state, "registry_owned", True):
    for ep in ALL_ENDPOINTS:
        default_registry.register_endpoint(ep)

    from gimbal_plate.systems.fin.system_info import FIN_SYSTEM
    wrong = [ep for ep in default_registry.list_endpoints() if ep.system != FIN_SYSTEM]
    if wrong:
        ids = ", ".join(repr(ep.id) for ep in wrong[:5])
        raise RuntimeError(
            f"plate lifespan sanity check failed: {len(wrong)} endpoint(s) "
            f"have system != FIN_SYSTEM (first: {ids}). "
            f"请检查 fin/endpoint/*.py 是否与 system_info.FIN_SYSTEM 一致。"
        )
```

## 设计边界 / 不属于本模块

`system_info` 是"非敏感、跨子模块共享"的常量集合。下列内容**有意**留在下游模块,
不属于 `system_info`:

- **凭据 / 用户密码**:`fin.config.test_user.password` 等占位符留在 `config.py`。
- **业务占位变量**:`fin_bl_no_template`、`fin_bank_id_count` 等业务变量留在 `config.py`。
- **endpoint 特定 metadata**:单个 endpoint 的 tags / owner 覆盖(若未来需要)
  应在 endpoint 文件本地定义,不污染 `system_info`。
- **服务发现信息**:第二系统/外部接入点的元数据。

判断标准:**如果它属于"客户系统首次接触 fin 时必须知道的基础信息"**, 入 `system_info`;
**如果它属于"运行时凭据 / 业务配置"**, 留在下游。

## 演进方向

- **第二系统接入**:复制 `system_info.py` 结构到 `systems/market/system_info.py`,把 `FIN_*` 改为 `MARKET_*`,
  并为每个 endpoint 加 `system=MARKET_SYSTEM`、`id="market.*"` prefix。
- **数据库化**:若日后 endpoint 数量从 18 涨到 100+,`system_info` 仍可保留(它是常量、不是动态数据),
  把 endpoint 文件改成 DB 加载,但 `system_info` 不会因 DB 化而消失。
- **多版本并存**:若 fin 系统出现 v1 / v2 兼容性窗口,可考虑 `FIN_DEFAULT_VERSION` 拆成
  `FIN_V1_VERSION` / `FIN_V2_VERSION`,但这是未来问题,当前 v1 唯一。

## 相关 commit

- **Commit 1**:`EndpointSpec._validate_integrity` 加 id prefix 校验。
- **Commit 2**:本模块(`system_info.py`)首次创建。
- **Commit 3**:`fin/meta.py` 从 system_info 派生。
- **Commit 4**:`fin/config.py` services 从 system_info 派生。
- **Commit 5**:18 个 endpoint 文件统一从 system_info 引用。
- **Commit 6**:`http/app.py` lifespan 自检。

ADR 编号: [0001 - endpoint id 必须以 system 字段作为 prefix](../adr/0001-endpoint-id-system-prefix.md)