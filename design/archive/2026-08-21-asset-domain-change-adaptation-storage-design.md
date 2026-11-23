# 资产域变更适配存储设计(实现方案)

> **[已取代]** 本文档内容已全量吸收并修订进
> `2026-08-21-asset-domain-complete-design.md`(存储 × 适配组件 × 数据集完整设计)。
> 修订要点:直填优先取代创建即全参数化、数据集稀疏行模型放开行间列一致校验、
> 批次注册落独立表、diff 拉取粒度与 ops 草案规则落定。请以新文档为准。

日期:2026-08-21
状态:已取代(见上方说明)
范围:gimbal-platform 资产域(场景/数据集存储)。**执行域不在本方案范围**(另行设计)。

---

## 1. 背景与目标

平台当前资产域存储是"文档形":`composer_scenarios.payload` 一个 JSON 容器装下全部编排产物(definition + orchestration),数据集 `rows` 也是 JSON。这满足了场景级编辑的敏捷性(增删步骤/字段零迁移),但缺一个关键能力:**接口目录变更时的反向影响分析与批量适配** —— "谁调用了接口 X / 谁绑定了 X 的字段 F"目前只能全表扫描 + Python 遍历 JSON。

本方案在**不动权威层**的前提下,补一套派生索引 + 变更检测 + 存档 + 适配操作契约,使平台能够:

1. 场景结构与执行过程数据分离(现状已满足,维持);
2. 场景级步骤/数据增删改查敏捷(现状已满足,维持);
3. 接口字段增删改 → 反查所有调用该接口的场景并快速适配;
4. 接口字段**值域**变更 → 同上,且能贯通到数据集列。

## 2. 需求与约束(原始表述)

- 编排完的用例在后台的存储要**高可用、能快速适应版本变更**;
- scenario 结构与执行过程数据分离;
- 三类变更适配能力:
  1. 单场景:结构(步骤)与数据(数据集行)的增删改查;
  2. 接口级:接口字段增删改 → 反查受影响场景 → 批量适配;
  3. 字段值级:某接口某字段的值变更 → 反查受影响场景(含数据)→ 快速变更;
- 适配实现先走"平台反查 + 逐条引导修改"(方案2),逐步过渡到"plate 版本管理 + 适配插件自动应用"(方案1);
- **硬约束:后续从 SQLite 迁移 PostgreSQL**,新结构必须两者兼容。

## 3. 已定决策记录(ADR)

| # | 决策 | 理由 |
|---|---|---|
| D1 | payload 容器保持单一权威,新表全部为可重建的派生态 | 源存果算;杜绝双写漂移(镜像列教训) |
| D2 | 影响**贯通到数据集列**(选项 B) | 字段值大量经 `${var.*}` 来自数据集行,只改场景结构不解决值的问题 |
| D3 | 存档 = 库内快照表(选项 a) | 批量自动适配(方案1)的安全网:一键整批回滚 + 审计 |
| D4 | 倒排索引用普通列表,不用生成列 | 生成列的 JSON 表达式 SQLite/PG 语法不兼容且 PG 无 VIRTUAL,违背 PG 约束 |
| D5 | 数据集列暂不建索引表 | 受影响场景集小,内存判定键存在性毫秒级;留 `dataset_columns` 升级路径 |
| D6 | 变更检测依赖 plate 现成的 `EndpointSpec.version`(semver)+ `updated_at` | `/api/endpoint/{id}/full` 已返回,plate 侧零开发 |
| D7 | 方案2 与方案1 共用同一补丁契约 | 2→1 过渡 = 换驱动器(人确认 → 插件自动),基底零改 |

## 4. 总体架构

```
权威层(不动)          派生层(新增)                安全网(新增)
─────────────        ──────────────────         ─────────────
composer_scenarios   scenario_endpoint_refs     adaptation_snapshots
  .payload 容器        (接口/字段倒排索引)          (批次 before 快照)
composer_data_sets   catalog_versions
  .rows JSON           (目录版本戳)
```

数据流:

```
plate 目录版本变化 → ① diff 检测(catalog_versions vs plate /full)
  → ② 反查影响清单(倒排索引:场景/步骤/字段/变量/数据集列)
  → ③ 开批次存档(snapshots)
  → ④ 生成 ops 草案(补丁契约)
  → ⑤ 方案2:UI 逐条人工确认应用 ──(未来)── 方案1:plate 插件自动应用
  → ⑥ 推进 catalog_versions,批次关闭
```

## 5. 存储结构设计

### 5.1 `scenario_endpoint_refs` —— 接口/字段倒排索引

```sql
CREATE TABLE scenario_endpoint_refs (
    scenario_id TEXT   NOT NULL,   -- 反查主键:哪些场景
    step_index  INTEGER NOT NULL,  -- definition.steps 下标(编排顺序)
    endpoint_id TEXT   NOT NULL,   -- api.view_hints.endpoint_id,如 fin.order_entrust.order_add
    field_name  TEXT   NOT NULL,   -- 字段键;一字段一行
    source      TEXT   NOT NULL,   -- 'body' | 'headers' | 'query'(同 step 内可能撞名,入 PK)
    via_var     TEXT,              -- 值为 ${var.xxx} 模板(整串或内嵌)时记变量名;直填值 NULL
    PRIMARY KEY (scenario_id, step_index, source, field_name)
);
CREATE INDEX ix_ser_endpoint ON scenario_endpoint_refs (endpoint_id);
```

**维护机制:**

- **写路径同事务**:scenario create / update / delete 时,在**同一数据库事务**内删除该 scenario_id 的旧行、从新 payload 解析插入新行。解析规则:
  - endpoint_id 取 `steps[i].api.view_hints.endpoint_id`(缺失则该步不进索引);
  - 字段遍历 `steps[i].request.body` / `api.headers` / `api.query` 的键;
  - `via_var` 由值匹配 `${var.NAME}` 提取(整串或内嵌均记 NAME)。
- **全量 rebuild 函数**:`rebuild_endpoint_refs(db)` 扫全表重建 —— 对账、灾后重建、升级迁移共用。派生态的不可变保证:任何时刻可 drop 后重建,结果与逐行维护一致。

**范围注(第一批不做):** strategy(断言/提取/赋值)中对 `${var.*}` 的引用是第二批扩展点,索引结构无需变更(加行即可),但解析器需扩展。

### 5.2 `catalog_versions` —— 目录版本戳

```sql
CREATE TABLE catalog_versions (
    endpoint_id TEXT PRIMARY KEY,
    version     TEXT NOT NULL,     -- plate EndpointSpec.version (semver)
    synced_at   DATETIME NOT NULL  -- 本平台最后一次适配完成到的版本时间
);
```

检测 = 拉 plate 目录(或按需逐 endpoint `/full`)对比此表。`synced_at` 只在**适配批次完成**时推进 —— 目录版本高于戳 = 有未适配变更。

### 5.3 `adaptation_snapshots` —— 适配批次存档

```sql
CREATE TABLE adaptation_snapshots (
    id          INTEGER PRIMARY KEY,
    batch_id    TEXT NOT NULL,             -- uuid,一次适配一批
    entity_type TEXT NOT NULL,             -- 'scenario' | 'dataset'
    entity_id   TEXT NOT NULL,             -- scenario_id / dataset_id
    before_json JSON NOT NULL,             -- 受影响实体的完整 before 整像(payload 或 rows)
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_snap_batch ON adaptation_snapshots (batch_id);
```

批次状态(由服务层维护,可落 `batches` 注册行或复用快照首行元数据,实施时定):

```
open(已存档,未应用) → applying(逐条应用中) → completed
                                    ↘ rolled_back
```

**回滚安全(乐观冲突检测):** 回滚写回 before 前,先比对当前库内实体与 `before_json` —— 若批次打开后实体又被用户编辑过(超出本批次 ops 的变更),该实体**跳过回滚并标记冲突**,不盲写。存档覆盖 scenario.payload 与受影响 dataset.rows(D2)。

## 6. 适配操作契约(patch ops)

机器可读修改单,方案2(平台生成 → 人工确认)与方案1(插件生成 → 自动应用)的共同接口:

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

- `renameVar` 同时改:场景内所有 `${var.from}` 引用(含 headers/query/strategy 文本)、数据集列名、绑定该 var 的字段索引行(via_var);
- `renameField` 只改 step 的字段键与索引行,不动数据;
- `mapValue / mapDatasetValues` 服务需求3(值域变更):值在场景直填 → mapValue;值经 var 来自数据集 → mapDatasetValues;
- ops 应用必须幂等(重复应用同 op 无害),自动应用(方案1)的前提。

## 7. 影响分析查询(D2 贯通)

```
接口 X.field 变更 →
SELECT r.scenario_id, r.step_index, r.via_var, d.dataset_id, d.name
FROM scenario_endpoint_refs r
JOIN composer_data_sets d ON d.scenario_id = r.scenario_id
WHERE r.endpoint_id = :X AND r.field_name = :F
-- 内存里确认 d.rows[*] 实际含 via_var 键(列存在性),产出最终影响清单
```

影响清单条目:`{scenarioId, stepIndex, field, viaVar?, datasetId?, datasetColumn?}` —— 即 UI 逐条修改页(方案2)的数据源。

## 8. 服务与 API 面(实施映射)

| 组件 | 内容 |
|---|---|
| `models/scenario_endpoint_ref.py` `catalog_version.py` `adaptation_snapshot.py` | 三张新表 ORM |
| `services/endpoint_ref_index.py` | 解析 payload → 索引行;写路径挂钩;rebuild |
| `services/adaptation_service.py` | 目录 diff、影响查询、批次(存档/ops 应用/回滚/推进戳) |
| `routers/adaptations.py` | `GET /api/adaptations/catalog-diff`、`GET .../impact`、`POST .../batches`、`POST .../batches/{id}/apply`、`POST .../batches/{id}/rollback` |
| `scenario_store` create/update/delete | 事务内挂索引维护 |
| 前端(方案2 闭环) | 目录变更提醒 + 影响清单页 + 逐条确认应用 + 批次回滚 |

**权限:** 批量适配会改他人场景,adaptation 路由**仅 admin**(复用现有 is_admin 判定)。

**方案1 预留(不在本期):** `POST /api/adaptations/batches/{id}/auto-apply` —— 接受 plate 插件生成的 ops 集,存档后批量应用。契约即 §6,无新概念。

## 9. PG 可移植性纪律(硬约束)

- 新表全部普通列(TEXT/INTEGER/DATETIME/JSON);JSON 列 PG 侧经 SQLAlchemy `JSON` 自动落 JSONB,代码零改;
- 禁用 SQLite 专属特性:不用生成列(D4)、不用 `json_extract` 表达式查询、不在新代码写 `PRAGMA`;
- 应用层全 SQLAlchemy ORM/表达式(现状已满足);
- 已知迁移债(迁 PG 前处理,非本期):db.py 手写迁移链(`PRAGMA table_info` + ALTER)换 Alembic;aiosqlite → asyncpg。

## 10. 实施计划(分期,每期独立可验证)

| 期 | 内容 | 验证标准 |
|---|---|---|
| P1 | 三张表 ORM + 建表;索引写路径挂钩(同事务)+ rebuild 函数 | 单测:建/改/删场景后索引一致;rebuild 后与逐行维护结果全等 |
| P2 | 目录 diff(拉 plate version 对戳)+ 影响查询 API | 单测:构造含 `${var}` 绑定场景,反查清单含数据集列 |
| P3 | 批次:存档 / ops 应用(8 种)/ 乐观回滚 / 推进戳 | 单测:每种 op 语义;改后回滚还原;批次后实体被编辑 → 回滚标冲突 |
| P4 | 前端方案2 闭环:变更提醒、影响清单、逐条应用、批次管理 | 手动验证全流程 + 前端测试 |
| P5(未来) | plate 适配插件协议 + auto-apply(方案1) | 插件端到端 |

测试基础设施复用现有 conftest(per-test SQLite fresh_db/client)。

## 11. 范围外(明确不做)

- 执行域任何改动(runs/明细/队列 —— 另案);
- strategy 中 `${var}` 引用的索引覆盖(P2 批扩展点,§5.1);
- `dataset_columns` 派生表(触发条件:数据集规模使内存判定变慢,§D5);
- Alembic 接入与 PG 迁移本身(§9,迁库前专项);
- 多场景并发适配的批间锁(单管理员串行操作,MVP 假设)。

## 12. 开放项

- 批次注册信息(cause/状态/操作者)落独立 `batches` 表还是快照首行元数据 —— P3 实施时定,倾向独立小表;
- 目录 diff 的拉取粒度(全目录列表 vs 仅被引用的 endpoint)—— P2 实施时按 plate 列表接口成本定;
- ops 草案的生成规则库(哪类版本变更映射到哪些 op)初版覆盖 rename/remove/add/mapValue 四类,其余 op 由人工在 UI 构造。
