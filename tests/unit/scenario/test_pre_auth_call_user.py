"""P0-12（S3）：预认证覆盖 call.user 引用的标签（定稿 C7 补全）。

_setup_auth 的引用面 = 模板 ${auth.<tag>.*} + call.user 字段：
仅经 call.user 引用的用户在 preprocess 期 eager 登录；
未被引用的标签仍不登录（保持现状语义）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.schema.auth import AuthSession
from gimbal.schema.call import Call
from gimbal.schema.scenario import Scenario, Config as ScenarioConfig, Meta
from gimbal.schema.step import Step


def _meta() -> Meta:
    return Meta(name="n", description="d", module="m", priority=1, author="a",
                owner="o", tags=[], version="1.0",
                createTime=datetime.now(timezone.utc), expire=False,
                requirementRef=[])


def _scenario_with_call_user(tag: str) -> Scenario:
    return Scenario(
        scenarioId="sc-pre-auth",
        meta=_meta(),
        config=ScenarioConfig(users={
            "buyer": AuthSession(token="b"),
            "seller": AuthSession(token="s"),
        }),
        resource={},
        steps=[Step(description="d",
                    call=Call(protocol="http", service="svc", method="GET",
                              path="/p", **{"user": tag}),
                    strategy=[])],
    )


def _run_setup_auth(scenario: Scenario) -> MagicMock:
    """直调 _setup_auth（绕过完整 preprocess），返回 mock 的 AuthManager 类。"""
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor

    pre = ScenarioPreprocessor.__new__(ScenarioPreprocessor)
    pre._schema = scenario
    pre._auth_registry = AuthRegistry()
    with patch("gimbal.auth.AuthManager") as am_cls:
        am_cls.return_value = MagicMock()
        pre._setup_auth()
    return am_cls.return_value


def test_call_user_tag_gets_eager_login():
    """仅经 call.user 引用的 buyer：preprocess 期即登录（非调用时 lazy）。"""
    am = _run_setup_auth(_scenario_with_call_user("buyer"))
    am.get_auth.assert_called_once_with("buyer")


def test_unreferenced_tag_not_logged_in():
    """seller 未被任何引用面触达：不登录。"""
    am = _run_setup_auth(_scenario_with_call_user("buyer"))
    # get_auth 只被 buyer 调过一次；seller 从未出现
    calls = [c.args[0] for c in am.get_auth.call_args_list if c.args]
    assert "seller" not in calls


def test_template_tag_still_eager_login():
    """既有行为回归：${auth.<tag>.token} 模板引用仍触发登录。"""
    sc = _scenario_with_call_user("seller")
    sc.steps[0].call = Call(protocol="http", service="svc", method="GET",
                            path="/p", headers={"X-T": "${auth.seller.token}"})
    am = _run_setup_auth(sc)
    am.get_auth.assert_called_once_with("seller")
