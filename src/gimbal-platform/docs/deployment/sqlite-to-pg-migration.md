# SQLite → PostgreSQL 数据迁移方案(已部署环境通用版)

> **用途**:把任意一台已部署、跑在 SQLite 上的 Gimbal Platform 数据完整迁到
> PostgreSQL。本方案在本仓 M0–M2 切换期间实测走通(2026-09-21 首切,演练三轮
> + 正式一轮,行数/checksum 双对账零差异),本文把那次实操固化成可重复执行的
> 运维手册。
>
> **配套**:运行期运维见 `docs/runbook-pg.md`(起库/备份/回滚的日常面);
> 设计依据见 `docs/superpowers/plans/PG迁移与权限域-实施计划/`。
> 全部工具随代码库分发,无需额外安装包(SQLAlchemy/asyncpg 已在依赖里)。

---

## 0. 迁移资产清单

| 资产 | 作用 |
|---|---|
| `backend/scripts/pg_preccheck.py` | 切换前体检(只读不改):类型亲和/超长/孤儿行/生成列拒插预演/stars 计数/密钥检查 |
| `backend/scripts/migrate_sqlite_to_pg.py` | ETL 直切:全表搬运 + 变换 + 对账报告 |
| `backend/alembic/`(0001→0005)+ `alembic.ini` | 目标库 schema 权威(空 PG 建表) |
| `compose.pg.yml` + `pg-init/01-timezone.sql` | PG 一键起库(时区钉 UTC) |

---

## 1. 硬前提(不满足则停下)

1. **版本对齐**:源环境的代码必须先升到**与 ETL 同版本**(即包含 M2 表结构:
   `users.role`、`execution_rows`/`execution_snapshots`、通知五表、`scenario_endpoint_refs`
   等;含 0005 起的 `composer_data_sets.row_count` 生成列与最终索引面)。
   旧版本 SQLite 库缺表缺列,ETL 按 models 取数会直接报错。
   升级步骤:拉代码 → 起一次后端(启动自适应会把 pre-alembic 旧库原地补齐,
   `app/core/migrations.py` 的 legacy 分支)→ 停掉。
2. **密钥固定**:源环境 `.env` 的 `JWT_SECRET` / `FERNET_KEY` 必须是非临时值
   (preccheck 第 9 项会查)。迁移后这两个值**原样照搬**到新环境 —— 否则全部
   登录态失效、全部凭证密文不可解(`auth_sessions` 的 Fernet 加密绑死密钥)。
3. **停机窗口**:ETL 是全量直切(非增量)。内部平台按「低峰窗口 + 公告预告」
   执行;数据量 GB 级时窗口按 §7 的量级估算预留。
4. **目标 PG**:14+;`compose.pg.yml` 起的库已把 `timezone` 钉为 UTC
   (init 脚本只在卷首次初始化生效,复用旧卷要手工补 `ALTER DATABASE …
   SET timezone TO 'UTC'`)。

---

## 2. 全流程(八步)

### Step 0 — 版本对齐(窗口前)

源环境升级代码并启动一次,让 SQLite schema 补齐到当前 models
(启动日志确认 `ensure_schema` 走了 upgrade/adapt 而非报错)。**这步在窗口前
做**,升级后源环境继续正常跑 SQLite,不影响业务。

### Step 1 — 备份(窗口开始)

```bash
cd <源环境 backend 目录>
cp data/app.db data/app.db.bak-migrate-$(date +%Y%m%d-%H%M%S)
cp -r data data.bak-migrate-$(date +%Y%m%d-%H%M%S)   # stars.json / runs / cases 全量
```

`data/` 整目录备份覆盖:stars.json(收藏)、runs/*.jsonl(行级历史)、
runs/cases/(执行工件)。**ETL 只搬数据库;文件资产在切换后原目录继续用,
不用搬**。

### Step 2 — 起目标 PG 并建空 schema

```bash
# 仓库根
docker compose -f compose.pg.yml up -d && docker compose -f compose.pg.yml ps

# backend 目录(生产用环境变量覆盖密码)
export PGPASSWORD='<生产密码>'   # 仅 psql 用;alembic 走 DSN
DATABASE_URL="postgresql+asyncpg://gimbal:<密码>@127.0.0.1:5432/gimbal" \
    python -m alembic -c alembic.ini upgrade head
```

PG 时区由 `pg-init/01-timezone.sql` 钉死 UTC —— init 脚本仅在卷**首次**
初始化时执行,接手既有卷/远端库须手工补跑一次
`ALTER DATABASE gimbal SET timezone TO 'UTC'`(运行期时间口径三防线的
第 1 条,完整说明见 Step 6)。

alembic 输出应走到 `0005_interaction_fields`。**不要**用 create_all 手工建表 ——
双方言细节(生成列方言变体/GIN 索引/部分唯一索引)只在 alembic 链里。

`0005`(交互字段统一轮,2026-09-22)对目标库的净效果,空库直建时自动成立:
* `composer_data_sets.row_count` 变 STORED 生成列(`jsonb_array_length`,
  带 `jsonb_typeof` 守卫)—— 应用写侧三处已停写,源值不再可写;
* 六个前缀冗余单列索引不建(execution_rows.execution_id /
  notifications.user_id / composer_scenarios.visibility 与 owner_name /
  carry_service_bindings.service_name / composer_run_schemes.scenario_id),
  `ix_executions_owner_id` 为 `(owner_id, id)` 复合;
* PG-only 视图 `v_scenarios_readable`(security_invoker;直连消费前
  `SET app.uid / app.role`,应用不消费它,见交互字段方案 §4 G5)。

### Step 3 — 体检(只读)

```bash
python scripts/pg_preccheck.py --db data/app.db --json preccheck.json
```

**门禁:`blocking_problems` 为空才允许继续**;警告项按下表处置:

| 体检发现 | 处置 |
|---|---|
| `executions.owner_id` 孤儿 | **预期存在**,ETL 按 SET NULL 语义吸收,不用处理 |
| `composer_scenarios.owner_id=0` | 预期(历史「未归属」),ETL 映射 NULL |
| display_name 重复(非空) | 窗口内先在 UI 改名;partial unique 会拒插 |
| payload 生成列拒插预演失败 | 按报错行修 meta(超 64 的 name、非法 priority);ETL 灌行时再遇会当场中止,窗口内修完重跑 |
| execution_rows 量级百万+ | 正常;§7 有保留策略说明 |
| JWT/FERNET ephemeral | 回 Step 0 前置项,固定后重跑体检 |

### Step 4 — 演练(对副本,窗口前可做)

```bash
cp data/app.db /tmp/rehearsal.db
python scripts/migrate_sqlite_to_pg.py \
    --source /tmp/rehearsal.db \
    --target postgresql+asyncpg://gimbal:<密码>@127.0.0.1:5432/gimbal \
    --report etl-rehearsal.json
```

演练目标库用**另建的空库**(如 `gimbal_rehearsal`),不要污染正式目标。
拿到报告后人工核对:
- 每表 `rows == target_rows`;
- `verifications.row_counts_match / checksums_match / generated_columns_match`
  全 `true`;
- `stars_dangling_skipped` 数量与源环境认知一致(悬空关注 = 场景已删而
  stars.json 未清的历史缺口,按 CASCADE 语义丢弃);
- `execution_rows_absorbed` 与 preccheck 第 7 项的实测数一致。

### Step 5 — 停机 + 正式 ETL(窗口内)

```bash
# 1) 停旧后端(uvicorn 进程;不 kill -9,等 graceful)
# 2) 最终 ETL(对生产 app.db 本体;目标库先清空重建一次保证幂等)
dropdb … && createdb … gimbal   # 或 DROP SCHEMA public CASCADE; CREATE SCHEMA public;
DATABASE_URL=… alembic upgrade head
python scripts/migrate_sqlite_to_pg.py \
    --source data/app.db \
    --target postgresql+asyncpg://gimbal:<密码>@127.0.0.1:5432/gimbal \
    --report etl-final.json
```

正式报告与演练报告**逐项 diff**,数字应一致(源库在两轮之间有增量则以正式为准,
量级突变要能解释)。停机窗口从这步起算。

### Step 6 — 切换配置并起新后端

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://gimbal:<密码>@127.0.0.1:5432/gimbal

# 其余键(JWT_SECRET / FERNET_KEY / GIMBAL_BIN / CORS_ORIGINS)原样不动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动日志三看:
1. `ensure_schema` 无 `pg_schema_behind`(版本链对齐);
2. `user_stars: absorbed N legacy stars`(若源环境 stars.json 尚未被应用吸收
   —— M6 代码会自动吸收并改名 `.absorbed`;ETL 已导过则是 0,都正常);
3. 无 `column … does not exist` 类报错。

运行期时间口径(三防线,2026-09-22 事故后成文;照本文档部署当前代码即
三线齐备,**宿主机任何时区都不影响正确性**):
1. **库级**:PG 库时区 = UTC(Step 2 的 pg-init 脚本;既有卷手工补跑);
2. **列级**:全部时间列 timestamptz(`timezone=True`,元数据断言测试把关);
3. **驱动级**:asyncpg 对 timestamptz 的 **naive** 绑定按**客户端本地时区**
   编码 —— `timeutil.utcnow()`(naive UTC)曾把 ORM 写入的时间整体
   -8h(切库后首单 finished_at 实测,**静默偏移不报错**)。代码已全量换
   `UtcDateTime` 装饰器(绑定侧 naive→UTC aware);自写外部工具直写库
   时仍必须传 aware-UTC。Step 7 的冒烟含时间口径校验。

### Step 7 — 冒烟验收(窗口收尾)

```bash
# 登录(旧密码必须能登录 —— 密码哈希原样搬运)
curl -X POST …/api/auth/login -d '{"username":"admin","password":"<旧密码>"}'
# 列表三件套:场景/执行/凭证 —— total 与源环境一致
curl …/api/scenarios | jq .total
curl …/api/executions | jq .total
curl …/api/auths | jq .total
```

UI 侧抽查:场景详情可开(生成列回读正常)、执行行级表有历史(M6 前存量单
走 JSONL 归档回放)、收藏页在场;执行列表行应带 `scenario_display_name`
(改名场景显示新名、已删场景显示快照名 +「已删」)。DB 侧抽查:
`SELECT count(*) FROM v_scenarios_readable` 不带 GUC 时仅返回 public 行。

时间口径校验(切库后首个 Python 写入的时间必须准,Step 6 三防线):
发起一次小执行(任意场景单行跑完,或发起后立即取消),然后

```sql
SELECT id, started_at, finished_at,
       EXTRACT(EPOCH FROM (finished_at - started_at)) AS dur_s
FROM executions ORDER BY id DESC LIMIT 1;
```

`dur_s` 应为正且量级正常;若 ≈ 真实时长 **-8h**(负八小时量级)= naive
绑定事故复现,查 §6 首行,不要带着偏差继续跑。验收过 → 发布「恢复」
公告,窗口结束。

### Step 8 — 收尾

- `scenario_endpoint_refs` **有意不导**(ETL SKIP):切换后首次访问适配中心
  时由应用按 CASCADE 语义自动 rebuild,顺带补齐存量锚点行 —— 无需人工动作。
- 旧 `data/app.db` 与备份**至少保留一个完整业务周期**再清。
- 源机上的旧 SQLite 后端进程不要留双活(两写会分叉)。

---

## 3. ETL 数据变换语义(如实清单)

设计偏离都有成因,换环境执行前过目:

| 变换 | 语义 |
|---|---|
| 生成列排除 INSERT | composer 七列(name/module/system…)由 PG 生成表达式自算,拒插;源值经 checksum+抽样校验等价。0005 起 `composer_data_sets.row_count` 同属此列(排除由 metadata 驱动,`c.computed is None`,非硬编码清单) |
| 时间戳**照搬**(不重置) | 台账是审计数据;对账也依赖原始时间。naive 值按「视为 UTC」补 aware |
| `owner_id=0` → NULL | 0 是历史「未归属」哨兵,PG 上恒违反 FK |
| 姓名快照回填 | owner_name/scenario_name 等列源库可能为空,ETL 从关联表回填真值(故这些列不进 checksum) |
| stars 悬空过滤 | 场景已删而 stars.json 未清的条目按 CASCADE 语义丢弃,计数进报告 |
| JSONL → execution_rows | 行级历史按「同 (executionId, seq) 终态覆盖」折叠入库;M6 起运行期直接写 DB |
| scenario_endpoint_refs 不搬 | 切换后 rebuild(见 Step 8) |
| bool/JSON 归一 | SQLite `1/0` vs PG `True/False`、JSON 字符串解析后再比 —— checksum 的已知异型面 |

## 4. 对账门禁(报告字段)

| 字段 | 判定 |
|---|---|
| `tables[*].rows == target_rows` | 全表行数相等 |
| `row_counts_match` / `checksums_match` | 抽样 50×2 行/表,PK 对齐后规范化 checksum 相等 |
| `generated_columns_match` | 生成列「源 payload 推导值 == PG 生成值」抽样相等(0005 起含 `row_count`:源 rows 数组长度 == PG 生成值 —— 源库过期的 row_count 会在目标侧**自愈**,不搬旧值) |
| `identity_columns_setval` | 全部整型序列列已 setval 到 max(id) —— 漏一个 = 切换后首次 INSERT 主键冲突 |
| `stars_imported + dangling == stars_in_file` | 收藏吸收守恒 |

## 5. 回滚预案

切换后 72 小时内发现不可修复问题:
1. 停 PG 后端;
2. `.env` 的 `DATABASE_URL` 删掉或改回 `sqlite+aiosqlite:///data/app.db`;
3. 起旧后端(旧 `app.db` 未被 ETL 触碰,ETT 全程只读源库);
4. **切换窗口之后新产生的数据不回灌**(低峰窗口 + 提前公告的既定取舍);
5. 旧库文件名不要改 —— 启动自适应认 `data/app.db`。

## 6. 已知坑速查(本仓实操踩过)

| 症状 | 根因与处置 |
|---|---|
| ETL 灌 composer_scenarios 当场拒插 | 源库有生成列同名列(不该有)或 payload 脏 —— preccheck 第 6 项会预演,窗口前修 |
| checksum 假阳性 | 排序差异('.'/'_' collation)→ ETL 已按 PK 在 Python 侧对齐;自写对账工具要同样处理 |
| 新后端首条 INSERT 主键冲突 | setval 漏列 → 报告 `identity_columns_setval` 应覆盖全部序列列,发现缺列手工补 |
| 凭证列表全部「无法解密」 | FERNET_KEY 没照搬 —— Step 1 前置项 |
| PG 起动报 `pg_schema_behind` | 目标库没 `alembic upgrade head` 或代码/链版本不一致 |
| 运行期时间整体差 8h(finished 早于 started/列表时间倒退) | asyncpg 对 timestamptz 的 naive 绑定按**客户端本地时区**编码,**静默偏移不报错** —— ORM 层曾中招(2026-09-22 切库首单),已由全模型 `UtcDateTime` 装饰器修复(Step 6 三防线第 3 条);自写外部工具直写库仍须传 aware-UTC |
| asyncpg 写 naive datetime 报错 | 外部工具直写时的已知行为:naive 按客户端时区编码;统一 aware-UTC |

## 7. 量级与窗口估算

- ETL 吞吐参考:GB 级库(数万场景/数十万执行)分钟级完成;窗口主要预算给
  体检人工过目与冒烟,各留 15–30 分钟。
- `execution_rows` 百万级:表本身照迁;如需瘦身,在**切换后**按保留参数清理
  (`DELETE … WHERE finished_at < now() - interval '…'` + 行级明细走 JSONL
  归档兜底的旧单不受影响)—— 不在迁移窗口内做删减,保持对账全集可验。

## 8. 增量 schema 演进 —— 0006(2026-09-23 迭代批次)

> 来源:`docs/superpowers/plans/2026-09-23-some_feature .md` v2(F1 分发 /
> F3 时间线事件化 / F4 服务引用方案 B)。`down_revision = 0005`。
> 本节是既有 PG 库上的**在线增量**,不再涉及 SQLite→PG ETL。

### 8.1 变更清单(4 列 + 1 表 + 2 索引)

| 对象 | 变更 | 类型 | 服务 |
|---|---|---|---|
| `notifications` | +`resource_type` | `VARCHAR(32) NULL` | F1 悬浮标签 |
| `notifications` | +`resource_id` | `VARCHAR(128) NULL` | F1 |
| `notifications` | +`payload` | `JSONB NULL`(SQLite 侧 JSON 文本) | F1(sender/original_name 结构化) |
| `service_aliases` | +`base_url` | `VARCHAR(512) NULL` | F4 方案 B 默认层 |
| `activity_events` | 新表 | 见下 | F3 |
| 新索引 ×2 | `ix_activity_events_actor_created (actor_id, created_at)`、`ix_activity_events_resource (resource_type, resource_id)` | — | F3 读侧 |

`activity_events`:`id BigIntPK` / `actor_id BIGINT NULL FK users.id ON DELETE SET NULL`
(镜像 `composer_scenarios.owner_id` 的「人走事留」模式)/ `kind VARCHAR(64) NOT NULL` /
`resource_type VARCHAR(32) NOT NULL` / `resource_id VARCHAR(128) NOT NULL` /
`detail JSONB NOT NULL`(客户端 default dict)/ `created_at timestamptz NOT NULL
server_default now()`(与 `notifications.created_at` 同款,UtcDateTime 防线覆盖)。

### 8.2 影响评估

**存量数据:零触碰、零回填。** 四个新列全部 nullable 且无 server default;
存量通知行 `resource_*` 为 NULL,而消费查询过滤 `type='resource_handoff'`
(仅新代码写入),无脏读面;存量别名 `base_url` NULL = 默认层不生效,行为不变。

**锁与时长:可在线执行。** PG 上 `ADD COLUMN … NULL`(不带默认)是纯元数据
操作,不重写表,ACCESS EXCLUSIVE 锁毫秒级;`notifications`/`service_aliases`
现有量级(千行内)无感知。CREATE TABLE + 新表索引无锁竞争。**但**为保持
「代码与 schema 同批生效」,仍按停后端 → `alembic upgrade head` → 起新后端的
顺序执行(与 §2 Step 5/6 同拍,不做在线双写)。

**部署顺序(硬约束,方向与 pg_schema_behind 门禁一致):**
- 先 upgrade、后起新代码:✅(旧 ORM 不 SELECT 新列,PG 多列无影响);
- 反过来先起新代码:❌ ORM SELECT 带新列 → PG `UndefinedColumn` → 通知接口 500。
即 **0006 先行安全,代码先行必炸**;顺序错了启动门禁(`pg_schema_behind`)会先拦。

**行为影响(上线瞬间)——时间线冷启动空窗(需拍板,建议已给):**
`/api/activity` 的 scenario 分支从 `updated_at` 反推切换为查 `activity_events`,
上线时表为空 → 时间线「场景」段空,直到首个事件落库(下一次编辑/重命名/分发)。
建议:**接受空窗**,不做「空表回退旧反推」的暖场逻辑 —— 旧口径本就不是真事件,
保留它等于留双口径,违背本轮「一处实现」纪律;前端给空态文案即可。
若不接受,替代方案是上线前用 `updated_at` 批量补一次 `scenario.edit` 存量事件
(一次性脚本,标注 synthetic),两案二选一后不得再改。

**数据增长:无需治理。** `activity_events` 在 autosave 5 分钟窗合并生效后,
每场景每窗最多 1 条 edit;按百场景日活估日增数百行,年 tens-of-万行量级、
detail 为小 JSON —— 不需要分区/保留期策略(P2 可选加清理)。
`notifications` 每 handoff +1 行,可忽略。

**回滚(0006 downgrade):**
1. 先起旧代码(旧 ORM 容忍 PG 多列,顺序宽松);
2. `alembic downgrade 0005`:`DROP TABLE activity_events`(**纯派生日志,
   可弃**;要留先导出)+ `DROP COLUMN` ×4(PG 原生 DROP COLUMN,快)。
3. SQLite 回滚源**不跑 0006**:本地 `app.db` 留在 0005 形态,回滚到 SQLite
   旧后端时旧代码不认新列,天然无冲突。

**未来 ETL(如有新环境再走 SQLite→PG):** 新列/新表由 ETL 的 metadata 驱动
逻辑自动纳入搬运集(非生成列);`payload`/`detail` 的 JSON 归一沿用 §3 已知
异型面,无新增变换语义。

### 8.3 执行清单(既有 PG 库)

```bash
# 1) 停后端(等 graceful,不 kill -9)
# 2) 迁移(cwd backend)
C:/Python314/python.exe -m alembic -c alembic.ini upgrade head
#    预期输出:0005_interaction_fields -> 0006_...(毫秒级)
# 3) 验形(应看到新列/新表)
#    psql: \d notifications  / \d service_aliases  / \d activity_events
# 4) 起新后端 → 冒烟:
#    - /docs 200、受保护路由 401(基线)
#    - GET /api/notifications 200(新列序列化不炸)
#    - GET /api/activity 200(scenario 段为空 = 空窗口径生效)
#    - POST /api/service-aliases 创建/编辑含 base_url 字段往返一致
# 5) 回滚预案:§8.2 末段
```
