"""导出 overlay + 黄金等价(spec §7.3/§8)。

同一场景、同一 overlay 下:preview-plate(带 overlay)产物 ≡ 基线单行
执行 case.json(逐字段相等)。无数据集 → 行 vars 无差异;stepTo/nRuns
不进 case.json → 无需模掉任何字段(spec §7.3 的「模掉行 vars/halt」
在基线单行下自然退化为零差)。

断言形状注:preview-plate 现返回 ``PreviewPlateResponse`` 信封
(``{ok, errors, converted}``),产物断言一律取 ``resp.json()["converted"]``
(brief 授权的「以外层包裹为准对齐」适配)。
"""
from __future__ import annotations

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member

OVERLAY = {
    "envId": "test-env-A",
    "serviceBindings": {"fin-service": {"authAlias": "qa1", "url": "https://bound"}},
}
# meta 钉死 owner/createTime:两路 fill_plate_defaults 全 setdefault 无增量;
# vars_map={} 显式带上 config.vars — _compose_scenario 恒定写回 vars(空 dict),
# 缺省 draft 无 vars 键会让两路差一个键。
# 其余 ScenarioMeta 全字段一并显式带上:dispatch 侧 convert 输入取自存储
# definition,scenario_store.create 会把 meta 经 ScenarioMeta.model_dump
# 归一化(补 description/author/tags/version/expire/updateTime 缺省);
# draft 侧显式对齐这些缺省值,两路 convert 输入才逐字段一致(非实质
# 差异的测试侧钉死,不改 dispatch/materialize 语义)。
_META = {
    "owner": "bob",
    "createTime": "2026-08-27T00:00:00Z",
    "description": "",
    "author": "",
    "tags": [],
    "version": "v0.1.0",
    "expire": False,
    "updateTime": None,
}
_STEP = {"kind": "step",
         "api": {"service": "fin-service", "path": "/x",
                 "headers": {"Authorization": "${auth.qa1.token}"}}}


def _eq_draft() -> dict:
    return _draft(steps=[_STEP], vars_map={}, **_META)


async def _seed(client, headers) -> None:
    r = await client.post("/api/scenarios", headers=headers, json=_eq_draft())
    assert r.status_code in (200, 201), r.text


async def test_preview_plate_without_overlay_unchanged(client, plate_mock: PlateMock):
    """不传 overlay → convert 原样(向后兼容,无绑定注入痕迹)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json=_eq_draft())
    assert resp.status_code == 200, resp.text
    converted = resp.json()["converted"]
    services = (converted.get("config") or {}).get("services") or {}
    assert services.get("fin-service") != "https://bound"


async def test_preview_plate_with_overlay_materializes(client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json={**_eq_draft(), "overlay": OVERLAY})
    assert resp.status_code == 200, resp.text
    converted = resp.json()["converted"]
    assert converted["config"]["services"]["fin-service"] == "https://bound"
    # qa1 无凭证池会话 → 告警继续,users 不含 qa1(与 dispatch 同语义)
    assert "qa1" not in (converted["config"].get("users") or {})


async def test_golden_equivalence_export_equals_baseline_case_json(
        client, plate_mock: PlateMock, monkeypatch):
    """黄金等价:导出产物 ≡ 基线单行 case.json,逐字段相等。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)

    exported = (await client.post(
        "/api/scenarios/preview-plate", headers=bob,
        json={**_eq_draft(), "overlay": OVERLAY})).json()["converted"]

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings=OVERLAY["serviceBindings"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    assert cases[0] == exported
