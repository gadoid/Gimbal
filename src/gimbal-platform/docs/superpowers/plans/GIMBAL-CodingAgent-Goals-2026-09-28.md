# GIMBAL 实施目标（Coding Agent 版）

- 日期：2026-09-28（同日修订：基线前移，并入缺口盘点补充项）
- 仓库：`gadoid/Gimbal`
- 基线：`feat/executor-v2.1-fusion` @ `07831974`
- 配套文档：《GIMBAL 待实现功能与路线图》（功能清单与阶段划分的来源；已重组为「当前问题 / 新增需求」两部分，本文件的 P0 对应其第一部分，P1–P8 对应第二部分）
- 修订记录：
  - P0-02、P0-07 经复核已在基线前完成（见各节状态行），保留原文供追溯；
  - 新增 P0-10 ~ P0-12（盘点补充：卫生批、编译期校验补全、预认证补全）；
  - P2-01 / P2-05 / P3-04 / P3-05 补入前置与字段要求；
  - 待拍板表新增 D-6 / D-7；
  - **P1+P2+P3 主体完成（2026-09-29）**：P1 全部（B1-B4/B6）→ P2 全部（N4/C1-C4/C8-C10）→ P3 的 C5/N5/N1/N2/S4/B5/C7/N3 —— 12 个 Goal 11 笔提交;verify_all 1182/758/131 三步全绿;D-4（不提前）/D-6（保留横切面）已拍板;D-7 已执行。剩余:C11/C12/C13 + C6 —— **已于 2026-09-29 完成(见 P3-01~04 状态行;全量门 gimbal 1198 / backend 769 / frontend 1133 三步全绿)**
- **P0 批次执行完成（2026-09-28）**：除 S4（随 D-6 拍板）与 S5（已随本批落库，见路线图执行记录）外，第一部分全部 Goal 完成；全量门 `verify_all.sh` 三步全绿（gimbal+plate 1076 / backend 727 / frontend 1133）。

本文把路线图拆成可以直接交给 coding agent 执行的目标（Goal）。每个 Goal 自成一体：做什么、改哪里、不做什么、怎样算完成、遇到什么情况必须停下来问人。

---

## 0. 全局规则（所有 Goal 通用）

### 0.1 约束

1. **不新增模块。** 所有改动落在现有目录与服务里。确实需要新目录或新服务时，停下来，写明必要性，交人评估。
2. **不留兼容层。** 项目处于开发阶段：旧形式一次性迁移，不保留语法糖、别名、双写或占位实现。
3. **不扩大范围。** 只做本 Goal 列出的内容。发现范围外的问题，记入"遗留"一节，不顺手修。
4. **不写占位代码。** 不提交"声明了但不生效"的字段、参数或命令。做不完的部分不要声明。
5. **协议细节不进入业务流程。** 协议相关的字段只存在于协议适配器和 binding 内部。
6. **数据描述统一用 JSONPath。**

### 0.2 通用完成定义（DoD）

每个 Goal 除自身验收标准外，还必须满足：

- [ ] 新行为有对应测试，测试放在对应模块现有的测试目录里；
- [ ] 在**干净克隆**上运行 `scripts/verify_all.sh`（由 P0-01 建立）全部通过；
- [ ] 不依赖任何被 `.gitignore` 排除的本地文件（例如 `gimbal-tmp/`）；
- [ ] 相关设计文档的状态更新附带证据：提交号 + 测试结果摘要。不得在验证之前标记完成；
- [ ] 提交粒度：一个 Goal 一组提交，提交信息写明 Goal 编号。

### 0.3 必须停下来问人的情况

- 需要新增模块、新服务或新的顶层目录；
- 需要对"待拍板事项"（第 11 节）做出选择；
- 验收标准与现有已定设计冲突；
- 需要删除用户数据或执行不可逆的数据迁移；
- 同一个 Goal 的修复连续两轮仍未通过验收。

### 0.4 环境

- Python ≥ 3.12（plate 使用了 `typing.override`）；
- 平台后端测试需要 `greenlet`、`aiosqlite`、`asyncpg`；
- 平台前端依赖安装需要可达的 npm registry（见 P0-09）。

---

## 1. 目标总览与依赖

| 阶段 | Goal | 依赖 |
|---|---|---|
| P0 质量与收尾 | P0-01、P0-03 ~ P0-12（P0-02、P0-07 已完成，见各节状态） | 无 |
| P1 执行器可观测性 | P1-01 … P1-05 | P0-01 |
| P2 平台执行链一期 | P2-01 … P2-07 | P1-02、P1-03 |
| P3 平台执行链二期 | P3-01 … P3-08 | P2 全部 |
| P4 plate 通用化 | P4-01 … P4-07 | P0-01；决策 D-1 |
| P5 release 与版本 | P5-01 … P5-05 | P4 全部 |
| P6 真相源反转 | P6-01 … P6-04 | P5 全部；决策 D-3 |
| P7 CLI 归一 | P7-01 … P7-03 | P3、P6 |
| P8 外部集成 | P8-01 … P8-05 | P3（推送类）；P4-07（拉取类） |

P1–P3 与 P4–P6 两条线可以并行，交汇点只有 P4-06（平台编排器渲染）。

---

## 2. P0 质量与收尾

### P0-01 建立统一验证入口

- **状态（2026-09-28）**：✅ 已完成——`scripts/verify_all.sh`（支持步骤选择）；全量门 1076 / 727 / 1133 三步全绿；注入失败用例验证 rc=1、清理后 rc=0
- **目标**：一条命令在干净克隆上跑完全部测试，作为所有 Goal 的合并门。
- **范围**：新建 `scripts/verify_all.sh`（`scripts/` 目录已存在）。
- **要求**：
  - 依次运行：根目录 `pytest tests/`（gimbal + plate）、`src/gimbal-platform/backend` 的 pytest、`src/gimbal-platform/frontend` 的 vitest；
  - 任一失败即返回非零；
  - 最后输出各部分通过/失败计数的汇总。
- **验收**：
  - [ ] 在新克隆目录（不存在 `gimbal-tmp/`）上执行，四部分都被执行并汇总计数；
  - [ ] 人为制造一个失败用例时，脚本返回非零。
- **不做**：CI 平台接入（Jenkins 属于 P8）。

### P0-02 平台后端测试同步

- **状态（2026-09-28 复核）：已完成——`07831974`。** 平台后端 pytest 719 通过。根因记录：`build_argv` 与夹具形态为存量漂移；`test_run_cancel` / `test_run_plate_resilience` 两例根因是行级 JSONL 停写（M6 设计变更）后测试仍断言 jsonl 行，已改断言 DB 行终态（此前被误判为「时序相关已知挂起」）。以下原文保留供追溯。
- **目标**：消除平台后端现有的 10 个失败。
- **范围**：`src/gimbal-platform/backend/tests/` 下的 `test_gimbal_launcher.py`、`test_run_injection.py`、`test_run_injectable_wire.py`、`test_run_cancel.py`、`test_run_plate_resilience.py`。
- **要求**：
  - `build_argv` 的断言改为 `-o jsonl`；
  - 测试里手写的 step 改为 `call` 形态，断言路径改为 `$.call.response.*`；
  - `test_run_cancel` 与 `test_run_plate_resilience` 先定位根因：属于测试问题就修测试；属于平台调度缺陷就修代码，并在提交信息里写明。
- **验收**：
  - [ ] 平台后端 pytest 0 失败；
  - [ ] 两个定位类用例的根因记录在提交信息中。
- **不做**：改变平台执行链行为（属于 P2/P3）。

### P0-03 跨模块契约测试

- **状态（2026-09-28）**：✅ 已完成——`tests/test_plate_gimbal_contract.py` 4 用例：进程内真 plate（ASGI+lifespan 注册 fin 目录）→ 真注入物化 → 真 gimbal CLI；含 call 形态守卫（产物 step 有 call 无 api，导出器回退 api 即红）
- **目标**：平台 → 真实 plate `/convert` → gimbal 的端到端测试，不使用 PlateMock 的 echo 模式。
- **范围**：平台后端测试目录；利用 plate 在同进程挂载子路由的方式。
- **要求**：至少覆盖——HTTP 单场景成功、断言失败、carry 注入生效、Assign 注入生效。
- **验收**：
  - [ ] 4 个用例通过；
  - [ ] 把 plate 导出器的 call 渲染临时改回 api 形态时，这组测试会失败（证明它确实守住了契约）。

### P0-04 配置卫生

- **状态（2026-09-28）**：✅ 已完成——`.env` 出库 + `.gitignore` 条目 + `.env.example` 更新；GIMBAL_BIN 未设全量 717 绿（2 例引擎可用性守卫 skip）；不注入 PYTHONPATH（src/gimbal 的 logging.py 遮蔽 stdlib 会炸子进程 site 初始化，成文于 launcher 注释）
- **目标**：仓库里不出现开发者本机路径。
- **范围**：`src/gimbal-platform/backend/.env`。
- **要求**：`.env` 移出版本控制，提供 `.env.example`；测试通过 fixture 显式设置 `GIMBAL_BIN`。
- **验收**：
  - [ ] `git ls-files` 中不再有 `.env`；
  - [ ] 未设置 `GIMBAL_BIN` 时平台测试仍然通过。

### P0-05 删除 `run match`

- **状态（2026-09-28）**：✅ 已完成——`run_match.py` 删除、注册/帮助/README 清理；ParallelOpt/TimeoutOpt/RetryOpt 死类型随删；`run --help` 无 match
- **目标**：去掉空命令。
- **范围**：`src/gimbal/cli/commands/run_match.py`、`cli/commands/run.py` 中的注册、根帮助文本里的示例。
- **验收**：
  - [ ] `gimbal run --help` 中不再出现 match；
  - [ ] 根帮助示例中不再引用 `run match`；
  - [ ] 仓库中没有对 `run_match` 的引用。

### P0-06 validate 机器可读输出

- **状态（2026-09-28）**：✅ 已完成——`compiler/errors.py` ErrCode + CompileError{code,location}；compile/validate/resolve `-o json`；五类错误码各有断言（CALL_FIELD_INVALID/UNKNOWN_PROTOCOL/INPUT_UNSATISFIED/SHARED_MISMATCH/CYCLE），失败 exit 2（7 个 CLI 测试）
- **目标**：validate、compile、resolve 的错误结构化，便于 Agent 消费。
- **范围**：`src/gimbal/cli/commands/pipeline_cmds.py`、`compiler/errors.py`。
- **要求**：
  - 支持 `-o json`；
  - 错误结构为 `{code, message, location: {unit?, step?, path?, field?}}`；
  - `CompileError` 带错误码。错误码采用稳定的字符串枚举，例如 `CALL_FIELD_INVALID`、`UNKNOWN_PROTOCOL`、`INPUT_UNSATISFIED`、`SHARED_MISMATCH`、`CYCLE`。
- **验收**：
  - [ ] 对 call 字段拼写错误、未知协议、输入不满足、shared 不一致、依赖成环五类错误，各有一个测试断言 JSON 结构与错误码；
  - [ ] 出错时退出码为 2。

### P0-07 生命周期条目编译期校验

- **状态（2026-09-28 复核）：已完成——`fc48a86d`。** `p_normalize` 增 `_validate_lifecycle_entries`（按 strategy 表查 kind + Params 校验，含 `${}` 模板容忍 `_relax_templates`）；sleep 注册为首个内置生命周期动作。以下原文保留供追溯。
- **目标**：setup/teardown 写错 kind 或参数，在编译期报错。
- **范围**：`compiler/pipeline.py` 的 `p_normalize`；`strategy/dispatcher.py` 的 `params_of`。
- **要求**：kind 必须在 strategy 表中存在；参数用该策略的参数模型校验。
- **验收**：
  - [ ] 未知 kind 与非法参数都在 `gimbal validate` 阶段报错（错误码见 P0-06）；
  - [ ] 合法条目行为不变。

### P0-08 执行器收尾三项

- **状态（2026-09-28）**：✅ 已完成——①join 上限=max(step 协议超时)+5s 余量（`_abandon_join_timeout`，未声明回落 30s；3 测试含 retry 晚于被弃 attempt 退出）；②StrategyPhase 别名删除（默认值换中立名，测试同步）；③validate_plan 别名删除（调用方改 p_validate）
- **目标**：清掉已知的小遗留。
- **要求**：
  1. `scheduler/plan.py` 的 `_ABANDON_JOIN_TIMEOUT_SEC` 改为取单元内各 step 协议超时的最大值（http 取 `timeout`），并加一个固定的余量；
  2. 删除 `schema/strategy.py` 中 StrategyPhase 的历史别名（`BEFORE_REQUEST` 等），并同步所有引用；
  3. 删除 `compiler/pipeline.py` 的 `validate_plan` 别名，调用方改用 `p_validate`。
- **验收**：
  - [ ] 协议超时为 60s、单元超时为 1s 时，被放弃的那次尝试退出之前不会开始重试（用可控耗时的测试协议验证）；
  - [ ] `grep` 不到这两类别名。

### P0-09 前端测试可运行

- **状态（2026-09-28）**：✅ 已完成——lockfile 21 处 npmmirror→官方源；`.npmrc` 默认官方 registry、可用 NPM_CONFIG_REGISTRY 覆盖；vitest 1133 绿
- **目标**：在任意环境都能安装前端依赖。
- **范围**：`src/gimbal-platform/frontend/`（`package-lock.json`、`.npmrc`）。
- **要求**：registry 可配置，默认使用官方 registry；锁文件中不写死镜像地址。
- **验收**：
  - [ ] 在只能访问官方 npm 的环境中，`npm ci && npx vitest run` 能执行完成。

### P0-10 执行器卫生批（盘点补充：路线图 R4–R6）

- **状态（2026-09-28）**：✅ 已完成——strategy/README 占位表对齐（标未实现四项+编译期即拒说明）；poll_timeout/poll_interval 删除；Literal 注解改 "graph"；selector 死分支删除
- **目标**：清除文档失真、悬空配置、注解与死分支。
- **范围**：`src/gimbal/strategy/README.md`、`config/models.py`、`cli/commands/run_target.py`、`suite/selector.py`。
- **要求**：
  1. strategy/README 的占位表与代码对齐：删去不存在的 poll/sql/chaos/composite 条目（实际仅注册 extract/assign/assertion/sleep）；
  2. 删除无消费者的 `poll_timeout` / `poll_interval` 配置字段；
  3. `execute_run_file` 的 Literal 注解改为与实传一致（`"graph"`）；
  4. 删除 `suite/selector.py` 中 `... if False else ...` 恒走 else 的死分支。
- **验收**：
  - [ ] `grep` 不到 poll_timeout / poll_interval / `if False else`；
  - [ ] README 的策略清单与 `gimbal ext list --json` 输出一致。

### P0-11 编译期校验补全（盘点补充：路线图 S1/S2）

- **状态（2026-09-28）**：✅ 已完成——p_validate 第 6 项 users 标签存在性（模板 ${auth.*} + call.user + setup/teardown；Engine 经 auth_tags 放行注册表已就位标签）；p_bind 增并发同名输出检查（SUITE_VAR_CONFLICT；豁免：needs 先后/跨括号组/同源 repeat 变体——变体组经 p_expand→p_desugar 传递）；6 个专项测试
- **目标**：补齐定稿 D3 声明但挂起的两项 dry-run 校验。
- **范围**：`compiler/pipeline.py`（`p_validate` / bind 阶段）。
- **要求**：
  1. **users 标签存在性**：编译期扫描 `${auth.<tag>.*}` 引用与 `call.user` 值，tag 不在 `config.users` 声明中即报错（docstring 已自认挂起）；
  2. **并发尾部写同名变量**：无依赖关系（DAG 不同分支）的多个单元向 suite 层写同名输出时 CompileError，提示用 map 改名。
- **验收**：
  - [ ] 未知 users 标签、并发同名写各有测试断言 CompileError 与错误码（沿用 P0-06 结构，建议 `USERS_TAG_UNKNOWN` / `SUITE_VAR_CONFLICT`）；
  - [ ] 合法引用不受影响（全量测试零回归）。

### P0-12 预认证补全（盘点补充：路线图 S3）

- **状态（2026-09-28）**：✅ 已完成——preprocess 引用面扩至 call.user 字段（eager 登录）；3 测试（含未引用不登录的回归）
- **目标**：执行前预认证覆盖全部被引用的 users 标签（定稿 C7 完整语义）。
- **范围**：`preprocessor/scenario_preprocessor.py`。
- **要求**：除 `${auth.<tag>.*}` 模板引用外，扫描各 step `call.user` 字段引用的标签，一并在 preprocess 期 eager 登录；登录失败按现有错误通道报错。
- **验收**：
  - [ ] 仅经 `call.user` 引用的用户在步骤执行前已完成登录（测试断言首个 step 发送时无 lazy 登录痕迹）；
  - [ ] 多标签场景未被引用的标签仍不登录（保持现状语义）。

---

## 3. P1 执行器可观测性

### P1-01 执行上下文标签

- **状态（2026-09-29）：已完成（ee1e3649）** —— 四边界 contextvar 接线;12 用例 tests/unit/observability
- **目标**：在四个执行边界设置统一的上下文标签。
- **范围**：`log/logger.py`（已有的 contextvar 设施）、`core/runner.py`、`scheduler/plan.py`、`core/scenario_runner.py`、`protocols/base.py`。
- **要求**：
  - 标签：`run`、`unit`、`attempt`、`scenario`、`step`、`module`（取 `meta.module`）、`service`、`protocol`、`endpoint`；
  - 进入边界时设置，退出时恢复；
  - 线程池中每个单元线程的上下文相互隔离。
- **验收**：
  - [ ] 并行度 3、repeat 2 的运行中，每个 step 执行时读到的标签与所属单元和尝试一致。

### P1-02 事件信封盖标签

- **状态（2026-09-29）：已完成（ee1e3649）** —— 总线锁内盖章;jsonl 行形状兼容
- **目标**：所有事件自动带上 P1-01 的标签。
- **范围**：`events/types.py` 的 `FrameworkEvent`、`events/bus.py` 的 `publish`。
- **要求**：
  - 事件基类新增上述标签的可选字段；
  - 总线在发布时，从 contextvar 取值填入尚未设置的字段；
  - 各事件子类与发布点不改。
- **验收**：
  - [ ] `-o jsonl` 输出中，step 与 call 相关事件都带有 unit/attempt/step/module/service/protocol；
  - [ ] repeat 与 n_runs 产生的事件可以相互区分。

### P1-03 日志结构化与分类

- **状态（2026-09-29）：已完成（ee1e3649）** —— log/category.py 唯一映射表;JsonSink 带标签
- **目标**：日志带同一组标签，并带有框架模块分类。
- **范围**：`log/formatters.py`（JSON sink）、`log/logger.py`。
- **要求**：
  - 日志记录包含 P1-01 的全部标签；
  - 新增 `category` 字段，按 logger 名静态映射：`gimbal.protocols.*`、`gimbal.strategy.builtin.call` → call；`gimbal.auth.*` → auth；`gimbal.strategy.*` → strategy；`gimbal.compiler.*` → compiler；`gimbal.scheduler.*` → scheduler；`gimbal.plugins.*` → plugin；`gimbal.core.debugger` → debug；其余 → core；
  - 映射表集中定义在一处。
- **验收**：
  - [ ] 一次运行的 stderr 中，每行 JSON 日志都有 category，且 step 内的日志带 unit/step。

### P1-04 声明式订阅规格

- **状态（2026-09-29）：已完成（e9892afc）** —— CLI/suite/server 三入口同编译器;SUBSCRIBE_INVALID 错误码
- **目标**：不写代码即可订阅事件和日志。
- **范围**：`schema/`（新增订阅规格模型）、`events/bus.py`（编译为 `EventFilter`）、`cli/common.py`（`--subscribe <file>`）、suite schema（`subscribe` 字段）、server 的 `RunsRequest`。
- **要求**：
  - 规格格式：`[{events?: [...], logs?: {level?, category?}, where?: {标签: 值或通配}, sink: stdout|stderr|file:<path>}]`；
  - 在编译阶段校验：未知事件类型、未知标签、未知 sink 都报错（错误码见 P0-06）。
- **验收**：
  - [ ] 同一份规格在 CLI、suite 配置、server 请求中产生相同的输出；
  - [ ] `where: {module: X, status: failed}` 只输出对应的事件。

### P1-05 事件导入与回放

- **状态（2026-09-29）：已完成（e9892afc）** —— gimbal events replay/query;乱序 jsonl 按 seq 回放
- **目标**：一次执行的事件流可以事后查询和重放给报告器。
- **范围**：`cli/commands/`（新增 `gimbal events replay <file.jsonl>` 与 `gimbal events query`），`reporter/runtime.py`。
- **要求**：
  - replay：把 jsonl 事件按 seq 顺序重新喂给指定的报告器，产出与原运行相同的报告；
  - query：用 P1-04 的 where 语法过滤。
- **验收**：
  - [ ] 对同一次运行，原始 html/json 报告与由 replay 产出的报告内容一致（时间戳字段除外）。

---

## 4. P2 平台执行链一期（不改进程模型）

### P2-01 单元级台账迁移（0007）

- **状态（2026-09-29）：已完成（b01468a0,0008 迁移）** —— unit_id/branch/attempts;升降级往返验证
- **目标**：台账从"行"改为"单元"。
- **范围**：`backend/alembic/versions/0007_*.py`、模型定义、`services/execution_store.py`。
- **要求**：新增 `unit_id`（别名 + 展开序号，与执行器一致）、`branch`、`attempts`；dataset/injection/row_index 保留为单元属性。**一并补 `skipped` 计数列**（`run.finished` 已携带、当前只留在 result.json 工件）。
- **验收**：
  - [ ] 迁移可以升级也可以降级；
  - [ ] 现有台账查询接口的输出不变。

### P2-02 事件与日志存储

- **状态（2026-09-29）：已完成（b01468a0）** —— execution_events 统一表;证据拆表;保留期配置
- **目标**：执行器产出的事件和日志入库。
- **范围**：alembic 迁移（可与 P2-01 合并为 0007，或单独 0008）；`services/execution_store.py`。
- **要求**：
  - 一张统一表，字段包括：execution_id、seq、ts、kind（event/log）、level、category、module、service、protocol、unit、attempt、step、event_type、message，原始内容存 JSONB；
  - 标签列建索引；
  - `call.exchange` 的证据体单独存储，主表只留摘要与引用；
  - 定义保留期限配置。
- **验收**：
  - [ ] 一次含 3 个单元的执行，事件条数与执行器 jsonl 的行数一致；
  - [ ] 按 `(execution_id, category, unit)` 查询命中索引（用 EXPLAIN 确认）。

### P2-03 流式读取 jsonl

- **状态（2026-09-29）：已完成（27ddc8b7）** —— launcher 逐行回调;_EventIngester 双轨冲刷;kill 保留已读
- **目标**：平台边运行边读取执行器输出。
- **范围**：`services/gimbal_launcher.py`、`services/run_dispatcher.py`。
- **要求**：
  - stdout（事件）与 stderr（日志）逐行读取并写入 P2-02 的表；
  - 最终判定仍取 `run.finished`；
  - 子进程异常退出时，已读取的内容保留。
- **验收**：
  - [ ] 执行尚未结束时，数据库中已经可以查到该执行的 step 事件；
  - [ ] 执行器进程被强制杀掉时，已写入的事件不丢失。

### P2-04 台账从事件投影

- **状态（2026-09-29）：已完成（d74f1494）** —— scenario.end 定行状态;run.finished 投影 attempts/unit
- **目标**：单元状态与计数由事件决定。
- **范围**：`services/run_dispatcher.py`、`services/execution_store.py`。
- **要求**：删除平台自行写入行状态的逻辑，改为根据 `scenario.end` 与 `run.finished` 投影。
- **验收**：
  - [ ] 同一批场景，投影出的计数与 `run.finished` 中的计数逐字段一致。

### P2-05 乘法下沉到执行器

- **状态（2026-09-29）：已完成（d74f1494/954fa057/1ea4caaf）** —— N4 CLI 参数 + nRuns 循环删除 + run.finished 带 attempts
- **目标**：平台不再自己循环 nRuns、并发。
- **范围**：`services/run_dispatcher.py`（`n_runs` 相关循环）、`services/run_materialize.py`；**前置（gimbal 侧）**：`run scenario` / `run suite` 增 `--n-runs` / `--retry` / `--parallel` 参数（定稿 D-16 的 scenario 半边；当前 n_runs 无任何 CLI 入口，launcher 传参无从组装）。
- **要求**：n_runs/retry/parallel 作为执行器参数传入；平台只负责数据集 × 注入的组装。
- **验收**：
  - [ ] nRuns=3 时平台只启动一个执行器进程，台账 attempts=3；
  - [ ] 删除后，平台代码里 grep 不到对 `n_runs` 的循环。

### P2-06 平台 → 浏览器 SSE

- **状态（2026-09-29）：已完成（ee0016b9）** —— SSE 端点(Last-Event-ID/心跳/done);前端 fetch-SSE 替代 1s 轮询
- **目标**：用 SSE 替代每秒轮询。
- **范围**：`backend/app/routers/executions.py`（新增事件流端点）；`frontend/src/views/Executions.vue`。
- **要求**：推送的是已入库的事件；支持 `Last-Event-ID` 续传；带心跳；鉴权沿用平台会话。
- **验收**：
  - [ ] 执行页不再发起 1 秒一次的轮询；
  - [ ] 断线重连后事件不重复、不丢失。

### P2-07 日志分析页

- **状态（2026-09-29）：已完成（ee0016b9）** —— 组合筛选 + level_min + 聚合;前端筛选页 + 工作台卡片
- **目标**：按模块标签筛选和分析日志与事件。
- **范围**：后端查询接口；前端新增视图，并在工作台补一张卡片（与现有页面的做法一致）。
- **要求**：
  - 支持按 category、module、service、protocol、unit、step、level、event_type 组合筛选；
  - message 支持全文搜索；
  - 支持按标签聚合计数；
  - 标签只取执行器写入的值，不从文本推断。
- **验收**：
  - [ ] 能筛出"某 module 下 auth 类 warning 以上的日志"；
  - [ ] 能展示按 category 聚合的计数。

---

## 5. P3 平台执行链二期（进程模型切换）

### P3-01 PG 队列

- **状态（2026-09-29）**：✅ 已完成——0009 迁移 execution_jobs（一执行一任务，fresh 守卫）；claim_next 用 FOR UPDATE SKIP LOCKED（PG）/普通子查询（SQLite）；租约+heartbeat+attempts 上限的孤儿回收（sweep_stale）；dispatch 只入队（ensure_workers 惰性入口覆盖 lifespan 未跑的测试直连）；取消=cancel_requested DB 位+本进程 advisory 快速通道；_in_flight/_cancel_requested/_tasks_by_execution/全局 launch 信号量退役；重启恢复：queued 任务留存续跑、无 job 僵尸 failed 收口；单 worker 串行测试钉住跨执行上界。6 个队列专项测试。
- **目标**：执行任务持久化排队。
- **范围**：alembic 迁移；`services/run_dispatcher.py`。
- **要求**：用 `FOR UPDATE SKIP LOCKED` 取任务；删除 `_in_flight`、`_cancel_requested` 与进程内信号量；支持多个 worker。
- **验收**：
  - [ ] 平台重启后，排队中的任务继续执行，已在运行的任务按对账结果收口；
  - [ ] 两个 worker 并行运行时，同一任务不会被重复执行。

### P3-02 执行进程模型切换

- **状态（2026-09-29）**：✅ 已完成——services/gimbal_server_session.py：每执行一个 ``gimbal run server`` 实例（随机空闲端口+平台生成 token+healthz 就绪等待）；POST /runs + SSE 逐帧消费（chunk 边界缓冲分行,事件入 execution_events 同一面）；run.finished 计数映射 LaunchResult；超时→cancel 端点+3s 宽限→launch_status=timeout；close()=terminate→wait→kill 无残留。执行器侧配套：POST /runs/{id}/cancel（外层取消事件,步骤边界/未启动单元生效——_CompositeCancel 双向传播+单元边界短路）;RunsRequest n_runs/parallel(apply_multiplication 同款变换);run_status 摘要补 attempts/skipped/halted。修 P2 遗留:多 case 事件 seq 撞唯一约束被静默丢弃→execution 级单调分配器。server 链端到端测试(真实拉起实例)通过。
- **目标**：每次执行起一个执行器 server 实例（总案决策 15）。
- **范围**：`services/gimbal_launcher.py`、`services/run_dispatcher.py`。
- **要求**：
  - worker 启动执行器 server，使用 `POST /runs` 下发任务，通过 SSE 消费事件（写入 P2-02 的表），执行结束后回收实例；
  - 执行器 server 的 token 由平台生成并持有；
  - 取消走执行器的 cancel 端点。
- **验收**：
  - [ ] 取消在 2 秒内生效；
  - [ ] Windows 与 Linux 上都没有残留的执行器进程。

### P3-03 灰度与对账

- **状态（2026-09-29）**：✅ 已完成——settings.EXEC_CHAIN(legacy|server,默认 legacy=回滚路径即关开关)；dispatch_run(chain_override=) 供对账强制链,config_json.chain 留档；scripts/reconcile_chain.py：同配方双链各跑一次,逐字段 diff(行 unit/status/attempts+计数)+事件类型集合与量级(>20% 差异)比对,verdict match/mismatch。
- **目标**：新旧执行链可以按执行粒度切换，并能对账。
- **要求**：提供特性开关；对同一场景可以两条链各跑一次，逐字段对比单元状态、计数与耗时量级；保留回滚路径。
- **验收**：
  - [ ] 选定的基准场景集在两条链上结果一致；
  - [ ] 关闭开关即回到旧链。

### P3-04 调试页

- **状态（2026-09-29）**：✅ 已完成——引擎侧 schema/debug.py 结构化命令(N6:kind+variable/path/value 成对校验,parse_debug_command 统一 CLI 文本协议,server 请求体直接校验 422);GET /runs/{id}/debug/output。平台侧 RunRequest.debug(单 case+nRuns=1+非 graph 强校验 409,恒走 server 链);/executions/{id}/debug(信息|output|command 三代理,token 不出后端);前端 RunConfigPanel 调试模式(pause/断点)+DebugConsole 调试台(事件流 after_seq 增量/输出轮询/九命令面板,write/patch 改值表单)+路由与发起直达跳转。取消语义/结构化校验/代理投影/端到端 server 链均有测试。
- **目标**：在平台上单步调试一个场景。
- **范围**：后端代理执行器 `/runs/{id}/debug`；前端新增调试视图。
- **要求**：
  - 支持断点地址、暂停模式、continue/step/abort、read、write、patch、retry、skip；
  - 事件流实时显示；
  - 前端不接触执行器 token；
  - **调试运行类型建模**：RunRequest 增 debug 形态，后端强制「单单元且 n_runs=1」（引擎 `schema/plan.py:115` 的既有约束），不满足直接拒绝发起；
  - **调试命令结构化**（路线图 N6）：会话命令从自由文本 + 正则解析升级为 `schema/debug.py` 结构化 schema，write/patch 参数经校验。
- **验收**：
  - [ ] 对一个运行中的场景：在 call_before 处暂停 → patch 请求体 → continue，被测系统收到的是 patch 之后的值；
  - [ ] 失败时暂停 → write 变量 → retry → 通过，该 step 标记为 repaired。

### P3-05 suite 编排页

- **状态（2026-09-29）：已完成（d27d499b）** —— graph 物化下发 + 前端编排(mode/单元/gates/checks)+ 台账单元投影;N5 前置同批(085557f9)
- **目标**：在平台上编排并执行 graph。
- **范围**：前端新增视图；后端生成 graph 并下发给执行器。
- **要求**：
  - 支持 aggregate/compose/fanout/chain、shared、before/after、control；
  - 参数表单由 `gimbal ext list --json` 的 schema 生成——**前置：mode 表 params_schema 注册**（定稿 A7 未落地，当前恒 None，表单会渲染不出内容）；
  - 保留"多条独立执行"的旧用法；
  - suite 横切面（checks/gates/metrics/plugins）与 SUITE 生命周期事件是否纳入本页，由 D-6 拍板后定范围。
- **验收**：
  - [ ] 一个 chain 模式的 graph 可以在平台上编排、执行，并在台账中按单元展示。

### P3-06 报告定义（执行器侧）

- **状态（2026-09-29）：已完成（80b02153）** —— ReportDefinition schema + DefinitionReporter;replay 一致性
- **目标**：按内容定制报告。
- **范围**：`reporter/`（新增通用的"定义驱动"报告器），`schema/`（报告定义模型）。
- **要求**：报告定义 = 选择（P1-04 的订阅规格）+ 投影（JSONPath 字段清单）+ 呈现（html/markdown 模板或表格列）；现有报告器保留。
- **验收**：
  - [ ] 一份定义可以生成"失败 step + 请求体 + 响应体中某字段"的 html 报告，执行器本地与 replay（P1-05）的产出一致。

### P3-07 报告定义（平台侧）

- **状态（2026-09-29）：已完成（80b02153）** —— CRUD + 私有/公共权限域 + RunRequest.reportDefinitionId
- **目标**：平台存储并复用报告定义。
- **要求**：报告定义按用户或团队存储，区分私有区与公共区；执行时可选择报告定义；报告作为执行的工件存储。
- **验收**：
  - [ ] 在平台上选择一份报告定义执行，可以从执行详情下载对应报告。

### P3-08 配置规范（路线图 N3，定稿 D8）

- **状态（2026-09-29）：已完成（773ec1ff）** —— 参数登记表 + p_patch 接线 + 值来源追踪;11 用例
- **目标**：调用参数有登记表与值来源追踪，补丁叠加可解释。
- **范围**：`compiler/pipeline.py`（`p_patch` 接线）、`schema/`（参数登记模型）。
- **要求**：
  - 参数登记表：每个可配置参数声明级别（suite / 单元 / 调用参数）、合并方式、允许来源、作用范围；
  - `p_patch` 五层补丁接线（当前恒等挂起，合并代数已有单测钉死），`--var` 从 extras 旁路并入补丁流水线；
  - 生效副本可产出「值来源」说明（哪个层改了什么）。
- **验收**：
  - [ ] 同一参数经 suite 补丁与调用参数两层设置时，生效值与登记表的合并规则一致，来源说明正确；
  - [ ] 现有 `--var` 行为不变（全量测试零回归）。

---

## 6. P4 plate 通用化（需先完成决策 D-1）

### P4-01 EndpointSpec 中立外壳与 binding

- **目标**：EndpointSpec 不再绑定 HTTP。
- **范围**：`gimbal_plate/schema/endpoint/endpoint.py`、`api_spec.py`。
- **要求**：`api` 改为 `binding: {protocol, ...该协议的字段}`；HTTP 的 binding 字段 = 现有 ApiSpec 的字段；外壳保留 id/system/service/name/metadata、declarations、query_views。
- **验收**：
  - [ ] fin 系统全部端点迁移到新结构（一次性脚本）；
  - [ ] plate 的测试全部通过。

### P4-02 响应按结果判别

- **目标**：响应结构不再以 HTTP 状态码为键。
- **范围**：`endpoint.py`（`responses`）、`io_spec.py`。
- **要求**：改为以"协议结果判别"为键，每种结果一棵响应声明树；HTTP 的判别值为状态码。
- **验收**：
  - [ ] fin 端点迁移后，导出的 gimbal 与平台视图和迁移前逐键等价。

### P4-03 路由索引按协议分派

- **范围**：`gimbal_plate/registry/index.py`。
- **要求**：每个协议声明自己的唯一定位字段；HTTP 仍为 (service, method, path)。
- **验收**：
  - [ ] 注册一个测试协议后，按它的定位字段可以查到端点。

### P4-04 binding schema 过渡来源

- **目标**：plate 用执行器导出的协议参数 schema 校验 binding（方案 A）。
- **要求**：plate 读取 `gimbal ext list --json` 中 protocol 表的 `params_schema`；binding 校验与编排器表单都以它为准。
- **验收**：
  - [ ] 在执行器新注册一个协议后，不改 plate 代码即可校验该协议的 binding。

### P4-05 执行器 services 配置带协议

- **范围**：`src/gimbal/schema/scenario.py`（`Config.services`）、`preprocessor/`、http 适配器。
- **要求**：`services: {name: {protocol, base_url, ...}}`；由对应的协议适配器解释。存量用例一次性迁移，不保留旧形态。
- **验收**：
  - [ ] 迁移后的用例执行结果与迁移前一致。

### P4-06 平台编排器按协议渲染

- **目标**：编排器从渲染 ApiSpec 改为按协议渲染 binding。
- **范围**：`frontend/src/components/composer/`、`frontend/src/types/plate.ts`。
- **验收**：
  - [ ] HTTP 端点的编排体验不变；
  - [ ] 测试协议的端点可以在编排器中配置并执行。

### P4-07 接入适配器约定

- **目标**：定义外部来源进入 plate 的中间形态与落点。
- **要求**：产出约定文档与一个参考实现（以 curl 导入为参考）；明确归一化的落点（EndpointSpec / EndpointDoc / 用户故事）。
- **停止条件**：约定中涉及新增结构（例如 EndpointDoc）时，提交设计交人评审后再实现。

### P4-08 第二协议验证

- **前置**：决策 D-1。
- **目标**：用真实的第二协议验证 P4-01 至 P4-06。
- **验收**：
  - [ ] 只新增协议适配器与 binding 定义，EndpointSpec 外壳与执行器核心零改动，即可端到端执行一个该协议的场景。

---

## 7. P5 release 与版本

### P5-01 冻结流程

- **范围**：`gimbal_plate/release/release.py`（替换占位实现）。
- **要求**：import 入 registry 并校验 → 序列化目标系统全部 EndpointSpec → 生成 manifest（含 content_hash、release_id、system_version）→ 原子写入 `plate_artifacts/<系统>/<版本>/`；latest 为指针；已写入的版本不可覆盖。
- **验收**：
  - [ ] 对同一代码冻结两次，content_hash 相同；
  - [ ] 写入中途失败不会留下半成品目录。

### P5-02 水合与按版本查询

- **要求**：构件用当前 schema 类水合；HTTP 接口支持按 release_id 查询各视图。
- **验收**：
  - [ ] 按版本取回的视图与冻结时逐字节一致。

### P5-03 值记录关联版本

- **范围**：平台 endpoint_value / scenario_case 相关表。
- **要求**：值记录带 release_id；物化时按 release_id 请求 plate。

### P5-04 用例变更插件

- **要求**：契约为 `(endpoint_id, from_version, to_version, old_value_json) → new_value_json`；平台按 `(endpoint_id, release_id)` 圈定记录，支持批量迁移与惰性迁移两种时机。
- **验收**：
  - [ ] 修改一个端点结构并冻结新版本后，存量值经插件迁移，迁移后的场景执行通过。

### P5-05 首个 release

- **前置**：P4 全部完成。
- **验收**：
  - [ ] fin 系统冻结首个 release，平台切换为按版本取定义。

---

## 8. P6 真相源反转（需先完成决策 D-3）

### P6-01 plate 发布执行态 schema 构件

- **要求**：release 同时产出执行态 schema（JSON Schema）构件。

### P6-02 gimbal 离线加载 schema 构件

- **要求**：gimbal 加载指定版本的本地构件进行校验；运行时不访问 plate HTTP，保持可独立运行。
- **验收**：
  - [ ] 断开 plate 服务时，gimbal 仍可用本地构件校验并执行。

### P6-03 按决策 D-3 处理 gimbal 模型类

### P6-04 消除镜像维护与 binding schema 翻转

- **要求**：移除 field_states 的三处镜像清单；binding schema 的真源由执行器翻转到 plate。
- **验收**：
  - [ ] 结构字段只在 plate 中定义一次，其他地方 grep 不到重复定义。

---

## 9. P7 CLI 归一

### P7-01 组件注册约定

- **要求**：各包通过 Python 入口点把命令组注册到统一的 `gimbal` 入口；未安装的组件不出现在帮助里。

### P7-02 plate 与 platform 命令组

- **要求**：`gimbal plate ...` 与 `gimbal platform ...` 分别作为 plate HTTP 与平台 API 的薄客户端，不在 CLI 中实现业务逻辑。

### P7-03 统一输出契约

- **要求**：所有命令支持 `-o json`；错误结构与 P0-06 一致；写操作支持 `--dry-run`。
- **验收**：
  - [ ] 一个脚本遍历全部命令，对 `-o json` 的输出做 schema 校验并全部通过。

---

## 10. P8 外部集成

### P8-01 推送类插件约定

- **要求**：凭证由平台下发，插件不自行管理；推送失败不影响测试判定，但记录为事件；提供可配置的重试。

### P8-02 Jenkins

- **要求**：提供 Jenkins 调用执行器 CLI 与平台 API 的参考流水线；结果使用现有 junit 报告器输出。

### P8-03 Jira 推送

- **要求**：失败时自动建缺陷（去重规则需说明）；可回写需求或用例的执行状态。

### P8-04 Confluence 推送

- **要求**：按报告定义（P3-06）生成或更新报告页。

### P8-05 Jira / Confluence 拉取

- **前置**：P4-07。
- **要求**：经 plate 接入适配器拉取需求与 PRD，关联 `meta.requirementRef`；平台后端提供 Webhook 接收与定时同步。

---

## 11. 待拍板事项（遇到即停）

| 编号 | 事项 | 阻塞 |
|---|---|---|
| D-1 | 第二协议的具体目标（gRPC / Dubbo / MQ / 数据库 / shell） | P4-08，并影响 P4-01~03 的设计取舍 |
| D-2 | 协议 binding schema 的真源 | 过渡期按方案 A（执行器为真源）执行；翻转时机在 P6 |
| D-3 | 反转后 gimbal pydantic 类的去向：由构件生成 / 仅用构件校验 / 移除改走 JSON | P6-03 |
| D-4 | 调试页是否提前到 P2 之后（只为调试会话起执行器 server） | P3-04 的时机 |
| D-5 | 外部集成的推送方向是否提前到 P2 之后 | P8-01~04 的时机 |
| D-6 | suite 横切面（checks/gates/metrics/plugins，定稿 D6）与 SUITE 生命周期事件（定稿 D7）是否仍要 | 裁撤则删除 SuiteStart/SuiteEndEvent 死类型；保留则随 P3-05 一批实现，避免编排页二次返工 |
| D-7 | platform_uploader reporter 的退役时机 | 其职责被 P2-03/P2-02 的平台拉流取代且平台无接收端点；建议 P2 落地后退役，不补接收端 |
