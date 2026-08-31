"""A5: field default suggestions for the field editor (M6 grammar).

M6 mapping (ADR 0002 §D1):
    GET /api/endpoints/{id}/field-defaults
        → GET /api/endpoint/{id}/action/field-defaults
"""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel

from gimbal_plate.http import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.fin.dimensions import register_fin_dims
from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import (
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.endpoint.api_spec import ApiSpec


class _ReqIn(BaseModel):
    client_expand_name: str
    bl_no: str
    etd: str
    supplier: str


class _RespOut(BaseModel):
    code: int
    msg: str


def _build_endpoint() -> EndpointSpec:
    return EndpointSpec(
        id="sample.fields",
        system="sample",
        service="sample-svc",
        name="sample",
        api=ApiSpec(service="sample-svc", method="POST", path="/sample/fields"),
        request=RequestSpec(
            body_type="json",
            schema_=_ReqIn.model_json_schema(),
            fields=[
                IOFieldBinding(
                    name="client_expand_name",
                    path="$.client_expand_name",
                    example="张三",
                ),
                IOFieldBinding(
                    name="bl_no",
                    path="$.bl_no",
                    example="${var.bl_no}",
                ),
                IOFieldBinding(
                    name="supplier",
                    path="$.supplier",
                    example="${auth.codfish.suppliers}",
                    source_kind="lookup",
                ),
                IOFieldBinding(
                    name="etd",
                    path="$.etd",
                    example="auto · date policy",
                    source_kind="generated",
                    ui_kind="number",
                ),
            ],
        ),
        responses={200: ResponseSpec(status=200, schema_=_RespOut.model_json_schema(), fields=[])},
        version="1.0.0",
    )


def _client() -> TestClient:
    reg = PlateRegistry()
    reg.register_endpoint(_build_endpoint())
    # M6 grammar — wire endpoint dim (only endpoint is needed for field-defaults).
    register_fin_dims(reg)
    return TestClient(create_app(registry=reg))


def test_field_defaults_kinds() -> None:
    with _client() as client:
        resp = client.get("/api/endpoint/sample.fields/action/field-defaults")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "endpoint"
    data: dict[str, Any] = body["data"]
    by_name = {f["name"]: f for f in data["field_defaults"]}
    assert by_name["client_expand_name"]["kind"] == "literal"
    assert by_name["client_expand_name"]["value"] == "张三"
    assert by_name["bl_no"]["kind"] == "scenario_var"
    assert by_name["supplier"]["kind"] == "auth_placeholder"
    assert by_name["etd"]["kind"] == "generated"
    assert data["carry_fields"] == []


def test_field_defaults_carry_fields_from_response() -> None:
    endpoint = _build_endpoint()
    endpoint.responses[200].fields = [
        IOFieldBinding(
            name="internal_note",
            path="$.internal_note",
            source_kind="generated",
            ui_kind="text",
        )
    ]
    reg = PlateRegistry()
    reg.register_endpoint(endpoint)
    register_fin_dims(reg)
    with TestClient(create_app(registry=reg)) as client:
        resp = client.get("/api/endpoint/sample.fields/action/field-defaults")
    assert resp.status_code == 200
    carry = resp.json()["data"]["carry_fields"]
    assert carry and carry[0]["name"] == "internal_note"
    assert carry[0]["carry"] is True