# Preprocessor 模块

> 预处理器模块，在执行前完成认证、模板展开等准备工作

## 目录结构

```
gimbal/preprocessor/
├── __init__.py
├── scenario_preprocessor.py  # ScenarioPreprocessor
├── pipeline.py               # 预处理管道
├── hook_base.py              # 预处理器钩子基类
├── cache.py                  # 预处理缓存
└── hooks/                    # 内置钩子
    ├── __init__.py
    ├── ref_resolver.py       # 引用解析
    ├── cycle_detector.py     # 循环依赖检测
    ├── completeness_checker.py # 完整性检查
    └── schema_validator.py   # Schema 验证
```

## 核心组件

### ScenarioPreprocessor

Scenario 预处理器，在执行链进入 StepRunner 之前完成所有准备工作：

```python
class ScenarioPreprocessor:
    """Scenario 预处理器"""

    def run(self) -> tuple[list[StepUnion], str]:
        """执行完整预处理，返回 (resolved_steps, base_url)"""
        # 1. 认证（填充 token 到 users）
        # 2. 构建查询根对象
        # 3. 批量展开 steps 模板
        # 4. 提取 base_url
```

## 职责

### 1. 认证

```python
def _setup_auth(self) -> None:
    """从 scenario.config.users 构造 AuthSession 并触发认证"""
    # users 可能包含多个认证入口（tag → {...}）
    for tag, entry in auth_dict.items():
        auth_session = AuthSession(**entry)
        self._cfg.users[tag] = auth_session
        auth_manager = AuthManager(self._cfg)
        auth_manager.get_auth(tag)
```

### 2. 构建查询根

两段查询根对象，优先级（高 → 低）：
- `scenario.config.services` > `bootstrap.services`
- `bootstrap.users`（含已认证的 AuthSession）

```python
def _build_resolve_root(self) -> dict[str, Any]:
    """构建两段查询根对象"""
    root = {}

    # 先放 bootstrap 级（低优先级）
    if self._cfg.services:
        root["service"] = dict(self._cfg.services)

    # scenario 级覆盖（高优先级）
    service_dict = getattr(self._schema.config, "services", None) or {}
    if service_dict:
        root["service"].update(service_dict)

    # users 已包含刚认证好的 AuthSession 对象
    root["auth"] = self._cfg.users

    return root
```

### 3. 模板展开

批量展开 steps 中的模板字段：
- `${auth.tag.token}` → 实际 token 值
- `${service.name}` → 服务 URL
- `${var.key}` → context 中的变量

```python
def _resolve_steps(self, root: dict[str, Any]) -> list[StepUnion]:
    """遍历所有 steps，对每个 Step 做模板展开"""
    resolved = []
    for idx, step_union in enumerate(self._schema.steps):
        if not hasattr(step_union, "api"):
            # StepRef，原样保留
            resolved.append(step_union)
            continue
        resolved.append(self._resolve_step(step_union, root, idx))
    return resolved
```

### 4. 提取 base_url

```python
def _pick_base_url(self) -> str:
    """从 services 取第一个 URL 作为 base_url"""
    sd = getattr(self._schema.config, "services", None) or {}
    if sd:
        return next(iter(sd.values()), "")

    if self._cfg.services:
        return next(iter(self._cfg.services.values()), "")

    return ""
```

## 预处理管道 Hook

### RefResolver

解析 `$ref` 引用：

```python
class RefResolver:
    """引用解析器"""
    ...
```

### CycleDetector

检测循环依赖：

```python
class CycleDetector:
    """循环依赖检测器"""
    ...
```

### CompletenessChecker

检查 Schema 完整性：

```python
class CompletenessChecker:
    """完整性检查器"""
    ...
```

### SchemaValidator

Pydantic Schema 验证：

```python
class SchemaValidator:
    """Schema 验证器"""
    ...
```

## 设计原则

1. **无副作用**: 预处理器不写入任何 Context，不触发事件
2. **认证集中**: 认证副作用在此集中，后续执行链只读
3. **Immutable-safe**: 返回新的 step 列表，原始 schema 不变
4. **两层查询**: scenario 级 > bootstrap 级（同名 key scenario 级覆盖）
5. **Token 自动刷新**: AuthManager 在执行期按需触发刷新