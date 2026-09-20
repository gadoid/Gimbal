# Platform 实现检查报告 — 架构 / 数据结构 / PostgreSQL 迁移就绪度

> 2026-09-21 · 树状态:`0aa695f` + 执行设计重构(批次键/预检/summary/rerun + 前端四页)之后。
> 方法:16 张模型逐表读、core 层全文读、run_dispatcher 关键路径(dispatch/计数器/终态/恢复)读、
> 其余服务定向核查(删除级联/状态转移/锁/缓存)、开发库实测孤儿行扫描、
> 执行域功能与《执行 — 设计与改造方案》§6/§7 逐条比对。

---

## 1. 总体结论

**架构与数据结构整体是干净的,可以支撑 PostgreSQL 迁移,但不是"零改动直迁"。**
分层(routers→services→models)、单一实现源纪律(失效判定/属主判定/时钟/状态投影各一处)、
派生层可重建(endpoint_refs / catalog_versions)、原子计数器、JSON 整档读改写——这些都是
对的关系建模方式,且已出现 PG 意识(双方言 partial unique index)。

**迁移前必须处理的硬项 2 个**(时区双轨、FK 强制差异),**过程项 3 个**(无迁移工具、
无 PG 驱动、测试仅 SQLite),**部署约束 1 个**(单进程假设)。现存数据实测**零孤儿行**,
PG 导入不会被 FK 校验卡住。

---

## 2. 架构评估

### 2.1 分层与依赖方向(✓ 干净)

```
routers/(HTTP 契约:参数校验、权限、错误映射)
   ├─ _ownership / _error_mapping / _name_checks / _codes(共享助手,无状态)
   └─ services/(领域逻辑;每个聚合一个 store)
        └─ models/(SQLAlchemy 2.0 typed ORM)
core/(db 引擎与session / config / security / deps / timeutil)
```

- 依赖方向单向:router→service→model;两处刻意的晚导入(`core/deps.py:60` 防 model 环、
  `run_dispatcher.py:1557` 尾部收 store)都有注释说明理由。
- 路由注册顺序纪律成文(`main.py:121-150`):静态后缀先于 `/{id}` 兜底,
  `executions/summary` 先于 `/{execution_id}` 有测试钉住(test_execution_refactor)。
- **单一实现源**执行得好,这是全库最值钱的性质:
  - 失效判定 = `filter_injection_entries`(dispatch 与 `/run/precheck` 共用,run_dispatcher.py:1213);
  - 属主判定 = `_ownership.ensure_owner` + `can_read_scenario`(全 composer 路由共用);
  - 执行读侧投影 = `execution_store.execution_out`;
  - 时钟 = `core/timeutil.utcnow`(naive-UTC 单点);
  - 表头配色/状态色这类前端事务在后端对应:状态字符串常量集中在 `models/execution.py`。

### 2.2 横切纪律(✓)

- 错误契约统一 `{"code","message"}`;404/403 合并防属主探测(`core/deps.py:69`,刻意);
- 优雅关闭三段式:拒新单(`is_shutting_down`)→ 启动期僵尸收敛(`startup_recovery`)→
  排空在途(`drain_in_flight_dispatches`)(main.py lifespan);
- 资源闸成体系:总量 200(`too_many_runs` 409)、并发子进程 8(Semaphore 按事件循环缓存)、
  plate 熔断器(连续 3 次失败短路剩余行);
- 计数器丢失自愈:双败后 JSONL 记账(`counter_bump_failed`),终态校账只标记不修正
  (`counterDrift`,真值以 JSONL 为准)——诚实的数据纪律。

### 2.3 架构级约束(需成文,见 P4)

**单进程、单机假设**藏在三处:
1. `run_dispatcher` 的进程内注册表:`_tasks_by_execution`(cancel 寻址)、`_row_states`
   (活跃行状态,终态前盖住 JSONL 回放)、cancel 标志;
2. 行级真相在本地文件:`data/runs/*.jsonl`(回放)、`data/runs/cases/*`(工件);
3. `marks_store`(`stars.json`)与声明面 LRU 缓存为进程内/进程旁状态。

SQLite 天然单写者,这些假设从未被挑战;**PG 本身不破坏它们**(可以继续单进程),
但 PG 通常伴随多 uvicorn worker / 多实例的诱惑——那时 cancel 语义与行状态会静默失效。
**建议:把"单进程部署"写进部署文档作为硬约束;将来需要横向扩展时,先把 _row_states 与
cancel 寻址挪进 DB/Redis,再谈第二实例。**

---

## 3. 数据结构逐表清单(16 表 + 2 文件岛)

| 表 | 主键 | 关键列与约束 | JSON 列 | 评价 |
|---|---|---|---|---|
| users | id int | username unique;display_name 双向查重(`_name_checks`) | — | ✓ 干净 |
| auth_sessions | id | (owner_id,alias) unique;owner FK CASCADE;凭证 Fernet 加密落库 | — | ✓ |
| constant_entries | id | (owner_id,name) unique;owner FK CASCADE;literal/generator 互斥由路由保证 | value,spec | ✓ |
| executions | id | scenario_id 索引**无 FK(刻意:台账保留已删场景,实测 3 行)**;owner FK CASCADE;batch_id 索引;计数器整数列 | config_json,scenario_snapshot | ✓;快照列会整行加载(注释已声明量级取舍) |
| composer_scenarios | id | scenario_id unique(字符串业务键);**owner_id int default=0 无 FK**;visibility 索引 | payload(整档) | △ 见 P6 |
| composer_data_sets | id | dataset_id unique;scenario_id FK CASCADE;row_count 冗余列 | rows,var_unlocks | ✓ 派生计数列有注释 |
| composer_run_schemes | id | scheme_id unique;(scenario_id,name) unique;**默认方案唯一 = 双方言 partial unique index** | payload | ✓ PG 意识最好的一张表 |
| scenario_endpoint_refs | (scenario_id,step_index,source,field_name) 复合 PK | endpoint_id 索引;无 FK | — | ✓ 派生层,可 drop 重建(注释成文) |
| catalog_versions | endpoint_id | version;synced_at | spec_json | ✓ 派生缓存 |
| adaptation_batches | batch_id str | status 枚举;**operator_id int 无 FK** | — | △ 软引用(见 P6) |
| adaptation_ops | id | batch_id 索引**无 FK**;scenario_id/dataset_id 可空(软引用);status 枚举 | payload | △ 同上 |
| adaptation_snapshots | id | batch_id 索引无 FK;before_json 整像 | before_json | ✓ 回滚安全网 |
| carry_service_bindings | id | (service_name,field_path) unique;**value NULL = 显式注入 null,行不存在 = 未配置**(语义写死在模型头注释) | — | ✓ 精确 |
| carry_global_defaults | id | field_path unique | — | ✓ |
| board_cards | id | root 唯一 = 双方言 partial unique index;author FK CASCADE | — | ✓ |
| service_aliases | alias_name str PK | base_service 索引;owner_user_id FK **SET NULL** | — | ✓ 注销共享化的承接列 |
| ★ stars.json | — | {user_id: set[scenario_id]},原子写 + 进程内锁 | — | △ DB 外数据岛(P5) |
| ★ data/runs/*.jsonl + cases/ | — | 行级真相 + 工件,14 天保留清扫 | — | 设计如此(行级不落库);PG 迁移不涉及 |

**建模风格总评**:关系维度(属主/唯一性/可见性)上列、文档(payload)进 JSON 的
"PG-friendly relational modelling"(run_scheme 模型头注释原话)贯穿始终;
JSON 列全部是**整档读改写**,从不从 SQL 查进 JSON 内部——这在两个库上都成立。
唯一建议:PG 侧用 JSONB(无查询损失、无理由不用 TEXT-JSON)。

---

## 4. PostgreSQL 迁移就绪度

### 4.1 会直接出问题的项(迁移前必须处理)

**P1 [高] FK 约束在 SQLite 运行时从未被强制。**
`core/db.py` 没有 `PRAGMA foreign_keys=ON` 的 connect 钩子(aiosqlite 每连接默认关)。
后果分两层:
- **行为分叉**:`users.py:285` 删用户只 `db.delete(target)`,依赖 DB 级 CASCADE 清理
  auth_sessions / constant_entries / board_cards / executions、SET NULL service_aliases——
  这些在当前 SQLite **一个都不会发生**(孤儿留在库里,只是 owner 隔离让人看不见);
  换 PG 后**全部真的发生**(执行记录随用户消失)。
- **迁移阻塞面**:若库里已有孤儿,PG 导入 INSERT 时即被 FK 拒绝。
  **本次实测开发库:全部 9 类孤儿扫描均为 0**——现存数据能过,但结构上没有东西阻止未来产生。
- 建议:① `core/db.py` 加 `event.listens_for(engine.sync_engine,"connect")` 对 SQLite 开
  PRAGMA,让两个库行为一致(立即收窄分叉);② 或把用户删除改为显式级联
  (scenario_store.delete 的做法:`scenarios.py` 删除已是显式级联,不依赖 CASCADE)。
  迁移脚本里保留孤儿体检步骤(本次的扫描 SQL 可直接复用)。

**P2 [高] 时区双轨。** Python 侧全部走 `timeutil.utcnow()`(naive-UTC,约定单点),
但 16 张表的 `server_default=func.now()` 在两边语义不同:SQLite `CURRENT_TIMESTAMP` = UTC
(与约定一致);PG `now()` 落 `TIMESTAMP WITHOUT TIME ZONE` 时**按会话 TimeZone 渲染**——
服务器 TZ ≠ UTC 时,server_default 写出的行与 Python 写出的行会出现两种"零点"。
建议:统一升 `DateTime(timezone=True)` + aware utcnow,或
`server_default=text("(now() at time zone 'utc')")`;迁移时对历史时间戳做一次归一校验。
(现状无恙只因 SQLite 的 CURRENT_TIMESTAMP 恰好也是 UTC——这是巧合不是设计。)

### 4.2 过程项(迁移工程需要但仓库没有)

**P3 [中] 无迁移工具、无 PG 驱动。** `create_all` 只建缺表不改列(仓库惯例,执行设计 §3.5
已注明"改模型声明 + 手工处理既有库")——SQLite 时代靠自律 + 手工 ALTER(本轮
`batch_id`、`var_unlocks` 两列就是这么补的);PG 迁移需要:**Alembic**(从此有可回放的
变更历史)+ 一次性搬迁脚本(含孤儿体检、时区归一、JSON→JSONB)+ `asyncpg` 进依赖
(requirements 目前只有 aiosqlite)。

**P12 [低] 测试仅覆盖 SQLite**(conftest 每测试换临时 SQLite 文件库)。PG 行为差异
(时区、FK、并发、NULL 排序)无 CI 防线。建议迁移前加一个可选的 PG profile 跑同一套 630 测。

### 4.3 部署与并发语义(迁移后才会暴露)

**P4 [中] 单进程假设**(见 §2.3)。PG 不强制多进程,但要把约束写死,防止"上了 PG 顺手
`--workers 4`"把 cancel/行状态弄坏。

**P7 [低] 全库无 `with_for_update`/乐观锁。** 适配 op 确认(`adaptation_service.py:553-582`
读-验-写)、批次状态推进、场景 payload 整档 PUT 都是 RMW。SQLite 单写者掩盖了竞态;
PG 下两个管理员并发确认同一 op 存在小窗口双写。业务上可容忍(幂等性尚可、内部平台),
但建议在关键状态转移改条件 UPDATE(`WHERE status='pending'`)——一行改动级别。

### 4.4 迁移检查清单(建议顺序)

1. 修 P1(开 PRAGMA 或显式级联)→ 两库行为一致化;
2. 修 P2(时区列型统一)→ 历史数据归一;
3. 引入 Alembic,把当前 16 表声明作为 baseline;
4. 搬迁脚本:孤儿体检(0 预期)→ 导出 → JSONB → 导入 → 校验和(行数 + 计数器抽查);
5. `asyncpg` + `DATABASE_URL` 切换,跑 630 测试(PG profile);
6. 部署文档写死单进程约束(P4);stars.json 决定去留(P5)。

---

## 5. 功能 vs 需求一致性比对(执行域,对照执行设计 §6/§7)

| 方案条目 | 实现 | 一致性 |
|---|---|---|
| E1 `list_executions` 加 status/时间筛选 | `routers/executions.py`(status 422 校验、created_from/to、batch_id) | ✓ 有测试 |
| E1 `GET /executions/summary`(路由须在 /{id} 前) | ✓ 声明在前;路由序测试钉住 | ✓ |
| E1 `POST /executions/{id}/rerun` 按 config_json 重建 | ✓ 不带原批(独立发起);404/409 语义齐 | ✓ |
| E1 组件收敛(RunPanelHost 退役/run-bindings 单源/useRunAssembly) | ✓ 上轮交付,前端 1067 测试全绿 | ✓ |
| E1末 `Execution` 批次键 | 列 + config 双落;列表筛 + 前端归并视图 | ✓ |
| `/run` 执行器页(队列 = 前端逐条 + batchId) | ✓;预检文字行无状态 pill;批策略为虚线说明 | ✓ 与 §1.4 纪律一致 |
| `POST /run/precheck`(复用 preview-plate 链) | 实现 = `scheme_store` + `filter_injection_entries` + `_referenced_services` | ○ 见下方注 |
| 信号列:连续失败/认证快速失败;漂移依赖前置①不出现 | ✓ streak 服务端扫描(`_STREAK_SCAN_LIMIT=1000`);authFailFast dispatch 写入;漂移未实现(正确——不发明) | ✓ |
| 展开行三件套/刻意不放行级表 | ✓ 注入快照 + 下一步入口;来源分析置灰带理由 | ✓ |
| 工件白名单(case.json 不暴露) | ✓ 不变 | ✓ |
| §5 owner 硬隔离(执行维度无 admin 分支) | `executions.py:73/98/156` 全部 `owner_id == user.id` | ✓ 与方案"刻意更严"的口径一致 |
| E2a 字段来源分析·预测 | 未做,侧边栏置灰 span | ✓ 与分期一致(E2a 下一期) |
| E2b/E3/数据分析延后 | 置灰入口 + /analytics 说明页 | ✓ |

**唯一口径注记**:precheck 的失效判定复用的是 **dispatch 自己的那份实现**
(`filter_injection_entries`,即"与 dispatch 同一条判定链"),而非方案字面写的
"preview-plate 那条链"。方案的真实意图是"别开第二份失效口径"(§1.6 原文),
dispatch 链与 preview-plate 共享 `filter_injection_entries` 的底层扫描,故语义等价、
意图达成;差异仅在于 precheck 少跑了 materialize(那是执行语义,不是判定语义)。
**结论:可接受,建议在方案文档把措辞从"复用 preview-plate 链"修为
"复用 dispatch 的失效判定单源"以免后人再对一遍。**

其余域(用户/场景/数据集/方案/适配/carry/画像)抽样比对未发现实现与需求打架;
`display_name 兼作归属身份`(users.py 注释)是刻意的防冒用设计,但造成身份三重表示
(username / display_name / scenarios.owner 快照字符串),改名后 owner 快照会陈旧
(仅展示用,归属权威是 owner_id)——现状无害,记为观察项 O1。

---

## 6. 问题登记表

| # | 级别 | 位置 | 问题 | 建议 |
|---|---|---|---|---|
| P1 | 高 | `core/db.py`(缺)、`users.py:285` | SQLite 未开 FK 强制;声明 CASCADE/SET NULL 运行时不生效;删用户留孤儿;PG 后行为翻转 | 加 PRAGMA connect 钩子或显式级联;迁移前孤儿体检 |
| P2 | 高 | 全部模型 `DateTime` + `server_default=func.now()` | 时区双轨:PG 会话时区≠UTC 时 server_default 与 utcnow() 混两种零点 | `DateTime(timezone=True)` 统一或 `now() at time zone 'utc'` |
| P3 | 中 | 仓库级 | 无 Alembic、无 asyncpg;create_all 不改列 | 迁移工程引入;baseline=现行 16 表 |
| P4 | 中 | `run_dispatcher`(进程内注册表)、JSONL/case 本地文件 | 单进程单机假设未成文;多 worker 会坏 cancel/行状态 | 部署文档写死;扩展前先外置状态 |
| P5 | 中 | `services/marks_store.py:122` | stars.json 是 DB 外数据岛;进程锁不跨进程;PG 迁移不带它 | 随迁移落表 `user_stars(user_id,item_id)` |
| P6 | 中 | `composer_scenario.py:25`、`adaptation_batch.py:20`、`adaptation_op.py:19` | owner_id/operator_id/batch_id 软引用无 FK,与 executions 等的 FK 风格不一致 | 收敛为 FK(先洗 0 值行)或注释写明豁免理由 |
| P7 | 低 | `adaptation_service.py:553-582` 等 | 状态转移 RMW 无锁;PG 并发小窗口双写 | 条件 UPDATE(WHERE status=…) |
| P8 | 低 | `users.py:72`(list_users) | 任意登录用户可枚举全部用户(前端隐藏入口、后端敞开,注释声明 spec-1 如此) | 按平台定位确认是否收紧 |
| P9 | 低 | `auth.py:70-72` | 首注册用户 count-then-insert 竞态,并发注册可出双管理员 | 唯一索引守门(admin 标志列部分唯一)或迁移锁 |
| P10 | 低 | 全部 JSON 列 | PG 侧将落 TEXT-JSON 而非 JSONB | 迁移时转 JSONB |
| P11 | 信息 | `execution.scenario_id` | 无 FK,3 行指向已删场景——**这是台账保留的刻意设计,迁移别"顺手"补 FK** | 保持豁免并成文 |
| P12 | 低 | `tests/conftest.py` | 测试仅 SQLite,PG 差异无防线 | 加可选 PG profile |
| O1 | 观察 | `users.py` / `composer_scenarios.owner` | 身份三重表示(username/display_name/owner 快照);改名后快照陈旧(仅展示) | 维持现状,归属权威始终是 owner_id |

---

## 7. 模块功能文档

> 只列职责/入口/数据/纪律;问题以 P# 交叉引用。前端模块从略(本轮另有交付记录)。

### 7.1 core/(基础设施)

| 文件 | 职责 |
|---|---|
| `db.py` | async 引擎 + session 工厂 + `init_db`(create_all,幂等;schema 变更走库外重建,历史数据带外迁移——仓库惯例,P3)。**缺 FK PRAGMA(P1)** |
| `config.py` | pydantic-settings 单例:JWT/Fernet(缺省时临时生成并打启动警告)、DATABASE_URL(锚定 backend/ 防误启动失忆)、DATA_DIR、case 保留 14 天、执行闸(总量 200/并发 8)、plate 端点与三段超时语义(30s 硬限 / 3s 软取 / 300s TTL + 3600s stale 窗,注释极详尽) |
| `security.py` | bcrypt 口令、JWT(access/refresh,jti 防同秒重复)、Fernet 对称加密(凭证落库加密) |
| `deps.py` | CurrentUser(token→用户,失活即 401)、AdminUser、OwnedExecution(404/403 合并防探测) |
| `timeutil.py` | `utcnow()`:naive-UTC 单点约定(P2 的另一半在模型侧) |

### 7.2 认证与用户

- `routers/auth.py`:login/refresh/register(首用户自动 admin——P9 竞态)/me。register 与 users 共用 `_name_checks`(username/display_name 双向查重,防冒名接管)。
- `routers/users.py`:list(**无 admin 门**,P8)/create(恒 member)/patch(成员仅自改且禁触 is_admin;末管理员保护)/reset-password(管理员或本人,明文仅返回一次)/delete(管理员、禁自删、末管理员保护;**级联依赖 DB,P1**)。

### 7.3 场景域

- `routers/scenarios.py`:CRUD、复制(`-copy-<6hex>` 新 id)、可见性翻转、preview-plate(装配 + carry 注入干跑,field-trace E2a 的落点)、快照读面。list:admin 全量 / member public+own(`can_read_scenario`)。
- `services/scenario_store.py`:payload 整档读写(源存果算——列镜像已退役,列表侧过滤在 Python);**delete 显式级联**(endpoint refs→datasets→schemes→行,单事务)+ stars 清理,不依赖 DB CASCADE(P1 的正面样板);copy 深拷贝;`owned_scenario_ids` 供跨域判定。
- `services/endpoint_ref_index.py`:场景→接口/字段倒排索引,场景写路径同事务维护、可 drop 重建(派生层纪律)。

### 7.4 数据集 / 方案

- `routers/data_sets.py` + `services/data_set_store.py`:场景 1:N 数据集(rows JSON 矩阵 + row_count 冗余 + var_unlocks 变量锁放开清单);owner 经 scenario 归属判定。
- `routers/run_schemes.py` + `services/scheme_store.py`:每场景方案表(默认恰一个——双方言 partial unique);`rs-` 前缀 id 区分自建;删除/重建保持默认位。方案是"一次执行的完整准备"(数据集行 + 注入条目 + 绑定 + 参数)。

### 7.5 执行发起域

- `routers/runs.py`:POST /runs 薄壳——属主闸(执行有真实副作用)→ dispatch_run;404/409 映射;plate 中途故障也是 201+runId(可观测性优先)。
- `services/run_dispatcher.py`(1591 行,核心):校验(步骤越界/行号越界/总量闸)→ 行级选择合并(dataSetSelection 超集语义)→ 注入条目过滤(`filter_injection_entries` 单源)→ 建行(batch_id/scenario_snapshot/config_json 同拍)→ 后台 fanout(交叉矩阵 行×条目×nRuns;per-execution 并发 Semaphore;launch 全局闸 8)→ 计数器**原子增量**(P8 无关,已是 delta UPDATE)→ 终态校账(counterDrift 只标记)。优雅关闭/僵尸收敛/协作取消/plate 熔断齐备。**进程内注册表(P4)**。
- `services/gimbal_launcher.py`:argv 组装(`gimbal run launch <case> -o json`)+ 同步子进程;`_base_argv` 测试缝。
- `services/plate_client.py`:plate 服务客户端(转换/目录代理),三段超时与 stale-while-error 缓存(config 注释为权威说明)。

### 7.6 执行读侧 / 预检

- `routers/executions.py`:list(status/batch/时间窗筛,owner 硬隔离无 admin 分支——方案 §5.3 刻意)/summary(KPI,声明序钉死)/rerun(config_json 重建,不带旧批)/rows(活跃读 registry、历史 JSONL 回放)/case-artifact(白名单 engine.log/result.json,**case.json 刻意不暴露**)/scenario-snapshot/cancel/delete。
- `services/execution_store.py`:`execution_out` 唯一投影;`consecutive_failure_streaks`(1000 行轻扫,窗内链长);delete 连带清 case 目录。
- `routers/run_precheck.py`:POST /run/precheck——{scenarioId,schemeId} 对(≤20 条)→ found/schemeValid/deadDatasetIds/danglingEntryIds/unboundServices;判定与 dispatch 同源(§5 注记)。

### 7.7 凭证池(auth_sessions 域)

- `routers/auth_sessions.py`:owner 隔离的凭证 CRUD;探测(probe)、引用扫描(auth_ref_scan/auth_references:别名被哪些场景引用——删除凭证的防误伤面)。存储 Fernet 加密;执行时 `run_dispatcher._resolve_exec_auths` 按执行者本人解析注入。

### 7.8 常量池

- `routers/constants.py`:owner 隔离;literal/generator 互斥且创建后不可变;**平台只存配置不求值**,引擎 preprocess 是唯一求值点(纪律成文)。

### 7.9 carry 值层

- `models/carry_binding.py`:两层表(服务绑定/全局默认);**value=NULL=显式 null,行不存在=未配置**——读侧降级链的根基。
- `services/carry_store.py` / `carry_injection.py`:层级合并(精确别名键>base 服务键>全局默认);`build_carry_context` 供 preview/dispatch 共用。
- `services/run_materialize.py` / `run_injection.py`:物化链(body 已有键不覆盖 setdefault 语义、字段级合并、case.json 落盘)。

### 7.10 适配域

- `routers/adaptations.py`:目录 diff/批次 CRUD/逐 op 确认/回滚——**全部 AdminUser 门禁**(member 不可见,与执行域的 owner 硬隔离形成口径不对称,执行设计 §5.3 已定性为"刻意更严")。
- `services/adaptation_service.py`(1133 行):字段级 diff(catalog_versions 的 spec_json 为旧形状基准,冷启动落基线)、批次快照(before 整像)、apply/rollback 逐 op 状态机(pending/applied/conflict/skipped;**RMW 无锁,P7**)。
- `services/endpoint_declarations.py`:契约声明面(软取 + stale-while-error,config 注释权威)。

### 7.11 服务画像域(0aa695f)

- `routers/service_profile.py`:热力网格(服务→接口四格,含「无用例覆盖」——数据分析延后期的覆盖盲区承接面)/线索板读侧。
- `services/board_cards.py` + `board_cards` 表:自建卡,root 槽位双方言 partial unique;作者权限边界。
- `routers/service_aliases.py` + `services/service_aliases.py`:别名登记面(命名复用引擎 `derive_base`);credential_alias 引**执行者本人**凭证池;owner_user_id 非空=个人默认(FK SET NULL 承接注销)。

### 7.12 目录与查询视图

- `routers/endpoint_catalog.py` / `strategy_catalog.py` / `generator_catalog.py`:plate 目录代理与编排候选面。
- `routers/query_views.py` + `services/query_view_runner.py`:查询视图试跑(带缓存 `query_view_cache`,进程内,良性)。

### 7.13 横切工具

- `services/jsonpath.py`(810 行):纯函数 JSONPath/模板求值——无 IO 无状态,两库无关。
- `services/marks_store.py`:stars.json 原子写文件存储(P5)。

---

## 8. 结语

这棵树的"干净"不是运气:单一实现源、派生层可重建、整档 JSON、显式级联样板、
原子计数器、诚实的数据纪律(counterDrift 只标记不修正)都有注释成文的理由。
PG 迁移的真实工作量集中在 **P1/P2 两个语义一致化 + P3 迁移工程**,不在建模本身——
16 张表没有任何一张需要为 PG 重塑形状。
