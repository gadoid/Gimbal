# Gimbal 项目已实现需求清单

> 本文档基于对 `d:\Gimbal\Gimbal\` 项目源码、文档、测试、变更方案的逆向分析整理而成（截至 2026-06-18）。
> 整理方法：阅读 README、架构文档、`docs/` 全部模块文档、`change/` 中的设计定稿（PathRegistry / ModelRegistry v2/v3）、`src/gimbal/**` 实现代码、`tests/**` 单测/集成/e2e、`plugins/collector/` 实际插件、`examples/` 与 `gimbal-tmp/` 真实场景样本，反向推导已落地的需求点。

---

## 0. 项目定位

Gimbal 是一个 **面向现代 API 测试场景的自动化测试框架**（Python 3.11+），核心定位：

- 把"**场景编排 / 策略执行 / 状态机驱动 / 资产复用 / 插件扩展**"装进同一条 CLI 链路。
- 提供**仿 Docker Registry v2 的本地资产仓库**，便于跨项目复用稳定的 Suite / Scenario 资产。
- 服务于 **PHP → Java 迁移对账**（已落地的 `gimbal-tmp/test2.json` 等结算单对账场景样本），目标场景是货运/结算类业务系统的接口与数据一致性验证。

---

## 1. 已实现的需求（按层次组织）

### 1.1 命令行入口（CLI）

| # | 需求 | 落地点 |
|---|---|---|
| R-CLI-01 | 统一 CLI 入口 `gimbal`（基于 Typer） | [cli/main.py:71-86](src/gimbal/cli/main.py) |
| R-CLI-02 | `gimbal run suite <REF>` 按 ID 执行 Suite 资产，支持命名空间通配 | [cli/commands/run_suite.py](src/gimbal/cli/commands/run_suite.py) |
| R-CLI-03 | `gimbal run scenario <REF>...` 按 ID 执行 Scenario 资产，支持通配 | [cli/commands/run_scenario.py](src/gimbal/cli/commands/run_scenario.py) |
| R-CLI-04 | `gimbal run match <GLOB>` 按路径/模式匹配本地未注册用例文件 | [cli/commands/run_match.py](src/gimbal/cli/commands/run_match.py) |
| R-CLI-05 | `gimbal run server` 作为服务监听端口接收任务（http/grpc/websocket） | [cli/commands/run_server.py](src/gimbal/cli/commands/run_server.py) |
| R-CLI-06 | `gimbal run launch <PATH>` 直接加载本地文件执行 | [cli/commands/run_launch.py](src/gimbal/cli/commands/run_launch.py) |
| R-CLI-07 | `gimbal asset` 资产仓库管理（push/pull/list/inspect/remove/tag/gc） | [cli/commands/asset.py](src/gimbal/cli/commands/asset.py) |
| R-CLI-08 | `gimbal self-check` 框架自检（集成测试级：bootstrap + 验证 event/hook 回路） | [cli/commands/self_check.py](src/gimbal/cli/commands/self_check.py) |
| R-CLI-09 | 共享执行选项：`--env/--mode/--log-level/--tag/--var/--var-file/--parallel/--timeout/--retry/--dry-run/--fail-fast/--plugins/--reporter/--report-dir/--output/--source/--registry/--version/--no-cache/--cache-only/--order/--continue-on-error/--yes/--allow-empty` | [cli/params.py](src/gimbal/cli/params.py) |
| R-CLI-10 | 步骤级断点控制：`--step-from/--step-to/--breakpoint` | [cli/commands/run_scenario.py](src/gimbal/cli/commands/run_scenario.py) |
| R-CLI-11 | 匹配模式选项：`--path/--recursive/--include/--exclude/--changed-only/--changed-since/--last-failed/--last-failed-first/--collect-only/--shuffle/--seed` | [cli/commands/run_match.py](src/gimbal/cli/commands/run_match.py) |
| R-CLI-12 | 统一退出码规范（0/1/2/3/4/5） | [cli/exit_codes.py](src/gimbal/cli/exit_codes.py) |
| R-CLI-13 | SIGINT 优雅中断（首次标记取消、二次强退） | [cli/main.py:27-41](src/gimbal/cli/main.py) |
| R-CLI-14 | `gimbal run launch` 支持 inline JSON / stdin 接收 | [cli/commands/run_launch.py:152-244](src/gimbal/cli/commands/run_launch.py) |

### 1.2 启动与配置（Bootstrap）

| # | 需求 | 落地点 |
|---|---|---|
| R-BS-01 | 框架启动唯一入口 `bootstrap(cli_ctx)` | [core/bootstrap.py:52-153](src/gimbal/core/bootstrap.py) |
| R-BS-02 | 多来源配置合并：CLI > env 变量 > mode > env > gimbal.yaml > 默认值 | [config/loader.py](src/gimbal/config/loader.py) |
| R-BS-03 | 不可变 `Configuration`（frozen dataclass） | [core/bootstrap.py:16-46](src/gimbal/core/bootstrap.py) |
| R-BS-04 | 基础设施一次性初始化（EventBus / Archive / ContextManager / Dispatcher / HookRegistry / PluginRegistry / AuthRegistry） | [core/bootstrap.py:81-102](src/gimbal/core/bootstrap.py) |
| R-BS-05 | 框架关闭入口 `shutdown()`（幂等） | [core/bootstrap.py:210-267](src/gimbal/core/bootstrap.py) |
| R-BS-06 | `RunMetaEvent` 在 run 前发布（CI provider / build URL / commit / 触发人） | [cli/commands/run.py](src/gimbal/cli/commands/run.py) |
| R-BS-07 | `framework_config.yaml` + `conf/environments/{dev,prod}.yaml` 多环境配置 | [conf/](conf/) |

### 1.3 数据模型（Schema，Pydantic v2）

| # | 需求 | 落地点 |
|---|---|---|
| R-SC-01 | 顶层模型：`Scenario` / `Suite` / `RunUnion`（多态） | [schema/scenario.py](src/gimbal/schema/scenario.py) |
| R-SC-02 | 用例元信息 `Meta`（name/description/module/priority/author/owner/tags/version/createTime/expire/requirementRef） | [schema/scenario.py:13-25](src/gimbal/schema/scenario.py) |
| R-SC-03 | 用例配置 `Config`（setup/teardown/services/users/timePolicy/retry/vars） | [schema/scenario.py:27-39](src/gimbal/schema/scenario.py) |
| R-SC-04 | 资源模型 `Resource` / `Mock` / `File`（含 MockRef/FileRef） | [schema/resource.py](src/gimbal/schema/resource.py) |
| R-SC-05 | `Api` 模型（service/method/path/headers/timeout） | [schema/api.py:5-11](src/gimbal/schema/api.py) |
| R-SC-06 | `Request` 模型（body） | [schema/request.py:5-7](src/gimbal/schema/request.py) |
| R-SC-07 | `Step` 模型（api / request / strategy 列表） | [schema/step.py:9-14](src/gimbal/schema/step.py) |
| R-SC-08 | Discriminated Union：`StepUnion` / `ApiUnion` / `RequestUnion` / `StrategyUnion` | 各 schema 模块 |
| R-SC-09 | 策略基类 `StrategyBase`（name/phase/order/enabled/onFailure/timeout/tags） | [schema/strategy.py:43-51](src/gimbal/schema/strategy.py) |
| R-SC-10 | 三种核心策略：`Extract` / `Assign` / `Assertion` | [schema/strategy.py:53-75](src/gimbal/schema/strategy.py) |
| R-SC-11 | 策略阶段枚举 `StrategyPhase`（BEFORE_REQUEST / AFTER_REQUEST / VERIFYING / TEARDOWN） | [schema/strategy.py:31-35](src/gimbal/schema/strategy.py) |
| R-SC-12 | 失败处理枚举 `FailurePolicy`（ABORT / CONTINUE / WARN / RETRY） | [schema/strategy.py:37-41](src/gimbal/schema/strategy.py) |
| R-SC-13 | 断言操作符 `AssertOperator`（EQ/NE/GT/GTE/LT/LTE/IN/NOT_IN/CONTAINS/NOT_CONTAINS/EXISTS/EMPTY/LENGTH_EQ/SCHEMA） | [schema/strategy.py:13-29](src/gimbal/schema/strategy.py) |
| R-SC-14 | `RetryPolicy`（maxAttempts/backoffSeconds/retryOn） | [schema/retrypolicy.py:5-10](src/gimbal/schema/retrypolicy.py) |
| R-SC-15 | `TimePolicy`（TimeoutPolicy / RecordPolicy） | [schema/timepolicy.py:4-19](src/gimbal/schema/timepolicy.py) |
| R-SC-16 | 引用基类 `RefBase` + 通用 `Ref`（`{"kind":"ref","ref":"..."}` 内联引用） | [schema/ref.py:37-74](src/gimbal/schema/ref.py) |
| R-SC-17 | 类型化引用 `StepRef` / `ApiRef` / `RequestRef` / `StrategyRef` / `ScenarioRef` / `SuiteRef` | 各 schema 模块 |
| R-SC-18 | `Setup` / `Teardown` 模型 | [schema/setup.py](src/gimbal/schema/setup.py) / [schema/teardown.py](src/gimbal/schema/teardown.py) |
| R-SC-19 | `AuthSession` 认证会话（含 token 刷新安全校验 CWE-93 防护） | [schema/auth.py:25-198](src/gimbal/schema/auth.py) |
| R-SC-20 | `StepState` 状态枚举 | [schema/states.py](src/gimbal/schema/states.py) |

### 1.4 执行上下文（Context）

| # | 需求 | 落地点 |
|---|---|---|
| R-CTX-01 | 4 层上下文：`FrameworkContext` → `SuiteContext` → `ScenarioContext` → `StepContext` | [context/](src/gimbal/context/) |
| R-CTX-02 | 层级枚举 `ContextLayer`（FRAMEWORK > SUITE > SCENARIO > STEP） | [context/base.py:10-24](src/gimbal/context/base.py) |
| R-CTX-03 | Sealed 机制（执行完毕后封印，防意外修改） | [context/base.py:27-75](src/gimbal/context/base.py) |
| R-CTX-04 | 每次 `Engine.run()` 独立创建上下文（run_id 唯一） | [context/framework.py](src/gimbal/context/framework.py) |
| R-CTX-05 | 单向 `parent` 引用 + 跨层 `run_id/suite_id` 委托 | 各 context 模块 |
| R-CTX-06 | 三通道 `Channels`（variables / metadata / artifacts） | [context/channels.py:96-336](src/gimbal/context/channels.py) |
| R-CTX-07 | 变量提升策略（`Policies.scenario_default/suite_default/framework_locked`） | [context/channels.py:64-90](src/gimbal/context/channels.py) |
| R-CTX-08 | 提升策略校验：来源层、黑名单 key、白名单前缀、是否覆盖、是否强制 reason | [context/channels.py:267-323](src/gimbal/context/channels.py) |
| R-CTX-09 | `ContextManager` 协调 4 层生命周期 | [context/manager.py:19-186](src/gimbal/context/manager.py) |
| R-CTX-10 | 上下文视图 `Views` / 投影 `Projections` / 函数 `Functions` | [context/views.py](src/gimbal/context/views.py) |
| R-CTX-11 | 模板解析（变量在 Pydantic @property 上的支持） | [context/template.py](src/gimbal/context/template.py) |

### 1.5 状态机驱动（Step 执行）

| # | 需求 | 落地点 |
|---|---|---|
| R-SM-01 | Step 状态机 `StepStateMachine` | [statemachine/engine.py:94-...](src/gimbal/statemachine/engine.py) |
| R-SM-02 | 9 个状态：`PENDING/BEFORE_REQUEST/CALLING/AFTER_REQUEST/VERIFYING/TEARDOWN/PASSED/FAILED/ERROR/SKIPPED` | [statemachine/states.py:11-28](src/gimbal/statemachine/states.py) |
| R-SM-03 | 合法跃迁表 `VALID_TRANSITIONS` 保护非法跳转 | [statemachine/states.py:56-94](src/gimbal/statemachine/states.py) |
| R-SM-04 | 5 个阶段 handler（before_request/calling/after_request/verifying/teardown） | [statemachine/engine.py:213-322](src/gimbal/statemachine/engine.py) |
| R-SM-05 | Teardown 失败不污染业务结果（`error_phase` 标记） | [statemachine/engine.py:283-322](src/gimbal/statemachine/engine.py) |
| R-SM-06 | HTTP 拼装 + `HTTP_BEFORE_SEND` / `HTTP_AFTER_RECV` hook 介入点 | [statemachine/engine.py:345-430](src/gimbal/statemachine/engine.py) |
| R-SM-07 | 场景级协作式超时（每 step 前检查 elapsed） | [core/scenario_runner.py:279-294](src/gimbal/core/scenario_runner.py) |
| R-SM-08 | ScenarioRunner.run() 编排：preprocessor + 逐步执行 + 事件发布 | [core/scenario_runner.py:143-409](src/gimbal/core/scenario_runner.py) |

### 1.6 策略系统（Strategy）

| # | 需求 | 落地点 |
|---|---|---|
| R-ST-01 | `StrategyExecutor` 抽象基类（execute 不抛异常，包成 ERROR 返回） | [strategy/executor_base.py:87-103](src/gimbal/strategy/executor_base.py) |
| R-ST-02 | `StrategyDispatcher` 集中分发（disabled 跳过、STRATEGY_BEFORE/AFTER 埋点、计时、软失败标记） | [strategy/dispatcher.py:51-138](src/gimbal/strategy/dispatcher.py) |
| R-ST-03 | 按 `phase` 过滤 + `order` 排序 + 硬失败 break | [strategy/dispatcher.py:140-177](src/gimbal/strategy/dispatcher.py) |
| R-ST-04 | `build_default_dispatcher()` 一次性注册 4 个内置 executor | [strategy/dispatcher.py:180-191](src/gimbal/strategy/dispatcher.py) |
| R-ST-05 | `CallExecutor`（实际 HTTP 调用，`httpx.Client`） | [strategy/builtin/call.py:12-100](src/gimbal/strategy/builtin/call.py) |
| R-ST-06 | `ExtractExecutor`（JSONPath 取值 + scope） | [strategy/builtin/extract.py:18-85](src/gimbal/strategy/builtin/extract.py) |
| R-ST-07 | `AssignExecutor`（变量赋值，支持字面量 / `${var}` / `$.jsonpath`） | [strategy/builtin/assign.py:12-63](src/gimbal/strategy/builtin/assign.py) |
| R-ST-08 | `AssertionExecutor`（按 operator 比较） | [strategy/builtin/assertion.py:14-73](src/gimbal/strategy/builtin/assertion.py) |
| R-ST-09 | `SleepExecutor`（`time.sleep`） | [strategy/builtin/sleep.py:19-44](src/gimbal/strategy/builtin/sleep.py) |
| R-ST-10 | `ChaosExecutor`（占位，预留混沌工程集成） | [strategy/builtin/chaos.py](src/gimbal/strategy/builtin/chaos.py) |
| R-ST-11 | `PollExecutor`（占位，预留条件轮询） | [strategy/builtin/poll.py](src/gimbal/strategy/builtin/poll.py) |
| R-ST-12 | `SqlExecutor`（占位，预留数据库执行） | [strategy/builtin/sql.py](src/gimbal/strategy/builtin/sql.py) |
| R-ST-13 | `CompositeExecutor`（占位，预留子策略聚合） | [strategy/builtin/composite.py](src/gimbal/strategy/builtin/composite.py) |

### 1.7 资产仓库（Repository，仿 Docker Registry v2）

| # | 需求 | 落地点 |
|---|---|---|
| R-REP-01 | 仿 OCI 不可变内容寻址存储（CAS）模型 | [repository/models.py](src/gimbal/repository/models.py) |
| R-REP-02 | `AssetRef` 双重形式：`namespace/name:tag` 或 `namespace/name@digest` | [repository/models.py:36-144](src/gimbal/repository/models.py) |
| R-REP-03 | `AssetRecord` / `AssetContent` 不可变数据模型 | [repository/models.py:150-207](src/gimbal/repository/models.py) |
| R-REP-04 | `ContentStore` Protocol（push_blob/pull_blob/has_blob/put_manifest/...） | [repository/store.py:44-90](src/gimbal/repository/store.py) |
| R-REP-05 | `AssetStore` 门面：push/pull/inspect/list/remove/tag | [repository/store.py:98-267](src/gimbal/repository/store.py) |
| R-REP-06 | sha256 摘要 + digest 校验 + 不可变 + 幂等 push | [repository/store.py](src/gimbal/repository/store.py) |
| R-REP-07 | 多 tag 共享同一 digest | [repository/store.py:250-267](src/gimbal/repository/store.py) |
| R-REP-08 | `LocalFsContentStore` 本地文件系统后端 | [repository/backends/filesystem.py:40-352](src/gimbal/repository/backends/filesystem.py) |
| R-REP-09 | FS 三段式目录布局：`blobs/sha256/...` + `indexes/...` + `manifests/...` | [repository/backends/filesystem.py:62-81](src/gimbal/repository/backends/filesystem.py) |
| R-REP-10 | 原子写（`tempfile + os.replace`，先 close 再 replace，Windows 兼容） | [repository/backends/filesystem.py:95-117](src/gimbal/repository/backends/filesystem.py) |
| R-REP-11 | 孤儿 blob 检测 + 手动 `gc` 清理 | [repository/backends/filesystem.py:313-352](src/gimbal/repository/backends/filesystem.py) |
| R-REP-12 | `AssetResolver`（CLI ID 解析 + 通配展开 + 拉取） | [core/asset_resolver.py](src/gimbal/core/asset_resolver.py) |
| R-REP-13 | `AssetMaterializer`（图内嵌 Ref 节点递归替换，固定点算法） | [core/asset_materializer.py](src/gimbal/core/asset_materializer.py) |
| R-REP-14 | 类型化 Ref → TypeAdapter 映射（StepRef/ApiRef/RequestRef/StrategyRef/ScenarioRef/SuiteRef） | [core/asset_materializer.py:47-75](src/gimbal/core/asset_materializer.py) |
| R-REP-15 | 循环保护 + 深度兜底（默认 max_depth=8） | [core/asset_materializer.py:245-301](src/gimbal/core/asset_materializer.py) |
| R-REP-16 | Asset 异常体系：`AssetNotFound` / `AssetDigestMismatch` / `AssetAlreadyExists` | [repository/exceptions.py](src/gimbal/repository/exceptions.py) |

### 1.8 插件系统（Plugins）

| # | 需求 | 落地点 |
|---|---|---|
| R-PL-01 | 插件发现：`plugins_dir/*/plugin.yaml` + pip entry point (`gimbal.plugins` group) | [plugins/loader.py:103-155](src/gimbal/plugins/loader.py) |
| R-PL-02 | 5 阶段流水线：discover → resolve_deps → load_all → activate_all → deactivate_all | [plugins/loader.py:8-15](src/gimbal/plugins/loader.py) |
| R-PL-03 | 拓扑依赖排序 + 循环依赖检测 | [plugins/loader.py:158-188](src/gimbal/plugins/loader.py) |
| R-PL-04 | 单插件 import / activate 失败被隔离 | [plugins/loader.py:191-204](src/gimbal/plugins/loader.py) |
| R-PL-05 | `sys.path` 临时插入 + LIFO 撤销（不留痕，修复 sys.path 泄漏） | [plugins/loader.py:216-233](src/gimbal/plugins/loader.py) |
| R-PL-06 | `Plugin` 抽象基类 + 生命周期状态机 | [core/plugin.py:152-257](src/gimbal/core/plugin.py) |
| R-PL-07 | `PluginContext`（event_bus / hook_registry / plugin_registry 句柄 + register_event/hook 便利方法） | [core/plugin.py:76-147](src/gimbal/core/plugin.py) |
| R-PL-08 | name-based 精确热卸载（event_bus / hook_registry / registry 全部按 name 清理） | [plugins/loader.py:324-387](src/gimbal/plugins/loader.py) |
| R-PL-09 | `DeactivateReport` 报告（succeeded / failed 列表） | [plugins/loader.py:40-60](src/gimbal/plugins/loader.py) |
| R-PL-10 | 插件类别枚举 `PluginCategory`（9 种） | [plugins/categories.py:13-35](src/gimbal/plugins/categories.py) |
| R-PL-11 | `PluginSpec`（运行时描述符）/ `PluginManifest`（静态声明）双层 | [plugins/spec.py](src/gimbal/plugins/spec.py) / [plugins/manifest.py](src/gimbal/plugins/manifest.py) |
| R-PL-12 | `PluginRegistry`（按 name 主索引 + category/capability 反向索引） | [plugins/registry.py:21-99](src/gimbal/plugins/registry.py) |
| R-PL-13 | `manifest` 文件解析（yaml / yml / toml） | [plugins/manifest.py:36-125](src/gimbal/plugins/manifest.py) |
| R-PL-14 | 实际示例插件：`plugins/collector/`（gimbal-collector） | [plugins/collector/](plugins/collector/) |

### 1.9 报告系统（Reporter）

| # | 需求 | 落地点 |
|---|---|---|
| R-RA-01 | `Reporter` Protocol（`name/begin/on_event/finalize`） | [reporter/protocol.py:58-89](src/gimbal/reporter/protocol.py) |
| R-RA-02 | `ReportArtifact` 数据类（name/path/content/media_type/metadata） | [reporter/base.py:28-68](src/gimbal/reporter/base.py) |
| R-RA-03 | `ReportContext`（framework_ctx/bus/config/report_dir/user_config/subscription_ids） | [reporter/protocol.py:22-53](src/gimbal/reporter/protocol.py) |
| R-RA-04 | `ReporterRegistry`（factory 形式注册，延迟实例化） | [reporter/registry.py:36-132](src/gimbal/reporter/registry.py) |
| R-RA-05 | `ReporterRuntime` 状态机：new → setup → ready → running → finalized → closed | [reporter/runtime.py:89-301](src/gimbal/reporter/runtime.py) |
| R-RA-06 | `is_async` 标志位，慢回调走 ASYNC 订阅避免阻塞 event pipeline | [reporter/base.py:97](src/gimbal/reporter/base.py) |
| R-RA-07 | `ConsoleReporter`（终端实时进度 + 终态高亮） | [reporter/builtin/console.py:35-198](src/gimbal/reporter/builtin/console.py) |
| R-RA-08 | `JsonReporter`（终结型，落盘 JSON，含可选 event_timeline） | [reporter/builtin/json_reporter.py:13-96](src/gimbal/reporter/builtin/json_reporter.py) |
| R-RA-09 | `JunitReporter`（CI 集成：Jenkins/GitLab/GitHub Actions） | [reporter/builtin/junit.py:13-96](src/gimbal/reporter/builtin/junit.py) |
| R-RA-10 | `AllureReporter`（Allure 2 JSON 协议） | [reporter/builtin/allure_reporter.py:25-...](src/gimbal/reporter/builtin/allure_reporter.py) |
| R-RA-11 | `HtmlReporter`（内嵌 CSS/JS 模板） | [reporter/builtin/html_reporter.py](src/gimbal/reporter/builtin/html_reporter.py) |
| R-RA-12 | `ImNotifierReporter`（钉钉/Slack/飞书 webhook 推送） | [reporter/builtin/im_notifier.py:12-127](src/gimbal/reporter/builtin/im_notifier.py) |
| R-RA-13 | `PlatformUploaderReporter`（上传 artifact 到内部平台，含 base64 + 200KB 限制 + 指数退避重试） | [reporter/builtin/platform_uploader.py:12-144](src/gimbal/reporter/builtin/platform_uploader.py) |
| R-RA-14 | `ReportErrorLog` 错误累积 + 多阶段异常隔离 | [reporter/runtime.py:36-84](src/gimbal/reporter/runtime.py) |

### 1.10 事件系统（Events）

| # | 需求 | 落地点 |
|---|---|---|
| R-EV-01 | `InMemoryEventBus` 进程内事件总线 | [events/bus.py:22-201](src/gimbal/events/bus.py) |
| R-EV-02 | 三种订阅模式：`SYNC` / `ASYNC` / `BATCH` | [events/subscription.py:11-14](src/gimbal/events/subscription.py) |
| R-EV-03 | 订阅过滤：`EventFilter`（event_type / event_type_pattern / run_id / step_id / scenario_id / custom） | [events/subscription.py:20-49](src/gimbal/events/subscription.py) |
| R-EV-04 | 优先级 + plugin_name 精确清理 | [events/bus.py:48-125](src/gimbal/events/bus.py) |
| R-EV-05 | 22 种事件类型（FRAMEWORK_INIT/TEARDOWN、RUN_*、SUITE_*、SCENARIO_*、STEP_*、HTTP_*、VARIABLE_PROMOTED、PLUGIN_*） | [events/types.py:32-76](src/gimbal/events/types.py) |
| R-EV-06 | `FrameworkEvent` 基类（frozen） | [events/types.py:79-89](src/gimbal/events/types.py) |
| R-EV-07 | `EventBusProtocol` / `HookRegistryProtocol` runtime_checkable | [events/protocols.py](src/gimbal/events/protocols.py) |
| R-EV-08 | 线程池异步处理（默认 8 worker） | [events/bus.py:19](src/gimbal/events/bus.py) |
| R-EV-09 | 后台批处理线程 + start_batch_loop / stop | [events/bus.py:178-201](src/gimbal/events/bus.py) |

### 1.11 Hook 系统

| # | 需求 | 落地点 |
|---|---|---|
| R-HK-01 | `HookPoint` 枚举（14 种埋点，含 framework/run/suite/scenario/step/http/strategy 全部阶段） | [core/hooks.py:32-66](src/gimbal/core/hooks.py) |
| R-HK-02 | Hook 可介入主流程（`HookSignal.STOP` 中断） | [core/hooks.py:4-8](src/gimbal/core/hooks.py) |
| R-HK-03 | Hook 可改写 payload（dict in-place 修改或 return 新对象） | [core/hooks.py:211-256](src/gimbal/core/hooks.py) |
| R-HK-04 | `HookRegistry.register` 按 `(point, priority)` 升序排序 | [core/hooks.py:139-170](src/gimbal/core/hooks.py) |
| R-HK-05 | `HookRegistry.trigger` 异常被吞并记录到 `result.errors` | [core/hooks.py:211-256](src/gimbal/core/hooks.py) |
| R-HK-06 | `HookTriggerer` 轻量级 `fire()` 包装 | [core/hooks.py:265-284](src/gimbal/core/hooks.py) |

### 1.12 认证管理（Auth）

| # | 需求 | 落地点 |
|---|---|---|
| R-AU-01 | `Authenticator` 抽象基类 + URL pattern 装饰器注册 | [auth/authenticator.py:24-95](src/gimbal/auth/authenticator.py) |
| R-AU-02 | `AuthManager` 统一入口（get/load_and_auth/_login/_refresh） | [auth/manager.py:21-166](src/gimbal/auth/manager.py) |
| R-AU-03 | `AuthRegistry` 容器（tag → AuthSession，__slots__ 防止扩展） | [auth/registry.py:24-85](src/gimbal/auth/registry.py) |
| R-AU-04 | `PreTokenAuthenticator`（password 直接当 token） | [auth/authenticators/pretoken.py:5-13](src/gimbal/auth/authenticators/pretoken.py) |
| R-AU-05 | `HTTPSAuthenticator` / `HTTPAuthenticator`（标准用户名密码登录） | [auth/authenticators/http_basic.py:6-47](src/gimbal/auth/authenticators/http_basic.py) |
| R-AU-06 | `GitHubAuthenticator`（OAuth access_token 申请） | [auth/authenticators/github.py:10-43](src/gimbal/auth/authenticators/github.py) |
| R-AU-07 | `WLAuthenticator`（内部业务系统 fin-tidb 登录） | [auth/authenticators/wl.py:13-64](src/gimbal/auth/authenticators/wl.py) |
| R-AU-08 | Token 提前 5 分钟刷新机制 | [schema/auth.py](src/gimbal/schema/auth.py) |
| R-AU-09 | refresh_token 刷新 + 失败回退到 _login | [auth/manager.py:120-165](src/gimbal/auth/manager.py) |

### 1.13 预处理器（Preprocessor）

| # | 需求 | 落地点 |
|---|---|---|
| R-PP-01 | `ScenarioPreprocessor.run()` 5 阶段编排 | [preprocessor/scenario_preprocessor.py:94-131](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-02 | Phase 0 引用物化（递归还原内层 Ref 节点） | [preprocessor/scenario_preprocessor.py:135-160](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-03 | Phase 1 认证（只登录被引用的 user，避免 25min 启动问题） | [preprocessor/scenario_preprocessor.py:164-228](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-04 | Phase 1.5 变量生成（合并 scenario_vars + cli_vars，CLI 胜） | [preprocessor/scenario_preprocessor.py:232-261](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-05 | Phase 2 构建查询根（services + auth.snapshot + vars） | [preprocessor/scenario_preprocessor.py:265-307](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-06 | Phase 3 批量展开 step 模板（保留 StepRef） | [preprocessor/scenario_preprocessor.py:311-337](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-07 | Phase 4 提取 base_url（按实际引用 service 解析） | [preprocessor/scenario_preprocessor.py:518-582](src/gimbal/preprocessor/scenario_preprocessor.py) |
| R-PP-08 | `find_template_var_refs` 扫描模板变量引用 | [utils/jsonpath.py:748-807](src/gimbal/utils/jsonpath.py) |

### 1.14 变量生成器（Generator）

| # | 需求 | 落地点 |
|---|---|---|
| R-GEN-01 | `Generator` 入口（按 kind 查 registry 调 func(**params)） | [generator/engine.py:20-47](src/gimbal/generator/engine.py) |
| R-GEN-02 | `GeneratorRegistry` + `build_default_registry()` | [generator/registry.py:10-42](src/gimbal/generator/registry.py) |
| R-GEN-03 | `VarSpec` 联合（discriminated）+ 7 个 Pydantic Spec | [generator/specs.py](src/gimbal/generator/specs.py) |
| R-GEN-04 | 内置函数：`uuid` / `random_str` / `random_int` / `random_decimal` / `timestamp` / `now` / `seq` | [generator/functions.py](src/gimbal/generator/functions.py) |
| R-GEN-05 | bootstrap 阶段注入 cfg | [core/bootstrap.py:137-140](src/gimbal/core/bootstrap.py) |

### 1.15 工具函数（Utils）

| # | 需求 | 落地点 |
|---|---|---|
| R-UT-01 | 零依赖 JSONPath 解析器（$.field / $[0] / $..field / $.items[?(...)]） | [utils/jsonpath.py](src/gimbal/utils/jsonpath.py) |
| R-UT-02 | JSONPath 5 个核心 API：get / get_all / set_value / delete / exists | [utils/jsonpath.py:514-598](src/gimbal/utils/jsonpath.py) |
| R-UT-03 | 模板变量解析 `${var.name}` | [utils/jsonpath.py:657-726](src/gimbal/utils/jsonpath.py) |
| R-UT-04 | `resolve_template_strict`（找不到时返回哨兵） | [utils/jsonpath.py:688-726](src/gimbal/utils/jsonpath.py) |
| R-UT-05 | `is_template` / `is_jsonpath` / `is_missing` 检测函数 | [utils/jsonpath.py:736-743](src/gimbal/utils/jsonpath.py) |
| R-UT-06 | `find_template_var_refs` 递归遍历 Pydantic 模型 | [utils/jsonpath.py:748-807](src/gimbal/utils/jsonpath.py) |
| R-UT-07 | 词法分析（9 种 Token）+ 语法分析 + 过滤求值 | [utils/jsonpath.py:76-340](src/gimbal/utils/jsonpath.py) |

### 1.16 日志系统（Log）

| # | 需求 | 落地点 |
|---|---|---|
| R-LG-01 | 基于 loguru 的统一日志 | [log/setup.py:17-66](src/gimbal/log/setup.py) |
| R-LG-02 | `LoggingConfig` Pydantic 配置（level / no_color / json_mode / show_path / log_file / rotation / retention / compression / diagnose / backtrace） | [log/config.py:22-119](src/gimbal/log/config.py) |
| R-LG-03 | 3 种 formatter：Color / Plain / Json（优先 orjson） | [log/formatters.py](src/gimbal/log/formatters.py) |
| R-LG-04 | 工厂函数 `make_console_sink` / `make_file_sink` | [log/formatters.py:180-264](src/gimbal/log/formatters.py) |
| R-LG-05 | `InterceptHandler`（stdlib logging → loguru 桥接） | [log/intercept.py:29-56](src/gimbal/log/intercept.py) |
| R-LG-06 | `bound_logger` / `log_context`（ContextVar 注入 run_id/scenario_id/step_id/suite_id） | [log/logger.py:77-131](src/gimbal/log/logger.py) |
| R-LG-07 | `setup_logging` 幂等 + 三方库静默（httpx/httpcore/urllib3/asyncio → WARNING） | [log/setup.py:82-85](src/gimbal/log/setup.py) |
| R-LG-08 | `configure_logging_from_bootstrap`（CI 环境无 tty 自动 json_mode） | [log/integration.py:50-101](src/gimbal/log/integration.py) |
| R-LG-09 | `configure_logging_from_cli`（bootstrap 前早期日志） | [log/integration.py:104-127](src/gimbal/log/integration.py) |
| R-LG-10 | NO_COLOR 环境变量自动检测 | [log/config.py](src/gimbal/log/config.py) |

### 1.17 Server 模式（核心服务骨架）

| # | 需求 | 落地点 |
|---|---|---|
| R-SV-01 | `ServerConfig` dataclass（host/port/workers/max_concurrent/queue_size/mode/auth/...） | [core/server.py:14-32](src/gimbal/core/server.py) |
| R-SV-02 | `start_server()` 入口骨架（占位实现，预留 http/grpc） | [core/server.py:34-55](src/gimbal/core/server.py) |
| R-SV-03 | 注册到调度中心（`register_to`）+ 心跳协程 | [core/server.py:14-32](src/gimbal/core/server.py) |
| R-SV-04 | 优雅关闭 `graceful_timeout` | [core/server.py:14-32](src/gimbal/core/server.py) |
| R-SV-05 | pidfile + health_port + metrics_port 支持 | [core/server.py:14-32](src/gimbal/core/server.py) |

### 1.18 异常体系

| # | 需求 | 落地点 |
|---|---|---|
| R-EX-01 | 全局基类 `GimbalError` | [exceptions.py](src/gimbal/exceptions.py) |
| R-EX-02 | 资产相关：`AssetNotFound` / `AssetDigestMismatch` / `AssetAlreadyExists` / `InvalidAssetRef` / `AssetCycleError` / `AssetMaterializationError` | [exceptions.py](src/gimbal/exceptions.py) + [repository/exceptions.py](src/gimbal/repository/exceptions.py) |
| R-EX-03 | 状态机：`InvalidTransitionError` | [statemachine/exceptions.py](src/gimbal/statemachine/exceptions.py) |
| R-EX-04 | 上下文：`SealedContextError` | [context/exceptions.py](src/gimbal/context/exceptions.py) |
| R-EX-05 | 认证：`AuthError` | [auth/exceptions.py](src/gimbal/auth/exceptions.py) |
| R-EX-06 | 生成器：`GeneratorError` / `UnknownGeneratorError` | [generator/exceptions.py](src/gimbal/generator/exceptions.py) |
| R-EX-07 | 资源：`ResourceError` | [resource/](src/gimbal/resource/) |
| R-EX-08 | AI：`AIError` | [ai/exceptions.py](src/gimbal/ai/exceptions.py) |
| R-EX-09 | 报告：`ReporterAlreadyRegistered` / `ReporterNotFound` | [reporter/registry.py:26-33](src/gimbal/reporter/registry.py) |

### 1.19 AI 辅助（占位骨架）

| # | 需求 | 落地点 |
|---|---|---|
| R-AI-01 | `AIAssistant` 抽象基类（占位） | [ai/assistant_base.py](src/gimbal/ai/assistant_base.py) |
| R-AI-02 | `Anthropic` provider（占位） | [ai/providers/anthropic.py](src/gimbal/ai/providers/anthropic.py) |
| R-AI-03 | Prompt 模板：`assemble` / `diagnose` / `generate_data`（占位） | [ai/prompts/](src/gimbal/ai/prompts/) |

### 1.20 模型契约（ModelRegistry，待实现但已设计定稿）

> 来源：[change/GIMBAL-ModelRegistry-变更方案-v3.md](change/GIMBAL-ModelRegistry-变更方案-v3.md)（**状态：设计定稿 · 待实现**）

| # | 需求（已设计） | 落地点 |
|---|---|---|
| R-MR-01 | 新建 `ModelRegistry` 模块（按 service 组织） | [src/ModelRegistry/](src/ModelRegistry/)（核心文件已就位，目录 `settlement/` 等未建） |
| R-MR-02 | `EndpointSpec` 数据类（含 method/path/request/responses/summary/tags/mock_hook） | [src/ModelRegistry/spec.py](src/ModelRegistry/spec.py) |
| R-MR-03 | `_Registry` 单例（collect / resolve / warm，含 threading.Lock） | [src/ModelRegistry/core.py](src/ModelRegistry/core.py) |
| R-MR-04 | `service 名 = 目录名 = import 路径` 约定 + `_aliases.py` 集中 alias 表 | [src/ModelRegistry/_aliases.py](src/ModelRegistry/_aliases.py) |
| R-MR-05 | 双场景复用：scenario 加载器（轻量，取数据类做字段检查）+ mock server（重量，取整个 spec 做路由/响应/hook） | 设计文档 §2 |
| R-MR-06 | 加载期 `extra="forbid"` + round-trip 无损自检 | 设计文档 §3.4 |
| R-MR-07 | 字段类型按 PHP 真实线格式（数字串保持 `str`） | 设计文档 §3.1 |
| R-MR-08 | 禁用 `exclude_none`，httpx 透传 null | 设计文档 §3.2 |
| R-MR-09 | `contract_validation.mode` 三态开关（off / warn / strict）平滑过渡 | 设计文档 §0 |
| R-MR-10 | response_model 同步建模（强烈建议） | 设计文档 §5.1 |
| R-MR-11 | schema 导出（JSON Schema / OpenAPI） | 设计文档 §5.2 |

### 1.21 业务场景样本（已落地）

| # | 需求 | 落地点 |
|---|---|---|
| R-BIZ-01 | 结算单对账场景：POST `/api/order/orderEntrust/orderAdd`（订舱/报关委托下单） | [gimbal-tmp/test2.json](gimbal-tmp/test2.json) |
| R-BIZ-02 | 海运订舱托书数据样本（含 agent/订单号/集装箱/订舱/报关供应商等结构） | [BookingNote/*.json](BookingNote/) |
| R-BIZ-03 | 登录认证场景（auth 注入 + token 提取 + 跨 step 复用） | 文档示例 / 单元测试 |
| R-BIZ-04 | e2e 完整流程（结算单详情查询 + 订舱/报关下单组合） | [gimbal-tmp/e2e.json](gimbal-tmp/e2e.json) |

### 1.22 测试与质量保障

| # | 需求 | 落地点 |
|---|---|---|
| R-QA-01 | 单元测试目录（按模块拆分：config / generator / reporter / scenario） | [tests/unit/](tests/unit/) |
| R-QA-02 | 集成测试（CLI run wiring、preprocessor vars、defect_6） | [tests/integration/](tests/integration/) |
| R-QA-03 | ModelRegistry 测试（aliases / concurrent_resolve / core / spec / zero_invasion） | [tests/model_registry/](tests/model_registry/) |
| R-QA-04 | e2e smoke 脚本（`bootstrap -> Engine.run -> artifacts`） | [_e2e_smoke.py](_e2e_smoke.py) |
| R-QA-05 | 缺陷修复单测矩阵（`test_defect_fixes.py` ~129KB，覆盖 B3/B6/B8/B9/B10 等历史缺陷） | [tests/unit/test_defect_fixes.py](tests/unit/test_defect_fixes.py) |
| R-QA-06 | 资产仓库 + AssetMaterializer + Plugin 集成测试 | [tests/unit/](tests/unit/) |
| R-QA-07 | 报告插件 collector 集成测试 | [tests/unit/test_collector_plugin.py](tests/unit/test_collector_plugin.py) |
| R-QA-08 | pre-commit 钩子（ruff format + ruff check + mypy + 标准 hooks） | [.pre-commit-config.yaml](.pre-commit-config.yaml) |
| R-QA-09 | ruff / mypy / pytest 工具链配置 | [pyproject.toml](pyproject.toml) |

### 1.23 文档体系

| # | 需求 | 落地点 |
|---|---|---|
| R-DOC-01 | 顶层 README（特性 + 快速开始 + CLI 树 + 架构） | [README.md](README.md) |
| R-DOC-02 | 架构概览（执行链路 + 模块职责 + Schema 模型 + Context 层次 + 状态机 + 策略分发） | [docs/architecture.md](docs/architecture.md) |
| R-DOC-03 | 23 个模块文档（每个模块 1 份） | [docs/modules/](docs/modules/) |
| R-DOC-04 | 扩展指南（9 类扩展点：策略 / 插件 / Reporter / Authenticator / ContentStore / StrategyPhase / ConfigLoader） | [docs/extending.md](docs/extending.md) |
| R-DOC-05 | 示例索引 + 常见用法 | [docs/examples.md](docs/examples.md) |
| R-DOC-06 | 插件开发指南（写插件 / 订阅事件） | [docs/plugins/](docs/plugins/) |
| R-DOC-07 | 设计定稿文档（变更方案 v1/v2/v3） | [change/](change/) |
| R-DOC-08 | Superpowers 设计与计划文档（scenario-vars-and-generator） | [docs/superpowers/](docs/superpowers/) |
| R-DOC-09 | Known Issues 登记（含优先级 P0/P1/P2 + 修复记录） | [docs/known-issues/](docs/known-issues/) |
| R-DOC-10 | Schema 速查表 | [docs/schema.md](docs/schema.md) |

---

## 2. 占位 / 待实现项（设计已定但代码未实装）

| # | 项 | 状态 | 说明 |
|---|---|---|---|
| R-WIP-01 | `chaos` strategy executor | 占位 | 注释明确 "TODO: 接入混沌工程平台（如 Chaos Mesh）" |
| R-WIP-02 | `poll` strategy executor | 占位 | "TODO: 实现轮询逻辑" |
| R-WIP-03 | `sql` strategy executor | 占位 | "TODO: 接入数据库执行" |
| R-WIP-04 | `composite` strategy executor | 占位 | "TODO: 实现子策略列表的顺序执行和结果聚合" |
| R-WIP-05 | `server.py` HTTP/gRPC/WebSocket 实际服务监听 | 骨架 | `start_server()` 仅打印 placeholder 日志；建议 FastAPI + uvicorn |
| R-WIP-06 | `repository/backends/mysql.py` | 占位 | 仅 docstring |
| R-WIP-07 | `repository/backends/python_module.py` | 占位 | 仅 docstring |
| R-WIP-08 | `repository/base.py`（AssetRepository ABC） | 占位 | 已被 `AssetStore + ContentStore Protocol` 取代（README 明确） |
| R-WIP-09 | `repository/router.py` | 占位 | 已被 AssetResolver 取代 |
| R-WIP-10 | `compiler/assembler.py` / `compiler.py` / `validators.py` | 占位 | 实际编译逻辑由 `core/asset_materializer` + `preprocessor` + `schema` 承担 |
| R-WIP-11 | `compiler/parsers/{yaml,markdown,text}.py` | 占位 | 当前 scenario 直接以 Pydantic 模型对象 + JSON/YAML 形式传入 |
| R-WIP-12 | `scheduler/{concurrency,dependency,retry,scheduler}.py` | 占位 | 当前并发由 Engine.run() 同步循环；重试由 RetryPolicy + state machine 兜底 |
| R-WIP-13 | `ai/{assistant_base,providers/anthropic,prompts/*}.py` | 占位 | 仅有 docstring |
| R-WIP-14 | `resource/{handle,manager,provider_base,providers/*}.py` | 占位 | 仅有 docstring；Resource 模型已在 schema 中定义 |
| R-WIP-15 | `suite/{environment,manager,plan,selector}.py` | 占位 | Suite 编排由 `core/runner.py` Engine.run(suite) 实现 |
| R-WIP-16 | `observability/{tracer,metrics,snapshot_recorder,logger,backends/*}.py` | 占位 | 仅有 docstring |
| R-WIP-17 | ModelRegistry 完整 `settlement/` 等业务目录 | 未建 | 仅有 core/spec/_aliases 3 个核心文件，业务目录未填充 |
| R-WIP-18 | `examples/{hello,login_and_query,suites,asset_library}/*` 实际示例文件 | 仅 .gitkeep | 实际示例未提交，README 文档假设存在 |

---

## 3. 已知遗留问题（已登记的 known-issues）

| # | 项 | 优先级 | 说明 |
|---|---|---|---|
| R-KN-01 | 模板变量替换机制遗留问题 | P0/P1/P2 | 见 [docs/known-issues/preprocessor/template-substitution.md](docs/known-issues/preprocessor/template-substitution.md) |
| R-KN-02 | gimbal-collector 报告插件局限 | P0/P1/P2 | 缺请求头详情、缺断言详情、无脱敏、单一格式；见 [docs/known-issues/plugins/collector/README.md](docs/known-issues/plugins/collector/README.md) |

---

## 4. 关键设计原则（已在代码中体现）

1. **Configuration 不可变**：BootstrapConfig / Configuration 是 frozen dataclass。
2. **数据单向流动**：低层 → 高层通过 `promote_from()` 受控提升。
3. **Seal 机制**：Context 执行完毕后封印。
4. **状态机驱动**：Step 执行由状态机控制。
5. **策略可扩展**：通过注册机制支持自定义策略。
6. **Frozen 产出**：bootstrap 产出的 Configuration 是 frozen 的。
7. **Event vs Hook 分离**：Event 通知型 fire-and-forget；Hook 介入型可中断/改写 payload。
8. **name-based 插件清理**：精确热卸载通过 name 字段全链路清理，不依赖订阅 id 列表。
9. **失败容错分层**：单 handler 异常不拖垮主流程。
10. **类型化 Ref + 通用 Ref 双形态**：类型化走 `TypeAdapter(Union).validate_python`；通用 Ref 直接塞回 `parsed`。
11. **固定点物化**：AssetMaterializer 递归至图中无 Ref 为止。
12. **协作式超时**：每 step 前检查 elapsed 时间。
13. **Teardown 软失败语义**：teardown 失败不污染业务结果。

---

## 5. 总结

Gimbal 是一个**功能完整、模块边界清晰、扩展点齐备**的 API 测试框架。截至 2026-06-18：

- **核心已实现**：CLI / Bootstrap / 4 层 Context / 状态机 / 9 个策略 executor / 仿 Docker 资产仓库 / 5 阶段插件流水线 / 7 个内置 Reporter / Event 三模式 / Hook 双侧同名埋点 / 5 种 Authenticator / 5 阶段 Preprocessor / 7 种变量生成器 / 零依赖 JSONPath / loguru 日志系统 / 23 个模块文档。
- **核心已设计定稿但未完全实装**：ModelRegistry（v3 方案，data class + EndpointSpec 双场景复用）、`run server` 实际服务监听、4 个 strategy executor（chaos/poll/sql/composite）、多个仓储后端。
- **核心已设计但完全占位**：AI 辅助、Scheduler、Resource、Suite 编排模块、Observability、Compiler parsers/assemblers。
- **核心业务落地**：海运订舱 / 报关 / 结算单对账（PHP→Java 迁移）已具备完整测试样本与场景定义。

项目整体处于 **"核心闭环可用 + 多处扩展点已规划"** 阶段，可作为现有 API 测试体系的核心框架使用。
