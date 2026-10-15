"""HTTP client for the gimbal-plate FastAPI service (V3 composer).

Plate exposes a single ``POST /api/scenario/action/convert`` action for
the platform's preview / run use-case.  This wrapper:

* Owns a process-wide ``httpx.AsyncClient`` (created lazily on first
  call) so we don't pay TCP/TLS setup per request.
* Translates Plate's ``{ok, dim, data, error}`` envelope into Platform's
  flat error model (HTTPException with ``{detail: {code, message,
  errors[]}}``).
* Surfaces two typed errors.  ``PlateUnavailableError`` → 502
  ``plate_unavailable`` everywhere; ``PlateRejectedError`` has **two**
  landing points (同名不同码), so its status depends on the route:
  422 ``plate_rejected`` in the preview route (``routers/scenarios.py``
  — the 4xx is a verdict on the *client's draft*, not a gateway
  failure) vs 502 ``plate_rejected`` in the ``/full`` proxy
  (``routers/endpoint_catalog.py`` — there the upstream call itself was
  rejected, and the message carries plate's real status code).
  见 docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.7(preview/convert)
  与 §10.4(``/full`` 代理)。
* Owns a process-wide cache for the ``GET /api/endpoint/{id}/full``
  contract fetch (:func:`get_endpoint_full`) — TTL/LRU/stale-while-error
  都在这里,见「/full 契约取数(进程级缓存)」一节(该节在 ``# ─── helpers
  ───`` 分隔线**之前**,不在文件末尾)。**不是**全仓唯一一条 /full 取数:
  别的 /full 路径不共享这条缓存,边界见 :func:`get_endpoint_full` 的末段。

Run 执行链(V3.2):dispatcher convert 成功后把注入完成的用例落盘,
交 ``gimbal_launcher.launch`` 子进程(``gimbal run launch``)执行。
"""
from __future__ import annotations

import asyncio
import copy
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

    **Two landing points — same code, different status**(同名不同码):

    * preview/convert(``routers/scenarios.py``)→ HTTP **422**
      ``plate_rejected`` —— 上游 4xx 是对**客户端草稿**的裁决,不是网关故障,
      故按「输入被拒」报 422 而非 502(502 会让运维去追一个并不存在的 Plate
      故障);上游 ``errors[]`` 原样回传,前端据此渲染字段级提示;
    * ``/full`` 代理(``routers/endpoint_catalog.py``)→ HTTP **502**
      ``plate_rejected`` —— 那里是**代理的上游调用失败**,``message`` 里带
      plate 的真实状态码。

    取舍依据见 docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.7(preview/convert)
    与 §10.4(``/full`` 代理)。
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
# fill_plate_defaults 已删除（M2 步骤 4 / Q18）：
# 新 M2 Meta 只 name 必填（M6），平台无需补默认值——
# 存储的定义即纯 M2 实例，保存时由 scenario_store 保证不写入平台元数据。



def _now_iso() -> str:
    return _utcnow().isoformat() + "Z"


# ─── public surface ───────────────────────────────────────────────

def _strip_ext_anchors(scenario_dict: dict[str, Any]) -> dict[str, Any]:
    """steps[*].endpoint 的 ``ext:`` 前缀锚点剥离(浅拷贝,不改入参)。

    仅剥锚点键;method/path 等场景自有字段原样(external 步骤的调用
    信息本就内联在步骤里)。非 dict steps / 无锚点场景原样返回。
    """
    import copy as _copy
    definition = scenario_dict.get("definition")
    if not isinstance(definition, dict):
        return scenario_dict
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return scenario_dict
    if not any(isinstance(s, dict)
               and str(s.get("endpoint") or "").startswith("ext:")
               for s in steps):
        return scenario_dict
    out = _copy.deepcopy(scenario_dict)
    for s in (out["definition"].get("steps") or []):
        if isinstance(s, dict) and str(
                s.get("endpoint") or "").startswith("ext:"):
            s.pop("endpoint", None)
    return out

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

    # 外部接口登记批 X2:ext:<alias>.<name> 锚点是平台视图字段(外部
    # 接口登记目录的引用),plate 侧零感知 —— 发送前统一剥离,与
    # 「无锚点原样通过 convert」同款出口(设计 v1.0 §3)。
    scenario_dict = _strip_ext_anchors(scenario_dict)
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

    边界:``adaptation_service._plate_full_endpoint`` 与
    ``routers/endpoint_catalog.py`` 的 ``field-states/validate`` 各有自己的 /full
    取数,**不共享**本缓存;经本函数取数的是 ``endpoint_declarations`` 的两个门面
    与 ``routers/endpoint_catalog.py`` 的 ``/full`` 代理 —— 后者因此与 dispatch
    判定读**同一条缓存条目**。
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
    # 当前**不可达**(防御性保留,与 ``convert`` 里 _raise_rejected 之后那条同款):
    # _refresh_full 要么返回 dict、要么抛 _FullFetchError,失败已由上面两个 except
    # 出口返回。判据不写成 ``or``:``{}`` 是合法 item(§5),真值合并会把空契约错报
    # 成取数失败。
    if refreshed is None:
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


# ─── RS3（Release v4.4 §4）：版本模型读取侧方法 ────────────────────

# B-7/W24:按修订读取的不可变结果缓存 —— 修订一经签发内容不变,条目
# **不设 TTL、只按容量 FIFO 淘汰**(与 plate 侧修订快照缓存同机制,
# b4a8bfc0;淘汰只是丢缓存,下次访问重新装载)。只缓存成功结果
# (非 None);404/失败不进缓存,保持「按需取、可重试」语义。
_REVISION_CACHE_MAX = 64
_revision_cache: dict[tuple[str, str, str], Any] = {}


def _revision_cache_get(key: tuple[str, str, str]) -> Any | None:
    """命中返回深拷贝(缓存是进程级共享状态,调用方改自己那份不污染)。"""
    if key in _revision_cache:
        # 命中即重插 → LRU 语义(淘汰最久未用);dict 保插入序
        value = _revision_cache.pop(key)
        _revision_cache[key] = value
        return copy.deepcopy(value)
    return None


def _revision_cache_put(key: tuple[str, str, str], value: Any) -> None:
    if value is None:
        return
    if len(_revision_cache) >= _REVISION_CACHE_MAX:
        for oldest in list(_revision_cache):
            _revision_cache.pop(oldest)
            break
    _revision_cache[key] = copy.deepcopy(value)


def _reset_revision_cache_for_test() -> None:
    _revision_cache.clear()


async def list_lines(system_id: str, *, timeout: float = 15.0) -> list[dict]:
    """GET /api/system/{id}/lines（版本线列表，2.4）。

    line_scheme 以线内最新修订为准；环境组版本线下拉用。
    """
    client = get_client()
    try:
        resp = await client.get(f"/api/system/{system_id}/lines",
                                timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "not ok"))
    return envelope.get("data", {}).get("items", [])


async def list_line_revisions(
    system_id: str, line: str, *, timeout: float = 15.0,
) -> list[dict]:
    """GET /api/system/{id}/lines/{line}/revisions(修订列表,2.4)。

    场景导入 v2.3 §3.1:声明修订本机缺失时组装 availableRevisions
    (错误信息给可选集,不把导入人卡死在 422)。plate 端点已有,平台侧
    此前只有线级 list_lines(count+latest,不含完整修订集)。
    """
    client = get_client()
    try:
        resp = await client.get(
            f"/api/system/{system_id}/lines/{line}/revisions",
            timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "not ok"))
    return envelope.get("data", {}).get("items", [])


async def resolve(
    meta_plate: dict[str, str],
    endpoints_used: dict[str, list[str]],
    *, timeout: float = 15.0,
) -> dict[str, dict]:
    """POST /api/system/action/resolve（生效修订解析，4.4）。

    入参：``meta_plate = {系统: "<line>#<n>" | "working"}``，
    ``endpoints_used = {系统: [endpoint_id, ...]}``。
    返回：``{系统: {effective, available, changed_endpoints}}``。

    计算只依赖 manifest 的 shape_hash（I-5：plate 不知道谁在用哪个版本），
    结果对同一组修订不变（可缓存）。
    """
    client = get_client()
    body = {"meta_plate": meta_plate, "endpoints": endpoints_used}
    try:
        resp = await client.post("/api/system/action/resolve",
                                 json=body, timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "not ok"))
    return envelope.get("data", {}).get("item", {})


async def list_system_endpoints(
    system_id: str, *, timeout: float = 15.0,
) -> list[dict]:
    """GET /api/systems/{system}/endpoint → data.items(working 树轻视图)。

    导入重锚定(2026-10-15 #323)的反查候选源:条目含 id/service/
    method/path。5xx/网络错误上抛 PlateUnavailableError,4xx 上抛
    PlateRejectedError(调用方决定降级口径)。
    """
    client = get_client()
    try:
        resp = await client.get(f"/api/systems/{system_id}/endpoint",
                                timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "not ok"))
    items = envelope.get("data", {}).get("items", [])
    return items if isinstance(items, list) else []


async def get_endpoint_full_at(
    endpoint_id: str, ref: str, *, timeout: float = 15.0,
) -> "dict[str, Any] | None":
    """``GET /api/endpoint/{id}/full?ref=`` —— 按修订取契约（4.1 修订快照）。

    与 working 缓存版 :func:`get_endpoint_full` 分离:修订内容不可变,
    **不进 TTL 缓存、进修订缓存**(B-7/W24:容量 FIFO 淘汰,同 plate 侧
    修订快照缓存机制;RS4a 保存检查的目标修订试算消费方)。404 → None
    (不进缓存)。
    """
    key = ("full", endpoint_id, ref)
    hit = _revision_cache_get(key)
    if hit is not None:
        return hit
    client = get_client()
    try:
        resp = await client.get(
            f"/api/endpoint/{endpoint_id}/full",
            params={"ref": ref}, timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code == 404:
        return None
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "not ok"))
    item = envelope.get("data", {}).get("item")
    _revision_cache_put(key, item)
    return item


async def get_projection(
    endpoint_id: str, ref: str, *, timeout: float = 15.0
) -> dict[str, Any] | None:
    """GET /api/endpoint/{id}/projection?ref=（投影查询，4.8）。

    编排页展示 method/path 等只读信息时调用；结果不可变 → 修订缓存
    (B-7/W24,容量 FIFO;404 → None 不进缓存)。
    """
    key = ("proj", endpoint_id, ref)
    hit = _revision_cache_get(key)
    if hit is not None:
        return hit
    client = get_client()
    try:
        resp = await client.get(
            f"/api/endpoint/{endpoint_id}/projection",
            params={"ref": ref}, timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code == 404:
        return None
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    item = envelope.get("data", {}).get("item")
    _revision_cache_put(key, item)
    return item


async def revision_objects(
    system_id: str, ref: str, *, timeout: float = 15.0
) -> dict[str, str]:
    """GET /api/system/{id}/revisions/{line}/{n} → manifest.objects。

    返回 ``{对象 id: review 状态}``(端点对象的评审面;W7 入库标准
    「生效修订中用到的接口全部已评审」的判定数据源)。修订不可变 →
    修订缓存(B-7/W24 已随批:容量 FIFO)。``ref`` 必须是
    ``<line>#<n>`` 精确修订。
    """
    if "#" not in ref:
        raise PlateRejectedError(
            code="invalid_ref",
            message=f"revision_objects 需要精确修订 <line>#<n>,得到 {ref!r}")
    line, _, n = ref.partition("#")
    key = ("objs", system_id, ref)
    hit = _revision_cache_get(key)
    if hit is not None:
        return hit
    client = get_client()
    try:
        resp = await client.get(
            f"/api/system/{system_id}/revisions/{line}/{n}", timeout=timeout)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(f"plate_unavailable: {e}") from e
    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}")
    if resp.status_code >= 400:
        _raise_rejected(resp)
    envelope = resp.json()
    if not envelope.get("ok"):
        raise PlateRejectedError(
            code="invalid_action",
            message=envelope.get("error", {}).get("message", "not ok"))
    objects = envelope.get("data", {}).get("item", {}).get("objects", [])
    result = {o["id"]: (o.get("review") or "") for o in objects
              if isinstance(o, dict) and o.get("id")}
    _revision_cache_put(key, result)
    return result


async def validate_meta_plate_refs(meta_plate: dict[str, str]) -> None:
    """保存端 meta.plate 引用校验(C-1,2026-10-13;与 R19 导入同口径)。

    每个声明须是 ``<line>#<n>``(working 豁免):线存在且 ``1 <= n <=
    线内修订数``。此前保存不校验 —— "1.0"(只有线)/"1.0#9"(修订不
    存在)/"2.0#1"(线不存在)全部入库,执行期才炸且错误被误归为
    plate_unavailable。plate 不可达时**跳过**(保存是定义面动作,
    不因目录故障阻断;执行期门仍在)。

    Raises:
        ValueError: ``meta_plate_invalid_ref`` 带具体系统与原因。
    """
    for sysname, ref in (meta_plate or {}).items():
        if not ref or ref == "working":
            continue
        if "#" not in ref:
            raise ValueError(
                f"meta_plate_invalid_ref: {sysname}={ref!r} 缺修订号"
                "(须 <line>#<n> 或 working)")
        line, _, num = ref.rpartition("#")
        if not line or not num.isdigit():
            raise ValueError(
                f"meta_plate_invalid_ref: {sysname}={ref!r} 形状非法")
        items = await list_lines(sysname)
        info = next((x for x in items if x.get("line") == line), None)
        if info is None:
            raise ValueError(
                f"meta_plate_invalid_ref: {sysname} 声明的版本线 "
                f"{line!r} 不存在")
        total = int(info.get("revisions") or 0)
        if not 1 <= int(num) <= total:
            raise ValueError(
                f"meta_plate_invalid_ref: {sysname}={ref!r} 修订不存在"
                f"(线内共 {total} 个修订,latest={info.get('latest')})")
