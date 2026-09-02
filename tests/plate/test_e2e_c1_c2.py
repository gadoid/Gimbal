"""端到端:C1 结构定义 → Registry → C2 用例导出。"""
from __future__ import annotations

from tests.plate.fixtures.sample_endpoint import make_sample_endpoint
from gimbal_plate import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
    registry,
)


def test_end_to_end_c1_c2() -> None:
    # 1. C1:构造 EndpointSpec
    ep = make_sample_endpoint()
    assert ep.system == "sample"
    assert ep.service == "order"
    assert ep.api.method == "POST"
    # P2 存储翻转:断言面 = view_only 条目的 assertable 旗标
    (order_id,) = [e for e in ep.responses[200].declarations
                   if e.name == "order_id"]
    assert order_id.channel == "view_only" and order_id.assertable is True

    # 2. 注册
    registry.reset()
    registry.register_endpoint(ep)
    assert registry.has_endpoint(ep.id)
    assert registry.list_systems() == ["sample"]
    assert [s.name for s in registry.list_services(system="sample")] == ["order"]

    # 3. 多维度查询
    found = registry.find_endpoints(
        service=ep.api.service,
        method=ep.api.method,
        path=ep.api.path,
    )
    assert [e.id for e in found] == [ep.id]

    # 4. C2:构造数据驱动用例并导出
    cases = [
        EndpointCase(
            name=f"run-{i}",
            parameters={"order_no": f"R-{i:03d}", "amount": i * 10.0},
            expected={"status_code": 200, "assertions": [
                {"target": "$.response_body.order_id", "operator": "exists"},
            ]},
        )
        for i in range(1, 4)
    ]
    dataset = EndpointCaseDataset(endpoint_id=ep.id, cases=cases)
    exporter = EndpointCaseExporter(ep)
    steps = exporter.to_gimbal_scenario_steps(dataset)

    # 5. 断言:每个 step 都是合法的 gimbal.Step 形态 dict
    assert len(steps) == 3
    for i, step in enumerate(steps, start=1):
        assert step["kind"] == "step"
        assert step["api"]["kind"] == "api"
        assert step["request"]["kind"] == "request"
        assert step["request"]["body"]["order_no"] == f"R-{i:03d}"
        assert step["request"]["body"]["amount"] == i * 10.0
        # strategy 至少包含 status_check + 1 个断言
        assert len(step["strategy"]) == 2
        assert step["strategy"][0]["target"] == "response.status"
        assert step["strategy"][0]["expected"] == 200

    # 6. 序列化:基于 version 的语义等价断言(详见 ENDPOINT_SPEC_V1.md §2.3)。
    # 不做字节级 round-trip;updated_at 不参与断言。
    data = ep.model_dump(mode="json")
    assert data["version"] == "1.0.0"
    assert data["id"] == ep.id
    assert data["api"]["method"] == "POST"
    assert "schema" in data["request"]
    assert "model_schema" not in data["request"]
    assert "schema" in data["responses"]["200"]
    assert "model_schema" not in data["responses"]["200"]
