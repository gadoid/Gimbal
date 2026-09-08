"""目录级校验 ①②⑥ + 索引投影(spec §3.3 聚合层 / §3.4)。"""
import pytest

from gimbal_plate.schema.endpoint import (
    ApiSpec, EndpointMetadata, EndpointSpec, RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry
from gimbal_plate.schema.endpoint.query_view import QueryView, ValueSource
from gimbal_plate.service.query_views import build_query_view_index, validate_query_view_catalog


def _ep(eid, *, views=None, binds=None, method="GET", query_safe=False):
    decls = [
        DeclarationEntry(name=b["path"].strip("$.") or "root", path=b["path"],
                         type="string", value_source=ValueSource(view=b["view"],
                                 column=b.get("column", ""),
                                 group=b.get("group", "")))
        for b in (binds or [])
    ]
    return EndpointSpec(
        id=eid, system="t", service="svc", name=eid,
        api=ApiSpec(service="svc", method=method, path=f"/api/{eid}"),
        request=RequestSpec(declarations=decls) if decls else None,
        responses={200: ResponseSpec(status=200)},
        metadata=EndpointMetadata(query_safe=query_safe),
        query_views=views,
    )


VIEW = QueryView(name="v1", items="$.data[*]", label="nm")
VIEW2 = QueryView(name="v2", items="$.rows[*]", label="code")


class TestValidate:
    def test_ok_multi_endpoint(self):
        validate_query_view_catalog([
            _ep("t.a", views=[VIEW], binds=[{"path": "$.x", "view": "v1"}]),
            _ep("t.b", views=[VIEW2], binds=[{"path": "$.y", "view": "v2",
                                              "group": "v2#r"}]),
        ])

    def test_dup_view_name_rejected(self):  # ①
        with pytest.raises(ValueError, match="重复"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW]),
                _ep("t.b", views=[QueryView(name="v1", items="$.z[*]", label="q")]),
            ])

    def test_dangling_reference_rejected(self):  # ②
        with pytest.raises(ValueError, match="未命中"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW], binds=[{"path": "$.x", "view": "v9"}]),
            ])

    def test_group_mixes_views_rejected(self):  # ⑥ 显式
        with pytest.raises(ValueError, match="分组一致性"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW, VIEW2], binds=[
                    {"path": "$.x", "view": "v1", "group": "g"},
                    {"path": "$.y", "view": "v2", "group": "g"},
                ]),
            ])

    def test_explicit_group_collides_with_default_group_rejected(self):  # ⑥ 显式×缺省撞名
        with pytest.raises(ValueError, match="分组一致性"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW, VIEW2], binds=[
                    {"path": "$.x", "view": "v2", "group": "v1"},   # 显式 v1 组
                    {"path": "$.y", "view": "v1"},                  # 缺省组也叫 v1
                ]),
            ])

    def test_deep_tree_binding_seen(self):  # 绑定在 children 树内也要被扫描
        deep = DeclarationEntry(name="obj", path="$.obj", type="object", children=[
            DeclarationEntry(name="leaf", path="$.obj.leaf", type="string",
                             value_source=ValueSource(view="v9")),   # 悬空引用:树内绑定不可见则漏检
        ])
        ep = EndpointSpec(
            id="t.d", system="t", service="svc", name="d",
            api=ApiSpec(service="svc", method="GET", path="/api/d"),
            request=RequestSpec(declarations=[deep]),
            responses={200: ResponseSpec(status=200)},
            query_views=[VIEW],
        )
        with pytest.raises(ValueError, match="未命中"):
            validate_query_view_catalog([ep])   # 树内悬空引用必须被 ② 拒


class TestIndex:
    def test_projection_shape(self):
        eps = [
            _ep("t.a", views=[VIEW], binds=[
                {"path": "$.x", "view": "v1", "column": "id", "group": "v1#g1"},
                {"path": "$.y", "view": "v1", "column": "id", "group": "v1#g2"},
            ]),
        ]
        rows = build_query_view_index(eps)
        assert len(rows) == 1
        r = rows[0]
        assert r["name"] == "v1" and r["endpoint_id"] == "t.a"
        assert r["method"] == "GET" and r["path"] == "/api/t.a"
        assert r["columns"] == ["nm", "id"]        # label ∪ 绑定列,有序去重
        assert r["query_safe"] is False and r["missing_required"] == []
        assert r["auth"] == "none" and r["timeout_seconds"] == 30.0

    def test_sorted_deterministic(self):
        rows = build_query_view_index([_ep("t.b", views=[VIEW2]),
                                       _ep("t.a", views=[VIEW])])
        assert [r["name"] for r in rows] == ["v1", "v2"]

    def test_merged_params_from_declarations(self):
        ep = _ep("t.a", views=[QueryView(name="v1", params={"k": 9},
                                         items="$.d[*]", label="nm")],
                 binds=[{"path": "$.x", "view": "v1"}])
        # 重新构造带声明缺省的端点
        from gimbal_plate.schema.endpoint import EndpointSpec
        decls = [DeclarationEntry(name="page", path="page", type="integer",
                                  required=True, example=7),
                 DeclarationEntry(name="x", path="$.x", type="string",
                                  value_source=ValueSource(view="v1"))]
        ep2 = EndpointSpec(id="t.a", system="t", service="svc", name="a",
                           api=ApiSpec(service="svc", method="GET", path="/api/a"),
                           request=RequestSpec(declarations=decls),
                           responses={200: ResponseSpec(status=200)},
                           query_views=ep.query_views)
        (r,) = build_query_view_index([ep2])
        assert r["params"] == {"k": 9, "page": 7}
