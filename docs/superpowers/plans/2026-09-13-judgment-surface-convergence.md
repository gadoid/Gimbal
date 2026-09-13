# 判定面与取数收敛(阶段二·①) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 plate `/full` 契约只被取一次、只被缓存一次、只被判定一次 —— 后端算出声明侧可注入面并经代理下发,前端不再自己算它。

**Architecture:** 把 `endpoint_declarations` 里那套「缓存 + 真值回退窗 + 在飞收敛 + 告警老化」整体上移到 `plate_client.get_endpoint_full(eid, *, ttl, timeout)`,使 dispatch 与代理**共用同一条缓存条目**;`endpoint_declarations` 退化为派生层(从缓存 item 里取 `request.declarations` 并缓存投影)。代理在同一条缓存条目上把声明侧可注入面(由既有纯函数 `injectable_universe(None, paths)` 算出)一并返回,前端据此删掉声明半的归一化与前缀逻辑。

**Tech Stack:** Python 3 / FastAPI / httpx / pytest / loguru;Vue 3 / TypeScript / vitest / @vue/test-utils。

**Spec:** `docs/superpowers/specs/2026-09-13-judgment-surface-convergence-design.md`

## Global Constraints

- **P8 名字不得跑在实物前面**。① 交付后的准确表述是「判定面的**声明侧**已单一定义;body 侧仍是双实现」(spec §2.4)。提交信息与注释**不得**写成「H 已解决」「判定面已单一定义」。
- **§5 禁止用真值合并有意义但 falsy 的值**。`None` / `[]` / `""` / `0` / `False` 不得被 `or` / `and` 抹平。例外必须在注释里说明等价性(仓库既有做法:`endpoint_declarations.py:182-185`)。本计划里涉及:`None`(降级) vs `[]`(真无声明)、`None` vs `frozenset()`、`declared_surface` 的 `null` vs `["$"]`。
- **ADR-0003**:退场知识只写在该 ADR;代码注释只描述**当前**行为,不写历史对照(不得出现「此前」「原来是」式的对照叙述)。
- **plate 与执行核零改动**:全部改动在 `src/gimbal-platform/` 内。
- **不 push**:分支 `feat/dataset-driven-refactor` 保持现状。
- **`PLATE_TIMEOUT_SEC` 的 30s 不得改动**:它服务 `convert` 等「等不到就报错」的链路。
- **测试命令**(backend 工作目录 `src/gimbal-platform/backend`):`D:/python/python.exe -m pytest <path> -v`;全量 `D:/python/python.exe -m pytest -q`。
- **测试命令**(frontend 工作目录 `src/gimbal-platform/frontend`):`npm run test:run -- <path>`;全量 `npm run test:run`;类型检查 `npm run typecheck`。
- **既有环境噪声**:后端全量在 uvicorn 运行时会有 **2 条既有失败**(`test_run_cancel.py::test_cancel_skips_remaining_rows`、`test_run_plate_resilience.py::test_breaker_opens_after_consecutive_unavailable`),根因是运行中的 uvicorn 并发写 `backend/data/runs/*.jsonl` 造成的撕裂行(属 ③ 的范围)。**本计划的验收必须区分「既有 2 条」与「本次引入的失败」**。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend/app/services/plate_client.py` | 改 | 新增**缓存取数** `get_endpoint_full` + `EndpointFull` 结果类型(搬入 D/R/S/U/在飞/shield) |
| `backend/app/services/endpoint_declarations.py` | 改 | 退化为**派生层**:从缓存 item 取 declarations + 缓存投影 + 降级告警 |
| `backend/app/routers/endpoint_catalog.py` | 改 | `/full` 代理改走同一缓存;新增 `declared_surface` |
| `backend/app/core/config.py` | 改 | `DECLARED_PATHS_TIMEOUT_SEC` 的「覆盖范围」注释重写(spec §3.5) |
| `backend/app/services/run_injection.py` | 改 | Z1:`exists` 兜底前判宿主类型 + 写侧宿主冲突拦截 |
| `backend/tests/test_plate_full_cache.py` | 建 | 从 `test_endpoint_declarations.py` 迁来的缓存语义用例 |
| `backend/tests/test_endpoint_declarations.py` | 改 | 保留派生层用例,缓存语义用例迁出 |
| `backend/tests/test_endpoint_catalog_proxy.py` | 改 | `declared_surface` + 降级 null 的用例 |
| `backend/tests/test_run_injection.py` | 改 | Z1 收紧 + 写侧拦截用例 |
| `frontend/src/utils/assertion-registry.ts` | 改 | 消费 `declared_surface`;`bodyPathSetOf` 物化前缀;删前缀扫描 |
| `frontend/src/composables/useEndpointFull.ts` | 改 | 300s TTL + 换面重判 + docstring 更正 |
| `frontend/src/composables/useInjectableSurface.ts` | 改 | 传入 surface;失败态可见 |
| `frontend/src/components/composer/CaseComposerCanvas.vue` | 改 | 删两处渲染期取数 |
| `frontend/src/types/plate.ts` | 改 | `declared_surface` 字段 |
| `docs/known-issues/**` | 改 | 四条记录 + README 索引 |
| `docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md` | 改 | `:105` 公开承诺修订(需用户过目) |

---

### Task 1: `plate_client` 承接 `/full` 缓存取数

把 `endpoint_declarations` 里那套缓存语义**整体搬进** `plate_client`,新增 `get_endpoint_full`。本轮**不改任何调用方** —— `endpoint_declarations` 暂时保持不动,两边并存,靠用例证明新实现与旧实现**行为等价**。这样复核者能单独拒这一个任务。

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/plate_client.py`
- Create: `src/gimbal-platform/backend/tests/test_plate_full_cache.py`

**Interfaces:**
- Consumes: `settings.DECLARED_PATHS_TTL_SEC` / `_MAX_ENTRIES` / `_STALE_WINDOW_SEC` / `_TIMEOUT_SEC`;`query_view_cache.TtlLruCache`;`get_client()`
- Produces:
  - `class EndpointFull` — frozen dataclass,字段 `item: dict[str, Any] | None`、`stale: bool`、`status: int | None`、`reason: str`
  - `async def get_endpoint_full(endpoint_id: str, *, timeout: float | None = None) -> EndpointFull`(**无 `ttl` 形参**:TTL 由缓存实例构造时冻结,见 Step 3 的 docstring)
  - `def _reset_full_cache_for_test() -> None`
- **`status` 的契约(T3 依赖它,必须真)**:成功 = `200`;**plate 返回非 200 = 那个真实状态码**(404 必须透出来,T3 靠它映射 `endpoint_not_found`);**没拿到响应**(连接失败 / 超时)= `None`。「拿到了 404」与「没拿到响应」是两件事,不得合并成同一个值。回退旧快照那条路径的 `status` 取值须在 docstring 写明,不留歧义。

- [ ] **Step 1: 写失败用例 —— 冷取成功返回 item**

创建 `src/gimbal-platform/backend/tests/test_plate_full_cache.py`:

```python
"""plate_client.get_endpoint_full 的缓存语义(从 endpoint_declarations 迁来)。

这些用例原本钉在 ``endpoint_declarations._refresh`` 上(阶段一 D/R/S/U 与
在飞收敛/shield 五项)。缓存上移到 plate_client 后语义必须逐条不变。
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.services import plate_client


def _envelope(item: dict) -> dict:
    return {"ok": True, "dim": "endpoint", "data": {"item": item}}


def _item(decls):
    return {"request": {"declarations": decls}, "responses": {"200": {}}}


@pytest.fixture
def install_transport(monkeypatch):
    """把 plate_client 的单例换成 MockTransport 客户端,并记录请求数。"""
    calls: list[str] = []

    def make(handler):
        def _wrapped(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return handler(request)
        plate_client.set_client_for_tests(
            httpx.AsyncClient(transport=httpx.MockTransport(_wrapped),
                              base_url=settings.PLATE_BASE_URL))
        return calls

    plate_client._reset_full_cache_for_test()
    yield make
    plate_client.set_client_for_tests(None)
    plate_client._reset_full_cache_for_test()


async def test_cold_fetch_returns_item(install_transport):
    install_transport(lambda req: httpx.Response(200, json=_envelope(_item([{"path": "$.a"}]))))
    res = await plate_client.get_endpoint_full("ep-1")
    assert res.item is not None
    assert res.item["request"]["declarations"] == [{"path": "$.a"}]
    assert res.stale is False
    assert res.reason == ""


async def test_second_call_hits_cache(install_transport):
    calls = install_transport(
        lambda req: httpx.Response(200, json=_envelope(_item([{"path": "$.a"}]))))
    await plate_client.get_endpoint_full("ep-1")
    await plate_client.get_endpoint_full("ep-1")
    assert len(calls) == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `D:/python/python.exe -m pytest tests/test_plate_full_cache.py -v`
Expected: FAIL — `AttributeError: module 'app.services.plate_client' has no attribute 'get_endpoint_full'`

- [ ] **Step 3: 实现 `EndpointFull` 与 `get_endpoint_full`**

在 `plate_client.py` 末尾(`aclose` 之前)追加。**五项语义逐条从 `endpoint_declarations.py:75-219` 搬来,注释一并搬** —— 尤其 `_refresh` 那段 shield 警告必须原样在场:

```python
# ─── /full 契约取数(唯一入口)─────────────────────────────────────
from dataclasses import dataclass                       # noqa: E402  (文件顶部导入更佳,实现时上移)
import asyncio                                          # noqa: E402
from functools import partial                           # noqa: E402
from loguru import logger                               # noqa: E402
from .query_view_cache import TtlLruCache               # noqa: E402


@dataclass(frozen=True)
class EndpointFull:
    """``GET /api/endpoint/{id}/full`` 的一次取数结果。

    ``item`` 为 None ⇒ **不可得**(调用方降级)。``stale`` 为 True ⇒ item 来自
    **回退的旧快照**(阶段一 D:刷新失败时旧快照继续服务,直到回退窗走完)。
    ``status`` 是 plate 的 HTTP 状态(None = 未拿到响应,如连接失败)。
    ``reason`` 是失败原因(**告警链路上唯一的遥测**,空串表示成功且非回退)。

    为什么带回 stale/status 而不是只返回 item:降级告警与代理的错误码映射
    都需要这层区分 —— 三者都是**有意义的值**,不得被真值合并(§5)。
    """

    item: dict[str, Any] | None
    stale: bool
    status: int | None
    reason: str


def _full_cache_cfg() -> tuple[float, int, float]:
    return (settings.DECLARED_PATHS_TTL_SEC,
            settings.DECLARED_PATHS_MAX_ENTRIES,
            settings.DECLARED_PATHS_STALE_WINDOW_SEC)


def _build_full_cache() -> TtlLruCache:
    return TtlLruCache(ttl=settings.DECLARED_PATHS_TTL_SEC,
                       max_entries=settings.DECLARED_PATHS_MAX_ENTRIES,
                       stale_max_window=settings.DECLARED_PATHS_STALE_WINDOW_SEC)


_FULL_CACHE: TtlLruCache = _build_full_cache()
_FULL_CACHE_CFG: tuple[float, int, float] = _full_cache_cfg()
_FULL_INFLIGHT: dict[str, asyncio.Task[dict[str, Any] | None]] = {}


def _full_cache() -> TtlLruCache:
    """当前缓存实例;settings 三个参数变了就**换实例**(裁定 C21,语义同
    ``endpoint_declarations._cache`` —— TtlLruCache 的 ttl/容量/回退窗构造即冻结,
    而既有用例 ``test_ttl_zero_refetches`` 钉的是「TTL 被实时读取」)。
    """
    global _FULL_CACHE, _FULL_CACHE_CFG
    cfg = _full_cache_cfg()
    if cfg != _FULL_CACHE_CFG:
        _FULL_CACHE = _build_full_cache()
        _FULL_CACHE_CFG = cfg
    return _FULL_CACHE


def _reset_full_cache_for_test() -> None:
    """测试钩子:按当前 settings 重建缓存、清在飞表。"""
    global _FULL_CACHE, _FULL_CACHE_CFG
    _FULL_CACHE = _build_full_cache()
    _FULL_CACHE_CFG = _full_cache_cfg()
    _FULL_INFLIGHT.clear()


def _forget_full_inflight(task: asyncio.Task, endpoint_id: str) -> None:
    """任务完成回调:摘除**自己那个**在飞项(校验身份,迟到回调不误删后来者)。

    为什么不是某个调用方的 finally:创建者可能被取消、等待方也可能先于任务
    完成退出,只有「任务真的完成了」才是摘除的正确时机(否则一次失败/取消会
    永久锈住该端点)。
    """
    if _FULL_INFLIGHT.get(endpoint_id) is task:
        _FULL_INFLIGHT.pop(endpoint_id, None)


async def _fetch_full_raw(endpoint_id: str, *, timeout: float,
                          fail_reason: list[str]) -> tuple[dict[str, Any] | None, int | None]:
    """真正打一次 plate。**fail-soft 绝不抛,也绝不写缓存**。

    失败返回 ``(None, status)`` 并**不动**缓存 —— 旧快照因此能留到回退窗,
    由调用侧决定是否回退(D)。``status`` 为 None 表示没拿到响应(连接/超时)。
    """
    status: int | None = None
    try:
        resp = await get_client().get(f"/api/endpoint/{endpoint_id}/full", timeout=timeout)
        status = resp.status_code
        if resp.status_code != 200:
            raise RuntimeError(f"plate status {resp.status_code}")
        item: Any = (resp.json().get("data") or {}).get("item")
        if not isinstance(item, dict):
            raise RuntimeError("no item in plate envelope")
        return item, status
    except Exception as e:  # noqa: BLE001 — 契约不可得绝不阻塞判定
        fail_reason[0] = str(e)
        return None, status
```

同文件再追加 `_refresh_full` 与 `get_endpoint_full`:

> ⚠ **实施修正(T1 实施者发现,已采纳)**:上面 `_fetch_full_raw` 的草图返回 `(item, status)` 元组,而下面 `_refresh_full` 写的是 `item = await asyncio.shield(inflight)` —— 照抄会把**元组**当 item 入缓存,Step 1 的 `res.item["request"]` 直接 TypeError。**形状由实施者定**,但两条契约必须成立:
> 1. 入缓存的载荷是 **item 本身**(不是元组/包装);
> 2. 真实 plate 状态必须能到达 `EndpointFull.status` —— 注意在飞收敛下**等待方读不到创建者的局部变量**(`fail_reason` 同款问题),所以状态要**随任务结果回来**,不能只塞进侧面单元。`stale` 回退路径的 `status` 取值须在 docstring 写明。

```python
async def _refresh_full(endpoint_id: str, *, timeout: float) -> dict[str, Any] | None:
    """在飞收敛(shield + 完成回调摘除)后真正取一次;成功入缓存。

    shield:本调用方被取消只落自己,不连带取消共享取数 —— 裸 await 会把取消
    扩散进共享任务(创建者随之收到 CancelledError);dispatcher 的
    ``except Exception`` **不捕** CancelledError → fan-out 被判取消、不写终止
    JSONL 行、执行卡在 running 直到下次进程重启。**务必保留 shield,摘除务必
    留在完成回调。**
    """
    fail_reason: list[str] = [""]
    inflight = _FULL_INFLIGHT.get(endpoint_id)
    if inflight is None:
        inflight = asyncio.ensure_future(_fetch_full_raw(endpoint_id, timeout=timeout,
                                                         fail_reason=fail_reason))
        _FULL_INFLIGHT[endpoint_id] = inflight
        inflight.add_done_callback(partial(_forget_full_inflight, endpoint_id=endpoint_id))
    item = await asyncio.shield(inflight)
    if item is None:
        raise RuntimeError(fail_reason[0] or "endpoint full fetch failed")
    # 成功才 put ⇒ 时间戳打在成功那刻(U),不是请求发起时
    _full_cache().put(endpoint_id, item, _now_iso())
    return item


async def get_endpoint_full(endpoint_id: str, *, timeout: float | None = None) -> EndpointFull:
    """``GET /api/endpoint/{id}/full`` 的 item(**全进程唯一取数入口 + 唯一缓存**)。

    * 命中且未过期 → 直接返回缓存 item;
    * 过期但在**回退窗**内 → 尝试刷新,**失败则回退旧快照**(阶段一 D)并置
      ``stale=True``(调用方据此告警);
    * 无缓存或已出回退窗 → 刷新;**失败即 ``item=None`` + reason**(调用侧降级)。

    TTL **不是形参**:它由 ``DECLARED_PATHS_TTL_SEC`` 在**缓存实例构造时冻结**
    (裁定 C21 —— 这样 settings 热改即刻生效),故没有「按调用方传 ttl」这回事。
    ``timeout`` 为 None 时取 ``DECLARED_PATHS_TIMEOUT_SEC``(3s 软取上限)。
    """
    eff_timeout = settings.DECLARED_PATHS_TIMEOUT_SEC if timeout is None else timeout
    entry, fresh = _full_cache().lookup(endpoint_id)
    if entry is not None and fresh:
        return EndpointFull(item=entry.payload, stale=False, status=200, reason="")
    if entry is not None and not fresh:
        reason = ""
        try:
            refreshed = await _refresh_full(endpoint_id, timeout=eff_timeout)
        except Exception as e:                      # noqa: BLE001
            refreshed = None
            reason = str(e)
        if refreshed is None:                       # 显式,不用 or(§5)
            return EndpointFull(item=entry.payload, stale=True, status=None, reason=reason)
        return EndpointFull(item=refreshed, stale=False, status=200, reason="")
    reason = ""
    try:
        refreshed = await _refresh_full(endpoint_id, timeout=eff_timeout)
    except Exception as e:                          # noqa: BLE001
        reason = str(e)
        return EndpointFull(item=None, stale=False, status=None, reason=reason)
    if refreshed is None:                           # 显式(不用 or):_refresh_full 靠 raise 报失败
        return EndpointFull(item=None, stale=False, status=None, reason="取数失败")
    return EndpointFull(item=refreshed, stale=False, status=200, reason="")
```

- [ ] **Step 4: 运行确认通过**

Run: `D:/python/python.exe -m pytest tests/test_plate_full_cache.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 补齐 18 条迁移用例(逐条从 `test_endpoint_declarations.py` 搬,断言对象改为 `get_endpoint_full`)**

必须逐条覆盖,一条不得少(每条都钉着一项语义):

| 迁来的用例 | 钉住什么 | 新断言形态 |
|---|---|---|
| `test_ttl_zero_refetches` | C21 TTL 实时读取 | 同(monkeypatch `DECLARED_PATHS_TTL_SEC=0.0`) |
| `test_concurrent_cold_calls_coalesce_to_one_fetch` | 在飞收敛 | 同 |
| `test_failure_returns_none_and_does_not_cache` | 失败不写缓存 | `res.item is None` 且第二次仍打 plate |
| `test_cancelled_waiter_does_not_kill_shared_fetch` | shield | 同(断言共享任务未被取消) |
| `test_cancelled_creator_still_clears_inflight` | 完成回调摘除 | 同 |
| `test_stale_snapshot_survives_a_failed_refresh` | **D** | `res.item is not None and res.stale is True` |
| `test_cache_has_lru_bound` | S 容量上界 | 同 |
| `test_fresh_window_starts_at_success_not_at_request_start` | U 时间戳 | 同 |
| `test_empty_declarations_is_empty_frozenset_not_none` | 空目录 ≠ 降级 | 改为:item 里有 `declarations: []`,且 `item is not None` |
| `test_absent_declarations_is_empty_not_degraded` | 缺键 ≠ 降级 | 改为:`item is not None`(缺键由 T2 派生层处理) |
| `test_garbage_declarations_is_degraded` | 垃圾 declarations | **移回 T2**(那是派生层的判据,不是取数的) |

Run: `D:/python/python.exe -m pytest tests/test_plate_full_cache.py -v`
Expected: PASS(全部)

- [ ] **Step 6: 提交**

```bash
git add src/gimbal-platform/backend/app/services/plate_client.py src/gimbal-platform/backend/tests/test_plate_full_cache.py
git commit -m "refactor(plate_client): /full 取数与缓存上移,含 D/R/S/U/在飞/shield 五项语义"
```

---

### Task 2: `endpoint_declarations` 退化为派生层

`endpoint_declarations` 不再自己取数、不再自己缓存 item;它从 `get_endpoint_full` 拿 item,派生 `declarations` 与投影。**降级告警仍在本模块**(它是「声明面不可得」的语义,不是「取数失败」的)。

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/endpoint_declarations.py`
- Modify: `src/gimbal-platform/backend/tests/test_endpoint_declarations.py`

**Interfaces:**
- Consumes: `plate_client.get_endpoint_full` / `EndpointFull`
- Produces: `declarations_of(eid) -> list | None`、`declared_paths_of(eid) -> frozenset[str] | None`(**签名与语义完全不变**,既有调用方零改动)

- [ ] **Step 1: 保留的用例先跑一遍,记下基线**

Run: `D:/python/python.exe -m pytest tests/test_endpoint_declarations.py -v`
Expected: 记录当前通过数(基线),后续不得低于它。

- [ ] **Step 2: 删除取数与缓存,改为派生**

从 `endpoint_declarations.py` 删除:`_cache_cfg`、`_build_cache`、`_CACHE`、`_CACHE_CFG`、`_cache`、`_INFLIGHT`、`_forget_inflight`、`_fetch_declarations`、`_refresh`。保留:`_warn_once`、`_WARNED_AT`、`_now_iso`。

新增投影缓存(保留 R 的收益 —— 每次 dispatch 每步都会问一次,不复用就会重走目录树):

```python
_PROJ_CACHE: TtlLruCache | None = None
_PROJ_CFG: tuple[float, int, float] | None = None


def _proj_cache() -> TtlLruCache:
    """投影缓存:与取数缓存同 ttl/容量/回退窗,载荷 = frozenset(paths)。

    为什么另立一份而不是塞进 plate_client:投影是**平台域概念**
    (``catalog_paths``),plate_client 只该懂 plate 契约。两份缓存的 ttl 同源,
    且投影是 item 的纯函数 ⇒ 二者永不分歧。
    """
    global _PROJ_CACHE, _PROJ_CFG
    cfg = (settings.DECLARED_PATHS_TTL_SEC,
           settings.DECLARED_PATHS_MAX_ENTRIES,
           settings.DECLARED_PATHS_STALE_WINDOW_SEC)
    if _PROJ_CACHE is None or cfg != _PROJ_CFG:
        _PROJ_CACHE = TtlLruCache(ttl=cfg[0], max_entries=cfg[1], stale_max_window=cfg[2])
        _PROJ_CFG = cfg
    return _PROJ_CACHE


def _decls_of_item(item: dict[str, Any]) -> list | None:
    """从 item 取 ``request.declarations``;垃圾值 → None(降级)。

    缺省合并(例外,已核等价性 —— 不是「有意义 falsy 被真值合并」):信封缺
    ``request`` 键 / 其值为 ``{}`` / ``declarations`` 为 ``null`` 三种「未提供」
    都落到真无声明 ``[]``;真·垃圾值(字符串/数字等非 list)才是降级。
    """
    decls = (item.get("request") or {}).get("declarations")
    if decls is None:
        return []
    if not isinstance(decls, list):
        return None
    return decls
```

`declarations_of` 改写为:

```python
async def declarations_of(endpoint_id: str) -> list | None:
    """端点 ``request.declarations`` 原始列表;取不到 → None(调用侧降级)。

    返回**浅拷贝**:缓存是进程级共享状态,调用方改自己那份不污染他人。
    """
    res = await get_endpoint_full(endpoint_id)
    if res.item is None:
        _warn_once(endpoint_id, res.reason)
        return None
    if res.stale:
        _warn_once(endpoint_id, f"刷新失败({res.reason}),回退旧快照")
    decls = _decls_of_item(res.item)
    if decls is None:
        _warn_once(endpoint_id, "declarations 不是 list")
    return None if decls is None else list(decls)
```

`declared_paths_of` 改写为:

```python
async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。

    合法空声明 → 空 frozenset(**非 None**):那是「真无声明」,不是「降级」。
    """
    entry, fresh = _proj_cache().lookup(endpoint_id)
    if entry is not None and fresh:
        return entry.payload
    decls = await declarations_of(endpoint_id)
    if decls is None:
        return None
    proj = frozenset(catalog_paths(decls))
    _proj_cache().put(endpoint_id, proj, _now_iso())
    return proj
```

- [ ] **Step 3: 改用例**

`test_endpoint_declarations.py` 中凡 monkeypatch 缓存 settings 后直接断言「打了几次 plate」的用例,改为经 `plate_client` 的 transport fixture(与 T1 同款),因为计数点已移到 plate_client。**`test_garbage_declarations_is_degraded` 留在本文件**(它钉的是派生层的判据)。

Run: `D:/python/python.exe -m pytest tests/test_endpoint_declarations.py -v`
Expected: PASS,且数量不低于 Step 1 的基线。

- [ ] **Step 4: 跑 carry 与 injection 的既有用例确认零回归**

Run: `D:/python/python.exe -m pytest tests/test_run_carry_injection.py tests/test_carry_api.py tests/test_carry_store.py tests/test_run_injectable_wire.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/backend/app/services/endpoint_declarations.py src/gimbal-platform/backend/tests/test_endpoint_declarations.py
git commit -m "refactor(endpoint_declarations): 退化为派生层,取数与缓存归 plate_client"
```

---

### Task 3: 代理返回 `declared_surface` + 超时统一

**这是本计划唯一改**用户可见行为**的任务**(候选树在 plate 慢时的等待从 30s 变 3s),必须连带重写 `config.py` 里那段「不得改动」的注释。

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/endpoint_catalog.py:41-74`
- Modify: `src/gimbal-platform/backend/app/core/config.py:100-118`
- Modify: `src/gimbal-platform/backend/tests/test_endpoint_catalog_proxy.py`
- Modify: `docs/superpowers/specs/2026-09-13-judgment-surface-convergence-design.md`(补 §3.5)

**Interfaces:**
- Consumes: `plate_client.get_endpoint_full`、`endpoint_declarations.declared_paths_of`、`run_injection.injectable_universe`
- Produces: 代理响应新增 `declared_surface: list[str] | None`

- [ ] **Step 1: 写失败用例**

`EndpointPlateMock`(`test_endpoint_catalog_proxy.py:32-68`)当前对非 `resolve-paths` 路径一律 404。先给它加一条 `/full` 支路:

```python
    def __init__(self) -> None:
        self.behaviour: str = "ok"
        # /full 的信封;None 时走 404(既有 resolve-paths 用例不受影响)
        self.full_envelope: dict | None = None
```

在 `handler` 的 `bad_envelope` 判断**之后**插入:

```python
            if request.url.path.endswith("/full"):
                if mock.behaviour == "not_found":
                    return httpx.Response(404, json={"ok": False})
                if mock.full_envelope is None:
                    return httpx.Response(404)
                return httpx.Response(200, json=mock.full_envelope)
```

再追加用例:

```python
_FULL_ENVELOPE = {
    "ok": True,
    "dim": "endpoint",
    "data": {
        "item": {
            "request": {"declarations": [{"path": "$.customer.id"}]},
            "responses": {"200": {}},
        }
    },
}


async def test_full_surface_is_declared_half_only(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """declared_surface = 声明半(含 $ 与容器前缀);item 必须原样并存。

    item 的第二个消费者是候选树 UI(buildTree/prefillBindings)—— 本任务只
    **增加**字段,不得裁剪 item。
    """
    endpoint_plate_mock.full_envelope = _FULL_ENVELOPE
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["declared_surface"] == ["$", "$.customer", "$.customer.id"]
    assert body["request"] == _FULL_ENVELOPE["data"]["item"]["request"]


async def test_full_surface_empty_decls_is_just_dollar(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """真无声明 → ["$"],**不是** null —— 空目录与降级是两件事。"""
    endpoint_plate_mock.full_envelope = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": []}, "responses": {}}},
    }
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.json()["declared_surface"] == ["$"]


async def test_full_surface_is_null_when_declarations_are_garbage(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock
) -> None:
    """item 在但 declarations 是垃圾值 → declared_surface **显式 null**(降级)。

    ⚠ 这是 `null` 出现的**唯一**入口:`item` 本身不可得时代理直接 502,前端根本
    看不到这个字段。spec §2.2 说「降级 → null」指的是本条,plan 在此写明。
    """
    endpoint_plate_mock.full_envelope = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": "garbage"}, "responses": {}}},
    }
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == 200
    assert r.json()["declared_surface"] is None


@pytest.mark.parametrize("behaviour,expected", [("unavailable", 502), ("not_found", 404)])
async def test_full_failure_states(
    client: AsyncClient, endpoint_plate_mock: EndpointPlateMock,
    behaviour: str, expected: int,
) -> None:
    """plate 连不上 → 502 plate_unavailable;plate 404 → 404 endpoint_not_found。"""
    endpoint_plate_mock.full_envelope = _FULL_ENVELOPE
    endpoint_plate_mock.behaviour = behaviour
    headers = await _auth(client)
    r = await client.get("/api/endpoint-catalog/ep-1/full", headers=headers)
    assert r.status_code == expected
```

- [ ] **Step 2: 运行确认失败**

Run: `D:/python/python.exe -m pytest tests/test_endpoint_catalog_proxy.py -v`
Expected: FAIL — `KeyError: 'declared_surface'`

- [ ] **Step 3: 改写代理**

```python
@router.get("/{endpoint_id:path}/full")
async def get_full_endpoint(user: CurrentUser, endpoint_id: str) -> dict:
    """Proxy ``GET {plate}/api/endpoint/{id}/full``.

    走 ``plate_client.get_endpoint_full`` —— 与 dispatch 侧**同一条缓存条目**,
    故编辑器浏览与 dispatch 判定看到的是**同一份快照**(阶段二·① I)。

    返回 = plate 的 item **原样** + 一个后端算好的 ``declared_surface``:
    声明侧可注入面的**扁平字符串集合**(归一化、容器前缀、模板形态全部展开)。
    前端据此不再自己算声明半(§2.2)。

    ``declared_surface`` 为 ``None`` ⇒ 契约不可得(降级),前端从严只认 body 面。
    **不用 [] 冒充**:空目录(真无声明)与降级是两件事。
    """
    res = await get_endpoint_full(endpoint_id)
    if res.item is None:
        # 状态映射:plate 404 → endpoint_not_found;拿到响应但信封无 item →
        # plate_invalid_envelope;其余(连接失败 / 5xx)→ unavailable。
        if res.status == 404:
            raise HTTPException(status_code=404, detail={
                "code": "endpoint_not_found", "message": "endpoint not found"})
        if res.status is not None and res.status < 500:
            raise HTTPException(status_code=502, detail={
                "code": "plate_invalid_envelope",
                "message": f"no item in response ({res.reason})"})
        raise HTTPException(status_code=502, detail={
            "code": "plate_unavailable", "message": res.reason})

    paths = await declared_paths_of(endpoint_id)
    surface = None if paths is None else sorted(injectable_universe(None, paths))
    return {**res.item, "declared_surface": surface}
```

**注意**:`injectable_universe(None, paths)` 里 `paths` 是 `frozenset[str]`;降级判定必须在调它**之前**(该函数对 `None` 与 `()` 不加区分,先算会把降级错报成「只有 `$`」)。

- [ ] **Step 4: 重写 `config.py:100-118` 的覆盖范围注释**

把「**覆盖范围 = 本模块这一条共享软取**」与「**`PLATE_TIMEOUT_SEC` 的 30s 不得改动:那条服务 `convert`、`/full` 代理(`plate_client.py:73`)**」两句改真:自本次起 `/full` 代理**也**走这条 3s 软取(取数已统一),`PLATE_TIMEOUT_SEC` 的 30s 只服务 `convert` 等「等不到就报错」的链路。**必须写明这是行为变更及其方向**(慢 plate 时候选树从「等 30s 后报错」变「3s 后降级/供旧面」)。

- [ ] **Step 5: 补 spec §3.5**

在 spec §3 末尾追加 §3.5「超时统一」,写明:取数统一迫使代理接受 3s;30s 方案会推翻阶段一 Z4;按调用方各传超时已被代码库否决(`config.py` 原注释的论证),故 3s 是推论而非选择。

- [ ] **Step 6: 运行**

Run: `D:/python/python.exe -m pytest tests/test_endpoint_catalog_proxy.py tests/test_endpoint_declarations.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add -A src/gimbal-platform/backend docs/superpowers/specs/2026-09-13-judgment-surface-convergence-design.md
git commit -m "feat(endpoint-catalog): 代理返回 declared_surface,取数统一到 plate_client(含 3s 超时统一)"
```

---

### Task 4: 前端消费 `declared_surface`,body 半物化前缀,删前缀扫描

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts`
- Modify: `src/gimbal-platform/frontend/src/utils/assertion-registry.ts:16-52`
- Modify: `src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts`
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts`

**Interfaces:**
- Consumes: 代理响应的 `declared_surface: string[] | null`
- Produces:
  - `containerPrefixes(path: string): string[]` — 与后端 `_container_prefixes` 同构
  - `injectablePathSetOf(bodyLeaves, declaredSurface?: readonly string[] | null): ReadonlySet<string>`

- [ ] **Step 1: 写失败用例 —— 前缀物化与后端同构**

```ts
import { describe, expect, it } from 'vitest'
import { containerPrefixes } from '@/utils/assertion-registry'

describe('containerPrefixes 与后端 _container_prefixes 同构', () => {
  // 后端语义(run_injection.py:112):段边界 —— `.` 之后 / `[` 之前
  it.each([
    ['$.a.b', ['$', '$.a']],
    ['$.tags[0]', ['$', '$.tags']],
    ['$.a.b.c', ['$', '$.a', '$.a.b']],
    ['$', []],
  ])('%s → %j', (path, expected) => {
    expect(containerPrefixes(path)).toEqual(expected)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test:run -- src/utils/__tests__/assertion-registry.test.ts`
Expected: FAIL — `containerPrefixes is not a function`

- [ ] **Step 3: 实现**

在 `assertion-registry.ts` 追加:

```ts
/** 路径的各级容器前缀 —— 与后端 `_container_prefixes`(run_injection.py:112)
 *  **同构**:段边界 = `.` 之后 / `[` 之前。`$.a.b` → `['$', '$.a']`。
 *
 *  为什么需要它:后端 `injectable_universe` 把前缀 **materialize** 进集合,
 *  完成后两侧才能都只做成员判定。此前前端靠扫描代替物化(见下),
 *  那是同一概念的第三份实现 —— 本次收敛掉。 */
export function containerPrefixes(path: string): string[] {
  const out: string[] = []
  for (let i = 1; i < path.length; i++) {
    const ch = path[i]
    if (ch === '.' || ch === '[') out.push(path.slice(0, i))
  }
  return out
}
```

`bodyPathSetOf` 改为物化前缀:

```ts
export function bodyPathSetOf(
  leaves: Array<{ source: string; path: string }>,
): ReadonlySet<string> {
  const out = new Set<string>()
  for (const l of leaves) {
    if (l.source !== 'body') continue
    out.add(l.path)
    for (const p of containerPrefixes(l.path)) out.add(p)
  }
  return out
}
```

`injectablePathSetOf` 的声明半改为并入后端给的面:

```ts
export function injectablePathSetOf(
  bodyLeaves: Array<{ source: string; path: string }>,
  declaredSurface?: readonly string[] | null,
): ReadonlySet<string> {
  const out = new Set<string>(['$'])
  for (const p of bodyPathSetOf(bodyLeaves)) out.add(p)
  // 声明半由后端算好(归一化 / 容器前缀 / 模板形态全部展开,spec §2.2)
  for (const p of declaredSurface ?? []) out.add(p)
  return out
}
```

`pathResolvable` 删掉 `:47-49` 的前缀扫描(两侧都已物化 ⇒ 与阶段一在后端删掉的那段同形同理),并把注释改写成当前行为:

```ts
export function pathResolvable(jsonpath: string, injectablePaths: ReadonlySet<string>): boolean {
  for (const form of [jsonpath, toTemplatePath(jsonpath)]) {
    if (injectablePaths.has(form)) return true
  }
  return false
}
```

- [ ] **Step 4: 运行**

Run: `npm run test:run -- src/utils/__tests__/assertion-registry.test.ts`
Expected: PASS

- [ ] **Step 5: 接线 `useInjectableSurface` 与类型**

`types/plate.ts` 的 `EndpointFullView` 加 `declared_surface?: string[] | null`;`useInjectableSurface.declarationsFor(si)` 的消费点改为读 `getEndpointFull(eid)?.declared_surface`,传给 `injectablePathSetOf`。

- [ ] **Step 6: 全前端回归**

Run: `npm run test:run && npm run typecheck`
Expected: 全绿(阶段一基线:86 files / 819 tests)+ `vue-tsc` exit 0

- [ ] **Step 7: 提交**

```bash
git add src/gimbal-platform/frontend/src
git commit -m "refactor(frontend): 消费后端 declared_surface,body 半物化前缀,删前缀扫描"
```

---

### Task 5: `useEndpointFull` 加 300s TTL + 换面 policy

**Files:**
- Modify: `src/gimbal-platform/frontend/src/composables/useEndpointFull.ts`
- Modify: `src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts`
- Test: `src/gimbal-platform/frontend/src/composables/__tests__/useEndpointFull.test.ts`

**Interfaces:**
- Produces:
  - `export const FULL_TTL_MS = 300_000`
  - `export function surfaceVersion(eid: string): number` — 面每变一次自增,供消费方做记忆化键
- **不改 `endpointFullState` 的返回域**:它已有消费者按 `'loading'` / `''` 比较,新增第三个值会波及 `useInjectableSurface.pending` 与画布 `currentFullState`。面的新鲜度**一律由 `surfaceVersion` 表达**。

- [ ] **Step 1: 写失败用例**

沿用本文件既有手法(`vi.spyOn(api, 'getFullEndpoint')` + `_resetEndpointFullCacheForTest`):

```ts
function fullWith(paths: string[]) {
  return { id: 'ep-1', request: { declarations: paths.map((p) => ({ path: p })) } } as any
}

it('EF-TTL-1: 到期后重取,且面版本自增', async () => {
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce(fullWith(['$.a']))
    .mockResolvedValueOnce(fullWith(['$.b']))
  await ensureEndpointFull('ep-1')
  const v0 = surfaceVersion('ep-1')
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  await ensureEndpointFull('ep-1')
  expect(spy).toHaveBeenCalledTimes(2)
  expect(surfaceVersion('ep-1')).toBeGreaterThan(v0)
  vi.useRealTimers()
})

it('EF-TTL-2: 到期前不重取', async () => {
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(fullWith(['$.a']))
  await ensureEndpointFull('ep-1')
  vi.advanceTimersByTime(FULL_TTL_MS - 1)
  await ensureEndpointFull('ep-1')
  expect(spy).toHaveBeenCalledTimes(1)
  vi.useRealTimers()
})

it('EF-TTL-3: 过期但重取失败时,getEndpointFull 仍返回旧面(不闪空)', async () => {
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce(fullWith(['$.a']))
    .mockRejectedValueOnce(new Error('plate down'))
  await ensureEndpointFull('ep-1')
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  await ensureEndpointFull('ep-1')
  expect(getEndpointFull('ep-1')).toBeDefined()      // 旧面仍在
  expect(endpointFullState('ep-1')).toBe('failed')   // 但状态如实报失败
  vi.useRealTimers()
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test:run -- src/composables/__tests__/useEndpointFull.test.ts`
Expected: FAIL — `surfaceVersion is not a function` / TTL 相关断言红

- [ ] **Step 3: 实现(TTL 语义:读与取**各管一头**)**

`useEndpointFull.ts`:

- 缓存条目由 `EndpointFullView` 改为 `{ view: EndpointFullView; at: number; rev: number }`。
- **`ensureEndpointFull(eid)`(取)负责 TTL**:命中且 `Date.now() - at < FULL_TTL_MS` 才直接返回;否则**照常走取数流程**(负缓存窗口仍优先 —— 失败仍 10s 内不重发)。取回后内容与旧 `view` **不相等**时 `rev++`(相等则 `rev` 不动,避免无谓重算)。
- **`getEndpointFull(eid)`(读)不看 TTL**,永远返回缓存里那份(可能已过期)—— 这样重取期间 UI **不闪空**,重取失败时旧面继续服务(与后端 D 的 fail-open-to-old 同向)。
- `_resetEndpointFullCacheForTest()` 一并清 `rev` 表。

**换面 policy(spec §3.3,裁定 A)**:面变后 `pathsOfStep` 的记忆化键随之改变 ⇒ dead 集合自动重算;因契约更新而变悬空的条目**灰显 + 非阻断提示**(复用 T8 的 `degraded` 呈现位),**勾选状态保留** —— 交给 dispatch 侧既有的 dangling skip 兜底,**不新造失败态、不阻断提交**。

`useInjectableSurface.pathsOfStep` 的记忆化键把 `endpointFullState(eid)` 换成 `${eid}:${surfaceVersion(eid)}`(该 si 自身的端点 —— 保持既有注释警告的语义:不要改成「被引用端点的联合版本」)。

**同时更正 docstring**:`:14-15` 的「前端缓存**无 TTL**,与后端 300s 不同」改为「与后端同量级 300s TTL」;`:39-43` 关于画布渲染期取数的已知问题段**留待 T7 删除**(T7 才修那段代码)。

- [ ] **Step 4: 运行**

Run: `npm run test:run -- src/composables && npm run typecheck`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/frontend/src/composables
git commit -m "feat(frontend): /full 缓存改 300s TTL,换面即重判且勾选保留"
```

---

### Task 6: Z1 收紧 `exists` + 写侧宿主冲突拦截

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_injection.py:144-172`(判据)、`:258-272`(写侧)
- Modify: `src/gimbal-platform/backend/tests/test_run_injection.py`

**Interfaces:**
- Produces: `def _host_conflict(body: Any, path: str) -> bool`

- [ ] **Step 1: 写失败用例**

```python
async def test_exists_fallback_does_not_pierce_str_attributes():
    """$.note.replace 不再判活 —— exists 兜底前判宿主类型。"""
    body = {"note": "hello"}
    assert not await _resolvable("$.note.replace", body, injectable_universe(body, None))


async def test_empty_container_leniency_is_kept():
    """空容器宽容**不得**被一起收掉(run_injection.py:166-168 明文容许)。"""
    body = {"items": []}
    assert await _resolvable("$.items", body, injectable_universe(body, None))


async def test_write_side_skips_string_host_conflict():
    """绕过 UI 下发 $.note.replace 时按悬空 skip,不把字符串改形。"""
    definition = {"steps": [{"request": {"body": {"note": "hello"}}}]}
    entry = {"path": {"stepIndex": 0, "jsonpath": "$.note.replace"}, "value": "x"}
    out = compose_injection_scenario(definition, [entry])
    assert out["steps"][0].get("strategy") in (None, [])   # 未物化
```

- [ ] **Step 2: 运行确认失败**

Run: `D:/python/python.exe -m pytest tests/test_run_injection.py -k "pierce or leniency or host_conflict" -v`
Expected: FAIL(前两条:第一条红,第二条绿 —— 记下这个不对称,它是收紧范围的证据)

- [ ] **Step 3: 实现收紧**

```python
def _path_resolvable(jsonpath: str, body: Any, universe: set[str]) -> bool:
    for form in (jsonpath, _template_path(jsonpath)):
        if form in universe:
            return True
    # exists 兜底**只对 dict 宿主**生效(阶段二·① Z1):此前 _eval_nodes 的 FIELD
    # 分支对非 dict 走 getattr,于是 exists({'note':'hello'}, '$.note.replace')
    # 拿到绑定的 str.replace 方法 → 判活;而写侧引擎 _set_at 遇非 dict 即 data={}
    # ⇒ 把字符串 note 整体换成 {"replace": v},请求体被改形。
    # 空容器宽容(`body={"items":[]}` 的 `$.items`)是**另一件事**,有意保留:
    # 它方向是「少判死」,由下面这行之前的 universe 命中即可覆盖,不受本行影响。
    if not isinstance(body, dict):
        return False
    return exists(body, jsonpath)
```

- [ ] **Step 4: 实现写侧拦截**

```python
def _host_conflict(body: Any, target: str) -> bool:
    """``target`` 的路径是否落在非 dict 宿主上 —— 是则不可安全物化。

    引擎 ``_set_at`` 遇非 dict 即 ``data={}``,故往字符串/数字/列表的**内部**
    写值会把整个宿主改形(``$.request_body.note.replace`` 之于
    ``{"note":"hello"}`` ⇒ ``note`` 被整体换成 ``{"replace": v}``)。

    三条**不算冲突**(都是 Assign 的正常语义或可创建情形):
    * target 就是 ``$.request_body`` 本身 —— 整体覆写 body;
    * ``body`` 为 ``None``(无 body)—— Assign 会创建;
    * 路径段**缺失** —— 同样由 Assign 创建。

    ``target`` 形如 ``$.request_body.note.replace``:前两段是调用点(``:271``)
    固定加的前缀,不是 body 的段,**必须剥掉再走**;不匹配则不判、不猜。
    """
    segs = [s for s in target.split(".") if s]
    if segs[:2] != ["$", "request_body"]:
        return False
    rest = segs[2:]
    if not rest:
        return False
    if body is None:
        return False
    if not isinstance(body, dict):
        return True                 # body 存在但非 dict ⇒ 整段会被改形
    cur: Any = body
    for seg in rest[:-1]:           # 末段不判:覆写叶子是 Assign 的正常语义
        if seg not in cur:
            return False            # 缺失 ⇒ 后续由 Assign 创建
        cur = cur[seg]
        if not isinstance(cur, dict):
            return True
    return False
```

在 `compose_injection_scenario` 的物化点(`:271-272`)前插入:

```python
            body = (steps[si].get("request") or {}).get("body")
            if _host_conflict(body, target):
                logger.warning(
                    "injection entry skipped: 目标路径 {} 落在非 dict 宿主上 "
                    "(物化会改形宿主,target={})", jp, target)
                continue
```

**必须逐字照抄上面这个实现** —— 计划初稿的版本漏了「剥掉 `$.request_body` 前缀」这一步,导致首段 `"$"` 永远不在 body 里、**永远返回 False**(预检 R6)。若你按注释自行重写,请自行补齐边界:`body is None` / 路径段缺失 / target 恰为 `$.request_body` 三种情形都**不算**冲突。

- [ ] **Step 5: 运行**

Run: `D:/python/python.exe -m pytest tests/test_run_injection.py tests/test_run_injectable_wire.py tests/test_run_bindings_injection.py -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/gimbal-platform/backend/app/services/run_injection.py src/gimbal-platform/backend/tests/test_run_injection.py
git commit -m "fix(run_injection): exists 兜底不穿非 dict 宿主 + 写侧宿主冲突拦截(Z1)"
```

---

### Task 7: 画布渲染期取数收口

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue:635-640, 1591-1596`
- Modify: `src/gimbal-platform/frontend/src/composables/useEndpointFull.ts:39-43`(删已知问题段)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`

- [ ] **Step 1: 写覆盖面测试(先写,它会指出风险)**

挂载走本文件既有的挂载辅助;计数点用 `vi.spyOn(api, 'getFullEndpoint')`:

```ts
function stepWith(eid: string) {
  return { api: { method: 'POST', view_hints: { endpoint_id: eid } }, request: {} }
}

it('CANVAS-FETCH-1: 预拉覆盖 stepDecls 会问到的每一个端点', async () => {
  const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL_STUB)
  mountCanvas({ steps: [stepWith('ep-a'), stepWith('ep-b'), stepWith('ep-c')] })
  await flushPromises()
  expect(new Set(spy.mock.calls.map((c) => c[0])))
    .toEqual(new Set(['ep-a', 'ep-b', 'ep-c']))
})

it('CANVAS-FETCH-2: 渲染不再驱动取数', async () => {
  const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL_STUB)
  const w = mountCanvas({ steps: [stepWith('ep-a')] })
  await flushPromises()
  const afterMount = spy.mock.calls.length
  await w.vm.$nextTick()
  await w.vm.$nextTick()
  expect(spy.mock.calls.length).toBe(afterMount)
})
```

**CANVAS-FETCH-2 在 Step 3 之前必须是红的** —— 它正是「渲染期取数」的可执行定义。

- [ ] **Step 2: 运行确认第二条失败**

Run: `npm run test:run -- src/components/composer/__tests__/CaseComposerCanvas.test.ts`
Expected: 第二条 FAIL(渲染期确有取数)

- [ ] **Step 3: 删两行**

删掉 `:638` 与 `:1594` 的 `void ensureEndpointFull(eid)`。画布 `:1603-1605` 已有 `immediate: true` 的全 step 预拉,覆盖面由 Step 1 的测试钉住。

- [ ] **Step 4: 更正 docstring**

删掉 `useEndpointFull.ts:39-43` 那段把画布渲染期取数记为已知问题的文字;同步把 `docs/known-issues/platform/declaration-cache/canvas-render-path-fetch.md` 加 `## 修复记录`(不得删文件),并**更正其两处记载**:`stepDecls` 是 `function` 非 computed;`currentFull` 的取数是冗余的。

- [ ] **Step 5: 运行**

Run: `npm run test:run && npm run typecheck`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add src/gimbal-platform/frontend/src docs/known-issues
git commit -m "fix(canvas): 删两处渲染期取数,预拉覆盖面加测试钉住"
```

---

### Task 8: 降级重试通道(有界退避 + 失败态可见)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts`
- Modify: `src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue`(失败态呈现)
- Test: `src/gimbal-platform/frontend/src/composables/__tests__/useInjectableSurface.test.ts`

**Interfaces:**
- Produces: `useInjectableSurface(...)` 返回值新增 `degraded: ComputedRef<boolean>`

- [ ] **Step 1: 写失败用例**

```ts
it('负缓存窗口过后自动重试一次(有界)', async () => {
  vi.useFakeTimers()
  fetchSpy.mockRejectedValue(new Error('plate down'))
  mount(...)
  await flushPromises()
  const n1 = fetchSpy.mock.calls.length
  vi.advanceTimersByTime(61_000)
  await flushPromises()
  expect(fetchSpy.mock.calls.length).toBeGreaterThan(n1)
  // 有界:再等同样的时间不再增长
  const n2 = fetchSpy.mock.calls.length
  vi.advanceTimersByTime(600_000)
  await flushPromises()
  expect(fetchSpy.mock.calls.length).toBe(n2)
})

it('RETRY-2: 失败态可见', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))
  const surface = mountSurface()                 // 本文件既有的挂载辅助
  await flushPromises()
  expect(surface.degraded.value).toBe(true)
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test:run -- src/composables/__tests__/useInjectableSurface.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现**

在 `useInjectableSurface` 内加退避重试:被引用端点出现 `failed` 时,按 `[10_000, 30_000, 60_000]` 三次后**停止**;定时器落在组合式内(它属于「取」,与挂载时的 `ensure()` 同类,**不违反读/取分离** C18)。`degraded` = 存在被引用端点为 `failed`。

- [ ] **Step 4: 运行**

Run: `npm run test:run -- src/composables && npm run typecheck`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/frontend/src
git commit -m "fix(frontend): 契约降级后有界退避重试 + 失败态可见"
```

---

### Task 9: 文档收敛

**Files:**
- Modify: `docs/known-issues/platform/declaration-cache/cache-freshness-divergence.md`(状态改「已按阶段二·①收口」+ `## 修复记录`)
- Modify: `docs/known-issues/platform/declaration-cache/no-retry-after-degradation.md`(`## 修复记录`)
- Modify: `docs/known-issues/platform/declaration-cache/canvas-render-path-fetch.md`(T7 已完成)
- Create: `docs/known-issues/platform/registry/candidate-dropdown-duplication.md`(N:已评估不做)
- Modify: `docs/known-issues/README.md`(索引行同步 —— **不得再滞后**)
- Modify: `docs/adr/0003-retired-features-log.md`(退场行:前端声明半归一化、`toTemplatePath` 退出判定路径、`pathResolvable` 前缀扫描)
- Modify: `docs/PLATFORM-SCENARIO-COMPOSER-API.md`(代理响应新增 `declared_surface`)
- Modify: `docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md:105`(公开承诺修订)

- [ ] **Step 1: 逐项改**（按上表,每条记录按 README 约定「改记录、保留历史、不删文件」）
- [ ] **Step 2: M 的裁定写进 API 文档**（画布样本候选 vs 编辑器声明候选 = 有意差异,附「前提:用户显式触发」）
- [ ] **Step 3: spec `:105` 的修订稿交用户过目后再提交**（改的是已交付 spec 的公开承诺）
- [ ] **Step 4: 提交**

```bash
git add docs
git commit -m "docs: 阶段二·① 的 known-issues / ADR / API 文档收敛(M/N 裁定 + 四条记录)"
```

---

### Task 10: 全量回归 + 四道门

- [ ] **Step 1: 后端全量**

Run: `D:/python/python.exe -m pytest -q`
Expected: **只允许**那 2 条既有环境失败(撕裂行根因);任何新增失败必须归因并修复。

- [ ] **Step 2: 前端全量 + 类型**

Run: `cd src/gimbal-platform/frontend && npm run test:run && npm run typecheck`
Expected: 全绿(基线 86 files / 819 tests);`vue-tsc` exit 0

- [ ] **Step 3: plate + 执行核零改动**

Run: `git diff --stat bd99740..HEAD -- src/gimbal-plate src/gimbal-core src/gimbal`
Expected: 空输出

- [ ] **Step 4: 逐条核对 spec §9 的验收要点**(尤其:删扫描后既有用例全绿 / D 的 stale-snapshot 用例仍绿 / 跨语言前缀对拍)

- [ ] **Step 5: 报告**

---

## Self-Review

**Spec coverage:** §2(H/a1)→T3/T4;§3(I)→T1/T2/T3;§3.3(换面)→T5;§3.5(超时,新增)→T3;§4(Z1)→T6;§5(canvas)→T7;§6(no-retry)→T8;§7(M/N)→T9;§8(外溢)→T9;§9(验收)→T10;§11(全局约束)→各任务提交前自查。**无遗漏。**

**已知的两处偏离,已在正文写明**:(1) 新增 §3.5 超时统一 —— 写计划时发现,已回填 spec;(2) `declared_surface` 降级取显式 `null`。
