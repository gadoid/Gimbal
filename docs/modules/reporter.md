# Reporter 模块

> 报告器模块，负责测试结果的报告输出

## 目录结构

```
gimbal/reporter/
├── __init__.py
├── reporter_base.py  # Reporter 基类
├── artifact.py       # 报告产物
└── builtin/         # 内置报告器
    ├── __init__.py
    ├── console.py    # 控制台报告器
    ├── json_reporter.py  # JSON 报告器
    ├── allure_reporter.py # Allure 报告器
    ├── platform_uploader.py # 平台上传器
    └── im_notifier.py    # IM 通知器
```

## 核心组件

### Reporter 基类

```python
class Reporter(ABC):
    """报告器抽象基类"""

    @abstractmethod
    def report(self, result: RunResult) -> None:
        """生成报告"""
        raise NotImplementedError

    def report_scenario(self, scenario_result: ScenarioRunResult) -> None:
        """报告单个 Scenario"""
        ...

    def report_step(self, step_result: StepRunResult) -> None:
        """报告单个 Step"""
        ...
```

### Artifact

报告产物：

```python
class Artifact:
    """报告产物"""
    path: Path
    content_type: str
    size: int
    sha256: str
```

## 内置报告器

### ConsoleReporter

控制台报告器：

```python
class ConsoleReporter(Reporter):
    """控制台报告器"""

    def report(self, result: RunResult) -> None:
        # 彩色输出
        # 进度条
        # 统计摘要
```

### JsonReporter

JSON 报告器：

```python
class JsonReporter(Reporter):
    """JSON 报告器"""

    def report(self, result: RunResult) -> None:
        # 输出到 JSON 文件
        # 包含完整执行详情
```

### AllureReporter

Allure 报告器：

```python
class AllureReporter(Reporter):
    """Allure 报告器"""

    def report(self, result: RunResult) -> None:
        # 生成 Allure 结果文件
        # 支持 Allure UI 查看
```

### PlatformUploader

平台上传器：

```python
class PlatformUploader(Reporter):
    """测试平台上传器"""

    def report(self, result: RunResult) -> None:
        # 上传结果到测试平台
```

### IMNotifier

IM 通知器：

```python
class IMNotifier(Reporter):
    """IM 通知器"""

    def report(self, result: RunResult) -> None:
        # 发送结果到企业微信/钉钉等
```

## 使用示例

```python
from gimbal.reporter.builtin.console import ConsoleReporter
from gimbal.reporter.builtin.json_reporter import JsonReporter

# 创建报告器
reporters = [
    ConsoleReporter(),
    JsonReporter(output_dir="./reports"),
]

# 执行测试
result = engine.run(scenario)

# 生成报告
for reporter in reporters:
    reporter.report(result)
```

## 设计原则

1. **接口统一**: 所有报告器继承 Reporter 基类
2. **可组合**: 支持多个报告器同时使用
3. **产物抽象**: 报告产物统一建模
4. **格式多样**: 支持控制台、JSON、Allure 等多种格式