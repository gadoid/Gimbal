# Adapters 模块

副作用适配器层，隔离所有 IO 操作，使核心逻辑可测试。

## 文件说明

### `http.py`
`HttpClient` - HTTP 客户端适配器：
- 封装 `requests` Session
- 提供 RESTful API 调用能力

**主要方法：**
- `request(method, url, ...)` - 通用请求方法
- `get(url, ...)` - GET 请求
- `post(url, ...)` - POST 请求
- `put(url, ...)` - PUT 请求
- `delete(url, ...)` - DELETE 请求
- `close()` - 关闭会话

**返回格式：**
```python
{
    "status_code": 200,
    "headers": {...},
    "body": {...},  # JSON 响应体
    "elapsed_ms": 123.45  # 响应时间（毫秒）
}
```

### `database.py`
`DbClient` - 数据库客户端适配器：
- 支持 SQLite（可扩展至其他数据库）
- 自动管理连接生命周期

**主要方法：**
- `connect()` - 建立数据库连接
- `execute(sql, params)` - 执行 SQL 查询/更新
- `close()` - 关闭连接

**返回格式：**
- SELECT 查询：返回 `list[dict]`
- INSERT/UPDATE/DELETE：返回 `list[dict]` 包含 `affected_rows`

## 设计原则

1. **隔离 IO** - 所有对外交互通过适配器进行
2. **可替换** - 同一接口可切换不同实现（Mock/Real）
3. **可测试** - 核心逻辑无需真实网络或数据库

## 使用示例

```python
from adapters import HttpClient, DbClient

# HTTP 请求
http = HttpClient(base_url="https://api.example.com")
response = http.post("/users", body={"name": "John"})
print(response["body"])
http.close()

# 数据库操作
db = DbClient("sqlite:///test.db")
results = db.execute("SELECT * FROM users WHERE id = ?", (1,))
db.close()
```
