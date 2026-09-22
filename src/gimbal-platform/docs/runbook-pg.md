# PG 运维 Runbook（骨架 — M0-5 建立，M2-T8 切换日前填充完整）

> 配套设计：《PostgreSQL迁移与后端化-设计方案》§3（迁移执行方案）、§8（风险清单）。
> 本文件是运维事件的唯一入口：起库、备份、切换日步骤、回滚。

## 1. 硬约束（违反即事故）

- **禁 `--reload`**：执行器触发约束延续，起服一律手动重启（§8 风险 9）。
- **禁多 worker**：单 uvicorn 进程语义不变——活跃行级状态在内存 `_row_states`、
  调度器是进程内线程/子进程，多 worker 会让两者分裂（§8 风险 10）。
- **PG 启动只校验不迁移**：current ≠ head 拒绝启动并打印待执行 revision；
  DDL 永远由人在带备份的窗口里手动执行（§2.1 第七轮分叉）。

## 2. 起库（开发与生产同文件）

```bash
# 仓库根
docker compose -f compose.pg.yml up -d          # 起库
docker compose -f compose.pg.yml ps             # 等 healthy
# 连接串（.env 用）：
#   DATABASE_URL=postgresql+asyncpg://gimbal:<密码>@<主机>:5432/gimbal
```

- 开发默认凭据 `gimbal/gimbal`；**生产必须用环境变量覆盖** `POSTGRES_PASSWORD`。
- 时区钉死：init 脚本 `pg-init/01-timezone.sql` 仅在卷**首次**初始化时执行；
  对既有卷（或忘了挂 init 的卷）手工补跑一次：
  `docker exec -it gimbal-pg psql -U gimbal -d gimbal -c "ALTER DATABASE gimbal SET timezone TO 'UTC';"`
- 国内网络拉不动官方镜像时，经可达镜像源拉取后打回官方 tag（compose 文件保持官方名）：
  `docker pull docker.1ms.run/library/postgres:16 && docker tag docker.1ms.run/library/postgres:16 postgres:16`

## 3. 备份策略（M0 定案，切换前必须已运转 ≥ 数日）

- **PG 侧**：`pg_dump` 每日定时（cron/计划任务），保留 N 份滚动；
  命名建议 `app-pg-YYYYMMDD-HHMMSS.dump`，目录与 SQLite 时代的 `app.db.bak-*` 分开。
  ```bash
  docker exec gimbal-pg pg_dump -U gimbal -d gimbal -Fc -f /tmp/app.dump \
    && docker cp gimbal-pg:/tmp/app.dump <备份目录>/app-pg-$(date +%Y%m%d-%H%M%S).dump
  ```
- **volume 侧**：compose named volume `pgdata_gimbal` 的离线备份说明（停库拷卷 或
  `docker run --rm -v pgdata_gimbal:/data -v <宿主目录>:/backup alpine tar czf /backup/pgdata.tgz /data`）。
- **密钥同等级保管**：`FERNET_KEY`/`JWT_SECRET` 与备份文件（含 Fernet 密文）同级——
  密钥丢 = 全部凭证密文不可解（§3.2 前置配置检查）。

### 3.5 ETL / preccheck 命令（M2 落地，backend 目录执行）

```bash
# ① 体检（不改数据只出报告；blocking_problems 必须为 0）
python scripts/pg_preccheck.py --db data/app.db

# ② 空目标库建 schema（切换链人工第一步）
DATABASE_URL=postgresql+asyncpg://gimbal:<pw>@<host>/<db>     python -c "from app.core.migrations import ensure_schema_sync;                import os; ensure_schema_sync(os.environ['DATABASE_URL'])"

# ③ ETL（演练必须用生产 app.db 的副本；报告落盘供逐项对比）
python scripts/migrate_sqlite_to_pg.py     --source <app.db 副本>     --target postgresql+psycopg://gimbal:<pw>@<host>/<db>     --report etl-report-<日期>.json
```

已演练（2026-09-21）：报告 `backend/gimbal-tmp-etl-rehearsal-2026-09-21.json`，全项 PASS。
已知语义：stars.json 中指向已删场景的悬空关注按 user_stars 的 CASCADE 语义滤除（计数入报告，不静默）；
时间戳照搬保历史（「func.now() 列不搬」按台账/对账要求修正，见脚本头注）。

## 4. 切换日 Runbook（M2-T8 填充；断点骨架先立）

1. [ ] 提前公告（用权限方案 announcement 通知首发；低峰窗口）
2. [ ] 停服（plate 可继续运行；平台后端停）
3. [ ] 备份 SQLite `app.db` → 只读保留作**回滚快照**（至少一个版本）
4. [ ] 空 PG 库 `alembic upgrade head` 建全部表（**人工第一步**，起服只校验）
5. [ ] 跑 ETL `scripts/migrate_sqlite_to_pg.py`，核对迁移报告
6. [ ] `.env` 切 `DATABASE_URL` → pg
7. [ ] 起服（禁 --reload；单 worker）
8. [ ] 冒烟：登录 / 场景列表 / 发起一次小执行 / 画像三页
   + 三条高危面（§3.3 第九轮）：①生成列筛选对拍（对比演练留存样本）
   ②删测试用户走通全链 ③旧执行详情「已过期清扫」显示正常
9. [ ] （回滚预案见 §5）

### 切换完成记录

- **2026-09-21 23:31 — 正式切换完成**（单部署内部平台,低峰直切）:
  备份 `data/app.db.bak-switch-20260921-233107`(回滚快照,只读保留);
  ETL 报告 `backend/gimbal-tmp-etl-switch-2026-09-21.json`(与演练报告逐项全等);
  三条高危面冒烟全过(生成列对拍/删测试用户/旧执行详情);浏览器终验正常。
- 回滚姿势:`.env` 的 DATABASE_URL 改回 sqlite 注释行(或删除该行,默认即 sqlite)
  → 重启后端。`data/app.db` 已被 legacy-adapt 适配到新结构,直接指向即可;
  切换后新产生的数据不回灌(切换点之后的数据以 PG 为准)。

### 存量 PG 库原地升级(版本化变更,如 0005)

新 revision 上线而目标库已承载业务数据时(非切换日空库场景):

1. [ ] 停平台后端(PG 起服**只校验不迁移**,落后会报 `pg_schema_behind`
   拒绝启动 —— 这是刻意设计,见 §6 第一行的处置);
2. [ ] backend 目录 `python -m alembic -c alembic.ini upgrade head`;
3. [ ] 起服,看日志走到 `Application startup complete`。

**量级注意**:加 STORED 生成列的 `ALTER TABLE … ADD COLUMN … GENERATED`
是**全表重写**(`composer_data_sets` 行多时锁表耗时随行数走)—— 大库
套用 0005 类变更走低峰窗口;空库切换日场景无此问题(直建即终态)。

**原地升级记录**:

- **2026-09-22 13:55 — 0005_interaction_fields 原地升级**(交互字段统一轮):
  远端 192.168.22.106 库,2 行数据秒级完成;`row_count` 转生成列后存量值
  自愈(ds-001=1/ds-002=2),六冗余索引消失、owner 复合索引在建、
  `v_scenarios_readable` 视图在场;后端重启冒烟通过。
- **2026-09-22 17:0x — asyncpg naive 绑定 -8h 事故修复**(时区复查轮):
  asyncpg 对 timestamptz 的 **naive** 绑定按客户端本地时区编码,
  `timeutil.utcnow()`(naive UTC)经 ORM 属性赋值/WHERE 比较落库整体
  -8h(`func.coalesce(col, naive)` 形态不受影响,PG 会话按 UTC 解析)。
  切 PG 后仅 executions 137 一行中招(finished_at),已按 JSONL 调度日志
  +case 目录 mtime 交叉验证后 `+interval '8 hours'` 修复;读侧影响仅
  活动窗口 since 实际比请求宽 8h(方向无害)。修复 = 全模型时间列换
  `UtcDateTime` TypeDecorator(PG 绑定侧 naive→UTC aware;DDL 逐字
  不变,无迁移),元数据不变量测试加「时间列必须 UtcDateTime」门禁;
  后端重启后线上探针 ORM 写入偏移 +0.000s、WHERE 绑定无偏移。

## 5. 回滚

- `.env` 切回 sqlite + 旧库文件，**不回退代码**（M2 同车代码不读任何新列）。
- 回滚库是 pre-alembic 存量库：启动分支识别后跳过 upgrade、打告警直跑。
- 切换后新产生的数据**不回灌**（内部平台可接受；靠低峰窗口 + 提前公告缓解）。

## 6. 常见故障

| 症状 | 处置 |
|---|---|
| 起服报 revision 不一致 | 按启动日志列出的待执行 revision，在备份后人工 `alembic upgrade <rev>`；**不要**改代码迁就 |
| ETL 中途失败 | 旧 SQLite 库未动过（ETL 只读源）；PG 侧可整库 DROP 重建后重跑 |
| 时区漂移（时间差 8h） | 两条独立防线：库级 UTC(§2)+ 列级 `timezone=True`(元数据断言把关);**驱动级**:asyncpg 对 naive 绑定按客户端本地时区编码,时间列必须走 `UtcDateTime`(绑定侧补 UTC,不变量测试把关),业务代码持续用 `timeutil.utcnow()` 即可 |

---

## 填充记录

- 2026-09-21（M0-5）：骨架建立。基线实测 **630 passed / 208.95s**（sqlite 全量）。
