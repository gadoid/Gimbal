# PRD · 用例编排（Case Composer）

> 平台新增功能模块 PRD — 让用户在被测系统的接口契约之上，编排出可执行的业务用例。

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 创建日期 | 2026-08-05 |
| 状态 | 草案 / 评审中 |
| 涉及模块 | `gimbal-plate`（结构定义） + 平台前端（编排画布） |
| 关联 schema | `schema/endpoint/*`、`schema/interface/*`、`schema/base/*` |
| 原型位置 | `pencil-welcome-desktop.pen` · 14 屏 |

> **术语映射(2026-09-02 注)**:本文撰写时 plate 侧 IO 字段模型为
> `fields: list[IOFieldBinding]` 三轴(fields/carry/assertable_fields);
> 现已归一化为 `declarations: list[DeclarationEntry]` 单一存储
> (binding/carry/view_only 三通道,assertable 为条目旗标)。
> 文中 `IOFieldBinding` / `fields[*]` 字样按语义对应
> `DeclarationEntry` / `request.declarations[*]`(binding 通道);
> `assertable_paths` 对应 view_only 通道 `assertable=true` 条目的 path 集。
> 现行契约见 plate `io_spec.py` 与
> [2026-09-01 归一化设计](superpowers/specs/2026-09-01-io-declarations-unification-design.md)。

---

## 1. 背景

平台目前只支持"用例的存储与执行"两条主线：

- **用例存储**：用户在 `gimbal` 端写 Scenario JSON（手写 / 通过 `EndpointCaseExporter` 由 endpoint 契约导出）
- **用例执行**：`gimbal` 引擎读取 Scenario JSON，按 Step 顺序调用接口

**痛点**：

1. **编排门槛高**：用户必须手写 Scenario JSON 或依赖 agent 生成，缺乏"看见就能改"的可视化界面。
2. **跨系统用例编写难**：业务用例（如 e2e）经常跨多个被测系统（fin 下单 → logi 物流 → wms 出库），但平台对"多系统"的支持是隐式的（依靠 `config.services` key 前缀）。
3. **字段不直观**：每个接口有几十个 IOFieldBinding，用户需要逐个查文档理解字段含义、是否必填、是否可断言。
4. **失败模式不可见**：被测系统在 schema 中声明了 `failed_criteria`、`preconditions`、`business_notes`，但平台 UI 没呈现。

## 2. 目标

提供一个**结构化、可视化、支持多系统混合**的用例编排模块，让测试工程师：

- 在不写 JSON 的前提下，从被测系统的接口契约组装出业务用例
- 清楚地看到每个字段的含义、是否必填、是否可断言、是否绑定到上游变量
- 支持跨系统编排（fin + logi + wms 任意组合）
- 即时看到失败参考 / 前置条件，避免接口契约的"暗契约"

**非目标**：

- 不替代 agent 生成（编排画布主要服务人类用户的手工编排）
- 不替代执行引擎（仍然依赖 `gimbal` 引擎按 Scenario JSON 执行）
- 不做模板解析 / 数据查询层（值来源采用"静态注入 + 动态注入"分层，模板解析层独立规划）

## 3. 用户角色

| 角色 | 场景 |
|---|---|
| **测试工程师**（主要） | 从被测系统接口组装业务用例、调试、复用到不同环境 |
| **业务分析师** | 用例评审，确认编排逻辑符合业务流程 |
| **架构师 / 管理员** | 注册被测系统、维护公共用例模板 |

## 4. 信息架构

### 4.1 菜单

在现有 5 个菜单（我的工作台 / 公共用例库 / 执行历史 / 认证管理 / 用户管理）后**新增第 6 个菜单"用例编排"**。当前 5 个菜单复用，新菜单独立。

### 4.2 屏功能定位 — 两层树

用例编排实际是**两层树**：
- **Scenario 层**（顶层用例编辑）：Meta / Resource / Config / Steps 4 个并列维度，由顶部 stepper 串起
- **Step 子树**（Step 内部）：在 Steps 编辑区里嵌套一个"选接口 → 查详情 → 加入"的子流程

| # | 屏幕 | 层级 | 入口 |
|---|---|---|---|
| 1 | **CaseComposerHome** | 列表（外层） | "用例编排" 菜单 |
| 4 | **CaseComposerCanvas** | Scenario 层 · 步骤编辑 | Home → "编辑" |
| 6 | **CaseComposerMeta** | Scenario 层 · 基本信息 | Canvas 顶部 stepper ① |
| 7 | **CaseComposerResource** | Scenario 层 · 资源 | Canvas 顶部 stepper ② |
| 8 | **CaseComposerConfig** | Scenario 层 · 配置 | Canvas 顶部 stepper ③ |
| — | **CaseComposerCanvasRunner** | Scenario ④ 子态 | Canvas → "下一步：运行"（内嵌替换） |
| — | **CaseComposerCanvasAddStep** | Scenario ④ 子态 | Canvas → "添加接口"（内嵌 Catalog Panel） |
| — | **CaseComposerCanvasAddStepDetail** | Scenario ④ 子态 | AddStep → 选接口（内嵌 Detail Panel） |

> 关键决定：2 / 3（Catalog / Detail）独立全屏已删除，**只保留内嵌形态**。Runner 不再是独立屏，**嵌入 Canvas 内成为子态**。代码上是 Canvas 内部的 `<CatalogPanel>`、`<DetailPanel>`、`<RunnerView>` 子组件。

### 4.3 业务流转树

```
                ┌─ [1 Home] 用例编排列表
                │     ↓ "+ 新建编排" / "编辑"
                │
                ▼
        ┌─ [Scenario Editor] 一个用例的完整编辑
        │   ┌─ ① [6 Meta] 基本信息 ──────────↓
        │   ├─ ② [7 Resource] 资源 ──────────↓
        │   ├─ ③ [8 Config] 配置 ────────────↓
        │   └─ ④ [4 Canvas] 步骤编辑 ─────────┘  ← 由 stepper 串联（4 屏共享同一 HeadStepper）
        │        │
        │        │ "▶ 运行"
        │        ▼
        │   [CanvasRunner]（同 Canvas 路由，④ 节点变 running 状态）
        │        │
        │        │ "← 退出运行" / 步骤完成
        │        ▼
        │   回到 [4 Canvas]
        │
        │        │ "+ 添加接口" (内嵌)
        │        ▼
        │   ┌─ [Step 子流程] 嵌套在 Canvas 内
        │   │   ├─ [Catalog Panel] (覆盖右两栏)
        │   │   │     ↓ 选某接口卡片
        │   │   └─ [Detail Panel] (覆盖 Catalog)
        │   │         ↓ "+ 加入到编排画布"
        │   │     (关闭子流程，回到 Canvas 主区，新 step 出现在步骤流)
        │   └─ 步骤流追加新 step
        │
        └─ "保存" → 回到 [1 Home] 列表
```

### 4.4 Scenario Editor 4 屏结构（统一）

**4 屏共享同一种 Head 布局**（垂直堆叠 3 段）：

```
┌───────────────────────────────────────────────┐
│ [TopNav]  全局菜单（用例编排高亮）             │  ← 与老 5 个屏一致
├───────────────────────────────────────────────┤
│ [HeadStepper]                                  │
│  ┌─ Crumb ────────────────────────────────┐  │  面包屑
│  │ 用例工作台 › 用例名 › 当前步骤          │  │
│  └─────────────────────────────────────────┘  │
│  ┌─ Stepper ──────────────────────────────┐  │  4 步进度条（位置一致）
│  │ ①基本信息 ─ ②资源 ─ ③配置 ─ ④步骤编辑 │  │
│  └─────────────────────────────────────────┘  │
│  ┌─ NavBar ───────────────────────────────┐  │  导航按钮
│  │ 说明 ...           [上一步/下一步/保存] │  │
│  └─────────────────────────────────────────┘  │
├───────────────────────────────────────────────┤
│ [Body] 主内容                                  │
└───────────────────────────────────────────────┘
```

**HeadStepper 在每屏的同一位置（TopNav 之后、Body 之前）**。

### 4.5 4 屏导航按钮规范

| 屏幕 | 左侧按钮 | 右侧按钮 |
|---|---|---|
| **Meta** (①) | "上一步"（灰禁用） | "下一步：资源 →" |
| **Resource** (②) | "上一步：基本信息 →" | "下一步：配置 →" |
| **Config** (③) | "上一步：资源 →" | "下一步：步骤编辑 →" |
| **Canvas** (④) | "上一步：配置 →" | "保存草稿" + "下一步：运行 →" |

**子态返回按钮规范**：

| 子态屏 | 返回按钮 |
|---|---|
| CanvasRunner | "← 退出运行" |
| CanvasAddStep | "← 返回步骤编辑" |
| CanvasAddStepDetail | "← 返回选接口" |

> 区分**正交 stepper 跳转**（"下一步：[name] →"）和**退出子态**（"← [动作]"）。两类按钮位置一致（NavBar 右侧）。

### 4.6 完整业务流转（正交线合成）

```
[1 Home] 编排列表
   ↓ "+ 新建编排" / "编辑"          ← 外层入口
[6 Meta] (①) 填写用例名 / 归属系统
   ↓ "下一步：资源 →"
[7 Resource] (②) 添加 Mock / File
   ↓ "下一步：配置 →"
[8 Config] (③) setup / teardown / timePolicy / retry
   ↓ "下一步：步骤编辑 →"
[4 Canvas] (④) 步骤编辑
   │
   ├─ 直接拖拽已有 step
   ├─ 点已有 step → 字段配置（@ 浮层选变量）
   └─ "+ 添加接口" → 内嵌 [Catalog Panel]
                       ↓ 选接口
                    内嵌 [Detail Panel]
                       ↓ "+ 加入"
                    回到 Canvas，新 step 出现在步骤流
   ↓ "下一步：运行 →" / "▶ 运行"
[CanvasRunner] 实时进度 + 请求/响应（④ 节点变 running）
   ↓ "← 退出运行"
回到 [4 Canvas]
```

### 4.7 为什么这样设计

- **顶层 4 步 stepper 串联**：元信息决定后面所有事，先 Meta 后 Steps 是最自然的认知顺序
- **Steps 子流程嵌套在 Canvas 内**：选接口是为了"组成"一个 step，本质上是 step 编辑的一部分，不应跳到独立屏打断思路
- **左侧步骤流始终保留**：用户随时能看到"在哪个 step 编辑 / 这个用例已经编排了哪些 step"
- **Runner 内嵌**：进度条 = 4 步 stepper 中的 ④ 节点状态，无需独立屏
- **正交但嵌套**：Scenario 配置（4 维）和 Step 编辑（接口查询 + 字段配置）是不同抽象层级，UI 上要分层但不能割裂

## 5. 关键设计决策

### 5.1 `Meta.system` 改为 `list[str]`

**背景**：当前 schema `Meta.system: str` 只能标注单个被测系统，无法表达跨系统用例。

**决定**：

```python
class Meta(BaseModel):
  system: list[str] = []   # V3
```

- `["common"]` — 纯公共模板（无具体系统接口）
- `["fin"]` — 单系统用例
- `["fin", "logi"]` — 跨系统用例
- `["fin", "common"]` — 含公共默认的多系统用例

**向后兼容**：`system: str` 旧数据迁移为单元素 list；空串 → `[]`。

**平台校验**：保存用例前对比 `meta.system` 与 `steps[*].api.service` 推出来的系统集合，不一致给 warning（提示"声明的系统与实际调用的系统不匹配"）。

### 5.2 `common` 与其他被测系统平级

`common` 是与其他系统平级的特殊标识（不是某个系统内部的 common）。在 UI 上一致用 chip 列表呈现：

- EndpointCatalog 系统 tab 顺序：common 在第一位
- Home 列 chip 列表 / Canvas 顶部 chip 列表：common 用中性灰色（`#64748B`）
- 服务命名空间 `common.` 前缀的 key（如 `common.order_id_prefix`、`common.monitor`）归到 common 系统

### 5.3 多系统命名空间 `<system>.key`

**背景**：`config.services`、`config.users`、`config.vars` 已经是 dict，可天然容纳多系统。

**决定**：保持单层 dict，靠**命名空间前缀**自动归属系统：

```yaml
config:
  services:
    fin.tidb-test: https://fin-tidb.21eflag.com/
    logi.mysql-svc: https://logi-mysql.21eflag.com/
    common.monitor: https://monitor.example.com/
  users:
    fin.codfish: AuthSession(...)
    logi.bot: AuthSession(...)
  vars:
    common.order_id_prefix: "ORD-"
    fin.bl_no: {kind: random_decorated, charset: alnum, length: 6}
    logi.tracking_url: "https://logi.example.com/api"
```

**不采用嵌套对象或 list 形式**（理由：与现有 20+ Scenario JSON 兼容、Step 引用语义不变、平台渲染自然反推）。

### 5.4 字段三类型（IOFieldBinding + Schema-only）

| 类型 | 识别 | #3 呈现 | #4 编辑 | #5 请求体 |
|---|---|---|---|---|
| **Type A** IOFieldBinding 完整 | `fields[*].ui_kind` 有值 | 按 ui_kind 渲染 | 按 ui_kind 控件，主要编辑区 | ✅ 完整 |
| **Type B** IOFieldBinding 缺 ui_kind | `fields[*].ui_kind == unknown` | 默认按 text 渲染 | 按 text 控件 | ✅ 完整 |
| **Type C** 仅 JSON Schema | `schema_.properties` 有但 `fields[]` 未绑 | 折叠区"仅 schema 字段 (N)" | 折叠区"附带字段 (N)" | ✅ 全量携带 |

**业务处理过程要全程携带所有字段**（不丢字段），仅在 UI 上区分主/次编辑区。

### 5.5 字段运行时携带策略

**默认全量，但可手动开关**；值来源**待规划**（template + 数据查询模式）。

平台目前只负责**结构管理**：
- 折叠区字段在加入编排时自动携带（默认开启）
- #4 字段行有 toggle 关闭开关，关闭则不发出
- 值来源待规划：当前板仅做"字段存在 / 已声明 / 运行时携带"的语义，不实现具体值解析

### 5.6 静态注入 vs 动态注入

| 类型 | 数据来源 | 注入机制 | schema 表现 |
|---|---|---|---|
| **静态注入** | `config.vars` + `config.users[].token` + IOFieldBinding.example/sample | **预处理** 阶段模板解析 | 字段值文本直接写 `${var.x}` / `${auth.x.token}` |
| **动态注入** | 上游 step 响应（Extract） | **运行时**：上游 Extract → 当前 step Assign | `strategy: [Extract(...), Assign(...)]` 配对 |

**UI 区分**：

| 字段值 | 类型 | 视觉标识 | Strategy 策略 |
|---|---|---|---|
| 字面量 | — | 灰底 input | 无 |
| `${var.x}` | **静态** | 紫色边框 · "🔗 static · ${var.x}" | ❌ 无 Assign |
| `${auth.x.token}` | **静态** | 紫色边框 · "🔗 static · ${auth.x.token}" | ❌ 无 Assign |
| `${var.order_id}`（上游 Extract） | **动态** | 紫色边框 · "🔗 dynamic · Assign · ${var.order_id}" | ✅ Assign 策略 |
| `step1.$.data.x` 未声明 | **动态 + Auto-Extract** | 黄色边框 · "⚠ Assign + Auto-Extract" | ✅ 上游 step 加 Extract + 当前 step 加 Assign |

### 5.7 @ 浮层 + 自动 Extract

**触发**：字段输入框聚焦按 `@`

**分组**：当前 step IO / 上游 Extract / 用例变量 / 认证会话 / 上游响应（未声明）

**自动 Extract**：选未声明的上游响应 path → 平台自动在来源 step 加 Extract + 当前 step 加 Assign，一次操作完成两步

### 5.8 失败参考 / 前置条件 / 业务备注

EndpointDetail Hero（接口元信息卡片）展示：

| 字段 | schema 字段 | 形态 |
|---|---|---|
| **成功标准** | `metadata.success_criteria` | 绿色卡（单行） |
| **失败参考** | `metadata.failed_criteria: list[str]` | 红色卡，多行（状态码 + 描述 + 失败字段路径，每行带 ✓ assertable / ○ 未声明 标记） |
| **前置条件** | `metadata.preconditions: list[str]` | 蓝色卡（单行汇总） |
| **业务备注** | `metadata.business_notes: str` | 紫色卡（折叠行，前 30 字 + ▾ 展开） |

**联动**：
- `failed_criteria` × `assertable_paths`：assertable 的失败模式平台可校验，未声明的需被测系统侧修复
- `#4 编排页`：failed_criteria 列表可一键加入 Assertion（response.status == 422 → fail）

### 5.9 字段折叠携带（schema-only 字段）

- `request_body_samples[0]` 等"附带字段"在加入编排时默认携带
- #4 字段行有 toggle 关闭开关，关闭则不发出
- 运行时请求体是全量字段（业务处理过程要携带所有字段）

## 6. 5 屏详细功能

### 6.1 Screen 1 · CaseComposer Home（编排任务列表）

**功能**：列出所有编排任务，按归属被测系统筛选。

**列**：编排名称（含 module/描述/星标）、模块 chip、优先级 chip、作者、**被测系统 chip 列表（多个）**、步骤数、变量数、最后编辑、操作（编辑 / 运行 / 复制 / 删除）

**Tabs**：我的编排 (N) / 公共编排 (N) / 收藏 (N)

**系统 chip 列表**：每行的"被测系统"列展示多个系统 chip（fin · logi · common），common 用中性灰

### 6.2 Screen 6 · CaseComposer Meta（Scenario · ① 基本信息）

**字段**：
- scenarioId（自动生成 · 锁定 · 🔒）
- name（用例名 · 必填）
- description（描述 · 多行）
- module（模块 · 必填 · 下拉）
- priority（优先级 · 必填 · 下拉）
- **归属被测系统**（meta.system · 必填 · list[str] · chip 列表）
- author（作者 · 下拉）
- owner（维护人 / 执行人 · 下拉）
- tags
- version
- requirementRef（需求关联）
- expire（过期标志）

### 6.3 Screen 7 · CaseComposer Resource（Scenario · ② 资源）

**字段**：
- **Mock 服务**（resource.mock）：镜像 image + 服务配置 config + 端口映射 portMapping
- **文件引用**（resource.file）：路径 path

每个 Mock / File 项可独立编辑 / 删除。

### 6.4 Screen 8 · CaseComposer Config（Scenario · ③ 配置）

**字段**：
- **用例前置 · setup**（config.setup：list，phase=before_request）
- **用例后置 · teardown**（config.teardown：list，phase=teardown）
- **时间策略 · timePolicy**：record（记录耗时）/ timeout（超时检查）
- **重试策略 · retry**：启用 + 最大次数 + 重试间隔 + 触发条件

注：services / users / vars 已经在 #4 Canvas 右栏常驻面板展示。

### 6.5 Screen 4 · CaseComposer Canvas（Scenario · ④ 步骤编辑 — 核心）

**三栏布局**：

```
┌────────────────────────────────────────────────────┐
│  左侧 StepList  │  中间 FieldEditor  │  右 ConfigPanel  │
│  (340 宽)      │  (620 宽)          │  (430 宽)         │
│                │                    │                  │
│  步骤卡        │  #1 orderAdd       │  用例配置         │
│  跨系统连接    │  POST / path       │  vars (按系统)    │
│  + 添加按钮    │  字段列表          │  users (按系统)   │
│                │  strategy          │  services (按系统)│
└────────────────────────────────────────────────────┘
```

**左侧 StepList**：步骤流（按系统着色，跨系统画"→ 切换到 logi"虚线连接符，底部"+ 从接口目录添加步骤"）

**中间 FieldEditor**：
- 步骤 header（#N + 名称 + method + 系统徽章 + v + 同步状态）
- path code block
- tabs（请求体 / 响应断言 / 前置条件）
- 描述输入框
- 字段列表（紧凑单行）：必填红点 + 字段名 + ui_kind chip + source_kind chip + 控件
  - 字面量：灰底 input
  - 静态变量：紫色边框 · "🔗 static · ${var.x}"
  - 静态 auth：紫色边框 · "🔗 static · ${auth.x.token}"
  - 动态：紫色边框 · "🔗 dynamic · Assign · ${var.x}"
  - 动态 + Auto-Extract：黄色边框 · "⚠ Assign + Auto-Extract"
- "附带字段 · N (从 schema 自动携带)" 入口条（折叠，提示从 schema 自动携带 / 全部开启 / ▾）
- Strategy 卡片：Assertion / Assign / Assign+Auto-Extract 行

**右侧 ConfigPanel**：用例配置 + vars（按 `<system>.key` 分组）+ users（按系统）+ services（按系统）

**@ 浮层**（字段输入框聚焦时触发）：
- 5 分组渲染
- 选未声明路径 → 自动在来源 step 加 Extract + 当前 step 加 Assign

### 6.6 Canvas 子态 · CaseComposer Canvas Runner（④ 步骤编辑 · 运行态）

**触发**：#4 Canvas 点"▶ 运行"或"下一步：运行 →"

**变化**：
- TopNav + HeadStepper（同一布局）
- HeadStepper 顶部加 StatusRow（RUNNING · 步骤 N/M + 耗时 + run ID + 中止/暂停/重跑/导出）
- 4 步 stepper 中 ④ 节点变 **running 状态**（橙底色 + ● 标记 + 描边加粗）
- 左侧 StepList 中当前 step 加橙色高亮（#2 ● running 高亮）
- 主区（Body）：
  - 当前步骤详情（步骤号 + 状态 + 名称 + method/path + 调用的服务 + 策略列表）
  - 已完成的步骤结果卡（response JSON + 断言结果）
  - 未开始的步骤 pending 卡
  - 变量轨迹（按产生顺序列出，含来源系统 chip）

**NavBar**：左侧 "← 退出运行"（无右侧按钮）

### 6.7 Canvas 子态 · CaseComposer Canvas AddStep（④ 步骤编辑 · 选接口）

**触发**：#4 Canvas 左侧 StepList 底部"+ 从接口目录添加步骤"

**变化**：
- TopNav + HeadStepper（同一布局，breadcrumb 加 "添加步骤 · 选接口"）
- 左侧 StepList 保留（底部 "+ 选接口中..." 高亮）
- 主区右栏（Catalog Panel 替换 FieldEditor + ConfigPanel）：
  - Catalog Header（📂 从接口目录添加步骤 + ✕ 关闭）
  - 左侧 service 树（复用 Catalog 左侧）
  - 右侧：系统 tab + 搜索 + endpoint 卡片网格（每张"+ 查看详情 →"）

**NavBar**：左侧 "← 返回步骤编辑"

### 6.8 Canvas 子态 · CaseComposer Canvas AddStep Detail（④ 步骤编辑 · 详情）

**触发**：Catalog Panel 选某接口 → 切到 Detail Panel

**变化**：
- TopNav + HeadStepper（同一布局，breadcrumb 加 "orderAdd 详情"）
- 主区右栏（Detail Panel 替换 Catalog Panel）：
  - Detail Header（📄 接口详情 · orderAdd + ✕ 关闭）
  - Hero（method POST / 系统 chip list / 接口名 / ID chip / path code block / tags / 成功标准绿 / 失败参考红）
  - **加入后会发生什么** Summary（步骤列表 / 字段 / strategy / 附带字段 4 行说明）
  - "+ 加入到编排画布 → 作为 #N step" 按钮（主操作）

**NavBar**：左侧 "← 返回选接口"

## 7. 状态/字段显示规范

| 状态 | 颜色 | 用途 |
|---|---|---|
| PASS / 成功 | 绿 `#15803D` / `#DCFCE7` | 断言通过、启用、已完成 |
| FAIL / 失败 | 红 `#B91C1C` / `#FCE7E7` | 失败、关闭、未声明 |
| RUNNING | 橙 `#B45309` / `#FEF3C7` | 进行中、运行中 |
| PENDING | 灰 `#64748B` / `#F1F5F9` | 等待、待执行 |
| STATIC | 紫 `#7C3AED` / `#FAF5FF` | 静态变量绑定（不生成 Assign） |
| DYNAMIC | 紫 `#7C3AED` / `#EDE9FE` | 动态变量绑定（生成 Assign） |
| AUTO | 黄 `#B91C1C` / `#FEE2E2` | 自动 Extract 提示 |

## 8. 设计 Token

复用现有平台 token：
- 品牌紫 `#4338CA` / 顶栏深 `#1F2933`
- success `#15803D` / fail `#B91C1C` / priority `#B45309`
- **系统色**：fin `#4338CA` / logi `#0891B2` / wms `#7C3AED` / common `#64748B`
- 字体 Inter（Google Fonts）

## 9. 与现有模块的关系

| 现有 | 与用例编排的关系 |
|---|---|
| 我的工作台 | 旧版用例库（手写 / 导入）。用例编排是新模块，两套并行，迁移策略待定 |
| 公共用例库 | 用例编排后产生的"公共编排"会同步到公共用例库 |
| 执行历史 | 用例编排的运行结果在执行历史里查看 |
| 认证管理 | 用例编排右侧 config.users 配置从此处拉取 |
| 用户管理 | 用例编排归属作者从此处拉取 |

## 10. 验收标准

### 10.1 菜单与结构
- [ ] 用例编排菜单在第 6 位，5 个旧菜单保留
- [ ] CaseComposer Home 列出已编排用例，每行展示归属被测系统 chip 列表（含 common）
- [ ] 4 步 stepper 在 Meta / Resource / Config / Canvas 4 屏**位置一致**（TopNav 之后、Body 之前）
- [ ] Canvas 屏的"运行"是子态切换，不是独立屏跳转

### 10.2 Scenario 4 屏字段
- [ ] EndpointCatalog 系统 tab common 在第一位
- [ ] EndpointDetail 展示成功标准 + 失败参考（每行带 assertable 标记）+ 前置条件 + 业务备注
- [ ] EndpointDetail 请求字段按 ui_kind 渲染；缺省按 text；未携带字段隐藏
- [ ] EndpointDetail "仅 schema 字段" 折叠区可见，"加入编排时携带"提示
- [ ] CaseComposerConfig 展示 setup / teardown / timePolicy / retry
- [ ] CaseComposerResource 展示 Mock / File 列表

### 10.3 Canvas 字段配置
- [ ] CaseComposerCanvas 三栏布局，步骤流按系统着色，跨系统画"→ 切换"虚线
- [ ] 字段编辑器：字面量 / 静态 / 动态 / Auto-Extract 四种视觉区分
- [ ] @ 浮层：字段框聚焦按 @ 唤起，5 分组渲染
- [ ] Auto-Extract：选未声明路径自动在来源 step 加 Extract
- [ ] StrategyCard 显示 Assertion / Assign / Auto-Extract 三类
- [ ] 配置面板 vars/users/services 按 `<system>.key` 命名空间分组

### 10.4 子态
- [ ] Runner 进度条 = 4 步 stepper 中 ④ 节点变 running 状态
- [ ] Runner 变量轨迹展示跨系统数据流（fin 提取 → logi 注入）
- [ ] Runner 请求/响应面板含附带字段折叠条
- [ ] AddStep 内嵌 Catalog Panel 替换右两栏
- [ ] AddStepDetail 内嵌 Detail Panel 替换 Catalog Panel

### 10.5 导航按钮
- [ ] 4 屏正交跳转按钮文案："上一步：[name] →" / "下一步：[name] →"
- [ ] 子态返回按钮文案："← 退出运行" / "← 返回步骤编辑" / "← 返回选接口"
- [ ] 所有按钮位置一致（NavBar 右侧），不与左侧面包屑重复

## 11. 待规划 / 开放问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | **值解析层**：字段值在运行时如何从 sample / template / 数据查询获取 | 独立模块，后续规划 |
| 2 | **业务处理过程的全量请求实现**：折叠字段在执行时如何真实发出（请求体合并 / 序列化） | 后端实现 |
| 3 | **Schema-only 字段运行时序列化**：当 example/sample 缺失时填什么 | 需业务约定（空串 / null / 报错） |
| 4 | **跨 step 同名字段冲突**：上游 step1 和 step2 都有 `$.data.id`，@ 浮层应展示 step 标识 | 后续 @ 浮层实现 |
| 5 | **类型校验**：@ 浮层选了 number 字段去填 string 控件，平台警告 | 后续 |
| 6 | **批量引用**：多选字段一次性填入 | 高级用户功能，后续 |
| 7 | **@ 浮层里的"最近用过"快捷区**：把当前 step 用过的变量钉在最上面 | 待你确认是否需要 |
| 8 | **Strategy 流向图**：把 StrategyCard 升级成"流向图"形态可视化 extract → assign 链路 | 后续 |
| 9 | **`Meta.system` 自动反推**：保存时与 `steps[*].api.service` 推导集合不一致的 warning 文案 | 平台前端 |
| 10 | **用例编排的"我的工作台"迁移路径**：是否废弃旧手写用例库 | 需业务确认 |

## 12. 关联文档

- schema 定义：`src/gimbal-plate/gimbal_plate/schema/`
  - `endpoint/` — `EndpointSpec` / `ApiSpec` / `RequestSpec` / `ResponseSpec` / `EndpointMetadata`
  - `interface/` — `Step` / `Request` / `Strategy`(Extract/Assign/Assertion) / `Scenario`
  - `base/` — `AuthSession` / `TimePolicy` / `RetryPolicy` / `RefBase`
- 平台需求：`docs/PLATFORM_REQUIREMENTS.md`
- 平台架构：`docs/architecture.md`

## 13. 原型位置

`pencil-welcome-desktop.pen` 14 屏布局：

```
Row 1 (y=0) — 老系统 + Home
  [登录] [CasesMine] [CasesPublic] [Executions] [Auths] [AdminUsers] [CaseComposerHome]

Row 2 (y=980) — Scenario Editor 4 步
  [CaseComposerMeta] [CaseComposerResource] [CaseComposerConfig] [CaseComposerCanvas]

Row 3 (y=1960) — Canvas 子态
  [CaseComposerCanvasAddStep] [CaseComposerCanvasAddStepDetail] [CaseComposerCanvasRunner]
```

## 14. 术语表

| 术语 | 含义 |
|---|---|
| **被测系统** | 业务方正在测试的、对外提供 HTTP 接口的系统（如 fin、logi、wms）。平台向其拉取接口契约 |
| **接口契约 (EndpointSpec)** | 一个接口的完整结构定义：API 坐标 + 请求体形态 + 响应体形态 + 业务元信息 |
| **IOFieldBinding** | 单个字段的元信息（name/path/ui_kind/source_kind/enum/default/example/description）；2026-09-02 起 plate 契约为 `DeclarationEntry`（同字段轴 + channel/type/required/assertable），前端本地投影仍沿用此名 |
| **ui_kind** | 字段 UI 渲染类型（text/number/boolean/select/textarea/json/file/binary/unknown） |
| **source_kind** | 字段值来源类型（independent/lookup/generated） |
| **assertable_paths** | 响应里可以被 Assertion 校验的 JSONPath 列表 |
| **Step** | 用例中的一个步骤（一个接口调用 + 一组 strategy） |
| **Extract 策略** | 从 step 响应里提取字段写入 scratch |
| **Assign 策略** | 把 scratch 里的字段注入到目标字段 |
| **Assertion 策略** | 对 step 响应做断言 |
| **静态注入** | 字段值在预处理阶段通过模板解析（`${var.x}` / `${auth.x.token}`） |
| **动态注入** | 字段值在运行时通过 Extract + Assign 链注入 |
| **@ 浮层** | 字段输入框聚焦按 `@` 唤起的变量选择器浮层 |
| **Auto-Extract** | 引用未声明的响应路径时自动在来源 step 加 Extract 策略 |
| **附带字段** | JSON Schema 里有但未绑 IOFieldBinding（现 binding 通道声明条目）的字段，运行时全量携带，默认开启可手动关闭 |
| **HeadStepper** | 4 屏共享的顶部"面包屑 + 4 步进度条 + 上下步按钮"组件 |
| **Scenario Editor** | 一个用例的完整编辑视图（4 步 stepper + Body），4 屏共享同一布局结构 |