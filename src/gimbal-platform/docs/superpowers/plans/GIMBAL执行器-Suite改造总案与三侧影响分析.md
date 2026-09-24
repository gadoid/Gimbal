# GIMBAL 执行器 / Suite 改造总案与三侧影响分析

> 日期:2026-09-24
> 依据:《GIMBAL执行器-suite-策略设计定稿与变更清单》(2026-09-24 定稿)及其多轮评审、技术可行性分析、降本裁定与平台/Plate 影响分析。
> 地位:本文件为实施批次的基准文件;与定稿冲突处以本文件为准。
> 代码事实核对基线:本文所有"现状"描述均经代码核对(文件:行号见各节)。

---

## 〇、范围与总原则

**本次改造的实质**:在一条几乎不动的引擎旁边,建一个 suite 子系统,并把五份契约提前定形。

三条总原则:

1. **引擎本体零改造**:ScenarioRunner、状态机、策略执行器全程不动;现有单场景 `run launch` 路径是全程零回归护栏。
2. **编译期摊平**:复杂度全部压进编译期(纯函数、最可测),运行期只剩拓扑调度与注入。
3. **三侧解耦交付**:gimbal 各批次经 CLI 验证即可交付;plate 只做 additive 小改;平台靠兼容措施在前五批次零改动,批次 6 一次性切换。

---

## 一、定案的架构决策(15 条)

| # | 决策 | 要点 |
|---|---|---|
| 1 | **编译期摊平** | suite 四阶段(编译→执行→后置→判定);五种模式 desugar 到 compose,一张执行图、一个调度器、一个注入点 |
| 2 | **suite 只声明不实现** | 单元 = scenario,走现有 ScenarioRunner(D-02) |
| 3 | **配置叠加五层→生效副本** | 源→suite 补丁→单元补丁→调用参数→生效副本;执行器只读副本,副本即快照 |
| 4 | **输入输出用静态分析** | 否决 Extract.export 声明(X-03);输出 = extract 目标,输入 = assign/模板引用中未内部产出者;Assign 的 `_resolve_source_value` 运行期通道是既有机制不是缺口 |
| 5 | **调试 = 一个 debugger 插件** | 否决 breakpoint/inspect 策略化;策略 none/every_step/on_failure + 断点地址表;会话命令 read/write/continue/step/abort;引擎只留三个让步(B3 干预 hook、超时挂起旗标、强制串行) |
| 6 | **多线程 = 单元级线程池,一进程一 run** | 六个共享点加锁;事件总线已是线程设施(`bus.py` threading + ThreadPoolExecutor,已验证无 asyncio 冲突) |
| 7 | **否决检查点续跑**(X-04) | 失败暂停 + 查询注入 + retry 在同一次执行内修正;保留 step_from + 手动输入注入 |
| 8 | **否决造数复用**(X-05) | 运行内 shared 去重即复用;跨执行缓存不做 |
| 9 | **否决 origin 字段**(X-02) | 生效副本结构性分离;来源由编译产物 + 事件记录 |
| 10 | **调用协议中立化现在定形、不做执行器** | gimbal 侧 `step.call` union + `api` 永久合法糖 + 编译归一化 + `_do_call` 分派缝;plate 侧 EndpointSpec 加 `protocol` 判别字段;存量用例/规格迁移量恒为零 |
| 11 | **日志两流分工** | 事件 = 契约流(版本化、粗粒度);op-log = 诊断流(结构化、可订阅、best-effort);基于现有 log/ 子系统(JsonSink 已在)补三件 |
| 12 | **事件传输双通道(带平台兼容模式)** | v1:事件写独立工件文件 events.ndjson,stdout 保持只输出终态结果 JSON;server 模式 SSE;v2(批次 6):平台切换消费 |
| 13 | **状态机不做结构性重构** | 受限回退(C6)用"整步重跑 + poll 从 scratch 自发重发"替代 |
| 14 | **平台推送物化** | suite 引用的场景由平台调 plate /convert 物化后整体交执行器;执行器不反向调用平台/plate;plate 的消费方、凭证链、memo/熔断机制全部不变 |
| 15 | **执行器进程形态建议 server-per-execution**(批次 6 拍板) | 取消、SSE、调试会话统一走 HTTP 通道;顺带解决 Windows 下杀子进程泄漏的老问题 |

---

## 二、执行器侧变更点(九域)

### A. 契约与事件

- **E1 事件结构**:版本号 + 总序号(总线锁内分配)+ run/suite/unit/step 四级标识;分类目录六类(lifecycle / call-evidence / strategy-result / debug-session / metrics / audit,后两类预留);调用证据信封带 `protocol` 字段(协议中立);**大小上限 + 字段脱敏为硬约束**(token 不入证据流)。
- **E2 行协议(分层)**:v1 = 事件文件模式(events.ndjson 工件 + stdout 终态 JSON 不变,平台零感知);Windows 子进程逐事件 flush;server SSE(id=序号、Last-Event-ID 续传、心跳)。v2 = 平台切换事件消费。
- **E3 事件日志落盘**:复用 json reporter 的 event_timeline 模式;支持重放与外部导入(E6 入口)。

### B. 数据流与静态分析

- **A3 分析器(全项目唯一"错了不报错"的点)**:输入面必须覆盖三形态——`${name}` 模板、`$.path`(含 STEP-scope 下 SCENARIO 层回退,`utils.py:67-79`)、裸名 scratch 查找;三形态覆盖写成验收标准;断言的 `read_variable(SCENARIO)` 旁路(`assertion.py:43-46`)收窄;同名冲突 → 编译错误 + `map` 改名。
- **统一输入注入原语(一处三用)**:suite 连线注入、step_from 输入注入、resolve --unit 导出,共用"单元启动时注入为 scenario vars"。
- Scope 枚举 `SESSION≈SUITE`(`utils.py:12`)改名或删除,趁动 schema 一并做;删除死代码 `context/resolver.py` SpecResolver(无引用,warning→None 静默隐患)。
- (可选后置)请求体运行期模板 = 编译糖,desugar 成自动插入的 Assign 条目。

### C. suite 子系统(全新建设)

- **A1 Suite schema**:别名池(同一引用多别名)、mode、policy、control、ConfigPatch、checks;待确认字段裁定——
  - `schemaVersion`:采纳;
  - 池条目 `{ref, data?, config?, repeat?, skip?, lock?}`:采纳,但 **repeat(编译展开)× n_runs(运行重复)× policy.retry(重试)三种乘法的组合语义与计划清单计数必须成文**;
  - **suite before/after 一等公民化**:runner 级前后括号、全模式可用,不 desugar(生命周期括号与 body 拓扑正交;aggregate+全局前置是最高频用法);
  - policy 补 timeout / unit_timeout / retry:采纳;自动重试与人工 retry(B3)分开,"经修复后通过"标记仅人工路径;
  - lock 互斥标签:采纳,配调度器 v2;
  - 未知字段严格报错:采纳。
- **四个规格洞的裁定**:
  1. shared 去重身份 = `key`;同 key 的依赖条目要求生效定义完全一致,不一致即编译错误;
  2. 连线物化 = 单元启动时注入为其 scenario vars(即统一输入注入原语);
  3. control = `only` + 传递依赖闭包(make 语义)为主;from_node/to_node 仅对 chain(线性)定义;
  4. shared 依赖 teardown = 后置阶段统一逆序(v1,确定性);last-use 引用计数清理后置。
- **D1** 四阶段运行器(取代 `Engine._run_suite`,`runner.py:266-361`);
- **D2 编译器**:引用加载(v1 = 平台推送物化,不做反向拉取)、五层补丁流水线 + 合并代数成文、模式 desugar、数据/repeat/注入变体展开 + **计划清单上限闸**、循环检测、连线绑定、计划清单与执行图;
- **D3 dry-run 校验**:输入满足、users 标签存在、参数 schema、并发尾部写 suite 层同名变量;
- **D4 模式驱动**:aggregate 先行;compose / fanout / chain;matrix 以后;
- **D5 调度器**:v1 拓扑串行 + shared 去重 + control 解析;v2 单元级线程池(锁标签在"依赖满足、即将运行"时获取,防死锁);
- **D6 判定**:failure / error / blocked / 经修复后通过 区分;计划清单对账;gates/metrics 延后;
- **D7** suite 生命周期 hook(改图的 hook 仅编译期);
- **D8 收缩版配置规范**:合并规则文档 + 生效副本 diff(不做参数登记表与值来源追踪);
- **D9** 检索器 v1 = 路径 + --where 直接字段;
- 单元标识稳定命名(别名 + 展开序号)= 事件 / 清单 / 平台台账三方 join 锚点;
- 三套清理机制分界规则成文:teardown = 单元内资源(登录/容器)、after 依赖单元 = 业务清理(取消单据)、suite before/after = 全局一次。

### D. 调试(独立批次)

- **debugger 插件**(决策 5):断点地址 = hook 点(STEP_START / HTTP_BEFORE_SEND / HTTP_AFTER_RECV / STRATEGY_BEFORE + 策略名匹配);阻塞发生在 hook 处理器内(引擎线程阻塞、to_thread 下事件循环存活,已验证 `server.py:122`);hook 覆盖不足时补 STEP_END 与生命周期插槽点。
- **B3 STEP_FAILED 干预 hook**:从事件升级为可裁决 hook,返回 retry / skip / abort;**retry = 整步重跑**(ScenarioRunner 再调 `step_runner.run(idx)`,从 PENDING 走全流程);重跑路径的 extract→promote 开幂等覆盖。
- **poll 自发重发**:从 scratch 取 `request_method/url/headers/body`(`call.py:42-45` 已写入)自行重发,不碰状态机。
- **超时挂起旗标**(调试档位挂起 scenario 超时 `scenario_runner.py:340` 与策略 timeout);**强制串行**。
- **server 会话鉴权是硬前置**:现状 `auth="none"` 且 token 模式未实现(`server.py:150-152` 裸跑);改值是特权面。
- 平台调试走 server 会话,不做子进程 stdin;调试槽与执行队列分离。
- CLI 终端 v1 只做极简提示(回车继续 / q 退出,`input()` 级成本);完整 REPL 后置。

### E. 多线程(独立小批,suite 串行版稳定后)

六个共享点:

| 共享点 | 动作 |
|---|---|
| 事件总线 | publish/subscribe/unsubscribe 加锁;序号在同一把锁内分配(保序) |
| Archive | 加锁 + **键空间化 (unit_id, step_id)**——并行单元都有 step_1,裸 step_id 会互相覆盖,纯加锁解决不了 |
| SUITE 层 promote | 锁罩住"不可覆盖检查 + 写入"复合操作 |
| hook 双语义 | 干预型内联 + 每插件串行;观察型排队复用现有 BATCH 单 daemon 线程派发(`bus.py:189`) |
| 认证 | 预认证(运行开始,天然串行)+ 按标签单飞刷新 + CallExecutor 401→重认证→重试一次 |
| 插件 | 现有 4 个插件(auth_headers / collector / response_body_extract / test_report)线程就绪审计 + 插件作者规则成文 |

加:日志行带单元标识;httpx.Client 按线程复用(线程安全,性能项);**并发测试基建单列工作项**(竞态注入/压力,是此项最易漏估的成本)。

### F. 调用协议中立化(并入批次 1,只定形不建楼)

- **gimbal**:`step.call: {protocol, …}` union + `api` 永久合法糖(校验规则:恰好其一)+ **编译归一化**(api → call{protocol:"http"});`_do_http_call` → `_do_call` 三段式(识别 protocol → 合成 spec → 注册表分发);CallExecutor 挂帅 http 协议执行器(注册表第一员)。
- **兼容性论证**:既有断言目标(`$.response_body…`)、scratch 键、hook 名(HTTP_BEFORE_SEND/AFTER_RECV)、现有插件全部不动——这些是 http 协议自己的证据形状与钩子;新协议来时各自命名空间,互不侵犯。
- 不做:sql/ssh 执行器、资源层、非 HTTP 路由(阶段 7;sql 的真实卡点是数据源资源类型,不是分派缝)。

### G. 日志结构化订阅(并入 E1/E2 工作项)

- 三轴分级:severity(已有)× **category**(lifecycle/resolution/auth/call/strategy/scheduler/plugin/audit,与 E1 目录对齐命名;模块名→分类静态映射表起步,调用点零强制改造)× **scope**(run/unit/step,contextvar,引擎只改 run/单元/step/调用四处边界;线程模型下每单元线程各自 context,天然隔离)。
- `SubscribingSink`(进程内按 category+severity+unit 过滤分发)+ E2 日志通道(平台 engine.log 升级结构化 NDJSON,过渡期文本+NDJSON 双写)。
- 两流判断规则:**结果性信息(值得进报告/台账)→ 事件;过程性叙述(为什么、怎么走的)→ op-log**;模糊时宁进 op-log(升级成事件有版本成本,反向没有)。
- `observability/` 空壳处置:删除,或标记与 SubscribingSink 合并再议。

### H. CLI

- 复活 run scenario / run suite(2026-09-21 随资产仓库删除,git 历史有骨架);run launch 按 kind 分派;run show 保留;run match 移除(X-15,被 --where 覆盖)。
- 填空壳:compile / validate / resolve(含 --unit 导出单元为独立可调 scenario)。
- `ext list --json`(name + params_schema 导出,供平台 G2 生成表单)。
- server 收窄:调试会话端点 + 单 run;舰队参数(workers/queue_size/register_to/heartbeat/metrics_port/pidfile)不激活。

### I. 平台侧(详见第四章)

### J. 清理与勘误

- 定稿现状备注勘误:poll/sql/sleep/chaos/composite 五策略**未注册**(`build_default_dispatcher`(`dispatcher.py:180-192`)只注册 Extract/Assign/Assertion/Call;五类除 builtin 目录外零引用;kind 不在 StrategyUnion,永不触发)——A5 实际工作 = 接线 + 开放 union + 占位改 ERROR。
- compiler / repository / scheduler 空壳随对应项启用或删除(repository 由 D2 引用加载器隐性复活,应点名);launch `--fail-fast` no-op(`run_launch.py:221` 注释掉的注入)随 CLI 重定义处理。

---

## 三、Plate 侧影响与变更方案

| # | 影响 | 方案 | 批次 |
|---|---|---|---|
| P1 | EndpointSpec 加 `protocol` 判别字段 | additive,默认 "http";exporter/query_views 消费处摆 by-protocol 分派纪律;semver minor bump;跑 tests/plate 基线验证 | 1 |
| P2 | gimbal `call` union 落地 | plate 的 step 镜像 schema **保持 HTTP-only**(composer 只产 http;归一化在 gimbal 内部;convert 继续输出 `api` 糖,两写法在 gimbal 侧均合法) | 1(仅决定) |
| P3 | gimbal A2 LifecycleEntry | plate 的 setup.py/teardown.py 镜像类同步 + convert 透传;composer 无此 UI,零前端影响 | 1 |
| P4 | A5 开放策略条目 | plate strategy 镜像暂不开放(UI 不产则校验不遇);执行器侧 schema 已兼容 | 延后 |
| P5 | suite schema | 过渡期归 gimbal schema;后迁 plate 另议 | 延后 |
| P6 | io_spec carry 面 vs suite 注入 | 不动;两个注入来源(平台 carry 配方 / suite 连线)在 D-04 调用参数层汇合,写一句对齐说明 | — |

**明确不动**:io_spec 字段目录、field_states 三镜像(protocol 字段不触发镜像税)、状态码响应索引(`responses: dict[int, ResponseSpec]` 是 http 自己的形状)、/convert API 形状、generators 代理、部署形态(:8765 常驻)。
**凭证链不动的原因**:平台推送物化(决策 14)保住了 plate 的现有角色——执行器不调 plate,平台照旧调。
**固定税提醒**:plate schema 后续任何改动都要查 field_states 三处镜像清单(plate schema / platform validate / resolve_state)。

---

## 四、平台侧影响与变更方案

### 4.1 兼容措施(批次 1-5 平台零改动的保障)

1. **E2 v1 事件文件模式**:stdout 保持只输出终态结果 JSON(现状 `gimbal_launcher.parse_run_result` 整体解析不破),事件流写 events.ndjson 工件;
2. **日志双写**:文本 engine.log 保留(平台继续抓 stderr),NDJSON 并行落盘,批次 6 后切。

### 4.2 按批次的平台动作

| 批次 | 平台需要做的 | 平台可以不动的 |
|---|---|---|
| 1-4 | **无** | 执行链、解析、台账全部现状 |
| 5 | 可选提前:G1 调试页后端/前端独立开发 | 老执行链照常 |
| 6 | **重写批**(见 4.3) | — |

### 4.3 批次 6 重写明细

**执行链(run_dispatcher)**:

- 数据集 × 注入 × nRuns 笛卡尔逐行循环 → 收窄为"构造调用参数(单用例)或 suite 物化包(多用例)交执行器";rep 循环随 nRuns 下沉消失;
- 执行器进程形态:server-per-execution(决策 15)——取消、SSE、调试会话统一 HTTP 通道,删除协作式取消注册表与 Windows 杀进程泄漏问题;
- PG 队列(FOR UPDATE SKIP LOCKED)替换进程内 `_in_flight / _cancel_requested / _row_states` 三套内存注册表;重启从"标记 failed"升级为"可恢复";多 worker 解禁;
- 事件消费从终态 stdout JSON 切到 events.ndjson 尾读或 SSE;行状态从平台写库改为执行器事件投影。

**台账(E5,迁移 0007+)**:

- `execution_rows` → 单元行:新增 unit_id(别名+展开序号,与执行器编译清单同一命名)、branch 维度(1 前置 + N 子项);dataset/injection/row_index/rep 保留为单元属性,rep 由执行器事件喂;
- batch_id 保留(前端独立多选仍是合法用法,独立批次 ≠ suite);
- 运行级 JSONL 生命周期日志由事件投影替代(届时决定去留);
- 报告工件模式(result.json/engine.log 白名单端点)先保留,E6 事件投影另立后置。

**RunScheme(G3)**:stepTo/nRuns/parallel 收窄为"单用例调用参数"透传;dataSetSelection/serviceBindings/injectionEntryIds 维持平台组装语义;字段词表与执行器 A6 调用参数结构对齐(进规格冻结页)。

**前端**:

- Runner.vue:方案面板 → 调用参数面板;新增 suite 入口(场景库多选→组 suite),保留"多条独立执行"老用法;
- Executions.vue:行级 → 单元级展示(嵌套 1 前置 + N 子项);1s 轮询换 SSE;
- G1 调试页:SSE 会话流 + 命令面板(继续/单步/改值),平台代理执行器 server 会话并传递鉴权令牌;
- G2 suite 配置页:由 `ext list --json` 的 params_schema 生成表单;compose 图编辑组件后置(文本 YAML 过渡)。

**取消**:POST 执行器取消端点(会话通道复用);执行器进程崩溃 = PG 队列可见,worker reconcile。

### 4.4 过渡与灰度策略

1. **特性开关**:新旧执行链并存,按执行粒度切换;灰度顺序:CLI → 平台单用例新链 → 平台 suite;
2. **回滚**:老路径保留至新链稳定运行约定周期;
3. **验收**:同场景新旧链执行结果对账(单元状态、计数、耗时)一致才过门。

### 4.5 安全与凭证链

- 凭证链零变化(推送物化红利):平台 Fernet 解密 → 物化注入 → 交付执行器,suite 新路与单用例老路同构;case.json 明文现状与工件保护策略延续;
- E1 证据:脱敏与大小上限在执行器侧出口做;平台存储沿用 case.json 同级保护;
- 调试会话:平台↔执行器 server 令牌由平台按执行持有与轮转,前端不接触。

---

## 五、否决与排除清单(范围控制)

| 类别 | 项 |
|---|---|
| 定稿已否决 | 检查点续跑 / --resume / goto;造数复用 / cached(ttl);策略 origin 字段;Extract.export;run_scenario 策略与 requires 字段;多角色专用策略;反向幂等专用策略;race 独立模式;suite 嵌套与 suite 输出;suite 级调试;调试作为组织模式;--pause-on-failure 参数;执行模式层;run match;检索条件池条目 |
| 本轮加砍 | 状态机受限回退(→整步重跑 + poll 自发);统一扩展注册大一统(→描述与校验约定);参数登记表 + 值来源追踪(→合并规则 + 生效副本 diff);server 舰队管理(→调试会话端点);breakpoint/inspect 策略(→debugger 插件);StepResolver 请求体运行期重解析(Assign 通道已在);CLI 全功能 REPL(→极简提示先行);gates/metrics(延后) |
| 延后 | matrix/pairwise;barrier 同步起跑;请求体模板编译糖;依赖按能力反推 |
| 阶段 7 | sql/shell 执行器;资源/句柄层(ResourceManager 全空壳,greenfield;E7 安全闸——平台默认关 shell、命令白名单、审计事件、参数转义——与资源层同批硬前置) |

---

## 六、实施计划

### 6.1 开工门槛(先于一切代码)

1. **规格冻结一页纸**:suite 四洞裁定 + 五字段裁定 + repeat×n_runs×retry 乘法语义 + RunScheme/调用参数字段词表对齐;
2. **三份小设计**:①hook 干预/观察双语义(阻塞批次 4/5 的前置);②A3 分析器三形态覆盖标准(阻塞 suite 连线正确性);③stdout 行协议与结果信封区分(阻塞 E2/G4 接缝);
3. **特征化测试先行**:assign 通道取值流、extract promote、halt_at、per-step service 路由——给引擎系安全绳。

### 6.2 三侧批次表

| 批次 | gimbal 执行器 | plate | 平台 | 验收门 |
|---|---|---|---|---|
| 1 基础结构 | 协议中立化两半、A2/A3/A5 接线、B1/B2、C1/C2 注入原语、E1+分类目录、日志三件套、E2 v1(事件文件模式)、清理项 | protocol 字段 + 分派纪律 + 镜像同步 | 零改动 | `run launch` 零回归 + plate 测试基线全绿 |
| 2 suite 骨架 | A1、D1、D2(无依赖展开)、D3、D4 aggregate、D6 基础、D9、CLI 复活、E2 事件文件 | — | 零改动 | aggregate suite CLI 端到端 |
| 3 编排 | compose/fanout/chain、依赖展开、D5 v1、D7、合并代数、ext list | — | 零改动 | 三模式端到端 + 连线正确性(三形态测试) |
| 4 并发小批 | 六锁点 + 键空间化 + hook 双语义落地 + C7 + 并发测试基建 | — | 零改动 | parallel 真跑 + 竞态测试通过 |
| 5 调试 | debugger 插件、B3、C3 step_from、server 会话+鉴权、E3 | — | 可选:G1 独立开发 | 平台(或 server)单步调试一个运行中场景 |
| 6 平台切换 | 稳定收尾 | — | **重写批**:新执行链 + PG 队列 + 单元台账(0007)+ 前端三页 + E2 v2 + 灰度开关 | 新旧链对账一致 + 灰度切换 |
| 7 以后 | 按需:matrix、poll/sql、资源层+协议执行器、依赖反推 | 届时 endpoint union | 届时配套 | — |

**全程护栏**:现有单场景路径零回归;平台双轨解耦互不阻塞。

---

## 七、风险登记册(按杀伤力排序)

1. **A3 静态分析闭包**——错了不报错、静默错绑;测试投入最重;
2. **hook 双语义**——阻塞批次 4/5 的前置设计;debugger 插件是其第一个正式消费者;
3. **stdout/事件协议接缝**——规范先行,平台兼容模式(v1 事件文件)保障;
4. **补丁代数含糊**——五层叠加合并规则必须成文,否则直接变 bug;
5. **Archive 键空间化**——易被当"加锁了事"漏掉键冲突修复;
6. **E1 证据体积与脱敏**——存储与安全双负债,出口约束硬执行;
7. **调试通道鉴权**——改值是特权面,server token 是硬前置;
8. **token 401 刷新窗口**——并发期真实竞态,需 401→重认证→重试一次;
9. **平台切换窗口**——特性开关 + 新旧链对账 + 可回滚三件套控制;
10. **范围回弹**——"以后再议"项(matrix/barrier/environments 等)不得回流进当前批次。

---

## 八、摘要

**本次改造的实质**:在一条几乎不动的引擎旁边,建一个 suite 子系统,并把五份契约(事件、输入注入、调用协议、日志两流、调用参数)提前定形。

- **核心工程**:suite 编译器/运行器/调度器(全新代码,编译期摊平,运行期只是拓扑循环);地基四件——事件结构(序号+分类+协议信封)、静态分析(三形态闭包)、生命周期插槽、统一输入注入原语(一处三用:suite 连线 / step_from / 单元导出)。
- **提前定形**:调用协议中立化(gimbal `call` union + plate `protocol` 字段,只定形状不建执行器,存量迁移恒为零);日志两流分工(契约事件 + 可订阅诊断流,基于现有 log/ 子系统补三件:分类轴、contextvar 绑定、订阅 sink)。
- **大幅收缩**:调试收敛为一个插件(引擎仅三个小让步);多线程收缩为六个加锁点(引擎零改造);砍掉检查点续跑、跨执行缓存、大一统注册、参数登记表、状态机回退、server 舰队管理等低性价比实现。
- **三侧分工**:plate 只做一个字段加一条分派纪律(批次 1,凭证物化链不动);平台前五批次靠"E2 事件文件模式 + 日志双写"两个兼容措施做到零改动,批次 6 一次性完成执行链重写(server-per-execution + PG 队列)、台账单元化(0007)、前端三页,以特性开关灰度、新旧链对账验收、可回滚控制风险。
- **交付纪律**:六个批次各自独立验收,现有 `run launch` 全程零回归作护栏;开工前三份小设计 + 规格冻结一页纸 + 特征化测试先行。
- **残余风险**集中在三处——静态分析正确性、hook 双语义、事件协议接缝——均为"不定会返工",无"造不出"。
