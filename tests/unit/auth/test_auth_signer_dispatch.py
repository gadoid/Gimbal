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
