# GIMBAL 执行器 / suite / 策略 设计定稿与变更清单（2026-09-24）

> 本文件为执行器、suite、策略相关讨论的汇总与权威版本；取代 execution-capabilities.md 中与 suite / plan / fixture 相关的条目。命令行细节见 run-commands.md。

---

## 一、设计原则

1. **能力落点**：声明在 scenario / suite / 调用参数；实现在执行器 / 策略。suite 只声明、不实现。
2. **业务与测试活动分离**：业务过程在 step 与策略里；流程组织在 suite 与执行器；作用域用上下文（固定四层，不加深）；特殊能力用策略。
3. **单元只定义一次，层级只加绑定信息**；差异用组合，不用继承。
4. **结构只承载，语义由注册的实现解释**：模式、策略、插件均为 name + params_schema + 实现，按名字分派；新增能力 = 注册，不改结构。
5. **三层同构**：suite 阶段 / scenario 生命周期阶段 / step 阶段，各自阶段固定、处理器注册。
6. **平台与 CLI 只是入口**，不各自实现执行逻辑；平台按注册 schema 渲染表单，执行图由执行器 compile 返回。
7. **调试只在 scenario 级**：suite 建立在 scenario 已能正常执行之上，不为 suite 的各种模式适配调试。
8. **并发只在执行单元级**：scenario 内的 step 保持线性。

---

## 二、已定决策

### 采纳
| # | 决策 |
|---|---|
| D-01 | 用例之间的依赖只在 suite 里声明，由 suite 生命周期调度；scenario 内不引用其他 scenario |
| D-02 | 单独执行 scenario 直接走 ScenarioRunner，不经过 suite、不拉起跨用例依赖；suite 在 ScenarioRunner 之上组合 |
| D-03 | suite 执行四阶段：编译 → 执行 → 后置 → 判定 / 报告 |
| D-04 | 配置叠加：源 scenario → suite 补丁 → 单元补丁 → 调用参数 → 生效 scenario；执行器只读生效副本，副本作为快照保存 |
| D-05 | 输入输出由静态分析得出：输出 = scenario 作用域的 extract 目标；输入 = assign / 模板引用中未在内部产出的变量（config.vars 有默认值的为可选）；多个依赖产出同名变量时编译报错，用 map 改名 |
| D-06 | scenario 的 setup / teardown 只放运行时策略（LifecycleEntry：kind + key + scope + params）；teardown 一定执行、逆序、与同 key setup 成对 |
| D-07 | 依赖 scope 只有 per_scenario / shared（一次执行只跑一次，调度去重） |
| D-08 | 模式：aggregate（默认）、compose（通用依赖图）、fanout、chain；matrix 以后按需。fanout / chain / matrix 是简写模式，展开成 compose 依赖，复用同一套执行图与调度 |
| D-09 | 并发竞争 = fanout + parallel；同步起跑（barrier）以后作为 fanout 选项 |
| D-10 | 调试：breakpoint（简单暂停）+ inspect（结构化命令）两个策略，共用会话通道；调试档位（--debug）默认装载失败暂停插件；单步由调试档位实现 |
| D-11 | 失败暂停做成插件 pause_on_failure，挂在 teardown 前的 step 失败 hook，返回 retry / skip / abort；"经修复后通过"由引擎标记，不计入正常通过率 |
| D-12 | 调试只在 scenario 级；run suite 不支持调试参数；suite 问题用 compile / resolve / dry-run 排查，运行期问题用 resolve --unit 取出单元转 scenario 调试 |
| D-13 | 执行器单元级多线程：线程池 = parallel，默认 1；一个进程同一时间只跑一个 run；上下文无需并发改造；处理 token（预认证 + 单飞刷新）与事件 / Archive 线程安全；reporter / 插件单线程分发 |
| D-14 | 命令行分立：run scenario / run suite（路径 + --where 双模式）/ run launch（按 kind 分派）/ run server；ID 通过 --where scenarioId=… 执行 |
| D-15 | 检索器第一版只做直接字段 |
| D-16 | 执行控制分类：策略类（n_runs / retry / parallel / fail_fast）只对 scenario 从命令行生效，suite 用自身 policy；环境类 / 输出类对两者生效 |
| D-17 | 多角色：users 标签表示角色并统一命名，由补丁或平台凭证池绑定账号；dry-run 校验标签存在；运行中产生的账号用普通登录 step |
| D-18 | 事件对外输出：子进程模式 stdout 逐行 JSON；server 模式 SSE（id=序号、Last-Event-ID 续传、心跳）；平台调试走 server 会话，不走子进程 stdin |
| D-19 | 横切 check = 选择器 + 标准策略，仅限测试活动类（断言、耗时、采集） |
| D-20 | 策略体系：核心 extract / assign / assertion 保持强类型；其余用开放扩展条目 {kind, params, phase…}，kind 须注册；占位执行器实现前返回 ERROR |

### 否决 / 移出
| # | 事项 | 原因 / 替代 |
|---|---|---|
| X-01 | run_scenario 策略、scenario 上的 requires 字段 | 用例依赖统一由 suite 声明与调度 |
| X-02 | 策略 origin 字段 | 注入只发生在生效副本，来源由编译产物与事件记录 |
| X-03 | Extract.export 字段 | 静态分析推导输入输出 |
| X-04 | 检查点续跑 / --resume / goto 策略 | 业务单据唯一且有状态，跨执行续跑不可靠；由 inspect 与失败暂停在同一次执行内修正 |
| X-05 | 造数复用 / cached(ttl) scope / --no-cache | 交易类前置会被消耗；主数据走常量池 / vars / 配置补丁 |
| X-06 | 多角色专用策略 | users 标签 + ${auth.<标签>.token} 已支持 |
| X-07 | 反向与幂等专用策略 | 断言错误码 / 复制 step / fanout 并发重复提交 |
| X-08 | 探索式转用例专用功能 | 由 Agent 通过 inspect + 事件完成，产物须评审入库 |
| X-09 | race 独立模式 | fanout + parallel（+ 以后的 barrier） |
| X-10 | suite 调试（suite 级断点 / inspect / 步骤区间） | 适配成本高；调试只在 scenario 级 |
| X-11 | 调试作为组织模式 | 调试与组织正交，做成调试档位 |
| X-12 | --pause-on-failure 命令参数 | 改为插件 |
| X-13 | suite 嵌套、suite 输出 | 保持四层上下文 |
| X-14 | 执行模式层 | 由 mode 字段 + 模式驱动注册表达 |
| X-15 | run match | 被 run scenario --where 覆盖，去掉或仅作别名 |

---

## 三、能力清单（最终处理方式）
| 能力 | 处理方式 | 落点 | 阶段 |
|---|---|---|---|
| 单次执行 | run scenario 直接走 ScenarioRunner | 执行器 | 已有（命令分立在阶段 2） |
| 数据驱动 | 编译阶段按数据集行展开单元并计入计划清单 | 执行器 | 已有 / 阶段 2 |
| 重复与并发 | n_runs、retry、parallel 下沉执行器；单元级线程池 | 调度器 | 阶段 3–4 |
| 断言注入变体 | 已有；编译阶段与数据集行并列展开 | 策略 + 编译 | 已有 |
| 区间执行 | step_from 生效 + 输入注入；仅 scenario | 执行器 | 阶段 5 |
| 断点调试 | 调试档位 + breakpoint / inspect + 失败暂停插件；仅 scenario | 策略 + 运行时 + 插件 | 阶段 5 |
| 用例拼接 | chain 模式 | suite + 执行器 | 阶段 3 |
| 1:N 前置扇出 | fanout 模式 | suite + 执行器 | 阶段 3 |
| 多级前置树 | compose 显式声明；按能力反推以后作为编译能力 | suite + 执行器 | 阶段 3 / 以后 |
| 组合覆盖 | matrix 模式 | 模式驱动 | 以后 |
| 并发竞争 | fanout + parallel；barrier 以后 | suite + 调度器 | 阶段 4 |
| 反向与幂等 | 断言 / 复制 step / fanout | scenario + suite | 已具备 |
| suite 批量执行 | 四阶段 | suite + 执行器 | 阶段 2–3 |

---

## 四、suite 结构

```
Suite
  kind: suite
  suiteId
  meta: Meta                          # 复用 scenario 的 Meta
  scenarios: {别名: 引用}               # 同一引用可有多个别名
  mode: aggregate | compose | fanout | chain | (matrix)
  params: {...}                       # 由模式驱动注册的 schema 校验
  policy:  parallel / fail_fast / serial_only
  control: only / from_node / to_node   # 单元选择，非调试
  config:  ConfigPatch                # setup / teardown / services / users / vars / retry / timePolicy
  checks:  [ {on: Selector, strategy} ]
  plugins / metrics: [ {name, params} ]
  gates:   [ {metric, op, value} ]
```

模式参数：
- aggregate：order?
- compose：bindings [ {target, before[], after[], config?} ] + entry；依赖条目 {ref, key, scope, map?}
- fanout：setup, targets[], scope?, barrier?（以后）
- chain：chain[]
- matrix（以后）：setups[], tails[], combine: full | zip | pairwise

### 待确认的字段补充（2026-09-24 提出，待 Codfish 评估）
1. schemaVersion：结构版本号，支撑演进与迁移
2. 用例池条目扩展为 {ref, data?, config?, repeat?, skip?, lock?}（简写仍可只写引用）；compose 的 binding 只保留依赖关系，单元设置移到池条目
3. suite 级 before / after：只执行一次的全局前置与清理（aggregate 模式也可用），条目格式复用依赖条目，语义固定为 shared
4. policy 补 timeout（总时限）、unit_timeout（单元时限）、retry（单元重试）
5. lock 互斥标签：带相同标签的单元不并发
- 以后再议：environments（按环境补丁）、expect_fail、池条目用检索条件
- 建议 Suite 严格校验：未知字段报错

---

## 五、变更清单

### A. schema（过渡期放 gimbal schema，后迁 plate）
- A1 Suite 重构（见第四节）；去掉嵌入式 list[Scenario]
- A2 Scenario.config.setup / teardown 改为 LifecycleEntry 列表，取代 Setup / Teardown 占位类
- A3 输入输出静态分析：extract（scenario 作用域）/ assign / 模板引用 / config.vars
- A4 新策略：breakpoint、inspect；补全占位：sleep、poll，按需 sql（先加数据源资源类型）；以后 shell / 句柄
- A5 开放扩展策略条目 {kind, params, phase…}；占位执行器实现前返回 ERROR
- A6 调用参数结构（取代 RuntimeControl）；调试会话命令结构（schema/debug.py）
- A7 各模式参数 schema：aggregate / compose / fanout / chain

### B. 执行器：扩展机制
- B1 统一扩展注册：name + params_schema + 列举接口（策略 / 模式 / 插件 / reporter / 会话命令）
- B2 策略注册声明默认阶段与适用位置（step / 生命周期插槽 / suite 横切）
- B3 STEP_FAILED 改为 teardown 前触发的可干预 hook，支持返回 retry / skip / abort，由引擎执行并标记

### C. 执行器：scenario 层
- C1 生命周期：setup 插槽 → steps → teardown 插槽
- C2 输入注入 / 输出收集
- C3 step_from 生效（区间执行）
- C4 调试档位：会话通道（CLI 终端 / server 接口、等待、超时、事件记录）、pause（none / on_failure / every_step）、breakpoint / inspect 命令处理器、默认装载 pause_on_failure、强制串行
- C6 状态机受限回退（poll 重发本步请求）
- C7 认证：执行前预认证执行图引用的 users 标签；运行中 token 刷新按标签单飞

### D. 执行器：suite 层（填 suite/、scheduler/ 空壳）
- D1 suite 阶段运行器（suite/manager.py），取代 Engine._run_suite
- D2 编译：引用加载器（路径 / 目录检索 / 平台接口）、配置补丁流水线、模式展开为依赖图（递归、循环检测、shared 去重、输出 → 输入连线、同名冲突检测）、数据集与注入变体展开、control 解析、生成执行图
- D3 dry-run 校验（覆盖、引用、循环、输入满足、users 标签存在、参数 schema、约束、并发尾部写 suite 层同名变量）+ 计划清单
- D4 模式驱动：aggregate、compose、fanout、chain；matrix 以后
- D5 调度器：第一版拓扑串行 + shared 去重 + after 用例时机 + only / from_node / to_node；第二版单元级线程池 + n_runs / retry；barrier 以后
- D6 结果与判定：failure / error / blocked / 经修复后通过 区分；计划清单对账；基础统计 + metrics；gates；checks 注入
- D7 suite 生命周期 event / hook 点，插件按阶段注册；改图的 hook 只能在编译期
- D8 配置规范：参数登记表（级别、合并方式、允许来源、作用范围）+ 值来源追踪
- D9 检索器（suite/selector.py）：路径 + --where 直接字段
- D10 并发基础设施：事件发布加锁 + 序号原子递增 + 单元标识；Archive 加锁；reporter / 插件单线程分发；日志带单元标识

### E. 事件与 SSE
- E1 事件结构版本化：run / suite / unit / step 标识 + 序号；inspect 命令、渲染后请求、响应完整记录
- E2 输出适配：stdout 逐行 JSON / server SSE
- E3 事件日志保存，支持 Last-Event-ID 续传

### F. CLI（详见 run-commands.md）
- F1 run scenario（普通 / 调试）、run suite（无调试）、run launch、run show；run match 去掉或作别名
- F2 run server：POST /runs、状态、SSE、取消、scenario 调试会话接口
- F3 填空壳：compile、validate、resolve（含 --unit）
- F4 新增 ext list --json

### G. 平台
- G1 scenario 执行页：普通执行 / 调试执行（指定步骤暂停、单步），调试走 server 会话（SSE + POST 命令）
- G2 suite 表 + 按模式的配置页（由 params_schema 生成表单，compose 可用图编辑组件）+ 执行图预览（compile）+ 失败单元跳转 scenario 调试
- G3 RunScheme 对应单用例执行的调用参数；多用例组合走 suite
- G4 执行链：一次执行一个执行器进程 + PG 队列；转发事件为 SSE；台账增加单元层级；nRuns / parallel 下沉后平台只填参数

---

## 六、现状备注（代码核对）
- strategy/builtin 已注册 poll、sql、sleep、chaos、composite，均为占位实现，当前直接返回 PASSED；assign / call / extract / assertion 已实现（call 每次新建 httpx.Client）。
- schema/strategy.py 的 StrategyUnion 只含 Extract / Assign / Assertion（封闭联合）。
- suite/、scheduler/、resource/ 为空壳；Suite schema 为嵌入式 list[Scenario]；Setup / Teardown 为只有 kind 的占位类；Resource 只有 Mock / File。
- CLI 已注册 run launch / match / server / show、self-check，已有 -P / --plugins；run scenario / run suite 已于 2026-09-21 随资产仓库删除；compile_case.py / resolve.py / validate.py 为空壳；--step-from 仅警告，--breakpoint 仅停止。
- core/hooks.py 已有 HookPoint.STEP_FAILED，但引擎只作为事件发出；HookResult 只支持 stop / modify。
- core/server.py 注明引擎设施按单 run 设计并串行执行；执行链为同步代码。
- ${auth.<tag>.token} 在 preprocessor 阶段一次性解析；运行时刷新待确认。
- 已有 preprocessor/scenario_preprocessor.py 与 step → scenario → suite 的 channels 提升机制（suite 层要求 reason、不可覆盖）。

---

## 七、实施顺序
1. 基础结构：A5（含占位改 ERROR）、A2、A3、B1、B2、C1、C2、E1
2. suite 骨架：A1、D1、D2（不含依赖展开）、D3、D4（aggregate）、D6 基础、D9、F1、F3、E2
3. 编排：A7、D4（compose / fanout / chain）、D2 依赖展开、D5 第一版、D7、D8、F4
4. 并发：C7、D10、D5 第二版
5. scenario 调试与运行控制：A6、A4（breakpoint、inspect、sleep、poll）、B3、C3、C4、C6、F2、E3
6. 平台接入：G1–G4
7. 以后：matrix、barrier、依赖反推、sql / shell / 句柄、第四节"以后再议"字段
