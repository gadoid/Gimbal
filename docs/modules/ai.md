# AI 模块

> AI 辅助功能模块，提供提示词管理和 AI Provider 集成

## 目录结构

```
gimbal/ai/
├── __init__.py
├── assistant_base.py      # AI 助手基类
├── exceptions.py          # AI 相关异常
├── prompts/               # 提示词管理
│   ├── __init__.py
│   ├── assemble.py        # 提示词组装
│   ├── diagnose.py        # 诊断相关提示词
│   └── generate_data.py   # 数据生成提示词
└── providers/             # AI Provider
    ├── __init__.py
    └── anthropic.py       # Anthropic Provider 实现
```

## 核心组件

### AssistantBase

AI 助手的抽象基类，定义了与 AI 交互的标准接口。

```python
class AssistantBase(ABC):
    """AI 助手基类"""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """发送提示词到 AI 并返回响应"""
        raise NotImplementedError
```

### Prompts 子模块

- **assemble.py**: 组合多个提示词片段构建完整提示词
- **diagnose.py**: 提供诊断相关的提示词模板
- **generate_data.py**: 提供测试数据生成相关的提示词模板

### Providers 子模块

- **anthropic.py**: Anthropic Claude API 的实现

## 异常类

```python
class AIError(Exception):
    """AI 模块基础异常"""
    pass

class ProviderError(AIError):
    """Provider 调用失败"""
    pass

class RateLimitError(AIError):
    """请求频率超限"""
    pass
```

## 使用示例

```python
from gimbal.ai.assistant_base import AssistantBase
from gimbal.ai.providers.anthropic import AnthropicProvider

# 创建 Provider
provider = AnthropicProvider(api_key="sk-...")

# 使用 Provider
response = await provider.complete("Explain this test failure")
```

## 设计原则

1. **Provider 抽象**: 通过基类定义统一接口，支持多种 AI Provider
2. **提示词模块化**: 将提示词拆分为可组合的片段
3. **异步优先**: 使用 async/await 模式避免阻塞