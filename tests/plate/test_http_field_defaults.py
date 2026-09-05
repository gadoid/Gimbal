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
    DeclarationEntry,
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
            declarations=[
                DeclarationEntry(
                    name="client_expand_name",
                    path="$.client_expand_name", type='string',
                    example="张三",
                ),
                DeclarationEntry(
                    name="bl_no",
                    path="$.bl_no", type='string',
                    example="${var.bl_no}",
                ),
                DeclarationEntry(
                    name="supplier",
                    path="$.supplier", type='string',
                    example="${auth.codfish.suppliers}",
                    source_kind="lookup",
                ),
                DeclarationEntry(
                    name="etd",
                    path="$.etd", type='string',
                    example="auto · date policy",
                    source_kind="generated",
                    ui_kind="number",
                ),
            ],
        ),
        responses={200: ResponseSpec.declare(_RespOut, status=200)},
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
    assert data["generated_fields"] == []


def test_field_defaults_generated_fields_from_response() -> None:
    endpoint = _build_endpoint()
    # P2 存储翻转:改声明面 = 整替 ResponseSpec 的 declarations
    endpoint.responses[200] = ResponseSpec(
        status=200,
        declarations=[
            DeclarationEntry(
                name="internal_note",
                path="$.internal_note", type='string',
                source_kind="generated",
                ui_kind="text",
            )
        ],
    )
    reg = PlateRegistry()
    reg.register_endpoint(endpoint)
    register_fin_dims(reg)
    with TestClient(create_app(registry=reg)) as client:
        resp = client.get("/api/endpoint/sample.fields/action/field-defaults")
    assert resp.status_code == 200
    generated = resp.json()["data"]["generated_fields"]
    assert generated and generated[0]["name"] == "internal_note"
    assert generated[0]["generated"] is True
