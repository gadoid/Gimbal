# 交互字段与口径统一 — 评估方案(待评审)

> **用途**:PG 迁移(2026-09-22 完成)后的读侧现代化评估。系统盘点平台侧
> "快照 vs 活名 / 前端自拼映射 / 同表双口径 / Python 聚合未下推"四类问题
> 点,给出统一处置规则与工作分包,供拍板。
> **来源**:2026-09-22 全库盘点(后端 models/routers/services + 前端
> views/stores/components 逐点核查,file:line 均为当期分支实测)。
> **状态**:已实施(2026-09-22,分支 ``feat/join-projection-caliber-unification``,
> E4 热修 + G1–G6 全包落地,后端 681/前端 1089 测试绿;远端 PG 已
> ``alembic upgrade head`` 到 0005,存量 row_count 自愈)。拍板缺省见
> §7 各条「已定」;§1.D 的 D2 勘误见该表下注。

---

## 0. 背景与问题定义

SQLite 时代,跨表交互字段(执行记录显示场景名、明细行显示数据集名)没有
廉价的 DB 侧手段,演化出两类代偿:**前端自拼 id→name 映射**与**冻结快照
列**。迁到 PG 后(JSONB 生成列、trgm 检索、join/子查询、DISTINCT ON),
这类字段可以统一为**服务端读侧投影**,且不触碰任何表结构。

首轮盘点 **20 个点位**:4 个已符合目标范式(§2),16 个待处置(§1),
归并为 5 条统一规则(§3)与 5 个工作包 G1–G5(§4)。

**二轮补充评审(同日,adaptation / carry / run_scheme / board 四域)**:
新增 E 类 5 点(§1.E),其中 **E4 是生产在跑的 bug**(board 场景标签恒
回落裸 id,§7 决策点 7);run_scheme 域核查通过、无需行动。工作包新增
G6,并扩展 G1 覆盖 adaptation 域与 board 修复。

**与既有决策的关系**:全部处置手段在「payload 唯一可写源 + 派生须 DB/纯
函数物化」(生成列四轮定稿)框架内 —— 读侧投影不落列、同表双口径走写归一
或生成列、**不做任何应用层镜像列/双写**;双方言纪律(SQLite 本地/测试 +
PG 生产)全程保持。

---

## 1. 全量清单

### A 类:前端自拼 id→name 映射(客户端 join)

| # | 位置 | 现状 | 硬伤 |
|---|---|---|---|
| A1 | `frontend/src/views/ExecutionsList.vue:280-290` | 拉 `listScenarioOptions({page_size:100})` 拼 `scenarioNames`,查不到回落裸 id | options 端点有分页但前端不翻页 → **第 101 个场景起静默丢失**;已删/他人 private 场景回落裸 id |
| A2 | `frontend/src/components/workbench/RecentExecutionsCard.vue:38` | 工作台最近执行直接显示裸 `scenario_id`(mono + title 提示) | 连映射都没做 |
| A3 | `frontend/src/components/adaptations/OpConstructDialog.vue:226,254` | 适配 op 构造对话框同样 options 拼映射(`buildMap`) | 同 100 截断 |
| A4 | `frontend/src/stores/scenario-composer.ts:98` | composer store 拉 options(选择器用途) | 场景过百后选择器选不到 |
| A5 | `frontend/src/views/Runner.vue:275` | 运行对话框场景选择器 | 同上 |
| A6 | `frontend/src/views/Executions.vue:135-137` | 行级明细表 `datasetId` 裸 id(缺省显示"基线"),`injectionId` 裸 id 徽标 | 无名称解析,数据集已删/改名时不可读 |
| A7 | `frontend/src/views/ServiceAliasDetail.vue:135` | 别名清单 + 目录服务名客户端拼接 | 量小,边缘,优先级最低 |

共性根因:**options 端点(`GET /scenarios?fields=options`,设计定位就是
"选择器/名称映射专用")被当作全量名称索引用,但它是分页的**。

### B 类:快照 vs 活源(跨表交互字段)

| # | 字段 | 现状 | 判定 |
|---|---|---|---|
| B1 | `executions.scenario_name`(快照列) | 在 DB 但**不进任何响应**;检索(M4 q,`backend/app/routers/executions.py:171-176`)打**快照名**,展示打**前端映射** → 同一个名字三个口径 | 待处置(核心) |
| B2 | `executions.owner_name` | 快照 + owner_id NULL 时"(已注销)"读侧投影(`execution_store.py:91-94`) | ✅ 范式 |
| B3 | `executions.config_json.schemeName` 等 | dispatch 时冻结,审计语义 | ✅ 正确保冻 |
| B4 | 通知 title/body | 事件发生时快照 | ✅ 正确保冻 |
| B5 | `execution_rows.dataset_id / injection_id` | 软引用无名称(A6 的根因) | 待处置 |

### C 类:同表双口径字段

| # | 字段 | 现状 | 判定 |
|---|---|---|---|
| C1 | `definition.scenarioId`(顶层)vs `definition.meta.scenarioId` | 写侧同步(`scenario_store.py:134-144`);但读侧 `create()` 顶层优先(`scenario_store.py:57`)、`_meta_from_row` 只读 meta —— 存量行两处不一致时各说各话 | 待归一 |
| C2 | `meta.updateTime` vs `updated_at` | 读时以 DB 行覆盖(`scenario_store.py:548`) | ✅ 范式 |
| C3 | `meta.createTime` vs `created_at` | **未覆盖**:客户端传的 createTime 直接透传展示,可伪造/漂移 | 待归一 |
| C4 | `meta.owner` vs `owner_name` 列 | 写侧同步 + ETL 回填,基本一致(owner_name 列本身几乎无读消费) | 顺带处置(§4 G3) |
| C5 | `composer_data_sets.row_count` vs `len(rows)` | 应用双写维护(`data_set_store.py:77,110`) | 待生成列化 |

### D 类:Python 聚合可下推 SQL

| # | 位置 | 现状 | 判定 |
|---|---|---|---|
| D1 | `backend/app/services/board_assembler.py:49-68` `_latest_terminals` | 全量拉 Execution 行内存折叠"每场景最近完成态"(跨 owner 平台视角) | 待下推(`DISTINCT ON`) |
| D2 | `frontend/src/stores/executions.ts:116` `fetchList()` | ~~API 的 `scenario_id` 参数未用~~ **实施轮勘误**:方案展开行走的是 `useScenarioRuns.load`(已传 `scenarioId`+limit 30),无参 `fetchList` 只服务台账列表页本身 —— D2 前端部分为误报,无需行动 | 勘误结案 |
| D3 | `execution_store.py:112-144` `consecutive_failure_streaks` | 最近 1000 条轻行扫描内存折叠 | 量级可控,可选优化 |

### E 类:派生/聚合展示面缺实体上下文(二轮补充评审)

四域补充核查的结论。共同点:数据都在,展示投影缺一层实体身份。

| # | 位置 | 现状 | 判定 |
|---|---|---|---|
| E1 | adaptation op 列表(`adaptation_service.py:480-486` `_op_out`) | 只带 `scenarioId/datasetId/opType/payload/status` 裸键 —— 用户看到"哪个场景的哪一步"但不知道场景叫什么、这步打的是哪个接口 | 待处置 → G1 扩展 |
| E2 | adaptation batch 触发上下文(`_batch_detail:489-520`) | **触发上下文其实记录了**(`endpoint_id/from_version/to_version` 都是列),缺的是展示投影:endpointId 无人类可读名 | 待处置 → G1 扩展 |
| E3 | carry 绑定面(`routers/carry.py:127-151`,`schemas/carry.py:28` `CarryFieldFace = {path,type,description}`) | face 是服务内**跨端点按 path 归并的并集**,归并时丢掉了贡献端点 —— 配置页只见字段名不知属于哪个接口 | 待处置 → G6(语义修正:不是逐行 join,见 §4) |
| E4 | board 场景节点标签(`board_assembler.py:238-246`) | **活 bug**:意图正确(label=活名 or sid + exists 标记),但读取路径是 `row.payload.get("meta")` —— 容器实际是 `payload.definition.meta`,恒取 None → **标签恒回落裸 sid**。根因是 C 类:容器形状知识绕过了 `definition_from_payload` 单点 | **bug,建议立即修**(§7 决策点 7) |
| E5 | board grid 槽③(`board_assembler.py:110-120`) | lastRun 是跨场景聚合(`best` 取覆盖场景里最近完成态),不携带"最近执行的是哪个场景" | 可选增强(产品定) |

**run_scheme 域核查通过,无需行动**:`name` 是独立列
(`models/composer_run_scheme.py:46`,进 `uq_run_scheme_scenario_name`
唯一索引),**非 JSON 嵌套**,无双口径;方案列表是场景内上下文(页面自带
场景名);跨场景溯源走 executions `config_summary.schemeName` 快照(审计
语义正确,照 B3 保冻)。


---

## 2. 已有正确范式(统一规则的提取源)

| 范式 | 实例 | 提取的规则 |
|---|---|---|
| 快照 + 读侧存在性投影 | owner_name"(已注销)" | 展示名活源优先、快照兜底、状态标记 |
| DB 权威读时覆盖 | updateTime 以 `row.updated_at` 覆盖 | 同表双口径,服务端权威赢 |
| 前端多请求拼合 → 服务端合流 | activity(M5,`routers/activity.py`) | 跨源展示字段由服务端一次给全 |
| 聚合下推 + 方言分派 | facets GROUP BY / q 下推(M3/M4) | PG 走 SQL,SQLite Python 兜底 |
| 批量 IN 预取替代逐行查 | `snapshot_ids` / `dataset_counts` | 列表页伴生名称解析的标准实现 |

---

## 3. 统一处置规则(五条)

1. **跨实体展示名 = 服务端读侧投影**。响应携带
   `display_name = COALESCE(活名, 快照名, id)` + 实体存在性标记;实现按
   `snapshot_ids` 先例做**每页一次批量 IN 预取**(≤200 id,双方言同一实现,
   不引入 ORM join 复杂度)。前端删除自拼映射。
   → 覆盖 A1 / A2 / A3(展示部分)/ A6 / B1 / B5。
2. **审计快照列不动、不 join**。B2 / B3 / B4 保持冻结;展示字段与审计字段
   物理分离,一个字段不兼任两职。B1 的 `scenario_name` 列原样保留(导出
   端点与"当时跑了什么"语义的唯一依据),新增的 display 字段只做导航。
3. **同表双口径 = 写归一 + 读时覆盖**。C3 照 C2 范式;C1 读侧统一口径 +
   存量审计;C5 走生成列(`jsonb_array_length`,SQLite 方言变体
   `json_array_length`)。
4. **选择器 ≠ join 问题**。A4 / A5 的出路是 options 端点支持 `q` 检索
   (复用 trgm)+ 前端可搜索下拉,不是给选择器做 join。
5. **聚合下推 = PG 走 SQL、SQLite Python 兜底**。D1 照 M3 方言分派模式;
   D2 只是前端改传已有参数。

---

## 4. 工作分包

### G1 执行台账名称投影(核心,前后端同车)

**目标**:执行列表/详情的 `scenario_display_name` + `scenario_deleted`;
行级明细的 `dataset_name`;q 检索与展示同口径。

后端改动:
- `GET /executions` 列表与 `GET /executions/{id}` 详情响应加
  `scenario_display_name`、`scenario_deleted`:列表路径对当页
  `scenario_id` 集合一次批量 IN 查 `composer_scenarios.scenario_id → name`
  (生成列直读),`COALESCE(活名, 快照, id)`,join 不到且快照非空 →
  `scenario_deleted = true`;
- **可见性约束(影响评估轮新增,防信息泄露)**:活名 join 必须套与列表
  相同的可见性谓词(`visibility = 'public' OR owner_id = :me OR admin`)
  —— 场景被执行后转让他人转 private 时,不得向历史执行者泄露当前名;
  快照名是执行者自己记录的一部分,照常显示。谓词复用
  `scenario_query._visibility_clause` 口径,不另开第二份;
- q 下推扩口径:`scenario_name ILIKE :q OR scenario_id ILIKE :q OR
  scenario_id IN (SELECT scenario_id FROM composer_scenarios WHERE
  name ILIKE :q)`(子查询吃 trgm 索引,快照名与活名都可命中);
- `GET /executions/{id}/rows` 每页批量 IN 查
  `composer_data_sets.dataset_id → name`,响应加 `dataset_name`
  (已删回落 id);`injection_id` 展示维持 alias 本身(自释义,不 join)。

前端改动:
- `ExecutionsList.vue` 删 `scenarioNames` 映射与 options 拉取,改用响应
  字段;已删场景按 owner_name"(已注销)"先例渲染"(已删)";
- `RecentExecutionsCard.vue` 改用 `scenario_display_name`。

**验收**:改名场景后,列表显示新名、旧名可搜到历史执行;删除场景后,列表
显示快照名 + "(已删)";前端不再持有名称映射。
**风险**:响应加字段向后兼容(新增键);q 扩口径后命中集变大,属预期修正。

**二轮扩展(E1/E2/E4)**:
- adaptation op 列表(`_op_out`)加 `scenario_display_name` + `dataset_name`
  (批量 IN 同上);已删场景兜底链是本域特有优势:**活名 →
  `adaptation_snapshots.before_json`(回滚安全网恰是场景 payload 整像,
  含 meta.name)→ 裸 id**;
- `_batch_detail` 加 `endpoint_display_name`(+ method/path):投影源用
  **`catalog_versions.spec_json`** 而非 plate `/full` —— 批次开立时刻的
  形状,审计正确,且是 DB 投影;op 级"这一步打哪个接口" =
  `(scenario_id, step_index)` 批量 IN `scenario_endpoint_refs` →
  endpoint_id → 同一投影;
- board 标签 bug 修复(E4):读路径改为 `definition_from_payload` 单点
  (或直接取生成列 `name`);顺带 `scen_rows` 可瘦身为只 SELECT
  `scenario_id + name`,不再为取名整行拉 payload。

### G2 选择器健壮化(前端为主)

- options 端点(`scenarios.py:392-484` `fields=options` 分支)支持 `q`
  下推(复用 `scenario_query._q_clause`),默认页大小不变;
- `Runner.vue` / `stores/scenario-composer.ts` / `OpConstructDialog.vue`
  的场景选择换可搜索下拉(q + 翻页);OpConstructDialog 内展示用途的
  标签改走 G1 响应字段。

**验收**:场景数 > 100 时,所有选择器仍可选到任意场景。

### G3 同表双口径归一 + 生成列(纯后端,可一个 revision)

- `_meta_from_row` 补 `createTime` 以 `row.created_at` 覆盖(照 updateTime
  范式;payload 原值不动,yaml 导出面不受影响 —— 见 §7 决策点 2);
- `definition.scenarioId` 顶层/meta 双键:先跑存量审计 SQL
  (`payload->'definition'->>'scenarioId' <> payload->'definition'->'meta'->>'scenarioId'`),
  有分歧则一次写回归一,读侧统一为 meta 优先(与 `_meta_from_row` 一致);
- `composer_data_sets.row_count` 改 STORED 生成列
  (`jsonb_array_length(rows)`,SQLite 变体 `json_array_length`),
  `data_set_store` 停写该列;alembic revision **可与另案的冗余索引清理
  合车**(见 §6);
- **写点共三处**(影响评估轮核实补全):`data_set_store.py:77`(create)、
  `data_set_store.py:110`(update)、**`scenario_store.py:253`
  (copy_scenario 直接构造行抄值——文档初版漏了这处)**,全部停写;
- **执行侧零依赖(已核实)**:`run_dispatcher.py:569-571` 的 total_runs
  刻意按实际行数算、注释明言防的就是 row_count 过期 —— dispatch 路径
  不消费该列,生成列化不触碰执行链,反而消灭该防御注释存在的原因;
- **ETL 工具适配点(仅一处)**:生成列 INSERT 排除是通用逻辑
  (metadata 驱动,`migrate_sqlite_to_pg.py:13` "排除全部 Computed 列"),
  row_count 自动进排除集;`generated_columns_sampled` 抽样清单建议随加;
- **量级注意**:PG 的 `ALTER TABLE … ADD COLUMN … GENERATED` 是全表重写
  —— 当前 2 行秒级无感;未来 GB 级环境套用时走低峰窗口(与迁移手册
  同款纪律);
- `meta.owner` / `owner_name` 列:维持现状(写侧已同步),owner_name 列
  的索引按另案索引清理处置。

**验收**:创建/编辑场景后 API 返回的 createTime/updateTime 均为 DB 权威;
数据集 row_count 恒等于 rows 长度(手工改 rows 也一致);双方言测试绿。

### G4 聚合下推(小)

- `_latest_terminals`:PG 分支改
  `SELECT DISTINCT ON (scenario_id) … WHERE status IN (终态) ORDER BY
  scenario_id, created_at DESC, id DESC`(吃 `ix_executions_scenario_id`);
  SQLite 分支保留现折叠;
- `stores/executions.ts` `fetchList` 支持 `scenarioId` 参数透传,
  `ScenariosMine.vue` 展开行改传 `scenario_id` + 小页,不再全量拉。

**验收**:board 热力网格结果与现实现逐场景一致;方案展开的网络请求只取
该场景执行。

### G5 权限数据侧体现(按需,建议轻档起步)

现状:隔离规则(admin 全量 / public 众人 / private 属主)只活在应用层三份
实现(`scenario_query._visibility_clause`、`_ownership.can_read_scenario`、
`_ownership.ensure_owner`);数据侧只有自由字符串 `visibility` + `owner_id`,
DB 既不表达也不强制策略,直连 psql 可见一切。

- **轻档(推荐起步)**:建 security_invoker 视图,策略首次落进 DB 目录:

  ```sql
  CREATE VIEW v_scenarios_readable WITH (security_invoker = true) AS
  SELECT * FROM composer_scenarios
  WHERE visibility = 'public'
     OR owner_id = NULLIF(current_setting('app.uid', true), '')::int
     OR current_setting('app.role', true) = 'admin';
  ```

  应用侧不动(仍走 ORM 基表 + 应用谓词);视图服务于直连 DB 的人/报表,
  使用前 `SET app.uid / app.role`。
- **重档(RLS)**:真强制,但 gimbal 是表 owner 需 FORCE 且 alembic/ETL 连接
  要专门处理;RLS 为 PG 独有,SQLite 无对应 → **双方言纪律被打破**,应用
  谓词仍须保留,形成双轨。**建议 defer**,等出现真实第二消费方(BI/直连
  分析)或合规要求再上,且只作纵深防御。
- **不做**:visibility/role 加 CHECK —— role CHECK 已被权限方案 §8 以
  "预留值空间"为由否决,visibility 无额外收益。

### G6 carry 面端点上下文(二轮补充,E3)

**语义修正先行**:carry 绑定行是 **service 级**(`service_name +
field_path`),field_path 不携带 endpoint 身份,逐行 join 键不存在 ——
正确的展示语义是"**该服务下声明了此字段的端点集合**"(一个字段可能被
服务内多个端点声明,绑定本身就是覆盖它们的单行)。

**实现**(零 DB 改动):face 折叠循环(`routers/carry.py:127-151`)本来就
逐端点迭代 `/full` 后按 path 归并 —— 归并时顺手收集贡献端点即可,
`CarryFieldFace` 加 `endpoints: [{id, name, method, path}]`(轻量投影);
前端配置页字段行按端点 chip 展示上下文。plate 不可达时 face 降级为空,
`endpoints` 同降级,不新增故障面。

**验收**:配置页任一绑定字段可看到它来自服务内哪个(哪些)接口;
`degraded` 行为不变。

**注**:catalog_versions 也能做同一反查(DB 侧),但 face 循环手里已有
逐端点数据,改那里成本最低;catalog_versions 路径留作 plate 长期不可达
时的兜底,不在本期。

---

## 5. 明确不做(边界重申)

- **应用层镜像列 / 双写 / 可写派生列**:终审否决,不重开。
- **子表 FK 从 `scenario_id String` 改指 int 主键**:稳定外部身份是刻意
  选择(rerun/导出/执行软引用都靠它),收益是索引字节,代价是全链改动。
- **executions 硬隔离语义**(连 admin 也只见自己,§5.1"聚合不得突破
  个体"):是拍板过的设计,本方案不改;G1 的 display join 同样只在
  owner 过滤后的当页行上做,不扩大可见面。

---

## 6. 关联工作(另案,不阻塞本方案)

上一轮表设计复盘的结论与本方案共享 alembic 车辆,但属独立决策:

| 另案项 | 与本方案的关系 |
|---|---|
| 冗余索引清理 5 项(execution_rows / notifications / composer_scenarios.visibility / carry / run_schemes 的前缀冗余单列索引) | 可与 G3 的 row_count 生成列合成一个 revision |
| `ix_executions_owner_id` 升级为 `(owner_id, id DESC)` | G1/G4 的查询同受益,同车 |
| 生命周期 GC(execution_snapshots 保留期、notifications 清理、adaptation_snapshots prune) | 独立 PR,需先拍保留期数字 |
| `_persist_row_terminal` 每行一会话(远端 RTT 放大) | 独立热路径优化,与读侧无关 |

---

## 7. 决策点清单(已按文档推荐缺省实施,2026-09-22)

1. **G1 范围**:rows 明细的 `dataset_name` 是否首期就做(涉及已删数据集
   的回落语义),还是首期只做场景名、数据集名二期?
2. **createTime 读时覆盖**:API 展示面改为 DB 权威(payload 原值保留,
   yaml 导出不受影响)—— 是否接受?若前端有依赖 createTime 往返的用例
   需同步改测试。
3. **row_count 生成列化**:是否与冗余索引清理合一个 revision(合车省一次
   发布,分车回滚面更小)?
4. **G5 轻档视图**:是否本期建 `v_scenarios_readable`(零应用影响,但多
   一个要随 schema 演进维护的目录对象)?RLS 确认 defer?
5. **顺序**:建议 G3+G4(纯后端小改)→ G1 → G2,G5/G6 并行按需;是否认可?
6. **A7(别名→目录名)**:量小,是否归入 G2 顺带或不做?
7. **board 标签 bug(E4)**:一行级读路径错误、生产在跑 —— 建议**不等本
   方案整体评审,立即单独修复**(挂 G1 或先行热修);是否认可?
8. **E5(grid lastRun 带场景身份)**:产品决策 —— 热力格是否需要展示
   "最近执行的是哪个场景"(实现轻:`best` 选中时带 display name)?
9. **二轮扩展范围确认**:E1/E2 并入 G1、E3 立项 G6、run_scheme 不动 ——
   已按此归并实施。

**实施拍板缺省**(用户「基于文档进行」授权,按文档推荐执行):
① dataset_name 首期做(已做);② createTime 读时覆盖(已做,导出面不动,
`test_draft_to_full_passes_definition_through` 边界测试仍绿);③ row_count
生成列与索引清理/G5 视图合一个 0005 revision(已做);④ G5 轻档视图建
(已做),RLS defer;⑤ 顺序 G3+G4 → G1 → G2 → G6(已走);⑥ A7 不做;
⑦ board bug 先行热修(已做,首 commit);⑧ E5 挂起待产品;G4 的 D2 前端
部分经核实为误报(见 §1.D 勘误),仅做后端下推。

---

## 8. 实施与验收纪律

- 所有读侧投影新增响应字段为**新增键**,不改既有键语义(前端旧版本兼容);
- 批量 IN 预取每页一次,禁止逐行查(N+1 红线,`dataset_counts` 先例);
- PG 分支改动必须带 SQLite 兜底分支的等值测试(方言分派先例:
  `scenario_query` vs `scenario_store.list_rows`);
- 生成列变更走 alembic revision + models 同步,ETL 工具面(生成列排除
  INSERT、`generated_columns_match` 抽样)随列清单更新;
- 本方案全部改动**零表结构变更**(G3 的 row_count 除外,且是生成列方向的
  既有定稿延伸),`pg-cutover` 后回滚窗口不受影响。

---

## 9. 整体影响与组件影响评估(三轮)

### 9.1 总评

**影响面小、方向增量、可逆。** 六个工作包里只有 G3 的 row_count 生成列
触碰 schema(单表单列);其余全部是读侧投影、前端消费、聚合下推 —— 不改
表、不改写路径、不迁移数据。风险集中在测试面与两处用户可见的行为变化
(q 检索扩口径、board 标签修正),均属预期修正而非回归。

### 9.2 分维度影响

| 维度 | 影响 |
|---|---|
| 数据/Schema | 仅 row_count 生成列(+ 另案可选的索引清理/G5 视图);alembic 链 +1 revision,双方言变体可行(PG `jsonb_array_length` / SQLite `json_array_length`,SQLite ≥3.31 支持生成列,本地环境满足);现网升级 = `upgrade head` 或重启后端(启动 ensure_schema 自动跑) |
| 写路径 | row_count 三处写点停写(§4 G3 已列);其余包零写路径变更 |
| 读路径/API | 全部**新增响应键**,向后兼容(旧前端忽略新键);行为变化仅两处:q 扩口径(命中集变大)、board 标签从裸 sid 变真名(bug 修复) |
| 性能 | 中性偏正:每页 +1 次批量 IN(远端 PG 一个 RTT,≤200 id);q 子查询吃 trgm;`DISTINCT ON` 替代 Python 折叠;生成列消灭双写;索引清理减写放大。N+1 红线全程(§8) |
| 安全/权限 | G1 活名 join 套可见性谓词(§4 G1 已补,防"执行过的场景转让后泄露当前名");快照名属执行者自己的记录,照常显示;executions 硬隔离语义不动(§5) |
| 测试基线 | 后端 611 / 前端 1037 中,受影响的是断言响应形状 / q 口径 / board 标签 / createTime 往返 / rowCount 写路径的用例 —— 机械性更新,估数十处;新增用例见 §8 |
| 回滚 | 代码级回退即回滚;G3 带 downgrade(删生成列、恢复普通列并回填 `len(rows)`);SQLite 应急回滚路径不受影响(新代码对旧 SQLite 库的启动自适应会把 revision 以 SQLite 变体打上) |

### 9.3 对其他组件的影响

| 组件 | 影响 | 依据 |
|---|---|---|
| **gimbal CLI / 执行器**(gimbal_launcher 子进程) | **零** | 执行器从不读平台库 —— 输入是 run_materialize 产出的临时 yaml;本方案不改任何执行侧契约;row_count 生成列经核实 dispatch 不消费(`run_dispatcher.py:569`) |
| **gimbal-plate**(:8765) | **零** | 不改 plate API;G6 读同样的 `/full`(调用次数不变);G1-E2 刻意选 `catalog_versions`(DB)而非新增 plate 依赖;plate 仍是契约形状权威 |
| **前端** | G1/G2/G6 消费端同车更新 | 兼容方向是"后端先、前端随"(新键旧前端无感);本机同仓部署无实际顺序约束 |
| **ETL / preccheck 工具** | 一处适配 | 生成列 INSERT 排除为通用逻辑(`migrate_sqlite_to_pg.py:13`),row_count 自动进排除集;`generated_columns_sampled` 清单随加 |
| **alembic / 双方言** | +1 revision | 方言分派先例齐备(0003 PG-only no-op;0005 生成列双方言变体 + PG-only 索引清理/视图段) |
| **远端 PG 运维** | 秒级 | 当前 2 行数据的表重写;未来大库套用时 `ADD COLUMN GENERATED` 是全表重写,走低峰(已写进 G3) |
| **部署拓扑 / 回滚预案** | 不变 | 本地后端 + 远端库拓扑无变化;72h SQLite 回滚窗口与后续操作均不受影响 |

**一句话结论**:这不是一次结构改造 —— 唯一的结构面改动(row_count 生成列)
是既有"生成列定稿"方向的自然延伸,且经核实无任何外围消费者依赖旧行为;
对 gimbal 执行器与 plate 两个外部组件零影响,ETL 工具一处清单适配,其余
全部是平台自身的读侧现代化。

