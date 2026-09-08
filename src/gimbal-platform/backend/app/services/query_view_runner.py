"""query_view_runner —— 组合期取数解释器(2026-09-07 spec §4/§5/§6)。

fail-soft:所有失败上抛 QueryViewError(code, message, status),路由翻译降级;
绝不自动重登录(§6.2);不重试(§4.2);错误永不写缓存(§5.1)。
锁序(§5.2):view 锁外层 → 凭证闸内层;永不同时持两把 view 锁。

凭证 duck-type 契约(四个面,对齐 app/auth/schema.py 真身 AuthSession):
auth_header / apply_token(tok, ttl) / clear_token() / .url —— 真身的
auth_header 是 @property(无 token 返 None,控制字符抛 ValueError),而契约
形态是无参方法;runner 内 _auth_header_value 归一两种形态与异常。
"""
from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from app.auth import AuthError, AuthSession, get_authenticator
from app.services import jsonpath as jsonpath_mod  # 镜像拷贝,同 plate 先例
from app.services.plate_client import get_client
from app.services.query_view_cache import TtlLruCache

MAX_ROWS = 200
INDEX_TTL = 60.0
INDEX_BREAKER_THRESHOLD = 3
INDEX_BREAKER_WINDOW = 30.0
VIEW_BREAKER_THRESHOLD = 3
VIEW_BREAKER_WINDOW = 30.0

_MISSING = object()


# 测试 seam(§6.2 凭证行为依赖它;真身 = get_authenticator(url).authenticate):
# 同步函数,runner 经 asyncio.to_thread 调用(登录是阻塞 HTTP)。
def _AUTHENTICATE(session: Any, why: str) -> None:  # noqa: N802(测试 seam 惯用名)
    get_authenticator(session.url).authenticate(session, why)


class QueryViewError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class RowsResult:
    view: str
    rows: list[dict]
    truncated: bool
    fetched_at: str
    cached: bool
    stale: bool


# ── 进程内状态(单 worker 语义;multi-worker 各自一份,§5.3 有界接受)──
_index_state: dict[str, Any] = {"at": -1.0, "rows": [], "fails": 0, "open_until": -1.0}
_cache = TtlLruCache(ttl=300.0, max_entries=64, stale_max_window=86400.0)
_view_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()
_view_breaker: dict[str, dict[str, float]] = {}
_cred_locks: dict[tuple[int, str], asyncio.Lock] = {}
_cred_sessions: dict[tuple[int, str], AuthSession] = {}
_cred_dead: set[tuple[int, str]] = set()   # 401 拉黑:同 key 后续直接降级(§6.2)


def reset_state_for_tests() -> None:
    _index_state.update({"at": -1.0, "rows": [], "fails": 0, "open_until": -1.0})
    _cache._data.clear()
    _view_breaker.clear()
    _cred_sessions.clear()
    _cred_dead.clear()


async def _view_lock(name: str) -> asyncio.Lock:
    async with _locks_guard:
        return _view_locks.setdefault(name, asyncio.Lock())


async def fetch_query_view_index() -> list[dict[str, Any]]:
    """plate /api/query-views 索引:TTL memo + 连续失败熔断(spec §3.4)。"""
    now = time.monotonic()
    if now - _index_state["at"] <= INDEX_TTL:
        return _index_state["rows"]
    if _index_state["fails"] >= INDEX_BREAKER_THRESHOLD and \
            now < _index_state["open_until"]:
        raise QueryViewError("plate_unavailable", "plate 索引熔断窗内")
    try:
        resp = await get_client().get("/api/query-views")
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        _index_state["fails"] += 1
        if _index_state["fails"] >= INDEX_BREAKER_THRESHOLD:
            _index_state["open_until"] = now + INDEX_BREAKER_WINDOW
        raise QueryViewError("plate_unavailable", f"plate 索引不可达: {e}") from e
    data = payload.get("data") if isinstance(payload, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    rows = items if isinstance(items, list) else []
    _index_state.update({"at": now, "rows": rows, "fails": 0})
    return rows


def extract_rows(payload: Any, items: str) -> list:
    """jsonpath(items) 提取;形状漂移与空结果分形(spec §4.2)。"""
    if items.endswith("[*]"):
        parent = items[:-3]
        node = jsonpath_mod.get(payload, parent, _MISSING)
        if node is _MISSING or not isinstance(node, list):
            raise QueryViewError(
                "shape_drift", f"行集提取失败(响应形状漂移?): {parent}")
        return node
    node = jsonpath_mod.get(payload, items, _MISSING)
    if node is _MISSING:
        raise QueryViewError("shape_drift", f"行集提取失败(响应形状漂移?): {items}")
    return node if isinstance(node, list) else [node]


def project_rows(rows: list, columns: list[str]) -> list[dict]:
    """投影到列集:仅保留行内存在的列键(缺列 = 键缺席,前端 '--' 语义)。"""
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append({c: row[c] for c in columns if c in row})
    return out


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _auth_header_value(session: Any) -> "str | None":
    """凭证 auth_header 兼容读取(真身 @property / 契约方法两形)。

    真 AuthSession.auth_header 无 token 返 None、控制字符抛 ValueError;
    duck-type 契约是方法。取属性后可调则调;任何异常归一为 None —— 与
    "无 token"同路(冷启登录 / 登录后仍无 token 则降级)。
    """
    try:
        value = session.auth_header
        if callable(value):
            value = value()
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def _bump_breaker(name: str) -> None:
    br = _view_breaker.get(name) or {"fails": 0, "open_until": 0.0}
    br["fails"] += 1
    if br["fails"] >= VIEW_BREAKER_THRESHOLD:
        br["open_until"] = time.monotonic() + VIEW_BREAKER_WINDOW
    _view_breaker[name] = br


async def _resolve_auth_header(
    view: dict, owner_id: int, query_alias: "str | None",
    load_credential: "Callable[[int, str], AuthSession | None] | None",
) -> "tuple[str | None, AuthSession | None, tuple[int, str] | None]":
    """凭证闸(L3):登录与查询同闸;§5.2 锁序 view 锁外层 → 此闸内层。

    返回 (Authorization 值|None, session|None, cred_key|None)。
    - auth == "none" → (None, None, None),不走凭证链路;
    - key 已在 _cred_dead → 直接 sut_auth_expired(401 拉黑,绝不重登,§6.2);
    - 冷启动(无 token)经 _AUTHENTICATE seam 登录一次;AuthError → 降级。
    """
    if view.get("auth") == "none":
        return None, None, None
    if query_alias is None:
        raise QueryViewError(
            "query_credential_required",
            f"{view.get('endpoint_id')} 需要查询凭证而 query_alias 缺席",
            status=422)
    cred_key = (owner_id, query_alias)
    if cred_key in _cred_dead:
        raise QueryViewError(
            "sut_auth_expired",
            f"查询凭证 {query_alias!r} 已 401 拉黑(不自动重登,§6.2)")
    if load_credential is None:
        raise QueryViewError(
            "query_credential_required", "查询凭证加载器未接线", status=422)
    lock = _cred_locks.setdefault(cred_key, asyncio.Lock())
    async with lock:
        if cred_key in _cred_dead:   # 等锁期间被并发 401 拉黑
            raise QueryViewError(
                "sut_auth_expired",
                f"查询凭证 {query_alias!r} 已 401 拉黑(不自动重登,§6.2)")
        session = _cred_sessions.get(cred_key)
        if session is None:
            session = load_credential(owner_id, query_alias)
            if session is None:
                raise QueryViewError(
                    "query_credential_required",
                    f"未找到查询凭证 {query_alias!r}(owner={owner_id})",
                    status=422)
            _cred_sessions[cred_key] = session
        header = _auth_header_value(session)
        if header is None:
            try:  # 冷启动:登录一次(§6.2);不重试(§4.2)
                await asyncio.to_thread(_AUTHENTICATE, session, "query")
            except AuthError as e:
                raise QueryViewError(
                    "sut_auth_expired",
                    f"查询凭证 {query_alias!r} 登录失败: {e}") from e
            header = _auth_header_value(session)
            if header is None:
                raise QueryViewError(
                    "sut_auth_expired",
                    f"查询凭证 {query_alias!r} 登录后仍无 token")
        return header, session, cred_key


async def _query_sut(
    view: dict, service_url: str, auth_header: "str | None",
    session: Any, cred_key: "tuple[int, str] | None",
) -> "tuple[list[dict], bool]":
    """请求组装 + SUT 查询 + 提取投影(spec §4)。

    httpx.request 必须是模块属性访问式调用(测试 monkeypatch 面)。
    401 → 清 token + 拉黑 key(§6.2 绝不自动重登录);错误上抛,永不写缓存。
    """
    method = view.get("method") or "GET"
    url = f"{service_url}{view.get('path', '')}"
    headers = {"Authorization": auth_header} if auth_header else None
    timeout = view.get("timeout_seconds") or 5.0
    if method == "GET":
        kw: dict[str, Any] = {"params": dict(view.get("params") or {})}
    else:
        kw = {"json": view.get("params") or {}}
    try:
        request_fn = httpx.request   # 属性访问式调用:测试 monkeypatch 面
        if inspect.iscoroutinefunction(request_fn):
            resp = await request_fn(method, url, headers=headers,
                                    timeout=timeout, **kw)
        else:  # 真身(同步阻塞 HTTP)进线程,不卡事件循环
            resp = await asyncio.to_thread(
                request_fn, method, url, headers=headers, timeout=timeout, **kw)
    except httpx.HTTPError as e:
        raise QueryViewError("sut_unreachable", f"SUT 不可达: {e}") from e
    if resp.status_code == 401:
        if session is not None and cred_key is not None:
            try:
                session.clear_token()
            except Exception:  # 拉黑才是硬动作;清理失败不遮蔽 401 降级
                pass
            _cred_dead.add(cred_key)
        raise QueryViewError(
            "sut_auth_expired", f"SUT 401:{view.get('endpoint_id')} 凭证已失效")
    if resp.status_code >= 400:
        raise QueryViewError(
            "sut_error", f"SUT {resp.status_code}:{resp.text[:200]}")
    rows = extract_rows(resp.json(), view.get("items", ""))
    truncated = len(rows) > MAX_ROWS
    return project_rows(rows[:MAX_ROWS], view.get("columns") or []), truncated


async def fetch_rows(
    name: str, *, refresh: bool, service_url: str, owner_id: int,
    query_alias: "str | None",
    load_credential: "Callable[[int, str], AuthSession | None] | None",
) -> RowsResult:
    """取一行集:L1 缓存 → 熔断 → 单飞锁 → 凭证闸 → SUT 查询 → 缓存回填。"""
    index = await fetch_query_view_index()
    view = next((v for v in index if v.get("name") == name), None)
    if view is None:
        raise QueryViewError("unknown_view", f"未知视图 {name!r}", status=404)
    # §4.2 纵深防御(构造期为主,此处兜底:防 plate 版本错位)
    if view.get("missing_required"):
        raise QueryViewError("missing_required_params",
                             f"必填键仍缺: {view['missing_required']}", status=422)
    if view.get("method") != "GET" and not view.get("query_safe"):
        raise QueryViewError("query_not_safe",
                             f"{view.get('endpoint_id')} 非 GET 未声明 query_safe",
                             status=422)
    if not service_url or not service_url.startswith(("http://", "https://")):
        raise QueryViewError("service_url_required",
                             "service_url 缺失(服务绑定未解析)", status=422)
    stale_entry, fresh = _cache.lookup(name)
    if fresh and not refresh:
        return RowsResult(name, stale_entry.rows, False, stale_entry.fetched_wall,
                          cached=True, stale=False)
    # 熔断窗内:有 stale 回退 stale,否则降级(§5.2);refresh 也不豁免
    br = _view_breaker.get(name)
    if br and br["fails"] >= VIEW_BREAKER_THRESHOLD and \
            time.monotonic() < br["open_until"]:
        if stale_entry is not None:
            return RowsResult(name, stale_entry.rows, False,
                              stale_entry.fetched_wall, cached=False, stale=True)
        raise QueryViewError("circuit_open", f"视图 {name} 熔断窗内")
    lock = await _view_lock(name)
    async with lock:                       # L2 同视图单飞
        if not refresh:                    # 双检:等锁期间别人已填
            e2, f2 = _cache.lookup(name)
            if f2:
                return RowsResult(name, e2.rows, False, e2.fetched_wall,
                                  cached=True, stale=False)
        try:
            header, session, cred_key = await _resolve_auth_header(
                view, owner_id, query_alias, load_credential)
            rows, truncated = await _query_sut(view, service_url, header,
                                               session, cred_key)
            wall = _now_iso()
            _cache.put(name, rows, wall)   # 投影后行入缓存(§5.3)
            _view_breaker.pop(name, None)  # 成功清零
            return RowsResult(name, rows, truncated, wall,
                              cached=False, stale=False)
        except QueryViewError as e:
            # 仅 SUT 域失败(502 类)计入熔断;422 配置错是确定性错误,
            # 不污健康信号(否则 3 次配置错会把 query_credential_required
            # 错误地翻译成 circuit_open)
            if e.status >= 500:
                _bump_breaker(name)
            if stale_entry is not None:    # stale-while-error(§5.1)
                return RowsResult(name, stale_entry.rows, False,
                                  stale_entry.fetched_wall,
                                  cached=False, stale=True)
            raise
