# Utils 模块

> 工具模块，提供通用工具函数

## 目录结构

```
gimbal/utils/
└── jsonpath.py  # JSONPath 解析器
```

## JSONPath 解析器

轻量级 JSON 路径解析器，零外部依赖。

### 支持的能力

**读 (get / get_all):**
- `$.field` — 对象字段
- `$.a.b.c` — 嵌套字段
- `$.items[0]` — 正向下标
- `$.items[-1]` — 倒序下标
- `$.items[*]` — 通配，返回所有元素
- `$.items[*].name` — 通配后继续导航
- `$['key with space']` — 带空格/特殊字符的 key
- `$.items[?(@.status==200)]` — 过滤
- `$..field` — 递归搜索（深度优先）

**写 (set):**
- 同上路径格式；路径不存在时自动创建中间节点

**删 (delete):**
- 同上路径格式

**模板变量解析:**
- `resolve_template("Bearer ${token}", ctx_vars)` → `"Bearer abc123"`

## 公开 API

### get

读取第一个匹配值：

```python
def get(data: Any, path: str, default: Any = None) -> Any:
    """读取第一个匹配值。找不到返回 default。"""

# 示例
get({"a": {"b": 1}}, "$.a.b")        # → 1
get({"items": [1, 2]}, "$.items[0]")  # → 1
get({}, "$.missing", "N/A")           # → "N/A"
```

### get_all

读取所有匹配值：

```python
def get_all(data: Any, path: str) -> list[Any]:
    """读取所有匹配值，返回列表（通配/过滤场景）。"""

# 示例
get_all({"items": [{"id": 1}, {"id": 2}]}, "$.items[*].id")  # → [1, 2]
```

### set_value

写入值：

```python
def set_value(data: Any, path: str, value: Any) -> Any:
    """在 data 上按路径写入 value（in-place + 返回根）。"""

# 示例
d = {}
set_value(d, "$.user.name", "Alice")  # d == {"user": {"name": "Alice"}}
```

### delete

删除值：

```python
def delete(data: Any, path: str) -> bool:
    """按路径删除字段，返回是否成功。"""

# 示例
d = {"a": {"b": 1, "c": 2}}
delete(d, "$.a.b")  # d == {"a": {"c": 2}}, returns True
```

### exists

检查路径是否存在：

```python
def exists(data: Any, path: str) -> bool:
    """检查路径是否存在。"""

# 示例
exists({"a": 1}, "$.a")    # → True
exists({"a": 1}, "$.b")    # → False
```

### resolve_template

模板变量解析：

```python
def resolve_template(template: str, variables: dict[str, Any]) -> Any:
    """将 '${varname}' 占位符替换为 variables 中的对应值。"""

# 示例
resolve_template("Bearer ${token}", {"token": "abc"})  # → "Bearer abc"
resolve_template("${user_id}", {"user_id": 42})        # → 42 (int 保留)
resolve_template("${a}+${b}", {"a": 1, "b": 2})       # → "1+2"
```

### is_template

判断是否是模板变量：

```python
def is_template(value: Any) -> bool:
    """判断 value 是否是模板变量字符串（含 ${...}）。"""
    is_template("${token}")  # → True
    is_template("Bearer abc")  # → False
```

### is_jsonpath

判断是否是 JSONPath 表达式：

```python
def is_jsonpath(value: Any) -> bool:
    """判断 value 是否是 JSONPath 表达式（以 $ 开头）。"""
    is_jsonpath("$.data")  # → True
    is_jsonpath("token")  # → False
```

## 过滤表达式

支持的过滤操作符：
- `==` / `!=` — 等于/不等于
- `>` / `>=` / `<` / `<=` — 比较
- `in` — 包含
- `contains` — 被包含

```python
# 示例
$.items[?(@.status==200)]    # 过滤 status == 200 的项
$.items[?(@.count in [1,2,3])]  # 过滤 count 在列表中的项
```

## 设计原则

1. **零依赖**: 纯 Python，无外部依赖
2. **线程安全**: 无模块级可变状态
3. **异常安全**: 除 `JsonPathError` 外不抛其他异常
4. **类型保留**: 整体模板返回原始类型（int/dict 等）