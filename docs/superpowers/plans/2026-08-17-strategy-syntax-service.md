# Strategy 语法服务化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 strategy 语法服务化为 plate 第 8 个 M6 dim(内省 `StrategyUnion`,strategy_ref 预埋排除),平台侧加代理路由 + 通用 StrategyForm(复用 FieldForm),使"plate 加一种策略 = 前端零改动自动出现新条目并渲染表单"。

**Architecture:** plate 侧新增 `StrategyIndex`(items 是 kind 描述符而非数据实例)+ `StrategyKindView`/`StrategyKindDetailView`(字段类型复用 `IOFieldBinding`),注册进 `register_fin_dims`;字段派生复用 `_bindings_from_model` 内省。平台后端克隆 endpoint_catalog 代理模式;前端 `StrategyForm.vue` 复用 FieldForm 渲染,Canvas 的 extract 专用区泛化为 kinds 驱动的通用策略区;策略实例已在 `definition.StepView.strategy`,orchestration 零改动。

**Tech Stack:** Python 3 + Pydantic v2 + FastAPI(plate/平台后端);Vue 3 + TypeScript + Pinia(前端)。

**Spec:** `docs/superpowers/specs/2026-08-17-strategy-syntax-service-design.md`

## Global Constraints

- **strategy schema 零改动**:两侧 `strategy.py`(plate `src/gimbal-plate/gimbal_plate/schema/strategy.py`、runner `src/gimbal/schema/strategy.py`)不动一个字节;schema 锁测试(test_v3_schema_closed / test_v3_schema_consistency)必须全绿。
- **strategy_ref 整条排除**:dim 内省不产出 `strategy_ref`;union 定义原样保留(预埋,待重设计)。
- **字段描述符复用 `IOFieldBinding`**:不新造描述符模型。
- **orchestration 零改动**:StrategyBase 原生 name/enabled/order,策略编辑直接读写 definition。
- **第一版无 widget 覆盖项**:全部走 FieldForm 通用渲染;base_fields 不渲染。
- **测试**:plate 侧 pytest(`tests/plate/`);后端平台用 pytest + MockTransport mock plate(参照 `test_scenario_composer_plate_integration.py` 的 PlateMock);前端 `vite build`(忽略预存 ghost error)。
- **每个 task 结尾必须 commit**;commit message 末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。

---

## File Structure

**plate 侧(改 3 + 新 1):**
- 新增 `src/gimbal-plate/gimbal_plate/http/strategy_dim.py` — kind 内省(`KIND_LABELS` 元数据 + `_descriptor_for(kind)`)+ `StrategyIndex(BaseIndex)` + light/full view 工厂函数。独立成文件避免 grammar.py/views.py 再膨胀。
- 修改 `src/gimbal-plate/gimbal_plate/http/grammar.py` — `__all__` 追加 `StrategyIndex`(re-export 自 strategy_dim)。
- 修改 `src/gimbal-plate/gimbal_plate/http/views.py` — 新增 `StrategyKindView` / `StrategyKindDetailView`(含 `from_descriptor` 工厂)。
- 修改 `src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py` — `register_fin_dims` 追加 strategy dim 注册(注释:语法级 dim,非 fin 数据)。
- 修改 `src/gimbal-plate/gimbal_plate/http/app.py` — 两处"7 个 dim"注释改"8 个(7 数据 + 1 语法)",纯文档。

**plate 测试(新 2):**
- 新增 `tests/plate/test_strategy_dim.py` — 内省单测(kind 清单/字段派生/strategy_ref 排除/base 拆分)。
- 新增 `tests/plate/test_http_strategy.py` — HTTP 面单测(list/detail/full/404/系统作用域/信封)。

**平台后端(新 1 + 改 1):**
- 新增 `src/gimbal-platform/backend/app/routers/strategy_catalog.py` — 代理 `GET /api/strategy-catalog[/full]`,克隆 endpoint_catalog 模式。
- 修改 `src/gimbal-platform/backend/app/main.py` — include_router。

**平台后端测试(新 1):**
- 新增 `tests/test_strategy_catalog.py` — MockTransport mock plate,验证代理/解信封/404/502 路径。

**前端(改 3 + 新 1):**
- 新增 `src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue` — kind 头 + FieldForm 复用 + 删除按钮。
- 修改 `src/gimbal-platform/frontend/src/api/scenario-composer.ts` — `listStrategyKinds()` / `getStrategyKindFull(kind)`。
- 修改 `src/gimbal-platform/frontend/src/types/plate.ts` — `StrategyKindView` / `StrategyKindDetailView`。
- 修改 `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue` — extract 专用区 → 通用策略区(kinds 下拉 + 按 kind 懒加载 detail + StrategyForm 列表);保留既有 extracts 摘要展示。

---

## Task 1: plate 内省 + StrategyIndex + View 模型

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/http/strategy_dim.py`
- Modify: `src/gimbal-plate/gimbal_plate/http/grammar.py`(`__all__`)
- Modify: `src/gimbal-plate/gimbal_plate/http/views.py`
- Test: `tests/plate/test_strategy_dim.py`

**Interfaces:**
- Consumes: `gimbal_plate.schema.strategy`(Extract/Assign/Assertion,只读 import)、`gimbal_plate.schema.endpoint.io_spec._bindings_from_model`(私有函数,同包 http → schema 单向依赖,不进 `__all__` 面)
- Produces: `StrategyIndex` (BaseIndex);`StrategyKindView{kind,label,phase}`;`StrategyKindDetailView{+fields,base_fields: list[IOFieldBinding]}`;kind 描述符 dataclass(内部)

- [ ] **Step 1: 写失败测试** `tests/plate/test_strategy_dim.py`:

```python
"""strategy dim 内省单测 —— kind 清单 / 字段派生 / strategy_ref 排除 / base 拆分。"""
from gimbal_plate.http.strategy_dim import StrategyIndex

def test_kinds_exclude_strategy_ref():
    idx = StrategyIndex(registry=None)
    kinds = [it["kind"] for it in idx.list_global()]
    assert sorted(kinds) == ["assertion", "assign", "extract"]
    assert idx.get("strategy_ref") is None      # 预埋字段,整条排除

def test_extract_fields_derived():
    idx = StrategyIndex(registry=None)
    item = idx.get("extract")
    names = [f["name"] for f in item["fields"]]
    assert "expression" in names and "target" in names
    scope = next(f for f in item["fields"] if f["name"] == "scope")
    assert scope["ui_kind"] == "select"
    assert "scenario" in scope["enum"]
    assert "kind" not in names                  # 判别字段剔除

def test_base_fields_split():
    idx = StrategyIndex(registry=None)
    item = idx.get("assertion")
    base_names = [f["name"] for f in item["base_fields"]]
    assert "order" in base_names and "onFailure" in base_names
    op = next(f for f in item["fields"] if f["name"] == "operator")
    assert op["ui_kind"] == "select" and "eq" in op["enum"]

def test_operator_enum_full():
    idx = StrategyIndex(registry=None)
    op = next(f for f in idx.get("assertion")["fields"] if f["name"] == "operator")
    assert len(op["enum"]) == 14                # AssertOperator 全量
```

- [ ] **Step 2: 实现** `strategy_dim.py`:`KIND_LABELS = {"extract": ("从响应提取变量", "after_request"), "assign": ("准备入参赋值", "before_request"), "assertion": ("响应断言", "verifying")}`;`_descriptor_for(kind)` 内省类(剔除 `kind` 判别字段;StrategyBase 字段集从 `StrategyBase.model_fields` 判定拆进 base_fields;业务字段走 `_bindings_from_model` 后按类自身字段名过滤)。**注意(2026-08-17 实测)**:Enum 字段(Scope/AssertOperator/FailurePolicy)在属性级输出 `{"$ref": "#/$defs/X"}` 而非内联 `enum`,`_bindings_from_model` 直接消费会误判 `ui_kind=unknown`——需先做一步本地 `$defs` ref 解析(把 `$ref` 展开为内联 enum;`default` 与 `$ref` 是 sibling,`prop.get("default")` 不受影响)再派生。`StrategyIndex` 四方法(list_for_system 无视 system 返回全量,docstring 标明 grammar-level dim)。
- [ ] **Step 3: View 模型** 加进 views.py,`from_descriptor` 工厂 + `model_dump(mode="json")`。
- [ ] **Step 4: 跑测试**:`pytest tests/plate/test_strategy_dim.py -q` 全绿;`pytest tests/plate/test_v3_schema_closed.py tests/plate/test_v3_schema_consistency.py -q` 确认 schema 锁不受扰动。
- [ ] **Step 5: commit** `feat(plate): strategy dim 内省与 view 模型 (Task 1)`

## Task 2: dim 注册 + HTTP 面打通

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py`
- Modify: `src/gimbal-plate/gimbal_plate/http/app.py`(注释)
- Test: `tests/plate/test_http_strategy.py`

**Interfaces:**
- Consumes: Task 1 的 StrategyIndex / view 工厂
- Produces: `GET /api/strategy`(light list)、`GET /api/strategy/{kind}`、`GET /api/strategy/{kind}/full`、系统作用域变体(经既有通用路由,零新路由代码)

- [ ] **Step 1: 写失败测试** `tests/plate/test_http_strategy.py`(用 conftest 的 `http_client`,其 registry 已被 `register_fin_dims` 装配,Task 2 的注册一完成即绿):
  - `GET /api/strategy` → 200,`data.items` 3 项,`dim == "strategy"`,每项有 kind/label/phase
  - `GET /api/strategy/extract/full` → 200,`data.item.fields` 含 expression(ui_kind=text)/scope(select+enum)
  - `GET /api/strategy/strategy_ref/full` → 404 dim_item_not_found
  - `GET /api/strategy/nope` → 404
  - `GET /api/systems/fin/strategy` → 200 且 items 与全局一致(语法全局)
  - `GET /api/strategy/extract/references` → 200,references.systems == []
- [ ] **Step 2: 注册** dimensions.py 追加 `reg.register_dim("strategy", DimSpec(name="strategy", index=StrategyIndex(registry=reg), view_factory=..., full_view_factory=..., actions={}))`,注释"语法级 dim,非 fin 数据;strategy_ref 预埋排除"。
- [ ] **Step 3: app.py** 两处"7 个 dim"注释 → "8 个(7 数据 + 1 语法)"。
- [ ] **Step 4: 全量回归** `pytest tests/plate/ -q`(既有 7-dim 显式枚举测试不受影响);起 `run_plate.py`,`curl /api/strategy` 与 `/api/strategy/extract/full` 人工验证信封。
- [ ] **Step 5: commit** `feat(plate): strategy dim 注册, M6 第 8 dim 打通 (Task 2)`

## Task 3: 平台后端 strategy_catalog 代理

**Files:**
- Create: `src/gimbal-platform/backend/app/routers/strategy_catalog.py`
- Modify: `src/gimbal-platform/backend/app/main.py`
- Test: `tests/test_strategy_catalog.py`

**Interfaces:**
- Consumes: plate `GET /api/strategy`(list)、`GET /api/strategy/{kind}/full`
- Produces: `GET /api/strategy-catalog`(返回 items 数组)、`GET /api/strategy-catalog/{kind}/full`(返回 item);错误路径同 endpoint_catalog(502 plate_unavailable / 404 / 信封透传)

- [ ] **Step 1: 写失败测试**(MockTransport mock plate,含 200/404/502 三路)。
- [ ] **Step 2: 实现**:克隆 endpoint_catalog.py 结构,`prefix="/strategy-catalog"`;list 路由解信封 `data.items`;detail 路由解 `data.item`;main.py include_router。
- [ ] **Step 3: 跑测试** + 起服务 curl 验证(需 plate 在跑)。
- [ ] **Step 4: commit** `feat(platform): strategy_catalog 代理路由 (Task 3)`

## Task 4: 前端类型 + API + StrategyForm

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue`
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts`
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`

**Interfaces:**
- Consumes: `GET /api/strategy-catalog[/full]`(Task 3);`FieldForm`(props: bindings/body);`StrategyView`(既有)
- Produces: `StrategyForm` 组件(props: `strategy: StrategyView`, `detail: StrategyKindDetailView`;emit: `remove`);内部 `v-model` 语义 —— FieldForm `@update:body` 直接改 props 引用的策略对象(与 Canvas 现有 extract 行为一致的直接变异模式)

- [ ] **Step 1: 类型** plate.ts 新增两个 view 接口(带注释:对齐 plate http/views.py 的 StrategyKindView/DetailView,语法引用数据,不进 draft)。
- [ ] **Step 2: API 函数** scenario-composer.ts 加 `listStrategyKinds` / `getStrategyKindFull`。
- [ ] **Step 3: StrategyForm.vue**:kind 头(label + phase 徽章 + kind 小标签 + 删除按钮)+ `FieldForm :bindings="detail.fields" :body="strategy"`;base_fields 不渲染;样式对齐 Canvas 现有 `.extract-row` 视觉(4 色 phase 徽章:before_request 橙 / after_request 绿 / verifying 紫,呼应 FIELD-UI-MAPPING 的 source_kind 配色心智)。
- [ ] **Step 4: `vite build`** 通过(过滤 TS6305 ghost error)。
- [ ] **Step 5: commit** `feat(frontend): StrategyForm 通用策略表单组件 (Task 4)`

## Task 5: Canvas 集成 — extract 专用区泛化为通用策略区

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`

**Interfaces:**
- Consumes: Task 4 全部;`definition.steps[*].strategy`(直接变异,容器方案);`EndpointFullView.responses[200].assertable_fields`(已在 `/full` 响应里,零新增请求)
- Produces: 通用策略编辑区(替换 extract 专用区);"+ 添加策略"下拉(kinds 驱动,含"从响应提取变量/准备入参赋值/响应断言");按 kind 懒加载 detail 的模块级缓存;添加时按 detail.fields 的 default 构造策略实例骨架(含 `kind` 判别字段);existed extract 草稿照常渲染
- **endpoint 策略原料预填**(2026-08-17 讨论并入):`onAddEndpoint` 拉的 `/full` 里**保存 `assertable_fields` 与 `success_criteria`/`failed_criteria`**(此前只取 `request.fields` 就丢弃),初始策略由 endpoint 契约驱动构造,替代硬编码的 `$.status eq 200`

- [ ] **Step 1: 模板改造**:extract 专用区(`el-form-item label="extract..."` 那段)替换为"策略"区 —— 每条策略一行 `StrategyForm`,底部下拉按钮添加;kinds 加载失败时降级显示既有 extract 专用 UI(保底,不阻塞编排)。
- [ ] **Step 2: 脚本**:`onMounted` 拉 kinds;`addStrategy(kind)` 构造骨架(`{kind, ...按字段 default 展开}`)push 进 `currentStep.strategy`;`removeStrategy(s)` splice;detail 缓存 `Map<kind, detail>`。**删除** `addExtract`/`removeExtract`/extract 专用模板(摘要展示区保留)。
- [ ] **Step 3: endpoint 策略原料预填**(`onAddEndpoint` 内,替代硬编码 `$.status eq 200`):
  - `/full` 拉取后保存 `full.responses?.['200']?.assertable_fields` 与 `full.metadata?.{success_criteria, failed_criteria}`(当前只取 `request.fields` 就把响应元数据丢弃了);
  - 初始 strategy 构造:`$.status eq 200` 断言保留为**保底第一条**(HTTP 层),其上追加:
    - `success_criteria` 非空 → 一条 `assertion { target: '$.code', operator: 'eq', expected: 0, message: success_criteria }`——**仅当** `assertable_fields` 含 `$.code` 或 `$.data.code`(避免给没有 code 语义的接口塞无效断言);不满足条件时跳过,target 候选探测顺序写成常量数组;
    - 断言 target 的 JSONPath 写法沿用 `$.status`(现状),`response.status` 写法差异记录到 known-issues,**不在本期统一**(涉及 runner resolver 验证,单独立项);
  - `assertable_fields` 同时存入 step 级 `view_hints`(或 Canvas 本地 Map,`endpoint_id → string[]`),供后续 target/expression 下拉候选使用(本期只存不消费);
  - 预填产生的断言与用户手动添加的策略无形态差异(同一 StrategyView),可删可改。
- [ ] **Step 4: E2E 验证**(gimbal-tmp 脚本,复用既有 Playwright 模式):新建场景 → 加 endpoint(选一个 success_criteria 非空且响应含 code 字段的,如 order_order_detail)→ DOM 审计初始策略 ≥2 条、含 `$.code eq 0` 断言 → 添加 assign + assertion → operator 下拉渲染 14 项 → 保存 reload 后策略仍在;再加一个无 success_criteria 的 endpoint 确认只有保底 status 断言;截图。
- [ ] **Step 5: `vite build` + 手动冒烟**(选一个已有 extract 的场景确认不回归)。
- [ ] **Step 6: commit** `feat(frontend): Canvas 策略区泛化 + endpoint 契约驱动预填 (Task 5)`

## Task 6: 收尾 — 文档 + 回归

**Files:**
- Modify: `docs/PLATE-API-SURFACE.md`(strategy dim 三个路由)
- Modify: `docs/FIELD-UI-MAPPING.md`(§2 新增"策略表单"小节:StrategyKindDetailView.fields 驱动,词汇表同 IOFieldBinding)

- [ ] **Step 1: 两份文档补 strategy 面**(路由/响应示例/前端渲染映射行)。
- [ ] **Step 2: 全量回归**:plate `pytest tests/plate/ -q`;平台后端 pytest;前端 `vite build`。
- [ ] **Step 3: commit** `docs: strategy 语法服务化文档补充 (Task 6)`

---

## 验收清单(对照 spec)

- [ ] `pytest tests/plate/` 全绿(schema 锁不破)
- [ ] `curl /api/strategy` 返回 3 kinds,**无 strategy_ref**
- [ ] `/api/strategy/assertion/full` 的 operator 字段 enum=14 项、ui_kind=select
- [ ] 平台前端能添加 assign/assertion 并保存 reload 不丢
- [ ] **加 endpoint 后初始策略由契约驱动**:有 success_criteria + code 字段的接口得到 `$.status eq 200` + `$.code eq 0` 两条;没有的只有保底 status 断言
- [ ] 既有 extract 草稿零回归
- [ ] orchestration / CaseComposer.vue / store / 后端 draft 结构零改动
- [ ] 两侧 strategy.py 零字节改动(`git diff` 证明)
