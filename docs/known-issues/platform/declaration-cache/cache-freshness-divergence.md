# 已接受局限：前后端契约缓存的新鲜度分歧

> **模块**：`gimbal-platform`（后端 `endpoint_declarations` ↔ 前端 `useEndpointFull`）
> **状态**：**已接受**（不是待修缺陷；本记录说明边界与残余风险）
> **来源**：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §6.3

---

## 0. 局限是什么

同一条 plate 契约（`GET /api/endpoint/{id}/full` → `data.item.request.declarations`），两侧各有一份**进程内 / 会话内**缓存，**过期策略不同**：

| | 后端 | 前端 |
|---|---|---|
| 位置 | `src/gimbal-platform/backend/app/services/endpoint_declarations.py` | `src/gimbal-platform/frontend/src/composables/useEndpointFull.ts` |
| 载体 | `TtlLruCache`（`:88` 的 `_CACHE`，`max_entries=256`） | 模块级 `shallowReactive(new Map())`（`:53`） |
| TTL | **300s**（`backend/app/core/config.py:88`，`DECLARED_PATHS_TTL_SEC`） | **无 TTL**（前端自述见 `useEndpointFull.ts:14-15`：「前端缓存**无 TTL**，与后端 `endpoint_declarations` 的 300s TTL 不同；差异方向：前端更粘」） |
| 过期后 | 回退窗内继续服务旧快照；刷新失败 → fail-open-to-old（`endpoint_declarations.py:237-252`；总上界 300s + 3600s，`config.py:95-99`） | 不失效 —— 只在页面刷新时清空（零持久化，`useEndpointFull.ts:16-17`） |
| 失败处置 | 负缓存**无**（失败不写缓存，下次调用即重试）；仅 `_warn_once` 冷却窗 300s 限制告警频率 | 负缓存 `FAILED_RETRY_MS = 10_000`（`useEndpointFull.ts:46`、`:64-67`） |

即：**plate 发版之后**，后端最迟 300s（正常路径）就会看到新契约；前端在同一次页面会话里**永远**看不到，直到用户刷新页面。

**多 worker 视角**（spec §4.4）：后端这份缓存是**每进程一份**，PG 部署多 worker 下同一个端点在两个 worker 上可能有不同的年纪 —— 比较「前后端新鲜度」时不能假设后端只有一个值。

---

## 1. 为什么接受

1. **冻结方向的合理性**：前端这份缓存的用途是**渲染与判定的一致性**（`useInjectableSurface.pathsOfStep` 记忆化键里就含端点态，见 `useInjectableSurface.ts:128-140`）。会话中途换一份声明面，会让「用户正在编辑的条目」在同一屏内改变死活判定 —— 刷新即一致，比中途换面更好解释。
2. **代价有界且自愈**：分歧窗口 = 一次页面会话；自愈动作 = 刷新页面（成本极低，且是用户已在用的动作）。
3. **两侧都不落库**（`useEndpointFull.ts:16-17`；后端纯进程内），所以分歧不产生任何**持久化**的错版本 —— 不会出现「库里存着一个错的声明面」。
4. 判定面的降级方向是**从严**（拿不到就只认 body 面），不会因为陈旧而放宽。

---

## 2. 残余风险与读者应当怎么做

**残余风险**：

- **plate 中途发版 + 用户不刷新**：该会话里前端按**旧契约**渲染字段目录与死活判定 —— 新增字段看不到（候选面偏小），已删字段仍显示（可能锚到不存在的路径）。此时后端 dispatch 侧按**新契约**判定 ⇒ 同一会话里「编辑器判活、dispatch 判死（skip + 告警）」是可能的。
- **反向窗口（≤300s）**：plate 发版后、后端 TTL 未到之前，后端按旧面判定而前端已按新面渲染（刷新过页面时）⇒ 同样形态的分裂。方向相反，窗口更短。
- 两侧都**不报错**：分歧不产生告警，只有 dispatch 侧的悬空 skip 会留 `logger.warning`（`run_dispatcher.py:498-501`）。

**读者应当这么做**：

1. **plate 发版后，要求使用者刷新页面**（或由运维在发版流程里显式说明）；不要依赖「等一会儿就好了」——前端那份不会自己过期。
2. 排查「编辑器里能选、跑起来却被 skip」时，**先看 dispatch 侧告警**（`run_dispatcher.py:498-501` 的 `injection entry … dangling … skipped`）与 `skipped_while_degraded` 的遥测（见 `judge-degraded-observability.md`）；这两条是分歧唯一的可观测面。
3. 不要把任何一侧的缓存当「全局唯一事实」（spec §4.4 明文边界）。

---

## 3. 优先级：P2

按 README：**结构性 / 风格性 / 可维护性问题，不影响功能**。

- 它是**已拍板的取舍**，不是待修缺陷；影响面是「同一次会话内的判定面新鲜度」，不丢数据、不产生错版本的持久化；
- 触发条件明确但需要**运维事件**（plate 中途发版）+ 不刷新；
- 若要收窄，可选方向（**不属于本记录的主张，仅备查**）：给前端缓存加一个与后端同量级的 TTL，或让刷新与「契约版本」信号联动 —— 但都会引入「会话中途换面」的代价，需与 §1.1 的收益再权衡。

---

## 4. 何时重开

1. **出现「编辑器判活 / dispatch 静默 skip」的用户投诉**且复盘指向 plate 中途发版；
2. **H 落点裁定**（spec §7）：若判定面收为「后端算、前端消费」，前端这份缓存的意义与 TTL 必须重新定；
3. **plate 发布节奏变化**（发版变频繁 / 引入灰度），使「刷新页面」不再是一个可依赖的运维动作；
4. **前端引入 TTL 或版本协商**的任何提案进入实施。
