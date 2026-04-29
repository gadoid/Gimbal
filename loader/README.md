# Loader 模块

YAML 加载器层，负责将 YAML 格式的场景文件解析为 Python 对象。

## 文件说明

### `yaml_loader.py`
`YamlLoader` - YAML 加载器：

**主要方法：**
- `load(file_path)` - 从文件加载场景
- `loads(yaml_str)` - 从字符串加载场景
- `normalize(data)` - 将字典数据规范化为 `Scenario` 对象

**内部方法：**
- `_normalize_step(step_data)` - 规范化为 `Step` 对象
- `_normalize_action(action_data)` - 规范化为 `Action` 对象

## YAML 格式

```yaml
name: 场景名称
description: 场景描述（可选）
tags:
  - tag1
  - tag2

variables:
  base_url: https://api.example.com
  user_id: 12345

steps:
  - name: 步骤名称
    retry: 0                    # 重试次数（可选）
    timeout: 30                 # 超时时间秒（可选）
    action:
      type: ASSIGN              # 动作类型
      target: variable_name     # 目标变量（可选）
      params:                   # 动作参数
        key: value
```

## 支持的动作类型

| type | 说明 | 必需参数 |
|------|------|---------|
| `HTTP` | HTTP 请求 | `method`, `url` |
| `SQL` | SQL 查询 | `sql` |
| `EXTRACT` | 数据提取 | `source`, `expression`, `target` |
| `ASSIGN` | 变量赋值 | `value`, `target` |
| `ASSERT` | 断言验证 | `actual`, `expected`, `operator` |

## 使用示例

```python
from loader import YamlLoader

# 从文件加载
scenario = YamlLoader.load("examples/scenario.yaml")

# 从字符串加载
yaml_str = """
name: Test Scenario
steps:
  - name: Assign var
    action:
      type: assign
      target: my_var
      params:
        value: hello
"""
scenario = YamlLoader.loads(yaml_str)

print(scenario.name)       # "Test Scenario"
print(len(scenario.steps)) # 1
```

## 注意事项

- 使用 `PyYAML` 库进行解析
- 文件编码假设为 UTF-8
- 动作类型不区分大小写（内部会转换为大写）
