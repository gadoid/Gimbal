# Generator 模块

> 变量生成器：为 Scenario 提供声明式变量求值能力（字面量 + 7 个内置生成器）

## 目录结构

```
gimbal/generator/
├── __init__.py        # 公开 API
├── exceptions.py      # GeneratorError, UnknownGeneratorError
├── functions.py       # 7 个 pure function + reset_seq_counter
├── registry.py        # GeneratorRegistry, build_default_registry
├── specs.py           # 7 个 Pydantic Spec + VarSpec 联合体
└── engine.py          # Generator 类
```

## 7 个内置生成器

| kind | 命名参数 | 用途 |
|------|---------|------|
| `uuid` | (无) | 32 位 hex |
| `random_str` | length / charset | 随机字符串 |
| `random_int` | min / max | 闭区间整数 |
| `random_decimal` | min / max / places | 闭区间小数 |
| `timestamp` | format / offset_seconds | 当前时间 + 偏移 |
| `now` | format | 当前时间（无偏移） |
| `seq` | prefix / width / start | 自增序号 |

详见 spec §7.3。

## 公开 API

```python
from gimbal.generator import (
    Generator,                    # 求值入口
    GeneratorRegistry,            # 注册表
    build_default_registry,       # 默认注册表（含 7 个内置）
    VarSpec,                      # 联合体
    GeneratorError, UnknownGeneratorError,
)
```

## 用法

```python
gen = Generator(build_default_registry())

# 单条求值
spec = RandomStrSpec(length=12, charset="alnum")
val = gen.generate(spec)               # "Yk2H8nQp3aZx"

# 批量求值
results = gen.generate_all({
    "bl_no":  {"kind": "random_str", "length": 12},
    "etd":    {"kind": "timestamp",  "format": "epoch"},
})
```

## 设计原则

1. **Pure function**：每个函数除自身参数外无外部依赖
2. **命名参数**：函数参数名与 Spec 字段一一对应
3. **注册表解耦**：新增生成器只需 register(kind, func) 一行
4. **错误透传**：函数异常被 GeneratorError 包装，保留 __cause__
5. **模块级 seq 计数器**：单进程有效；多进程用 reset_seq_counter 隔离
