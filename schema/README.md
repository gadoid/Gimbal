# Schema 模块

静态描述层，使用 Pydantic 定义测试框架的核心数据模型。

## 文件说明

### `states.py`
定义 `StepState` 枚举，表示测试步骤的执行状态：
- `PENDING` - 等待执行
- `RUNNING` - 执行中
- `PASSED` - 执行成功
- `FAILED` - 执行失败
- `SKIPPED` - 已跳过

### `actions.py`
定义动作类型和动作基类：
- `ActionType` - 支持的动作类型枚举（HTTP、SQL、EXTRACT、ASSIGN、ASSERT）
- `Action` - 动作 Pydantic 模型，包含 `type`、`params`、`target` 字段

### `step.py`
定义测试步骤和场景模型：
- `Step` - 单个测试步骤，包含名称、动作、状态、重试次数、超时时间
- `Scenario` - 测试场景，包含名称、描述、步骤列表、变量、标签

### `api.py`
定义 API 规格模型：
- `RequestSpec` - HTTP 请求规格（方法、URL、头、参数、请求体、超时）
- `ApiSpec` - API 规格，包含请求规格和期望的响应状态/内容

## 使用示例

```python
from schema import Step, Scenario, Action, ActionType, StepState

step = Step(
    name="登录接口",
    action=Action(type=ActionType.HTTP, params={"method": "POST", "url": "/api/login"})
)

scenario = Scenario(
    name="用户登录流程",
    steps=[step],
    variables={"base_url": "https://api.example.com"}
)
```
