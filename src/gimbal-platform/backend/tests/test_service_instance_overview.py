"""服务×环境实例组合读模型(``GET /services/instance-overview``)。

实例 = 有 deployment 或 identity 的 (service, env);登录口/版本线/
说明/tags 按 (service.system, env) 从 system_env_instances 联表。
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models import Environment, Service
from app.models.deployment import Deployment
from app.models.service_identity import ServiceIdentity
from app.models.system_env_instance import SystemEnvInstance

from .helpers import role_headers


async def _seed() -> tuple[int, int]:
    """dev/test 两个环境 + fin/logi/empty 三个服务 + 实例事实。"""
    async with db_module.SessionLocal() as s:
        dev = Environment(name="dev", is_default=True)
        test = Environment(name="test")
        s.add_all([dev, test])
        await s.flush()
        s.add_all([
            Service(name="fin", system="fin", kind="plate"),
            Service(name="logi", system="logi", kind="plate"),
            Service(name="empty-svc", system="empty", kind="external"),
        ])
        await s.flush()
        s.add_all([
            Deployment(base_service="fin", env_id=dev.id,
                       base_url="https://fin-dev.example"),
            Deployment(base_service="logi", env_id=test.id,
                       base_url="https://logi-test.example"),
            SystemEnvInstance(system="fin", env_id=dev.id,
                              login_url="https://login.fin-dev",
                              line="v4.4#3"),
            ServiceIdentity(alias_name="fin-dev", base_service="fin",
                            env_id=dev.id, ref_mode="username",
                            ref_username="qa1", display="QA"),
            ServiceIdentity(alias_name="fin-default", base_service="fin",
                            env_id=dev.id, ref_mode="default"),
        ])
        await s.commit()
        return dev.id, test.id


@pytest.mark.asyncio
async def test_overview_composes_service_env(client: AsyncClient):
    dev, test = await _seed()
    h = await role_headers(client, "svc-overview")
    r = await client.get("/api/services/instance-overview", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    by_name = {s["name"]: s for s in body["services"]}
    assert set(by_name) == {"fin", "logi", "empty-svc"}
    assert by_name["empty-svc"]["instances"] == []

    fin = by_name["fin"]
    assert fin["system"] == "fin"
    assert fin["kind"] == "plate"
    assert len(fin["instances"]) == 1
    inst = fin["instances"][0]
    assert inst["envId"] == dev
    assert inst["envName"] == "dev"
    assert inst["groupId"]          # 有系统实例行 → 组 id 在场
    assert inst["baseUrl"] == "https://fin-dev.example"
    assert inst["loginUrl"] == "https://login.fin-dev"
    assert inst["line"] == "v4.4#3"
    assert [i["aliasName"] for i in inst["identities"]] == [
        "fin-default", "fin-dev"]
    assert inst["identities"][1]["refMode"] == "username"
    assert inst["identities"][1]["refUsername"] == "qa1"

    logi = by_name["logi"]["instances"][0]
    assert logi["envId"] == test
    assert logi["groupId"] == ""     # 无系统实例行 → 前端按 env 自成一实例
    assert logi["loginUrl"] == ""      # 未登记系统登录口
    assert logi["identities"] == []
