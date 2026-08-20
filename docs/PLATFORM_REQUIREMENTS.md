# GIMBAL Platform · 用例配置 & 执行平台 · 需求规格说明书 V0.1

> ⚠️ **V3 现状说明（以本节为准，覆盖下文 V0.1 描述）**
>
> 本文档写于 V0.1 立项期，§3/§4.5/§5/§6/§10 中与执行链路、数据模型相关的
> 描述已被 V3 架构取代。当前实现（V3 场景编排版）：
>
> - **Case 层已解散**：场景（Scenario）是唯一挂载点。数据表
>   `composer_scenarios`（payload JSON 为唯一权威）、`composer_data_sets`、
>   `composer_envs`、`executions`；`cases` / `case_favorites` /
>   `hidden_field_profiles` 等表已随迁移删除。
> - **执行链路（V3）**：`POST /api/runs` → `run_dispatcher` 逐行 fan-out →
>   `gimbal run server` HTTP 服务（`POST /run`，默认 127.0.0.1:8766）。
>   **不再起子进程**，不再落临时 yaml；`executor.py` 子进程链路已退役。
> - **可观测面**：`executions` 表计数器（total/passed/failed/status）+
>   `data/runs/<date>.jsonl` 调度日志（运维直读文件，不经 API）。
>   **`exec_runs` 表、单 run 报告/日志/SSE 端点、run 级 rerun 均已退役**
>   （重跑 = 重新发起一次 `POST /api/runs`，by design）。
> - **服务拓扑**：gimbal-plate（8765，场景/策略语法服务）、gimbal run
>   server（8766，执行器）、backend（8000，uvicorn）、frontend（5173，Vite，
>   代理 `/api`→8000、`/plate`→8765）。
> - `executions.config_json` 存 V3 调度配方（camelCase）：
>   `{runId, scenarioId, dataSetIds, envId, exec_auth_alias, stepTo,
>   injectCredentials, nRuns, parallel, prefix, mergePolicy}`。
>
> 下文保留为历史设计记录，除本节所述覆盖项外，认证/用户管理（模块 A）、
> 认证管理（模块 D）等描述仍大体适用。

> 项目代号：**GimbalPlatform**
> 后端：FastAPI（Python 3.11+）
> 前端：Vue 3 + Vite + Element Plus / 自研组件（视觉接近 Prism）
> 与 Gimbal / Prism 关系：本平台是 **Gimbal 的 Web 化配置与执行前端**，使用 `gimbal run launch` 触发执行；视觉语言沿用 Prism Configurator（顶部固定栏 / 标签页 / 卡片堆叠 / 折叠 / 拖拽）。

---

## 0. 文档结构

1. 背景 & 目标
2. 与 Gimbal / Prism 对齐点
3. 技术栈 & 总体架构
4. **需求清单（覆盖认证 / 用例选择 / 用例配置 / 认证管理 / 用例执行）**
5. 数据模型（前后端契约）
6. FastAPI 接口约定（REST）
7. **识别出的需求不合理 / 缺失项（V0.1 待用户确认）**
8. 验收标准 & V0.1 MVP 范围
9. 非功能需求

---

## 1. 背景 & 目标

**目标**：把 Gimbal 中"结构化数据驱动用例"以 Web 页面形式提供给用户——让用户能：

1. **检索 / 选择**用例（公共用例 + 个人用例）；
2. **在线配置**用例的 `meta / resource / steps / config`，支持字段隐藏、自定义变量替换、认证用户绑定、步骤顺序拖拽；
3. **管理认证凭据**（URL / 别名 / 用户名 / 密码 / token_type）；
4. **执行用例**，支持提单号前缀、并发次数、并发度控制，并实时查看执行结果。

**直接用户用例**：测试 / 开发 / 业务 团队成员，上传流量或手写用例，沉淀为公共资产，被同 / 其他租户复用。

---

## 2. 与 Gimbal / Prism 的对齐点

### 2.1 Schema 对齐（Gimbal → 平台）

Gimbal 已有的数据契约（`gimbal/schema/`）直接成为本平台的数据结构：

| 平台概念 | Gimbal 类型 | 备注 |
|---|---|---|
| `Meta` | `gimbal.schema.Meta` | name / description / module / priority / author / owner / tags / version / expire / requirementRef |
| `Config` | `gimbal.schema.Config` | services / users / timePolicy / retry / vars / setup / teardown |
| `Resource` | `gimbal.schema.ResourceUnion` | 平台 V0.1 不渲染（仅占位），对应 UI 仅显示已有键 |
| `Step` | `gimbal.schema.Step` | description / api / request / strategy |
| `Api` | `gimbal.schema.Api` | service / method / path / headers / timeout |
| `Request` | `gimbal.schema.Request` | body（任意 JSON） |
| `Strategy` | `gimbal.schema.StrategyUnion`（Extract / Assign / Assertion） | V0.1 前端用 Monaco JSON 编辑器读写 |
| `AuthSession` | `gimbal.schema.AuthSession` | url / username / password / expires_in / token_type / token / expires_at |

**关键约束**：
- `Api.service` 必须是 `Config.services` 已存在的键；前端在切换 service 时校验一致性。
- `Config.users[alias]` 的 `alias` 即 template 中 `${auth.<alias>.token}` 用法；前端"认证管理"的"别名"字段就是这里 dict 的 key。
- `Config.vars` 与 CLI `--var` 行为对齐：平台在最顶层暴露 vars 编辑器即映射到 `Config.vars`。

### 2.2 视觉对齐（Prism → 平台）

沿用 Prism Configurator 的视觉规范：

- **顶部固定栏**（高度 48px，背景 `#1f2933`）：左侧平台 logo + StatusDot；中部 SCENARIO ID 输入；右上 撤销 / 重做 / 帮助 / YAML 预览 按钮；
- **Tab 行**：四类一级资源对应四个 tab，`meta / config / resource / steps`，每个 tab 自带颜色（紫 / 绿 / 黄 / 蓝），用 `--tab-color` / `--tab-bg` 控制；
- **卡片堆叠**：每个 tab 内容是一张大圆角卡片，padding 18×28；
- **控件**：`.fin` 统一输入框，`.tog` 滑块，`.sub-h` 小标题，`.tag-pill` 圆角胶囊（标签）；
- **拖拽**：步骤 / 标签 / 用户块可拖拽重排，复用 Prism 的 `.dragging / .prism-drop-target` 视觉；
- **Toast**：右上浮层 `success / error / info`；
- **图标库**：`tabler-icons` CDN，跟 Prism 一致；
- **响应式**：≤ 768px 标签宽度 / 字段宽度自动收缩。

> **关键差异**：本平台是**多页应用**（登录 / 用例列表 / 用例详情 / 执行），Prism 是单页 Configurator；视觉系统延续，但布局组件用 Vue + Element Plus（按钮 / 表格 / 表单 / Modal）或自研 CSS（沿用上面这套变量）。

---

## 3. 技术栈 & 总体架构

```
                ┌──────────────────────────────────────────────────┐
                │            Browser (Vue 3 SPA)                  │
                │   • Vue Router 4  • Pinia  • Element Plus        │
                │   • Monaco Editor (YAML/JSON 片段)              │
                │   • vuedraggable (拖拽)                          │
                └────────────────┬─────────────────────────────────┘
                                 │ HTTPS / JSON
                                 ▼
                ┌──────────────────────────────────────────────────┐
                │           FastAPI Backend (uvicorn)              │
                │   • JWT 鉴权（access + refresh）                 │
                │   • SQLAlchemy + SQLite (V0.1) / Postgres (V1)   │
                │   • 用户 / 认证 / 用例仓库 / 执行任务 4 个域    │
                │   • ShellOut → `gimbal run launch <yaml>`        │
                │   • 后台任务: APScheduler (or asyncio Task)      │
                └────────────────┬─────────────────────────────────┘
                                 │ subprocess / file IO
                                 ▼
                ┌──────────────────────────────────────────────────┐
                │       Gimbal 本地进程 (gimbal.exe / pip)        │
                │   gimbal run launch <path> -f yaml               │
                │   reports/*.html -> 平台落库 + 前端展示         │
                └──────────────────────────────────────────────────┘
```

| 关注点 | 选型 |
|---|---|
| 后端框架 | FastAPI 0.115+，依赖 SQLAlchemy 2.x、Pydantic v2 |
| 鉴权 | JWT（HS256，签名密钥 env `JWT_SECRET`），access 60min / refresh 14d |
| 存储 | SQLite + `data/` 目录（V0.1 内嵌）；Postgres（V1 可换驱动） |
| YAML 解析 | `PyYAML`（与 Gimbal 一致） |
| 执行触发 | 后端 `subprocess.run(["gimbal", "run", "launch", "<abs_path>"], …)` ；并发用 `asyncio.gather` + `Semaphore` |
| 前端构建 | Vite 5 + Vue 3 + TypeScript + Vue Router 4 + Pinia |
| UI 组件 | Element Plus（表格 / 弹窗 / 表单 / 抽屉）+ 自研 Configurator 视觉（同 Prism） |
| 状态管理 | Pinia（auth store / cases store / executions store / vars store） |
| HTTP | axios + 拦截器（401 刷新 token / 鉴权头） |
| 代码编辑器 | Monaco Editor（仅用于 JSON/YAML 片段：headers / body / strategy / resource） |

---

## 4. 需求清单

> 每条都给出 **前端 / 后端 / 接口** 三段说明；优先级标记 **P0 / P1 / P2**。

### 4.1 模块 A · 认证 & 用户管理 **【P0】**

#### A1 注册 / 登录
- **前端**：登录页（账号 + 密码）/ 注册页（账号 + 密码 + 确认 + 昵称）；表单校验；
- **后端**：`POST /api/auth/register` / `POST /api/auth/login` / `POST /api/auth/refresh` / `GET /api/auth/me`；
- **规则**：密码 ≥ 8 位必须含字母 + 数字；账号唯一；JWT 颁发。

#### A2 用户管理（仅管理员 V0.1 简化：账号自带管理员标志）
- 前端：用户列表 / 创建 / 启停；
- 后端：`GET /api/users`、`PATCH /api/users/{id}`、`DELETE /api/users/{id}`；
- 规则：不能删除自己；不能降级最后一个管理员。

#### A3 会话保持
- 前端在 axios 拦截器中 401 自动调 `/api/auth/refresh`，刷新失败则跳登录页；
- Pinia `authStore` 持久化 token 到 `localStorage`（access + refresh 双 token）。

---

### 4.2 模块 B · 用例选择页 **【P0】**

#### B1 主页（默认）= 我的工作台
- Tab 切换：**我的上传 / 我的收藏**（两个分区，分别由后端接口过滤）；
- 列表列：名称 / 模块 / 优先级 / 作者 / Tags / 更新时间 / 收藏 / 执行；
- 行为：
  - 点击行 → 跳 `/cases/{id}/config`（用例配置页）；
  - ⭐ 收藏图标切换（已收藏 → 取消；未收藏 → 加进收藏）；
  - ▶ 执行图标 → 跳 `/executions?caseId=xxx`（执行页）。
- 后端：
  - `GET /api/cases/mine?visibility=public|private|mine&favorites=true|false` → `{items, total}`；
  - `POST /api/cases/{id}/favorite` / `DELETE /api/cases/{id}/favorite`。

#### B2 公共用例库（独立页）
- 路由 `/cases/public`；
- 列表同 B1，但**只显示 visibility=public**；仅展示 + 收藏 / 复制到自己 / 在线配置；
- 后端：`GET /api/cases/public?page=&pageSize=&module=&q=&tags=`。

#### B3 用例上传（创建）
- **入口**：配置页顶部条"另存为" / 列表页"+ 上传用例"；
- 行为：选择本地 YAML 文件 / JSON 文件；后端解析；**校验失败禁止上传**；上传时选择 `visibility=public | private`；
- 后端：`POST /api/cases/upload`（multipart/form-data）→ 返回 caseId；
- 后端额外提供 `POST /api/cases/validate` 干跑 schema 校验。

#### B4 复制用例到我的列表
- 公共用例页面进入详情 → 顶部"复制到我的"按钮 → 后端 `POST /api/cases/{id}/copy` → 返回新 caseId，进入我的上传列表。

#### B5 搜索 / 过滤
- 顶部搜索框：按 name / module / description / tags；
- 高级过滤抽屉（Element Plus `el-drawer`）：module / priority / tags 多选 / author / 创建时间区间。

---

### 4.3 模块 C · 用例配置页 **【P0 - 核心】**

> 视觉与交互 1:1 对齐 Prism Configurator：顶部固定栏 → 四 tab（meta/config/resource/steps）→ 卡片堆叠 → 每个一级资源（meta/resource/steps/config）默认折叠可展开。

#### C1 一级资源结构（4 个 panel，**默认折叠**）
1. **Meta Panel**：name(必填) / description / module(必填) / priority / author+owner / tags（pill，可拖拽重排）/ version / expire 开关 / requirementRef；
2. **Config Panel**：services / users / timePolicy / retry / vars / setup / teardown；
3. **Resource Panel**：以 `key → resource` 字典形式展示（V0.1 仅字典查看，不做编辑，仅支持新增 / 删除 key）；
4. **Steps Panel**：步骤列表（每个 step 一个 step-card，**默认折叠**），详见 C5。

#### C2 字段隐藏规则（**需求明确：每个字段都支持配置，但允许设置为隐藏**）

> ⚠️ **真实用例深度痛点**：参考一份 27 步的业务用例，每一步都重复以下 8 个浏览器嗅探 header：
> ```
> sec-ch-ua-platform / sec-ch-ua / sec-ch-ua-mobile / Sec-Fetch-Site / Sec-Fetch-Mode / Sec-Fetch-Dest / Content-Type / Authorization
> ```
> 其中前 6 个（`sec-*` / `Sec-*`）对业务用例作者无意义，**默认就应当隐藏**。如果按 Prism 风格一刀全展开，配置页会立即变成 27×N 行的"墙壁"，无法使用。本节规则专门为这种重数据场景设计。

**隐藏粒度三层**（同时支持）：

| 粒度 | 作用范围 | 实现 |
|---|---|---|
| **L1 字段级** | 单个 key（如 `api.headers["sec-ch-ua-platform"]`） | 单字段右侧 👁 切换；写回 yaml 顶部 `x-hidden: [...path]` |
| **L2 路径模式** | 多次出现的 key 模式（glob：`api.headers["sec-*"]` / `api.headers["Sec-*"]`） | 平台扫描 yaml，正则识别高频 key；给出"批量隐藏"按钮 |
| **L3 全局预设** | 跨用例通用的"无意义 header"清单 | 平台内置一份，**新用例加载时即应用一次**——相当于 Pruning |

**L3 平台内置默认隐藏清单（V0.1）**：

```yaml
# 当 L3 被启用时，下列路径在加载用例后立即降噪
default_hidden:
  - api.headers["sec-ch-ua-platform"]
  - api.headers["sec-ch-ua"]
  - api.headers["sec-ch-ua-mobile"]
  - api.headers["Sec-Fetch-Site"]
  - api.headers["Sec-Fetch-Mode"]
  - api.headers["Sec-Fetch-Dest"]
  - meta.requirementRef            # AI 模板默认留空，本地用例无意义
```

平台也允许管理员在 `settings.json` 编辑 `default_hidden`，并提供"还原默认"按钮。

**持久化与作用域**：

| 维度 | 行为 |
|---|---|
| 持久化的位置 | 用户级：`hidden_field_profiles(user_id, scope, pattern, hidden_paths)` —— `scope = global`（默认预设）/ `case_id`（用户对单用例的偏好）；**不写回 yaml**，仅供前端使用 |
| 写入 yaml 还是 DB | **只写 DB**；导出 yaml 时 **保留原字段**（仅前端 UI 隐藏）以保证执行时与原样一致 |
| 多人协作 | A 用户隐藏 `sec-ch-ua*`，B 用户看见——每人独立偏好，不互相影响 |
| 显示隐藏字段 | 顶部固定栏右侧 toggle "👁 显示隐藏"；开启后**所有** L1/L2/L3 隐藏字段以灰色 `~~strike~~` 形式呈现，可正常编辑但视觉弱化 |

**批量隐藏 UI**（首次加载 27 步用例时弹一次，或顶部有"批量隐藏"按钮）：
```
┌────────────────────────────────────────────┐
│ 检测到用例里频繁出现以下 6 个字段，是否批量隐藏？    │
│  ┌── sec-ch-ua*     ⚪ 跳过  ⚫ 隐藏         │
│  ┌── sec-ch-ua-platform  ⚫ 隐藏              │
│  ┌── Sec-Fetch-*   ⚫ 隐藏                    │
│  [ 应用到所有 step ]  [ 仅本 step ]  [ 不再提示 ]  │
└────────────────────────────────────────────┘
```

**未来扩展**（V1+）：用户级"我的偏好"页面，看到所有被自动 / 手动隐藏的项，可统一还原。

#### C3 自定义变量替换（**需求明确：最顶层暴露 vars 编辑器**）
- Config Panel 顶部一个"🔧 全局变量"区块即 `config.vars`；
- 表格形式：key / value / 备注；新增一行 / 删除一行；
- 表格**不存在于 step 内**——vars 在整个 scenario 共享作用域，等价 Gimbal `Config.vars`；
- 渲染时编辑器右侧提供"使用 ${var.xxx}"提示 chip；Gimbal 模板规则：`${var.foo}` / `${auth.<tag>.token}` / `${service.<name>}` — 平台不做新模板，原样透传 Gimbal 解析；
- 保存到 `Config.vars` 后由 Gimbal preprocessor Phase 1.5 接管（CLI 风格等价 `gimbal run launch <yaml> --var k=v`，但平台只写 scenario.vars，不调用 CLI，因为 execute 阶段统一走 launch）。

**两种变量用法均支持**：

| 用法 | 形态 | 示例 |
|---|---|---|
| **字面量（literal）** | `Config.vars.<name> = "<字符串>"` | `bl_no: "YUEMU-YIHANGDAO-00016"` |
| **生成式 spec（generator）** | `Config.vars.<name> = { kind: <spec>, ... }` | `{ kind: uuid }` / `{ kind: seq, prefix: "BIZ", width: 4 }` / `{ kind: random_int, min: 100, max: 999 }` |

**真实用例特征**（基于 `Scenario_Test_9.json`）：
- 该用例的 `vars` 全部是字面量业务 ID（`bl_no` / `finance_id_1` / `bank_id_1` 等），平台默认值即 **literal 模式**；
- 执行时刻的"提单号前缀"（见 §4.5 E3）让用户可以**在执行抽屉填前缀字符串**，平台自动追加 `Config.vars[<var_name>] = "<prefix>"`，例如：
  ```yaml
  config:
    vars:
      prefix: "BIZ2024"      # 平台注入（来自执行抽屉）
      order_no: "ORDER-${var.prefix}-${exec.seq}"   # 平台主动写入的生成式
  ```
  其中 `${exec.seq}` 是平台在执行时**额外维护**的运行时变量（每跑一次 N=1..N 自增），注入到临时 yaml 的 `vars.seq`；Gimbal preprocessor Phase 1.5 解析生成式 spec 时已有该 key，所以可被 `vars.order_no` 解析。

**平台生成式 spec 内置支持**（V0.1）：
- `kind: uuid` → 32 字符 UUID（去连字符 8 位短形式可选）
- `kind: seq` → 自增整数，从 1 起，每次执行重置（依赖平台端 `exec.seq`）。
  gimbal 同时接受历史别名 `kind: sequence`；推荐用 `seq` 以避免歧义。
- `kind: timestamp` → Unix epoch 秒

复杂生成式（基于别的 var 计算 / 哈希等）由用户在 yaml 里手写"取巧"模板，例如 `"${var.prefix}-${var.seq}"`，Gimbal preprocessor 已支持 string concatenation via `${}` 引用。

#### C4 认证用户绑定（**需求明确：headers 里选 auth 用户，key 可选 Cookie/Authorization 等**）
- 在 Api.headers 区域内，"key" 输入框旁边加"ⓘ"按钮弹出选择器：
  - 左列：从 **`auths` 表中当前用户的全部自存凭证**列出（alias 显示形如 `codfish / https://...`）；**注意：数据源是 §4.4 D 模块，不是本 yaml 的 `Config.users`**——这两份数据相互独立；
  - 右列：可选 key（`Authorization` / `Cookie` / `X-Token` / 自定义）；
  - value 自动渲染为 `${auth.<alias>.<key>}`；
- 选择后写入 `api.headers[key] = "${auth.<alias>.token}"`（或 `cookie/value` 等其他 key），运行时由 Gimbal 解析为 token；
- **alias 一致性先决条件**：选中的 alias 必须存在于 §4.4 D 的 `auths` 表中（即"在执行时刻由'执行用认证'挑中"）；前端编辑器此时不做拦截，仅在 §4.5 E3 校验阻断；
- token_type 在认证管理页配置；模板中 `${auth.<alias>.token_type}` 也可暴露。注意 Gimbal preprocessor 仅按字面替换，并不会自动把 `${token_type} ${token}` 拼成 `Authorization: Bearer xxx`；若需要完整 `Authorization: <type> <token>` 字符串，可写完整字面值 `${auth.<alias>.token_type} ${auth.<alias>.token}`——前提是 `auth_header` 字段会在认证成功后的 `apply_token` 时被填回；如果失败，则只暴露独立 token 而非整段 auth_header。
- 本 yaml 的 `Config.users` 也保留一份可见/可编辑（沿用 Prism 能力），二者可并存——执行时按 §4.4 D3 合并策略决定如何处理。

**真实用例特征**（基于 `Scenario_Test_9.json`）：
- `token_type` 字段允许是字面量 `"Authorization"`（非默认 Bearer），即"`Authorization` 即作为 token 名前缀"。平台在 `token_type` 下拉中需要支持**"无前缀（粘贴原始 token 值）"** 这一选项；
- `Config.users.codfish.token_type: "Authorization"` 即"模板使用方直填整段 Authorization header 值"的语义——平台需要：
  1. **D1**：`token_type` 下拉选项：`无（前缀由 Bearer / Basic / Cookie / Custom 自填）` / `整段 Authorization 头` / 自定义；
  2. **C4**：当 token_type 选了"整段 Authorization 头"，前端编辑器自动把 value 渲染为 `${auth.<alias>.token}`（不再加前缀）；
- 27 步用例每步的 `Authorization` header 引用同一个 `${auth.codfish.token}`——平台支持"全选 all steps 的 `Authorization` header → 批量绑定到 alias codfish"的一次性动作。

#### C5 步骤列表（**需求明确：steps 中的 step 拖拽**）
- step-card 列表使用 `vuedraggable`；
- 每个 step 展开后 sub-tab：`description / api / request / strategy / assertions`；
- step 顶部条：序号 / method-pill / service.path / 折叠按钮 / 删除按钮 / cURL 复制按钮 / 状态徽章；
- step 子区拖拽：strategy（断言列表）同样支持重排；每个 strategy 用 `.strategy-item` 行（沿用 Prism 风格）；
- step 删除前 confirm 弹窗（沿用 Prism confirm-modal）；

#### C6 拖拽一致性
- meta.tags、config.services、config.users、config.vars、steps 全部支持拖拽（`vuedraggable`），操作风格统一。

#### C7 保存 / 导出 / 修改 / 另存（**需求明确**）
- 顶部条右侧新增：
  - **导出 YAML**：把当前 in-memory scenario dump 为 yaml，下载或复制；
  - **修改**：直接 PATCH `/api/cases/{id}`（仅当 `ownerId == me`，否则按钮 disabled）；后端写回 YAML 文件（覆盖原文件，`updated_at` 更新）；
  - **另存为**：弹输入框接收新名字 `name`，`POST /api/cases/{id}/save-as`，存到我的列表（私有 visibility=private）；原文件不动；
- **完整性校验**：所有出口（导出 / 修改 / 另存）→ 后端再用 `Scenario.model_validate(payload)` 校验一次（沿用 Gimbal）；
- 校验失败：弹 toast 提示具体路径，并阻止提交。

#### C8 取消 / 重做（沿用 Prism）
- 全局 50 步 undo stack；快捷键 Ctrl/⌘+Z / Ctrl/⌘+Y / 1..4；
- 仅作用于当前 case（路由切换清空栈）。

#### C9 帮助弹窗
- 帮助 Modal 沿用 Prism Help 弹窗内容并扩展（拖拽说明 / 隐藏字段 / 变量使用）；快捷键 `?` 触发。

---

### 4.4 模块 D · 认证管理页 **【P0】 · 用户级独立凭证池**

> ⚠️ **本模块是独立的用户凭证池，与用例文件无绑定关系。**
> 也就是说：用户在 D 里登记的凭据**不写到**用例 yaml 中；只在 §4.5 用例执行时通过"执行抽屉"的"执行用认证"显式选择一个（或多个）alias 注入到本次临时 yaml 的 `Config.users` 段落。

#### D1 列表页 `/auths`
- 字段：别名（唯一 key）/ URL / 用户名 / 密码 / token_type / expires_in / 操作（编辑 / 删除 / 测试）；
- 顶部"+ 新增认证"按钮 → 抽屉式表单（Element Plus Drawer）。
- 后端：
  - `GET /api/auths?page=`
  - `POST /api/auths` 创建：body `{alias, url, username, password, expires_in, token_type}` —— 不带 `owner_scope`，V0.1 一律 self
  - `PATCH /api/auths/{id}`
  - `DELETE /api/auths/{id}`
  - `POST /api/auths/{id}/test` 实际调认证接口验证密码正确性；返回成功 / 失败及新 token。
  - `GET /api/auths/{id}/fetch-token` 在执行准备阶段被后端调用，向用户库内的 url 发认证请求，将临时拿到的 token 落到执行态缓存中；调用者必须为本人。

#### D2 数据规则（**self 视角**）
- **可见性**：列表只列当前登录用户的 `auths`；admin 也没有"共享认证池"能力（见 §7.3.8）；
- `alias` **同一所有者（user_id）内唯一**；用例代码里写 `${auth.<alias>.token}` 必须用此 alias；
- 密码数据库用 **Fernet 对称加密**（env `FERNET_KEY`），列出 / 详情默认 mask `<REDACTED>`；编辑时需要"显示密码"动作；
- token_type 默认 `Bearer`，下拉可选：`Bearer / Basic / Cookie / Custom Header`；选 Custom 时多一个输入框填 key 名。

#### D3 与用例文件 / 执行的关系（关键边界）
| 关系 | 行为 |
|---|---|
| D 与 yaml `Config.users` | **完全解耦** —— D 改 / 删 / 加 不影响任何 yaml；用例 yaml 修改也不会触碰 D 的凭据 |
| 用例 yaml 可有可无 `Config.users` | V0.1 允许 yaml 里就硬编码 `users`（沿用 Prism 的能力）；也可全空，由执行瞬间注入；执行时按"覆盖/合并/忽略"策略生效，见下表 |
| 执行时如何注入 | §4.5 E2 "执行用认证" 选 1~N 个 alias → 渲染临时 yaml 时按策略合并 → 后端不修改磁盘上的原 yaml |

**yaml 中 `Config.users` 与执行期注入的三种合并策略（V0.1 默认 A）**：

| 策略 | 行为 | 适用场景 |
|---|---|---|
| **A. 替换（override，V0.1 默认）** | 临时 yaml 的 `Config.users` 完全用"执行用认证"列表生成，原 yaml 的 `users` **整体丢弃** | 公共用例作者未编任何 `users`，由执行人全权注入；alias 必须全部可解 |
| **B. 合并（merge）** | 原 yaml 的 `users` 保留，新选择的认证以 alias 为 key **仅覆盖**同名 alias，其他保留 | 用例自带部分内部测试用户 + 借平台密码补一两个 |
| **C. 仅追加（append）** | 原 yaml 的 `users` 全部保留，新选择的以新 alias **追加** （冲突时报错） | 极少数场景，V0.1 不开放 UI，CLI 留口 |

> 默认 A 选的理由：公共用例作者不该误传用户密码，让执行人负责注入更安全。

#### D4 alias 一致性校验
- 配置页 C4 选 auth 用户时，**下拉数据源仅来自当前用户 D 模块的 `auths` 列表**；
- 用例 step 写死 `${auth.<alias>.token}` 但 alias 不在执行人选的执行用认证列表里 → 后端拒绝启动执行，返回 400 `{"code": 4400, "msg":"missing auth alias '<x>'"}`，前端在抽屉里把缺失项红框高亮；
- 提示："用例中引用的 alias `xxx` 不在你的执行用认证中，请先到 §4.4 认证管理添加或换一个执行认证"。

---

### 4.5 模块 E · 用例执行页 **【P0】**

> ⚠️ **关键数据流边界**：用例 yaml 与认证管理（D）模块是**独立**的两份数据。
> 用例 yaml 可有可无 `Config.users`；无论 yaml 里有没有，**只有执行时刻**，平台才会按"执行用认证"列表 + §4.4 D3 合并策略，把 `auths` 表里的凭据注入到本次临时 yaml 的 `Config.users`，供 Gimbal preprocessor 在 `${auth.<alias>.token}` 解析时使用。
> 磁盘上的原 yaml **永远不会被认证信息写入或覆盖**。

```
        你的认证管理（D）                你的用例 yaml（可能空 users）
        ┌──────────────┐                ┌──────────────────────────┐
        │ auths 表      │                │ users: {} 或硬编码       │
        │  alias=qa1    │                │                          │
        │  url=...      │                │ step1.headers:           │
        │  user/pwd     │                │   Auth: ${auth.qa1.token}│
        └──────┬───────┘                └──────────┬───────────────┘
               │                                    │
               │  E2 选"执行用认证"                  │ 选中此 yaml 执行
               │        ▼                           ▼
               │   ┌─────────────────────────────────────┐
               └──▶│ 临时 yaml (data/tmp/exec_xxx.yaml)   │
                   │  users: { qa1: {....（注入而来）} } │
                   │  其余字段与原 yaml 一致             │
                   └────────────────┬────────────────────┘
                                    ▼
                          gimbal run launch <临时 yaml>
                          preprocessor 替换 ${auth.qa1.token}
                                    ▼
                                report HTML
```


#### E1 列表 = 收藏 + 我自己上传
- 复用 B1 同一接口，叠加 `favorites + mine` 两状态合集显示；
- 列后附：[执行] 按钮 → 弹"快速执行抽屉"。

#### E2 快速执行抽屉（点击执行按钮打开）

> 抽屉内最关键的字段是 **"执行用认证"** —— 它决定本次执行以哪个用户的凭证登录，而不是从用例文件读取。要与 §4.4 / 5 中的 `auths` 表对齐理解。

字段：
- **执行用认证**（多选，**必填 1~N**）：下拉列出 `GET /api/auths` 当前用户的全部 self 凭证，按 alias 排序。每条形如 `codfish | https://fin-tidb... | Bearer`；可搜索过滤；
- **默认 token_type**（下拉，默认跟随第一个选中的认证，可下拉切换 `Bearer/Basic/Cookie/Custom Header`）：仅作用于"执行用认证"未指定的字段（V0.1 仅留底，UI 默认禁用，V1 解锁覆盖）；
- **合并策略**（单选，参考 §4.4 D3）：
  - `override`（默认）：原 yaml 的 `users` 整体替换为"执行用认证"列表；
  - `merge`：原 yaml `users` 保留，alias 同名覆盖；
  - `append`：原 yaml `users` 保留，仅追加；
- **提单号前缀**（文本，可选）：会写入 `Config.vars[order_no_prefix] = "<前缀>"` 或类似命名（生成式 spec 见 E3）；
- **执行次数 N**（数字，1-1000，默认 1）；
- **并发度**（数字，1-200，默认 = N）：后端 `Semaphore(<并发度>)`；
- **超时秒数 / 单次重试**（来自 `Config.retry`；UI 可覆盖）；
- **环境**（`dev` / `prod`，默认 `dev`）：透传 `gimbal run launch --env=<env>`。

#### E3 执行触发（**严格区分认证池与用例 yaml**）

后端处理流程：

1. **校验 alias 一致性**：扫描当前场景所有 `${auth.<alias>.token}` / `${auth.<alias>.*}` 引用 → `referenced_aliases`；与"执行用认证"列表比对 → 缺失集合缺失则直接拒绝（400 + D4 错误码）；多选但未引用的 alias 给出 warning，不阻断。
2. **临时 YAML 落盘**：渲染当前 scenario 对象 → 按合并策略构造新的 `Config.users` → `yaml.safe_dump` 到 `data/tmp/exec_<executionId>_<idx>.yaml`（**注意磁盘上原 yaml 始终不动**）。
3. **生成 vars / 提单号**：把提单号前缀落入 `Config.vars`：
   ```yaml
   config:
     vars:
       order_no_prefix: "<用户输入的前缀>"
       # V0.1 也可包含生成式 spec，如：
       # order_no_seq:
       #   kind: uuid4
   ```
   Gimbal preprocessor Phase 1.5 接管。
4. **触发 N 次独立子进程**：
   ```python
   async with Semaphore(concurrency):
       await asyncio.gather(*[run_one(idx) for idx in range(N)])
   ```
   每次 `run_one(idx)`：
   - 调 `subprocess.run([GIMBAL_BIN, "run", "launch", yaml_path,
                          "--env", env, "--report-dir", report_dir,
                          "--parallel", "1"], capture_output=True)`
   - 退出码 0 → passed；非 0 → failed；
   - 解析 stdout / stderr 落到 `exec_runs`。
5. **报告聚合**：每份 `--report-dir/yyyymmdd/exec_<executionId>_<idx>.html` 是 Gimbal 原生输出；后端把 `report_dir` 路径存到 `execution_record.report_dir`，前端通过 `GET /api/executions/{id}/report/{idx}` 静态拉 HTML 渲染。
6. **资源清理**：临时 yaml 保留到执行结束，7 天后清理（`data/tmp`）。

#### E4 实时进度（V3：轮询计数器）
- 前端 1s 轮询 `GET /api/executions/{id}`（计数器快照）；
- **V3 起 run 级状态徽章 / 报告链接 / WS / SSE 已全部退役**；每-run
  调度明细在 `data/runs/<date>.jsonl`（服务端文件，不经 API）。

#### E5 结果保留
- DB 表 `executions(id, scenario_id, owner_id, status, total_runs, passed,
  failed, config_json, started_at, finished_at, created_at)`；
- **`exec_runs` 表已随 V3 退役**（init_db 幂等 DROP）；
- 每-run 调度日志 `data/runs/<date>.jsonl` 按需创建、追加写入。

---

## 5. 数据模型

> 仅列平台自有表；Gimbal 原 schema 不变，通过 `case.yaml` 文件落地存。
> ⚠️ `auths` 表与 `cases` 表之间**没有外键**。即 auths 行的增删并不影响任何用例文件；用例 yaml 的 `Config.users` 也是独立在文件里的。两者只在执行瞬间（§4.5 E3）通过 alias 字符串发生关系。

```sql
-- 用户
users (id PK, username UNIQUE, password_hash, display_name, is_admin, is_active,
       created_at, updated_at)

-- 用例元数据（实际定义在 .yaml 文件里；这里只存引用 + 业务信息）
cases (
  id PK,
  case_id TEXT UNIQUE,                -- 与 scenario.scenarioId 同
  name TEXT,
  module TEXT,
  visibility TEXT CHECK(visibility IN ('public','private')),
  owner_id FK -> users.id,
  file_path TEXT,                     -- 例: data/users/{user}/cases/{case_id}.yaml
  -- 公共用例文件单独存: data/public/cases/{case_id}.yaml
  created_at, updated_at, deleted_at
)

-- 收藏
case_favorites (user_id FK, case_id FK, created_at, PRIMARY KEY(user_id, case_id))

-- 认证管理
auths (
  id PK,
  alias TEXT, -- 唯一：当前用户名下唯一
  url TEXT,
  username_enc TEXT,
  password_enc TEXT,        -- Fernet
  token_type TEXT,
  expires_in INTEGER,
  owner_id FK -> users.id,
  -- V0.1 不做 shared，先省
  created_at, updated_at
)

-- 执行总记录
executions (
  id PK,
  case_id TEXT,
  owner_id FK,
  started_at, finished_at,
  total_runs INT, passed INT, failed INT,
  status TEXT,              -- queued/running/done/failed
  config_json JSON,         -- 含 N / parallel / env / execAuthAlias / prefix
  report_dir TEXT
)

-- 执行单条 run
exec_runs (
  id PK,
  execution_id FK,
  idx INT,                  -- 1..N
  started_at, finished_at,
  exit_code INT,
  status TEXT,              -- pending/running/passed/failed
  report_path TEXT,
  duration_ms INT
)

-- 隐藏字段 meta（per user, per case）
hidden_field_profiles (user_id FK, case_id TEXT,
                       hidden_paths JSON,    -- ["meta.priority", "config.users.codfish.password", ...]
                       PRIMARY KEY(user_id, case_id))
```

---

## 6. FastAPI 接口约定（节选）

> 所有路由前缀 `/api`；除 auth 公开外需 Bearer token。返回格式统一为：`{code: 0, data, msg}`，错误时 `code != 0`。

| Method | Path | 说明 |
|---|---|---|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录，返回 access+refresh |
| POST | `/auth/refresh` | 刷新 access |
| GET | `/auth/me` | 当前用户 |
| GET | `/cases?scope=mine\|favorites\|public&page=&q=&module=&tags=` | 用例列表 |
| GET | `/cases/{case_id}` | 详情（返回完整 scenario yaml 解析对象） |
| POST | `/cases/upload` | 上传用例（multipart，body = YAML 文件） |
| POST | `/cases/validate` | 仅校验 schema |
| PATCH | `/cases/{case_id}` | 修改用例（仅 owner） |
| POST | `/cases/{case_id}/save-as` | 另存为 |
| POST | `/cases/{case_id}/copy` | 复制公共用例到我的（私有） |
| POST | `/cases/{case_id}/favorite` / DELETE | 收藏切换 |
| GET | `/auths` | 我的认证 |
| POST | `/auths` | 创建 |
| PATCH | `/auths/{id}` | 修改 |
| DELETE | `/auths/{id}` | 删除 |
| POST | `/auths/{id}/test` | 测试连通性 |
| POST | `/executions` | 触发执行 |
| GET | `/executions/{id}` | 执行总览 |
| GET | `/executions/{id}/runs` | 每次 run 状态列表 |
| GET | `/executions/{id}/report/{idx}` | 取回单次 report HTML（来自 Gimbal `report_dir`） |
| GET | `/users` / `PATCH /users/{id}` | 用户管理 |

WebSocket：`/ws/executions/{id}`（V1；V0.1 用轮询）。

---

## 7. ⚠️ 需求不合理 / 缺失 / 待确认项（必须澄清）

> 在动手开发前请您逐条确认；这些地方是我额外识别出的问题，写入需求文档以追溯。
> 已确认项以 **✅** 开头。

### 7.1 范围与权属边界
1. **公共用例修改权限未明**：原文"修改 则直接修改存储的原文件（只能改自己上传的）"，意味着 **公共用例** 只能配置但不能修改原文件。但另存为能创建副本吗？需要明确：**公共用例 → 进入配置页后，只读 / 可改但保存另存为副本 / 还是允许覆盖公共原文件？（建议默认：公共用例在配置页 read-only，写入一律走"另存为"）**
2. **公共区域写入策略未明**：原文"用户上传时，支持上传到公共或者私人路径下"，但平台应不应该有"公共空间管理员审批"流程？V0.1 建议：**任何人上传公共用例，先入库 visibility=public 但 platform_admin 角色才可标记"已审核"；未审核的公共用例在公共列表置底 + "未审核"标签**。需要您确认或简化。
3. **收藏夹容量上限**：收藏夹是否限 100 / 500 / 不限？建议默认不限制。

### 7.2 用例结构相关
4. **`resource` 字段**：原文提到"列出一级资源（meta, resource,steps,config）"，但 Gimbal 的 `resource` 字段是 `dict[str, ResourceUnion]`（包含 db / mock / file / variable 等多种 kind）。**需求仅"列出"即可吗？还是支持拖拽 + 编辑？建议 V0.1 仅展示 / 添加 / 删除 key（不编辑内容），完整编辑留 V1**。
5. **`setup` / `teardown` 字段**：原文未提。Gimbal 中这两个是 `Config.setup: list[SetupUnion]`。建议 V0.1 默认折叠为单条占位（`+ setup` / `+ teardown`），与 resource 同样简化。
6. **自定义变量替换 vs `vars` 注入机制**：原文"在最顶层支持自定义配置替换。其实就是映射了 config 中的vars进行替换"——平台只暴露 `Config.vars`，**不建议**再另造一套顶层 key→value 替换语法，以免双语法混淆。请确认。
7. **`requirementRef`**：当前 Schema 里是 `list[RefBase]`，引用资产层；V0.1 建议前端展示为"字符串数组"（简化）。请确认简化可接受。

### 7.3 认证侧
8. **认证管理页的"共享"语义**：原文给出 `users.codfish` 示例，但没有解释页面是"我的私有认证"还是"平台公共认证池"？建议：**v0.1 只做"我的私有认证"**（每个用户各自维护；用例执行时只能选自己的认证），公共认证池留 V1。需要您确认。
9. **✅ 已确认：认证管理 ↔ 用例 `Config.users` 是两份独立数据**。
   - **认证管理页** 是**用户级独立凭证池**（`auths` 表），与任何用例文件无强绑定。
   - 用例文件 `Config.users` 是另一份（在 YAML 内），可以为空、可以是作者硬编码用户、也可以两者并存 —— 但**只有执行时刻**才会把"选中的认证"以 `Config.users[alias] = <auth>` 临时注入到本次生成的临时 yaml 里。
   - 别名（alias）必须两边一致才生效：即用例 step 写 `${auth.codfish.token}`，执行选凭证时也只能选 alias=`codfish` 的那条，否则预处理器查不到会抛 `KeyError`。
   - 详情同步到 §7.3-A 与 §4.5。

### 7.4 执行侧
10. **"用例名触发执行"`gimbal run launch 用例名`"**：原文称"调用 gimbal run launch 用例名触发用例执行"，但 **`gimbal run launch` 只接受文件路径 / '-' stdin / --inline**，不接受名字。可能的解读：
    - (a) `gimbal run scenario <id>` 触发走资产仓库；
    - (b) 把用例落盘为 yaml 后 `gimbal run launch <yaml_path>`；
    - (c) 通过 `gimbal run server` HTTP 通信触发。
    建议默认 **(b)**：执行时把当前 scenario 渲染成 yaml → 落盘 → `gimbal run launch <abs.yaml>`。需要您拍板。

11. **并发执行次数 N 与 Config.retry 的关系**："执行次数 N=10 次并发"是平台调 N 次 launch 进程，每个进程内部 Gimbal 不会再跑 N 次；这与您说的"启动并发线程调用 gimbal run launch 用例名"一致。但**单次 launch 内部 --parallel 与外部进程并发是两件事**，请您确认：平台 N=10 即 **10 个独立 gimbal 进程**（每个进程内 --parallel=1）。
12. **提单号前缀生成式**：前缀 `prefix` 是仅作为字面量字串？还是要配合 `uuid()` 生成变量？建议：在 vars 里加 `{prefix: prefix}` 字面量；如果用户想编号 + uuid，由用户在 vars 里手动写。如果只想用平台内置"runtime_vars"模板（如 `${exec.seq}`），可在文档中说明但 V0.1 不做。
13. **失败重试**：执行次数内若某次失败是否自动重试？建议：**N 次之间不做重试**，由用户在 Config.retry 里配 step 内的重试 — 平台不再叠加重试层，避免计数不准。

### 7.5 UI / 交互
14. **步骤 vs 资源 拖拽**：需求明确支持资源拖拽，但 `resource` 是 dict 形式，**Key 拖拽** vs **整个 resource entry 拖拽**是两种语义，建议做 key 拖拽 + 上下移位。
15. **monaco 编辑 vs 表格编辑**：策略/headers/json body 用 monaco JSON，但 headers 也支持每行 key-value。新增按钮"T"切换表格 / JSON 两种模式，与 Prism 风格一致即可。
16. **隐藏字段的"还原"**：字段被隐藏后能否一键恢复？建议：右上角 toggle"显示隐藏字段"统一管理所有"已隐藏字段"的临时显示 + 永久还原按钮。
17. **用例版本控制**：现在描述里没有"修改历史 / diff / 回滚"概念。是 V1 才有，还是 V0.1 简单做"最近 5 个 yaml 版本快照"？建议 **V0.1 不做版本控制，但保留每次修改的 updated_at 记录**。
18. **多人协作冲突**：用例被 A 编辑时 B 也打开 → 平台如何处理？建议 V0.1 **最后写入者获胜 + 乐观锁 ETag（If-Match）**；并发冲突返回 409，前端弹 diff 让用户选择。
19. **角色权限**：
    - 普通用户：可见公共 + 可上传私有 / 公共、可改自己私有；
    - 公共用例管理员（admin 标志）：可修改任何公共用例 + 删除任何公共用例 + 标记已审核；
    - 请确认 admin 角色权限范围是否覆盖以上。

### 7.6 部署 / 环境
20. **多平台可执行文件**：`gimbal.exe` 已经在 `D:\Capture\Scripts\` 下。后端启动时如何定位 gimbal 可执行文件？建议：
    - 优先环境变量 `GIMBAL_BIN`；
    - 默认 `gimbal` 走 PATH；
    - V0.1 在 Windows 上跑通即可；Linux/macOS 留 V1。
21. **gimbal run launch 的报告目录**：`--report-dir` 是相对路径，建议后端解析为绝对路径 `data/reports/<executionId>/`，并把 HTML 通过 `/executions/{id}/report/{idx}` 静态暴露。
22. **数据存储隔离**：建议 `data/{config.yml, app.db, users/<u>/cases/*.yaml, public/cases/*.yaml, reports/<execId>/*.html}`，全部纳入 `.gitignore`。

### 7.7 验收需要
23. **P0 MVP 演示场景**：建议默认内置一个例子 `data/public/cases/hello-login.yaml` + 一个测试 token 用户，作为模板示例。可接受？
24. **首页默认**：原文"主页优先进入用户自己的用例列表页，公共用例列表页作为单独一页"——确认：登录后默认 `/cases/mine`（顶部 tab = 我的上传 / 我的收藏），`/cases/public` 用顶部导航条切。

---

## 8. 验收标准 / V0.1 MVP 范围

### 8.0 真实用例验收基准（基于 `gimbal-tmp/Scenario_Test_9.json`）

> 平台 V0.1 完成后，**必须能流畅渲染下面这份 3856 行的真实用例**：

- scenario `e2e订单到应收核销`（中文字符作 ID）
- 27 个 step；每步同样的 8 个 header（其中 6 个为浏览器嗅探 noise）
- 25+ 个 strategy 项类型混合（assertion / extract / assign），assign 的 target 多为 `$.request_body.<...>` 或 `$.request_body.<...>[0]`
- `Config.users.codfish.token_type: "Authorization"`（非默认）
- `Config.vars` 5 个全为字面量业务 ID

##### 关键验收要求

1. 加载该 yaml → 列表首屏 ≤ 1s；
2. 默认折叠 + L3 预设隐藏后，**视觉噪声行 ≤ 用例真实字段数的 30%**；
3. `token_type: "Authorization"` + `headers.Authorization: ${auth.codfish.token}` 这一组合在执行页能正确解析（详见 C4 + §4.4 D1）；
4. 修改后 yaml 写盘与原 schema 校验 100% 通过；
5. 27 步用例的执行抽屉能立刻识别 `${auth.codfish.token}` 缺失并拦截。

### 8.1 MVP 范围

**MVP 范围（P0）**：

- [x] 认证：注册 / 登录 / JWT
- [x] 我的工作台：上传 / 收藏 / 我的上传 tab
- [x] 公共用例库：独立页 + 复制到我的
- [x] 用例配置页：4 tab / 折叠 / 拖拽 / 字段隐藏 / 顶层 vars / headers 引 auth / 导出 yaml / 修改 / 另存 / 复制
- [x] 认证管理页：增删改查 + 密码 Fernet 加密 + 测试连通
- [x] 用例执行页：抽屉配置 + N 次并发 + 提单号前缀 + 实时状态 + 报告链接

**P1 / V1**：
- 公共认证池 / 管理员审核 / 完整 version history / WebSocket 实时推送 / 单点登录 / 主题切换 / 多端共享 admin token

**验收场景（来自原文 + 补充）**：

| 场景 | 验收步骤 |
|---|---|
| 1. 注册登录 | 新用户注册 → 登录 → 进入 `/cases/mine` |
| 2. 上传用例 | 上传一份 hello-login.yaml → 在"我的上传"看到 |
| 3. 配置用例 | 进配置页 → 改 name / 拖拽 step 顺序 / 隐藏 priority → 修改保存 → 重新加载验证 |
| 4. vars 替换 | 在 config.vars 加 `region = "cn-east"` → step headers 用 `${var.region}` → 导出 yaml 验证字段 |
| 5. headers 引 auth | 认证管理新增 `alias=qa1` 用户 → 配置页 headers 选 alias=qa1 / key=Authorization → value 自动为 `${auth.qa1.token}` |
| 6. 收藏 | 公共用例列表 → 点 ⭐ → 我的收藏 tab 出现 |
| 7. 复制 + 另存 | 公共用例 → 复制到我的 → 我的上传出现私有副本 |
| 8. 并发执行 | 执行抽屉：N=10, 并发=3 → 后端开 10 次子进程 → 实时表格显示 10 个 run 状态 → 全部结束后展示总耗时 / pass / fail |
| 9. 提单号前缀 | 输入前缀 `BIZ2024` → 生成 yaml `Config.vars.biz_key = BIZ2024-xxxx`（生成式 spec）→ 单次 run 后能在 step request body 中找到这个值 |
| 10. 报告 | 点单 run 链接 → 弹出 Gimbal 报告 HTML |

---

## 9. 非功能需求

- **响应性能**：列表页首屏 < 800ms；配置页切 tab < 200ms；
- **大用例场景（基于真实 27 步用例）**：
  - 一份 27 步用例平均每步 8 个 header + 5 个 strategy 项 → 渲染首屏应 ≤ 1s；
  - 默认折叠所有 step（**仅渲染 step header 行**），展开后才挂载 step 详情 → 避免一次性 mount 380+ 节点；
  - 拖拽 step 重排：仅在折叠行层面交换位置，**不要在重排时 touch Vue `<draggable>` 子节点全部重建**（vuedraggable 默认行为是 use-vue3 版本支持的，避免重排大节点 O(N) 重建）；
- **执行并发**：平台后端默认 Semaphore=20 并发任务；
- **可观测性**：FastAPI access log + 关键业务事件 stdout（CaseCreated / ExecutionStarted / ExecutionFinished）；
- **审计**：所有修改写 `audit_logs(id, user_id, action, target_id, payload_hash, at)`；
- **安全**：
  - 密码 & auth.password 用 Fernet 加密；
  - 前端 Token 标 `httpOnly=false` 但加 `SameSite=Lax`（V0.1 简化；V1 切 Refresh cookie + CSRF）；
  - 后端解析 YAML 禁止 `!!python/object/apply:` 等不安全 tag，强制 `yaml.safe_load`；
- **可移植**：FastAPI 后端 Windows / Linux 都能跑；
- **构建 & 运行**：
  - 后端：`uvicorn app.main:app --reload --port 8000`；
  - 前端：`npm run dev` → `http://localhost:5173`。
- **数据迁移**：V0.1 直接使用 `Base.metadata.create_all()` 启动建表；V1 引入 Alembic。

---

## 10. 仓库结构

```
gimbal-platform/
├── backend/                          # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── deps.py                   # FastAPI Depends（DB, 当前用户, 权限）
│   │   ├── security.py               # JWT + Fernet
│   │   ├── models/                   # SQLAlchemy models
│   │   ├── schemas/                  # Pydantic schemas
│   │   ├── routers/                  # auth / users / cases / auths / executions
│   │   ├── services/
│   │   │   ├── case_loader.py        # yaml ↔ pydantic
│   │   │   ├── executor.py           # async 调度器 + Semaphore
│   │   │   ├── gimbal_runner.py      # subprocess shell out
│   │   │   └── crypto.py             # Fernet
│   │   └── core/config.py
│   ├── tests/
│   ├── data/                         # sqlite / cases / reports / tmp
│   ├── pyproject.toml
│   └── README.md
├── frontend/                         # Vue 3 + Vite
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── stores/                   # pinia
│   │   ├── api/                      # axios 封装
│   │   ├── views/
│   │   │   ├── Login.vue / Register.vue
│   │   │   ├── CasesMine.vue / CasesPublic.vue
│   │   │   ├── CaseConfig.vue        # 核心：4 tab card-stack
│   │   │   ├── Auths.vue
│   │   │   └── Execution.vue
│   │   ├── components/
│   │   │   ├── Configurator/         # 自研，沿用 Prism 视觉
│   │   │   ├── StepCard.vue
│   │   │   ├── Header.vue            # 顶部固定栏
│   │   │   └── ...
│   │   ├── styles/
│   │   │   ├── theme.css             # 沿用 Prism 变量
│   │   │   └── prism.css             # 组件视觉
│   ├── package.json
│   └── README.md
└── docs/
    └── PLATFORM_REQUIREMENTS.md      # 本文件
```

---

## 11. 待办 / 下一步

1. **需求确认**：请用户就 §7 中的 7.1–7.7 共 **24 项**逐一确认（回复 "7.x ✅"或 "请改为 ..." 即可），确认后冻结 V0.1 范围。
2. 数据库 / 持久化路径决定（data/ vs 数据库外挂）。
3. `gimbal.exe` 路径约定（默认 `PATH`，env `GIMBAL_BIN`）。
4. 样例用例准备（hello-login + 一个 rich 用例）。
5. 按 §10 仓库结构搭建框架；先后端骨架 → 前端骨架 → 用例配置页是核心 → 执行侧。
