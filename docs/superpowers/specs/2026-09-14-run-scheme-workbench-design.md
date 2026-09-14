# 方案工作台(RunScheme Workbench)设计

- 日期:2026-09-14
- 状态:已评审通过(待实施)
- 分支:feat/dataset-driven-refactor-phase2

## 1. 背景与问题

「方案」(RunScheme)= 一次执行的全部准备(数据、状态、身份、参数)。当前这些能力零散在四处:

| 能力 | 现有入口 | 问题 |
|---|---|---|
| 方案本身 | RunDialog 方案栏(三态:`__adhoc__` 临时 / `__last__` 上次 / 已存) | **只能运行前保存**,无独立管理入口 |
| 数据集选择 | RunDialog tile 多选 + 数据集页 RunPreset 预填 | 注入位置分散 |
| 断言注入 | RunDialog 异常组多选 + 断言编辑器 | 同上 |
| 用户与服务 | RunDialog 折叠区 | 收纳在折叠里 |
| 插件/日志订阅 | RunDialog 只读占位 | no-op 预埋 |

场景库行操作收在 `el-dropdown`「⋯」折叠菜单,方案配置无直接入口。TopNav 已平铺多项,再加一级导航会更乱。

## 2. 目标与非目标

**目标**
1. 方案从运行时拿出来:场景库/详情页直接按钮 → 方案工作台(独立路由页,左右分栏)
2. 方案作为其管理的各类注入方式的统一入口(数据集/断言注入/用户与服务/运行参数/插件/日志订阅)
3. 运行侧只有两条执行路径:选自建方案直接执行 / 默认方案(基线)自由配置后执行
4. 默认方案:系统方案,数据集锁空(基线)、断言注入锁空,可配绑定与运行参数
5. 顶层导航不加新项

**非目标(本期不做)**
- 跨场景方案模板 / 全局方案库(真需求出现时再评估)
- 「以此行建方案」快捷方式(数据集页运行入口统一两路径后,如路径过长再加)
- 核心用例结构改造:`definition` / `composer_data_sets` / `assertion_registry` / `orchestration.steps` / `resourceMeta` / plate convert / 注入物化 / dispatcher fan-out **全部零改动**
- 插件/日志订阅的执行侧消费(仍 no-op,仅 UI 升格可编辑)

## 3. 概念模型

```
方案(RunScheme)= 一次执行的全部准备
  ├── 数据:dataSetSelection(数据集 + 行级选择)
  ├── 状态:injectionEntryIds(断言注入条目)
  ├── 身份:serviceBindings(凭证别名 + URL 覆盖)
  ├── 参数:stepTo / nRuns / parallel
  └── 预埋:plugins / logSub(待引擎支持)

每个场景的方案列表:
  ├── 默认方案(isDefault=true,系统保证恰一个)— 数据集锁空、注入锁空,可配绑定与参数
  └── 自建方案 — 全字段自由,选中即执行

执行路径只有两条:
  ① 选自建方案 → 只读概要 → 直接执行(不允许运行时篡改;失效方案禁跑)
  ② 默认方案 → 露出绑定 + 运行参数自由配置 → 执行,可「另存为方案」
```

**退役概念**:`__adhoc__`(临时手填,被默认方案自由配置态替代)、`__last__`(上次运行回填,被持久化方案替代)、`RunPreset`(数据集页行级预填,见 §7)。

## 4. 数据模型

### 4.1 新表 `composer_run_schemes`

方案从 `composer_scenarios.payload.orchestration.runSchemes[]` sidecar 迁出为独立表(**PG 迁移友好**:关系的做关系,文档的做文档)。

```sql
composer_run_schemes
  id           INTEGER PK 自增
  scheme_id    TEXT UNIQUE        -- rs-001 形式(与 ds-NNN 同习惯,自动分配)
  scenario_id  TEXT FK → composer_scenarios.scenario_id ON DELETE CASCADE
  name         TEXT               -- 唯一索引 (scenario_id, name)
  is_default   BOOLEAN            -- 部分唯一索引:每场景恰一个 default
                                  --   (SQLite 与 PG 均支持 partial unique index)
  payload      JSON               -- 方案体,见 4.2
  created_at / updated_at
```

### 4.2 方案体(payload JSON)

```python
{
    "dataSetSelection": [{"datasetId": "ds-001", "rowIndexes": [0, 2]}],
    "injectionEntryIds": ["..."],
    "serviceBindings": {"<service>": {"authAlias": "...", "url": "..."}},
    "stepTo": None,
    "nRuns": 1,
    "parallel": 1,
    "plugins": None,   # 预埋,引擎就绪前不收紧 schema
    "logSub": None,    # 预埋,同上
}
```

方案体是配置文档(整体读写、无字段级跨行查询),留 JSON;需要查询/约束/级联的维度(scenario 归属、名字唯一、默认标记)提升为列加索引。SQLite(TEXT JSON)与 PG(JSONB)两边原生支持。

### 4.3 迁移(一次性、幂等、启动时自动)

`init_db` 建表后:新表为空且存量 payload 含 `orchestration.runSchemes[]` → 搬入新表(自动分配 scheme_id;无默认项则补一个),搬完清空 payload 里的键。`Orchestration` schema 移除 `run_schemes` 字段,`scenario_store` 的键所有权透传逻辑(`scenario_store.py:138-143`)随之退役。

## 5. API 设计

| 端点 | 语义 |
|---|---|
| `GET /scenarios/{id}/run-schemes` | 列表(保证返回默认项,缺失自动物化);含每方案概要(数据集数/注入条数)供徽标 |
| `POST /scenarios/{id}/run-schemes` | 创建(重名 409 `run_scheme_name_conflict` 沿用;不允许显式建 default) |
| `PUT /scenarios/{id}/run-schemes/{scheme_id}` | 单方案更新(default 项:强制清空 `dataSetSelection`/`injectionEntryIds`、名字锁定) |
| `DELETE /scenarios/{id}/run-schemes/{scheme_id}` | 删除(default 项 405) |
| `POST /runs` | **零改动**;前端展平传 RunRequest(现有行为);`config_json` 溯源增加 `schemeId` + `schemeName`(快照语义,改名不断链) |
| 旧 `PUT /scenarios/{id}/run-schemes`(整表替换) | 退役(过渡期双读,见 §10 阶段①) |

**执行链路零改动**(dispatch / plate / run_injection / run_materialize 只消费展平字段)—— 本设计的核心保护面。

权限:沿用场景属主语义(owner/admin),与数据集一致。

## 6. 方案工作台(前端,新路由)

路由:`/scenarios/:scenarioId/schemes`(深链 `/schemes/:schemeId` 定位右栏选中态)。

**左栏(方案列表)**
- 默认方案置顶(系统徽标,不可删/不可改名)
- 自建方案:名字 + 概要徽标(数据集数 / 注入条数 / 失效标记)
- 「+ 新建方案」;项上操作:重命名 / 复制派生 / 删除(默认方案无重命名/删除)

**右栏(选中方案编辑,显式保存 + 脏态提示,与 DataSetEditor 一致)**

| 分区 | 内容 | 默认方案行为 |
|---|---|---|
| 头部 | 方案名 + 保存状态 + 「▶ 运行此方案」(跳运行弹窗并预选) | 名字锁定 |
| ① 数据区 | 数据集多选(含行级勾选);「新建数据集」→ 跳 DataSetEditor(现有路由,创建后回来自动勾选);失效数据集醒目标注 + 一键移除 | 分区隐藏(锁基线) |
| ② 断言注入区 | 条目多选(悬空/旧版禁选,复用 `useInjectableSurface` 判定面);条目弹层快建(步骤 + jsonpath);「管理断言」跳断言编辑器 | 分区隐藏 |
| ③ 用户与服务 | 服务行(声明∪引用)= 凭证别名下拉 + URL 覆盖;**平铺不再折叠**;凭证创建跳「认证管理」页 | 可配 |
| ④ 运行参数 | stepTo / nRuns / parallel,实时总量预览(对齐后端 MAX_TOTAL_RUNS=200 的 409 规则) | 可配 |
| ⑤ 预埋区 | 插件列表 / 日志订阅:结构化占位表单,标注「待引擎支持」,存入 payload、执行不消费 | 可配 |

## 7. 运行弹窗 v2(RunDialog)

```
┌ 方案选择: [默认方案(基线)] [方案A] [方案B…]   ← 两类,无临时/上次
│
├─ 选中自建方案 → 只读概要(数据/注入/绑定/参数)
│    失效方案:禁跑 + 「去工作台修复」
│    [ 发起运行 ]
│
└─ 选中默认方案 → 露出可配区(仅 ③绑定 + ④参数)
     [ 另存为方案 ](命名 → POST 创建)  [ 发起运行 ]
```

- 退役:三态下拉、对自建方案的运行时覆盖、弹窗内删方案(归工作台)
- 宿主不变:CaseComposer / RunPanelHost 继续挂载
- **数据集页运行入口**(CaseDataSetsList 卡片 / DataSetEditor「运行此行」):打开标准运行弹窗(两路径),**不做行级预填,`RunPreset` 机制退役** —— 已拍板:统一执行模型,行级精确性通过先建方案获得

## 8. 入口收敛清单

| 旧入口 | 处置 |
|---|---|
| 场景库行 dropdown「查看数据集」 | 移除,由新增直接按钮「方案」替代(带方案数徽标,如 `方案 ·3`) |
| 场景库行 | 新增直接按钮「方案」→ 工作台 |
| 场景详情页「管理数据集」 | 改指工作台;详情页顶栏同加「方案」直接按钮 |
| 数据集页「管理断言」 | 保留(断言编辑器仍是全量编辑视图),工作台断言区另有入口,形成回路 |
| `CaseDataSetsList` / `DataSetEditor` / `AssertionRegistryEditor` 路由 | **全部保留**(工作台深层编辑视图 + 已有深链接不断) |
| TopNav | 不加新项(方案是场景级,无全局页) |

## 9. 失效处理与边界

| 场景 | 工作台 | 运行弹窗 |
|---|---|---|
| 方案引用的数据集被删 | 区内标注「已删除」+ 一键移除 | 方案带失效徽标,禁跑,提示去工作台修复 |
| 断言条目悬空(step 越界 / path 不可解析 / 旧版形状) | 禁选 + 灰显(复用死因分组) | 方案级禁跑 |
| 凭证别名被删 | 绑定行警示(显示原别名),可重选 | UI 提前拦截(dispatch 侧 fail-fast 兜底) |
| 并发编辑 | 单方案 PUT,冲突面小 | — |
| 权限 | 场景属主(owner/admin) | 同 |
| 总量闸 | 参数区实时预览(≤200),不等到运行才 409 | 沿用钳位 |

## 10. 测试策略

- **后端(pytest)**:存量 payload→新表迁移幂等性;CRUD 约束(默认方案不可删/名字锁/两字段强制空/重名 409/属主 403);`config_json` 溯源字段;**现有 runs/dispatcher 测试原样通过**(执行链路零改动的直接证据)
- **前端(vitest)**:工作台分区渲染与默认方案锁定态、失效徽标;RunDialog v2 两路径 + 另存为方案;入口改道路由
- **回归保护**:数据集编辑器/断言编辑器路由与页面不动,其现有测试零变更

## 11. 实施阶段(每阶段可独立合入、平台始终可用)

| 阶段 | 内容 | 期间状态 |
|---|---|---|
| ① 后端地基 | `composer_run_schemes` 表 + 启动迁移 + 方案 CRUD;旧 `PUT /run-schemes` 双读保留 | 旧前端照常工作 |
| ② 工作台 | 新路由页 + 场景库/详情页「方案」直接按钮(读新 API) | 新旧入口并存 |
| ③ 运行侧切换 | RunDialog v2 两路径;`__adhoc__`/`__last__`/`RunPreset` 退役;入口收敛(菜单改道/移除) | 新运行体验上线 |
| ④ 清理 | 旧端点、`scenario_store` 透传逻辑、迁移代码下线 | 收尾 |

## 12. 已拍板决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | 方案 = 一次执行的全部准备,统一工作台,方案是各注入方式的入口 | 用户重构宣言:能力零散、注入位置分散 |
| D2 | 实体归属:数据集/断言条目维持场景级共享库,方案做引用组织 | 资产复用、核心用例结构零改动 |
| D3 | 运行侧:选自建方案即执行(不允许临时调整);默认方案自由配置可另存 | 消除「覆盖是否回写」歧义;用户拍板 |
| D4 | `__adhoc__`/`__last__` 退役 | 分别被默认方案自由配置态、持久化方案替代 |
| D5 | 工作台 = 独立路由页左右分栏;旧入口收敛,编辑器路由保留 | 用户选择 |
| D6 | 方案独立表(非 payload sidecar) | PG 迁移预期:关系建模、部分唯一索引、级联原生 |
| D7 | 方案不加独立 id 以 name 定位 → **被 D6 修订:独立表带 scheme_id** | 表主键自然获得;溯源改名不断链 |
| D8 | 默认方案持久化为 `is_default=true` 特殊项(非运行时虚拟合成) | 配置(绑定/参数)需要记住 |
| D9 | 数据集页运行入口统一两路径,`RunPreset` 退役 | 用户拍板:不搞特殊路径 |
| D10 | 插件/日志订阅在工作台升格为可编辑预埋区(仍 no-op) | schema 已有预埋位,升格 UI |
