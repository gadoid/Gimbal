"""字段状态解析链测试(spec 2026-09-05 §3.2 / §7④ / §7⑦)。

三层:
  1. resolve_state 单点公式 —— 空 step 读穿 / 增量命中 /
     entry 无 state → form / 目录外 path 交集容忍(§3.4);
  2. carry_face 注入面投影 —— 祖先吸收(整容器是注入单元)/
     form 容器下 carry 叶子下钻 / 垃圾输入防御;
  3. step.field_states 存储保形(§3.1/§7⑦)—— 场景草稿 POST →
     GET draft → PUT 更新,增量原样往返(自含,不依赖 plate)。
"""
from __future__ import annotations

from httpx import AsyncClient

from app.services.field_state_resolution import (
    DESCRIPTIVE,
    carry_face,
    catalog_paths,
    composite_states,
    iter_flat,
    resolve_state,
)

from .helpers import make_draft, register_and_login

# ── 语料:M1 后的 wire 形态(state 键 + children 树,无 channel)──────

_CARRY_CONTAINER = {
    "name": "supplier", "path": "$.supplier", "state": "carry",
    "type": "array",
    "children": [
        {"name": "supplier_id", "path": "$.supplier.order_supplier_id",
         "state": "carry", "type": "string"},
        {"name": "order_id", "path": "$.supplier.order_id",
         "state": "carry", "type": "string"},
    ],
}
_FORM_CONTAINER_CARRY_CHILD = {
    "name": "ext", "path": "$.ext", "state": "form", "type": "object",
    "children": [
        {"name": "trace_id", "path": "$.ext.trace_id",
         "state": "carry", "type": "string"},
    ],
}
_TOP_CARRY_LEAF = {"name": "appCode", "path": "$.appCode",
                   "state": "carry", "type": "string"}
_TOP_FORM_LEAF = {"name": "order_no", "path": "$.order_no",
                  "state": "form", "type": "string"}


class TestResolveStateChain:
    """§3.2 单点公式:state(path) = field_states[path] ?? entry.state ?? form。"""

    def test_empty_overlay_reads_through(self) -> None:
        """§7④-1 空 step(无增量)→ 读共识默认 entry.state。"""
        assert resolve_state("$.x", "carry", None) == "carry"
        assert resolve_state("$.x", "carry", {}) == "carry"
        assert resolve_state("$.x", "form", None) == "form"

    def test_overlay_hit_overrides_default(self) -> None:
        """§7④-2 增量命中:显式覆盖优先(§3.3 显式覆盖受保护)。"""
        assert resolve_state("$.x", "carry", {"$.x": "form"}) == "form"
        assert resolve_state("$.y", "form", {"$.y": "carry"}) == "carry"
        assert resolve_state("$.z", "form", {"$.z": "collapse"}) == "collapse"

    def test_entry_without_state_defaults_form(self) -> None:
        """§7④-3 entry 无 state(理论不至)→ form(fail-closed:零注入)。"""
        assert resolve_state("$.x", None, None) == "form"
        assert resolve_state("$.x", "binding", None) == "form"  # 词表外读穿

    def test_non_dict_overlay_reads_through(self) -> None:
        """防御:field_states 形状不符(非 dict)→ 整体视同缺席。"""
        assert resolve_state("$.x", "carry", ["$.x"]) == "carry"
        assert resolve_state("$.x", "carry", "$.x") == "carry"

    def test_bogus_overlay_value_reads_through(self) -> None:
        """增量值不在词表(如旧通道词 'binding')→ 该条增量视同缺席;
        词表约束归配置编辑校验(§3.5),解析侧不抛错。"""
        assert resolve_state("$.x", "carry", {"$.x": "binding"}) == "carry"
        assert resolve_state("$.x", None, {"$.x": "view_only"}) == "form"


class TestCarryFace:
    """注入/值表候选面投影(§4 carry_injection 行 + §4.1(a))。"""

    def test_carry_container_absorbs_descendants(self) -> None:
        """祖先吸收:carry 容器是注入单元,模板子孙不单列 ——
        深实例缩并(§2.4)后子孙 path 无实例下标,单独注入会物化出
        dict 顶替 array 的错误形态。"""
        face = carry_face([_CARRY_CONTAINER, _TOP_FORM_LEAF])
        assert face == {"$.supplier": "array"}

    def test_form_container_carry_child_descends(self) -> None:
        """form 容器下的 carry 叶子要下钻收录(整传一致性只单向约束:
        carry 容器 ⇒ 子孙 carry,不反向强制 form 容器无 carry 子孙)。"""
        face = carry_face([_FORM_CONTAINER_CARRY_CHILD])
        assert face == {"$.ext.trace_id": "string"}

    def test_top_level_leaves_projected(self) -> None:
        face = carry_face([_TOP_CARRY_LEAF, _TOP_FORM_LEAF])
        assert face == {"$.appCode": "string"}

    def test_overlay_flips_container_into_face(self) -> None:
        """增量把 form 容器划成 carry → 整容器入面,子孙被吸收。"""
        container = {
            "name": "supplier", "path": "$.supplier", "state": "form",
            "type": "array",
            "children": [
                {"name": "sid", "path": "$.supplier.sid",
                 "state": "form", "type": "string"},
            ],
        }
        face = carry_face([container], {"$.supplier": "carry"})
        assert face == {"$.supplier": "array"}

    def test_overlay_pulls_leaf_out_of_face(self) -> None:
        """增量把 carry 划回 form → 出面(移除 = 增量[path]=form/collapse,
        与添加同机制,§3.1)。"""
        face = carry_face([_TOP_CARRY_LEAF], {"$.appCode": "form"})
        assert face == {}

    def test_out_of_catalog_path_tolerated(self) -> None:
        """§7④-4 / §3.4 交集容忍:field_states 含目录外 path → 忽略
        (不抛错、不影响目录内条目解析)。stale 警告归 composer(挂账)。"""
        face = carry_face([_TOP_CARRY_LEAF], {"$.ghost": "form"})
        assert face == {"$.appCode": "string"}

    def test_garbage_input_degrades_to_empty(self) -> None:
        """plate 不可达/坏包降级(§3.4):declarations 非 list / 条目非
        dict / path 非 str → 空面,不注入。"""
        assert carry_face(None) == {}
        assert carry_face("nope") == {}
        assert carry_face([["bad"], {"no_path": 1}, 42]) == {}
        assert carry_face([{"path": ""}]) == {}

    def test_missing_type_defaults_string(self) -> None:
        face = carry_face([{"path": "$.x", "state": "carry"}])
        assert face == {"$.x": "string"}


class TestFlatIteration:
    """先序平铺(容器先于子孙)—— 与 plate iter_declarations 次序对齐。"""

    def test_preorder_container_before_children(self) -> None:
        paths = [e["path"] for e in iter_flat(
            [_CARRY_CONTAINER, _TOP_FORM_LEAF])]
        assert paths == [
            "$.supplier", "$.supplier.order_supplier_id",
            "$.supplier.order_id", "$.order_no",
        ]

    def test_composite_states_preorder(self) -> None:
        states = composite_states([_CARRY_CONTAINER, _TOP_FORM_LEAF])
        assert list(states) == [
            "$.supplier", "$.supplier.order_supplier_id",
            "$.supplier.order_id", "$.order_no",
        ]
        assert set(states.values()) == {"carry", "form"}

    def test_catalog_paths_is_tree_universe(self) -> None:
        assert catalog_paths([_CARRY_CONTAINER]) == {
            "$.supplier", "$.supplier.order_supplier_id",
            "$.supplier.order_id",
        }

    def test_descriptive_vocab_seeded_from_plate_policy(self) -> None:
        """§9 验收:DESCRIPTIVE 词表落户 platform 常量(备注族)。"""
        assert DESCRIPTIVE == {"remark", "notes", "cancel_remark"}


# ── §7⑦ 存储 roundtrip:field_states 随场景草稿保形 ─────────────────


def _fs_step() -> dict:
    """带 field_states 增量的 step(§3.1:与 api/request/strategy 平级)。"""
    return {"kind": "step",
            "api": {"service": "fin-service", "path": "/x"},
            "request": {"kind": "request", "body": {"order_no": "O-1"}},
            "field_states": {"$.remark": "form", "$.appCode": "carry"}}


async def test_field_states_roundtrip_through_draft(
    client: AsyncClient,
) -> None:
    """POST 创建 → GET draft → 增量原样保形;PUT 更新仍保形
    (自含存储:definition 自由 dict,不依赖 plate;§3.1/§7⑦)。"""
    headers = await register_and_login(client)
    r = await client.post("/api/scenarios", headers=headers,
                          json=make_draft("sc-fs-rt", steps=[_fs_step()]))
    assert r.status_code in (200, 201), r.text

    r = await client.get("/api/scenarios/sc-fs-rt/draft", headers=headers)
    assert r.status_code == 200, r.text
    step = r.json()["definition"]["steps"][0]
    assert step["field_states"] == {"$.remark": "form", "$.appCode": "carry"}

    # PUT 整体替换(server-side meta 归一化不动 steps)→ 增量仍在
    draft = r.json()
    draft["definition"]["steps"][0]["field_states"]["$.notes"] = "collapse"
    r = await client.put("/api/scenarios/sc-fs-rt", headers=headers,
                         json=draft)
    assert r.status_code == 200, r.text
    r = await client.get("/api/scenarios/sc-fs-rt/draft", headers=headers)
    step = r.json()["definition"]["steps"][0]
    assert step["field_states"] == {
        "$.remark": "form", "$.appCode": "carry", "$.notes": "collapse"}


async def test_field_states_absent_by_default(client: AsyncClient) -> None:
    """§3.1 默认不存:零增量的 step 落库后无 field_states 键(零存储)。"""
    headers = await register_and_login(client)
    plain = {"kind": "step",
             "api": {"service": "fin-service", "path": "/x"},
             "request": {"kind": "request", "body": {"order_no": "O-1"}}}
    r = await client.post("/api/scenarios", headers=headers,
                          json=make_draft("sc-fs-none", steps=[plain]))
    assert r.status_code in (200, 201), r.text
    r = await client.get("/api/scenarios/sc-fs-none/draft", headers=headers)
    assert "field_states" not in r.json()["definition"]["steps"][0]


# ── §3.5 配置编辑校验(§7⑤:树一致性拒 + 双软警告)──────────────────

from app.services.field_state_resolution import validate_field_states  # noqa: E402

_REQUIRED_LEAF = {"name": "order_no", "path": "$.order_no",
                  "state": "form", "type": "string", "required": True}
_DESCRIPTIVE_LEAF = {"name": "remark", "path": "$.remark",
                     "state": "form", "type": "string"}
_COLLAPSE_DESCRIPTIVE = {**_DESCRIPTIVE_LEAF, "state": "collapse"}


class TestValidateFieldStates:
    """合成态校验:对象是 plate 默认 + step 增量合并后的树。"""

    def test_clean_catalog_passes(self) -> None:
        """干净目录 = 备注族在 carry(政策面)、required 在 form。"""
        out = validate_field_states(
            [_CARRY_CONTAINER, _REQUIRED_LEAF,
             {**_DESCRIPTIVE_LEAF, "state": "carry"}])
        assert out == {"errors": [], "warnings": []}

    def test_overlay_breaking_tree_consistency_rejected(self) -> None:
        """§7⑤-1 树一致性(拒):增量把 carry 容器的子孙划回 form ——
        目录本身一致,合成态被增量破坏,同样拒。"""
        out = validate_field_states(
            [_CARRY_CONTAINER],
            {"$.supplier.order_supplier_id": "form"},
        )
        assert [e["code"] for e in out["errors"]] == ["tree_inconsistency"]
        assert out["errors"][0]["path"] == "$.supplier.order_supplier_id"
        assert not out["warnings"]

    def test_overlay_lifting_container_allows_children(self) -> None:
        """反向合法:增量把 carry 容器划成 form,子孙仍 carry ——
        整传一致性只单向约束(carry 容器 ⇒ 子孙 carry),不拒。"""
        out = validate_field_states(
            [_CARRY_CONTAINER], {"$.supplier": "form"})
        assert out["errors"] == []

    def test_baked_inconsistent_catalog_reported(self) -> None:
        """防御:目录本身树不一致(理论不至,plate 侧已校验)也报。"""
        broken = {"path": "$.box", "state": "carry", "type": "object",
                  "children": [
                      {"path": "$.box.a", "state": "form", "type": "string"},
                  ]}
        out = validate_field_states([broken])
        assert [e["code"] for e in out["errors"]] == ["tree_inconsistency"]

    def test_required_carry_soft_warning(self) -> None:
        """§7⑤-2 required 落 carry 软警告(增量划出 or 共识默认即在)。"""
        out = validate_field_states([_REQUIRED_LEAF],
                                    {"$.order_no": "carry"})
        assert out["errors"] == []
        assert [w["code"] for w in out["warnings"]] == ["required_carry"]
        assert out["warnings"][0]["path"] == "$.order_no"

    def test_descriptive_form_soft_warning(self) -> None:
        """§7⑤-3 DESCRIPTIVE 进 form 面 → 提示;collapse 不触发
        (折叠区非直接渲染面)。"""
        out = validate_field_states([_DESCRIPTIVE_LEAF])
        assert [w["code"] for w in out["warnings"]] == ["descriptive_form"]
        out = validate_field_states([_COLLAPSE_DESCRIPTIVE])
        assert out["warnings"] == []
        out = validate_field_states(
            [_DESCRIPTIVE_LEAF], {"$.remark": "carry"})
        assert out["warnings"] == []

    def test_stale_path_soft_warning(self) -> None:
        """§3.4 交集容忍:目录外 path 忽略但可见(stale 警告)。"""
        out = validate_field_states(
            [_TOP_FORM_LEAF], {"$.ghost": "carry", "$.gone.form": "form"})
        assert [w["code"] for w in out["warnings"]] == ["stale_path", "stale_path"]
        assert [w["path"] for w in out["warnings"]] == ["$.ghost", "$.gone.form"]

    def test_garbage_tolerated(self) -> None:
        """垃圾输入零崩溃:decls 非 list / field_states 非 dict → 干净通过。"""
        assert validate_field_states(None) == {"errors": [], "warnings": []}
        assert validate_field_states([_TOP_FORM_LEAF], "junk") == (
            {"errors": [], "warnings": []})


# ── §3.5 校验 API 面:POST /endpoint-catalog/{id}/field-states/validate ──

_VALIDATE_DECLS = [
    {"name": "supplier", "path": "$.supplier", "state": "carry",
     "type": "array", "children": [
         {"name": "supplier_id", "path": "$.supplier.order_supplier_id",
          "state": "carry", "type": "string"},
     ]},
    {"name": "order_no", "path": "$.order_no", "state": "form",
     "type": "string", "required": True},
    {"name": "remark", "path": "$.remark", "state": "carry",
     "type": "string"},
]


async def test_validate_route_returns_verdicts(client, plate) -> None:
    """校验端点全链路:plate /full 目录 + 增量 → errors/warnings 裁决
    (合成态树一致性拒 + required_carry 软警告)。"""
    plate.fulls = {"fin.settlement.create_order":
                   {"request": {"declarations": _VALIDATE_DECLS}}}
    headers = await register_and_login(client)
    r = await client.post(
        "/api/endpoint-catalog/fin.settlement.create_order"
        "/field-states/validate",
        headers=headers,
        json={"field_states": {
            "$.supplier.order_supplier_id": "form",   # 树一致性 → error
            "$.order_no": "carry",                     # required → warning
        }})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [e["code"] for e in body["errors"]] == ["tree_inconsistency"]
    assert [w["code"] for w in body["warnings"]] == ["required_carry"]


async def test_validate_route_clean_pass(client, plate) -> None:
    plate.fulls = {"fin.settlement.create_order":
                   {"request": {"declarations": _VALIDATE_DECLS}}}
    headers = await register_and_login(client)
    r = await client.post(
        "/api/endpoint-catalog/fin.settlement.create_order"
        "/field-states/validate",
        headers=headers, json={"field_states": {}})
    assert r.status_code == 200, r.text
    assert r.json() == {"errors": [], "warnings": []}


async def test_validate_route_unknown_endpoint_404(client, plate) -> None:
    plate.fulls = {}
    headers = await register_and_login(client)
    r = await client.post(
        "/api/endpoint-catalog/fin.nope/field-states/validate",
        headers=headers, json={"field_states": {}})
    assert r.status_code == 404, r.text
