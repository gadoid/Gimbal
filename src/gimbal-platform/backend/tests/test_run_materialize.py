"""materialize_run_copy — POST-convert 物化纯函数(执行/导出同源)。

绑定优先级(spec §5):显式绑定 url > 场景 authored > env.baseUrl 补缺。
users 合并固定 merge 语义(spec §10:merge_policy 退役)。
"""
from types import SimpleNamespace

from app.services.run_materialize import materialize_run_copy


def _converted() -> dict:
    return {
        "kind": "scenario",
        "config": {
            "services": {"fin-service": "https://authored"},
            "users": {"builtin": {"url": "https://u", "username": "b",
                                  "password": "p", "expires_in": 7200,
                                  "token_type": "Authorization"}},
            "vars": {},
        },
        "steps": [
            {"kind": "step", "api": {"service": "fin-service", "path": "/x",
                                     "headers": {"Authorization": "${auth.qa1.token}"}}},
            {"kind": "step", "api": {"service": "svc-orphan", "path": "/y"}},
        ],
    }


def _auth(alias: str, url="https://auth-url") -> SimpleNamespace:
    return SimpleNamespace(alias=alias, url=url, username="u1", password="p1",
                           token_type="Authorization", expires_in=7200)


def test_binding_url_overrides_authored() -> None:
    out = materialize_run_copy(_converted(), env_base_url="https://env",
                               service_bindings={"fin-service": {"url": "https://bound"}})
    assert out["config"]["services"]["fin-service"] == "https://bound"


def test_authored_kept_when_no_binding() -> None:
    out = materialize_run_copy(_converted(), env_base_url="https://env")
    assert out["config"]["services"]["fin-service"] == "https://authored"


def test_env_fills_missing_referenced_service() -> None:
    out = materialize_run_copy(_converted(), env_base_url="https://env")
    assert out["config"]["services"]["svc-orphan"] == "https://env"


def test_no_env_leaves_gap_visible() -> None:
    out = materialize_run_copy(_converted())
    assert "svc-orphan" not in out["config"]["services"]


def test_auths_merge_over_builtin() -> None:
    out = materialize_run_copy(_converted(), resolved_auths=[_auth("qa1")])
    users = out["config"]["users"]
    assert users["builtin"]["username"] == "b"          # 内置保留
    assert users["qa1"]["url"] == "https://auth-url"     # 注入覆盖同名
    assert users["qa1"]["username"] == "u1"
    assert users["qa1"]["token_type"] == "Authorization"
    assert users["qa1"]["expires_in"] == 7200


def test_built_in_users_base_precedes_converted_users() -> None:
    """merge 基座 = built_in_users(definition.config.users,pre-convert)
    先铺,converted 自带 users 后铺,auths 最后覆盖 — 与现 _inject_exec_users
    ``{**built_in, **cfg.users}`` 同构(内置认证以场景定义为唯一可信源)。"""
    src = _converted()
    src["config"]["users"]["from-converted"] = {"url": "https://c", "username": "c",
                                                "password": "c", "expires_in": 1,
                                                "token_type": "Bearer"}
    out = materialize_run_copy(src, resolved_auths=[_auth("qa1")],
                               built_in_users={"from-definition": {"url": "https://d"}})
    assert "from-definition" in out["config"]["users"]
    assert "from-converted" in out["config"]["users"]


def test_config_created_when_missing() -> None:
    """PlateMock ok 桩的 converted 无 config/steps — 物化不炸且注入可落。"""
    out = materialize_run_copy({"kind": "platform_scenario"},
                               service_bindings={"any": {"url": "https://x"}})
    assert out["config"]["services"] == {}   # 无 steps → 无 referenced → 绑定不落
    assert out["config"]["users"] == {}


def test_no_auths_leaves_users_untouched() -> None:
    out = materialize_run_copy(_converted())
    assert set(out["config"]["users"]) == {"builtin"}


def test_pure_function_input_not_mutated() -> None:
    src = _converted()
    snapshot = {"services": dict(src["config"]["services"]), "users": dict(src["config"]["users"])}
    materialize_run_copy(src, env_base_url="https://env",
                         service_bindings={"fin-service": {"url": "https://bound"}},
                         resolved_auths=[_auth("qa1")])
    assert src["config"]["services"] == snapshot["services"]
    assert src["config"]["users"] == snapshot["users"]


def test_unreferenced_service_keys_preserved() -> None:
    src = _converted()
    src["config"]["services"]["legacy-svc"] = "https://legacy"
    out = materialize_run_copy(src, env_base_url="https://env")
    assert out["config"]["services"]["legacy-svc"] == "https://legacy"
