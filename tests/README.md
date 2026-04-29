# Tests 模块

单元测试目录，用于存放各模块的单元测试代码。

## 目录结构

```
tests/
└── __init__.py
```

## 测试原则

1. **隔离测试** - 每个测试文件应独立，不依赖外部资源
2. **快速执行** - 单元测试应能快速运行
3. **明确断言** - 每个测试应有清晰的断言和错误信息

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行指定测试文件
pytest tests/test_interpolation.py

# 运行指定测试函数
pytest tests/test_interpolation.py::test_json_path_get
```

## 示例测试结构

```python
# tests/test_interpolation.py
import pytest
from interpolation import Interpolator, JsonPath

class TestInterpolator:
    def test_interpolate_simple_var(self):
        interp = Interpolator({"name": "Alice"})
        result = interp.interpolate("Hello ${name}")
        assert result == "Hello Alice"

class TestJsonPath:
    def test_get_nested_value(self):
        data = {"user": {"name": "Bob"}}
        result = JsonPath.get(data, "user.name")
        assert result == "Bob"
```

## 待补充

建议后续添加以下测试文件：
- `test_schema/` - 数据模型测试
- `test_runtime/` - 执行引擎测试
- `test_handlers/` - 动作处理器测试
- `test_adapters/` - 适配器测试（可使用 Mock）
