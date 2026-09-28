"""残留 #8：plate Step 的 api/call 恰好其一（validator 强制）。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "src", "gimbal-plate"))

from gimbal_plate.schema.call import Call
from gimbal_plate.schema.step import Step


def test_step_exactly_one_of_api_call():
    """api 与 call 恰好其一：双填拒绝、双空拒绝、单填合法。"""
    from pydantic import ValidationError

    api = {"kind": "api", "service": "s", "method": "GET", "path": "/x"}
    call = {"kind": "call", "protocol": "http", "service": "s",
            "method": "GET", "path": "/x"}

    # 单填合法
    assert Step.model_validate({"api": api, "request": {"kind": "request", "body": {}}})
    assert Step.model_validate({"call": call, "request": {"kind": "request", "body": {}}})

    # 双填拒绝
    with pytest.raises(ValidationError):
        Step.model_validate({"api": api, "call": call,
                             "request": {"kind": "request", "body": {}}})
    # 双空拒绝
    with pytest.raises(ValidationError):
        Step.model_validate({"request": {"kind": "request", "body": {}}})
