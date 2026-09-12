# 潜伏绿（latent-green）：`test_stale_snapshot_survives_a_failed_refresh` 的判别力会静默消失

> **模块**：`gimbal-platform/backend/tests`（声明面回退窗的回归证据）
> **状态**：已知未修复
> **来源**：架构收敛执行会话自查（非 spec 条目）
> **定性**：**latent-green risk** —— 不是「CI 抖动（flaky）」

---

## 0. 先说定性

这不是「偶尔变红」的抖动：**该用例任何情况下都不会红**。风险是反方向的 —— 它有时**根本没有测试它声称测的那条路径**，而结果依然是绿的。这类用例的危险在于：它守护的是「D：TTL 到期且刷新失败 → 旧快照仍服务」（spec §8 的验收要点之一），而这条能力**可以悄悄退化而不被发现**。

---

## 1. 用例的构造

```python
# src/gimbal-platform/backend/tests/test_endpoint_declarations.py:282-302（节选）
monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)        # 立即过期
monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
assert await declared_paths_of("ep-s") == frozenset({"$.customer_id"})   # 先成功入缓存
calls["fail"] = True
got = await declared_paths_of("ep-s")
assert got == frozenset({"$.customer_id"}), "刷新失败时应回退旧快照…"
```

两条断言都只看**返回值**（两次调用期望值**相同**），因此：

- **走回退分支**（stale → 刷新失败 → 返回旧快照）⇒ 绿；
- **走 TTL 命中分支**（被判定为 fresh → 直接返回缓存值）⇒ **也是绿**。

判别力完全依赖「第二次 `lookup` 时的 `age` 落在 `(0, ttl]` 之外」，而 TTL 被设成 `0.0`，所以条件退化为 **`age > 0`**：

```python
# src/gimbal-platform/backend/app/services/query_view_cache.py:46-48
age = self._clock() - e.fetched_mono
if age <= self._ttl:          # ttl == 0.0 ⇒ 只有 age == 0.0 才算 fresh
    return e, True
```

**触发条件（判别力消失的那一刻）**：`put` 与第二次 `lookup` 落在**同一个 `time.monotonic()` 取值**上 ⇒ `age == 0.0 ≤ 0.0` ⇒ 判为 fresh ⇒ 回退分支一次都没跑，`calls["fail"] = True` 的桩**根本没被调用**，用例照样绿。

这不是理论上的巧合：两次调用之间只隔着一次 `await`（MockTransport 的本地请求），在时钟分辨率较粗的平台上（Windows 上 `time.monotonic()` 的可用粒度约 15.6ms）完全可以落在同一刻度内。是「有时测、有时没测」，**取决于机器与调度**。

---

## 2. 为什么值得记下来（影响）

- **退化不可见**：`_cache().put` 的时间戳打点（U）、`lookup` 的 `age <= ttl` 判定、`entry.payload[0]` 回退返回 —— 这一整条链今天被 D 的验收要点依赖，但守护它的用例**只在某些运行里真的走到**；
- **误诊风险高**：一旦有人真的把 D 改坏，CI 仍可能全绿；反过来，若有人发现「这条用例有时没打桩」而把它当抖动删掉/跳过，就彻底失去守护（这正是本记录要阻止的处置）；
- **不是新缺陷**：生产行为没问题（`query_view_cache.py:46-52` 的三段判定是正确的）；问题是**证据本身**。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 不影响任何生产路径；影响的是回归保护的有效性；
- 触发即「判别力丢失」，代价在**未来**（D 退化时无人察觉）。

**可选修法方向（仅备查，不是结论）**：

1. **断言副作用而不只是返回值**：补 `assert calls["n"] == 2`（或断言第二次确实打了 plate 且失败）—— 时间塌缩时该断言会红，把「没测到」暴露出来；
2. **让陈旧性确定化**：`TtlLruCache.__init__` 已支持注入时钟（`query_view_cache.py:33-34` 的 `clock: Callable[[], float] = time.monotonic`），用可控时钟把 `age` 推到明确大于 0；
3. **两条都做**：1 保证「确实进了回退分支」，2 保证「稳定进入」。

---

## 4. 何时重开

1. **D 的回退语义被改动**（TTL / 回退窗 / `lookup` 判定）—— 先修本条，否则改动是否安全无从判断；
2. **该用例出现「间歇性不打桩」的观察**（例如有人给它加日志/覆盖率后注意到）；
3. **测试套件引入变异测试或覆盖率门禁** —— 这条用例会被立刻标出来；
4. **同类写法在别处复制**（先看 `tests/test_endpoint_declarations.py` 中其他把 TTL 设 0 的用例）—— 同类问题可能成片存在。
