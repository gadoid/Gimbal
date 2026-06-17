# Preprocessor 模块

> 预处理器模块：Scenario 执行前完成引用物化、认证、模板展开、base_url 提取等准备工作

## 目录结构

```
gimbal/preprocessor/
├── __init__.py
└── scenario_preprocessor.py  # ScenarioPreprocessor（核心入口；含 Phase 0 物化、Phase 1 认证、Phase 2~4 模板/URL 解析）
```

> 旧 `preprocessor/hooks/` 子目录（ref_resolver / cycle_detector / completeness_checker / schema_validator）
> 与 `pipeline.py` / `hook_base.py` / `cache.py` 等占位文件已清理——之前是 hook 管线风格的脚手架，
> 实际逻辑由 `ScenarioPreprocessor` 内部阶段化承担，引用物化由 [`AssetMaterializer`](core.md#assetmaterializer内层递归还原-ref--数据类对象) 负责。

> **无任何 stub 文件**：本模块已精简到单文件实现。

## 核心组件

### ScenarioPreprocessor

```python
class ScenarioPreprocessor:
    """Scenario 预处理器。

    用法：
        pre = ScenarioPreprocessor(
            scenario_schema=scenario,
            bootstrap_config=cfg,
            auth_registry=auth_registry,
            asset_store=asset_store,         # None 时跳过 Phase 0
        )
        resolved_steps, base_url = pre.run()
        # resolved_steps 中所有 ${} 模板已展开
        # base_url 供 StepRunner 构造完整 URL
    """

    def __init__(
        self,
        scenario_schema: "Scenario",
        bootstrap_config: "BootstrapConfig",
        auth_registry: Optional["AuthRegistry"] = None,    # 认证目标容器
        asset_store: Optional["AssetStore"] = None,        # Phase 0 注入
    ) -> None:
        # 缺省时构造一个空 registry（仅当 scenario 不需要认证时安全）
        if auth_registry is None:
            from gimbal.auth.registry import AuthRegistry
            auth_registry = AuthRegistry()
        self._schema = scenario_schema
        self._cfg = bootstrap_config
        self._auth_registry = auth_registry
        self._asset_store = asset_store

    def run(self) -> tuple[list["StepUnion"], str]:
        """执行完整预处理入口。

        步骤：
          0. 引用物化（asset_store 不为 None 时；递归替换 Ref 节点）
          1. 认证（填充 token 到 AuthRegistry）
          2. 构建查询根对象（两段优先级：scenario > bootstrap）
          3. 批量展开 steps 模板（${auth.*} / ${service.*} / ${var.*}）
          4. 提取 base_url

        返回:
            (resolved_steps, base_url) 元组
        """
```

## 五段处理流程（Resolve Phases）

### Phase 0：引用物化（资产仓库引用还原）

在所有其他阶段**之前**完成对 scenario 中 `Ref` 节点的结构化还原。

- 调用方传入 `AssetStore`（由 `ScenarioRunner` 持有）
- 通过 [`AssetMaterializer`](core.md#assetmaterializer内层递归还原-ref--数据类对象) 递归识别 `RefBase` 子类（含 `StepRef` / `ApiRef` / `RequestRef` / `StrategyRef` 以及通用内联 `Ref`），从仓库拉取并替换为真实数据类对象
- 递归到不动点（fixed-point），自动处理传递闭包
- 显式环检测 + `max_depth=8` 兜底 → `AssetCycleError`
- `asset_store is None` 时此阶段整体跳过（保持向后兼容）

```python
def _materialize_refs(self) -> None:
    if self._asset_store is None:
        logger.debug("[Preprocessor] 未提供 asset_store，跳过 Phase 0 物化")
        return

    from gimbal.core.asset_materializer import AssetMaterializer
    materializer = AssetMaterializer(self._asset_store)
    # 物化整个 scenario 图（包括 steps、api、request、strategy、body）
    materializer.materialize(self._schema)
```

注意：
- 直接修改 `self._schema`（Pydantic v2 默认非 frozen 即可 setattr）
- 物化后的 `scenario.steps` 中应该全部是 `Step`，不再含 `StepRef`
- 物化后 step 内 `body` 等 free-form dict 中的内联 Ref 也会被替换

### Phase 1：认证

**从 `scenario.config.users` 构造 `AuthSession` 并触发认证，token 写入 `AuthRegistry`**（**不再**写入 `BootstrapConfig.users`——该字段已删除）：

```python
def _setup_auth(self) -> None:
    """从 scenario.config.users 构造 AuthSession 并触发认证。

    回滚 B4 → template 引用的 user 在 preprocess 阶段登录（eager）。
    原因：模板替换（_resolve_steps）依赖 token 字段值——
    模板 ${auth.<tag>.token} 必须解析为真实 token 字符串，而非 lazy 模式的 None。
    """
    auth_dict = getattr(self._schema.config, "users", None) or {}
    if not auth_dict:
        logger.debug("[Preprocessor] 无 users，跳过认证")
        return

    # 1. 先把 AuthSession 注入 registry
    for tag, entry in auth_dict.items():
        if isinstance(entry, AuthSession):
            self._auth_registry.set(tag, entry)
        elif isinstance(entry, dict):
            self._auth_registry.set(tag, AuthSession(**entry))
        else:
            logger.warning(...)

    # 2. 扫描模板找出实际引用的 auth tags
    #    用公共 helper 递归扫描，自动覆盖嵌套 body / 自定义 strategy 字段
    from gimbal.utils.jsonpath import find_template_var_refs
    referenced_tags: set[str] = set()
    for step_union in self._schema.steps:
        for tag in find_template_var_refs(step_union, prefix="auth"):
            referenced_tags.add(tag)

    # 3. 登录：只登录模板引用的（未引用的 skip）
    auth_manager = AuthManager(self._auth_registry)
    for tag in auth_dict:
        if tag in referenced_tags:
            auth_manager.get_auth(tag)
```

要点：
- **eager 登录**（回滚 B4）：所有被模板引用的 user 都在预处理阶段登录，避免执行期 lazy 模式返回 None
- **按需登录**：未在模板中引用的 user 跳过，节省 25min startup（修复前）
- **失败传播**：认证失败抛异常上抛，不静默吞掉

### Phase 2：构建查询根

两段查询根对象，优先级（高 → 低）：

| 命名空间 | 高优先级 | 低优先级 |
|----------|----------|----------|
| `service` | `scenario.config.services` | `bootstrap.services` |
| `auth` | `AuthRegistry.snapshot()` | — |
| `var` | `BootstrapConfig.vars`（CLI --var / --var-file 注入） | — |

```python
def _build_resolve_root(self) -> dict[str, Any]:
    """构建两段查询根对象。

    不做 model_dump()，直接持有对象引用：
      - AuthSession.token 是普通字段，认证后已填充
      - AuthSession.auth_header 是 @property，实时计算
      - token 刷新后无需重建 root，下次模板解析自动拿到新值
    """
    root: dict[str, Any] = {}

    # service —— 先 bootstrap 级，再用 scenario 级覆盖
    if self._cfg.services:
        root["service"] = dict(self._cfg.services)
    else:
        root["service"] = {}
    service_dict = getattr(self._schema.config, "services", None) or {}
    if service_dict:
        root["service"].update(service_dict)

    # auth（snapshot 返回浅拷贝）
    root["auth"] = self._auth_registry.snapshot()

    # var（修复 #52 完整链路：CLI --var / --var-file 注入的 KV）
    if self._cfg.vars:
        root["var"] = dict(self._cfg.vars)

    return root
```

### Phase 3：批量展开 steps 模板

```python
def _resolve_steps(self, root: dict) -> list["StepUnion"]:
    """遍历所有 steps，对每个 Step 做模板展开，返回新列表。

    StepRef 不做展开（未解析的引用，跳过）。
    """
    resolved: list[Any] = []
    for idx, step_union in enumerate(self._schema.steps):
        if not hasattr(step_union, "api"):
            # StepRef，原样保留
            logger.debug("[Preprocessor] step[{}] 是 StepRef，跳过展开", idx)
            resolved.append(step_union)
            continue
        resolved.append(self._resolve_step(step_union, root, idx))
    return resolved
```

四个子解析阶段：

#### Phase 3.1：Api 解析（`_resolve_api`）

```python
def _resolve_api(self, api, root: dict):
    """展开 Api 中的模板字段：解析 path 和 headers 中的 ${} 占位符；
    若任一模板变量缺失则抛 ValueError（fail-fast）。
    """
    # ApiRef 原样返回
    if isinstance(api, ApiRef):
        return api

    # 修复 B5：先解析所有 header；记录哪些解析失败
    resolved_headers = {}
    missing_headers = []
    for k, v in (api.headers or {}).items():
        resolved = self._resolve_value(v, root)
        if resolved is None:
            missing_headers.append(k)
        else:
            resolved_headers[k] = resolved

    if missing_headers:
        # 修复 B5：header 模板变量未找到时报错，不静默丢弃
        raise ValueError(
            f"[Preprocessor] api header 模板变量未找到, header 缺失: {missing_headers}"
        )

    # path 也必须能解析
    resolved_path = self._resolve_value(api.path, root)
    if resolved_path is None:
        raise ValueError(f"[Preprocessor] api.path 模板变量未找到: {api.path!r}")

    return Api(kind=api.kind, service=api.service, method=api.method,
               path=resolved_path, headers=resolved_headers, timeout=api.timeout)
```

#### Phase 3.2：Request 解析（`_resolve_request`）

```python
def _resolve_request(self, request, root: dict):
    """展开 Request 中的模板字段：递归解析 body 嵌套结构中的所有 ${} 占位符。"""
    if isinstance(request, RequestRef):
        return request
    return Request(
        kind=request.kind,
        body=self._resolve_nested(request.body or {}, root),
    )
```

#### Phase 3.3：Strategy 解析（`_resolve_strategy`）

按 strategy 类型分派：

```python
def _resolve_strategy(self, strategy, root: dict):
    """展开单条策略（Extract/Assign/Assertion）的模板字段，模板变量缺失时 fail-fast。"""
    if isinstance(strategy, StrategyRef):
        return strategy

    base = self._base_strategy_fields(strategy)
    owner = f"{type(strategy).__name__}#{strategy.name or '?'}"

    if isinstance(strategy, Extract):
        return Extract(
            **base,
            expression=self._resolve_or_fail(strategy.expression, root, owner=owner, field="expression"),
            target=strategy.target, scope=strategy.scope,
            default=self._resolve_or_fail(strategy.default, root, owner=owner, field="default"),
            required=strategy.required,
        )
    if isinstance(strategy, Assign):
        return Assign(
            **base,
            source=self._resolve_or_fail(strategy.source, root, owner=owner, field="source"),
            target=strategy.target, scope=strategy.scope,
            default=self._resolve_or_fail(strategy.default, root, owner=owner, field="default"),
            required=strategy.required,
        )
    if isinstance(strategy, Assertion):
        return Assertion(
            **base,
            target=self._resolve_or_fail(strategy.target, root, owner=owner, field="target"),
            operator=strategy.operator,
            expected=self._resolve_or_fail(strategy.expected, root, owner=owner, field="expected"),
            message=strategy.message, soft=strategy.soft,
        )
    # 未知策略类型，原样返回
    return strategy
```

#### Phase 3.4：嵌套结构解析（`_resolve_nested`）

```python
def _resolve_nested(self, data: Any, root: dict) -> Any:
    """递归展开嵌套结构（dict / list）中的所有模板字段。

    dict → 递归每个 value
    list → 递归每个 item
    scalar → 走 _resolve_value
    """
    if isinstance(data, dict):
        return {k: self._resolve_nested(v, root) for k, v in data.items()}
    if isinstance(data, list):
        return [self._resolve_nested(item, root) for item in data]
    return self._resolve_value(data, root)
```

#### 单值模板解析（核心辅助）

```python
def _resolve_value(self, value, root) -> Any:
    """解析单个值中的 ${} 模板。
    - 非字符串 / 不含模板 → 原样返回
    - 整体是单个 ${} → 保留原始类型（int / dict / AuthSession）
    - 嵌入式 ${} → 字符串拼接
    - 解析失败（变量不存在） → 返回 _Missing 哨兵（修复 B5 + Fix 3）
    - 合法 None 值（key 存在但值为 None） → 正常返回 None / 空串

    Fix 3 修正：
      区分"路径不存在"（_Missing，触发 fail-fast）与"合法 None 值"
      （key 存在但值为 None，渲染为空串 / 返回 None）。
    """

def _resolve_or_fail(self, value, root, *, owner: str, field: str) -> Any:
    """解析模板值；缺失则抛 ValueError（fail-fast），与 _resolve_api 一致。
    
    注意：必须直接调用 resolve_template_strict，不能走 _resolve_value 包装，
    否则 _resolve_value 会把 _MISSING 折叠成 None，与"合法 None 值"混淆，误报 fail-fast。
    """
```

模板格式支持：
- `${auth.tag.token}` → 实际 token 值
- `${auth.tag.auth_header}` → 完整 Authorization 头（`AuthSession` 实时计算）
- `${service.name}` → 服务 URL
- `${var.key}` → CLI 注入的变量
- 嵌入式 `${}` → 字符串拼接

### Phase 4：提取 base_url

```python
def _pick_base_url(self) -> str:
    """按 step 实际引用的 service 提取 base_url（修复 B1）。

    解析策略：
      1. 收集所有 step 引用了哪些 service key
      2. 如果只有一个 service 被引用：用它（精确匹配）
      3. 如果多个 service 被引用：当前架构只支持一个 base_url per scenario，
         取第一个并 warn（让用户知道是 multi-service 降级）
      4. 如果 step 未引用任何 service：fallback 到 services dict 的第一个（向后兼容）
      5. 优先取 scenario.config.services，找不到再查 bootstrap.services
    """
```

要点：
- 修复 B1：避免"静默错路由"——最坏情况是 warn 而非 silent misroute
- 修复 #6：未找到时使用空字符串，触发 error 报告而非空字符串拼接

## 模板保留类型

`${auth.admin.auth_header}` 这种**整体是单个 `${}`** 的字段，**保留原始类型**——`AuthSession` 不会被 dump 成 dict，`@property`（如 `auth_header`）在每次访问时实时计算。

## 异常传播

| 异常 | 触发条件 |
|------|----------|
| `AssetMaterializationError` | Phase 0：pull 失败 / 反序列化失败 / Ref 格式非法 |
| `AssetCycleError` | Phase 0：引用图出现环 / 嵌套超过 `max_depth=8` |
| `AuthError` / `AuthLoginFailed` | Phase 1：登录失败 |
| `ValueError` | Phase 3：模板变量缺失（api header / api.path / strategy.expression 等） |

## 设计原则

1. **无副作用**（除认证）：预处理器不写入任何 Context，不触发事件；唯一副作用是把 AuthSession 写入 AuthRegistry。
2. **认证集中**：认证副作用（写 `AuthRegistry`）在此集中，后续执行链只读。
3. **Immutable-safe**：返回新的 step 列表，原始 schema 不变。
4. **两层查询**：scenario 级 > bootstrap 级（同名 key scenario 级覆盖）。
5. **Token 自动刷新**：`AuthManager` 在执行期按需触发刷新，预处理不负责。
6. **配置/状态分离**：认证结果写入 `AuthRegistry`（运行期容器），不污染 `BootstrapConfig`（frozen）。
7. **类型保留**：单 `${}` 整体保留对象引用而非 dump，token 刷新后自动可见。
8. **fail-fast**：模板变量缺失时立即抛 `ValueError`，避免执行期 `expected=None` 这类误导性失败信息。
9. **按需认证**：未在模板中引用的 user 跳过登录，节省 startup 时间。
10. **物化前置**：引用物化（Phase 0）必须在认证/模板替换之前完成，否则执行器会碰到未解析的 Ref 节点。
