"""共享打桩:捕获 dispatch 入队后 worker 解包的 _fanout 实参。

(迁自 v3 的 test_inbound_recipe_scope;令牌改造后该文件退役,桩留此。)
"""
from __future__ import annotations

from app.services import run_dispatcher as rd
from app.services.run_dispatcher import STATUS_DONE


async def _capture_fanout(monkeypatch) -> "list[dict]":
    """把 _fanout 打桩:捕获 dispatch 入队后 worker 解包后的实参。"""
    cap: list[dict] = []

    async def _fake_fanout(*, db_factory, execution_id, **kw):
        cap.append({"execution_id": execution_id, **kw})
        await rd.transition_with_retry(db_factory, execution_id, STATUS_DONE)

    monkeypatch.setattr(rd, "_fanout", _fake_fanout)
    return cap
