# `Scenario.stepCount` 取自**过滤后**的步骤列表（潜在基数分歧）

> **模块**：`gimbal-platform/backend`（`app/services/scenario_store.py` 读形状）× 前端消费
> **状态**：已知未修复（今天两侧口径一致；风险在下一次「拿它当**条目的**下标上界」时兑现）
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 事实

`Scenario.stepCount` 是**过滤后**列表的长度：

```python
# src/gimbal-platform/backend/app/services/scenario_store.py:402-405
meta = _meta_from_row(row)
steps = steps_from_payload(row.payload)
# stepCount is derived from the payload (the mirror column was
# retired); len() of the persisted steps list is authoritative.
```

```python
# src/gimbal-platform/backend/app/services/scenario_store.py:461-464
def steps_from_payload(payload: dict | None) -> list[dict]:
    """Steps live inside the container's definition now (plate-shaped dicts)."""
    raw = definition_from_payload(payload).get("steps") or []
    return [s for s in raw if isinstance(s, dict)]        # ← 非 dict 元素被滤掉
```

⇒ `stepCount == 持久化 steps 里 dict 元素的个数`，**不是** `len(持久化 steps)`。上引注释里的「the persisted steps list」措辞因此不精确：它指的是**过滤后**的那份。

（同一函数返回的 `steps` 也是这份过滤后列表，见 `scenario_store.py:412-419`。）

---

## 1. 它与 Z2 修的不是同一件事

Z2 修的是**判定面三投影的索引基数**：声明面 / body / asserts 一律按 `definition.steps` 的**原始**下标寻址（`src/gimbal-platform/backend/app/services/run_dispatcher.py:433-437` 的注释与 `raw_steps = definition_from_payload(raw_payload).get("steps")`）。`stepCount` 是**读形状**里的一个展示/选择字段，不参与那三个投影，因此**不是** Z2 要统一的那处不一致。

**本会话核实：今天两套基数各自内部一致。**

| 用途 | 上界来源 | 侧 |
| --- | --- | --- |
| 条目 `path.stepIndex` 越界判定 | `len(definition.steps)`（**原始**）：编辑器 `views/AssertionRegistryEditor.vue:213`/`:224`，数据页 `views/CaseDataSetsList.vue:173`，编排器 `views/CaseComposer.vue:521` | 前端 |
| 同上 | `len(raw_steps)`（**原始**）：`services/run_dispatcher.py:436-437` | 后端 |
| `stepTo` 选择器选项数 | `Scenario.stepCount`（**过滤后**）：`components/composer/RunDialog.vue:562` → `:118-120`（`v-for="i in stepCount"`，值 `i-1`） | 前端 |
| `stepTo` 越界校验 | `steps_from_payload(...)`（**过滤后**）：`services/run_dispatcher.py:383-391`（`step_to_out_of_range`，0..len-1） | 后端 |
| 列表页步数列 | `Scenario.stepCount`：`views/Scenarios.vue:105` | 前端（纯展示） |

即：**条目下标用原始基数（两侧一致），`stepTo` 用过滤后基数（两侧一致）** —— 今天没有错位。（顺带更正一处措辞：`stepCount` 并非纯展示，它是 `stepTo` 选择器的上界；只是它上界的是**另一个**索引空间，因而与后端同口径。）

---

## 2. 残余风险

**触发条件**：任何一侧**开始用 `Scenario.stepCount` 去界条目 `path.stepIndex`**（例如新增一个「条目步骤越界」的前端检查，或后端把读形状的 `stepCount` 当作寻址上界）。

**为什么那时就错**：`steps_from_payload` 是**过滤**而非**映射** —— 非 dict 元素被删掉后，其后元素的**下标整体前移**。于是原始下标 `N` 与过滤后下标 `N` 指向**不同的步骤**，且过滤后长度更小：

- 假阳性：原始下标合法（`N < len(raw)`）但 `N >= stepCount` ⇒ 被误判越界；
- 假阴性 + 错位：`N < stepCount` 但 `N` 在原始列表里指向的是**另一个**步骤（中间有被滤掉的元素时）。

**读者应当怎么做**：

1. 要界**条目**下标，用 `len(definition.steps)`（原始，两侧同口径）—— 与 `run_dispatcher.py:433-437` 的 Z2 契约一致；**不要**用 `Scenario.stepCount`；
2. 要界 `stepTo`，继续用 `stepCount`（后端就是拿过滤后的列表校验的）；
3. 排查「步骤编号对不上」时，先确认 payload 里是否混有非 dict 的 steps 元素（`git grep` 不到，只能在数据里看）。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能（今天）**。

- 今天两侧口径一致，无实际后果；
- 风险是**未来误用**（把展示字段当寻址上界）—— 本记录的目的就是把这条判据写下来；
- 触发需要同时满足「payload 含非 dict steps」+「有人用 stepCount 界条目下标」。

---

## 4. 何时重开

1. **payload 出现非 dict 的 steps 元素**（手工改库 / 迁移工具 / 旧格式）—— 两套基数第一次真的分叉；
2. **任何一侧用 `stepCount` 界条目下标**（本记录 §2 的触发条件）；
3. **`steps_from_payload` 改成映射（保留下标）而非过滤**，或读形状改用原始长度 —— 改完请把上引 `scenario_store.py:404-405` 的「persisted steps list」措辞一并改准；
4. **Z2 契约修订**（判定面索引基数再次变化）。
