# AI 模块

AI 集成模块，提供 AI 辅助测试能力。

## 设计理念

### 1. 模块结构

```
ai/
├── assistant_base.py    # AIAssistant 抽象基类
├── exceptions.py        # AI 相关异常定义
├── prompts/             # Prompt 模板
│   ├── assemble.py      # 组装 prompt
│   ├── diagnose.py      # 诊断 prompt
│   └── generate_data.py # 数据生成 prompt
└── providers/           # AI Provider 实现
    └── anthropic.py     # Anthropic Claude provider
```

### 2. 核心抽象

| 类 | 说明 |
|----|------|
| `AIAssistant` | AI 助手的抽象基类，定义交互接口 |
| `AIError` | AI 相关异常基类 |

### 3. Provider 扩展

可通过继承 `AIAssistant` 实现自定义 AI Provider：

```python
class AIAssistant(ABC):
    """AI 助手抽象接口。"""

    @abstractmethod
    def chat(self, message: str, context: dict) -> str:
        """发送消息并获取回复。"""
        pass

    @abstractmethod
    def diagnose(self, test_result: dict) -> str:
        """诊断测试失败原因。"""
        pass
```

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `assistant_base.py` | `AIAssistant` 抽象基类定义 |
| `exceptions.py` | AI 异常类定义 |
| `prompts/assemble.py` | Prompt 组装逻辑 |
| `prompts/diagnose.py` | 诊断场景 Prompt |
| `prompts/generate_data.py` | 测试数据生成 Prompt |
| `providers/anthropic.py` | Anthropic Claude Provider 实现 |

---

## 异常类

```python
class AIError(Exception):
    """AI 相关异常基类。"""
```

---

## 使用示例

```python
from gimbal.ai import AIAssistant

# 使用 Anthropic Provider
from gimbal.ai.providers.anthropic import AnthropicAssistant

assistant = AnthropicAssistant(api_key="...")
result = assistant.chat("分析这个测试失败的原因", context={})
```

---

## 运行测试

```bash
python -m gimbal.ai
```
