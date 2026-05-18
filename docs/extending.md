# Extension Guide

## 概述

Gimbal 框架设计为可扩展的，主要扩展点包括：

- **自定义策略 Executor**: 添加新的策略类型
- **自定义报告器 Reporter**: 添加新的报告格式
- **自定义资产解析器**: 支持新的资产来源
- **自定义调度器**: 支持新的调度策略

---

## 1. 添加自定义策略 Executor

### 1.1 实现 StrategyExecutor

```python
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

class MyCustomExecutor(StrategyExecutor):
    kind = "my_custom"  # 唯一标识

    def execute(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        # 业务逻辑
        try:
            # 执行逻辑
            return StrategyResult(
                status=StrategyStatus.PASSED,
                strategy_id=getattr(spec, "name", self.kind),
                message="执行成功",
            )
        except Exception as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=getattr(spec, "name", self.kind),
                error=str(exc),
            )
```

### 1.2 注册 Executor

```python
from gimbal.strategy.dispatcher import StrategyDispatcher

dispatcher = StrategyDispatcher()
dispatcher.register(MyCustomExecutor())
```

### 1.3 规范

- `kind` 必须唯一
- 不允许抛出异常，异常必须包裹进 `StrategyResult`
- 执行耗时写入 `result.duration_ms`
- 通过 `view.promote_variable()` 写入 context

---

## 2. 添加自定义报告器

### 2.1 实现 Reporter 接口

```python
from gimbal.reporter.base import Reporter

class MyCustomReporter(Reporter):
    name = "my_custom"  # 唯一标识

    def on_scenario_start(self, scenario_id: str) -> None:
        pass

    def on_scenario_end(self, result: ScenarioRunResult) -> None:
        pass

    def on_step_start(self, step_id: str) -> None:
        pass

    def on_step_end(self, result: StepRunResult) -> None:
        pass

    def on_finalize(self, summary: RunResult) -> None:
        # 输出报告
        pass
```

### 2.2 注册 Reporter

```python
from gimbal.reporter.manager import ReporterManager

manager = ReporterManager()
manager.register(MyCustomReporter())
```

---

## 3. 添加新的 StrategyPhase

如果需要添加新的执行阶段：

### 3.1 在 `strategy.py` 添加枚举值

```python
class StrategyPhase(str, Enum):
    BEFORE_REQUEST = "before_request"
    AFTER_REQUEST = "after_request"
    VERIFYING = "verifying"
    TEARDOWN = "teardown"
    CUSTOM_PHASE = "custom_phase"  # 新增
```

### 3.2 在状态机中添加对应 handler

```python
class StepStateMachine:
    def __init__(self, ...):
        self._handlers = {
            StepState.BEFORE_REQUEST: self._handle_before_request,
            StepState.CUSTOM_PHASE: self._handle_custom,  # 新增
            # ...
        }

    def _handle_custom(self) -> StepState:
        """执行自定义阶段逻辑"""
        # ...
        return StepState.NEXT_STATE
```

---

## 4. 添加新的上下文字段

### 4.1 扩展 StepContext

```python
from gimbal.context.step import StepContext

class MyStepContext(StepContext):
    custom_field: str = ""
```

### 4.2 注册到 ContextManager

```python
from gimbal.context.manager import ContextManager

class MyContextManager(ContextManager):
    def derive_step_context(self, ..., custom_field: str = "") -> MyStepContext:
        ctx = super().derive_step_context(...)
        ctx.custom_field = custom_field
        return ctx
```

---

## 5. 添加新的 Asset 类型

### 5.1 定义 Schema

```python
from pydantic import Field
from typing import Annotated

class MyAsset(BaseModel):
    kind: Literal["my_asset"] = "my_asset"
    name: str
    config: dict = {}

class MyAssetRef(RefBase):
    kind: Literal["my_asset_ref"] = "my_asset_ref"

MyAssetUnion = Annotated[
    Union[MyAsset, MyAssetRef],
    Field(discriminator="kind")
]
```

### 5.2 实现解析器

```python
class MyAssetResolver:
    def resolve(self, ref: str) -> MyAsset:
        # 从资产库解析
        pass
```

---

## 6. 扩展配置来源

Gimbal 使用 `BootstrapConfig` 合并多来源配置：

```python
from gimbal.config.loader import ConfigLoader

class MyConfigLoader(ConfigLoader):
    def load(self) -> BootstrapConfig:
        # 添加自定义配置源
        base_config = super().load()
        # 合并自定义配置
        return merged_config
```

---

## 7. 最佳实践

1. **保持职责单一**: 每个扩展只关注一个功能
2. **使用组合而非继承**: 优先使用组合模式
3. **错误处理**: 所有异常必须包裹进结果对象
4. **日志记录**: 使用 `logging.getLogger(__name__)` 记录日志
5. **类型注解**: 提供完整的类型注解
6. **单元测试**: 为扩展编写单元测试
