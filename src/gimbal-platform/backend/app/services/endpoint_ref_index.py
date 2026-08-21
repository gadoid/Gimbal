"""倒排索引解析与维护(spec §3.2;源存果算 — 本模块是 payload 的派生态)。

职责:
* ``parse_refs``  纯函数:payload → (索引行, 未索引步骤报告)
* ``sync_scenario`` 写路径同事务维护(删旧插新,不 commit)
* ``drop_scenario`` 场景删除时清索引行
* ``rebuild``      全量重建 + 报告(Task 3)

注意:本模块**不得** import scenario_store(那里反向 import 本模块挂
钩子,会成环)—— steps 提取用本地 walker,3 行,接受这点重复。
"""
from __future__ import annotations

import re

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario  # noqa: F401(PG/类型引用)
from ..models.scenario_endpoint_ref import ScenarioEndpointRef

# 变量名允许 "."(③ 配置步的 <system>.key 命名空间键含点)
_VAR_RE = re.compile(r"\$\{var\.([A-Za-z0-9_.]+)\}")

# field 容器:body 在 step.request 下,headers/query 在 step.api 下(spec §3.2)
_SOURCES = ("body", "headers", "query")


def _steps(payload: dict | None) -> list[dict]:
    definition = (payload or {}).get("definition")
    raw = definition.get("steps") if isinstance(definition, dict) else None
    return [s for s in (raw or []) if isinstance(s, dict)]


def _fields(step: dict, source: str) -> dict:
    container = (step.get("request") if source == "body" else step.get("api")) or {}
    fields = container.get(source) if isinstance(container, dict) else None
    return fields if isinstance(fields, dict) else {}


def parse_refs(
    scenario_id: str, payload: dict | None
) -> tuple[list[ScenarioEndpointRef], list[dict]]:
    """payload → 索引行 + 未索引步骤报告(spec §3.2/C10)。

    via_var 取值中**第一个** ``${var.NAME}`` 匹配(多变量内嵌属尾部
    场景,P2 扩展可改列形状);非字符串值(数值/布尔)恒为直填。
    """
    refs: list[ScenarioEndpointRef] = []
    unindexed: list[dict] = []
    for i, step in enumerate(_steps(payload)):
        api = step.get("api") if isinstance(step.get("api"), dict) else {}
        hints = api.get("view_hints") if isinstance(api.get("view_hints"), dict) else {}
        endpoint_id = hints.get("endpoint_id")
        if not endpoint_id:
            unindexed.append({
                "scenario_id": scenario_id, "step_index": i,
                "reason": "no_endpoint_id",
            })
            continue
        for source in _SOURCES:
            for name, value in _fields(step, source).items():
                via_var = None
                if isinstance(value, str):
                    m = _VAR_RE.search(value)
                    via_var = m.group(1) if m else None
                refs.append(ScenarioEndpointRef(
                    scenario_id=scenario_id, step_index=i, source=source,
                    field_name=str(name), endpoint_id=str(endpoint_id),
                    via_var=via_var,
                ))
    return refs, unindexed


async def sync_scenario(
    db: AsyncSession, scenario_id: str, payload: dict | None
) -> None:
    """写路径同事务维护:删旧插新。调用方负责 commit。"""
    await db.execute(
        sa_delete(ScenarioEndpointRef).where(
            ScenarioEndpointRef.scenario_id == scenario_id
        )
    )
    refs, _ = parse_refs(scenario_id, payload)
    for r in refs:
        db.add(r)


async def drop_scenario(db: AsyncSession, scenario_id: str) -> None:
    """场景删除时清索引行(无 FK,显式删;调用方负责 commit)。"""
    await db.execute(
        sa_delete(ScenarioEndpointRef).where(
            ScenarioEndpointRef.scenario_id == scenario_id
        )
    )
