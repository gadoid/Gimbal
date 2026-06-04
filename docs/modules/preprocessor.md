# Preprocessor 模块

> 预处理器模块：Scenario 执行前完成认证、模板展开、base_url 提取等准备工作

## 目录结构

```
gimbal/preprocessor/
├── __init__.py
└── scenario_preprocessor.py  # ScenarioPreprocessor（核心入口；含 Phase 0 物化、Phase 1 认证、Phase 2~4 模板/URL 解析）
```

> 旧 `preprocessor/hooks/` 子目录（ref_resolver / cycle_detector / completeness_checker / schema_validator）
> 与 `pipeline.py` / `hook_base.py` / `cache.py` 等占位文件已清理——之前是 hook 管线风格的脚手架，
> 实际逻辑由 `ScenarioPreprocessor` 内部阶段化承担，引用物化由 [`AssetMaterializer`](repository.md#assetmaterializer-结构化引用物化) 负责。

## 核心组件

### ScenarioPreprocessor

```python
class ScenarioPreprocessor:
    """Scenario 预处理器。

    用法：
        pre = ScenarioPreprocessor(scenario_schema, bootstrap_config, auth_registry)
        resolved_steps, base_url = pre.run()
        # resolved_steps 中所有 ${} 模板已展开
        # base_url 供 StepRunner 构造完整 URL
    """

    def __init__(
        self,
        scenario_schema: "Scenario",
        bootstrap_config: "BootstrapConfig",
        auth_registry: Optional["AuthRegistry"] = None,    # Issue 1 新增
        asset_store: Optional["AssetStore"] = None,        # Phase 0 新增
    ) -> None:
        # 缺省时构造一个空 registry（仅当 scenario 不需要认证时安全）
        if auth_registry is None:
            from gimbal.auth.registry import AuthRegistry
            auth_registry = AuthRegistry()
        self._auth_registry = auth_registry
        self._asset_store = asset_store

    def run(self) -> tuple[list["StepUnion"], str]:
        """执行完整预处理，返回 (resolved_steps, base_url)。

        步骤：
          0. 引用物化（Phase 0：asset_store 不为 None 时递归还原 Ref 节点）
          1. 认证（填充 token 到 AuthRegistry）
          2. 构建查询根对象
          3. 批量展开 steps 模板
          4. 提取 base_url
        """
```

## 职责

### 0. 引用物化（Phase 0，asset 仓库引用还原）

在所有其他阶段**之前**完成对 scenario 中 `Ref` 节点的结构化还原。

- 调用方传入 `AssetStore`（由 `ScenarioRunner` 持有）
- 通过 [`AssetMaterializer`](../modules/repository.md#assetmaterializer-结构化引用物化) 递归识别 `RefBase` 子类（含 `StepRef` / `ApiRef` / `RequestRef` / `StrategyRef` 以及通用内联 `Ref`），从仓库拉取并替换为真实数据类对象
- 递归到不动点（fixed-point），自动处理传递闭包
- 显式环检测 + `max_depth` 兜底 → `AssetCycleError`
- `asset_store is None` 时此阶段整体跳过（保持向后兼容）

详见 [repository.md](../modules/repository.md#assetmaterializer-结构化引用物化)。

### 1. 认证（Issue 1 修复后）

**从 `scenario.config.users` 构造 `AuthSession` 并触发认证，token 写入 `AuthRegistry`**（**不再**写入 `BootstrapConfig.users`——该字段已删除）：

```python
def _setup_auth(self) -> None:
    auth_dict = getattr(self._schema.config, "users", None) or {}
    if not auth_dict:
        logger.debug("[Preprocessor] 无 users，跳过认证")
        return

    for tag, entry in auth_dict.items():
        if isinstance(entry, AuthSession):
            self._authenticate_one(tag, entry)
        elif isinstance(entry, dict):
            self._authenticate_one(tag, AuthSession(**entry))
        else:
            logger.warning(...)

def _authenticate_one(self, tag: str, auth_session) -> None:
    self._auth_registry.set(tag, auth_session)        # 写入 registry
    auth_manager = AuthManager(self._auth_registry)    # 兼容：传 registry
    auth_manager.get_auth(tag)
```

### 2. 构建查询根

两段查询根对象，优先级（高 → 低）：
- `scenario.config.services` > `bootstrap.services`
- `AuthRegistry.snapshot()`（含已认证的 `AuthSession`）

```python
def _build_resolve_root(self) -> dict[str, Any]:
    """构建两段查询根对象。

    不做 model_dump()，直接持有对象引用：
      - AuthSession.token 是普通字段，认证后已填充
      - AuthSession.auth_header 是 @property，实时计算
      - token 刷新后无需重建 root，下次模板解析自动拿到新值
    """
    root: dict[str, Any] = {}

    # service
    if self._cfg.services:
        root["service"] = dict(self._cfg.services)
    else:
        root["service"] = {}
    service_dict = getattr(self._schema.config, "services", None) or {}
    if service_dict:
        root["service"].update(service_dict)

    # auth（snapshot 返回浅拷贝）
    root["auth"] = self._auth_registry.snapshot()

    return root
```

### 3. 模板展开

批量展开 steps 中的模板字段：
- `${auth.tag.token}` → 实际 token 值
- `${auth.tag.auth_header}` → 完整 Authorization 头
- `${service.name}` → 服务 URL
- `${var.key}` → context 中的变量

```python
def _resolve_steps(self, root: dict) -> list["StepUnion"]:
    """遍历所有 steps，对每个 Step 做模板展开，返回新列表。

    StepRef 不做展开（未解析的引用，跳过）。
    """

def _resolve_value(self, value, root) -> Any:
    """解析单个值中的 ${} 模板。

    - 非字符串 / 不含模板 → 原样返回
    - 整体是单个 ${} → 保留原始类型（int / dict / AuthSession）
    - 嵌入式 ${} → 字符串拼接
    - 解析失败（变量不存在） → 返回原始字符串 + warning
    """

def _resolve_nested(self, data, root) -> Any:
    """递归展开嵌套结构（dict / list）中的所有模板字段。"""
```

### 4. 提取 base_url

```python
def _pick_base_url(self) -> str:
    """从 services 取第一个 URL 作为 base_url。

    优先 scenario.config.services，找不到再查 bootstrap.services。
    """
```

### 模板保留类型

`${auth.admin.auth_header}` 这种**整体是单个 `${}`** 的字段，**保留原始类型**——`AuthSession` 不会被 dump 成 dict，`@property`（如 `auth_header`）在每次访问时实时计算。

## 辅助模块

### pipeline.py
通用预处理管道（链式调用 hook）。

### hook_base.py
预处理器钩子基类。

### cache.py
预处理结果缓存（按 scenario hash）。

## 设计原则

1. **无副作用**：预处理器不写入任何 Context，不触发事件。
2. **认证集中**：认证副作用（写 `AuthRegistry`）在此集中，后续执行链只读。
3. **Immutable-safe**：返回新的 step 列表，原始 schema 不变。
4. **两层查询**：scenario 级 > bootstrap 级（同名 key scenario 级覆盖）。
5. **Token 自动刷新**：`AuthManager` 在执行期按需触发刷新，预处理不负责。
6. **配置/状态分离**：认证结果写入 `AuthRegistry`（运行期容器），不污染 `BootstrapConfig`（frozen）。
7. **类型保留**：单 `${}` 整体保留对象引用而非 dump，token 刷新后自动可见。
