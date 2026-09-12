# `judgeDegraded` 的缺席无法区分「没降级」与「降级了但没跳过任何条目」

> **模块**：`gimbal-platform/backend`（执行记录的可观测粒度）
> **状态**：已知未修复（可观测性粒度局限）
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 事实

两个键**同生同灭**，且只在「降级 + 有跳过」同时成立时出现：

```python
# src/gimbal-platform/backend/app/services/run_dispatcher.py:590-594
# spec §1.1 Y:判定降级是可审计事实,不留静默窗口。
# entriesSkippedWhileDegraded = 降级期间被跳过的条目 id(因由不限);
# 键缺席 = 本次执行没有「降级 + 跳过」同时发生,不是「零跳过」。
**({"judgeDegraded": True, "entriesSkippedWhileDegraded": skipped_while_degraded}
   if skipped_while_degraded else {}),
```

`skipped_while_degraded` 只在「某条目被跳过 **且** 它锚定的那一步当时声明面不可得」时累积（`:485-497`）；而 `judgeDegraded` **没有**独立取值 —— 它不会以 `false` 出现（值恒为 `True`，仅与列表一起出现）。用例把这条语义钉住了：`src/gimbal-platform/backend/tests/test_run_cross_matrix.py:391`（有跳过 ⇒ `is True`）与 `:400`（无跳过 ⇒ `is None`）。

于是 `config_json` 的读取者面对三种情形，却只能看到两种：

| 真实情形 | `judgeDegraded` | 可区分? |
| --- | --- | --- |
| 没降级 | 缺席 | ✅（是「降级但零跳过」的**两种**情形都落在这一行） |
| 降级了，但没有任何条目因此被跳过（判定面不可得 ≠ 有东西被跳） | 缺席 | ❌ |
| 降级了，且至少有 1 条被跳过 | `true` + 列表 | ✅ |

**触发条件**：`declared_paths_of` 返回 `None`（plate 抖动 / 超时 / 信封坏）**且**本次选中的条目里没有一条因此被判悬空跳过（例如没有条目、或条目没锚在缺面的那一步上）。

**影响**：审计侧无法回答「这次执行到底有没有降级」—— 只能回答「有没有降级**并造成跳过**」。而这两个问题在排障时的含义完全不同（前者说明判定面**不完整**，后者说明**已经产生了可见后果**）。

`judgeDegraded` 是**机器可读**面：前端目前不消费它（`frontend/src` 零命中），读取者是 API 消费者 / 审计脚本；平台 API 文档已如实写明「键缺席 ≠ `false`」（`docs/PLATFORM-SCENARIO-COMPOSER-API.md:811`，另见 `:670`）。

**已有的补偿**：**逐步骤**的降级有独立的 loguru 告警，不受本条影响：

```python
# src/gimbal-platform/backend/app/services/run_dispatcher.py:463-468
for si, face in face_by_step.items():
    if face is None:
        logger.warning(
            "run_dispatcher: step %s 声明面不可得(plate 降级)— 该步判定只认 body 面,"
            "锚在契约声明上的条目可能被误判为悬空并跳过", si,
        )
```

即「降级发生了」在**日志**里是逐步骤可见的；缺的只是**结构化记录**（`config_json`）里的同一信息。

---

## 1. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 判定与控制流本身正确（降级行为、跳过行为、告警都在）；
- 缺的是**可观测性的一个维度**：结构化记录无法表达「无后果的降级」；
- 补偿路径存在（逐步骤 warning），且文档已如实标注「缺席 ≠ false」—— 不构成误读的陷阱。

**可选收口方向（仅备查，不是结论）**：给 `config_json` 加一个独立键，如 `judgeFaceUnavailableSteps: [si, …]`（或把 `judgeDegraded` 改成**独立**取值、与跳过列表解耦）。这样做会改变**机器可读契约**（`RunRequest`/Execution 的读取方），需按平台 API 文档的变更纪律同步（§5 持久化设计 / §4.18）。

---

## 2. 读者应当怎么做

1. 要判断「这次执行有没有降级」，**不要**只看 `judgeDegraded`：缺席时去日志里找 `声明面不可得` 的逐步骤告警（上引 `:463-468`）；
2. 要判断「降级有没有造成跳过」，`entriesSkippedWhileDegraded` 是可靠答案（非空即真）；
3. **不要**把「键缺席」写成「零跳过」或「未降级」—— 平台 API 文档已把这条写死（`:811`），任何新消费者照此实现即可。

---

## 3. 何时重开

1. **审计 / 合规要求「记录每一次降级」**（无论有无后果）—— 本条的粒度不够；
2. **前端开始展示降级状态**：届时「缺席」会被渲染成某种文案，歧义立即变成误导；
3. **`skipped_while_degraded` 的累积口径变化**（`:485-497` 的「因由不限」口径）—— 两个键的耦合关系需重核；
4. **Y 项（`None` 不抹平）再次改动** —— 降级判定链随之变化。
