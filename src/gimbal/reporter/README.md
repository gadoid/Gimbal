# Reporter 模块

报告模块，负责生成和输出测试执行报告。

## 设计理念

### 1. Reporter 架构

```
Test Execution Results
         │
         ▼
┌─────────────────┐
│  ReporterBase   │  Reporter 抽象基类
└────────┬────────┘
         │
         ├── ConsoleReporter ───▶ 终端输出
         ├── JsonReporter ──────▶ JSON 文件
         ├── AllureReporter ────▶ Allure 报告
         ├── IMNotifier ────────▶ 即时通讯通知
         └── PlatformUploader ───▶ 平台上报
```

### 2. 报告生成流程

```python
# 1. 收集测试结果
results = engine.run(scenario)

# 2. 选择 Reporter
reporter = ConsoleReporter()

# 3. 生成报告
reporter.report(results)
```

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `reporter_base.py` | `Reporter` 抽象基类 |
| `artifact.py` | `ReportArtifact` 报告产物定义 |
| `builtin/` | 内置 Reporter 实现 |
| `builtin/console.py` | 控制台 Reporter |
| `builtin/json_reporter.py` | JSON Reporter |
| `builtin/allure_reporter.py` | Allure Reporter |
| `builtin/im_notifier.py` | 即时通讯通知 |
| `builtin/platform_uploader.py` | 平台上报 |

---

## ReporterBase

```python
class Reporter(ABC):
    """Reporter 抽象基类。"""

    @abstractmethod
    def report(self, result: RunResult) -> ReportArtifact:
        """生成报告。"""
        pass

    @abstractmethod
    def supports(self, result: RunResult) -> bool:
        """判断是否支持该类型结果。"""
        pass
```

---

## ReportArtifact

```python
@dataclass
class ReportArtifact:
    """报告产物。"""

    name: str                    # 报告名称
    path: Optional[Path]         # 报告文件路径
    content: Optional[str]       # 报告内容
    metadata: dict               # 报告元数据
```

---

## 内置 Reporters

### ConsoleReporter

控制台输出 Reporter。

```python
class ConsoleReporter(Reporter):
    """控制台 Reporter。"""

    name = "console"
    supports_colors = True
```

### JsonReporter

JSON 格式报告 Reporter。

```python
class JsonReporter(Reporter):
    """JSON Reporter。"""

    name = "json"
    output_dir = Path("./reports")
```

### AllureReporter

Allure 报告生成器。

```python
class AllureReporter(Reporter):
    """Allure Reporter。"""

    name = "allure"
    output_dir = Path("./reports/allure")
```

### IMNotifier

即时通讯通知 Reporter（预留）。

```python
class IMNotifier(Reporter):
    """IM 通知 Reporter。"""

    name = "im_notifier"
    channels = ["dingtalk", "wechat", "feishu"]
```

### PlatformUploader

平台上报 Reporter（预留）。

```python
class PlatformUploader(Reporter):
    """平台上报 Reporter。"""

    name = "platform_uploader"
```

---

## 使用示例

```python
from gimbal.reporter import Reporter
from gimbal.reporter.builtin import ConsoleReporter, JsonReporter

# 使用控制台 Reporter
reporter = ConsoleReporter()
reporter.report(result)

# 使用 JSON Reporter
reporter = JsonReporter(output_dir=Path("./reports"))
reporter.report(result)

# 组合使用
for reporter in [ConsoleReporter(), JsonReporter()]:
    reporter.report(result)
```

---

## 自定义 Reporter

```python
from gimbal.reporter import Reporter, ReportArtifact
from gimbal.core.runner import RunResult

class CustomReporter(Reporter):
    name = "custom"

    def report(self, result: RunResult) -> ReportArtifact:
        # 自定义报告逻辑
        return ReportArtifact(
            name=self.name,
            path=None,
            content="...",
            metadata={}
        )

    def supports(self, result: RunResult) -> bool:
        return True
```

---

## 运行测试

```bash
python -m gimbal.reporter
```
