"""C1/C2 端到端(已停用冒烟,S1-0 B4)。

旧版覆盖「注册→编排→转换」全链;C1 内存注册与 P1(文件为唯一真源)冲突
已停用(410),平台无调用(已核实)。保留 410 冒烟 + convert 主链仍可用。
"""
from __future__ import annotations


def test_register_disabled_and_convert_alive(http_client) -> None:
    resp = http_client.post("/api/system/action/register", json={"id": "e2e"})
    assert resp.status_code == 410
    # scenario convert 主链不受停用影响(契约回归在 test_http_scenario_convert)
    assert http_client.get("/api/system").status_code == 200
