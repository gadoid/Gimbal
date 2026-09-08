"""query_view_runner:组装/提取/投影/漂移空分形 + 缓存/单飞/凭证/熔断(spec §4/§5/§6)。"""
import asyncio

import httpx
import pytest

from app.services import jsonpath as jp
from app.services import query_view_runner as r


@pytest.fixture(autouse=True)
def _reset():
    r.reset_state_for_tests()
    yield
    r.reset_state_for_tests()


IDX = [{
    "name": "v1", "endpoint_id": "t.a", "system": "t", "service": "svc",
    "method": "GET", "path": "/api/a", "params": {"page": 1},
    "items": "$.data.list[*]", "label": "nm",
    "columns": ["nm", "id"], "query_safe": False, "missing_required": [],
    "auth": "none", "timeout_seconds": 5.0,
}, {
    "name": "v2", "endpoint_id": "t.b", "system": "t", "service": "svc",
    "method": "POST", "path": "/api/b", "params": {"k": "x"},
    "items": "$.rows[*]", "label": "code",
    "columns": ["code"], "query_safe": True, "missing_required": [],
    "auth": "bearer", "timeout_seconds": 5.0,
}]


@pytest.fixture
def index(monkeypatch):
    async def fake():
        return IDX
    monkeypatch.setattr(r, "fetch_query_view_index", fake)


class _FakeSession:
    """Duck-typed 查询凭证。契约:auth_header() 无 token 返回 None;
    apply_token/clear_token 管理态。执行者对齐 app/auth 真实 AuthSession
    API 时保持同形(runner 只依赖这四个面)。"""

    def __init__(self):
        self.token = None

    def apply_token(self, tok: str, ttl: int) -> None:
        self.token = tok

    def clear_token(self) -> None:
        self.token = None

    def auth_header(self) -> "str | None":
        return f"Bearer {self.token}" if self.token else None


class TestJsonpathMirror:
    """Step 0 镜像拷贝冒烟:get/get_all 的 $.data.list[*] 与过滤形态。"""

    def test_get_all_wildcard(self):
        payload = {"data": {"list": [{"id": 1}, {"id": 2}]}}
        assert jp.get_all(payload, "$.data.list[*]") == [{"id": 1}, {"id": 2}]

    def test_get_wildcard_is_first_match(self):
        payload = {"data": {"list": [{"id": 1}, {"id": 2}]}}
        assert jp.get(payload, "$.data.list[*]") == {"id": 1}   # 首匹配
        assert jp.get(payload, "$.data.list[-1].id") == 2       # 倒序下标

    def test_filter_form(self):
        payload = {"data": {"list": [{"s": 200}, {"s": 404}]}}
        assert jp.get_all(payload, "$.data.list[?(@.s==200)]") == [{"s": 200}]


class TestExtract:
    def test_empty_list_is_legal(self):
        assert r.extract_rows({"data": {"list": []}}, "$.data.list[*]") == []

    def test_shape_drift_missing_parent(self):
        with pytest.raises(r.QueryViewError, match="漂移"):
            r.extract_rows({"data": {}}, "$.data.list[*]")

    def test_shape_drift_not_a_list(self):
        with pytest.raises(r.QueryViewError):
            r.extract_rows({"data": {"list": {"a": 1}}}, "$.data.list[*]")


class TestProject:
    def test_keeps_only_present_columns(self):
        rows = [{"nm": "a", "id": 1, "junk": "x"}, {"nm": "b"}]
        assert r.project_rows(rows, ["nm", "id"]) == [
            {"nm": "a", "id": 1}, {"nm": "b"}]      # 缺列 = 键缺席


class TestFetchRows:
    async def test_get_querystring_and_projection(self, index, monkeypatch):
        seen = {}
        def fake_request(method, url, **kw):
            seen.update(kw, method=method, url=url)
            return httpx.Response(200, json={"data": {"list": [
                {"nm": "a", "id": 1, "junk": 0}, {"nm": "b", "id": 2}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert seen["method"] == "GET" and seen["params"] == {"page": 1}
        assert res.rows == [{"nm": "a", "id": 1}, {"nm": "b", "id": 2}]
        assert not res.cached and not res.stale and not res.truncated

    async def test_post_body_and_auth_header(self, index, monkeypatch):
        seen = {}
        class _S:  # 假 AuthSession
            def auth_header(self): return "Bearer tok"
        def fake_request(method, url, **kw):
            seen.update(kw, method=method, url=url)
            return httpx.Response(200, json={"rows": [{"code": "c1"}]})
        monkeypatch.setattr(httpx, "request", fake_request)
        res = await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias="qa",
                                 load_credential=lambda o, a: _S())
        assert seen["method"] == "POST" and seen["json"] == {"k": "x"}
        assert seen["headers"]["Authorization"] == "Bearer tok"
        assert res.rows == [{"code": "c1"}]

    async def test_async_load_credential_awaited(self, index, monkeypatch):
        """路由 _loader 是 async 闭包(异步 DB 会话)—— 凭证闸须 await
        coroutine-function 装载器(与 httpx.request seam 同款双形态);
        同步装载器路径由其余各例锁定。"""
        def fake_auth(session, why):
            session.apply_token("tok-1", 3600)
        monkeypatch.setattr(r, "_AUTHENTICATE", fake_auth)
        monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
            200, json={"rows": [{"code": "c1"}]}))

        async def load(o, a):
            assert (o, a) == (1, "qa")
            return _FakeSession()

        res = await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias="qa", load_credential=load)
        assert res.rows == [{"code": "c1"}]

    async def test_unknown_view_404(self, index):
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("nope", refresh=False, service_url="http://s",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.status == 404

    async def test_deep_defense_422(self, monkeypatch):
        bad = [dict(IDX[1], query_safe=False)]
        async def fake(): return bad
        monkeypatch.setattr(r, "fetch_query_view_index", fake)
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v2", refresh=False, service_url="http://s",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.status == 422 and e.value.code == "query_not_safe"

    async def test_max_rows_truncate(self, index, monkeypatch):
        monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
            200, json={"data": {"list": [{"nm": i, "id": i} for i in range(250)]}}))
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert len(res.rows) == 200 and res.truncated
        # §5.1 截断标记随行集入缓存:TTL 内二开(命中)仍透出 truncated
        cached = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                    owner_id=1, query_alias=None, load_credential=None)
        assert cached.cached and cached.truncated and len(cached.rows) == 200

    async def test_l1_cache_and_refresh_bypass(self, index, monkeypatch):
        calls = {"n": 0}
        def fake_request(method, url, **kw):
            calls["n"] += 1
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        a = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        b = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert calls["n"] == 1 and b.cached and b.rows == a.rows
        c = await r.fetch_rows("v1", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert calls["n"] == 2 and not c.cached

    async def test_error_never_cached(self, index, monkeypatch):
        state = {"fail": True}
        def fake_request(method, url, **kw):
            if state["fail"]:
                raise httpx.ConnectError("down")
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        with pytest.raises(r.QueryViewError):
            await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        state["fail"] = False
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert res.rows == [{"nm": "x", "id": 1}]     # 失败没被缓存,重取成功

    async def test_non_json_200_shape_drift_and_not_cached(self, index, monkeypatch):
        state = {"bad": True}
        def fake_request(method, url, **kw):
            if state["bad"]:
                return httpx.Response(200, text="<html>gateway</html>")
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.code == "shape_drift"    # 2xx 非 JSON 体 ≠ 未处理异常
        state["bad"] = False
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert res.rows == [{"nm": "x", "id": 1}]   # 错误没被缓存,好响应即恢复

    async def test_stale_while_error(self, index, monkeypatch):
        def ok(m, u, **kw):
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", ok)
        first = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                   owner_id=1, query_alias=None, load_credential=None)
        r._cache._data["v1"].fetched_mono -= 400.0     # 人工老化过 TTL(仍在 stale 窗)
        async def boom(m, u, **kw):
            raise httpx.ConnectError("down")
        monkeypatch.setattr(httpx, "request", boom)
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert res.stale and res.rows == first.rows
        assert res.fetched_at == first.fetched_at      # fetched_at 照实显示

    async def test_single_flight(self, index, monkeypatch):
        calls = {"n": 0}
        # to_thread 包装的是同步 httpx.request —— 单飞测试用同步慢函数即可
        def slow_sync(method, url, **kw):
            import time as _t; _t.sleep(0.05); calls["n"] += 1
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", slow_sync)
        rs = await asyncio.gather(*[
            r.fetch_rows("v1", refresh=False, service_url="http://sut",
                         owner_id=1, query_alias=None, load_credential=None)
            for _ in range(4)])
        assert calls["n"] == 1                           # 同视图并发单飞
        assert all(x.rows == rs[0].rows for x in rs)

    async def test_circuit_breaker(self, index, monkeypatch):
        def boom(m, u, **kw):
            raise httpx.ConnectError("down")
        monkeypatch.setattr(httpx, "request", boom)
        for _ in range(3):
            with pytest.raises(r.QueryViewError):
                await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                   owner_id=1, query_alias=None, load_credential=None)
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v1", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.code == "circuit_open"            # 熔断窗内 refresh 也拒

    async def test_sut_401_degrade_no_relogin(self, index, monkeypatch):
        logins = {"n": 0}
        def fake_auth(session, why):
            logins["n"] += 1
            session.apply_token("tok-1", 3600)
        def fake_request(method, url, **kw):
            if kw.get("headers", {}).get("Authorization") == "Bearer tok-1":
                return httpx.Response(401, json={"msg": "expired"})
            raise AssertionError("未经凭证直接请求 auth=bearer 视图")
        monkeypatch.setattr(httpx, "request", fake_request)
        monkeypatch.setattr(r, "_AUTHENTICATE", fake_auth)
        sess = _FakeSession()
        load = lambda o, a: sess
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias="qa", load_credential=load)
        assert e.value.code == "sut_auth_expired"
        with pytest.raises(r.QueryViewError) as e2:
            await r.fetch_rows("v2", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias="qa", load_credential=load)
        assert e2.value.code == "sut_auth_expired"   # 拉黑后直接降级,不打 SUT
        assert logins["n"] == 1      # 冷启一次;401 后绝不自动重登录(§6.2)
