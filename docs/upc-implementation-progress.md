# UPC 实施进度记录

> Unified Project Context(UPC)v2.10 · 实施进度与验收台账
> 设计契约:**01-Gimbal-UPC-v2.10-Design.md(冻结稿)**,基线 main @ `3e71a998`
> 实施分支:`feat/upc`(自基线派生;迁移链接在 `0066_incremental_model_align` 之后)
> 最后更新:2026-11-26(M2 完成后、review 补充提交 `42868c58` 之后)

---

## 1. 里程碑总览

| 阶段(§16) | 状态 | 承载提交 | 出口条件核验 |
|---|---|---|---|
| M0 目标契约 | ✅(有登记缺口,见 §4) | (无独立工件,契约 = v2.10 冻结稿) | 契约签核 = 文档冻结;开发数据属性已确认;实际重建另设准入 |
| M1 容器与授权 | ✅ | `260b7138` + `8febbf26` | 多私有空间(AC-02)/ 项目列表与对象可见性一致(AC-51)/ 隔离结构 Suite 父端移动 / §20.4 双路径断言 —— 全过 |
| M2 领域服务/API | ✅ | `4523046a` | 统一契约无旧归属分支及 JSON 权威绑定 / 修复状态迁移 / §20.5 升级 fixtures / 诊断脱敏 / 正式 precheck 最小链路 / AC-45–47 —— 全过(46 补齐于 `42868c58`) |
| M3 执行装配 | ⬜ 未开工 | — | 新执行契约、全部装配入口负向、AC-48–50/53;复跑 M2 样例完整装配 |
| M4 前端 | ⬜ 未开工 | — | 三类空间 E2E + AC-52 异步乱序 |
| M5 迁移与验证 | ⬜ 未开工(准入另设) | — | 开发库重建、场景导出/导入、独立 DDL 升级验证、恢复报告 |
| M7 清理 | ⬜ 未开工 | — | DoD |

**回归基线(截至 `42868c58`)**:全量 `2286 passed / 2 skipped / 0 failed`(真实 PG 测试库,xdist);
契约快照(openapi/error-codes + 前端 openapi.ts/errorCodes.ts)已重生,守卫 3/3 绿。
**dev 库(gimbal-pg@5432)全程未动** —— M5 破坏性操作单独准入。

---

## 2. 各里程碑交付要点

### M1(UPC-01/03/04:容器、授权、能力)

- **Project 容器模型**(`app/models/project.py`):kind ∈ {private, public, normal};
  `project_uid`(§13.2 不可复用身份);private↔owner 形状 CHECK、public 唯一部分索引、
  每用户默认私有唯一部分索引(AC-01 并发权威)、名称分域唯一、status 四态 + kind 不可改。
- **库层不变量单源三路径**:`PROJECT_CONTAINER_DDL`(models/project.py 尾部)由
  0067 迁移、空库自举(ensure_schema_sync)、conftest 三处共享 —— §20.4 双路径结构一致
  的前提。六组触发器:private/public 无成员行、活跃 normal ≥1 有效 admin(延迟约束×3,
  覆盖成员增删改/项目状态/用户停用)、每非系统用户 ≥1 默认空间(系统用户排除)。
- **能力矩阵**(`app/policies/__init__.py`):§7 唯一规范性矩阵的代码化;未登记能力
  KeyError 默认拒绝;矩阵之外无第二套开关。
- **授权**:`zone_read_clause` / `_ownership.can*` 收敛为项目关系判定;
  `/auth/me`、`/projects`、详情、context 同源谓词(AC-51,含 ops.write 非所有者不可枚举)。
- **§20.2/§20.6 隔离结构验证**(`tests/test_upc_isolated_ddl.py`):真实 PG 上
  跨区绑定即拒、伪造 Scheme.project_id 拒、合法延迟事务移动成功、非法提交失败回滚、
  引用删除保护、Suite 单父移动失败/整体移动成功/父删级联。

### M2(UPC-02:资源容器收口)

- **§5 资源表**:scenario / suite / report / integration 模板行 / account_combo
  全部 `project_id NOT NULL` 真实 FK;Suite `UNIQUE(project_id, name)` 替代 owner+name。
- **迁移 0068**(`alembic/versions/0068_upc_resource_containers.py`):
  - §20.5 中止闸:非空 `payload.accountComboId` 证据 → RuntimeError 整笔回滚(版本钉 0066,无半成品列);
  - **排序要点(踩坑记录)**:0066 期单列 FK 是 `DEFERRABLE INITIALLY DEFERRED`,
    回填 UPDATE 会排队挂起触发事件,阻塞随后的 `SET NOT NULL` ALTER(PG ObjectInUse
    "pending trigger events")—— **触发器 + 单列 FK 的 drop 必须先于回填 UPDATE**
    (run_schemes 与 suite_members 两处均已前置);
  - trgm 索引按「链收敛到模型」纪律摘除(M3 检索 SQL 化时按需再补)。
- **§20.2 复合契约**:`fk_scheme_scenario_zone` / `fk_scheme_combo_zone`
  (NO ACTION DEFERRABLE INITIALLY IMMEDIATE)+ `uq_scenario_project_scenario_id` /
  `uq_combo_project_id` 候选键 + 双索引;`ck_scheme_combo_repair`。
- **§20.6**:suite_members `project_id NOT NULL` + 双复合 FK(CASCADE)取代 0042 触发器;
  迁移先回填核验两端一致。
- **§16.1 绑定收敛**:`scheme_store.normalized` 恒剥 `accountComboId`;DTO ↔ 显式列
  双向映射;全仓归类扫描 = 仅 DTO/显式列/注释;运行链零 payload 消费。
- **§20.3 修复状态域**(`app/services/scheme_repair.py`):blocked 状态 + 三原因码 +
  诊断授权投影(combo_missing 仅内部;无权一律 `combo_dependency_invalid`;
  修复命令不成存在性探针)+ `rebind_combo`/`confirm_no_combo` 命令(expected_revision
  原子,审计 `scheme_repair_events` 同事务)+ **正式 precheck 首闸**(blocked 在凭证
  解析前返回,凭证调用数为零,有 monkeypatch 断言)。
- **§14.2 资产包闭环**(`app/services/scenario_asset_package.py`):导出(秘密剥离)→
  原子恢复(幂等键 = project×packageId×sourceScenarioId;默认候选零提交;组合确定性
  映射 / skipCombos→combo_missing / 跨区→blocked;只 flush 单事务提交)→ 预检。
  并发同键败者收敛(§14.2「重试可继续」):IntegrityError → 回滚重查台账 →
  同摘要重放 / 异摘要 409。
- **授权收口顺带修正**(review 中抓到的退役口径残留):`adaptation_service._ensure_batch_scope`
  与 `project_promotion.analyze_promotion` 的「project_id 空 = 私有区」判定 → 容器 kind 判定;
  `project_space.dispose_private_assets` 删场景前漏清方案行(NO ACTION FK)→ 已补。

### Review 补充(`42868c58`)

- **AC-31 并发不变量**(`test_upc_m1_container.py::TestConcurrentInvariants`):
  末位双 admin 并发互删 / 停用×降级交错 / 默认切换竞争 —— 双会话事务边界拼出真实交错,
  证明延迟触发器与部分唯一索引在 COMMIT 求值点不被击穿。
- **AC-46 故障注入**(`test_upc_m2_domain.py`):写 Scheme 处 / 事务内审计处注入 →
  整场景零提交;并发同键重试收敛(恰一份场景 + 台账一行)。

---

## 3. 对照 v2.10 review 结论(2026-11-26)

**符合度总评:M0/M1/M2 高符合,M2 出口六条全过。**

已闭缺口:
- AC-46 故障注入腿 + AC-31 并发竞争用例(见 §2,`42868c58` 补齐)。

仍开放的事项(均已定位归属,详见 §4):

| 事项 | 来源 | 归属建议 |
|---|---|---|
| M0 装配入口登记表未持久化 | §20.3「M0 登记实际入口」/ §11.3 系统默认凭证来源登记 | M3 开工前补一份入口登记(代码 docstring 或 docs) |
| Integration 拆表未完成 | §5 终态「禁止模板实例同表」;当前单表两层 + `ck_integration_task_shape` 形状约東(模型注释已声明延期) | M3(§11.5 执行/调度)交付清单显式登记 |
| 项目删除状态机(§13.1)与默认空间切换端点 | 模型落列,流程未实现 | M3/M5 生命周期交付;「删除与派发竞争」并发用例随其落地 |
| §9 project-scoped 路径未全面切换 | 场景/套件/报告仍走全局路径 + zone 谓词 | M3/M4 边界显式裁定(补端点或裁定现契约为定稿) |
| graph_dispatch.py:301 死分支 + 陈旧注释 | project_id 恒非空,分支永不走(行为正确) | M3 装配重整时顺带清 |
| AccessToken principal_id(§20.1)/ ExecConfig XOR(§11.2) | 设计属 M3 范围 | M3 清单登记 |

---

## 4. 环境与操作备忘(跨会话有效)

- 后端 cwd:`src/gimbal-platform/backend`;venv:`/root/gimbal/.venv`。
- 测试库:`TEST_DATABASE_URL="postgresql+asyncpg://gimbal:gimbal@127.0.0.1:15432/gimbal"`
  (**口令是 `gimbal:gimbal`,曾两次误打 `gimbal@gimbal` 浪费整轮**)。
  dev 库是 5432,**不许动**;测试库是 15432。
- 测试机制:conftest schema-per-test 池 + create_all + `PROJECT_CONTAINER_DDL`;
  `asyncio_mode=auto`(不要写 `pytest.mark.anyio`);xdist 默认 `-n16`,单进程用 `-n0`。
  era 形态测试:`test_migrations._relax_project_zone` / `_to_0039_shape` /
  `_to_0066_shape`(M2 升级 fixtures)。
- **`fresh_db` 用测试函数同一个 monkeypatch 实例绑定 `db_module.engine/SessionLocal`**
  —— 测试中途 `monkeypatch.undo()` 会撤销引擎绑定(`relation "users" does not exist`)。
  局部注入用独立 `pytest.MonkeyPatch()` 实例。
- 直插/移动布景:`tests/helpers.py` 的 `mk_user_with_space` / `mk_normal_project` /
  `default_space_id` / `scenario_project_id`;场景迁区须「SET CONSTRAINTS
  fk_scheme_scenario_zone[, fk_scheme_combo_zone] DEFERRED + 方案行同迁」
  (参考 `test_authz_s11_projects.py` 的模式)。
- 注册面有速率限制 → 每用例唯一用户名;`mk_user_with_space` 密码哈希是 "x",
  需要登录则**先 register 再用 API 建**(见 helpers 注释)。
- 契约快照:改动路由/模型/错误码后须 `python scripts/gen_api_contract.py gen` +
  `python scripts/gen_frontend_contract.py`,error-codes 的 sites 记录**源码行号**
  —— 服务内 raise 位置移动也会造成合法漂移,重生成即可。
- grep 守卫(`test_grep_guard_owner_compare.py`):allowlist 键 = 扫描器逐字行,
  收编语义后的行要同步增删,陈旧条目会被 `test_allowlist_has_no_stale_entries` 抓出。

---

## 5. 下一步(M3 起)

1. **M3 开工前**:补装配入口登记表(§3 表中第 1 行)。
2. **M3 主体**:§11 配置解析 / 凭证来源 / 环境链 / 调度 / 快照;§20.3 统一装配闸接入
   execute / query / schedule / probe 全入口;§20.1 AccessToken / §11.2 ExecConfig
   单表 XOR / Integration 拆表;清理 graph_dispatch 死分支。
3. **M4**:ProjectLayout + 模块注册;裁定 §9 路径形态(§3 表第 4 行);AC-52。
4. **M5(准入另设)**:先场景清单导出保护,再重建 dev 库;§14.2 全清单恢复;
   独立 DDL 升级验证全量复验(§20.4 断言套件)。
