"""assertion_registry 写侧形状闸(I-01「隔离区+后端闸」,2026-11-24)。

非前端写入方(直连 API / 脚本 / 旧客户端)提交非对象 ``entries`` → 422
``assertion_registry_invalid``;前端隔离区 ``unrecognized`` 原样放行
(元素自由,存档不执行);``entries`` 缺键(旧客户端回落 pydantic
default)不拦。运行面存量行由 dispatch/graph 的 isinstance 过滤兜底
(graph_dispatch 过滤为本批补齐),不做存量回写。
"""
from __future__ import annotations

import pytest

from app.services.run_injection import validate_registry_shape
from tests.helpers import make_draft, register_and_login

_VALID_ENTRY = {
    "id": "inj-1", "name": "n",
    "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
    "value": -1, "asserts": [],
}


def _draft(entries, unrecognized=None) -> dict:
    draft = make_draft("sc-gate", vars_map={"amount": "1"})
    reg: dict = {"entries": entries}
    if unrecognized is not None:
        reg["unrecognized"] = unrecognized
    draft["assertion_registry"] = reg
    return draft


# ── 纯函数面 ─────────────────────────────────────────────────────

@pytest.mark.parametrize("reg", [
    {"entries": [7]},
    {"entries": [None]},
    {"entries": [[1]]},
    {"entries": ["x"]},
    {"entries": "nope"},
    "not-a-dict",
    {"entries": [], "unrecognized": {}},       # 隔离区须为数组
])
def test_gate_rejects_bad_shapes(reg):
    with pytest.raises(ValueError, match="assertion_registry_invalid"):
        validate_registry_shape(reg)


@pytest.mark.parametrize("reg", [
    {"entries": [_VALID_ENTRY]},
    {"entries": [_VALID_ENTRY], "unrecognized": [7, None, "x", [1]]},
    {},                                        # 缺键 = 旧客户端回落,不拦
    {"entries": []},
])
def test_gate_accepts_good_shapes(reg):
    validate_registry_shape(reg)               # 不抛即过


# ── API 面(create / PUT 双跑)────────────────────────────────────

async def test_create_with_junk_entry_rejected_422(client):
    headers = await register_and_login(client)
    r = await client.post("/api/scenarios", headers=headers,
                          json=_draft([7]))
    assert r.status_code == 422, r.text
    assert "assertion_registry_invalid" in r.json()["detail"]


async def test_put_with_junk_entry_rejected_422(client):
    headers = await register_and_login(client)
    assert (await client.post(
        "/api/scenarios", headers=headers, json=make_draft("sc-gate"))
    ).status_code in (200, 201)
    r = await client.put("/api/scenarios/sc-gate", headers=headers,
                         json=_draft([None]))
    assert r.status_code == 422, r.text
    assert "assertion_registry_invalid" in r.json()["detail"]


async def test_put_valid_entries_with_quarantine_passthrough(client):
    """前端隔离区(unrecognized)原样放行并落库 —— 数据零丢失的
    服务端半边:entries 合法 + junk 全在隔离键。"""
    headers = await register_and_login(client)
    assert (await client.post(
        "/api/scenarios", headers=headers, json=make_draft("sc-gate"))
    ).status_code in (200, 201)
    r = await client.put("/api/scenarios/sc-gate", headers=headers,
                         json=_draft([_VALID_ENTRY],
                                     unrecognized=[7, None, "x", [1]]))
    assert r.status_code in (200, 201), r.text
    d = await client.get("/api/scenarios/sc-gate/draft", headers=headers)
    assert d.status_code == 200, d.text
    reg = d.json()["assertion_registry"]
    assert reg["entries"] == [_VALID_ENTRY]
    assert reg["unrecognized"] == [7, None, "x", [1]]   # 原样,零丢失
