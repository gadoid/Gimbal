# `children` 非数组形状：理论不可达（登记，不需处理）

> **模块**：`gimbal-platform/frontend`（声明树消费）+ plate 契约面
> **状态**：**按裁定不需处理**（形状到不了平台侧）；本记录保留证据与判据
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 结论先说

「`children` 不是数组」（例如 `{"0": {...}}`）这一形状被登记为**理论不可达**：plate 侧由 pydantic 强制，平台侧拿到的声明面是**每次现拉**的、既不落库也不手改。因此**不需要**为它决定「静默丢弃 vs 硬抛」的取舍，也不需要为它写防御。

---

## 1. 证据

**① plate 侧形状由模型强制**：

```python
# src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py:114
children: "list[DeclarationEntry] | None" = None
```

`DeclarationEntry` 是 pydantic 模型（`io_spec.py:86` 的 `model_config = ConfigDict(extra="forbid")`），`children` 的类型注解为 `list[DeclarationEntry] | None` ⇒ 非数组值在**模型构造时**就 `ValidationError`，**发射不出来**。目录树也不是手写 JSON 直灌的：`RequestSpec.declare` / `ResponseSpec.declare` 由 schema 递归生成（`io_spec.py:283-302`、`:429-445`），最终都过 `_walk_schema_properties` 组装 `DeclarationEntry(**kwargs)`。

**② 平台侧的声明面是现拉、不落库**：

- 后端：`endpoint_declarations._fetch_declarations`（`src/gimbal-platform/backend/app/services/endpoint_declarations.py:163-197`）每次取数都打 `GET /api/endpoint/{id}/full` 并解 `data.item.request.declarations`；进程内 `TtlLruCache` 只是缓存（`config.py:88` 的 300s TTL），**没有持久化快照表/快照字段**（spec §4.1 的裁定；同轮文档已把「无快照表」措辞收窄到「判定面无快照表/快照字段」）；
- 前端：`useEndpointFull.ts:16-17` 明文「**零持久化**：缓存只活在本次页面会话（刷新即失效），不落库 / 不落 localStorage」。

⇒ 平台侧**不存在**「用户手改声明面 → 存进平台 → 再把畸形 children 读回来」这条链；形状唯一来源就是 plate，而 plate 那一关已被 pydantic 拦住。

---

## 2. 影响（既然不可达，为何还登记）

- 这是本会话**做过判断并得出结论**的一项：结论是「不需要为它做取舍」，写下来是为了**防止后人重复调查**（否则读 `sanitizeDeclarations` 的注释会以为这是个悬而未决的取舍，重开一轮）；
- 若哪天真能到达（见 §4），后果是明确的：`iterFlat` / `formBindings` 的 `for (const e of entries ?? [])` 对普通对象会 `TypeError: entries is not iterable`（**硬抛 = 白屏**，不是静默），消费方会立刻看见。

---

## 3. 优先级：P2（仅为登记）

按 README：**结构性 / 可维护性问题，不影响功能**（且按现有证据**不可触发**）。

---

## 4. 附注：一处与裁定不同步的注释（属文档债）

`frontend/src/utils/declarations.ts` 的 `sanitizeDeclarations` docstring 仍把它写作**待定取舍**：

> **不保证 `children` 的形状**：非数组 children（如 `{"0": {...}}`）原样放行…… 该形状是否归一是**待定取舍**（静默丢弃畸形 children = 字段树悄悄变瘦 vs 保持硬抛 = 白屏但响亮），**未在本轮处理**

以及与之一致的测试注释（`frontend/src/api/__tests__/scenario-composer.full.test.ts:6`：「`children` 形状未归一」）。

裁定既然是「形状到不了我们这里 ⇒ 不需取舍」，这两处注释的字面主张（「待定」）就滞后于裁定了。**本记录不动 `src/`**（该文件不在本任务范围），仅登记该差异；后续谁再进这两个文件时顺手把「待定取舍」改成「形状经 plate 模型与现拉取数双重约束，平台侧不可达」即可。

---

## 5. 何时重开

1. **声明面出现落库路径**：若将来把 plate 契约存进平台表，或允许手工编辑声明面（spec §4.1 否定了这一方向，若被推翻则本条前提失效）；
2. **plate 侧放宽 `children` 类型**（如改成 `Any` / 允许 dict 形态）；
3. **出现真实白屏且堆栈指向 `entries is not iterable`** —— 那说明上面的 ①/② 至少有一条不再成立。
