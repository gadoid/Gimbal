# gimbal-platform 自举：响应契约层与自用例编排

日期：2026-09-28
基线：`feat/executor-v2.1-fusion @ 07831974`
性质：架构级（新增子系统）

---

## 0. 目标

三件事：

1. **响应契约层** —— 把 gimbal-platform 自己的 115 个 HTTP 操作的结构化响应契约定义出来并注册进 gimbal-plate，作为可校验、可断言的基线。
2. **自举用例** —— 在 gimbal-platform 上编排约 18 条用例，打 gimbal-platform 自己。
3. **黄金链路** —— health → 注册专用账号 → 登录取 token → 建场景/数据集/运行方案 → `POST /runs` → 取执行结果 → 清理，外加每主要域一条烟雾用例。

### 成功标准

接入平台自身**不需要改任何 schema** —— 契约走 OpenAPI 机械导出 + plate 现有注册面，不新增结构类型。P4-02 之后不返工。

核心承诺：**没有任何一处需要手改契约**。

```
平台改字段 → OpenAPI 变 → 漂移检测红 → 重跑生成器 → 契约更新 → 用例断言自动跟上
```

---

## 1. 授权边界

用户明令：**不得变更 gimbal / gimbal-plate / 执行器的实现**，只允许为被测系统做必要的结构实现与用例组织实现。

逐处裁定如下。**超出此表的任何改动都需重新请示。**

| 位置 | 改动 | 授权 |
|---|---|---|
| `src/gimbal-platform/backend/app/routers/auth.py` | 补一行 `ChangePasswordIn` import | ✅ 已授权 |
| `src/gimbal-plate/gimbal_plate/systems/platform/**` | 新增 endpoint 定义（新增文件） | ✅ 已授权 |
| `src/gimbal-plate/gimbal_plate/http/app.py` | 导入并注册平台 endpoints | ✅ 已授权 |
| `src/gimbal-plate/gimbal_plate/http/app.py` | system 自检放宽为白名单 | ✅ 已授权 |
| `src/gimbal-bootstrap/**` | 全新项目 | ✅ 已授权 |
| 一切其它 gimbal 组件 | —— | ❌ 禁止 |

### 1.1 `auth.py` 那一行为什么是必要的

`app/routers/auth.py:122` 使用 `ChangePasswordIn`，但文件顶部 `from ..schemas.auth import (...)` 只导了 `LoginIn / MeOut / RefreshIn / RegisterIn / TokenOut / UserPublic` —— **漏了 `ChangePasswordIn`**。因文件头有 `from __future__ import annotations`，注解是字符串，运行时不报错，直到 FastAPI 生成 OpenAPI schema 时才炸：

```
GET /openapi.json → HTTP 500
pydantic.errors.PydanticUserError: TypeAdapter[...ForwardRef('ChangePasswordIn')...] is not fully defined
```

后果：**平台无法输出任何机器可读的接口契约**。契约层因此完全无源。

已用内存探针验证：注入该名字后全量生成成功 —— **91 paths / 115 operations / 132 schemas**。

---

## 2. 契约层

### 2.1 真源

以**平台 `/openapi.json` 为唯一真源**。人工不写任何契约字段。

### 2.2 落点

不照抄 fin 的"一个接口一个 `.py`" —— 那是给手工精雕用的；115 个机械派生的契约用同样格式会变成 115 个几乎一样的文件。

```
src/gimbal-plate/gimbal_plate/systems/platform/
├── system_info.py      PLATFORM_SYSTEM="platform" 等常量
├── endpoints.json      ← 真源：115 个 EndpointSpec 的 JSON 数组（入库、git diff 友好）
└── endpoints.py        ~20 行加载器：读 json → [EndpointSpec(...)] → ALL_PLATFORM_ENDPOINTS
```

生成器放新项目（不污染 plate）：

```
src/gimbal-bootstrap/gimbal_bootstrap/contract_gen.py
    读 http://127.0.0.1:8000/openapi.json  →  写 plate 的 endpoints.json
```

### 2.3 JSON Schema → DeclarationEntry 映射

| OpenAPI | DeclarationEntry |
|---|---|
| `properties` | 递归转 `children`（仅 object 带） |
| `string`/`integer`/`number`/`boolean`/`object`/`array` | 六原语直译 |
| 无 `type`（`anyOf` / 未解 `$ref`） | 回落 `string` + 记 warning |
| `array` | `type:"array"`，**不展开 items**（YAGNI） |
| 属性名不合 `^[A-Za-z_]\w*$` | 记 warning，该字段丢弃 |
| 每个响应字段 | `assertable: true` |

### 2.4 三个硬约束

1. **`responses` 必须含 key `200`**（plate 校验器要求），而平台有 20+ 个 `DELETE`/`PATCH` 只回 `204`。对策：补一个空 `200`，并在 JSON 里标 `"__synthetic200": true` 供人辨识。
2. **`api.auth`** 按端点实际填：绝大多数 `bearer`，但 `/api/health`、`/api/auth/register`、`/api/auth/login` 是 `none`。
3. **`by_route` 索引静默覆盖** —— `by_route[(service,method,path)]` 后写覆盖，fin 已因此埋 3 处坑。生成器内置碰撞检测，撞了**直接失败**，不覆盖。

### 2.5 已知缺口（明确不做）

GET 的 **query 参数**在 plate 里没有对应字段（`ApiSpec` 无 `query`，`RequestSpec` 是 body 形态）。第一阶段 GET 端点的 query 参数不声明成 declaration，用例侧靠 `${}` 模板拼 path。

**这是缺口，不是方案。** 将来 P4 若要补再说。

### 2.6 id 派生

`EndpointSpec.id` 必须匹配 `^[a-z][a-z0-9_.\-]{1,63}$` 且以 `{system}.` 前缀。从 `(method, path)` 派生：

```
platform.<domain>.<action>
```

例：`platform.scenarios.get_list` ← `GET /api/scenarios`；
`platform.scenarios.get_one` ← `GET /api/scenarios/{scenario_id}`。

`service` 统一 `platform-service`（与 fin 的 `fin-service` 隔离，天然规避 `by_route` 跨系统碰撞）。

---

## 3. 自举用例编排

### 3.1 新项目布局

```
src/gimbal-bootstrap/
├── README.md
├── pyproject.toml
├── gimbal_bootstrap/
│   ├── __init__.py
│   ├── contract_gen.py       # OpenAPI → EndpointSpec JSON
│   ├── orchestrator.py       # 编排器：注册/登录/建资源/发起运行/轮询/清理
│   ├── cases.py              # YAML 用例清单加载与渲染
│   └── assertion.py          # 断言路径拼装（对齐 $.call.response.body.*）
├── cases/
│   ├── golden_path.yaml      # T1-T8
│   └── domains.yaml          # 每域一条
└── tests/
    └── test_contract_drift.py
```

用例走 **YAML 声明式**而非脚本内联 —— 可 review、可 git diff、将来能直接被平台 UI 导入。

配套一条平台侧守卫测试（归平台，因为守的是平台自己的代码）：

```
src/gimbal-platform/backend/tests/test_openapi_generation.py
```

### 3.2 断言路径（已核实）

引擎 `scratch.call` = `CallResult.to_scratch()` = `{protocol, request, response:{status, meta, body}}`（`src/gimbal/protocols/base.py:297`）。

`Assertion.target` 是打在 scratch 上的 JSONPath（`src/gimbal/strategy/builtin/assertion.py:36-37`）。

故断言路径统一为 **`$.call.response.body.<path>`**，状态断言用 `$.call.response.status`。

断言策略形状：`{kind:"assertion", target, operator, expected, message, soft, phase}`
（`src/gimbal/schema/strategy.py:80-88`）

### 3.3 黄金链路（8 条）

| # | 打什么 | 关键断言 | 传给下一步 |
|---|---|---|---|
| T1 | `GET /api/health` | `status=200`、`body.status=="ok"` | — |
| T2 | `POST /api/auth/register` | `201`、`body.user.username==${sb.username}` | `access_token`（注册即返回 TokenOut） |
| T3 | `POST /api/auth/login` | `200`、`body.token_type=="bearer"` | `access_token` → 存 AuthSession |
| T4 | `POST /api/scenarios` | `201`、`body.scenarioId` 存在 | `scenarioId` |
| T5 | `POST /api/scenarios/{id}/data-sets` | `200`、`body.datasetId` 存在 | `datasetId` |
| T6 | `POST /api/scenarios/{id}/run-schemes` | `200`、`body.schemeId` 存在 | `schemeId` |
| T7 | `POST /api/runs` | `201`、`body.executionId` 存在 | `executionId` |
| T8 | `GET /api/executions/{id}` | `200`、`body.status ∈ {done,failed}` | — |

**轮询在编排器里做，不进用例。** 引擎的 poll 策略尚未实现（路线图列为待拍板），所以 T8 只断言单次响应，执行是否跑完由编排器轮询 `GET /api/executions/{id}` 到终态。

### 3.4 每域一条（10 条）

users / auths / constants / carry / service-aliases / data-sets / run-schemes / executions / endpoint-catalog / notifications，各挑一个代表性 GET，只断言响应契约。

**合计 ~18 条**。

### 3.5 断言密度

每条用例**只断言 3-5 个关键字段**，不铺全字段 —— 否则 115 操作 × 数十字段会炸。全字段防漂移交给第 4 节，不放在运行期。

### 3.6 两个必踩的坑（编排器负责规避）

1. **`orchestration` 必须与 `definition.steps` 严格同序同长、index 对齐** —— 平台侧硬约定，长度不匹配会被拒。编排器组装时强制对齐。
2. **`scenarioId` 格式 `^sc-[a-z0-9-]+$`，数据集名/用户名撞车会 409** —— 自举资源统一前缀 `sb-`，用户名带 `uuid` 变量（`config.vars` 的 `{"kind":"uuid"}` 生成器已有）避免重复运行撞名。

### 3.7 运行方式

- 平台已运行（`127.0.0.1:8000`），**真打服务**，不走进程内 ASGI 直调
- 编排器先注册一个**自举专用账号**（`sb-` 前缀），不复用任何人的身份
- **注册后停下等人提权** —— `app/routers/auth.py` 的 `register` 只在库里一个用户都没有时才给 `role="admin"`，之后注册一律 `member`。每域用例要打 `/api/users/roster` 等管理员端点，member 身份会 403。编排器打印账号名并等回车；提权过后的账号写进 `GIMBAL_SB_USERNAME`/`GIMBAL_SB_PASSWORD` 供 pytest 复用
- 编排器先探测 `gimbal` CLI 可用性（执行链依赖 `gimbal_launcher` spawn 子进程），不可用就早失败而不是跑到一半

### 3.8 清理

每条用例收尾按依赖倒序 `DELETE`：dataset → run-scheme → scenario → auth-session。

**执行台账（`executions`）会留存** —— 它是审计面，删了就没法验证。

---

## 4. 防漂移与验证

### 4.1 漂移检测

`src/gimbal-bootstrap/tests/test_contract_drift.py`：

- 拉真实响应 → 按 `endpoints.json` 的 declarations 树递归检查：**声明的 path 必须存在且类型相符**
- **只做单向**（声明 ⊆ 实际）。反向（实际有但未声明）会因 `createdAt`/`updatedAt`/生成 id 这类动态字段误报 —— 不做
- 不依赖运行用例，`pytest` 单独可跑，是 CI 的真防线

### 4.2 三层验证

| 层 | 验证什么 | 怎么过 |
|---|---|---|
| plate | platform endpoints 注册成功、id 唯一、`by_route` 无碰撞、query_views 全局唯一校验通过 | `tests/plate/` 新增用例 |
| 契约 | 115 个操作全部转换成功、无字段丢弃告警 | 生成器自身断言 |
| 端到端 | 18 条自举用例全绿、执行台账 `status=done` | 编排器跑一遍 |

---

## 5. 风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | `/openapi.json` 可能还有**其它**未解析的 ForwardRef（今天这个只是最外层的） | 实现第一步就全量生成，第二个炸点当场暴露 |
| R2 | `by_route[(service,method,path)]` 后写静默覆盖 —— fin 已埋 3 处坑 | 生成器内置碰撞检测，撞了直接失败 |
| R3 | plate 重启即失？ | **不适用**。endpoint 定义是随 lifespan 装配的代码/JSON，不是 `declare_system` 那类内存声明 |
| R4 | **P4-02 会改 `responses` 结构**（状态码 → 结果判别） | 生成器从 OpenAPI 走，OpenAPI 是平台自己的 Pydantic，不受 plate 改动影响；声明树字段名可能要改，但**只在生成器一处** |
| R5 | 自举用例打真平台，污染真实 PG 库 | 专用账号 + `sb-` 前缀 + 每例自清理；执行台账留存 |
| R6 | 执行链依赖 `gimbal` CLI 子进程 | 编排器先探测，不可用就早失败 |

---

## 6. 不做的事

- 不碰 GET query 参数的契约化（§2.5）
- 不做反向漂移检查（§4.1）
- 不做浏览器/前端层用例（第一阶段仅后端 API）
- 不铺全字段运行期断言（§3.5）
- 不建 `QueryView`（平台 API 的列表端点不作为取数源）
- 不改 `plate_client.convert` 的 `consumer`（平台仍固定 `"gimbal"`）
- 不做用例重跑 / 检查点续跑 / 造数复用（路线图 X-04/X-05 已否决）

---

## 7. 已核实的事实记录

供实现阶段对照，避免重走：

| 事实 | 出处 |
|---|---|
| 平台 91 paths / 115 operations / 132 schemas | 内存探针实测 |
| 115 是纯业务操作数 —— `/openapi.json`、`/docs`、`/redoc` 不进 `paths`，无需排除 | 内存探针实测 |
| **auth 域 wire 键是 snake_case**（`access_token`/`token_type`/`display_name`），与其它域的 camelCase 不一致 —— 生成器与用例必须按各 schema 的实际 OpenAPI 键名走，勿凭 Python 字段名想当然 | `app/schemas/auth.py` 无 alias generator；OpenAPI 实测 |
| `/openapi.json` 返回 500，根因 `ChangePasswordIn` 未导入 | `app/routers/auth.py:122` + 探针 traceback |
| plate 路由是维度化的：`/api/{dim}`、`/api/{dim}/{id}/full`、`/api/{dim}/action/{name}` | plate openapi（15 paths / 2 schemas） |
| plate 无 endpoint 写入口，唯一注册是 Python `register_endpoint()` | `gimbal_plate/registry/registry.py:69` |
| plate lifespan 自检断言所有 endpoint `system == FIN_SYSTEM` | `gimbal_plate/http/app.py:50-62` |
| `action_system_register` 只吃 `{id,name,description}`，无 endpoints，重启即失 | `gimbal_plate/http/routes_grammar.py:788-810` |
| `EndpointSpec.responses: dict[int, ResponseSpec]`，JSON 序列化后键为字符串 | 实测 `/api/endpoint/fin.cost.amount_list/full` |
| `DeclarationEntry` 六原语封闭词表 + `assertable` | `gimbal_plate/schema/endpoint/io_spec.py` |
| `scratch.call` = `{protocol, request, response:{status,meta,body}}` | `src/gimbal/protocols/base.py:297` |
| `Assertion.target` 打在 scratch 上的 JSONPath | `src/gimbal/strategy/builtin/assertion.py:36-37` |
| 断言策略字段 | `src/gimbal/schema/strategy.py:80-88` |
| 执行链 = `gimbal run launch <case.json> -o jsonl` CLI 子进程 | `app/services/gimbal_launcher.py` |
| `orchestration` 与 `definition.steps` 严格同序同长 | `app/models/composer_scenario.py` |
| `scenarioId` 正则 `^sc-[a-z0-9-]+$` | `app/schemas/scenario_composer.py` |
| 路线图把自举定为 I1，排在 P4 之后，验收"不改 schema" | `docs/superpowers/plans/GIMBAL-待实现功能与路线图-2026-09-28.md` §2.9 |

---

## 8. 未解决 / 留待实现期决定

- **用例 YAML 的 schema**：编排器自定，第一版从简（按域分组的列表），不引入 P4-07 的 EndpointDoc 概念
- **`--check` 模式**：生成器是否需要 CI 友好的一次性检查模式（不写文件只比对）
- **`endpoints.json` 的版本策略**：暂用 `"1.0.0"`；plate 的 `CatalogVersion` 派生缓存机制会自动落基线，冲突处理留给 adaptation 批次
