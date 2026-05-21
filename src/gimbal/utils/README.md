# Utils 模块

工具模块，提供通用的工具函数和类。

## 模块结构

| 文件 | 说明 |
|------|------|
| `jsonpath.py` | JSON 路径解析器 |

---

## JSONPath

轻量级 JSON 路径解析器，零外部依赖。

### 支持的能力

**读 (get / get_all):**

| 语法 | 说明 |
|------|------|
| `$.field` | 对象字段 |
| `$.a.b.c` | 嵌套字段 |
| `$.items[0]` | 正向下标 |
| `$.items[-1]` | 倒序下标 |
| `$.items[*]` | 通配，返回所有元素 |
| `$.items[*].name` | 通配后继续导航 |
| `$['key with space']` | 带空格/特殊字符的 key |
| `$.items[?(@.status==200)]` | 过滤（==, !=, >, >=, <, <=, in, contains） |
| `$..field` | 递归搜索（深度优先） |

**写 (set):**

同上路径格式；路径不存在时自动创建中间节点（dict / list）

**删 (delete):**

同上路径格式

**模板变量解析:**

```python
resolve_template("Bearer ${token}", ctx_vars) → "Bearer abc123"
```

---

## 函数

### get

```python
def get(data: Any, path: str, default: Any = None) -> Any:
    """根据路径获取值，找不到返回 default。"""
    pass
```

### get_all

```python
def get_all(data: Any, path: str) -> list[Any]:
    """根据路径获取所有匹配的值。"""
    pass
```

### set

```python
def set(data: Any, path: str, value: Any) -> Any:
    """根据路径设置值，返回修改后的对象。"""
    pass
```

### delete

```python
def delete(data: Any, path: str) -> Any:
    """根据路径删除值，返回修改后的对象。"""
    pass
```

### resolve_template

```python
def resolve_template(template: str, variables: dict) -> str:
    """解析模板中的变量。"""
    pass
```

---

## 异常

```python
class JsonPathError(Exception):
    """路径语法或运行时错误。"""
```

---

## 使用示例

```python
from gimbal.utils.jsonpath import get, set, delete, resolve_template

data = {
    "users": [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25}
    ],
    "settings": {
        "theme": "dark"
    }
}

# 获取字段
name = get(data, "$.users[0].name")  # "Alice"

# 嵌套字段
theme = get(data, "$.settings.theme")  # "dark"

# 通配
all_names = get(data, "$.users[*].name")  # ["Alice", "Bob"]

# 过滤
adults = get(data, "$.users[?(@.age>=30)]")  # [{"name": "Alice", "age": 30}]

# 递归搜索
all_ages = get(data, "$..age")  # [30, 25]

# 设置值
set(data, "$.settings.theme", "light")

# 删除值
delete(data, "$.users[1]")

# 模板变量解析
token = resolve_template("Bearer ${token}", {"token": "abc123"})
# "Bearer abc123"
```

---

## 设计原则

- 纯 Python，零依赖
- 所有公开函数不抛 `JsonPathError` 以外的异常
- `get()` 找不到时返回 `default`（默认 None），不抛异常
- `set()` / `delete()` 直接修改传入的 dict/list（in-place），同时返回修改后的对象
- 线程安全（无模块级可变状态）

---

## 运行测试

```bash
python -m gimbal.utils
```
