"""ApiSpec.protocol 判别字段（P1，2026-09-27 协议中立化）。

覆盖：
  - 默认值 "http"，存量端点零迁移；
  - is_http 分派守卫；
  - EndpointDetailView（strict 镜像）携带 protocol —— 前端契约变更必须响亮；
  - by_route 三元组索引只对 http 端点生效（分派纪律守卫）；
  - gimbal 侧 Call 开放模型与 plate 端点协议声明的对齐（http 字段直通）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "src" / "gimbal-plate"
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from gimbal_plate import ApiSpec, EndpointSpec
from gimbal_plate.registry import PlateRegistry


def _endpoint(protocol: str = "http", service: str = "svc", path: str = "/x") -> EndpointSpec:
    api = ApiSpec(service=service, method="GET", path=path, protocol=protocol)
    return EndpointSpec(
        id=f"sys.{service}.ep",
        system="sys",
        service=service,
        name="ep",
        api=api,
        request=RequestSpec(body_type="none"),
        responses={200: ResponseSpec(status=200)},
        metadata=EndpointMetadata(module="m"),
    )


from gimbal_plate import EndpointMetadata, RequestSpec, ResponseSpec  # noqa: E402


class TestApiSpecProtocol:
    def test_default_is_http(self):
        spec = ApiSpec(service="s", method="GET", path="/p")
        assert spec.protocol == "http"
        assert spec.is_http is True

    def test_non_http_allowed_and_guard(self):
        spec = ApiSpec(service="s", method="GET", path="/p", protocol="grpc")
        assert spec.protocol == "grpc"
        assert spec.is_http is False

    def test_endpoint_detail_view_carries_protocol(self):
        from gimbal_plate.http.views import EndpointDetailView
        view = EndpointDetailView.from_spec(_endpoint("http"))
        assert view.api.protocol == "http"

    def test_by_route_only_indexes_http(self):
        reg = PlateRegistry()
        http_ep = _endpoint("http", service="a", path="/h")
        grpc_ep = _endpoint("grpc", service="b", path="/g")
        reg.register_endpoint(http_ep)
        reg.register_endpoint(grpc_ep)

        assert reg.find_endpoints("a", "GET", "/h") == [http_ep]
        # 非 http 端点不进 http 路由三元组索引
        assert reg.find_endpoints("b", "GET", "/g") == []
        # 但 by_id / by_service 维度不受影响
        assert reg.get_endpoint(grpc_ep.id) is not None

    def test_gimbal_call_aligns_with_plate_protocol(self):
        _gimbal_root = Path(__file__).resolve().parents[2] / "src"
        if str(_gimbal_root) not in sys.path:
            sys.path.insert(0, str(_gimbal_root))
        from gimbal.schema.call import Call

        api = ApiSpec(service="s", method="POST", path="/p", protocol="http")
        # gimbal Call 开放字段直通 http 坐标，protocol 与 plate 判别字段同名同值
        call = Call(protocol=api.protocol, service=api.service,
                    method=api.method, path=api.path)
        assert call.protocol == "http"
        assert call.service == "s" and call.path == "/p"
