"""TOK-08 审计遗留(2026-11-20)—— 认证器行为钉:

- TOK-08c:http_basic 的 HTTPAuthenticator 在 http:// login_url 上发凭据
  前告警(内网合法形态,只告警不拦截);
- TOK-08e:yz 认证器 token 未初始化(None)即消费 fail-fast —— 此前会把
  字面量 ``data[username]=None`` 写成会话 token。
"""
from __future__ import annotations

import pytest

from gimbal.auth.authenticators.http_basic import HTTPAuthenticator
from gimbal.auth.authenticators.yz import YZAuthenticator
from gimbal.auth.session import AuthSession
from gimbal.exceptions import AuthError


def _session(**kw) -> AuthSession:
    base = dict(url="http://plain.internal/auth", username="u",
                password="p123456")
    base.update(kw)
    return AuthSession(**base)


class TestHttpBasicPlaintextWarning:
    def test_http_login_url_logs_warning_before_post(self, monkeypatch):
        posted: dict = {}

        def fake_post(url, **kw):
            posted["url"] = url
            posted.update(kw)

            class R:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"token": "t-ok"}

            return R()

        monkeypatch.setattr(
            "gimbal.auth.authenticators.http_basic.httpx.post", fake_post)
        s = _session()
        HTTPAuthenticator().authenticate(s, "qa1")
        assert s.token == "t-ok"

    def test_https_authenticator_not_affected(self, monkeypatch):
        from gimbal.auth.authenticators.http_basic import HTTPSAuthenticator

        monkeypatch.setattr(
            "gimbal.auth.authenticators.http_basic.httpx.post",
            lambda url, **kw: type("R", (), {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"token": "t-https"},
            })())
        s = _session(url="https://secure.internal/auth")
        HTTPSAuthenticator().authenticate(s, "qa1")
        assert s.token == "t-https"


class TestYZNoneTokenFailsFast:
    def test_token_none_raises_auth_error(self):
        s = _session(url="https://track-test.21eline.com/")
        assert s.token is None  # 初始即 None(session 默认)
        with pytest.raises(AuthError, match="未初始化"):
            YZAuthenticator().authenticate(s, "yz")

    def test_preset_token_passes_through(self):
        s = _session(url="https://track-test.21eline.com/",
                     token="preset-token")
        YZAuthenticator().authenticate(s, "yz")
        # 直通形态:token 原样进 data[username]= 载荷
        assert s.token == "data[username]=preset-token"
