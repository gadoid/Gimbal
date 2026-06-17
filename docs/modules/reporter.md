# Reporter 模块

> 报告器模块：负责把一次测试运行的中间事件与最终结果加工成报告产物（控制台、JSON、Allure、HTML、IM 通知、平台上传等）。

## 目录结构

```
gimbal/reporter/
├── __init__.py                # 公共 API 导出
├── base.py                    # ReportArtifact 数据类 + ReporterBase 可选基类
├── protocol.py                # ReportContext + Reporter Protocol
├── registry.py                # ReporterRegistry（按 name 注册/创建 reporter）
├── runtime.py                 # ReporterRuntime（begin_all / notify / finalize_all / shutdown 调度）
└── builtin/                   # 内置 reporter 集合
    ├── __init__.py            # register_builtin_reporters / builtin_reporter_names
    ├── console.py             # 控制台 reporter
    ├── json_reporter.py       # JSON reporter
    ├── junit.py               # JUnit XML reporter
    ├── allure_reporter.py     # Allure reporter
    ├── html_reporter.py       # HTML reporter
    ├── im_notifier.py         # IMNotifier（钉钉/Slack/飞书 webhook）
    └── platform_uploader.py   # PlatformUploader（HTTP 上传到内部测试平台）
```

## 核心组件

### ReportArtifact

所有 Reporter 的统一终产物。`path` 与 `content` 至少一个非空（构造时校验），
因此既支持"落盘 + 文件型"（JUnit、Allure、HTML），也支持"内容型"（IM 推送 Markdown）。

```python
@dataclass
class ReportArtifact:
    name: str                              # 报告名（通常 == reporter.name）
    path: Optional[Path] = None            # 文件路径（落盘场景）
    content: Optional[str] = None          # 字符串内容（推送 payload）
    media_type: str = "application/octet-stream"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None: ...   # 校验 path/content 至少一个非空
    def is_file_based(self) -> bool: ...   # 是否文件型（path is not None）
    def to_dict(self) -> dict[str, Any]: ...  # 供 JsonReporter / log 序列化
```

### ReporterBase（可选基类）

内置 Reporter 的可选基类，子类约定：

1. 必须定义类属性 `name`（注册名，例如 `"console"` / `"junit"` / `"im_notifier"`）。
2. 可选定义 `interested_events: tuple[str, ...]`：`begin()` 时按列表自动订阅。
3. 可选定义 `is_async: bool`：True = `SubscriptionMode.ASYNC`（慢回调不阻塞 event pipeline），False（默认）= SYNC。
4. 可选定义 `stream_to_stderr: bool`：仅 ConsoleReporter 默认 True。
5. 必须实现 `finalize(run_result, ctx) -> ReportArtifact`。
6. 可选实现 `on_event(event)`（订阅了事件的 reporter 才需要）。

`ReporterBase` 不显式继承 `Reporter` Protocol，但方法签名兼容，第三方插件可以走
duck typing 直接实现 `Reporter` Protocol，不必继承此基类。

```python
class ReporterBase(ABC):
    name: str = ""
    interested_events: tuple[str, ...] = ()
    is_async: bool = False
    stream_to_stderr: bool = False

    def begin(self, ctx: "ReportContext") -> None: ...  # 默认按 interested_events 自动订阅
    def on_event(self, event: "FrameworkEvent") -> None: ...  # 默认 no-op
    @abstractmethod
    def finalize(self, run_result: "RunResult", ctx: "ReportContext") -> ReportArtifact: ...
```

### ReportContext

`Reporter` 在生命周期中能拿到的所有上下文（事件总线、报告目录、用户配置、订阅模式等）。
通常由 `ReporterRuntime` 构造并传入。

### ReporterRegistry

按 `name` 注册 reporter 工厂（`name -> factory(user_config: dict) -> Reporter`），
提供 `register / create / list_names / get_factory` 等接口。重复注册默认抛
`ReporterAlreadyRegistered`，`register(..., replace=True)` 时覆盖。

### ReporterRuntime（调度器）

统一管理一组 Reporter 的生命周期。状态机：

```
new
 │ setup()
 ▼
ready
 │ begin_all()
 ▼
running
 │ notify() × N
 ▼
running
 │ finalize_all()
 ▼
finalized
 │ shutdown()
 ▼
closed
```

`setup` / `begin_all` / `finalize_all` 各自幂等：重复调用只生效一次。

```python
class ReporterRuntime:
    def __init__(self, registry: ReporterRegistry) -> None: ...
    def setup(self, bus: Any, config: Any) -> None:
        """绑定 bus 与 config。在 bootstrap 末尾、Engine.run 之前调用。"""

    def begin_all(
        self,
        framework_ctx: FrameworkContext,
        reporter_names: list[str],
        report_dir: Path,
        plugin_configs: dict[str, dict[str, Any]],
    ) -> None:
        """实例化 reporters + 调 begin() + 调 ReporterBase.begin 自动订阅事件。"""

    def notify(self, event: FrameworkEvent) -> None:
        """转发一个事件到所有 reporter（带错误隔离）。
        通常 reporter 通过 EventBus 自己订阅，不需 Engine 主动 notify；此方法
        保留是为了让 Engine 在没有 bus 的场景（例如离线 replay）也能驱动 reporter。"""

    def finalize_all(self, run_result: RunResult) -> list[ReportArtifact]:
        """逐个 finalize reporter，产出 ReportArtifact 列表。"""

    def shutdown(self) -> ReportErrorLog:
        """unsubscribe 全部订阅，返回错误日志。"""

    # 辅助属性
    @property
    def state(self) -> str: ...        # new/ready/running/finalized/closed
    @property
    def error_log(self) -> ReportErrorLog: ...
    @property
    def reporters(self) -> list[Any]: ...
```

#### ReportErrorLog

单个 reporter 在 `begin` / `on_event` / `finalize` / `shutdown` 任一阶段抛异常时，
runtime 把异常隔离并记录到 `ReportErrorLog`，**不中断**其他 reporter。

```python
@dataclass
class ReportErrorEntry:
    reporter_name: str
    phase: str                  # "begin" / "on_event" / "finalize" / "shutdown"
    error_type: str
    error_message: str
    traceback: Optional[str] = None
    def short(self) -> str: ...

@dataclass
class ReportErrorLog:
    entries: list[ReportErrorEntry] = field(default_factory=list)
    def add(self, reporter_name, phase, exc) -> None: ...
    @property
    def has_errors(self) -> bool: ...
    def summary(self) -> str: ...   # 多行可读汇总
```

## 内置 reporter

`gimbal.reporter.builtin` 提供：

- `console`、`json`、`junit`、`allure`、`html`：常规文件型/控制台输出。
- `im_notifier`：即时通讯 webhook 推送。
- `platform_uploader`：把本 run 的 artifact 批量上传到内部测试平台。

### 注册方式

```python
from gimbal.reporter import ReporterRegistry, ReporterRuntime
from gimbal.reporter.builtin import register_builtin_reporters

registry = ReporterRegistry()
register_builtin_reporters(registry)         # 注册所有内置 reporter
names = builtin_reporter_names()             # ('console','json','junit','allure','html','im_notifier','platform_uploader')
```

`register_builtin_reporters(registry)` 内部对每个内置 reporter 调用
`registry.register(name, factory, replace=True)`，重复注册安全。

### IMNotifier（钉钉 / Slack / 飞书）

```python
class IMNotifier(ReporterBase):
    name = "im_notifier"
    interested_events = ("step.failed", "scenario.end")
    is_async = True   # IM webhook 慢，不阻塞 event pipeline
```

- 支持三个内置 channel：`dingtalk`（加签）、`slack`（无签名）、`feishu`（加签）。
- 订阅 `step.failed`：失败步骤立即推送并按 `(step_id, phase)` 去重。
- 订阅 `scenario.end`：失败/错误的 scenario 推送 WARN 消息。
- `finalize()` 推送 PASS/FAIL 汇总 Markdown，返回 content-only 的 `ReportArtifact`。

```yaml
# gimbal.yaml
plugin_configs:
  im_notifier:
    channel: dingtalk            # dingtalk | slack | feishu
    webhook_url: https://oapi.dingtalk.com/robot/send?access_token=xxx
    secret: SEC...
    at_mobiles: []
    send_on_step_failed: true    # 失败步骤立即推送（默认 True）
```

### PlatformUploader（HTTP 上传到内部测试平台）

```python
class PlatformUploader(ReporterBase):
    name = "platform_uploader"
    is_async = True   # 平台上传可能 100s+，不阻塞 finalize
    # 不订阅事件，只在 finalize 一次性产出
```

- `finalize()` 扫描 `ctx.report_dir` 下的常见文件（junit-*.xml / *.json / *.html / *.txt），
  打包成 `body` dict，再以 Bearer token 头 POST 到 `platform_url`。
- 失败指数退避重试 `max_retries` 次（默认 3），间隔 `min(2**attempt, 10)` 秒。
- 未配置 `platform_url` 时落盘 `platform-upload-debug.json` 便于调试。

```yaml
# gimbal.yaml
plugin_configs:
  platform_uploader:
    platform_url: https://test-platform.example.com/api/v1/runs
    api_token: xxx
    timeout: 30
    max_retries: 3
```

## 使用示例

### 1. 典型 bootstrap 用法

```python
from gimbal.reporter import ReporterRegistry, ReporterRuntime
from gimbal.reporter.builtin import register_builtin_reporters

registry = ReporterRegistry()
register_builtin_reporters(registry)
runtime = ReporterRuntime(registry)
runtime.setup(bus=event_bus, config=bootstrap_config)

runtime.begin_all(
    framework_ctx=framework_ctx,
    reporter_names=["console", "junit", "im_notifier"],
    report_dir=Path("./reports"),
    plugin_configs={
        "im_notifier": {
            "channel": "dingtalk",
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
            "secret": "SEC...",
        },
        "platform_uploader": {
            "platform_url": "https://test-platform.example.com/api/v1/runs",
            "api_token": "xxx",
        },
    },
)

# ... 跑测试（reporter 通过 EventBus 自行订阅感兴趣的事件）...
artifacts = runtime.finalize_all(run_result)
runtime.shutdown()
```

### 2. 自定义一个简单 reporter

```python
from gimbal.reporter.base import ReportArtifact, ReporterBase

class MarkdownSummaryReporter(ReporterBase):
    name = "markdown_summary"
    interested_events = ("scenario.end",)

    def __init__(self) -> None:
        self._lines: list[str] = []

    def on_event(self, event):
        if event.status == "passed":
            self._lines.append(f"- PASS {event.scenario_id}")
        else:
            self._lines.append(f"- FAIL {event.scenario_id}: {event.error}")

    def finalize(self, run_result, ctx):
        text = "# Summary\n\n" + "\n".join(self._lines)
        return ReportArtifact(
            name=self.name,
            path=None,
            content=text,
            media_type="text/markdown",
            metadata={"scenarios": len(self._lines)},
        )

def factory(user_config: dict) -> MarkdownSummaryReporter:
    return MarkdownSummaryReporter()

# 注册并加入 runtime
registry.register("markdown_summary", factory, replace=True)
```

## 设计原则

1. **生命周期统一**：所有 reporter 走 `begin → on_event → finalize` 三段式，由 `ReporterRuntime` 调度。
2. **错误隔离**：单个 reporter 在任何阶段抛异常都不会影响其他 reporter，错误累积到 `ReportErrorLog`。
3. **产物抽象**：用 `ReportArtifact` 统一表示文件型/内容型/上传型产物。
4. **可组合**：多个 reporter 可同时启用（console + junit + im_notifier + platform_uploader）。
5. **同步/异步可配**：慢 reporter（IM、平台上传）设 `is_async = True` 走 `SubscriptionMode.ASYNC`，不阻塞主流程。
6. **protocol-first**：第三方插件可只实现 `Reporter` Protocol，不必继承 `ReporterBase`。
