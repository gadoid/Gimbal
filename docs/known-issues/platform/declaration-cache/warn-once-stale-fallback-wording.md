# `_warn_once` 的固定模板尾在其中一条调用路径上描述了错误后果

> **模块**：`gimbal-platform/backend`（`app/services/endpoint_declarations.py` 降级遥测）
> **状态**：已知未修复
> **来源**：架构收敛执行会话自查（非 spec 条目）
> **性质**：**遥测措辞**（不影响控制流，见 §2）

---

## 0. 机制

降级告警的正文是**固定模板**，只有 `{}` 占位的 `endpoint_id` / `reason` 随调用变化：

```python
# src/gimbal-platform/backend/app/services/endpoint_declarations.py（_warn_once）
logger.warning(
    "endpoint_declarations: {} 声明面不可得({}) — 调用侧降级"
    "(carry 空面 / 悬空判定只认 body 面)",
    endpoint_id, reason,
)
```

而 `_warn_once` 有**两条语义不同的调用路径**：

| 路径 | 调用点 | 该路径的真实行为 |
| --- | --- | --- |
| **冷缓存**（真拿不到，调用侧降级） | `declarations_of` 的 `res.item is None` 分支（`_warn_once(endpoint_id, res.reason)` 后 `return None`），以及同函数「声明面形状不可解析」（`request` 非 dict / `declarations` 非 list）那一支 | 返回 `None` ⇒ 调用方降级：carry 空面 / 判定只认 body 面（`run_dispatcher.py:463-468` 的逐步骤告警、`declarations_of` 的 None 契约） |
| **过期回退**（旧快照继续服务） | `declarations_of` 的 `res.stale` 分支（`_warn_once(endpoint_id, f"刷新失败({res.reason}),回退旧快照")`），随后照常从 `res.item`（= 缓存里那份**旧**快照）派生声明面 | **不降级** —— 返回**旧快照**，carry 面与悬空判定都按旧契约面继续（fail-open-to-old，见 `backend/app/core/config.py:92-95` 的裁定记录与 `plate_client.get_endpoint_full` 的过期分支） |

结果：回退路径打出的一行是**自相矛盾**的 —— `reason` 说「回退旧快照」，模板尾却说「调用侧降级（carry 空面 / 悬空判定只认 body 面）」。读整条日志会得出错误的结论：**以为这次已经降级成空面**，实际上按旧面在服务。

**触发条件**：TTL 已过（默认 300s，`config.py:88`）、条目仍在回退窗内（`DECLARED_PATHS_STALE_WINDOW_SEC`）、且刷新失败 —— 即 plate 抖动 + 该端点已被访问过一次。

---

## 1. 影响

- **排障误导**：`回退旧快照` 与 `调用侧降级` 是两个相反的结论（一个是「给了陈旧的面」，一个是「什么都没给」）。运维/开发者按后者去查「为什么声明面空了」，会查错方向；
- **规格面已有前车之鉴**：任务 7b 的复核正是栽在这句话上 —— 该轮的记录一度用回退分支 `reason` 串去断言「这条告警不是降级」，按**整条日志**读不成立；复核确认后，文档侧已改成只描述真实行为（`.superpowers/sdd/2026-09-12-architecture-convergence/task-7b-report.md` §3），但**代码里这个模板尾没动**（该轮 `src/` 零改动，明示由本目录承载；阶段二·① 之后同样没动 —— 取数层换了家，模板尾仍是同一句）；
- **不影响控制流**：告警文案不参与任何判定，两条路径的返回行为本身都是正确的。

---

## 2. 优先级：P2

按 README：**结构性 / 风格性 / 可维护性问题，不影响功能**。

- 纯遥测文案；控制流与两条路径的语义都正确；
- 影响面是「看日志的人」，但结论方向的错误恰好落在最需要准确的时刻（plate 故障期）。

**修法方向（仅备查，不是结论）**：把模板尾与调用点解耦 —— 或让调用方传入后果短语（与 `reason` 同路），或把模板尾收成中性句（「声明面不可得」）由调用方各自补充后果。**不要**只改回退路径的 `reason` 措辞 —— 模板尾仍在，矛盾依旧。

---

## 3. 何时重开

1. **plate 故障期的一次排障复盘**发现有人按「降级」误判；
2. **降级链路的任何改动**（例如新增第三条调用路径）—— 模板尾会再次成为错误来源；
3. **日志/遥测规范化**（例如引入结构化字段描述后果）—— 顺手收口最省。
