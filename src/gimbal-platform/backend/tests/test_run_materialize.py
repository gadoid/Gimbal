"""materialize_run_copy — POST-convert 物化纯函数(执行/导出同源)。

绑定优先级(spec §5 / D2):显式绑定 url > 场景 authored(env 补缺层已退役)。
users 合并固定 merge 语义(spec §10:merge_policy 退役)。
"""
import inspect
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
    out = materialize_run_copy(_converted(),
                               service_bindings={"fin-service": {"url": "https://bound"}})
    assert out["config"]["services"]["fin-service"] == "https://bound"


def test_authored_kept_when_no_binding() -> None:
    out = materialize_run_copy(_converted())
    assert out["config"]["services"]["fin-service"] == "https://authored"


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
    materialize_run_copy(src,
                         service_bindings={"fin-service": {"url": "https://bound"}},
                         resolved_auths=[_auth("qa1")])
    assert src["config"]["services"] == snapshot["services"]
    assert src["config"]["users"] == snapshot["users"]


def test_unreferenced_service_keys_preserved() -> None:
    src = _converted()
    src["config"]["services"]["legacy-svc"] = "https://legacy"
    out = materialize_run_copy(src)
    assert out["config"]["services"]["legacy-svc"] == "https://legacy"


def test_no_env_layer_binding_and_authored_only() -> None:
    """D2:env 补缺层删除后,URL 链只剩 显式绑定 > authored。"""
    # env 层不存在:签名已无 env_base_url 参数
    assert "env_base_url" not in inspect.signature(materialize_run_copy).parameters

    # 已有声明(authored)+ 无绑定 → 原样保留
    out = materialize_run_copy(_converted())
    assert out["config"]["services"]["fin-service"] == "https://authored"

    # 显式绑定覆盖 authored(语义不变)
    out = materialize_run_copy(
        _converted(),
        service_bindings={"fin-service": {"url": "https://bound"}},
    )
    assert out["config"]["services"]["fin-service"] == "https://bound"

    # 未声明且未绑定 → 留空(引擎显式报错语义,RunDialog 并集行提前发现)
    out = materialize_run_copy(_converted())
    assert "svc-orphan" not in out["config"]["services"] or \
        not out["config"]["services"].get("svc-orphan")


# ─── carry 填充(spec §4)────────────────────────────────────────
from app.services.run_materialize import CarryContext


def _carry_converted() -> dict:
    return {
        "kind": "scenario",
        "config": {"services": {}, "users": {}, "vars": {}},
        "steps": [
            {"kind": "step",
             "api": {"service": "fin-service", "path": "/x",
                     "view_hints": {"endpoint_id": "fin.ep1"}},
             "request": {"kind": "request", "body": {"order_id": "o-1"}}},
        ],
    }


def _ctx(**over) -> CarryContext:
    base = dict(
        step_fields={0: {"$.remark": "string", "$.appCode": "string",
                          "$.count": "integer", "$.flag": "boolean",
                          "$.meta": "object", "$.tpl": "string"}},
        service_bindings={"fin-service": {"$.remark": "压测-张三",
                                           "$.count": "3"}},
        global_defaults={"$.appCode": "TRACE-V2", "$.flag": "true",
                          "$.meta": "{\"k\": 1}"},
    )
    base.update(over)
    return CarryContext(**base)


class TestCarryFill:
    def test_service_binding_wins_over_default(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            global_defaults={"$.remark": "全局备注", "$.appCode": "V2"}))
        body = out["steps"][0]["request"]["body"]
        assert body["remark"] == "压测-张三"

    def test_global_default_fills_unbound_path(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx())
        assert out["steps"][0]["request"]["body"]["appCode"] == "TRACE-V2"

    def test_body_existing_key_skipped(self):
        src = _carry_converted()
        src["steps"][0]["request"]["body"]["remark"] = "手填值"
        out = materialize_run_copy(src, carry_context=_ctx())
        assert out["steps"][0]["request"]["body"]["remark"] == "手填值"

    def test_two_layers_absent_skips(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={0: {"$.nosuch": "string"}}))
        assert "nosuch" not in out["steps"][0]["request"]["body"]

    def test_null_row_injects_json_null(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": {"$.remark": None}}))
        assert out["steps"][0]["request"]["body"]["remark"] is None

    def test_type_coercion(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx())
        body = out["steps"][0]["request"]["body"]
        assert body["count"] == 3            # integer
        assert body["flag"] is True          # boolean 严格 true/false
        assert body["meta"] == {"k": 1}      # object JSON 解析

    def test_coerce_failure_keeps_original_string(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": {"$.count": "3x"}},
            global_defaults={"$.meta": "{not-json}"}))
        body = out["steps"][0]["request"]["body"]
        assert body["count"] == "3x"
        assert body["meta"] == "{not-json}"

    def test_repr_text_heals_for_container_faces(self):
        """值表容器值是 Python repr 文本(单引号/None/True,粘贴产物)——
        非法 JSON 但可字面还原;json.loads 失败须再试 literal_eval,
        不得把 repr 原串注入 body(fin orderAdd supplier 实录回归)。"""
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={0: {"$.supplier": "array", "$.meta": "object"}},
            service_bindings={"fin-service": {
                "$.supplier": "[{'is_manual': '', 'settlement_date': None,"
                              " 'isset_fee': '0'}]",
                "$.meta": "{'k': 'v', 'on': True}"}}))
        body = out["steps"][0]["request"]["body"]
        assert body["supplier"] == [{"is_manual": "", "settlement_date": None,
                                     "isset_fee": "0"}]
        assert body["meta"] == {"k": "v", "on": True}

    def test_repr_heal_rejects_non_container_and_garbage(self):
        """兜底只收容器:literal_eval 还原出标量(None)不收;两级都解析
        不了的残缺文本保留原串。"""
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={0: {"$.supplier": "array", "$.meta": "object"}},
            service_bindings={"fin-service": {
                "$.supplier": "None",         # 标量 repr:兜底不收,保串
                "$.meta": "{'k': 'v'",        # 残缺 repr:literal_eval 也败
            }}))
        body = out["steps"][0]["request"]["body"]
        assert body["supplier"] == "None"
        assert body["meta"] == "{'k': 'v'"

    def test_template_value_passes_through_uncoerced(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": {"$.tpl": "${var.envId}",
                                              "$.count": "${var.n}"}}))
        body = out["steps"][0]["request"]["body"]
        assert body["tpl"] == "${var.envId}"
        assert body["count"] == "${var.n}"   # 模板不做二次 coerce

    def test_unresolved_service_skips_whole_step(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": None}))
        body = out["steps"][0]["request"]["body"]
        assert "appCode" not in body and "remark" not in body

    def test_no_anchor_falls_back_to_value_table_keys(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={}))
        body = out["steps"][0]["request"]["body"]
        # 降级门控:候选 = 绑定键 ∪ 全局默认键
        assert body["remark"] == "压测-张三"
        assert body["appCode"] == "TRACE-V2"
        # 降级无类型 → 透传不转换:候选 dict 的"类型"位实际是值串,
        # coerce 无分支命中 — "true" 保持字符串,不得变 boolean True
        assert body["flag"] == "true"
        assert body["meta"] == "{\"k\": 1}"

    def test_nested_path_builds_intermediate_layers(self):
        # $.a.b 深路径:body 无 a 键 → _carry_targets 逐层建 dict 后写入嵌套值
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={0: {"$.a.b": "string"}},
            service_bindings={"fin-service": {"$.a.b": "深嵌值"}}))
        assert out["steps"][0]["request"]["body"]["a"]["b"] == "深嵌值"

    # ── 字段级注入 × 数组容器广播(2026-09-05 注入粒度)─────────────

    @staticmethod
    def _container_src() -> dict:
        src = _carry_converted()
        src["steps"][0]["request"]["body"]["container"] = [
            {"box_type": "20GP", "box_num": "1", "box_no": ["A1"]},
            {"box_num": "2", "box_no": []},
        ]
        return src

    def test_field_path_broadcasts_to_all_rows(self):
        """模板字段 path 跨数组容器 → 广播每个 dict 行(行级填缺失)。"""
        out = materialize_run_copy(self._container_src(), carry_context=_ctx(
            step_fields={0: {"$.container.sea_trans_unit_price": "number"}},
            service_bindings={"fin-service": {
                "$.container.sea_trans_unit_price": "100"}}))
        rows = out["steps"][0]["request"]["body"]["container"]
        assert [r.get("sea_trans_unit_price") for r in rows] == [100, 100]

    def test_row_explicit_value_wins_over_broadcast(self):
        out = materialize_run_copy(self._container_src(), carry_context=_ctx(
            step_fields={0: {"$.container.box_type": "string"}},
            service_bindings={"fin-service": {"$.container.box_type": "40HQ"}}))
        rows = out["steps"][0]["request"]["body"]["container"]
        assert rows[0]["box_type"] == "20GP"    # 行显式值最优先
        assert rows[1]["box_type"] == "40HQ"    # 缺失行被填充

    def test_array_rows_and_siblings_survive_injection(self):
        """洗行病理回归:旧 _body_set 把数组中间节点替换成 {},行数据
        整组蒸发;新 walker 只按点填缺失,行数/兄弟键/嵌套数组全保留。"""
        out = materialize_run_copy(self._container_src(), carry_context=_ctx(
            step_fields={0: {"$.container.box_type": "string"}},
            service_bindings={"fin-service": {"$.container.box_type": "40HQ"}}))
        rows = out["steps"][0]["request"]["body"]["container"]
        assert len(rows) == 2
        assert rows[0] == {"box_type": "20GP", "box_num": "1", "box_no": ["A1"]}
        assert rows[1] == {"box_type": "40HQ", "box_num": "2", "box_no": []}

    def test_nested_array_broadcasts_two_levels(self):
        src = _carry_converted()
        src["steps"][0]["request"]["body"]["a"] = [
            {"b": [{"q": 1}, {"q": 2, "c": "显式"}]},
            {"b": []},                            # 空子数组:无行不造行
            {"b": "非容器"},                       # 非列表中间节点:下钻为 dict
        ]
        out = materialize_run_copy(src, carry_context=_ctx(
            step_fields={0: {"$.a.b.c": "string"}},
            service_bindings={"fin-service": {"$.a.b.c": "广播"}}))
        rows = out["steps"][0]["request"]["body"]["a"]
        assert [r["c"] for r in rows[0]["b"]] == ["广播", "显式"]
        assert rows[1]["b"] == []
        assert rows[2]["b"] == {"c": "广播"}       # 非列表 → dict 骨架下钻

    def test_whole_container_injection_shared_channel(self):
        """整容器注入与字段级注入共用同一通道:容器值 setdefault 落顶键,
        body 已有整容器字面量时最优先(整容器粒度填缺失)。"""
        out = materialize_run_copy(self._container_src(), carry_context=_ctx(
            step_fields={0: {"$.container": "array"}},
            service_bindings={"fin-service": {
                "$.container": "[{'box_type': '40HQ', 'box_num': '9'}]"}}))
        # body 已有 container 字面量 → 不覆盖
        assert out["steps"][0]["request"]["body"]["container"][0]["box_type"] == "20GP"

        src2 = _carry_converted()                  # body 无 container 键
        out2 = materialize_run_copy(src2, carry_context=_ctx(
            step_fields={0: {"$.container": "array"}},
            service_bindings={"fin-service": {
                "$.container": "[{'box_type': '40HQ', 'box_num': '9'}]"}}))
        assert out2["steps"][0]["request"]["body"]["container"] == [
            {"box_type": "40HQ", "box_num": "9"}]

    def test_empty_or_non_dict_rows_never_fabricate(self):
        """空数组无行不造行;标量行跳过不炸 —— 广播只面向 dict 行。"""
        src = _carry_converted()
        src["steps"][0]["request"]["body"]["container"] = []
        out = materialize_run_copy(src, carry_context=_ctx(
            step_fields={0: {"$.container.box_type": "string"}},
            service_bindings={"fin-service": {"$.container.box_type": "40HQ"}}))
        assert out["steps"][0]["request"]["body"]["container"] == []

        src["steps"][0]["request"]["body"]["container"] = ["20GP", 3, None]
        out = materialize_run_copy(src, carry_context=_ctx(
            step_fields={0: {"$.container.box_type": "string"}},
            service_bindings={"fin-service": {"$.container.box_type": "40HQ"}}))
        assert out["steps"][0]["request"]["body"]["container"] == ["20GP", 3, None]

    def test_carry_context_none_behaves_as_today(self):
        out = materialize_run_copy(_carry_converted())
        assert out["steps"][0]["request"]["body"] == {"order_id": "o-1"}

    def test_pure_function_input_not_mutated_carry(self):
        src = _carry_converted()
        materialize_run_copy(src, carry_context=_ctx())
        assert src["steps"][0]["request"]["body"] == {"order_id": "o-1"}
