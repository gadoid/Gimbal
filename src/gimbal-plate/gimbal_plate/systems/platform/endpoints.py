"""加载 endpoints.json → EndpointSpec[]。

JSON 是契约真源，由 gimbal-bootstrap/gimbal_bootstrap/contract_gen.py 从
平台 OpenAPI 生成。本模块只加载，不含生成逻辑 —— plate 不认识生成器。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)

_DATA: Final[dict[str, Any]] = json.loads(
    (Path(__file__).with_name("endpoints.json")).read_text(encoding="utf-8")
)


def _declarations(raw: list[dict[str, Any]]) -> list[DeclarationEntry]:
    out: list[DeclarationEntry] = []
    for d in raw:
        children = d.get("children")
        out.append(
            DeclarationEntry(
                name=d["name"],
                path=d["path"],
                type=d["type"],
                description=d.get("description", ""),
                assertable=bool(d.get("assertable", False)),
                children=_declarations(children) if children else None,
            )
        )
    return out


def _endpoint(raw: dict[str, Any]) -> EndpointSpec:
    api = raw["api"]
    return EndpointSpec(
        id=raw["id"],
        system=raw["system"],
        service=raw["service"],
        name=raw["name"],
        description=raw.get("description", ""),
        api=ApiSpec(
            protocol=api.get("protocol", "http"),
            service=api["service"],
            method=api["method"],
            path=api["path"],
            timeout_seconds=api.get("timeout_seconds", 30.0),
            auth=api.get("auth", "none"),
            produces=api.get("produces", ["application/json"]),
            consumes=api.get("consumes", ["application/json"]),
        ),
        request=RequestSpec(
            body_type=raw["request"].get("body_type", "none"),
            declarations=_declarations(raw["request"].get("declarations", [])),
        ),
        responses={
            int(status): ResponseSpec(
                status=int(status),
                description=spec.get("description", ""),
                declarations=_declarations(spec.get("declarations", [])),
            )
            for status, spec in raw["responses"].items()
        },
        metadata=EndpointMetadata(**raw.get("metadata", {})),
        version=raw.get("version", "1.0.0"),
    )


ALL_PLATFORM_ENDPOINTS: Final[list[EndpointSpec]] = [
    _endpoint(e) for e in _DATA["endpoints"]
]
