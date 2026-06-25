# Gimbal Schema 层 Skill 文档

> 本文档描述 `src/gimbal/schema/` 下 Pydantic 静态描述层（DSL 数据契约），供 AI 将 API 描述/业务需求**转换为数据驱动场景用例**时使用。
>
> **不涉及**：`Ref / *Ref / Mock / File / ScenarioRef / SuiteRef` 等资产/引用层概念（由后续资产功能承载）。

---

## 0. 总体定位

Schema 层定义**场景化测试用例的静态数据契约**。所有模型基于 Pydantic v2；多态字段（kind discriminator）由执行器层处理，AI 生成场景时**只需关心内联具体类型**。

**AI 必读集**：`Meta / Config / Step / Api / Request / Strategy(Extract/Assign/Assertion) / AuthSession / TimePolicy / RetryPolicy`

**AI 不必读集**：所有 `*Ref`、`*Union` 多态层、`Resource/Mock/File`、`Suite`

---

## 0.5 最少必填字段集合（生成基线）

生成一个合法 `Scenario` **必须**包含的字段：

| 模型 | 必填字段 |
|---|---|
| `Scenario` | `scenarioId`, `meta`, `config`, `steps` |
| `Meta` | `name`, `description`, `module`, `priority`, `author`, `owner`, `tags` |
| `Config` | `timePolicy` |
| `Step`（每步） | `api`, `request`, `strategy`（至少 1 个） |
| `Api` | `service`, `method`, `path` |
| `Request` | （`body` 可空 dict） |
| `Meta.tags` | 至少 1 个 |

> AI 自检：生成完成后对照上表逐项校验，缺失即补全。

---

## 0.6 常用取值约定

AI 生成时直接套用以下约定，避免任意编造：

| 字段 | 约定值 / 格式 |
|---|---|
| `Meta.priority` | `1`=P0 冒烟 / `2`=P1 核心 / `3`=P2 常规 / `4`=P3 边缘 / `5`=P4 废弃 |
| `Meta.tags`（推荐） | `smoke` / `regression` / `e2e` / `negative` / `slow`（至少 1 个） |
| `Meta.module` | 业务模块名（`settlement` / `order` / `auth` / ...） |
| `Meta.author` / `Meta.owner` | 用户名或邮箱字符串 |
| `Api.path` | 支持 `{param}` 占位（如 `/api/orders/{id}`），不含域名 |
| `Api.method` | 严格使用 5 个字面量之一（**禁止** `POSTGET` / `get` 等变体） |
| `Api.headers` | 常见键：`Content-Type`、`Authorization`、`X-Request-Id` |
| `Extract.expression` | **JSONPath**，根用 `$`，例：`$.data.id` / `$.items[0].name` / `$.code` |
| `Assign.source` | 字面量直接写；引用已有变量用 `$.var_name`（scope 内可见变量） |
| `Assign.target` | 注入后的变量名（不含 `$`），例：`order_id` |
| `Assertion.target` | 同样用 JSONPath，例：`$.code` / `$.data.status` |
| `RetryPolicy.retryOn` | HTTP 状态码字符串列表，如 `["500", "502", "503"]` |
| `TimePolicy` | 默认 `RecordPolicy`；仅显式要求超时失败时用 `TimeoutPolicy` |
| `AuthSession.token_type` | 默认 `Bearer`（除非明确 OAuth/Custom） |

---

## 0.7 黄金生成规则

按重要性从高到低，AI 须无条件遵守：

1. **生成顺序**：`Meta` → `Config(services/users/timePolicy)` → `Steps`。Config 必先于 Steps 落地，否则 `Api.service` 无法校验。
2. **服务名一致**：`Config.services` 必须包含所有 `Api.service` 取值；缺失即补 `"service-name": "http://host:port"`。
3. **断言不可省**：每个 `Step.strategy` 至少 1 个 `Assertion`，推荐断言 `$.code == 200` + 关键业务字段。
4. **提取驱动串联**：依赖前序结果的字段，前序 step 必须先有 `Extract` 提取到 `scope=scenario`，后续 step 的 `target`/`source` 才能引用。
5. **作用域选型**：跨 step 共享 → `scope=scenario`；仅当前 step 用 → `scope=step`；多场景共享 → `session`。
6. **认证凭据隔离**：`AuthSession` 只填 `url/username/password`（认证前态），**禁止**预设 `token` / `expires_at`。
7. **不写资产层**：不生成 `Ref / *Ref / Mock / File / ScenarioRef / SuiteRef`；不写 `Suite` 顶层。
8. **失败策略分层**：单策略级用 `StrategyBase.onFailure`；step 整体级用 `Config.retry`，二者**不重复配置**。

---

## 1. states.py — 步骤状态枚举

| 枚举 | 值 | 语义 |
|---|---|---|
| `StepState` | `pending` / `running` / `passed` / `failed` / `skipped` | 步骤执行生命周期状态（AI 不直接生成，仅用于结果判定） |

---

## 2. api.py — 接口请求定义

| 模型 | kind | 字段 | 必填 | 语义 |
|---|---|---|---|---|
| `Api` | `"api"` | `service: str` | ✓ | 服务名，必须出现在 `Config.services` 的 key 中 |
| | | `method: Literal[GET/POST/PUT/DELETE/PATCH]` | ✓ | HTTP 方法 |
| | | `path: str` | ✓ | URL 路径（不含域名） |
| | | `headers: dict[str, str]` | ✗ | 头信息，默认 `{}` |
| | | `timeout: float` | ✗ | 超时秒数，默认 `30` |

---

## 3. request.py — 请求体

| 模型 | kind | 字段 | 必填 | 语义 |
|---|---|---|---|---|
| `Request` | `"request"` | `body: dict \| list` | ✗ | 请求体；JSON 对象或数组，默认 `{}`；body 内部可内联 `Ref` 占位 |

---

## 4. strategy.py — 策略层（最复杂模块）

### 4.1 枚举

| 枚举 | 取值（中文助记） | 用途 |
|---|---|---|
| `Scope` | `framework`(框架级) / `session`(会话级) / `scenario`(场景级) / `step`(步骤级) / `request`(请求级) | 变量写入作用域；高优先级可覆盖低优先级同名变量 |
| `AssertOperator` | `eq`(等于) / `ne`(不等于) / `gt`(大于) / `gte`(大于等于) / `lt`(小于) / `lte`(小于等于) / `in`(在集合中) / `not_in`(不在集合中) / `contains`(包含子串) / `not_contains`(不包含) / `exists`(字段存在) / `empty`(为空) / `length_eq`(长度等于) / `schema`(符合 schema) | 断言比较符 |
| `StrategyPhase` | `before_request`(请求前) / `after_request`(请求后) / `verifying`(校验中) / `teardown`(清理中) | 策略执行阶段 |
| `FailurePolicy` | `abort`(中止 step) / `continue`(记录但继续) / `warn`(仅警告) / `retry`(配合 retry 重试) | 失败处理 |

### 4.2 基类 `StrategyBase`（所有策略共享字段）

| 字段 | 类型 | 必填 | 默认 | 语义 |
|---|---|---|---|---|
| `name` | str | ✗ | None | 策略名 |
| `phase` | `StrategyPhase` | ✗ | None | 执行阶段；不填则执行器按策略类型推断 |
| `order` | int | ✗ | 0 | 同阶段内执行顺序 |
| `enabled` | bool | ✗ | True | 是否启用 |
| `onFailure` | `FailurePolicy` | ✗ | `abort` | 失败策略 |
| `timeout` | float | ✗ | None | 策略执行超时（秒） |
| `tags` | list[str] | ✗ | [] | 标签 |

### 4.3 策略子类

| 模型 | kind | 字段 | 必填 | 默认 | 语义 |
|---|---|---|---|---|---|
| `Extract` | `"extract"` | `expression: str` | ✓ | — | JSONPath，在响应/scratch 上导航 |
| | | `target: str` | ✓ | — | 写入目标的 key |
| | | `scope: Scope` | ✗ | `step` | 写入作用域 |
| | | `default: Any` | ✗ | None | 提取失败时使用的默认值 |
| | | `required: bool` | ✗ | True | 提取失败是否抛异常 |
| `Assign` | `"assign"` | `source: Any` | ✓ | — | 字面量或路径 |
| | | `target: str` | ✓ | — | 注入目标 key |
| | | `scope: Scope` | ✗ | `scenario` | 写入作用域 |
| | | `default: Any` | ✗ | None | 注入失败时使用的默认值 |
| | | `required: bool` | ✗ | True | 注入失败是否抛异常 |
| `Assertion` | `"assertion"` | `target: str` | ✓ | — | 断言的目标字段 |
| | | `operator: AssertOperator` | ✓ | — | 断言的比较符 |
| | | `expected: Any` | ✗ | None | 断言的比较值 |
| | | `message: str` | ✗ | None | 断言失败信息 |
| | | `soft: bool` | ✗ | False | 软断言（失败不中断） |

**生成建议**：每个 `Step.strategy` 列表至少包含 1 个 `Assertion`（断言响应码/关键字段）和 0~N 个 `Extract`（提取供后续 step 使用的字段）。

---

## 5. timepolicy.py — 时间策略

| 模型 | kind | 字段 | 必填 | 语义 |
|---|---|---|---|---|
| `RecordPolicy` | `"record"` | — | — | 仅记录耗时，不检查超时（**默认**） |
| `TimeoutPolicy` | `"timeout"` | `seconds: int` | ✓ | 强制超时；超时抛异常 |

> AI 默认生成 `RecordPolicy`；仅在用例明确要求超时失败时才用 `TimeoutPolicy`。

---

## 6. retrypolicy.py — 重试策略

| 字段 | 类型 | 必填 | 默认 | 语义 |
|---|---|---|---|---|
| `kind` | `"retry_policy"` | ✓ | — | 固定值 |
| `maxAttempts` | int | ✗ | 1 | 最大尝试次数 |
| `backoffSeconds` | float | ✗ | 20 | 退避基础时长（秒） |
| `retryOn` | list[str] | ✗ | [] | 触发重试的错误码/标签集合 |

> AI 默认不生成 `RetryPolicy`；仅在用例显式要求"重试 N 次"时附加。

---

## 7. setup.py / teardown.py — 前后置

| 模型 | kind | 字段 | 必填 | 语义 |
|---|---|---|---|---|
| `Setup` | `"setup"` | — | — | 用例前置动作（数据准备、清理） |
| `Teardown` | `"teardown"` | — | — | 用例后置动作（数据清理、状态恢复） |

> 放在 `Config.setup` / `Config.teardown` 列表中。AI 仅在用例需要前后置数据准备时生成，否则不写。

---

## 8. auth.py — 认证会话

**设计**：读写一体；认证前填凭证，认证后 token 字段自动填充。

| 字段 | 类型 | 必填 | 默认 | 语义 |
|---|---|---|---|---|
| `url` | str | ✓ | `""` | 认证接口地址 |
| `username` | str | ✓ | `""` | 用户名 |
| `password` | str | ✓ | `""` | 密码 |
| `expires_in` | int | ✗ | None | Token 有效期（秒），**认证前**配置 |
| `token` | str | ✗ | None | 访问令牌，**认证后**填充（AI 不生成） |
| `token_type` | str | ✗ | `Bearer` | Token 类型 |
| `expires_at` | datetime | ✗ | None | 过期时间，**认证后**自动计算（AI 不生成） |
| `refresh_token` | str | ✗ | None | 刷新令牌（与 access_token 独立） |

### 计算属性（AI 了解即可，不直接生成）
- `is_authenticated`：有 token 且未过期
- `should_refresh`：距过期 < 5 分钟
- `auth_header`：返回 `f"{token_type} {token}"`；**含 ASCII 控制字符时抛 ValueError**（防 HTTP header 注入 CWE-93）
- `remaining_seconds`：剩余秒数

### 方法
| 方法 | 行为 |
|---|---|
| `apply_token(token, expires_in=None)` | 写入 token；含控制字符时早失败；`expires_in>0` 重置 lifetime；`==0` 清空；`None` 保持 lifetime 并重新锚定 expires_at |
| `clear_token()` | 清空 token / expires_at / expires_in |
| `clear_password()` | 仅清空 password，缩短凭据驻留 |
| `is_same_credential(other)` | 按 url/username/password 相等比较 |
| `from_dict(data)` | 类方法，从 dict 构造 |

> **时间处理**：`expires_at` 统一以 UTC 时区存储；naive datetime 视为 UTC。
>
> **AI 使用方式**：在 `Config.users` 字典中以"用户别名"为 key 放置 `AuthSession` 对象；value 中只填 `url/username/password`（认证前态）。

---

## 9. step.py — 步骤

| 模型 | kind | 字段 | 必填 | 类型 | 语义 |
|---|---|---|---|---|---|
| `Step` | `"step"` | `description` | ✗ | str | 步骤说明/意图，供人和 CLI 参考 |
| | | `api` | ✓ | `Api` | 接口请求定义 |
| | | `request` | ✓ | `Request` | 请求体 |
| | | `strategy` | ✓ | list[Strategy] | 策略集（至少 1 个） |

**生成建议**：每步 `description` 用一句话写明业务意图（如"登录获取 token"），便于审计和回溯。

---

## 10. scenario.py — 顶层用例

### 10.1 `Meta` — 用例元信息

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `name` | str | ✓ | 用例名（人读） |
| `description` | str | ✓ | 用例业务描述 |
| `module` | str | ✓ | 业务模块（settlement / order / ...） |
| `priority` | int | ✓ | 用例等级（值域未硬编码，按团队约定） |
| `author` | str | ✓ | 作者 |
| `owner` | str | ✓ | 维护/执行人 |
| `tags` | list[str] | ✓ | 标签（至少 1 个；推荐带 `smoke`/`regression`/`e2e` 等） |
| `version` | str | ✗ | 版本号 |
| `createTime` | datetime | ✗ | 创建时间 |
| `expire` | bool | ✗ | 过期标志 |
| `requirementRef` | list | ✗ | 关联需求链接（引用层，AI 不必填） |

### 10.2 `Config` — 执行配置

| 字段 | 类型 | 必填 | 默认 | 语义 |
|---|---|---|---|---|
| `setup` | list[`Setup`] | ✗ | [] | 前置动作 |
| `teardown` | list[`Teardown`] | ✗ | [] | 后置动作 |
| `services` | dict[str, str] | ✗ | {} | 服务名 → URL 映射（**`Api.service` 必须出现在此 dict 的 key 中**） |
| `users` | dict[str, `AuthSession`] | ✗ | {} | 用户别名 → 认证会话（key 即 user tag） |
| `timePolicy` | `TimePolicy` | ✓ | `RecordPolicy()` | 时间策略 |
| `retry` | `RetryPolicy` | ✗ | None | 重试策略 |
| `vars` | dict[str, Any] | ✗ | {} | 变量声明；字面量或生成式 spec；CLI `--var` 优先级更高 |

### 10.3 `Scenario`

| 模型 | kind | 字段 | 必填 | 类型 | 语义 |
|---|---|---|---|---|---|
| `Scenario` | `"scenario"` | `scenarioId` | ✓ | str | 场景 ID（前缀 `sc`，需唯一） |
| | | `meta` | ✓ | `Meta` | 用例元信息 |
| | | `config` | ✓ | `Config` | 执行配置 |
| | | `resource` | ✗ | dict | 资源（AI 不必填，由资产层处理） |
| | | `steps` | ✓ | list[`Step`] | 步骤列表（按业务顺序） |

### 10.4 `Suite`（了解即可）

| 模型 | kind | 字段 | 必填 | 语义 |
|---|---|---|---|---|
| `Suite` | `"suite"` | `suite: list[Scenario]` | ✓ | 场景集合（AI 通常不直接生成 Suite） |

---

## 11. 全局心智模型

```
Scenario
├── meta (Meta)          # 管理信息：name/description/module/priority/author/owner/tags
├── config (Config)      # 执行配置
│   ├── setup/teardown
│   ├── services (dict)  # service 名 → URL，Api.service 引用此表
│   ├── users (dict)     # user 名 → AuthSession
│   ├── timePolicy       # 默认 RecordPolicy
│   ├── retry (可选)
│   └── vars (可选)
├── resource (dict)      # AI 不必填
└── steps (list)         # 按业务顺序
    └── Step
        ├── description  # 业务意图说明
        ├── api (Api)            # service + method + path
        ├── request (Request)    # body
        └── strategy (list)      # Extract / Assign / Assertion
```

---

## 12. 字段间约束（AI 必读）

生成时必须满足的隐式约束：

| 约束 | 说明 |
|---|---|
| **服务名一致性** | `Api.service` 的取值必须出现在 `Config.services` 的 key 中 |
| **用户引用一致性** | 用到认证的 step 应在 `Config.users` 中先声明对应会话 |
| **steps 顺序敏感** | `Extract` 提取的字段在**后续** step 的 `target`/`source` 中才能被引用；前向引用会失败 |
| **Strategy 必含断言** | 每个 `Step.strategy` 至少 1 个 `Assertion`，否则用例无验证能力 |
| **scope 优先级** | `framework` > `session` > `scenario` > `step` > `request`（高优先级可覆盖低优先级同名变量） |
| **scope 默认值** | `Extract` 默认 `step`；`Assign` 默认 `scenario` |
| **时间统一 UTC** | `expires_at` 必为 UTC；naive datetime 视为 UTC |
| **控制字符约束** | `token` / `token_type` 不允许 ASCII 控制字符（0x00-0x1F、0x7F） |

---

## 13. 编写要点速查

1. **先填元信息**：每次生成从 `Meta` 开始，name/description/module/tags 是审计和检索的关键。
2. **服务名先行**：`Config.services` 必须先于 `steps` 落地，所有 `Api.service` 才能校验通过。
3. **变量作用域**：跨 step 共享用 `scope: scenario`；仅当前 step 用 `scope: step`；多场景共享用 `session`。
4. **断言不可省**：每步至少 1 个 `Assertion`，推荐断言 HTTP 状态码 + 关键业务字段。
5. **提取驱动串联**：依赖前序结果的字段必须先有 `Extract`，再被后续 step 引用。
6. **失败策略分层**：单策略用 `StrategyBase.onFailure`；step 整体用 `Config.retry`。
7. **认证信息隔离**：`AuthSession` 只放 `url/username/password`（认证前态），不预设 token。
