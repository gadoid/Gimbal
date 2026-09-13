"""plate_client.get_endpoint_full 的取数 + 缓存语义。

钉住五条:失败不写缓存与旧快照回退(D)、LRU 容量上界(S)、时间戳取在成功
之后(U)、告警只按时间窗老化(告警表在消费者侧,本层只交 reason/stale)、
在飞收敛 + shield 取消隔离。另钉取数层的两条边界:``timeout`` 逐请求下发
(3s 软取上限,不是客户端级的 30s)、本层不解读声明(空目录 / 缺键 / 空 item
都照常返回 item,不是降级)。

``endpoint_declarations`` 在派生层消费本层的 item(声明面 + path 投影),由
``tests/test_endpoint_declarations.py`` 覆盖;本文件只钉 ``plate_client`` 这一层。
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.config import settings
from app.services import plate_client


def _envelope(item: dict) -> dict:
    return {"ok": True, "dim": "endpoint", "data": {"item": item}}


def _item(decls):
    return {"request": {"declarations": decls}, "responses": {"200": {}}}


@pytest.fixture
async def install_transport(monkeypatch):
    """把 plate_client 的单例换成 MockTransport 客户端,并记录请求数。

    卸载时**关闭**本次装过的每个客户端,不止 ``set_client_for_tests(None)``:
    解绑只是 rebind 全局,裸 ``AsyncClient`` 被 GC 时会漏一条 ``ResourceWarning``
    —— 那是**本工作引入**的噪声,不该花掉门禁里「既有噪声」的预算(用例自己
    提前 ``set_client_for_tests(None)`` 的,也在这里关)。
    """
    calls: list[str] = []
    installed: list[httpx.AsyncClient] = []

    def make(handler):
        def _wrapped(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return handler(request)
        client = httpx.AsyncClient(transport=httpx.MockTransport(_wrapped),
                                   base_url=settings.PLATE_BASE_URL)
        installed.append(client)
        plate_client.set_client_for_tests(client)
        return calls

    plate_client._reset_full_cache_for_test()
    try:
        yield make
    finally:
        for client in installed:
            if not client.is_closed:
                await client.aclose()
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


async def _wait_until(pred, tries: int = 500) -> bool:
    """推进事件循环直到 pred 为真(避免靠固定 sleep(0) 次数猜调度)。"""
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(0)
    return pred()


# ── 缓存语义(C21 TTL / D / S / U)───────────────────────────────────

async def test_ttl_zero_refetches(monkeypatch, install_transport):
    """C21:TTL 被**实时**读取 —— settings 一改即刻生效,无需重建缓存。"""
    calls = install_transport(
        lambda req: httpx.Response(200, json=_envelope(_item([]))))
    await plate_client.get_endpoint_full("ep-1")
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)
    await plate_client.get_endpoint_full("ep-1")
    assert len(calls) == 2


async def test_failure_returns_none_and_does_not_cache(install_transport):
    """失败入不了缓存:下次调用必须重试,而不是把一次抖动记成「不可得」。"""
    state = {"fail": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json=_envelope(_item([{"path": "$.a"}])))

    calls = install_transport(handler)
    failed = await plate_client.get_endpoint_full("ep-x")
    assert failed.item is None                # 拿不到 → 调用侧降级
    assert failed.stale is False              # 不是「回退」,是「不可得」
    assert failed.reason                      # 告警链路的遥测必须带上
    state["fail"] = False
    retried = await plate_client.get_endpoint_full("ep-x")
    assert retried.item is not None           # 失败不入缓存 → 可重试
    assert len(calls) == 2


async def test_stale_snapshot_survives_a_failed_refresh(monkeypatch, install_transport):
    """D:TTL 过期后刷新失败 → **旧快照仍服务**(stale-while-error)。

    一次 plate 抖动不得把契约面从「有面」降级成「空面」;``stale=True`` 是
    调用方发降级告警的唯一依据。回退路径的 ``status`` 是那次**刷新失败**的状态
    (item 非 None + ``stale=True`` 已经说明「这份是旧的」,状态位回答「为什么旧」)。
    """
    state = {"fail": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json=_envelope(
            _item([{"path": "$.customer_id"}])))

    install_transport(handler)
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)        # 立即过期
    monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
    first = await plate_client.get_endpoint_full("ep-s")                # 先成功入缓存
    assert first.item is not None and first.stale is False
    state["fail"] = True
    got = await plate_client.get_endpoint_full("ep-s")
    assert got.item is not None, "刷新失败时应回退旧快照,而不是降级为 None"
    assert got.item["request"]["declarations"] == [{"path": "$.customer_id"}]
    assert got.stale is True
    assert got.status == 503, "回退时的状态是那次刷新失败的状态(不是回退快照的)"
    assert got.reason, "回退分支的告警必须带失败原因(它此刻就在 reason 里)"


async def test_stale_window_does_not_swallow_an_empty_item(monkeypatch, install_transport):
    """刷新**成功**但 item 是 ``{}`` → 用新快照,不回退旧快照。

    ``{}`` 是合法 item,不是「没刷新成功」:回退分支的判据必须是 ``is None``
    而非真值(§5),否则这份空契约会被静默换成旧快照、还挂上一条空 ``reason``
    的 stale 告警(消费者据此报降级 —— 一次假告警)。
    """
    state = {"empty": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["empty"]:
            return httpx.Response(200, json=_envelope({}))
        return httpx.Response(200, json=_envelope(_item([{"path": "$.a"}])))

    install_transport(handler)
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)        # 立即过期
    monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
    first = await plate_client.get_endpoint_full("ep-e")                # 先成功入缓存
    assert first.item == _item([{"path": "$.a"}])
    state["empty"] = True
    got = await plate_client.get_endpoint_full("ep-e")
    assert got.item == {}                 # 刷新成功 → 新快照,不是回退
    assert got.stale is False
    assert got.reason == ""
    assert got.status == 200              # 刷新成功 ⇒ 200(空 item 不是失败)


# ── status:三种失败情形分得开(错误码映射的承重面)─────────────────

async def test_plate_404_reports_the_real_status(install_transport):
    """plate 非 200 → ``status`` 是**那个真实状态码**(尤其 404)。

    「拿到了 404」(端点不存在)与「连不上」(plate 不可达)必须分得开 ——
    status 只剩 200-or-None 会让 404 那条映射永不触发。
    """
    install_transport(lambda req: httpx.Response(404, json={"ok": False}))
    res = await plate_client.get_endpoint_full("ep-missing")
    assert res.item is None
    assert res.stale is False
    assert res.status == 404
    assert "plate status 404" in res.reason


async def test_connection_failure_has_no_status(install_transport):
    """连接失败 / 超时 = **没拿到响应** ⇒ ``status is None``(与 404 是两件事)。"""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    install_transport(handler)
    res = await plate_client.get_endpoint_full("ep-down")
    assert res.item is None
    assert res.status is None             # 没拿到响应 → 没有状态码可报
    assert res.reason


async def test_invalid_envelope_is_not_reported_as_unreachable(install_transport):
    """200 但信封无 dict item = 第三种情形:``status == 200`` 配 ``item is None``。

    若这里落 None,就与「连不上」合并成同一格 —— 调用方再也分不出
    「plate 回了话但信封不可用」。
    """
    install_transport(lambda req: httpx.Response(200, json={"ok": True, "data": {}}))
    res = await plate_client.get_endpoint_full("ep-noitem")
    assert res.item is None
    assert res.status == 200
    assert res.reason == "no item in plate envelope"


async def test_cache_has_lru_bound(monkeypatch, install_transport):
    """S:超过 max_entries 时逐出最旧 —— 不再是"永不淘汰"。"""
    calls = install_transport(
        lambda req: httpx.Response(200, json=_envelope(_item([]))))
    monkeypatch.setattr(settings, "DECLARED_PATHS_MAX_ENTRIES", 1)
    await plate_client.get_endpoint_full("ep-1")
    await plate_client.get_endpoint_full("ep-2")
    await plate_client.get_endpoint_full("ep-1")     # ep-1 已被逐出 ⇒ 必须重取
    assert len(calls) == 3


async def test_fresh_window_starts_at_success_not_at_request_start(
        monkeypatch, install_transport):
    """U:TTL 起点取在**成功之后**,不是请求发起时。

    取数耗时 > TTL 时,时间戳若打在请求发起时,条目**一入缓存即已过期**
    ⇒ 每次调用都重取(缓存退化为无缓存)。
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.4)                 # 慢取数:耗时 > TTL
        return httpx.Response(200, json=_envelope(_item([{"path": "$.a"}])))

    calls = install_transport(handler)
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.25)
    assert (await plate_client.get_endpoint_full("ep-slow-ttl")).item is not None
    assert (await plate_client.get_endpoint_full("ep-slow-ttl")).item is not None
    assert len(calls) == 1, "时间戳应在取数成功后打点(否则慢取数一入缓存即过期)"


# ── 在飞收敛 + 取消隔离(shield 与完成回调摘除)─────────────────────

async def test_concurrent_cold_calls_coalesce_to_one_fetch(install_transport):
    """在飞收敛:冷缓存并发同端点 → 只打一次 plate,两者同一结果。"""
    calls = install_transport(
        lambda req: httpx.Response(200, json=_envelope(_item([{"path": "$.a"}]))))
    a, b = await asyncio.gather(
        plate_client.get_endpoint_full("ep-1"),
        plate_client.get_endpoint_full("ep-1"),
    )
    assert len(calls) == 1          # 收敛为同一在飞请求(或后到者直接命中缓存)
    assert a.item is not None and a.item == b.item


async def test_cancelled_waiter_does_not_kill_shared_fetch(install_transport):
    """等待方被取消不得连带取消共享取数(取消只落自己)。

    裸 ``await task`` 会把取消扩散进共享任务:创建者收到 CancelledError、
    其他等待方也全军覆没 —— 真链路上那会让 fan-out 被判取消、不写终止
    JSONL 行,执行卡在 running,直到下次进程重启。
    """
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        await release.wait()                 # 挂住,制造稳定的在飞窗口
        return httpx.Response(200, json=_envelope(_item([{"path": "$.a"}])))

    calls = install_transport(handler)
    creator = asyncio.ensure_future(plate_client.get_endpoint_full("ep-slow"))
    try:
        assert await _wait_until(lambda: "ep-slow" in plate_client._FULL_INFLIGHT)
        shared = plate_client._FULL_INFLIGHT["ep-slow"]

        # 第二个等待方:在飞期间被取消(取消落在它自己的 shield 等待上)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(plate_client.get_endpoint_full("ep-slow"), timeout=0.05)
        assert shared.cancelled() is False   # 共享任务未被连带取消
        assert not creator.done()            # 创建者仍在等,没被波及

        release.set()
        assert (await creator).item is not None   # 创建者照常拿到结果
        assert len(calls) == 1                    # 全程只打一次 plate
    finally:
        release.set()
        plate_client.set_client_for_tests(None)


async def test_cancelled_creator_still_clears_inflight(install_transport):
    """创建者被取消 → 在飞项仍会在**完成时**被摘除(不是永久锈住)。

    摘除由任务完成回调驱动,不依赖创建者的 ``finally``;否则创建者一被取消,
    该端点的在飞项就永远留着,后续调用全被钉在死任务上。
    """
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        await release.wait()
        return httpx.Response(200, json=_envelope(_item([{"path": "$.a"}])))

    install_transport(handler)
    creator = asyncio.ensure_future(plate_client.get_endpoint_full("ep-slow"))
    try:
        assert await _wait_until(lambda: "ep-slow" in plate_client._FULL_INFLIGHT)
        shared = plate_client._FULL_INFLIGHT["ep-slow"]

        creator.cancel()
        with pytest.raises(asyncio.CancelledError):
            await creator
        assert shared.cancelled() is False           # 取消不扩散,共享取数还活着
        assert "ep-slow" in plate_client._FULL_INFLIGHT   # 尚未完成,仍在飞

        release.set()
        assert await _wait_until(lambda: "ep-slow" not in plate_client._FULL_INFLIGHT)
        shared_item, shared_status = await shared     # 结果就绪且可用(未被打断)
        assert isinstance(shared_item, dict)
        assert shared_status == 200
    finally:
        release.set()
        plate_client.set_client_for_tests(None)


# ── 取数层的边界:本层不解读声明 ──────────────────────────────

async def test_empty_declarations_still_yields_item(install_transport):
    """``declarations: []`` 是**成功**取数 —— item 照常返回,不是降级。

    「真无声明 vs 降级」的判定在派生层(空目录 → 空面);取数层若把空目录当
    拿不到 item,那个区分就无从谈起(carry 侧会被误判成降级)。
    """
    install_transport(lambda req: httpx.Response(200, json=_envelope(
        {"request": {"declarations": []}, "responses": {}})))
    res = await plate_client.get_endpoint_full("ep-empty")
    assert res.item is not None
    assert res.item["request"]["declarations"] == []


@pytest.mark.parametrize("item", [
    {"request": {}},                       # 封套合法但缺 declarations 键
    {"request": {"declarations": None}},   # declarations: null
    {},                                    # 整份空 item(§5:{} 是真值 falsy 但合法)
])
async def test_absent_declarations_still_yields_item(item, install_transport):
    """缺键 / null / 整份空 item 同款:endpoint 本就没有 body 声明是**成功**结果。

    取数层只认「有没有整份 item」;缺声明键的判定留给派生层。第三条同时钉住
    §5:``{}`` 是**有意义**的 item —— 若拿它当「拿不到」做真值合并
    (``if not item``),那份空契约就被报成降级。
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(item))

    install_transport(handler)
    res = await plate_client.get_endpoint_full("ep-nobody")
    assert res.item is not None
    assert res.stale is False and res.reason == ""


async def test_soft_timeout_is_per_request(install_transport):
    """``timeout=None`` ⇒ 逐请求带 ``DECLARED_PATHS_TIMEOUT_SEC``(3s 软取上限)。

    这条上限必须落在**逐请求**层:客户端级的是 ``PLATE_TIMEOUT_SEC``(30s,服务
    ``convert`` 一类「等不到就报错」的链路),拿它当软取上限就把 /runs 的同步段
    绑在了那条线上。httpx 把生效的 timeout 放进 ``request.extensions``,传输层
    读到的就是生产链路真正用上的值;客户端级的值与之不同,断言才有判别力。
    """
    seen: list[float | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # §5 例外:两侧同为「未提供 timeout 扩展」的缺省形(None / {}),合并后
        # ``.get("read")`` 仍得 None;0.0 是**有意义的值**(显式要求零超时)。
        seen.append((request.extensions.get("timeout") or {}).get("read"))
        return httpx.Response(200, json=_envelope(_item([])))

    install_transport(handler)
    await plate_client.get_endpoint_full("ep-t")
    await plate_client.get_endpoint_full("ep-t-explicit", timeout=7.5)
    assert seen == [pytest.approx(settings.DECLARED_PATHS_TIMEOUT_SEC), 7.5]
