"""契约的形态：plate 侧要 fin 那样的结构化 py 定义，不是裸 JSON。

`endpoints.json` 有结构（declarations 带 name/path/type/required/children），
但它是**产物**不是定义：358KB 单文件，没法按域导航，没法 review 单个端点的
改动，改一个字段要 diff 一整份 JSON 的几万行。

fin 的形制是每端点一个 .py，构造 `EndpointSpec` 实例常量，聚合层汇总。
本组把 platform 拉到同一形制上。

**形制上的一处有意偏离**：fin 是 `endpoint/<domain>_<action>.py` 单层平铺
（18 个端点），platform 有 123 个 —— 单层没法导航，按域分目录
（`endpoint/scenarios/get_root.py`）。

**换形态不许换信息量**：py 定义是 JSON 的等价物，不是摘要。字段面、required、
嵌套 children 一条都不能少 —— 少一条就等于把上一轮的下钻成果扔了。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gimbal-plate"))

from gimbal_bootstrap.contract_gen import build_specs  # noqa: E402
from gimbal_bootstrap.contract_gen_py import (  # noqa: E402
    constant_name,
    emit_module,
    emit_package,
    module_path,
)

FAKE_OPENAPI = {
    "paths": {
        "/api/auth/register": {
            "post": {
                "summary": "注册一个新用户",
                "description": "注册一个新用户",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["username", "password"],
                                "properties": {
                                    "username": {
                                        "type": "string",
                                        "description": "登录名",
                                    },
                                    "password": {"type": "string"},
                                    "display_name": {"type": "string"},
                                },
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TokenOut"}
                            }
                        },
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "TokenOut": {
                "type": "object",
                "properties": {
                    "access_token": {"type": "string"},
                    "token_type": {"type": "string"},
                    "user": {
                        "type": "object",
                        "description": "注册出来的那个用户",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                        },
                    },
                },
            }
        }
    },
}


def _spec() -> dict:
    specs, _warnings = build_specs(FAKE_OPENAPI)
    return specs[0]


def _load(spec: dict):
    """执行生成的源码，取出里面的 EndpointSpec 实例。"""
    from gimbal_plate.schema.endpoint import EndpointSpec

    ns: dict = {}
    exec(compile(emit_module(spec), f"<{spec['id']}>", "exec"), ns)
    found = [v for v in ns.values() if isinstance(v, EndpointSpec)]
    assert len(found) == 1, f"{spec['id']} 的模块里应有且只有一个 EndpointSpec"
    return found[0]


def _flatten(node: dict):
    """声明条目及其全部子孙 —— 测试侧自备的展开，不依赖被测实现。"""
    yield node
    for kid in node.get("children") or []:
        yield from _flatten(kid)


def test_constant_name_is_derived_from_the_endpoint_id():
    """id `platform.auth.post_register` → 常量 `AUTH_POST_REGISTER`。

    去掉 system 前缀（fin 惯例：`fin.order.order_page` → `ORDER_ORDER_PAGE`）；
    端点文件里已经没有 system 了，再带一遍是噪音。
    """
    assert constant_name("platform.auth.post_register") == "AUTH_POST_REGISTER"
    assert constant_name("platform.health.get_root") == "HEALTH_GET_ROOT"


def test_module_path_groups_by_domain():
    assert module_path("platform.auth.post_register") == Path("auth/post_register.py")
    assert module_path("platform.scenarios.get_by_scenario_id") == Path(
        "scenarios/get_by_scenario_id.py"
    )


def test_the_emitted_module_is_importable_python():
    """生成物必须是能跑的 Python，不是「长得像 Python 的字符串」。"""
    ep = _load(_spec())
    assert ep.id == "platform.auth.post_register"
    assert ep.api.method == "POST"
    assert ep.api.path == "/api/auth/register"
    assert ep.api.auth == "none"  # /api/auth/register 在免鉴权名单里


def test_the_emitted_module_keeps_every_field_of_the_source_definition():
    """换形态不许换信息量：整棵声明树的 path/type 一条不少。"""
    spec = _spec()
    ep = _load(spec)

    from gimbal_plate.schema.endpoint.io_spec import iter_declarations

    got = [(d.path, d.type) for d in iter_declarations(ep.responses[201].declarations)]
    want = [
        (d["path"], d["type"])
        for d in spec["responses"]["201"]["declarations"]
        for d in _flatten(d)
    ]
    assert got == want


def test_the_emitted_module_keeps_nested_children():
    """下钻出来的 children 是上一轮的全部成果，不能在换形态时丢掉。"""
    ep = _load(_spec())
    user = {d.name: d for d in ep.responses[201].declarations}["user"]
    assert {c.path for c in user.children} == {"$.user.id", "$.user.username"}


def test_the_emitted_module_keeps_required_flags():
    """required 是请求面的必填星标，丢了表单就少一颗星。

    顺带堵一个现存缺口：endpoints.json 里写着 required，加载器 `_declarations`
    没往 DeclarationEntry 传它 —— 声明早就有了，到 plate 里全成了 False。
    """
    spec = _spec()
    ep = _load(spec)
    by_path = {d.path: d for d in ep.request.declarations}
    assert by_path["$.username"].required is True
    assert by_path["$.password"].required is True
    assert by_path["$.display_name"].required is False
    # 中间形态里本来就带着 required —— 丢的是加载器，不是生成器。
    src = {d["name"]: d for d in spec["request"]["declarations"]}
    assert src["username"]["required"] is True


def test_the_emitted_module_marks_response_fields_assertable_and_request_fields_not():
    """断言面只在响应侧 —— 请求字段标成可断言，等于告诉编排器去断言自己刚发的 body。"""
    ep = _load(_spec())
    assert all(d.assertable for d in ep.responses[201].declarations)
    assert not any(d.assertable for d in ep.request.declarations)


def test_the_emitted_module_keeps_field_descriptions():
    """说明是契约里唯一带语义的部分，也是用例作者写断言时唯一的依据。"""
    ep = _load(_spec())
    by_path = {d.path: d for d in ep.request.declarations}
    assert by_path["$.username"].description == "登录名"


@pytest.mark.parametrize(
    ("json_type", "ui_kind"),
    [
        ("string", "text"),
        ("integer", "number"),
        ("number", "number"),
        ("boolean", "boolean"),
        ("object", "json"),
        ("array", "json"),
    ],
)
def test_ui_kind_is_derived_from_the_type(json_type, ui_kind):
    """类型 → 控件形态，映射跟 plate 自己的 `_ui_kind_of` 同款。

    不给 ui_kind 的话所有字段都是 unknown，场景编辑器里没有可用的控件提示 ——
    这正是「只给了基础接口信息」在编辑侧的样子。
    """
    from gimbal_bootstrap.contract_gen_py import ui_kind_of

    assert ui_kind_of(json_type) == ui_kind


def test_the_emitted_module_documents_the_endpoint():
    """文件头要能替代「翻源码才知道这个端点是干嘛的」。

    fin 每个端点文件都有说明字段面来源的 docstring；platform 的 123 个端点
    靠人读 JSON 是读不动的。
    """
    src = emit_module(_spec())
    assert src.startswith('"""'), "文件必须以模块 docstring 开头"
    assert "platform.auth.post_register" in src
    assert "POST" in src and "/api/auth/register" in src
    assert "注册一个新用户" in src


def test_emit_package_writes_one_module_per_endpoint_plus_the_aggregator(tmp_path):
    specs, _ = build_specs(FAKE_OPENAPI)
    written = emit_package(specs, root=tmp_path)
    assert (tmp_path / "auth" / "post_register.py").is_file()
    assert (tmp_path / "__init__.py").is_file()
    assert len(written) == len(list(tmp_path.rglob("*.py")))


def test_every_domain_directory_is_importable(tmp_path):
    """按域分目录是本方案对 fin 的偏离，代价是每个目录得有 __init__.py。

    缺了它，`...platform.endpoint.auth.post_register` 这个 import path 在
    打包安装后就断了 —— 开发时 namespace package 还能凑合，装上就 ImportError。
    """
    specs, _ = build_specs(FAKE_OPENAPI)
    emit_package(specs, root=tmp_path)
    assert (tmp_path / "auth" / "__init__.py").is_file()


def test_the_aggregator_imports_every_endpoint_constant(tmp_path):
    specs, _ = build_specs(FAKE_OPENAPI)
    emit_package(specs, root=tmp_path)
    text = (tmp_path / "__init__.py").read_text(encoding="utf-8")
    assert "AUTH_POST_REGISTER" in text
    assert "ALL_ENDPOINTS" in text


def test_re_generating_does_not_clobber_a_hand_edited_file(tmp_path):
    """这些文件是给人改的 —— 人工核订的语义注释不能被重新生成抹掉。

    fin 的每个端点文件都有实测核订的说明，那些字没有一份在 OpenAPI 里。
    重新生成时跳过已存在的文件，要覆盖得显式 --force。
    """
    specs, _ = build_specs(FAKE_OPENAPI)
    target = tmp_path / "auth" / "post_register.py"
    target.parent.mkdir(parents=True)
    target.write_text("# 人工核订：这行在 OpenAPI 里没有\n", encoding="utf-8")

    emit_package(specs, root=tmp_path, force=False)
    assert target.read_text(encoding="utf-8") == "# 人工核订：这行在 OpenAPI 里没有\n"


def test_the_aggregator_is_always_rewritten(tmp_path):
    """聚合层例外：它必须跟磁盘上的端点文件对得上，否则漏注册一个端点。

    代价是人删了端点文件就 ImportError —— 显式、响亮，优于静默少注册。
    """
    specs, _ = build_specs(FAKE_OPENAPI)
    emit_package(specs, root=tmp_path)
    (tmp_path / "__init__.py").write_text("# 手改的\n", encoding="utf-8")

    emit_package(specs, root=tmp_path, force=False)
    assert "AUTH_POST_REGISTER" in (tmp_path / "__init__.py").read_text(encoding="utf-8")


def test_force_regeneration_overwrites(tmp_path):
    specs, _ = build_specs(FAKE_OPENAPI)
    target = tmp_path / "auth" / "post_register.py"
    target.parent.mkdir(parents=True)
    target.write_text("# 旧的\n", encoding="utf-8")

    emit_package(specs, root=tmp_path, force=True)
    assert "EndpointSpec" in target.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad_id", ["platform.Auth.Post", "platform..x", "1bad", "x"])
def test_an_id_that_cannot_become_a_module_name_is_rejected(bad_id):
    """id 直接决定文件路径与 import 名 —— 不合法的必须挡在生成期。

    放到生成期而不是导入期：等到 plate 加载时才炸，报错点离成因十万八千里。
    """
    with pytest.raises(ValueError):
        constant_name(bad_id)
