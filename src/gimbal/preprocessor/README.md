# Preprocessor 模块

预处理模块，在用例执行前进行预处理操作，包括引用解析、循环检测、完整性检查等。

## 设计理念

### 1. 预处理管道

```
Schema 输入
    │
    ▼
┌─────────────────┐
│     Pipeline    │  预处理管道主入口
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RefResolver    │  引用解析
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CycleDetector   │  循环依赖检测
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CompletenessChecker │  完整性检查
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SchemaValidator │  Schema 校验
└────────┬────────┘
         │
         ▼
    处理后的 Schema
```

### 2. Hook 机制

预处理管道使用 Hook 机制扩展，每个 Hook 在特定阶段执行。

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `pipeline.py` | `PreprocessorPipeline` 预处理管道 |
| `hook_base.py` | `PreprocessorHook` Hook 抽象基类 |
| `cache.py` | 装配缓存读写 |
| `hooks/` | Hook 实现 |
| `hooks/ref_resolver.py` | 引用解析器 |
| `hooks/cycle_detector.py` | 循环依赖检测器 |
| `hooks/completeness_checker.py` | 完整性检查器 |
| `hooks/schema_validator.py` | Schema 校验器 |

---

## PreprocessorPipeline

```python
class PreprocessorPipeline:
    """预处理管道主入口。"""

    def process(self, schema: Scenario) -> Scenario:
        """执行完整预处理流程。"""
        pass

    def add_hook(self, hook: PreprocessorHook) -> None:
        """添加自定义 Hook。"""
        pass
```

---

## PreprocessorHook

```python
class PreprocessorHook(ABC):
    """预处理 Hook 抽象基类。"""

    @abstractmethod
    def run(self, schema: Scenario, context: dict) -> Scenario:
        """执行 Hook 逻辑。"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Hook 名称。"""
        pass
```

---

## 内置 Hooks

### RefResolver

解析 Schema 中的引用（`$ref`），将其替换为实际内容。

```python
class RefResolver(PreprocessorHook):
    """引用解析器。"""

    name = "ref_resolver"
```

### CycleDetector

检测 Schema 中的循环依赖。

```python
class CycleDetector(PreprocessorHook):
    """循环依赖检测器。"""

    name = "cycle_detector"
```

### CompletenessChecker

检查 Schema 的完整性，确保所有必需字段都已填充。

```python
class CompletenessChecker(PreprocessorHook):
    """完整性检查器。"""

    name = "completeness_checker"
```

### SchemaValidator

使用 Pydantic 验证 Schema 的正确性。

```python
class SchemaValidator(PreprocessorHook):
    """Schema 校验器。"""

    name = "schema_validator"
```

---

## 使用示例

```python
from gimbal.preprocessor import PreprocessorPipeline
from gimbal.schema import Scenario

pipeline = PreprocessorPipeline()

# 添加自定义 Hook
pipeline.add_hook(MyCustomHook())

# 执行预处理
processed = pipeline.process(scenario)
```

---

## 缓存机制

预处理结果可以缓存以提升性能：

```python
from gimbal.preprocessor.cache import AssemblyCache

cache = AssemblyCache()
cache.save(assembly_id, processed_schema)
cached = cache.load(assembly_id)
```

---

## 运行测试

```bash
python -m gimbal.preprocessor
```
