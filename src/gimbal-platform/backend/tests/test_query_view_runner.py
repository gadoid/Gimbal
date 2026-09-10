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
    """Duck-typed 查询凭证。契约面:.token(裸值注入,§13.8)/
    apply_token/clear_token 管理态 / .url。执行者对齐 app/auth 真实
    AuthSession API 时保持同形(runner 只依赖这四个面)。"""

    def __init__(self):
        self.token = None
        self.url = "https://sut-login"

    def apply_token(self, tok: str, ttl: int) -> None:
        self.token = tok

    def clear_token(self) -> None:
        self.token = None


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

    async def test_post_body_and_bare_token(self, index, monkeypatch):
        seen = {}
        class _S:  # 假 AuthSession(契约面:.token 裸值)
            token = "tok"
        def fake_request(method, url, **kw):
            seen.update(kw, method=method, url=url)
            return httpx.Response(200, json={"rows": [{"code": "c1"}]})
        monkeypatch.setattr(httpx, "request", fake_request)
        res = await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias="qa",
                                 load_credential=lambda o, a: _S())
        assert seen["method"] == "POST" and seen["json"] == {"k": "x"}
        # 裸 token 注入,与认证部分的控制一致(执行侧 ${auth.<tag>.token}
        # 模板同源,§13.8 实证);token_type 不参与拼头
        assert seen["headers"]["Authorization"] == "tok"
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
            if kw.get("headers", {}).get("Authorization") == "tok-1":
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

    @pytest.mark.parametrize("bc", [401, 407])
    async def test_business_auth_codes_degrade_blacklists(
            self, index, monkeypatch, bc):
        """§13.8 首连测实证:fin SUT 凭证失效在业务码层应答(HTTP 200 +
        code=401/407 + 空 data;407 msg="登录已过期")—— HTTP 401 检测
        不可见;死/坏凭证必须降级拉黑,不得静默当"合法空行集"缓存/供数。"""
        sess = _FakeSession()
        sess.apply_token("tok-1", 3600)
        calls = {"n": 0}

        def fake_request(method, url, **kw):
            calls["n"] += 1
            return httpx.Response(200, json={"code": bc, "msg": "未登录",
                                             "rows": []})
        monkeypatch.setattr(httpx, "request", fake_request)
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias="qa",
                               load_credential=lambda o, a: sess)
        assert e.value.code == "sut_auth_expired"
        assert sess.token is None                    # 清 token(拉黑硬动作)
        with pytest.raises(r.QueryViewError) as e2:  # 拉黑后不再打 SUT
            await r.fetch_rows("v2", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias="qa",
                               load_credential=lambda o, a: sess)
        assert e2.value.code == "sut_auth_expired" and calls["n"] == 1

    async def test_business_code_non_200_is_sut_error(self, index, monkeypatch):
        """其余非成功业务码 → sut_error 诚实透出;错误不写缓存(重查仍打 SUT)。"""
        calls = {"n": 0}

        def fake_request(method, url, **kw):
            calls["n"] += 1
            return httpx.Response(200, json={"code": 500, "msg": "服务异常",
                                             "data": {"list": []}})
        monkeypatch.setattr(httpx, "request", fake_request)
        for _ in range(2):
            with pytest.raises(r.QueryViewError) as e:
                await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                   owner_id=1, query_alias=None, load_credential=None)
            assert e.value.code == "sut_error" and "500" in e.value.message
        assert calls["n"] == 2                       # 失败没被缓存

    async def test_business_code_envelope_success_passes(self, index, monkeypatch):
        """携 code=200 成功信封的正常响应不受影响(fin SUT 全域此形状)。"""
        monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
            200, json={"code": 200, "msg": "成功",
                       "data": {"list": [{"nm": "a", "id": 1}]}}))
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert res.rows == [{"nm": "a", "id": 1}]

    async def test_drop_credential_revives_blacklist(self, index, monkeypatch):
        """§7.5 复活钩子:认证页重存凭证(patch/delete 触发)→ 清拉黑与缓存
        会话 → 下次查询重装凭证冷启登录,降级态有真实恢复路径。"""
        sess = _FakeSession()
        sess.apply_token("tok-1", 3600)
        seq = [{"code": 401, "msg": "x", "rows": []},
               {"code": 200, "rows": [{"code": "c1"}]}]
        monkeypatch.setattr(httpx, "request",
                            lambda m, u, **kw: httpx.Response(200, json=seq.pop(0)))
        with pytest.raises(r.QueryViewError):
            await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias="qa",
                               load_credential=lambda o, a: sess)
        sess.apply_token("tok-2", 3600)              # 重存后冷启登录得新 token
        r.drop_credential(1, "qa")
        res = await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias="qa",
                                 load_credential=lambda o, a: sess)
        assert res.rows == [{"code": "c1"}]


# ── §13.3 点击期参数面 ────────────────────────────────────────────

_POLICY_VIEW = {
    "name": "customer_policy", "endpoint_id": "fin.customer.policy",
    "method": "POST", "path": "/api/Customer/Policy/getCustomerPolicy",
    "params": {"status": "2"}, "query_params": ["customer_id"],
    "items": "$.data[*]", "label": "policy_name",
    "columns": ["policy_name", "policy_id"], "query_safe": True,
    "missing_required": ["customer_id"], "auth": "none", "timeout_seconds": 5.0,
}


def _patch_view(monkeypatch, view):
    async def fake_index():
        return [view]
    monkeypatch.setattr(r, "fetch_query_view_index", fake_index)


@pytest.mark.asyncio
async def test_click_params_overlay_static_and_exemption(monkeypatch):
    """点击期 ▸ 索引静态 params(已含 view.params▸default▸example);缺键被点击期豁免。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    sent = {}

    def fake_request(method, url, **kw):
        sent.update(kw)
        return httpx.Response(200, json={"data": [{"policy_name": "P1", "policy_id": "32"}]})

    monkeypatch.setattr(r.httpx, "request", fake_request)
    res = await r.fetch_rows(
        "customer_policy", refresh=True, service_url="http://sut",
        owner_id=1, query_alias=None, load_credential=None,
        click_params={"customer_id": "1"})
    assert sent["json"] == {"status": "2", "customer_id": "1"}   # 合并链:点击期最高
    assert res.rows == [{"policy_name": "P1", "policy_id": "32"}]
    assert res.cached is False


@pytest.mark.asyncio
async def test_click_param_absent_still_422(monkeypatch):
    """query_param 未供给 → missing_required 不豁免 → 422。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    with pytest.raises(r.QueryViewError) as ei:
        await r.fetch_rows(
            "customer_policy", refresh=True, service_url="http://sut",
            owner_id=1, query_alias=None, load_credential=None)
    assert ei.value.status == 422


@pytest.mark.asyncio
async def test_param_face_view_never_enters_l1(monkeypatch):
    """带参数面视图不进 L1:同参数重查再发上游(无缓存命中)。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    calls = []

    def fake_request(method, url, **kw):
        calls.append(kw.get("json"))
        return httpx.Response(200, json={"data": [{"policy_name": "P", "policy_id": "1"}]})

    monkeypatch.setattr(r.httpx, "request", fake_request)
    for _ in range(2):
        res = await r.fetch_rows(
            "customer_policy", refresh=False, service_url="http://sut",
            owner_id=1, query_alias=None, load_credential=None,
            click_params={"customer_id": "1"})
        assert res.cached is False
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_param_face_single_flight_keyed_by_params(monkeypatch):
    """单飞键 = (view, 点击期 params):并发同参 1 发,异参各 1 发 → 共 2 发。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    calls = []

    async def slow_request(method, url, **kw):
        calls.append(kw.get("json"))
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"data": [{"policy_name": "P", "policy_id": "1"}]})

    monkeypatch.setattr(r.httpx, "request", slow_request)
    await asyncio.gather(
        r.fetch_rows("customer_policy", refresh=False,
                     service_url="http://sut", owner_id=1,
                     query_alias=None, load_credential=None,
                     click_params={"customer_id": "1"}),
        r.fetch_rows("customer_policy", refresh=False,
                     service_url="http://sut", owner_id=1,
                     query_alias=None, load_credential=None,
                     click_params={"customer_id": "1"}),
        r.fetch_rows("customer_policy", refresh=False,
                     service_url="http://sut", owner_id=1,
                     query_alias=None, load_credential=None,
                     click_params={"customer_id": "2"}),
    )
    assert len(calls) == 2


def test_project_rows_dotted_columns():
    """§13.4 点路径列:逐段下钻;缺列(含中途非 dict)= 键缺席。"""
    rows = [{"handover_form": {"client_expand_id": "E1"},
             "customer_service": {"user_name": "庞燕"},
             "finance": [{"chinese_header": "X"}]}]
    out = r.project_rows(
        rows, ["customer_service.user_name", "handover_form.client_expand_id",
               "finance.chinese_header", "absent.col"])
    # finance 是数组 → finance.chinese_header 不可导航 = 缺席(不脏写 '--')
    assert out == [{"customer_service.user_name": "庞燕",
                    "handover_form.client_expand_id": "E1"}]


def test_extract_rows_single_object_wraps_one_row():
    """§13.4 单对象型:$.data 命中对象 → 包一行(extract_rows 既有分支的显式钉)。"""
    assert r.extract_rows({"data": {"a": 1}}, "$.data") == [{"a": 1}]


_NO_FACE_VIEW = {
    "name": "cost_list", "endpoint_id": "fin.cost.list",
    "method": "POST", "path": "/api/cost/list",
    "params": {"page": 1}, "query_params": [],
    "items": "$.data[*]", "label": "cost_name",
    "columns": ["cost_name"], "query_safe": True,
    "missing_required": [], "auth": "none", "timeout_seconds": 5.0,
}


@pytest.mark.asyncio
async def test_carried_params_on_non_param_face_view_bypass_l1(monkeypatch):
    """§13.7 手工携参调用非参数面视图:合并发送,但按携参口径旁路 L1 —
    携参结果不得回填裸名键,否则无参调用吃到污染行集(TTL 300s)。"""
    _patch_view(monkeypatch, dict(_NO_FACE_VIEW))
    calls = []

    def fake_request(method, url, **kw):
        calls.append(kw.get("json"))
        return httpx.Response(200, json={"data": [{"cost_name": "c"}]})

    monkeypatch.setattr(r.httpx, "request", fake_request)
    res = await r.fetch_rows(
        "cost_list", refresh=False, service_url="http://sut",
        owner_id=1, query_alias=None, load_credential=None,
        click_params={"x": "1"})
    assert calls[0] == {"page": 1, "x": "1"}    # 合并链仍生效(携参语义照发)
    assert res.cached is False
    res2 = await r.fetch_rows(
        "cost_list", refresh=False, service_url="http://sut",
        owner_id=1, query_alias=None, load_credential=None)
    assert len(calls) == 2                       # 无参调用未吃到携参结果 = L1 未被污染
    assert res2.cached is False
