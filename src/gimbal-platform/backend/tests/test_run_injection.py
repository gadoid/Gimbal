"""run_injection — 注入条目物化纯函数 + 集成(spec v3 §3)。"""
import asyncio
import sys
from pathlib import Path

import pytest

from app.services.run_injection import compose_injection_scenario, entry_issues
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)

# ── 真引擎 / 真 plate(下方「convert 穿越 + 真解析」组)────────────────
# 平台进程里这两棵树是兄弟源树、非安装包(引擎以子进程运行),backend
# 测试环境默认不在 sys.path —— 显式挂上。只读,不改任何一行。
_SRC_ROOT = Path(__file__).resolve().parents[3]          # <repo>/src
for _root in (_SRC_ROOT, _SRC_ROOT / "gimbal-plate"):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

DEF = {
    "config": {"vars": {"amount": 100, "bl_no": "BL1"}},
    "steps": [
        {"description": "下单", "request": {"body": {"amount": "${var.amount}"}},
         "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                       "operator": "eq", "expected": "0"}]},
        {"description": "查单", "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
    ],
}


def _body_of(steps):
    return lambda si: (steps[si].get("request") or {}).get("body")


def _targets_of(steps):
    def _t(si: int) -> set:
        return {st.get("target") for st in (steps[si].get("strategy") or [])
                if isinstance(st, dict) and st.get("kind") == "assertion"}
    return _t


def test_assign_appends_strategy_without_touching_vars():
    """path 直补(spec v3 §3):Assign 追加进 steps[si].strategy,config.vars
    零触碰(与数据集 vars 注入解耦);源 definition 零污染。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
             "value": -1, "asserts": []}
    out = compose_injection_scenario(DEF, entry)
    assert out["config"]["vars"]["amount"] == 100            # vars 不动
    st = out["steps"][0]["strategy"]
    assert st[-1] == {"kind": "assign", "source": -1, "target": "$.request_body.amount"}
    assert DEF["steps"][0]["strategy"] == [{"kind": "assertion", "target": "$.response_body.code",
                                            "operator": "eq", "expected": "0"}]   # 源零污染


def test_assign_value_passthrough_no_coerce():
    """value 原样覆写不 coerce(str/bool/嵌套 dict 都不转形)。"""
    for v in ["-1", True, {"a": [1, 2]}, None]:
        entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
                 "value": v, "asserts": []}
        out = compose_injection_scenario(DEF, entry)
        assert out["steps"][0]["strategy"][-1]["source"] == v


def test_override_and_append_patch_keep_v2_semantics():
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
             "value": -1, "asserts": [
                 {"stepIndex": 0, "target": "$.response_body.code", "operator": "eq",
                  "expected": "400", "mode": "override"},
                 {"stepIndex": 1, "target": "$.response_body.msg", "operator": "contains",
                  "expected": "金额非法", "mode": "append"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "400"    # override 改 expected
    assert {"kind": "assertion", "target": "$.response_body.msg",
            "operator": "contains", "expected": "金额非法"} in out["steps"][1]["strategy"]


def test_dangling_path_and_unmatched_override_skipped():
    """悬空项静默跳过(dispatcher 已过滤,双保险):越界 stepIndex 不落
    Assign;无匹配 override 不动既有断言。issues 同构断言四种。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 9, "source": "body", "jsonpath": "$.x"},
             "value": 1, "asserts": [
                 {"stepIndex": 0, "target": "$.nope", "operator": "eq", "expected": "1", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "0"     # 无匹配 override 不动
    assert all(st.get("kind") != "assign" for s in out["steps"] for st in s["strategy"])
    issues = entry_issues(entry, 2, _body_of(DEF["steps"]), _targets_of(DEF["steps"]))
    assert {"kind": "step-oob", "stepIndex": 9} in issues
    assert {"kind": "override-no-match", "stepIndex": 0, "target": "$.nope"} in issues


def test_entry_issues_path_unresolvable_and_legacy():
    body_of = _body_of(DEF["steps"])
    targets = _targets_of(DEF["steps"])
    ghost = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.ghost"},
             "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.ghost"} in \
        entry_issues(ghost, 2, body_of, targets)
    # 容器前缀可解析:叶子 $.amount 在树上,$. 不在
    ok = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
          "value": 1, "asserts": []}
    assert entry_issues(ok, 2, body_of, targets) == []
    # str body 步骤无可索引字段 → 一律不可解析(spec v3 §2)
    str_body = [{"request": {"body": "raw"}}]
    s = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.x"},
         "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.x"} in \
        entry_issues(s, 2, _body_of(str_body), targets)
    # v2 旧形状(无 path)→ legacy-entry 全量 issue(spec v3 §8)
    legacy = {"id": "inj-old", "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
              "injection": [{"varName": "amount", "value": "-1"}], "asserts": []}
    assert entry_issues(legacy, 2, body_of, targets) == [{"kind": "legacy-entry"}]


# ── dispatcher 集成(spec v3 §3:Assign 直补落 case.json;skip 链)────
# 骨架不变:建场景(assertion_registry 注入)→ POST /api/runs → 断言
# case 数 / case.json patch / rows 回放。

_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """JSONL/case 目录指到 tmp:回放只读本测试写入的行(镜像
    test_execution_rows.py 的做法,理由见其注释)。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


async def test_dispatcher_fans_out_injection_entries(
    client, plate_mock: PlateMock, monkeypatch
):
    """选中 1 活条目(+ 死条目 + 旧版条目)且无数据集 → case 数 = 活条目数
    ×nRuns;死/旧条目 skip 不炸;case.json 的 steps[0].strategy 已追加
    Assign 直补($.request_body.amount)且 vars 未被触碰;rows 回放含
    injectionId。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[
            {"id": "s1", "request": {"body": {"amount": "${var.amount}"}},
             "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                           "operator": "eq", "expected": "0"}]},
            {"id": "s2", "strategy": []},
        ],
        vars_map={"amount": 100},
    )
    draft["assertion_registry"] = {"entries": [
        # 活条目:Assign 直补(value -1,原样不 coerce)+ override patch('400')
        {"id": "inj-live", "name": "金额非法",
         "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
         "value": -1,
         "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                      "operator": "eq", "expected": "400", "mode": "override"}]},
        # 死条目:path stepIndex 越界 → entry_issues 判死,skip 不炸
        {"id": "inj-dead", "name": "越界死条目",
         "path": {"stepIndex": 9, "source": "body", "jsonpath": "$.x"},
         "value": 1,
         "asserts": [{"stepIndex": 9, "target": "$.x", "operator": "eq",
                      "expected": "1", "mode": "append"}]},
        # 旧版条目(v2 anchor+injection 形状)→ legacy-entry 全量 issue → skip
        {"id": "inj-old", "name": "旧版条目",
         "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount", "varName": "amount"},
         "injection": [{"varName": "amount", "value": "-1"}], "asserts": []},
    ]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    # echo:converted 原样回灌 → case.json 保留 patched strategy 可断言
    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-live", "inj-dead", "inj-old"], "nRuns": 2,
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 2)
    assert len(cases) == 2                       # 1 活条目 × nRuns=2;死/旧 skip
    for case in cases:
        st = case["steps"][0]["strategy"]
        assert st[0]["expected"] == "400"                          # override patch
        assert {"kind": "assign", "source": -1,
                "target": "$.request_body.amount"} in st           # Assign 直补
        assert case["config"]["vars"]["amount"] == 100             # vars 未触碰

    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 2
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 2
    assert all(row["injectionId"] == "inj-live" for row in rows)
    assert all(row["datasetId"] is None for row in rows)


# ── 真解析 / 真 convert(spec §3「convert 穿越」)──────────────────────
# plate_mock.behaviour="echo" 把输入原样回灌,证明不了:①真 plate 的
# Scenario 校验 + export.dispatch 收得下注入的 Assign;②真引擎的
# `_resolve_source_value`/AssignExecutor 把用户 value 落成了什么。
# 下面两组打这两个面(引擎/plate 只读,零改动)。

# plate 必填面全量(Scenario.model_validate 通过):meta 的 author/owner/
# tags/version/expire 等平台 UI 不采集,生产链由 plate_client
# .fill_plate_defaults 补;测试里一次写全,便于断言转换产物本身。
_PLATE_SCENARIO: dict = {
    "kind": "scenario",
    "scenarioId": "sc-inj",
    "meta": {
        "name": "注入穿越", "description": "convert 黄金等价", "module": "order",
        "priority": 1, "author": "t", "owner": "t", "tags": [], "version": "1",
        "createTime": "2026-09-12T00:00:00Z", "expire": False,
        "requirementRef": [], "system": ["fin"],
    },
    "config": {"vars": {"amount": 100}, "services": {}},
    "resource": {},
    "steps": [{
        "kind": "step",
        "description": "下单",
        "api": {"kind": "api", "service": "fin", "method": "POST", "path": "/order/add",
                "headers": {}, "view_hints": {"endpoint_id": "fin.order.add"}},
        "request": {"kind": "request", "body": {"amount": "${var.amount}"}},
        "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                      "operator": "eq", "expected": "0"}],
    }],
}


def _compose(value, jsonpath: str = "$") -> dict:
    """单条目注入(整 body 目标 = jsonpath "$";字段级 = "$.amount")。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": jsonpath},
             "value": value, "asserts": []}
    return compose_injection_scenario(_PLATE_SCENARIO, entry)


class _ScratchView:
    """StrategyContextView 最小替身:Assign 只用到读上下文 + 写 scratch
    两面(scope=SCENARIO 的 source 解析走 read_variable)。"""

    def __init__(self) -> None:
        self.scratch: dict = {}

    def read_variable(self, key, *, from_layer=None, default=None):
        return default                       # 空上下文:引用一律解析不到

    def write_scratch(self, key, value) -> None:
        self.scratch[key] = value

    def get_scratch_dict(self) -> dict:
        return dict(self.scratch)


def _real_assign_execute(strategy: dict):
    """真引擎执行一条 Assign(延迟导入:只在真解析用例里加载引擎包)。"""
    from gimbal.schema.strategy import Assign
    from gimbal.strategy.builtin.assign import AssignExecutor

    view = _ScratchView()
    result = AssignExecutor().execute(Assign.model_validate(strategy), view)
    return result, view


@pytest.mark.parametrize("value", ["$.amount", "${var.amount}", "$.5"])
def test_assign_shape_carries_literal_fallback_for_reference_shapes(value):
    """两类「引擎会当引用读」的字符串 → 追加 default(=字面量)+
    required:false,否则解析不到 None 即整步 FAILED(见下条反证)。"""
    st = _compose(value)["steps"][0]["strategy"][-1]
    assert st == {"kind": "assign", "source": value,
                  "target": "$.request_body", "default": value, "required": False}


@pytest.mark.parametrize("value", ["hello", "-1", "", "$", "0.5", {"a": 1}, [1, 2], True, 0])
def test_assign_shape_stays_default_for_everything_else(value):
    """非引用形状(含裸 "$")零附加键 — Assign 基座字段全取默认(spec §3)。"""
    st = _compose(value)["steps"][0]["strategy"][-1]
    assert st == {"kind": "assign", "source": value, "target": "$.request_body"}


@pytest.mark.parametrize("value", [
    "$.amount", "${var.amount}", "$.5", "hello", "-1", "", "$",
    {"a": [1, 2]}, [1, 2, 3], True, False, 0,
])
def test_real_assign_executor_writes_the_user_literal(value):
    """真引擎解析 + 真 AssignExecutor:每条 value 都原样落到 target
    (整 body 目标 "$.request_body")—— 「原样覆写不 coerce」在引擎侧成立。"""
    from gimbal.strategy.executor_base import StrategyStatus

    strategy = _compose(value)["steps"][0]["strategy"][-1]
    result, view = _real_assign_execute(strategy)
    assert result.status is StrategyStatus.PASSED, result.message
    assert view.scratch["$.request_body"] == value


def test_real_assign_fails_without_the_literal_fallback():
    """反证(红证据的静态形态):不带 default/required:false 的裸 source
    在真引擎里 FAILED 且**什么都没写** —— 正是修复前的行为。"""
    from gimbal.strategy.executor_base import StrategyStatus

    result, view = _real_assign_execute(
        {"kind": "assign", "source": "$.amount", "target": "$.request_body"})
    assert result.status is StrategyStatus.FAILED
    assert "resolved to None" in result.message
    assert view.scratch == {}


async def test_real_convert_accepts_and_roundtrips_injected_assign():
    """真 plate `/convert`(进程内 ASGITransport,lifespan 手起:dim 路由
    要 registry 就位):注入的 Assign 收得下、原样穿出,且转换产物能被
    **真引擎** `Scenario.model_validate` 加载(dict 源 + 整 body 目标、
    list 源 + 字段目标、引用形字符串三条)。"""
    from gimbal_plate.http.app import create_app
    import httpx

    from app.services import plate_client
    from gimbal.schema.scenario import Scenario

    cases = [
        ({"a": [1, 2]}, "$", "$.request_body"),
        ([1, 2, 3], "$.amount", "$.request_body.amount"),
        ("$.amount", "$.amount", "$.request_body.amount"),
    ]
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://plate-real"
        ) as real:
            plate_client.set_client_for_tests(real)
            try:
                for value, jsonpath, target in cases:
                    data = await plate_client.convert(_compose(value, jsonpath))
                    converted = data["converted"]
                    strat = converted["steps"][0]["strategy"]
                    assert strat[0]["kind"] == "assertion"          # 既有断言同链存活
                    assert {"kind": "assign", "source": value, "target": target} == {
                        k: v for k, v in strat[-1].items()
                        if k in ("kind", "source", "target")}
                    assert strat[-1]["target"] == target
                    if value == "$.amount":
                        # 引用形:兜底键随 convert 一起穿出
                        assert strat[-1]["default"] == "$.amount"
                        assert strat[-1]["required"] is False
                    Scenario.model_validate(converted)               # 真引擎收得下
            finally:
                plate_client.set_client_for_tests(None)


async def test_json_null_value_boundary_is_recorded_not_silently_written():
    """边界记录(不是期望行为):JSON null 偏离值**无法送达**引擎 ——
    plate 导出 `model_dump(exclude_none=True)` 把 source=None 整键丢弃,
    引擎 `Assign.source` 必填 → 该 case 加载即 ValidationError。故
    `_assign_strategy` 对 null 不置 required:false(改不了结局,只会把
    「单步失败」伪装成成功);编辑器对 null 值显形警告。plate 若改为保留
    null,此测试应同步放开。"""
    from pydantic import ValidationError

    from gimbal_plate.http.app import create_app
    import httpx

    from app.services import plate_client
    from gimbal.schema.scenario import Scenario

    composed = _compose(None)
    assert composed["steps"][0]["strategy"][-1]["source"] is None   # compose 原样保留用户值
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://plate-real"
        ) as real:
            plate_client.set_client_for_tests(real)
            try:
                data = await plate_client.convert(composed)
            finally:
                plate_client.set_client_for_tests(None)
    assert "source" not in data["converted"]["steps"][0]["strategy"][-1]
    with pytest.raises(ValidationError):
        Scenario.model_validate(data["converted"])
