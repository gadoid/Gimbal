# Examples 目录

示例文件目录，包含场景 YAML 文件示例。

## 文件说明

### `scenario.yaml`
示例场景文件，演示 TDF 框架的基本用法。

## 场景内容

```yaml
name: Example Scenario
description: An example test scenario demonstrating TDF features
tags:
  - example
  - demo

variables:
  base_url: https://api.example.com
  user_id: 12345

steps:
  - name: Assign test variable
    action:
      type: assign
      target: test_var
      params:
        value: hello_world

  - name: Extract user data
    action:
      type: extract
      target: extracted_user
      params:
        source: '{"user": {"id": 123, "name": "John"}}'
        expression: user.name

  - name: Assert extracted value
    action:
      type: assert
      params:
        actual: John
        expected: John
        operator: equals
        message: Extract user name should be John
```

## 运行示例

```bash
# 使用 CLI 运行
python run.py examples/scenario.yaml

# 或使用 Python API
from runner import TestRunner
from loader import YamlLoader

runner = TestRunner()
scenario = YamlLoader.load("examples/scenario.yaml")
context = runner.run(scenario)
```

## 扩展示例

### HTTP 请求示例

```yaml
steps:
  - name: GET User Info
    action:
      type: http
      params:
        method: GET
        url: /users/${user_id}
        headers:
          Authorization: Bearer ${token}
```

### SQL 查询示例

```yaml
steps:
  - name: Query User
    action:
      type: sql
      params:
        sql: SELECT * FROM users WHERE id = ?
        args:
          - ${user_id}
```

### 链式提取示例

```yaml
steps:
  - name: Login and Extract Token
    action:
      type: http
      params:
        method: POST
        url: /login
        body:
          username: admin
          password: ${password}

  - name: Extract Token
    action:
      type: extract
      target: auth_token
      params:
        source: ${response}  # 上一步响应
        expression: data.token

  - name: Use Token
    action:
      type: http
      params:
        method: GET
        url: /protected
        headers:
          Authorization: Bearer ${auth_token}
```
