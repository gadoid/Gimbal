# Interpolation 模块

变量插值层，实现 `${var}` 语法和 JSONPath 数据存取。

## 文件说明

### `interpolator.py`
`Interpolator` - 变量插值器：
- 将字符串中的 `${var}` 替换为实际变量值
- 支持嵌套字典和列表的递归插值

**主要方法：**
- `interpolate(text)` - 对单个字符串进行插值
- `interpolate_dict(data)` - 对字典中所有字符串进行插值
- `update_variables(vars)` - 更新变量字典

**插值规则：**
- `${var}` - 替换为 `variables["var"]` 的值
- 变量不存在时保留原字符串
- 非字符串类型直接返回原值

### `path.py`
`JsonPath` - 简化版 JSONPath 实现：
- 从嵌套数据结构中取值
- 支持路径设置

**支持语法：**
| 语法 | 说明 | 示例 |
|------|------|------|
| `key` | 获取字典键值 | `user` |
| `key.subkey` | 嵌套访问 | `user.name` |
| `key[0]` | 数组索引访问 | `items[0]` |
| `key[*].subkey` | 数组所有元素 | `users[*].name` |

**主要方法：**
- `get(data, path)` - 从 data 中获取 path 指定的值
- `set(data, path, value)` - 设置 data 中 path 的值

## 使用示例

```python
from interpolation import Interpolator, JsonPath

# 变量插值
vars = {"base_url": "https://api.example.com", "user_id": 123}
interp = Interpolator(vars)

text = "${base_url}/users/${user_id}"
result = interp.interpolate(text)
# => "https://api.example.com/users/123"

# JSONPath 取值
data = {
    "user": {
        "name": "John",
        "addresses": [
            {"city": "Beijing"},
            {"city": "Shanghai"}
        ]
    }
}

JsonPath.get(data, "user.name")           # => "John"
JsonPath.get(data, "user.addresses[0].city")  # => "Beijing"
JsonPath.get(data, "user.addresses[*].city")  # => ["Beijing", "Shanghai"]

# JSONPath 设值
JsonPath.set(data, "user.age", 30)
# data["user"]["age"] = 30
```
