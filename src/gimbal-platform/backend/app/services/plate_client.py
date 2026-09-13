"""HTTP client for the gimbal-plate FastAPI service (V3 composer).

Plate exposes a single ``POST /api/scenario/action/convert`` action for
the platform's preview / run use-case.  This wrapper:

* Owns a process-wide ``httpx.AsyncClient`` (created lazily on first
  call) so we don't pay TCP/TLS setup per request.
* Translates Plate's ``{ok, dim, data, error}`` envelope into Platform's
  flat error model (HTTPException with ``{detail: {code, message,
  errors[]}}``).
* Surfaces two typed errors the routers map to 502 ``plate_unavailable``
  vs 502 ``plate_rejected`` per docs/PLATFORM-SCENARIO-COMPOSER-API.md
  §4.7.
* Owns the process-wide cache for the ``GET /api/endpoint/{id}/full``
  contract fetch (:func:`get_endpoint_full`) — TTL/LRU/stale-while-error
  都在这里,见文件末尾「/full 契约取数」一节。

Run 执行链(V3.2):dispatcher convert 成功后把注入完成的用例落盘,
交 ``gimbal_launcher.launch`` 子进程(``gimbal run launch``)执行。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any

import httpx

from ..core.config import settings
from ..core.timeutil import utcnow as _utcnow
from .query_view_cache import TtlLruCache


# ─── typed errors ──────────────────────────────────────────────────
class PlateUnavailableError(Exception):
    """Plate couldn't be reached (connect / timeout / 5xx).

    Maps to HTTP 502 ``plate_unavailable``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PlateRejectedError(Exception):
    """Plate validated the call but rejected the payload (4xx).

    Routers map this to HTTP 422 ``plate_rejected`` (preview: the
    verdict is on the *client's draft*, not a gateway failure) carrying
    the upstream ``errors[]`` array so the frontend can render
    field-level hints.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        errors: list[dict[str, Any]] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or []
        self.status_code = status_code


# ─── singleton client ─────────────────────────────────────────────
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.PLATE_BASE_URL,
            timeout=settings.PLATE_TIMEOUT_SEC,
        )
    return _client


def set_client_for_tests(client: httpx.AsyncClient | None) -> None:
    """Replace (or clear) the singleton — used by the MockTransport
    fixture in test_scenario_composer_plate_integration.py."""
    global _client
    _client = client


# ─── plate 契约归一化 ──────────────────────────────────────────────
def fill_plate_defaults(
    payload: dict[str, Any], *, owner: str = ""
) -> dict[str, Any]:
    """就地补 plate /convert 必填而平台 UI 不采集的字段。

    Plate 的 Scenario 校验要求 meta 若干字段必填(requirementRef 等),
    平台编辑器不采集它们 —— preview/export 路由一直在发送前补默认,
    run 执行链曾漏做(存量场景 plate_rejected:meta.requirementRef
    Field required,2026-08-24 sc-test-5nhvaloj6)。归一化收敛在本
    模块:plate_client 拥有 plate 契约知识,preview 与 run 两条路径
    共用同一份默认值,不再各写一套。

    填充项(仅 setdefault 语义,已存在的值一律不动):
    * kind:"scenario"
    * scenarioId(顶层,缺失时镜像 meta.scenarioId)
    * meta.createTime(plate 必填;缺失时取当前时刻)
    * meta.requirementRef(plate 必填 list;UI 不采集 → [])
    * meta.owner(为空且调用方给了 owner 时填)
    """
    payload.setdefault("kind", "scenario")

    meta = payload.setdefault("meta", {})
    if not meta.get("createTime"):
        meta["createTime"] = _now_iso()
    meta.setdefault("requirementRef", [])
    if owner and not meta.get("owner"):
        meta["owner"] = owner

    payload.setdefault("scenarioId", meta.get("scenarioId", ""))
    return payload


def _now_iso() -> str:
    return _utcnow().isoformat() + "Z"


# ─── public surface ───────────────────────────────────────────────
async def convert(scenario_dict: dict[str, Any]) -> dict[str, Any]:
    """POST /api/scenario/action/convert(consumer 固定 "gimbal")。

    Plate 侧由 GimbalScenarioExporter 导出可执行 dict,自动
    model_dump(exclude=...) 剥掉平台视图扩展字段(endpoints /
    navigation / config_summary / steps[*].api.view_hints /
    steps[*].request.fields_meta / steps[*].strategy[*].view_note)。
    fields_meta 键控面 2026-09-05 目录化起随 M1 携带 state 与
    children 树(顶层 name 键控,值透传的 carry 顶层条目不进表)。
    step.field_states 是平台侧配置意图(§3.1),plate Step 模型
    extra=ignore 静默剥除 —— 注入面在 dispatch 预解析阶段读原始
    definition,不依赖 convert 产物。
    (plate 契约还支持 consumer="platform" 供 UI 渲染,但平台目前
    不消费 —— 需要时再加回该参数。)

    Returns Plate's ``data`` payload (``{consumer, converted}``) on
    success.  Raises :class:`PlateUnavailableError` on connect / 5xx,
    :class:`PlateRejectedError` on 4xx.
    """
    body = {"consumer": "gimbal", "scenario": scenario_dict}
    client = get_client()
    try:
        resp = await client.post("/api/scenario/action/convert", json=body)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e

    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    if resp.status_code >= 400:
        # _raise_rejected always raises; the explicit raise is
        # defensive against future changes that might return early.
        _raise_rejected(resp)
        raise PlateUnavailableError(  # pragma: no cover
            f"plate_unavailable: 4xx without envelope: {resp.text[:200]}"
        )

    envelope = resp.json()
    if not isinstance(envelope, dict) or not envelope.get("ok"):
        # Plate says not-ok but with 2xx — treat as rejected.
        raise PlateRejectedError(
            code="invalid_action",
            message=str(envelope.get("error") or envelope),
            errors=[],
        )
    return envelope.get("data") or {}


# ─── /full 契约取数(进程级缓存)────────────────────────────────────
# 语义:某端点 ``GET /api/endpoint/{id}/full`` → ``data.item``(整份契约 item;
# 派生面 —— ``request.declarations`` 及其 path 投影 —— 是它的子集)。
#
# 纪律:
# * **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 dict item)都返回
#   ``item=None``,调用方降级,绝不阻塞执行;
# * **失败不写缓存 + 旧快照回退(D)** — 失败不写缓存,下次调用可重试;TTL 过期后
#   **刷新失败时旧快照继续服务**,直到回退窗 ``DECLARED_PATHS_STALE_WINDOW_SEC``
#   走完才真过期(一次 plate 抖动不得把契约面从「有面」降级成「空面」);
# * **LRU 容量上界(S)** — ``DECLARED_PATHS_MAX_ENTRIES`` 逐出最旧;
# * **时间戳取在成功之后(U)** — 入缓存统一由 ``_refresh_full`` 在**成功那刻**做,
#   由 ``TtlLruCache.put`` 自己打点(不是请求发起时 —— 否则慢 plate 上条目一入
#   缓存即已过期,缓存退化);
# * **告警按时间窗老化** — 本层不持有告警表,只把 ``reason`` / ``stale`` 交给
#   消费者;消费者按端点 + 冷却窗去重,而那张表只随**时间**老化,成功事件不重置
#   它 —— 否则长期失败的端点在恢复前彻底失声(而它的告警正是降级的唯一遥测)。
#   故 ``reason`` 在失败路径上**永不为空**(空串 = 成功且非回退);
# * **缓存实例随 settings 惰性重建** — 见 :func:`_full_cache`;
# * **在飞收敛 + 取消隔离** — 见 :func:`_refresh_full` 与
#   :func:`_forget_full_inflight`。


@dataclass(frozen=True)
class EndpointFull:
    """``GET /api/endpoint/{id}/full`` 的一次取数结果。

    ``item`` 为 None ⇒ **不可得**(调用方降级)。``stale`` 为 True ⇒ item 来自
    **回退的旧快照**(刷新失败时旧快照继续服务,直到回退窗走完)。``reason`` 是
    失败原因(**告警链路上唯一的遥测**,空串表示成功且非回退)。

    ``status`` 是**这次取数拿到的 plate HTTP 状态**,各情形都有确定含义:
    * 刷新成功(含 TTL 命中)→ ``200``;
    * 回退旧快照(``stale=True``)→ 那次**刷新失败**的状态码 —— item 是旧的,
      状态位回答的是「为什么旧」,不是快照本身的状态;
    * 不可得(``item is None``)→ 失败时拿到的状态码;``200`` 配 ``item is None``
      是「响应拿到了,但信封里没有 dict item」;
    * ``None`` ⇒ **压根没拿到响应**(连接失败 / 超时)—— 与「拿到了 404」是
      两件事,不得合并(§5):前者「plate 不可达」、后者「端点不存在」。

    **``item`` 是缓存对象本身(只读,不是拷贝)**:本缓存是进程级共享面,本层
    不为每个消费者拷贝整份契约 item。消费者**不得就地修改**它 —— 要改的调用方
    **先自己 ``copy``**,再改自己那份(容器内的嵌套条目仍是共享的,同款只读
    契约)。

    为什么带回 stale/status/reason 而不是只返回 item:降级告警与错误码映射都需要
    这层区分 —— 三者都是**有意义的值**,不得被真值合并(§5)。
    """

    item: dict[str, Any] | None
    stale: bool
    status: int | None
    reason: str


def _full_cache_cfg() -> tuple[float, int, float]:
    """本缓存实例的三个构造参数(settings 现值)。"""
    return (settings.DECLARED_PATHS_TTL_SEC,
            settings.DECLARED_PATHS_MAX_ENTRIES,
            settings.DECLARED_PATHS_STALE_WINDOW_SEC)


def _build_full_cache() -> TtlLruCache:
    return TtlLruCache(ttl=settings.DECLARED_PATHS_TTL_SEC,
                       max_entries=settings.DECLARED_PATHS_MAX_ENTRIES,
                       stale_max_window=settings.DECLARED_PATHS_STALE_WINDOW_SEC)


_FULL_CACHE: TtlLruCache = _build_full_cache()
_FULL_CACHE_CFG: tuple[float, int, float] = _full_cache_cfg()
_FULL_INFLIGHT: dict[str, asyncio.Task[tuple[dict[str, Any] | None, int | None]]] = {}


def _full_cache() -> TtlLruCache:
    """当前缓存实例;settings 的三个参数变了就**换实例**(裁定 C21)。

    为什么不是模块级单例(别"简化"回去):``TtlLruCache`` 的 ttl/容量/回退窗
    **构造即冻结**,而用例 ``test_ttl_zero_refetches`` 钉的语义是「TTL 被
    **实时**读取」—— 它先取一次、再 monkeypatch ``DECLARED_PATHS_TTL_SEC``、
    **中间不重置缓存**就再取一次并断言必然重取;单例下那条必红。生产 cfg 恒定
    ⇒ 本分支永不触发,**等价单例**,只多一次元组比较。
    """
    global _FULL_CACHE, _FULL_CACHE_CFG
    cfg = _full_cache_cfg()
    if cfg != _FULL_CACHE_CFG:
        _FULL_CACHE = _build_full_cache()
        _FULL_CACHE_CFG = cfg
    return _FULL_CACHE


def _reset_full_cache_for_test() -> None:
    """测试钩子:按当前 settings 重建缓存、清在飞表。

    重建(而非逐键清)是必须的:``TtlLruCache`` 的 ttl/容量/回退窗构造即冻结,
    而调用方(测试)先 monkeypatch settings 再重置 —— 只有换实例才让新值生效。
    """
    global _FULL_CACHE, _FULL_CACHE_CFG
    _FULL_CACHE = _build_full_cache()
    _FULL_CACHE_CFG = _full_cache_cfg()
    _FULL_INFLIGHT.clear()


def _forget_full_inflight(
    task: asyncio.Task[tuple[dict[str, Any] | None, int | None]],
    endpoint_id: str,
) -> None:
    """任务完成回调:摘除**自己那个**在飞项(校验身份,迟到回调不误删后来者)。

    由完成回调驱动,而不是某个调用方的 ``finally`` —— 创建者可能被取消、等待方
    也可能先于任务完成退出,只有「任务真的完成了」才是摘除的正确时机(否则一次
    失败/取消会永久锈住该端点)。
    """
    if _FULL_INFLIGHT.get(endpoint_id) is task:
        _FULL_INFLIGHT.pop(endpoint_id, None)


async def _fetch_full_raw(endpoint_id: str, *, timeout: float,
                          fail_reason: list[str]) -> tuple[dict[str, Any] | None, int | None]:
    """真正打一次 plate。**fail-soft 绝不抛,也绝不写缓存**。

    入缓存统一由 ``_refresh_full`` 在**成功之后**做(U:时间戳由 ``TtlLruCache.put``
    在成功那一刻打点,不是本函数入口)。失败返回 ``(None, status)`` 且**不动**
    缓存 —— 旧快照因此能留到回退窗,由调用侧决定是否回退(D)。

    ``status`` 是**本次拿到的 plate HTTP 状态**,``None`` 表示压根没拿到响应
    (连接失败 / 超时)。这个区分是承重件:拿到了 404 与「连不上」是两件事,
    调用方要据此分开映射(端点不存在 vs plate 不可达),不得合并(§5)。注意
    ``status == 200`` 配 ``item is None`` 是第三种:响应拿到了,但信封里没有
    dict item。

    ``fail_reason[0]`` 回填失败原因(调用方组进 ``EndpointFull.reason``):告警是
    降级链路上唯一的遥测,「plate status 503 / 信封缺 item / 连接失败」必须透得
    出来。这个 list 由 ``_refresh_full`` 随本次取数创建、随任务一起回收,不是新的
    模块级状态。
    """
    status: int | None = None
    try:
        resp = await get_client().get(
            f"/api/endpoint/{endpoint_id}/full", timeout=timeout)
        status = resp.status_code
        if resp.status_code != 200:
            raise RuntimeError(f"plate status {resp.status_code}")
        # 缺省合并(例外,已核等价性 —— 不是「有意义 falsy 被真值合并」):信封缺
        # ``data`` 键 / ``data`` 为 ``null``/``{}`` 三种「未提供」都落到同一缺省
        # ``{}``,而 ``{}`` 正是缺省值本身;真·垃圾值(字符串/数字等非 dict)仍
        # 会在 ``.get`` 上抛错 → 降级。
        item: Any = (resp.json().get("data") or {}).get("item")
        # item 缺失 / 为 null / 非 dict 都是**拿不到契约面**(降级)。「真无声明」
        # (空目录)是派生层的事:那是成功拿到 item,只是它里面没有声明。
        if not isinstance(item, dict):
            raise RuntimeError("no item in plate envelope")
        return item, status
    except Exception as e:  # noqa: BLE001 — 契约不可得绝不阻塞判定
        fail_reason[0] = str(e)
        return None, status


class _FullFetchError(RuntimeError):
    """取数失败的内部出口,携带 plate 的 HTTP 状态(``None`` = 没拿到响应)。

    取数结果的两个分量(``item`` / ``status``)都是承重件,故失败也一并交出来 ——
    调用方要区分「拿到了 404」「信封不可用」「连不上」三种情形。只在
    ``plate_client`` 内部流转(``get_endpoint_full`` 把它折成
    ``EndpointFull``),调用方不捕获它。
    """

    def __init__(self, message: str, status: int | None) -> None:
        super().__init__(message)
        self.status = status


async def _refresh_full(endpoint_id: str, *, timeout: float) -> dict[str, Any] | None:
    """在飞收敛(shield + 完成回调摘除)后真正取一次;成功入缓存。

    shield:本调用方被取消只落自己,不连带取消共享取数 —— 裸 ``await task`` 会把
    取消扩散进共享任务(创建者随之收到 CancelledError);dispatcher 的
    ``except Exception`` **不捕** CancelledError → fan-out 被判取消、不写终止
    JSONL 行、执行卡在 running 直到下次进程重启。**务必保留 shield,摘除务必
    留在完成回调**(见 ``_forget_full_inflight``)。
    """
    fail_reason: list[str] = [""]      # 仅创建者那个任务持有它(见 _fetch_full_raw)
    inflight = _FULL_INFLIGHT.get(endpoint_id)
    if inflight is None:
        inflight = asyncio.ensure_future(_fetch_full_raw(
            endpoint_id, timeout=timeout, fail_reason=fail_reason))
        _FULL_INFLIGHT[endpoint_id] = inflight
        inflight.add_done_callback(partial(_forget_full_inflight, endpoint_id=endpoint_id))
    item, status = await asyncio.shield(inflight)
    if item is None:
        # 状态随**任务结果**回来,故复用他人在飞任务的等待方也拿得到真实状态码;
        # 只有原因串依赖创建者手上的 fail_reason(空串 = 「未提供」,与缺省串等价),
        # 复用者落缺省串 —— 真正的原因由创建者那份 ``EndpointFull.reason`` 透出。
        raise _FullFetchError(fail_reason[0] or "endpoint full fetch failed", status)
    # 成功才 put ⇒ 时间戳打在成功那刻(U),不是请求发起时。
    _full_cache().put(endpoint_id, item, _now_iso())
    return item


async def get_endpoint_full(endpoint_id: str, *, timeout: float | None = None) -> EndpointFull:
    """``GET /api/endpoint/{id}/full`` 的 item —— 带进程级 TTL/LRU/回退窗缓存。

    * 命中且未过期 → 直接返回缓存 item(``stale=False``,``status=200``);
    * 过期但在**回退窗**内 → 尝试刷新,**失败则回退旧快照**(D)并置
      ``stale=True``(调用方据此告警),``reason`` 带失败原因、``status`` 带那次
      刷新失败的 plate 状态;
    * 无缓存或已出回退窗 → 刷新;**失败即 ``item=None`` + reason**(调用侧降级),
      ``status`` 同款带失败状态(``None`` 表示连响应都没拿到 —— 见
      :class:`EndpointFull` 的四种情形)。

    TTL **不是形参**:它由 ``DECLARED_PATHS_TTL_SEC`` 在**缓存实例构造时冻结**
    (裁定 C21 —— 这样 settings 热改即刻生效),故没有「按调用方传 ttl」这回事。
    ``timeout`` 为 None 时取 ``DECLARED_PATHS_TIMEOUT_SEC``(3s 软取上限):这是一条
    **软取**,plate 慢过该值即降级从严,不把调用方绑到 ``PLATE_TIMEOUT_SEC``
    —— 那条 30s 服务 ``convert`` 一类「等不到就报错」的链路。

    边界:``adaptation_service._plate_full_endpoint`` / 目录代理各有自己的 /full
    取数,**不共享**本缓存 —— 本缓存只服务经本函数取数的消费者。
    """
    eff_timeout = settings.DECLARED_PATHS_TIMEOUT_SEC if timeout is None else timeout
    entry, fresh = _full_cache().lookup(endpoint_id)
    if entry is not None and fresh:
        return EndpointFull(item=entry.payload, stale=False, status=200, reason="")
    if entry is not None and not fresh:
        reason = ""                     # 先声明:出 except 块 Python 即 del e(裁定 C23)
        status: int | None = None       # 刷新失败时 plate 的真实状态(None = 没拿到响应)
        try:
            refreshed = await _refresh_full(endpoint_id, timeout=eff_timeout)
        except _FullFetchError as e:
            refreshed = None
            # 原因此刻就在手里(裁定 C23):_FullFetchError 的消息永不为空
            # (``fail_reason[0] or "endpoint full fetch failed"``)⇒ 无需缺省,不做真值合并(§5)。
            reason, status = str(e), e.status
        except Exception as e:                      # noqa: BLE001 — 兜底:非取数层的意外错误没有 plate 状态
            refreshed = None
            reason = str(e)
        if refreshed is None:                       # ← 显式,不用 or:``{}`` 是合法 item(§5)
            # 回退旧快照(D):告警由消费者发 —— 它按端点 + 冷却窗去重,故本层交出的
            # ``reason`` 必须带着原因,否则「静默供旧契约面」就没有任何遥测。
            # ``status`` 是那次**刷新失败**的状态(不是回退快照的状态):item 非 None
            # + ``stale=True`` 已经说明「这份是旧的」,状态位留给调用方看「为什么旧」。
            return EndpointFull(item=entry.payload, stale=True, status=status, reason=reason)
        return EndpointFull(item=refreshed, stale=False, status=200, reason="")
    try:
        refreshed = await _refresh_full(endpoint_id, timeout=eff_timeout)
    except _FullFetchError as e:                    # 不可得:状态码随异常上来(可能是 404)
        return EndpointFull(item=None, stale=False, status=e.status, reason=str(e))
    except Exception as e:                          # noqa: BLE001 — 兜底:非取数层的意外错误
        return EndpointFull(item=None, stale=False, status=None, reason=str(e))
    if refreshed is None:                           # 显式(不用 or):_refresh_full 靠 raise 报失败
        return EndpointFull(item=None, stale=False, status=None, reason="取数失败")
    return EndpointFull(item=refreshed, stale=False, status=200, reason="")


# ─── helpers ──────────────────────────────────────────────────────
def _raise_rejected(resp: httpx.Response) -> None:
    """Translate a 4xx into :class:`PlateRejectedError`.

    Best-effort envelope parsing — if the body isn't the expected shape
    we fall back to the raw status / text.
    """
    code = "invalid_action"
    message = ""
    errors: list[dict[str, Any]] = []
    try:
        envelope = resp.json()
    except Exception:  # noqa: BLE001
        envelope = None
    if isinstance(envelope, dict):
        err = envelope.get("error") or {}
        if isinstance(err, dict):
            code = str(err.get("code") or code)
            message = str(err.get("message") or message)
            details = err.get("details") or {}
            if isinstance(details, dict):
                inner = details.get("errors")
                if isinstance(inner, list):
                    errors = [e for e in inner if isinstance(e, dict)]
    if not message:
        message = f"plate rejected: status {resp.status_code}: {resp.text[:200]}"
    raise PlateRejectedError(
        code=code, message=message, errors=errors, status_code=resp.status_code
    )


async def aclose() -> None:
    """Close the singleton (used by lifespan teardown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
