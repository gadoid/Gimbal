# gimbal-collector 插件

> **模块**：[`plugins/collector/`](../../../plugins/collector)（本地开发插件）
> **状态**：**已实现**，跑通端到端（[tests/unit/test_collector_plugin.py](../../../../tests/unit/test_collector_plugin.py) 9 个测试 + 真实 `PluginLoader` 路径验证）
> **核心能力**：订阅 9 个框架事件（run/scenario/step/http/promotion），在 `run.end` 时落盘 JSON 报告

---

## 0. 实现概览

### 数据流

```
事件总线
  ├─ run.start / run.end                 ─→ ReportStore.on_run_*
  ├─ scenario.start / scenario.end       ─→ ReportStore.on_scenario_*
  ├─ step.start / step.end               ─→ ReportStore.on_step_*
  ├─ http.request / http.response        ─→ ReportStore.on_http_*
  └─ variable.promoted                   ─→ ReportStore.on_variable_*
                                              │
                                              ▼
                                    ReportStore.snapshot()
                                              │
                                              ▼
                                       JsonRenderer.render()
                                              │
                                              ▼
                              ./reports/run-{run_id}.json
```

### 关键文件

| 文件 | 行数 | 职责 |
|------|------|------|
| [`plugins/collector/plugin.yaml`](../../../plugins/collector/plugin.yaml) | — | PluginSpec 清单（name / version / entry_point / category） |
| [`plugins/collector/gimbal_collector/plugin.py`](../../../plugins/collector/gimbal_collector/plugin.py) | ~110 | `CollectorPlugin` 入口；9 个事件订阅 + run.end 落盘 |
| [`plugins/collector/gimbal_collector/report_data.py`](../../../plugins/collector/gimbal_collector/report_data.py) | ~95 | `RunReport` / `ScenarioReport` / `StepReport` / `HttpExchange` 数据类 |
| [`plugins/collector/gimbal_collector/store.py`](../../../plugins/collector/gimbal_collector/store.py) | ~155 | `ReportStore` 事件聚合（含 thread lock、深拷贝 snapshot） |
| [`plugins/collector/gimbal_collector/renderers/json_renderer.py`](../../../plugins/collector/gimbal_collector/renderers/json_renderer.py) | ~30 | JSON 落盘 |
| [`tests/unit/test_collector_plugin.py`](../../../../tests/unit/test_collector_plugin.py) | ~270 | 9 个测试（store / 序列化 / renderer / 端到端 / 鲁棒性 / 重置） |

### 启用方式

```yaml
# gimbal.yaml（项目根）
plugins:
  enabled:
    - gimbal-collector
plugin_configs:
  gimbal-collector:
    output_dir: ./reports
```

跑完后在 `output_dir` 下生成 `run-{run_id}.json`。

---

## 1. 已知缺陷（影响报告内容完整性）

### 1.1 [P0] `HttpRequestEvent.request_headers` 框架不填

**位置**：[`statemachine/engine.py`](../../../../src/gimbal/statemachine/engine.py) 触发 `HttpRequestEvent` 时

**行为**：事件字段 `request_headers: dict = Field(default_factory=dict)`，框架实际**不填值**，永远为空 dict。

**触发场景**：报告里 `http_exchanges[].request_headers = {}`，看不到实际发送的请求头。

**影响**：

- 报告无法体现请求头（如 `Authorization`、`X-Trace-Id` 等）
- 调试"鉴权失败"类问题时缺关键信息

**修复方向**：

- **短期**：在 `HttpRequestEvent` payload 里加上当前 step 上下文（`auth_header` 已经在 `AuthSession` 里能拿到）
- **长期**：让 `Call` 策略 executor 在发请求前 publish 一个"完整 headers 已就绪"的 `HttpRequestEvent`

**触发修复的信号**：用户反馈"报告里看不到请求头信息"。

### 1.2 [P0] `StepEndEvent` 不带 per-assertion 详情

**位置**：[`events/types.py`](../../../../src/gimbal/events/types.py) `StepEndEvent` payload

**行为**：`assertion_count: int = 0` / `assertion_passed: int = 0` 是**聚合数**，没有 `assertions: list[AssertionResult]` 字段。

**触发场景**：报告里看不到"断言 X 失败，期望 Y 实际 Z"。

**影响**：

- 报告只能看到"该 step 失败了"，看不到具体哪个断言失败
- 必须配合 `RunResult.details[].steps[].assertions`（CLI 那条路）才能看到详情

**修复方向**：

- 在 `StepEndEvent` 加 `assertions: list[dict] = Field(default_factory=list)` 字段（`AssertionResult` 的精简版）
- 框架在 `statemachine/engine.py` 收 step 结束事件前从 `StepContext.outcome.assertions` 提取
- 这是**协作项**——需要改 `events/types.py` + 至少一处 publish 点

**触发修复的信号**：用户开始要求"报告里看到具体断言失败信息"。

### 1.3 [P1] 失败 step 的 traceback 不在报告里

**位置**：[`events/types.py`](../../../../src/gimbal/events/types.py) `StepEndEvent.error_brief: Optional[str] = None`

**行为**：`error_brief` 只是**一句话摘要**（如 `"AssertionError: expected 200, got 500"`），没有 `error_traceback` 字段。

**触发场景**：step 失败时，报告只能看到摘要，看不到调用栈。

**修复方向**：

- 在 `StepEndEvent` 加 `error_traceback: Optional[str] = None`
- 框架在 `statemachine/engine.py` 收 step 失败时从 `StepContext.outcome.error_info.traceback` 提取

**触发修复的信号**：CI 出现"失败 step 但不知道是哪里抛的"。

### 1.4 [P1] 框架 init/teardown 事件未订阅

**位置**：插件 [`plugin.py`](../../../plugins/collector/gimbal_collector/plugin.py) `on_activate`

**行为**：只订阅了"处理信息"相关的 9 个事件，未订阅 `framework.init` / `framework.teardown` / `plugin.activated` 等。

**影响**：

- 报告里 `run_id` 是事件自带，但**框架版本、插件列表、加载耗时**等"元信息"看不到
- 排查"插件问题"时不知道当时激活了哪些插件

**修复方向**：

- 订阅 `framework.init` 拿 `framework_version`
- 订阅 `plugin.activated` 累积插件列表

**触发修复的信号**：报告需要"环境元信息"维度。

### 1.5 [P2] `scenario_id` 在 `StepStartEvent` / `StepEndEvent` 可能为空

**位置**：[`events/types.py`](../../../../src/gimbal/events/types.py) `StepStartEvent.scenario_id: str = ""`

**注释**：
```python
# scenario_id 由 ContextManager 填充；statemachine 直接发时为空
scenario_id: str = ""
```

**行为**：`statemachine/engine.py` 直接 publish `StepStartEvent` 时**不填 `scenario_id`**，依赖 `ContextManager.project_step_started` 后处理。

**影响**：

- 当前 `ReportStore` 走 `self._current_scenario_id`（跟踪当前位置）做关联，**workaround 已就绪**
- 但 `event.scenario_id` 字段本身是空的，订阅者拿不到，需要靠"最近一次 scenario.start"推断

**修复方向**：

- 让 `statemachine/engine.py` 直接 publish 时填 `scenario_id`（消除 dual-path 维护成本）
- 或者干脆去掉这个字段，统一用 `_current_*` 跟踪

**触发修复的信号**：重构 `ContextManager.project_*` 时一起处理。

### 1.6 [P2] report 一次性写盘，无流式输出

**位置**：[`plugin.py`](../../../plugins/collector/gimbal_collector/plugin.py) `_flush`

**行为**：run 结束才一次性写整个 JSON。

**影响**：

- 跑超大 run（10w+ steps）时，内存里要 hold 全部 `RunReport`，可能 OOM
- 跑 run 中途崩溃，**之前所有数据全丢**

**修复方向**：

- 改为 `ScenarioEndEvent` 触发时增量写（每 scenario 写一次，append 模式）
- 或者开 background thread，run 中按时间间隔 flush

**触发修复的信号**：CI 出现 OOM 或 run 中崩后零数据可查。

### 1.7 [P2] 报告未做敏感信息脱敏

**位置**：[`json_renderer.py`](../../../plugins/collector/gimbal_collector/renderers/json_renderer.py) `render`

**行为**：直接序列化 `request_body` / `response_body` / `request_headers` 原值。

**影响**：

- 报告里可能含密码、token、个人信息等
- 报告落到磁盘、CI artifact、平台上传链路**任一环节**都泄密

**修复方向**：

- 加 `redact_rules` 配置（正则 / 字段名匹配）
- 默认规则：把 `password` / `token` / `secret` / `authorization` 字段值替换为 `***`
- header 走全 key 匹配，body 走字段名递归匹配

**触发修复的信号**：安全审计 / 报告被传到外网。

### 1.8 [P2] 没有 HTML / Allure / JUnit 等格式

**位置**：[`renderers/`](../../../plugins/collector/gimbal_collector/renderers) 目录

**行为**：只实现了 `JsonRenderer`，没有 `HtmlRenderer` / `AllureRenderer` / `JUnitRenderer`。

**影响**：CLI 用户的可读性差，只能看 JSON。

**修复方向**：

- 仿照 `JsonRenderer` 加 `HtmlRenderer`（纯字符串拼或 Jinja2）
- 加 `JUnitRenderer`（CI 系统友好，pytest/Jenkins 直接识别）
- 加 `AllureRenderer`（生成 Allure results 目录）

**触发修复的信号**：需要给非技术 stakeholder 看报告 / CI 接入。

---

## 2. 设计决策（已落定，写下来防止反复纠结）

### 2.1 继承 `Plugin` 而非 `Reporter`

`reporter/` 目录全是 stub（[reporter/README.md](../../../../src/gimbal/reporter/README.md) 有设计但未落地）。等 `Reporter` 体系实现后再考虑迁移。

### 2.2 单一格式 = 单一插件

不内嵌多格式：`formats: ["json", "html"]` 这种配置**当前不实现**。需要多格式就开多个 plugin 实例（每个 plugin 一份 `plugin.yaml`）。

理由：插件激活 = 单一职责；多格式让单个 plugin 复杂化、配置膨胀。

### 2.3 不加 `_safe` wrapper

`InMemoryEventBus._safe_call`（[events/bus.py:136-144](../../../../src/gimbal/events/bus.py#L136-L144)）已经 `try/except` 兜底，再加一层 wrapper 是冗余。日志靠 `EventBus` 的 `logger.exception` 输出。

### 2.4 `run.end` 注册两次（同事件多 handler）

`store.on_run_end`（写最终统计）和 `_flush`（落盘）都注册到 `run.end`。`_flush` 用 `priority=1`（最低），确保在 store 收完所有数据后跑。

不合并成一个 handler 是为了**关注点分离**：store 只管状态，flush 只管 I/O。

### 2.5 `scenario_id` 用 `_current_scenario_id` 跟踪

`StepStartEvent.scenario_id` 字段是空字符串，插件靠"最近一次 `scenario.start`"推断当前位置。这是**已知的 dual-path workaround**（见 1.5），不修但记录。

### 2.6 snapshot 用 `copy.deepcopy`

renderer 遍历时新事件可能并发写入（`mode=ASYNC` 时），深拷贝切断耦合。代价是内存翻倍，但 run-level 树一般 < 100MB，可接受。

---

## 3. 验证记录

### 3.1 单测（`tests/unit/test_collector_plugin.py`）

```
9 tests, OK
- test_full_flow                              ReportStore 9 个事件全流程
- test_http_response_without_request          异常路径（response 先到）容错
- test_snapshot_is_deep_copy                  snapshot 与 store 隔离
- test_run_report_to_dict_round_trip          序列化往返
- test_writes_file                            JsonRenderer 落盘
- test_creates_output_dir_if_missing          自动建目录
- test_full_run_emit_writes_file              Plugin + EventBus 端到端
- test_handler_exception_does_not_break_bus   handler 抛错不污染 bus
- test_store_reset_after_deactivate           插件卸载后状态重置
```

### 3.2 真实框架路径验证

`PluginLoader.discover(plugins_dir="plugins") → load_all → activate_all → bus.publish(真实 Pydantic 事件) → run.end 触发落盘 → deactivate_all`。生成的报告：

```json
{
  "run_id": "real-001",
  "env": "dev", "mode": "run",
  "summary": {"total": 1, "passed": 1, "failed": 0, "error": 0},
  "scenarios": [{
    "scenario_id": "sc-login", "scenario_name": "login", "status": "passed",
    "steps": [
      {"step_id": "s1", "status": "passed", "duration_ms": 15.3,
       "http_exchanges": [{"method": "POST", "url": "/api/login", "status_code": 200,
                           "request_body": {"user": "alice"}, "response_body": {"token": "xyz"}}]},
      {"step_id": "s2", "status": "passed", "duration_ms": 5.0,
       "http_exchanges": [{"method": "GET", "url": "/api/profile", "status_code": 200,
                           "response_body": {"name": "alice"}}]}
    ]
  }]
}
```

---

## 4. 触发修复的信号（"何时重开"）

满足任意一项即可重开对应工单：

1. **CI 出现"报告里看不到请求头 / 断言详情"** → 1.1、1.2
2. **报告泄密** → 1.7
3. **跑超大 run OOM** → 1.6
4. **非技术 stakeholder 要看报告** → 1.8
5. **重构 `ContextManager.project_*`** → 1.5 顺带处理
6. **`Reporter` 体系落地** → 考虑迁移（见 2.1）

---

## 5. 修复记录

> 修改时在此追加，**不要删除历史条目**。格式：`### YYYY-MM-DD — 简述`。

<!-- 暂无 -->
