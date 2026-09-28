"""api→call 清理(2026-09-28):plate Step 仅收 call,api 形态显式拒绝。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "src", "gimbal-plate"))

from gimbal_plate.schema.step import Step


def test_step_api_form_rejected():
    """api 形态已退役:model_validate 期拒绝,错误信息指向迁移脚本。"""
    from pydantic import ValidationError

    api = {"kind": "api", "service": "s", "method": "GET", "path": "/x"}
    with pytest.raises(ValidationError, match=r"step\.api 形态已退役|migrate_legacy_case"):
        Step.model_validate({"api": api, "request": {"kind": "request", "body": {}}})


def test_step_call_form_accepted():
    """call 单填合法(唯一调用形态)。"""
    call = {"kind": "call", "protocol": "http", "service": "s",
            "method": "GET", "path": "/x"}
    step = Step.model_validate({"call": call, "request": {"kind": "request", "body": {}}})
    assert step.call.protocol == "http"


def test_step_call_required():
    """缺 call 拒绝(必填)。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Step.model_validate({"request": {"kind": "request", "body": {}}})
