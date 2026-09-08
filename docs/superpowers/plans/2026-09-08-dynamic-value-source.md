# 动态取数源(QueryView 端点注记 + 组合期取数解释器)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 2026-09-07 动态取数源设计:字段候选值可在配置期实时查询被测系统,选择后以字面量钉进场景 body(尺轨不破);plate 加 QueryView 端点注记 + value_source 字段绑定,platform 加一条通用取数解释器路由(缓存/单飞/凭证闸/熔断),前端修通 enum 渲染通道并消费 value_source(分组选择器/一查多填扇出/降级态)。

**Architecture:** 三条独立链。**plate 链**:schema/endpoint 新增 QueryView/ValueSource 模型(单模型校验)+ service/query_views 目录级校验与索引投影 + 目录落点(新端点 cost_amount_list / order_page 挂视图 / 绑定与 enum 回填)+ GET /api/query-views 只读聚合路由 + golden 意识性重钉。**backend 链**:jsonpath 按先例拷贝 + TtlLruCache 原语 + query_view_runner 解释器(索引 memo/组装复核/SUT 调用/提取截断投影/凭证冷启登录绝不重登/L2 单飞/L3 凭证闸/短熔断/stale-while-error)+ rows 路由(CurrentUser)。**前端链**:FieldForm enum 通道修复(顺车票)+ value_source 全链类型透传 + ValueSourcePicker 组件 + Canvas 分组扇出写值。

**Tech Stack:** pydantic v2 + pytest(plate)/ FastAPI + httpx + pytest-asyncio(backend)/ Vue 3 `<script setup>` + vitest + vue-tsc(前端)。

**Spec:** [2026-09-07-dynamic-value-source-design.md](../specs/2026-09-07-dynamic-value-source-design.md)(§3 目录模型 / §4 解释器 / §5 缓存 / §6 凭证 / §7 前端;本计划所有 §N 引用均指该 spec)。

## Global Constraints

- **测试命令**(CWD 必须正确):
  - plate:`cd /d/Gimbal/Gimbal && python -m pytest tests/plate -q`(仓库根);
  - backend:`cd src/gimbal-platform/backend && python -m pytest tests -q`;
  - 前端单文件:`cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/<file>`;全套件 `npm test`;类型 `npx vue-tsc --noEmit`(EXIT 0)。
- **TDD 纪律**:每例先 RED(确认失败原因正确)再 GREEN;GREEN 最小实现。
- **用户 WIP 对账(执行前必做,清单以当日 `git status` 实查为准)**:本计划编写时工作树未提交改动 = `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_fee_book_real_amount_edit.py`、`tests/plate/fixtures/io_declarations_p1.json`、`src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`、`reports/test-report.html`(另 gimbal-tmp/ 未跟踪)。碰这些目标文件的任务(Task 3/4/9)动手前先 `git diff <file>` 读用户改动,在其之上叠加而非覆盖;意图不明则停下问用户;`reports/test-report.html` 与 `gimbal-tmp/` **永不提交、永不触碰**。
- **提交纪律**:每任务绿后选择性提交——只 `git add` 该任务 Files 清单内的文件;commit message 中文前缀惯例(`feat(plate): …` / `test(backend): …`),尾行 `Co-Authored-By: Claude Code <noreply@anthropic.com>`;fixture 重钉类提交须单开并说明原因(golden 文件 docstring 要求)。
- **执行核零改动**:gimbal 执行核(resolver/jsonpath/context)、export/gimbal.py、dispatch 物化链(run_dispatcher/run_materialize/carry_injection)一行不动。
- **dispatch 基线预期(重要,别误判失败)**:本设计后 dispatch 六节中 `carry_faces / carry_injected / convert_gimbal / exports` 四节必须**零漂**(场景语义不变);`endpoints`(新增 cost_amount_list + 既有端点携带 query_views)与 `convert_platform`(fields_meta 元数据投影:绑定条目多 `value_source` 对象、11 处 enum 回填键)两节发生**意识性漂移**——fields_meta 序列化是 `exclude_none=True`(export/platform.py:321),存量 None 键不携带,只有真绑定/真 enum 的条目漂。重钉流程见 Task 4。
- **命名不可变(§3.5)**:view name(`cost_list` / `pending_orders`)一经合入不可改名;四重身份(路由键/引用/缓存键/二期变量名)。
- **DSL 红线(§4.3)**:解释器 v1 词表零格——items 提取 + label/列投影,不做 filter/first/dedupe/join;检索 = 前端本地过滤。
- **绝不自动重登录(§6.2)**:SUT 401 → 清进程内 token → 降级 `sut_auth_expired`;只有冷启动(进程内无 token)才登录一次;登录与查询同受 L3 凭证闸约束。
- **参数常数(§5.1)**:`QUERY_CACHE_TTL=300s`、`MAX_ENTRIES=64`、`MAX_ROWS=200`、`STALE_MAX_WINDOW=86400s`、视图熔断 `3 次连续失败 → 30s 窗`、索引 memo TTL 60s。缓存键 = view name(不含 service_url,§6.3 跨环境 v1 接受)。
- **行为锚点(防回归)**:FieldForm typed-template 既有行为——值为 `${var}` 模板串时 select 降级为 text 输入(L575-583 既有逻辑,保留);`— select —` 空选项保留。

---

### Task 1: plate 模型 — QueryView / ValueSource / query_safe / value_source

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/schema/endpoint/query_view.py`
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/metadata.py`(query_safe 字段)
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/endpoint.py`(query_views 字段 + ④⑤ 构造期校验)
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`(value_source 字段 + ③ 互斥)
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/__init__.py`(导出)
- Test(新): `tests/plate/test_schema_query_view.py`

**Interfaces:**
- Produces(后续任务与端点文件依赖的精确形状):
  - `QueryView(BaseModel)`:字段 `name: str` / `params: dict[str, Any] | None = None` / `items: str` / `label: str`;`extra="forbid"`;校验:name 非空 ASCII 标识符、items 以 `$.` 开头、label 非空。
  - `ValueSource(BaseModel)`:字段 `view: str` / `column: str = ""` / `group: str = ""`;`extra="forbid"`;校验:view 非空。
  - `resolve_view_params(spec: EndpointSpec, view: QueryView) -> tuple[dict[str, Any], list[str]]`:per-key 合成(view.params 覆盖同名声明键/追加未声明键;声明键 default ▸ example;双 None 且 required → 进 missing;"缺"=双 None,空串/0/false 合法)。
  - `EndpointMetadata.query_safe: bool = False`;`EndpointSpec.query_views: list[QueryView] | None = None`;`DeclarationEntry.value_source: ValueSource | None = None`。
  - 校验分层(§3.3 的实现细化):③ enum×value_source 互斥 = 条目级;④ 非 GET 须 query_safe、⑤ 视图参数闭合 = EndpointSpec 级(端点自含);①②⑥ = Task 2 目录级。

- [ ] **Step 1: RED — 失败测试** `tests/plate/test_schema_query_view.py`:

```python
"""QueryView / ValueSource / query_safe 模型级校验(spec §3.1-§3.3)。"""
import pytest
from pydantic import ValidationError

from gimbal_plate.schema.endpoint import (
    ApiSpec, EndpointMetadata, EndpointSpec, RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry
from gimbal_plate.schema.endpoint.query_view import QueryView, ValueSource


def _spec(**kw) -> EndpointSpec:
    """最小合法端点(POST 版,便于测 query_safe)。"""
    base = dict(
        id="t.demo.ep", system="t", service="svc", name="demo",
        api=ApiSpec(service="svc", method="POST", path="/api/demo"),
        responses={200: ResponseSpec(status=200)},
    )
    base.update(kw)
    return EndpointSpec(**base)


class TestQueryViewShape:
    def test_ok(self):
        v = QueryView(name="cost_list", items="$.data[*]", label="cost_name")
        assert v.params is None

    @pytest.mark.parametrize("bad", [
        {"name": "cost list", "items": "$.d[*]", "label": "x"},   # name 非法字符
        {"name": "", "items": "$.d[*]", "label": "x"},            # name 空
        {"name": "v", "items": "data[*]", "label": "x"},          # items 不以 $. 开头
        {"name": "v", "items": "$.d[*]", "label": ""},            # label 空
    ])
    def test_rejected(self, bad):
        with pytest.raises(ValidationError):
            QueryView(**bad)


class TestValueSourceShape:
    def test_defaults(self):
        vs = ValueSource(view="cost_list")
        assert vs.column == "" and vs.group == ""

    def test_view_required(self):
        with pytest.raises(ValidationError):
            ValueSource(view="")


class TestEntryMutex:  # §3.3③
    def test_enum_and_value_source_rejected(self):
        with pytest.raises(ValidationError, match="互斥"):
            DeclarationEntry(name="a", path="a", type="string",
                             enum=["x"], value_source=ValueSource(view="v"))

    def test_value_source_alone_ok(self):
        e = DeclarationEntry(name="a", path="a", type="string",
                             value_source=ValueSource(view="v"))
        assert e.value_source.view == "v"


class TestQuerySafeAndClosure:  # §3.3④⑤
    def test_non_get_without_query_safe_rejected(self):
        with pytest.raises(ValidationError, match="query_safe"):
            _spec(query_views=[QueryView(name="v", items="$.d[*]", label="x")])

    def test_non_get_with_query_safe_ok(self):
        ep = _spec(metadata=EndpointMetadata(query_safe=True),
                   query_views=[QueryView(name="v", items="$.d[*]", label="x")])
        assert ep.query_views[0].name == "v"

    def test_get_view_without_params_closure_ok(self):
        ep = _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
                   query_views=[QueryView(name="v", items="$.d[*]", label="x")])
        assert ep.metadata.query_safe is False  # GET 不要求

    def test_required_key_double_none_rejected(self):
        decls = [DeclarationEntry(name="q", path="q", type="string", required=True)]
        with pytest.raises(ValidationError, match="必填键"):
            _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
                  request=RequestSpec(declarations=decls),
                  query_views=[QueryView(name="v", items="$.d[*]", label="x")])
        # 可选键双 None → 合法(缺省不携带)
        decls_opt = [DeclarationEntry(name="q", path="q", type="string", required=False)]
        _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
              request=RequestSpec(declarations=decls_opt),
              query_views=[QueryView(name="v", items="$.d[*]", label="x")])

    def test_falsy_values_are_not_missing(self):
        # 空串/0/false 是合法值,不算缺(required 键 example='' 也闭合)
        decls = [DeclarationEntry(name="q", path="q", type="string",
                                  required=True, example="")]
        _spec(api=ApiSpec(service="svc", method="GET", path="/api/d"),
              request=RequestSpec(declarations=decls),
              query_views=[QueryView(name="v", items="$.d[*]", label="x")])


class TestResolveViewParams:
    def test_merge_semantics(self):
        decls = [
            DeclarationEntry(name="a", path="a", type="string", required=True, default="DA"),
            DeclarationEntry(name="b", path="b", type="string", required=True, example="EB"),
            DeclarationEntry(name="c", path="c", type="string", required=False),
        ]
        ep = _spec(metadata=EndpointMetadata(query_safe=True),
                   request=RequestSpec(declarations=decls),
                   query_views=[QueryView(name="v", params={"a": "OV", "z": 1},
                                          items="$.d[*]", label="x")])
        from gimbal_plate.schema.endpoint.query_view import resolve_view_params
        merged, missing = resolve_view_params(ep, ep.query_views[0])
        assert merged == {"a": "OV", "b": "EB", "z": 1}   # 覆盖 a / 补 b / 追加 z / 丢 c
        assert missing == []
```

- [ ] **Step 2: 跑 RED** — `python -m pytest tests/plate/test_schema_query_view.py -q`,预期 `ModuleNotFoundError: gimbal_plate.schema.endpoint.query_view`。
- [ ] **Step 3: GREEN — 实现**。新建 `query_view.py`:

```python
"""schema.endpoint.query_view —— 取数视图注记与字段绑定(spec 2026-09-07 §3.1/§3.2)。

QueryView 是普通端点定义上的行集视图注记:method/path/请求缺省全部复用端点
声明(单一真源),本注记只补固定过滤预设(params)与行集提取呈现(items/label)。
ValueSource 是字段绑定:字段值可经视图组合期查询得到,选择后钉字面量落 body。
词表封闭(§4.3):v1 仅 items 提取 + label/列投影,无 transforms 键。
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:  # 仅类型引用,运行时零依赖(避免与 endpoint/io_spec 循环 import)
    from gimbal_plate.schema.endpoint.endpoint import EndpointSpec

# view name 标识符规则:与 io_spec _NAME_RE 同式(四重身份 §3.5,命名不可变)
_QV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class QueryView(BaseModel):
    """端点作为取数配方时的行集视图(§3.1)。

    params 是声明缺省(default ▸ example 链)之上的固定过滤预设
    (如 entrust_status=1 的"待委托"视图);GET → querystring /
    POST → JSON body 由解释器按端点 ApiSpec 分流(§4.2)。
    """

    model_config = ConfigDict(extra="forbid")

    name: str                              # 全局唯一(跨端点);四重身份见 §3.5
    params: dict[str, Any] | None = None
    items: str                             # 响应行集 JSONPath,如 '$.data.list[*]'
    label: str                             # 选择器显示列(行内键)

    @model_validator(mode="after")
    def _validate(self) -> "QueryView":
        if not _QV_NAME_RE.match(self.name):
            raise ValueError(
                f"QueryView.name={self.name!r} 须为 ASCII 标识符"
                f"([A-Za-z_][A-Za-z0-9_]*,命名不可变 §3.5)"
            )
        if not self.items.startswith("$."):
            raise ValueError(
                f"QueryView.items={self.items!r} 须为 JSONPath 形态($. 开头)"
            )
        if not self.label:
            raise ValueError("QueryView.label 不可为空(选择器显示列)")
        return self


class ValueSource(BaseModel):
    """字段绑定(§3.2):view=查询身份(查哪张表),group=选择身份(哪次业务占用)。

    group 空 = 缺省取 view name(单一用途场景零配置零行为变化);
    同 view 多角色时各赋不同 group(建议 `<view>#<role>`)拆独立选择器。
    group 是纯前端消歧机制:不进解释器语义/场景产物/徽标(§3.2 可见性边界)。
    """

    model_config = ConfigDict(extra="forbid")

    view: str         # QueryView.name(全局唯一引用)
    column: str = ""  # 行内取值列;空 = label 列(N=1 退化)
    group: str = ""   # 显式分组键;空 = 缺省取 view name

    @model_validator(mode="after")
    def _validate(self) -> "ValueSource":
        if not self.view:
            raise ValueError("ValueSource.view 不可为空(QueryView.name 引用)")
        return self


def resolve_view_params(
    spec: "EndpointSpec", view: QueryView
) -> tuple[dict[str, Any], list[str]]:
    """view.params ▸ 声明 default ▸ 声明 example 的 per-key 合成(§4.2)。

    返回 (merged, missing_required):
    - view.params 覆盖同名声明键、追加未声明键(如 entrust_status 未声明则追加);
    - 声明键取 default(非 None)否则 example(非 None);
    - 双 None:必填键 → missing_required(端点构造期拒,§3.3⑤);
      可选键 → 不携带(缺省不携带)。
    "缺" = default 与 example 双 None;空串/0/false 是合法值,不算缺。
    键 = 顶层声明 path 去掉 '$.' 前缀。
    """
    merged: dict[str, Any] = dict(view.params or {})
    missing: list[str] = []
    if spec.request is not None:
        for entry in spec.request.declarations:
            key = entry.path[2:] if entry.path.startswith("$.") else entry.path
            if key in merged:
                continue
            if entry.default is not None:
                merged[key] = entry.default
            elif entry.example is not None:
                merged[key] = entry.example
            elif entry.required:
                missing.append(key)
    return merged, missing
```

`metadata.py` 在 `experimental: bool = False`(L22)后加:

```python
    # §3.3④:非 GET 端点挂 query_views 须显式声明写副作用白名单(声明式护栏,
    # git 评审可见;fin 是 POST 重镇,不能走 GET-only 禁令)。
    query_safe: bool = False
```

`endpoint.py`:import 行加 `from .query_view import QueryView, resolve_view_params`;`responses` 字段(L47)后加:

```python
    # ── 取数视图注记(2026-09-07 动态取数源 §3.1;None = 无)──
    query_views: list[QueryView] | None = None
```

`_validate_integrity`(L97 `return self` 前)加:

```python
        # §3.3④⑤:query_views 写副作用护栏 + 视图参数闭合(构造期拒)
        if self.query_views:
            if self.api.method != "GET" and not self.metadata.query_safe:
                raise ValueError(
                    f"EndpointSpec {self.id}: 非 GET({self.api.method})端点挂 "
                    f"query_views 须显式 metadata.query_safe=True(§3.3④)"
                )
            for v in self.query_views:
                _, missing = resolve_view_params(self, v)
                if missing:
                    raise ValueError(
                        f"EndpointSpec {self.id} view {v.name!r}: 必填键经 "
                        f"view.params▸default▸example 合并后仍缺 {missing}(§3.3⑤)"
                    )
```

`io_spec.py`:顶部 import 加 `from .query_view import ValueSource`;`source_kind`(L108)与 `assertable`(L109)之间加:

```python
    # 组合期取数绑定(2026-09-07 §3.2):字段值可经 QueryView 查询后钉字面量。
    # enum(静态闭集)× value_source(动态开集)互斥,见 _validate_entry。
    value_source: ValueSource | None = None
```

`_validate_entry`(L145 `return self` 前)加:

```python
        # §3.3③:enum × value_source 互斥 —— 并置 = 定义精神分裂
        if self.enum and self.value_source is not None:
            raise ValueError(
                f"DeclarationEntry {self.path!r}: enum 与 value_source 互斥(§3.3③)"
            )
```

`schema/endpoint/__init__.py` 导出清单加 `QueryView`、`ValueSource`。

- [ ] **Step 4: 跑 GREEN** — `python -m pytest tests/plate/test_schema_query_view.py -q` 全绿;`python -m pytest tests/plate -q` 零回归(存量端点无 query_views/value_source,新校验零触发)。
- [ ] **Step 5: 提交** — `git add src/gimbal-plate/gimbal_plate/schema/endpoint/{query_view.py,metadata.py,endpoint.py,io_spec.py,__init__.py} tests/plate/test_schema_query_view.py`;`feat(plate): QueryView/ValueSource 模型 + query_safe/value_source 字段与构造期校验(③④⑤)`。

---

### Task 2: plate 目录级校验 + 索引投影

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/service/query_views.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/__init__.py`(聚合后校验)
- Test(新): `tests/plate/test_query_view_catalog.py`

**Interfaces:**
- Consumes: Task 1 的 `QueryView/ValueSource/resolve_view_params`;`iter_declarations`(io_spec,先序展开 children 树)。
- Produces:
  - `validate_query_view_catalog(endpoints: list[EndpointSpec]) -> None`:①view name 跨端点全局唯一 ②value_source.view 引用闭合 ⑥分组一致性(同 group——解析后键,缺省=view——下 view 必须一致,显式 group 与他 view 缺省组撞名同拒);违规 raise `ValueError`(文案带 §编号)。
  - `build_query_view_index(endpoints: list[EndpointSpec]) -> list[dict[str, Any]]`:§3.4 投影行,键 `{name, endpoint_id, system, service, method, path, params, items, label, columns, query_safe, missing_required, auth, timeout_seconds}`;`params` = resolve_view_params 合并后;`columns` = label ∪ 全目录绑定列(有序去重);按 name 排序(确定性,golden 友好)。`auth/timeout_seconds` 是 §4.2"超时与鉴权跟随 ApiSpec"的数据载体(单一真源仍是 ApiSpec,索引是派生投影)。

- [ ] **Step 1: RED — 失败测试** `tests/plate/test_query_view_catalog.py`:

```python
"""目录级校验 ①②⑥ + 索引投影(spec §3.3 聚合层 / §3.4)。"""
import pytest

from gimbal_plate.schema.endpoint import (
    ApiSpec, EndpointMetadata, EndpointSpec, RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry
from gimbal_plate.schema.endpoint.query_view import QueryView, ValueSource
from gimbal_plate.service.query_views import build_query_view_index, validate_query_view_catalog


def _ep(eid, *, views=None, binds=None, method="GET", query_safe=False):
    decls = [
        DeclarationEntry(name=b["path"].strip("$.") or "root", path=b["path"],
                         type="string", value_source=ValueSource(view=b["view"],
                                 column=b.get("column", ""),
                                 group=b.get("group", "")))
        for b in (binds or [])
    ]
    return EndpointSpec(
        id=eid, system="t", service="svc", name=eid,
        api=ApiSpec(service="svc", method=method, path=f"/api/{eid}"),
        request=RequestSpec(declarations=decls) if decls else None,
        responses={200: ResponseSpec(status=200)},
        metadata=EndpointMetadata(query_safe=query_safe),
        query_views=views,
    )


VIEW = QueryView(name="v1", items="$.data[*]", label="nm")
VIEW2 = QueryView(name="v2", items="$.rows[*]", label="code")


class TestValidate:
    def test_ok_multi_endpoint(self):
        validate_query_view_catalog([
            _ep("t.a", views=[VIEW], binds=[{"path": "$.x", "view": "v1"}]),
            _ep("t.b", views=[VIEW2], binds=[{"path": "$.y", "view": "v2",
                                              "group": "v2#r"}]),
        ])

    def test_dup_view_name_rejected(self):  # ①
        with pytest.raises(ValueError, match="重复"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW]),
                _ep("t.b", views=[QueryView(name="v1", items="$.z[*]", label="q")]),
            ])

    def test_dangling_reference_rejected(self):  # ②
        with pytest.raises(ValueError, match="未命中"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW], binds=[{"path": "$.x", "view": "v9"}]),
            ])

    def test_group_mixes_views_rejected(self):  # ⑥ 显式
        with pytest.raises(ValueError, match="分组一致性"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW, VIEW2], binds=[
                    {"path": "$.x", "view": "v1", "group": "g"},
                    {"path": "$.y", "view": "v2", "group": "g"},
                ]),
            ])

    def test_explicit_group_collides_with_default_group_rejected(self):  # ⑥ 显式×缺省撞名
        with pytest.raises(ValueError, match="分组一致性"):
            validate_query_view_catalog([
                _ep("t.a", views=[VIEW, VIEW2], binds=[
                    {"path": "$.x", "view": "v2", "group": "v1"},   # 显式 v1 组
                    {"path": "$.y", "view": "v1"},                  # 缺省组也叫 v1
                ]),
            ])

    def test_deep_tree_binding_seen(self):  # 绑定在 children 树内也要被扫描
        deep = DeclarationEntry(name="obj", path="$.obj", type="object", children=[
            DeclarationEntry(name="leaf", path="$.obj.leaf", type="string",
                             value_source=ValueSource(view="v1")),
        ])
        ep = EndpointSpec(
            id="t.d", system="t", service="svc", name="d",
            api=ApiSpec(service="svc", method="GET", path="/api/d"),
            request=RequestSpec(declarations=[deep]),
            responses={200: ResponseSpec(status=200)},
            query_views=[VIEW],
        )
        validate_query_view_catalog([ep])  # 不抛即通过


class TestIndex:
    def test_projection_shape(self):
        eps = [
            _ep("t.a", views=[VIEW], binds=[
                {"path": "$.x", "view": "v1", "column": "id", "group": "v1#g1"},
                {"path": "$.y", "view": "v1", "column": "id", "group": "v1#g2"},
            ]),
        ]
        rows = build_query_view_index(eps)
        assert len(rows) == 1
        r = rows[0]
        assert r["name"] == "v1" and r["endpoint_id"] == "t.a"
        assert r["method"] == "GET" and r["path"] == "/api/t.a"
        assert r["columns"] == ["nm", "id"]        # label ∪ 绑定列,有序去重
        assert r["query_safe"] is False and r["missing_required"] == []
        assert r["auth"] == "none" and r["timeout_seconds"] == 30.0

    def test_sorted_deterministic(self):
        rows = build_query_view_index([_ep("t.b", views=[VIEW2]),
                                       _ep("t.a", views=[VIEW])])
        assert [r["name"] for r in rows] == ["v1", "v2"]

    def test_merged_params_from_declarations(self):
        ep = _ep("t.a", views=[QueryView(name="v1", params={"k": 9},
                                         items="$.d[*]", label="nm")],
                 binds=[{"path": "$.x", "view": "v1"}])
        # 重新构造带声明缺省的端点
        from gimbal_plate.schema.endpoint import EndpointSpec
        decls = [DeclarationEntry(name="page", path="page", type="integer",
                                  required=True, example=7),
                 DeclarationEntry(name="x", path="$.x", type="string",
                                  value_source=ValueSource(view="v1"))]
        ep2 = EndpointSpec(id="t.a", system="t", service="svc", name="a",
                           api=ApiSpec(service="svc", method="GET", path="/api/a"),
                           request=RequestSpec(declarations=decls),
                           responses={200: ResponseSpec(status=200)},
                           query_views=ep.query_views)
        (r,) = build_query_view_index([ep2])
        assert r["params"] == {"k": 9, "page": 7}
```

- [ ] **Step 2: 跑 RED** — 预期 `ModuleNotFoundError: gimbal_plate.service.query_views`。
- [ ] **Step 3: GREEN — 实现** `service/query_views.py`:

```python
"""query-views 目录级校验与索引投影(2026-09-07 动态取数源 §3.3 聚合层 / §3.4)。

纯函数 over list[EndpointSpec],零 HTTP 依赖。两个消费方:
- systems/fin/endpoint ALL_ENDPOINTS 组装后立即 validate(构造期拒);
- http/routes_grammar GET /api/query-views 按需 build_index(纯投影零状态)。
"""
from __future__ import annotations

from typing import Any

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.io_spec import iter_declarations
from gimbal_plate.schema.endpoint.query_view import resolve_view_params


def validate_query_view_catalog(endpoints: list[EndpointSpec]) -> None:
    """聚合层校验 ①②⑥(③条目级/④⑤端点级在 schema validator,§3.3)。"""
    # pass 1:① view name 全局唯一(跨端点)
    seen: dict[str, str] = {}
    for ep in endpoints:
        for v in ep.query_views or []:
            if v.name in seen:
                raise ValueError(
                    f"QueryView.name={v.name!r} 重复(§3.3①):"
                    f"{seen[v.name]} 与 {ep.id}"
                )
            seen[v.name] = ep.id
    # pass 2:② 引用闭合 + ⑥ 分组一致性(解析后键 = group or view)
    group_view: dict[str, str] = {}
    for ep in endpoints:
        if ep.request is None:
            continue
        for entry in iter_declarations(ep.request.declarations):
            vs = entry.value_source
            if vs is None:
                continue
            if vs.view not in seen:
                raise ValueError(
                    f"value_source.view={vs.view!r} 未命中任何 QueryView"
                    f"(§3.3②):{ep.id} {entry.path}"
                )
            key = vs.group or vs.view
            if key in group_view and group_view[key] != vs.view:
                raise ValueError(
                    f"分组一致性(§3.3⑥):group={key!r} 同时绑定 view "
                    f"{group_view[key]!r} 与 {vs.view!r}({ep.id} {entry.path})"
                )
            group_view[key] = vs.view


def build_query_view_index(endpoints: list[EndpointSpec]) -> list[dict[str, Any]]:
    """§3.4 只读聚合投影。columns = label ∪ 全目录绑定列(有序去重)。"""
    binding_cols: dict[str, list[str]] = {}
    for ep in endpoints:
        if ep.request is None:
            continue
        for entry in iter_declarations(ep.request.declarations):
            vs = entry.value_source
            if vs is None or not vs.column:
                continue
            cols = binding_cols.setdefault(vs.view, [])
            if vs.column not in cols:
                cols.append(vs.column)
    rows: list[dict[str, Any]] = []
    for ep in endpoints:
        for v in ep.query_views or []:
            merged, missing = resolve_view_params(ep, v)
            cols = [v.label] + [c for c in binding_cols.get(v.name, []) if c != v.label]
            rows.append({
                "name": v.name,
                "endpoint_id": ep.id,
                "system": ep.system,
                "service": ep.service,
                "method": ep.api.method,
                "path": ep.api.path,
                "params": merged,
                "items": v.items,
                "label": v.label,
                "columns": cols,
                "query_safe": ep.metadata.query_safe,
                "missing_required": missing,
                # §4.2:超时与鉴权跟随 ApiSpec —— 索引是派生载体,真源仍是 ApiSpec
                "auth": ep.api.auth,
                "timeout_seconds": ep.api.timeout_seconds,
            })
    rows.sort(key=lambda r: r["name"])
    return rows
```

`systems/fin/endpoint/__init__.py` 在 `ALL_ENDPOINTS = [...]`(L69-90)之后加:

```python
# §3.3 聚合层校验(构造期拒):view 唯一/引用闭合/分组一致。
from gimbal_plate.service.query_views import validate_query_view_catalog as _validate_qv

_validate_qv(ALL_ENDPOINTS)
```

(import 放文件头部 import 区,调用放 ALL_ENDPOINTS 定义后。)

- [ ] **Step 4: 跑 GREEN** — 单文件绿 + `python -m pytest tests/plate -q` 零回归(现目录无 view/绑定,校验空过)。
- [ ] **Step 5: 提交** — `feat(plate): query-views 目录级校验(①②⑥)+ 索引投影,fin 聚合点挂构造期校验`。

---

### Task 3: plate 目录落点 — 新端点 / 挂视图 / 绑定 / enum 回填

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/cost_amount_list.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/__init__.py`(ALL_ENDPOINTS 增新端点)
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_page.py`(query_safe + pending_orders 视图)
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_add.py`(bl_no 绑定 + action enum)
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_fee_book_real_amount_edit.py`(cost_id ×2 绑定 + action enum)⚠ **先 git diff 对账用户 WIP**
- Modify(仅 enum 回填):`order_entrust_order_dispatch.py:53`、`order_order_notice.py:35`、`order_order_book.py:40`、`order_fee_asset_push.py:34`、`order_order_add.py:54`、`order_fee_real_amount_lock_submit.py:34`、`order_order_page.py:99`(sort_order)、`audit_audit_page.py:36`(active_tab)
- Modify: `tests/plate/test_v3_systems_fin.py`(计数 20→21 + 新策略断言)

**Interfaces:**
- Consumes: Task 1 模型;Task 2 校验(import ALL_ENDPOINTS 即触发)。
- Produces(后续任务依赖的目录事实):
  - 视图 `cost_list`(GET `/api/home/cost/amountCostList`,items `$.data[*]`,label `cost_name`,auth=bearer);
  - 视图 `pending_orders`(POST `/api/order/orderEntrust/orderPage`,query_safe=True,params `{"entrust_status": "1"}`,items `$.data.data[*]`,label `order_no`)——**注意 items 修正**:该端点响应行集在 `$.data.data`(见 `_ROW_BASE = "$.data.data[0]."`),spec §3.1 示例写的 `$.data.list[*]` 是笔误;
  - 绑定 3 条:entrust_add `$.bl_no` → pending_orders(column=bl_no,group 缺省);fee_edit `$.to_customer.put_amount.standard_list.cost_id` → cost_list(column=cost_id,group=`cost_list#to_customer`)与 `$.to_supplier.pay_amount.standard_list.cost_id` → cost_list(column=cost_id,group=`cost_list#to_supplier`)——**同 view 双角色拆组,§3.2 反例的真实落点**;
  - enum 回填 11 处(值全部来自既有 description/example,非编造):action ×8 = `['check', 'submit']`;active_tab ×1 = `['examine_wait', 'examine_done']`;sort_order ×2 = `['asc', 'desc']`(audit_audit_page 既有 sort_order enum 不动)。

- [ ] **Step 0: 用户 WIP 对账** — `git diff src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_fee_book_real_amount_edit.py` 读用户未提交改动;若与下方编辑冲突(如已手改 cost_id 条目),在用户改动之上合并;意图不明则停下问用户,不覆盖。
- [ ] **Step 1: RED — 策略测试**(`tests/plate/test_v3_systems_fin.py` 追加;计数断言同步 20→21):

```python
class TestQueryViews:
    """动态取数源目录落点(2026-09-07 spec §3.1/§3.2/§7.1)。"""

    def test_endpoint_count(self):  # 既有 20 → 21(cost_amount_list 入册)
        assert len(ALL_ENDPOINTS) == 21

    def test_views_present(self):
        by_id = {e.id: e for e in ALL_ENDPOINTS}
        views = {v.name: v for v in by_id["fin.cost.amount_list"].query_views or []}
        assert views["cost_list"].items == "$.data[*]"
        assert views["cost_list"].label == "cost_name"
        pv = {v.name: v for v in by_id["fin.order_entrust.order_page"].query_views or []}
        assert pv["pending_orders"].params == {"entrust_status": "1"}
        assert pv["pending_orders"].items == "$.data.data[*]"
        assert by_id["fin.order_entrust.order_page"].metadata.query_safe is True

    def test_bindings(self):
        by_id = {e.id: e for e in ALL_ENDPOINTS}
        add = by_id["fin.order_entrust.order_add"].request.declarations
        bl = next(e for e in add if e.name == "bl_no")
        assert bl.value_source is not None
        assert bl.value_source.view == "pending_orders"
        assert bl.value_source.column == "bl_no"
        assert bl.value_source.group == ""            # 缺省组 = view(N=1)
        fee = by_id["fin.order_fee.book_real_amount_edit"].request.declarations
        c_ids = [e for e in fee if e.name == "cost_id"]
        assert len(c_ids) == 2
        groups = {e.value_source.group for e in c_ids}
        assert groups == {"cost_list#to_customer", "cost_list#to_supplier"}  # 双角色拆组

    def test_enum_backfill(self):
        for ep in ALL_ENDPOINTS:
            for e in ep.request.declarations if ep.request else []:
                if e.name == "action":
                    assert e.enum == ["check", "submit"], f"{ep.id} action enum"
        by_id = {e.id: e for e in ALL_ENDPOINTS}
        tabs = [e for e in by_id["fin.audit.audit_page"].request.declarations
                if e.name == "active_tab"]
        assert tabs[0].enum == ["examine_wait", "examine_done"]
        so = [e for e in by_id["fin.order.order_page"].request.declarations
              if e.name == "sort_order"]
        assert so[0].enum == ["asc", "desc"]
```

- [ ] **Step 2: 跑 RED** — 新类失败(21≠20 / fin.cost.amount_list 不存在);注意 `io_declarations_golden` 与 `test_dispatch_baseline` 此时会红(目录变了)——**属预期,Task 4 统一重钉,本任务不修不跳过它们**。
- [ ] **Step 3: GREEN — 目录编辑**。

新文件 `cost_amount_list.py`:

```python
"""fin.cost.amount_list — 费用字典列表(组合期取数源)。

GET /api/home/cost/amountCostList:业务持续增补的费用字典(130+),
cost_list 视图供字段绑定组合期取数(spec 2026-09-07 §0.1/§3.1)。
字典接口成为目录公民 = 获得声明、golden 覆盖、自身可测。
行集结构待首次连测核对(cost_name/cost_id 键位),响应声明只登记信封。
"""
from typing import Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.endpoint.query_view import QueryView
from gimbal_plate.systems.fin import FIN_DEFAULT_MODULE, FIN_DEFAULT_OWNER, FIN_DEFAULT_TAGS, FIN_DEFAULT_VERSION, FIN_SYSTEM
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="code", path="$.code", type="number", required=False,
                     ui_kind="number", description="业务状态码(200=成功)", assertable=True),
    DeclarationEntry(name="msg", path="$.msg", type="string", required=False,
                     ui_kind="text", description="业务提示信息", assertable=True),
]

COST_AMOUNT_LIST: Final[EndpointSpec] = EndpointSpec(
    id="fin.cost.amount_list",
    system=FIN_SYSTEM,
    service="fin-service",
    name="费用字典列表(amountCostList)",
    description="费用名称/费用ID 字典;组合期取数源 cost_list 视图挂此",
    api=ApiSpec(service="fin-service", method="GET",
                path="/api/home/cost/amountCostList",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="none"),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS)),
    query_views=[QueryView(name="cost_list", items="$.data[*]", label="cost_name")],
)
```

(注:`RequestSpec(body_type="none")` 零声明满足 B4;`auth="bearer"` 按 fin 全系惯例——若实测免鉴权,后续修订。fin 常量 import 名以既有端点文件头部为准照抄。)

`order_entrust_order_page.py`:metadata 块与 responses 之间加(常量 import 补 `QueryView`):

```python
    query_views=[QueryView(
        name="pending_orders",
        params={"entrust_status": "1"},
        items="$.data.data[*]",       # 行集真位:响应声明 _ROW_BASE 同源
        label="order_no",             # 选择器按业务订单号选行
    )],
```

metadata 块加一行 `query_safe=True,`(§3.3④,POST 端点显式白名单)。

`order_entrust_order_add.py` L52 bl_no 条目加绑定,action(L54)补 enum:

```python
        DeclarationEntry(name='bl_no', path='$.bl_no', type='string', default='Codfish_TEST_001', example='Codfish_TEST_001', ui_kind='text',
                         value_source=ValueSource(view='pending_orders', column='bl_no')),
        ...
        DeclarationEntry(name='action', path='$.action', type='string', default='check', example='submit', description='check[校验]/submit[提交]', ui_kind='text', enum=['check', 'submit']),
```

(ValueSource import 补进文件头。)

`order_fee_book_real_amount_edit.py`(在用户 WIP 之上):两条 cost_id 条目(L59/L90 附近)各加 `value_source=ValueSource(view='cost_list', column='cost_id', group='cost_list#to_customer')`(to_customer 行)/ `group='cost_list#to_supplier'`(to_supplier 行);action 条目(L38)补 `enum=['check', 'submit']`。

其余 7 文件 enum 回填 = 对应行追加 `enum=['check', 'submit']`(action)或 `enum=['asc', 'desc']`(order_order_page sort_order);`audit_audit_page.py:36` active_tab 追加 `enum=['examine_wait', 'examine_done']`(example='examine_wait' 必须在 enum 内,满足既有 enum 一致性校验)。

`systems/fin/endpoint/__init__.py`:import `COST_AMOUNT_LIST` 并插入 ALL_ENDPOINTS 首位(SETTLEMENT_CREATE_ORDER 之前)。

- [ ] **Step 4: 跑 GREEN** — `python -m pytest tests/plate/test_v3_systems_fin.py -q` 全绿;`python -m pytest tests/plate -q` 仅允许 `test_io_declarations_golden` 与 `test_dispatch_baseline` 红(目录变化,Task 4 重钉),其余零回归。
- [ ] **Step 5: 提交** — `git add` 上述端点文件 + `tests/plate/test_v3_systems_fin.py`(注意**不add** io_declarations_p1.json 的用户 WIP 部分——若 Step 0 已对账合并则连同本任务变更一起 add,提交信息注明);`feat(plate): 目录落点 — cost_amount_list 新端点 + pending_orders/cost_list 视图 + 3 绑定 + 11 处事实枚举回填`。

---

### Task 4: plate wire — GET /api/query-views + golden 重钉

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/http/routes_grammar.py`(新路由,**注册顺序坑**)
- Create: `tests/plate/test_http_query_views.py`
- Create: `tests/plate/fixtures/query_views_index.json`(golden,捕获生成)
- Modify: `tests/plate/fixtures/io_declarations_p1.json`(意识性重钉)⚠ 用户 WIP
- Modify: `tests/plate/fixtures/dispatch_baseline.json`(意识性重钉,仅元数据面)

**Interfaces:**
- Consumes: Task 2 `build_query_view_index`;`_registry(request)` / `ok_response`(routes_grammar 既有)。
- Produces(platform Task 6 的契约):`GET /api/query-views` → 信封 `{data: {items: list[索引行], total: n}}`;行形状 = Task 2 投影。

- [ ] **Step 1: RED — 路由测试** `tests/plate/test_http_query_views.py`:

```python
"""GET /api/query-views 只读聚合路由(spec §3.4)+ 索引 golden。"""
import json
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "query_views_index.json"
CAPTURE = bool(os.environ.get("GIMBAL_GOLDEN_CAPTURE"))


def _rows(http_client):
    r = http_client.get("/api/query-views")
    assert r.status_code == 200
    body = r.json()
    data = body.get("data") or body  # 信封或裸,以实现为准但必须稳定
    return data["items"]


def test_route_shape(http_client):
    items = _rows(http_client)
    names = {i["name"] for i in items}
    assert {"cost_list", "pending_orders"} <= names
    by_name = {i["name"]: i for i in items}
    po = by_name["pending_orders"]
    assert po["endpoint_id"] == "fin.order_entrust.order_page"
    assert po["method"] == "POST" and po["query_safe"] is True
    assert po["params"]["entrust_status"] == "1"
    assert "order_no" in po["columns"] and "bl_no" in po["columns"]
    cl = by_name["cost_list"]
    assert cl["endpoint_id"] == "fin.cost.amount_list"
    assert cl["columns"] == ["cost_name", "cost_id"]
    assert cl["auth"] == "bearer"


def test_capture_or_equal(http_client):
    live = _rows(http_client)
    if CAPTURE and not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(live, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        pytest.skip("query-views index baseline captured")
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert live == base, "query-views 索引漂移(golden 基线)"
```

- [ ] **Step 2: 跑 RED** — 404(路由不存在)。
- [ ] **Step 3: GREEN — 路由**。`routes_grammar.py`:import `build_query_view_index`;在 `get_full_dim_item_global`(L414)**之前**(关键:必须先于 L529 的 `@router.get("/{dim}")` 注册,否则 `/api/query-views` 被吞成 `dim="query-views"`)加:

```python
@router.get("/query-views")
def list_query_views(request: Request) -> dict[str, Any]:
    """动态取数源只读聚合索引(2026-09-07 spec §3.4):纯投影零状态。"""
    reg = _registry(request)
    eps = list(reg.index_for("endpoint").index.values())
    items = build_query_view_index(eps)
    return ok_response({"items": items, "total": len(items)})
```

(dim 键名以 `_registry`/`register_fin_dims` 实际注册为准——执行时先看 `/{dim}/{id}/full` 用什么 dim 值(`/api/endpoint/.../full` ⇒ `"endpoint"`),照抄。)

- [ ] **Step 4: golden 三重钉**(顺序执行,逐个 diff 审查):
  1. **索引 golden**:`GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_http_query_views.py -q` 生成 fixture → 裸跑确认绿 → `git diff` 审查:只有预期两行(cost_list/pending_orders)。
  2. **io_declarations 重钉**:先 `git diff tests/plate/fixtures/io_declarations_p1.json` 读用户 WIP;删除 fixture 文件(或仅删受影响端点节)→ `GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_io_declarations_golden.py -q` 重建 → `git diff` 逐键审查,只允许出现:`fin.cost.amount_list` 新节、绑定条目 `value_source` 对象、11 处 `enum` 键、order_page `query_views`/`query_safe`;出现其他漂移 = 实现有 bug,回去修。
  3. **dispatch 基线重钉**:`python tools/ab_dispatch_dump.py --values-from tests/plate/fixtures/dispatch_baseline.json --out gimbal-tmp/dispatch_new.json`(输出进 gimbal-tmp,**不提交**)→ diff 六节:`carry_faces/carry_injected/convert_gimbal/exports` 四节必须零 diff(有 diff = 语义回归,修完再来);`endpoints/convert_platform` 的 diff 逐键审查 = 目录增量 + fields_meta 元数据键 → 按工具 docstring 流程重钉(新 dump 并回原 carry_values 段覆盖 fixture)。
- [ ] **Step 5: 全量绿** — `python -m pytest tests/plate -q` 全绿(含 golden 与 dispatch 基线)。
- [ ] **Step 6: 提交(分两笔)** — ①`feat(plate): GET /api/query-views 只读聚合路由 + 索引 golden`;②`chore(plate): io golden + dispatch 基线意识性重钉 — 目录增量/绑定/enum 元数据面(语义四节零漂)`(fixture 单独成笔,提交信息说明原因)。

---

### Task 5: backend TtlLruCache 原语

**Files:**
- Create: `src/gimbal-platform/backend/app/services/query_view_cache.py`
- Test(新): `src/gimbal-platform/backend/tests/test_query_view_cache.py`

**Interfaces:**
- Produces(Task 6 消费):
  - `CacheEntry`:`rows: list[dict]` / `fetched_wall: str`(ISO,透出给前端)/ `fetched_mono: float`(时钟读数);
  - `TtlLruCache(ttl=300.0, max_entries=64, stale_max_window=86400.0, clock=time.monotonic)`:
    - `lookup(key) -> tuple[CacheEntry | None, bool]` — (None,False)=未命中或超窗真过期;(entry,True)=新鲜;(entry,False)=过期但在 stale 窗内(可回退);命中 `move_to_end`;
    - `put(key, rows, fetched_wall)` — LRU 容量逐出 `popitem(last=False)`;
    - `drop(key)`。错误永不 put(调用方纪律,测试钉)。

- [ ] **Step 1: RED — 失败测试**(时间全用注入 clock,零 sleep):

```python
"""TtlLruCache:惰性过期 / LRU 逐出 / stale 窗(spec §5.1)。"""
from app.services.query_view_cache import TtlLruCache


def _cache(ttl=300.0, stale=86400.0, n=64):
    t = {"now": 1000.0}
    c = TtlLruCache(ttl=ttl, max_entries=n, stale_max_window=stale,
                    clock=lambda: t["now"])
    return c, t


def test_fresh_hit():
    c, t = _cache()
    c.put("v", [{"a": 1}], "2026-09-08T00:00:00Z")
    e, fresh = c.lookup("v")
    assert fresh and e.rows == [{"a": 1}] and e.fetched_wall == "2026-09-08T00:00:00Z"


def test_lazy_expiry_then_stale_window():
    c, t = _cache()
    c.put("v", [{}], "w1")
    t["now"] += 301            # 过 TTL,仍在 stale 窗
    e, fresh = c.lookup("v")
    assert not fresh and e is not None and e.rows == [{}]


def test_beyond_stale_window_is_true_miss():
    c, t = _cache()
    c.put("v", [{}], "w")
    t["now"] += 86401
    e, fresh = c.lookup("v")
    assert e is None and not fresh


def test_lru_eviction():
    c, _ = _cache(n=2)
    c.put("a", [{}], "w"); c.put("b", [{}], "w"); c.lookup("a")   # a 变热
    c.put("c", [{}], "w")                                           # 逐出 b
    assert c.lookup("b")[0] is None
    assert c.lookup("a")[0] is not None


def test_drop():
    c, _ = _cache()
    c.put("v", [{}], "w"); c.drop("v")
    assert c.lookup("v")[0] is None
```

- [ ] **Step 2: RED** → **Step 3: GREEN**:

```python
"""query_view_cache —— 组合期取数行集缓存(2026-09-07 spec §5.1)。

进程内 TtlLruCache(OrderedDict,~40 行语义):
惰性过期(读时判 TTL,无后台线程)/ LRU 容量逐出 / stale-while-error 回退窗。
纪律:错误永不 put;空列表是合法答案可缓存;键 = view name(§5.1)。
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable


class CacheEntry:
    __slots__ = ("rows", "fetched_wall", "fetched_mono")

    def __init__(self, rows: list[dict], fetched_wall: str, fetched_mono: float):
        self.rows = rows
        self.fetched_wall = fetched_wall
        self.fetched_mono = fetched_mono


class TtlLruCache:
    def __init__(self, *, ttl: float, max_entries: int, stale_max_window: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._max = max_entries
        self._stale_window = stale_max_window
        self._clock = clock
        self._data: "OrderedDict[str, CacheEntry]" = OrderedDict()

    def lookup(self, key: str) -> "tuple[CacheEntry | None, bool]":
        e = self._data.get(key)
        if e is None:
            return None, False
        self._data.move_to_end(key)
        age = self._clock() - e.fetched_mono
        if age <= self._ttl:
            return e, True
        if age <= self._ttl + self._stale_window:
            return e, False        # 过期但在回退窗内(stale-while-error 候选)
        self._data.pop(key, None)
        return None, False         # 超 STALE_MAX_WINDOW:真过期

    def put(self, key: str, rows: list[dict], fetched_wall: str) -> None:
        self._data.pop(key, None)
        self._data[key] = CacheEntry(rows, fetched_wall, self._clock())
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def drop(self, key: str) -> None:
        self._data.pop(key, None)
```

- [ ] **Step 4: GREEN + 提交** — `test(backend): TtlLruCache 原语 — 惰性过期/LRU/stale 窗(spec §5.1)`。

---

### Task 6: backend 解释器 runner(jsonpath 拷贝 + 组装/提取/投影 + 凭证 + 并发)

**Files:**
- Create: `src/gimbal-platform/backend/app/services/jsonpath.py`(自 `src/gimbal/utils/jsonpath.py` 整文件拷贝,头注释加镜像说明——先例:plate 侧 `gimbal_plate/utils/jsonpath.py` 同款拷贝)
- Create: `src/gimbal-platform/backend/app/services/query_view_runner.py`
- Test(新): `src/gimbal-platform/backend/tests/test_query_view_runner.py`

**Interfaces:**
- Consumes: Task 4 索引行形状;Task 5 `TtlLruCache`;`app.auth`(`AuthSession`/`get_authenticator`/`AuthError`);`plate_client.get_client()`。
- Produces(Task 7 路由消费):
  - `QueryViewError(code: str, message: str, status: int = 502)`;
  - `RowsResult` dataclass:`view: str / rows: list[dict] / truncated: bool / fetched_at: str / cached: bool / stale: bool`;
  - `fetch_query_view_index() -> list[dict]`(TTL 60s memo + 3 次连续失败 30s 熔断;失败 raise `QueryViewError('plate_unavailable')`);
  - `async fetch_rows(name: str, *, refresh: bool, service_url: str, owner_id: int, query_alias: str | None, load_credential: Callable[[int, str], "AuthSession | None"]) -> RowsResult`;
  - `extract_rows(payload, items) -> list`(模块级纯函数,漂移/空分形);
  - `project_rows(rows, columns) -> list[dict]`(仅保留行内存在的列键——缺列=键缺席,前端 '--' 语义);
  - 常数:`MAX_ROWS = 200`;`reset_state_for_tests()`(清缓存/熔断/凭证 session,测试隔离用)。
- 错误码契约(路由翻译依据):`unknown_view`(404)/ `query_not_safe`(422)/ `missing_required_params`(422)/ `service_url_required`(422)/ `query_credential_required`(422)/ `plate_unavailable` / `circuit_open` / `sut_unreachable` / `sut_error` / `shape_drift` / `sut_auth_expired`(均 502)。

- [ ] **Step 0: jsonpath 拷贝** — `cp src/gimbal/utils/jsonpath.py src/gimbal-platform/backend/app/services/jsonpath.py`,头部 docstring 加一行:`"""…(自 gimbal/utils/jsonpath.py 镜像拷贝,与 gimbal_plate/utils/jsonpath.py 同款先例;API:get/get_all/…)— 改动三处同步。"""`;冒烟测试 3 例(`get`/`get_all` 的 `$.data.list[*]` 与过滤形态)进本任务测试文件。

- [ ] **Step 1: RED — 失败测试**(核心纯函数 + 编排;SUT 用 monkeypatch `httpx.request`,runner 内必须写 `httpx.request(...)` 属性访问式调用使 monkeypatch 生效):

```python
"""query_view_runner:组装/提取/投影/漂移空分形 + 缓存/单飞/凭证/熔断(spec §4/§5/§6)。"""
import asyncio

import httpx
import pytest

from app.services import query_view_runner as r


@pytest.fixture(autouse=True)
def _reset():
    r.reset_state_for_tests()
    yield
    r.reset_state_for_tests()


IDX = [{
    "name": "v1", "endpoint_id": "t.a", "system": "t", "service": "svc",
    "method": "GET", "path": "/api/a", "params": {"page": 1},
    "items": "$.data.list[*]", "label": "nm",
    "columns": ["nm", "id"], "query_safe": False, "missing_required": [],
    "auth": "none", "timeout_seconds": 5.0,
}, {
    "name": "v2", "endpoint_id": "t.b", "system": "t", "service": "svc",
    "method": "POST", "path": "/api/b", "params": {"k": "x"},
    "items": "$.rows[*]", "label": "code",
    "columns": ["code"], "query_safe": True, "missing_required": [],
    "auth": "bearer", "timeout_seconds": 5.0,
}]


@pytest.fixture
def index(monkeypatch):
    async def fake():
        return IDX
    monkeypatch.setattr(r, "fetch_query_view_index", fake)


class _FakeSession:
    """Duck-typed 查询凭证。契约:auth_header() 无 token 返回 None;
    apply_token/clear_token 管理态。执行者对齐 app/auth 真实 AuthSession
    API 时保持同形(runner 只依赖这四个面)。"""

    def __init__(self):
        self.token = None

    def apply_token(self, tok: str, ttl: int) -> None:
        self.token = tok

    def clear_token(self) -> None:
        self.token = None

    def auth_header(self) -> "str | None":
        return f"Bearer {self.token}" if self.token else None


class TestExtract:
    def test_empty_list_is_legal(self):
        assert r.extract_rows({"data": {"list": []}}, "$.data.list[*]") == []

    def test_shape_drift_missing_parent(self):
        with pytest.raises(r.QueryViewError, match="漂移"):
            r.extract_rows({"data": {}}, "$.data.list[*]")

    def test_shape_drift_not_a_list(self):
        with pytest.raises(r.QueryViewError):
            r.extract_rows({"data": {"list": {"a": 1}}}, "$.data.list[*]")


class TestProject:
    def test_keeps_only_present_columns(self):
        rows = [{"nm": "a", "id": 1, "junk": "x"}, {"nm": "b"}]
        assert r.project_rows(rows, ["nm", "id"]) == [
            {"nm": "a", "id": 1}, {"nm": "b"}]      # 缺列 = 键缺席


class TestFetchRows:
    async def test_get_querystring_and_projection(self, index, monkeypatch):
        seen = {}
        def fake_request(method, url, **kw):
            seen.update(kw, method=method, url=url)
            return httpx.Response(200, json={"data": {"list": [
                {"nm": "a", "id": 1, "junk": 0}, {"nm": "b", "id": 2}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert seen["method"] == "GET" and seen["params"] == {"page": 1}
        assert res.rows == [{"nm": "a", "id": 1}, {"nm": "b", "id": 2}]
        assert not res.cached and not res.stale and not res.truncated

    async def test_post_body_and_auth_header(self, index, monkeypatch):
        seen = {}
        class _S:  # 假 AuthSession
            def auth_header(self): return "Bearer tok"
        def fake_request(method, url, **kw):
            seen.update(kw, method=method, url=url)
            return httpx.Response(200, json={"rows": [{"code": "c1"}]})
        monkeypatch.setattr(httpx, "request", fake_request)
        res = await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias="qa",
                                 load_credential=lambda o, a: _S())
        assert seen["method"] == "POST" and seen["json"] == {"k": "x"}
        assert seen["headers"]["Authorization"] == "Bearer tok"
        assert res.rows == [{"code": "c1"}]

    async def test_unknown_view_404(self, index):
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("nope", refresh=False, service_url="http://s",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.status == 404

    async def test_deep_defense_422(self, monkeypatch):
        bad = [dict(IDX[1], query_safe=False)]
        async def fake(): return bad
        monkeypatch.setattr(r, "fetch_query_view_index", fake)
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v2", refresh=False, service_url="http://s",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.status == 422 and e.value.code == "query_not_safe"

    async def test_max_rows_truncate(self, index, monkeypatch):
        monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
            200, json={"data": {"list": [{"nm": i, "id": i} for i in range(250)]}}))
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert len(res.rows) == 200 and res.truncated

    async def test_l1_cache_and_refresh_bypass(self, index, monkeypatch):
        calls = {"n": 0}
        def fake_request(method, url, **kw):
            calls["n"] += 1
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        a = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        b = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert calls["n"] == 1 and b.cached and b.rows == a.rows
        c = await r.fetch_rows("v1", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert calls["n"] == 2 and not c.cached

    async def test_error_never_cached(self, index, monkeypatch):
        state = {"fail": True}
        def fake_request(method, url, **kw):
            if state["fail"]:
                raise httpx.ConnectError("down")
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", fake_request)
        with pytest.raises(r.QueryViewError):
            await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        state["fail"] = False
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert res.rows == [{"nm": "x", "id": 1}]     # 失败没被缓存,重取成功

    async def test_stale_while_error(self, index, monkeypatch):
        def ok(m, u, **kw):
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", ok)
        first = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                   owner_id=1, query_alias=None, load_credential=None)
        r._cache._data["v1"].fetched_mono -= 400.0     # 人工老化过 TTL(仍在 stale 窗)
        async def boom(m, u, **kw):
            raise httpx.ConnectError("down")
        monkeypatch.setattr(httpx, "request", boom)
        res = await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                 owner_id=1, query_alias=None, load_credential=None)
        assert res.stale and res.rows == first.rows
        assert res.fetched_at == first.fetched_at      # fetched_at 照实显示

    async def test_single_flight(self, index, monkeypatch):
        calls = {"n": 0}
        async def slow_request(method, url, **kw):
            calls["n"] += 1
            await asyncio.sleep(0.05)
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        # to_thread 包装的是同步 httpx.request —— 单飞测试用同步慢函数即可
        def slow_sync(method, url, **kw):
            import time as _t; _t.sleep(0.05); calls["n"] += 1
            return httpx.Response(200, json={"data": {"list": [{"nm": "x", "id": 1}]}})
        monkeypatch.setattr(httpx, "request", slow_sync)
        rs = await asyncio.gather(*[
            r.fetch_rows("v1", refresh=False, service_url="http://sut",
                         owner_id=1, query_alias=None, load_credential=None)
            for _ in range(4)])
        assert calls["n"] == 1                           # 同视图并发单飞
        assert all(x.rows == rs[0].rows for x in rs)

    async def test_circuit_breaker(self, index, monkeypatch):
        def boom(m, u, **kw):
            raise httpx.ConnectError("down")
        monkeypatch.setattr(httpx, "request", boom)
        for _ in range(3):
            with pytest.raises(r.QueryViewError):
                await r.fetch_rows("v1", refresh=False, service_url="http://sut",
                                   owner_id=1, query_alias=None, load_credential=None)
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v1", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias=None, load_credential=None)
        assert e.value.code == "circuit_open"            # 熔断窗内 refresh 也拒

    async def test_sut_401_degrade_no_relogin(self, index, monkeypatch):
        logins = {"n": 0}
        def fake_auth(session, why):
            logins["n"] += 1
            session.apply_token("tok-1", 3600)
        def fake_request(method, url, **kw):
            if kw.get("headers", {}).get("Authorization") == "Bearer tok-1":
                return httpx.Response(401, json={"msg": "expired"})
            raise AssertionError("未经凭证直接请求 auth=bearer 视图")
        monkeypatch.setattr(httpx, "request", fake_request)
        monkeypatch.setattr(r, "_AUTHENTICATE", fake_auth)
        sess = _FakeSession()
        load = lambda o, a: sess
        with pytest.raises(r.QueryViewError) as e:
            await r.fetch_rows("v2", refresh=False, service_url="http://sut",
                               owner_id=1, query_alias="qa", load_credential=load)
        assert e.value.code == "sut_auth_expired"
        with pytest.raises(r.QueryViewError) as e2:
            await r.fetch_rows("v2", refresh=True, service_url="http://sut",
                               owner_id=1, query_alias="qa", load_credential=load)
        assert e2.value.code == "sut_auth_expired"   # 拉黑后直接降级,不打 SUT
        assert logins["n"] == 1      # 冷启一次;401 后绝不自动重登录(§6.2)
```

- [ ] **Step 2: 跑 RED** — ModuleNotFoundError。
- [ ] **Step 3: GREEN — 实现** `query_view_runner.py` 骨架(关键决策已定,实现遵循):

```python
"""query_view_runner —— 组合期取数解释器(2026-09-07 spec §4/§5/§6)。

fail-soft:所有失败上抛 QueryViewError(code, message, status),路由翻译降级;
绝不自动重登录(§6.2);不重试(§4.2);错误永不写缓存(§5.1)。
锁序(§5.2):view 锁外层 → 凭证闸内层;永不同时持两把 view 锁。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from app.auth import AuthError, AuthSession, get_authenticator
from app.services import jsonpath as jsonpath_mod  # 镜像拷贝,同 plate 先例
from app.services.plate_client import get_client
from app.services.query_view_cache import TtlLruCache

MAX_ROWS = 200
INDEX_TTL = 60.0
INDEX_BREAKER_THRESHOLD = 3
INDEX_BREAKER_WINDOW = 30.0
VIEW_BREAKER_THRESHOLD = 3
VIEW_BREAKER_WINDOW = 30.0

_MISSING = object()

# 测试 seams(§6.2 凭证行为依赖它们):
_AUTHENTICATE = lambda session, why: get_authenticator(session.url).authenticate(session, why)


class QueryViewError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class RowsResult:
    view: str
    rows: list[dict]
    truncated: bool
    fetched_at: str
    cached: bool
    stale: bool


# ── 进程内状态(单 worker 语义;multi-worker 各自一份,§5.3 有界接受)──
_index_state: dict[str, Any] = {"at": -1.0, "rows": [], "fails": 0, "open_until": -1.0}
_cache = TtlLruCache(ttl=300.0, max_entries=64, stale_max_window=86400.0)
_view_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()
_view_breaker: dict[str, dict[str, float]] = {}
_cred_locks: dict[tuple[int, str], asyncio.Lock] = {}
_cred_sessions: dict[tuple[int, str], AuthSession] = {}
_cred_dead: set[tuple[int, str]] = set()   # 401 拉黑:同 key 后续直接降级(§6.2)


def reset_state_for_tests() -> None:
    _index_state.update({"at": -1.0, "rows": [], "fails": 0, "open_until": -1.0})
    _cache._data.clear()
    _view_breaker.clear()
    _cred_sessions.clear()
    _cred_dead.clear()


async def _view_lock(name: str) -> asyncio.Lock:
    async with _locks_guard:
        return _view_locks.setdefault(name, asyncio.Lock())


async def fetch_query_view_index() -> list[dict[str, Any]]:
    """plate /api/query-views 索引:TTL memo + 连续失败熔断(spec §3.4)。"""
    now = time.monotonic()
    if now - _index_state["at"] <= INDEX_TTL:
        return _index_state["rows"]
    if _index_state["fails"] >= INDEX_BREAKER_THRESHOLD and \
            now < _index_state["open_until"]:
        raise QueryViewError("plate_unavailable", "plate 索引熔断窗内")
    try:
        resp = await get_client().get("/api/query-views")
        resp.raise_for_status()
        rows = (resp.json().get("data") or {}).get("items") or []
    except (httpx.HTTPError, ValueError) as e:
        _index_state["fails"] += 1
        if _index_state["fails"] >= INDEX_BREAKER_THRESHOLD:
            _index_state["open_until"] = now + INDEX_BREAKER_WINDOW
        raise QueryViewError("plate_unavailable", f"plate 索引不可达: {e}") from e
    _index_state.update({"at": now, "rows": rows, "fails": 0})
    return rows


def extract_rows(payload: Any, items: str) -> list:
    """jsonpath(items) 提取;形状漂移与空结果分形(spec §4.2)。"""
    if items.endswith("[*]"):
        parent = items[:-3]
        node = jsonpath_mod.get(payload, parent, _MISSING)
        if node is _MISSING or not isinstance(node, list):
            raise QueryViewError(
                "shape_drift", f"行集提取失败(响应形状漂移?): {parent}")
        return node
    node = jsonpath_mod.get(payload, items, _MISSING)
    if node is _MISSING:
        raise QueryViewError("shape_drift", f"行集提取失败(响应形状漂移?): {items}")
    return node if isinstance(node, list) else [node]


def project_rows(rows: list, columns: list[str]) -> list[dict]:
    """投影到列集:仅保留行内存在的列键(缺列 = 键缺席,前端 '--' 语义)。"""
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append({c: row[c] for c in columns if c in row})
    return out


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
```

`fetch_rows` 编排(实现时按此顺序,细节以测试为准):

```python
async def fetch_rows(name, *, refresh, service_url, owner_id, query_alias,
                     load_credential) -> RowsResult:
    index = await fetch_query_view_index()
    view = next((v for v in index if v["name"] == name), None)
    if view is None:
        raise QueryViewError("unknown_view", f"未知视图 {name!r}", status=404)
    # §4.2 纵深防御(构造期为主,此处兜底:防 plate 版本错位)
    if view["missing_required"]:
        raise QueryViewError("missing_required_params",
                             f"必填键仍缺: {view['missing_required']}", status=422)
    if view["method"] != "GET" and not view["query_safe"]:
        raise QueryViewError("query_not_safe",
                             f"{view['endpoint_id']} 非 GET 未声明 query_safe", status=422)
    if not service_url or not service_url.startswith(("http://", "https://")):
        raise QueryViewError("service_url_required",
                             "service_url 缺失(服务绑定未解析)", status=422)
    stale_entry, fresh = _cache.lookup(name)
    if fresh and not refresh:
        return RowsResult(name, stale_entry.rows, False, stale_entry.fetched_wall,
                          cached=True, stale=False)
    # 熔断窗内:有 stale 回退 stale,否则降级(§5.2)
    br = _view_breaker.get(name)
    if br and br["fails"] >= VIEW_BREAKER_THRESHOLD and \
            time.monotonic() < br["open_until"]:
        if stale_entry is not None:
            return RowsResult(name, stale_entry.rows, False,
                              stale_entry.fetched_wall, cached=False, stale=True)
        raise QueryViewError("circuit_open", f"视图 {name} 熔断窗内")
    lock = await _view_lock(name)
    async with lock:                       # L2 同视图单飞
        if not refresh:                    # 双检:等锁期间别人已填
            e2, f2 = _cache.lookup(name)
            if f2:
                return RowsResult(name, e2.rows, False, e2.fetched_wall,
                                  cached=True, stale=False)
        try:
            auth_header = await _resolve_auth_header(view, service_url, owner_id,
                                                     query_alias, load_credential)
            rows, truncated = await _query_sut(view, service_url, auth_header)
            wall = _now_iso()
            _cache.put(name, rows, wall)   # 投影后行入缓存(§5.3)
            _view_breaker.pop(name, None)  # 成功清零
            return RowsResult(name, rows, truncated, wall, cached=False, stale=False)
        except QueryViewError:
            _bump_breaker(name)
            if stale_entry is not None:    # stale-while-error(§5.1)
                return RowsResult(name, stale_entry.rows, False,
                                  stale_entry.fetched_wall, cached=False, stale=True)
            raise
```

`_resolve_auth_header`:`auth == "none"` → None;`query_alias is None` → `QueryViewError('query_credential_required', ..., 422)`;否则 cred_key=(owner_id, query_alias):**key 已在 `_cred_dead` → 直接 `sut_auth_expired`(401 拉黑,绝不重登)**;取/建 `_cred_locks[key]` 并 `async with`(**L3 凭证闸**,登录与查询同闸):session = `_cred_sessions.get(key)` or `load_credential(owner_id, alias)`(None → 同 422 错;拿到后存入 `_cred_sessions`);`session.auth_header()` 返回 None(无 token,冷启动)→ `await asyncio.to_thread(_AUTHENTICATE, session, "query")`(`AuthError` → `sut_auth_expired`);否则返回 header。**凭证 duck-type 契约**(四个面):`auth_header() -> str | None` / `apply_token(tok, ttl)` / `clear_token()` / `.url`——执行者先读 `app/auth/schema.py` 对齐真实 AuthSession(若其 auth_header 无 token 时抛错而非返 None,在 runner 内 try/except 归一为 None)。

`_query_sut`:`await asyncio.to_thread(httpx.request, method, f"{service_url}{path}", params=…(GET)/json=…(POST), headers=…, timeout=view["timeout_seconds"])`;`httpx.HTTPError` → `sut_unreachable`;401 → **清 token + key 进 `_cred_dead`**(`session.clear_token()`;拉黑后同 key 后续请求直接 `sut_auth_expired`,绝不自动重登);非 2xx → `sut_error`;然后 `extract_rows` → `[:MAX_ROWS]`(标记 truncated)→ `project_rows(rows, view["columns"])`。

- [ ] **Step 4: GREEN + backend 全量** — `python -m pytest tests/test_query_view_runner.py -q` 绿;`python -m pytest tests -q` 零回归。
- [ ] **Step 5: 提交** — `feat(backend): 组合期取数解释器 runner — 索引 memo/组装复核/SUT 查询/提取投影/凭证闸/单飞/熔断/stale(spec §4-§6)`。

---

### Task 7: backend rows 路由 + ServiceBinding.query_user

**Files:**
- Create: `src/gimbal-platform/backend/app/routers/query_views.py`
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:186`(ServiceBinding 加 query_user)
- Modify: `src/gimbal-platform/backend/app/main.py`(注册 router)
- Test(新): `src/gimbal-platform/backend/tests/test_query_views_route.py`

**Interfaces:**
- Consumes: Task 6 `fetch_rows/QueryViewError`;`CurrentUser`(`app.core.deps`)、`DbSession` 惯例(`auth_sessions.py` 样板)、`models/auth_session` + `fernet_decrypt`(凭证装载)。
- Produces(前端 Task 9 的契约):
  - `GET /api/query-views/{name}/rows?refresh=&service_url=&query_alias=`:
    - 200 → `{"view": str, "rows": list[dict], "truncated": bool, "fetched_at": str(ISO), "cached": bool, "stale": bool}`;
    - 404/422/502 → `HTTPException(detail={"code": …, "msg": …})`(前端 `http.ts` 归一为 ApiError);
  - `ServiceBinding.query_user: str | None`(alias `queryUser`,JSON 列透传零迁移)。

- [ ] **Step 1: RED — 路由测试**(用 conftest `client` + `register_and_login`;plate mock 扩展:在测试内 `set_client_for_tests(MockTransport)` 提供 `/api/query-views` 索引;SUT 用 monkeypatch `httpx.request`):

```python
"""rows 路由:鉴权门 / 参数 / 错误形状 / query_user 键(spec §4.1/§6.1)。"""
import httpx
import pytest

from app.services import query_view_runner as run
from tests.helpers import register_and_login


@pytest.fixture(autouse=True)
def _reset_runner():
    """索引 memo/缓存是模块级状态——每例隔离,防前例 IDX 污染后例断言。"""
    run.reset_state_for_tests()
    yield
    run.reset_state_for_tests()


def _install_plate(monkeypatch, items):
    from app.services import plate_client
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"items": items, "total": len(items)}})
    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler),
                          base_url="http://plate-test"))

_IDX = [{
    "name": "v1", "endpoint_id": "t.a", "system": "t", "service": "svc",
    "method": "GET", "path": "/api/a", "params": {}, "items": "$.d[*]",
    "label": "nm", "columns": ["nm"], "query_safe": False,
    "missing_required": [], "auth": "none", "timeout_seconds": 5.0,
}]


async def test_requires_auth(client):
    r = await client.get("/api/query-views/v1/rows")
    assert r.status_code == 401


async def test_ok_shape(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(
        200, json={"d": [{"nm": "x"}]}))
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["view"] == "v1" and body["rows"] == [{"nm": "x"}]
    assert body["cached"] is False and body["stale"] is False
    assert body["truncated"] is False and "fetched_at" in body


async def test_unknown_view_404_shape(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/nope/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "unknown_view"


async def test_missing_service_url_422(client, monkeypatch):
    _install_plate(monkeypatch, _IDX)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows", headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "service_url_required"


async def test_bearer_without_alias_422(client, monkeypatch):
    idx = [dict(_IDX[0], auth="bearer")]
    _install_plate(monkeypatch, idx)
    h = await register_and_login(client)
    r = await client.get("/api/query-views/v1/rows",
                         params={"service_url": "http://sut"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "query_credential_required"


async def test_query_user_binding_field():
    from app.schemas.scenario_composer import ServiceBinding
    b = ServiceBinding.model_validate({"authAlias": "main", "queryUser": "q1",
                                       "url": "http://s"})
    assert b.query_user == "q1" and b.auth_alias == "main"
    assert ServiceBinding.model_validate({"authAlias": "main"}).query_user is None
```

(注:`_install_plate` 替换 plate 测试客户端后,收尾恢复以 conftest 既有模式为准:`set_client_for_tests(None)` 或依赖 autouse stub 顺序,照同目录既有 plate-mock 测试的做法抄。)

- [ ] **Step 2: RED** — 404(路由未注册)。
- [ ] **Step 3: GREEN**。`app/routers/query_views.py`:

```python
"""query-views rows 路由 —— 组合期取数解释器入口(2026-09-07 spec §4.1)。

CurrentUser 鉴权(查询身份是平台服务绑定的查询凭证,不是平台用户自己);
service_url/query_alias 由前端按 ServiceBinding.url > authored
config.services / query_user ?? auth_alias 优先级求值后传入(组合上下文
在调用方;后端无集中 resolver,与 _apply_services 同语义)。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentUser
from app.core.security import fernet_decrypt
from app.auth import AuthSession
from app.models.auth_session import AuthSession as AuthSessionRow
from app.services import query_view_runner

router = APIRouter(prefix="/query-views", tags=["query-views"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _loader(db: DbSession):
    async def load(owner_id: int, alias: str) -> AuthSession | None:
        from sqlalchemy import select
        row = (await db.execute(
            select(AuthSessionRow).where(
                AuthSessionRow.owner_id == owner_id,
                AuthSessionRow.alias == alias,
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        return AuthSession(
            url=row.url,
            username=fernet_decrypt(row.username_enc),
            password=fernet_decrypt(row.password_enc),
        )
    return load


@router.get("/{name}/rows")
async def get_rows(
    name: str,
    user: CurrentUser,
    db: DbSession,
    refresh: bool = False,
    service_url: str = "",
    query_alias: str | None = None,
) -> dict:
    try:
        r = await query_view_runner.fetch_rows(
            name, refresh=refresh, service_url=service_url,
            owner_id=user.id, query_alias=query_alias,
            load_credential=_loader(db),
        )
    except query_view_runner.QueryViewError as e:
        raise HTTPException(status_code=e.status,
                            detail={"code": e.code, "msg": e.message}) from e
    return {"view": r.view, "rows": r.rows, "truncated": r.truncated,
            "fetched_at": r.fetched_at, "cached": r.cached, "stale": r.stale}
```

(模型字段名以 `app/models/auth_session.py:22-39` 实际为准(`username_enc/password_enc`);`AuthSessionRow` 命名冲突时 `as` 别名。)`scenario_composer.py:186` ServiceBinding 加:

```python
    # 组合期取数专用账号别名(2026-09-07 §6.1):指向 owner 的 auth_sessions;
    # 缺省回落 authAlias(主凭证)。查询凭证永不进场景执行配置(§6.2)。
    query_user: str | None = Field(default=None, alias="queryUser", max_length=128)
```

`main.py`:import 块加 `query_views`,`create_app()` 里在 scenarios **之前** `app.include_router(query_views.router, prefix="/api")`。

- [ ] **Step 4: GREEN + 全量 + 提交** — `feat(backend): GET /query-views/{name}/rows 路由(CurrentUser/降级错误形状)+ ServiceBinding.query_user 键(spec §6.1)`。

---

### Task 8: 前端 enum 顺车票 — FieldForm 渲染通道修复

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(L574 主面 / L775 折叠区 / Number 包裹 / :value 匹配)
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`(`toFieldBinding` 补 `type` 透传,IOFieldBinding 需要)
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts`(IOFieldBinding 加 `type?: string | null`)
- Test(新): `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.enum.test.ts`

**Interfaces:**
- Produces(Task 9 复用):`IOFieldBinding.type?: string | null`(Number 包裹判据:`type === 'integer' || type === 'number'`);enum 渲染规则 = **enum 非空即 select,优先于 ui_kind 分支**(spec §7.1)。

- [ ] **Step 1: RED — 失败测试**:

```typescript
import { describe, expect, it } from 'vitest'
import { h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '../FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

function mountField(entry: Partial<IOFieldBinding>, body: unknown) {
  const b = ref(body as any)
  const w = mount({
    setup() {
      return () => h(FieldForm, {
        bindings: [{ name: 'f', path: '$.f', required: false, description: '',
                     default: null, example: null, enum: null,
                     ui_kind: 'unknown', source_kind: 'independent', ...entry } as IOFieldBinding],
        body: b.value,
        'onUpdate:body': (v: unknown) => { b.value = v },
      })
    },
  }, { global: { plugins: [ElementPlus] } })
  return { w, b }
}

describe('FieldForm enum 通道(spec §7.1)', () => {
  it('ui_kind=text + enum → select', () => {
    const { w } = mountField({ ui_kind: 'text', enum: ['a', 'b'] }, {})
    expect(w.find('select.ctl').exists()).toBe(true)
  })

  it('ui_kind=unknown + enum → select', () => {
    const { w } = mountField({ ui_kind: 'unknown', enum: ['a'] }, {})
    expect(w.find('select.ctl').exists()).toBe(true)
  })

  it('enum 选择写字面量(string)', async () => {
    const { w, b } = mountField({ ui_kind: 'text', enum: ['a', 'b'] }, {})
    await (w.find('select.ctl').element as HTMLSelectElement) &&
      await w.find('select.ctl').setValue('b')
    expect(b.value.f).toBe('b')
  })

  it('number 型 enum 写值为 number 非 "1"(§7.1 number 陷阱)', async () => {
    const { w, b } = mountField({ ui_kind: 'text', type: 'integer',
                                  enum: [1, 2] }, {})
    await w.find('select.ctl').setValue('2')
    expect(b.value.f).toBe(2)
    expect(typeof b.value.f).toBe('number')
  })

  it('body 已有 number 值时 select 正确回显(不显空)', () => {
    const { w } = mountField({ ui_kind: 'text', type: 'integer', enum: [1, 2] }, { f: 2 })
    const sel = w.find('select.ctl').element as HTMLSelectElement
    expect(sel.value).toBe('2')
  })

  it('模板串降级 text 输入(既有行为保持)', () => {
    const { w } = mountField({ ui_kind: 'select', enum: ['a'] }, { f: '${var.x}' })
    expect(w.find('select.ctl').exists()).toBe(false)
    expect(w.find('input.ctl.tpl').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 跑 RED** — 前两例失败(text 分支先命中渲染 input)。
- [ ] **Step 3: GREEN — 编辑**:
  1. **主面**:把 L574-610 的 select 块**整块上移到 L444 text/unknown 分支之前**,条件改 `v-else-if="item.f.enum && item.f.enum.length > 0"`(去掉 `ui_kind === 'select'` 合取;tpl 降级 input 在块内保留)。
  2. **折叠区**:L775 条件改 `v-else-if="r.f.enum && r.f.enum.length > 0 && !isTpl(getValue(r.f))"`(位置本就在 text 兜底前,只删合取)。
  3. **两处 select 元素**:`:value="String(getValue(item.f) ?? '')"`(主面)/ `:value="String(getValue(r.f) ?? '')"`(折叠区);`@change` 写值改 `setValue(item.f, coerceEnumOut(item.f, (e.target as HTMLSelectElement).value))`(折叠区 `r.f` 同理)。
  4. script 加 helper(一个):

```typescript
function coerceEnumOut(f: IOFieldBinding, raw: string): unknown {
  if (raw === '') return ''
  return f.type === 'integer' || f.type === 'number' ? Number(raw) : raw
}
```

  5. `declarations.ts` `toFieldBinding`(L201-213)投影加 `type: e.type ?? null`;`types/plate.ts` `IOFieldBinding` 加 `type?: string | null`(注释:enum Number 包裹判据,2026-09-07 §7.1)。
- [ ] **Step 4: GREEN + 回归** — 新文件绿;`npx vitest run src/components/composer/__tests__/FieldForm.typed-template.test.ts`(既有 select 用例不回归)+ 全套件 + `npx vue-tsc --noEmit` EXIT 0。
- [ ] **Step 5: 提交** — `fix(frontend): enum 非空即 select — 主/折叠双面分支优先级修复 + number 型写值 Number 包裹 + 回显匹配(spec §7.1 顺车票)`。

---

### Task 9: 前端 value_source 消费 — 类型透传 / 分组 / 选择器 / 扇出 / 降级

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts`(ValueSourceView + 两接口字段)
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`(value_source 透传链 + `groupValueSources`)
- Create: `src/gimbal-platform/frontend/src/api/query-views.ts`
- Create: `src/gimbal-platform/frontend/src/components/composer/ValueSourcePicker.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(查钮 + view 徽标 + fieldQuery emit)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(picker 状态机 + 扇出写值 + 降级态)
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`(前端 ServiceBinding 类型补 `queryUser?: string | null`)
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunDialog.vue`(方案栏服务绑定行加 queryUser 输入 —— 挂账 #3 最小配置)
- Test(新): `src/utils/__tests__/declarations.valueSource.test.ts`、`src/components/composer/__tests__/ValueSourcePicker.test.ts`;Modify: `CaseComposerCanvas.test.ts`(扇出用例)、`RunDialog.auths.test.ts`(queryUser 输入一例)

**Interfaces:**
- Consumes: Task 7 rows 路由契约;Task 8 的 IOFieldBinding.type。
- Produces:
  - `types/plate.ts`:`interface ValueSourceView { view: string; column?: string | null; group?: string | null }`;`DeclarationEntryView.value_source?: ValueSourceView | null`;`IOFieldBinding.value_source?: ValueSourceView | null`;
  - `declarations.ts`:`groupValueSources(decls: DeclarationEntryView[]) -> Array<{ group: string; view: string; label?: undefined; fields: Array<{ path: string; name: string; column: string }> }>`(iterFlat 扫描;group = `value_source.group || value_source.view`;column = `value_source.column || label 列由消费方补`——函数只返回绑定字段与其显式 column,补 label 的逻辑在 Canvas);
  - `api/query-views.ts`:`fetchQueryViewRows(name: string, opts: { refresh?: boolean; serviceUrl?: string; queryAlias?: string | null }): Promise<{ view: string; rows: Array<Record<string, unknown>>; truncated: boolean; fetched_at: string; cached: boolean; stale: boolean }>`(axios `http`,错误 throw ApiError,`detail.code` 归一进 `error.code`);
  - `ValueSourcePicker.vue`:Props `{ modelValue: boolean, view: string, label: string, columns: string[], rows: Array<Record<string, unknown>>, truncated: boolean, fetchedAt: string, stale: boolean, loading: boolean, error: { code: string; message: string } | null }`;Emits `{ 'update:modelValue': [boolean], select: [row: Record<string, unknown>], refresh: [] }`;el-dialog(560px,VarSelectorModal 样板)+ 顶部本地过滤框(行内子串、大小写不敏感、纯前端)+ 表格(行 = label 列 + columns;缺列显示 `--`)+ truncated/stale 提示条 + 错误条(`error.code === 'sut_auth_expired'` → `<router-link to="/auths">到认证页刷新凭证</router-link>`,§7.5)+ 刷新钮(emit refresh)。**测试锚点 class**:过滤框 `input.vs-filter`、数据行 `tr.vsp-row`、刷新钮 `button.vs-refresh`;
  - `FieldForm.vue`:新 prop `queryBadges?: Record<string, { view: string; fetchedAt?: string }>`;新 emit `'fieldQuery': [field: IOFieldBinding]`;叶子 label 行(L401-415 区)加查钮与徽标。
- 分组语义(§7.3 拆组不拆查询):组是渲染层视角;两组同 view 各自打开选择器,fetch 参数同 view(后端 L1/L2 天然共享);前端不复用结果、不跨组覆写。

- [ ] **Step 1: RED — 纯函数测试** `declarations.valueSource.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { groupValueSources } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

const e = (name: string, vs?: { view: string; column?: string; group?: string },
          children?: DeclarationEntryView[]): DeclarationEntryView =>
  ({ name, path: `$.${name}`, required: false, description: '', ui_kind: 'text',
     source_kind: 'independent', ...(children ? { children } : {}),
     ...(vs ? { value_source: { column: '', group: '', ...vs } } : {}) } as DeclarationEntryView)

describe('groupValueSources(spec §3.2/§7.3)', () => {
  it('无绑定 → 空', () => {
    expect(groupValueSources([e('a')])).toEqual([])
  })

  it('缺省组 = view(N=1)', () => {
    const g = groupValueSources([e('bl_no', { view: 'pending_orders', column: 'bl_no' })])
    expect(g).toHaveLength(1)
    expect(g[0].group).toBe('pending_orders')
    expect(g[0].view).toBe('pending_orders')
    expect(g[0].fields).toEqual([{ path: '$.bl_no', name: 'bl_no', column: 'bl_no' }])
  })

  it('同 view 双角色显式拆组互不混合(§3.2 反例)', () => {
    const g = groupValueSources([
      e('cost_c', { view: 'cost_list', column: 'cost_id', group: 'cost_list#to_customer' }),
      e('cost_s', { view: 'cost_list', column: 'cost_id', group: 'cost_list#to_supplier' }),
    ])
    expect(g.map(x => x.group).sort()).toEqual(['cost_list#to_customer', 'cost_list#to_supplier'])
  })

  it('children 树内绑定被扫描(深层)', () => {
    const g = groupValueSources([e('obj', undefined,
      [e('leaf', { view: 'v', column: 'c' })])])
    expect(g[0].fields[0].path).toBe('$.leaf')
  })

  it('column 空 = 前端补 label 列(fields.column 保持空串)', () => {
    const g = groupValueSources([e('f', { view: 'v' })])
    expect(g[0].fields[0].column).toBe('')
  })
})
```

- [ ] **Step 2: RED — 组件测试** `ValueSourcePicker.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ValueSourcePicker from '../ValueSourcePicker.vue'

const rows = [
  { nm: '海运费', id: 1 },
  { nm: '陆运费', id: 2 },
  { nm: '稀疏行' },
]

function mountPicker(over: Record<string, unknown> = {}) {
  return mount(ValueSourcePicker, {
    props: {
      modelValue: true, view: 'cost_list', label: 'nm',
      columns: ['nm', 'id'], rows, truncated: false,
      fetchedAt: '2026-09-08T00:00:00Z', stale: false, loading: false,
      error: null, ...over,
    } as any,
    global: { plugins: [ElementPlus] },
  })
}

describe('ValueSourcePicker(spec §7.3/§7.5)', () => {
  it('渲染行集:label 列 + 绑定列;缺列显示 --', () => {
    const w = mountPicker()
    expect(w.text()).toContain('海运费')
    const cells = w.findAll('td')
    expect(cells[cells.length - 1].text()).toBe('--')   // 稀疏行缺 id 列
  })

  it('本地过滤收窄行集(纯前端,零上游)', async () => {
    const w = mountPicker()
    await w.find('input.vs-filter').setValue('海运')
    expect(w.text()).toContain('海运费')
    expect(w.text()).not.toContain('陆运费')
  })

  it('点击行 → emit select(row)', async () => {
    const w = mountPicker()
    await w.findAll('tr.vsp-row')[0].trigger('click')
    expect(w.emitted('select')![0][0]).toEqual(rows[0])
  })

  it('truncated → 提示条', () => {
    const w = mountPicker({ truncated: true })
    expect(w.text()).toContain('200')
  })

  it('sut_auth_expired → 认证页直达链接', () => {
    const w = mountPicker({ error: { code: 'sut_auth_expired', message: 'x' } })
    expect(w.find('a[href="/auths"]').exists()).toBe(true)
  })

  it('刷新钮 → emit refresh', async () => {
    const w = mountPicker()
    await w.find('button.vs-refresh').trigger('click')
    expect(w.emitted('refresh')).toHaveLength(1)
  })
})
```

- [ ] **Step 3: RED — Canvas 扇出用例**(`CaseComposerCanvas.test.ts` 追加;挂载/fixture 构造复用本文件既有 `mountCanvas` 与 scenario 构建器,执行者对齐既有用例形态;断言与 mock 形状如下,不得缺项):

```typescript
// vi.mock 区追加(与既有 '@/api/scenario-composer' mock 同排):
vi.mock('@/api/query-views', () => ({
  fetchQueryViewRows: vi.fn(),
}))
// import 区:import { fetchQueryViewRows } from '@/api/query-views'

it('value_source 扇出:选行 → 组内字段全落;缺列跳过;未绑定字段不动(spec §7.3)', async () => {
  // fixture:step 请求声明三字段(group 显式 'g'):
  //   $.a { value_source: { view: 'v', column: 'x', group: 'g' } }
  //   $.b { value_source: { view: 'v', column: 'y', group: 'g' } }
  //   $.c 无绑定
  const { canvas, stepBody } = await mountCanvasWithDecls(/* 既有构建器形态 */)
  ;(fetchQueryViewRows as ReturnType<typeof vi.fn>).mockResolvedValue({
    view: 'v', rows: [{ x: '1', y: '2', nm: 'r1' }, { x: 'only-x', nm: 'r2' }],
    truncated: false, fetched_at: 'T', cached: false, stale: false,
  })
  await canvas.get('.vs-query-btn').trigger('click')    // $.a 查钮 → fieldQuery → picker 开
  await flushPromises()
  await canvas.get('tr.vsp-row').trigger('click')       // 选第一行
  expect(stepBody()).toMatchObject({ a: '1', b: '2' })  // 组内扇出全落
  await canvas.get('.vs-query-btn').trigger('click')    // 再查,选第二行(y 缺列)
  await flushPromises()
  await canvas.findAll('tr.vsp-row')[1].trigger('click')
  expect(stepBody()).toMatchObject({ a: 'only-x' })     // a 覆写
  expect(stepBody().b).toBe('2')                        // b 缺列跳过保留原值
  expect(stepBody().c).toBeUndefined()                  // 未绑定字段恒不被写
})
```
- [ ] **Step 4: GREEN — 实现**(要点):
  1. `types/plate.ts` + `declarations.ts` 透传链:`toFieldBinding`/`nodeBinding`(FieldForm L1063)/`containerBinding`/`synthRowNode`/`leafSurface` dict 行/`extraSurfaceBindings` 六处投影补 `value_source: e.value_source ?? null`(与 enum 同款)。
  2. `groupValueSources` 进 declarations.ts(iterFlat 扫描)。
  3. `api/query-views.ts`:

```typescript
import { http } from './http'

export interface QueryViewRowsResult {
  view: string
  rows: Array<Record<string, unknown>>
  truncated: boolean
  fetched_at: string
  cached: boolean
  stale: boolean
}

export async function fetchQueryViewRows(
  name: string,
  opts: { refresh?: boolean; serviceUrl?: string; queryAlias?: string | null } = {},
): Promise<QueryViewRowsResult> {
  const { data } = await http.get(`/query-views/${encodeURIComponent(name)}/rows`, {
    params: {
      refresh: opts.refresh ? 1 : 0,
      ...(opts.serviceUrl ? { service_url: opts.serviceUrl } : {}),
      ...(opts.queryAlias ? { query_alias: opts.queryAlias } : {}),
    },
  })
  return data
}
```

  4. `ValueSourcePicker.vue`(el-dialog + 本地过滤 + 表格,样板 VarSelectorModal;样式对齐 composer 徽标风格)。
  5. `FieldForm.vue`:emit 加 `'fieldQuery': [field: IOFieldBinding]`;label 行(L401-415 区,FieldStateSelect 旁)加:

```vue
<button v-if="item.f.value_source && props.domain !== 'response'" type="button"
        class="vs-query-btn" title="从被测系统查询候选值"
        @click.stop="emit('fieldQuery', item.f)">查</button>
<span v-if="props.queryBadges?.[item.f.path]" class="vs-badge"
      :title="`view:${props.queryBadges[item.f.path].view}"
             + (props.queryBadges[item.f.path].fetchedAt
                 ? ' · fetched_at ' + props.queryBadges[item.f.path].fetchedAt : '')">
  view:{{ props.queryBadges[item.f.path].view }}
</span>
```

(徽标钉 view 不钉 group,§7.5;`.vs-query-btn`/`.vs-badge` 样式照 `.fss-reset`/`.strategy-tag` 惯例。)
  6. `CaseComposerCanvas.vue`:
     - `valueSourceGroups(step)` computed(基于 `stepDecls(step)`);
     - picker 状态:`vsPicker = ref<{ open: boolean; group?: ValueSourceGroup; label: string; rows: Array<Record<string, unknown>>; loading: boolean; error: { code: string; message: string } | null; truncated: boolean; fetchedAt: string; stale: boolean }>`;`vsBadges = ref<Record<string, { view: string; fetchedAt?: string }>>({})`;
     - `resolveQueryContext(step)`:`svc = step.api.service`;取 orchestration 首个含 `service_bindings[svc]` 的 runScheme → `{ url: binding.url, alias: binding.queryUser || binding.authAlias || null }`;回落 authored `local.config?.services?.[svc]`(字符串 URL,alias=null);URL 用 `api.view_hints` 会话内已解析的 `/full` 亦可为源——实现取最直接可用者,测试钉返回形状;
     - `onFieldQuery(field)`:`g = valueSourceGroups.find(g => g.fields.some(f => f.path === field.path))` → 打开 picker → `vsLoad(g, refresh=false)`;
     - `vsLoad`:`fetchQueryViewRows(g.view, { serviceUrl, queryAlias, refresh })` → 填状态;`ApiError` → error 填 `{ code: e.code, message: e.msg }`;
     - `onVsSelect(row)`:见下方扇出写值代码——`column` 空的绑定字段取 label 列(= 投影行首键 `firstRowKeyLabel(row)`;后端投影列序 = label ∪ 绑定列,首键恒为 label 列;空行集不进选择态,无歧义);
     - 扇出写值:

```typescript
function onVsSelect(row: Record<string, unknown>) {
  const g = vsPicker.value.group
  if (!g || !currentStep.value) return
  const body = JSON.parse(JSON.stringify(currentStep.value.request.body ?? {}))
  for (const f of g.fields) {
    const col = f.column || firstRowKeyLabel(row)      // column 空 = label 列(= 行首键)
    if (row[col] === undefined || row[col] === null) continue   // 缺列跳过(§7.3)
    setByPath(body, f.path.replace(/^\$\.?/, ''), row[col])
  }
  currentStep.value.request.body = body
  for (const f of g.fields) {
    const col = f.column || firstRowKeyLabel(row)
    if (row[col] !== undefined && row[col] !== null)
      vsBadges.value[f.path] = { view: g.view, fetchedAt: vsPicker.value.fetchedAt }
  }
  vsPicker.value.open = false
}
```

(`setByPath` 自 `@/utils/jsonpath` import;`firstRowKeyLabel(row) = Object.keys(row)[0]`。)
     - Canvas 模板:FieldForm 传 `:query-badges="vsBadges" @field-query="onFieldQuery"`;`<ValueSourcePicker v-model="vsPicker.open" … @select="onVsSelect" @refresh="vsLoad(vsPicker.group!, true)" />`。
  7. **挂账 #3 最小配置**:`scenario-composer.ts` 前端 ServiceBinding 类型补 `queryUser?: string | null`(与后端 alias 键 `queryUser` 对齐);`RunDialog.vue` 方案栏服务绑定行(现有 authAlias 凭证选择旁)加可选文本输入 v-model `binding.queryUser`(placeholder `查询账号别名(缺省用主凭证)`),保存走既有 runScheme PUT 通路零新机制。`RunDialog.auths.test.ts` 扩一例:绑定行渲染 queryUser 输入 → 填值保存载荷携带 `queryUser` 键;不填则载荷不携带该键(挂载/保存断言对齐该文件既有绑定编辑用例的写法)。
- [ ] **Step 5: GREEN + 全套件 + vue-tsc 0 + 提交** — `feat(frontend): value_source 消费 — 分组选择器/一查多填扇出/缺列跳过/本地过滤/view 徽标/降级态认证页直达 + queryUser 绑定最小配置(spec §7/挂账#3)`。

---

### Task 10: 回归收尾 + 文档 + 手验清单

**Files:**
- Modify: `docs/superpowers/specs/2026-09-07-dynamic-value-source-design.md`(状态行 → 已实施 + commit hash)
- Modify: `docs/FIELD-UI-MAPPING.md`(enum select 通道 + 查钮/徽标条目)
- Modify: `docs/PLATE-API-SURFACE.md`(GET /api/query-views + query_views/value_source wire 说明)

- [ ] **Step 1: 三套件 + 类型门**:
  - `cd /d/Gimbal/Gimbal && python -m pytest tests/plate -q`;
  - `cd src/gimbal-platform/backend && python -m pytest tests -q`;
  - `cd src/gimbal-platform/frontend && npm test && npx vue-tsc --noEmit`。
- [ ] **Step 2: dispatch 语义四节零漂复核**(Task 4 重钉后的基线再跑一遍对拍确认:`python tools/ab_dispatch_dump.py --values-from tests/plate/fixtures/dispatch_baseline.json --out gimbal-tmp/dispatch_re.json` → 六节与基线零 diff)。
- [ ] **Step 3: 手验清单(需 8765 plate 与 8000 backend 常驻普通模式运行,见记忆 plate-reload-blackhole;SUT 内网可达时执行,不可达则记待验)**:
  1. `curl http://127.0.0.1:8765/api/query-views` → data.items 含 cost_list/pending_orders;
  2. 费用字典:composer 打开 fee 编辑端点 → cost_id(to_customer)行点「查」→ 选择器列 cost_name → 选一行 → cost_id 落 body 字面量 + 徽标;to_supplier 组不受覆写(双角色);
  3. 待委托:entrust_add bl_no 点「查」→ 行集按 order_no 显示 → 选行 → bl_no 落值;**核验 entrust_status 键位**(顶层 vs params 内):若 SUT 实际过滤键在 `params` 对象内,改 view.params 为 `{"params": {"entrust_status": "1"}}`(声明键覆盖语义)并重钉索引 golden;
  4. **核验 amountCostList 行含 cost_id 键**(若只有 cost_name 无 id,报回用户定绑定列);
  5. SUT 停机窗:查一次成功 → 停 SUT → 再查 → stale 回退(fetched_at 原值)不空白;连点 3 次失败后 refresh 也降级(熔断);
  6. 凭证过期路径:配一个错密码 auth session 为 queryAlias → 查 → 错误条 + 认证页链接,无自动重登录。
- [ ] **Step 4: 文档三处** + spec §11 验收清单勾选(手验项标注实测结果;未验项留空并注明原因)。
- [ ] **Step 5: 提交** — `docs: 动态取数源收尾 — spec 状态/FIELD-UI-MAPPING/PLATE-API-SURFACE 同步 + 手验留痕`。

---

## spec §11 验收清单 → 任务映射

| spec 验收项 | 覆盖 |
|---|---|
| 费用名称(实际消费方 = fee 编辑 cost_id ×2)选择器全列 + 字面量落 body | Task 3 绑定 + Task 9 扇出 + Task 10 手验 2 |
| 待委托订单一查多填 bl_no/客户/容器全落 | v1 目录现实:客户/容器为 carry 无表单行,绑定 = bl_no 单字段下拉(Task 3);**一查多填机制**由 Task 9 Canvas 扇出测试钉死(synthetic 同组双字段);真实 N>1 绑定随目录增长再挂 |
| 同 view 双角色拆独立选择器互不覆写 + 共享同一次查询 | Task 3 cost_list#to_customer/#to_supplier 真实绑定 + Task 9 拆组测试;共享查询 = 后端 L1/L2(Task 6 单飞测试) |
| 静态 enum 字段渲染 select;number 型写 number | Task 8 |
| /full golden 重钉入库;dispatch 基线(语义四节)零漂 | Task 4 |
| 凭证过期 → 提示 + 认证页引导,无自动重登录 | Task 6(401 不重登)+ Task 9(认证页链接)+ Task 10 手验 6 |
| 非 GET 未声明 query_safe → 构造期拒 + 路由 422 双保险 | Task 1(④)+ Task 6(query_not_safe 422) |
| SUT 停机窗 stale 回退不空白;超窗真降级 | Task 5 + Task 6(stale_while_error) |
| 同视图连点一次上游请求;refresh=1 新时间戳 | Task 6(single_flight / refresh_bypass) |
| 三套件 + vue-tsc 0 | Task 10 |

## 已知实现细化决策(spec 允许范围内的钉死,执行时不再议)

1. **③④⑤ 下沉、①②⑥ 目录级**(§3.3 分层的实现细化):单端点自含的规则进 pydantic validator(更早拒),跨端点规则进 `validate_query_view_catalog`;全部仍在构造期。
2. **索引行补 `auth/timeout_seconds/missing_required` 三键**(§3.4 形状的实现补全):§4.2"超时与鉴权跟随 ApiSpec"与"必填仍缺 422 纵深防御"的数据载体;真源仍是 ApiSpec,索引是派生投影。
3. **service_url/query_alias 由前端求值传参**:平台无集中式 SUT URL resolver(现状 = run_dispatcher `_apply_services` 语义内联);组合上下文在 composer,优先级 `ServiceBinding.url > authored config.services` / `query_user ?? auth_alias` 同语义在调用方求值,路由保持无状态。
4. **凭证 = 冷启一次登录、401 清 token 降级、永不重登**:进程内 `(owner_id, alias) → AuthSession` 缓存;登录与查询同受 L3 闸(防并发自踢,§6.2)。
5. **picker 显示列**:后端投影行键序首列即 label 列;Canvas 从结果行取,空行集回退组名(不为此加目录链路)。
6. **jsonpath 走镜像拷贝**(backend 无 jsonpath 依赖;`gimbal_plate/utils/jsonpath.py` 同款先例,改动三处同步)。
7. **enum 回填值域全部取自既有 description/example**(check/submit、examine_wait/examine_done、asc/desc),零编造;ui_kind 不动(enum 非空即 select 后 ui_kind 对 enum 条目不再有裁决权)。
8. **凭证态机(§6.2 的实现钉死)**:进程内按 `(owner_id, alias)` 维护 session + `_cred_dead` 拉黑集——冷启(无 token)登录**一次**;401 清 token 并拉黑,同 key 后续直接 `sut_auth_expired`,绝不自动重登录;登录与查询同受 L3 凭证闸。测试用 duck-typed stub(`auth_header()->str|None` / `apply_token` / `clear_token` / `.url` 四个面),执行者对齐 `app/auth/schema.py` 真实 API(差异在 runner 内归一)。
9. **挂账 #3 最小配置的边界**:本计划做 = ServiceBinding `query_user` 后端键 + 前端类型 + RunDialog 绑定行输入框(缺省回落主凭证);"挪用执行配置告警 UI"仍挂账(spec §12.3 明示可滞后)。
