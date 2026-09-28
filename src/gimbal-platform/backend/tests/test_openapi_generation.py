"""守住 OpenAPI 可生成。

背景：auth.py 曾使用 ChangePasswordIn 却忘了 import，
`from __future__ import annotations` 让注解变字符串，
运行时不报错，直到 FastAPI 生成 schema 才炸 PydanticUserError。
"""


def test_openapi_schema_builds():
    from app.main import app

    spec = app.openapi()

    assert len(spec["paths"]) > 50, "路径数异常少，OpenAPI 可能不完整"
    schemas = spec["components"]["schemas"]
    assert "RegisterIn" in schemas, "RegisterIn 未进 components，注册端点契约丢失"


def test_auth_router_has_no_unresolved_forward_ref():
    """auth 路由用到的每个请求模型都必须真实存在于模块命名空间。"""
    import typing

    import app.routers.auth as auth_mod
    from fastapi.routing import APIRoute

    unresolved: list[str] = []
    for route in auth_mod.router.routes:
        if not isinstance(route, APIRoute):
            continue
        try:
            typing.get_type_hints(route.endpoint)
        except NameError as exc:
            unresolved.append(f"{route.path}: {exc}")

    assert not unresolved, "auth 路由存在未解析的 ForwardRef: " + "; ".join(unresolved)
