# IO 声明归一化(declarations 唯一真源)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** fields/carry/assertable_fields 三轴收敛为 `declarations` 单一承重存储(通道标记条目清单),旧轴全部变为派生投影,线上 /full 既有键逐键不变、新增 declarations 键;P1 读侧统一 → P2 存储翻转(构造桥保 17 文件零 diff)。

**Architecture:** plate 契约层单点改造:`io_spec.py` 新增 DeclarationEntry(path 唯一、channel ∈ binding/carry/view_only、B6 禁值),RequestSpec/ResponseSpec 存储切到 declarations,构造桥(model_validator mode=before)把旧参数编译成清单,fields/carry/assertable_fields 变 @property 派生;declare() 类方法从 schema 节点吸收元数据;platform service_fields 切读 declarations;golden 三角(①②③)以提交进库的 fixture 锁线上等价。

**Tech Stack:** Pydantic v2(模型/校验器/序列化器)/ FastAPI(backend 切读)/ pytest(plate 与 backend)/ 无前端改动。

**Spec:** `docs/superpowers/specs/2026-09-01-io-declarations-unification-design.md`(已评审定稿,3719ef7;本计划从 spec 立论,执行者须同时读 spec —— B1–B7 裁定、§3.5 落点闭合、§8 测试矩阵是本计划的验收依据)

## Global Constraints

- **测试命令**:plate = repo 根 `python -m pytest tests/plate/<file> -v`;backend = `cd src/gimbal-platform/backend && python -m pytest tests/<file> -v`;三套件 = plate `tests/plate`、backend 全量 `python -m pytest -q`、前端 `npm run typecheck && npm test`(本计划不动前端,前端门禁只作回归)。
- **工作分支**:`feat/io-declarations-unification`,从 `feat/carry-fields-storage-injection`(3719ef7)开出;commit 中文,尾部 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- **线上等价铁律**(spec §1.1/1.2/4.3):/full 既有键(body_type/fields/schema/carry/assertable_fields)逐键逐字节不变;唯一增量 = declarations 键(有声明才发);schema 内容一字不动,不合成。
- **键序约定**(spec §4.3):declarations = binding/view_only 条目(输入序)在前,carry 条目(输入序)在后;P1 view 与 P2 桥两处实现显式遵循同一约定。
- **基线口径**(spec §0.3):ALL_ENDPOINTS = 18(fin 全量,account_query_balance 在内);有声明端点 17 + account(零声明,request 缺席、响应 schema-only);声明总数 747 = 737 binding/view_only + 10 carry;**fixture 是计数权威**(grep 行级 736/出现级 737 有出入,以 Task 1 捕获实测为准);**捕获只补缺** —— 两个 fixture 的捕获分支均带 `not FIXTURE.exists()` 守卫,fixture 提交后任何 CAPTURE 运行都走比对分支,re-baseline 必须显式删文件再捕(单开 commit 说明原因)。
- **2026-09-02 漂移预警**:文档定稿(1f04edb)后语料已大改 —— 73cc71b 把 order_entrust 委托下单重构为 3 binding + 80 余 carry、响应 view_only 大批转 schema-only,carry 面 10→99、binding 面 737→524(HEAD 实测);根路径 `$` 先例随重构消失(entrust 已提交删除,order_detail 在未提交工作树中)。**本节 747/737/10、Task 1 计数断言、Task 2 test_coverage_747 与 test_root_path_entry 前提均已过期** —— 执行日 Task 1 以 fixture 实测重新钉数(spec §0.3 + 本计划一并改,单开 commit);根路径测试按届时语料换锚或删除;`or "$"` 兜底逻辑与 Task 5 根路径用例保留(模型规则仍允许,只是不再有现网实例)。
- **端点归属**:settlement 唯一 declare() 迁移(Task 8);其余 17(fin 16 + account)走构造桥零改动 —— account 归桥是被线上等价逼定(spec §8 ②)。
- **②③ 基线不混用**(spec §8):② 的 binding 条目 type 恒 None(桥不吸收),③ 的 type 恒吸收值;两测试各自独立断言,不共享基线对象。
- **政策守卫不可删**:`tests/plate/test_v3_systems_fin.py::TestCarryFacesAllEndpoints` 在 P2 派生属性下必须零改动通过(spec §5 分层声明);任何任务不得"顺手优化"它。
- **值/声明分离(B6)**:carry 条目 default/example 必为 None;enum 不禁。
- **P3 不做**:不移除旧线上键、不移除构造桥、不动前端(spec §11.1 挂账)。

---

### Task 1: golden 基线物化 — pre-P1 /full fixture + 既有键等价测试 ①

**Files:**
- Create: `tests/plate/test_io_declarations_golden.py`
- Create: `tests/plate/fixtures/io_full_pre_p1.json`(捕获产物,提交进库)

**Interfaces:**
- Consumes: `gimbal_plate.http.views.EndpointDetailView`(views.py:142;`from_spec(ep).model_dump(mode="json", exclude_none=True)` 即 /full 端点载荷 —— routes_grammar 的 full_view_factory 走此视图);`gimbal_plate.systems.fin.endpoint.ALL_ENDPOINTS`(18 个)
- Produces: `_full_dict(ep)` helper 与 fixture 文件 —— Task 4/9 复用;`LEGACY_REQUEST_KEYS = {"body_type","fields","schema","carry"}`、`LEGACY_RESPONSE_KEYS = {"status","description","fields","assertable_fields","schema"}`

- [ ] **Step 1: 确认 /full 出口的序列化参数**

Run: `git grep -n "model_dump" -- src/gimbal-plate/gimbal_plate/http/routes_grammar.py | head`
预期:full 路由经视图类 dump(mode="json", exclude_none=True)。若参数不同,Task 内所有 `_full_dict` 以实际参数为准(golden 必须镜像真实出口,不能镜像假设)。

- [ ] **Step 2: 写基线测试(含捕获模式)**

```python
# tests/plate/test_io_declarations_golden.py
"""IO 声明归一化 golden 三角(spec §8 ①②③)。

fixture 纪律:基线物化提交进库;corpus 漂移 = 红,强制 diff 可见的
意识性 re-baseline(改 fixture 必须单开 commit 说明原因)。
"""
import json
import os
from pathlib import Path

import pytest

from gimbal_plate.http.views import EndpointDetailView
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS

FIXTURE = Path(__file__).parent / "fixtures" / "io_full_pre_p1.json"
CAPTURE = bool(os.environ.get("GIMBAL_GOLDEN_CAPTURE"))
LEGACY_REQUEST_KEYS = {"body_type", "fields", "schema", "carry"}
LEGACY_RESPONSE_KEYS = {"status", "description", "fields", "assertable_fields", "schema"}


def _full_dict(ep) -> dict:
    return EndpointDetailView.from_spec(ep).model_dump(mode="json", exclude_none=True)


def _ep_payloads() -> dict:
    return {ep.id: _full_dict(ep) for ep in ALL_ENDPOINTS}


def test_capture_or_equal() -> None:
    """① 前半:capture 模式写盘;断言模式锁既有键,新增仅 declarations。"""
    live = _ep_payloads()
    # 捕获只补缺,从不覆写:fixture 提交后,任何 CAPTURE 运行(含 Task 4
    # 的第二基线捕获)都落进比对分支 —— pre_p1 不可能被 P1 末态静默污染
    if CAPTURE and not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        pytest.skip("baseline captured")
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert set(live) == set(base), "端点集合漂移"
    for ep_id in base:
        _assert_request(base[ep_id], live[ep_id])
        for code in base[ep_id].get("responses", {}):
            _assert_response(base[ep_id]["responses"][code],
                             live[ep_id]["responses"][code])


def _assert_request(base: dict, live: dict) -> None:
    if base.get("request") is None:
        assert live.get("request") is None
        return
    lr, lv = base["request"], live["request"]
    for k in LEGACY_REQUEST_KEYS & lr.keys():
        assert lv.get(k) == lr[k], f"request.{k} 漂移"
    assert set(lv) - set(lr) <= {"declarations"}, "新增键超出 declarations"


def _assert_response(base: dict, live: dict) -> None:
    for k in LEGACY_RESPONSE_KEYS & base.keys():
        assert live.get(k) == base[k], f"response.{k} 漂移"
    assert set(live) - set(base) <= {"declarations"}, "新增键超出 declarations"


def test_baseline_counts() -> None:
    """基线计数权威:747 = 737 + 10(fixture 实测;grep 行级 736 是假象)。"""
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bindings = sum(len((b.get("request") or {}).get("fields") or [])
                   for b in base.values())
    views = sum(len(r.get("fields") or [])
                for b in base.values()
                for r in b.get("responses", {}).values())
    carries = sum(len((b.get("request") or {}).get("carry") or {})
                  for b in base.values())
    assert bindings + views == 737, f"binding/view_only 总数 {bindings + views} != 737(若红:以 fixture 实测重新核对 spec §0.3 并意识性更新)"
    assert carries == 10
```

若计数红:停下来用 `git grep -o "IOFieldBinding(" -- src/gimbal-plate/gimbal_plate/systems/fin/endpoint | wc -l` 出现级计数交叉核对,确认是基线数字错还是实现错,**不许静默改断言**。

- [ ] **Step 3: 捕获基线并验证**

Run: `GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_io_declarations_golden.py -v` 然后 `python -m pytest tests/plate/test_io_declarations_golden.py -v`
预期:第一次 skip(捕获),第二次 PASS(此时 live==base 全等)。

- [ ] **Step 4: Commit**

```bash
git add tests/plate/test_io_declarations_golden.py tests/plate/fixtures/io_full_pre_p1.json
git commit -m "test(plate): golden 基线物化 — pre-P1 /full fixture(① 既有键等价)"
```

---

### Task 2: declarations_view() 派生视图 + _serialize 发射 declarations 键(P1 核心)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`(RequestSpec/ResponseSpec 各加 `declarations_view()`;两个 `_serialize` 各加发射)
- Test: `tests/plate/test_io_declarations_p1.py`(新建)

**Interfaces:**
- Consumes: 现行存储 `self.fields / self.carry / self.assertable_fields`;`gimbal_plate.utils.path.last_segment`(io_spec 已 import 为 `_path`)
- Produces: `RequestSpec.declarations_view() -> list[dict]`、`ResponseSpec.declarations_view() -> list[dict]`,条目 dict 键集 = §3.1 DeclarationEntry 字段名(name/path/channel/type/required/default/example/description/enum/ui_kind/source_kind/assertable)。Task 6 将用真模型替换 dict 形状(P2 存储翻转时本方法退役为读存储)。

- [ ] **Step 1: 写失败测试**

```python
# tests/plate/test_io_declarations_p1.py
"""P1:declarations_view 派生视图(spec §3.1 形状、§4.3 键序)。"""
from gimbal_plate.schema.endpoint.io_spec import (
    CarryEntry, IOFieldBinding, RequestSpec, ResponseSpec,
)
from gimbal_plate.systems.fin.endpoint import (
    ALL_ENDPOINTS, SETTLEMENT_CREATE_ORDER, ACCOUNT_QUERY_BALANCE,
    ORDER_ENTRUST_ORDER_ADD,
)


def _by_channel(entries):
    return [e for e in entries if e["channel"] != "carry"], \
           [e for e in entries if e["channel"] == "carry"]


class TestDeclarationsView:
    def test_request_channels_and_order(self) -> None:
        rs = RequestSpec(
            body_type="json", schema_={},
            fields=[IOFieldBinding(name="remark", path="$.remark")],
            carry={"$.notes": CarryEntry(description="备注", type="string")},
        )
        dv = rs.declarations_view()
        non_carry, carry = _by_channel(dv)
        assert [e["path"] for e in non_carry] == ["$.remark"]
        assert all(e["channel"] == "binding" for e in non_carry)
        assert [e["path"] for e in carry] == ["$.notes"]
        assert carry[0]["type"] == "string" and carry[0]["description"] == "备注"
        assert all(e["assertable"] is False for e in dv)  # 请求侧恒 False

    def test_response_assertable_mapping(self) -> None:
        resp = ResponseSpec(
            status=200, schema_={},
            fields=[IOFieldBinding(name="audit_id", path="$.data.data[0].audit_id"),
                    IOFieldBinding(name="total", path="$.data.total")],
            assertable_fields=["$.data.total"],
        )
        dv = resp.declarations_view()
        assert all(e["channel"] == "view_only" for e in dv)
        by_path = {e["path"]: e for e in dv}
        assert by_path["$.data.total"]["assertable"] is True
        assert by_path["$.data.data[0].audit_id"]["assertable"] is False

    def test_root_path_entry(self) -> None:
        # order_entrust 响应现网 name='$' 先例(spec §3.1)
        rs = ORDER_ENTRUST_ORDER_ADD.request
        dv = rs.declarations_view()
        root = [e for e in dv if e["path"] == "$"]
        assert all(e["name"] == "$" for e in root)

    def test_coverage_747(self) -> None:
        total = 0
        for ep in ALL_ENDPOINTS:
            if ep.request:
                total += len(ep.request.declarations_view())
            total += sum(len(r.declarations_view())
                         for r in ep.responses.values())
        assert total == 747, f"declarations 覆盖 {total} != 747"

    def test_serialize_emits_only_when_present(self) -> None:
        rs = RequestSpec(body_type="json", schema_={})
        assert "declarations" not in rs.model_dump(mode="json")
        # account:零声明端点,full 视图不含 declarations(⑨ 的前置事实)
        full = ACCOUNT_QUERY_BALANCE.request
        assert full is None or not full.declarations_view()

    def test_settlement_carry_entry_shape(self) -> None:
        dv = SETTLEMENT_CREATE_ORDER.request.declarations_view()
        remark = next(e for e in dv if e["path"] == "$.remark")
        assert remark["channel"] == "carry"
        assert remark["description"] == "备注(随请求传递,不进表单)"
        assert remark["default"] is None and remark["example"] is None  # B6 形状
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_io_declarations_p1.py -v`
预期:FAIL — `declarations_view` 不存在(AttributeError)。

- [ ] **Step 3: 实现 declarations_view 与序列化发射**

RequestSpec(响应同构,channel 换 view_only + assertable 映射):

```python
def declarations_view(self) -> list[dict[str, Any]]:
    """§3.1 形状条目(纯派生,不动存储)。键序:binding 在前、carry 在后。"""
    out: list[dict[str, Any]] = []
    for f in self.fields:
        out.append({"name": f.name, "path": f.path, "channel": "binding",
                    "type": None, "required": f.required, "default": f.default,
                    "example": f.example, "description": f.description,
                    "enum": f.enum, "ui_kind": f.ui_kind,
                    "source_kind": f.source_kind, "assertable": False})
    for path, c in self.carry.items():
        # 根路径 "$" 的 last_segment 为 None → name="$"(现网先例)
        out.append({"name": _path.last_segment(path) or "$", "path": path,
                    "channel": "carry", "type": c.type, "required": True,
                    "default": None, "example": None,
                    "description": c.description, "enum": None,
                    "ui_kind": "unknown", "source_kind": "independent",
                    "assertable": False})
    return out
```

ResponseSpec 版本:fields 循环里 `channel="view_only"`、`assertable=path in set(self.assertable_fields)`;无 carry 循环。

两个 `_serialize` 末尾(before return)加:

```python
        decls = self.declarations_view()
        if decls:
            out["declarations"] = decls
```

- [ ] **Step 4: 跑本文件测试与 golden ①**

Run: `python -m pytest tests/plate/test_io_declarations_p1.py tests/plate/test_io_declarations_golden.py -v`
预期:全 PASS(① 允许新增 declarations 键 —— `set(lv) - set(lr) <= {"declarations"}` 已放行)。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py tests/plate/test_io_declarations_p1.py
git commit -m "feat(plate): declarations_view 派生视图 + /full 发射 declarations 键(P1)"
```

---

### Task 3: platform service_fields 切读 declarations + ⑨ 缺键容忍

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/carry.py:81`(service_fields 的 carry 面提取段)
- Test: backend 侧 carry router 既有测试文件(Step 1 定位;若无对应文件则 Create `tests/test_carry_service_fields.py`)

**Interfaces:**
- Consumes: /full 的 `request.declarations` 键(Task 2 产物;条目含 channel/path/type/description)
- Produces: service_fields 输出形状不变(`ServiceFieldsOut{fields, degraded}`),数据源从 `request.carry` 切到 declarations 的 carry 条目

- [ ] **Step 1: 定位既有测试**

Run: `cd src/gimbal-platform/backend && git grep -ln "service_fields" -- tests`
有 → 改该文件;无 → 新建。以下按"新建"给代码,改既有文件则追加同类用例。

- [ ] **Step 2: 写失败测试**

```python
"""service_fields 切读 declarations(spec §7 P1.3)+ ⑨ 缺键容忍。"""
from app.routers.carry import service_fields  # 按既有测试的 app 导入约定


class TestServiceFieldsDeclarations:
    async def test_reads_carry_channel_entries(self, monkeypatch) -> None:
        # 两端点:一个带 declarations,一个无(⑨:account 形态 —— request 缺席)
        async def fake_full(ep_id):
            if ep_id == "fin.settlement.create_order":
                return {"request": {"declarations": [
                    {"path": "$.remark", "channel": "carry",
                     "type": "string", "description": "备注"},
                    {"path": "$.order_id", "channel": "binding",
                     "type": None, "description": "单号"},
                ]}}
            return {}  # account:无 request → 无 declarations 键
        ...  # patch _plate_list_endpoints_filtered/_plate_full_endpoint 按
             # 该文件既有 monkeypatch 模式;断言 fields 只有 $.remark(binding
             # 条目被过滤)、degraded=False、无空占位条目

    async def test_degrades_on_plate_failure(self, monkeypatch) -> None:
        ...  # 复用既有降级用例形状:任一 /full 失败 → degraded=True
```

`...` 处按该测试文件既有 fixture/monkeypatch 风格补全 —— 断言要点写死:`{f.path for f in out.fields} == {"$.remark"}`、`degraded is False`。

- [ ] **Step 3: 实现切读**

carry.py service_fields 循环体替换:

```python
        decls = ((full.get("request") or {}).get("declarations")) or []
        for entry in decls:
            if entry.get("channel") != "carry":
                continue  # 消费面只取 carry 通道(spec §7 P1.5 免疫链)
            path = str(entry.get("path") or "")
            faces.setdefault(path, CarryFieldFace(
                path=path,
                type=str(entry.get("type") or "string"),
                description=str(entry.get("description") or ""),
            ))
```

- [ ] **Step 4: 跑 backend 测试 + plate golden**

Run: `cd src/gimbal-platform/backend && python -m pytest tests -q -k "carry or service"`;repo 根 `python -m pytest tests/plate/test_io_declarations_golden.py -v`
预期:PASS。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/routers/carry.py src/gimbal-platform/backend/tests/
git commit -m "feat(platform): service_fields 切读 declarations carry 条目 + ⑨ 缺键容忍"
```

---

### Task 4: P1 收尾 — declarations 快照 fixture(为 ② 备)+ 三套件门禁

**Files:**
- Create: `tests/plate/fixtures/io_declarations_p1.json`
- Modify: `tests/plate/test_io_declarations_golden.py`(捕获第二基线)

**Interfaces:**
- Produces: P1 末 declarations 快照(**捕获自 `_full_dict` 出口的 declarations 键**,非 declarations_view() 旁路)—— Task 9 golden ② 的比对基线(② = 既有键对 pre_p1 + declarations 对 p1 快照,两侧同序列化路径)

- [ ] **Step 1: 扩展捕获**

test_io_declarations_golden.py 增加:

```python
FIXTURE_DECL = Path(__file__).parent / "fixtures" / "io_declarations_p1.json"


def _decl_payloads() -> dict:
    """declarations 快照:从 _full_dict 里摘取 declarations 键。

    必须与 Task 9 ② 的比对走同一序列化出口(EndpointDetailView.
    model_dump(mode="json", exclude_none=True))。若另走
    declarations_view() 旁路捕获,exclude_none 对嵌套 dict 的裁剪
    行为差异会在 ② 处爆成假红;同出口捕获,任何裁剪两侧自然抵消。
    """
    out = {}
    for ep in ALL_ENDPOINTS:
        full = _full_dict(ep)
        d: dict = {}
        if (full.get("request") or {}).get("declarations"):
            d["request"] = full["request"]["declarations"]
        resp = {str(code): r["declarations"]
                for code, r in full.get("responses", {}).items()
                if r.get("declarations")}
        if resp:
            d["responses"] = resp
        if d:
            out[ep.id] = d
    return out


def test_capture_or_equal_declarations() -> None:
    live = _decl_payloads()
    # 捕获只补缺,不覆写(与 pre_p1 同款守卫)
    if CAPTURE and not FIXTURE_DECL.exists():
        FIXTURE_DECL.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        pytest.skip("declarations baseline captured")
    base = json.loads(FIXTURE_DECL.read_text(encoding="utf-8"))
    assert live == base, "declarations 漂移(P1 末基线,Task 9 ② 依赖)"
```

Run: `GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_io_declarations_golden.py -v && python -m pytest tests/plate/test_io_declarations_golden.py -v` → skip + PASS。此跑时 pre_p1 已提交 → 守卫使其走比对分支(既有键 P1 未动,绿),只有 decl 基线落盘;`git status` 不应出现 io_full_pre_p1.json 的改动。

- [ ] **Step 2: P1 门禁:三套件**

Run:repo 根 `python -m pytest tests/plate -q`;`cd src/gimbal-platform/backend && python -m pytest -q` (346+);`cd src/gimbal-platform/frontend && npm run typecheck && npm test`(401)。
预期:全绿(plate 允许 +新增用例)。**任何红在此停,不带病进 P2。**

- [ ] **Step 3: Commit(P1 完成断点)**

```bash
git add tests/plate/fixtures/io_declarations_p1.json tests/plate/test_io_declarations_golden.py
git commit -m "test(plate): P1 末 declarations 快照基线 + P1 三套件门禁通过"
```

---

### Task 5: DeclarationEntry 模型 + 条目级校验(B6/enum/path/name)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`(IOFieldBinding 与 CarryEntry 之间插 DeclarationEntry)
- Test: `tests/plate/test_schema_endpoint.py`(末尾追加)

**Interfaces:**
- Consumes: `_path.is_valid_path / normalize / last_segment`;CarryEntry 的六原语词表常量(复用同一词表对象,不复制)
- Produces: `DeclarationEntry(BaseModel)`(§3.1 全字段,extra=forbid)—— Task 6 存储/Task 7 declare()/Task 8 settlement 依赖

- [ ] **Step 1: 写失败测试**

```python
class TestDeclarationEntry:
    """DeclarationEntry 条目级校验(spec §3.1/§5)。spec 级(B7/B4/唯一)在 Task 6。"""

    def test_minimal_binding_entry(self) -> None:
        e = DeclarationEntry(name="remark", path="$.remark", channel="binding")
        assert e.type is None and e.assertable is False

    def test_b6_carry_bans_values(self) -> None:
        DeclarationEntry(name="remark", path="$.remark", channel="carry",
                         type="string")  # 合法
        with pytest.raises(ValueError, match="carry.*default"):
            DeclarationEntry(name="remark", path="$.remark", channel="carry",
                             type="string", default="压测-张三")
        with pytest.raises(ValueError, match="carry.*example"):
            DeclarationEntry(name="remark", path="$.remark", channel="carry",
                             type="string", example="x")
        # enum 不禁(词表约束非值)
        DeclarationEntry(name="level", path="$.level", channel="carry",
                         type="string", enum=["a", "b"])

    def test_carry_type_required_and_vocab(self) -> None:
        with pytest.raises(ValueError, match="carry.*type"):
            DeclarationEntry(name="remark", path="$.remark", channel="carry")
        with pytest.raises(ValueError, match="词表"):
            DeclarationEntry(name="remark", path="$.remark",
                             channel="carry", type="timestamp")

    def test_path_and_name_rules(self) -> None:
        with pytest.raises(ValueError):
            DeclarationEntry(name="x", path="$[0]", channel="binding")
        with pytest.raises(ValueError):
            DeclarationEntry(name="wrong", path="$.remark", channel="binding")
        DeclarationEntry(name="$", path="$", channel="view_only")  # 根路径先例

    def test_enum_membership(self) -> None:
        with pytest.raises(ValueError):
            DeclarationEntry(name="level", path="$.level", channel="binding",
                             enum=["a", "b"], default="c")

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValueError):
            DeclarationEntry(name="x", path="$.x", channel="binding", bogus=1)
```

- [ ] **Step 2: 跑失败** — `python -m pytest tests/plate/test_schema_endpoint.py -k DeclarationEntry -v`,FAIL:未定义。

- [ ] **Step 3: 实现**

```python
class DeclarationEntry(BaseModel):
    """统一声明条目(spec §3.1)—— declarations 清单的元素。"""
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    channel: Literal["binding", "carry", "view_only"]
    type: str | None = None          # 仅 carry 必填(§6 B5)
    required: bool = True
    default: Any | None = None
    example: Any | None = None
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: Literal["text", "number", "boolean", "select", "textarea",
                     "json", "file", "binary", "unknown"] = "unknown"
    source_kind: Literal["independent", "lookup", "generated"] = "independent"
    assertable: bool = False

    @model_validator(mode="after")
    def _validate_entry(self) -> "DeclarationEntry":
        # path/name/enum 规则复用 IOFieldBinding 同款逻辑
        # carry: type 必填且在六原语词表;default/example 必为 None(B6)
        ...
```

`...` 的校验体从 IOFieldBinding/CarryEntry 现行 `_validate` 逐条移植(路径归一 + name==last_segment 含 `$`;enum 非空 → default/example ∈ enum;carry 禁值与词表)。**不复制粘贴两份** —— 若 IOFieldBinding 的校验可提取为模块级函数则提取,IOFieldBinding 改为调用(保持其报错文案不变,现有测试锁文案)。

- [ ] **Step 4: 跑通过 + 全文件回归** — DeclarationEntry 用例 PASS 且 test_schema_endpoint.py 原有用例零失败。

- [ ] **Step 5: Commit** — `git commit -m "feat(plate): DeclarationEntry 模型 + 条目级校验(B6/词表/path)"`

---

### Task 6: 存储翻转 + 构造桥 + 派生属性 + spec 级校验(B7/B4/唯一/二选一)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`(RequestSpec/ResponseSpec 主体改造)
- Test: `tests/plate/test_io_declarations_p2.py`(新建)

**Interfaces:**
- Consumes: DeclarationEntry(Task 5)
- Produces: 存储字段 `declarations: list[DeclarationEntry]`;构造桥(旧参数 fields=/carry=/assertable_fields= 编译进清单);派生属性 `fields/carry/assertable_fields`(@property);spec 级校验器;**17 个端点文件零改动**(Task 9 验证)。Task 7 declare()/Task 8 settlement 依赖此存储。

- [ ] **Step 1: 写失败测试(④ 派生==手写 + ⑤ 结构守卫)**

```python
# tests/plate/test_io_declarations_p2.py
"""P2:存储翻转 —— 桥编译、派生等价、结构守卫(spec §4/§5)。"""
from gimbal_plate.schema.endpoint.io_spec import (
    CarryEntry, DeclarationEntry, IOFieldBinding, RequestSpec, ResponseSpec,
)


class TestBridge:
    def test_request_bridge_equivalence(self) -> None:
        legacy = RequestSpec(
            body_type="json", schema_={},
            fields=[IOFieldBinding(name="order_id", path="$.order_id")],
            carry={"$.remark": CarryEntry(description="备注")},
        )
        canonical = RequestSpec(
            body_type="json", schema_={},
            declarations=[
                DeclarationEntry(name="order_id", path="$.order_id",
                                 channel="binding"),
                DeclarationEntry(name="remark", path="$.remark",
                                 channel="carry", type="string",
                                 description="备注"),
            ],
        )
        assert legacy.fields == canonical.fields
        assert legacy.carry == canonical.carry
        assert legacy.declarations == canonical.declarations  # 键序:binding 前 carry 后

    def test_response_bridge_assertable(self) -> None:
        legacy = ResponseSpec(
            status=200, schema_={},
            fields=[IOFieldBinding(name="total", path="$.data.total")],
            assertable_fields=["$.data.total"],
        )
        (d,) = legacy.declarations
        assert d.channel == "view_only" and d.assertable is True

    def test_mutual_exclusion(self) -> None:
        with pytest.raises(ValueError, match="二选一"):
            RequestSpec(body_type="json", schema_={},
                        fields=[IOFieldBinding(name="x", path="$.x")],
                        declarations=[DeclarationEntry(name="x", path="$.x",
                                                       channel="binding")])

    def test_seventeen_endpoint_files_untouched_shape(self) -> None:
        # 桥承接:全部 ALL_ENDPOINTS 仍可构造且派生形状不变(细锁在 Task 9 ②)
        from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        for ep in ALL_ENDPOINTS:
            if ep.request:
                assert isinstance(ep.request.fields, list)


class TestStructuralGuards:
    def test_duplicate_path_cross_channel(self) -> None:
        with pytest.raises(ValueError, match="重复"):
            RequestSpec(body_type="json", schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding"),
                DeclarationEntry(name="x", path="$.x", channel="carry",
                                 type="string"),
            ])

    def test_b7_channel_closure(self) -> None:
        with pytest.raises(ValueError, match="view_only"):
            RequestSpec(body_type="json", schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="view_only")])
        with pytest.raises(ValueError, match="binding"):
            ResponseSpec(status=200, schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding")])
        with pytest.raises(ValueError, match="carry"):
            ResponseSpec(status=200, schema_={}, declarations=[
                DeclarationEntry(name="x", path="$.x", channel="carry",
                                 type="string")])

    def test_b4_body_type_none(self) -> None:
        with pytest.raises(ValueError, match="none"):
            RequestSpec(body_type="none", declarations=[
                DeclarationEntry(name="x", path="$.x", channel="binding")])


class TestDerived:
    def test_derived_returns_fresh_snapshots(self) -> None:
        rs = RequestSpec(body_type="json", schema_={},
                         declarations=[DeclarationEntry(name="x", path="$.x",
                                                        channel="binding")])
        rs.fields[0].name = "mutated"  # type: ignore[index]
        assert rs.fields[0].name == "x"  # 派生每次新建,改快照不回流
```

- [ ] **Step 2: 跑失败** — `python -m pytest tests/plate/test_io_declarations_p2.py -v`,FAIL:RequestSpec 无 declarations 参数。

- [ ] **Step 3: 实现翻转**

RequestSpec 骨架(响应同构):

```python
class RequestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body_type: BodyType = "json"
    declarations: list[DeclarationEntry] = []
    schema_: dict | None = Field(default=None, alias="schema")

    @model_validator(mode="before")
    @classmethod
    def _bridge_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        decls = data.get("declarations")
        legacy = {"fields", "carry", "assertable_fields"} & data.keys()
        if decls is not None and legacy:
            raise ValueError("declarations 与旧参数(fields/carry/"
                             "assertable_fields)二选一,不得同传")
        if decls is not None or not legacy:
            return data
        # mode=before 拿到的可能是调用方(model_validate)持有的 dict
        # 引用 —— 浅拷贝后再 pop,不污染调用方
        data = dict(data)
        # 构造参数可能是模型实例(17 个端点文件传 IOFieldBinding/CarryEntry)
        # 也可能是 dict(测试)。归一路由:实例直接 dump;dict 过对应模型
        # model_validate —— 默认值填充(含 CarryEntry.type="string" 默认)、
        # extra=forbid 拒 junk 键、词表校验,与今日裸 dict 构造同路同文案。
        # 两路 model_dump() 后键集完整,编译只补通道标记,零 .get() 兜底
        # —— 缺键在校验层自然炸,不在桥里静默
        compiled: list[dict] = []
        for f in (data.pop("fields") or []):
            fd = f.model_dump() if isinstance(f, IOFieldBinding) \
                else IOFieldBinding.model_validate(f).model_dump()
            fd["channel"] = "binding"
            compiled.append(fd)
        for p, c in (data.pop("carry") or {}).items():
            cd = c.model_dump() if isinstance(c, CarryEntry) \
                else CarryEntry.model_validate(c).model_dump()
            # 根路径 "$" 的 last_segment 为 None → name="$"(现网先例)
            cd.update(name=_path.last_segment(p) or "$", path=p,
                      channel="carry")
            compiled.append(cd)
        data["declarations"] = compiled
        return data

    @model_validator(mode="after")
    def _validate(self) -> "RequestSpec":
        # 移植现行 _validate 的 body_type/schema Rule B;新增:
        # path 全清单唯一(跨通道);B7:channel ∈ {binding, carry};
        # B4:body_type=='none' → declarations 空;B6 条目级已在 Task 5
        ...

    @property
    def fields(self) -> list[IOFieldBinding]:
        return [IOFieldBinding(name=e.name, path=e.path, required=e.required,
                               default=e.default, example=e.example,
                               description=e.description, enum=e.enum,
                               ui_kind=e.ui_kind, source_kind=e.source_kind)
                for e in self.declarations if e.channel == "binding"]

    @property
    def carry(self) -> dict[str, CarryEntry]:
        # e.type 非 None 由 B5(carry 必填 type)保证;cast 只安抚类型
        # 检查,不做值兜底 —— 意外缺失应在校验层炸,不在派生层静默
        return {e.path: CarryEntry(description=e.description,
                                   type=cast(str, e.type))
                for e in self.declarations if e.channel == "carry"}
```

ResponseSpec 桥:构造参数归一同款路由(实例 `model_dump()` / dict 过 `IOFieldBinding.model_validate`,再 dump);fields→view_only,`assertable_fields` pop 后按 path 集合对每条 compiled 置 `assertable=True`;派生 `assertable_fields = [e.path for e in ... if e.channel=="view_only" and e.assertable]`;B7:channel == "view_only"。(模块头部 `from typing import` 补 `cast`)

`_serialize`:body 不变(读 `self.fields`/`self.carry` —— property 同调用形态);declarations 键改为 `[e.model_dump(mode="json", exclude_none=False) for e in self.declarations]`(非空才发;**exclude 用法以 io_declarations_p1.json 逐字节为准** —— Task 4 起 fixture 直接捕获自 `_full_dict` 的 declarations 键,本步骤的验收就是让该键与 fixture 相等;捕获与比对同走 full 出口,裁剪行为两侧自然抵消)。`declarations_view()` 方法删除(P1 已完成历史使命,视图=存储),Task 2/4 测试文件里对 `declarations_view` 的调用改为 `.declarations` 属性访问(`[e.model_dump() for e in ...]`),**仅改测试访问面,断言值不变**。

- [ ] **Step 4: 消费面扫除(轴 grep,spec §4.2 注)**

Run(逐条,确认无计划外消费点):
```bash
git grep -n "\.fields\b\|\.carry\b\|\.assertable_fields\b" -- src/gimbal-plate | grep -v io_spec.py
git grep -n "model_dump\|\.dict()" -- src/gimbal-plate | grep -iv "scenario\|step\|resource\|config\|meta\|view\|grammar\|envelope\|export"
git grep -rn "model_validate\|model_dump" -- tests/plate | grep -i "requestspec\|responsespec"
```
第三条 = spec §9 wire 回构边缘:若有测试对 spec 做 dump→validate round-trip,改断言(桥二选一会拒同传)。第一条结果应全部落在 §4.2 已登记消费者(views/export/platform/field_defaults)。

- [ ] **Step 5: 全量回归**

Run:repo 根 `python -m pytest tests/plate -q`
预期:**全绿,含 TestCarryFacesAllEndpoints 零改动通过**(政策守卫,Global Constraints)。`git diff --stat -- src/gimbal-plate/gimbal_plate/systems/` 应显示**零端点文件改动**(桥承接;settlement 在 Task 8)。

- [ ] **Step 6: Commit** — `git commit -m "feat(plate): 存储翻转 — declarations 真源 + 构造桥 + 派生属性 + B7/B4/唯一校验"`

---

### Task 7: declare() 糖(两类方法 + ⑦ 全量规则)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`
- Test: `tests/plate/test_io_declarations_declare.py`(新建)

**Interfaces:**
- Consumes: Task 6 存储
- Produces: `RequestSpec.declare(model, *, body_type="json", bindings=None, carry=None)`、`ResponseSpec.declare(model, *, view_only=None, assert_paths=None)` —— Task 8 settlement 迁移用

- [ ] **Step 1: 写失败测试(⑦:吸收/覆写/Type C/边界报错)**

```python
"""declare() 展开规则与表达力边界(spec §3.4)。"""
from pydantic import BaseModel as PdBModel

from gimbal_plate.schema.endpoint.io_spec import RequestSpec, ResponseSpec


class CreateOrderRequest(PdBModel):
    order_id: str
    amount: int = 100
    currency: str = "CNY"
    remark: str = ""


class TestDeclare:
    def test_bindings_absorption(self) -> None:
        rs = RequestSpec.declare(
            CreateOrderRequest,
            bindings={"order_id": None, "amount": {"ui_kind": "number"}},
        )
        by = {e.path: e for e in rs.declarations}
        assert by["$.order_id"].required is True
        assert by["$.amount"].ui_kind == "number"      # 覆写优先
        assert by["$.amount"].default == 100            # 节点吸收
        assert all(e.channel == "binding" for e in rs.declarations)
        assert "remark" not in {e.path.strip("$.") for e in rs.declarations}  # Type C
        assert rs.schema_ == CreateOrderRequest.model_json_schema()  # 伴随原样

    def test_carry_absorbs_type_skips_default(self) -> None:
        rs = RequestSpec.declare(CreateOrderRequest, carry=["remark"])
        (e,) = rs.declarations
        assert e.channel == "carry" and e.type == "string"
        assert e.default is None        # B6:跳过 default 吸收
        assert e.example is None        # example 从不在吸收清单

    def test_carry_requires_explicit_type_when_nodeless(self) -> None:
        with pytest.raises(ValueError, match="carry.*type"):
            RequestSpec.declare({}, carry=["remark"])  # 空 schema 无节点

    def test_boundary_nested_key_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\.| \["):
            RequestSpec.declare(CreateOrderRequest,
                                bindings={"a.b": None})
        with pytest.raises(ValueError):
            RequestSpec.declare(CreateOrderRequest, bindings={"a[0]": None})

    def test_boundary_unknown_binding_key(self) -> None:
        with pytest.raises(ValueError, match="schema.properties"):
            RequestSpec.declare(CreateOrderRequest, bindings={"nope": None})

    def test_response_declare_assert_paths(self) -> None:
        class Resp(PdBModel):
            code: int
            msg: str

        resp = ResponseSpec.declare(Resp, view_only=["code"],
                                    assert_paths=["$.code"])
        by = {e.path: e for e in resp.declarations}
        assert by["$.code"].assertable is True
        assert by["$.code"].channel == "view_only"
```

- [ ] **Step 2: 跑失败** — FAIL:declare 不存在。

- [ ] **Step 3: 实现**(纯函数展开:顶层 `schema["properties"][key]` 直查;吸收 type/default/description/enum,required←`schema["required"]` 成员;dict 值键覆写优先;carry 跳过 default;键含 `.` 或 `[` → 构造错误;bindings 键查无 → 构造错误;carry 无节点且无显式 type → 构造错误)。default 吸收范围注意:仅 binding 通道吸收节点 default(§3.4)。

- [ ] **Step 4: 跑通过 + plate 全量** — PASS;`python -m pytest tests/plate -q` 全绿。

- [ ] **Step 5: Commit** — `git commit -m "feat(plate): declare() 糖 — 节点吸收/覆写/B6 跳值/边界报错"`

---

### Task 8: settlement 迁移 declare() 写法(③ 覆写保串)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/settlement_create_order.py`(request 段;唯一允许改动的端点文件)
- Test: `tests/plate/test_io_declarations_golden.py`(追加 ③)

**Interfaces:**
- Consumes: declare()(Task 7);`CreateOrderRequest`(fin.models,含 remark 节点)
- Produces: settlement declare() 写法;③(a) 既有键对 pre_p1 相等 + ③(b) 手写/declare 全键相等

- [ ] **Step 1: 写失败测试 ③**

```python
from gimbal_plate.schema.endpoint.io_spec import RequestSpec
from gimbal_plate.systems.fin.models import CreateOrderRequest


class TestSettlementDeclare:
    """③(spec §8):③a 锁既有键(覆写保串);③b 手写与 declare 全键相等。
    与 ② 不混用:③ 的 binding 条目 type 恒为吸收值(非 None)。"""

    def test_3a_legacy_keys_vs_pre_p1(self) -> None:
        live = _full_dict(SETTLEMENT_CREATE_ORDER)
        base = json.loads(FIXTURE.read_text(encoding="utf-8"))[
            "fin.settlement.create_order"]
        _assert_request(base, live)

    def test_3b_handwritten_equals_declare(self) -> None:
        handwritten = RequestSpec(
            body_type="json",
            schema_=CreateOrderRequest.model_json_schema(),
            declarations=[
                # 手写:含节点吸收值(order_id required=True、amount default=100
                # 等按 CreateOrderRequest 实测)+ remark 覆写 description
                ...(执行时从 declare() 输出反填,先手写一条 remark 带
                   "备注(随请求传递,不进表单)" 与 type="string")
            ],
        )
        sugared = RequestSpec.declare(
            CreateOrderRequest,
            bindings={"order_id": None, "amount": {"ui_kind": "number"},
                      "currency": None},
            carry={"remark": {"description": "备注(随请求传递,不进表单)"}},
        )
        assert handwritten.declarations == sugared.declarations
        assert handwritten.model_dump(mode="json") == sugared.model_dump(mode="json")
```

`...` 占位处:实现时先跑 `sugared` 拿到真实吸收值再落成手写清单(这不是假实现 —— ③b 的语义就是"手写全量 == 糖输出",手写侧字面量来自模型节点实测)。落清单时对模型源码抽查 2–3 个字面量(如 `amount: int = 100` → default==100、`order_id: str` 无默认 → required=True)—— ③b 反填后实质是 declare() 的确定性回归锁,真正的独立锚是 ③a 对 pre_p1 的既有键比对;抽查让手写侧也锚到模型本身,证明力补全。

- [ ] **Step 2: 迁移端点文件**

settlement_create_order.py 的 request= 段替换为:

```python
request=RequestSpec.declare(
    CreateOrderRequest,
    bindings={"order_id": None,
              "amount": {"ui_kind": "number"},
              "currency": None},
    carry={"remark": {"description": "备注(随请求传递,不进表单)"}},
),
```

**覆写串逐字节保真**:`备注(随请求传递,不进表单)` 与今日线上完全一致(半角逗号、全角括号)—— ③a 红了先核对这个串。

- [ ] **Step 3: 跑 ③ + golden ① + 政策守卫**

Run: `python -m pytest tests/plate/test_io_declarations_golden.py tests/plate/test_v3_systems_fin.py -v`
预期:③ab PASS、① PASS(既有键未动)、`TestCarryFacesAllEndpoints` PASS(carry 面不变)。

- [ ] **Step 4: Commit** — `git commit -m "refactor(plate): settlement 迁 declare() 写法 — 覆写保串,③ golden 锁等价"`

---

### Task 9: golden ② + ⑥ + P2 终门禁

**Files:**
- Modify: `tests/plate/test_io_declarations_golden.py`(追加 ②⑥)
- Test: `tests/plate/test_io_declarations_p2.py`(⑥ assertable 语义追加)

**Interfaces:**
- Consumes: 双 fixture(pre_p1 + declarations_p1,Task 1/4)
- Produces: P2 验收完形 —— ②③①⑥⑧ 全绿即 P2 完成

- [ ] **Step 1: 写 ②(17 桥路线端点全键相等)**

```python
BRIDGE_ENDPOINT_IDS = {ep.id for ep in ALL_ENDPOINTS} - {
    "fin.settlement.create_order"}


class TestGolden2Bridge:
    """②(spec §8):17 桥路线端点(fin 16 + account)settlement 除外。
    全键 = 既有键(对 io_full_pre_p1)+ declarations(对 io_declarations_p1)。
    binding 条目 type 恒 None(桥不吸收)—— 与 ③ 基线不混用。"""

    def test_bridge_full_key_equality(self) -> None:
        base = json.loads(FIXTURE.read_text(encoding="utf-8"))
        decl = json.loads(FIXTURE_DECL.read_text(encoding="utf-8"))
        for ep in ALL_ENDPOINTS:
            if ep.id not in BRIDGE_ENDPOINT_IDS:
                continue
            live = _full_dict(ep)
            _assert_request(base[ep.id], live)
            ep_decl = decl.get(ep.id) or {}
            # 空态天然对齐:无声明端点两侧均无 declarations 键/记录 → None==None
            assert (live.get("request") or {}).get("declarations") == \
                   ep_decl.get("request")
            for code, base_resp in base[ep.id]["responses"].items():
                _assert_response(base_resp, live["responses"][code])
                assert live["responses"][code].get("declarations") == \
                       (ep_decl.get("responses") or {}).get(code)
            for e in (live.get("request") or {}).get("declarations") or []:
                if e["channel"] == "binding":
                    assert e["type"] is None  # 桥不吸收(②③ 不混用锚点)
```

- [ ] **Step 2: 写 ⑥(assertable 语义)**

test_io_declarations_p2.py 追加:

```python
class TestAssertableSemantics:
    def test_default_derives_empty(self) -> None:
        resp = ResponseSpec(status=200, schema_={},
                            declarations=[DeclarationEntry(
                                name="code", path="$.code",
                                channel="view_only")])
        assert resp.assertable_fields == []  # B3:缺省 False 派生回空

    def test_audit_detail_keeps_false(self) -> None:
        # audit_detail 的 audit_id 声明但未断言(现网)→ 桥编译后保持 False
        from gimbal_plate.systems.fin.endpoint import AUDIT_AUDIT_DETAIL
        for r in AUDIT_AUDIT_DETAIL.responses.values():
            for e in r.declarations:
                if e.name == "audit_id":
                    assert e.assertable == (e.path in r.assertable_fields)
```

- [ ] **Step 3: 零 diff 验证 + P2 三套件终门禁**

Run:
```bash
git diff --stat $(git merge-base HEAD feat/carry-fields-storage-injection)..HEAD -- src/gimbal-plate/gimbal_plate/systems/fin/endpoint/
python -m pytest tests/plate -q
cd src/gimbal-platform/backend && python -m pytest -q
cd src/gimbal-platform/frontend && npm run typecheck && npm test
```
预期:diff --stat **只出现 settlement_create_order.py**;plate(453+ 新增)/ backend 346+ / frontend 401 + typecheck 全绿。

- [ ] **Step 4: Commit(P2 完成断点)** — `git commit -m "test(plate): golden ② 桥路线全键相等 + ⑥ assertable 语义 — P2 终门禁"`

---

## 自审记录(writing-plans Self-Review)

1. **Spec 覆盖**:§7 P1(Task 1–4:declarations_view/发射/切读/门禁+快照)、P2.1–6(Task 5–9 逐一对应);§8 ①(Task1/4)②(Task9)③(Task8)④⑤(Task6)⑥(Task9)⑦(Task7)⑧(各任务门禁)⑨(Task3)全覆盖;B1–B7:条目级 B6(Task5)、spec 级 B7/B4/唯一/二选一(Task6)、B3(Task9⑥)、B5/B2(Task5/7)。§9 消费面扫除 = Task6 Step4;wire 回构边缘扫测试 = 同步骤第三条 grep。
2. **占位符扫描**:Task 3 Step2 `...` 与 Task 8 Step1 `...` 均为"按既有测试模式补全 monkeypatch/从糖输出反填字面量"的显式指示,附断言要点 —— 非 TBD。符号名已对照源码核实:`last_segment`(utils/path.py:71,返回 `str | None`,根路径/数组末段返 None —— 桥与 view 均以 `or "$"` 兜根路径,carry 语料全为叶子路径)、五个端点导出名(`fin/endpoint/__init__.py` re-export 确认)、id 串 `fin.settlement.create_order`(settlement_create_order.py:29)、`CarryFieldFace`(app/schemas/carry.py:28)、`ui_kind` 九词 Literal(io_spec.py:23-26,与 DeclarationEntry 词表逐词一致)。桥代码按"构造参数可能是模型实例"归一(`model_dump()` 再编译)—— 端点文件传 `IOFieldBinding`/`CarryEntry` 实例而非 dict。
3. **类型一致**:`declarations_view()`(P1,dict 形状)→ Task 6 明确退役为 `.declarations` 属性访问并同步改 Task 2/4 测试访问面;`DeclarationEntry` 字段集在 Task 2(view dict 键集)与 Task 5(模型字段)一致;`CarryFieldFace` 形状 Task 3 保持不变。
4. **执行前评审修订(2026-09-01,用户评审抓出)**:① CAPTURE 开关全局共享,Task 4 带开关重跑会把 pre_p1 基线污染成 P1 末快照 → 两个捕获分支均加 `not FIXTURE.exists()` 守卫(捕获只补缺,re-baseline 必须显式删文件,呼应意识性 re-baseline 纪律);② decl 快照原走 `declarations_view()` 旁路,Task 9 ② 却比 `_full_dict` 出口的 declarations 键,exclude_none 嵌套裁剪差异必爆假红 → `_decl_payloads()` 改为从 `_full_dict` 摘键,捕获与比对同出口;③ 桥 `data.pop` 直接改调用方 dict → 先 `data = dict(data)` 浅拷贝;④ 两处 `"string"` 兜底是掩蔽性死代码,但 `CarryEntry.type` 有默认 `"string"`(io_spec.py:84),裸 dict 无 type 今日并不报错 → 删兜底改为归一路由:dict 过 `CarryEntry/IOFieldBinding.model_validate`(默认值填充/extra 拒 junk/词表校验与今日同路同文案),实例直接 dump,两路后键集完整、编译零 `.get()` 兜底;⑤ ③b 手写反填补"对模型源码抽查字面量"提示(独立锚是 ③a,抽查补全 ③b 证明力)。
