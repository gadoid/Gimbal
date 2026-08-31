"""EndpointCaseExporter C2 端到端测试。"""
from __future__ import annotations

import pytest

from gimbal_plate import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
)


class TestSingleStep:
    def test_basic_step(self, order_endpoint) -> None:
        case = EndpointCase(
            name="正常下单",
            parameters={"order_no": "ORD-001", "amount": 99.9},
            expected={"status_code": 200, "assertions": [
                {"target": "$.response_body.order_id", "operator": "exists"},
            ]},
        )
        exporter = EndpointCaseExporter(order_endpoint)
        step = exporter.to_gimbal_step(case)

        assert step["kind"] == "step"
        assert step["description"] == "正常下单"
        # api
        api = step["api"]
        assert api["kind"] == "api"
        assert api["service"] == "settlement"
        assert api["method"] == "POST"
        assert api["path"] == "/api/v1/orders"
        assert api["timeout"] == 30
        # request
        req = step["request"]
        assert req["kind"] == "request"
        assert req["body"] == {"order_no": "ORD-001", "amount": 99.9}
        # strategy: status_check + assertion
        assert len(step["strategy"]) == 2
        s0 = step["strategy"][0]
        assert s0["kind"] == "assertion"
        assert s0["target"] == "response.status"
        assert s0["expected"] == 200
        s1 = step["strategy"][1]
        assert s1["target"] == "$.response_body.order_id"
        assert s1["operator"] == "exists"

    def test_step_without_status_check(self, order_endpoint) -> None:
        case = EndpointCase(
            name="no_status",
            parameters={"order_no": "X", "amount": 1},
            expected={"assertions": []},
        )
        exporter = EndpointCaseExporter(order_endpoint)
        step = exporter.to_gimbal_step(case)
        # 仅期望断言列表,无 status_check
        assert step["strategy"] == []

    def test_step_invalid_operator_rejected(self, order_endpoint) -> None:
        case = EndpointCase(
            name="bad_op",
            parameters={"order_no": "X", "amount": 1},
            expected={"assertions": [
                {"target": "x", "operator": "totally_bogus"},
            ]},
        )
        exporter = EndpointCaseExporter(order_endpoint)
        with pytest.raises(ValueError):
            exporter.to_gimbal_step(case)


class TestDataset:
    def test_dataset_to_steps(self, order_endpoint) -> None:
        cases = [
            EndpointCase(name="c1", parameters={"order_no": "A", "amount": 1}),
            EndpointCase(name="c2", parameters={"order_no": "B", "amount": 2}),
        ]
        dataset = EndpointCaseDataset(
            endpoint_id=order_endpoint.id,
            cases=cases,
        )
        exporter = EndpointCaseExporter(order_endpoint)
        steps = exporter.to_gimbal_scenario_steps(dataset)
        assert len(steps) == 2
        assert steps[0]["request"]["body"]["order_no"] == "A"
        assert steps[1]["request"]["body"]["order_no"] == "B"

    def test_dataset_endpoint_id_mismatch(self, order_endpoint) -> None:
        dataset = EndpointCaseDataset(endpoint_id="wrong", cases=[])
        exporter = EndpointCaseExporter(order_endpoint)
        with pytest.raises(ValueError):
            exporter.to_gimbal_scenario_steps(dataset)

    def test_dataset_variables_applied(self, order_endpoint) -> None:
        case = EndpointCase(
            name="var_test",
            parameters={"order_no": "${prefix}-001", "amount": 1},
        )
        dataset = EndpointCaseDataset(
            endpoint_id=order_endpoint.id,
            cases=[case],
            variables={"prefix": "RUN"},
        )
        exporter = EndpointCaseExporter(order_endpoint)
        steps = exporter.to_gimbal_scenario_steps(dataset)
        assert steps[0]["request"]["body"]["order_no"] == "RUN-001"

    def test_scenario_dict_shape(self, order_endpoint) -> None:
        case = EndpointCase(name="c1", parameters={"order_no": "A", "amount": 1})
        dataset = EndpointCaseDataset(endpoint_id=order_endpoint.id, cases=[case])
        exporter = EndpointCaseExporter(order_endpoint)
        sd = exporter.to_gimbal_scenario_dict(dataset, scenario_id="sc_test")
        assert sd["scenarioId"] == "sc_test"
        assert sd["endpoint"]["id"] == order_endpoint.id
        assert len(sd["steps"]) == 1


class TestBodyRendering:
    def test_request_body_passes_through_interpolated(self, order_endpoint) -> None:
        # model 机制退役(spec §2.1.1):_render_body 只做 ${var} 插值,不再校验
        case = EndpointCase(
            name="passthrough",
            parameters={"order_no": "X", "amount": 5},
        )
        exporter = EndpointCaseExporter(order_endpoint)
        step = exporter.to_gimbal_step(case)
        body = step["request"]["body"]
        assert body == {"order_no": "X", "amount": 5}

    def test_request_none_returns_interpolated(self, order_patch_endpoint) -> None:
        case = EndpointCase(
            name="raw",
            parameters={"order_id": "X", "status": "ok"},
        )
        exporter = EndpointCaseExporter(order_patch_endpoint)
        step = exporter.to_gimbal_step(case)
        assert step["request"]["body"] == {"order_id": "X", "status": "ok"}
