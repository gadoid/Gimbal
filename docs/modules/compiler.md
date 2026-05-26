# Compiler 模块

> 场景文件编译模块，负责解析 YAML/Markdown/Text 格式的场景文件

## 目录结构

```
gimbal/compiler/
├── __init__.py
├── compiler.py       # 编译器主入口
├── assembler.py      # 场景组装器
├── validators.py    # 验证器
└── parsers/         # 解析器
    ├── __init__.py
    ├── markdown.py   # Markdown 解析器
    ├── yaml.py       # YAML 解析器
    └── text.py       # 纯文本解析器
```

## 核心组件

### Compiler

编译器主入口，负责协调解析和组装过程。

```python
class Compiler:
    """场景编译器"""

    def compile(self, source: str | Path) -> Scenario | Suite:
        """编译场景文件"""
        ...

    def validate(self, source: str | Path) -> ValidationResult:
        """验证场景文件"""
        ...
```

### Assembler

场景组装器，负责将从不同格式解析出的内容组装成标准场景结构。

```python
class Assembler:
    """场景组装器"""

    def assemble(self, parsed: dict) -> Scenario | Suite:
        """组装解析结果为场景对象"""
        ...
```

### Parsers

#### YAML Parser

解析 YAML 格式的场景文件：

```yaml
kind: scenario
scenarioId: sc-001
meta:
  name: 用户登录测试
  description: 测试用户登录流程
steps:
  - api:
      service: user-service
      method: POST
      path: /api/login
    request:
      body:
        username: "${username}"
        password: "${password}"
```

#### Markdown Parser

解析 Markdown 格式的场景文件，支持代码块中定义 API 和断言。

#### Text Parser

解析纯文本格式的场景文件。

## 验证器

```python
class Validator:
    """场景验证器"""

    def validate(self, scenario: Scenario) -> ValidationResult:
        """验证场景完整性"""
        ...

    def check_refs(self, scenario: Scenario) -> list[RefError]:
        """检查引用完整性"""
        ...
```

## 使用示例

```python
from gimbal.compiler import Compiler

compiler = Compiler()

# 编译场景文件
scenario = compiler.compile("./tests/login.yaml")

# 验证场景
result = compiler.validate("./tests/login.yaml")
if not result.is_valid:
    for error in result.errors:
        print(f"Error: {error}")
```

## 设计原则

1. **多格式支持**: 通过解析器抽象支持不同格式
2. **验证先行**: 解析前先验证，验证失败不解析
3. **引用解析**: 支持 `$ref` 引用并解析
4. **错误累积**: 收集所有错误而非遇到第一个错误就停止