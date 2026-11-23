# PG 迁移与权限域 — 开发计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> 状态：开发计划（2026-09-21）。本计划从两份九轮评审定稿的设计方案**直接推导**，不重新讨论任何已拍板的设计决策——设计理由、否决史、修订记录一律以方案原文为准；本文只回答「按什么顺序、动哪些文件、过什么门禁」。

**Goal:** 完成平台从 SQLite 到 PostgreSQL 的直切迁移与检索/聚合/分页后移（迁移方案 M0-M6），同车落地三级角色权限域与通知中心（权限方案 P1a/P1b/P2）。终态：PG 单库 + alembic 必经 + Page 信封全站统一 + member/operator/admin 三级权限 + 站内通知。

**Architecture:** 见两份方案。一句话：payload 是唯一可写源（投影用 STORED 生成列由 DB 自算）；FK 是校验器不是级联器（Python 该管的 NO ACTION DEFERRABLE、机械的 CASCADE、台账的 SET NULL+快照）；权限矩阵后端依赖为边界、前端守卫只是 UX；通知走 30s 轮询铃铛不上长连接。

**Tech Stack:** 后端 Python 3.11+（FastAPI + SQLAlchemy 2 async + pydantic v2 + alembic + asyncpg/psycopg + pytest）；前端 Vue 3 `<script setup>` + TS + vitest；PG 16（docker compose）。plate **零改动**（内存注册表，与迁移无关）。

**Spec（最高约束，实施不得偏离）：**

- [PostgreSQL迁移与后端化-设计方案](../PostgreSQL迁移与后端化-设计方案/PostgreSQL迁移与后端化-设计方案.md)（下称**迁移方案**，§ 编号均指该文）
- [用户权限与用户管理-设计方案](../用户权限与用户管理-设计方案/用户权限与用户管理-设计方案.md)（下称**权限方案**）

---

## Global Constraints（两文原则合并，全程有效）

1. **直切不双写**：无双写双读期，切换窗口 = 停服 → 备份 → `alembic upgrade head` 建表 → ETL → 切 `.env` → 起服 → 冒烟（§3.3）。
2. **alembic 从此必经**：baseline = 第一个 revision（携带 §2 全部 DDL），**无 stamp 步骤**；此后任何 schema 变更没有 revision 不合入（§0 原则 4）。启动行为分叉：SQLite/测试自动 `upgrade head`（batch 模式）；**PG 启动只校验不迁移**（current ≠ head 拒启）；存量 pre-alembic 库（无版本表且已有业务表）跳过 upgrade 打告警直跑（§2.1）。
3. **payload 是唯一可写源**：派生态只能由数据库（STORED 生成列）或可重放纯函数生成，**不得由应用写入侧维护**（§0 原则 6）。
4. **FK 动作判据是「该不该管」**：有业务处置语义的删除 → NO ACTION DEFERRABLE（Python 显式管，漏删 commit 当场报错）；机械随主行消失 → CASCADE；台账 outlive 用户 → SET NULL + 姓名快照列。全量映射表见 §2.1，**逐行照抄，不自行裁量**。
5. **时区结构修法**：全库 TIMESTAMPTZ + Python 全链 aware；`ALTER DATABASE gimbal SET timezone='UTC'`；元数据断言测试防新列回退（§2.1）。
6. **单进程部署不变**：禁多 worker、禁 `--reload`（活跃行级状态在内存 `_row_states`、调度器是进程内线程/子进程，§8 风险 10）。PG 不改变这一点。
7. **权限边界**：后端依赖才是边界（`require_role`），前端守卫只是 UX（权限方案 §0.4）；role 不进 JWT，每请求查库；执行记录对 admin 也 owner 硬隔离（不变量）；「字段面可见、值面不可见」——`before_json` 永不出 API（权限方案 §0.3/§1.2）。
8. **凭证永不跟随**：任何数据传递通道（复制/转让/批次适配）不得携带或暴露凭证密文/明文（权限方案 §4.1）。
9. **回归底线**：现有测试套件只增不减全绿（基线数 M0 实测钉死）；`vue-tsc --noEmit` 绿；alembic revision 双方言（PG / SQLite batch）都必须可执行。
10. **明确不做清单**照单执行（迁移方案 §9、权限方案 §8）：不双写、不上 ES/tsvector、keyset 分页不做、CarryConfig 不分页、本地默认库仍 sqlite、不做 superadmin/IM/per-user 共享/审批流/匿名发布/邮箱通知、工作台 UI 偏好本期不迁服务端。

**工作目录与分支**：后端任务在 `src/gimbal-platform/backend`；前端任务在 `src/gimbal-platform/frontend`；compose/运维脚本在仓库根。一个里程碑一条分支一个 PR（M0、M1 可各自独立合并，互不依赖）；M2 起严格串行。当前基线分支 `feat/frontend-signal-refactor`。

---

## 里程碑总览与调度

| 里程碑 | 一句话 | 前置 | 核心门禁（详规见各节） |
|---|---|---|---|
| **M0 准备** | PG 环境、测试隔离选型、生成列×batch 三案验证、基线钉死 | 无 | sqlite 全量绿（实测基线）；隔离选型定案 + PG 冒烟子集绿；三案验证有结论 |
| **M1 列表减负** | 响应投影 + Page 信封 + store 退位（**现行 SQLite 上线**） | 无（与 M0 并行） | §6.3 场景页验收；无全量场景请求；门禁**不含** DB 扫描下降 |
| **M2 表定稿+切换** | §2 全部 DDL 进 alembic baseline；preccheck/ETL/演练/停服切换；**P1a 同车** | M0、M1 | PG 全量 pytest 绿；逐表对账零差异；冒烟含三条高危面 |
| **M2.5 权限上线** | **P1b 整包**：require_role / 前端 hasRole / 通知+铃铛 / role 权威翻转 / 接口收紧 | M2 | 三角色验收口径全过；铃铛 + type 开关可用 |
| **M3 检索 SQL 化** | 生成列上 SQL 端过滤/排序/分页 + facets | M2 | q/筛选全走 SQL；facets 计数与全量一致 |
| **M4 分页规范化** | Page 信封铺其余端点 + P1 批页面 | M2.5、M3 | §6.3 全部验收 |
| **M5 聚合轮询后移** | 四个聚合端点 + 轮询治理 + P2 批页面 | M2 | 关注页/工作台网络请求计数达标 |
| **M6 收尾** | execution_rows 转正 + user_stars 上线 + 旧物退役 | M2 | 行级回放分页可用；stars.json 不再被读 |
| **P2 权限收尾** | /profile、删除处置流、审计落码、前端测试 | M2.5（排在 M4 后做） | 权限方案 §7 验收口径 |

调度注记：M0 与 M1 **并行推进**（M1 不依赖任何 M0 产物）；M2 停服窗口只做数据搬运 + P1a 两段零风险代码；M2.5 紧随切换上线（不依赖停服）；P2 是切换后独立小迭代。M3-M6 依次铺开，其中 M3 依赖 M2 的生成列。

---

## M0 准备（不动业务代码）

### Task M0-1: PG 环境与驱动

**Files:**
- Create: `compose.pg.yml`（仓库根；pg16 + healthcheck + named volume，**生产同文件**）
- Create: `compose.pg.yml` 同目录 `pg-init/01-timezone.sql`（`ALTER DATABASE gimbal SET timezone='UTC'`，§2.1 钉死会话时区）
- Modify: `src/gimbal-platform/backend/pyproject.toml`（+`asyncpg` 运行时驱动）
- Modify: `src/gimbal-platform/backend/requirements-platform-constraints.txt`（asyncpg、psycopg[binary] 钉版；psycopg 供 ETL 同步 engine 用）

**Steps:**

- [x] 写 `compose.pg.yml`：pg16、healthcheck、init 挂载时区 SQL
- [x] 依赖入列并钉版；`docker compose -f compose.pg.yml up -d` 本机起库验证 healthcheck 通过
- [x] 用 venv Python 连通性冒烟：`asyncpg` 直连 + `SELECT 1`

### Task M0-2: config 分支与 engine 参数

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/config.py`（`DATABASE_URL` 默认保持 sqlite；`.env` 切 pg 是显式 opt-in）
- Modify: `src/gimbal-platform/backend/app/core/db.py`（engine 补 `pool_size=10, max_overflow=20, pool_pre_ping=True`——**仅 PG 方言生效**，aiosqlite 传这些参数会报错，按 URL 前缀分支）

**Steps:**

- [x] engine 构造按 dialect 分支补 pool 参数；sqlite 路径行为不变
- [x] 起服冒烟：sqlite 默认路径零变化；临时 `.env` 指 PG 路径起服能连上（表还没有，init_db 此时仍 create_all——**M0 阶段不切 PG 跑业务**，验证完即切回）

### Task M0-3: PG 测试隔离选型与 conftest 改造（§3.4，独立工作项，M2 门禁压在它上）

**Files:**
- Modify: `src/gimbal-platform/backend/tests/conftest.py`（现行范式：每测试临时 SQLite 文件 + create_all + monkeypatch 全局 engine——**PG 上不成立**）
- Create: 选型结论记录（本文件附录或独立 `tests/PG_ISOLATION.md`）

**Steps:**

- [x] 定选型：倾向 **schema-per-test**（每测试 `CREATE SCHEMA` + `set search_path`，结束 DROP——语义最贴近现行独立库、不碰被测代码）；事务回滚路线与 run_dispatcher 后台线程的独立 session 相冲，除非 schema-per-test 验证失败否则不选
- [x] 改造 `fresh_db` fixture：`TEST_DATABASE_URL` 存在时走 PG schema-per-test，否则维持 sqlite 临时文件（默认路径不变，双方言自律）
- [x] PG 上跑通冒烟子集（挑 `test_users.py` + `test_executions.py` + `test_scenario_visibility_and_copy.py` 三件，覆盖 auth/owner 过滤/复杂 store）
- [x] 结论写档：选型、fixture 形态、已知限制

### Task M0-4: 生成列 × alembic batch 交叉验证（三案齐：进两案、出一案；§2.2 交叉验证欠账 + §7 M0）

**Files:**
- Create: `src/gimbal-platform/backend/scripts/m0_verify_computed.py`（一次性验证脚本，跑完留档结论）

**Steps:**

- [x] **案① 进/composer 七列**：SQLite 上对一张带数据的表用 alembic batch 加 `Computed(..., persisted=True)` 跑通（batch 走建新表→拷数据→换名，拷贝步是否自动排除生成列**不替 alembic 断言**，实测为准）；跑不通 → 退路定案：PG STORED / SQLite VIRTUAL 方言分叉（本地量小不要 STORED 性能）
- [x] **案② 进/users.role 单列**：同一个「带数据表上加 STORED 生成列」的坑，但 role 在 M2 关键路径上（回滚安全整个压在零读零写上）——单列同验，不和 composer 七列假定同构
- [x] **案③ 出/生成列→普通列翻转**（M2.5 权威翻转的后半程）：PG 原生 `ALTER COLUMN … DROP EXPRESSION` 跑一行；SQLite 无等价 DDL，靠 batch「读生成列→写普通列」重建，**必须断言逐行值相等**（若案①走了 VIRTUAL 分叉，生成列无存量数据、拷贝全靠现算）；跑不通 → M2.5 翻转 revision 对 SQLite 退化为手写重建 SQL（CREATE/INSERT SELECT/DROP/RENAME）
- [x] **PG 侧 ETL 写法同批试掉**（同一坑的两侧只验一侧不算验证完，§3.3）：空表 + 一行 payload 直插——列清单**排除**生成列确认 PG 自算；**故意带上**生成列确认报 `cannot insert into column … GENERATED ALWAYS` 的形态
- [x] 三案结论回写本计划附录

### Task M0-5: 运维 runbook 与基线钉死

**Files:**
- Create: `src/gimbal-platform/docs/runbook-pg.md`（备份策略：`pg_dump` 每日定时 + 保留 N 份 + compose volume 备份说明；禁 `--reload` 与禁多 worker 并列为硬约束；切换日 runbook 骨架，M2-T8 填充）
- Create: 基线记录（写进本计划附录：sqlite 全量 pytest 的实测通过数——**仓内审计 630 与前稿 622 两数并存，M0 实测为准**）

**Steps:**

- [x] 后端 sqlite 全量 pytest 跑一遍，实测数写档
- [x] runbook 骨架落盘

**M0 门禁**：sqlite 全量绿（基线实测钉死）；PG 隔离选型定案 + 冒烟子集绿；生成列×batch 三案齐（进×2 + 出×1）有结论；compose PG 可用；runbook 骨架在。**→ 2026-09-21 全项达成（基线 630 / 冒烟 27 绿 / 三案 10/10 / PG 16.15 healthy UTC）。**

---

## M1 列表减负（切换前上线，现行 SQLite；与 M0 并行）

> §7 M1：这是「**响应投影**」不是「查询投影」——服务端查询仍全表加载 payload（`_passes_filters` 吃 `_meta_from_row`），M1 收益只在浏览器侧；SQL 端过滤排序是 M3 的事，**门禁不含 DB 扫描下降**。

### Task M1-1: 场景列表响应投影 + Page 信封

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/scenarios.py`（列表端点）
- Modify: `src/gimbal-platform/backend/app/services/scenario_store.py`（列表查询 + Python 过滤保留，分页在 Python 侧切片）
- Modify: `src/gimbal-platform/backend/app/schemas/`（列表形态 DTO：不含 payload/steps，仅 meta 摘要 / stepCount / starred；Page 信封 `{items,total,page,page_size}`）

**Interfaces:**
- Produces: `GET /api/scenarios?q=&page=1&page_size=20&sort=&visibility=&system=&module=&priority=&tags=&author=&updatedWithin=` → Page 信封；`page_size` 上限 100 默认 20；排序白名单（场景 `updated_at DESC`）首期服务端定死；`q` = 域内白名单字段子串匹配（对齐现状 `.lower().includes` 口径）
- Produces: `GET /api/scenarios?fields=options` 轻量元数据形态（仅 id/name/visibility/owner；可见性口径 member=自己+public、admin=全量）——供选择器与名称映射

**Steps:**

- [x] 先写失败测试：列表响应不含 `payload`/`steps` 键；信封字段齐；`fields=options` 形态正确；分页切片正确（Python 过滤后切片，总数 = 过滤后全量 count）
- [x] 实现响应投影与信封；过滤/排序暂留 Python（分页后每页数据量可控，§7 M1）

### Task M1-2: ExecutionsList 翻页补齐 + 列表去 config

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/executions.py`（+offset 翻页、total 补齐；q 暂留客户端——SQL 下推在 M4）
- Modify: `src/gimbal-platform/backend/app/schemas/execution.py`（`ExecutionOut.config` 列表形态去除，详情页保留——债 4 的另一半，`config_json` 是凭证引用面敏感列）

**Steps:**

- [x] 先写失败测试：列表行无 `config` 键、详情有；`page/page_size/total` 信封齐；超 200 条不再静默截断
- [x] 实现：列表 SELECT 排除 `config_json`

### Task M1-3: 前端三件公共设施

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/ui/pagination/`（把 `components/scenario-lib/ListPager.vue` 升格为 ui 级；props: page/pageSize/total/siblingCount；emit update:page；禁用态/省略号/总数文案/键盘可达——**全站唯一分页实现**）
- Create: `src/gimbal-platform/frontend/src/composables/useServerList.ts`（统一服务端列表范式：入参 fetch 函数 + 响应式参数；产出 items/total/loading/error/page/setPage/query/setQuery；内置 300ms 防抖；参数变化自动重置页码；翻页后 scrollTo(0) 可选）
- Create: `src/gimbal-platform/frontend/src/utils/debounce.ts`（全站第一个公共防抖，收编 FieldStateSearch 的内联实现）
- Modify: URL query 同步（`q/page` 写回 `router.replace({ query })`，replace 不进历史；既有深链 `?batch_id/?path/?rows=failed` 原样兼容）

**Steps:**

- [x] ui/pagination 组件 + 单测
- [x] useServerList + debounce + 单测（防抖、页码重置、URL 同步）

### Task M1-4: 场景 store 退位与消费面清点

**Files:**
- Modify: `src/gimbal-platform/frontend/src/stores/scenario-composer.ts`（只存当前页 + options 形态元数据缓存；去掉「store 空就全量 fetch」兜底——`ScenarioDetailView.vue:334`；mutation 后只作废当前页重拉）
- Modify: `src/gimbal-platform/frontend/src/views/ScenarioDetailView.vue`（按 id 拉单条详情；断言统计吃详情而非列表行）
- Modify: Runner picker / OpConstructDialog / 工作台四卡 → 改走 `?fields=options` 或详情端点（§7 M1 消费面清单）
- Modify: `src/gimbal-platform/frontend/src/views/ScenariosMine.vue`、`ScenariosPublic.vue`（接入 useServerList + ui/pagination）

**Steps:**

- [x] 逐消费面改道（详情统计 / picker / 对话框 / 工作台四卡）
- [x] store 兜底分支删除；确认无「不带分页参数的 GET /api/scenarios」请求

### Task M1-5: 「已过期清扫」前端分支

**Files:**
- Modify: 执行详情行级表组件（`case_dir` 软引用消费面）

**Steps:**

- [x] 行的 case 工件被 14 天清扫后，详情页显式显示「已过期清扫」而非死链 404/500——**这是待写的前端代码不是既有行为**（§2.2 第九轮注记：切换后首启即批量触发，必须切换前就位）

**M1 门禁（2026-09-21 达成）**：后端 638 passed（基线 630 + 8 投影测试）;前端 124 文件 / 1082 测试全绿 + vue-tsc 0 错误;浏览器验收——搜索 FC → 地址栏 `?q=FC`、刷新状态不丢、服务端过滤生效(4 行→3 行)、变量列 varCount 正常。§6.3 场景页验收——造 45 条场景，搜索+筛选+翻页 → 地址栏 `q=…&system=…&page=2` 刷新不丢；网络面板确认只拉当前页（无全量 GET /api/scenarios 不带分页参数）；ExecutionsList 超 200 条不截断且 total 正确；浏览器内存三件事（①列表不回 payload ②分页 ③store 退位）不等停服窗口全部落地。**门禁不含 DB 扫描下降。**

---

## M2 表定稿 + 切换（停服窗口；P1a 同车）

> §7 M2：M1 前置 + P1 拆包后，停服窗口的结构性风险只剩「数据搬对了没有」；同车代码仅 P1a 两段（role 生成列零代码 + 删除端点最小级联纯端点代码）。**切换当天不动执行链路。**

### Task M2-1: 模型全面改版（§2 逐表设计落 models）

**Files:**
- Create: `src/gimbal-platform/backend/app/models/user_pref.py`、`notification.py`、`audit_log.py`、`user_star.py`、`execution_snapshot.py`、`execution_row.py`
- Modify: `src/gimbal-platform/backend/app/models/` 全部既有模型（FK 动作、TEXT 放宽、timestamptz、快照列、partial unique、JSONB）
- Modify: `src/gimbal-platform/backend/app/models/__init__.py`（注册新模型）

**关键落点（照 §2.2 逐表清单，不自行裁量）：**

- [x] **composer_scenarios 七个 STORED 生成列**（name VARCHAR(64)/description/module VARCHAR(64)/author VARCHAR(128)/priority SMALLINT/system JSONB/tags JSONB）——SQLAlchemy `Computed(..., persisted=True)` 映射；索引 `(visibility, updated_at DESC)`、`(owner_id)`、`(author)`、GIN `tags/system jsonb_path_ops`（GIN 仅 PG，方言段处理）；**users.role 不进 models**（生成列方向翻转：代码零读零写、回滚物理安全，§2.2）
- [x] users：`display_name` partial unique `WHERE display_name <> ''`；`password_hash TEXT`；`is_admin` 过渡期保留
- [x] executions：拆 `execution_snapshots`（`execution_id PK REFERENCES … CASCADE, snapshot JSONB`）；`owner_id FK SET NULL` + `owner_name VARCHAR(128)`；`scenario_name VARCHAR(255)` 快照列；`has_scenario_snapshot` 改存在性查询
- [x] execution_rows 新表（字段对齐 `_replay_rows` 折叠后真实行形状：seq/dataset_id/injection_id/row_index/rep/status/case_dir/started_at/finished_at；`UNIQUE(execution_id, seq)`；BIGSERIAL）
- [x] user_stars（`PK(user_id, scenario_id)`，双 FK CASCADE）
- [x] notifications / audit_logs / user_prefs DDL 照权限方案 §3.3/§6（**只建表不上代码**——P1a）
- [x] carry_*（`updated_by` → `updated_by_id` FK SET NULL + `updated_by_name`）、adaptation_*（operator FK SET NULL + 快照）对齐三件套规范
- [x] 全部 FK 动作按 §2.1 映射表**逐行照抄**（NO ACTION DEFERRABLE / CASCADE / SET NULL+快照；`service_aliases.owner_user_id` 改 NO ACTION 是对模型注释「注销即共享化」的**显式推翻**，理由见迁移方案第八轮第 3 条）
- [x] **全库 TIMESTAMPTZ**：所有 DateTime 列 `timezone=True`；`server_default=func.now()` 全部处理（结构修法下不再有裸 now()）

### Task M2-2: naive→aware 时区扫尾（§2.1 / §8 风险 2）

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/adaptation_service.py:100-118`（`_parse_dt`/`_utcnow` 改 aware；`:168` 的 `updated > stamp.synced_at` 混比点显性化）
- Modify: `src/gimbal-platform/backend/app/services/scenario_store.py:450-453`（读侧 replace 删除）
- Modify: `src/gimbal-platform/backend/app/core/timeutil.py`、时长减法、Pydantic 序列化面（专项扫一遍）

**Steps:**

- [x] 全链 aware 化；`catalog_versions.synced_at` 的 DB 生成值在 PG 下按 UTC 渲染（时区已钉死 + timestamptz）

### Task M2-3: alembic 基建 + baseline revision + 启动分叉

**Files:**
- Create: `src/gimbal-platform/backend/alembic.ini`、`alembic/env.py`、`alembic/versions/0001_baseline.py`
- Modify: `src/gimbal-platform/backend/app/main.py`（lifespan 的 `init_db()` create_all 替换为启动分叉）

**Steps:**

- [x] baseline revision 携带 §2 全部 DDL：**第一个 revision 即全量新 schema = 天然 baseline，无 stamp**；双方言（PG 原生 DDL；SQLite 走 batch_alter_table 模式）；partial unique（`uq_run_scheme_default`/`uq_board_cards_root`）在 alembic 里用 dialect 参数重建勿丢（§8 风险 5）；生成列渲染按 M0-4 三案结论（含可能的 STORED/VIRTUAL 分叉）
- [x] 空库（无版本表也无业务表）`alembic upgrade head` 从零建起——**这是切换的人工第一步**
- [x] lifespan 启动分叉：SQLite/测试自动 `upgrade head`；**PG 只校验不迁移**（current vs head 不一致拒启并打印待执行 revision）；pre-alembic 存量库（无 `alembic_version` 且已有业务表）跳过 upgrade 打告警直跑（回滚快照正是此类库）
- [x] create_all 仅保留给测试 conftest 新建临时库

### Task M2-4: 元数据断言测试

**Files:**
- Create: `src/gimbal-platform/backend/tests/test_metadata_invariants.py`

**Steps:**

- [x] 遍历 `Base.metadata` 全部列：断言没有不带 `timezone=True` 的 DateTime、没有裸 `server_default=func.now()`——防的是以后新加的列（§2.1）

### Task M2-5: preccheck 数据体检脚本

**Files:**
- Create: `src/gimbal-platform/backend/scripts/pg_preccheck.py`

**Steps（§3.2 全清单，先出报告不改代码）：**

- [x] 逐表扫描：类型亲和异常、变长列超长（保留的短键逐个对现网 max 长度）、孤儿行（FK 若真生效会被拒的行——`executions.owner_id` 指向已删用户**预期存在**，SET NULL 吸收）、`display_name` 重复
- [x] **payload 抽出面逐行校验**：composer_scenarios 逐行抽 `definition.meta` 过 `ScenarioMeta` 校验（name>64、priority 不可转换等会在 ETL 写入即拒，今天靠 `_meta_from_row` 读时兜——先打清单）；与 module/system 修复写回放同一步
- [x] **execution_rows 量级实测**：现网 JSONL 按 `_replay_rows` 折叠后的总行数写进报告——百万级则 §2.2「默认全保」改「上线即带保留参数」
- [x] 前置配置检查：`FERNET_KEY`/`JWT_SECRET` 非 ephemeral（跨库可解密前提）；旧库备份文件按密钥同等级保管
- [x] 报告人工过目后才允许 ETL

### Task M2-6: ETL 脚本

**Files:**
- Create: `src/gimbal-platform/backend/scripts/migrate_sqlite_to_pg.py`

**Steps（§3.3 全清单）：**

- [x] 双同步 engine（sqlite3 + psycopg）；FK 全 DEFERRABLE INITIALLY DEFERRED（事务内插入顺序自由）；每表一个事务；`func.now()` 列不搬
- [x] **INSERT 列清单显式排除全部生成列**（composer 七列 + users.role——M0-4 已试掉写法）
- [x] 存量可疑表 `ADD CONSTRAINT … NOT VALID` → 导入后 `VALIDATE CONSTRAINT`（典型 `composer_scenarios.owner_id=0` 批：ETL 映射 NULL + preccheck 清点 + NOT VALID 第二道保险）
- [x] 变换：场景 meta 遗留修复一次性写回 payload（复用 `update()` repair 口径；迁移后 `_meta_from_row` 修复分支删除）；`executions.owner_name` join users 回填（join 不到 → 留空显示「已注销用户」，**设计内降级**）；`scenario_name` 同理；`stars.json` 导入 user_stars（**键一律 `int(k)`**）；JSONL 按 `_replay_rows` 折叠导入 execution_rows；naive 时间戳按「视为 UTC」补时区
- [x] **`scenario_endpoint_refs` 不导入**，切换后 rebuild（顺带补齐存量锚点行）
- [x] 收尾：全部 IDENTITY 列 setval——**遍历 `information_schema` 全部 IDENTITY 列、逐列 `pg_get_serial_sequence('表','列')` 取名**，不手拼序列名；重建全部索引/约束
- [x] 校验报告：逐表行数对账 + 每表抽样 50 行规范化 JSON checksum + 生成列抽样与提取函数直接求值比对 + user_stars 导入行数 vs stars.json 文件内计数

### Task M2-7: P1a — 删除端点最小显式级联（纯端点代码，不碰 dispatcher）

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/users.py`（`DELETE /api/users`）

**Steps（权限方案 §7 P1a）：**

- [x] 显式删除：凭证池（auth_sessions）/ 常量（constant_entries）/ 个人别名（service_aliases `owner_user_id`=该用户，保守默认=删除，转共享留 P2 处置对话框）；收藏由 user_stars CASCADE 自收；场景/执行/看板由 SET NULL+快照自收
- [x] 不带这段代码则 M2→M2.5 之间删号被三张 NO ACTION 表当场拦死——M2 起必须同车；完整处置 UI 留 P2
- [x] 测试：删一个带凭证/常量/个人别名的测试号走通（M2 冒烟第 ② 条复用）

#### M2 实施注记(2026-09-21,M2-1~M2-7 落地)

- **legacy-adapt 偏离说明**:设计稿 §2.1 对存量 pre-alembic 库定的「跳过 upgrade 直跑」在 M2 改列名(owner→owner_name 等)后不可行——新代码读不到旧列,跳过即起不来。baseline 落地为**内省识别 + 原地适配**(列改名/补列/新表/快照数据搬家,数据全保留),已在真实 app.db 副本与生产库上实测通过(5 场景保留、55 条快照搬家、生成列从真实 payload 自算)。其余保证不变:alembic 必经、PG 只校验不迁移、空库 upgrade 建库。
- **users.role 仅 PG 建列**:SQLite 本地不建(M2 期间代码零读零写);M2.5 权威翻转 revision 按方言处理。
- **执行快照拆表**(scenario_snapshot → execution_snapshots):dispatch 写入、详情/列表 has_snapshot 存在性查询、快照端点读新表,全部就位;legacy-adapt 自动搬历史数据。
- **验证记录**:sqlite 全量 642 passed(基线 630 + 8 投影 + 4 级联/不变量新测试);PG 冒烟 43 passed(schema-per-test,真实 PG 上含生成列/timestamptz/FK 全表);四条升级路径(空 SQLite/legacy SQLite/空 PG/PG 落后拒启)逐一实测。
- **元数据断言测试**当场抓到 board_cards.updated_at 漏改 —— 防回退价值即时兑现。

## Task M2-8: 演练与正式切换

**Steps（§3.3；runbook 主体在 M0-5 骨架上填充）：**

- [x] **演练 1 次已完成（2026-09-21，生产副本，报告 gimbal-tmp-etl-rehearsal-2026-09-21.json；正式切换前建议再演练一次并逐项对比）——原计划句：演练 ≥1 次（正式切换门禁）：必须用生产 `app.db` 副本**——ETL 唯一失败源是存量数据，开发库一条都验不了；演练与正式各产一份迁移报告**逐项对比**（行数/生成列抽样/stars 计数；不一致本身就是信号）
- [x] 演练时在旧栈采好生成列对拍样本（按 tag 与 system 各筛一次的结果留存）
- [x] **正式切换**：停服 → 备份 `app.db`（只读保留作回滚快照，至少一个版本）→ 空 PG 库 `alembic upgrade head` 建表 → ETL → `.env` 切 pg → 起服（**依旧禁 --reload**）→ 冒烟
- [x] **冒烟含三条高危面**：①生成列对拍（样本与演练留存比对——生成列错了页面照开、只是筛选悄悄不对）；②删测试用户走通全链（FK 校验器 + 最小显式级联端到端）；③打开一条 ETL 前的旧执行详情，已清扫 case_dir 的行显示「已过期清扫」而非死链/500（起服即扫 `run_dispatcher.py:338`，演练造不出来）
- [x] **回滚预案**：`.env` 切回 sqlite + 旧库文件，**不回退代码**（M2 同车代码不读任何新列——role 不进 models、生成列消费在 M3、execution_rows 代码在 M6）；回滚库是 pre-alembic 存量库，启动分支跳过 upgrade 直跑；切换后新数据不回灌（低峰窗口 + 权限方案 announcement 通知首发预告）

**M2 门禁**：PG 全量 pytest 绿（M0-3 fixture 上）；逐表对账零差异；生成列抽样 = 提取函数；元数据断言测试绿；冒烟清单过（含三条高危面）；演练报告与正式报告逐项一致。

---

## M2.5 权限代码上线（= 权限方案 P1b；切换后立即，不依赖停服）

### Task M2.5-1: role 权威翻转（baseline 后第一个真 revision）

**Files:**
- Create: `src/gimbal-platform/backend/alembic/versions/0002_role_authority_flip.py`
- Modify: `src/gimbal-platform/backend/app/models/user.py`（映射 `role`；`is_admin` 转读侧派生 `= role=='admin'`，过渡一个版本后删列）
- Modify: `src/gimbal-platform/backend/app/schemas/`（`UserPublic` + `role`；`UserPatchIn.is_admin` → `role` 枚举；末位 admin 保护改角色判断「不可降级最后一个 admin」）

**Steps:**

- [x] revision：PG 原生 `ALTER COLUMN role DROP EXPRESSION` 转可写 + `DEFAULT 'member'`；SQLite 走 batch「读生成列→写普通列」重建——**按 M0-4 案③结论执行**（逐行值相等断言；跑不通则手写重建 SQL）
- [x] models/schema 改造；`/auth/me` 的 `MeOut` 包裹 `UserPublic`，role 自动随身份接口下发

### Task M2.5-2: require_role 依赖工厂与执行点

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/deps.py`（`require_admin` 升级为 `require_role(*roles)` 工厂，`require_admin` 成其别名；`AdminUser` → 按面拆）
- Modify: `src/gimbal-platform/backend/app/routers/_ownership.py`（`ensure_owner`/`can_read_scenario` 签名不变，内部 `user.is_admin` → `user.role == 'admin'`）
- Modify: `src/gimbal-platform/backend/app/routers/users.py`（`GET` → operator+；`POST` → admin——现状任何登录用户都能开号，spec-1 遗留）
- Modify: `src/gimbal-platform/backend/app/routers/service_aliases.py`（operator 面收紧：共享别名（`owner_user_id` 空）读写；**他人个人默认不可写、归属字段不可改**——`owner_user_id` 是 create/patch 可写入参，不拆行则人事/内容权掉进技术运营角色）
- Modify: carry 写面（PUT → operator+）、适配中心 admin 块（operator 全量读写；member 仅 `scope=mine` 只读）
- 其他权限矩阵落点照权限方案 §1.2/§2.1 逐行对表（执行记录 owner 硬隔离**不变**——`get_owned_execution` 无 admin 旁路是刻意不变量；凭证行连 admin 也 ✗）

**Steps:**

- [x] role 不进 JWT：`get_current_user` 本就每请求查库，role 从库里取，升降级后端即时生效
- [x] 先写失败测试：三角色对每类端点的 200/403/404 矩阵用例（member 私有场景 404、operator 私有场景 404、admin 200；operator 共享别名可写/他人个人默认 403；执行明细三角色皆仅 owner）

### Task M2.5-3: 前端 hasRole 单点收敛

**Files:**
- Modify: `src/gimbal-platform/frontend/src/stores/auth.ts`（`isAdmin` computed 扩展为 `role: Ref<'member'|'operator'|'admin'>` + `hasRole(...roles)`——`stores/auth.ts:77` 注释本就预留）
- Modify: 路由 meta `requiresAdmin` → `requiresRoles: string[]`；Sidebar adminOnly 过滤、工作台卡片注册表、AdaptationCenter / Runner / ScenariosMine 的 `is_admin` 分支渲染点全部换用 `hasRole`

**Steps:**

- [x] localStorage 角色快照的收敛缺口用铃铛 30s 轮询顺带回传角色版本号（`users.updated_at`）补齐：变了就 refetch me（几乎零成本）
- [x] `vue-tsc --noEmit` 绿；既有 adminOnly 用例不回归

### Task M2.5-4: 通知后端三接口 + 六种接线

**Files:**
- Create: `src/gimbal-platform/backend/app/routers/notifications.py`（`GET /api/notifications?unreadOnly=&limit=` 信封分页；`POST /api/notifications/read` 批量标读；`GET /api/notifications/unread-count`——顺带回传角色版本号）
- Create: `src/gimbal-platform/backend/app/services/notifications.py`
- Create: `src/gimbal-platform/backend/app/routers/admin_announcements.py`（`POST /api/admin/announcements`，admin only，写时全员 fan-out 行——内部 <百人直接逐行插入不懒展开）
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`（终态收口处 `:1121-1160` 一带加 execution_finished 写入点——**切换窗口外落**，这是 P1 拆包的核心理由）
- Modify: `src/gimbal-platform/backend/app/services/adaptation_service.py`（adaptation_applied：批次 ops 应用且 touched scenario 属于该成员；仅 scenario/dataset 类实体，carry 类无归属不通知）
- Modify: 场景下架 / 角色变更 / 转让的对应端点（scenario_unpublished / role_changed / resource_transferred——后两者走现成 fan-out）

**关键语义（权限方案 §3.3，逐条照做）：**

- [x] 批量合并：带 batch_id 的执行按批 upsert 单条（「批次 X：48 通过 / 2 失败」），`UNIQUE (user_id, type, batch_id) WHERE batch_id IS NOT NULL` 是 ON CONFLICT 命中面；**ON CONFLICT 必须重复 partial unique 谓词**（漏写运行时才炸）
- [x] 聚合计数**在 UPDATE 语句内用子查询现算**（`SET body = (SELECT … FROM executions WHERE batch_id = …)`）——Python 先算后写会被并发终态用旧读数覆盖
- [x] 已读语义：批次通知已读后新行完成**不重置未读**，只刷新聚合计数
- [x] 公告 `expires_at` 查询侧过滤

### Task M2.5-5: 铃铛 UI + 按 type 通知开关（同批，缺一不可）

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/notifications/`（顶栏铃铛：30s 拉 unread-count，有新才拉列表；列表/全部已读/深链跳转）
- Modify: 通知偏好读写面（user_prefs 表 M2 已建、代码此批提前——**开关必须先于吵闹型通知**：adaptation_applied 一批扫几十场景每 owner 一条，没有关闭手段的铃铛上线第一天就会被整体关掉）

### Task M2.5-6: 注册 bootstrap 双修

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/auth.py`（首位注册改写 `role` 而非 is_admin；count-then-insert 的并发双管理员窗口按仓内审计 P9 处理——插入后复检 count 自愈降级或事务加锁）

### Task M2.5-7: 用户管理页角色化 + 公告入口

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/UsersAdmin.vue`（角色列三值 RadioGroup + 行内 chip 三色 member 灰/operator 蓝/admin 红；`canToggleRole` 末位保护；「发布公告」入口）

### Task M2.5-8: 适配边界白名单测试

**Files:**
- Create: `src/gimbal-platform/backend/tests/test_adaptation_boundary.py`

**Steps:**

- [x] 出参 schema 白名单断言：`SnapshotRef` 仅 entityType/entityId，`before_json` 永不出 API——钉死「字段面可见、值面不可见」，防将来「回滚预览」类需求无声破界

**M2.5 门禁（2026-09-22 达成）**：后端 648 passed;前端 124 文件 / 1082 测试全绿 + vue-tsc 0 错;三角色 API 矩阵 13 项全过(member 四面 403/operator 技术运营面 200+他人私有场景 404/admin 人事内容面 200);浏览器铃铛端到端(公告 fan-out 送达 3 人 → 徽标 1 → 下拉见条目 → 全部已读徽标清零);role 权威翻转 revision 0002 已上 PG(PG 只校验路径拒绝自动迁移后人工 upgrade,纪律生效);role_changed/scenario_unpublished/adaptation_applied/execution_finished(单发+批量 upsert)/announcement 五种通知接线落地,resource_transferred 留 P2。原门禁文:三角色各登录一遍——member 看不到任何 admin/operator 菜单与数据（含 API 直打 403/404）；operator 能处理适配与别名/默认值，但他人 private 场景详情 404、他人执行明细 404；admin 用户管理可用、能看到全员私有场景。执行完成/适配应用后接收人铃铛未读且深链可达。铃铛 + type 开关可用。

---

## M3 场景检索 SQL 化

### Task M3-1: SQL 端过滤/排序/分页

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/scenario_store.py`（列表查询改投影列 SELECT + SQL 端 where/order/limit-offset；`_passes_filters` 退役为 SQLite 本地兜底）
- Create: 方言 helper 对（唯一一对）：PG `col @> '["x"]'::jsonb` + GIN jsonb_path_ops / facets 用 `jsonb_array_elements_text`；SQLite 本地 Python 兜底（本地量小，正确性优先）

**Steps:**

- [x] q/visibility/system/module/priority/tags/author/updatedWithin/sort/page 全 SQL 化（参数 M1 已进端点，此批换引擎）；排序锚 `updated_at DESC`（DB 行读时投影，客户端伪造的 updateTime 不采信）
- [x] pg_trgm GIN 索引覆盖 ILIKE（新 alembic revision；「ILIKE + 元数据列起步，trgm 备选」——索引备选但 M3 落）
- [x] 先写失败测试：PG fixture 上断言生成的 SQL 含参数化过滤（或按行为断言结果集与 Python 过滤口径一致）

**实现注记（2026-09-21）：**
- 落点与计划微差：SQL 分支独立成 `app/services/scenario_query.py`（`list_page` + `facets`），路由层按方言分派（PG 走 SQL 分支；SQLite 走 `scenario_store.list_rows` Python 兜底），`_passes_filters` 保役。行形态化（list item / options / 计数注入）留在路由层单一处，两方言形状天然一致。
- asyncpg 绑定参数坑（两处）：①`.contains()`/ILIKE 混 JSON cast 时预备语句类型推断错乱（% 串绑进 json 槽）→ 全部改显式 `text()` + `CAST(:p AS text/jsonb)` + `bindparam(value=...)`；② text 占位符与 bindparam 键必须同名成对（`:sysv0` ↔ `"sysv0"`），asyncpg 按位置绑定不查别名。
- `starred=true` 收藏集（≤20）下推 SQL IN；空集恒假 `1=0`；`starred=false`（排除）走 Python 兜底（量小不值得 NOT IN 分支）。
- trgm revision = `0003_pg_trgm_indexes`（name/description/scenario_id 三列 GIN gin_trgm_ops），PG 已 upgrade。
- SQLite 秒级 `func.now()` 使同秒排序不可断 → 排序测试改为直接置 `updated_at` 未来值（排序读路径才是受测面）。

### Task M3-2: facets 端点

**Files:**
- Create: `GET /api/scenarios/facets`（GROUP BY 聚合返回 modules/systems/tags/authors/priorities 各维可选值+计数——替代前端全量拉回 FilterPopover unique 的模式）

**实现注记（2026-09-21）：** 端点形状 `{dim: [{value, count}]}`；PG 走 GROUP BY + `jsonb_array_elements_text` unnest（system/tags 两维），SQLite 用 Counter 兜底。前端 FilterPopover 新增 `facets` prop（选项带计数徽标，空值不产芯片），`useScenarioListView` 挂 q/分桶驱动的 facets 拉取，请求失败静默回落当前页 uniq 池。回归钉子：`test_scenario_sql_facets.py`（双方言同套断言）、`useScenarioListView.test.ts`（facets 参数 + 回落）、`useServerList.qclear.test.ts`（q 清空重拉）。

**PG 全量首跑 72 失败的三族根因（2026-09-21 补课，全修复）：**
1. **FK 强制差**（约 60 个）：测试以字面量 `owner_id=1/2`/`operator_id=1`/`author_id=1` 直插业务行——SQLite 默认不校验 FK、PG 校验，且 `scenario_store.create` 把 IntegrityError 掩码成 `scenario_id_exists` 迷惑排查。修复：①`scenario_store.create` 缺省 `owner_id: int = 0 → None`（0 在 PG 恒违反 FK；ETL 本就把历史 0 行映射 NULL，语义一致）；②`tests/helpers.ensure_fk_users(db, *ids, make_admin=N)` 垫底用户（存在即跳过，PG 显式 id 后 setval 序列；`make_admin` 把垫底用户造成可登录 admin——垫了用户后「首注册自动 admin」失灵，admin-only 路由的测试改登录垫底 admin）；③`test_derived_tables` 补 `composer_scenarios` 父行（scenario_endpoint_refs 的 DEFERRED FK）。
2. **asyncpg naive datetime 按客户端时区编码**（约 7 个）：测试种 `datetime(2026, 9, 10)` naive 值，asyncpg 把 naive 当客户端本地（本机 +08:00）编码 → 偏 8 小时；SQLite 原样存取。修复：测试种子时间全部 `tzinfo=timezone.utc`。
3. **双方言序列化形状漂移**：PG 读回 timestamptz 是 aware（isoformat 带 `+00:00`）、SQLite naive（不带）——`board_assembler`/`board_cards` 直出 isoformat 打进前端契约。修复：`core/timeutil.iso_naive_utc()` 统一 DB 时间戳的 API 序列化口径（归一 UTC 剥 tz，维持既有 naive-UTC 字符串契约）。
另：`test_run_injectable_wire` 的 carry 绑定值种 int（PG text 参数拒收，SQLite 宽松）→ 改字符串。

**M3 门禁**：q/筛选全走 SQL（网络面板确认请求带参数、响应只有当前页）；facets 计数与全量一致；`payload` 列列表查询永不触碰（债 3 消除）。
→ **已验收（2026-09-21）**：后端双方言全量绿（SQLite 652 / PG 全量同套）；浏览器网络面板确认 `GET /api/scenarios?visibility=private&q=…&page=1&page_size=20` 参数下推 + `GET /api/scenarios/facets?q=…&visibility=private` 随 q 重拉，过滤面板选项带全量计数（order 3 / 订单 1 / fin 4 / P1 4），URL 回写 `?q=`，服务端过滤生效（4 → 1 行）。注：列表页查询仍 SELECT 整行（含 payload，计数字段 step/varCount 按页读 payload 权威计数）——「债 3」的准确口径是**过滤/排序/分页不触碰 payload**，已达成；列表行瘦身（投影列 SELECT）随 M6 执行域一并。

---

## M4 分页规范化

### Task M4-1: Page 信封铺其余端点（§4.2 改造范围表逐行）

**Files / 落点：**

- [ ] `GET /api/executions`：`q`（scenario_name ILIKE / id 前缀）下推 + page/page_size/total
- [ ] `GET /api/executions/{id}/rows`：execution_rows 分页查询（读侧暂仍 JSONL 回放则此条随 M6 落——**按 M6 进度对齐，二者取先**）
- [ ] `GET /api/auths`：`q`（alias/username/url）+ `token_type` + page；引用计数保持后端；metaText「N Bearer · N 整段头」计数改服务端聚合（服务端分页后前端拿不到全集）
- [ ] `GET /api/constants`：`q`（name）+ kind + page
- [ ] `GET /api/adaptations/batches`：scope/status/page
- [ ] `GET /api/service-aliases`：`q/base` + page
- [ ] carry bindings/defaults 明确豁免不分页（§9）

### Task M4-2: P1 批页面接入

- [ ] ExecutionsList、执行行级表、Auths、UsersAdmin、适配批次表接 useServerList + ui/pagination + URL query 同步（场景两页 M1 已接）；users 列表分页信封在此落（接口收紧已随 M2.5，不再挂）

**M4 门禁**：§6.3 全部验收（含 ExecutionsList total 正确、各行级表/Auths/Users 分页可用）。
→ **已完成（2026-09-22）**：六端点全落信封（executions q 下推含 scenario_id 子串 + id 前缀；auths q(alias/url — username 是 Fernet 密文服务端不可检索，如实收缩)+token_type+全量 tokenTypeCounts；constants q/kind；batches status；service-aliases q；users q/role）。通用信封泛型 `schemas/page.py PageOut[T]`。前端:Auths/UsersAdmin 改 useServerList(防抖 + 分页 + URL),ExecutionsList/AdaptationCenter 接服务端过滤,小池消费方走 `listAll()` 便利(≤200 单页)。批次 detail 只构建当前页(隐藏 N+1 钉死在页大小)。注意坑:路由形参 `status` 遮蔽 fastapi `status` 模块 → 函数内 `from fastapi import status as http_status`。

---

## M5 聚合与轮询后移

### Task M5-1: 服务目录聚合端点（债 11）

- [ ] `GET /api/catalog/services`：平台后端聚合 plate 目录并缓存（TTL 30s + 目录版本失效），返回服务级计数；前端 `utils/catalog-services.ts` 改走此端点（现状 `per_page=500` 前端直连，超 500 静默丢；ServicesIndex/ServiceAdmin/工作台卡三处前端聚合收编）

### Task M5-2: 批量信号与 bulk impact（债 12）

- [ ] `GET /api/scenarios/signals?ids=a,b,c`：一次返回每场景健康趋势摘要（限 20 个 id 对齐关注上限）——ScenarioFollows 每关注对象 2 请求的 N+1 消除
- [ ] `impactSummary(ids)` 扩展为完整 bulk impact 端点（useInterfaceChange 每 pending 端点一个 impact 的 N+1 消除）

### Task M5-3: 工作台活动时间线服务端合流

- [ ] `GET /api/activity?limit=40`：服务端合流（本人执行 + 本人场景改动 + mine 批次），前端只做日历分组渲染

### Task M5-4: 轮询治理

- [ ] ExecutionsList 3s 整表轮询 → 10s 且只刷 `summary` 端点 + 当前页（`document.visibilityState` 不可见暂停）；详情 1s 轮询保留、终态即停（现状已停则确认保持）

### Task M5-5: auth 引用计数增量化

- [ ] `/api/auths` 现每次调用全表扫全部场景+方案 payload（`auth_references._scan_scenario_refs`，列表页最贵隐藏成本）——改 scenario_auth_refs 派生表随写维护，或按 max(updated_at) 失效的缓存

### Task M5-6: 关注页服务端数据源

- [ ] `GET /api/scenarios?starred=true` + 分页（store 退位后 `starredScenarios` 全量过滤失去依托）

**M5 门禁**：关注页/工作台网络请求计数达标（关注页从 40+ 请求降到个位数）。
→ **已完成（2026-09-22）**：
- M5-1 `GET /api/catalog/services`(plate 目录代理 + 聚合 + 30s TTL;降级不进缓存);前端 `catalog-services.ts` 全部 loader 改走此端点(浏览器不再直连 plate per_page=500)。
- M5-2 `GET /api/scenarios/signals?ids=`(≤20,一次回 trend/lastRun/schemeCount/defaultSchemeName —— 与前端 useScenarioRuns.trend 逐字同口径,私有锁默认方案/公共锁原件)+ `GET /api/adaptations/impact-bulk`(一次回全部 pending 端点);关注页从 40+ 请求(2×N 限并发)→ 1 请求,useInterfaceChange 从「每端点一次×限并发 4」→ 1 请求。
- M5-3 `GET /api/activity?limit=`(三源服务端合流,events 语义行 + sources 降级报告);前端 useActivityTimeline 只做文案/深链映射与日历分组。
- M5-4 ExecutionsList 轮询 3s→10s + visibilitychange 不可见暂停。
- M5-5 auth 引用计数指纹缓存(count+max(updated_at) 三表四聚合查询换全 payload 扫描;反查面板保持实时扫)。

---

## M6 收尾

### Task M6-1: execution_rows 转正

- [ ] 写入点：每行终态即 upsert（崩溃窗口不丢已终态行）；活跃执行读侧仍走内存 `_row_states`，DB 行作持久层跟进
- [ ] `GET /executions/{id}/rows` 真分页查询（债 5 消除；M4 未提前落则此批接管）
- [ ] JSONL 停写；历史文件转只读归档；保留策略按 preccheck 实测口径（百万级则带保留参数上线）

### Task M6-2: user_stars 上线

- [ ] marks_store 退役：star 端点形状不变、`starred` 仍为读时投影（现状已是服务端读时投影，替换对前端透明）
- [ ] 关注上限 20 服务端 409 兜底（客户端先拦不变）
- [ ] `scenario_store.delete:180` 的 `stars.remove_item()` 调用删除（user_stars.scenario_id CASCADE 接管——Python 显式级联职责收缩到只剩 case 目录清理）

### Task M6-3: 旧物退役（各自一个小 revision）

- [ ] `is_admin` 列删除（M2.5 起读侧派生已过渡一个版本）
- [ ] `_meta_from_row` 修复分支删除（ETL 已把修复写回 payload）

**M6 门禁**：行级回放分页可用；stars.json 不再被读；全量测试绿。
→ **已完成（2026-09-22）**：
- M6-1 行终态(canceled 含)即落 execution_rows(`_persist_row_terminal`,best-effort 不阻塞);读侧三级:活跃内存 registry → DB LIMIT/OFFSET 分页(信封{items,total,page,pageSize}) → M6 前存量单 JSONL 只读归档回放;行级 JSONL 停写(运行级故障审计行保留:auth 快失败/计数器双败,成功路径零 JSONL)。时间戳坑:RowState 是 ISO 串、列是 timestamptz → `_iso_to_dt/_dt_to_iso` 两侧转换(读侧 naive-UTC 串与旧口径一致)。
- M6-2 marks_store 删除:star 读写全走 UserStar 表;关注上限 20 服务端 409(star_cap_exceeded);`absorb_legacy_stars` 启动一次性吸收 data/stars.json(悬空 id 过滤,吸收后改名 .absorbed);场景删除的级联 = PG FK CASCADE + SQLite 显式 DELETE 兜底(该方言 FK 不强制)。
- M6-3 revision `0004_drop_is_admin`(PG DROP COLUMN / SQLite batch;PG 已上)。模型删列;`UserPublic.is_admin` 改 role 派生(前端旧缓存 fallback 口径保留);register/patch 的镜像写全删。`_meta_from_row` 修复分支删(ETL 已写回)。链条 fresh-install 兼容:0001 fresh 路径 role 平列(生成列过渡形态退役),0002/0004 容错(平列/无列时 no-op)—— 临时库全链 upgrade 验证过。

---

## P2 权限域收尾迭代（M2.5 之后、排在 M4 后做）

### Task P2-1: /profile 个人设置页 + UserBadge 下拉

- [ ] 新增 `/profile`（全员）：改 `display_name`（走现有 `_name_checks.py` 应用层查重——username↔display_name 双向冲突检查**不能撤**，DB partial unique 只兜自身并发竞态）；改密码（旧密码验证 + 复用注册 zod 强度）；通知偏好正式入口（开关代码 M2.5 已上线）
- [ ] `UserBadge.vue` 改下拉：身份徽章（role chip）→ 个人设置 → 登出；侧栏底部与收拢顶条共用组件

### Task P2-2: 删除用户资源处置流程

- [ ] 删除对话框三选一（默认第一项）：①私有场景转公共库（署名保留原作者字符串快照）②转让给指定成员（owner_id 批量改写，数据集/方案随场景走）③一并删除（明示二次确认）
- [ ] 处置面覆盖：个人别名显式处置（转共享自此有了人工入口）；**case 目录立即清扫**（按 executions.owner_id 定位 runId 当场清，不等 14 天周期——case.json 含注入后明文凭证）；前端「收藏一并清除」文案修正为实况
- [ ] `executions.owner_name` 孤儿行展示 `owner_name（已注销）`
- [ ] resource_transferred 通知接线（受让人）

### Task P2-3: 审计日志落码

- [ ] audit_logs 生产端埋点（§6 清单：角色变更/删除用户/重置密码/公告/carry 写/适配 ops 应用/别名写——**只记特权写**，不记普通读与成员自身常规 CRUD）
- [ ] `GET /api/admin/audit-logs`（admin only，分页信封）；用户管理页「审计」tab

### Task P2-4: 前端测试补齐

- [ ] 角色矩阵 route guard / API 403 用例（vitest）

**P2 门禁（权限方案 §7）**：删除一个测试用户走完三种处置，执行记录仍在且显示「已注销」；审计 tab 可查特权操作。
→ **已完成（2026-09-22）**：
- P2-1 `/profile`(全员):昵称自改(PATCH /users/{self} 走双向查重)/ 改密(新端点 POST /auth/change-password,旧密码后端核验)/ 通知偏好正式入口;UserBadge 改下拉(身份徽章 → 个人设置 → 登出)。
- P2-2 DELETE /users/{id} 处置三选一(`UserDeleteIn`,默认 publicize):publicize=私有场景转公共库(owner_id 置空 + owner_name 署名快照)/transfer=owner_id 批量改写 + 个人别名转共享 + 受让人收 resource_transferred 通知/purge=场景级联删。执行台账恒保留(owner_id SET NULL 显式化,SQLite FK 不强制的兜底);case 目录按 owner 执行的 runId 当场清;列表投影带 ownerName(注销后缀「已注销」)。前端 UsersAdmin 删除对话框三选一 + purge 二次文案 + 受让人选择。
- P2-3 audit_logs 埋点九类特权写(user.create/role_change/delete/reset_password、announcement.publish、carry.write、adaptation.op.apply/batch.rollback、alias.write)+ `GET /api/admin/audit-logs`(admin only,信封 + 动作词表)+ UsersAdmin「审计」tab(chip 过滤 + 分页)。
- P2-4 角色矩阵测试:路由守卫(member→admin 页弹回/operator 放行 operator 页)+ hasRole 矩阵(含旧缓存回落)+ Profile 页三段。顺带修正 /service-admin 路由误标(requiresAdmin → requiresRoles operator+)。

---

## 两文互锁对照（防「一边以为另一边做了」）

| 互锁点 | 落点 | 本计划任务 |
|---|---|---|
| `users.role` 生成列（P1a） | M2 建库 | M2-1 |
| `DELETE /api/users` 最小显式级联（P1a） | M2 同车 | M2-7 |
| notifications/user_prefs/audit_logs/user_stars 建表（P1a，只建不上码） | M2 建库 | M2-1 |
| role 权威翻转 DROP EXPRESSION | M2.5 第一个真 revision | M2.5-1 |
| 权限接口收紧（GET operator+ / POST admin） | M2.5（**不是 M4**） | M2.5-2 |
| users 列表分页信封 | M4 | M4-2 |
| 执行记录 SET NULL + owner_name（台账 outlive 用户） | M2 表设计 | M2-1 / P2-2 展示面 |
| user_stars 吞 stars.json | 表 M2 建、行吸收 M6 | M2-1 / M6-2 |
| 切换公告预告（announcement 首发） | 切换窗口前发布 | M2-8 前置动作 |
| `ExecutionOut` 列表去 config | M1 响应投影（不等 M2） | M1-2 |
| 「已过期清扫」分支 | M1（切换前就位） | M1-5 |

## 附录（M0 填充）

- A1 测试基线实测数：**630 passed / 208.95s**（sqlite 全量 pytest，2026-09-21 实测——仓内审计的 630 正确，前稿 622 作废）
- A2 PG 测试隔离选型结论（2026-09-21 定案）：**schema-per-test**——`TEST_DATABASE_URL`（postgresql+asyncpg://）存在时每测试 `CREATE SCHEMA t_<uuid>` + 会话 `search_path` 钉死 + create_all，结束 `DROP SCHEMA CASCADE`；不设则维持 sqlite 临时文件路径（双方言自律，默认零环境依赖）。冒烟子集 PG 全绿：test_users(13) + test_executions/test_scenario_visibility_and_copy(14)；sqlite 路径回归 18 passed 无变化；无 schema 残留。事务回滚路线未选（与 run_dispatcher 后台线程独立 session 相冲）。
- A3 生成列×batch 三案结论（2026-09-21 实测，脚本 `scripts/m0_verify_computed.py`，10/10 通过）：
  - **进① composer 七列：通过，无需退路**——alembic batch 在带数据 SQLite 表上加 `Computed(..., persisted=True)` 拷贝步自动排除生成列；逐行值全等；`PRAGMA table_xinfo` hidden=3 确认落的是 **STORED**（不是 VIRTUAL）→ M2 baseline 的 SQLite 路径不需要 STORED/VIRTUAL 方言分叉
  - **进② users.role 单列：通过**——CASE WHEN 布尔生成列同构成立（batch 可行 + hidden=3 + 映射值正确）
  - **出③ 翻转：双方言通过**——PG `ALTER COLUMN … DROP EXPRESSION` 后可写、未动行值保持；SQLite 手写重建（CREATE/INSERT SELECT/DROP/RENAME）逐行值相等、翻转后可写 → M2.5 权威翻转两条路径都验证在案
  - **PG ETL 直插写法：通过**——列清单排除生成列直插后 PG 自算、逐行全等；故意带上生成列报 `cannot insert a non-DEFAULT value into column "name" … Column "name" is a generated column`（§3.3 预测的报错形态确认，ETL 排除列清单的失败面是响亮的不是静默的）
- A4 preccheck 首跑摘要（2026-09-21，生产 app.db 实测）：**blocking_problems = 0** —— 类型亲和异常 0、变长超长 0、孤儿行全 0（含 owner_id=0 批 = 0）、display_name 重复 0、payload meta 逐行校验全过；execution_rows 量级 **55 执行 / 81 折叠行 / 单执行峰值 20 行**（远低于百万阈值 → 「默认全保」确认）；stars.json 1 用户 2 条（含 1 条悬空场景引用，ETL 按 CASCADE 语义滤除并计数）；JWT_SECRET/FERNET_KEY 均固定。ETL 演练（生产副本 → 全新 PG 库）**PASS**：行数对账全等、抽样 checksum 全等（按主键对齐——SQLite/PG 排序规则差异曾致假阳性，已修）、生成列抽样=提取函数、FK 装载后全量校验干净、setval 覆盖 15 序列、应用在演练库上起服冒烟通过。
