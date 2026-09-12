# 已接受局限：声明面的模板粒度边界

> **模块**：`gimbal-platform`（判定面 × plate 契约声明面）
> **状态**：**已接受**（不是待修缺陷；本记录说明边界与残余风险）
> **来源**：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §6.3（「声明面模板粒度」）

---

## 0. 局限是什么

契约声明面（plate 的 `request.declarations`）是**模板态**的：`plate` 侧明文禁止 children 子树出现实例下标，并校验父子后代关系：

```python
# src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py:231-245
# ③ 模板纪律:children 子树内 path 须模板态且为父链后代
#    (顶层条目路径形态自由 — 响应断言候选可带实例下标)
if not _is_template_path(e.path):
    raise ValueError(f"{owner} children 子树 path 须为模板态 …")
if not e.path.startswith(parent.path + "."):
    raise ValueError(f"{owner} children path 须为父 path 后代 …")
```

理由是同文件开头的目录纪律（`io_spec.py:11-12`）：**深实例下标 `[i]` 是渲染器实例化的产物，不进目录**。

而判定面在消费声明路径时把它**归一到模板形态**：

- 后端：`declared` 侧一律过 `_template_path`（`src/gimbal-platform/backend/app/services/run_injection.py:124-127`、`:135-140`）；
- 前端：`injectablePathSetOf` 对声明路径调 `toTemplatePath`（`frontend/src/utils/assertion-registry.ts:26-34`，实现于 `frontend/src/utils/declarations.ts:766-768`）。

**结论（这就是那条边界）**：模板归一之后，路径**不再区分具体下标** —— 声明 `$.items.sku` 覆盖 `$.items[0].sku`、`$.items[7].sku`、任意 `i`。声明面能表达的单位是**模板**，不是实例；「只声明第 2 个元素可注入」这种诉求在声明面里**无法表达**。

---

## 1. 为什么接受

1. **契约侧的硬约束**：实例下标不进目录是 plate 的**校验规则**（上引 §③），不是平台的选择 —— 平台改不了契约的形态，只能按模板态消费；
2. **数组长度是数据相关的**：为每个下标各声明一条会让目录随数据膨胀，且永远追不上真实响应；
3. **归一方向与判定面的整体放宽一致**：条目锚在**具体下标**时被模板声明「顺带覆盖」属于**放宽**（把可能误判死的路径判活）—— 这与可注入面 spec 的方向（`injectable-path-surface-design.md:105`「只放宽、不收紧」）一致，是既有承诺的接受面。

---

## 2. 残余风险与读者应当怎么做

**残余风险（模板粒度换来的代价）**：

- **「声明了模板」≠「该下标真的存在」**：条目锚 `$.items[9].sku` 时，判定按模板声明判**活**，但 body 里可能根本没有第 9 项。此时写侧的处置是**自动补位**而不是报错：

  ```python
  # src/gimbal/utils/jsonpath.py:461-463
  if idx >= 0:
      while len(data) <= idx:
          data.append(None)     # 自动扩展到该下标
  ```

  即可注入面 spec 已记录的后果（`docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md:104`）：表现为**请求载荷与断言结果的变化**，而不是步骤失败。
- **元素数不固定的响应**：声明面只能给到外层容器（`$.items`）或模板叶子（`$.items.sku`）；「第几个元素」的级联校验/展示在声明面无处安放 —— 响应侧的实例级标注属于被搁置的设计，不在本记录主张之列。

**读者应当这么做**：

1. 元素数不固定时，**按整容器 / 模板路径锚**（如 `$.items`、`$.items.sku`），把「整容器注入」当作语义单元 —— 与 `carry` 容器的「一树一主、整容器传递」是同一条思路（`io_spec.py:246-255` 的整传一致性校验）；
2. **不要**期待声明面给出「某下标存在」的保证；需要这个保证时，用 body 面（实例叶子）作为判据 —— 那也是 `exists` 兜底唯一比可注入面更宽的地方（见 `exists-property-hole.md` §3）；
3. 排查「注入写进了不存在的下标」时，直接看 body 的实际长度与 `_set_at` 的补位行为，不要往契约面找。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 它是**接受的**边界（spec §6.3 列在「已接受局限」），不是缺陷；
- 后果有明确记载（补位而非报错），且方向是「少判死」；
- 只有在元素数不固定 + 用户按下标锚定 + 期望「不存在就失败」三者同时成立时才会被感知。

---

## 4. 何时重开

1. **H 落点裁定**（spec §7）：判定面单一定义那一轮，模板/实例双形态的归一规则要一并定；
2. **plate 目录纪律变化**：若 `[i]` 被打进目录（或新增「实例级声明」形态），本边界随之改变；
3. **响应侧实例级标注重启**：一旦要做「第 N 个元素」的级联展示，模板粒度会成为第一道障碍；
4. **用户按具体下标锚定并期待失败语义**：此时「补位」从可接受变成误期望（README 的「用户实际用例命中」信号）。
