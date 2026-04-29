# Handlers 模块

动作处理器层，每种动作类型对应一个处理器实现。

## 文件说明

### `base.py`
`ActionHandler` - 动作处理器抽象基类：
- 定义 `execute(action, context)` 接口
- 所有具体处理器需实现此接口

### `sql.py`
`SqlHandler` - SQL 执行处理器：
- 从 `action.params` 获取 SQL 语句
- 通过数据库适配器执行查询
- 返回查询结果

**参数：**
- `sql` - SQL 语句字符串

### `extract.py`
`ExtractHandler` - 数据提取处理器：
- 从 `source` 中使用 JSONPath 表达式提取数据
- 将结果存储到 `target` 变量名

**参数：**
- `source` - 源数据（JSON 字符串或字典）
- `expression` - JSONPath 表达式，如 `user.name`、`data[0].id`
- `target` - 目标变量名

### `assign.py`
`AssignHandler` - 变量赋值处理器：
- 将 `value` 赋值给 `target` 变量

**参数：**
- `value` - 要赋值的值
- `target` - 目标变量名

### `assert_.py`
`AssertHandler` - 断言处理器：
- 执行断言验证，记录结果到上下文
- 断言失败时抛出 `AssertionError`

**支持的 operator：**
- `equals` - 相等比较
- `not_equals` - 不等比较
- `contains` - 包含检查
- `greater_than` - 大于比较
- `less_than` - 小于比较

**参数：**
- `actual` - 实际值
- `expected` - 期望值
- `operator` - 比较操作符（默认 `equals`）
- `message` - 断言消息

## 使用示例

```python
from handlers import SqlHandler, ExtractHandler, AssignHandler, AssertHandler

# 赋值
assign_handler = AssignHandler()
assign_handler.execute(
    Action(type=ActionType.ASSIGN, params={"value": "test"}, target="var"),
    context
)

# 提取
extract_handler = ExtractHandler()
extract_handler.execute(
    Action(type=ActionType.EXTRACT, params={"source": '{"name": "John"}', "expression": "name"}, target="user_name"),
    context
)

# 断言
assert_handler = AssertHandler()
assert_handler.execute(
    Action(type=ActionType.ASSERT, params={"actual": 200, "expected": 200, "operator": "equals"}),
    context
)
```
