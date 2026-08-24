# 执行器 Platform 侧缺陷修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-08-24 执行器评审(仅 platform 侧)确认的 P1–P9 及低危项:证据落盘、关闭窗口吞单、重启 reconcile、案卷生命周期、取消、env 服务端权威、plate memo+熔断、总量/并发闸、计数器完整性、JSONL 异步化、分页与文档。

**Architecture:** 全部改动收敛在 `gimbal-platform/backend`(Task 11 为配套前端)。`gimbal` 引擎(`src/gimbal/**`)**零改动**——子进程边界(argv 进 / stdout JSON 出)保持原样。执行链主结构(dispatch → _fanout → per-row 七步 → launcher)不变,只修缺陷不改架构。

**Tech Stack:** FastAPI + SQLAlchemy async + pytest(async)+ Vue3/Pinia 前端。

**Spec:** 本文件 §「设计决策」小节(需求来源:2026-08-24 执行器评审会话,评审结论 P1–P9 即需求;无独立 spec 文件)。

## Global Constraints

- **禁止触碰 `src/gimbal-platform/backend/probe_ui.js`**(不读不写不提交)。
- **禁止修改 `src/gimbal/**` 任何文件**(本轮只修 platform;引擎侧发现已另行记录,不在本计划)。
- 测试运行目录:`src/gimbal-platform/backend`,命令 `python -m pytest tests/<file> -v`(venv 已激活)。
- 注释/文档风格随所在文件现状(该仓库为英文 docstring + 中文行内注释混排,新代码照抄邻近风格)。
- 提交信息沿用仓库现行风格:`fix(platform): …` 中文主题,每 Task 一次提交。
- 新配置项全部进 `app/core/config.py` 的 `Settings`,默认值用本计划给出的精确值,**不得另造默认值**。
- `LaunchResult.run_result`(JSONL `runResult` 字段)保持 counts-only 契约不变——完整证据走 per-case `result.json` 新工件,不改旧字段形状。

## 测试基座(所有新测试文件共用)

`tests/helpers.py` 已提供,**勿重复造**:

- `register_and_login(client) -> headers` — 注册+登录(alice/alicepass123)。
- `make_draft(scenario_id, *, steps=, vars_map=, **meta_over) -> dict` — 最小合法 ScenarioDraft。
- `test_env() -> dict` — `{"envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://x"}`,与 env_store 内置 `test-env-A` 一致(篡改 baseUrl 的 P5 测试以此值为服务端真值)。
- `launch_ok()` — 绿色 LaunchResult;`wait_until(predicate, timeout_s=5.0)` — 异步轮询。
- `client: AsyncClient` fixture 由 conftest 提供,签名 `async def test_x(client, monkeypatch)`。

标准派发模式(monkeypatch 两个模块属性即断流 plate/launch——dispatcher 经模块属性调用,此接法已被 `test_run_baseline.py` 验证):

```python
async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None):
    return _ok()          # 或自定义 LaunchResult

async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}

from app.services import gimbal_launcher as gl, plate_client as pc
monkeypatch.setattr(gl, "launch", _fake_launch)
monkeypatch.setattr(pc, "convert", _fake_convert)

r = await client.post("/api/runs", headers=headers, json={
    "scenarioId": "sc-x", "dataSetIds": [], "env": test_env(),
    # 可选: "nRuns": 3, "parallel": 2
})
assert r.status_code == 201, r.text
```

多行数据集:`await client.post(f"/api/scenarios/{sid}/data-sets", headers=headers, json={"name": "ds", "rows": [{"customer_id": "1"}, ...]})` → `dataset_id = r.json()["datasetId"]`(行键须 ⊆ 场景 `vars_map` 声明)。

Execution 轮询与插行(直读库;`import sqlalchemy as sa`):

```python
from app.core import db as db_module
from app.models.execution import Execution

async def _get_execution(eid: int) -> Execution | None:
    async with db_module.SessionLocal() as s:
        return await s.get(Execution, eid)

async def _wait_terminal(eid: int, statuses=("done", "failed", "canceled")) -> Execution:
    row = None
    for _ in range(100):
        row = await _get_execution(eid)
        if row is not None and row.status in statuses:
            return row
        await asyncio.sleep(0.05)
    raise AssertionError(f"execution {eid} never reached {statuses}: {row and row.status}")

async def _seed_execution(owner_id: int, **over) -> int:
    fields = dict(scenario_id="sc-x", owner_id=owner_id, status="queued",
                  total_runs=2, passed=0, failed=0, config_json={"runId": "run-x"})
    fields.update(over)
    async with db_module.SessionLocal() as s:
        ex = Execution(**fields); s.add(ex); await s.commit(); await s.refresh(ex)
        return ex.id
```

JSONL 断言一律**逐行 `json.loads` 后取字段**,不断言原文子串(dump 分隔符是实现细节):

```python
def _jsonl_records(run_dispatcher) -> list[dict]:
    text = run_dispatcher._jsonl_path().read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]
```

以上四个局部 helper 直接放各自测试文件顶部(跨文件复用时是否上收 helpers.py 由执行者按 DRY 判断)。

## 设计决策(评审 P# → 选定方案,执行中冲突以此为准)

| 缺陷 | 决策 | 落点 |
|---|---|---|
| P1 证据丢失 | per-case `result.json` 全量证据(details[]/stdout 兜底);JSONL 维持 counts-only | Task 1 |
| P9 JSONL 同步 IO | `asyncio.to_thread` 异步化(**先做**,后续任务的日志调用直接用新形态) | Task 2 |
| P8 计数漂移 | bump 重试一次,双败写 JSONL 记账行;finalize 校账 `passed+failed==total_runs`,漂移置 `config_json.counterDrift` | Task 2 |
| P3 关闭窗口吞单 | `dispatch_run` 入口检查 `is_shutting_down()` → `Conflict("shutting_down")` → 409,行不再创建 | Task 3 |
| P3 重启无 reconcile | `startup_recovery()`:启动期把 stale `queued` 批量标 failed + `config_json.reconciled` 记录 | Task 4 |
| P2 案卷/凭证留存 | 删除执行 → 同步清 case 目录;启动期保留期清扫(`CASE_RETENTION_DAYS`,0=禁用);JSONL 按日期分文件**仍不随删**(现行设计) | Task 5 |
| P4 无取消 | **协作式取消**(行边界检查,不打断在飞子进程——避免 Windows 下 task.cancel 泄漏 gimbal 子进程);新状态 `canceled`;zombie(无在飞 task)立即终态化 | Task 6 |
| P5 baseUrl 客户端直供 | 服务端权威:按 envId 从 `env_store.list_envs()` 取 name/baseUrl,客户端值不一致仅告警不采信 | Task 7 |
| P6 plate 重复+无熔断 | fanout 内按 convert 输入哈希 memo;连续 `PlateUnavailableError` ≥ 阈值开路,剩余行快速失败不再调用 | Task 8 |
| P7 无总量/并发闸 | `MAX_RUNS_PER_EXECUTION`(409 拒单)+ 进程级 launch 信号量(按事件循环缓存,避免 pytest 多循环踩同一个 Semaphore) | Task 9 |
| 低:分页/docstring | list 加 limit/offset(默认 200 向后兼容,前端已消费 {items,total} 信封);修 2 处过期 docstring | Task 10 |
| P4/P1 前端闭环 | `canceled` 状态文案/颜色/轮询终止 + 列表页取消按钮 | Task 11 |

明确不做(记录在案,勿在本计划中夹带):exit 2 三源细分(诊断粒度,另议)、per-scenario 超时覆盖、`gimbal run server` 死界面清理、`--reporter` 透传(被 result.json 方案取代)。

---

### Task 1: P1 — per-case `result.json` 全量证据

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/gimbal_launcher.py`(`parse_run_result` :109-138、`LaunchResult` :38-75)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`_row` 内 launch 后,约 :381-437)
- Test: `src/gimbal-platform/backend/tests/test_gimbal_launcher.py`(扩展)、`src/gimbal-platform/backend/tests/test_run_evidence.py`(新建)

**Interfaces:**
- Produces: `LaunchResult.details: list[dict[str, Any]]`(默认 `[]`);`parse_run_result` 返回 dict 新增 `details` 键(list,缺省 `[]`)——`run_result` 属性形状**不变**。
- Produces: `run_dispatcher._write_result_evidence(case_dir: Path, result: LaunchResult, status: str) -> None`(模块私有,best-effort)。

- [ ] **Step 1: 写失败测试(launcher 解析 details)**

`tests/test_gimbal_launcher.py` 追加:

```python
def test_parse_run_result_extracts_details():
    stdout = (
        '{"exit_code": 1, "total": 2, "passed": 1, "failed": 1, "skipped": 0, '
        '"details": [{"step_id": "s1", "status": "failed", "error": "boom", '
        '"error_phase": "verifying"}]}'
    )
    counts = parse_run_result(stdout)
    assert counts is not None
    assert counts["details"] == [
        {"step_id": "s1", "status": "failed", "error": "boom", "error_phase": "verifying"}
    ]


def test_parse_run_result_details_missing_defaults_empty():
    counts = parse_run_result('{"exit_code": 0, "total": 1, "passed": 1}')
    assert counts is not None
    assert counts["details"] == []
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_gimbal_launcher.py -v -k details`
Expected: FAIL(`KeyError: 'details'` 或断言失败)

- [ ] **Step 3: 实现 launcher 侧**

`gimbal_launcher.py`:

3a. `LaunchResult` 增字段(放 `skipped` 之后、`error` 之前):

```python
    # 步骤级明细(-o json stdout 里的 details[];解析失败/兜底路径为 [])。
    details: list[dict[str, Any]] = field(default_factory=list)
```

3b. `parse_run_result` 命中对象后的返回 dict 增加一行(在 `"skipped": …` 之后):

```python
                "details": [d for d in (data.get("details") or []) if isinstance(d, dict)],
```

3c. `launch()` 解析成功分支(:227-236)的 `LaunchResult(...)` 增加 `details=counts["details"],`;counts-None 兜底分支(:219-225)`details` 走默认 `[]`。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_gimbal_launcher.py -v`
Expected: PASS(全部,含存量)

- [ ] **Step 5: 写失败测试(dispatcher 落盘 result.json)**

新建 `tests/test_run_evidence.py`(顶部按「测试基座」放 `_fake_convert` 等局部 helper):

```python
"""P1 证据落盘:每个 case 目录写 result.json(details/兜底 stdout)。"""
import json

from tests.helpers import make_draft, register_and_login, test_env


async def test_row_writes_result_json_with_details(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-evidence"))

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    fake = gl.LaunchResult(
        launch_status="ok", exit_code=1, total=2, passed=1, failed=1,
        skipped=0, error="",
        details=[{"step_id": "s1", "status": "failed", "error": "boom"}],
    )

    async def _launch(*a, **k):
        return fake

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(gl, "launch", _launch)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-evidence", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]

    result_files = list(run_dispatcher._run_dir(run_id).rglob("result.json"))
    assert len(result_files) == 1
    payload = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"          # exit 1 → failed 行
    assert payload["launchStatus"] == "ok"
    assert payload["details"] == [
        {"step_id": "s1", "status": "failed", "error": "boom"}
    ]
    assert "stdout" not in payload                # 有 details 不带 stdout 兜底


async def test_row_writes_result_json_stdout_fallback(client, monkeypatch):
    # counts=None 兜底路径:details 为空时保留 stdout 原文作证据
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-evidence2"))

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    fake = gl.LaunchResult(launch_status="ok", exit_code=2,
                           error="usage: bad case", stdout="not-json")

    async def _launch(*a, **k):
        return fake

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(gl, "launch", _launch)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-evidence2", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]

    result_files = list(run_dispatcher._run_dir(run_id).rglob("result.json"))
    assert len(result_files) == 1
    payload = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert payload["exitCode"] == 2
    assert payload["stdout"] == "not-json"
    assert payload["details"] == []
```

- [ ] **Step 6: 运行验证失败**

Run: `python -m pytest tests/test_run_evidence.py -v`
Expected: FAIL(找不到 result.json)

- [ ] **Step 7: 实现 dispatcher 侧**

`run_dispatcher.py`:

7a. 新增模块级 helper(放 `_append_log_quietly` 附近):

```python
def _write_result_evidence(
    case_dir: Path, result: gimbal_launcher.LaunchResult, status: str
) -> None:
    """P1 证据落盘:per-case result.json(步骤级 details 完整保留)。

    JSONL 保持 counts-only(运维索引);完整证据(含 details[] / 兜底
    stdout 原文)落在本文件,与 case.json 同目录构成审计面。
    Best-effort:写失败只告警,绝不打断行执行。
    """
    payload: dict[str, Any] = {
        "launchStatus": result.launch_status,
        "exitCode": result.exit_code,
        "status": status,
        "total": result.total,
        "passed": result.passed,
        "failed": result.failed,
        "skipped": result.skipped,
        "details": result.details,
        "error": result.error,
    }
    if not result.details and result.stdout:
        # 引擎未给出可解析 JSON 报告(如 exit 2 走 typer err)时保留原文。
        payload["stdout"] = result.stdout
    try:
        (case_dir / "result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: failed to write result.json for {}: {}",
            case_dir, e,
        )
```

7b. `_row` 内,状态映射 if/elif/else 链之后、`_append_log_quietly(log_path, log_line)`(:437)之前加:

```python
            # P1:引擎结果全量证据落盘(仅真实拿到 LaunchResult 的路径;
            # plate 异常分支不设 runResult,短路跳过)。
            if "runResult" in log_line:
                _write_result_evidence(case_dir, result, log_line["status"])
```

- [ ] **Step 8: 运行验证通过 + 全量回归**

Run: `python -m pytest tests/test_run_evidence.py tests/test_run_baseline.py tests/test_run_m1_capabilities.py -v`
Expected: PASS 全部

- [ ] **Step 9: Commit**

```bash
git add src/gimbal-platform/backend/app/services/gimbal_launcher.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_gimbal_launcher.py src/gimbal-platform/backend/tests/test_run_evidence.py
git commit -m "fix(platform): P1 执行证据落盘 — per-case result.json 保留步骤级 details"
```

---

### Task 2: P9+P8 — JSONL 异步化 + 计数器完整性

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`_append_log_quietly` :489-497、`_bump_counters` :500-523、`_finalize_execution` :526-544、`_fail_whole_execution` :464-486、`_row` 两处调用 :352/:437)
- Modify: `src/gimbal-platform/backend/app/models/execution.py`(:29 加常量)
- Test: `src/gimbal-platform/backend/tests/test_run_log_integrity.py`(新建)

**Interfaces:**
- Produces: `async def _append_log(path: Path, payload: dict) -> None`(替代同步 `_append_log_quietly`;所有调用点 await)。测试可 monkeypatch `_append_jsonl`。
- Produces: `_finalize_execution(db_factory, execution_id, *, status: str | None = None)`(None=现行 failed/done 判定;canceled 终态化时跳过校账——Task 6 依赖此签名)。
- Produces: `models.execution.STATUS_CANCELED = "canceled"`(先行引入,避免 T6 前向引用)。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_run_log_integrity.py`(顶部按「测试基座」放 `_seed_execution`;`db_module.SessionLocal` 即满足 db_factory 契约——`async with factory() as session`):

```python
"""P8/P9:JSONL 异步写 + 计数器重试与漂移校账。"""
import asyncio

from tests.helpers import register_and_login


async def test_append_log_is_async_and_tolerates_failure(tmp_path, monkeypatch):
    from app.services import run_dispatcher

    written = []

    def fake_append(path, payload):
        written.append(payload)
        if payload.get("boom"):
            raise OSError("disk full")

    monkeypatch.setattr(run_dispatcher, "_append_jsonl", fake_append)
    await run_dispatcher._append_log(tmp_path / "a.jsonl", {"x": 1})
    await run_dispatcher._append_log(tmp_path / "a.jsonl", {"boom": 1})  # 不抛
    assert written[0] == {"x": 1}


async def test_bump_counters_retries_once(monkeypatch):
    from app.services import run_dispatcher

    factory_calls = {"n": 0}

    class FlakySession:
        def __init__(self):
            self.nth = 0

        async def __aenter__(self):
            factory_calls["n"] += 1
            self.nth = factory_calls["n"]
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a, **k):
            if self.nth == 1:
                raise OSError("db locked")
            return None

        async def commit(self):
            return None

    def factory():
        return FlakySession()

    await run_dispatcher._bump_counters(factory, 999, passed=0, failed=1)
    assert factory_calls["n"] == 2          # 第一次失败,重试一次


async def test_bump_counters_double_failure_logs_jsonl(monkeypatch, tmp_path):
    from app.services import run_dispatcher

    async def dead_factory():
        raise OSError("db gone")

    monkeypatch.setattr(run_dispatcher, "_jsonl_path", lambda: tmp_path / "r.jsonl")
    recorded = []

    async def fake_append(path, payload):
        recorded.append(payload)

    monkeypatch.setattr(run_dispatcher, "_append_log", fake_append)
    await run_dispatcher._bump_counters(dead_factory, 999, passed=1, failed=0)
    assert recorded and recorded[0]["status"] == "counter_bump_failed"


async def test_finalize_flags_counter_drift():
    from app.core import db as db_module
    from app.services import run_dispatcher
    from tests.helpers import register_and_login  # noqa: F401 — DB 由 conftest 备好

    eid = await _seed_execution(1, status="queued", total_runs=2,
                                passed=0, failed=0)
    await run_dispatcher._finalize_execution(db_module.SessionLocal, eid)
    row = await _get_execution(eid)
    assert row.status == "done"             # failed=0 → done
    assert row.config_json.get("counterDrift") is True   # 0+0 != 2


async def test_finalize_no_drift_when_consistent():
    from app.core import db as db_module
    from app.services import run_dispatcher

    eid = await _seed_execution(1, status="queued", total_runs=2,
                                passed=1, failed=1)
    await run_dispatcher._finalize_execution(db_module.SessionLocal, eid)
    row = await _get_execution(eid)
    assert row.status == "done"
    assert "counterDrift" not in (row.config_json or {})
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_log_integrity.py -v`
Expected: FAIL(`_append_log` 不存在 / 无重试 / 无 counterDrift)

- [ ] **Step 3: 实现**

`run_dispatcher.py`:

3a. `_append_log_quietly` 改名并异步化(函数体整体替换):

```python
async def _append_log(path: Path, payload: dict) -> None:
    """Best-effort JSONL append(to_thread 异步写,不阻塞事件循环)。

    写失败只告警,绝不打断 fan-out(P9:原同步写在逐行大单下会
    阻塞 loop)。
    """
    try:
        await asyncio.to_thread(_append_jsonl, path, payload)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: failed to write JSONL log line for {}: {}",
            payload.get("runId"), e,
        )
```

3b. 全部调用点改 `await _append_log(...)`:`_row` :352、:437;`_fail_whole_execution` :478。

3c. `_bump_counters` 整体替换:

```python
async def _bump_counters(
    db_factory: Any, execution_id: int, *, passed: int, failed: int
) -> None:
    """Atomic Execution counter bump(P8:失败重试一次,双败 JSONL 记账)。

    Deltas(not absolute write-backs)so concurrent rows and concurrent
    UI deletions compose correctly.
    """
    for attempt in (1, 2):
        try:
            async with db_factory() as session:
                await session.execute(
                    sqlalchemy_update(Execution)
                    .where(Execution.id == execution_id)
                    .values(
                        passed=Execution.passed + passed,
                        failed=Execution.failed + failed,
                    )
                )
                await session.commit()
            return
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                logger.error(
                    "run_dispatcher: counter bump failed twice for execution {}: {}",
                    execution_id, e,
                )
                await _append_log(_jsonl_path(), {
                    "ts": _utcnow().isoformat() + "Z",
                    "executionId": execution_id,
                    "status": "counter_bump_failed",
                    "error": repr(e),
                    "deltas": {"passed": passed, "failed": failed},
                })
```

3d. `_finalize_execution` 整体替换:

```python
async def _finalize_execution(
    db_factory: Any, execution_id: int, *, status: str | None = None
) -> None:
    """终态收尾:只写 status + 时间戳(计数器由上方增量维护)。

    ``status`` 显式覆盖用于取消终态(canceled);缺省沿用严格规则
    ``failed > 0 → failed``。P8:非 canceled 终态校账
    ``passed + failed == total_runs``,漂移只标记不修正(counterDrift
    供读侧发现"数字对不上",真值以 JSONL 为准)。
    """
    try:
        async with db_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is not None:
                final_status = status or (
                    STATUS_FAILED if ex.failed else STATUS_DONE
                )
                ex.status = final_status
                if ex.started_at is None:
                    ex.started_at = _utcnow()
                ex.finished_at = _utcnow()
                if (
                    final_status != STATUS_CANCELED
                    and ex.passed + ex.failed != ex.total_runs
                ):
                    logger.error(
                        "run_dispatcher: counter drift execution {}: "
                        "total={} passed+failed={}",
                        execution_id, ex.total_runs, ex.passed + ex.failed,
                    )
                    cfg = dict(ex.config_json or {})
                    cfg["counterDrift"] = True
                    ex.config_json = cfg
                await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: failed to update execution {}: {}", execution_id, e)
```

3e. `app/models/execution.py` :29 后加,并同步 :41 状态注释与 run_dispatcher 的常量导入(与现有 STATUS_QUEUED/STATUS_FAILED/DONE 同行或同风格):

```python
STATUS_CANCELED = "canceled"
```

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_run_log_integrity.py tests/test_run_baseline.py tests/test_run_evidence.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/app/models/execution.py src/gimbal-platform/backend/tests/test_run_log_integrity.py
git commit -m "fix(platform): P8/P9 计数器重试+校账标记、JSONL 异步写、引入 canceled 状态常量"
```

---

### Task 3: P3a — 关闭窗口拒单(不再静默制造永挂单)

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`dispatch_run` 入口 :128 之后、任何 DB 写之前)
- Test: `src/gimbal-platform/backend/tests/test_run_log_integrity.py`(追加)

**Interfaces:**
- Consumes: 现有 `Conflict(code, message)` typed error(runs.py 已映射 409)。

- [ ] **Step 1: 写失败测试**

`tests/test_run_log_integrity.py` 追加:

```python
async def test_dispatch_rejects_when_shutting_down(client, monkeypatch):
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution
    from app.services import run_dispatcher
    from tests.helpers import make_draft, register_and_login, test_env

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-shutdown"))

    run_dispatcher._shutting_down = True
    try:
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-shutdown", "dataSetIds": [], "env": test_env(),
        })
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "shutting_down"
        async with db_module.SessionLocal() as s:
            n = (await s.execute(
                sa.select(sa.func.count()).select_from(Execution)
            )).scalar_one()
        assert n == 0                      # 不留 Execution 行
    finally:
        run_dispatcher._shutting_down = False
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_log_integrity.py -v -k shutting`
Expected: FAIL(当前返回 201)

- [ ] **Step 3: 实现**

`dispatch_run` 函数体第一行(签名/docstring 之后、场景校验之前)加:

```python
    # P3:优雅关闭窗口内不再"建行但不 spawn"(那会制造一条 201 返回、
    # 永远停在 queued 的僵尸单)。直接拒单,客户端重启后重试。
    if is_shutting_down():
        raise Conflict(
            "shutting_down",
            "platform is shutting down; retry after the backend restarts",
        )
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_run_log_integrity.py tests/test_run_baseline.py -v`
Expected: PASS(存量 baseline 用例在非关闭态不受影响)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_log_integrity.py
git commit -m "fix(platform): P3 关闭窗口拒单 409 — 不再静默制造 queued 僵尸执行"
```

---

### Task 4: P3b — 启动期 reconcile(startup_recovery)

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(新增公开函数)
- Modify: `src/gimbal-platform/backend/app/main.py`(lifespan,`reset_shutdown_state()` 调用点 :63 之后)
- Test: `src/gimbal-platform/backend/tests/test_run_log_integrity.py`(追加)

**Interfaces:**
- Produces: `async def reconcile_stale_executions(db_factory) -> int`;`async def startup_recovery() -> tuple[int, int]`(内部用 `_session_factory`,返回 `(stale_executions, swept_case_dirs)`,清扫数 Task 5 接线)。

- [ ] **Step 1: 写失败测试**

`tests/test_run_log_integrity.py` 追加:

```python
async def test_reconcile_marks_stale_queued_failed():
    from app.core import db as db_module
    from app.services import run_dispatcher

    eid = await _seed_execution(1, status="queued")
    n = await run_dispatcher.reconcile_stale_executions(db_module.SessionLocal)
    assert n == 1
    row = await _get_execution(eid)
    assert row.status == "failed"
    assert row.finished_at is not None
    assert row.config_json["reconciled"]["reason"] == "backend restarted mid-dispatch"


async def test_reconcile_ignores_terminal():
    from app.core import db as db_module
    from app.services import run_dispatcher

    eid = await _seed_execution(1, status="done")
    n = await run_dispatcher.reconcile_stale_executions(db_module.SessionLocal)
    assert n == 0
    assert (await _get_execution(eid)).status == "done"
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_log_integrity.py -v -k reconcile`
Expected: FAIL(函数不存在)

- [ ] **Step 3: 实现**

3a. `run_dispatcher.py` 新增(需 `from sqlalchemy import select` 若未导入;放 drain/reset 生命周期函数附近;`session_factory` 公开别名放 `_session_factory` 定义旁):

```python
async def reconcile_stale_executions(db_factory: Any) -> int:
    """启动期 reconcile:进程内 _fanout 随重启丢失,queued 即僵尸。

    全部标 failed + ``config_json.reconciled`` 记录(P3:此前永远
    停在 queued,UI 无从得知)。返回处理行数。
    """
    count = 0
    async with db_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Execution).where(Execution.status == STATUS_QUEUED)
                )
            )
            .scalars()
            .all()
        )
        for ex in rows:
            ex.status = STATUS_FAILED
            if ex.started_at is None:
                ex.started_at = ex.created_at or _utcnow()
            ex.finished_at = _utcnow()
            cfg = dict(ex.config_json or {})
            cfg["reconciled"] = {
                "at": _utcnow().isoformat() + "Z",
                "reason": "backend restarted mid-dispatch",
            }
            ex.config_json = cfg
            count += 1
        await session.commit()
    if count:
        logger.warning(
            "run_dispatcher: reconciled {} stale queued execution(s) after restart",
            count,
        )
    return count


async def startup_recovery() -> tuple[int, int]:
    """启动恢复:reconcile 僵尸执行 + 清扫过期 case 目录(Task 5 接入)。"""
    stale = await reconcile_stale_executions(_session_factory)
    swept = 0  # Task 5: swept = sweep_stale_case_dirs()
    return stale, swept
```

3b. `main.py` lifespan 内 `reset_shutdown_state()`(:63)之后加(导入块 :56-59 追加 `startup_recovery`):

```python
    # P3:重启后把丢失 _fanout 的 queued 僵尸单收敛为 failed。
    try:
        n_stale, _swept = await startup_recovery()
        if n_stale:
            logger.warning("lifespan: reconciled {} stale execution(s)", n_stale)
    except Exception as e:  # noqa: BLE001
        logger.error("lifespan: startup recovery failed: {}", e)
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_run_log_integrity.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/app/main.py src/gimbal-platform/backend/tests/test_run_log_integrity.py
git commit -m "fix(platform): P3 启动期 reconcile — queued 僵尸执行标 failed 并留痕"
```

---

### Task 5: P2 — 删除清案卷 + 保留期清扫

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/config.py`(Settings 增 `CASE_RETENTION_DAYS: int = 14`,放 DATA_DIR 块内)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`purge_case_dir` / `sweep_stale_case_dirs` / `startup_recovery` 接线)
- Modify: `src/gimbal-platform/backend/app/services/execution_store.py`(`delete_execution` :28-31)
- Test: `src/gimbal-platform/backend/tests/test_run_case_retention.py`(新建)

**Interfaces:**
- Produces: `run_dispatcher.purge_case_dir(run_id: str) -> None`(public);`run_dispatcher.sweep_stale_case_dirs() -> int`。
- Consumes: `execution_store.delete_execution` 读 `ex.config_json["runId"]`。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_run_case_retention.py`(顶部按「测试基座」放 `_fake_launch`/`_fake_convert`;`_make_case_dir` 为本文件私有):

```python
"""P2 案卷生命周期:删除执行清 case 目录;启动清扫过期目录。"""
import os
import time


def _make_case_dir(run_dispatcher, run_id: str, age_days: float = 0):
    d = run_dispatcher._run_dir(run_id) / "case-001-baseline-r0-n0"
    d.mkdir(parents=True, exist_ok=True)
    (d / "case.json").write_text("{}", encoding="utf-8")
    if age_days:
        stamp = time.time() - age_days * 86400
        os.utime(d.parent, (stamp, stamp))
        os.utime(d, (stamp, stamp))
    return d


async def test_delete_execution_purges_case_dir(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher
    from tests.helpers import make_draft, register_and_login, test_env

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-purge"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-purge", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 201, r.text
    run_id, eid = r.json()["runId"], r.json()["executionId"]
    await _wait_terminal(eid)
    assert run_dispatcher._run_dir(run_id).exists()

    r = await client.delete(f"/api/executions/{eid}", headers=headers)
    assert r.status_code == 204
    assert not run_dispatcher._run_dir(run_id).exists()
    # JSONL 按日期分文件,设计上不随删
    assert run_dispatcher._jsonl_path().exists()


def test_sweep_removes_old_dirs_only(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import run_dispatcher

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    _make_case_dir(run_dispatcher, "old-run", age_days=30)
    _make_case_dir(run_dispatcher, "new-run", age_days=0)
    removed = run_dispatcher.sweep_stale_case_dirs()
    assert removed == 1
    assert not (tmp_path / "runs" / "cases" / "old-run").exists()
    assert (tmp_path / "runs" / "cases" / "new-run").exists()


def test_sweep_disabled_when_zero(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import run_dispatcher

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "CASE_RETENTION_DAYS", 0)
    _make_case_dir(run_dispatcher, "old-run", age_days=365)
    assert run_dispatcher.sweep_stale_case_dirs() == 0
    assert (tmp_path / "runs" / "cases" / "old-run").exists()
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_case_retention.py -v`
Expected: FAIL(函数不存在/目录残留)

- [ ] **Step 3: 实现**

3a. `config.py` Settings 的 Data dir 块加:

```python
    # case 案卷(result.json/case.json,含注入后明文凭证)保留天数;
    # 启动期清扫超期目录。0 = 禁用清扫(P2:此前无限累积)。
    CASE_RETENTION_DAYS: int = 14
```

3b. `run_dispatcher.py` 新增(需 `import shutil`、`import time`;放 `_run_dir` :766 附近):

```python
def purge_case_dir(run_id: str) -> None:
    """删除整单的 case 案卷目录(P2:case.json 含明文凭证,删除执行
    必须连带清理,否则 UI 删除后凭证仍永久留盘)。Best-effort。"""
    shutil.rmtree(_run_dir(run_id), ignore_errors=True)


def sweep_stale_case_dirs() -> int:
    """启动期保留期清扫:删除 mtime 超过 CASE_RETENTION_DAYS 的 run 目录。

    0 = 禁用。JSONL 按日期分文件、不在此清理(现行设计)。
    """
    days = settings.CASE_RETENTION_DAYS
    if days <= 0:
        return 0
    root = settings.DATA_DIR / "runs" / "cases"
    if not root.exists():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for child in root.iterdir():
        try:
            stale = child.is_dir() and child.stat().st_mtime < cutoff
        except OSError:
            continue
        if stale:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    if removed:
        logger.info("run_dispatcher: swept {} stale case dir(s) (> {}d)", removed, days)
    return removed
```

3c. `startup_recovery` 的 `swept = 0` 行替换为 `swept = sweep_stale_case_dirs()`。

3d. `execution_store.py` `delete_execution` 整体替换:

```python
async def delete_execution(session: AsyncSession, ex: Execution) -> None:
    """删除整单 + 连带清理 case 案卷目录(P2:案卷含明文凭证)。

    调度日志(data/runs/*.jsonl)按日期分文件、不随删(现行设计)。
    """
    from . import run_dispatcher

    run_id = (ex.config_json or {}).get("runId")
    await session.delete(ex)
    await session.commit()
    if run_id:
        run_dispatcher.purge_case_dir(str(run_id))
```

(函数内延迟导入;run_dispatcher 不导入 execution_store,无环。)

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_run_case_retention.py tests/test_executions.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/core/config.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/app/services/execution_store.py src/gimbal-platform/backend/tests/test_run_case_retention.py
git commit -m "fix(platform): P2 删除执行清案卷 + case 目录保留期清扫(CASE_RETENTION_DAYS)"
```

---

### Task 6: P4 — 协作式取消

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(取消注册表、`_row` 入口、fanout 收尾、`dispatch_run` 登记 task)
- Modify: `src/gimbal-platform/backend/app/routers/executions.py`(新端点)
- Test: `src/gimbal-platform/backend/tests/test_run_cancel.py`(新建)

**Interfaces:**
- Produces: `run_dispatcher.request_cancel(execution_id: int) -> None`;`run_dispatcher.has_live_fanout(execution_id: int) -> bool`;`run_dispatcher.reset_cancel_state() -> None`(测试用)。
- Produces: `POST /api/executions/{execution_id}/cancel` → `ExecutionOut`;终态单 → 409 `{code: "not_cancelable"}`。
- Consumes: Task 2 的 `_finalize_execution(status=...)`、`STATUS_CANCELED`、`await _append_log(...)`。

**取消语义(写进代码注释):协作式——只在未来行边界生效,在飞子进程自然跑完(Windows 下 task.cancel 会让 asyncio 放弃收尸、泄漏 gimbal 子进程,不做);未跑行记 `canceled` JSONL 行、不进计数器;`total_runs` 不变,canceled 单允许 `passed+failed < total_runs`(finalize 跳过校账)。**

- [ ] **Step 1: 写失败测试**

新建 `tests/test_run_cancel.py`(顶部按「测试基座」放 `_get_execution`/`_wait_terminal`/`_seed_execution`/`_fake_convert`):

```python
"""P4 协作式取消:行边界生效、canceled 终态、终态单 409。"""
import asyncio

from tests.helpers import (
    launch_ok as _ok,
    make_draft,
    register_and_login,
    test_env,
    wait_until,
)


async def test_cancel_skips_remaining_rows(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cancel", vars_map={"customer_id": "1"}))
    r = await client.post("/api/scenarios/sc-cancel/data-sets", headers=headers,
                          json={"name": "ds", "rows": [
                              {"customer_id": str(i)} for i in range(6)]})
    ds_id = r.json()["datasetId"]

    done = {"n": 0}

    async def _slow_launch(*a, **k):
        await asyncio.sleep(0.02)
        done["n"] += 1
        return _ok()

    monkeypatch.setattr(gl, "launch", _slow_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cancel", "dataSetIds": [ds_id], "env": test_env(),
        "parallel": 1,
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    await wait_until(lambda: done["n"] >= 1)     # 至少一行落地后取消
    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text

    row = await _wait_terminal(eid)
    assert row.status == "canceled"
    assert row.passed + row.failed < row.total_runs   # 有行被跳过

    records = _jsonl_records(run_dispatcher)
    assert any(rec.get("status") == "canceled" for rec in records)


async def test_cancel_terminal_conflicts(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cancel-done"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cancel-done", "dataSetIds": [], "env": test_env(),
    })
    eid = r.json()["executionId"]
    await _wait_terminal(eid)

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 409, cr.text
    assert cr.json()["detail"]["code"] == "not_cancelable"


async def test_cancel_zombie_finalizes_immediately(client):
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    eid = await _seed_execution(me["user"]["id"], status="queued")  # MeOut 信封

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["status"] == "canceled"
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_cancel.py -v`
Expected: FAIL(404 无 cancel 路由)

- [ ] **Step 3: 实现**

3a. `run_dispatcher.py` 模块级(放 `_in_flight` 附近):

```python
# 取消注册表(P4 协作式取消):取消请求集合 + 在飞 fanout task 索引。
_cancel_requested: set[int] = set()
_tasks_by_execution: dict[int, asyncio.Task] = {}


def request_cancel(execution_id: int) -> None:
    """登记取消请求(幂等);由 _fanout 在行边界消费。"""
    _cancel_requested.add(execution_id)


def has_live_fanout(execution_id: int) -> bool:
    return execution_id in _tasks_by_execution


def reset_cancel_state() -> None:
    """测试隔离:清空取消注册表。"""
    _cancel_requested.clear()
    _tasks_by_execution.clear()
```

3b. `dispatch_run` 现有 `_track(task)`(:254)后加登记与出清:

```python
        _tasks_by_execution[execution.id] = task
        task.add_done_callback(
            lambda _t, eid=execution.id: _tasks_by_execution.pop(eid, None)
        )
```

(`_in_flight.discard` 的既有 done_callback 保持不动,两个回调并存。)

3c. `_row` 入口(`async with sem:` 之前)加:

```python
        if execution_id in _cancel_requested:
            # P4 协作式取消:未启动的行直接记 canceled,不进计数器。
            await _append_log(log_path, {
                "ts": _utcnow().isoformat() + "Z",
                "runId": run_id,
                "executionId": execution_id,
                "datasetId": ds["datasetId"],
                "rowIndex": row_idx,
                "rep": rep,
                "status": "canceled",
            })
            return
```

3d. `_fanout` 收尾(:461)改为:

```python
    if execution_id in _cancel_requested:
        # canceled 允许 passed+failed < total_runs(finalize 跳过校账)。
        await _finalize_execution(db_factory, execution_id, status=STATUS_CANCELED)
    else:
        await _finalize_execution(db_factory, execution_id)
```

3e. `executions.py` 新端点(导入区补:`HTTPException`、`status as http_status`(与现有 `status` 导入合并注意命名,现有写法是 `from fastapi import APIRouter, Depends, status` —— 改为 `HTTPException` 加入该行,http 状态码直接用 `status.HTTP_409_CONFLICT` 现有别名)、`from ..core.timeutil import utcnow`、`from ..models import Execution, STATUS_CANCELED`(models 的导出方式以 `from ..models import Execution` 现行为准,常量按包导出实情调整,必要时直接 `from ..models.execution import STATUS_CANCELED`)、`from ..services import execution_store, run_dispatcher`):

```python
# ── cancel ──────────────────────────────────────────────────────
@router.post("/{execution_id}/cancel", response_model=ExecutionOut)
async def cancel_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> ExecutionOut:
    """P4 协作式取消:登记请求,在飞 fanout 在行边界收敛为 canceled。

    无在飞 task 的 queued 僵尸单立即终态化。终态单 409。
    """
    if ex.status != STATUS_QUEUED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "not_cancelable",
                "message": f"execution already {ex.status}",
            },
        )
    run_dispatcher.request_cancel(ex.id)
    if not run_dispatcher.has_live_fanout(ex.id):
        ex.status = STATUS_CANCELED
        ex.finished_at = utcnow()
        await session.commit()
        await session.refresh(ex)
    return execution_store.execution_out(ex)
```

(`STATUS_QUEUED` 与 `STATUS_CANCELED` 同源导入;`executions.py` 已导入 `Execution` 模型。)

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_run_cancel.py tests/test_run_baseline.py tests/test_executions.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/app/routers/executions.py src/gimbal-platform/backend/tests/test_run_cancel.py
git commit -m "feat(platform): P4 执行取消 — 协作式行边界取消 + canceled 终态 + cancel 端点"
```

---

### Task 7: P5 — env 服务端权威

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`dispatch_run` env 校验段,约 :159)
- Test: `src/gimbal-platform/backend/tests/test_run_env_authority.py`(新建)

**Interfaces:**
- Consumes: `env_store.list_envs()`(已存在);`RunEnv` schema 不变(客户端仍可发完整对象,服务端不采信 name/baseUrl)。
- `_fanout` 的 `env` 参数改传服务端记录的 dump(`server_env.model_dump(by_alias=True, mode="json")`)。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_run_env_authority.py`(顶部按「测试基座」放 `_fake_launch`/`_fake_convert`/`_jsonl_records`):

```python
"""P5 env 服务端权威:下发 env 取自 env_store,不采信请求体 baseUrl。"""
from tests.helpers import make_draft, register_and_login, test_env, wait_until


async def test_dispatch_uses_server_env_base_url(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-env"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    tampered = test_env()
    tampered["baseUrl"] = "http://evil.example"     # envId 不变,baseUrl 篡改
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-env", "dataSetIds": [], "env": tampered,
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]
    await wait_until(
        lambda: list(run_dispatcher._run_dir(run_id).rglob("case.json"))
    )

    dispatched = [rec for rec in _jsonl_records(run_dispatcher)
                  if rec.get("status") == "dispatched"]
    assert dispatched
    # 服务端 test-env-A 的真值是 http://x(helpers.test_env)
    assert dispatched[0]["env"]["baseUrl"] == "http://x"
    assert "evil.example" not in str(dispatched[0]["env"])
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_env_authority.py -v`
Expected: FAIL(JSONL 里是篡改后的 `http://evil.example`)

- [ ] **Step 3: 实现**

`dispatch_run` env 校验段:把现有"envId ∈ env_store 存在性校验"改为捕获命中记录并比对告警(保留原 NotFound 分支语义;`env_store` 已在导入域内,若 dispatch 现用其他校验方式则就地替换为下述):

```python
    server_env = next(
        (e for e in env_store.list_envs() if e.env_id == req.env.env_id), None
    )
    if server_env is None:
        raise NotFound("env_not_found", f"env not found: {req.env.env_id}")
    # P5 服务端权威:name/baseUrl 一律取 env_store 记录;请求体携带的
    # 值不一致时告警(此前客户端可传 envId=dev + baseUrl=任意内网地址,
    # env 治理形同虚设)。
    if (req.env.name, req.env.base_url) != (server_env.name, server_env.base_url):
        logger.warning(
            "run_dispatcher: env mismatch for {} — client ({}, {}), "
            "server ({}, {}); using server record",
            req.env.env_id, req.env.name, req.env.base_url,
            server_env.name, server_env.base_url,
        )
```

`_fanout(...)` 调用点的 `env=req.env.model_dump(by_alias=True, mode="json")`(:242)改为:

```python
            env=server_env.model_dump(by_alias=True, mode="json"),
```

(验收标准写死:`_fanout` 必须收服务端记录;实现细节可随 dispatch 现状微调。)

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_run_env_authority.py tests/test_run_baseline.py -v`
Expected: PASS 全部(baseline 的 `test_env()` 与服务端一致,不受影响)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_env_authority.py
git commit -m "fix(platform): P5 env 服务端权威 — baseUrl 一律取 env_store,不采信请求体"
```

---

### Task 8: P6 — plate convert memo + 连续不可用熔断

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/config.py`(Settings 增 `PLATE_BREAKER_THRESHOLD: int = 3`,放 Plate integration 块)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`_fanout` 内 `_row` 的 convert 段 :354-361 与 `PlateUnavailableError` 处理 :420-423)
- Test: `src/gimbal-platform/backend/tests/test_run_plate_resilience.py`(新建)

**Interfaces:**
- Produces: 模块私有 `_convert_cache_key(payload: dict) -> str`(sha1 of canonical JSON)。
- 行为契约:同一行 n_runs 次重复只调一次 plate `/convert`;连续 `PLATE_BREAKER_THRESHOLD` 次 `PlateUnavailableError` 后,剩余行不再调用 plate,直接记 `plate_unavailable`(error 注明 circuit open)。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_run_plate_resilience.py`(顶部按「测试基座」放 `_fake_launch`/`_wait_terminal`/`_jsonl_records`):

```python
"""P6:convert 按输入 memo;plate 连续不可用开路。"""
from tests.helpers import make_draft, register_and_login, test_env


async def _run_with_convert(client, monkeypatch, convert, *, body_over=None):
    from app.services import gimbal_launcher as gl, plate_client as pc

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-plate", vars_map={"customer_id": "1"}))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", convert)
    body = {"scenarioId": "sc-plate", "dataSetIds": [], "env": test_env()}
    body.update(body_over or {})
    r = await client.post("/api/runs", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["executionId"]


async def test_convert_memoized_across_repeats(client, monkeypatch):
    from app.services import plate_client as pc  # noqa: F401 — patched below

    calls = {"n": 0}

    async def counting_convert(scenario):
        calls["n"] += 1
        return {"consumer": "platform", "converted": dict(scenario)}

    eid = await _run_with_convert(client, monkeypatch, counting_convert,
                                  body_over={"nRuns": 3})
    await _wait_terminal(eid)
    assert calls["n"] == 1          # 同一行 ×3 重复共享一次 convert


async def test_breaker_opens_after_consecutive_unavailable(
    client, monkeypatch
):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher
    from tests.helpers import register_and_login  # noqa: F401

    headers = await register_and_login(client)  # noqa: F841 — 复用登录态
    # 5 行数据集,行值互不相同(防 memo 干扰熔断计数路径)
    await client.post("/api/scenarios/sc-plate/data-sets", headers=headers,
                      json={"name": "ds5", "rows": [
                          {"customer_id": str(i)} for i in range(5)]})

    calls = {"n": 0}

    async def down_convert(scenario):
        calls["n"] += 1
        raise pc.PlateUnavailableError("plate_unavailable: connect timeout")

    async def noop_launch(*a, **k):
        from tests.helpers import launch_ok
        return launch_ok()

    monkeypatch.setattr(gl, "launch", noop_launch)
    monkeypatch.setattr(pc, "convert", down_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-plate", "dataSetIds": [ds_id], "env": test_env(),
        "parallel": 1,
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    await _wait_terminal(eid)

    assert calls["n"] == 3          # 阈值 3:第 4、5 行不再打 plate
    records = _jsonl_records(run_dispatcher)
    assert any(
        rec.get("status") == "plate_unavailable"
        and "circuit open" in str(rec.get("error", ""))
        for rec in records
    )
```

(`ds_id` 从 data-sets POST 响应取——测试里补一行 `ds_id = r.json()["datasetId"]`,上面为可读性分开写了;实际落文件时合成一段完整函数体。)

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_plate_resilience.py -v`
Expected: FAIL(convert 被调 3 次 / 5 次)

- [ ] **Step 3: 实现**

3a. `config.py` Plate 块加:

```python
    # 连续 PlateUnavailable 达到该次数后熔断:本轮 fan-out 剩余行不再
    # 调用 plate,直接记 plate_unavailable(P6:plate 宕机时避免逐行
    # 全超时等待)。
    PLATE_BREAKER_THRESHOLD: int = 3
```

3b. `run_dispatcher.py` 新增 helper(需 `import hashlib`;放模块 helper 区):

```python
def _convert_cache_key(payload: dict) -> str:
    """convert memo 键:合成场景的规范化 JSON 摘要。

    同一行 n_runs 次重复输入完全一致(P6:此前重复打 plate)。
    """
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        .encode("utf-8")
    ).hexdigest()
```

3c. `_fanout` 在 `sem = asyncio.Semaphore(...)`(:320)之后加:

```python
    # P6:fan-out 级 convert memo + plate 连续不可用熔断计数。
    convert_cache: dict[str, dict] = {}
    plate_state = {"consecutive_unavailable": 0}

    def _breaker_open() -> bool:
        return (
            plate_state["consecutive_unavailable"]
            >= settings.PLATE_BREAKER_THRESHOLD
        )
```

3d. `_row` 的 try 块改造——`convert_data = await plate_client.convert(composed)`(:355)起,到 `result = await gimbal_launcher.launch(...)`(:375-380)止的整段逻辑包进 `else:` 分支,try 块开头加熔断快速失败:

```python
            try:
                if _breaker_open():
                    # 熔断开路:不再调用 plate,行快速失败(落到下方
                    # 公共尾部:记日志行 + failed 计数)。
                    log_line["status"] = "plate_unavailable"
                    log_line["error"] = (
                        "plate circuit open: "
                        f"{plate_state['consecutive_unavailable']} "
                        "consecutive unavailable"
                    )
                else:
                    cache_key = _convert_cache_key(composed)
                    if cache_key in convert_cache:
                        convert_data = convert_cache[cache_key]
                    else:
                        convert_data = await plate_client.convert(composed)
                        convert_cache[cache_key] = convert_data
                    plate_state["consecutive_unavailable"] = 0
                    # ↓ 原有逻辑整体保持,仅整体缩进一级挂到 else 下:
                    converted = convert_data.get("converted") or {}
                    ...(_inject_exec_users / prefix / _inject_services /
                        _write_case_file / launch 原样)...
```

(熔断分支设置完 `log_line` 后**不注入不执行**,直接走到 `_append_log` + `_bump_counters(passed=0, failed=1)` 公共尾部——与 `plate_unavailable` 异常分支同收敛点。)

3e. `except plate_client.PlateUnavailableError` 分支(:420-423)首行加计数:

```python
            except plate_client.PlateUnavailableError as e:
                plate_state["consecutive_unavailable"] += 1
                ...其余保持...
```

(`PlateRejectedError` 不计数——拒绝是输入问题,不代表 plate 不健康。)

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_run_plate_resilience.py tests/test_run_baseline.py tests/test_run_evidence.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/core/config.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_plate_resilience.py
git commit -m "fix(platform): P6 plate convert memo + 连续不可用熔断(PLATE_BREAKER_THRESHOLD)"
```

---

### Task 9: P7 — 总量上限 + 全局并发闸

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/config.py`(Settings 增 `MAX_RUNS_PER_EXECUTION: int = 200`、`MAX_CONCURRENT_LAUNCHES: int = 8`,放 Gimbal 执行链块 :44 后)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(`dispatch_run` total_runs 计算后;`_row` 的 launch 调用;模块级信号量缓存)
- Test: `src/gimbal-platform/backend/tests/test_run_capacity.py`(新建)

**Interfaces:**
- Produces: `run_dispatcher.reset_concurrency_state() -> None`(测试隔离,清 `_launch_sems`)。
- 行为契约:`total_runs > MAX_RUNS_PER_EXECUTION` → `Conflict("too_many_runs")` → 409;进程内并发的 `gimbal_launcher.launch` 同时在飞数 ≤ `MAX_CONCURRENT_LAUNCHES`(跨 execution 合并生效)。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_run_capacity.py`(顶部按「测试基座」放 `_wait_terminal`;`_fake_convert` 同基座):

```python
"""P7:总量上限拒单 + launch 全局并发闸。"""
import asyncio

from tests.helpers import make_draft, register_and_login, test_env


async def test_dispatch_rejects_over_cap(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_RUNS_PER_EXECUTION", 3)
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cap", vars_map={"customer_id": "1"}))
    r = await client.post("/api/scenarios/sc-cap/data-sets", headers=headers,
                          json={"name": "ds", "rows": [
                              {"customer_id": "1"}, {"customer_id": "2"}]})
    ds_id = r.json()["datasetId"]

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cap", "dataSetIds": [ds_id], "env": test_env(),
        "nRuns": 2,                      # 2 行 × 2 次 = 4 > 3
    })
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "too_many_runs"


async def test_global_launch_semaphore_caps_concurrency(client, monkeypatch):
    from app.core.config import settings
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    run_dispatcher.reset_concurrency_state()
    monkeypatch.setattr(settings, "MAX_CONCURRENT_LAUNCHES", 2)

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-sem"))
    # convert 必须一起断流:否则测试环境无 plate,行全部 plate_unavailable,
    # launch 根本不被调用,并发断言空转通过。
    monkeypatch.setattr(pc, "convert", _fake_convert)
    state = {"live": 0, "peak": 0}

    async def launch(*a, **k):
        state["live"] += 1
        state["peak"] = max(state["peak"], state["live"])
        await asyncio.sleep(0.02)
        state["live"] -= 1
        return gl.LaunchResult(launch_status="ok", exit_code=0, total=1, passed=1)

    monkeypatch.setattr(gl, "launch", launch)

    eids = []
    for _ in range(2):                   # 两个 execution,各 1 行 × nRuns=4
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-sem", "dataSetIds": [], "env": test_env(),
            "nRuns": 4, "parallel": 4,
        })
        assert r.status_code == 201, r.text
        eids.append(r.json()["executionId"])

    for eid in eids:
        await _wait_terminal(eid)
    assert state["peak"] <= 2
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_capacity.py -v`
Expected: FAIL(无 409 / peak 超限)

- [ ] **Step 3: 实现**

3a. `config.py` Gimbal 执行链块加:

```python
    # P7 资源闸:单次执行总行数上限(行数 × nRuns,409 拒单)与
    # 进程内 launch 子进程同时在飞上限(跨 execution 合并生效)。
    MAX_RUNS_PER_EXECUTION: int = 200
    MAX_CONCURRENT_LAUNCHES: int = 8
```

3b. `run_dispatcher.py` 模块级(放 `_in_flight` 附近):

```python
# 全局 launch 并发闸(P7):按事件循环缓存 Semaphore——asyncio 原语
# 绑定创建时的 loop,pytest 每用例新 loop,进程级单例会跨 loop 复用
# 报 "attached to a different loop"。
_launch_sems: dict[int, asyncio.Semaphore] = {}


def _global_launch_sem() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    sem = _launch_sems.get(loop_id)
    if sem is None:
        sem = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_LAUNCHES))
        _launch_sems[loop_id] = sem
    return sem


def reset_concurrency_state() -> None:
    """测试隔离:清空按 loop 缓存的信号量(换上限后重建)。"""
    _launch_sems.clear()
```

3c. `dispatch_run` 在 `total_runs` 计算之后、`_create_execution` 之前加:

```python
    # P7:总量闸——行数 × nRuns 无上限时,万行数据集 × n_runs 会派生
    # 出十万级子进程。
    if total_runs > settings.MAX_RUNS_PER_EXECUTION:
        raise Conflict(
            "too_many_runs",
            f"total runs {total_runs} exceed platform cap "
            f"{settings.MAX_RUNS_PER_EXECUTION} (rows x nRuns)",
        )
```

3d. `_row` 内 launch 调用(:375-380)加全局闸:

```python
                async with _global_launch_sem():
                    result = await gimbal_launcher.launch(
                        case_path,
                        step_to=halt_at,
                        report_dir=case_dir / "reports",
                        cwd=case_dir,
                    )
```

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_run_capacity.py tests/test_run_baseline.py tests/test_run_m1_capabilities.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/core/config.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_capacity.py
git commit -m "fix(platform): P7 执行总量上限 + launch 全局并发闸(MAX_RUNS/CONCURRENT)"
```

---

### Task 10: 低危 — executions 分页 + 过期文档修正

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/executions.py`(list :33-49 加分页;模块 docstring :1-10)
- Modify: `src/gimbal-platform/backend/app/models/execution.py`(docstring :1-9 中 "gimbal HTTP 服务" 过期表述)
- Test: `src/gimbal-platform/backend/tests/test_executions.py`(追加)

**Interfaces:**
- `GET /api/executions?limit=&offset=`(limit 默认 200、1–500;offset 默认 0);响应 `{items, total}` 信封不变,total 为属主全量计数。前端零改动兼容(现消费信封且不传参)。

- [ ] **Step 1: 写失败测试**

`tests/test_executions.py` 追加(造数/登录方式照抄该文件现行写法;若该文件已有造 Execution 的 helper 则复用):

```python
async def test_list_pagination(client):
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    for _ in range(5):
        await _seed_execution(me["user"]["id"], status="done")  # MeOut 信封

    r = await client.get("/api/executions?limit=2&offset=1", headers=headers)
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    ids = [it["id"] for it in body["items"]]
    assert ids == sorted(ids, reverse=True)   # id 倒序,offset=1 跳过最新


async def test_list_limit_bounds(client):
    headers = await register_and_login(client)
    assert (await client.get("/api/executions?limit=0", headers=headers)).status_code == 422
    assert (await client.get("/api/executions?limit=501", headers=headers)).status_code == 422
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_executions.py -v -k pagination`
Expected: FAIL(limit 参数不存在被忽略 → 200 且 items 全量)

- [ ] **Step 3: 实现**

`executions.py`:

3a. 导入区:`from fastapi import APIRouter, Depends, HTTPException, Query, status`(本 Task 只加 `Query`/`HTTPException`——`HTTPException` 供 Task 6,若 Task 6 已加则跳过);`from sqlalchemy import func, select`。

3b. list 整体替换:

```python
@router.get("", response_model=ExecutionListOut)
async def list_executions(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExecutionListOut:
    """分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。"""
    base = select(Execution).where(Execution.owner_id == user.id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(Execution.id.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    items = [execution_store.execution_out(e) for e in rows]
    return ExecutionListOut(items=items, total=total)
```

3c. 模块 docstring :3-5 的 "run_dispatcher → gimbal HTTP service" 改为 "run_dispatcher → gimbal_launcher 子进程(``gimbal run launch``)";`models/execution.py` docstring 同义修正(逐行 fan-out 调 gimbal HTTP 服务 → 子进程)。

- [ ] **Step 4: 运行验证通过 + 回归**

Run: `python -m pytest tests/test_executions.py tests/test_run_cancel.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/routers/executions.py src/gimbal-platform/backend/app/models/execution.py src/gimbal-platform/backend/tests/test_executions.py
git commit -m "fix(platform): executions 分页(limit/offset)+ 执行链 docstring 过期表述修正"
```

---

### Task 11: 前端 — canceled 状态 + 取消按钮

**Files:**
- Modify: `src/gimbal-platform/frontend/src/api/executions.ts`(:5 状态类型;新增 cancel API)
- Modify: `src/gimbal-platform/frontend/src/utils/executionStatus.ts`(:9-13 标签表)
- Modify: `src/gimbal-platform/frontend/src/styles/status-colors.css`(.status-* 区)
- Modify: `src/gimbal-platform/frontend/src/stores/executions.ts`(:63 附近轮询终止条件)
- Modify: `src/gimbal-platform/frontend/src/views/ExecutionsList.vue`(表格操作列)

**Interfaces:**
- Consumes: Task 6 的 `POST /api/executions/{id}/cancel`;新状态 `canceled`。

- [ ] **Step 1: api 层**

`api/executions.ts` :5 改:

```typescript
export type ExecutionStatus = 'queued' | 'done' | 'failed' | 'canceled'
```

新增(照抄本文件现有单条请求的写法——fetch 包装/错误处理保持一致,勿造新 http 封装):

```typescript
/** P4 协作式取消:queued 单登记取消,canceled 为终态。 */
export function cancelExecution(id: number): Promise<Execution> {
  return request(`/executions/${id}/cancel`, { method: 'POST' })
}
```

(`request` 以文件内现有 helper 实名/实签名为准照抄。)

- [ ] **Step 2: 状态文案与颜色**

`utils/executionStatus.ts` 的 `EXECUTION_STATUS_LABELS`(:9-13)增一行:

```typescript
  canceled: '已取消',
```

同文件新增终态判断供轮询复用:

```typescript
/** canceled 与 done/failed 同为终态(轮询停止条件)。 */
export function isTerminalExecutionStatus(s: string): boolean {
  return s === 'done' || s === 'failed' || s === 'canceled'
}
```

`styles/status-colors.css` 照 `.status-queued` 块的结构新增灰色中性样式(取文件内既有中性色,无则 `#64748b`;文件头注释的状态集说明同步加 canceled):

```css
.status-canceled {
  /* 与 .status-queued 同结构:background/border/color 换灰 */
}
```

- [ ] **Step 3: 轮询终止 + 取消按钮**

`stores/executions.ts` :63 附近的轮询终止条件改用 `isTerminalExecutionStatus(status)`(找到实际的 status 判断处替换;若多处判断,统一收敛到该函数)。

`views/ExecutionsList.vue`:操作列对 `row.status === 'queued'` 的行加"取消"按钮(样式照抄同表既有按钮),点击 → `cancelExecution(row.id)` → 沿用本页现有刷新路径;失败走本页现有错误提示。

- [ ] **Step 4: 构建验证**

Run: `cd src/gimbal-platform/frontend && npm run build`
Expected: 构建通过,无类型错误(若无 build script 则 `npx vue-tsc --noEmit`)

- [ ] **Step 5: 手工冒烟(可选但推荐)**

后端 + 前端 dev 起服,发一单多行执行,列表页点取消,确认状态流转到"已取消"、轮询停止、按钮消失。

- [ ] **Step 6: Commit**

```bash
git add src/gimbal-platform/frontend/src/api/executions.ts src/gimbal-platform/frontend/src/utils/executionStatus.ts src/gimbal-platform/frontend/src/styles/status-colors.css src/gimbal-platform/frontend/src/stores/executions.ts src/gimbal-platform/frontend/src/views/ExecutionsList.vue
git commit -m "feat(frontend): canceled 状态呈现 + 执行列表取消按钮"
```

---

## Self-Review 记录(写计划时已核)

- **P1–P9 覆盖**:P1→T1,P2→T5,P3→T3/T4,P4→T6(+T11 前端),P5→T7,P6→T8,P7→T9,P8/P9→T2;低危(docstring/分页)→T10。全部有归属;明确不做清单在「设计决策」末尾。
- **任务间接口**:`STATUS_CANCELED` 与 `_finalize_execution(status=)` 在 T2 先行引入供 T6 消费;`_append_log` 异步形态 T2 先改,T4/T6/T8 新增调用直接用;`startup_recovery` T4 建骨架、T5 接清扫;T6 的 `HTTPException` 导入若 T10 已顺手加入则跳过——顺序即依赖序。
- **测试基座真实性**:全部 helper 签名取自 `tests/helpers.py` 实文(`test_env()` 的服务端真值为 `http://x`);monkeypatch 接法照抄 `test_run_baseline.py` 验证过的模式;JSONL 断言一律逐行 parse,不依赖 dump 分隔符。
- **已知留给执行者的自由度**:T7 实现允许随 dispatch 现状微调(验收标准写死);T11 的 `request`/按钮样式以文件现状为准;`_seed_execution`/`_wait_terminal` 等局部 helper 是否上收 helpers.py 由执行者按 DRY 判断。
