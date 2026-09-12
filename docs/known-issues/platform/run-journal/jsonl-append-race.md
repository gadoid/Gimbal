# 执行日志 JSONL 的写侧并发竞态（`_append_jsonl`）

> **模块**：`gimbal-platform/backend`（`app/services/run_dispatcher.py` 执行日志）
> **状态**：已知未修复
> **来源**：架构收敛执行会话自查（非 spec 条目）
> **证据级别**：机制已读源 + **现场物证**（见 §1 的撕裂行）

---

## 0. 机制

所有 JSONL 行都经同一函数落盘，**append 模式 + 单次 `write`**：

```python
# src/gimbal-platform/backend/app/services/run_dispatcher.py:1443-1446
def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

调用侧在**线程池**里发起：

```python
# src/gimbal-platform/backend/app/services/run_dispatcher.py:1056-1063
async def _append_log(path: Path, payload: dict) -> None:
    """Best-effort JSONL append(to_thread 异步写,不阻塞事件循环)。…"""
    try:
        await asyncio.to_thread(_append_jsonl, path, payload)
```

而 `_append_log` 在 fan-out 的**逐行协程**里被调用，受 `asyncio.Semaphore(parallel)` 限流（`run_dispatcher.py:711` 建闸，`:766` 准入；`:772`、`:817`、`:942` 三处落行）——`parallel` 默认大于 1 时，**多个行协程同时在飞**，各自 `to_thread` 到线程池 ⇒ 同一文件的多个 append 写**并发**发生。

同一份当日文件还有第二个并发来源：**同一个进程/机器上的另一个 server 实例**（测试与开发机上的 live server 都写 `DATA_DIR/runs/<date>.jsonl`；测试侧读的也是它，见 `src/gimbal-platform/backend/tests/test_run_cancel.py:71-80` 与 `src/gimbal-platform/backend/tests/test_run_plate_resilience.py:39-48` 的 `_jsonl_records` → `json.loads(line)` **逐行解析**）。

**为什么会在 Windows 上撕裂**：CPython 在文本 append 模式下的落盘不是 POSIX 意义上的原子追写（Windows 的 CRT 以 `_O_APPEND` 语义处理 append，是「定位到末尾再写」，不是「内核原子追加」）。两个线程各自定位到**同一个末尾偏移**再写，后写者覆盖先写者的字节 ⇒ 文件里留下**撕裂行**。本记录不把该平台细节当作已核证的内部实现结论，而是以 §1 的现场物证为准：**撕裂确实发生了，且形态与「同一偏移被两次写覆盖」一致。**

---

## 1. 现场物证

`src/gimbal-platform/backend/data/runs/2026-09-12.jsonl` 第 **6764** 行（本会话读取，`awk NR==6764`）：

```text
 esult": {"exitCode": 0, "total": 1, "passed": 1, "failed": 0, "skipped": 0}}
```

该行以 `esult": …` 起头 —— 是一个 JSON 对象**中段**的残片（`…"r` + `esult…` 的尾半段），前后相邻行（6763 / 6765）都是完整行。这正是「两个 append 落在同一偏移、后写覆盖前写」的产物：被覆盖那次写入的前半段消失，留下后半段自成一行。

---

## 2. 影响

1. **运行日志（审计面）被静默损坏**：撕裂行不是合法 JSON。任何按行解析该文件的消费者（测试、运维脚本）都会在这里炸。
   - 影响范围可界定：JSONL 是**运维索引**（counts-only），完整证据另有 per-case `result.json`（`run_dispatcher.py:1071-1078`：「JSONL 保持 counts-only(运维索引);完整证据(含 details[] / 兜底 stdout 原文)落在本文件」）⇒ **不是唯一证据源**，这是本条不升级为 P0 的主要理由；
2. **两个既有测试会因此变红**（本会话复核过的解析口径：两者都逐行 `json.loads` 当日的**共享**文件）：
   - `tests/test_run_cancel.py::test_cancel_skips_remaining_rows`（读于 `:120-121`）
   - `tests/test_run_plate_resilience.py::test_breaker_opens_after_consecutive_unavailable`（读于 `:167-172`）
   失败形态是**误报**：与用例断言无关，只与同一天的日志文件里有没有撕裂行有关 ⇒ **顺带污染了不相关的用例**；
3. **写入本身不丢错误**：`_append_log` 捕异常只告警（`run_dispatcher.py:1064-1068`），所以撕裂不会被写侧发现。

---

## 3. 修法是写侧的（记录不主张具体实现）

可选方向（**仅备查，不是结论**）：

- 进程内**写锁**（模块级 `threading.Lock` 包住 open/write/close）—— 治同进程并发，治不了跨进程；
- `os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_BINARY)` + 单次 `os.write` —— 把「一行一次写」做成单次系统调用（跨进程仍取决于平台 append 语义）；
- 单写者模型（一个专职写线程 / 队列消费）—— 上界最强，改动最大。

**不要**用「测试里按行解析时跳过坏行」来收口 —— 那会把审计面的损坏变成不可见（见 §4 第 1 条）。

---

## 4. 优先级：P1

按 README：**触发条件明确、可控、规避成本低**。

- **触发条件明确**：并发 fan-out（`parallel > 1`）或双写者（live server + 测试）同时写当日文件；
- **可控 + 规避成本低**：修法局部（一个函数），不需要动协议或数据结构；
- **为什么不是 P0**：虽然形态是「静默损坏」，但受损的是**运维索引**而非唯一证据（per-case `result.json` 完整），且不改动任何业务结果；
- **若维护者认为 JSONL 就是审计的唯一权威**（例如下游有按它做对账/合规的消费者），**应改判 P0** —— 判据见 README 的 P0 定义（静默错误 / 丢数据）。这一点留给维护者拍板。

---

## 5. 何时重开

1. **测试再次出现「与被测行为无关」的 `json.loads` 失败**（先 grep 当日文件是否存在撕裂行再判定）；
2. **JSONL 成为下游权威数据源**（对账 / 合规 / 计费）⇒ 立即按 P0 处理；
3. **fan-out 并发度调大**（`parallel` 默认值上调）或**部署形态变为多进程写同一 `DATA_DIR`**；
4. **引入结构化日志 / 入库**（spec §4.5 已把「JSONL 是否随之入库」记为独立议题）—— 那一轮顺手收口最省。
