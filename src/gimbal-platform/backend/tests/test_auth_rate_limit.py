"""Auth 限流面专测(known-issue auth/login-rate-limit-gap 落地步的钉子)。

conftest 对整套件默认旁路(``_disable_auth_rate_limit``);本文件显式
开闸,验四个面:双键(IP + 账号)预算各自触发 429(数值码 4291)、
拒绝不记窗(Retry-After 不被重试推长)、开关旁路、以及滑动窗滑出
语义(``now`` 注入直打 ``rate_limit.check``)。

IP 键显式给 ``x-real-ip``(ASGITransport 无对端地址,生产键源即该头,
nginx 恒重写、反代后不可伪造 —— 见 core/rate_limit.py docstring)。
"""
from __future__ import annotations

import pytest

from app.core import rate_limit
from app.core.config import settings


IP = {"x-real-ip": "10.99.0.7"}


async def _register(client, username: str) -> None:
    r = await client.post("/api/auth/register", headers=IP, json={
        "username": username, "password": "rl-pass-123",
        "display_name": username,
    })
    assert r.status_code == 201, r.text


async def _login(client, username: str, password: str = "wrong-pass-1"):
    return await client.post("/api/auth/login", headers=IP, json={
        "username": username, "password": password,
    })


@pytest.fixture(autouse=True)
def _enable_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    rate_limit.reset()
    yield
    rate_limit.reset()


async def test_login_account_budget(client):
    """账号面:同 IP 同账号错密 6 次后第 7 次 429(数值码 4291)。"""
    await _register(client, "rlacct")
    for _ in range(settings.AUTH_LOGIN_ACCT_MAX):
        assert (await _login(client, "rlacct")).status_code == 401
    r = await _login(client, "rlacct")
    assert r.status_code == 429, r.text
    assert r.json()["detail"] == {
        "code": 4291, "msg": "请求过于频繁,请稍后再试"}
    assert int(r.headers["Retry-After"]) >= 1


async def test_login_ip_budget_spray(client, monkeypatch):
    """IP 面(密码喷洒):账号面预算内,别账号被 IP 预算连坐。"""
    monkeypatch.setattr(settings, "AUTH_LOGIN_IP_MAX", 3)
    # 注册不占 login 面(register 自己的 10/600s IP 窗内,3 次)
    for i in range(3):
        await _register(client, f"rlspray{i}")
    for i in range(3):
        assert (await _login(client, f"rlspray{i}")).status_code == 401
    # 每账号各只 1 次(远未到账号面),但 IP 面已满 → 429
    r = await _login(client, "rlspray0")
    assert r.status_code == 429, r.text


async def test_login_other_ip_not_affected(client):
    """双键分账语义:账号面不分 IP —— 换 IP 打同一账号仍被账号预算拦
    (防分布式爆破);换 IP 打**别**账号则两个面都全新,不连坐。"""
    await _register(client, "rltwo")
    for _ in range(settings.AUTH_LOGIN_ACCT_MAX):
        await _login(client, "rltwo")
    assert (await _login(client, "rltwo")).status_code == 429
    # 换 IP 打同一账号:IP 面重开,但账号面已耗尽 → 仍 429
    r = await client.post("/api/auth/login", headers={"x-real-ip": "10.99.0.8"},
                          json={"username": "rltwo", "password": "wrong"})
    assert r.status_code == 429, r.text
    # 换 IP 打别的账号:两个面各自分账 → 正常 401(不连坐)
    await _register(client, "rltwo_b")
    r = await client.post("/api/auth/login", headers={"x-real-ip": "10.99.0.8"},
                          json={"username": "rltwo_b", "password": "wrong"})
    assert r.status_code == 401, r.text


async def test_refresh_ip_budget(client, monkeypatch):
    """refresh 无账号面(body 是 token),IP 面耗尽即 429。"""
    monkeypatch.setattr(settings, "AUTH_REFRESH_IP_MAX", 3)
    await _register(client, "rlrefresh")
    r = await _login(client, "rlrefresh", password="rl-pass-123")
    assert r.status_code == 200, r.text
    refresh_token = r.json()["refresh_token"]
    for _ in range(3):
        ok = await client.post("/api/auth/refresh", headers=IP,
                               json={"refresh_token": refresh_token})
        assert ok.status_code == 200, ok.text
    r = await client.post("/api/auth/refresh", headers=IP,
                          json={"refresh_token": refresh_token})
    assert r.status_code == 429, r.text


async def test_register_ip_budget(client, monkeypatch):
    """register:同 IP 超配额后连自助注册也 429(慢窗 10/600s 的面)。"""
    monkeypatch.setattr(settings, "AUTH_REGISTER_IP_MAX", 3)
    for i in range(3):
        await _register(client, f"rlreg{i}")
    r = await client.post("/api/auth/register", headers=IP, json={
        "username": "rlreg4", "password": "rl-pass-123",
        "display_name": "rlreg4"})
    assert r.status_code == 429, r.text


async def test_rejected_hits_not_recorded(client):
    """拒绝不记窗:连续 429 的 Retry-After 不被重试推长(最早命中定长)。"""
    await _register(client, "rlstill")
    for _ in range(settings.AUTH_LOGIN_ACCT_MAX):
        await _login(client, "rlstill")
    first = await _login(client, "rlstill")
    for _ in range(3):
        again = await _login(client, "rlstill")
        assert again.status_code == 429
        assert int(again.headers["Retry-After"]) == int(first.headers["Retry-After"])


async def test_disabled_bypasses(client, monkeypatch):
    """AUTH_RATE_LIMIT_ENABLED=False 整面旁路(回退开关)。"""
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", False)
    await _register(client, "rloff")
    for _ in range(settings.AUTH_LOGIN_ACCT_MAX + 4):
        assert (await _login(client, "rloff")).status_code == 401


def test_sliding_window_expiry():
    """滑出语义(直打 check,注入 now):过窗即回预算,Retry-After 递减。"""
    # 5 命中 @ t=0..4(窗 60s)
    for t in range(5):
        rate_limit.check("unit", ip="u-ip", ip_max=5, ip_window_s=60, now=float(t))
    with pytest.raises(rate_limit.RateLimited) as ei:
        rate_limit.check("unit", ip="u-ip", ip_max=5, ip_window_s=60, now=10.0)
    # t=10 时最早命中(0)还有 50s 滑出
    assert ei.value.retry_after == pytest.approx(50.0)
    with pytest.raises(rate_limit.RateLimited):
        rate_limit.check("unit", ip="u-ip", ip_max=5, ip_window_s=60, now=30.0)
    assert ei.value.retry_after == pytest.approx(50.0)   # 拒绝不记窗,原值不动
    # t=60.5:t=0 的命中已滑出 → 预算回 1,放行
    rate_limit.check("unit", ip="u-ip", ip_max=5, ip_window_s=60, now=60.5)
