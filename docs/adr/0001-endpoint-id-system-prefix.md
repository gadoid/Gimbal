# ADR 0001:EndpointSpec.id 必须以 system 字段作为 prefix

## 状态

已实装 / Accepted。

实装 commit 见 [Commit 1] 起的 7 个 commit 链。

## 背景

plate 作为 API 契约 / 测试编排服务,核心数据模型是 `EndpointSpec`,
其 `id` 字段是对外暴露的稳定标识符(用例导出、查询 key、跨系统引用都用它)。

目前的 `id` 格式是字符串,如 `"fin.audit.audit_page"`,但**没有任何契约约束**
`id` 与 `system` 字段的对应关系。具体到现有 fin 系统的 18 个 endpoint,
约定俗成 `id.startswith("fin.")` 与 `system="fin"` 配套,
但这条约定仅靠人工维护,无机器校验。

这导致两个问题:

1. **客户系统反查归属必须先拉 system 列表**:拿到一个 id 后,
   要先调用 `list_systems()` / 缓存系统表,才能反查 `id.split(".", 1)[0]` 是否在表中。
   这条 discover 路径在所有客户系统都要重复实现。
2. **契约不一致无人发现**:把某个 endpoint 的 `system` 改成 `"finance"` 但忘记改 id,
   或反之,服务仍正常启动,运行时静默错误。

## 决策

**`EndpointSpec.id` 必须以 `f"{system}."` 作为前缀**。
约束点在 schema 层 `EndpointSpec._validate_integrity` 的 model_validator:

```python
if not self.id.startswith(f"{self.system}."):
    raise ValueError(
        f"EndpointSpec.id={self.id!r} 必须以 system 字段 "
        f"'{self.system}' 作为 prefix,"
        f"完整期望 prefix='{self.system}.'"
    )
```

由此引出:

- **FIN_SYSTEM = "fin"**:作为 `system` 取值,也是所有 fin endpoint id 的 prefix。
- **http/app.py lifespan 自检**:服务启动时检查
  `all(ep.system == FIN_SYSTEM for ep in list_endpoints())`,
  防止"系统级常量被改而 endpoint 文件忘改"或反之。
- **`system_info.py` 是常量的 single source of truth**,
  保证 `FIN_SYSTEM` 在 endpoint、lifespan、ADR 中一致。

## 后果

### 正面

- **零发现成本反查**:客户系统拿到 id,直接 `id.split(".", 1)[0]` 得到 system,
  无需先拉 system 列表 / 维护 system 缓存表。
- **构造期 fail-fast**:`EndpointSpec(id="wrong", system="fin", ...)` 直接抛错,
  不会进入 registry 后才发现。
- **启动期 fail-fast**:lifespan 自检若发现某个 endpoint 与 `FIN_SYSTEM` 失配,
  `RuntimeError` 即抛错,带文件名提示。

### 负面 / 限制

- **第二系统接入成本**:新增 `market` 系统需要复制 `system_info` 结构,
  每个新 endpoint 显式 `system=MARKET_SYSTEM`。这不是大成本,但确实增加样板。
- **id 重命名成本**:若 `FIN_SYSTEM` 从 `"fin"` 改为 `"finance"`,
  所有 18 个 endpoint 的 prefix + lifespan 自检代码 + 客户系统缓存 都要同步更新。
  约束强度对应契约稳定性 — 我们认为 `FIN_SYSTEM="fin"` 是稳定的命名,
  若未来真要改名,需走一次专门的迁移 commit。
- **schema 强制 prefix 不放过"故意无 system 的 endpoint"**:
  任何 endpoint 都必须有 system 字段(已存在约束),现在还要求 id 显式带上。

## 替代方案

### A. 用 `int` 编码代替 string id(如 `id=1002003` 表示 system=1 module=002 endpoint=003)

**未选**。原因:

- **可读性差**:`1002003` 不如 `fin.audit.audit_page` 自描述。
- **代码复杂度**:需要编码 / 解码函数,跨语言客户系统难解析。
- **容量限制**:每段位数硬编码(如 2 位 module),调整困难。
- **仍然无法消除 discover**:仍需要"system_id=1 → 系统名映射表"。

### B. 用 `name` 作为主键

**未选**。原因:

- **稳定性差**:中文 / 重命名 / 重名场景都难以处理。
- **机器校验缺失**:`name` 没有合法 pattern 约束。
- **同样无法消除 discover**:`name` → `system` 的反查仍是 O(N) 全局扫描。

### C. 让客户系统自己缓存 system 列表 + 心跳同步(不强制 prefix)

**部分采用但不是主导**。原因:

- 这是"不做事"的方案,核心问题(id 与 system 失配)未解决。
- 当前规模(18 个 endpoint)下,缓存表成本远高于"id 自带 system prefix"。
- 但仍是兜底:即便 prefix 校验通过,客户系统首次接入时仍需拉一次
  `/plate/v1/systems` / `/plate/v1/registry/lookup` 之类的 endpoint 进行初始发现,
  prefix 校验只是减少了后续每次拿 id 反查的成本。

### D. 用关系型数据库存储 system / endpoint 表

**未选**。原因:

- 当前 18 个 endpoint 用 Python 常量 + 文件 import 完全够用。
- 数据库化会引入 migration / schema 同步 / connection pool 等额外问题,
  收益<成本。
- id 的稳定性来自"约定 + 校验",不来自"持久化"。

## 实施

### Commit 1 — 校验层

`src/gimbal-plate/gimbal_plate/schema/endpoint/endpoint.py` 的 `_validate_integrity`
新增 id prefix 校验。同时修复 2 处 fixture id prefix(`tests/plate/conftest.py`)+ 21 处测试断言。

### Commit 2 — `system_info.py`

新增 `src/gimbal-plate/gimbal_plate/systems/fin/system_info.py`,12 个 `Final[...]` 导出,
其中 `FIN_SYSTEM="fin"` 是本 ADR 的核心常量。

### Commit 3 / 4 — meta.py / config.py

把硬编码的 fin 默认值改为从 `system_info` 派生。

### Commit 5 — 18 个 endpoint 文件

每个 endpoint 文件改为 `system=FIN_SYSTEM`、`version=FIN_DEFAULT_VERSION`、
`metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER, tags=list(FIN_DEFAULT_TAGS))`。
同时加 `XXX: Final[EndpointSpec]` 类型注解。

### Commit 6 — lifespan 自检

`http/app.py` `_lifespan` 注册完毕后扫一遍 `default_registry.list_endpoints()`,
校验每个 endpoint 的 `system == FIN_SYSTEM`,失败抛 `RuntimeError`。

### Commit 7 — 文档

- `docs/modules/fin-system-info.md`:模块文档,介绍 `system_info` 的 5 类 12 个导出。
- `docs/adr/0001-endpoint-id-system-prefix.md`:本 ADR。
- `docs/README.md`:加新文档链接。

## 验证

- **正测**:`EndpointSpec(id="fin.x", system="fin", ...)` 通过。
- **反测**:`EndpointSpec(id="wrong", system="fin", ...)` 抛 ValueError。
- **lifespan 反测**:故意注册 `system="other_system"` 的 endpoint,`create_app()` 启动时抛 RuntimeError。
- **回归**:330/330 plate tests passed。

## 参考

- [docs/modules/fin-system-info.md](../modules/fin-system-info.md) — system_info 模块文档。
- 相关代码位置:
  - `src/gimbal-plate/gimbal_plate/schema/endpoint/endpoint.py` — `_validate_integrity` 校验。
  - `src/gimbal-plate/gimbal_plate/systems/fin/system_info.py` — 常量定义。
  - `src/gimbal-plate/gimbal_plate/http/app.py` — lifespan 自检。
- 7 个 commit 链从 Commit 1 到 Commit 7,按依赖顺序逐提交。