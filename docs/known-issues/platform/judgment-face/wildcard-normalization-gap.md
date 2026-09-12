# 已接受局限：`[*]` 写法不被归一（无覆盖）

> **模块**：`gimbal-platform`（判定面的路径归一：后端 `_template_path` / 前端 `toTemplatePath`）
> **状态**：**已接受**（不是待修缺陷；本记录说明边界与残余风险）
> **来源**：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §6.3（「`[*]` 归一无覆盖」）

---

## 0. 局限是什么

两条归一实现都只吃**数字下标**：

```python
# src/gimbal-platform/backend/app/services/run_injection.py:73
_ARRAY_IDX_RE = re.compile(r"\[\d+\]")            # 只认 [0] / [-1]，不认 [*]
```

```ts
// src/gimbal-platform/frontend/src/utils/declarations.ts:766-768
export function toTemplatePath(path: string): string {
  return path.replace(/\[\d+\]/g, '')
}
```

于是 `$.items[*].sku` 归一等号不成立（实测 `_template_path('$.items[*].sku')` → **原样返回**）。这正是平台 API 文档已经写明的已知局限（`docs/PLATFORM-SCENARIO-COMPOSER-API.md:938-942`：「`[*]` 写法不被归一，**无覆盖**」——该处同时把「声明面模板粒度」指到本目录，即同批记录中的 `declaration-template-granularity.md`）。

---

## 1. 实测后果：两侧方向**不同**（本会话验证）

`[*]` 不归一的后果不是「都不认」，而是**前端判死、后端可能判活**：

**后端**（本会话实测，body = `{"items":[{"sku":1}]}`，universe = `['$', '$.items', '$.items[0]', '$.items[0].sku']`）：

```text
path_resolvable('$.items[*].sku', body, universe) -> True     # 靠 exists 兜底救回
exists({'items':[{'sku':1}]}, '$.items[*].sku')   -> True     # WILDCARD 节点展开到 [0]
exists({'items':[]},        '$.items[*].sku')     -> False    # 空列表 ⇒ 展开不出东西
```

即：后端**不是**靠归一认它，而是靠 `_path_resolvable` 的 `exists` 兜底（`run_injection.py:172`）在 body **碰巧真有**匹配元素时救回来的 —— 一旦该列表为空或元素形状不匹配，立刻判死。**该行为是兜底的副作用，不是被设计的覆盖面。**

**前端**（读源推断，`frontend/src/utils/assertion-registry.ts:39-52`）：`pathResolvable` 只有「两形态成员判定 + 容器前缀扫描」两条子句，没有通配处理；`$.items[*].sku` 既不在 `injectablePathSetOf` 里（`fieldPathsOf` 只产 `$.items[0].sku` 这类实例叶子），前缀扫描也不命中 ⇒ **判死（悬空）**，与 body 里有没有匹配元素无关。

**用户能碰到它**：编辑器的条目路径是**自由文本**（只要以 `$` 开头就收，`frontend/src/views/AssertionRegistryEditor.vue:374-377`）。所以手填 `$.items[*].sku` 是可能的 —— 结果是编辑器标「悬空」、不可勾选，而后端其实跑得动。

---

## 2. 为什么接受

1. **UI 不产出它**：编辑器给的候选路径来自实例化后的 body 面 / 契约声明面，都是 `[i]` 形态或模板形态，`[*]` 只可能来自**手写**；
2. **失败是可见的、不是静默的**：前端悬空标注 + 后端 skip 时的 `logger.warning`（`run_dispatcher.py:498-501`）都会留下痕迹；
3. **有零成本替代写法**：写具体下标（`$.items[0].sku`）或写容器/模板路径（`$.items.sku`）都覆盖得了 `[*]` 想表达的语义 —— 前者按实例、后者按模板（后者由 `injectable_universe` 的声明面与容器前缀覆盖）。

---

## 3. 残余风险与读者应当怎么做

- **风险一（前后端分裂）**：同一份注册表里，`[*]` 条目在编辑器显示悬空、在后端**可能**被物化执行。若将来编辑器放开「悬空条目仍可勾选」，这条分裂会立刻变成「用户看到一个灰条，跑起来却生效了」。（今天不可勾选，所以只是显示与能力的错配。）
- **风险二（空列表翻脸）**：后端的「活」依赖 body 当时的内容。同一份场景，改了 body（列表清空）就可能从「活」变「死」—— 这一步的判定**随数据变化**，与「路径是否被契约声明覆盖」无关。

**读者应当这么做**：

1. 需要「数组每一项都注入」时，**写模板形态**（`$.items.sku`）而不是 `$.items[*].sku` —— 模板形态是判定面真正支持的表达（后端 `injectable_universe` 会把声明路径归一后收进 universe，前端 `injectablePathSetOf` 同样收 `toTemplatePath` 后的声明路径）。
2. 排查「编辑器说悬空但后端在跑」时，先看路径里是否含 `[*]`。
3. **不要**把 `_ARRAY_IDX_RE` / `toTemplatePath` 顺手扩成能吃 `[*]` —— 那会改变两侧的判定面（方向是放宽，但与声明面的模板纪律、与 `_container_prefixes` 的段边界假设都要一起核）。若确要做，属判定面变更，走 H 那一轮的裁定。

---

## 4. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能（不影响**正常**路径）**。

- 触发需要手写 `[*]`（UI 不产出）；
- 后果可见（悬空标注 / skip 告警），且替代写法零成本；
- 被 spec §6.3 明确列为「已接受局限」。

---

## 5. 何时重开

1. **H 落点裁定**（spec §7）：判定面单一定义那一轮，`[*]` 是否归一必须一并定；
2. **编辑器放开悬空条目的勾选**：风险一立即升级为功能缺陷；
3. **用户实际写入 `[*]`**：出现真实用例（README 的「用户实际用例命中遗留缺陷」信号）；
4. **路径归一规则变化**：任一侧的 `toTemplatePath` / `_template_path` 被改动时，两侧同构假设需重核（它们是**镜像实现**，不是共享实现）。
