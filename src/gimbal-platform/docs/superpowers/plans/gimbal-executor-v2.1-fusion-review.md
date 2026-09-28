# feat/executor-v2.1-fusion 评审问题清单

- 评审对象：`gadoid/Gimbal` 分支 `feat/executor-v2.1-fusion`，提交 `52388d6`
- 评审日期：2026-09-28
- 对照基准：《GIMBAL 执行器重构方案 v2》、《GIMBAL 执行器重构 v2.1 融合实施案》

## 结论

方向正确，Plan 单路径、CallResult、协议注册、Decision、事件 seq/jsonl 的骨架已按 v2 落地。但以下问题使本分支暂不可合并：

- plate 在此提交中无法 import；
- 并行、括号、shared、调试等路径存在已复现的正确性缺陷；
- v2 的核心设计"统一注册机制"基本未落地；
- 实施案中"v2.1 全案收官"的状态与代码不符。

## 验证情况

| 项 | 结果 |
|---|---|
| gimbal 侧单测（13 个目录） | 356 个全部通过 |
| `tests/plate` | 无法收集（见 P0-1） |
| CLI 冒烟：`run launch -o jsonl` 对本地 HTTP | stdout 14 行全为合法 JSON，末行 `run.finished`，exit=0 |
| 下列缺陷 | 均在分支代码上用脚本实际复现，"复现"列为实际输出 |

---

## 一、必须修复（正确性）

### P0-1 plate 缺失 `schema/call.py`，整个 plate 无法 import

- 位置：`src/gimbal-plate/gimbal_plate/schema/step.py:14` 引用 `gimbal_plate.schema.call`，该文件未提交。
- 影响：`import gimbal_plate` 报 `ModuleNotFoundError`；plate 服务无法启动，`tests/plate` 全部无法收集。
- 修复：补提交 `schema/call.py`。

### P0-2 并行模式下 n_runs / retry / lock 全部失效

- 位置：`src/gimbal/scheduler/plan.py` `_schedule_parallel`：直接 `pool.submit(run_unit, …)`，绕过了 `_run_one`（乘法核与 lock 都在 `_run_one` 内）。
- 复现：
  - parallel=1、n_runs=3 → 发送 3 次；parallel=2、n_runs=3 → 只发送 1 次；
  - 3 个单元同 `lock: db`、parallel=3 → 锁内最大并发 = 3。
- 修复：并行分支提交 `self._run_one(run_unit, u, inputs)`；`_lock_for` 的 `setdefault` 加锁。

### P0-3 scratch 存的是"证据形态"，导致断言/提取失败

- 位置：`src/gimbal/protocols/result.py`：`to_scratch()` 直接返回 `to_evidence()`。
- 问题：
  - 响应头（meta）中键名含 `token` / `cookie` / `password` 等的字段在 scratch 中被替换为 `***redacted***`；
  - 请求体中同类键名也被脱敏；
  - body 序列化超过 64KB 时被截断为字符串。
- 复现：
  - 断言 `$.call.response.meta.headers.accesstoken eq abc123` → failed（同一响应上 `$.call.response.body.orderNo` → passed）；
  - body 超过 64KB 时，`$.call.response.body.orderNo`、`items[0].i` 全部 failed。
- 影响：从响应头取登录 token、大列表查询类接口的所有提取与断言都会失败。
- 修复：scratch 存原值；脱敏与截断只在事件、归档、报告等出口做。

### P0-4 before 括号失败不影响判定，主体照常执行

- 位置：`src/gimbal/core/runner.py` `_assemble_aggregate`（括号行不参与 exit_code）；`scheduler/plan.py` 注释写明 before 失败"不阻断主体"。
- 复现：before 单元断言失败 → `exit=0 passed=1 failed=0`，括号行状态为 failed。
- 修复：before 失败时，主体单元记 blocked，并计入 exit_code；after 失败同样计入判定。

### P0-5 after 括号无法消费主体单元输出

- 位置：`src/gimbal/compiler/pipeline.py` bind 阶段：after 单元的 ancestors 只含 before 单元。
- 复现：主体单元提取 `orderId`，after 单元引用 `${orderId}` → CompileError（输入不满足）。
- 影响：总案定义的"after 依赖单元 = 业务清理（取消单据）"无法表达。
- 修复：after 单元的可见上游应为 before 加全部主体单元；主体未产出时按 blocked 或跳过处理，需成文。

### P0-6 shared 塌缩不比较 inputs，静默丢单元

- 位置：`src/gimbal/compiler/pipeline.py` `_collapse_shared`：只比较 `scenario.model_dump()`。
- 复现：两个单元 `shared="L"`，inputs 分别为 `{user: buyer}` 与 `{user: seller}` → 塌缩后只剩 `a`（buyer），seller 被静默丢弃。
- 修复：一致性校验纳入 inputs（以及 policy、map 等影响生效定义的字段），不一致即 CompileError。

### P0-7 静态分析与步骤顺序无关，产生静默错绑

- 位置：`src/gimbal/compiler/analysis.py`：`required = refs - outputs`。
- 问题：场景先使用 `${orderId}`、后又提取 `orderId` 时，输入被输出抵消。
- 复现：生产者提取 `orderId`；消费者先使用 `${orderId}`、再提取 `orderId`。chain 编译后 inputs 为空，wiring 为空，编译无报错，运行期模板未解析。
- 说明：这正是总案风险登记册第 1 条"错了不报错"。
- 修复：按 step 顺序做数据流分析——某变量在首次被产出之前被引用，即计为输入。

### P1-8 静态分析的内部前缀误伤业务变量

- 位置：`src/gimbal/compiler/analysis.py` `_INTERNAL_SCRATCH_PREFIXES`，按 `startswith` 匹配 `call` / `scratch` / `response_` / `echo_` 等。
- 复现：Assign source `$.callbackUrl` → inputs 为空（被当作内部 scratch 键排除）。
- 另：`echo_` 是测试协议名，泄漏进生产代码。
- 修复：内部键按精确键名（`call`、`request_body`）匹配，删除 `echo_`。

### P1-9 debugger 中止后重复暂停

- 位置：`src/gimbal/core/debugger.py` 与 `core/scenario_runner.py`：STEP_BEFORE 的 abort 使 step 变为 ERROR，随后又触发 STEP_FAILED，debugger 再次暂停。
- 复现：pause=every_step，命令 `q` → paused_count=2，第二次提示为 `step.failed … aborted: debugger:abort`。
- 修复：step 的 abort 来源为 debugger 时，不再询问 STEP_FAILED；或让 abort 直接终止 run。

### P1-10 debugger 未实现改值能力

- v2 定义的会话命令包含 `write`（改变量）和 `patch`（改待发请求），实现只有 continue / step / abort / read / retry / skip。
- `Decision.patch` 通道存在，但 debugger 从不产生 patch，调试只能看不能改。
- 另：STEP_FAILED 的 retry 只重跑一次，重跑后若仍失败，不再询问。

### P1-11 n_runs 计数口径不一致

- 位置：`src/gimbal/core/runner.py`：total 按 attempts 累加，passed 按单元计数。
- 复现：n_runs=3 全部通过 → `total=3 passed=1`；测试 `test_n_runs_counts_every_run` 把这个结果写成了预期。
- 修复：统一口径——要么全按 attempt 计数，要么全按单元计数、attempts 单列。

### P1-12 已声明但不生效的字段

- `PlanPolicy.timeout`、`UnitPolicy.timeout`：没有任何代码读取。
- `Scenario.config.setup` / `teardown`、`config.retry`：声明了，执行器不执行。
- 修复：实现，或在实现前从 schema 中删除（与"不留占位"原则一致）。

---

## 二、与 v2 设计的结构性偏离

### S-1 统一注册机制基本未落地

- `core/registry.py` 的 `Registry[T]` 只有 mode 表在使用，且 params 为 None。
- strategy 的参数 schema 靠 `cli/commands/ext_cmds.py` 中硬编码的 dotted 映射获取。
- protocol 的 `params_schema` 为 None。
- `schema/call.py` 的 `Call` 为 `extra="allow"`，协议字段在编译期完全不校验（v2 要求在 normalize 阶段用适配器 Params 校验）。

### S-2 协议表与策略表耦合

- `ProtocolExecutor` 继承 `StrategyExecutor`，经 dispatcher 分派；spec 必须 duck-type StrategyBase。
- hook_registry 与 event_bus 经 `pctx` 塞进 spec 传递。
- 认证（`login`）未并入协议适配器，仍是 AuthRegistry 加上 http 适配器内的专用逻辑。

### S-3 拦截与观察二分未完成

- HookPoint 仍保留 `RUN_START`、`SCENARIO_START`、`STEP_START` 等观察型点。
- Decision 通过 `raise HookSignal.STOP(Decision(...))` 夹带返回，而不是作为返回值。
- CALL_BEFORE 补丁有两条路：原地改写 request 视图，以及 `Decision.patch`。
- CALL_AFTER 仍是普通 fire，不是 Decision，RETRY 不可用。
- `HookRegistry.trigger` 在全局 RLock 内执行 handler：并行时所有 STRATEGY_BEFORE 等串行化；debugger 阻塞等待输入时一直持锁。

### S-4 编译管线不是七个纯函数

- 实际为 `_graph_plan` 一个约 150 行的函数。
- normalize、patch（五层合并代数）、expand（数据集展开）均不存在；`validate_plan` 只检查 mode 名。
- commit message 的"七阶段管线"与代码不符。

### S-5 run.finished 不是总线事件

- CLI 在 `cli/common.py` 中手工拼 dict 打印；`events/types.py` 的 `RunFinishedEvent` 定义了但从未发布。
- 结果：server/SSE 拿不到终态，终态没有 seq。
- SSE 的 `id` 使用事件列表下标，而不是 seq。

### S-6 server 调试端点缺少保护

- server 路径没有"单单元 + 强制串行"的检查（只有 CLI 做了）。
- `POST /runs` 无鉴权；运行注册表和事件缓冲从不回收。
- async handler 中调用了阻塞的 `time.sleep(0.05)`。
- CLI 下 `--debug` 与 `-o jsonl` 同时使用时，调试提示会混入 stdout 事件流。

---

## 三、违背"不留兼容层"原则的残留

| 残留 | 位置 |
|---|---|
| StepState 三组别名（BEFORE_REQUEST / CALLING / AFTER_REQUEST） | `statemachine/states.py` |
| http 协议 kind 仍为 `"_call"` | `protocols/base.py`、`strategy/builtin/call.py` |
| `--breakpoint` 重载：数字 = halt_at，地址 = debugger 断点 | `cli/commands/run_launch.py` |
| `RuntimeControl` 仍作为参数载体 | `core/scenario_runner.py` |
| scratch `request_body` 键保留 | `statemachine/engine.py` |
| 两套结果组装口径 | `core/runner.py` `_assemble_implicit` / `_assemble_aggregate` |
| 死代码 `SuiteScheduler`、`dispatch_parallel` | `scheduler/scheduler.py`、`scheduler/concurrency.py` |
| plate step 的 api / call 双 Optional | `gimbal_plate/schema/step.py` |
| `run scenario` / `run suite` 缺少 `--where`、策略参数与 step_from，功能仍集中在 `run launch` | `cli/commands/run_target.py` |

---

## 四、工程卫生

- 一个提交包含 205 个文件、+35,740 / −22,626 行，难以评审。
- 混入了非代码内容：`gimbal-tmp/` 语料、`reports/test-report.html`（运行测试会重新生成）、截图。
- 实施案中批次 A–F 同日全部标 ✅ 并写"全案收官"，与本清单问题不符。
- 建议：按批次拆分提交；语料与报告不入库或加入 `.gitignore`；文档状态与代码同步更新。

---

## 五、建议修复顺序

1. P0-1：补 plate `schema/call.py`。
2. P0-2、P0-4、P0-6：并行乘法与锁、before/after 判定、shared 比较 inputs。
3. P0-3：scratch 与证据分离。
4. P0-7、P1-8：静态分析改为按 step 顺序的数据流分析，内部键精确匹配。
5. P0-5、P1-9 ~ P1-12：after 连线、debugger、计数口径、清理无效字段。
6. S-1 ~ S-6：注册表收敛、协议与策略解耦、hook 二分、编译管线拆分、终态事件化、server 保护。
7. 第三、四节：兼容残留清理与提交拆分。


---

## 六、修复记录（2026-09-28 勾销对照）

| 项 | 修复提交 | 备注 |
|---|---|---|
| P0-1 plate schema/call.py | 0658aac8 | 补提交恢复 import 与测试收集 |
| P0-2 并行乘法/锁失效 | 062b47e9 | 并行分支走 _run_one；_lock_for 加锁 |
| P0-3/P0-3b scratch 原值/出口脱敏 | 03dd4bdb / 2bd9145d | scratch 存原值，脱敏截断只在证据出口 |
| P0-4 before/after 判定 | 5ef34fc1 | 括号失败计入判定，before 失败阻断主体 |
| P0-5 after 连线 | 55d3d79e | after 可见上游含全部主体单元；缺输入注入 None 成文 |
| P0-6 shared 塌缩一致性 | f5dd3395 | 比较全量生效定义（inputs/policy/map/repeat） |
| P0-7/P1-8 静态分析 | f2205a6b | 按 step 序数据流；内部键精确匹配、删 echo_ |
| P1-9 abort 二次暂停 | 973d688a | debugger abort 后不再触发 STEP_FAILED |
| P1-10 write/patch/retry 循环 | 9e9e29db | 会话命令补齐 |
| P1-11/P1-12 计数口径/timeout/retry | dc039d77 | 单元口径 + attempts 单列；timeout/retry 全链路 |
| S-1 统一注册机制 | 141ebc7f | Registry 收敛 + params_of + Call 编译期校验 + ext 删硬编码 |
| S-2 协议/策略表解耦 | 32bde794 | ProtocolExecutor 独立 ABC；login 并入适配器；_do_call 直调 |
| S-3 拦截/观察二分 | 7ad66b31 | HookPoint 收缩七拦截点；STOP/HookResult 退役→Decision 列表；trigger 锁外执行 |
| S-4 七阶段管线 | 3990b3e7 | p_load/normalize/patch/desugar/expand(4096 闸)/bind/p_validate |
| S-5 run.finished 事件化 | 7ad66b31 | RunFinishedEvent 带 seq 发布；jsonl 终线事件化；SSE id=seq+续传 |
| S-6 server 保护 | 28383c69 / 68fcbf12 | POST /runs 鉴权+回环限制；单单元校验；注册表回收；asyncio.sleep；CliSession 走 stderr |
| 残留 1-3 | 07ddbfb4 | 状态别名删除；kind "_call"→"call"；--breakpoint 拆 --halt-at |
| 残留 4-9 | bdd599d3 | RuntimeControl 裁定；$.call.request.body 统一；组装合一；死代码删除；plate 恰其一守卫；run target 补参 |
| 工程卫生 | 65169384 | 语料/报告出库 .gitignore（123 文件）；实施案状态勘误 |
| （附）主线基线漂移 | d6872fe6 | order_add_demo 入册未回填 + call 形态迁移未重钉 + tests 根包化（评审"无法收集"之外的既有漂移，随本轮修复） |

全量验证：`python -m pytest -q` → 1014 passed（gimbal + plate 全目录）；
CLI 冒烟：`run launch -o jsonl` 末行 run.finished(seq)、`--halt-at` halted 语义、`self-check` 12/12。

### 补充轮（2026-09-28 遗漏审计）

| 项 | 修复 | 备注 |
|---|---|---|
| D-15 检索器空壳 / --where 缺失（残留 #9 的 --where 部分） | suite/selector.py 落地（目录枚举 + 直接字段 AND 匹配 + 零命中报错）；run scenario 增 `--where`/目录双模式（D-14）；5 用例 + CLI 端到端冒烟 | |
| tests/unit/test_defect_fixes.py 引用已删枚举（CALLING/BEFORE_REQUEST 别名） | 迁移到中立名（INVOKING/PREPARE/EXTRACTING） | print 式块 pytest 不执行故未暴露,`pytest tests/` 全目录收集时一并验证 |
| engine.py 处理器历史别名（_handle_calling 等） | 删除（残留 #1 收尾） | |
| Scope.SESSION≈SUITE 命名地雷 | 枚举改名 SUITE（值 "suite"）；utils 映射同步；存量 "session" 字面量迁移 | 对话评审发现,原清单未列 |
| events/types.py docstring 引用已删 HookPoint.STEP_START | 更新为 S-3 二分表述 | |
| HookTriggerer 死代码 | 删除（无消费者） | |
| observability/ 空目录树 | 本地清理（git 已无跟踪文件） | fusion 批次删了 .py 但留了目录 |
| tests/integration/test_server_run.py 用旧 api 糖 | 迁移 call 形态（`pytest tests/` 收集期 422 的根因） | 不在 testpaths,此前未跑到 |

补充轮验证：`pytest tests/`（全目录）1042 passed、`pytest -q`（testpaths）1019 passed。
