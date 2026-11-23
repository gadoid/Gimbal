# carry 字段找回与导出解析态穿线 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 09-05 field-state-catalog 的两笔活跃欠账(§10.0 + §10.6):① 字段状态搜索框 —— carry 字段可找回(含 plate 共识 carry 的备注族),状态写入升级为级联批量增量(顺带修复行尾无法 carry 容器的隐性缺陷);② plate 导出定面切解析链 —— 导出产物面与 composer/注入/物化一致,存量场景逐键零漂。

**Architecture:** 两条独立链。**A 前端链**(纯 platform frontend):declarations.ts 新增两个纯函数(searchCorpus / cascadeIncrements)→ 新组件 FieldStateSearch.vue → Canvas 统一写入通路(applyFieldStates 批量乐观 + 整批校验回滚,行尾下拉同换此通路)。**B plate 链**:schema/step.py Step 收编 field_states(平台配置意图,plate 唯一消费点 = 导出定面)→ export/platform.py `_render_request_view` 增参切解析态(plate 侧 5 行 resolve_state 镜像)→ dispatch 基线存量零漂对拍。平台后端预期零代码改动(注入/物化已 join,回归验证)。

**Tech Stack:** Vue 3 `<script setup>` + vitest(@vue/test-utils 挂载级,TDD Red-Green)/ pydantic v2 + pytest。

**Spec:** [2026-09-07-field-recovery-and-export-threading-design.md](../specs/2026-09-07-field-recovery-and-export-threading-design.md)(章节引用 §2=搜索框/§3=导出穿线;级联规则表 = spec §2.3)。

## Global Constraints

- **测试命令**:
  - 前端:`cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/<file>`;类型 `npx vue-tsc --noEmit`(EXIT 0)。CWD 必须在前端目录(@ alias);
  - plate:`cd /d/Gimbal/Gimbal && python -m pytest tests/plate -q`(CWD 必须仓库根部);
  - backend:`cd src/gimbal-platform/backend && python -m pytest tests -q`。
- **TDD 纪律**:每例先 RED(确认失败原因正确)再 GREEN;GREEN 最小实现。
- **解析链三处镜像纪律**:resolve_state 公式 `field_states[path] ?? entry.state ?? 'form'` 现有 platform backend(field_state_resolution.py)与前端(declarations.ts resolveState)两处,本计划新增 plate export 第三处 —— 三处同式(形状防御 + 词表校验),改动词表时三处同步(09-05 §3.2 跨语言边界声明)。
- **基线零重钉**:io_declarations golden 与 dispatch 基线 fixture 本项目**不动**;存量场景导出逐键零漂是验收硬门(spec §3.5)。dispatch 对拍:`python tools/ab_dispatch_dump.py --values-from tests/plate/fixtures/dispatch_baseline.json` 六节比对(exports/convert 节零 diff)。
- **不动**:gimbal 执行核(resolver/jsonpath/context);export/gimbal.py(无面逻辑,已 grep 验证);平台后端(预期零改动,Task 8 仅回归);端点级 request_fields(共识默认领地)。
- **级联语义**(已拍板,spec §2.3):surface(target=form/collapse)= path + 解析态 carry 的祖先容器(祖先落 **collapse**,最小侵入);sink(target=carry)= path + 解析态非 carry 的子孙;容器 surface 不动子孙增量;祖先显式 carry 增量被 surface 覆写;同值仍写显式增量(↺ 可回);↺ 仅清自身。
- **不提交**:未获指令不 git 提交(工作树含本计划外的文档/注释改动,见任务 9 汇总)。

---

### Task 1: declarations.ts — searchCorpus + cascadeIncrements 纯函数

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`
- Test(新): `src/gimbal-platform/frontend/src/components/composer/__tests__/declarations.search.test.ts`

**Interfaces:**
- Produces:
  - `searchCorpus(declarations, fieldStates?): Array<{ path, name, description, type, resolved: FieldState, overlay: boolean, breadcrumb: string }>` —— iterFlat 全量(children 先序,**不按状态剪**;carry 是搜索语料);overlay = field_states[path] 存在且合法;
  - `cascadeIncrements(declarations, fieldStates, path, target: FieldState): Record<string, FieldState>` —— 级联规则见 Global Constraints;目录外 path → 空对象(防御,不上抛)。

- [ ] **Step 1: RED — 失败测试**
  - searchCorpus:① 语料含解析态 carry 条目与容器条目;② resolved/overlay 正确(增量命中 / 读穿 / 词表外增量视同缺席);③ 面包屑 = 祖先 name 链。
  - cascadeIncrements:④ surface 深层字段拉起 carry 祖先(祖先 = collapse,path = target);⑤ sink 容器压平解析态非 carry 子孙;⑥ 祖先显式 carry 增量被 surface 覆写;⑦ 同值写入仍产显式增量;⑧ 容器 surface 不动子孙增量;⑨ 目录外 path → `{}`。
- [ ] **Step 2: GREEN** —— 复用 iterFlat / resolveState;祖先链从 children 树下钻收集(path 前缀 + 容器判定)。
- [ ] **Step 3:** `npx vue-tsc --noEmit` EXIT 0。

### Task 2: FieldStateSearch.vue — 搜索组件

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/composer/FieldStateSearch.vue`
- Test(新): `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldStateSearch.test.ts`

**Interfaces:**
- Props: `corpus: Array<searchCorpus 行>`(Canvas 预计算);
- Emits: `apply: [increments: Record<string, FieldState>, origin: { path: string; target: FieldState }]`;
- UI:防抖 200ms 输入框(placeholder `搜索字段(含 carry 传递面)`)+ 结果面板(前 50 + 计数);行 = 面包屑 › name + type + 解析态徽标 + FieldStateSelect(复用,`overlay` prop 直连,change/reset 上抛);ESC/失焦清面板;空查询不渲染面板。

- [ ] **Step 1: RED** —— 挂载渲染输入框;输入过滤(name/path/description 大小写不敏感子串);命中行 change → emit apply(增量批 + origin);↺ → emit apply(仅清该 path 的批);空态/超 50 折叠;失焦清面板。
- [ ] **Step 2: GREEN** —— 最小组件;样式对齐 composer 现有 hint/徽标风格。
- [ ] **Step 3:** vitest + vue-tsc 绿。

### Task 3: Canvas — applyFieldStates 统一写入通路 + 挂载搜索框

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(扩展)

**Interfaces:**
- `applyFieldStates(step, increments)`:① 快照 before;② 合并(空 → `delete step.field_states`,§3.1 零存储);③ `validateEndpointFieldStates`(整批一次);④ errors 非空 → 回滚 + 行内提示(code/path)。
- `onFieldState`(行尾)改调 `cascadeIncrements` → `applyFieldStates`(隐性缺陷修复:carry 容器一次成功)。
- 请求签 hint 行区挂 `<FieldStateSearch :corpus="searchCorpus(stepDecls(step), step.field_states)" @apply=...>`(仅 activeIoTab === 'request' 且有端点契约)。

- [ ] **Step 1: RED** —— ① 批量写合并 + 清空删键;② 校验失败整批回滚(tree_inconsistency 构造:手工传非级联增量);③ 行尾 carry 容器(cascadeIncrements 路径)一次通过校验;④ 搜索行 apply 落地为 field_states(含级联祖先)。
- [ ] **Step 2: GREEN** —— 替换 onFieldState 内核;挂载组件。
- [ ] **Step 3:** 前端全套件 + vue-tsc 0。

### Task 4: plate Step 收编 field_states

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/step.py`
- Test: `tests/plate/test_schema_step_field_states.py`(新)

**Interfaces:**
- `Step.field_states: Optional[dict[str, str]] = Field(default=None, description=...)`(spec §3.2 文案:平台配置意图,plate 唯一消费点 = 导出定面);
- 序列化纪律:None 不携带 —— 验证 Scenario.model_dump 对无增量 step 的输出**不含 field_states 键**(wire 零漂;若 dump 默认携带 None 则 export 序列化处 exclude_none)。

- [ ] **Step 1: RED** —— ① 带 field_states 的 step JSON roundtrip 保留;② 无增量的 step dump 输出与改动前逐键相等(零漂守卫);③ 词表外值/形状不符容忍进入(不在此层拒 —— 解析链防御口径)。
- [ ] **Step 2: GREEN** + plate 套件绿(Step 被大量既有测试消费,零回归确认)。

### Task 5: export/platform.py — 面基准切解析链

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/export/platform.py`(`_render_request_view` + platform.py:592 调用点 + 3 处注释由"已立项"改"已实施")
- Test: `tests/plate/test_export_resolved_face.py`(新)

**Interfaces:**
- `_render_request_view(request, ep, field_states: Any = None)`;
- plate 侧 `resolve_state(path, entry_state, field_states)`(模块级 5 行,docstring 注明与 platform field_state_resolution / 前端 declarations.ts 三处镜像纪律);
- 面语义(spec §3.3):carry 面(解析态)= 不补默认 + 透传字面量;form/collapse 面 = 补全链不变;fields_meta 登记面 = 解析态非 carry 顶层条目,条目 state = 解析态。

- [ ] **Step 1: RED** —— 四象限:① form→carry 增量:不补默认/不进 fields_meta/透传;② carry→form:补默认 + 登记 + state='form';③ 容器整 sink:整树不补;④ 深层 surface(祖先增量随行):补叶子。⑤ 存量无增量 = 与旧输出逐键相等(读穿等价守卫)。⑥ 端点级 request_fields 不受 field_states 影响(不传参)。
- [ ] **Step 2: GREEN** —— 调用点 592 穿 `s.field_states`;实现镜像 resolve_state。
- [ ] **Step 3:** plate 套件绿。

### Task 6: dispatch 基线存量零漂对拍

**Files:**
- 无产物改动(验证任务);若漂移 → 回 Task 4/5 修序列化,**禁止重钉基线**。

- [ ] **Step 1:** `python tools/ab_dispatch_dump.py --values-from tests/plate/fixtures/dispatch_baseline.json` 六节比对 —— endpoints/carry_faces/carry_injected/convert_gimbal/convert_platform/exports 与基线零 diff。
- [ ] **Step 2:** 构造带 field_states 的 fixture 场景(新建临时语料,不入库)→ convert 产物 = spec §3.4 期望终态(form→carry 字段不在 body/fields_meta)。

### Task 7: 平台侧回归(预期零改动)

- [ ] **Step 1:** backend 套件绿(carry_injection / build_carry_context 已 join,Step 新键零影响确认);
- [ ] **Step 2:** 前端 e2e 手验(可用):搜索框找回备注族字段 → 切 form → 保存 → 导出预览面一致。

### Task 8: 文档收尾

- [ ] 09-05 spec §10 表:#0 / #6 行状态改"已实施 → commit <hash>";09-07 spec §6.3(gimbal 容忍性)实测结果销账;
- [ ] FIELD-UI-MAPPING.md 增搜索框条目;PLATE-API-SURFACE.md Step wire 说明补 field_states。

### Task 9: 门禁与交付汇总

- [ ] 三套件 + vue-tsc 0 全绿;
- [ ] 变更清单交付(含本计划前已存在的文档/注释改动:09-05 §10 重写、FieldStateSelect/platform.py 指针注释、2 份新文档),按用户指令分批提交。
