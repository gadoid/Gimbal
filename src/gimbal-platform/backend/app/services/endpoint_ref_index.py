"""倒排索引解析与维护(spec §3.2;源存果算 — 本模块是 payload 的派生态)。

职责:
* ``parse_refs``  纯函数:payload → (索引行, 未索引步骤报告)
* ``sync_scenario`` 写路径同事务维护(删旧插新,不 commit)
* ``drop_scenario`` 场景删除时清索引行
* ``rebuild``      全量重建 + 报告(Task 3)
* ``unindexed_steps`` 未索引步骤只读清单(P5 适配中心挂牌)

锚点行(2026-09-20):锚定了 endpoint 但 body/headers 全空的 step 也发
一行哨兵行(``source=ANCHOR_SOURCE``、``field_name=ANCHOR_FIELD``)。
此前这类 step 零行,对 endpoint→scenario 影响查询不可见——impact 靠
全量 payload 兜底直扫补位(O(全部场景)/次),而 open_batch 的草案
展开没有那份兜底,零字段步连 addField op 都漏生成。锚点行让两类
消费方读同一份索引。升级部署后须跑一次 ``rebuild`` 补齐存量。

注意:本模块**不得** import scenario_store(那里反向 import 本模块挂
钩子,会成环)—— steps 提取用本地 walker,3 行,接受这点重复。
"""
from __future__ import annotations

import re

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.scenario_endpoint_ref import ScenarioEndpointRef

# 变量名允许 "."(③ 配置步的 <system>.key 命名空间键含点)
_VAR_RE = re.compile(r"\$\{var\.([A-Za-z0-9_.]+)\}")

# field 容器:body 在 step.request 下,headers 在 step.call 下(spec §3.2)。
# 无 query 容器 —— plate Api schema 无此字段(convert 会静默吞掉),引擎的
# GET 查询参数约定放 request.body(executor 映射为 params=),body 管道天然覆盖。
_SOURCES = ("body", "headers")

# 锚点行哨兵值:PK 四列天然容纳(空串满足 NOT NULL);消费方按 source 判别。
# 只为零字段锚点 step 发(有字段行的 step 无需占位),保持既有行的语义不变。
ANCHOR_SOURCE = "anchor"
ANCHOR_FIELD = ""

# 外部接口登记批 X3:断言侧行的 source 值 —— 断言条目的 jsonpath 指向
# 的是**响应**(与字段行的 body/headers 请求侧语义不同),独立 source
# 不混淆;field_name = jsonpath 根段(同根段多条断言合一,行语义 =
# 「该步骤断言引用了根段 X」,重复无信息 —— PK 四列天然去重)。
ASSERT_SOURCE = "assertion"


def _steps(payload: dict | None) -> list[dict]:
    definition = (payload or {}).get("definition")
    raw = definition.get("steps") if isinstance(definition, dict) else None
    return [s for s in (raw or []) if isinstance(s, dict)]


def _fields(step: dict, source: str) -> dict:
    holder = (step.get("request") if source == "body"
              else step.get("call"))
    container = holder or {}
    fields = container.get(source) if isinstance(container, dict) else None
    return fields if isinstance(fields, dict) else {}


def parse_refs(
    scenario_id: str, payload: dict | None
) -> tuple[list[ScenarioEndpointRef], list[dict]]:
    """payload → 索引行 + 未索引步骤报告(spec §3.2/C10)。

    X3(D3 拍板):``via_vars`` 收值内**全部** ``${var.NAME}``(按出现序,
    JSON 列);``via_var`` 保留首变量兼容读,消费方迁移后改读新列。
    断言条目(assertion_registry.entries[].path.jsonpath 指向响应)发
    断言侧行(source=ASSERT_SOURCE、field_name=jsonpath 根段;同
    (step, 根段) 去重)——影响查询对断言引用可见。

    锚定但业务字段全空(body/headers 皆空)的 step 发一行锚点行
    (source=ANCHOR_SOURCE),保证影响查询可见;有字段行的 step 不发。
    """
    refs: list[ScenarioEndpointRef] = []
    unindexed: list[dict] = []
    # X3 断言侧行:同 (step, 根段) 去重(多条断言同根段无新信息)
    seen_assert_roots: set[tuple[int, str]] = set()
    for i, step in enumerate(_steps(payload)):
        # M3:锚点唯一 = step.endpoint(view_hints 双读已删)
        endpoint_id = step.get("endpoint")
        if not endpoint_id:
            unindexed.append({
                "scenario_id": scenario_id, "step_index": i,
                "reason": "no_endpoint_id",
            })
            continue
        step_rows = 0
        for source in _SOURCES:
            for name, value in _fields(step, source).items():
                via_vars: list[str] | None = None
                if isinstance(value, str):
                    via_vars = _VAR_RE.findall(value) or None
                refs.append(ScenarioEndpointRef(
                    scenario_id=scenario_id, step_index=i, source=source,
                    field_name=str(name), endpoint_id=str(endpoint_id),
                    via_var=(via_vars[0] if via_vars else None),
                    via_vars=via_vars,
                ))
                step_rows += 1
        if step_rows == 0:
            refs.append(ScenarioEndpointRef(
                scenario_id=scenario_id, step_index=i,
                source=ANCHOR_SOURCE, field_name=ANCHOR_FIELD,
                endpoint_id=str(endpoint_id), via_var=None,
            ))
        # X3:断言条目(jsonpath 指向响应)→ 断言侧行;锚点含 ext:
        # (外部接口登记批,影响查询对 external 接口同样可见)
        reg = (payload or {}).get("assertion_registry") or {}
        entries = (reg.get("entries") if isinstance(reg, dict) else None) or []
        for e in entries:
            if not isinstance(e, dict):
                continue
            loc = e.get("path")
            if not isinstance(loc, dict):
                continue
            try:
                si = int(loc.get("stepIndex"))
            except (TypeError, ValueError):
                continue
            if si != i:
                continue
            root = _jsonpath_root(loc.get("jsonpath"))
            if not root:
                continue
            key = (si, root)
            if key in seen_assert_roots:
                continue
            seen_assert_roots.add(key)
            refs.append(ScenarioEndpointRef(
                scenario_id=scenario_id, step_index=si,
                source=ASSERT_SOURCE, field_name=root,
                endpoint_id=str(endpoint_id), via_var=None,
            ))
    return refs, unindexed


def _jsonpath_root(path) -> str:
    """``$.a.b[0]`` → ``a``;非 $. 前缀原样(与注入改写同口径)。"""
    p = str(path or "")
    if not p.startswith("$."):
        return p
    return p[2:].split(".")[0].split("[")[0]


def anchor_step_indexes(payload: dict | None, endpoint_id: str) -> list[int]:
    """锚点=endpoint_id 的全部 step 下标(含业务字段全空者)。

    锚点行上线前的 impact 兜底直扫用;现在 parse_refs 已为零字段锚点
    step 发锚点行,本函数仅留作索引外的直扫工具(测试/排障),生产
    路径不再依赖。
    """
    out: list[int] = []
    for i, step in enumerate(_steps(payload)):
        if step.get("endpoint") == endpoint_id:
            out.append(i)
    return out


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


async def rebuild(db: AsyncSession) -> dict:
    """全量重建索引 + 未索引步骤报告(spec §3.2/C10)。

    对账 / 灾后重建 / 升级迁移共用。确定性 ≠ 完备性:缺
    step.endpoint 的步骤(手写调用)不进索引,必须在报告里显式可见。
    """
    from sqlalchemy import select  # 局部 import 避免与模块头冲突

    # order_by:PG 无隐式行序,报告喂 P5 适配中心须确定性
    rows = (await db.execute(
        select(ComposerScenario).order_by(ComposerScenario.scenario_id)
    )).scalars().all()
    await db.execute(sa_delete(ScenarioEndpointRef))
    refs_total = 0
    unindexed: list[dict] = []
    for row in rows:
        refs, un = parse_refs(row.scenario_id, row.payload)
        unindexed.extend(un)
        refs_total += len(refs)
        for r in refs:
            db.add(r)
    await db.commit()
    return {
        "scenarios": len(rows), "refs": refs_total, "unindexed_steps": unindexed,
    }


async def unindexed_steps(db: AsyncSession) -> list[dict]:
    """当前库的未索引步骤清单(P5 适配中心挂牌;rebuild 的只读子集)。"""
    from sqlalchemy import select

    rows = (await db.execute(
        select(ComposerScenario).order_by(ComposerScenario.scenario_id)
    )).scalars().all()
    out: list[dict] = []
    for row in rows:
        _, un = parse_refs(row.scenario_id, row.payload)
        out.extend(un)
    return out
