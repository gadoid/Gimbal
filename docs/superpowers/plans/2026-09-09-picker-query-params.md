# 选择器参数面(query_params)实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec §13(修订 7)——QueryView 增 `query_params` 点击期参数面:三级级联链路(customerList 选公司 → customerPart 单对象扇出 → getCustomerPolicy 选策略)在组合期选择器内闭环,钉字面量落 body。

**Architecture:** plate 模型加字段+校验(同名互斥/闭合豁免)+ 索引投影键 + 三客户域端点与四下单端点绑定;backend 解释器扩合并链(点击期 ▸ 索引静态 params)、参数面视图缓存旁路 + 单飞键 (view+params)、点路径列投影,路由加 `params` JSON 参数与索引代理;前端 Picker 增参数段(stage: params → rows)、Canvas 同名约定预填(字面量预填/模板串留空)与携参拉数。响应三形态中"单对象包一行"`extract_rows` 已天然支持,零改动。

**Tech Stack:** Pydantic v2(plate)/ FastAPI + httpx(backend)/ Vue 3 + TS + vitest(frontend)

**Spec:** `docs/superpowers/specs/2026-09-07-dynamic-value-source-design.md` §13(修订 7,2026-09-09;§3.3 校验 / §4.2 组装 / §5 缓存为其上游依据)

## Global Constraints

- **执行核零改动**:gimbal resolver/jsonpath/context、export/gimbal.py、dispatch 物化链一行不动;钉值走既有 body 写入通路,场景存储/导出链零变化,dispatch 基线**零重钉**(Task 6 验证;若漂移 = 实现出错,停下排查,**绝不反射性重钉**)。
- **FieldForm.vue 零改动**(查钮/徽标/扇出全复用;本计划不触碰该文件)。
- **词表红线**(spec §4.3):不新增 transforms;参数面是"查询的身份"不是"查询后的处理"。
- **绝不自动重登录**(§6.2);凭证闸/死集拉黑/熔断按 view 的既有语义零改动。
- **view name 命名不可变**(§3.5):本计划新增 `customer_list` / `customer_part` / `customer_policy` 三个名字,一经合入不可改名。
- **工作树纪律**:工作树常带用户多股 WIP——选择性暂存(`git add` 仅限本任务清单内文件);`gimbal-tmp/` 永不提交;`reports/test-report.html` 永不提交、永不触碰;`probe_ui.js` 永不触碰;commit message 尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 每任务收尾:所属套件全绿 + 选择性提交。测试命令(以仓库现状为准):
  - plate(仓库根):`python -m pytest tests/plate -q`
  - backend:`cd src/gimbal-platform/backend && python -m pytest -q`
  - frontend:`cd src/gimbal-platform/frontend && npx vitest run`(单文件加路径)+ `npx vue-tsc --noEmit`
- golden 重钉程序(plate 既有惯例):`rm tests/plate/fixtures/<fixture>.json && GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_http_query_views.py`(或 io golden 对应测试),`git diff` 人工审阅增量后随任务提交。

---

### Task 1: plate — QueryView.query_params 模型 + 校验 + 闭合豁免 + 索引投影键

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/query_view.py`
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/endpoint.py:102-114`(⑤ 闭合检查)
- Modify: `src/gimbal-plate/gimbal_plate/service/query_views.py`(`build_query_view_index`)
- Test: `tests/plate/test_schema_query_view.py`、`tests/plate/test_query_view_catalog.py`
- Regenerate: `tests/plate/fixtures/query_views_index.json`(索引 golden:全行新增 `query_params` 键)

**Interfaces:**
- Produces: `QueryView.query_params: list[str] | None = None`(约束:名字非空、不含 `.`、与 `params` 键不同名——违反构造期拒);`EndpointSpec` ⑤ 闭合检查对 `query_params` 键**豁免**(必填键可由点击期供给);索引行新增键 `"query_params": list[str]`(缺省空列表,与 `enum: null` 同例全条目携带)。
- 后续任务消费:Task 2 端点/视图用本字段声明;Task 3 runner 读索引 `query_params` 键判参数面;Task 5 前端读索引代理的同名键渲染参数段。

- [ ] **Step 1: 写失败测试(模型校验)**

追加到 `tests/plate/test_schema_query_view.py`(文件已有 `QueryView`/`EndpointSpec` 相关导入与 `test_non_get_without_query_safe_rejected` 等样板,构造式沿用本文件既有导入;缺的补 `pytest`/`pydantic.ValidationError`):

```python
# ── §13.2 query_params 点击期参数面 ──────────────────────────────

def test_query_params_params_collision_rejected():
    """query_params × params 同名 = 构造期拒(静态身份与点击期变量分家)。"""
    import pytest
    from pydantic import ValidationError
    from gimbal_plate.schema.endpoint.query_view import QueryView
    with pytest.raises(ValidationError, match="同名冲突"):
        QueryView(name="v", params={"status": "2"}, query_params=["status"],
                  items="$.data[*]", label="n")


def test_query_params_dot_name_rejected():
    """名字禁点:预填只读顶层 '$.<name>',嵌套键不做预填源(§13.7)。"""
    import pytest
    from pydantic import ValidationError
    from gimbal_plate.schema.endpoint.query_view import QueryView
    with pytest.raises(ValidationError, match="不含"):
        QueryView(name="v", query_params=["a.b"], items="$.data[*]", label="n")


def test_query_params_default_none_ok():
    from gimbal_plate.schema.endpoint.query_view import QueryView
    v = QueryView(name="v", items="$.data[*]", label="n")
    assert v.query_params is None   # 缺省无参 = 现状行为零变化


def test_closure_exempts_query_params_keys():
    """⑤ 豁免:必填键在 query_params → 构造期不拒(点击期供给 §13.2);
    索引仍透出 missing_required(backend 422 兜底)。"""
    from gimbal_plate.schema.endpoint import (
        ApiSpec, DeclarationEntry, EndpointMetadata, EndpointSpec,
        QueryView, RequestSpec,
    )
    ep = EndpointSpec(
        id="t.customer.part", system="t", service="t-service", name="part",
        api=ApiSpec(service="t-service", method="POST", path="/p", auth="none"),
        request=RequestSpec(body_type="json", declarations=[
            DeclarationEntry(name="customer_id", path="$.customer_id",
                             type="string", required=True, ui_kind="text"),
        ]),
        metadata=EndpointMetadata(query_safe=True),
        query_views=[QueryView(name="v_part", query_params=["customer_id"],
                               items="$.data", label="x")],
    )
    assert ep.query_views[0].query_params == ["customer_id"]   # 构造通过即豁免成立
```

(若本文件顶层已统一 import,则函数内 import 去重、移到顶层——以文件既有风格为准。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_schema_query_view.py -q`
Expected: 新增 4 例 FAIL(`query_params` 未知字段 / 豁免未生效)。

- [ ] **Step 3: 实现(query_view.py + endpoint.py + 索引投影)**

`query_view.py` — `QueryView` 增字段与校验(插在 `params` 字段后、`_validate` 尾部加规则):

```python
    name: str                              # 全局唯一(跨端点);四重身份见 §3.5
    params: dict[str, Any] | None = None
    # 点击期参数面(spec 2026-09-09 §13.2):参数名列表;None/空 = 无参(现状零变化)。
    query_params: list[str] | None = None
    items: str                             # 响应行集 JSONPath,如 '$.data.list[*]'
    label: str                             # 选择器显示列(行内键)
```

`_validate` 追加(在 label 非空检查之后、`return self` 之前):

```python
        if self.query_params:
            static_keys = set(self.params or {})
            for q in self.query_params:
                if not q or "." in q:
                    raise ValueError(
                        f"QueryView.query_params 含非法名 {q!r}(须非空且不含 '.',"
                        f"预填只读顶层键,嵌套键不做预填源 §13.7)"
                    )
                if q in static_keys:
                    raise ValueError(
                        f"QueryView.query_params 与 params 同名冲突:{q!r}"
                        f"(§13.2 静态身份与点击期变量分家)"
                    )
```

`endpoint.py` ⑤ 循环(现 109-114 行)改为豁免式:

```python
            for v in self.query_views:
                _, missing = resolve_view_params(self, v)
                # §13.2:query_params 键由点击期参数面供给,构造期不拒;
                # 索引仍透出静态链视角的 missing_required(backend 422 兜底)
                missing = [k for k in missing if k not in (v.query_params or [])]
                if missing:
                    raise ValueError(
                        f"{v.name}: "
                        f"view.params▸default▸example 合并后仍缺 {missing}(§3.3⑤)"
                    )
```

(错误信息文案以现有 109-114 行原文为准,只改 missing 过滤行——保持既有文案不漂。)

`service/query_views.py` `build_query_view_index` 行字典(在 `"params": merged,` 后)加:

```python
                "query_params": list(v.query_params or []),
```

- [ ] **Step 4: 跑测试确认通过 + 索引投影测试**

追加到 `tests/plate/test_query_view_catalog.py`(沿用本文件 `_ep`/`VIEW` 构造样板):

```python
def test_index_carries_query_params():
    """§13.3:索引行携带 query_params;缺省视图携带空列表(全条目同例)。"""
    from gimbal_plate.schema.endpoint.query_view import QueryView
    qv = QueryView(name="v_param", query_params=["customer_id"],
                   items="$.data", label="x")
    rows = build_query_view_index([_ep("t.q", views=[qv])])
    by_name = {r["name"]: r["name"] for r in rows}
    assert "v_param" in by_name
    param_row = next(r for r in rows if r["name"] == "v_param")
    assert param_row["query_params"] == ["customer_id"]
    # 既有无参视图(BODY 同文件样板构造)携带空列表
    bare = next(r for r in rows if r["name"] != "v_param") if len(rows) > 1 else None
    if bare is not None:
        assert bare["query_params"] == []
```

(`_ep` 签名以文件现状为准;核心断言 = `query_params` 键存在且取值正确。)

Run: `python -m pytest tests/plate/test_schema_query_view.py tests/plate/test_query_view_catalog.py -q`
Expected: PASS。

- [ ] **Step 5: golden 重钉(索引全行 +query_params 键)**

```bash
rm tests/plate/fixtures/query_views_index.json
GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_http_query_views.py -q
git diff --stat tests/plate/fixtures/query_views_index.json
```

`git diff` 审阅:增量应仅为每行新增 `"query_params": []`(此时还没有带参视图)。

- [ ] **Step 6: 全套件 + 提交**

```bash
python -m pytest tests/plate -q
git add src/gimbal-plate/gimbal_plate/schema/endpoint/query_view.py \
        src/gimbal-plate/gimbal_plate/schema/endpoint/endpoint.py \
        src/gimbal-plate/gimbal_plate/service/query_views.py \
        tests/plate/test_schema_query_view.py tests/plate/test_query_view_catalog.py \
        tests/plate/fixtures/query_views_index.json
git commit -m "feat(plate): QueryView.query_params 点击期参数面 — 同名互斥/⑤闭合豁免/索引投影键

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: plate — 客户域三端点 + 四下单端点级联绑定 + golden 重钉 + API 文档

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/customer_list.py`
- Create: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/customer_part.py`
- Create: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/customer_policy.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/__init__.py`(按 `COST_AMOUNT_LIST` 同款注册三端点)
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_add.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_add.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_dispatch.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_book.py`
- Modify: `docs/PLATE-API-SURFACE.md`(三个新目录公民 + 索引 `query_params` 键)
- Test: `tests/plate/test_http_query_views.py`(shape 断言)
- Regenerate: `tests/plate/fixtures/query_views_index.json`

**Interfaces:**
- Consumes(Task 1): `QueryView.query_params` 字段与豁免语义;索引 `query_params` 键。
- Produces(后续任务依赖的目录事实):
  - 视图 `customer_list`(无参,items `$.data[*]`,label `customer_name`,columns 含 `customer_id`/`customer_name`)
  - 视图 `customer_part`(`query_params=['customer_id']`,items `$.data` 单对象,label `customer_service.user_name`,columns 含点路径列 `handover_form.client_expand_id`/`handover_form.client_expand_name`)
  - 视图 `customer_policy`(`params={'status':'2'}` + `query_params=['customer_id']`,items `$.data[*]`,label `policy_name`)
  - 四下单端点 6 字段绑定(value_source 注记,**state 保持 carry 不动**):`customer_id`/`customer_name` → customer_list;`client_expand_id`/`client_expand_name` → customer_part(点列);`policy_id`/`policy_name` → customer_policy。

**关键事实(2026-09-09 抓包实证,来自用户实链):**
- ① `POST /api/customer/customer/customerList` body `{}` → `$.data[*]` 行含 `customer_id`/`customer_name`(customer_code 等);
- ② `POST /api/customer/customer/customerPart` body `{customer_id}` → `$.data` 单对象 `{bill[], contact[], customer_service{user_name…}, finance[], handover_form{client_expand_id…}, …}` → 点路径列取 `handover_form.client_expand_id`;
- ③ `POST /api/Customer/Policy/getCustomerPolicy` body `{customer_id, status}` → `$.data[*]` 行含 `policy_id`/`policy_name`/`customer_policy_id`;status 固定 `"2"` 走视图静态 `params`。
- 消费字段在 4 端点全部存在且均为 `state='carry'` —— **carry 不进树,查钮经 FieldStateSearch 找回翻 form 后才现**(09-07 既有机制,目录默认不动 → dispatch 零漂)。手验流程见 Task 6。

- [ ] **Step 1: 写失败测试(shape 断言)**

`tests/plate/test_http_query_views.py` `test_route_shape` 追加(在既有 `cl = by_name["cost_list"]` 块后):

```python
    # §13 客户域三级链路视图
    assert {"customer_list", "customer_part", "customer_policy"} <= names
    cl1 = by_name["customer_list"]
    assert cl1["endpoint_id"] == "fin.customer.list"
    assert cl1["query_params"] == []                    # 无参 = 现状通道
    assert "customer_id" in cl1["columns"] and "customer_name" in cl1["columns"]
    cp = by_name["customer_part"]
    assert cp["endpoint_id"] == "fin.customer.part"
    assert cp["query_params"] == ["customer_id"]
    assert cp["items"] == "$.data"                      # 单对象型(§13.4)
    assert cp["label"] == "customer_service.user_name"
    assert "handover_form.client_expand_id" in cp["columns"]
    assert cp["missing_required"] == ["customer_id"]    # 静态链视角;点击期补齐
    po3 = by_name["customer_policy"]
    assert po3["endpoint_id"] == "fin.customer.policy"
    assert po3["query_params"] == ["customer_id"]
    assert po3["params"]["status"] == "2"               # 静态预设
    assert "customer_id" not in po3["params"]           # 点击期供给,静态面不含
    assert po3["missing_required"] == ["customer_id"]
```

Run: `python -m pytest tests/plate/test_http_query_views.py::test_route_shape -q`
Expected: FAIL(`customer_list` 等视图不存在)。

- [ ] **Step 2: 实现三端点文件**

三个新文件均以 `cost_amount_list.py` 为模板(`system_info` 导入、信封响应声明、`Final` 常量)。响应声明只登记信封(code/msg),行集结构待首连测核对(与 cost_amount_list 同款诚实口径)。

`customer_list.py`:

```python
"""fin.customer.list — 客户列表(组合期取数源,级联链 ①)。

POST /api/customer/customer/customerList:客户公司列表,无必填参。
customer_list 视图:选公司 → customer_id/customer_name 一查多填(§13.1 ①)。
行集结构待首连测核对,响应声明只登记信封。
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE, FIN_DEFAULT_OWNER, FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION, FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec, DeclarationEntry, EndpointMetadata, EndpointSpec,
    RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint import QueryView

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="code", path="$.code", type="number", required=False,
                     ui_kind="number", description="业务状态码(200=成功)", assertable=True),
    DeclarationEntry(name="msg", path="$.msg", type="string", required=False,
                     ui_kind="text", description="业务提示信息", assertable=True),
]

CUSTOMER_LIST: Final[EndpointSpec] = EndpointSpec(
    id="fin.customer.list",
    system=FIN_SYSTEM,
    service="fin-service",
    name="客户列表(customerList)",
    description="客户公司列表;组合期取数源 customer_list 视图挂此(级联链 ①,§13.1)",
    api=ApiSpec(service="fin-service", method="POST",
                path="/api/customer/customer/customerList",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="json"),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS), query_safe=True),
    query_views=[QueryView(name="customer_list", items="$.data[*]",
                           label="customer_name")],
)
```

`customer_part.py`:

```python
"""fin.customer.part — 客户详情(组合期取数源,级联链 ②)。

POST /api/customer/customer/customerPart(body customer_id):单对象详情
{bill, contact, customer_service, finance, handover_form, …}。
customer_part 视图:单对象型($.data 整对象即一行,§13.4),点路径列
handover_form.client_expand_id 等扇出;customer_id 走点击期参数面(§13.2)。
行集结构待首连测核对,响应声明只登记信封。
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE, FIN_DEFAULT_OWNER, FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION, FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec, DeclarationEntry, EndpointMetadata, EndpointSpec,
    RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint import QueryView

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="code", path="$.code", type="number", required=False,
                     ui_kind="number", description="业务状态码(200=成功)", assertable=True),
    DeclarationEntry(name="msg", path="$.msg", type="string", required=False,
                     ui_kind="text", description="业务提示信息", assertable=True),
]

CUSTOMER_PART: Final[EndpointSpec] = EndpointSpec(
    id="fin.customer.part",
    system=FIN_SYSTEM,
    service="fin-service",
    name="客户详情(customerPart)",
    description="客户单对象详情;组合期取数源 customer_part 视图挂此(级联链 ②,§13.1/§13.4)",
    api=ApiSpec(service="fin-service", method="POST",
                path="/api/customer/customer/customerPart",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="json", declarations=[
        DeclarationEntry(name="customer_id", path="$.customer_id", type="string",
                         required=True, ui_kind="text",
                         description="客户ID(点击期参数面供给,§13.2)"),
    ]),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS), query_safe=True),
    query_views=[QueryView(
        name="customer_part",
        query_params=["customer_id"],
        items="$.data",                       # 单对象型:整对象即一行(§13.4)
        label="customer_service.user_name",   # 单对象行标识列(点路径,2026-09-09 抓包实证)
    )],
)
```

`customer_policy.py`:

```python
"""fin.customer.policy — 客户策略列表(组合期取数源,级联链 ③)。

POST /api/Customer/Policy/getCustomerPolicy(body customer_id + status):
策略列表($.data[*]:policy_id/policy_name/customer_policy_id)。
customer_policy 视图:status="2" 静态预设(params)+ customer_id 点击期
(query_params)—— 静态/动态分离的实证样本(§13.1)。
行集结构待首连测核对,响应声明只登记信封。
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE, FIN_DEFAULT_OWNER, FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION, FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec, DeclarationEntry, EndpointMetadata, EndpointSpec,
    RequestSpec, ResponseSpec,
)
from gimbal_plate.schema.endpoint import QueryView

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = [
    DeclarationEntry(name="code", path="$.code", type="number", required=False,
                     ui_kind="number", description="业务状态码(200=成功)", assertable=True),
    DeclarationEntry(name="msg", path="$.msg", type="string", required=False,
                     ui_kind="text", description="业务提示信息", assertable=True),
]

CUSTOMER_POLICY: Final[EndpointSpec] = EndpointSpec(
    id="fin.customer.policy",
    system=FIN_SYSTEM,
    service="fin-service",
    name="客户策略列表(getCustomerPolicy)",
    description="客户策略列表;组合期取数源 customer_policy 视图挂此(级联链 ③,§13.1)",
    api=ApiSpec(service="fin-service", method="POST",
                path="/api/Customer/Policy/getCustomerPolicy",
                auth="bearer", timeout_seconds=30.0),
    request=RequestSpec(body_type="json", declarations=[
        DeclarationEntry(name="customer_id", path="$.customer_id", type="string",
                         required=True, ui_kind="text",
                         description="客户ID(点击期参数面供给,§13.2)"),
        DeclarationEntry(name="status", path="$.status", type="string",
                         required=True, ui_kind="text",
                         description="策略状态(视图静态预设 status=2,§13.1)"),
    ]),
    responses={200: ResponseSpec(status=200, description="成功",
                                 declarations=_RESPONSE_DECLS)},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(module=FIN_DEFAULT_MODULE, owner=FIN_DEFAULT_OWNER,
                              tags=list(FIN_DEFAULT_TAGS), query_safe=True),
    query_views=[QueryView(
        name="customer_policy",
        params={"status": "2"},
        query_params=["customer_id"],
        items="$.data[*]",
        label="policy_name",
    )],
)
```

- [ ] **Step 3: 注册 + 四端点绑定**

`endpoint/__init__.py`:按 `COST_AMOUNT_LIST` 完全同款的位置与式样追加 `CUSTOMER_LIST` / `CUSTOMER_PART` / `CUSTOMER_POLICY` 的 import 与导出(含 ALL_ENDPOINTS 聚合处)。

四下单端点绑定:每文件为 6 个既有字段追加 `value_source=` 注记(**state='carry' 原样不动**,目录共识零变化)。以 `order_order_add.py` 为例(其余三文件同款;`ValueSource` 缺则按 `order_entrust_order_add.py:53-54` 的 `bl_no` 样板补 import):

```python
        DeclarationEntry(name='customer_id', path='$.customer_id', state='carry', type='string',
                         value_source=ValueSource(view='customer_list', column='customer_id')),
        DeclarationEntry(name='customer_name', path='$.customer_name', state='carry', type='string',
                         value_source=ValueSource(view='customer_list', column='customer_name')),
        DeclarationEntry(name='client_expand_id', path='$.client_expand_id', state='carry', type='string',
                         value_source=ValueSource(view='customer_part', column='handover_form.client_expand_id')),
        DeclarationEntry(name='client_expand_name', path='$.client_expand_name', state='carry', type='string',
                         value_source=ValueSource(view='customer_part', column='handover_form.client_expand_name')),
        DeclarationEntry(name='policy_id', path='$.policy_id', state='carry', type='string',
                         value_source=ValueSource(view='customer_policy', column='policy_id')),
        DeclarationEntry(name='policy_name', path='$.policy_name', state='carry', type='string',
                         value_source=ValueSource(view='customer_policy', column='policy_name')),
```

绑定映射(4 文件 × 6 字段全挂,2026-09-09 grep 实证四文件六字段齐备):

| 消费字段(path) | view | column(行内取值列) |
|---|---|---|
| `$.customer_id` | customer_list | `customer_id` |
| `$.customer_name` | customer_list | `customer_name` |
| `$.client_expand_id` | customer_part | `handover_form.client_expand_id` |
| `$.client_expand_name` | customer_part | `handover_form.client_expand_name` |
| `$.policy_id` | customer_policy | `policy_id` |
| `$.policy_name` | customer_policy | `policy_name` |

- [ ] **Step 4: 跑测试 + golden 重钉**

```bash
python -m pytest tests/plate/test_http_query_views.py -q          # shape 过,capture_or_equal FAIL(3 新行)
rm tests/plate/fixtures/query_views_index.json
GIMBAL_GOLDEN_CAPTURE=1 python -m pytest tests/plate/test_http_query_views.py -q
git diff tests/plate/fixtures/query_views_index.json              # 审阅:恰增 3 行(customer_*),别行零漂
python -m pytest tests/plate -q                                   # 全套件(dispatch 基线必零漂)
```

若 `test_io_declarations_golden.py` 失败(/full 若按端点清单收录新端点):按 Global Constraints 的 golden 程序重钉该 fixture 并 diff 审阅;若通过则不动。

- [ ] **Step 5: 文档同步 + 提交**

`docs/PLATE-API-SURFACE.md`:目录清单补三个新端点(一行一个:method/path/视图);`GET /api/query-views` 条目补 `query_params` 键说明(点击期参数面,§13)。

```bash
git add src/gimbal-plate/gimbal_plate/systems/fin/endpoint/customer_list.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/customer_part.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/customer_policy.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/__init__.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_add.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_add.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_dispatch.py \
        src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_book.py \
        docs/PLATE-API-SURFACE.md \
        tests/plate/test_http_query_views.py tests/plate/fixtures/query_views_index.json
git commit -m "feat(plate): 客户域三端点(列表/详情/策略)+ 级联视图注记 + 四下单端点 value_source 绑定

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: backend — 解释器:点击期 params 合并链 + 缺键豁免 + 点路径投影 + 缓存旁路与单飞键

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/query_view_runner.py`
- Test: `src/gimbal-platform/backend/tests/test_query_view_runner.py`

**Interfaces:**
- Consumes(Task 1/2): 索引行 `query_params` 键;`missing_required` 静态链视角。
- Produces(Task 4 消费): `fetch_rows(name, *, refresh, service_url, owner_id, query_alias, load_credential, click_params: dict[str, Any] | None = None) -> RowsResult`;`project_rows` 支持点路径列;参数面视图(`view["query_params"]` 非空)**不进 L1**(无 fresh/stale),单飞键 = `name::canonical_json(click_params)`,熔断仍按 `name`;点击期 params per-key 覆盖索引静态 params(最高优先)。

- [ ] **Step 1: 写失败测试**

追加到 `tests/plate/../src/gimbal-platform/backend/tests/test_query_view_runner.py`(自包含:monkeypatch `fetch_query_view_index` + `httpx.request`;文件既有 `query_view_runner` 导入与 pytest.asyncio 样板沿用,缺的补 `import asyncio` / `import httpx`):

```python
# ── §13.3 点击期参数面 ────────────────────────────────────────────

_POLICY_VIEW = {
    "name": "customer_policy", "endpoint_id": "fin.customer.policy",
    "method": "POST", "path": "/api/Customer/Policy/getCustomerPolicy",
    "params": {"status": "2"}, "query_params": ["customer_id"],
    "items": "$.data[*]", "label": "policy_name",
    "columns": ["policy_name", "policy_id"], "query_safe": True,
    "missing_required": ["customer_id"], "auth": "none", "timeout_seconds": 5.0,
}


def _patch_view(monkeypatch, view):
    async def fake_index():
        return [view]
    monkeypatch.setattr(query_view_runner, "fetch_query_view_index", fake_index)


@pytest.mark.asyncio
async def test_click_params_overlay_static_and_exemption(monkeypatch):
    """点击期 ▸ 索引静态 params(已含 view.params▸default▸example);缺键被点击期豁免。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    sent = {}

    def fake_request(method, url, **kw):
        sent.update(kw)
        return httpx.Response(200, json={"data": [{"policy_name": "P1", "policy_id": "32"}]})

    monkeypatch.setattr(query_view_runner.httpx, "request", fake_request)
    r = await query_view_runner.fetch_rows(
        "customer_policy", refresh=True, service_url="http://sut",
        owner_id=1, query_alias=None, load_credential=None,
        click_params={"customer_id": "1"})
    assert sent["json"] == {"status": "2", "customer_id": "1"}   # 合并链:点击期最高
    assert r.rows == [{"policy_name": "P1", "policy_id": "32"}]
    assert r.cached is False


@pytest.mark.asyncio
async def test_click_param_absent_still_422(monkeypatch):
    """query_param 未供给 → missing_required 不豁免 → 422。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    with pytest.raises(query_view_runner.QueryViewError) as ei:
        await query_view_runner.fetch_rows(
            "customer_policy", refresh=True, service_url="http://sut",
            owner_id=1, query_alias=None, load_credential=None)
    assert ei.value.status == 422


@pytest.mark.asyncio
async def test_param_face_view_never_enters_l1(monkeypatch):
    """带参数面视图不进 L1:同参数重查再发上游(无缓存命中)。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    calls = []

    def fake_request(method, url, **kw):
        calls.append(kw.get("json"))
        return httpx.Response(200, json={"data": [{"policy_name": "P", "policy_id": "1"}]})

    monkeypatch.setattr(query_view_runner.httpx, "request", fake_request)
    for _ in range(2):
        r = await query_view_runner.fetch_rows(
            "customer_policy", refresh=False, service_url="http://sut",
            owner_id=1, query_alias=None, load_credential=None,
            click_params={"customer_id": "1"})
        assert r.cached is False
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_param_face_single_flight_keyed_by_params(monkeypatch):
    """单飞键 = (view, 点击期 params):并发同参 1 发,异参各 1 发 → 共 2 发。"""
    _patch_view(monkeypatch, dict(_POLICY_VIEW))
    calls = []

    async def slow_request(method, url, **kw):
        calls.append(kw.get("json"))
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"data": [{"policy_name": "P", "policy_id": "1"}]})

    monkeypatch.setattr(query_view_runner.httpx, "request", slow_request)
    await asyncio.gather(
        query_view_runner.fetch_rows("customer_policy", refresh=False,
                                     service_url="http://sut", owner_id=1,
                                     query_alias=None, load_credential=None,
                                     click_params={"customer_id": "1"}),
        query_view_runner.fetch_rows("customer_policy", refresh=False,
                                     service_url="http://sut", owner_id=1,
                                     query_alias=None, load_credential=None,
                                     click_params={"customer_id": "1"}),
        query_view_runner.fetch_rows("customer_policy", refresh=False,
                                     service_url="http://sut", owner_id=1,
                                     query_alias=None, load_credential=None,
                                     click_params={"customer_id": "2"}),
    )
    assert len(calls) == 2


def test_project_rows_dotted_columns():
    """§13.4 点路径列:逐段下钻;缺列(含中途非 dict)= 键缺席。"""
    rows = [{"handover_form": {"client_expand_id": "E1"},
             "customer_service": {"user_name": "庞燕"},
             "finance": [{"chinese_header": "X"}]}]
    out = query_view_runner.project_rows(
        rows, ["customer_service.user_name", "handover_form.client_expand_id",
               "finance.chinese_header", "absent.col"])
    # finance 是数组 → finance.chinese_header 不可导航 = 缺席(不脏写 '--')
    assert out == [{"customer_service.user_name": "庞燕",
                    "handover_form.client_expand_id": "E1"}]


def test_extract_rows_single_object_wraps_one_row():
    """§13.4 单对象型:$.data 命中对象 → 包一行(extract_rows 既有分支的显式钉)。"""
    assert query_view_runner.extract_rows({"data": {"a": 1}}, "$.data") == [{"a": 1}]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_query_view_runner.py -q`
Expected: 新增 6 例 FAIL(`click_params` 未知参数 / 点路径列缺席)。

- [ ] **Step 3: 实现(runner)**

`query_view_runner.py`:

1) 顶部加 `import json`(现无)。

2) `project_rows` 换点路径导航版(替换 123-129 行):

```python
def _dig(row: dict, dotted: str) -> Any:
    """点路径列导航(§13.4):逐段下钻 dict;任一段非 dict/缺席 → _MISSING。"""
    node: Any = row
    for seg in dotted.split("."):
        if not isinstance(node, dict) or seg not in node:
            return _MISSING
        node = node[seg]
    return node


def project_rows(rows: list, columns: list[str]) -> list[dict]:
    """投影到列集(§13.4):含点路径列;缺列 = 键缺席,前端 '--' 语义。"""
    out = []
    for row in rows:
        if isinstance(row, dict):
            proj: dict[str, Any] = {}
            for c in columns:
                v = _dig(row, c) if "." in c else row.get(c, _MISSING)
                if v is not _MISSING:
                    proj[c] = v
            out.append(proj)
    return out
```

3) `_query_sut` 签名与 params 组装(替换 224-240 行相关段):

```python
async def _query_sut(
    view: dict, service_url: str, auth_header: "str | None",
    session: Any, cred_key: "tuple[int, str] | None",
    click_params: "dict[str, Any] | None" = None,
) -> "tuple[list[dict], bool]":
```

组装处(237-240 行)改为:

```python
    # §13.3 合并链 per-key:点击期 ▸ 索引 params(已含 view.params▸default▸example)
    merged_params = {**dict(view.get("params") or {}), **(click_params or {})}
    if method == "GET":
        kw: dict[str, Any] = {"params": merged_params}
    else:
        kw = {"json": merged_params}
```

4) `fetch_rows` 签名(273-277 行)加 `click_params`;体内五处改:

```python
async def fetch_rows(
    name: str, *, refresh: bool, service_url: str, owner_id: int,
    query_alias: "str | None",
    load_credential: "Callable[[int, str], AuthSession | None | Awaitable[AuthSession | None]] | None",
    click_params: "dict[str, Any] | None" = None,
) -> RowsResult:
```

- 开头(`view is None` 检查后)归一 + 参数面判定 + 缺键豁免(替换原 284-286 行 missing 检查):

```python
    click_params = click_params or {}
    has_param_face = bool(view.get("query_params"))   # §13.3 参数面视图
    # §13.3 缺键豁免:索引 missing_required 是静态链视角,点击期供给即补齐
    missing = [k for k in (view.get("missing_required") or []) if k not in click_params]
    if missing:
        raise QueryViewError("missing_required_params",
                             f"必填键仍缺: {missing}", status=422)
```

- L1 旁路(替换 294-297 行):

```python
    stale_entry, fresh = None, False
    if not has_param_face:            # §13.3 参数随表单变,按 view 键必破 → 不进键就不缓存
        stale_entry, fresh = _cache.lookup(name)
        if fresh and not refresh:
            return RowsResult(name, stale_entry.rows, stale_entry.truncated,
                              stale_entry.fetched_wall, cached=True, stale=False)
```

- 单飞键(306 行 `lock = await _view_lock(name)` 改):

```python
    # §13.3 单飞键:参数面视图 = (view, 点击期 params canonical);无参视图维持 view
    lock_key = name
    if has_param_face:
        lock_key = f"{name}::{json.dumps(click_params, sort_keys=True, ensure_ascii=False)}"
    lock = await _view_lock(lock_key)
```

- 锁内双检(308-312 行)加门:`if not refresh and not has_param_face:`(参数面无缓存可双检)。

- 成功回填(319 行)加门:`if not has_param_face: _cache.put(...)`。

- `_query_sut` 调用处(316-317 行)传 `click_params=click_params`。

熔断(`_bump_breaker`/成功清零)键仍用 `name` —— 零改动。

- [ ] **Step 4: 跑测试确认通过 + 回归**

```bash
cd src/gimbal-platform/backend && python -m pytest tests/test_query_view_runner.py tests/test_query_view_cache.py -q
python -m pytest -q     # 全 backend(既有无参视图行为零漂)
```

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/backend/app/services/query_view_runner.py \
        src/gimbal-platform/backend/tests/test_query_view_runner.py
git commit -m "feat(backend): 解释器点击期 params — 合并链/缺键豁免/点路径投影/参数面缓存旁路与单飞键

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: backend — rows 路由 params 参数 + 索引代理路由

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/query_views.py`
- Test: `src/gimbal-platform/backend/tests/test_query_views_route.py`

**Interfaces:**
- Consumes(Task 3): `fetch_rows(..., click_params=...)`;`fetch_query_view_index()`(runner 既有,带 plate memo+熔断)。
- Produces(Task 5 消费):
  - `GET /api/query-views` → `{"items": QueryViewIndexEntry[]}`(索引代理,CurrentUser 门内);
  - `GET /api/query-views/{name}/rows?...&params=<JSON对象串>`(与 service_url/query_alias 同先例:调用方求值,路由无状态;非法 JSON / 非对象 → 422 `bad_params`)。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_query_views_route.py`(client/鉴权 fixture 沿用本文件既有样板;缺的导入补 `query_view_runner`):

```python
# ── §13.3 索引代理 + params 参数 ────────────────────────────────

def test_index_proxy_shape(client, auth):                     # fixture 名以本文件现状为准
    r = client.get("/api/query-views")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["name"] == "customer_part" and i["query_params"] == ["customer_id"]
               for i in items)


def test_rows_params_bad_json_422(client, auth):
    r = client.get("/api/query-views/customer_part/rows"
                   "?service_url=http://sut&params=not-json")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_params"


def test_rows_params_non_object_422(client, auth):
    r = client.get("/api/query-views/customer_part/rows"
                   '?service_url=http://sut&params=[1]')
    assert r.status_code == 422


def test_rows_params_passes_click_params(client, auth, monkeypatch):
    captured = {}

    async def fake_fetch(name, *, refresh, service_url, owner_id,
                         query_alias, load_credential, click_params=None):
        captured["click"] = click_params
        return query_view_runner.RowsResult(name, [], False, "t", False, False)

    monkeypatch.setattr(query_view_runner, "fetch_rows", fake_fetch)
    r = client.get('/api/query-views/customer_part/rows'
                   '?service_url=http://s&params={"customer_id":"1"}')
    assert r.status_code == 200
    assert captured["click"] == {"customer_id": "1"}
```

(索引代理测试依赖 plate 可达;若本文件既有测试对 plate 有 stub 惯例则照搬 stub——核心断言 = 200 + items 结构 + query_params 键。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_query_views_route.py -q`
Expected: 新增 FAIL(路由 404/无 params 解析)。

- [ ] **Step 3: 实现(路由)**

`query_views.py` — 顶部补 `import json`;`get_rows` 前插索引代理;`get_rows` 加 `params` 参数:

```python
@router.get("")
async def list_views(user: CurrentUser) -> dict:
    """索引代理(§13.3):前端参数段消费 query_params;复用 runner 的
    plate memo + 熔断,零新增状态。"""
    items = await query_view_runner.fetch_query_view_index()
    return {"items": items}


@router.get("/{name}/rows")
async def get_rows(
    name: str,
    user: CurrentUser,
    db: DbSession,
    refresh: bool = False,
    service_url: str = "",
    query_alias: str | None = None,
    params: str = "",
) -> dict:
    click: dict[str, Any] | None = None
    if params:
        try:
            parsed = json.loads(params)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params", "msg": "params 非合法 JSON"}) from e
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "bad_params", "msg": "params 须为 JSON 对象"})
        click = {str(k): v for k, v in parsed.items()}
    try:
        r = await query_view_runner.fetch_rows(
            name, refresh=refresh, service_url=service_url,
            owner_id=user.id, query_alias=query_alias,
            load_credential=_loader(db), click_params=click)
    except query_view_runner.QueryViewError as e:
        raise HTTPException(status_code=e.status,
                            detail={"code": e.code, "msg": e.message}) from e
    return {"view": r.view, "rows": r.rows, "truncated": r.truncated,
            "fetched_at": r.fetched_at, "cached": r.cached, "stale": r.stale}
```

(`typing.Any` 已在文件类型注解使用面内则补 `from typing import Any, Annotated`;`GET ""` 注册在 `/{name}/rows` 之前。)

- [ ] **Step 4: 跑测试 + 全量回归 + 提交**

```bash
cd src/gimbal-platform/backend && python -m pytest tests/test_query_views_route.py -q && python -m pytest -q
git add src/gimbal-platform/backend/app/routers/query_views.py \
        src/gimbal-platform/backend/tests/test_query_views_route.py
git commit -m "feat(backend): rows 路由 params 点击期参数 + GET /api/query-views 索引代理

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: frontend — 索引拉取 + Picker 参数段 + Canvas 同名预填/携参/回跳

**Files:**
- Modify: `src/gimbal-platform/frontend/src/api/query-views.ts`
- Modify: `src/gimbal-platform/frontend/src/components/composer/ValueSourcePicker.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(仅取数状态机段:vsPicker/onFieldQuery/onVsRefresh/vsLoad/模板 ValueSourcePicker 绑定)
- Modify: `docs/FIELD-UI-MAPPING.md`(参数段一行)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/ValueSourcePicker.test.ts`、`CaseComposerCanvas.test.ts`

**Interfaces:**
- Consumes(Task 4): `GET /api/query-views`(items 含 `query_params`);rows `params` 查询参数。
- Produces: `fetchQueryViewIndex(): Promise<QueryViewIndexEntry[]>`;`fetchQueryViewRows(name, { refresh?, serviceUrl?, queryAlias?, params? })`;Picker 新 props `paramFields: string[]` / `paramPrefill: Record<string, string>` 与新 emit `query(values)`;Canvas 状态机 `stage: 'params' | 'rows'`(无参视图 stage 恒 rows,现状零变化)。
- **FieldForm.vue 零改动**(Global Constraints);`onVsSelect` 零改动(点路径列到达前端时已被后端投影为**扁平键**,`row[col]`/`setByPath(f.path)` 既有通路直接吃)。

- [ ] **Step 1: 写失败测试(Picker)**

追加到 `ValueSourcePicker.test.ts`(mount 样板沿用本文件既有 helper):

```typescript
// ── §13.5 参数段(stage: params → rows)────────────────────────

it('paramFields 非空:先渲染参数行,预填自 paramPrefill,查询钮 emit query', async () => {
  const wrapper = mountPicker({
    paramFields: ['customer_id'],
    paramPrefill: { customer_id: 'C1' },
    rows: [],
  })
  // 打开 → 参数段
  const input = wrapper.find('.vsp-param-row input')
  expect((input.element as HTMLInputElement).value).toBe('C1')
  await wrapper.find('.vsp-param-query').trigger('click')
  expect(wrapper.emitted('query')?.[0]).toEqual([{ customer_id: 'C1' }])
})

it('↩ 改参数回跳:值保留(修改后回跳可见)', async () => {
  const wrapper = mountPicker({
    paramFields: ['customer_id'],
    paramPrefill: { customer_id: 'C1' },
    rows: [{ policy_name: 'P', policy_id: '1' }],
  })
  await wrapper.find('.vsp-param-query').trigger('click')   // → rows 段
  await wrapper.find('.vsp-back-params').trigger('click')   // ↩ 改参数
  const input = wrapper.find('.vsp-param-row input')
  expect((input.element as HTMLInputElement).value).toBe('C1')   // 值未丢
})

it('无 paramFields:零参数段,直通行集(现状零变化)', () => {
  const wrapper = mountPicker({ rows: [{ a: '1' }] })
  expect(wrapper.find('.vsp-params').exists()).toBe(false)
  expect(wrapper.find('table').exists()).toBe(true)
})

it('错误态也可 ↩ 改参数(参数面不被错误困住)', () => {
  const wrapper = mountPicker({
    paramFields: ['customer_id'],
    error: { code: 'sut_error', message: 'x' },
  })
  expect(wrapper.find('.vsp-back-params').exists()).toBe(true)
})
```

(`mountPicker` 为本文件既有 mount 封装的别名/薄改——传参面两 props;若本文件用内联 mount 则直接内联。)

- [ ] **Step 2: 写失败测试(Canvas)**

追加到 `CaseComposerCanvas.test.ts`(沿用本文件既有 vi.mock('@/api/query-views') 样板,补 `fetchQueryViewIndex` mock;绑定字段用 form 态 decls 直接构造):

```typescript
// ── §13.5 级联参数面:同名预填 / 携参查询 / 单对象点列扇出 ────────

it('query_params 视图:打开即参数段;同名字面量预填、模板串留空', async () => {
  // decls: customer_id(form, value_source customer_list)+ client_expand_id(form,
  // value_source customer_part 点列);step body: { customer_id: 'C1' }
  // mock index: [{ name: 'customer_part', query_params: ['customer_id'], … }]
  // 点 client_expand_id 查钮 → 参数段 input 值 = 'C1'(同名约定预填)
  // 再置 body.customer_id = '${var.x}' 重开 → 参数段 input 值 = ''(模板串留空 §13.6)
})

it('参数确认携 params 查询;单对象行点选点列扇出(§13.4)', async () => {
  // mock rows: [{ 'customer_service.user_name': '庞燕',
  //               'handover_form.client_expand_id': 'E1',
  //               'handover_form.client_expand_name': 'Expand' }]
  // 参数段输入 C1 → 查询 → fetchQueryViewRows 断言 opts.params = { customer_id: 'C1' }
  // 点行 → body.client_expand_id = 'E1' 且 body.client_expand_name = 'Expand'
  //   (点路径列到达前端已是扁平键;onVsSelect 既有通路直写)
})
```

(骨架两例:断言落值写全,组件事件序列按本文件既有「value_source 一查多填」组的触发式样展开。)

- [ ] **Step 3: 跑测试确认失败**

```bash
cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/ValueSourcePicker.test.ts src/components/composer/__tests__/CaseComposerCanvas.test.ts
```
Expected: 新增用例 FAIL(props/emit 不存在)。

- [ ] **Step 4: 实现(api + Picker + Canvas)**

`api/query-views.ts` 追加:

```typescript
/** §13.3 索引代理消费:参数段据 query_params 渲染。 */
export interface QueryViewIndexEntry {
  name: string
  endpoint_id: string
  method: string
  path: string
  params: Record<string, unknown>
  query_params: string[]
  items: string
  label: string
  columns: string[]
  query_safe: boolean
  missing_required: string[]
}

export async function fetchQueryViewIndex(): Promise<QueryViewIndexEntry[]> {
  const { data } = await http.get('/query-views')
  return data.items
}
```

`fetchQueryViewRows` 的 opts 加 `params?: Record<string, unknown>`,params 段加:

```typescript
      ...(opts.params && Object.keys(opts.params).length
        ? { params: JSON.stringify(opts.params) } : {}),
```

`ValueSourcePicker.vue`:

- props 增(withDefaults 包裹或可选 prop;两新 prop 均可选):

```typescript
  /** §13.5 点击期参数名列表;空 = 无参直行集(现状) */
  paramFields?: string[]
  /** 预填值(Canvas 同名约定求值后传入;选择器保持零 IO) */
  paramPrefill?: Record<string, string>
```

- emits 增 `'query': [values: Record<string, string>]`;
- 状态:

```typescript
const stage = ref<'params' | 'rows'>('rows')
const paramValues = ref<Record<string, string>>({})
```

- `watch(() => props.modelValue)` 开分支(open 时):除 `filter.value = ''` 外,加:

```typescript
    if (open) {
      filter.value = ''
      if (props.paramFields?.length) {
        stage.value = 'params'
        paramValues.value = { ...(props.paramPrefill ?? {}) }
      } else {
        stage.value = 'rows'
      }
    }
```

- 模板:`<template v-else>` 内最前插参数段(错误态之外最先判):

```html
        <div v-if="stage === 'params' && paramFields?.length" class="vsp-params">
          <p class="vsp-params-hint">查询参数 — 预填自表单同名键,可改;查询钉当时字面量</p>
          <label v-for="p in paramFields" :key="p" class="vsp-param-row">
            <code class="mono">{{ p }}</code>
            <input v-model="paramValues[p]" type="text" class="vs-filter"
                   :placeholder="`$.${p} 为空或模板时手输`" />
          </label>
          <button type="button" class="vsp-param-query" :disabled="loading"
                  @click="stage = 'rows'; emit('query', { ...paramValues })">
            {{ loading ? '查询中…' : '查询' }}
          </button>
        </div>
        <template v-else>
          <!-- 原 toolbar/表格/banner/meta 整体原样内嵌 -->
```

toolbar 内(本地过滤框之前)加回跳钮:

```html
            <button v-if="paramFields?.length" type="button"
                    class="vs-refresh vsp-back-params" @click="stage = 'params'">
              ↩ 改参数
            </button>
```

错误块(`.vsp-error` 内链接后)加同款回跳钮(错误态不被困):

```html
          <button v-if="paramFields?.length" type="button"
                  class="vs-refresh vsp-back-params" @click="emit('update:modelValue', false) || (stage = 'params')">
            ↩ 改参数
          </button>
```

(错误块回跳直接置 stage —— 错误在拉数期发生,改参数即关错误重开参数段;`emit(...) || …` 换成纯 `stage = 'params'` 亦可,以 vue-tsc 干净为准,采用 `@click="stage = 'params'"`。)

- 样式追加:

```css
.vsp-params { display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
.vsp-params-hint { margin: 0; font-size: 11px; color: var(--c-text-secondary); }
.vsp-param-row { display: grid; grid-template-columns: 130px 1fr; gap: 8px; align-items: center; }
.vsp-param-row code { font-size: 11px; color: var(--c-text-secondary); }
.vsp-param-query {
  align-self: flex-end; padding: 5px 14px; font-size: 12px;
  border: 1px solid #4f46e5; border-radius: 6px; background: #4f46e5;
  color: #fff; cursor: pointer;
}
.vsp-param-query:disabled { opacity: 0.5; cursor: not-allowed; }
```

`CaseComposerCanvas.vue`(仅取数状态机段):

- import 增 `fetchQueryViewIndex` 与 `QueryViewIndexEntry` 类型;
- `VsPickerState` 增三键,reactive 初始化同步:

```typescript
  /** §13.5 参数面:stage params→rows;params = 最近一次携参(refresh 复用) */
  stage: 'params' | 'rows'
  paramFields: string[]
  paramPrefill: Record<string, string>
  params: Record<string, string> | null
```

```typescript
const vsPicker = reactive<VsPickerState>({
  open: false, group: null, anchorPath: '', label: '', columns: [], rows: [],
  truncated: false, fetchedAt: '', stale: false, loading: false, error: null,
  stage: 'rows', paramFields: [], paramPrefill: {}, params: null,
})
```

- `onFieldQuery` 改 async(先定参数面再开,无参数段闪烁):

```typescript
async function onFieldQuery(field: IOFieldBinding) {
  const tmpl = toTemplatePath(field.path)
  const g = valueSourceGroups.value.find((x) => x.fields.some((f) => f.path === tmpl))
  if (!g || !currentStep.value) return
  vsPicker.group = g
  vsPicker.anchorPath = field.path
  await primeParamFace(g)          // §13.5:先定参数面(索引),再开选择器
  vsPicker.open = true
  if (!vsPicker.paramFields.length) void vsLoad(g, false, null)
}

/** §13.5 参数面:索引读 query_params;同名约定预填当前 step body 顶层
 *  字面量(模板串/空 → 留空手输 §13.6);索引不可达按无参处理(rows 侧降级)。 */
async function primeParamFace(g: ValueSourceGroup) {
  let entry: QueryViewIndexEntry | undefined
  try {
    const idx = await fetchQueryViewIndex()
    entry = idx.find((v) => v.name === g.view)
  } catch {
    entry = undefined
  }
  const fields = entry?.query_params ?? []
  vsPicker.paramFields = fields
  const prefill: Record<string, string> = {}
  for (const p of fields) {
    const v = (currentStep.value?.request?.body as Record<string, unknown> | undefined)?.[p]
    prefill[p] = typeof v === 'string'
      ? (v && !v.includes('${') ? v : '')
      : (typeof v === 'number' || typeof v === 'boolean') && v !== null ? String(v) : ''
  }
  vsPicker.paramPrefill = prefill
  vsPicker.stage = fields.length ? 'params' : 'rows'
}
```

- `onVsQuery` 新增 + `onVsRefresh`/`vsLoad` 携参:

```typescript
/** 参数段确认(§13.5):空值剔除(未填 = 未供给,后端缺键 422 兜底)→ 携参拉数。 */
function onVsQuery(values: Record<string, string>) {
  if (!vsPicker.group) return
  const params: Record<string, string> = {}
  for (const [k, v] of Object.entries(values)) {
    const t = v.trim()
    if (t) params[k] = t
  }
  void vsLoad(vsPicker.group, false, params)
}

function onVsRefresh() {
  if (vsPicker.group) vsLoad(vsPicker.group, true, vsPicker.params)
}
```

`vsLoad(g, refresh, params)` 签名加第三参 `params: Record<string, string> | null`;函数体 `vsPicker.params = params`;`fetchQueryViewRows` 调用加 `...(params && Object.keys(params).length ? { params } : {})`。

- 模板 `<ValueSourcePicker>` 绑定追加:

```html
      :param-fields="vsPicker.paramFields"
      :param-prefill="vsPicker.paramPrefill"
      @query="onVsQuery"
```

- [ ] **Step 5: 跑测试 + 类型门 + 文档 + 提交**

```bash
cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit
```

`docs/FIELD-UI-MAPPING.md`:动态取数源段落补一行(参数段:预填/改参数回跳/携参查询,spec §13.5)。

```bash
git add src/gimbal-platform/frontend/src/api/query-views.ts \
        src/gimbal-platform/frontend/src/components/composer/ValueSourcePicker.vue \
        src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue \
        src/gimbal-platform/frontend/src/components/composer/__tests__/ValueSourcePicker.test.ts \
        src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts \
        docs/FIELD-UI-MAPPING.md
git commit -m "feat(frontend): 取数选择器参数段 — 索引拉取/同名预填/改参数回跳/携参查询

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 三套件回归 + dispatch 零漂验证 + spec 补注 + 手验清单

**Files:**
- Modify: `docs/superpowers/specs/2026-09-07-dynamic-value-source-design.md`(§13.5 carry 承载一句 + §13.8 手验留痕位)

**Interfaces:**
- Consumes: Task 1-5 全部产物。
- Produces: 全绿证据 + spec 与实现的一致性收口。

- [ ] **Step 1: 三套件全量**

```bash
python -m pytest tests/plate -q
cd src/gimbal-platform/backend && python -m pytest -q
cd ../frontend && npx vitest run && npx vue-tsc --noEmit
```

Expected: 全绿;`tests/plate/test_dispatch_baseline.py` **零重钉通过**(绑定不进导出面,carry 态未动)。若 dispatch 漂移:停下排查(实现违背了"钉值走既有 body 通路"约束),**不得重钉**。

- [ ] **Step 2: spec 补注**

§13.5 末追加一行:

```markdown
- 消费承载(2026-09-09 实施注):下单端点链路字段(customer_id/policy_id/
  client_expand_* 等)目录默认 carry(值表注入语义不动)——value_source 绑定
  挂 carry 字段合法(能力与状态两轴正交),经 FieldStateSearch 找回翻 form 后
  查钮显形;目录共识与 dispatch 基线零变化。
```

- [ ] **Step 3: 手验清单(SUT fin-tidb.21eflag.com 已可达;与 §11 手验 2-6 同批执行)**

1. 任一下单端点场景(order_order_add / order_entrust_order_add):FieldStateSearch 找回 `customer_id`/`customer_name` → 翻 form;
2. `customer_id` 查钮 → customer_list 无参直查 → 选公司 → `customer_id`+`customer_name` 落值 + view 徽标;
3. `client_expand_id` 查钮 → 参数段 `customer_id` 预填(读 ① 落值)→「查询」→ 单对象一行(`customer_service.user_name` 行首)→ 点行 → `client_expand_id`/`client_expand_name` 点列扇出落值;
4. `policy_id` 查钮 → 参数段 `customer_id` 预填(status=2 静态不可见)→「查询」→ 策略列表 → 选 → `policy_id`+`policy_name` 落值;
5. 「↩ 改参数」回跳值保留;改参重查后已落值字段不被自动清(重选行才覆写);
6. 参数段留空硬查 → 后端 422 缺键提示透出(缺 = 未供给)。

(手验需要三服务在跑:plate 8765 / backend 8000 / 前端 5173;凭证 = 服务绑定 queryUser。执行时机随 SUT 可达,不阻塞本计划合入。)

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/specs/2026-09-07-dynamic-value-source-design.md
git commit -m "docs(spec): §13.5 carry 承载实施注 — 级联绑定挂 carry 字段经找回翻 form

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 自审记录(writing-plans Self-Review)

1. **Spec 覆盖**:§13.2(模型/校验/三端点)→ Task 1/2;§13.3(索引键/params 参数/合并链/缓存/单飞)→ Task 1/3/4;§13.4(点列/三形态——单对象既有 `extract_rows` 分支,Task 3 显式钉测试)→ Task 2/3;§13.5(参数段/预填/回跳/FieldForm 零改/注入字段可查)→ Task 5;§13.6 四红线 → Task 5(预填字面量/模板留空)+ 既有 D8;§13.7 边界 → 各任务注释与 Task 6 手验 5/6;§13.8 → 各任务测试 + Task 6 手验。无缺口。
2. **占位符**:Task 5 Step 2 Canvas 两测试为骨架(断言写全、事件序列引用本文件既有式样)——因目标测试文件的 mount/mock 惯例在实施时以现状为准展开,已给出断言终态;其余步骤均含完整代码。
3. **类型一致**:`click_params`(runner kwarg)= 路由 `click` = 前端 `params`;Picker props `paramFields`/`paramPrefill` 与 Canvas state 同名;`QueryViewIndexEntry.query_params: string[]` 与 plate 索引 `list[str]` 对齐;`'query'` emit 载荷 `Record<string, string>` 三处一致。
