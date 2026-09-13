# 潜伏绿（latent-green）：`test_stale_snapshot_survives_a_failed_refresh` 的判别力会静默消失

> **模块**：`gimbal-platform/backend/tests`（声明面回退窗的回归证据）
> **状态**：**已修复**（阶段二 Task 1 的用例迁移把副作用断言补上了）
> **来源**：架构收敛执行会话自查（非 spec 条目）
> **定性**：**latent-green risk** —— 不是「CI 抖动（flaky）」
>
> 正文**保留原记载**（其中失效的行号已就地按符号改指 —— 改动逐条列在文末
> [修复记录](#修复记录) §3）；被修复作废的陈述的更正同见该节。

---

## 0. 先说定性

这不是「偶尔变红」的抖动：**该用例任何情况下都不会红**。风险是反方向的 —— 它有时**根本没有测试它声称测的那条路径**，而结果依然是绿的。这类用例的危险在于：它守护的是「D：TTL 到期且刷新失败 → 旧快照仍服务」（spec §8 的验收要点之一），而这条能力**可以悄悄退化而不被发现**。

---

## 1. 用例的构造

```python
# 该用例原在 tests/test_endpoint_declarations.py（现见文末修复记录）（节选）
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
# src/gimbal-platform/backend/app/services/query_view_cache.py（TtlLruCache.lookup）
age = self._clock() - e.fetched_mono
if age <= self._ttl:          # ttl == 0.0 ⇒ 只有 age == 0.0 才算 fresh
    return e, True
```

**触发条件（判别力消失的那一刻）**：`put` 与第二次 `lookup` 落在**同一个 `time.monotonic()` 取值**上 ⇒ `age == 0.0 ≤ 0.0` ⇒ 判为 fresh ⇒ 回退分支一次都没跑，`calls["fail"] = True` 的桩**根本没被调用**，用例照样绿。

这不是理论上的巧合：两次调用之间只隔着一次 `await`（MockTransport 的本地请求），在时钟分辨率较粗的平台上（Windows 上 `time.monotonic()` 的可用粒度约 15.6ms）完全可以落在同一刻度内。是「有时测、有时没测」，**取决于机器与调度**。

---

## 2. 为什么值得记下来（影响）

- **退化不可见**：`TtlLruCache.put` 的时间戳打点（U）、`lookup` 的 `age <= ttl` 判定、回退时返回缓存里那份**旧快照** —— 这一整条链今天被 D 的验收要点依赖，但守护它的用例**只在某些运行里真的走到**；
- **误诊风险高**：一旦有人真的把 D 改坏，CI 仍可能全绿；反过来，若有人发现「这条用例有时没打桩」而把它当抖动删掉/跳过，就彻底失去守护（这正是本记录要阻止的处置）；
- **不是新缺陷**：生产行为没问题（`TtlLruCache.lookup` 的三段判定是正确的）；问题是**证据本身**。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 不影响任何生产路径；影响的是回归保护的有效性；
- 触发即「判别力丢失」，代价在**未来**（D 退化时无人察觉）。

**可选修法方向（仅备查，不是结论）**：

1. **断言副作用而不只是返回值**：补 `assert calls["n"] == 2`（或断言第二次确实打了 plate 且失败）—— 时间塌缩时该断言会红，把「没测到」暴露出来；
2. **让陈旧性确定化**：`TtlLruCache.__init__` 已支持注入时钟（`clock: Callable[[], float] = time.monotonic`），用可控时钟把 `age` 推到明确大于 0；
3. **两条都做**：1 保证「确实进了回退分支」，2 保证「稳定进入」。

---

## 4. 何时重开

1. **D 的回退语义被改动**（TTL / 回退窗 / `lookup` 判定）—— 先修本条，否则改动是否安全无从判断；
2. **该用例出现「间歇性不打桩」的观察**（例如有人给它加日志/覆盖率后注意到）；
3. **测试套件引入变异测试或覆盖率门禁** —— 这条用例会被立刻标出来；
4. **同类写法在别处复制**（先看 `tests/test_endpoint_declarations.py` 中其他把 TTL 设 0 的用例）—— 同类问题可能成片存在。

---

## 修复记录

**阶段二 Task 1（`plate_client.get_endpoint_full` 承载取数与缓存）**：D 语义（回退窗）随取数
一起上移到 `plate_client`，这条用例跟着搬了家，**并在迁移中补齐了副作用断言** —— 正是本记录
§3 的修法方向 1。提交：`f5e43d8`（新文件与用例）/ `b3cec6a`（旧文件里的同名用例删除）。

### 1. 现在是什么

用例：`tests/test_plate_full_cache.py` 的 `test_stale_snapshot_survives_a_failed_refresh`。
它不再只看返回值 —— 除了「回退后 item 仍是旧快照」，还钉住**只有真的走了回退分支才会有**的
副作用：

```python
assert got.stale is True                  # ← 判别力所在：TTL 命中分支给的是 False
assert got.status == 503, "回退时的状态是那次刷新失败的状态(不是回退快照的)"
assert got.reason, "回退分支的告警必须带失败原因(它此刻就在 reason 里)"
```

### 2. 证据（实测，不是推断）

把 `TtlLruCache` 的时钟**冻成常量**（= 本记录 §1 那个「`put` 与第二次 `lookup` 落在同一个
`time.monotonic()` 取值」的条件，`age == 0.0 ≤ ttl == 0.0` ⇒ 判 fresh）：

- 原样跑：`1 passed`；
- 冻时钟后跑：**FAILED**，报错正是 `assert got.stale is True`（`False is True`），
  而它前面那条断言（declarations 相等）**照样通过** —— 与 §1 的论证一致：只看返回值时，
  「走了回退分支」与「TTL 命中」两条路给的是同一个值。

⇒ 这条用例现在**能抓住**时间塌缩（判别力不再依赖机器时钟粒度）。探针是一次性脚本，未入提交。

### 3. 更正正文里被作废的陈述

1. **用例位置**：`tests/test_endpoint_declarations.py:282-302` → 同名的 `tests/test_plate_full_cache.py`
   用例（旧文件里那份已随迁移删除；派生层自己的回退用例仍在 `test_endpoint_declarations.py`，
   且**带反空转断言** —— 先 `assert got == frozenset(...)`、再断言告警里含 `plate status 503`）。
2. **`_cache().put` 的打点** → `TtlLruCache.put`，打点位置不变（成功之后，U）。
3. **`entry.payload[0]` 回退返回** → 回退返回的是缓存里那份**整份 item**（缓存载荷已泛化为
   `payload`，声明侧现在是 plate 的完整 item）；派生层再从它派生 declarations。
4. **§2/§3 的行号**（`query_view_cache.py:46-48` / `:46-52` / `:33-34`）→ 一律改按符号指
   （`TtlLruCache.lookup` / `TtlLruCache.__init__` 的 `clock` 形参）—— 本计划动的就是该文件，
   行号已漂。

### 4. 同类写法的现状（正文 §4 第 4 条的答案）

`DECLARED_PATHS_TTL_SEC = 0` 的用例现在有 5 处。回退窗相关的那几条都已断言**副作用**
而非只断言返回值，时间塌缩会让它们红：

| 用例 | 钉住的副作用 |
| --- | --- |
| `test_plate_full_cache.py::test_stale_snapshot_survives_a_failed_refresh` | `stale` / `status` / `reason` |
| `test_plate_full_cache.py::test_stale_window_does_not_swallow_an_empty_item` | 刷新成功那一格：`item == {}` + `stale is False` + `status == 200` |
| `test_plate_full_cache.py::test_ttl_zero_refetches` | 请求计数 `len(calls) == 2` |
| `test_endpoint_declarations.py`（派生层回退用例） | 先 `assert got == frozenset(...)`（反空转）+ 告警里含 `plate status 503` |

⇒ 「同类写法复制」这一条在当前这几处**已被回答**；残余风险只剩**新写的** TTL=0 用例可能退回
「只看返回值」的写法（本记录的最初价值即在此，保留）。

### 5. 本条关闭

正文 §4 的触发条件：第 1 条（D 语义被改动）仍有效 —— 但按 §2，改动是否安全现在**有证据可判**；
第 2 条（观察到「间歇性不打桩」）不再适用（判别力已不依赖时钟粒度）；第 3 条（覆盖率门禁）
仍是外部事项。`docs/known-issues/README.md` 索引行的状态同步更新。
