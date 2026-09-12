# 平台 API 文档里的成节不实内容（`docs/PLATFORM-SCENARIO-COMPOSER-API.md`）

> **模块**：文档（平台唯一 API 文档）
> **状态**：已知未修复
> **来源**：架构收敛执行会话自查（非 spec 条目）
> **权威清单**：`.superpowers/sdd/2026-09-12-architecture-convergence/task-7b-report.md` 的「残留清单更新」（第三轮改写那份）
> **本记录不改该文档**（另一个任务所有），只登记性质、范围与正确处置方式。

---

## 0. 先说性质

该文档有**两类**问题，处置方式完全不同，混为一谈会做出更坏的结果：

| 类 | 举例 | 性质 | 正确处置 |
| --- | --- | --- | --- |
| **甲** | §4.8 / §4.9 / §4.10 / §4.11 / §4.14 | 整节描述的**端点不存在**（`/api/cases` 家族） | **端点级重写**这些节 |
| **乙** | §4.3 的 `docs:373` | 端点真实存在，只是**组件名不实** | 按实现改一处引用即可（**可独立修**） |

**为什么不能把甲类当乙类修**：把甲类节里的旧组件名逐个换成真实文件名，会让「`GET /api/cases` → `Case[]`」这个**更大的假陈述**看起来像已经核实过 —— 那是把半真换成**更精致的半真**（task-7b 报告的原话，第三轮复核采纳的判据）。同理，用一个真实文件名去替换不存在的端点，只会让下一轮复核更难发现端点本身是假的。

---

## 1. 甲类：`/api/cases` 家族的整节不实

**证据（端点不存在）**：

- Case 层已解散，写在路由模块的 docstring 里：

```python
# src/gimbal-platform/backend/app/routers/runs.py:6-8
The former Case layer was dissolved — the run recipe (dataSetIds /
serviceBindings / stepTo / nRuns / parallel) lives entirely in
``RunRequest``; …
```

- 路由注册表里**没有** cases：`src/gimbal-platform/backend/app/main.py:111-133` 的 `include_router` 清单（auth / auth_sessions / executions / users / runs / data_sets ×2 / endpoint_catalog / strategy_catalog / constants / generator_catalog / adaptations / carry / query_views / scenarios）；
- 文件层面也不存在：`src/gimbal-platform/backend/app/routers/` 下**无** `cases.py`、**无** `envs.py`。

**受影响的小节**（标题与行号，本会话读自该文档目录）：

| 节 | 标题 | 行 |
| --- | --- | --- |
| §4.8 | `GET /api/cases` | `:458` |
| §4.9 | `GET /api/cases/{caseId}` | `:476` |
| §4.10 | `PATCH /api/cases/{caseId}` | `:486` |
| §4.11 | `DELETE /api/cases/{caseId}` | `:506` |
| §4.14 | `POST /api/cases/{caseId}/data-sets` | `:539` |

> **对既有清单的一处更正**：任务里列的是 §4.8 / §4.9 / §4.11 / §4.14；本会话按节标题逐条核对，**§4.10（`PATCH /api/cases/{caseId}`）同属该家族**，一并计入。§4.14 的真实路由是**场景嵌套**的：`POST /api/scenarios/{scenario_id}/data-sets`（`src/gimbal-platform/backend/app/routers/data_sets.py:146-153`，在 `main.py:122` 以 `data_sets.create_router` 注册）—— 即该节的**路径与权限句都错**，不是「换个前端组件名」能收口的。

**影响**：这是平台**唯一**的 API 文档（文档自己的 §9 定位：「`frontend/src/api/scenario-composer.ts` 本文件的前端实现（一一对应每个端点）」）。任何按它对接的人会**实现一组不存在的端点**；而且它同时让读者以为「Case 层还在」—— 与 §0 架构图、§2.2、§3 的 `⏳` 状态列互相强化同一个幻觉。

---

## 2. 乙类：`docs:373` 的组件名不实（**可独立修**）

§4.3 的**端点是真的**：

```text
### 4.3 `GET /api/scenarios/{scenarioId}`            ←  :371
**角色**：场景详情（前端 `ScenarioEditorMeta/Steps.vue`）  ←  :373
**响应**：`200 OK` → `Scenario`
```

- 端点存在：`scenarios.router` 注册于 `main.py:133`（`prefix="/api"`），文档 §4.3 描述的 `GET /api/scenarios/{scenarioId}` 与「响应 `Scenario`」一致（`app/schemas/scenario_composer.py:354` 有 `class Scenario`）；
- 组件不存在：`git ls-files src/gimbal-platform/frontend/src/components/ScenarioEditorMeta/Steps.vue` = **0 行**（同批核实的还有 `views/Cases.vue`、`views/CasesOfScenario.vue`、`components/CaseEditorBasic.vue`，均为 0）。

**处置**：这一处**可以**单独修（改引用即可），且**应当**单独修 —— 因为该节其余断言为真。修法照 §4.7 的先例：读实现找真实入口再填（task-7b 对 §4.7 就是这么做的：从 `views/CaseComposer.vue:185-188` 的按钮 → `api/scenario-composer.ts:211-219` 的 `POST /scenarios/preview-plate` 逐跳验证）。

---

## 3. 其余陈旧内容（同文档，非本记录主张的精确清单）

以下同属残留（**权威清单见 §0 的 task-7b 报告**）：§0 架构图与「1:1 Scenario↔Case」断言、§1.3、§1.4、§2.2（`Case` 模型）、§2.5（`RunEnv`）、§3 的状态列、§6、§7、§8、文件头。本会话实地核到的两条：

1. **§2.2 / §2.5 描述的是不存在的模型**：`app/schemas/scenario_composer.py` 的类清单里**没有** `class Case`、**没有** `class RunEnv`（该文件现有：ScenarioMeta / StepOrchestration / Orchestration / ScenarioDraft / DataSet / DataSetSummary / DataSetDraft / ServiceBinding / DataSetSelection / RunScheme / RunSchemesIn / ExportOverlay / RunRequest / RunResponse / PreviewPlateIn / PreviewPlateError / PreviewPlateResponse / StarIn / Scenario）。§2.5 把 `RunEnv` 当成一个现行模型展示（`:192-200`）。
2. **§1.3 引用了不存在的 `cases.py`**：「**成功**直接返回数据本体（与现有 `cases.py` 一致…）」（`:59`）—— `app/routers/cases.py` 不存在（§1 证据）。

### 3.1 本计划**引入**的一处自相矛盾（值得单独点名）

同一份文档里，**§3 的端点总览**与 **§4.17** 已被本轮文档工作标为 `/api/envs` **已退役**（`docs:314` 的 `❌ 已退役（D2，0f136c7）`），但 **§7 的实现 TODO** 仍把它当作待写文件、把 `RunEnv` 当作待建模型：

```text
## 7. 实现 TODO（按优先级）                      ←  :835
1. ⏳ `app/schemas/scenario_composer.py` — Pydantic 模型（Scenario / Case / DataSet / RunEnv / …）   ←  :837
3. ⏳ `app/services/case_store.py` — 文件型 CRUD                                    ←  :839
8. ⏳ `app/routers/cases.py` — **追加** §4.8–4.11                                  ←  :844
10. ⏳ `app/routers/envs.py` — §4.17                                               ←  :846
```

**处置**：与甲类**同一个结论** —— **逐节重写**（TODO 清单与状态列必须与端点表同口径重建），**不能**用「删掉第 10 行」的一行补丁收口：该清单里 `case_store.py`（`:839` 第 3 项）、`routers/cases.py`（`:844` 第 8 项）同样指向不存在的文件（均 `git ls-files` = 0），而 `scenario_store.py` / `data_set_store.py` / `plate_client.py` / `run_dispatcher.py` / `routers/scenarios.py` / `routers/data_sets.py` / `routers/runs.py` / `tests/test_scenario_composer_api.py` 均已存在（`git ls-files` = 1）—— 即整张表的「待实现」前提**整体过期**。

---

## 4. 本会话未核实、因此**不主张**的两处（留给下一轮逐条核）

1. **§6「与 Plate 一期接口的对接」**：残留清单列了它，但本会话的 spot check **没能证伪**其 plate 侧行 —— plate 的语法路由是**维度泛化**的（`src/gimbal-plate/gimbal_plate/http/routes_grammar.py:43` `APIRouter(prefix="/api")`；`:419` `@router.get("/{dim}/full")`、`:436` `@router.get("/{dim}/{id}/full")`），所以文档里的 `GET /api/scenario/full` / `GET /api/scenario/{id}/full` 很可能**是真实路由**（`dim="scenario"`，正如平台实际使用的 `/api/endpoint/{id}/full` 即 `dim="endpoint"`）。⇒ **不要**在未逐条核实前把 §6 当假陈述清掉。
2. **§1.4 错误码表**：未逐行核实（哪些码仍在用、哪些随 Case 层消失）。

---

## 5. 优先级：P1

按 README：**触发条件明确、可控、规避成本低**。

- **触发条件明确**：任何读者按该文档对接（它是平台唯一 API 文档，且被文档自身声明为「前端实现一一对应每个端点」）；
- **规避成本低**：处置是**有界的端点级重写**（§4.8–§4.14 几节 + §7 那张表 + §0/§2.2/§2.5 的模型叙述），不需要新协议、不碰代码；
- **不是 P0**：文档不产生业务结果（README 的 P0 定义要求「非预期业务结果」）；
- **但高于普通 P2**：它不是「风格/可维护性」，而是**成节的错误事实**，且已经被当作「已核实」的参照物使用过一次（见下 §6 的教训）。

---

## 6. 教训（为什么这条要写下来）

本计划的文档工作中，**同一句话**被引用两次：一次引用它去断言「告警语不是降级」（按整条日志读不成立），随后该轮复核把文档改成只描述真实行为（`.superpowers/sdd/2026-09-12-architecture-convergence/task-7b-report.md` §3）。这说明该文档的**陈旧段落会被下游当成事实来源**。⇒ 处置它时：

1. **按节核实**（端点是否存在、模型是否存在、文件是否存在），不要按行改名；
2. **能独立修的（乙类）与必须整节重写的（甲类）分开**，并在提交信息/报告里说清哪类是哪种；
3. 每改一节，**降一条残留**（对照 §0 的权威清单），不要留下「半真」的中间态。

---

## 7. 何时重开

1. **有人按该文档对接**（或按它写测试/客户端）—— 触发条件兑现；
2. **该文档的任何一轮修订**：请连甲类一并做端点级重写（否则又是半真）；
3. **ADR-0003 补录旧退场**（见 `pre-plan-retirement-comments.md`）：两者是同一时期的历史叙述债，同一轮做最省；
4. **文档被纳入 CI 校验**（例如端点清单与实际 `include_router` 对账）—— 那时本条应转为自动化门禁，而不是人工清单。
