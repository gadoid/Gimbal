# Compiler 模块

Schema 编译和解析模块，负责将测试用例从各种格式编译为统一的 Schema 结构。

## 设计理念

### 1. 编译链路

```
输入格式 (Markdown/Text/YAML/JSON)
         │
         ▼
┌─────────────────┐
│    Compiler     │  主入口，协调编译流程
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Assembler    │  资产选择与组装
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Validators    │  编译结果校验
└─────────────────┘
```

### 2. 支持的输入格式

| 格式 | Parser | 说明 |
|------|--------|------|
| Markdown | `markdown.py` | Markdown 格式用例编译 |
| Text | `text.py` | 纯文本格式用例编译 |
| YAML | `yaml.py` | YAML 格式用例编译 |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `compiler.py` | 编译主入口 |
| `assembler.py` | 资产选择与组装 |
| `validators.py` | 编译结果校验 |
| `parsers/` | 格式解析器 |
| `parsers/markdown.py` | Markdown 解析器 |
| `parsers/text.py` | Text 解析器 |
| `parsers/yaml.py` | YAML 解析器 |

---

## 核心类

### Compiler

```python
class Compiler:
    """编译主入口。"""

    def compile(self, source: str, format: str) -> Scenario:
        """将输入编译为 Scenario Schema。"""
        pass
```

### Assembler

```python
class Assembler:
    """资产选择与组装。"""

    def assemble(self, parts: list[Any]) -> Scenario:
        """将多个部分组装为完整的 Scenario。"""
        pass
```

### Validators

```python
class Validators:
    """编译结果校验。"""

    def validate(self, scenario: Scenario) -> bool:
        """校验 Scenario 的完整性和正确性。"""
        pass
```

---

## 使用示例

```python
from gimbal.compiler import Compiler

compiler = Compiler()
scenario = compiler.compile(markdown_text, format="markdown")
```

---

## 运行测试

```bash
python -m gimbal.compiler
```
