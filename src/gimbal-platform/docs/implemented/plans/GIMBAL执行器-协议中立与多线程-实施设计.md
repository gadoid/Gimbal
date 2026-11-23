# GIMBAL 执行器 — 协议中立化与多线程分派 实施设计

> 日期：2026-09-27
> 依据：《GIMBAL执行器-Suite改造总案与三侧影响分析》(2026-09-24) 批次 1（F 调用协议中立化）与批次 4（E 多线程六锁点）、决策 6/10/13。
> 地位：本文档是上述两块工作的**落地实施设计**（代码级），与总案冲突处以总案为准；总案未覆盖的实现细节以本文为准。
> 本轮目标（用户口径）：
> 1. 执行器归一化 —— 状态机、策略、插件注册从"只适配 HTTP 请求过程"调整为"支持多协议编排与流转"；
> 2. 多线程模型 —— 单进程串行执行重构为支持多线程、允许每个 scenario 分派执行；
> 3. 协议可注册，每种协议的请求体有对应数据结构定义；协议字段定义查询统一使用 JSONPath。

---

## 一、现状与耦合点（代码核对基线）

HTTP 耦合在五层：

| 层 | 位置 | 耦合事实 |
|---|---|---|
| Schema | `schema/step.py:12` | `Step.api: ApiUnion` 与 `request` 均为必填 —— 非 HTTP 步骤无法表达 |
| 状态机 | `statemachine/engine.py:380` `_do_http_call` | URL 拼装、service 路由、`_CallSpec` 合成全部内联在状态机 |
| 传输 | `strategy/builtin/call.py` `CallExecutor` | httpx 唯一传输；kind=`_call` |
| 钩子/事件 | `core/hooks.py:61` `HTTP_BEFORE_SEND/AFTER_RECV`；`events/types.py` `HttpRequestEvent/HttpResponseEvent` | 钩子/事件名是 HTTP 专属形状（`auth_headers`/`response_body_extract`/`collector` 三个插件依赖） |
| Scratch 约定 | `context/step.py:26` | `request_*` / `response_*` 键为 HTTP 证据形状（Extract/Assertion 的 JSONPath 依赖） |

多线程现状：`Engine._run_suite`（`core/runner.py:311`）是纯 for 循环；`scheduler/`、`suite/` 全是 1 行空壳；事件总线（`events/bus.py`）已有 threading 设施但 publish/subscribe 无锁；`InMemoryArchive` 无锁且 step 键会跨 scenario 互踩；`Channels.promote_from` 的"检查+写入"复合操作无锁；`HookRegistry.trigger` 无锁。

JSONPath 现状：`gimbal/utils/jsonpath.py`（零依赖自研）已是三侧唯一查询语言 —— gimbal Extract/Assertion/Assign、plate `DeclarationEntry.path`/`QueryView.items`/`ValueSource`、platform 镜像 `app/services/jsonpath.py`。本轮**维持 JSONPath 为唯一统一查询方法**，新协议的请求体字段声明继续用 JSONPath 寻址。

## 二、目标架构

### 2.1 调用协议中立化（gimbal 侧）

```
Step（schema）
  ├─ api:  Optional[Api]        # HTTP 语法糖，永久合法（存量用例零迁移）
  ├─ call: Optional[Call]       # 协议中立调用：{protocol: str, ...协议自有字段}
  └─ request: Optional[Request] # 请求体（body 结构由协议定义解释）
  校验：api 与 call 恰好其一；api 存在时编译归一化 → call{protocol:"http"}（api 字段保留）
```

- `Call` 是**开放模型**（`protocol: str` + `extra="allow"`）：协议字段由协议执行器自行解释校验，
  注册新协议不需要改 schema（满足"多种协议可注册、每种协议请求体有对应数据结构定义"）。
- 归一化在 `Step` 的 model_validator 内完成 —— 任何加载路径（CLI/平台/测试）拿到的 Step 恒有 `call`。

**协议执行器层**（新包 `gimbal/protocols/`）：

```
ProtocolExecutor(StrategyExecutor)          # 抽象基类
  protocol: str                             # 协议名（注册表键）
  kind = f"_call:{protocol}"                # dispatcher 注册键（http 特例 = "_call" 兼容）
  build_spec(call, pctx) -> spec            # 第一段：识别协议自有字段 → 合成传输 spec
  execute(spec, view) -> StrategyResult     # 第三段：真正传输（spec 内嵌埋点设施）

ProtocolRegistry                            # protocol → executor，线程安全
  register / resolve / unregister_plugin    # 插件注册与按插件批量注销
  绑定 dispatcher：注册时同步登记 dispatcher（kind 键）
```

**状态机三段式**（`_do_call` 取代 `_do_http_call`，后者保留为别名）：

1. 识别 protocol：`step.call.protocol` → `ProtocolRegistry.resolve`
2. 合成 spec：`executor.build_spec(call, pctx)`（URL 拼装/service 路由从状态机移入 http 执行器）
3. 注册表分发：`dispatcher.dispatch(spec, view)`（计时、STRATEGY_BEFORE/AFTER 钩子走既有插装）

**钩子/事件命名空间**（总案兼容性论证：新协议各自命名空间，互不侵犯）：

| 命名空间 | 钩子 | 事件 | 触发者 |
|---|---|---|---|
| 中立（所有协议） | `CALL_BEFORE_SEND = "call.before_send"` / `CALL_AFTER_RECV = "call.after_recv"` | `CallExchangeEvent`（信封带 `protocol` 字段，E1） | 状态机 `_do_call` |
| http 专属 | `HTTP_BEFORE_SEND` / `HTTP_AFTER_RECV`（payload 形状不变，headers 仍传同对象引用支持原地改写） | `HttpRequestEvent` / `HttpResponseEvent`（形状不变） | HttpProtocolExecutor |

现有 4 插件（auth_headers / collector / response_body_extract / test_report）零改动。

**状态机状态协议中立化**（决策 13 允许范围内：不做结构重构，只做语义归一）：

| 新名（语义） | 别名（历史名） | value（不变） |
|---|---|---|
| `PREPARE`（协议前置准备） | `BEFORE_REQUEST` | `"before_request"` |
| `INVOKING`（协议调用发出） | `CALLING` | `"calling"` |
| `EXTRACTING`（响应/结果后处理） | `AFTER_REQUEST` | `"after_request"` |

枚举 value 全部不变 → 事件、报告、状态序列化零回归。`StrategyPhase` 同步加同名别名。

### 2.2 多线程模型（suite 内 scenario 级分派）

- 决策 6 口径：**一进程一 run；单元级线程池**。当前 Suite 是扁平 Scenario 列表，单元 = scenario。
- `Suite` schema 增加 `execution: SuiteExecution`（`parallel: bool = False`，`maxWorkers: int = 4`）——
  **默认串行**，行为与现状逐字节一致（零回归护栏）；parallel=true 走线程池分派。
- 新 `scheduler/` 实现：`SuiteScheduler.run_all(scenarios, run_one, parallel, max_workers, fail_fast)`
  - 串行：与现状 for 循环等价（fail_fast 即 break）；
  - 并行：`ThreadPoolExecutor` 提交全部 scenario；fail_fast = 取消未开始的 future + 等待在跑的；
  - 结果按**提交顺序**汇总（details 顺序稳定，与串行输出可对账）。

**六个共享点加锁**（总案批次 4 表格的落地）：

| 共享点 | 动作 |
|---|---|
| 事件总线 | `RLock` 罩住 subscribe/unsubscribe/unsubscribe_plugin/publish；SYNC handler 在锁内派发（跨线程保序、reporter 串行化 → 现有 4 插件线程就绪零改动） |
| Archive | `RLock` + **step/exchange 键空间化** `(scenario_id, step_id)` —— 并行单元都有 step-000，裸 step_id 会互踩 |
| SUITE 层 promote | `Channels` 加 `RLock` 罩住"policy 检查 + 写入"复合操作与快照读 |
| Hook | `HookRegistry` 加 `RLock`（register/sort 与 trigger 并发） |
| 认证 | `AuthRegistry` 加 `RLock`（并发 set/get/snapshot；401 单飞刷新属批次 4 后置项，v1 文档标注） |
| Dispatcher/ProtocolRegistry | `RLock`；注册发生在 bootstrap 期（天然串行），运行期只读 |

补：httpx.Client 按调用创建（每线程独立连接，正确性优先）；日志带单元标识由 log 三件套批次承接。

### 2.3 插件注册通道（补齐文档承诺）

`PluginContext` 新增（`core/plugin.py` 文档早已承诺 `register_strategy`，本轮补齐并加 `register_protocol`）：

- `register_strategy(executor)` → `dispatcher.register`（记录 kind，随插件卸载注销）
- `register_protocol(executor)` → `protocol_registry.register(executor, plugin_name)`（同时登记 dispatcher）

`PluginLoader.activate_all / deactivate_all` 透传 `dispatcher` / `protocol_registry`；卸载时按插件名批量注销协议与策略。协议类插件（`PluginCategory` 新增 `PROTOCOL`）即"多协议注册"的正式入口。

### 2.4 Plate 侧（additive，P1）

- `ApiSpec` 加 `protocol: str = "http"`（开放 str，不锁 Literal —— 协议注册是执行器侧事务，plate 只承载判别字段）。
- `EndpointDetailView`（strict 镜像）同步加字段；存量端点默认 "http"，迁移量恒为零。
- 分派纪律：`registry` 的 `by_route`（service, method, path 三元组）仅对 `protocol == "http"` 的端点建索引；
  query_views / exporter 消费端点字段时按 `protocol` 分派（本轮只加纪律注释与路由守卫，非 http 端点尚无生产者）。
- 协议请求体的数据结构定义 = `RequestSpec.declarations`（JSONPath 树）不变 —— 对 JSON 树形态的协议
  （http-json / grpc-json / dubbo-json）天然通用；非 JSON 载荷协议在各自 ApiSpec 变体中自定义（阶段 7）。

### 2.5 不做（本轮范围控制，继承总案否决清单）

sql/ssh 执行器、资源层、suite 编排（D1-D9 留批次 2/3）、检查点续跑、跨执行缓存、状态机受限回退、
server 舰队、matrix 模式。注册机制以测试内注册的自定义协议端到端验证，不内置第二协议实现。

## 三、实施清单（文件级）

| # | 文件 | 变更 |
|---|---|---|
| 1 | `schema/call.py` 新 | `Call` 开放模型 + `from_api` |
| 2 | `schema/step.py` | api/request 转可选；call 字段；恰好其一校验 + api→call 归一化 |
| 3 | `schema/scenario.py` | `SuiteExecution`（parallel/maxWorkers）挂在 Suite |
| 4 | `protocols/base.py` 新 | `ProtocolExecutor` / `ProtocolCallContext` |
| 5 | `protocols/registry.py` 新 | `ProtocolRegistry`（线程安全 + dispatcher 联动 + 按插件注销） |
| 6 | `strategy/builtin/call.py` 改 | `CallExecutor` 原地升级为 http 协议执行器（吸收 URL 路由 + HTTP 钩子/事件；类名/kind/模块 logger 三处历史契约不动，插件与既有测试零改动）；`protocols/builtin/http.py` 为规范化别名 `HttpProtocolExecutor` |
| 7 | `statemachine/states.py` | 中立名 + 别名（value 不变） |
| 8 | `statemachine/engine.py` | `_do_call` 三段式；`_do_http_call` 别名；`_CallSpec` re-export；protocol_registry 注入 |
| 9 | `core/hooks.py` | `CALL_BEFORE_SEND/AFTER_RECV` + RLock |
| 10 | `events/bus.py` | RLock 全罩 |
| 11 | `events/types.py` | `CallExchangeEvent`（protocol 信封） |
| 12 | `context/channels.py` | promote/snapshot RLock |
| 13 | `context/archive.py` | RLock + step/exchange 键空间化 |
| 14 | `auth/registry.py` | RLock |
| 15 | `strategy/dispatcher.py` | `unregister`/`kinds`；`build_default_dispatcher` 挂 protocols |
| 16 | `core/plugin.py` | PluginContext.register_strategy/register_protocol |
| 17 | `plugins/loader.py` | activate/deactivate 透传两个注册表 |
| 18 | `plugins/categories.py` | `PROTOCOL` 类别 |
| 19 | `core/bootstrap.py` | Configuration.protocols；loader 透传 |
| 20 | `core/scenario_runner.py` | protocol_registry 透传；step 可执行判定改 call |
| 21 | `core/runner.py` | `_run_suite` 走 SuiteScheduler；protocols 透传 |
| 22 | `scheduler/scheduler.py` + `concurrency.py` | `SuiteScheduler`（串行/并行两模式，Engine._run_suite 接线） |
| 23 | `preprocessor/scenario_preprocessor.py` | `_resolve_step` 携带 call 并展开模板 |
| 24 | plate `schema/endpoint/api_spec.py` | protocol 字段 |
| 25 | plate `http/views.py` | 镜像同步 |
| 26 | plate `registry/index.py` | by_route 仅对 protocol=="http" 建索引（分派纪律守卫） |
| 27 | `cli/commands/run_launch.py` | 按 kind 分派（suite 亦可 launch，execution.parallel 可达） |
| 28 | `pyproject.toml` testpaths | + tests/unit/protocols、tests/unit/scheduler |
| 29 | 既有缺陷顺手修 | ① `ContextManager.finalize_step` exchange 快照按引用保存被 clear 清空（历史 bug：归档 exchange 恒空）→ 浅拷贝；② `tests/unit/runtime_control` 三处 `scenario_runner.StepRunner` 全局替换不恢复（污染同进程后续测试）→ finally 恢复 |

## 四、验收门

1. **零回归**：既有 testpaths（tests/plate + tests/unit/{reporter,generator,config,scenario,engine,runtime_control}）结果与基线一致（基线 10 个 plate 既有失败不新增不减少）；`_do_http_call` 直调测试全绿；HTTP_BEFORE_SEND headers 原地改写契约保持。
2. **多协议**：测试内注册自定义协议执行器 → Step 用 `call{protocol:"custom"}` 表达 → 状态机全流程流转（含 Extract/Assertion 用 JSONPath 消费该协议写下的 scratch）→ 插件通道 `register_protocol` 可注册、卸载可注销。
3. **多线程**：parallel=true 的 suite，多 scenario 并发执行（耗时证明重叠）；Archive 键不互踩；事件序号单调；结果按提交序汇总；fail_fast 串行/并行语义成文且有测试。
4. **plate 基线**：protocol 字段默认 http，plate 测试与基线一致。
