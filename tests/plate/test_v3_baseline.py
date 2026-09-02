"""V3 阶段 0:基线测试 —— 验证现有 schema/endpoint、schema/(扁平后),export/gimbal 的现状。

目的:V3 不修改这三处,只确认它们能 import / 实例化 / 序列化。这是后续阶段
验证"未引入回归"的对照基线。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import BaseModel

from gimbal_plate.export.gimbal import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
)
from gimbal_plate.schema import (
    ApiSpec,
    Config,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    Meta,
    RequestSpec,
    ResponseSpec,
    Scenario,
    Step,
)


class _SampleIn(BaseModel):
    order_id: str


class _SampleOut(BaseModel):
    order_id: str
    status: str


@pytest.fixture
def sample_endpoint() -> EndpointSpec:
    return EndpointSpec(
        id="baseline.sample.endpoint",
        system="baseline",
        service="sample",
        name="基线样例",
        api=ApiSpec(service="sample", method="GET", path="/baseline/sample"),
        request=RequestSpec(body_type="json", schema_=_SampleIn.model_json_schema()),
        responses={200: ResponseSpec(status=200, schema_=_SampleOut.model_json_schema())},
        version="1.0.0",
    )


def _meta_full(name: str = "baseline") -> Meta:
    """Meta 的 createTime / expire / requirementRef 是必填字段,这里集中构造。"""
    return Meta(
        name=name,
        description="baseline meta",
        module="baseline",
        priority=1,
        author="tester",
        owner="tester",
        tags=["baseline"],
        version="1.0.0",
        createTime=datetime(2026, 8, 4, 0, 0, 0),
        expire=False,
        requirementRef=[],
    )


class TestSchemaEndpointImportable:
    """schema/endpoint/* 全部可 import 并实例化。"""

    def test_endpoint_spec_instantiable(self, sample_endpoint: EndpointSpec) -> None:
        assert sample_endpoint.id == "baseline.sample.endpoint"
        assert sample_endpoint.system == "baseline"
        assert sample_endpoint.version == "1.0.0"

    def test_endpoint_spec_dump_contains_response_schema(
        self, sample_endpoint: EndpointSpec
    ) -> None:
        # RequestSpec / ResponseSpec 的 @model_serializer 输出 declarations /
        # schema(P2 存储翻转后 IO 节点与 wire 同形)。
        # 测试只校验 dump 出来的结构里我们填的关键字段都在。
        dumped = sample_endpoint.model_dump(mode="json")
        assert dumped["id"] == "baseline.sample.endpoint"
        assert dumped["api"]["path"] == "/baseline/sample"
        resp_200 = dumped["responses"]["200"]
        assert "schema" in resp_200
        assert resp_200["schema"]["title"] == "_SampleOut"


class TestSchemaInterfaceImportable:
    """schema/(扁平化后)Step/Config/Meta 等接口类型 全部可 import 并实例化。"""

    def test_meta_instantiable(self) -> None:
        m = _meta_full()
        assert m.name == "baseline"

    def test_config_instantiable(self) -> None:
        c = Config()
        assert c.services == {}
        assert c.users == {}
        assert c.vars == {}

    def test_step_instantiable(self) -> None:
        from gimbal_plate.schema import Api, Request

        s = Step(
            api=Api(service="sample", method="GET", path="/baseline/sample"),
            request=Request(),
        )
        assert s.api.service == "sample"


class TestCaseExporterImportable:
    """case/exporter.py 核心类型可 import 且基本翻译方法可用。"""

    def test_exporter_to_gimbal_step(
        self, sample_endpoint: EndpointSpec
    ) -> None:
        exporter = EndpointCaseExporter(endpoint=sample_endpoint)
        case = EndpointCase(name="baseline-case", parameters={"order_id": "x"})
        step_dict = exporter.to_gimbal_step(case)
        assert step_dict["kind"] == "step"
        assert step_dict["api"]["path"] == "/baseline/sample"
        assert step_dict["request"]["kind"] == "request"
