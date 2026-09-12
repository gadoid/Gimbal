"""run_injection — 注入条目物化纯函数 + 集成(spec v3 §3)。"""
import asyncio
import sys
from pathlib import Path

import pytest

from app.services.run_injection import (
    as_step_index,
    compose_injection_scenario,
    entry_issues,
    injectable_universe,
)
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


# ── 可注入面(spec v3.1 §2.1):声明命中的路径不再判悬空 ──────────────
_DECLARED = frozenset({"$.bl_no", "$.customer_id", "$.items", "$.items.sku"})


def _universe_of(body_of, declared):
    """``entry_issues`` 的第 5 参现在是**预计算好的**可注入面查表
    (``Callable[[int], set[str]]``),不再是声明路径集 —— 归一/前缀展开由
    生产侧 :func:`injectable_universe` 统一做。本帮助函数即该预计算
    (等价于本模块历史上在 ``_path_resolvable`` 内部就地重建的那份)。"""
    return lambda si: injectable_universe(body_of(si), declared)


def test_declared_path_is_resolvable_even_when_absent_from_body():
    """carry 字段(契约声明、body 无)放宽后可寻址 —— 本次 spec 的核心。

    universe_of 缺省(不传)→ 只剩 ``{"$"}`` 那张表 → 该 path 仍判死
    (兼容面,见 test_empty_declared_of_falls_back_to_body_only)。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.customer_id"},
             "value": 1, "asserts": []}
    body_of = _body_of(DEF["steps"])          # DEF 的 body 只有 $.amount/$.bl_no
    targets = _targets_of(DEF["steps"])
    assert {"kind": "path-unresolvable", "stepIndex": 0,
            "jsonpath": "$.customer_id"} in entry_issues(entry, 2, body_of, targets)
    assert entry_issues(entry, 2, body_of, targets,
                        _universe_of(body_of, _DECLARED)) == []


def test_undeclared_path_still_dangling():
    """两边都没有 → 仍判死(拼写错误仍被抓)。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.ghost"},
             "value": 1, "asserts": []}
    body_of = _body_of(DEF["steps"])
    issues = entry_issues(entry, 2, body_of, _targets_of(DEF["steps"]),
                          _universe_of(body_of, _DECLARED))
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.ghost"} in issues


def test_instance_path_matches_template_declaration():
    """实例路径 $.items[0].sku 对齐契约模板声明 $.items.sku。"""
    body_of = _body_of([{"request": {"body": {}}}])       # body 里没有 items
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.items[0].sku"},
             "value": 1, "asserts": []}
    assert entry_issues(entry, 1, body_of, lambda si: set(),
                        _universe_of(body_of, _DECLARED)) == []


def test_empty_declared_of_falls_back_to_body_only():
    """降级:声明面为空集 → universe 只剩 body 面 ∪ {"$"}(从严)。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.customer_id"},
             "value": 1, "asserts": []}
    body_of = _body_of(DEF["steps"])
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.customer_id"} in \
        entry_issues(entry, 2, body_of, _targets_of(DEF["steps"]),
                     _universe_of(body_of, ()))


def test_declared_face_is_normalized_like_frontend_injectable_path_set():
    """声明面条目自身可带实例下标(plate 只强制 children 子树为模板态)→
    两侧都必须先归一,否则出现「编辑器判活、dispatch 静默 skip」的判定层
    分裂(与前端 `injectablePathSetOf` 的 `toTemplatePath(p)` 同落点)。"""
    declared = frozenset({"$.supplier[0].code", "$.bl_no"})
    body_of = _body_of([{"request": {"body": {}}}])       # body 里没有 supplier

    def _entry(jp: str) -> dict:
        return {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                        "jsonpath": jp},
                "value": 1, "asserts": []}

    # 声明 `$.supplier[0].code` → 同实例、异实例、模板形态三种锚点都判活
    for jp in ("$.supplier[0].code", "$.supplier[1].code", "$.supplier.code"):
        assert entry_issues(_entry(jp), 1, body_of, lambda si: set(),
                            _universe_of(body_of, declared)) == [], jp
    # 归一不等于放宽:声明面外的路径仍判死(拼写错误仍被抓)
    assert {"kind": "path-unresolvable", "stepIndex": 0,
            "jsonpath": "$.supplier.name"} in \
        entry_issues(_entry("$.supplier.name"), 1, body_of, lambda si: set(),
                     _universe_of(body_of, declared))


def test_body_face_covers_container_prefixes_like_frontend():
    """终审 F2:body 面按 spec §2.1 公式补齐 —— 此前**替代**成了
    `jsonpath.exists`(实例精确判),少了 `prefixes(body)` 与两形态的前缀
    子句 ⇒ 下面两例「编辑器判活、dispatch 静默 skip」(终审给的正是这两个
    反例方向,后端必须转活)。"""
    def _entry(jp: str) -> dict:
        return {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                        "jsonpath": jp},
                "value": 1, "asserts": []}

    # 方向一:数组越界 —— 前端 `toTemplatePath('$.tags[9]')='$.tags'`,命中
    # 容器前缀(universe 建时已 materialize 出 `$.tags`)→ 判活;exists 越界 → 判死。
    arr_body = _body_of([{"request": {"body": {"tags": ["a", "b"]}}}])
    assert entry_issues(_entry("$.tags[9]"), 1, arr_body, lambda si: set(),
                        _universe_of(arr_body, ())) == []
    # 方向二:键含点 —— 叶子 `$.a.b.c` 的容器前缀含 `$.a.b`(段边界字面比),
    # universe 命中;`exists` 会去取 a→b(a 下没有键 b)→ 判死。
    dotted = _body_of([{"request": {"body": {"a": {"b.c": 1}}}}])
    assert entry_issues(_entry("$.a.b"), 1, dotted, lambda si: set(),
                        _universe_of(dotted, ())) == []
    # 补前缀不等于放宽:越界段之后再拼一段,两形态都不命中 → 仍判死
    assert {"kind": "path-unresolvable", "stepIndex": 0,
            "jsonpath": "$.tags[9].nope"} in \
        entry_issues(_entry("$.tags[9].nope"), 1, arr_body, lambda si: set(),
                     _universe_of(arr_body, ()))
    # body 面外(拼写错误)仍判死 —— 与既有用例同向,新增前缀面不误救
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.tags2"} in \
        entry_issues(_entry("$.tags2"), 1, arr_body, lambda si: set(),
                     _universe_of(arr_body, ()))


def test_body_face_prefix_matches_frontend_injectable_path_set():
    """同上两个方向,声明面为空(降级态)下也必须转活 —— universe 是
    body ∪ declared 的全集,不是「只有声明面才有前缀」。"""
    body_of = _body_of([{"request": {"body": {"a": {"b.c": 1}, "tags": ["a"]}}}])
    for jp in ("$.a.b", "$.tags[9]", "$.a", "$.tags"):
        entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                         "jsonpath": jp}, "value": 1, "asserts": []}
        assert entry_issues(entry, 1, body_of, lambda si: set(),
                            _universe_of(body_of, ())) == [], jp


# ── stepIndex 归一(Z3)/ 可注入面纯函数化(P)────────────────────────
def test_step_index_accepts_integral_float_rejects_bool():
    """Z3:JSON 只有一种数字类型 —— 后端与前端的 Number.isInteger 同构。"""
    assert as_step_index(1) == 1
    assert as_step_index(1.0) == 1          # JSON 1.0 → JS 也是整数
    assert as_step_index(True) is None      # bool 不是数字(前端 Number.isInteger(true) 为假)
    assert as_step_index("0") is None
    assert as_step_index(None) is None


def test_injectable_universe_covers_body_prefixes_and_declared():
    """P/§2.1:universe 是纯函数,可单测(不再藏在判定里每次重建)。"""
    u = injectable_universe({"tags": ["a", "b"]}, frozenset({"$.customer_id"}))
    assert {"$", "$.tags", "$.tags[0]", "$.tags[1]", "$.customer_id"} <= u


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


async def test_dispatcher_keeps_entry_anchored_on_declared_carry_path(
    client, plate_mock: PlateMock, monkeypatch
):
    """契约声明了 $.customer_id(carry,body 无)→ 条目不再被 skip;
    plate 不可得声明面时该条目仍被 skip(降级从严)。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(steps=[
        {"id": "s1", "api": {"kind": "api", "service": "fin-svc", "method": "POST",
                             "path": "/order", "headers": {},
                             "view_hints": {"endpoint_id": "ep-carry-x"}},
         "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
        {"id": "s2", "strategy": []},
    ], vars_map={"bl_no": "BL1"})
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-carry", "name": "carry 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 261, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    plate_mock.fulls["ep-carry-x"] = {"request": {"declarations": [
        {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
        {"name": "customer_id", "path": "$.customer_id", "state": "carry", "required": True},
    ]}}
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-carry"]})
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1                      # 未被 skip(此前会是 0 case)
    st = cases[0]["steps"][0]["strategy"]
    assert {"kind": "assign", "source": 261, "target": "$.request_body.customer_id"} in st

    # 降级:声明面不可得 → 同一条目重新被判死(skip),不炸 dispatch
    plate_mock.fulls.pop("ep-carry-x")
    from app.services.endpoint_declarations import _reset_declared_paths_cache
    _reset_declared_paths_cache()
    cases.clear()
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-carry"]})
    assert r.status_code == 201, r.text
    # 降级从严:条目仍被判死 → skip;派发的只剩基线 case(无该条目的
    # Assign 直补)—— 判定退回 body 面,不是"整单不发"。
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1
    assert {"kind": "assign", "source": 261,
            "target": "$.request_body.customer_id"} not in \
        cases[0]["steps"][0]["strategy"]


async def test_dispatcher_fetches_declaration_face_only_for_referenced_steps(
    client, plate_mock: PlateMock, monkeypatch
):
    """懒取(任务口径 §2):只为**被选中条目实际引用到的步骤**取声明面 ——
    未选中条目的 step 与无 ``view_hints.endpoint_id`` 的 step 一次都不取
    (无谓 plate 往返为零);无声明面步骤的条目照旧按 body 面判定。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member
    from app.services import run_dispatcher as _disp

    bob = await _member(client, "bob")
    draft = _draft(steps=[
        {"id": "s1", "api": {"view_hints": {"endpoint_id": "ep-a"}},
         "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
        {"id": "s2", "api": {"view_hints": {"endpoint_id": "ep-b"}},
         "request": {"body": {"x": 1}}, "strategy": []},
        {"id": "s3", "request": {"body": {"y": 1}}, "strategy": []},   # 无 endpoint_id
    ], vars_map={"bl_no": "BL1"})
    draft["assertion_registry"] = {"entries": [
        {"id": "inj-a",                                  # 选中:step 0(有声明面)
         "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
         "value": 1, "asserts": []},
        {"id": "inj-b",                                  # 未选中 → 其 step 不取数
         "path": {"stepIndex": 1, "source": "body", "jsonpath": "$.nope"},
         "value": 1, "asserts": []},
        {"id": "inj-c",                                  # 选中:step 2(无 endpoint_id)
         "path": {"stepIndex": 2, "source": "body", "jsonpath": "$.y"},
         "value": 1, "asserts": []},
    ]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    plate_mock.fulls["ep-a"] = {"request": {"declarations": [
        {"name": "customer_id", "path": "$.customer_id", "state": "carry"},
    ]}}
    plate_mock.fulls["ep-b"] = {"request": {"declarations": [
        {"name": "nope", "path": "$.nope", "state": "carry"},
    ]}}

    seen: list[str] = []
    _real = _disp.declared_paths_of

    async def _spy(eid):
        seen.append(eid)
        return await _real(eid)

    monkeypatch.setattr(_disp, "declared_paths_of", _spy)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-a", "inj-c"]})
    assert r.status_code == 201, r.text
    # 取数在 dispatch 同步段完成:响应回来时清单已定格(无竞态)。
    assert seen == ["ep-a"]                 # ep-b 未被选中 → 不取;step2 无 eid → 不取
    await _wait(lambda: len(cases) >= 2)
    assert len(cases) == 2                  # 两条选中条目都存活(一条走声明面,一条走 body 面)


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


def _preprocess(scenario_dict: dict) -> list:
    """真引擎预处理(认证 + 模板展开),返回 resolved steps —— 策略执行的
    上游:ScenarioPreprocessor 在**任何 strategy 执行之前**跑完整 scenario
    (gimbal/core/scenario_runner.py:258-266)。延迟导入:只在真预处理
    用例里加载引擎包。"""
    from gimbal.config.models import BootstrapConfig
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.schema.scenario import Scenario

    steps, _base_url, _services = ScenarioPreprocessor(
        scenario_schema=Scenario.model_validate(scenario_dict),
        bootstrap_config=BootstrapConfig(),
    ).run()
    return steps


def test_jsonpath_value_class_passes_the_preprocessor_untouched():
    """`$.` 前缀串**不是模板**(预处理器的模板正则只认 `${...}`,
    gimbal/utils/jsonpath.py:603/736)→ 原样穿过预处理,default/required
    也随之活到 Assign 执行期 —— 这正是平台侧兜底能生效的前提。"""
    st = _preprocess(_compose("$.amount"))[0].strategy[-1]
    assert st.source == "$.amount"
    assert st.default == "$.amount"
    assert st.required is False


def test_template_value_class_fails_in_the_preprocessor_not_in_the_assign():
    """边界(记录,不是期望行为):整串 `${...}` 类的**变量缺失**结局 ——
    引擎在策略执行前做模板展开,`_resolve_strategy` 把 `Assign.source` 与
    `Assign.default` 一并过 `_resolve_or_fail`(scenario_preprocessor.py:
    416-429)→ 预处理阶段 `ValueError`,比 Assign 更早,平台补的 default
    从未被读过(失败点不是 BEFORE_REQUEST)。"""
    composed = _compose("${var.ghost}")          # config.vars 无 ghost
    # 平台产出的形状本身合法(source/default/required 都在)
    assert composed["steps"][0]["strategy"][-1]["default"] == "${var.ghost}"
    # 失败点必须**是预处理器**(不是 Assign 的 resolved-to-None)
    with pytest.raises(ValueError, match=r"\[Preprocessor\].*ghost"):
        _preprocess(composed)


def test_template_value_class_writes_the_vars_value_not_the_literal():
    """边界(记录):整串 `${...}` 类的**变量存在**结局 —— source(以及
    default)被预处理器改写成变量值 → 字面量**不写入**,该偏离对该字段
    实际不生效。平台侧不修(修它就得往 config.vars 塞哨兵,spec §3 把
    「compose 不触碰 config.vars」定为核心保证)。"""
    composed = _compose("${var.amount}")          # config.vars.amount = 100
    st = _preprocess(composed)[0].strategy[-1]
    assert st.source == 100                       # 变量值,不是 "${var.amount}"
    assert st.default == 100                      # default 同样被改写(死重,无害)
    assert st.required is False
