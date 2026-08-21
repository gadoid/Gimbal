# 资产域完整设计:存储结构 × 变更适配组件 × 数据集

日期:2026-08-21
状态:设计定稿,待实施
范围:gimbal-platform 资产域 —— ① 存储结构(权威层 + 派生索引);② 目录版本变更/字段变更/步骤变更的适配组件;③ 数据集功能重做。
取代 `2026-08-21-asset-domain-change-adaptation-storage-design.md`(其内容已全量吸收并修订)。
执行域不在本方案范围,唯一例外见 D12(基线执行的派发校验放宽)。

---

## 1. 背景与目标

平台资产域存储现状是"文档形":`composer_scenarios.payload` 一个 JSON 容器装下全部编排产物,数据集 `composer_data_sets.rows` 也是 JSON。这满足了场景级编辑的敏捷性(增删步骤/字段零迁移),但存在三个缺口:

1. **反向影响分析缺失** —— "谁调用了接口 X / 谁绑定了 X 的字段 F"只能全表扫描 + Python 遍历 JSON;
2. **目录版本变更无感知** —— plate 侧接口字段增删改/值域变更后,平台无法定位受影响场景,更无法批量适配;
3. **数据集功能不可用** —— 创建靠 RunDialog 里裸 JSON 粘贴,无编辑器、无删除、无列语义(列与场景变量的关系不存在),校验器还强制行间列一致(与运行时的覆盖语义相悖,见 §9 自检 C1)。

本方案一次性补齐这三块,总纲不变:**权威层保持单一源(payload),新增的全部是可重建的派生态;数据集重做只动 API 面与编辑器,存储层零改。**

## 2. 领域模型(总纲)

```
场景 = 配方 + 基线        数据集 = 差异矩阵         执行 = 全量事实(范围外)
```

### 2.1 值存储地图(权威层,唯一真相)

```
场景 payload(一行数据库记录,唯一权威容器)
├── steps[i].request.body / api.headers / api.query
│     ├── 直填字段:  "customer_id": "261"          ← 编排时写的值,存在步骤里,永不搬家
│     └── 已提升字段: "amount": "${var.amount}"     ← 提升后步骤里只留绑定模板
├── config.vars(扁平 name → 值 映射,已存在,零 schema 改动)
│     └── amount: 200                               ← 提升动作把原值落这里;"值即默认值"
│     └── seq: {"kind": "seq"}                      ← 结构化引擎声明,不进列调色板
│
数据集表 composer_data_sets(每数据集一行)
└── rows[*]: { "amount": 300 }                      ← 只存差异;行键 ⊆ 列调色板
```

运行时合成(`_compose_scenario`,已存在):行键合入 `config.vars`,**行值覆盖同名键**;缺键 = 用 vars 值;字段无模板 = 直填值。即:

**基线(默认配置)= 步骤直填值 ∪ vars 扁平值;数据集行 = 对基线的稀疏覆盖。**

### 2.2 直填优先 + 显式提升(D8)

- 编排时字段照旧直填(现状不动);
- "设为变量"是每字段一次的**显式动作**:`body[field] = "${var.<name>}"` + `vars[<name>] = 原值`。提升后基线行为不变(模板解析 = 原值);
- **不做创建即全参数化** —— 同名值场景(如多次审批,同名参数各次取值不同)下自动参数化必然碰撞,且多数字段永远不需要变,全量模板化只是噪音;
- 数据集只能覆盖**已提升**的维度;直填字段对数据集不可见,直到显式提升。

### 2.3 同名提升规则(D11)

- 提升时若 `vars` 已有同名键 → 系统检测并自动后缀:`amount` → `amount_2`、`amount_3`(按序递增),用户可改名;
- 用户故意改回已有名字 = **共享变量**(一次改值,多处生效 —— 本就是 `${var}` 的传值特性),弹确认:"该变量已被步骤 N 使用,共享后改一处动多处";共享是刻意行为,不是意外。

## 3. 存储结构设计

### 3.1 权威层(不动)

`composer_scenarios`(payload 容器)与 `composer_data_sets`(rows JSON)结构零改。数据集列不是 DB 结构(JSON 键),列操作 = JSON 重写。

### 3.2 `scenario_endpoint_refs` —— 接口/字段倒排索引(派生)

```sql
CREATE TABLE scenario_endpoint_refs (
    scenario_id TEXT   NOT NULL,
    step_index  INTEGER NOT NULL,   -- definition.steps 下标
    endpoint_id TEXT   NOT NULL,   -- api.view_hints.endpoint_id
    field_name  TEXT   NOT NULL,   -- 字段键,一字段一行
    source      TEXT   NOT NULL,   -- 'body' | 'headers' | 'query'(同 step 可撞名,入 PK)
    via_var     TEXT,              -- 值为 ${var.NAME} 模板(整串或内嵌)时记 NAME;直填 NULL
    PRIMARY KEY (scenario_id, step_index, source, field_name)
);
CREATE INDEX ix_ser_endpoint ON scenario_endpoint_refs (endpoint_id);
```

**维护**:scenario create/update/delete 在**同一事务**内删旧插新(解析 payload);`rebuild_endpoint_refs(db)` 全量重建 —— 对账、灾后重建、升级迁移共用。派生不变量:任何时刻 drop 后重建,结果与逐行维护一致。rebuild 同时产出**未索引步骤报告**(缺 `view_hints.endpoint_id` 的步骤清单)—— 确定性 ≠ 完备性:rebuild 只保证与逐行维护一致,不保证覆盖全部步骤;漏索引 = 适配清单静默漏保,必须显式可见(C10)。适配中心挂牌展示该报告。

**范围注(第一批不做)**:strategy(断言/提取/赋值)中 `${var.*}` 引用的索引覆盖是第二批扩展点 —— 索引结构不变(加行即可),解析器扩展。影响见 §9 自检 C7。

### 3.3 `catalog_versions` —— 目录版本戳(派生)

```sql
CREATE TABLE catalog_versions (
    endpoint_id TEXT PRIMARY KEY,
    version     TEXT NOT NULL,     -- plate EndpointSpec.version (semver)
    synced_at   DATETIME NOT NULL  -- 最后一次适配完成到的版本
);
```

检测 = 拉 plate 目录列表,逐 endpoint 对戳。`synced_at` 只在**适配批次完成**时推进 —— 目录版本高于戳 = 有未适配变更。

### 3.4 `adaptation_batches` + `adaptation_snapshots` —— 批次与存档

```sql
CREATE TABLE adaptation_batches (
    batch_id     TEXT PRIMARY KEY,        -- uuid
    endpoint_id  TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version   TEXT NOT NULL,
    status       TEXT NOT NULL,           -- open|applying|completed|rolled_back
    operator_id  INTEGER NOT NULL,
    created_at   DATETIME NOT NULL,
    closed_at    DATETIME
);

CREATE TABLE adaptation_snapshots (
    id          INTEGER PRIMARY KEY,
    batch_id    TEXT NOT NULL,             -- FK adaptation_batches
    entity_type TEXT NOT NULL,             -- 'scenario' | 'dataset'
    entity_id   TEXT NOT NULL,
    before_json JSON NOT NULL,             -- 受影响实体完整 before 整像(payload 或 rows)
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_snap_batch ON adaptation_snapshots (batch_id);
```

批次状态机:`open(已存档未应用) → applying(逐条应用中) → completed`;任意完成前状态可 → `rolled_back`。(老方案的"批次注册信息落哪"开放项就此定为独立小表。)

### 3.5 PG 可移植性纪律(硬约束)

- 新表全部普通列(TEXT/INTEGER/DATETIME/JSON);JSON 列经 SQLAlchemy `JSON` 在 PG 侧自动落 JSONB,代码零改;
- 禁用 SQLite 专属特性:无生成列、无 `json_extract` 表达式查询、新代码不写 `PRAGMA`;
- 已知迁移债(迁 PG 前专项处理,非本期):db.py 手写迁移链换 Alembic;aiosqlite → asyncpg。

## 4. 数据集实现

### 4.1 决策表(v3 定稿)

| # | 决策 |
|---|---|
| D8 | 直填优先;"设为变量"为显式动作,原值落 vars(扁平值即默认值,零 schema 改动) |
| D9 | 基线 = 步骤直填值 ∪ vars 扁平值(同 payload 两地址,**零另存**);行 0 为投影 |
| D10 | 数据集行**稀疏**:行键各自 ⊆ 列调色板;**放开现网行间列一致性强校验**(§9 C1) |
| D11 | 同名提升:系统检测 + 自动后缀 `_2/_3`;改名共享 = 刻意行为,确认弹窗 |
| D12 | 基线执行:空 dataSetIds = 一个隐式空覆盖行(唯一执行域触点,仅改派发校验一处) |
| — | 列调色板 = 已声明且为**标量**的 vars 键;行键超出 → 422,错误信息含提升指引 |
| — | 各数据集列集可为不同子集(存储自由);编辑器按场景级统一列视图展示(展示统一) |

### 4.2 行 0"默认配置"虚行

数据集编辑器第 0 行 = 基线投影,**不落库**(源存果算:撤掉重算结果一致):

- **渲染数据源 = 场景 payload**(`GET /api/scenarios/{id}`,已存在),**不是倒排索引** —— 索引不存值,只做反查(§9 C3);
- 列 = 按步骤分组的全部端点绑定字段,两类列:

| | 变量列 | 直填列 |
|---|---|---|
| 行 0(基线) | 按默认渲染的值,浅灰,标"变量" | 步骤里的直填值,深灰,标"直填·步骤 N" |
| 真实行 1..n | 白格可覆盖 | **"—" 不可覆盖** |
| 点行 0 格子 | 改 vars 值(场景更新) | 就地改直填值(场景更新)或**就地"提升为变量"** |

- 行 0 因此成为完整配置工作台:一眼看到"实际会发什么"(基线渲染)、"哪些维度可变"(变量列)、"为什么跑了没变"(直填列,想变 → 就地提升);
- 两种格子的编辑都路由**场景更新 API**,`composer_data_sets` 永远只存真实变体行;
- 场景尚无任何已提升变量 → 调色板为空,编辑器提示"先在编排中(或行 0)把字段设为变量"。

### 4.3 列调色板与校验

- **调色板** = `{ name ∈ config.vars : 值为标量(str/num/bool) }` —— 排除结构化引擎声明(如 `{"kind":"seq"}`,数据集覆盖会破坏生成器语义);
- 行键 ⊆ 调色板,否则 422,错误信息直接教学:`undeclared_var: "qty2" — 该字段未声明为变量;在编排中"设为变量"后即可作为数据集列`;
- **放开 `_check_rows_consistent`**(现网 `scenario_composer.py` DataSet/DataSetDraft 双处):删除"行间列集必须一致"校验,替换为上述子集校验。运行时语义本就支持稀疏(`_compose_scenario` 缺键回落),旧校验是 JSON 粘贴时代的防御,与新模型冲突;
- 死数据 lint(保存时告警,不阻断):声明未引用 / 引用未声明 / 数据集列无任何字段引用 / 步骤缺 `endpoint_id`(不参与变更适配)/ `endpoint_id` 与 api URL 疑似漂移 —— 后两条即索引完备性 lint(C10)。

### 4.4 提升交互

- 入口两处:编排页字段表单("设为变量")+ 数据集编辑器行 0 直填格(就地提升);
- 提升是前端 store 操作(无状态编排架构不变):写绑定模板 + vars 注册,保存走既有场景 PUT;同名检测在前端对 `config.vars` 键做,后端 lint 兜底;
- 提升后原值落 vars,基线行为不变;数据集从此可覆盖该列;
- 未来可选"参数化向导"(多选字段 → 预览生成名含后缀 → 确认),单字段提升是原语,批量只是循环它。

### 4.5 API 面(现状 + 增改)

| 端点 | 现状 | 变更 |
|---|---|---|
| `GET /api/data-sets?scenarioId=` | 有(ownserhip 过滤) | 不变 |
| `GET /api/data-sets/{id}` | 有 | 不变 |
| `PUT /api/data-sets/{id}` | 有(全量替换) | 不变(校验换为 §4.3) |
| `POST /api/scenarios/{id}/data-sets` | 有 | 不变(校验换为 §4.3) |
| `DELETE /api/data-sets/{id}` | **无(曾因零消费者移除)** | **新增** —— 编辑器重做引入真实消费者;ownership 走既有 `_require_dataset_owner` |
| `GET /api/scenarios/{id}` | 有 | 行 0 渲染数据源,不变 |

规模:几十到几百行/数据集,全量替换 PUT 足够;行级 PATCH 不做。粘贴导入**预留**(行 = dict 的数据模型天然兼容,UI 后补)。

### 4.6 编辑器(CaseDataSetsList 重做)

- 场景维度列表(卡片 → 表格)+ 详情编辑页:行 0 虚行 + 真实行网格(Element Plus table 行内编辑,无虚拟滚动);
- 列头两行:变量名 / `→ 步骤 N · 字段 X`(via_var 对应关系);
- 手动录入为主;新建便捷动作"**从基线提取首行**"(把全部变量列的基线值抄成第 1 行,解决冷启动);
- 运行对话框(RunDialog)增"**默认配置(基线)**"伪数据集选项 = 空覆盖行执行(联动 D12)。

## 5. 变更适配组件

### 5.1 检测:目录 diff

拉取 plate 目录列表(全目录,接口量级为几十,一次列表足够 —— 老开放项就此定为全量拉取),逐 endpoint 比对 `catalog_versions`:

- 版本高于戳 → 记入"待适配"提醒(前端导航徽章 + 适配中心列表);
- 提醒是**拉取时计算**,不后台轮询(管理员打开适配中心时 diff);
- (可选半步,P3)同次拉取顺带比对 `updated_at`:"plate 侧已更新但 version 未动"标为**异常提醒**,不自动适配 —— 抓"忘 bump"(列表接口若不携带 `updated_at` 则此半步顺延);内容哈希兜底明确**不做**:plate 与平台同仓同队,单系统信任边界内版本纪律归 plate;方案1 插件生态/外部目录源出现时再议(C12)。

### 5.2 影响分析

```
接口 X.field 变更 →
SELECT r.scenario_id, r.step_index, r.via_var, d.dataset_id, d.name
FROM scenario_endpoint_refs r
JOIN composer_data_sets d ON d.scenario_id = r.scenario_id
WHERE r.endpoint_id = :X AND r.field_name = :F
-- 内存里确认 d.rows[*] 实际含 via_var 键(列存在性,D5:不建 dataset_columns 表)
```

清单条目:`{scenarioId, stepIndex, source, field, viaVar?, datasetId?, datasetColumn?}` —— 方案2 逐条引导页的数据源。**直填字段同样命中**(索引行按字段键存在,与值是否模板无关),条目标记"直填/模板"。

### 5.3 批次生命周期

```
管理员发现待适配 → 开批次:存档全部受影响实体(snapshots.before_json)→ status=open
  → 生成 ops 草案 → 逐条确认应用 → applying → completed → 推进 catalog_versions
  ↘ 任意完成前状态可整批回滚 → rolled_back
```

- **回滚安全(乐观冲突)**:回滚写回 before 前,比对库内当前实体与 `before_json`;批次打开后实体被用户编辑过(超出本批次 ops)→ 该实体**跳过回滚并标记冲突**,不盲写;
- **应用期防过期**(§9 C5):ops 以 `step_index` 寻址,若清单生成后用户重排了步骤,应用时**重验该 step 的 endpoint_id 与 op 期望一致**,不一致 → 该条标记冲突跳过,不盲改;
- ops 应用必须**幂等**(重复应用同 op 无害)—— 方案1 自动应用的前提。

### 5.4 补丁契约(patch ops)

方案2(平台生成 → 人工确认)与方案1(plate 插件生成 → 自动应用)的共同接口:

```jsonc
{
  "batchId": "...",
  "scenarioId": "sc-xx",
  "cause": { "endpointId": "fin.order_entrust.order_add", "fromVersion": "1.0.0", "toVersion": "1.1.0" },
  "ops": [
    { "op": "renameField",         "step": 2, "from": "customer_id", "to": "cust_id" },
    { "op": "addField",            "step": 2, "field": "new_field", "value": "" },
    { "op": "removeField",         "step": 2, "field": "deprecated_field" },
    { "op": "rebindField",         "step": 2, "field": "cust_id", "var": "customer_id" },
    { "op": "renameVar",           "from": "customer_id", "to": "cust_id" },
    { "op": "renameDatasetColumn", "datasetId": "ds-1", "from": "customer_id", "to": "cust_id" },
    { "op": "mapValue",            "step": 2, "field": "settle_type", "map": { "1": "2" } },
    { "op": "mapDatasetValues",    "datasetId": "ds-1", "column": "settle_type", "map": { "1": "2" } }
  ]
}
```

语义要点:

- `renameField`:改 step 字段键 + 索引行,不动数据;
- `renameVar`:改场景内全部 `${var.from}` 引用(body/headers/query/strategy 文本)+ 数据集列名 + via_var;
- `mapValue`(值域变更,直填)/ `mapDatasetValues`(值域变更,经 var 来自数据集)—— D8 下两条通路并存,影响清单按 via_var 是否为空自动选路;
- **草案生成规则**(初版):rename/remove/add/mapValue 四类由 diff 自动生成草案;其余 op(rebind/renameVar/renameDatasetColumn/mapDatasetValues)由人工在 UI 构造。

### 5.5 方案2 UI 流(本期)与方案1 预留(未来)

- **本期(方案2,人工确认)**:目录变更提醒 → 适配中心(批次列表/待适配清单)→ 影响清单(按 endpoint/字段分组,含直填/模板、数据集列标注)→ 逐条预览 op diff → 确认应用 → 批次详情可整批回滚;
- **未来(方案1,插件自动)**:`POST /api/adaptations/batches/{id}/auto-apply` 接受 plate 插件生成的 ops 集,存档后批量应用。契约即 §5.4,无新概念 —— 过渡 = 换驱动器,基底零改;
- **权限**:批量适配会改他人场景,adaptation 路由**仅 admin**(复用现有 is_admin 判定);
- **所有者知情(P5)**:批次列表提供按 owner 过滤的只读视图("我的场景被适配记录"),零新基础设施(平台无通知系统,不为此新建);所有者**确认流程**明确不做 —— 与单管理员 MVP 假设冲突(C13);真正的安全网 = 快照 + 整批回滚(已有)。

## 6. 服务与实施映射

| 组件 | 内容 |
|---|---|
| `models/scenario_endpoint_ref.py` `catalog_version.py` `adaptation_batch.py` `adaptation_snapshot.py` | 四张新表 ORM |
| `services/endpoint_ref_index.py` | payload → 索引行解析;写路径同事务挂钩;rebuild(附未索引步骤报告) |
| `services/adaptation_service.py` | 目录 diff、影响查询、批次(存档/ops 应用/回滚/推进戳) |
| `services/data_set_store.py` | 扩展:调色板校验(422 教学)、DELETE |
| `schemas/scenario_composer.py` | `_check_rows_consistent` 替换为行键 ⊆ 调色板校验 |
| `routers/adaptations.py` | catalog-diff / impact / batches / apply / rollback(admin-only) |
| `routers/data_sets.py` | +DELETE |
| `run_dispatcher`(唯一执行域触点) | 空 dataSetIds 放行 = 隐式空行(D12) |
| 前端 | 数据集编辑器重做(行 0/提升/删除/从基线提取首行)、字段表单"设为变量"、RunDialog 默认配置项、适配中心 |

## 7. 实施计划(分期,每期独立可验证)

| 期 | 内容 | 验证标准 |
|---|---|---|
| P1 ✅(2026-08-21 完成) | 四表 ORM + 建表;索引写路径挂钩(同事务)+ rebuild(附未索引步骤报告) | 单测:建/改/删场景后索引一致;rebuild 与逐行维护结果全等;缺 endpoint_id 的步骤进报告 |
| P2 ✅(2026-08-21 完成) | 数据集重做:校验替换、调色板 422、DELETE、编辑器(行 0/提升/提取首行)、RunDialog 基线项 + D12 校验放宽 | 单测:稀疏行接受、超集 422、DELETE;集成:行 0 编辑路由场景更新、空数据集执行 = 基线 |
| P3 | 目录 diff + 影响查询 API(可选:updated_at 异常提醒) | 单测:构造 `${var}` 绑定场景,反查清单含数据集列;直填字段命中 |
| P4 | 批次:存档 / 8 种 op 应用 / 乐观回滚 / 应用期重验 / 推进戳 | 单测:每种 op 语义与幂等;改后回滚还原;批次后实体被编辑 → 回滚标冲突;步骤重排后应用 → 标冲突跳过 |
| P5 | 前端适配闭环:变更提醒、影响清单、逐条应用、批次管理、owner 只读批次视图 | 手动全流程 + 前端测试 |
| P6(未来) | plate 适配插件协议 + auto-apply(方案1) | 插件端到端 |

P2 与 P1 无依赖(调色板只需 payload 的 vars,不需索引),可并行。测试基础设施复用现有 conftest(per-test SQLite fresh_db/client)。

### 实施进度(2026-08-21 交接)

**P1+P2 已完成并推送** — 分支 `strbody_avaliable`,提交区间 `cafa46d..afdb602`(16 个提交)。实施计划:`docs/superpowers/plans/2026-08-21-asset-domain-p1-p2.md`(11 任务全部通过任务评审 + 最终全分支评审 + 修复批次复审)。验证基线:后端 pytest **133 passed**、前端 vitest **18 文件 113 tests**、`npm run build` 干净。

**接手 P3 前的代码状态:**

- **活**:倒排索引 `scenario_endpoint_refs` 随场景 create/update/delete 同事务维护(`services/endpoint_ref_index.py`),`rebuild()` / `unindexed_steps()` 可对账(P3 影响查询的数据源已实时就绪);数据集域全量落地(稀疏行 D10、调色板 422、行 0 基线 D9、字段提升 D8、基线执行 D12)。
- **休眠**:`catalog_versions` / `adaptation_snapshots` / `adaptation_batches` 三表已建已注册(`models/`),无任何服务读写 — **P3 第一步即在它们之上接 `adaptation_service`**。
- **缺**:`services/adaptation_service.py`、`routers/adaptations.py`(契约见 §5/§6)、前端适配中心(P5)。

**实施期裁定的语义(计划原文与此有出入时以此为准):**

1. 场景 `create()` 的索引挂钩位于既有 try 块**内**(autoflush 会使重复 PK 的 IntegrityError 提前浮出;见 `scenario_store.py` 代码注释);
2. `rowFromBaseline` 为结构性两遍规则:整串 `${var.x}` 模板定义基线(first-writer-wins),纯组合模板变量不入行(D10 稀疏语义);
3. RunDialog 空数据集选择按基线显示运行数(`totalRuns` 与磁贴,`onConfirm` 仍原样派发空数组)。

**最终评审遗留(已裁定接受,后续顺手清):**

`helpers.test_env` 幽灵收集改名(独立卫生项,会改测试计数基线);FieldActionMenu 4 处 `:domain` 透传(基线既有,无伤害);`renderTemplate` 非全局正则(行 0 显示尾部场景);空调色板提示文案(§4.2);§4.3 其余 lint 项(URL 漂移等,随 P3/P5 补)。

**下一步**:为 P3(目录 diff + 影响查询 API)出实施计划,§5 即需求源;P3+P4 可合并规划。本地起服务:后端 `cd src/gimbal-platform/backend && python -m app.main`(8000),前端 `cd src/gimbal-platform/frontend && npm run dev`(5173,/plate 代理→8765)。

## 8. 范围外(明确不做)

- 执行域重构(runs/明细/队列/JSONL —— 另案;D12 仅一处校验放宽);
- strategy 中 `${var}` 引用的索引覆盖(第二批扩展点,§3.2);
- `dataset_columns` 派生表(触发条件:数据集规模使内存列存在性判定变慢);
- Alembic 接入与 PG 迁移本身(迁库前专项);
- 多场景并发适配的批间锁(单管理员串行操作,MVP 假设);
- 场景所有者的适配确认流程(知情走只读视图,§5.5);
- 版本检测的内容哈希兜底(单系统信任边界,方案1/外部目录源出现时再议,§5.1);
- 粘贴导入 UI(数据模型已预留,本期只做手动录入)。

## 9. 自检报告(冲突检查)

编写本稿时对三部分(存储/适配/数据集)与**现网代码**交叉核对,发现并处理以下冲突(C1-C9);C10-C13 为评审轮对用户提出的设计层问题的处置记录:

| # | 冲突 | 处置 |
|---|---|---|
| C1 | **现网 `scenario_composer.py` `_check_rows_consistent`(DataSet 与 DataSetDraft 双处)强制同一数据集内所有行列集一致** —— 与 D10 稀疏行模型(缺键回落基线)直接冲突,且与运行时 `_compose_scenario` 语义本就不符 | P2 删除该校验,替换为"行键 ⊆ 调色板"子集校验;编辑器灰格渲染保留表格心智,存储不再要求全宽 |
| C2 | D12 基线执行需改 `run_dispatcher` 校验(现网空 dataSetIds → 409 `no_data_selected`)—— 与"执行域封存"路线冲突 | 明确为**唯一例外**:仅放宽校验(空 = 一个隐式空覆盖行),不改执行结构/存储;已获用户决策确认,实施期单独提交 |
| C3 | 行 0 若从倒排索引渲染则无值可显(索引不存值) | 行 0 渲染数据源 = 场景 payload(GET scenario),索引仅做反查;两者职责写死不可互换 |
| C4 | 早前讨论中"vars 需补 default 形态"的设想与现网不符 —— `config.vars` 是扁平 name→值,`_compose_scenario` 直接合并 | 修正:扁平值即默认值,零 schema 改动;提升 = 写绑定 + `vars[name]=原值` |
| C5 | ops 以 step_index 寻址,清单生成到应用之间用户可能重排步骤 → 盲改错步骤 | 应用期重验 step 的 endpoint_id 与 op 期望一致,不一致标冲突跳过(§5.3) |
| C6 | 老存储文档定稿后,讨论中"创建即全参数化/常量锁/行 0 只显示已参数化变量"三项已被后续决策推翻 | 本稿以最新决策为准(D8 直填优先、常量锁概念取消 —— 未提升即常量、行 0 显示全部端点绑定字段);老文档标记取代 |
| C7 | 调色板含"仅在 strategy 引用的变量"(可被行覆盖)但索引第一批不覆盖 strategy 引用 → 此类列可跑不可反查 | 已知缺口,非矛盾:P 第二批扩展索引解析器后闭合;影响清单对无字段绑定的列不误报 |
| C8 | 老文档开放项三项(批次注册落哪 / diff 拉取粒度 / ops 草案生成规则)悬而未决 | 本稿全部落定:独立 `adaptation_batches` 表 / 全目录列表拉取 / rename-remove-add-mapValue 四类自动草案 |
| C9 | DELETE 数据集端点曾因零消费者移除(路由注释明示),本方案重新引入 | 有意为之:编辑器重做产生真实消费者;ownership 复用既有 `_require_dataset_owner`,无新权限面 |
| C10 | ①索引完备性依赖 `view_hints.endpoint_id`,手工/API 编辑路径漏带即**静默漏保**(rebuild 只保证确定性不保证完备性,漏索引场景在适配清单中消失) | P1 rebuild 附未索引步骤报告 + 编辑器 lint 两条(缺 endpoint_id / 与 URL 疑似漂移)+ 适配中心挂牌(§3.2/§4.3);判定:四项中唯一立即做 —— 核心机制的信任缺口 × 保险最便宜 |
| C11 | ②自动草案仅覆盖四类 op,复杂变更需人工构造 | 判定:**非缺口** —— 人工构造即方案2 本体,自动草案只是便利层;复杂变更多可分解为简单 op 序列(字段挪位 = remove + add);op 库按真实使用频率增长,不预穷举(§5.4) |
| C12 | ③版本检测完全信任 plate semver,无内容哈希兜底 | 单系统信任边界内可接受,哈希兜底明确不做(§8);P3 可选半步:diff 同次比对 `updated_at`,"改了但 version 未动"标异常提醒不自动适配(§5.1) |
| C13 | ④批量适配仅 admin 门槛,场景所有者无知情/确认 | 确认流程与单管理员 MVP 假设冲突,范围外(§8);知情走 P5 批次列表按 owner 过滤的只读视图(§5.5);安全网 = 快照 + 整批回滚(已有) |

其余交叉点核对无冲突:mapValue/mapDatasetValues 双通路与 D8 一致(§5.4);renameVar 联动数据集列名与调色板定义一致;数据集表零改与 D1 权威层不动一致;快照表覆盖 scenario.payload 与 dataset.rows 与 D2 贯通范围一致。
