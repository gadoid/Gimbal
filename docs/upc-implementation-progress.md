# UPC 实施进度记录

> Unified Project Context(UPC)v2.10 · 实施进度与验收台账
> 设计契约:**01-Gimbal-UPC-v2.10-Design.md(冻结稿)**,基线 main @ `3e71a998`
> 实施分支:`feat/upc`(自基线派生;迁移链接在 `0066_incremental_model_align` 之后)
> 最后更新:2026-11-27(评审六轮 3 P2 + M3 主体收口 + M5 前置件导出保护就绪,全量 2367 绿;M4 与拆表类待冻结稿,dev 库重建待破坏性准入)

---

## 1. 里程碑总览

| 阶段(§16) | 状态 | 承载提交 | 出口条件核验 |
|---|---|---|---|
| M0 目标契约 | ✅(有登记缺口,见 §4) | (无独立工件,契约 = v2.10 冻结稿) | 契约签核 = 文档冻结;开发数据属性已确认;实际重建另设准入 |
| M1 容器与授权 | ✅ | `260b7138` + `8febbf26` | 多私有空间(AC-02)/ 项目列表与对象可见性一致(AC-51)/ 隔离结构 Suite 父端移动 / §20.4 双路径断言 —— 全过 |
| M2 领域服务/API | ✅ | `4523046a` | 统一契约无旧归属分支及 JSON 权威绑定 / 修复状态迁移 / §20.5 升级 fixtures / 诊断脱敏 / 正式 precheck 最小链路 / AC-45–47 —— 全过(46 补齐于 `42868c58`) |
| M3 执行装配 | ◐ 主体收口(§20.3 全入口 + 组合垫底**八面全接** + 出口条件「复跑 M2 样例完整装配」;AC-48–50/53 与 §11 细节项待冻结稿) | 工作区(未提交) | §20.3 闸全入口负向(6 测)+ 组合垫底八面(7 测 + 查询面 §7.1 6 测,含完整装配 e2e: blocked→修复→dispatch→done)+ 装配入口登记表 + graph_dispatch 死分支清理;AC-48–50/53 与 §11 执行契约细节待冻结稿 |
| M4 前端 | ⬜ 待设计稿(见 §3.11 注) | — | 三类空间 E2E + AC-52 异步乱序;ProjectLayout/模块注册仅存名于台账引用,冻结稿不在库 → 无法忠实实施 |
| M5 迁移与验证 | ◐ 准备件就绪(§3.11.6 导出保护落地,测试库验证;重建待破坏性准入) | 工作区(未提交) | ① 导出保护 CLI 已就绪 → ② 开发库重建(**破坏性,单独准入,未执行**)→ ③ §14.2 全清单恢复(既有 API)→ ④ verify 对账 + 恢复报告;独立 DDL 升级验证 = 既有 §20.4 双路径套件 |
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
| 项目删除状态机(§13.1)与默认空间切换端点 | ✅ archive/restore/set-default 已落地(§3.11.3;deleting/delete_failed 异步批删态保留建模,随 M5 交付) | 已收口;「删除与派发竞争」并发用例由既有 delete_project 显式清理面承接 |
| §9 project-scoped 路径未全面切换 | 场景/套件/报告仍走全局路径 + zone 谓词 | M3/M4 边界显式裁定(补端点或裁定现契约为定稿) |
| graph_dispatch.py:301 死分支 + 陈旧注释 | project_id 恒非空,分支永不走(行为正确) | M3 装配重整时顺带清 |
| AccessToken principal_id(§20.1)/ ExecConfig XOR(§11.2) | §11.2 形状闸已落地(§3.11.4);§20.1 推断审计完成 —— **结论:不做盲改**(§3.11.5:身份活取 + 各存续面快照已齐,活取语义与换绑恢复产品语义一致;列语义/位置/回填三无依据) | principal_id 待稿裁定;拆表类重构(§11.5)同判定待稿 |

---

## 3.5 评审修复轮(2026-11-26,review 结论落地)

外部评审 4 高 + 5 中全部收口(工作区未提交,base = `b0ccd051`):

**高优先级**
- **H1 资产包 blocked 往返**:导出随包携带 `repairStatus`/`repairReason`/受限
  `sourceComboRef`;恢复侧对无映射的源 blocked 方案原样重建 blocked(矛盾输入
  dep 不采信;显式映射仍可显式修复)。回归 `test_blocked_scheme_roundtrip_stays_blocked`。
- **H2 用户处置组合绑定**:`users.py` 处置 publicize/transfer 在方案迁出私有空间
  前经 `scheme_repair.mark_blocked(combo_missing, action=disposal.unbound)` 解离
  绑定 —— 不再撞 `fk_scheme_combo_zone` 500。回归 `test_disposal_severs_combo_bindings`。
- **H3 项目授权旁路**:`_require_manage` normal 分支摘除 ops.write 旁路(D1/§6/AC-51
  与可见性同源);成员管理四端点改 `_load_visible_project`;删除 = 成员管理员 ∧
  Admin+(§6 投影 `project.delete = is_ops` 于管理员分支)。既有 s14/membership
  测试按新契约调整;回归 `test_adminplus_nonmember_no_manage_bypass`。
- **H4 迁移/双路径**:0067 补 `project_uid` 唯一约束、0068 补 `scheme_uid` 唯一约束
  (命名随 create_all 自动名,§20.4 索引断言按名比较);0068 三处 `sa.JSON()` →
  `JsonVar`(PG jsonb 同型);`_build_chain` 增 `_strip_upc_shapes` 时代造形 ——
  链路径还原 ≤0066 起点,0067/0068 增量分支真实执行(守卫空转的假绿盲区消除,
  由此现形并修掉 description/actor_name server_default 与 ix_account_combos_project_id
  三处漂移)。双路径 6/6 绿。

**中优先级**
- **M1**:修复命令入口 `db.refresh(with_for_update=True)` 行锁串行;回归
  `test_repair_command_revision_race_serialized`(同 revision 双会话竞态恰一笔生效)。
- **M2**:删除内容闸外的历史台账行(`scenario_asset_imports`/`project_promotions`)
  随项目显式收口;`project.deleted` 审计移到成功删除之后(`audit.record` 自带
  commit,删除失败不得留假审计)。回归 `test_delete_cleans_history_ledger_rows`。
- **M3**:Suite 改名查重轴换 `(project_id, name)`(与 `uq_suites_project_name`
  同轴;跨项目同名不再误 409)。
- **M4**:资产恢复按源 `combo:<id>` ref 去重映射 —— 多方案引用同一源组合只建一份。
  回归 `test_shared_combo_dedup_across_schemes`。
- **M5**:末位管理员预检换 `count_valid_admins`(在职 ∧ 非系统,与触发器同口径)
  —— 存在非活跃 admin 残留行时 409 预检,不再 API 放行后撞触发器 500。回归
  `test_last_admin_precheck_counts_valid_only`。

**验证**:`2292 passed / 2 skipped / 0 failed`(真实 PG 测试库 15432,xdist);
契约快照重生(openapi/error-codes + 前端 openapi.ts),守卫 3/3 绿;
grep 守卫白名单同步删两条已收口条目;分支 `git diff --check` 干净;
新改文件 Ruff correctness 零新增违例。

---

## 3.6 评审二轮修复(2026-11-26,7 主项 + 9 P2 全部收口)

**主项**
- **P1-1 导出脱敏**:`export_bundle` 增 `viewer` 参数,非属主数据集行经
  `strip_sensitive_columns`(与数据集单读同一 `is_foreign_viewer` 谓词)。
  回归 `test_upc_m2_review2.py::TestExportRedaction`。
- **P1-2 blocked 预检零凭证解析**:`run_precheck` 外层 `builtin_auth_shadowed`
  与套件 validate 两处 `_shadowed_item`、编排模式 shadowed 面均 gate 在
  `repair_blocked`/默认方案 blocked 之后。探针升级为**非属主执行人 +
  config.users**(P2-15):blocked 零 `resolve_exec_auths`,ready 对照腿 ≥1。
- **P1-3 处置台账与原子性**:`dispose_private_assets` 补
  `ScenarioAssetImport`/`ProjectPromotion`;`scenario_store.delete(commit=)`
  与 `audit.record(commit=)` 增事务内路径,purge 与处置审计并入最终事务。
  回归 `test_upc_review2_authz.py::test_disposal_purge_cleans_history_ledger_rows`。
- **P1-4 0068 同名 Suite**:`_dedup_suite_names` 确定性重命名(保 id 最小,
  余者「名-迁移N」);回归 `test_upgrade_renames_same_name_suites_in_one_project`
  (真实 0066 形态造数升级)。
- **P1-5 归档闸**:`can()` 写/run 动词与 `can_run_scenario` 查项目状态;
  `effective_permissions.project.update` 收敛 active 门。回归
  `test_archived_project_blocks_write_and_execute`(PUT 403 / run False / 恢复对照)。
- **P1-6 默认权威**:恢复以 `defaultSchemeId` 落库唯一默认;包内标记冲突
  422 `asset_bundle_default_conflict`;报告与库一致断言。
  回归 `TestDefaultSchemeAuthority`。
- **P1-7 成员管理 TOCTOU**:`_require_manage_locked` 写点对操作者成员行
  FOR UPDATE 重验(add/patch/remove);回归 `test_member_manage_serialized_
  on_operator_row`(持锁阻塞 + 降级后 403)。

**P2**:公共项目组合读路径 ComboError 统一映射 422(P2-8);导出修复状态走
授权投影、`sourceComboRef` 不随包(P2-9);规范化先于默认候选校验(P2-10,
回归旧式 dataSetIds);缺省 packageId 派生 `auto-<src>-<digest16>` 稳定键
(P2-11,重试收敛回归);嵌套形状边界校验统一 422(P2-12,六类形状用例);
facets 读门换 `can_view_project` 同源谓词(P2-13);普通 PUT 可选
`expectedRevision` 行锁 CAS(P2-14,落空 409 回归);默认切换真实交错用例
(P2-15,重叠窗口证据 + 顺序语义测试表述下调)。

**验证**:全量 `2306 passed / 2 skipped / 0 failed`(真实 PG 测试库
15432,xdist);契约快照随 RunScheme.expectedRevision 重生,守卫 3/3 绿;
新改文件 Ruff correctness 零新增违例;`git diff --check` 干净。

---

## 3.7 评审三轮修复(2026-11-26,7 主项 + 3 P2 收口)

- **R3-1 处置内通知**:`users.py` publicize 面的外部 holder 通知
  `create_notification(commit=False)` —— 不再把此前的场景迁移/模板删除
  提前落库。
- **R3-2 审计 savepoint**:`audit.record(commit=False)` 改走
  `begin_nested()` —— 审计失败只回滚审计行自身,**禁止回滚调用方
  事务**(修前失败分支无条件 rollback + 吞错,可把 transfer/publicize
  退化成 purge)。
- **R3-3 晋升申请收口**:用户处置按 `applicant_id` 删除
  `ProjectPromotion`(覆盖 pending/approved/rejected;普通项目行不随
  私有容器走)。回归 `test_disposal_cleans_promotions_by_applicant`。
- **R3-4 编排装配闸**:编排 validate 按单元**实际 schemeId**
  (`resolve_for_run` 与执行链同选择语义)先过 `require_ready` ——
  blocked 结构化禁跑(整体不可运行 + 明细),别名收集/`resolve_exec_
  auths`/物化零调用。回归 `test_graph_validate_blocked_scheme_forbids_run`。
- **R3-5 最长名迁移**:`_dedup_suite_names` 候选名先按 varchar(128)
  截断再消歧。回归 `test_upgrade_renames_128_char_same_name_suites`
  (128 字符同名真实 0066 形态升级)。
- **R3-6 归档管理写封闭**:patch_project / 成员增删改 / 组合写统一
  409 `project_not_active`(与创建闸同码);权限投影
  `project.member.manage` 收敛 active 门。回归
  `test_archived_project_blocks_management_writes`。
- **R3-7 行锁覆盖**:`_require_manage_locked` 扩展到 patch_project /
  delete_project(normal 分支)。回归
  `test_project_patch_delete_locked_reverify`。
- **P2**:comboDependencies[*].entries/ref 边界校验统一 422(P2-8);
  同 ref 复用前比对条目规范化指纹,矛盾 422
  `asset_bundle_combo_conflict`(P2-9,回归);前端 SchemeWorkbench
  保存随读取 revision 发 `expectedRevision`,409 刷新本地并提示重试
  (P2-10;typecheck + vitest 729 绿)。

**验证**:全量 `2314 passed / 2 skipped / 0 failed`(真实 PG 测试库
15432,xdist);契约快照随新错误码重生,守卫绿;`git diff --check` 干净;
新增测试文件 Ruff correctness 零违例。

---

## 3.8 评审四轮修复(2026-11-27,2 P1 + 6 P2 收口)

- **P1-1 归档 remove_member**:`remove_member` 补 `_require_active`;
  `_can_manage`/`_can_write` 投影收敛 active 门。回归
  `test_archived_project_blocks_remove_member`(409 + canManage False;
  公共项目恒 active,B1 遗留行清理通道不受影响)。
- **P1-2 归档凭证写**:`project_credentials._manage_gate` 补 active 闸
  (创建/设默认/PATCH/删除四入口复用);列表 canManage 同步。回归
  `test_archived_project_blocks_credential_writes`(修前运行时探针 201)。
- **P2-3 资产包形状**:schemes[*].schemeId 唯一性 + dataSetSelection
  对象数组 + injectionEntryIds 数组校验(修前重复默认候选撞唯一索引
  500、selection 非数组迭代 TypeError)。回归两条。
- **P2-4 编排闸两遍法**:第一遍全部单元授权+装配闸(blocked 即收
  not_runnable),全部 ready 后第二遍阴影凭证检查/别名收集/物化 ——
  blocked 单元无论次序,凭证解析零调用。回归:ready 在前 blocked 在后
  `resolve_exec_auths` 零调用。
- **P2-5 单元选择单源**:新增 `scheme_store.resolve_unit_scheme`
  (显式 schemeId / 仅行→默认 / 都无→裸基线),编排预检、执行器
  resolve_graph_units、多行提示三处共用;裸基线单元不再被预检误报
  blocked(修前预检走 resolve_for_run 回落默认)。回归:裸基线编排
  默认方案 blocked 仍 ok=true + no_scheme 提示。
- **P2-6 前端 CAS 闭环**:冲突判定改 `httpStatusOf(e) === 409 &&
  code === 'scheme_revision_conflict'`(修前读 e.response.status,
  拦截器实抛 ApiError 永远进不了分支);重命名同发 expectedRevision;
  测试消费拦截器形态 ApiError(4 条,含非版本冲突不误伤)。
- **P2-7 修复命令锁序**:rebind_combo 改 **combo→scheme** 全序
  (require_combo_bindable lock=True 先行,scheme 锁到手后重验
  blocked/revision;ComboError 折算 RepairCommandError,修复面
  不可读组合按 §20.3 恒 404)。与普通 PUT 不再对锁成环。
- **P2-8 成员锁序**:成员写点一次锁定 {操作者,目标} 行按 user_id
  升序 FOR UPDATE;**连带发现并修复**:remove 的 `_audit` 自带
  commit 在写点中途提交、释放刚锁的行(固定序锁形同虚设 + 末位
  预检退化 TOCTOU)→ 改并入最终事务。回归:真交错 asyncio.gather
  双管理员互降 + remove×patch 交叉,无 500/IntegrityError,后到者
  行锁重验 403(P1-7 语义)。

**验证**:全量 `2322 passed / 2 skipped / 0 failed`(真实 PG 测试库
15432,xdist);契约快照重生守卫绿;前端 typecheck 干净 + vitest
SchemeWorkbench 7 绿;`git diff --check` 干净;新测试文件 Ruff
correctness 零违例。另:`test_p35_rollout_fixes` 恢复序列用例在 xdist
并发下偶发(单跑 3/3 绿,与本轮改动无关)——已留意,后续单独排查。

---

## 3.9 评审五轮修复(2026-11-27,1 P1 + 7 P2 收口)

- **P1-1 run/materialize blocked 装配闸**:整图方案 ready 校验提取为
  `_assembly_gate`(validate 与 run 共用同一实现);`_run_orchestration`
  在创建 execution、凭证解析**之前**完整执行(修前 run 只查场景可运行
  性,blocked 方案仍入队物化并解密凭证 —— validate ok=false vs run 201
  契约裂缝)。**单源兜底**:`graph_dispatch.resolve_graph_units` 对
  blocked 方案直接 GraphDispatchError —— validate 预检 / 凭证清单
  (missing_auth_aliases)/ materialize_graph(worker 重物化)共同路径,
  绕过路由预检也进不了物化。回归:run 403 units_not_runnable +
  resolve_exec_auths 零调用;resolve_graph_units 直测 blocked raise /
  ready 放行。
- **P2-1 归档探测面**:`_manage_gate` 归档闸移到**角色校验之后** ——
  非成员访问归档项目写端点恒 404(与 active 同面),不再以 409 + 具体
  状态泄露项目存在性/生命周期。回归:外部人 404 / 管理员成员 409。
- **P2-2 实例凭证聚合**:`instance_credential_matches` 投影收敛
  `role == admin && status == active`(与 list_project_credentials 同
  一口径)—— 归档管理员不再看到 canManage=true 与明文 username。回归:
  归档后 canManage False + username 全脱敏。
- **P2-3 形状补漏**:`_validate_shape` 补:payload 判型不许 `or {}` 吞
  falsy([] / 0 → 422)、selection 条目 datasetId 须非空字符串(列表键
  重指映射 TypeError)、rowIndexes 须整数数组、旧式 dataSetIds 须非空
  字符串数组(规范化迭代 TypeError)。回归 6 例(修前函数探针全 500)。
- **P2-4 rowIndex 错误面**:非法 rowIndex(非整数)在 resolve_graph_
  units 转 **GraphDispatchError**(4xx 面),不再被 validate 基础设施
  降级分支吞成 degraded warning(修前「预检绿 + degraded + run 201」);
  composition 写边界补 row/schemeId 结构校验(落库前 422)。回归:写
  边界 5 例 422;存量直改库后 validate 报 materialize_failed error 且
  degraded=false。
- **P2-5 末位管理员 TOCTOU**:成员写点**先锁项目行**(projects →
  project_members 全仓一致锁序,与 project_tokens 治理面同向)—— 两名
  管理员并发自降级/自移除不再双双读到「还有两名管理员」;patch/remove
  提交期 IntegrityError 按触发器消息/驱动异常名识别
  (`project_admin_required`,SQLAlchemy 2.0 无 CheckViolation 专类)
  兜底映射 409 last_project_admin。回归见 P2-6。
- **P2-6 锁交错 barrier**:评审四轮裸 gather 并发测试升级 —— 包装
  `_require_manage_locked` 的 barrier(先到者持锁挂起,后到者入场即
  上报后真阻塞),强制命中「一方持锁、另一方等待」窗口;补**自降级/
  自移除**双管理员场景。收口后结果确定:交叉 patch (200,403)、
  remove×patch (204,404)、自降级 (200,409)、自移除 (204,409),
  库内恰留一名管理员(修前后提交者撞延迟触发器 500)。
- **P2-7 假绿修正**:后端 —— blocked 顺序测试改**外部执行人**布景
  (发起人 ≠ 场景属主,ready 单元携带存量内置凭证基座):修前属主自检
  分支吞探针、旧交替循环同样零解析;新布景下计数真实可判。前端 ——
  ApiError/httpStatusOf 上提零依赖 **@/api/httpError**(http.ts 转发
  导出,调用点不受影响),测试直接消费真实错误模块(弃 vi.hoisted
  同形类);列表快照带 revision,断言保存/重命名请求**真的携带**
  expectedRevision(修前显式断言 undefined)。

**验证**:全量 `2331 passed / 2 skipped / 0 failed`(真实 PG 测试库
15432,xdist;+9 = 新增 review5 文件 8 例 + review4 升级);契约快照
重生守卫绿(前端生成件 noop,无新增错误码);前端 typecheck 干净 +
vitest 全量 1547 绿(含 SchemeWorkbench 7 例);changed 文件 Ruff
correctness 仅存 HEAD 既有 F401(非本轮引入)。

---

## 3.10 评审六轮修复(2026-11-27,3 P2 收口)

- **P2-1 缺省 rowIndex 读取面**:row 省略 rowIndex 是写入边界接受的
  合法缺省(默认 0),validate 的 row_single 告警读取端统一
  `.get('rowIndex', 0)` —— 修前直接下标 `u['row']['rowIndex']` →
  KeyError → 500(合法配置无法预检)。回归:多行方案 + 缺省 row 的
  PUT→validate 200,告警「第 0 行」。
- **P2-2 单元级参数写入闸 + cap 一致**:`_validate_composition` 补
  needs(非空字符串数组)/repeat/nRuns(非 bool 整数,1..cap 与
  SUITE_RUN_TOTAL_CAP 同界)/injectionEntryIds(非空字符串数组)——
  修前 needs=7 在 needs_edges 推导 TypeError→500,"x" 落库后
  validate est `int("x")` ValueError→500,负值把 est 压到 0 以下
  **绕过总 cap**(est>cap 恒假)。est 改共享 `_estimate_graph_runs`
  (validate/run 同一实现):图级 nRuns 的整图乘法按物化 setdefault
  语义计入 —— 修前 est 漏乘图级 nRuns,单值合法但总量绕 cap
  (评审「尚未证明」的绕界路径实为图级乘法 + 负值两条,均已堵)。
  写入闸前落库的遗留垃圾:_build_graph_spec 人话 ValueError,validate
  报 error 级 mode_config_invalid、run 422,不再拼装层 500。
- **P2-3 无 CAS 解绑「200 但未生效」**:`update_scheme` **恒取方案
  行锁**(修前仅 CAS 腿 FOR UPDATE 刷新)。根因:无 CAS 保存工作在
  过期快照上 —— 并发 rebind 提交 combo=1/rev=3 后,解绑的 ORM 对象
  仍持旧值,赋同值(None→None)不产生 UPDATE diff,commit 只写
  revision=3 → 200 但绑定未解除 + 与换绑共享 revision=3(破坏
  CAS token 唯一性)。行锁位于调用方 combo 校验
  (require_combo_bindable 已锁组合行)之后,combo→scheme 全序不变;
  锁内重读后写入,200 = 真生效,revision 严格递增。回归:确定性
  服务层交错(解绑读过行挂起→换绑提交→放行)断言响应与库内
  accountComboId=None、rev=4(修前 combo=1/rev=3);CAS 腿契约不变
  (expectedRevision 落空仍 409 scheme_revision_conflict)。

**验证**:全量 `2337 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+6 = review6 新文件);契约快照重生守卫绿(前端 errorCodes 有
一行位点漂移,已重生);Ruff correctness 零新违例。

---

## 3.11 M3 主体开工(2026-11-27,§20.3 统一装配闸全入口 + 登记表)

- **装配入口登记表**(M3 开工前置,§3 表第 1 行收口):新增
  `docs/upc-assembly-entry-registry.md` —— 四类入口(execute/query/
  schedule/probe)× 八装配面逐面登记(代码入口、方案选择单源、闸位置、
  blocked 错误面)、§11.3 系统默认凭证来源实测登记、读面豁免口径、
  维护约定(新增装配面须回表登记 + 同基础断言)。
- **§20.3 闸接入剩余四面**(M2 已收 probe=precheck 与 Suite 编排):
  - **单场景 JWT 执行**(`dispatch_target`):溯源 `req.schemeId` 复核
    持久化状态,blocked → `Conflict("scheme_repair_required")`,先于
    执行配置/凭证解析与执行行创建;悬空溯源 id(方案已删)不拦 ——
    配方本体由请求携带(与 resolve_for_run §7 回落口径一致);重跑
    同门(历史方案 blocked 则拒)。
  - **令牌执行**(`runs._apply_scheme_recipe`):服务端取方案后
    `require_ready`,blocked → 409(投影原因,不透传内部 reason)。
  - **生效配置预览**(`runs.preview_effective_config`):方案取行后
    `require_ready` —— 预览解析别名/凭证终值,与执行同一受控面。
  - **集成调度/手动触发**(`integration_runner.run_instance`):
    `_load_exec_shape` 后、working 闸同位 —— blocked 当轮 channel 收口
    (实例 failed + 人话原因),先于任何装配/凭证解析。
  - Suite 直跑(聚合)成员经 dispatch 闸 → Conflict 归
    skipped(reason=`scheme_repair_required`),单成员禁跑不掀批次。
  - **query 面(取数)豁免**:定义级无方案引用,无 blocked 面 ——
    登记于登记表第 8 行。
- **graph_dispatch 死分支清理**(§3 表第 6 行):carry 上下文的
  「project_id 空 = 私有区 → 执行人个人层」分支恒不走(UPC M2 起
  scenarios.project_id NOT NULL)—— 删除条件并登记;行为不变。
- **回归**:`tests/test_upc_m3_assembly_gate.py` 6 测:blocked 方案
  dispatch 零执行行、悬空溯源 id 放行(执行行照建)、令牌面 409 +
  ready 放行、预览 409 + ready 200、集成 channel 收口(「待修复」
  文案)、Suite 直跑 skipped reason 断言 + 零执行行。
- **设计细节项登记**(登记表 §3,实施前须取冻结稿):AccessToken
  `principal_id`(§20.1)/ ExecConfig 单表 XOR(§11.2)/ Integration
  拆表(§5 终态/§11.5)/ §13.1 状态机全貌 + 默认空间切换端点。
  **注**:v2.10 冻结稿不在本仓库(全 git 历史无此文件)—— 上述项
  涉及表结构与契约字段,凭进度台账引用的章节号无法忠实实施,已按
  台账 §3 处置列「M3 清单登记」收口;AC-48–50/53 验收同因。

**验证**:全量 `2343 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+6 = M3 闸测试);契约快照重生守卫绿;Ruff changed 文件仅存
HEAD 既有违例(非本轮引入)。

**§9 裁定收口**(台账 §3 表第 4 行):project-scoped 路径形态裁定为
**现契约定稿**(全局路径 + zone 谓词)—— 依据与「待冻结稿复核」标记
见登记表 §3。

**M4/M5 推进受阻登记**:v2.10 冻结稿不在本仓库(全 git 历史亦无);
M4 的 ProjectLayout / 模块注册 / AC-52 异步乱序、M3 清单四项的表结构
语义均只在该稿内。已向用户提问裁定(未获答复前不做臆测实施);M5
开发库重建按台账纪律**破坏性操作单独准入**,dev 库(5432)全程未动。

### 3.11.1 M3 执行装配主体:组合垫底八面接入(2026-11-27 续)

- **依据**:M2 在 `account_combo.py` 立好的读取面(`combo_base` /
  `pad_bindings` / `scheme_bindings_with_combo`,模块 docstring 明文
  「执行装配的垫底合并**随 M3 执行装配接入**」)+ 仓库内设计
  《05-account-combo-final.md》§3.2 八装配面垫底接法(逐面实测表,
  非冻结稿依赖项)。修前 **零调用点** —— 绑定了组合的方案在全部
  执行面上丢失组合条目身份(执行/预检误报 identity_missing)。
- **七面接入**(组合永远垫底,面内覆盖序不动):
  - JWT 单场景(dispatch_target):`_validated_bindings` 后垫底
    「后端权威垫底,不依赖前端拼全」;组合行缺失 fail-closed 归
    新码 `identity_combo_missing`(库层 FK NO ACTION + in-use 409
    使其实际近不可达,注册为防线位)。
  - 令牌(_apply_scheme_recipe):覆写源 = `{**组合, **方案}`
    (scheme_bindings_with_combo 单源)。
  - 预览(preview_effective_config):组合 < 方案 < 请求。
  - 预检(_precheck_one):与执行同基础,组合条目不再误报缺身份。
  - Suite 图(resolve_graph_units):取方案处垫底,图/单元覆盖在上。
  - 集成(_load_exec_shape):规范化 scheme_payload 写回视图副本
    (环境标签/订阅指纹/slot binding 三面同源;ORM 不写回)。
  - Suite 直跑(run_suite 聚合):调用方垫底(_combo_padded_scheme,
    _req_from_scheme 纯函数签名不改)。
- **查询面(第 8 面)单独立项**:§7.1(schemeId 解析 + 垫底 + 池通道
  + 缓存隔离 + 前端 headerAuthTagOf 补 call.user)是含前端参数与
  缓存键的独立子项,登记于装配入口登记表待后续批次。
- **同基础断言**(§9 测试面,`tests/test_upc_m3_combo_assembly.py`
  7 测):同一布景(方案 payload serviceBindings **空**,身份唯一
  来源 = 组合)下七面生效身份逐面钉死;**M3 出口条件「复跑 M2 样例
  完整装配」e2e**:blocked(闸拒 + 零执行行)→ rebind-combo 修复 →
  JWT 面发起(请求绑定留空)→ 全链装配 → done/passed=1,config_json
  见证 `serviceBindings == {fin-service: {alias: 组合别名}}`。

**验证**:全量 `2350 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+7 = 组合装配面测试);契约快照重生(新码 identity_combo_
missing 入册)守卫绿;前端 typecheck 干净 + vitest(api + 视图)
433 绿;新测试文件 Ruff correctness 零违例。

### 3.11.2 查询面 §7.1 落地(2026-11-27 续,八面收齐)

- **方案感知**:`resolve_query_context` 增 `schemeId` 参数
  (`resolve_for_run` 同款回落:缺省/跨场景/已删 → 默认方案;未保存
  编辑态不参与);绑定基础从定义级改为「方案 serviceBindings +
  组合垫底」(`scheme_bindings_with_combo` 单源)—— 绑定组合的方案
  在查询面首次生效;场景无方案 → 定义级 legacy 回落。
- **§20.3 闸**:方案 blocked → 409 `scheme_repair_required`,先于
  身份/标签/地址/凭证解析(下游 loader 会解密,查询面不再是豁免面)。
- **多身份不猜测**:步骤直接身份(`step_auth_refs` 复用,`${auth.*}`
  ∪ `call.user` 直引)>1 个 → 422 `query_identity_ambiguous`(前端
  headers 首命中即「取第一个」,后端统一挡住);单个直引优先于绑定
  兜底。前端 `headerAuthTagOf` 同步补 `call.user` 分支(§7.1 点 2)。
- **池通道与缓存隔离**(§7.1 点 4):rows 端点增 `credentialSource`
  (project 须 `can_use_project_credentials` 成员资格,与执行面同判;
  显式 `service_url` 直连通道无项目语境恒 409);`_loader` 通道透传
  `cred_project_id`;L1/单飞/会话/401 拉黑键的凭证分量扩为
  `(owner, alias, pool)` 三分量(个人池/项目池同 (owner, alias) 可
  解析不同账户,不串会话不串缓存);`drop_credential` 个人凭证事件
  按 (owner, alias) 前两分量清**全池变体**。
- **回归**(`tests/test_upc_m3_query_face.py` 6 测 + 既有 query 三
  套 63 例):缺省回落默认方案 vs 显式 schemeId 组合垫底别名、blocked
  409(路由面)、双直引 422、call.user 单直引优先、project 池资格
  409 两通道、池维度键隔离 + drop_credential 全池清理(键形单元钉)。
- **待接线**:画布暂不传 `schemeId`(回落默认 = 缺省语义,设计允许);
  workbench 选方案 → 画布取数传参属前端 UI 批次,登记于装配登记表。

**验证**:全量 `2356 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+6 = 查询面);契约快照重生(新码 `query_identity_ambiguous`/
`credential_source_invalid` 入册)守卫绿;前端 typecheck 干净 +
vitest 全量 1547 绿;`git diff --check` 干净。

### 3.11.3 §13.1 生命周期端点 + 默认空间切换(2026-11-27 续,清单第 4 项收口)

按裁定路径②(代码惯例推断;依据 = 模型状态机常量 + docstring
「处置流程随 M2+ 实现」+ DB 触发器 ④⑤⑥ + 部分唯一索引,均在库内):

- **archive / restore**(`POST /{id}/archive|restore`):normal = 项目
  管理员(锁内重验,与成员写同序);private = 所有者;public 恒 active
  不可归档/无恢复面。恢复后活跃 normal 须有有效管理员 —— API 面
  (调用者 = 在职 admin)恒满足,直写/竞态由延迟触发器 ④ 提交期兜底
  (人话前置检同口径);归档中成员写冻结(既有 R3-6 闸),恢复即解冻。
- **默认空间保护**:默认私有空间不可归档(409
  `default_space_not_archivable`)—— 触发器 ⑥ 只保存在性,默认空间
  是新建场景等缺省写入的落点;须先 set-default 换默认再归档。
- **set-default**(默认空间切换,§4 恰一个默认的写面):私有空间
  专属(409 `default_space_private_only`),原子换(旧默认先清、目标后
  置,即时部分唯一索引序敏感;并发竞态 → 409
  `default_space_switch_conflict`);目标须 active;幂等。切换不落
  「零默认」窗口(触发器 ⑥ 全程成立)。
- **审计登记**:`project.archived` / `project.restored` /
  `project.default_switched` 入 AUDIT_ACTIONS 词表。
- **回归**(`tests/test_upc_m3_lifecycle.py` 5 测):归档→冻结→恢复
  →解冻往返 + 状态机单向闸(重复归档 409 / 恢复非归档 409);归档门
  (非管理员 403 / Admin+ 非成员 404 / public 409);**触发器纵深
  全链**(⑤ 使「active 唯一管理员停用」不可达 → 归档后停用放行 →
  直写恢复撞 ④ CheckViolation);私有默认空间保护 + 他人 404 +
  归档空间不可成默认 + 恢复→切换默认→恰一个默认→原默认可归档。

**验证**:全量 `2361 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+5 = 生命周期);契约快照重生(三端点 + 五新码入册)守卫绿;
前端 typecheck + api 测试绿;新文件 Ruff correctness 零违例。

### 3.11.4 §11.2 ExecConfig 形状闸(2026-11-27 续,库层 CHECK)

- **`ck_exec_configs_scope`**(scope IN ('user','project')):把路由层
  的 (scope, scope_id) 成对写纪律(⑧:user → user.id / project →
  项目 id,恒非空)下沉到库层 —— 直写/存量违例在提交期拒绝,不为
  第三形态留缝(§20 不变量纪律:应用层校验 + 库层兜底)。
- **迁移 0069**(链头前移):fresh 链 baseline create_all 天然就位,
  0069 守卫空转;链路径 0053 建表形态无此 CHECK → 增量补挂,幂等。
  双路径终态一致由既有 §20.4 套件(TestDualPathStructure.test_
  constraints)自动覆盖。
- **回归**(`tests/test_upc_m3_exec_config_shape.py` 3 测):违例
  scope 直写在 flush 期被库层拒(合法两型先行放行);_upgrade_to
  链腿(0068 → 0069 幂等,约束两态都在);模型元数据登记断言
  (防手滑摘除后 fresh 链静默漂移)。
- **§11.2 余项(拆表/XOR 重构)登记**:若冻结稿的「单表 XOR」指
  (scope, scope_id) 之外的表结构重构(如模板/实例分表),超出本项
  推断依据 —— 待稿裁定。

**验证**:全量 `2364 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+3;迁移/dual-path/exec_config 回归 48 例全绿);契约无漂移
(纯库层,无新错误码);新文件 Ruff correctness 零违例。

### 3.11.5 §20.1 AccessToken principal_id 推断审计(2026-11-27,结论:不做盲改)

按裁定路径②对 §20.1 做了逐消费面审计,结论:**库内依据不足以
推断该列的语义与结构,实施 = 盲改表结构**,登记如下(这是本项在
缺稿状态下唯一可忠实交付的产物):

- **Principal 现状**(`services/access_token.py`):身份在**每次认证时
  活取** —— 个人令牌按 `tok.user_id`、项目令牌按 `tok.holder_id`
  (+`holder_problem` 派生失效判定:负责人停用/非管理员 → 401
  ERR_TOKEN_HOLDER_INVALID,换绑自动恢复,不落库)。
- **身份存续面已各有快照**(无缺口可推断「须补列」):
  executions = `owner_id`(FK SET NULL)+ `owner_name` 快照
  (台账三件套);webhook_deliveries = `token_id`(SET NULL)+
  `token_name` 快照;审计 `record_inbound` = 令牌四元组快照
  (M2b Q2 含 project_id)。
- **活取的已知语义是特性而非缺陷**:项目令牌负责人换绑后,令牌
  身份随新负责人 —— 与「换绑生效后自动恢复」产品语义一致
  (integration_runner #5 复核、notify_holder_lost 通知面)。
- **登记**:若冻结稿的 principal_id = 「调用身份的时间点快照」
  (审计取证不受后续换绑影响),则须定:落列位置(access_tokens /
  executions / 新表)、回填策略、与 holder_id 的不变量 —— 三者
  均无库内依据,待稿裁定后实施。§11.5 拆表同判定(数据迁移面,
  ck_integration_task_shape 现为权威)。

### 3.11.6 M5 前置件:场景清单导出保护(2026-11-27,准备件就绪)

台账 §5 顺序「**先**场景清单导出保护,**再**重建 dev 库」的前件落地
(不依赖冻结稿:§14.2 资产包格式 M2 已全量实现):

- **服务**(`app/services/scenario_inventory.py`,只读纪律 —— 对目标
  库零写入):`export_inventory(db, out_dir)` 全库逐场景导出 §14.2
  资产包 —— **属主视角全保真**(脱敏谓词对属主不生效:保护 = 完整,
  脱敏包不是保护)+ manifest.json(计数/归属/项目 kind/内容摘要);
  `verify_inventory(out_dir)` 恢复后对账(缺包/摘要漂移如实报告)。
- **内容摘要定义**:规范化 JSON sha256,**剥 packageId**(每次导出
  随机生成的包身份 —— §14.2 request_digest 把它算进重放键,但保护
  对账关心内容:同库同内容 → 同摘要;探针实证唯 packageId 随导出变)。
- **CLI**(`scripts/export_scenario_inventory.py`,`--out-dir/--db-url/
  --verify`):操作者在 M5 准入后以显式 `--db-url` 指向开发库执行;
  本轮全部验证仅针对测试库(15432),**dev 库全程未动**。
- **回归**(3 测):全保真(敏感列随包)+ 清单完备 + 双导出确定性;
  导出包经既有 §14.2 恢复 API 圆满回放(恢复报告计数对照导出侧
  —— 重建后全清单恢复的可行性证明);篡改/缺包被 verify 抓出。
- **M5 执行序列就绪**:① 导出保护(CLI)→ ② 开发库重建(破坏性,
  **单独准入,未执行**)→ ③ §14.2 全清单恢复(既有 API)→
  ④ verify_inventory 对账 + 恢复报告。

**验证**:全量 `2367 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+3 = 导出保护);契约快照重生(scanned_files 189→190 合法
漂移)守卫绿;`git diff --check` 干净;新文件 Ruff correctness 零违例。

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
---

## 3.12 冻结稿入库后的契约收口轮(2026-11-27,P0 三项 + schedule 写点 + P2)

冻结稿(`docs/01-Gimbal-UPC-v2.10-Design.md`,`c1446fe7` 入库)解除
「待稿裁定」阻塞后的第一批契约收口;同步修评估报告列出的越权面。

### P0-1 executions 项目聚合 Admin+ 旁路(AC-05/AC-51)

`executions_summary` 的 projectId 维度门改 `can_view_project` 统一
谓词(删手写成员查询 + ops.write 旁路)—— Admin+ 不再看见他人私有
/普通项目执行聚合;非成员恒 404。`batch-summary` 逐执行属主过滤,
无旁路(核对确认)。回归 `tests/test_executions.py` 10/10。

### P0-2 §11.1#1 内置凭证执行链退役

- **裁定**:写边界早有 `plaintext_users_rejected` 禁新内嵌(阶段 2);
  本轮让**执行链**(dispatch / Suite 编排 / 集成)不再消费存量内嵌
  基座 —— `materialize_run_copy` 的 users 唯一来源 = `resolved_auths`;
  `graph_dispatch`/`run_dispatcher`/`integration_runner` 三链摘除
  `built_in_users` 传参。
- **导出面保留**(10-14 口径,属主自有数据可携带,非执行语义;
  `scenarios.py` 导出物化 + `prep.built_in_users` 注明「仅剩导出面
  消费」)。属主编排物化同改断言(`test_public_content_strips_
  credentials` 属主腿 users == {},负向腿不动);
  `test_authz_s60_slimming` 私有区腿改「authored 直连保留、内置退
  役」(地址面不在 §11.1 五开关清单)。

### P0-3 §11.2 ExecConfig 单选 + 单表 XOR FK(0070)

- **0070 迁移**:`exec_configs` 换 `principal_id`/`project_id` 两真实
  FK(NO ACTION)+ XOR CHECK(`ck_exec_configs_owner_shape`)+
  同侧 name/默认部分唯一索引(谓词钉本侧非空 —— 单列部分索引对
  NULL 互不冲突);(scope, scope_id) 多态列退役。孤儿配置行(无外键
  时代合法残留)回填前显式清理。0069 加时代守卫(fresh 基线无 scope 列
  空转);era 造形 `_strip_exec_config_owner_shape` /
  `_to_exec_config_era_shape` 让 0069→0070 增量真实重放
  (`_strip_upc_shapes` 同步覆盖 exec_configs)。
- **处置收口**:私有容器处置清项目配置(`dispose_private_assets`);
  用户删除清个人配置(principal_id NO ACTION,与旧凭证行同口径)。
- **单选序**(`exec_config.load_choice`):显式 = 本人个人行 ∨ 当前
  项目行(归属错/不存在/无 use → 404 fail-closed 不降级);未显式 =
  **项目默认行**;**个人默认不参与后端解析**(签核项)。`exec_config.
  use` 与 read 区分:项目配置 use = 容器执行面
  (`can_use_project_config`:private 属主 ∨ normal 成员 ∧ active;
  公共恒 False —— §7 关闭)。私有空间项目配置写面 = 属主(§7 开)。
- **carry 链收敛**:决策 9 区规则退役 —— 选定配置(显式或项目默认)
  的覆盖即「选定执行配置层」(公共 < 项目 Carry 资源 < 选定配置);
  AC-49「显式个人替换整个项目默认,仍继承项目 Carry」。
- **晋升冲突对照**(`_carry_conflicts`):两侧有效值 = 公共 < 容器
  Carry 层 < 容器默认执行配置覆盖(`path in` 判成员,显式 null 与
  缺席分立);s72 测试改由源空间容器默认配置承载。
- **调用点**:dispatch(场景坐标提前解析)/预览/预检(项目语境入参)
  / 晋升;路由 DTO 保持 scope/projectId 形状映射新列。
- **回归**:形状闸 4 测(直写 XOR/FK 拒 + 链腿 0069→0070 真实换形
  + 模型登记)、双路径(增列 `exec_configs` 对照)、
  `test_migrations` 全量、链 36 例、圈定门 8 例、s72 8 例。

### P1 schedule 写点修复闸(§20.3「创建、启用、更新执行绑定」)

`integration.py` 增 `_require_scheme_ready`(指定 id 必属场景同码
`scheme_not_owned`;未指定按将生效默认配方核对):创建(显式绑定)、
PATCH 换绑、subscribe(将生效)、resume(恢复前核对)四写点统一
blocked → 409;派发闸仍在 run_instance。登记表 §1 后补「schedule
写点闸」注记。回归 4 新测 + integration 全量 19/19。

### P2 收尾

处置动作码漂移:users.py 处置解离改用
`scheme_repair.ACTION_DISPOSAL_BLOCKED` 常量(状态机边名同源);
`run_prepare`/`carry_store` 旧口径注释清理(个人层退役/单选链);
登记表补账:§11.1 五开关状态、§11.4 remove 未实施、CLI/Agent 行、
`access_tokens._task_bindings` 读面豁免行。

**验证**:全量 `2371 passed / 2 skipped / 0 failed`(真实 PG 15432,xdist;+4 = schedule 闸四测,装配闸文件 10 测);
契约快照重生(错误码 sites 随新 raise 点合法漂移,前端生成件 noop);
`git diff --check` 干净。

**开放项登记**(不变):§11.4 remove/递归合并(carry 值层结构,
登记表 §4 行)、AccessToken principal_id(§20.1)、Integration 拆表
(§5 终态)、§13.1 状态机全貌端点、M4 前端、M5 重建准入。

## 3.13 复核轮:外部复审七项的 M3 收口 + M5 三项登记(2026-11-27 续)

外部复审列出七项(默认空间并发×2、项目凭证缓存、JWT 闸绕过、
query_alias 消歧矛盾、备份漏公共资产/verify 名不副实/非原子写)。
逐条复核**全部属实**;按里程碑归属拆分:M3 四项本轮收口,M5 三项
(均在 scenario_inventory.py 导出保护面)登记待 M5 准入切片。

### M3 收口(本轮)

* **默认空间生命周期并发窗口**(§3.11.3 落地点的锁序补漏):
  set-default 的 `_require_active` 移到 `refresh(with_for_update=True)`
  **之后**(修前归档可在预检与加锁之间提交,归档空间仍被置默认);
  private 项目删除补行锁 + 锁后复查 `is_default`(修前并发 set-default
  可越过"默认空间不可删";DB 层 `uq_projects_private_default` 谓词
  不含 status、不拦删除,应用层是唯一防线)。
* **项目凭证写面清查询缓存**(§7.1 点 4 项目池通道):
  `query_view_runner.drop_project_pool(project_id)` 新钩子 —— 项目池
  键 `(场景属主, alias, pool)` 的属主维度路由处拿不到,按**池分量**
  整池清(会话 + 401 拉黑 + L1 行集);`project_credentials._after_write`
  接线(创建/改密/默认位/删除同清,与 auth_sessions 个人钩子同闭环)。
* **JWT 面 blocked 闸服务端强制**(§20.3):dispatch 闸从"仅显式
  schemeId 可解析才复核"改为 `resolve_for_run` 单源取**生效方案**
  (显式可解析 = 该行;缺省/悬空/跨场景 = 默认方案)—— 与令牌面
  `_apply_scheme_recipe`/查询面同口径,schemeId 缺省不再绕闸;唯一
  免闸 = `raw` 保留字(显式零方案意图)。悬空 id 用例口径随之更新
  (回落默认 ready → 放行腿)+ 新增缺省绕闸负向。
* **显式 query_alias 消歧**(§7.1 点 3):`resolve_query_context` 增
  `query_alias` 参数,显式点名胜出(显式 > 步骤直接身份 > 生效别名)
  且先行短路多直接身份 422 —— 修前路由先解析上下文后应用显式别名,
  报 422 的文案"请改用明确的 query_alias"所指通路实际不通。

### M5 三项登记(待准入切片,均在 M5 前置件导出保护面)

1. **公共化资产漏出备份 manifest**:users.py publicize 对私有迁公共
   与已是公共的场景都置 `owner_id=None`(署名留 owner_name 快照),
   而 `scenario_inventory.export_inventory` 把**全部** owner=None 行
   当"整删残留"(`reason: owner_missing`)跳过导出 —— 公共场景及
   公开化场景不进备份包。修法方向:owner=None 行按系统视角导出
   (全保真对公共内容成立)或以 owner_name 快照参与。
2. **verify_inventory 名不副实**:签名只收 `out_dir`,不接 db —— 只
   校验备份目录自身完整性(包体存在 + 摘要一致),证明不了恢复后
   库内容完整;M5 序列④"对账"需接恢复后库连接做内容级比对。
3. **备份落盘非原子**:包体逐个直接 `write_text` 终路径、manifest
   最后写 —— 中途崩溃留旧 manifest + 部分新包(半截 JSON 还会让
   verify 的 json.loads 崩);应临时目录写完 + rename 原子替换。

**验证**:M3 定向回归绿(装配闸 + 查询面 19;生命周期/处置/查询路由
/auth 会话 73);全量回归见下。

## 3.14 外部静态复核两项 P1(2026-11-27 续)

### P1-1 订阅指纹纳入方案不可变身份(AC-50 收口,本轮修复)

复核属实:consent_fingerprint 投影只覆盖内容七要素,不含 M2 已建的
不可变 ``scheme_uid`` 与组合溯源 —— 删原方案同内容重建(新 uid)指纹
不变,订阅者确认过的对象已换代,AC-50 要求暂停/零派发/重确认。
修复:指纹投影新增 ``scheme_identity`` = ``{schemeUid, combo:{id,name,
revision}}``(account_combo.py 修订纪律本就声明「订阅指纹记录
id+name+revision 溯源」);三个计算点同源 —— ``consent_fingerprint_
now``(订阅确认比对)、``consent_fingerprint_now_shape``(订阅摘要,
经 subscription_view 装载行)、run_instance 派发前比对 —— 与既有
template_changed 暂停闸合流,无需新增暂停路径。存量指纹(旧格式)按
不一致处理 = 多一次重确认,方向安全。

### P1-2 显式配置未整份替换项目默认 —— 复核结论:已收口(上轮)

复核引用的合并点(run_dispatcher:1318 / runs.py:472)与
`merge_carry_overrides`/`project_carry_overrides` 全库已无残留 ——
上轮 §11.2 单选改造即本项修法(选定唯一 ExecConfig + 项目 Carry
资源层在 build_carry_context 正交参与)。本轮以 AC-49 设计样例
端到端用例锁定:项目 Carry(region)+ 项目默认配置(timeout)+
显式个人配置(locale)→ 终值 = {region, locale},timeout 缺席
(test_exec_config_chain.py::test_ac49_design_example_single_select_
carries,选定腿 + 全链合成腿双断言)。

### 复核旧快照项勘误(不改代码)

复核 M3 段引用 `exec_config.py:51 scope_id` 为旧快照 —— 0070 已以
principal_id/project_id 双真实 FK + XOR CHECK 替代 scope/scope_id。
**勘误(上轮本节误判)**:AccessToken 的 `user_id`/`holder_id` 双主体
**仍是现状** —— 0070 改的是 ExecConfig,AccessToken 未动;§20.1
principal_id 收口项维持登记(§3.12)。Integration 同表拆分仍开放
(§3.12 登记项)。

**验证**:定向回归(装配闸/查询面 19;W0a + exec_config 链 20;
指纹触面 env_chain/S8/C2/consent_fixes/integration/plate 集成 85)全绿;
全量见下。AC-50 用例:同内容删建 → template_changed 暂停(指纹未
确认前不刷新)→ 再订阅恢复。

## 3.15 复核轮二:ExecConfig 归档闸 + 默认位冲突分派 + 0070 回填腿 + schedule 写点收口(2026-11-27 续)

* **P1 ExecConfig 管理写面归档闸**(§13.1):`_project_gate` 文档声称
  "归档项目拒写"但代码无 status 检查 —— 补闸:write 面在归属/角色
  判定**之后**复查 `project.status != active → 409 project_not_active`
  (先角色后 active,归档态不作存在性探针,r5-2.2 同拍;与项目凭证
  管理门一致)。私有空间属主治理面同受冻结;读面不冻结。负向用例:
  归档非默认私有空间 → 项目配置创建 409,读照常。
* **P2 默认位并发冲突误报撞名**:create/copy 的 IntegrityError 原样
  映射 `exec_config_name_exists` —— 新增 `_integrity_conflict` 按约束
  名分派(account_integrity_conflict 同款):`uq_exec_configs_*_default`
  → 409 `exec_config_default_conflict`(并发切换默认,请重试);真撞名
  仍报 name_exists。set-default 路由的裸字符串 detail 同步规范为
  {code, message} 结构。契约快照随新错误码重生。
* **P2 0070 数据回填腿**:`test_0070_backfills_and_cleans_orphans` —
  时代形状播 (scope, scope_id) 五行(合法 user/project + 孤儿主体/
  项目/零 id)→ 0070 后 principal_id/project_id 正确回填、三孤儿行
  清理、合法行保留(形状腿之外的语义腿)。种子用户 is_system=true
  绕开 user_default_space_required 触发器(该腿不验证用户不变量)。
* **边界收口 schedule 创建/清空绑定核对默认方案**(§11.5 将生效配方):
  复核指出创建不传 schemeId、PATCH 显式清空 schemeId 时写点未调
  `_require_scheme_ready` —— helper 本就受理 None 腿(默认方案),
  补接线:创建恒调(显式查该行/未绑定查默认);PATCH 清空腿先核对
  将生效的默认方案再清位。订阅闸用例布景随之改为"ready 创建后转
  blocked"(创建面已拦),新增两个写点负向(默认受阻创建 409 + 模板
  行不落库;清空 409 + 原显式绑定保留)。
* **M5 三项**:维持 §3.13 登记,不在本轮范围。

**验证**:定向回归(装配闸 + 形状 + API 30;契约快照守卫 3)全绿;
全量 `2381 passed / 2 skipped / 0 failed`(真实 PG 15432,xdist;
+5 = 归档闸/两个 schedule 写点/0070 回填 + 既有拆腿);
契约快照重生(`exec_config_default_conflict` 新码入册,前端 errorCodes
生成件同步);Ruff changed 文件零新增(违例数回到 HEAD 基线);
`git diff --check` 干净。

## 3.16 复核轮三:AC-50 owner 自订阅收口 + 台账勘误 + AC-49 调度一致性登记(2026-11-27 续)

* **AC-50 指纹闸覆盖私有所有者自订阅**(v2.10 §22 验收矩阵):派发前
  指纹比对原条件 `holder != tpl.owner_id`(v1.4 §2 旧口径 owner 豁免)
  与「旧订阅因 UID 变化保持暂停」冲突 —— 收口为
  `consent_gate = holder is not None`(成员门语义不变:私有模板仅
  属主、普通项目按成员、公共不走成员门)。既有依赖豁免的布景两处
  随之修正:W0a 主链 owner 腿改为「同暂停 + owner 再订阅恢复」;
  consent_fixes 的 alias_default_credentials 用例暴露创建面指纹晚于
  布景的陈旧性(部署地址/凭证命中集入指纹)—— 补 owner 重确认两步。
  AC-50 用例同步改造为设计指定向量:**同业务 ID、名称、revision、
  内容**重建(占回原 scheme_id,唯一约束随删行释放)+ owner 自订阅
  腿(私有模板独立用例)+ 成员腿。
* **台账勘误(§3.14 事实错误)**:AccessToken 的 user_id/holder_id
  双主体仍是现状 —— 0070 改的是 ExecConfig,AccessToken 未动;
  §20.1 principal_id 收口项维持登记(§3.12)。
* **AC-49 调度一致性 —— 登记待裁定**(不做臆测实施):§11.2 要求
  「预览、执行和调度使用同一选择结果」,而集成链显式**不消费**
  ExecConfig(结构性守卫 test_integration_never_resolves_exec_config,
  「同一模板全订阅者同一指纹」不变量)。两种收敛路径待裁定:
  (a) 调度订阅面绑定执行配置(§11.2「调度订阅明确绑定所需个人配置」
  —— 需 IntegrationTask 增列 + 订阅面/指纹扩展,里程碑级);
  (b) 显式登记「集成调度豁免 ExecConfig」边界,守卫即裁定。
  复核原文只指出未闭环,未指定方向;与同指纹不变量的取舍须人工裁定。

**验证**:定向回归(W0a 7;consent_fixes 13;integration/S8/env_chain/
C2/webhook_tokens 70;S0 4;grep 守卫 2)全绿;既有依赖 owner 豁免的
布景四处修正(W0a 主链 owner 腿 / consent_fixes alias_credentials /
S0 scope / S0 partial —— 均为「布景晚于创建面指纹或合法内容变更后
补 owner 重确认」,非放宽闸);grep 守卫白名单收编两行(consent 门
与成员门简化后属主比较形状消除);
全量 `2382 passed / 2 skipped / 0 failed`(真实 PG 15432,xdist);
Ruff changed 文件零新增;`git diff --check` 干净。

## 3.17 复核轮四:归档闸 TOCTOU 锁行 + 公共副本修复死角(2026-11-27 续)

* **P2 ExecConfig 归档闸 TOCTOU**:`_project_gate` 写面补行锁
  (`refresh(with_for_update=True)`)后复查 status —— 归档事务可在
  无锁预检与配置提交之间落定的窗口收口(set-default/delete 同款
  锁序;读面不锁)。
* **P2 公共副本修复死角**:发布(copy_schemes)忠实继承 blocked,
  但公共项目组合能力关闭(§7)→ rebind_combo/confirm_no_combo 均
  422 → 副本不可修复 + schedule 写点闸拒建任务 = 只能回源修复重
  发布。按 §20.3「继承阻塞**或**在目标域显式修复」的第二分支在
  公共域结构性不可用裁定:**组合能力关闭的目标域,副本组合引用
  已剥(绑定恒剥),「组合依赖受阻」对副本事实不成立 —— copy_
  schemes 按依赖事实生成 ready**(§20.3「由领域服务按依赖事实生
  成」;非「普通空绑定清除」—— 普通 PATCH/PUT/保存仍不得清,同域
  复制仍忠实继承、可在目标域显式修复)。源方案保持 blocked 不受
  影响。用例:发布携带 blocked 方案的场景 → 公共副本全 ready
  (reason/combo 位 None)+ 源 blocked 保持;同域复制继承腿
  (test_copy_strips_binding_and_inherits_blocked)不受影响。

**验证**:定向回归(m2 domain + exec_configs + exec_config 链 46)全绿;
全量 `2382 passed / 2 skipped / 0 failed`(真实 PG 15432,xdist;+1 =
发布公共副本 ready 用例);契约快照重生(raise 点行号位移,前端
生成件 noop);Ruff changed 文件零新增(git stash 真路径 + 项目配置
对比;/tmp 副本对比受 ruff 配置解析失真,弃用);
`git diff --check` 干净。

## 3.18 复核轮五:AC-50 公共模板订阅面收口 + 订阅指纹同读入库(2026-11-27 续)

* **P1 公共模板直接订阅绕过复制/映射/确认**(§22 AC-50):订阅入口补
  闸 —— 公共项目模板非属主 subscribe → 409
  `public_template_subscribe_forbidden`(属主重确认不受闸);运行时
  成员门公共分支收口(原 `_tpl_kind != "public"` 豁免删除):公共模板
  非属主持有行 → 派发前暂停 `public_template`(零派发,存量漏网行
  同口径)。正路 = 复制(fork)→ 建本域模板 → 确认订阅,用例钉住。
* **P1 订阅指纹同读入库**:subscribe 原流程「consent_fingerprint_now
  比对 → refresh_consent 二次重算入库」在两读之间方案可被同业务 ID
  重建 —— 用户确认 A、入库 B,派发闸对 B 无感。改为保存**已通过与
  回传值比对的那次指纹**(consented_at 同拍写入);refresh_consent
  保留给创建面。
* **测试迁移(新订阅模型)**:W0a/W0b/W2/consent_fixes/C2/horizontal
  订阅语义用例从「公共模板直订」迁到普通项目模板(成员订阅;新
  helpers:`mk_normal_template` / w0b `_mk_task` 重构 / consent_fixes
  `_mk_normal_tid`);公共模板上的 legacy 行用例(转私有联动/漏网/
  转移订阅实例)改为直插行模拟;新增公共直订拒绝 + 零派发 + fork 正
  路用例;grep 守卫白名单收编三行(成员门公共分支同形 + 订阅闸)。
  R1 钉(0038 迁移)随 AC-50 修订:存量非属主公共行 = public_
  template 暂停(非 made_private 误伤语义保持)。

**验证**:定向回归(W0a 8;W0b 6;W2 + horizontal + S0 + consent_fixes
+ C2 + s16 转移 + 守卫)全绿;全量 `2384 passed / 2 skipped / 0
failed`(真实 PG 15432,xdist;+2 = 公共直订拒绝/私有 owner 腿);
契约快照重生(`public_template_subscribe_forbidden` 新码入册,前端
errorCodes 同步);Ruff changed 文件 13 份零新增(git stash 真路径
对比,违例总数 133 = 133);`git diff --check` 干净。

## 3.19 复核轮六:AC-50 终裁三条 —— 公共模板全禁直调/发布复制忠实继承 blocked/调度遇 blocked 立即暂停(2026-11-27 续)

* **公共模板对属主和非属主都禁止直接调度**(§22 AC-50 终裁;上轮只
  收口了订阅面):手动触发端点补闸 —— 公共项目模板 run → 409
  `public_template_dispatch_forbidden`(**属主也不例外**);运行闸
  公共分支改全暂停(原"属主豁免"删除):公共模板任何持有行 → 派发
  前暂停 `public_template`,零派发。执行走「复制 → 本域模板 → 确认
  订阅」;公共模板成为纯目录面。
* **发布、复制不得自动把 blocked 方案改为 ready**(§20.3 终裁,
  **勘误回退 §3.17 的 P2 裁定**):copy_schemes 恢复忠实逐行继承
  (blocked 保持 blocked 同原因,ready 保持 ready)—— 上轮"能力关
  闭目标域按依赖事实生成 ready"与终裁冲突,撤销;修复死角由闸面
  承接:blocked 公共副本不可建任务/订阅(schedule 写点闸),调度遇
  之暂停,回源修复后重发布。
* **调度遇到 blocked 立即暂停订阅**(§22「显式 Scheme 失效...均暂停,
  无外部派发,修复后需重新确认」终裁细化):run_instance 的 blocked
  分支从「当轮 channel 收口后照常调度」改为 **paused/
  scheme_blocked**(先于任何装配/凭证解析,零派发);scheme_blocked
  ∉ _RESUMABLE(resume 409 引导),订阅路由重确认恢复集合补
  scheme_blocked(闸核对 ready 后放行)。
* **验收**(用户指定口径):新增两用例 —— ① 公共模板手动触发(属主
  ∧非属主)409 + 定时领取运行闸暂停,**断言外部派发次数为零**(零
  Execution 行);② blocked 暂停修复流:订阅 → 源方案置 blocked →
  手动触发暂停 scheme_blocked 零派发 → 定时领取同口径 → resume 409
  → 修复(confirm_no_combo)→ 再订阅恢复。既有 channel 收口用例改
  口径(assembly gate),发布继承用例改逐行保真断言,made_private
  channel 语义保留给可见性/成员路径。

**验证**:定向回归(W0a 10;assembly gate 14;m2 域;consent_fixes
13)全绿;全量 `2384 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+2 终裁验收);契约快照重生
(`public_template_dispatch_forbidden` 新码入册);Ruff changed 文件
零新增(git stash 真路径对比);grep 守卫白名单计数随成员门公共分支
删除同步(2→1);`git diff --check` 干净。

## 3.20 复核轮七:强制暂停原因防改写 + 指纹身份/版本补齐 + 零派发断言换真实通道(2026-11-27 续)

* **手动暂停不得覆盖强制暂停原因**(复核 P1):手动暂停写点对**已
  处于强制暂停**(非 _RESUMABLE 家族:scheme_blocked /
  template_changed / made_private / public_template / token_* /
  missing_credential)的订阅改为幂等保持原原因 —— 此前重按手动暂停
  会把 scheme_blocked 改写成 manual,方案修复后普通恢复入口(方案
  已 ready)即可回 idle,绕过重新确认;指纹同值时派发前比对也补不
  回这次确认。resume 提示语补 scheme_blocked / public_template 引导。
* **确认指纹补齐身份/版本组**(v2.10 §11.5「实际目标项目、模板及
  版本、实际 Scheme 及修订、组合 ID 及修订」;复核 P1):指纹投影
  新增 ``target``(实际目标项目 id + **不可复用 project_uid** + 本地
  模板行 id/版本 ``updated_at``),``scheme_identity`` 增
  ``schemeRevision`` —— 同 UID 目标迁移、模板行修订(含未入内容投
  影的管理字段:名称/映射/令牌绑定)、方案重排修订不再靠内容碰巧
  不变而漏确认。三个计算点(订阅摘要/重确认/派发前)同一算法;
  ``target`` 按 ``scen.project_id`` 解析(目标迁移态与模板行项目分
  叉时取真实目标);``updated_at`` 显式 SELECT 取数(同会话写模板
  行后 ORM 侧该属性被卸载待服务端回填,同步读 = MissingGreenlet;
  显式 SELECT 自动 autoflush,订阅/派发两侧同值)。
* **零派发断言换真实外呼通道**(复核 P2):run_instance 本就不写
  Execution 行,「零 Execution 行」是恒真断言 —— 两用例改在实际对
  外执行通道(channels.run_case)装调用计数,覆盖手动触发与定时领
  取两条路径。
* **验收用例**(用户指定口径):① 迁移腿 —— 场景+方案行+模板行整
  体迁往另一普通项目(复合 FK SET CONSTRAINTS DEFERRED 同事务迁
  移;断言 scheme_uid/修订/内容不变)旧订阅派发即暂停
  template_changed、旧预览指纹再确认 409、新指纹重确认恢复;② 修
  订腿 —— 同 payload 重存(内容逐字相同,revision+1 唯一变化)旧
  订阅暂停、旧预览 409、重确认恢复;③ 暂停覆盖腿 —— blocked 暂停
  后重按手动暂停,原因保持 scheme_blocked,修复后 resume 仍 409,
  再订阅才恢复。
* **既有用例收编**(新闸的正确暴露):state_mapping 直写模板行、
  s0 schemeId 直改模板行两用例在模板行写后补同会话重确认
  (refresh_consent;s0 直改腿不走订阅面 —— 订阅绑定闸会拒绝他场景
  schemeId,该腿验证 runner 级回落纵深防御)。

**验证**:全量 `2388 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+2 = 迁移腿/修订腿;暂停覆盖腿并入既有 blocked 流用例,
零派发两用例换通道计数);
契约快照重生(仅代码位点行号移动,无新码);Ruff changed 文件零新
增(git stash 真路径对比);`git diff --check` 干净。

## 3.21 复核轮八:模板与目标同区三面收口 + 显式 Scheme 失效禁回落(2026-11-27 续)

* **模板与实际执行目标同区(创建/确认/派发三面)**(v2.10 §11.5
  「可调度订阅必须绑定可执行项目中的本地模板…实际目标、模板及所属
  Scheme 必须落在同一执行项目」;复核 P1):此前创建面仅在显式传入
  projectId 时核对场景同区,省略时「项目内可跑」的普通项目场景 +
  私有模板落默认私有空间形成分叉 —— 派发成员门只看模板项目、指纹
  不含目标项目成员关系,持有人被移出场景项目后场景与模板都不改版、
  指纹不变,照常调度。收口:
  - **创建面**:私有模板缺省 projectId 只接受注册者默认私有空间内
    的场景;目标在普通/公共项目 → 422 `scenario_not_in_project`
    引导显式指定同区 projectId(显式路径既有核对不变);
  - **确认面**:模板与目标不同区 → 409 `target_zone_mismatch`
    (存量分叉行在此拦下,不可再确认);
  - **派发面**:run_instance 成员门后新增**按订阅主体的目标执行权
    复核**(`can_run_scenario`,§11.5「派发以订阅主体重新校验模板
    读取、目标执行」)—— 分叉存量行/场景迁项目后成员门拦不住的
    「已不在场景项目」持有人在此暂停 made_private;同区新行与成员
    门同真,纯增量复核。
* **显式 Scheme 失效禁回落默认**(§11.5「显式 Scheme 缺失、已移动、
  跨场景或 blocked 时暂停,禁止改跑默认方案」;复核 P1):方案装载
  未绑定/显式绑定分流 —— 未指定照常走既定默认选择规则(resolve_
  for_run 回落);**显式 id 须属本场景,失效直接报
  IntegrationRunError("explicit_scheme_invalid")**,run_instance 先
  于形态装载核对 → 暂停 template_changed(零派发,与 blocked 闸同
  位),订阅面绑定闸既有 422 拦失效确认。上轮 s0 用例把「跨场景
  scheme 直改 + 刷指纹 + 期望默认回落」写成断言,属被禁行为 —— 改
  口径三腿:跨场景显式 → 暂停 + run_case 计数为零;清绑定(未绑定)
  → 默认回落照常;显式有效 → 正常注入。
* **验收用例**:同区三面一条(test_template_target_same_zone_
  enforced:创建 422/201 两腿 + 确认 409 + 派发正向对照
  (template_changed = 越过目标闸)+ 移出项目 → made_private 零
  外呼);s0 三腿见上。

**验证**:全量 `2389 passed / 2 skipped / 0 failed`(真实 PG 15432,
xdist;+1 同区三面,s0 同数改口径);契约快照重生(新码
`target_zone_mismatch` / `explicit_scheme_invalid` 入册);Ruff
changed 文件零新增(git stash 真路径对比);`git diff --check` 干净。
