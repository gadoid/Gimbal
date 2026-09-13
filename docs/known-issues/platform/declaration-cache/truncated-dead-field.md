# 声明面缓存条目上的 `truncated` 恒为 `False`（死字段）

> **模块**：`gimbal-platform/backend`（`app/services/query_view_cache.py` × `app/services/endpoint_declarations.py`）
> **状态**：已知未修复（「一套缓存」裁定的固有代价）
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 事实

`CacheEntry` 保留了一个只对**行集**有意义的字段：

```python
# src/gimbal-platform/backend/app/services/query_view_cache.py:21-27
class CacheEntry:
    __slots__ = ("payload", "truncated", "fetched_wall", "fetched_mono")
    def __init__(self, payload, truncated, fetched_wall, fetched_mono):
        self.truncated = truncated   # §5.1 截断标记随行集入缓存(命中也透出)
```

`put` 的默认值是 `False`（`TtlLruCache.put` 的 `truncated: bool = False`），而声明面的条目入缓存时都**不传**它 —— 取数层缓存的是 plate 的**整份 item**（`plate_client.get_endpoint_full`），派生层缓存的是 path 投影：

```python
# src/gimbal-platform/backend/app/services/endpoint_declarations.py（declared_paths_of）
_proj_cache().put(endpoint_id, proj, _now_iso())
```

⇒ 声明面条目上的 `truncated` **恒为 `False`**，且**没有任何读取方**。这一事实已写在缓存模块自己的 docstring 里：

```python
# src/gimbal-platform/backend/app/services/query_view_cache.py（模块 docstring）
字段叫 ``rows`` 会让后两个消费者"名不副实";``truncated`` 仍只对行集有意义
(声明面 / 契约 item 恒为默认 ``False``)。
```

---

## 1. 为什么接受

这是**「一套缓存」裁定的固有代价**（spec §3.1）：把 `TtlLruCache` 的载荷从 `rows: list[dict]` 泛化为 `payload`（保留 `truncated` / `fetched_wall` / `fetched_mono`），让声明面与 query-view 行集共用同一套 TTL / LRU / 回退语义。`truncated` 属于**行集特有**的语义（查询结果被截断标记，`query_view_cache.py:27` 的行内注释「§5.1 截断标记随行集入缓存(命中也透出)」），泛化时选择**保留字段**而不是为两个消费者拆表/加分支 —— 因为拆表就等于放弃收敛。

- 代价：一个恒 `False`、无人读的字段挂在声明面条目上（字段名与实际语义不符的**轻度**形态）；
- 收益：不用为第二个消费者复制一套 TTL/LRU/回退实现（spec §3.1 的整条理由）。

---

## 2. 残余风险与读者应当怎么做

**残余风险**：低，但有一个**读错的方向**值得点名 ——

- 若有人看到声明面条目的 `truncated` 字段，**不要**据此认为「声明面可能被截断」。声明面是**完整**的原始列表：`endpoint_declarations` 是派生层（取数归 `plate_client.get_endpoint_full`），`declarations_of` 从 item 里解出 `request.declarations`，要么返回完整列表、要么 `None`（降级），**没有中间态**；`declarations` 真值非 list 时降级为 `None`（`_decls_of_item` 的类型判据）而不是截断。
- 反向：行集那条链的 `truncated` 是**活**的（`query_view_runner` 消费），改动缓存时不要为了「清掉死字段」把行集的语义一起删了。

**读者应当怎么做**：把 `truncated` 读作「**行集**专用字段」；声明面的完整性靠 `None`（降级）与 `[]`（真无声明）的区分来表达（`declarations_of` / `_decls_of_item` 的契约，spec §1.1 Y 的「不抹平」）。

---

## 3. 优先级：P2

按 README：**结构性 / 风格性 / 可维护性问题，不影响功能**。

- 无行为影响；只有「字段名撒谎」的轻度形态（本仓库对此一贯严格，但它被显式记录、有 docstring 说明，属**已知并接受**）；
- 若未来第三个消费者出现，这类字段的归属会再次成为问题。

**可选收口方向（仅备查，不是结论）**：把 `truncated` 从 `CacheEntry` 移出、改由行集在自己的 `payload` 里携带，或给 `CacheEntry` 加一条「哪些字段只对某消费者有意义」的显式说明 —— 但两者都要碰 `query_view_runner` 与其单测（`tests/test_query_view_cache.py`），属机械但非零的改动。

---

## 4. 何时重开

1. **第三个消费者加入共享缓存**：字段归属需要重新划分；
2. **`query_view_runner` 的截断语义变化**（或行集侧不再需要 `truncated`）；
3. **有人按 `truncated` 误判声明面被截断**（说明该字段已经开始误导读者）。
