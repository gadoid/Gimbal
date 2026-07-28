"""EndpointSpec 与子模型字段、约束、校验、序列化测试。"""
from __future__ import annotations

from datetime import datetime

import pytest

from gimbal_plate import ApiSpec, EndpointMetadata, EndpointSpec, RequestSpec, ResponseSpec


class TestApiSpec:
    def test_minimal(self) -> None:
        api = ApiSpec(service="svc", method="POST", path="/x")
        assert api.service == "svc"
        assert api.timeout_seconds == 30.0
        assert api.auth == "none"
        assert api.produces == ["application/json"]

    def test_invalid_method_rejected(self) -> None:
        with pytest.raises(Exception):
            ApiSpec(service="svc", method="INVALID", path="/x")

    def test_path_must_start_with_slash(self) -> None:
        with pytest.raises(Exception):
            ApiSpec(service="svc", method="GET", path="no-slash")


class TestIOSpec:
    def test_request_spec_no_body(self) -> None:
        req = RequestSpec(body_type="none")
        assert req.model is None
        assert req.schema_ is None
        assert req.json_schema() is None

    def test_response_status_range(self) -> None:
        with pytest.raises(Exception):
            ResponseSpec(status=99)
        with pytest.raises(Exception):
            ResponseSpec(status=600)


class TestEndpointSpec:
    def test_construct(self, order_endpoint) -> None:
        ep = order_endpoint
        assert ep.id == "settlement.order.add"
        assert ep.system == "finas"
        assert ep.service == "settlement"
        assert ep.api.service == "settlement"
        assert ep.responses[200].model is not None
        assert ep.metadata.priority == 1

    def test_id_required(self) -> None:
        with pytest.raises(Exception):
            EndpointSpec(
                id="",
                system="x",
                service="x",
                name="x",
                api=ApiSpec(service="x", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_id_pattern(self) -> None:
        with pytest.raises(Exception):
            EndpointSpec(
                id="BadID",  # 大写
                system="x",
                service="x",
                name="x",
                api=ApiSpec(service="x", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_service_must_match_api(self) -> None:
        with pytest.raises(Exception):
            EndpointSpec(
                id="svc.x",
                system="sys",
                service="svc1",
                name="x",
                api=ApiSpec(service="svc2", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_200_required(self) -> None:
        with pytest.raises(Exception):
            EndpointSpec(
                id="svc.x",
                system="sys",
                service="svc",
                name="x",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={400: ResponseSpec(status=400)},
            )

    def test_extra_forbid(self) -> None:
        with pytest.raises(Exception):
            EndpointSpec(
                id="svc.x",
                system="sys",
                service="svc",
                name="x",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
                unknown_field="nope",
            )

    def test_updated_at_default(self, order_endpoint) -> None:
        # 构造时已自动填 updated_at
        assert order_endpoint.updated_at is not None
        assert isinstance(order_endpoint.updated_at, datetime)


class TestEndpointMetadata:
    def test_priority_range(self) -> None:
        EndpointMetadata(priority=1)
        EndpointMetadata(priority=3)
        EndpointMetadata(priority=None)
        with pytest.raises(Exception):
            EndpointMetadata(priority=4)


class TestSerialization:
    """序列化语义等价校验:基于 ``version`` 字段;``updated_at`` 不参与断言。

    详见 [ENDPOINT_SPEC_V1.md §2.3](../src/gimbal-plate/gimbal_plate/design/ENDPOINT_SPEC_V1.md)。
    """

    # 同版本下需断言语义相等的字段子集(仅稳定字段,不含 updated_at)。
    _SEMANTIC_KEYS = (
        "id", "system", "service", "name", "description",
        "api.method", "api.path", "api.timeout_seconds", "api.auth",
        "responses.200.status", "responses.200.assertable_fields",
        "metadata.module", "metadata.priority", "metadata.owner", "metadata.tags",
        "version",
    )

    @staticmethod
    def _project(data: dict, path: str):
        cur = data
        for seg in path.split("."):
            cur = cur[seg]
        return cur

    def test_model_dump_json_carries_key_fields(self, order_endpoint) -> None:
        # JSON 模式需要把 class 字段显式 dump 成 schema。
        # 这里验证关键字段都能 JSON 化,且 model_schema / model_name 出现在 IO 节点上。
        data = order_endpoint.model_dump(mode="json")
        assert data["id"] == "settlement.order.add"
        assert data["api"]["method"] == "POST"
        assert data["responses"]["200"]["status"] == 200
        assert "model_schema" in data["request"]
        assert data["request"]["model_name"] == "OrderIn"
        assert "model_schema" in data["responses"]["200"]
        assert data["responses"]["200"]["model_name"] == "OrderOut"

    def test_version_based_semantic_equivalence(self, order_endpoint) -> None:
        # 校验基准:同 version 下,关键字段语义等价;updated_at / 调试派生字段不参与。
        dump1 = order_endpoint.model_dump(mode="json")
        # dump2 走另一条路径(构造一个语义等价的副本,显式制造时间字段差异)
        ep2 = order_endpoint.model_copy(deep=True)
        ep2.updated_at = datetime(2000, 1, 1, 0, 0, 0)
        dump2 = ep2.model_dump(mode="json")
        # 1) 调试字段允许不同(且不影响关键字段)
        assert dump1["updated_at"] != dump2["updated_at"]
        # 2) version 与关键字段全部相等
        for path in self._SEMANTIC_KEYS:
            assert self._project(dump1, path) == self._project(dump2, path), path
        # 3) 序列化字符串不强求逐字节相等(updated_at 差异使其必然不等)
        import json as _json
        s1 = _json.dumps(dump1, sort_keys=True)
        s2 = _json.dumps(dump2, sort_keys=True)
        assert s1 != s2  # updated_at 改了 ⇒ 字符串必然不同


class TestVersion:
    """锁定 ``EndpointSpec.version`` 的初始基线与序列化版本字段。"""

    def test_version_default_is_1_0_0(self) -> None:
        ep = EndpointSpec(
            id="svc.x",
            system="sys",
            service="svc",
            name="x",
            api=ApiSpec(service="svc", method="GET", path="/x"),
            responses={200: ResponseSpec(status=200)},
        )
        assert ep.version == "1.0.0"

    def test_version_serialized_into_dump(self, order_endpoint) -> None:
        data = order_endpoint.model_dump(mode="json")
        assert data["version"] == "1.0.0"

    def test_version_preserved_under_explicit_override(self) -> None:
        ep = EndpointSpec(
            id="svc.x",
            system="sys",
            service="svc",
            name="x",
            version="1.2.3",
            api=ApiSpec(service="svc", method="GET", path="/x"),
            responses={200: ResponseSpec(status=200)},
        )
        assert ep.version == "1.2.3"
        assert ep.model_dump(mode="json")["version"] == "1.2.3"

    def test_version_not_compared_for_byte_equality(self, order_endpoint) -> None:
        # 两次 dump 不强求字节相同,但 version 必须保留为同版本。
        import json as _json
        d1 = order_endpoint.model_dump(mode="json")
        d2 = order_endpoint.model_dump(mode="json")
        # 时间字段经 Pydantic 序列化往返可能产生纳秒级截断,dump1 / dump2 可能不同。
        # 这里重点是验证两条 dump 的 version 与关键字段语义等价。
        assert d1["version"] == d2["version"] == "1.0.0"
        for path in TestSerialization._SEMANTIC_KEYS:
            assert TestSerialization._project(d1, path) == TestSerialization._project(d2, path), path
        # 显式确认:version 字段本身在两条 dump 中字符串相等。
        assert _json.dumps(d1["version"]) == _json.dumps(d2["version"])
