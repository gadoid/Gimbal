# Utils 模块

> 工具模块：提供通用工具函数。当前实现中仅有 `jsonpath.py`（轻量级 JSONPath 解析器）。

## 目录结构

```
gimbal/utils/
└── jsonpath.py  # JSONPath 解析器 + 模板变量解析
```

> 当前仓库中 `gimbal/utils/__init__.py` 不存在（仅 `jsonpath.py` 一个文件）。所有工具函数都从 `gimbal.utils.jsonpath` 直接 import。

## JSONPath 解析器

轻量级 JSON 路径解析器，**零外部依赖**（`gimbal/utils/jsonpath.py`）。

### 支持的能力

**读（`get` / `get_all`）：**
- `$.field` — 对象字段
- `$.a.b.c` — 嵌套字段
- `$.items[0]` — 正向下标
- `$.items[-1]` — 倒序下标
- `$.items[*]` — 通配，返回所有元素
- `$.items[*].name` — 通配后继续导航
- `$['key with space']` — 带空格/特殊字符的 key
- `$.items[?(@.status==200)]` — 过滤（`==` / `!=` / `>` / `>=` / `<` / `<=` / `in` / `contains`）
- `$..field` — 递归搜索（深度优先）

**写（`set_value`）：**
- 同上路径格式；路径不存在时自动创建中间节点（dict / list）

**删（`delete`）：**
- 同上路径格式

**模板变量解析：**
- `resolve_template("Bearer ${token}", ctx_vars)` → `"Bearer abc123"`

**模板变量引用扫描：**
- `find_template_var_refs(obj)` 递归扫描 Pydantic / dict / list 中的所有 `${var.name}` 引用

### 公开 API

#### get

读取第一个匹配值：

```python
def get(data: Any, path: str, default: Any = None) -> Any:
    """读取第一个匹配值。找不到返回 default。"""

# 示例
get({"a": {"b": 1}}, "$.a.b")        # → 1
get({"items": [1, 2]}, "$.items[0]")  # → 1
get({"items": [1, 2]}, "$.items[-1]") # → 2
get({}, "$.missing", "N/A")           # → "N/A"
```

#### get_all

读取所有匹配值：

```python
def get_all(data: Any, path: str) -> list[Any]:
    """读取所有匹配值，返回列表（通配/过滤/递归场景）。"""

# 示例
get_all({"items": [{"id": 1}, {"id": 2}]}, "$.items[*].id")  # → [1, 2]
get_all({"a": {"b": 1}, "c": {"b": 2}}, "$..b")             # → [1, 2]
get_all(
    {"items": [{"status": 200}, {"status": 404}]},
    "$.items[?(@.status==200)]",
)                                                          # → [{"status": 200}]
```

#### set_value

写入值（in-place + 返回根）：

```python
def set_value(data: Any, path: str, value: Any) -> Any:
    """在 data 上按路径写入 value（in-place + 返回根）。

    - 中间节点不存在时按类型自动创建（FIELD → dict，INDEX → list）
    - 不支持通配符 / 过滤写入
    """

# 示例
d = {}
set_value(d, "$.user.name", "Alice")  # d == {"user": {"name": "Alice"}}

lst = []
set_value(lst, "$.[0]", "first")      # lst == ["first"]
```

#### delete

删除值：

```python
def delete(data: Any, path: str) -> bool:
    """按路径删除字段，返回是否成功。"""

# 示例
d = {"a": {"b": 1, "c": 2}}
delete(d, "$.a.b")  # d == {"a": {"c": 2}}, returns True
```

#### exists

检查路径是否存在：

```python
def exists(data: Any, path: str) -> bool:
    """检查路径是否存在。"""

# 示例
exists({"a": 1}, "$.a")    # → True
exists({"a": 1}, "$.b")    # → False
```

#### resolve_template

模板变量解析（宽松模式）：

```python
def resolve_template(template: str, variables: dict[str, Any]) -> Any:
    """将 '${varname}' 占位符替换为 variables 中的对应值。

    - 若整个 template 就是单个占位符（如 "${token}" 或 "${auth.codfish.token}"），
      直接返回原始类型值（避免把 int/dict 强制转为字符串）。
    - 若包含多个占位符或夹杂普通文本，则做字符串替换。
    - 嵌入式 ${...} 找不到时保留原样。
    """

# 示例
resolve_template("Bearer ${token}", {"token": "abc"})  # → "Bearer abc"
resolve_template("${user_id}", {"user_id": 42})        # → 42  (int 保留)
resolve_template("${a}+${b}", {"a": 1, "b": 2})       # → "1+2"
resolve_template("${auth.codfish.token}", {"auth": {"codfish": AuthSession(...)}})
# → token 属性值
```

支持的变量路径：
- `dict` 嵌套：`variables["auth"]["codfish"]`
- 对象属性：`variables["auth"]["codfish"].token`
- Pydantic `@property`
- 点号分隔的嵌套路径：`auth.codfish.token`

#### resolve_template_strict

模板变量解析（严格模式）：

```python
def resolve_template_strict(template: str, variables: dict[str, Any]) -> Any:
    """resolve_template 的 strict 版本。

    与 resolve_template 的区别：
      - resolve_template:      嵌入式变量找不到时返回原 ${...} 字符串
      - resolve_template_strict: 嵌入式变量找不到时返回 _MISSING 哨兵
        （调用方用 is_missing(result) 检测并 fail-fast）

    关键规则：
      - key 缺失（_Missing）→ 触发 fail-fast
      - key 存在但值为 None：
        * 整体是单个 ${}   → 返回 None（合法值）
        * 嵌入式 ${}        → 渲染为空字符串 ""
    """
```

`_MISSING` 是一个模块级哨兵对象（`object()`），用 `is_missing(value)` 判断。区分"字段不存在"与"合法 None"。

#### is_template

判断是否是模板变量：

```python
def is_template(value: Any) -> bool:
    """判断 value 是否是模板变量字符串（含 ${...}）。"""
    is_template("${token}")    # → True
    is_template("Bearer abc")  # → False
```

#### is_jsonpath

判断是否是 JSONPath 表达式：

```python
def is_jsonpath(value: Any) -> bool:
    """判断 value 是否是 JSONPath 表达式（以 $ 开头）。"""
    is_jsonpath("$.data")  # → True
    is_jsonpath("token")   # → False
```

#### is_missing

判断 `_MISSING` 哨兵：

```python
def is_missing(value: Any) -> bool:
    """判断 value 是否是 _MISSING 哨兵（路径不存在）。"""
```

#### find_template_var_refs

递归扫描对象中的所有 `${...}` 模板变量引用：

```python
def find_template_var_refs(obj: Any, *, prefix: str | None = None) -> Iterator[str]:
    """递归遍历 obj，yield 所有 ${var.name} 形式的 var 引用。

    支持递归：str / dict / list / tuple / Pydantic BaseModel。
    Pydantic 模型按 `model_fields` 遍历每个字段。

    Args:
        obj: 任意 Pydantic 模型、dict、list、tuple、scalar
        prefix: 若指定，只 yield 以 "{prefix}." 开头的 var，
                并去掉前缀段。例如 prefix="auth" 遇到 ${auth.admin.token}
                → yield "admin"

    Yields:
        var 名字符串。纯 ${var} → "var"；${auth.x.token} → "auth.x.token"

    Examples:
        >>> list(find_template_var_refs({"x": "${a.b}"}))
        ['a.b']
        >>> list(find_template_var_refs({"x": "${auth.admin.token}"}, prefix="auth"))
        ['admin']
    """
```

用于"找出哪些 auth tag 被实际引用"等优化场景——避免手动逐字段 `hasattr/getattr` 链（容易漏嵌套 body / 自定义 strategy 字段）。

## 过滤表达式

支持的过滤操作符：

| 操作符 | 说明 |
| --- | --- |
| `==` / `!=` | 等于 / 不等于 |
| `>` / `>=` / `<` / `<=` | 比较 |
| `in` | 包含 |
| `contains` | 被包含 |

过滤表达式右侧值支持：字符串（带引号）、整数、浮点数、`true` / `false` / `null`、裸字符串。

```python
# 示例
$.items[?(@.status==200)]            # 过滤 status == 200 的项
$.items[?(@.count in [1,2,3])]       # 过滤 count 在列表中的项
$.items[?(@.name contains "foo")]    # 过滤 name 包含 "foo" 的项
$.items[?(@.user.id==1)]             # 支持嵌套字段 @.user.id
```

## 异常

```python
class JsonPathError(Exception):
    """路径语法或运行时错误。"""
```

`get` / `get_all` / `set_value` / `delete` / `exists` 在路径解析失败时：
- 路径错误（`JsonPathError`）→ 直接重新抛出
- 其它内部错误 → 包装为 `JsonPathError` 抛出
- `exists` 路径错误时返回 `False`

## 设计原则

1. **零依赖**: 纯 Python，无外部依赖
2. **线程安全**: 无模块级可变状态（`_MISSING` 是不可变哨兵）
3. **异常安全**: 除 `JsonPathError` 外不抛其他异常
<<<<<<< HEAD
4. **类型保留**: 整体模板返回原始类型（int/dict 等）

## 已知问题

`resolve_template` 内部的 `${}` 解析依赖 `_get_nested`（仅点号路径），与 `get` / `get_all` 暴露的完整 JSONPath 能力**不对齐**。常见遗留缺陷（不支持下标/通配/过滤、嵌入式缺失静默原样保留等）见：

[`docs/known-issues/preprocessor/template-substitution.md`](../known-issues/preprocessor/template-substitution.md)
=======
4. **类型保留**: 整体模板（`resolve_template`）返回原始类型（int / dict 等），不强制转 str
5. **in-place 修改**: `set_value` / `delete` 直接修改传入的 dict/list，同时返回修改后的对象
6. **`get` 找不到不抛**: 返回 `default`（默认 `None`），调用方无需 try/except
>>>>>>> 872479815603132e2dab0d5cb4e876c5c6fbf731
