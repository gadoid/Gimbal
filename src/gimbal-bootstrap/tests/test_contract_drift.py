"""契约漂移检测：plate 里登记的 platform 端点必须都是平台真有的路由。

**单向**（declared ⊆ actual）：平台多出来的端点不算漂移 —— 契约是地板不是天花板；
但契约里登记了、平台却没了的端点算漂移，因为用例编排会拿着这个 path 去打真实 HTTP。

两层：
1. 静态层 —— 拿平台自己的 /openapi.json 对账。无副作用、无需登录，CI 可直接跑。
2. 实测层 —— 用提权后的自举账号真打几个 GET，确认不只是 schema 上有、而是真能通。
   没有 GIMBAL_SB_USERNAME 就跳过。
"""

from __future__ import annotations

import pytest

from gimbal_bootstrap.contract_gen import fetch_openapi
from gimbal_plate.systems.platform.endpoints import ALL_PLATFORM_ENDPOINTS
# 实测层挑的端点：全是 GET，admin 才能过，不产生任何写。
LIVE_PROBES = [
    ("GET", "/api/health"),
    ("GET", "/api/users/roster"),
    ("GET", "/api/scenarios"),
    ("GET", "/api/constants"),
]


def _declared_routes() -> set[tuple[str, str]]:
    out = set()
    for ep in ALL_PLATFORM_ENDPOINTS:
        out.add((ep.api.method.upper(), ep.api.path))
    return out


def _openapi_routes(openapi: dict) -> set[tuple[str, str]]:
    out = set()
    for path, item in (openapi.get("paths") or {}).items():
        for method in item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                out.add((method.upper(), path))
    return out


@pytest.fixture(scope="module")
def openapi() -> dict:
    # 回落打开：文档承诺这一层「无副作用、无需登录、CI 可直接跑」，那就别
    # 依赖 127.0.0.1:8000 上有个进程在听。进程内拿的是当前 checkout 的代码。
    return fetch_openapi(allow_inprocess_fallback=True)


def test_every_declared_route_exists_on_the_platform(openapi):
    """契约登记的每条路由，平台都得有 —— 否则用例编排打过去就是 404。"""
    missing = _declared_routes() - _openapi_routes(openapi)
    assert not missing, "契约里登记但平台没有的路由：\n" + "\n".join(
        f"  {m} {p}" for m, p in sorted(missing)
    )


def test_declared_route_count_is_sane(openapi):
    """防呆：契约被清空或生成器退化成空产物时，这门会响。"""
    declared, actual = _declared_routes(), _openapi_routes(openapi)
    assert len(declared) > 100, f"契约只剩 {len(declared)} 条端点，生成器多半坏了"
    assert declared <= actual


def test_no_declared_endpoint_reuses_a_route(openapi):
    """plate 的 by_route 是后写覆盖先写 —— 两条端点撞同一 (service,method,path)
    会静默吃掉一条。登记时就该炸。"""
    from gimbal_bootstrap.contract_gen import check_collisions

    specs = [
        {
            "id": ep.id,
            "service": ep.api.service,
            "api": {"method": ep.api.method, "path": ep.api.path},
        }
        for ep in ALL_PLATFORM_ENDPOINTS
    ]
    check_collisions(specs)  # 不抛即通过


def _live_client():
    """实测层用的 client —— 拿编排器注册好的那个自举账号现登一次换 token。

    之前这里是 `Platform(BASE_URL, os.environ["GIMBAL_SB_TOKEN"])`，而
    GIMBAL_SB_TOKEN 谁也不定义、编排器也从不导出：按文档配一遍实测层永远
    跳过，只配一半就在裸 KeyError 上死。凭据池和 token 都走编排器已经在用
    的那一份 —— `.env` 里的账号口令。
    """
    from gimbal_bootstrap.orchestrator import _login, _resolve_env

    if not _resolve_env("GIMBAL_SB_USERNAME"):
        return None
    return _login(_resolve_env("GIMBAL_SB_USERNAME"), _resolve_env("GIMBAL_SB_PASSWORD"))


def _live_layer_configured() -> bool:
    from gimbal_bootstrap.orchestrator import _resolve_env

    return bool(_resolve_env("GIMBAL_SB_USERNAME"))


def test_live_layer_needs_no_token_variable(tmp_path, monkeypatch):
    """实测层只认 GIMBAL_SB_USERNAME/PASSWORD —— 编排器注册完就把这两个写进
    .env 了。之前这里读的是一个谁也没定义过的 GIMBAL_SB_TOKEN：按文档配一遍
    实测层永远跳过，只设一半就在 os.environ[...] 上炸一个裸 KeyError。"""
    from gimbal_bootstrap import orchestrator
    from tests import test_contract_drift as drift  # noqa: PLC0415

    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    (tmp_path / ".env").write_text(
        "GIMBAL_SB_PASSWORD=Pw-12345678\nGIMBAL_SB_USERNAME=sb_prev\n", encoding="utf-8"
    )
    monkeypatch.delenv("GIMBAL_SB_TOKEN", raising=False)
    monkeypatch.setattr(orchestrator, "Platform", _RecordingPlatform)

    assert drift._live_client() is not None, "配全了却拿不到 client"
    assert drift._live_client().token == "tok-live", "没有自己登进去换 token"


def test_live_layer_skips_cleanly_when_nothing_is_configured(tmp_path, monkeypatch):
    from gimbal_bootstrap import orchestrator
    from tests import test_contract_drift as drift  # noqa: PLC0415

    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    assert drift._live_client() is None, "没配就该返回 None 好让 skipif 跳掉"


@pytest.mark.skipif(
    not _live_layer_configured(),
    reason="没配 GIMBAL_SB_USERNAME，跳过实测层（需要一个提权到 admin 的自举账号）",
)
def test_declared_get_routes_answer_over_real_http():
    from gimbal_bootstrap.platform_client import PlatformError

    client = _live_client()
    dead = []
    for method, path in LIVE_PROBES:
        try:
            client.request(method, path)
        except PlatformError as exc:
            if exc.status == 404:
                dead.append(f"{method} {path} -> 404")
    assert not dead, "平台真打不通的已登记端点：\n" + "\n".join(dead)


class _RecordingPlatform:
    """只够实测层登录用：POST 换 token，构造器把 token 存下来。"""

    def __init__(self, base_url, token=None):
        self.token = token

    def post(self, path, body=None):
        assert path == "/api/auth/login", path
        return 200, {"access_token": "tok-live"}
