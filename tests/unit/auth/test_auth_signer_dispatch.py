"""外部接口登记批 X4:G1 认证施加分派框架(设计 v1.0 §6 实施修正)。

钉住三态:
1. 默认 auth_signer=md5sign(或会话缺该属性)→ 遗留 md5 签名头逐字节
   不变(与退役插件 auth_headers 契约一致,存量场景零回归);
2. standard.bearer → Authorization: Bearer <token>;
3. standard.basic → Authorization: Basic base64(u:p)(token 空也生效
   —— basic 凭证本就未必登录换 token)。

形状陷阱的边界(设计 §6 实施修正):token_type 默认即 "Bearer",分派
**不看** token_type —— 显式 auth_signer 是唯一开关;写入面挂集成 P2
的 call.auth 透传(M2 代际升位)。
"""
from __future__ import annotations

import base64
import hashlib
import time as _t


class _Session:
    def __init__(self, **kw):
        self.token = "abc123"
        self.username = "u0"
        self.password = "p0"
        for k, v in kw.items():
            setattr(self, k, v)


class _Auth:
    def __init__(self, session):
        self._s = session

    def get(self, tag):
        return self._s


def _login(session):
    from gimbal.protocols.builtin.http import HttpProtocolExecutor
    ex = HttpProtocolExecutor()
    ex.bind(auth_registry=_Auth(session))
    return ex.login("user1")


def test_default_md5sign_unchanged():
    """默认(无 auth_signer 属性的存量会话)→ md5 签名头逐字节一致。"""
    signed = _login(_Session())          # 无 auth_signer 属性(旧会话形状)
    ts = int(signed["timestamp"])
    assert signed["token"] == hashlib.md5(f"abc123{ts}".encode()).hexdigest()
    assert abs(int(_t.time()) - ts) <= 1
    assert "Authorization" not in signed

    signed2 = _login(_Session(auth_signer="md5sign"))
    assert "timestamp" in signed2 and "token" in signed2


def test_explicit_md5sign_same_shape():
    signed = _login(_Session(auth_signer="md5sign"))
    signed2 = _login(_Session())
    assert set(signed) == set(signed2) == {"token", "timestamp"}


def test_standard_bearer():
    signed = _login(_Session(auth_signer="standard.bearer"))
    assert signed == {"Authorization": "Bearer abc123"}


def test_standard_basic():
    signed = _login(_Session(auth_signer="standard.basic"))
    expect = base64.b64encode(b"u0:p0").decode("ascii")
    assert signed == {"Authorization": f"Basic {expect}"}


def test_standard_basic_without_token():
    """basic 凭证未登录(token 空)也施加 —— Basic 头不需要 token。"""
    signed = _login(_Session(auth_signer="standard.basic", token=None))
    assert signed["Authorization"].startswith("Basic ")


def test_bearer_without_token_skips():
    signed = _login(_Session(auth_signer="standard.bearer", token=None))
    assert signed == {}


def test_token_type_default_bearer_does_not_hijack():
    """形状陷阱钉子:token_type='Bearer'(默认)不带显式 signer → 仍 md5。"""
    signed = _login(_Session(token_type="Bearer"))
    assert "Authorization" not in signed and "timestamp" in signed


def test_session_model_has_auth_signer_default():
    from gimbal.auth.session import AuthSession
    s = AuthSession(url="http://x", username="u", password="p")
    assert s.auth_signer == "md5sign"


# ── Y1:call.auth 声明驱动(优先级:声明 > 会话 auth_signer > 遗留 md5)──

class _Call:
    def __init__(self, user="u1", auth="", auth_signer=None):
        self.user = user
        self.auth = auth
        self.auth_signer = auth_signer


class _Pctx:
    def __init__(self, call):
        self.call = call


def _inject(session, call) -> dict:
    from gimbal.protocols.builtin.http import HttpProtocolExecutor
    ex = HttpProtocolExecutor()
    ex.bind(auth_registry=_Auth(session))
    headers: dict = {}
    ex._inject_auth_headers(headers, _Pctx(call))
    return headers


def test_call_auth_bearer_overrides_session():
    """声明 bearer > 会话 auth_signer=md5sign → Bearer 头。"""
    h = _inject(_Session(auth_signer="md5sign"),
               _Call(auth="bearer"))
    assert h == {"Authorization": "Bearer abc123"}


def test_call_auth_custom_default_md5():
    """custom 无 auth_signer → 遗留 md5(fin 修正后的行为)。"""
    h = _inject(_Session(), _Call(auth="custom"))
    assert "timestamp" in h and "Authorization" not in h


def test_call_auth_custom_named_signer():
    h = _inject(_Session(), _Call(auth="custom", auth_signer="standard.basic"))
    assert h["Authorization"].startswith("Basic ")


def test_call_auth_none_keeps_legacy_md5():
    """auth 缺省(none)且 call.user 在 → 遗留 md5(存量场景零变化)。"""
    h = _inject(_Session(), _Call())
    assert "timestamp" in h


def test_call_auth_none_no_user_no_injection():
    assert _inject(_Session(), _Call(user="")) == {}


def test_projection_passes_auth_fields():
    """_call_projection:binding.auth/auth_signer → call 透传(none 不写键)。"""
    from gimbal_plate.release.release import _call_projection

    class _B:
        protocol = "http"
        method = "GET"
        path = "/x"
        headers = {}
        timeout_seconds = 30.0
        auth = "bearer"

    class _Ep:
        service = "svc"
        binding = _B()

    out = _call_projection(_Ep())
    assert out["auth"] == "bearer" and "auth_signer" not in out

    _B.auth = "custom"
    _B.auth_signer = "md5sign"
    out = _call_projection(_Ep())
    assert out["auth"] == "custom" and out["auth_signer"] == "md5sign"

    _B.auth = "none"
    out = _call_projection(_Ep())
    assert "auth" not in out        # none 不写键,存量形状不变


def test_m2_gen2_migrate_noop():
    """gen1→2 迁移为 no-op(Call 加可选字段,存量语料行为等价)。"""
    from gimbal_plate.schema import M2_GENERATION
    from gimbal_plate.schema.migrate import _migrate_map, migrate_definition
    assert M2_GENERATION == 2
    assert 1 in _migrate_map
    d = {"kind": "scenario", "meta": {"name": "n"}, "steps": []}
    out = migrate_definition(d, from_generation=1)
    assert out == d


# ── P0-1(2026-11-06):真实 Call 模型(Auth 为 str 枚举)也必须命中声明分派 ──
# 上面的 _Call 用纯字符串,掩盖了 str(Auth.bearer) == "Auth.bearer" 的问题:
# 运行期 step.call 是 gimbal.schema.Call,auth 是枚举成员。

def _real_call(auth: str, auth_signer=None):
    from gimbal.schema import Call
    return Call.model_validate({"protocol": "http", "user": "u1", "auth": auth,
                                "auth_signer": auth_signer})


def test_real_call_model_bearer_dispatches():
    h = _inject(_Session(auth_signer="md5sign"), _real_call("bearer"))
    assert h == {"Authorization": "Bearer abc123"}


def test_real_call_model_basic_dispatches():
    h = _inject(_Session(), _real_call("basic"))
    assert set(h) == {"Authorization"}
    assert h["Authorization"].startswith("Basic ")


def test_real_call_model_custom_signer_dispatches():
    h = _inject(_Session(auth_signer="md5sign"),
                _real_call("custom", auth_signer="standard.bearer"))
    assert h == {"Authorization": "Bearer abc123"}


def test_real_call_model_none_keeps_legacy_md5():
    h = _inject(_Session(), _real_call("none"))
    assert set(h) == {"token", "timestamp"}


# ── P0-1 续:端到端——声明经预处理器重建 Call 后仍在(此前被丢,恒 none)──

def test_engine_path_applies_declared_bearer():
    from gimbal.auth.session import AuthSession
    from gimbal.schema import Call, Request, Step
    from tests.unit.characterization.test_events_and_plugins import (
        http_scenario, make_engine, mock_httpx,
    )
    sess = AuthSession(username="u", password="p")
    sess.apply_token("T1", 3600)
    engine, *_ = make_engine(auth_session=("tester", sess))
    sc = http_scenario()
    sc.steps[0] = Step(
        call=Call(protocol="http", service="svc", method="GET", path="/p",
                  user="tester", auth="bearer"),
        request=Request(kind="request", body={}), strategy=[])
    patcher, client = mock_httpx(200, {"ok": 1})
    with patcher:
        engine.run(sc)
    headers = client.request.call_args.kwargs.get("headers") or {}
    assert headers.get("Authorization") == "Bearer T1"
    assert "token" not in headers and "timestamp" not in headers
