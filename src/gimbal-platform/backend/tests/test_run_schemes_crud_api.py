"""新方案 CRUD 端点:默认置顶、创建/改名/删除、权限、default 保护。"""
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member

BASE = "/api/scenarios/sc-test/run-schemes"


async def _setup(client, username="alice"):
    h = await _member(client, username)
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text  # create 端点声明 201
    return h


def _body(name="冒烟", **over):
    b = {"name": name, "dataSetSelection": [], "injectionEntryIds": [],
         "serviceBindings": {}, "stepTo": None, "nRuns": 1, "parallel": 1,
         "plugins": None, "logSub": None}
    b.update(over)
    return b


async def test_list_returns_default_on_top(client):
    h = await _setup(client)
    await client.post(BASE, headers=h, json=_body("A"))
    r = await client.get(BASE, headers=h)
    assert r.status_code == 200
    lst = r.json()
    assert lst[0]["isDefault"] is True
    assert [s["name"] for s in lst[1:]] == ["A"]
    assert lst[0]["schemeId"].startswith("rs-")


async def test_create_conflict_and_reserved_name(client):
    h = await _setup(client)
    assert (await client.post(BASE, headers=h, json=_body("A"))).status_code == 201
    r = await client.post(BASE, headers=h, json=_body("A"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_scheme_name_conflict"
    r = await client.post(BASE, headers=h, json=_body("默认方案"))
    assert r.status_code == 409


async def test_update_renames_and_normalizes_default(client):
    h = await _setup(client)
    made = (await client.post(BASE, headers=h, json=_body("A", nRuns=3))).json()
    r = await client.put(f"{BASE}/{made['schemeId']}", headers=h,
                         json=_body("B", stepTo=2))
    assert r.status_code == 200 and r.json()["name"] == "B" and r.json()["stepTo"] == 2
    # default 行:锁名、清空两键
    d = (await client.get(BASE, headers=h)).json()[0]
    r = await client.put(f"{BASE}/{d['schemeId']}", headers=h,
                         json=_body("改名无效", nRuns=5,
                                    injectionEntryIds=["inj-x"],
                                    dataSetSelection=[{"datasetId": "ds-x", "rowIndexes": [0]}]))
    assert r.status_code == 200
    got = r.json()
    assert got["name"] == "默认方案" and got["injectionEntryIds"] == []
    assert got["dataSetSelection"] == [] and got["nRuns"] == 5


async def test_delete_default_405_and_normal_204(client):
    h = await _setup(client)
    made = (await client.post(BASE, headers=h, json=_body("A"))).json()
    r = await client.delete(f"{BASE}/{made['schemeId']}", headers=h)
    assert r.status_code == 204
    d = (await client.get(BASE, headers=h)).json()[0]
    r = await client.delete(f"{BASE}/{d['schemeId']}", headers=h)
    assert r.status_code == 405 and r.json()["detail"]["code"] == "run_scheme_default_protected"


async def test_owner_enforced(client):
    alice = await _setup(client, "alice")
    await client.post(BASE, headers=alice, json=_body("A"))
    bob = await _member(client, "bob")
    assert (await client.get(BASE, headers=bob)).status_code == 403
    assert (await client.post(BASE, headers=bob, json=_body("B"))).status_code == 403


async def test_update_delete_404_unknown_scheme_id(client):
    """§13 T2-2 错误面:PUT/DELETE 不存在的 scheme_id → 404 run_scheme_not_found。"""
    h = await _setup(client)
    r = await client.put(f"{BASE}/rs-999", headers=h, json=_body("X"))
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "run_scheme_not_found"
    r = await client.delete(f"{BASE}/rs-999", headers=h)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "run_scheme_not_found"


async def test_update_delete_owner_enforced(client):
    """§13 T2-2 错误面:非属主 PUT/DELETE → 403,且不产生副作用。"""
    alice = await _setup(client, "alice")
    made = (await client.post(BASE, headers=alice, json=_body("A"))).json()
    bob = await _member(client, "bob")
    assert (await client.put(
        f"{BASE}/{made['schemeId']}", headers=bob, json=_body("B"))).status_code == 403
    assert (await client.delete(
        f"{BASE}/{made['schemeId']}", headers=bob)).status_code == 403
    # bob 的 403 未动 alice 的数据(仅默认方案 + A)
    lst = (await client.get(BASE, headers=alice)).json()
    assert [s["name"] for s in lst if not s["isDefault"]] == ["A"]
