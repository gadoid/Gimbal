"""B2: failed_criteria × assertable_fields linkage analysis (M6 grammar).

M6 mapping (ADR 0002 §D1):
    POST /api/endpoints/{id}/failed-criteria-resolved
        → POST /api/endpoint/{id}/action/failed-criteria
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel

from gimbal_plate.http import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.fin.dimensions import register_fin_dims
from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding, RequestSpec, ResponseSpec
from gimbal_plate.schema.endpoint.api_spec import ApiSpec
from gimbal_plate.schema.endpoint.metadata import EndpointMetadata


class _Req(BaseModel):
    placeholder: str


class _Out(BaseModel):
    code: int
    msg: str


def _build_endpoint() -> EndpointSpec:
    return EndpointSpec(
        id="sample.failed",
        system="sample",
        service="sample-svc",
        name="sample",
        api=ApiSpec(service="sample-svc", method="POST", path="/sample/failed"),
        request=RequestSpec(body_type="json", schema_=_Req.model_json_schema()),
        responses={
            200: ResponseSpec(
                status=200,
                schema_=_Out.model_json_schema(),
                fields=[IOFieldBinding(name="code", path="$.code", required=True)],
                assertable_fields=["$.code"],
            )
        },
        metadata=EndpointMetadata(
            failed_criteria=[
                "401 未登录 → $.code = 10001",
                "403 无权限 → $.code = 10003",
                "422 客户不存在",
            ]
        ),
        version="1.0.0",
    )


def test_failed_criteria_resolved() -> None:
    reg = PlateRegistry()
    reg.register_endpoint(_build_endpoint())
    register_fin_dims(reg)
    with TestClient(create_app(registry=reg)) as client:
        resp = client.post(
            "/api/endpoint/sample.failed/action/failed-criteria",
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    items = body["data"]["failed_criteria"]
    assert len(items) == 3
    by_code = {it["code"]: it for it in items}
    assert by_code[401]["assertable"] is True
    assert by_code[401]["field"] == "$.code"
    assert by_code[403]["assertable"] is True
    # The third line has no $.code reference, so it must be non-assertable.
    assert by_code[422]["assertable"] is False
    assert by_code[422]["field"] is None