"""声明面取数(spec v3.1 §3):契约 request.declarations 的 path 全集,
进程缓存 + TTL + fail-soft。"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.core.config import settings
from app.services import plate_client
from app.services.carry_injection import _endpoint_declarations
from app.services.endpoint_declarations import (
    _INFLIGHT, _reset_declared_paths_cache, declarations_of, declared_paths_of,
)

_PATHS = frozenset({"$.bl_no", "$.customer_id", "$.items", "$.items.sku"})


def _envelope(item: dict) -> dict:
    """plate /full 信封(只用到 data.item 一层)。"""
    return {"ok": True, "dim": "endpoint", "data": {"item": item}}


def _declarations_item() -> dict:
    return {"request": {"declarations": [
        {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
        {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True},
        {"name": "items", "path": "$.items", "state": "form", "required": False,
         "children": [{"name": "sku", "path": "$.items.sku", "state": "form",
                       "required": True}]},
    ]}}


def _install(client_handler):
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(client_handler), base_url="http://plate-test",
    ))


async def _wait_until(pred, tries: int = 500) -> bool:
    """推进事件循环直到 pred 为真(避免靠固定 sleep(0) 次数猜调度)。"""
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(0)
    return pred()


@pytest.fixture(autouse=True)
def _install_transport(monkeypatch):
    """plate 单例换成可编程 MockTransport;每例前清缓存。"""
    calls: list[str] = []
    payload = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": [
            {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
            {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True},
            {"name": "items", "path": "$.items", "state": "form", "required": False,
             "children": [{"name": "sku", "path": "$.items.sku", "state": "form", "required": True}]},
        ]}}},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=payload)

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test")
    )
    _reset_declared_paths_cache()
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 300.0)
    yield calls
    plate_client.set_client_for_tests(None)


async def test_declared_paths_of_returns_flat_path_set(_install_transport):
    paths = await declared_paths_of("fin.order.add")
    assert paths is not None
    assert {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"} <= set(paths)
    assert len(_install_transport) == 1


async def test_second_call_hits_cache(_install_transport):
    await declared_paths_of("fin.order.add")
    await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 1          # 缓存命中,只拉一次


async def test_ttl_zero_refetches(monkeypatch, _install_transport):
    await declared_paths_of("fin.order.add")
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)
    await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 2


async def test_concurrent_cold_calls_coalesce_to_one_fetch(_install_transport):
    """在飞收敛:冷缓存并发同端点 → 只打一次 plate,两者同一结果。"""
    a, b = await asyncio.gather(
        declared_paths_of("fin.order.add"),
        declared_paths_of("fin.order.add"),
    )
    assert len(_install_transport) == 1          # 收敛为同一在飞请求
    # == 而非 is:投影随取数入缓存,两条返回路径都直接取那份算好的 frozenset
    # (不重派生)—— 但断言取**等值**而非同一对象:收敛要保的是「同一次取数」,
    # 不是同一个对象。
    assert a is not None and a == b
    assert {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"} <= set(a)


async def test_carry_delegate_and_paths_share_one_fetch(_install_transport):
    """跨消费者共用取数:carry 侧门面与 declared_paths_of 只打一次 plate。"""
    decls = await _endpoint_declarations("fin.order.add")
    assert isinstance(decls, list) and len(decls) == 3   # carry 侧拿到原始列表
    paths = await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 1                  # 合并生效:只打一次
    assert paths == frozenset(
        {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"}
    )


async def test_failure_returns_none_and_does_not_cache(monkeypatch):
    state = {"fail": True, "calls": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json={
            "ok": True, "dim": "endpoint",
            "data": {"item": {"request": {"declarations": [
                {"name": "a", "path": "$.a", "state": "form", "required": True}]}}},
        })

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test")
    )
    _reset_declared_paths_cache()
    assert await declared_paths_of("ep-x") is None      # 失败 → 降级信号
    state["fail"] = False
    assert await declared_paths_of("ep-x") == frozenset({"$.a"})   # 失败不入缓存 → 可重试
    assert state["calls"] == 2
    plate_client.set_client_for_tests(None)


async def test_returned_list_is_a_copy_not_the_cached_object(_install_transport):
    """返回浅拷贝:调用方改自己那份不污染进程缓存(它现在是共享公共面)。

    两条返回路径**都要**是拷贝 —— 取数路径与缓存命中路径各覆盖一次。
    """
    first = await declarations_of("fin.order.add")       # 取数路径
    first.clear()                                        # 疏忽/恶意的调用方
    second = await declarations_of("fin.order.add")      # 缓存命中路径
    second.clear()
    # 两条路径若漏了拷贝,缓存已被清空 → 这里会得到空集
    assert await declared_paths_of("fin.order.add") == _PATHS
    assert len(_install_transport) == 1                  # 缓存未破坏 → 未重取


async def test_empty_declarations_is_empty_frozenset_not_none():
    """合法空目录 ≠ 降级:``[]`` → 空 frozenset(**非 None**)。

    这个区分承载「真无声明 vs 降级」;只钉降级那一半(失败 → None)
    会漏掉本半,把空目录误当失败即本用例要拦的变异。
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope({"request": {"declarations": []}}))

    _install(handler)
    _reset_declared_paths_cache()
    paths = await declared_paths_of("ep-empty")
    assert paths is not None                 # 关键区分:不是降级
    assert isinstance(paths, frozenset)
    assert paths == frozenset()
    # 原始列表侧同款:空列表,不是 None
    assert await declarations_of("ep-empty") == []
    plate_client.set_client_for_tests(None)


@pytest.mark.parametrize("item", [
    {"request": {}},                       # 封套合法但缺 declarations 键
    {"request": {"declarations": None}},   # declarations: null
])
async def test_absent_declarations_is_empty_not_degraded(item):
    """真无声明(缺键 / null)≠ 降级 → 空 frozenset,而非 None。

    端点本就没有 body 声明是**成功**结果;若按「非 list → None」处理,
    这类端点每个失败链都会误报一条降级告警,并压掉该端点在
    ``_WARN_COOLDOWN_SEC`` 冷却窗内的真实告警。
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(item))

    _install(handler)
    _reset_declared_paths_cache()
    assert await declared_paths_of("ep-nobody") == frozenset()
    assert await declarations_of("ep-nobody") == []
    plate_client.set_client_for_tests(None)


async def test_garbage_declarations_is_degraded():
    """非 list 的垃圾值(字符串)才是降级 → None(与空目录区分开)。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(
            {"request": {"declarations": "$.oops"}}))

    _install(handler)
    _reset_declared_paths_cache()
    assert await declared_paths_of("ep-garbage") is None
    plate_client.set_client_for_tests(None)


async def test_cancelled_waiter_does_not_kill_shared_fetch():
    """等待方被取消不得连带取消共享取数(取消只落自己)。

    裸 ``await task`` 会把取消扩散进共享任务:创建者收到 CancelledError、
    其他等待方也全军覆没 —— 真链路上那会让 fan-out 被判取消、不写终止
    JSONL 行,执行卡在 running。
    """
    release = asyncio.Event()
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        await release.wait()                 # 挂住,制造稳定的在飞窗口
        return httpx.Response(200, json=_envelope(_declarations_item()))

    _install(handler)
    _reset_declared_paths_cache()
    creator = asyncio.ensure_future(declared_paths_of("ep-slow"))
    assert await _wait_until(lambda: "ep-slow" in _INFLIGHT)
    shared = _INFLIGHT["ep-slow"]
    try:
        # 第二个等待方:在飞期间被取消(取消落在它自己的 shield 等待上)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(declared_paths_of("ep-slow"), timeout=0.05)
        assert shared.cancelled() is False   # 共享任务未被连带取消
        assert not creator.done()            # 创建者仍在等,没被波及

        release.set()
        assert await creator == _PATHS       # 创建者照常拿到结果
        assert len(calls) == 1               # 全程只打一次 plate
    finally:
        release.set()
        plate_client.set_client_for_tests(None)


async def test_cancelled_creator_still_clears_inflight():
    """创建者被取消 → 在飞项仍会在**完成时**被摘除(不是永久锈住)。

    摘除由任务完成回调驱动,不依赖创建者的 ``finally``;否则创建者一被
    取消,该端点的在飞项就永远留着,后续调用全被钉在死任务上。
    """
    release = asyncio.Event()
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        await release.wait()
        return httpx.Response(200, json=_envelope(_declarations_item()))

    _install(handler)
    _reset_declared_paths_cache()
    creator = asyncio.ensure_future(declared_paths_of("ep-slow"))
    assert await _wait_until(lambda: "ep-slow" in _INFLIGHT)
    shared = _INFLIGHT["ep-slow"]

    creator.cancel()
    with pytest.raises(asyncio.CancelledError):
        await creator
    assert shared.cancelled() is False       # 取消不扩散,共享取数还活着
    assert "ep-slow" in _INFLIGHT            # 尚未完成,仍在飞

    release.set()
    assert await _wait_until(lambda: "ep-slow" not in _INFLIGHT)
    assert isinstance(await shared, list)    # 结果就绪且可用(未被打断)


# ── 声明面缓存收编 TtlLruCache(spec 架构收敛 §3.1;D/S/R/U)─────────────

async def test_stale_snapshot_survives_a_failed_refresh(monkeypatch):
    """D:TTL 过期后刷新失败 → **旧快照仍服务**(stale-while-error)。"""
    calls = {"n": 0, "fail": False}
    PAY = {"ok": True, "dim": "endpoint", "data": {"item": {"request": {"declarations": [
        {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True}]}}}}

    async def handler(request):
        calls["n"] += 1
        if calls["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json=PAY)

    plate_client.set_client_for_tests(httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)        # 立即过期
    monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
    assert await declared_paths_of("ep-s") == frozenset({"$.customer_id"})   # 先成功入缓存
    calls["fail"] = True
    got = await declared_paths_of("ep-s")
    assert got == frozenset({"$.customer_id"}), "刷新失败时应回退旧快照,而不是降级为 None"
    plate_client.set_client_for_tests(None)


async def test_projection_is_cached_not_recomputed(monkeypatch):
    """R:投影只在**取数**时算一次;TTL 命中路径不再重算(以 catalog_paths 调用计数断言)。"""
    import app.services.endpoint_declarations as ed

    calls = {"n": 0}
    real = ed.catalog_paths

    def _counting(decls):
        calls["n"] += 1
        return real(decls)

    async def _ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "dim": "endpoint", "data": {"item": {
            "request": {"declarations": [{"name": "a", "path": "$.a", "state": "form", "required": True}]}}}})

    monkeypatch.setattr(ed, "catalog_paths", _counting)
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(_ok_handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    await declared_paths_of("ep-p")
    after_first = calls["n"]
    await declared_paths_of("ep-p")          # TTL 内命中缓存
    assert calls["n"] == after_first == 1     # 投影没有第二次遍历
    plate_client.set_client_for_tests(None)


async def test_cache_has_lru_bound(monkeypatch):
    """S:超过 max_entries 时逐出最旧 —— 不再是"永不淘汰"。"""
    hits: list[str] = []

    async def handler(request):
        hits.append(request.url.path)
        return httpx.Response(200, json={"ok": True, "dim": "endpoint",
                                         "data": {"item": {"request": {"declarations": []}}}})

    monkeypatch.setattr(settings, "DECLARED_PATHS_MAX_ENTRIES", 1)
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    await declared_paths_of("ep-1")
    await declared_paths_of("ep-2")
    await declared_paths_of("ep-1")           # ep-1 已被逐出 ⇒ 必须重取
    assert len(hits) == 3
    plate_client.set_client_for_tests(None)


async def test_fresh_window_starts_at_success_not_at_request_start(monkeypatch):
    """U:TTL 起点取在**成功之后**,不是请求发起时。

    取数耗时 > TTL 时,时间戳若打在请求发起时,条目**一入缓存即已过期**
    ⇒ 每次调用都重取(声明面缓存在慢 plate 上退化为无缓存)。
    """
    hits: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.url.path)
        await asyncio.sleep(0.4)             # 慢取数:耗时 > TTL
        return httpx.Response(200, json=_envelope(_declarations_item()))

    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.25)
    _install(handler)
    _reset_declared_paths_cache()
    assert await declared_paths_of("ep-slow-ttl") == _PATHS     # 取数耗时 0.4s > TTL 0.25s
    assert await declared_paths_of("ep-slow-ttl") == _PATHS
    assert len(hits) == 1, "时间戳应在取数成功后打点(否则慢取数一入缓存即过期)"
    plate_client.set_client_for_tests(None)


async def test_cold_fetch_path_returns_a_copy_too(_install_transport):
    """冷取数路径同样返回浅拷贝(投影入缓存后,这条不再被上一条用例间接覆盖)。

    投影随取数缓存后,``declared_paths_of`` 只读缓存里那次算好的 frozenset ——
    ``test_returned_list_is_a_copy_not_the_cached_object`` 清空列表后仍能拿到
    path 集,对**冷取数路径是否拷贝**已无判别力。本用例直接钉住缓存载荷。
    """
    first = await declarations_of("fin.order.add")       # 冷路径:唯一一次取数
    assert first is not None and len(first) == 3
    first.clear()                                       # 疏忽/恶意的调用方
    again = await declarations_of("fin.order.add")      # 缓存命中路径
    assert again is not None and len(again) == 3, "冷取数路径也必须是浅拷贝:缓存载荷被调用方清空了"
    assert len(_install_transport) == 1                 # 缓存未破坏 → 未重取


async def test_degradation_warning_ages_out_by_time(monkeypatch):
    """S:降级告警按**时间窗**老化 —— 告警表(``_WARNED_AT``)只按
    ``_WARN_COOLDOWN_SEC`` 冷却窗去重,成功事件**不**重置它;一个长期失败的
    端点在每个冷却窗过后重新告警,不会一直失声。

    冷却窗设 0 ⇒ 每次失败都该重新告警(判别力:计数 2;若去重口径退化成
    「同一失败链内一次」,计数恒为 1 —— 本断言即钉住时间窗语义)。
    """
    import app.services.endpoint_declarations as ed
    from loguru import logger

    async def handler(request):
        return httpx.Response(503, json={"ok": False})

    _install(handler)
    _reset_declared_paths_cache()
    monkeypatch.setattr(ed, "_WARN_COOLDOWN_SEC", 0.0)
    seen: list[str] = []
    sink_id = logger.add(lambda m: seen.append(str(m)), level="WARNING")
    try:
        assert await declared_paths_of("ep-warn") is None
        assert await declared_paths_of("ep-warn") is None
    finally:
        logger.remove(sink_id)
    assert len([s for s in seen if "ep-warn" in s]) == 2
    # 告警必须带着**失败原因**(告警是降级链路上唯一的遥测:plate 503 / 信封缺
    # item / 连接失败要分得出来)。
    assert any("plate status 503" in s for s in seen), seen
    plate_client.set_client_for_tests(None)


async def test_stale_fallback_warning_carries_the_cause(monkeypatch):
    """D:回退分支的告警必须带失败原因(裁定 C23)。

    回退分支正是「静默供旧契约面」(fail-open-to-old,见 ``config.py`` 的
    ``DECLARED_PATHS_STALE_WINDOW_SEC`` 注释)—— 运维排查「carry 面为何陈旧」的
    第一现场;而 ``_warn_once`` 按端点 + 冷却窗去重,先发的哑告警会**压掉**后发
    的带原因那条 ⇒ 回退路径自己就得把原因带上(它此刻就在 ``_refresh`` 抛的
    ``RuntimeError`` 里)。动作短语「回退旧快照」是运维的判读锚点,必须保留。
    """
    from loguru import logger

    calls = {"n": 0, "fail": False}
    PAY = _envelope({"request": {"declarations": [
        {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True}]}})

    async def handler(request):
        calls["n"] += 1
        if calls["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json=PAY)

    _install(handler)
    _reset_declared_paths_cache()
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)     # 立即过期
    monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
    assert await declared_paths_of("ep-s") == frozenset({"$.customer_id"})   # 先成功入缓存
    calls["fail"] = True
    seen: list[str] = []
    sink_id = logger.add(lambda m: seen.append(str(m)), level="WARNING")
    try:
        got = await declared_paths_of("ep-s")
    finally:
        logger.remove(sink_id)
    assert got == frozenset({"$.customer_id"}), "前置:必须真的走回退分支"
    stale = [s for s in seen if "ep-s" in s]
    assert stale, seen
    # 原因:_refresh 的 RuntimeError 文本(plate status 503)必须出现在告警里
    assert any("plate status 503" in s for s in stale), seen
    # 动作短语仍在(裁定要的是「补原因」,不是推翻 D3/改动作语义)
    assert all("回退旧快照" in s for s in stale), seen
    plate_client.set_client_for_tests(None)


# ── 判定软取有界(Z4)──────────────────────────────────────────────
class _TimeoutEnforcingTransport(httpx.AsyncBaseTransport):
    """按**真实传输层**语义施加读超时的 MockTransport 替身。

    为什么不能用 ``httpx.MockTransport``(实测证据,勿"简化"回去):httpx 的
    逐请求超时只经 ``request.extensions["timeout"]`` 交给传输层,而
    ``MockTransport.handle_async_request`` 拿到该扩展**直接丢弃**。生产用的是
    ``AsyncHTTPTransport``(读它、并据此中断),所以那条上限在 MockTransport 下
    **测不到**:本用例在"传了 timeout"与"没传 timeout"两种实现下都等满 5s 并
    成功(实测 5.01s,断言恒红、零判别力)。本替身照真实读超时语义施加
    ``asyncio.wait_for``,断言于是测的是**生产链路**的行为,而不是替身的行为。
    """

    def __init__(self, handler) -> None:
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # §5 例外:两侧同为「未提供 timeout 扩展」的缺省形(``None`` / ``{}``),
        # 合并后 ``.get("read")`` 仍得 None;0.0 是**有意义的值**(显式要求零
        # 超时),不是被抹平的 falsy。
        read = (request.extensions.get("timeout") or {}).get("read")
        if read is None:                      # 显式判 None(§5):0.0 也是"要给"的值
            return await self._handler(request)
        try:
            # wait_for 在超时处**取消并回收**挂起的 handler ⇒ 不在事件循环上
            # 遗留 pending task(裸 sleep 留给 loop teardown 会报
            # "Task was destroyed but it is pending")。
            return await asyncio.wait_for(self._handler(request), timeout=read)
        except asyncio.TimeoutError:
            raise httpx.ReadTimeout("read timeout", request=request) from None


async def test_slow_plate_degrades_within_bounded_time(monkeypatch):
    """Z4:判定取数是**软取** —— plate 慢时在 3s 内降级,不把 /runs 绑到 30s。

    修的是这条链:dispatcher 同步段 ``gather(declared_paths_of(...))`` 一旦被
    plate 拖满 ``PLATE_TIMEOUT_SEC``(30s),就与前端 axios 的 30s 撞在同一条
    线上 —— 前端报失败、后端已建执行,用户重试即**重复执行**。故取数自带短
    超时,超时即降级从严(只认 body 面)。

    客户端的默认超时**照生产设 30s**:本用例要钉的正是「客户端 30s 不改,靠
    逐请求超时把它压下来」(客户端不设则为 httpx 默认 5.0,与 handler 的 5s
    睡眠撞车 → 用例不稳定)。
    """
    async def handler(request):
        await asyncio.sleep(5)                     # 超过 3s 判定超时
        return httpx.Response(200, json={"ok": True, "data": {"item": {}}})

    monkeypatch.setattr(settings, "DECLARED_PATHS_TIMEOUT_SEC", 0.3)   # 测试里收紧
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=_TimeoutEnforcingTransport(handler),
        base_url="http://plate-test",
        timeout=settings.PLATE_TIMEOUT_SEC,        # 生产同款 30s(与被测的逐请求超时无关)
    ))
    _reset_declared_paths_cache()
    t0 = time.monotonic()
    assert await declared_paths_of("ep-slow") is None       # 超时 → 降级
    assert time.monotonic() - t0 < 2.0                      # 有界(远小于 5s)
    plate_client.set_client_for_tests(None)
