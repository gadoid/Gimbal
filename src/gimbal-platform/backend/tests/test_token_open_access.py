"""authz W5 令牌开放面:User 签发 + 全部 PrincipalIn 端点冒烟 + 默认值。

* user 角色经 API 签发个人令牌(原 403 签发门删除);
* 用该令牌打满 13 个 PrincipalIn 端点(dev-plan W5 验收,grep 实测
  13 处:integration 6 / executions 4 / webhook_deliveries 2 /
  run_precheck 1 + runs 1 —— 部分与 executions 计数重叠,见矩阵)——
  断言**过认证**(非 401,且无 token 相关 403),业务面按各自契约;
* 集成任务省略 identityMode → 落库 personal(默认值反转,A2);
* 平台入口 410 三面的用例在 test_access_tokens(签发/候选)与
  本文件(任务创建)分头钉住。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import make_draft, role_headers

_GET_STEP = {
    "kind": "step", "description": "查单",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x", "headers": {}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}


async def _user_token(client: AsyncClient) -> tuple[dict, str]:
    """user 角色注册 → API 签发个人令牌 → (JWT 头, 明文)。"""
    h = await role_headers(client, "tk_open", role="user")
    r = await client.post("/api/access-tokens", headers=h, json={
        "kind": "personal", "name": "open", "ttlDays": 30,
        "scope": {"aliases": [], "authIds": []}})
    assert r.status_code == 201, r.text
    return h, r.json()["token"]


# (method, path, json, 期望状态码) —— 期望 = 该端点对「已过认证但空
# 世界」的契约;冒烟点在认证层(非 401 / 无 token 403),不在业务语义
_SMOKE = [
    ("GET", "/api/integration/tasks", None, 200),
    ("POST", "/api/integration/tasks", {
        "name": "t", "scenarioId": "sc-none", "identityMode": "personal"},
     404),   # 场景不存在(令牌属主 = 创建者)
    ("GET", "/api/integration/tasks/999999", None, 404),
    ("PATCH", "/api/integration/tasks/999999", {}, 404),
    ("DELETE", "/api/integration/tasks/999999", None, 404),
    ("POST", "/api/integration/tasks/999999/run", None, 404),
    ("GET", "/api/executions", None, 200),
    ("GET", "/api/executions/999999", None, 404),
    ("GET", "/api/executions/999999/rows", None, 404),
    ("GET", "/api/executions/999999/events", None, 404),
    ("POST", "/api/executions/999999/cancel", None, 404),
    ("GET", "/api/webhook-deliveries", None, 422),  # 过认证;缺过滤参数
    ("POST", "/api/webhook-deliveries/999999/redeliver", None, 404),
    ("POST", "/api/run/precheck", [], 200),   # 空清单过认证(§读侧契约)
]


class TestTokenOpenAccess:
    async def test_user_issues_and_hits_all_principal_endpoints(
            self, client: AsyncClient):
        h, plain = await _user_token(client)
        tk = {"Authorization": f"Bearer {plain}"}
        for method, path, body, expect in _SMOKE:
            # GET 不带 body(httpx 限制);写方法才传 json
            r = await client.request(
                method, path, headers=tk,
                json=body if method != "GET" else None)
            assert r.status_code == expect, (method, path, r.text)
            assert r.status_code != 401, (method, path)
            detail = r.json().get("detail") if r.status_code >= 400 else None
            if isinstance(detail, dict):
                assert detail.get("code") not in (
                    "token_owner_ineligible", "role_forbidden",
                    "capability_forbidden"), (method, path, detail)
        # JWT 侧照常(签发者本人;列表形状 items)
        r = await client.get("/api/access-tokens", headers=h)
        assert r.status_code == 200, r.text
        assert len(r.json()["items"]) == 1

    async def test_task_default_identity_mode_personal(self, client):
        """省略 identityMode 的创建请求 → 落库 personal(A2:防省略
        字段漏网建成平台任务;模型与 TaskIn 双侧默认一致)。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.integration_task import IntegrationTask

        h = await role_headers(client, "tk_dflt", role="user")
        r = await client.post("/api/scenarios", headers=h,
                              json=make_draft("sc-tk-dflt", steps=[_GET_STEP]))
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/integration/tasks", headers=h, json={
            "name": "默认模式", "scenarioId": "sc-tk-dflt"})
        assert r.status_code == 201, r.text
        assert r.json()["identityMode"] == "personal"
        async with db_module.SessionLocal() as s:
            row = (await s.execute(sa_select(IntegrationTask).where(
                IntegrationTask.scenario_id == "sc-tk-dflt",
                IntegrationTask.template_id.is_(None)))).scalar_one()
            assert row.identity_mode == "personal"
