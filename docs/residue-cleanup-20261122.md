# 残留数据清理与新结构改造记录

- **执行日期**：2026-11-22
- **分支/基线**：`feat/service-registry` @ b3f2a0db → af78dece
- **性质**：存量数据处置记录 + 兼容面清零清单（非审计报告；结论均已落地并验证）

---

## 0. 政策依据

本次处置遵循的开发期数据政策（2026-11-22 确立）：

> 现在整个项目还是开发阶段，对于以前的数据直接用新的结构定义改造就好了，
> 而不是为了兼容以前的格式，而增加冗余代码。
> 即可以对残留数据直接进行改造，但是不要为残留的数据做兼容适配。

三条执行口径：

1. **残留数据直接改造/清除**，不在读侧保留旧格式分支；
2. **一次性迁移/对账工具用完即退役**——使命耗尽的脚本不留在代码树（git 历史可考古）;
3. **向导类工具使命闭环即退役**——它服务的"残留侦察"对象归零后，工具本身成为冗余。

---

## 1. 残留数据处置（DB 侧，直接改造）

| 残留类别 | 处置 | 方式 |
|---|---|---|
| pre-M6 执行台账 | **67 个旧执行级联删除**（行/事件随级联清除），空 unit 行归零 | 直接对库一次性改造，未留脚本 |
| 清理后台账 | 全量为现行 M6 结构；JSONL 归档无存量消费者 | — |

处置后验证口径：执行台账 0 条 pre-M6 记录、空 unit 行 0、审计巡检归零。

---

## 2. 随之退役的读侧兼容代码（不留旧格式分支）

以下代码分支存在的唯一理由是"读取旧形态数据"，数据归零后一并删除：

| 兼容分支 | 位置 | 旧形态 |
|---|---|---|
| `_replay_rows` JSONL 回放 | `run_dispatcher.py` | M6 前存量单 DB 无行 → JSONL 归档只读回放兜底 |
| `build_report` snake_case 双键回落 | `run_dispatcher.py` | 旧事件流 snake_case 键回落读取 |
| `to_list_item_shape` visibility 兜底 | `scenario_store.py` | visibility=None 宽口径兜底 → 改为 REQUIRED，`derive_visibility` 单源 |

---

## 3. 一次性迁移/对账工具退役（21 个，使命耗尽）

这批脚本就是历次"数据改造以适配新实现"的执行器——**改造已全部完成、已验证，脚本按政策退役**。清单即改造目录：

### backend/scripts（3 个，随 0604be08 退役）

| 脚本 | 数据改造使命 |
|---|---|
| `migrate_sqlite_to_pg.py` | SQLite→PG 整库搬迁（2026-10-14 era 耗尽） |
| `pg_preccheck.py` | 搬迁前置校验 |
| `m0_verify_computed.py` | M0 计算列验收 |

### 根 scripts（18 个，随 90e7918e 退役，-3584 行）

| 脚本 | 数据改造使命 |
|---|---|
| `normalize_service_scope.py` | service_scope 旁挂键归位（服务范围归一） |
| `cleanup_credential_debt.py` | 凭证债三面清账（清账向导的数据侧配套） |
| `cleanup_authored_services.py` | 服务注册 authored URL 清账 |
| `backfill_import_anchors.py` | 导入锚点重锚定回填 |
| `p1_backfill_service_kinds.py` | 服务 kind 回填 |
| `rs3_backfill_meta_plate.py` | 场景 meta.plate 版本声明回填 |
| `retire_share_refs.py` | share_ref 退役清理 |
| `migrate_scheme_run_options.py` | RunScheme 运行配方选项迁移 |
| `migrate_field_state_catalog.py` | IO channel → state 三态目录化存量迁移（2026-09-05 设计） |
| `migrate_strip_binding_fields.py` | 锚点 binding 派生字段剥除对齐 |
| `migrate_legacy_case.py` / `migrate_legacy_case_pg.py` | 旧 Case 层场景迁移（Case 层解散，数据集直挂场景） |
| `migrate_stamp_json.py` | stamp json 结构迁移 |
| `gen_m2.py` | M2 类型契约生成（`_m2.py` 已固化） |
| `m2_step0_audit.py` | M2 存量审计 |
| `m2_step4_platform_migration.py` | M2 平台侧存量迁移 |
| `reconcile.py` / `reconcile_chain.py` | 一次性对账验收门 ×2 |

---

## 4. 凭证清账向导退役（使命闭环）

清账三面（服务范围 / 凭证 / 身份）已完成 `enforce` 且归零，向导的"残留侦察"对象不复存在，整链下线：

- **后端**（0604be08）：`GET /admin/cleanup-survey` 端点 + 请求/响应 schema 删除；admin 路由仅剩 audit-logs；
- **前端**（af78dece）：`CredentialCleanupWizard.vue` + 测试、路由、侧栏入口、类型定义整链退役；
- **巡检承接**：清账口径由 `scripts/audit_*` ×3 CLI 承接（保留项，见 §5）。

---

## 5. 保留工具与承接关系

| 保留 | 职责 |
|---|---|
| `audit_*` ×3 | 清账三面巡检 CLI（向导退役后的巡检口径承接者） |
| `check_migration_drift.py` | alembic 模型/迁移漂移门 + fixtures 快照 |
| `gen_api_contract.py` | OpenAPI / error-codes 契约快照生成与校验 |
| `bootstrap` / `ext_gates` / `release` / `verify_all` | 工程链 |

---

## 6. 验证与提交索引

- 后端 **2183 passed**（含契约快照随批重生）；前端 **1536 passed / vue-tsc 0**；
- 提交索引：
  - `0604be08` fix(platform-backend)：授权边界/读面闸收口 + 执行台账单源化 + **残留清除**（含 §1 数据处置、§2 兼容分支删除、backend/scripts ×3、清账端点下线）
  - `90e7918e` chore(scripts)：**一次性迁移/对账脚本退役 ×18**
  - `af78dece` fix(platform-frontend)：评审修复 + 单源化 + **清账向导整链退役**
- 效果：代码树中"为旧数据服务"的分支、脚本、向导**全部清零**；读侧对任何旧格式的容忍面为零。
