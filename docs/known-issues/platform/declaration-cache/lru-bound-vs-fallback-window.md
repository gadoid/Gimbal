# 已接受取舍：容量压力下 LRU 逐出先于回退窗到期

> **模块**：`gimbal-platform/backend`（`app/services/query_view_cache.py` 的 `TtlLruCache`，声明面在用）
> **状态**：**已接受**（有意为之的取舍；本记录说明边界与残余风险）
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 取舍是什么

共享缓存的三个维度是**独立**的，容量逐出**不看**回退窗：

```python
# src/gimbal-platform/backend/app/services/query_view_cache.py（TtlLruCache.put）
def put(self, key: Hashable, payload: Any, fetched_wall: str,
        truncated: bool = False) -> None:
    self._data.pop(key, None)
    self._data[key] = CacheEntry(payload, truncated, fetched_wall, self._clock())
    while len(self._data) > self._max:
        self._data.popitem(last=False)          # 容量到了就逐出最旧，与 stale 窗无关
```

```python
# TtlLruCache.lookup：TTL 命中 → fresh；TTL 过但 ≤ stale_window → 回退候选；再久 → 真过期
```

于是当条目数超过 `DECLARED_PATHS_MAX_ENTRIES`（默认 **256**，`backend/app/core/config.py` 的该 setting）时，**最久未用**的条目会被逐出 —— 哪怕它仍在回退窗内（默认 **3600s**，`DECLARED_PATHS_STALE_WINDOW_SEC`），本来还「可被回退服务」。

**「the bound wins over the fallback」**：容量是硬上界，回退窗是尽力而为的时间窗；两者冲突时容量优先。

---

## 1. 为什么接受

1. **上界必须硬**：回退窗是一个**时间**维度，若让「窗内条目」豁免逐出，容量上界就不再是上界（plate 长期故障时，窗内条目会无限堆积）—— 那正是 S 项要消除的「无界增长」；
2. **256 的判据**：声明面是**端点级**粒度（一个 endpoint 一条）而非字段级/行级 —— 单个部署上「同时活跃的端点」数量远低于 256（`config.py` 的 `DECLARED_PATHS_*` 三值裁定注释把三个值一并写明，并注明「对照 query_view_runner 的 stale_max_window = 86400s，本值保守」）；
3. **逐出的后果是「回到正常路径」而不是损坏**：条目被逐出 ⇒ 下次访问 = 冷缓存 ⇒ 重新取数（成功则入缓存）。**唯一**退化是 plate 当时正好故障：此时本来可以回退的旧快照没了 ⇒ 退化为 `None` ⇒ 调用侧降级从严。

---

## 2. 残余风险与读者应当怎么做

**残余风险**：

- **大端点目录 + plate 故障的叠加**：活跃端点 > 256 且 plate 同时抖动时，容量逐出会把「本来还能回退的旧快照」提前丢掉 ⇒ carry 空面 / 悬空判定只认 body 面（比回退窗承诺的「最多陈旧 3900s」更早失效）。此时告警模板尾描述的情形反而**成立**（见 `warn-once-stale-fallback-wording.md` 的两条路径区别）；
- **判据依赖部署规模**：256 是「端点级」的估计；若某个部署的活跃端点数接近或超过它，回退窗实际上形同虚设 —— 但**不会有任何信号**提示这一点（没有逐出计数/指标）。

**读者应当怎么做**：

1. 遇到「plate 抖动时声明面降级比预期早」时，先核 `DECLARED_PATHS_MAX_ENTRIES` 与实际活跃端点数，**不要**先怀疑回退窗配置；
2. 调大 `DECLARED_PATHS_MAX_ENTRIES` 时记住代价是内存 —— 声明面这条路现在有**两份**同 cfg 的缓存，两份都要认：**取数层** `plate_client._full_cache()`（载荷 = plate 的**整份 item**）与**派生层** `endpoint_declarations._proj_cache()`（载荷 = path 投影 `frozenset`）。该值来自 settings，两个工厂函数都会比对新旧 cfg 并**换实例**，故热改即刻生效（但**旧缓存整份丢弃** —— 换实例不是迁移）；
3. 若维护者要动这块，**先读完 `query_view_cache.py` 模块 docstring 的「载荷泛化」一段**：`TtlLruCache` 由**三个**消费者共用（query-view 行集 + 契约声明面的 path 投影 + `plate_client` 的整份 item），改逐出策略会同时影响另两条链（`query_view_runner` / 编辑器候选树与 dispatch 判定）。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能（正常路径）**。

- 这是被明确记录的**有意取舍**（「the bound wins over the fallback」），不是缺陷；
- 正常路径（plate 可用）下逐出的唯一后果是重新取数一次；
- 触发需要「活跃端点 > 256 且 plate 同时故障」的叠加，且后果仍是既有的降级路径。

---

## 4. 何时重开

1. **活跃端点数接近 256**：出现「回退窗在故障期没起作用」的实测；
2. **共享缓存再新增消费者**：第三个（`plate_client` 的整份契约 item，阶段二·①）**已到位**，三者共用一套容量/回退语义；再加第四个时逐出策略的影响面会再次扩大；
3. **plate 故障期的可用性成为硬指标**（SLO）：需要逐出计数/指标与容量策略一起重新论证；
4. **`TtlLruCache` 的语义变更**（例如引入「窗内条目受保护」的优先级）—— 那会改动 §1.1 的硬上界前提。
