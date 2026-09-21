# SQLite → PostgreSQL 迁移与后端化 — 设计方案

> 状态：设计稿（2026-09-20，第四轮修订后）。本文覆盖四件事，它们必须在同一次设计里定稿，因为互相咬合：① SQLite→PG 迁移与新表结构；② 检索从前端下移到后端；③ 随规模增长该后移的聚合/轮询/明细存储；④ 前端分页的统一规范化。权限域的新表（role/notifications/audit_logs/user_prefs/user_stars）随 M2（表定稿+切换）一并落库，语义见《用户权限与用户管理-设计方案》。

## 0. 目标与六条原则

1. **直切，不做双写双读期**。单部署内部平台，没有第二个消费方；双写只会带来一个月的对账痛苦。切换窗口 = 停服 → ETL → 起服（§3）。
2. **迁移即重构窗口**。借换库把结构债一次还清：场景元数据提升为真实列、执行快照拆表、明细行入库、收藏入库、时区统一、alembic 引入。这些改动在 SQLite 上也能做，但那样要经历两轮「无迁移机制的 schema 变更」（现状建表 = `create_all`，`core/db.py:30-36` 注释自认 schema 变更走重建库），不如一步到位。
3. **审计级数据 outlive 用户**。执行记录、审计日志的归属用 `SET NULL + 姓名快照`，不用 CASCADE（与权限方案 §4.3 互锁）。
4. **alembic 从此必经**。这是本方案对 `executions.batch_id` 手工补列事件（2026-09-21，commit 168a2cf3 无迁移脚本）的制度性回应：**baseline 就是第一个 revision**——它携带 §2 全部 DDL，空 PG 库 `alembic upgrade head` 从零建库（§3.3 切换的人工第一步），此后任何 schema 变更没有 alembic revision 不合入。第九轮修订：不存在「切换完成后 baseline stamp」这一步——stamp 与 revision-建库两种模式互斥，库既然由 revision 从零建起，第一个 revision 就是天然 baseline，事后再 stamp 只会把已执行的 revision 标错。
5. **PG 用量级恰当的特性**。检索用 `ILIKE` + 元数据列起步，`pg_trgm` 索引备选；不上 ES、不上 tsvector 全文检索（内部量级，§9）。JSON 一律 JSONB（可索引、去空白，且现有代码从不在 SQL 里查 JSON 内部，平移无方言风险）。
6. **payload 是唯一可写源；派生态可以物化，但必须由数据库或可重放的纯函数生成，不得由应用写入侧维护**。`endpoint_ref_index`、`catalog_versions` 这些既有派生态与本次的生成列投影（§2.2）同在这条原则之下——不为特例开口子，后来者也不能援引「场景列能双写，我这个也行」。当年的镜像列教训被完整保存在「不得由写入侧维护」这半句里。

## 1. 现状盘点：迁移要偿还的债

| # | 债 | 证据 |
|---|---|---|
| 1 | **FK 从未生效**：engine 无 `PRAGMA foreign_keys=ON`，CASCADE/SET NULL 全是纸面约定 | `core/db.py:16-27` |
| 2 | **无迁移机制**：`create_all` 只建新表不改旧表；历史靠重建库+带外搬数据 | `core/db.py:30-36`、`batch_id` 事件 |
| 3 | **场景列表全表加载**：每行连 `payload` 大 JSON 一起捞，`q` 搜索/筛选/排序全在 Python | `scenario_store.py:305-312, 518-528` |
| 4 | **执行列表整实体加载**：`config_json` + `scenario_snapshot`（KB~MB 级）整列进列表 | `execution.py:61-62` 自认 |
| 5 | **行级明细在文件系统**：`data/runs/*.jsonl` 无清理无限增长，回放逐文件逐行扫 | `run_dispatcher.py:256-290` |
| 6 | **收藏在库外**：`data/stars.json` 原子写文件 | `marks_store.py:122` |
| 7 | **前端三种检索模式并存**：纯客户端（场景库/Auths/Users/Runner）、纯服务端（ExecutionsList 筛选、CaseComposerCatalog）、混合（ExecutionsList 搜索） | 前端报告 §一/§七 |
| 8 | **分页只有场景库一份前端 slice 版**；ExecutionsList 固定 limit=200 无 offset 静默截断 + 3s 全量轮询；行级表/批次表/常量池/Auths 全裸奔 | 前端报告 §三 |
| 9 | **返回形状分裂**：executions `{items,total}`，其余全裸数组 | 前端报告 §四 |
| 10 | **无公共防抖、无 URL query 同步**（q/page 不写回地址栏，刷新即丢） | 前端报告 §五 |
| 11 | **plate 目录前端直连 `per_page=500` 写死**，超 500 端点静默丢，ServicesIndex/ServiceAdmin 树各自前端聚合 | `utils/catalog-services.ts:33-52` |
| 12 | **N+1 扇出三处**：ScenarioFollows 信号（每关注对象 2 请求）、useInterfaceChange（每 pending 端点一个 impact）、工作台时间线三源前端合流 | 前端报告 §六 |

## 2. 新表结构设计

### 2.1 横切决策（先于逐表）

- **时区：结构修法定案（全库 timestamptz），战术备选入案**。诊断已收窄（第五轮核实）：`adaptation_service.py:100-118` 的 `_parse_dt`/`_utcnow` 是**故意**剥掉 tzinfo 走 naive-UTC 的，适配模块内部自洽；真正的破口是 `catalog_versions.synced_at` 这类 `server_default=func.now()` 列——值由数据库生成、不经过 `_utcnow()`，SQLite 的 CURRENT_TIMESTAMP 恰为 UTC 所以今天没事，PG 的 `now()` 按会话时区渲染即偏 8 小时。两条路：**战术修法**一行 `server_default=text("(now() at time zone 'utc')")`，naive-UTC 契约原样保留、零代码改动（仓内审计 P2 亦取此解）；**结构修法**（本方案所选，借重构窗口）全库 TIMESTAMPTZ + Python 全链 aware——`updated > stamp.synced_at`（`adaptation_service.py:168`）这类 naive/aware 混比会当场 TypeError，失败从静默漏报变成显性崩溃是好事，但意味着 `_parse_dt`/`_utcnow` 必须同改。不管走哪条路都做的两件事：① `ALTER DATABASE gimbal SET timezone='UTC'` 钉死会话时区，任何漏网的 naive 列不再漂；② **元数据断言测试**——遍历 `Base.metadata` 全部列，断言没有不带 `timezone=True` 的 DateTime、没有裸 `server_default=func.now()`——它防的是以后新加的列，比一次性人工扫描值钱。
- **变长列放宽**：Fernet 密文（`username_enc/password_enc`）、URL、spec/payload 类 → `TEXT`（密文长度随密码长度变，`VARCHAR(512)` 在 PG 会真报错）；有业务语义上限的短键（username/alias/scenario_id/batch_id/role/type）保留 `VARCHAR(n)` 但逐个复核现网最长值（风险 4）。
- **FK 动作总原则（第五轮定；第七轮措辞修正：判据是「该不该管」，不是「能不能管」）：Python 该管的删除（有业务处置语义），FK 用 `NO ACTION`（配 `DEFERRABLE INITIALLY DEFERRED`）；Python 不该管的删除（纯机械随主行消失、无业务语义），FK 用 `CASCADE`**。初稿措辞「删得到/删不到」会被援引出错误结论——场景删除 Python 完全删得到收藏行，但收藏随场景机械消失、没有处置语义，正该 CASCADE（user_stars 即此例）。NO ACTION + DEFERRABLE 让 FK 从「第二套级联」变成**校验器**：Python 显式级联漏删某张子表，commit 当场报错回滚，而不是被 DB 悄悄补掉、漏洞永远发现不了——注释里写的权威关系变成约束强制的权威关系，这正是安全网该有的语义。按此对全部归属 FK 做映射：

| FK | 动作 | 依据 |
|---|---|---|
| scenario_endpoint_refs / composer_data_sets / composer_run_schemes → 场景 | NO ACTION DEFERRABLE | `scenario_store.delete` 已在 Python 管理整组子表 |
| user_prefs / notifications / user_stars / execution_snapshots / execution_rows → 属主 | CASCADE | 无 Python 属主，DB 该自己收；execution 子表是整删语义、无处置分支 |
| executions.owner_id → users | SET NULL + owner_name 快照 | 台账语义（§2.2 / 权限方案 §4.3） |
| composer_scenarios.owner_id → users | SET NULL + owner_name 快照 | 人走场景留（转公共库 / 转让） |
| auth_sessions / constant_entries → users | NO ACTION DEFERRABLE | 权限方案删除处置流程 Python 显式管；最小显式级联随 M2 切换同车（第九轮定，非 M2.5——M2 起 FK 真生效，不带它则 M2→M2.5 之间删号被三张 NO ACTION 表当场拦死）：凭证池（auth_sessions）/常量/个人别名显式删（个人别名保守默认=删除，转共享留 P2 处置对话框），收藏由 user_stars CASCADE 自收，处置 UI 照旧 P2——FK 从第一天就是校验器，不留「先 CASCADE 以后再改」的窗口 |
| service_aliases.owner_user_id → users | NO ACTION DEFERRABLE（**第八轮改记：这是对模型既定意图的显式推翻，不是「避开陷阱」**——`models/service_alias.py:42-45` 注释明写「用户注销时置空（共享化）」且 FK 声明 SET NULL；但 FK 从未生效、该意图从未真正执行过，且「注销即共享化」该由人显式决定。改 NO ACTION 后未处置的删除当场报错，处置见权限方案 §4.3） |
| board_cards.author_id → users | SET NULL + author_name 快照 | 协作内容不连坐，展示侧显示「已注销」；**作者注销后卡片转只读**——现状 `_get_owned` 无 admin 旁路（`services/board_cards.py:33-37`，author_id 为 NULL 时对所有人 403，**含 admin**），补一行 admin 旁路让 admin 可接管编辑 |
| carry_*.updated_by_id / adaptation_batches.operator_id / audit_logs.actor_id → users | SET NULL + *_name 快照 | 全局资产上的操作者溯源——行不连坐，只降级为快照可读 |

双级联的净效果：`user_stars` 落表后 `scenario_store.delete:180` 的 `stars.remove_item()` 调用可删（真 CASCADE 接管）；Python 显式级联的职责收缩到只剩 case 目录清理——那恰恰是数据库唯一管不到的东西。迁移后「两套级联」的重叠面不是变大，是变小到几乎没有。归属快照列（`*_name`）一律 `VARCHAR(128)`。
- **表名与业务键不变**：`scenario_id/dataset_id/scheme_id/alias_name` 等字符串业务键原样保留（它们是跨表引用的契约面，改名成本远超收益），只补 FK 约束。
- **schema 管理单一路径（第三轮定统一 alembic；第七轮修订：启动行为分叉）**：现状 `main.py` lifespan 恒跑 `init_db()`（create_all）。初稿曾计划「PG 走 alembic、SQLite 本地保留 create_all」——第三轮否决：create_all 不会 ALTER 既有表，本地库会在每次模型变更后重演 batch_id 式漂移（恰是本方案要根除的病，只是换了个环境）。定案：**两方言统一 alembic，但启动行为分叉**——SQLite/测试启动自动 `alembic upgrade head`（batch_alter_table 模式）；**PG 启动只校验不迁移**：比对 current 与 head，不一致即拒绝启动并打印待执行 revision。漂移照样不可能（起不来），但 DDL 永远由人在带备份的窗口里手动执行——「启动自动 upgrade」意味着任何一次部署都在无人值守、无备份步骤下对生产库做 DDL，绕过 §3.3 的切换纪律，是脚枪。create_all 仅保留给测试 conftest 的新建临时库；PG 与本地库共享同一条迁移历史。**存量 pre-alembic 库（无 `alembic_version` 且已有业务表）走旁路**：启动分支识别后跳过 upgrade、打告警直跑——对这种库跑全量 revision 会在 CREATE TABLE 撞既有表；§3.3 的回滚快照正是此类库（回滚零代码回退依赖此行为），本地开发库的正经姿势是重建而非带病续跑。空库（无版本表也无业务表）照常 upgrade 建起。
- **主键序列**：整型 PK 全部 `GENERATED BY DEFAULT AS IDENTITY`，ETL 后 `setval` 对齐（风险 5）。

### 2.2 逐表设计（只列变化）

**users**：+`role VARCHAR(16)`——**M2 期间建为 is_admin 的 STORED 生成列**（`CASE WHEN is_admin THEN 'admin' ELSE 'member' END`，第九轮「方向翻转」：代码零读零写、回滚天然安全，见 §3.3 回滚），M2.5 `DROP EXPRESSION` 转可写后补 `DEFAULT 'member'`（权威翻转见权限方案 §1.2/§7；SQLite 无 DROP EXPRESSION，出程靠 batch 重建等价——随 M0 验证，§7 三案之③）；`display_name` 补 DB 唯一索引——**partial unique `WHERE display_name <> ''`**（列默认空串，普通唯一索引会让两个未设昵称的用户相撞；现仅应用层查重，`_name_checks.py`，并发可竞态——风险 6）；`password_hash TEXT`；`is_admin` 过渡期保留后删。新增 `user_prefs(user_id FK CASCADE, key VARCHAR(64), value JSONB, PK(user_id,key))`。

**composer_scenarios — 本方案最大的一刀（第四轮定稿：STORED 生成列）**：让列表与筛选下推到 SQL，投影由**数据库在写入时自算**（`GENERATED ALWAYS AS … STORED`），应用写入侧一行不改。

决策链：第一轮否决镜像列（误读退役史）→ 第二轮按用户澄清恢复镜像列 + 三道护栏 → 第四轮按用户复核定稿生成列。**定案依据是已核实的关键事实**：`scenario_store.create()` 与 `update()` 都把 `ScenarioMeta` 校验归一后的 `server_owned.model_dump()` 写回 `definition.meta`（`scenario_store.py:56-70`、`:120-146`——update 还在写前修复空 module/system，create 镜像同一归一化），所以**落库的 meta 恒为归一后形态，SQL 侧的提取能 1:1 复现 Python 侧的读取**——「两套提取逻辑要保持一致」的问题根本不存在，生成列的前提成立。

```
composer_scenarios(
  id, scenario_id VARCHAR(128) UNIQUE,
  owner_id INT REFERENCES users(id) ON DELETE SET NULL,   -- 补 FK；人走场景留（转公共库或转让）
  owner_name VARCHAR(128) NOT NULL DEFAULT '',            -- 现有 owner 字符串快照列升正位
  visibility VARCHAR(16) NOT NULL DEFAULT 'private',
  -- ↓ 查询投影：STORED 生成列，DB 写入时自算；应用与 ETL 均不可写（PG 导入时自算，无需回填）
  name VARCHAR(64)    GENERATED ALWAYS AS (payload->'definition'->'meta'->>'name') STORED,       -- 上限 64 对齐 ScenarioMeta（初稿 255 是硬错）
  description TEXT    GENERATED ALWAYS AS (payload->'definition'->'meta'->>'description') STORED,
  module VARCHAR(64)  GENERATED ALWAYS AS (payload->'definition'->'meta'->>'module') STORED,
  author VARCHAR(128) GENERATED ALWAYS AS (payload->'definition'->'meta'->>'author') STORED,      -- 作者筛选用 meta.author（filters.ts:88），非 owner 快照
  priority SMALLINT   GENERATED ALWAYS AS ((payload->'definition'->'meta'->>'priority')::int) STORED,  -- int 0-3（对齐 ScenarioMeta）
  system JSONB        GENERATED ALWAYS AS (payload->'definition'->'meta'->'system') STORED,      -- list[str] 最少一项，数组列
  tags JSONB          GENERATED ALWAYS AS (payload->'definition'->'meta'->'tags') STORED,
  payload JSONB,        -- 文档体（唯一可写源）：steps/orchestration/assertion_registry
  created_at/updated_at TIMESTAMPTZ
)
INDEX (visibility, updated_at DESC), INDEX (owner_id), INDEX (author)
INDEX USING gin (tags jsonb_path_ops), INDEX USING gin (system jsonb_path_ops)   -- GIN 仅 PG；SQLite 见方言段
```

**为什么物化、且由数据库物化**：PG 会把大 payload TOAST 出去，`payload->>'x'` 表达式在列表查询里要逐行 de-TOAST 才能求值；STORED 生成列把值物化进主元组，列表扫描根本不碰 payload。物化是对的，物化者选数据库。

**收益**：双写漂移从「需要门禁防范的风险」变成**物理上不可能**——没有写入侧维护代码、不需要 backfill 脚本、不需要 CI 一致性断言，`scenario_store` 的 create/update 一行不改；SQL 端过滤/排序/分页全部拿到，「payload 是唯一可写源」一个字不让。SQLAlchemy 用 `Computed(..., persisted=True)` 直接映射。

**代价（如实入案）**：① 改提取表达式不能 UPDATE，只能 DROP + ADD 列（一次 migration，小表无所谓）；② tags/system 数组落 jsonb 生成列 + `GIN (… jsonb_path_ops)`，不为了 TEXT[] 去造 IMMUTABLE 转换函数；③ `_meta_from_row` 的遗留修复（空 module→default、空 system→`["default"]`）**不塞进生成表达式**——ETL 一次性把修复写回 payload（复用 `update()` 的 repair 口径），迁移正是清掉这段修复的窗口，之后那几行删除。

**方言**：SQLite 3.31+ 支持 STORED 生成列；表达式渲染走 SQLAlchemy `Computed` + dialect 变体（PG `->/->>`，SQLite `json_extract`）。数组包含与 facets 收敛到唯一一对 helper（PG `col @> '["x"]'::jsonb` + GIN jsonb_path_ops、facets 用 `jsonb_array_elements_text`；SQLite 本地 Python 兜底——本地量小，正确性优先）。标量列在两方言上语义一致。

**交叉验证欠账（第七轮标记，M0 十分钟最小验证）**：SQLite 的 `ALTER TABLE ADD COLUMN` **不能加 STORED 列**（只允许 VIRTUAL）——第三轮「统一 alembic」与第四轮「STORED 生成列」各自正确、合在一起未验证：alembic batch 走「建新表→拷数据→换名」，新表本身能带 STORED 列，但拷贝那步 `INSERT INTO new (…) SELECT …` 必须把生成列排除在列清单外，alembic 是否自动识别 `Computed` 并跳过**未经验证，不替它断言**。M0 先在 SQLite 上用 batch 给一张带数据的表加 `Computed(..., persisted=True)` 跑通再定稿；跑不通的退路现成：PG 侧 STORED、SQLite 侧渲染 VIRTUAL（本地量小，不要 STORED 的性能），方言分叉本段本来就在做。

排序/分页锚 `updated_at`——「最后编辑」本来就是 DB 行 `updated_at` 的读时投影（scenario_store 明文「服务端权威」，payload 里客户端伪造的 updateTime 不采信），天然可索引。q 检索（name/description/module/scenario_id + tags 子串，口径对齐 `_passes_filters` 的 haystacks）在 PG 用 pg_trgm GIN 索引覆盖 ILIKE。列表端点从此 SELECT 投影列 + SQL 端过滤/排序/分页，`payload` 列列表查询永不触碰——债 3 就此消除。

**executions + execution_snapshots 拆表**：

```
executions(
  id, scenario_id VARCHAR(128), scenario_name VARCHAR(255) NOT NULL DEFAULT '',  -- 快照，场景删了执行仍可读
  owner_id INT REFERENCES users(id) ON DELETE SET NULL, owner_name VARCHAR(128),
  status, batch_id, total_runs/passed/failed, config_json JSONB,
  started_at/finished_at/created_at TIMESTAMPTZ
)
INDEX (owner_id, id DESC), INDEX (scenario_id, id DESC), INDEX (batch_id)
execution_snapshots(execution_id INT PK REFERENCES executions(id) ON DELETE CASCADE, snapshot JSONB)
```

列表查询天然不含快照——但**债 4 只消除了一半（第八轮）**：`ExecutionOut.config: dict`（`schemas/execution.py:19`）把 `config_json` 整列随每行列表发给前端，而它正是权限论证收窄后的敏感面（凭证引用面，权限方案 §1.2）。补刀：列表 SELECT 一并排除 `config_json`、`ExecutionOut` 列表形态去 `config`（详情页保留）——**并入 M1 的响应投影**（ExecutionsList 本就在 M1 范围），不必等 M2。`has_scenario_snapshot` 判定变成一次存在性查询，不再依赖「整实体加载时列是否 unloaded」的 ORM 细节。拆表可行性已核实：rerun **不依赖**快照（`executions.py` 的 rerun 用 `config_json` 重建配方 + 现查场景，场景已删即 404），快照的唯一消费方是 `GET /api/executions/{id}/scenario-snapshot` 端点——改查新表即可。

**execution_rows（新表，吸收 JSONL，查漏轮修订：对齐真实行形状）**：

```
execution_rows(
  id BIGSERIAL, execution_id INT NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
  seq INT NOT NULL, dataset_id VARCHAR(128), injection_id VARCHAR(128),
  row_index INT, rep INT, status VARCHAR(24), case_dir VARCHAR(255),
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
  UNIQUE (execution_id, seq)
)
```

字段对齐 `_replay_rows` 折叠后的真实行形状（seq/datasetId/injectionId/rowIndex/rep/status/caseDir/startedAt/finishedAt）——初稿草拟的 ok/failed/duration_ms/error 在现状行里并不存在，删去。关键语义：JSONL 是**事件流**而非终态（同一 `(executionId, seq)` 会先写 dispatched 再写 final，回放时后行覆盖前行）。落库写入点拍板为**每行终态即 upsert**（第三轮修订，原「等 finalize 批量落」会让崩溃窗口丢掉已终态的行、JSONL 停写后无兜底）；活跃执行的读侧仍走内存 `_row_states` registry，DB 行作为持久层跟进。ETL 导入复用 `_replay_rows` 折叠函数而不是逐事件搬运。`GET /executions/{id}/rows` 变成真分页查询（债 5 消除）。**保留策略定案（第七轮；量级口径第八轮补）：行是台账、工件是易耗品**——execution_rows 默认全保，但**量级以 preccheck 实测为准（§3.2）——百万级则上线即带保留参数，不拿「内部量级」当假设**；case 工件照旧 14 天清扫；`case_dir` 是软引用，工件被清扫后详情页显式显示「已过期清扫」而非死链 404（**第九轮实施注记：这个分支是待写的前端代码，不是既有行为**——14 天清扫今天就跑（`CASE_RETENTION_DAYS=14`，`run_dispatcher.py:338` 启动期触发），且切换后第一次起服就会**批量**兑现：ETL 刚把全部历史 JSONL 折成带 case_dir 的行，sweep 随即清走超龄目录，「行在、工件没了」会摆在切换后第一个打开老执行详情的人面前——分支实现进 M1（纯前端，切换前就位），§3.3 冒烟第 ③ 条对拍）。`data/runs/cases/` 的工件目录（engine.log/reports）**保留文件制**——它们是大体积只追加工件，入库无查询价值。JSONL 历史文件 ETL 导入后转只读归档。

**user_stars（新表）**：`(user_id FK CASCADE, scenario_id VARCHAR(128) FK CASCADE, created_at, PK(user_id, scenario_id))`，吞掉 `data/stars.json`（债 6）；`scenario_id` 上的 CASCADE 接管 `scenario_store.delete:180` 的 `stars.remove_item()` 调用（M6 删除）。关注页的 N+1 信号扇出另由 §5 的 bulk 端点解决。

**notifications / audit_logs**：结构见权限方案 §3.3/§6，此处只落库。

**carry_service_bindings / carry_global_defaults**：`updated_by VARCHAR(64)` → `updated_by_id INT REFERENCES users(id) ON DELETE SET NULL` + `updated_by_name VARCHAR(128)`（对齐三件套规范）；`value TEXT` 不变；唯一约束原样。

**adaptation_batches / adaptation_ops / adaptation_snapshots**：`operator_id` 补 FK SET NULL + `operator_name` 快照；其余原样（partial index 无关的表不动）。

**composer_data_sets / composer_run_schemes**：`rows/var_unlocks/payload → JSONB`；`uq_run_scheme_scenario_name` 与 partial unique `uq_run_scheme_default` 原样（双方言 `where` 已备好，alembic 里用 dialect 参数重建，勿丢——风险 7）。

**scenario_endpoint_refs**：复合 PK 原样；`scenario_id` 补 FK `composer_scenarios(scenario_id)` **NO ACTION DEFERRABLE**（`scenario_store.delete` 经 `endpoint_ref_index.sync_scenario` 在 Python 侧删——映射表第一行）；派生层定位不变，**ETL 不导入、切换后 rebuild**（§3.3，顺带补齐存量锚点行）。

**service_aliases / board_cards / catalog_versions / constant_entries / auth_sessions**：JSON→JSONB、密文列放宽 TEXT、`owner_user_id` FK 语义原样；`board_cards` 的 partial unique `uq_board_cards_root` 同上双言重建。`service_aliases.credential_alias` 维持按名引用凭证别名（alias 是业务键，凭证删除时的悬空由现有校验兜底，不升级为 FK——两表分属不同 owner 域）。

### 2.3 不进库的东西

`data/runs/cases/` 工件目录（文件制）；plate 内存注册表（无 DB，迁移不涉及）；前端 localStorage 偏好（权限方案 §8 明确本期不迁）。

## 3. 迁移执行方案

### 3.1 环境与配置（M0）

- PG 16，开发机 `docker compose`（仓库提供 `compose.pg.yml`：pg + healthcheck + named volume），生产同文件；驱动 `asyncpg`（`requirements-platform.txt` +constraints 同步钉版）。
- `config.py`：`DATABASE_URL` 默认保持 sqlite（本地裸跑零依赖不变），`.env` 切 pg；`aiosqlite` 依赖保留（测试与本地起步仍用 sqlite，见 3.4）。
- engine 补齐：`pool_size=10, max_overflow=20, pool_pre_ping=True`。

### 3.2 前置数据体检（不改代码，先出报告）

`scripts/pg_preccheck.py` 对 SQLite 库逐表扫描：类型亲和异常（Integer 列存字符串等，风险 8）、变长列超长、孤儿行（FK 若真生效会被拒的行：如 `executions.owner_id` 指向已删用户——**预期存在**，SET NULL 语义吸收）、`display_name` 重复；**payload 抽出面逐行校验（第七轮补）**——生成列把「脏数据读时修复」变成「写入即拒」：任何一行 meta.name 超 64、或 priority 存成不可转换的字符串，ETL 灌行当场炸（今天这类行会被 `_meta_from_row` 读时兜住），preccheck 对 composer_scenarios 逐行抽取 definition.meta 过一遍 `ScenarioMeta` 校验、不合规行打清单，与 module/system 修复写回放同一步做——成本几乎为零，防的是 ETL 跑到一半炸掉。**execution_rows 量级实测（第八轮补）**：现网 JSONL 按 `_replay_rows` 折叠后的总行数在 preccheck 数出来写进方案——行数 ≈ Σ(数据集 × 行 × rep)，ETL 还要一次性吞全部历史；「内部量级」目前是假设不是测量，实测若已百万级，§2.2 的「默认全保」改为「上线即带保留参数」（ETL 报告反正要出这个数，提前到 preccheck 只是把事后变事前）。体检报告人工过目后才允许 ETL。

**前置配置检查（查漏轮补）**：`FERNET_KEY` 与 `JWT_SECRET` 必须已是固定配置（`.env`）——凭证密文是应用层 Fernet 加密，跨库搬运可解密的前提是密钥不变；`main.py` 对 ephemeral 密钥有启动告警，ETL 前确认两键非 ephemeral，且旧库备份文件（同样含密文）按密钥同等级保管。

### 3.3 ETL（`scripts/migrate_sqlite_to_pg.py`）

- 双同步 engine（sqlite3 + psycopg）；**FK 全部 DEFERRABLE INITIALLY DEFERRED，事务内插入顺序自由，约束在 commit 时统一校验**（第五轮放松初稿的「按依赖序逐表搬」）；每表一个事务；`func.now()` 列不搬（让 PG 生成）。
- **INSERT 列清单显式排除全部生成列**（composer_scenarios 七列 + `users.role`，第九轮补）——psycopg 直插只要列清单带上生成列，PG 当场拒 `cannot insert into column … GENERATED ALWAYS`；写法本身在 M0 就用几行脚本试掉：空表 + 一行 payload 直插（排除生成列）确认自算、故意带上生成列确认报错形态——与 SQLite batch 交叉验证是同一坑的两侧，只验一侧不算验证完。
- **存量可疑的表先 `ADD CONSTRAINT … NOT VALID`、导入后再 `VALIDATE CONSTRAINT`**：约束挂上只对新行生效，存量单独验，不让可疑历史行把 ETL 打断——典型是 `composer_scenarios.owner_id`（Integer default=0，历史行可能成批指向不存在用户；ETL 变换已映射 NULL，NOT VALID 是第二道保险）。
- **`scenario_endpoint_refs` 不导入，切换后 rebuild**（本就与 PG 无关、纯脚本顺序问题，写进步骤防漏）——rebuild 顺带把存量场景的锚点行补齐，这是 NOT VALID 换不来的。
- **变换**：role 不搬不映射——生成列自算（第九轮方向翻转，§2.2 users / §7 M2，users 导入按上条排除该列即可）；**场景 meta 遗留修复一次性写回 payload**（空 module→default、空 system→`["default"]`，复用 `update()` 的 repair 口径——生成列从修复后的 payload 自算，无需回填列；迁移后 `_meta_from_row` 的修复分支删除，§2.2）；`composer_scenarios.owner_id=0` 的历史行映射为 NULL（模型 default=0 的遗留值会被 FK 拒收，preccheck 先清点）；`executions.owner_name` 只能 **join users 回填**（config_json 的键是 runId/scenarioId/dataSetIds/injectedAuths/serviceBindings/stepTo/nRuns/parallel——没有人名，初稿「从 config_json 回填」不成立），**已注销属主的历史行 join 不到 → owner_name 留空、列表显示「已注销用户」，这是设计内的降级而非回填缺口**——而那恰是 owner_name 最有价值的行；`scenario_name` 同理，join 场景表拿不到的（审计 P11：3 行指向已删场景）留空；`stars.json` 导入 user_stars（**JSON 对象键一律是字符串，必须 `int(k)`**——直接拿 key 插库轻则类型报错、重则零行静默导入）；JSONL 历史按 `_replay_rows` 折叠成终态后导入 execution_rows；naive 时间戳统一按「视为 UTC」补时区转 aware。executions / execution_snapshots / execution_rows 三表放同一事务。
- **收尾**：全部 IDENTITY 列 `setval` 到 max(id)——**序列名一律不手拼**（`<table>_<col>_seq` 是实现细节不是契约，命名例外比漏表更难发现，第九轮）：checklist 写死为遍历 `information_schema` 中全部 IDENTITY 列、逐列 `pg_get_serial_sequence('表名','列名')` 取名再 setval，遍历驱动一个表都漏不了（风险 4）；重建全部索引/约束。
- **校验**：逐表行数对账 + 每表抽样 50 行的规范化 JSON checksum 比对 + 生成列抽样与提取函数直接求值比对 + **user_stars 导入行数 vs stars.json 文件内计数**（防字符串键静默丢数），输出迁移报告（含 execution_rows 从 JSONL 吸收的行数）。
- **演练（≥1 次，正式切换的门禁；第九轮补数据源要求）**：**必须用生产 `app.db` 的副本**——ETL 唯一的失败源是存量数据（超长 meta、owner_id=0 批、孤儿行、脏类型、stars 字符串键），开发库一条都验不了，跑通≠门禁过；演练与正式切换各产一份迁移报告（行数对账/生成列抽样/stars 计数），**逐项对比**——两份不一致本身就是信号（多半是两次之间数据又动了，那就再对一次）。
- **切换**：停服 → 备份 `app.db`（只读保留作回滚快照，至少留一个版本）→ **空 PG 库 `alembic upgrade head` 建全部表（第九轮补的断点：第七轮把 PG 启动改为只校验不迁移后，整条链路里再没有任何一步创建 schema——建表是 ETL 的前提，前移为人工步骤；起服只校验）** → ETL → `.env` 切 pg → 起服（**依旧禁用 --reload**，执行器触发约束延续）→ 冒烟（登录/场景列表/发起一次小执行/画像三页；**第九轮补三条高危面**：①生成列对拍——按 tag 与 system 各筛一次、与切换前旧栈留存的结果比对（样本在演练时于旧栈采好）——生成列错了页面照开、只是筛选悄悄不对，「页面能开」验不出它；②删一个测试用户走通全链（先造好带凭证/常量/个人别名的测试号——收藏此时还在 stars.json 文件里、user_stars 行吸收在 M6，不进本条）——FK 校验器 + 最小显式级联的端到端验证；③打开一条 ETL 前的旧执行详情，确认已清扫 case_dir 的行显示「已过期清扫」而非死链/500——起服即扫（`run_dispatcher.py:338`），这不是演练造得出来的，切换后第一个打开老执行的人就会撞见）。
- **回滚**：`.env` 切回 sqlite + 旧库文件，**不回退代码**（第九轮写明成立前提，两条都由拆包决策保证）：①role 用生成列方向翻转——M2 期间代码零读零写 role（不需要「有 role 用 role、没 role 回落 is_admin」的运行时探测——那要条件化 mapper 配置，脆；列不进 models，物理上不依赖）；②生成列的消费（检索 SQL 化）在 M3、execution_rows 代码在 M3+，M2 同车代码不读任何新列。回滚库是 pre-alembic 存量库，SQLite 启动分支对其跳过 upgrade 直跑（§2.1）。切换后产生的新数据不回灌（内部平台可接受，切换窗口选低峰并提前公告——用权限方案的 announcement 通知首发）。

### 3.4 测试策略（第六轮修订：PG 隔离选型单列）

`conftest` 的现行范式是「每测试一个临时 SQLite 文件 + create_all + monkeypatch 全局 engine」——**这在 PG 上不成立**：500+ 测试不可能每测试建一个库，初稿「加个 `TEST_DATABASE_URL` 就全量跑同一套测试」低估了这一步。两条可行路线都要求重写 fixture：

- **schema-per-test**：每测试 `CREATE SCHEMA` + `set search_path`，结束后 DROP——最贴近现行「每测试独立库」的语义，改动集中在 conftest 一处；
- **事务回滚 fixture**：每测试开事务、结束 ROLLBACK——最快，但与被测代码自己的 commit 语义相冲（run_dispatcher 的后台线程用独立 session，会提前落盘逃逸回滚），需要 SAVEPOINT 嵌套协议，改动更深。

**M0 必须先定选型并作为独立工作项交付**（倾向 schema-per-test：与现行语义最接近、不碰被测代码）——M2 切换门禁「PG 全量 pytest 绿」压在它上面。默认路径仍 sqlite（快、零环境依赖），双方言自律不变（两处 partial index 已示范）。**切换验收 = PG 后端跑全量 pytest 绿 + M0 实测钉死的基线不降**（仓内审计 630 与本文前稿 622 两数并存，M0 实测为准）。

## 4. 检索后移 — 统一契约与改造范围

### 4.1 统一列表契约（Page 信封）

所有列表端点统一：

```
GET ...?q=&page=1&page_size=20&sort=&<域内筛选键>
→ { "items": [...], "total": 123, "page": 1, "page_size": 20 }
```

- `page_size` 上限 100，默认 20；`q` 语义 = 域内白名单字段的 ILIKE 子串（大小写不敏感，对齐现状 `.lower().includes` 口径）。
- **一次性破坏性切换，不做兼容期**：内部单部署，前后端同版本上线；executions 现有 `{items,total}` 缺 `page/page_size` 字段，补齐即向后兼容。
- 排序：场景 `updated_at DESC`、执行 `id DESC`、用户/别名 name ASC，首期服务端定死不接受任意 sort 注入（白名单）。
- 场景库高级筛选（modules/systems/tags/authors/priorities/updatedWithin）配套 **facets 端点** `GET /api/scenarios/facets`（GROUP BY 聚合返回各维可选值+计数），替代现在「全量拉回来在 FilterPopover 里 unique」的模式。

### 4.2 改造范围表（后端参数化 + 前端接入）

| 页面/端点 | 现状 | 目标 |
|---|---|---|
| `GET /api/scenarios`（ScenariosMine/Public、Runner picker、OpConstructDialog、ScenarioDetailView 兜底） | 全表加载含 payload，Python 过滤 | 投影列 + `q/visibility/system/module/priority/tags/author/updatedWithin/sort/page` 全 SQL 化（author 与 updatedWithin 是 FilterPopover 的既有筛选维度，第三轮补齐）；**新增轻量元数据形态 `?fields=options`**（仅 id/name/visibility/owner，可见性口径与列表一致：member=自己+public、admin=全量），供选择器与名称映射——砍掉四处「为拿名字拉全量场景表」 |
| `GET /api/executions`（ExecutionsList） | 服务端筛选+limit200 无翻页；q 在前端 | `q`（scenario_name ILIKE / id 前缀）下推；+page/page_size/total |
| `GET /api/executions/{id}/rows` | JSONL 全量扫一次性返回 | execution_rows 分页查询 |
| `GET /api/auths` | 裸全量 | `q`（alias/username/url）+ `token_type` + page；引用计数保持后端；metaText 的「N Bearer · N 整段头」计数改由服务端聚合返回（现状是前端对全量 reduce——服务端分页后前端再也拿不到全集，第三轮补） |
| `GET /api/users` | 裸全量、全员可见 | 权限收紧（operator+）+ `q`/`role` + page |
| `GET /api/constants` | 裸全量 | `q`（name）+ kind + page |
| `GET /api/adaptations/batches` | 全量（注释自认「分页留待 P5」） | `scope/status/page` |
| `GET /api/carry/bindings|defaults` | 整表 | 行数小，本期不分页（明确豁免，见 §9） |
| `GET /api/service-aliases` | 全量 | `q/base` + page |

### 4.3 场景 store 的退位

`stores/scenario-composer.ts` 现在把全量场景当全局缓存（三页 + 详情 + 各卡共写一份）。检索后移后 store 只存**当前页 + options 形态的元数据缓存**；详情页直接按 id 拉单条（新增 `GET /api/scenarios/{id}` 已有，去掉「store 空就全量 fetch」的兜底，`ScenarioDetailView.vue:334`）。发布/下架/收藏等 mutation 后只作废当前页重拉。

## 5. 聚合与轮询后移

| 现状前端聚合 | 后移为 |
|---|---|
| ServicesIndex/ServiceAdmin/工作台卡各自 `per_page=500` 拉 plate 目录再前端聚合计数（>500 静默丢） | `GET /api/catalog/services`：平台后端聚合 plate 目录并缓存（TTL 30s + 目录版本失效），返回服务级计数；前端 catalog-services.ts 改走此端点（债 11） |
| ScenarioFollows 每关注对象 `listRunSchemes`+`listExecutions` N+1 | `GET /api/scenarios/signals?ids=a,b,c`：一次返回每场景的健康趋势摘要（批量、限 20 个 id 对齐关注上限） |
| useInterfaceChange 对每个 pending 端点逐个 `impact()` | 已有 `impactSummary(ids)` 扩展为完整 bulk impact 端点，一次返回变更场景集合 |
| 工作台时间线三源前端合流排序 | `GET /api/activity?limit=40`：服务端合流（本人执行 + 本人场景改动 + mine 批次），前端只做日历分组渲染 |
| 场景详情断言覆盖率/统计 reduce | 量小（单场景 steps），**留在前端**（明确豁免） |

**轮询治理**（同批落地）：ExecutionsList 的 3s 整表轮询 → 10s 且只刷 `summary` 端点 + 当前页（`document.visibilityState` 不可见时暂停）；Executions 详情 1s 轮询保留（活跃执行场景合理），终态即停（现状已停则确认保持）；新增铃铛 30s（权限方案）。

## 6. 前端分页规范化

### 6.1 三件公共设施

- **`components/ui/pagination/`**：把场景库自绘的 `ListPager.vue` 升格为 ui 级组件（props: page/pageSize/total/siblingCount；emit update:page；禁用态/省略号/总数文案；键盘可达），全站唯一分页实现。
- **`composables/useServerList.ts`**：统一「服务端列表页」范式——入参 fetch 函数 + 响应式参数；产出 `items/total/loading/error/page/setPage/query/setQuery`；内置 300ms 防抖（`utils/debounce.ts` 顺手补全站第一个公共防抖，收编 FieldStateSearch 的内联实现）；参数变化自动重置页码；翻页后 `scrollTo(0)` 可选。
- **URL query 同步**：`q/page` 写回 `router.replace({ query })`（replace 不进历史），刷新/分享/返回不丢状态——覆盖全部列表页；既有深链（`?batch_id/?path/?rows=failed` 等）原样兼容。

### 6.2 页面接入清单

P1 批（有分页 UI）：ScenariosMine、ScenariosPublic、ExecutionsList、Executions 行级表、Auths、UsersAdmin、适配批次表。
P2 批（补搜索/轻量接入）：ConstantsPool、ServiceAdmin 别名表、Runner picker、CaseComposerCatalog（plate 直连改走平台聚合端点后天然获得服务端检索）。
明确豁免：CarryConfig（行数 ~几十）、方案列表（场景级小量）、数据集、别名详情页。

### 6.3 验收口径

场景页：造 45 条场景，搜索「订单」+筛选 system + 翻到第 2 页 → 地址栏含 `q=订单&system=xx&page=2`，刷新状态不丢，网络面板确认只拉了当前页（无全量 GET /api/scenarios 不带分页参数的请求）；ExecutionsList 超 200 条不再截断且 total 正确；关注页网络面板从 40+ 请求降到个位数。

## 7. 分期与门禁

| 阶段 | 内容 | 门禁 |
|---|---|---|
| **M0 准备** | docker compose PG、asyncpg、config 分支、pool 参数、测试参数化（TEST_DATABASE_URL）；**PG 测试隔离选型与 conftest fixture 改造**（§3.4，单列工作项：schema-per-test（倾向）vs 事务回滚，先行定选型——M2 门禁压在它上）；**生成列 × alembic batch 交叉验证（第九轮补遗后三案齐——进两案、出一案）**：①进/composer 七列（§2.2 方言段：带数据表上 batch 加 `Computed(persisted=True)` 跑通，跑不通走 PG STORED / SQLite VIRTUAL 分叉）；②进/users.role 单列同验——同一个「带数据表上加 STORED 生成列」的坑，但它在 M2 关键路径上（回滚安全整个压在 role 零读零写上，生成列建错=切换当天卡住），不和 composer 七列假定同构（布尔 CASE 比 JSON 抽取简单，简单≠免验）；③出/生成列→普通列翻转（M2.5 权威翻转的后半程）——PG 原生 `ALTER COLUMN … DROP EXPRESSION` 顺手跑一行；SQLite 无等价 DDL，靠 batch 重建把「读生成列 → 写普通列」拷过去，**必须断言逐行值相等**（SQLite 若走 VIRTUAL 分叉，生成列无存量数据、拷贝全靠现算）；跑不通则 M2.5 翻转 revision 对 SQLite 退化为手写重建 SQL（CREATE/INSERT SELECT/DROP/RENAME），batch 之外仍有出路——只验进不验出，等于只验了能不能进、没验能不能出；**PG 侧 ETL 写法同批试掉**——空表 + 一行 payload 直插：列清单排除生成列确认自算、故意带上确认 `GENERATED ALWAYS` 报错形态，同一坑的两侧只验一侧不算验证完，§3.3 第九轮；**备份策略**（查漏轮补：SQLite 时代备份=拷文件，PG 需要 `pg_dump` 每日定时 + 保留 N 份 + compose volume 备份说明，进运维 runbook）；`ALTER DATABASE gimbal SET timezone='UTC'` 钉死会话时区（§2.1） | sqlite 全量测试绿（**基线以 M0 实测钉死——仓内审计写 630、本文前稿写 622，两数并存不猜**）；PG 隔离选型定案 + fixture 改造在 PG 上跑通冒烟子集；生成列×batch 验证有结论——**三案齐**：进（composer 七列）、进（users.role）、出（双方言翻转，逐行值相等） |
| **M1 列表减负（第四轮新增：切换前上线，现行 SQLite 即可；第七轮措辞修正——这是「响应投影」，不是「查询投影」）** | 场景列表**响应投影**（响应不含 payload/steps，仅 meta 摘要/stepCount/starred）；**服务端查询仍全表加载 payload**——`_passes_filters` 吃 `_meta_from_row(row)`，Python 过滤就得把 payload 捞出来；查询投影与 SQL 端过滤排序依赖 M3 的生成列，M1 不假装拿到；Page 信封先落场景域 + ExecutionsList 补 offset 翻页（q 暂留客户端）+ **ExecutionOut 列表形态去 `config`**（config_json 整列随列表下发是债 4 的另一半，`schemas/execution.py:19`，详见 §2.2——详情页保留）；ui/pagination + useServerList（含防抖）+ URL query 同步；`?fields=options`；store 退位（§4.3）+ 消费面清点（ScenarioDetailView 断言统计、Runner picker、OpConstructDialog、工作台四卡改走 options/详情端点）；Mine/Public 两页接入；过滤/排序暂留 Python（分页后每页数据量可控）；**「已过期清扫」前端分支**（case_dir 软引用的消费面，§2.2 第九轮——14 天清扫今天就跑（`run_dispatcher.py:338`），这个分支与迁移无关地欠着；切换后首启即批量触发，必须切换前就位） | 6.3 场景页验收；无全量场景请求——**浏览器内存三件事（①列表不回 payload ②分页 ③store 退位）不等停服窗口全部落地**；门禁**不含**「DB 扫描下降」（那是 M3 的门禁，别写错） |
| **M2 表定稿 + 切换** | §2 全部 DDL 进 alembic（生成列/快照拆表/权限域新表/FK 动作映射；**第一个 revision 即全量新 schema = 天然 baseline，无 stamp——§0 原则 4；空库 `upgrade head` 建表是切换的人工第一步，§3.3**）；preccheck + 密钥前置检查；ETL 脚本（含 meta 修复写回、DEFERRABLE/NOT VALID 策略、refs rebuild 步骤、生成列排除与 `pg_get_serial_sequence` setval 写法）+ 校验报告；切换演练（备份→建表→ETL→切 env→冒烟）≥1 次成功后正式切——**演练必须用生产 `app.db` 副本**（存量数据是 ETL 唯一失败源，开发库验不了任何一条，§3.3），演练与正式两份迁移报告逐项对比；**停服窗口同车权限 P1a（第九轮修边界）：role 列随 DDL 建库——以 is_admin 为源的 STORED 生成列，代码零读零写（「方向翻转」替代 is_admin 读侧派生那段代码：回滚不需运行时双向探测，§3.3 回滚段）+ `DELETE /api/users` 最小显式级联（第九轮从 M2.5 拎回：FK 真生效后凭证池/常量/个人别名三张 NO ACTION 表在场，不带它则 M2→M2.5 之间删号必被当场拦死；纯端点代码不碰 dispatcher）——第八轮拆包仍然成立：其余权限代码整体后挪 M2.5（execution_finished 要在 dispatcher 终态收口新加写入点，切换当天最不该动的就是执行链路——数据搬运错了可回滚，调度器错了是线上事故）**；lifespan 的 create_all 替换：**SQLite/测试自动 upgrade，PG 启动只校验不迁移（§2.1 第七轮分叉）** | PG 全量 pytest 绿；逐表对账零差异；生成列抽样=提取函数；元数据断言测试绿（全列 timezone=True、无裸 func.now()）；冒烟清单过（含第九轮补的三条高危面：生成列筛选对拍/删测试用户走通/旧执行「已过期清扫」）——**M1 前置 + P1 拆包后，M2 的结构性风险只剩「数据搬对了没有」（第九轮后加半句：同车代码仅最小级联一段纯端点删除，删号冒烟即验）** |
| **M2.5 权限代码上线（第八轮新增：切换后立即，不依赖停服）** | 权限方案 P1b 整包：require_role 依赖工厂与执行点、前端 hasRole 全量替换与路由 meta、notifications 三接口 + 铃铛 UI + 六种通知接线（dispatcher 终态写入点在切换窗口外落）、**按 type 通知开关与铃铛同批**（user_prefs 表随 M2 DDL 已建、代码提前——开关先于吵闹型通知，否则 adaptation_applied 一批扫几十场景、每 owner 一条，铃铛上线即被整体关掉）、用户接口收紧（GET→operator+ / POST→admin）、注册 bootstrap 双修、role 权威翻转（`ALTER COLUMN role DROP EXPRESSION` 转可写 + models 映射 role、is_admin 转读侧派生——baseline 后第一个真 revision，双方言，SQLite 走 batch 重建，出程转换随 M0 验证 §7 三案之③）、适配边界白名单测试 | 权限方案 §7 三角色验收口径全过；铃铛 + type 开关可用 |
| **M3 场景检索 SQL 化** | 生成列上线的 SQL 端过滤/排序（§2.2）；facets 端点（modules/systems/tags/authors/priorities）；author/updatedWithin/tags 参数下推；trgm ILIKE | q/筛选全走 SQL（网络面板确认请求带参数）；facets 计数与全量一致 |
| **M4 分页规范化** | Page 信封铺其余 §4.2 端点；P1 批页面接入；users 列表分页信封（**接口收紧已随 M2.5 落地，此处不再挂——第九轮修滞后**） | 6.3 全部验收 |
| **M5 聚合与轮询后移** | §5 四个聚合端点 + 轮询治理 + P2 批页面；**auth 引用计数增量化**（查漏轮补：`/api/auths` 现每次调用全表扫全部场景+方案 payload（`auth_references._scan_scenario_refs`），是列表页最贵的隐藏成本——改 scenario_auth_refs 派生表随场景/方案写维护，或按 max(updated_at) 失效的缓存）；**关注页服务端数据源**（`GET /api/scenarios?starred=true` + 分页——store 退位后 `starredScenarios` 全量过滤失去依托） | 关注页/工作台网络请求计数达标 |
| **M6 收尾** | execution_rows 吸收 JSONL + 历史导入；user_stars 上线（marks_store 退役，star 端点形状不变、`starred` 仍为读时投影；**关注上限 20 改服务端 409 兜底**，客户端先拦不变）；**`scenario_store.delete:180` 的 `stars.remove_item()` 调用删除**（user_stars.scenario_id 的 CASCADE 接管，§2.2）；`is_admin` 列删除；`_meta_from_row` 修复分支删除（§2.2）；旧 data/runs/*.jsonl 归档只读 | 行级回放分页可用；stars.json 不再被读 |

顺序依据（第四轮重排，第八轮修订）：**M1 列表减负不依赖任何 schema 改动**——响应投影 + limit/offset 在现行 SQLite 上即可成立，故置于切换之前：浏览器内存压力不等停服窗口先缓解。**权限 P1 拆包后，M2 停服窗口也真的只剩「数据搬对了没有」一个失败维度**——M1 前置解决浏览器那一半的窗口肥胖，权限代码后挪 M2.5 解决另一半。M3 的 SQL 端过滤/排序依赖 M2 的生成列；M4 起依次铺开。权限方案 P1a 随 M2、P1b = M2.5、P2 在 M4 后独立迭代。

## 8. 风险清单（迁移特有）

1. **FK 开始真执行**：孤儿行在 ETL 前必须 preccheck 发现并处置（SET NULL 语义吸收 / 预清理），否则搬运即失败（存量可疑表另有 NOT VALID 缓冲，§3.3）。切换后删除用户的行为要按新语义回归（§2.1 映射表）：场景/执行/线索板/溯源列 SET NULL；凭证/常量/别名 NO ACTION 由 Python 显式处置（漏处置当场报错，这是特性）；user_prefs/notifications/收藏 CASCADE 自收。
2. **时区扫尾**：naive→aware 波及 `timeutil`、`scenario_store.py:450-453` 的读侧 replace、**`adaptation_service.py:100-118` 的 `_parse_dt`/`_utcnow`**（`:168` 的 `updated > stamp.synced_at` 混比会当场 TypeError）、时长减法、Pydantic 序列化；`catalog_versions.synced_at` 的 `server_default=func.now()` 是唯一不经 `_utcnow()` 的 DB 生成值（战术备选一行 `now() at time zone 'utc'`，见 §2.1）。M2（切换）专项扫一遍 + 元数据断言测试 + `ALTER DATABASE … SET timezone='UTC'` 钉死会话时区。
3. **VARCHAR 真校验**：密文/URL 列放宽 TEXT 的同时，保留的短键逐个对现网 max 长度体检（preccheck 输出）；**生成列的七个抽出字段同受此约束**（name>64 即写入即拒）——由 preccheck 的 payload 逐行 meta 校验覆盖（§3.2）。
4. **IDENTITY setval**：漏一个表 → 切换后首次 INSERT 主键冲突；ETL 收尾 checklist 强制全表，且序列名一律 `pg_get_serial_sequence` 取、不手拼（`<table>_<col>_seq` 是实现细节非契约，命名例外比漏表更难发现——第九轮，§3.3）。
5. **partial unique 双言重建**：`uq_run_scheme_default`、`uq_board_cards_root` 在 alembic 里用 dialect where 子句重建，迁移后用 PG 端 EXCEPT 抽样验证约束等价。
6. **并发语义变化**：SQLite 单写者串行 → PG MVCC。已有缓解（计数器增量 UPDATE + 2 次重试，`run_dispatcher.py:1086-1118`）保留；M2（切换）后压测一次并发 fanout（并行 10 case）确认无死锁回归。
7. **类型亲和脏数据**：preccheck 全表扫描，发现即人工清洗后再 ETL，不带病搬运。
8. **回滚不对称**：切换后新数据不回灌 SQLite；用低峰窗口 + 提前公告缓解，接受残余风险。回滚动作本身零代码回退（§3.3：M2 同车代码不读任何新列），残余风险收窄为「切换窗口内新数据丢失」。
9. **`--reload` 禁令延续**：PG 版起服命令不变，仍手动重启（既有运维约束，写进切换 runbook）。
10. **单进程部署约束不变（第三轮补）**：PG 不改变「单 uvicorn 进程」语义——活跃行级状态在内存 `_row_states`、调度器是进程内线程/子进程，多 worker 部署会让两者分裂。部署文档把「禁多 worker」与「禁 --reload」并列为硬约束。

## 9. 明确不做的

- **双写/双读过渡期**（§0.1）；**读写分离/分库分表**（量级差三个数量级）。
- **Elasticsearch / tsvector 全文检索**：ILIKE + 元数据列 +（必要时）pg_trgm GIN 索引足够；检索质量真成为瓶颈再议。
- **keyset/cursor 分页**：统一 offset 分页；executions 若单用户量级到十万级再对它单独升级（接口留 `sort=id desc` 的天然游标位）。
- **Plate 侧任何改动**：plate 无 DB（内存注册表，重启重建），迁移与其无关；仅前端改走平台聚合端点。
- **CarryConfig 分页**：行数 ~几十，整表编辑语义（全量提交）也依赖小表，明确豁免。
- **场景详情页统计后移**：单场景 steps 的 reduce，规模不构成问题。
- **本地默认库切 PG**：`DATABASE_URL` 默认仍是 sqlite，裸跑零依赖；PG 是显式 opt-in（`.env`）。

## 附：与《用户权限与用户管理-设计方案》的互锁点

见该文附表。一句话：权限域的全部新表（role/notifications/user_prefs/audit_logs/user_stars）与 `executions` SET NULL 语义、删除端点最小显式级联在本文 M2（表定稿+切换）落库/同车，权限域的接口收紧随 M2.5（P1b）上线、users 列表分页信封在 M4（第九轮修滞后——本行与 §7 M4 行原残留「接口收紧在 M4」的旧说法，第八轮已定 M2.5 而迁移文漏改）。

## 修订记录

**2026-09-20 查漏补缺轮**（方案 × 代码逐条核对后修订，引用行号均已回读核实）：

1. **镜像列方案否决，改生成列 + 表达式索引**（§2.2）：初稿的「六列提升为应用维护的真实列」与 commit `6790ce10`（2026-08-20）退役 11 个镜像列、确立 payload 单一权威的既定决策正面冲突——应用维护投影列会复活双源漂移病（同期被删的 lastRunStatus/lastRunAt 假列即前车之鉴）。改为 `GENERATED ALWAYS AS (payload #> …) STORED` 生成列（DB 写入时自算，结构上无第二权威）+ system/tags 的 GIN 表达式索引；同时纠正字段类型（priority 是 int 0-3、system 是 list[str]，非初稿所写的 VARCHAR）。**（本条的「否决」结论在第二轮被推翻——见下；字段类型纠正保留有效。）**
2. **execution_rows 对齐真实行形状**（§2.2）：JSONL 是事件流（同 seq 后行覆盖前行），终态需折叠；行字段为 seq/datasetId/injectionId/rowIndex/rep/status/caseDir/startedAt/finishedAt，初稿草拟的 ok/failed/duration_ms/error 不存在，删去；ETL 导入复用 `_replay_rows` 折叠逻辑。
3. **schema 管理双路径**（§2.1）：PG 环境 lifespan 停用 create_all、部署走 alembic upgrade，缺 revision 拒启；CI 全量 PG 测试作两路径漂移防线。**（第三轮推翻：双路径会让本地库重演 batch_id 式漂移，已改统一 alembic——见第三轮第 3 条。）**
4. **密钥前置检查**（§3.2）：Fernet 密文跨库可解密前提 = FERNET_KEY 固定；备份文件含密文同级保管。
5. **PG 备份策略**（M0）：pg_dump 定时 + 保留策略 + volume 备份，进运维 runbook。
6. **M2 列表消费面清点**：现 `Scenario` DTO 含全量 steps，详情页统计/picker/对话框/工作台四卡都吃列表行，退位需逐一改道。
7. **M4 auth 引用增量化**：`/api/auths` 每次调用全表扫全部场景+方案 payload（`auth_references._scan_scenario_refs`），改派生表或失效缓存。
8. **M4 关注页服务端数据源**：store 退位后 `?starred=true` 服务端过滤补位；M5 关注上限 20 加服务端 409 兜底。
9. **已核实不改**：rerun 不依赖 scenario_snapshot（用 config_json 重建 + 现查场景），拆 `execution_snapshots` 表成立；`starred` 已是服务端读时投影（`scenario_store.py:413`），user_stars 替换对前端透明。

**2026-09-20 第二轮（用户澄清历史口径后修订）**：

1. **镜像列恢复，生成列方案撤销**（§2.2）：用户厘清 6790ce10 退役镜像列的真实动因——当时优先做 composer 与 plate 的结构归一化，直读 payload 所见即所得最省心；且 SQLite 上镜像列换不来查询收益。**是阶段性取舍，不是对镜像列的永久否决**；PG 阶段做镜像列是既定路线允许的。第一轮把权宜之计误读成了架构原则，现已纠正。设计回归真镜像列 + 三道防漂移护栏：① 单一写入者（本轮核实：payload 写路径全部收口在 `scenario_store.create/update/copy_scenario`，适配应用也走 `scenario_store.update`，无旁路）；② `reconcile_scenario_meta.py` 幂等对账进 preccheck/CI；③ 读侧不设「列缺失回读 payload」分支。生成列的否决理由同步修正为技术不适配（default 归一化写不进不可变表达式、TEXT[] 无法从 jsonb 生成、双方言渲染），非「违反既定决策」。

**2026-09-20 第三轮（基于镜像列恢复版全文复查，引用均回读核实）**：

1. **数组列方言策略补齐（§2.2）**：SQLite 没有 TEXT[]/GIN，「投影列让本地库同构受益、无方言分支」只对标量列成立。system/tags 定为 JSONB（PG）/JSON（SQLite）单列，包含判定与 facets 收敛到唯一 helper 对（PG `@> '["x"]'::jsonb` + GIN、`jsonb_array_elements_text` 做 facets；SQLite Python 兜底）。权衡记录同步改写为诚实版本：JSONB 投影下生成列技术可行，不选的真实理由是归一化与 `_meta_from_row` 单一口径 + 镜像列路线已定。
2. **镜像列集合补 author（§2.2/§4.2）**：FilterPopover 的作者筛选用 `meta.author`（`filters.ts:88`），六列集合漏了它——补为第七列并加索引；列表参数同步补 author / updatedWithin（FilterPopover 的既有维度，初稿漏收）。
3. **alembic 统一两方言（§2.1，推翻第一轮的「双路径」）**：「PG 走 alembic、SQLite 留 create_all」会让本地库在每次模型变更后重演 batch_id 式漂移（create_all 不 ALTER 既有表）。改为两方言统一 alembic（SQLite batch 模式、启动自动 upgrade），create_all 仅测试建库。
4. **execution_rows 改「每行终态即 upsert」（§2.2）**：原「等 finalize 批量落」在崩溃窗口会丢已终态行，且 JSONL 停写后无兜底。
5. **ETL 补 owner_id=0 映射（§3.3）**：`composer_scenarios.owner_id` 模型 default=0，历史行携带 0 会被 PG FK 拒收——ETL 映射 NULL + owner_name 回填，preccheck 清点。
6. **杂项**：`?fields=options` 的可见性口径写明（member=自己+public、admin=全量）；auths metaText 计数改服务端聚合；风险清单补「单进程部署约束不变」。
7. **再核实（护栏加固）**：`ComposerScenario(` 构造仅存在于 scenario_store（模型定义除外），路由与适配全部走 store（`routers/scenarios.py:209/309/371`、`adaptation_service` 走 update）——「单一写入者」成立；`priority` 为必填 int 0-3 无默认、`_meta_from_row` 只修 module/system 缺省，投影提取直接复用该函数即无第二口径。

**2026-09-20 第四轮（用户复核后定稿：生成列方案）**：

1. **生成列定稿，推翻第二轮的镜像列 + 护栏**（§2.2）：用户指出的关键事实经回读核实成立——`scenario_store.create()`/`update()` 都把 `ScenarioMeta` 校验归一后的 `server_owned.model_dump()` 写回 `definition.meta`（`scenario_store.py:56-70`、`:120-146`，update 写前还修复空 module/system），**落库 meta 恒为归一后形态，SQL 提取 1:1 复现 Python 读取，「两套提取逻辑要保持一致」的前提性顾虑不存在**。改为 STORED 生成列：双写漂移从「门禁防范的风险」变「物理上不可能」——无写入侧维护代码、无 backfill、无 CI 一致性断言、scenario_store 一行不改；第二轮的三道护栏与 `reconcile_scenario_meta.py` 全部撤销。物化理由补记：大 payload 会被 PG TOAST，表达式索引在列表查询逐行 de-TOAST，STORED 把值物化进主元组、列表扫描不碰 payload——物化是对的，物化者选数据库。代价如实入案：表达式变更只能 DROP+ADD 列；数组列用 jsonb + `GIN jsonb_path_ops`，不为 TEXT[] 造 IMMUTABLE 转换；遗留修复（空 module/system）不进表达式，ETL 一次性写回 payload，迁移后删 `_meta_from_row` 修复分支。
2. **三处类型硬错修正**（对齐 `schemas/scenario_composer.py:38-57`）：name 上限 64（初稿 255）；system 是 list[str] 数组列（jsonb）；priority 是 int 0-3。其中 system 若按标量建列，第一条多系统场景即被截断/报错，而多系统是常态。
3. **阶段重排**（§7）：新增 **M1 列表减负**置于切换之前——投影 SELECT（响应不含 payload）+ 分页 + store 退位三件事**不依赖任何 schema 改动**，现行 SQLite 上即可上线，浏览器内存压力不等停服窗口；原 M1-M5 顺移为 M2-M6，M2（切换）只剩「数据搬对了没有」一个失败维度。两文互锁的阶段引用已同步改（M1→M2、M3→M4、M5→M6）。
4. **原则改写而非废除**（§0 新增原则 6）：「payload 是唯一可写源；派生态可以物化，但必须由数据库或可重放的纯函数生成，不得由应用写入侧维护」——endpoint_ref_index、catalog_versions 与本次生成列同在这条原则之下，不为特例开口子。

**2026-09-20 第五轮（用户三点复核后修订，引用均回读核实）**：

1. **时区：诊断收窄 + 波及面补全 + 双路径入案**（§2.1 / §8 风险 2）：破口收窄到 `catalog_versions.synced_at` 的 `server_default=func.now()`——DB 生成值不经 `_utcnow()`，SQLite CURRENT_TIMESTAMP 恰为 UTC 所以无恙，PG `now()` 按会话时区渲染偏 8h；`adaptation_service.py:100-118` 的 `_parse_dt`/`_utcnow` 是故意 naive-UTC、模块内自洽（`:168` 的 `updated > stamp.synced_at` 是结构修法下会 TypeError 的比较点），**该文件补进波及面（初稿漏列）**。战术修法（一行 `(now() at time zone 'utc')`、零代码改动、仓内审计 P2 同解）作为备选入案，结构修法维持定案。无论路径都做：`ALTER DATABASE … SET timezone='UTC'` + 遍历 `Base.metadata` 的元数据断言测试（防以后新列回退）。
2. **ETL 借 PG 两个特性放松**（§3.3）：FK `DEFERRABLE INITIALLY DEFERRED` → 事务内插入顺序自由、commit 统一校验，「按依赖序逐表搬」删除；存量可疑表（owner_id=0 批）`ADD CONSTRAINT … NOT VALID` + 导入后 `VALIDATE CONSTRAINT`，可疑行不打断 ETL；`scenario_endpoint_refs` 不导入、切换后 rebuild（顺带补齐存量锚点）写进步骤。
3. **FK 动作总原则进 schema 而非注释**（§2.1）：「Python 删得到的，NO ACTION DEFERRABLE；Python 删不到的，CASCADE」——FK 从第二套级联变校验器，Python 漏删子表 commit 当场报错而非被 DB 悄悄补掉。全量归属 FK 映射表落 §2.1；service_aliases 的「SET NULL 静默把个人默认变团队共享」陷阱因改 NO ACTION 从根上消失；user_stars 落表后 `scenario_store.delete:180` 的 `stars.remove_item()` 可删，Python 显式级联收缩到只剩 case 目录清理——双级联重叠面迁移后趋近于零。

**2026-09-20 第六轮（用户四点复核后修订，代码断言均已回读核实）**：

1. **executions.owner_name 回填源纠偏**（§3.3）：config_json 的键没有人名（runId/scenarioId/dataSetIds/…），只能 join users 回填；**已注销属主的历史行恰恰 join 不到**——那些行 owner_name 留空、列表显示「已注销用户」，写明为设计内降级而非回填缺口。scenario_name 同理（审计 P11：3 行指向已删场景）。
2. **stars.json 导入的类型陷阱**（§3.3）：JSON 对象键一律字符串，必须 `int(k)`——不写则轻则类型报错、重则零行静默导入；对账项加「user_stars 导入行数 vs 文件内计数」。
3. **PG 测试隔离单列为 M0 工作项**（§3.4）：现行「每测试临时 SQLite 文件」范式在 PG 上不成立，schema-per-test（倾向，语义最贴近、改动集中）vs 事务回滚（与 dispatcher 后台线程的独立 session 相冲）都要求重写 fixture——初稿「加 TEST_DATABASE_URL 即可」低估了这步；M0 门禁补「选型定案 + PG 上跑通冒烟子集」。
4. **M6 显式列入** `scenario_store.delete:180` 的 `stars.remove_item()` 删除（FK CASCADE 接管）——§2.2 第二轮已述，阶段清单同步补齐。

**2026-09-20 第七轮（用户「评估这些问题」五点 + 遗留四点 + 小点，代码断言均已回读核实）**：

1. **生成列 × 统一 alembic 交叉验证欠账标记**（§2.2 方言段 + M0）：SQLite 的 `ALTER TABLE ADD COLUMN` 不能加 STORED 列（只允许 VIRTUAL），第三轮与第四轮的决策各自正确、合在一起未验证——alembic batch 的拷贝步是否自动排除 `Computed` 列不替它断言；M0 十分钟最小验证，退路 = PG STORED / SQLite VIRTUAL 方言分叉。
2. **PG 启动从「自动 upgrade」改「只校验不迁移」**（§2.1）：自动 upgrade = 无人值守、无备份的 DDL，日常部署绕过切换纪律；改比对 current/head、不一致拒启——漂移照样不可能，DDL 永远人在带备份窗口执行。
3. **preccheck 补 payload 抽出面逐行校验**（§3.2 / §8 风险 3）：生成列把读时修复变写入即拒，meta 超长/类型不合规的行会让 ETL 半途炸——逐行过 `ScenarioMeta` 打清单，与修复写回同步做。
4. **M1 措辞修正为「响应投影」**（§7）：Python 过滤仍需全表加载 payload（`_passes_filters` 吃 `_meta_from_row`），M1 收益只在浏览器侧；门禁明确不含「DB 扫描下降」（那是 M3 的）。
5. **execution_rows 保留策略定案**（§2.2）：行是台账（默认全保、参数化远期）、工件是易耗品（照旧 14 天）；`case_dir` 为软引用，详情页对已清扫工件显示「已过期清扫」非死链。
6. **FK 判据措辞修正**（§2.1）：「删得到/删不到」→「该不该管」——user_stars.scenario_id 是 CASCADE 正例（Python 删得到但**不该管**，无业务语义），旧措辞会推出错误结论。
7. **杂项**：测试基线 622/630 两数并存，M0 实测钉死；board_cards 作者注销后转只读（现状 `_get_owned` 连 admin 都 403——`services/board_cards.py:33-37`，补 admin 旁路一行接管）。

**2026-09-20 第八轮（用户「第七轮改了一处漏另一处 + 新发现」复核后修订，代码断言均已回读核实）**：

1. **修同轮编辑残留两处**（§7）：M2 内容栏的「create_all 替换为统一 alembic 自动 upgrade」更新为第七轮的启动分叉决策（原句反向引用已改掉的 §2.1，同文冲突）；「顺序依据」段的「投影 SELECT」随 M1 措辞改「响应投影」。
2. **债 4 只消除一半，补刀 config_json**（§2.2 / M1）：`ExecutionOut.config: dict`（`schemas/execution.py:19`）把 config_json 整列随每行列表发给前端——拆表只拆了快照；且它正是权限论证收窄后的敏感面（凭证引用面）。列表 SELECT 排除 config_json、ExecutionOut 列表形态去 config（详情保留），并入 M1 响应投影。
3. **service_aliases 的 SET NULL 改记为「显式推翻模型既定意图」**（§2.1）：模型注释明写「注销时置空（共享化）」（`models/service_alias.py:42-45`）——推翻理由 = FK 从未生效、意图从未执行、共享化该由人显式决定；原「避开陷阱」措辞会让后来者以为方案没看见那行注释。
4. **权限 P1 拆包，新增 M2.5**（§7）：停服窗口只同车 P1a（role 列 + ETL 映射 + is_admin 派生，零代码风险）；P1b 整包后挪 M2.5——execution_finished 要在 dispatcher 终态收口新加写入点，切换当天不动执行链路；门禁「只剩数据搬对了没有」从口号变成真话。
5. **铃铛空窗消除**（M2.5）：按 type 通知开关与铃铛同批（user_prefs 表随 M2 DDL 已建）——开关先于吵闹型通知上线。
6. **execution_rows 量级从假设变实测**（§3.2/§2.2）：preccheck 数出 JSONL 折叠后的总行数；百万级则「默认全保」改「上线即带保留参数」。
7. **行号引用补目录**：`_get_owned` = `services/board_cards.py:33-37`（第七轮漏了目录前缀）。

**2026-09-20 第九轮（用户「runbook 断点 + 拆包新缝 + ETL 写法 + 残留」十点复核后修订）**：

1. **切换链补建表断点**（§3.3）：第七轮把 PG 启动改为只校验后，整条链路再无一步创建 schema——补「空 PG 库 `alembic upgrade head`」为 ETL 前的人工步骤，起服只校验。
2. **stamp 与 revision-建库二选一，定后者**（§0 原则 4）：第一个 revision 即全量新 schema = 天然 baseline，「切换完成后 baseline stamp」作废——库由 revision 建起后再 stamp 会把已执行 revision 标错；「没 revision 不合入」不变。
3. **演练数据源钉死**（§3.3/§7 M2）：必须用生产 `app.db` 副本——ETL 唯一失败源是存量数据，开发库一条都验不了，跑通≠门禁过；演练与正式两份迁移报告逐项对比（行数/生成列抽样/stars 计数），不一致本身就是信号。
4. **回滚零代码回退的成立条件写明**（§3.3/§2.1/§2.2）：role 改「生成列方向翻转」——M2 期间 role 是 is_admin 的 STORED 生成列、代码零读零写（替代运行时「有 role 用 role」双向探测：那要条件化 mapper 配置，脆；列不进 models 即物理不依赖）；生成列消费在 M3。存量 pre-alembic 库（含回滚快照）启动跳过 upgrade 直跑。
5. **冒烟补三条高危面**（§3.3）：①生成列筛选对拍（生成列错了页面照开、只是筛选悄悄不对，「页面能开」验不出）；②删测试用户走通（FK 校验器 + 最小级联端到端）；③旧执行详情「已过期清扫」显示（起服即扫、首启批量触发）。
6. **最小显式级联从 M2.5 拎回 M2 同车**（§2.1 FK 表/§7 M2）：M2 起 FK 真生效且凭证池/常量/个人别名三张 NO ACTION 表在场，不带这段代码则 M2→M2.5 之间删号必被拦死——拆包要挡的是通知写入点进 dispatcher，不是这段纯端点代码；个人别名保守默认=删除，转共享留 P2。
7. **case_dir 软引用落为工作项**（§2.2/M1）：「已过期清扫」分支是待写前端代码非既有行为；清扫今天就跑（`run_dispatcher.py:338`），切换首启即批量触发，进 M1。
8. **ETL INSERT 排除全部生成列 + PG 侧写法入 M0**（§3.3/M0）：列清单带上生成列 PG 当场拒 `GENERATED ALWAYS`（composer 七列 + users.role）；空表试插与 SQLite batch 交叉验证是同一坑的两侧；is_admin→role 映射改由生成表达式自算。
9. **setval 用 `pg_get_serial_sequence`**（§3.3/§8 风险 4）：不手拼 `<table>_<col>_seq`（实现细节非契约，命名例外比漏表更难发现）——checklist 写死遍历 `information_schema` 全部 IDENTITY 列逐列取名。
10. **互锁残留两处修平**（§7 M4 行/文末附表）：users 接口收紧从 M4 改随 M2.5（第八轮已定，迁移文漏改——互锁文档里重复比漏写更危险：一边以为另一边做了，或两边各做一遍）。

**2026-09-20 第九轮补遗（M0 交叉验证闭环：进两案、出一案）**：

11. **users.role 不与 composer 七列假定同构**（§7 M0 ②）：同为「带数据表上加 STORED 生成列」，但 role 在 M2 关键路径上（回滚安全整个压在它零读零写上）——单列同验，验 users 表自身的 batch 路径；布尔 CASE 比 JSON 抽取简单，简单≠免验。
12. **出程验证补齐：生成列→普通列翻转**（§7 M0 ③/§2.2/§7 M2.5）：M2.5 权威翻转 = PG 原生 `DROP EXPRESSION` + SQLite batch「读生成列→写普通列」重建——原验证项只覆盖建（进），出程没验，等于只验了能不能进、没验能不能出；补双方言出程 + 逐行值相等断言（SQLite 若走 VIRTUAL 分叉，生成列无存量数据、拷贝全靠现算）；跑不通则 SQLite 翻转退化为手写重建 SQL（CREATE/INSERT SELECT/DROP/RENAME）。
