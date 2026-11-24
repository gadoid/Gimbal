# 阶段二待修：`normalizeRegistry` 把「读侧容忍」写回了服务端（E）

> **模块**：`gimbal-platform/frontend`（断言注册表水化与保存）＋ `gimbal-platform/backend`（写侧形状闸）
> **状态**：**已裁定并落盘**（2026-11-24：隔离区+后端闸；见 §3 顶部裁定行与文末[修复记录](#修复记录)）
> **来源**：`docs/implemented/specs/2026-09-12-architecture-convergence-design.md` §6.3 / §7（E）
> **适用范围**：`assertion_registry` 场景级节的水化入口 → 任意保存路径（入口清单实况勘误见修复记录）。

---

## 0. 现状：同一份数据，两个方向

`normalizeRegistry` 存在的理由是**渲染防御**——`assertion_registry` 来自服务端 `/draft`，是不可信 JSON：

- V2 之前的场景**无** `assertion_registry` 键，后端 pydantic default 补成 `{}`（truthy、无 `entries`），`?? { entries: [] }` 兜不住 ⇒ 直灌会在 `registry.entries.length` 崩渲染；
- 条目里 `junk` / `null` / `7` / `[]` 之类非对象值，模板渲染 `e.id` 先于任何判定就 TypeError；
- `asserts` 缺键或非数组，编辑器详情 `selected.asserts.length` / `v-for` 崩渲染。

（以上三条是 `frontend/src/utils/assertion-registry.ts:107-117` 的 docstring 原文口径。）

它的实现做两件事（`frontend/src/utils/assertion-registry.ts:118-133`）：

```ts
if (typeof e !== 'object' || e === null || Array.isArray(e)) continue     // ① 丢弃非对象条目
entries.push(Array.isArray(entry.asserts) ? entry
  : { ...entry, asserts: [] })                                            // ② 补 asserts: []
```

**读侧容忍到这里为止都正确。问题在于它的返回值被当成了「当前注册表」继续往下走。**

---

## 1. 缺陷：容忍面被当成数据面，原样 PUT 回去

水化的四个入口都是**同一个形状**——把归一结果赋给**可编辑的** `registry.value`：

| 入口 | 位置 |
|---|---|
| 编排器运行面板 | `frontend/src/components/composer/RunPanelHost.vue:128` |
| 断言管理编辑器 | `frontend/src/views/AssertionRegistryEditor.vue:371` |
| 编排器（加载 / 水化重试） | `frontend/src/views/CaseComposer.vue:781`、`:872` |
| 数据页 | `frontend/src/views/CaseDataSetsList.vue:172` |

而 `registry.value` 就是**写侧的载荷**：

- `frontend/src/views/AssertionRegistryEditor.vue:420`
  `await updateScenario(scenarioId, { ...draft.value, assertion_registry: registry.value })`
- `frontend/src/views/CaseComposer.vue:896`（保存草稿的 `ScenarioDraft.assertion_registry`）
- `frontend/src/views/CaseComposer.vue:489`（写进共享 draft store，任何从该 store 保存的路径同样带它）

### 触发条件

1. 存量 `assertion_registry.entries` 里存在**至少一个非对象值**（`null` / 数字 / 字符串 / 数组）。来源：手改 JSON、更早的写入方、或任何非本前端的写入路径；
2. 用户打开上述四个视图中的**任意一个**（水化即丢弃那些条目）；
3. 用户**保存**（编辑器保存 / 编排器保存 / 自动保存 / 从共享 draft store 的任何落盘）。

### 影响

服务端那份注册表里的非对象条目**被永久删除**——不是报错、不是提示，是一次「静默写回」。用户下次打开时数据已经不在，且没有任何痕迹说明它何时消失。

- 区分：`asserts: []` 的补键是**加法**（不改用户语义），不属此列；
- 真正丢数据的是 ①：非对象条目**整条**消失。

这就是 README 对 P0 的定义（丢数据）——spec §6.3 因此写作「P0 候选」。

---

## 2. 优先级：P0（候选）

- **后果属于 P0 类**：静默丢用户数据，且丢在服务端（不是本地视图状态）。
- **触发面窄于典型 P0**：需要「存量数据里真的存在非对象条目」这一前提（正常 UI 写出的条目都是对象）。spec §6.3 因此写作「P0 候选」。
- 结论：**按后果定级 P0**；修法需要 §3 的职责拆分裁定，不能只改一行。

---

## 3. 待裁定

> **裁定已作（2026-11-24，用户拍板）**：结论 = **「隔离键」+ 服务端防线（下方选项 1 的第三分支 + 选项 3），两者都做**——①前端 `normalizeRegistry` 不再丢弃：非对象条目搬显式隔离键 `unrecognized`（不渲染、不执行、保存原样写回），隔离条在断言管理编辑器可见；②后端写侧形状闸 `run_injection.validate_registry_shape`（scenario_store create/PUT 双跑接线，抄 param_slots 同层先例）：`entries` 逐元素 dict 硬闸、`unrecognized` 须数组（元素自由），违约 422 `assertion_registry_invalid`；③告知用户 = 隔离区条（「N 条无法识别的条目已原样保留」），不做保存弹窗。运行面存量行由 dispatch/graph 的 isinstance 过滤兜底（graph 过滤为本批补齐），不回写存量。下方决策清单保留为裁定前的历史；实装见文末[修复记录](#修复记录)。

> 原文见 spec §7：**E `normalizeRegistry` 职责拆分** —— *读侧容忍（渲染防御）与写侧保真（不得静默删用户数据）如何分家。*

留给维护者的决策（**本记录不下结论**）：

1. **分家方式**：读侧继续容忍（渲染不崩），写侧在保存前**逐条比对**「归一前 vs 归一后」并在有差异时显式拦截/告警？还是写侧改为原样透传、只让渲染层消费归一结果？还是把丢弃的非对象条目**搬到一个显式的隔离键**（不删、不可渲染）？
2. **要不要告知用户**：静默丢弃 vs 保存前弹一次「有 N 条无法识别的条目，保存将丢弃」的显式确认；
3. **服务端是否也应有防线**：后端 `app/schemas/scenario_composer.py` 对 `assertion_registry` 的形状容忍到什么程度（现状见 `app/services/run_injection.entry_issues` 的容忍面：非 dict 的 `path` 判 `legacy-entry`，不是丢弃）。若后端落库前就能拒收/隔离这些值，前端这一侧的写回后果会被截断。

**相关的既有事实**（供裁定参考，不是结论）：

- 后端 `entry_issues`（`src/gimbal-platform/backend/app/services/run_injection.py:189-243`）对同一条数据的处置是「判 `legacy-entry` → skip + 告警」——**判死但保留数据**，与前端「丢弃并写回」不同向。两处容忍面「看齐」的说法目前只覆盖**判据形态**，不覆盖**数据去留**。
- `RegistryIssue` 已有的 `legacy-entry` 死因可以复用为「这条读不了」的用户可见信号（前端 `registryIssues`，`frontend/src/utils/assertion-registry.ts:63`）。

---

## 4. 何时重开

1. **用户反馈条目消失**：任何一次「我保存后条目不见了」的复盘；
2. **出现非 UI 写入方**：任何脚本 / 导入 / 迁移工具开始写 `assertion_registry`；
3. **H 落点裁定**（spec §7）：判定面收为单一定义那一轮，注册表的读/写职责必须一并定清；
4. **断言注册表加新字段**：新增字段时归一函数与写侧的耦合面会扩大（今仅 `entries` / `asserts` 两处）。

---

## 修复记录

**2026-11-24 — 裁定落盘（隔离区 + 后端闸；数据零丢失）**

前端（隔离区）：

- `utils/assertion-registry.ts` `normalizeRegistry`：非对象条目不再 `continue` 丢弃 → 搬 `unrecognized` 隔离键（原始值原样保留）；隔离区为空不落键（payload 与旧形状逐字节兼容）。`AssertionRegistry` 类型增 `unrecognized?: unknown[]`。
- 保存路径**零改动**即获得写侧保真：三个保存位（ARE `save()` / `CaseComposer` 两处）本就把 `registry.value` 整体写回，隔离键随容器写回。水化重试合并路径（`CaseComposer` hydrate-retry）显式保留两侧 `unrecognized`（该路径原先全新构造会丢）。
- 断言管理编辑器新增隔离区条（`data-testid="are-quarantine"`）：「隔离 N 条无法识别的条目已原样保留（不参与渲染与执行，保存时写回）」+ 截断 JSON 预览；测试 ARE-8 断言更新、新增 ARE-20（roundtrip：含 junk 打开→保存→junk 仍在 PUT payload）/ ARE-21（无隔离条不渲染、payload 无键）。

后端（写侧闸 + 运行面兜底）：

- `run_injection.validate_registry_shape`：registry 须 dict；`entries` 带键须 list 且逐元素 dict；`unrecognized` 须 list（元素自由）；`entries` 缺键放行（旧客户端回落语义不变）。违约 `ValueError("assertion_registry_invalid: …")`。
- `scenario_store` create/PUT 双跑接线（紧挨 `validate_param_slots`，同层平台侧字段同形）；`routers/scenarios.py` 两处 `value_error_http` 码表 +`"assertion_registry_invalid": 422`（契约快照已收编新码）。
- 运行面存量兜底：`graph_dispatch` 注入条目查找补 `isinstance(e, dict)` 过滤（此前 junk 条目 `e.get` → AttributeError 掀掉编排物化；run_dispatcher 选中段与 runs.py 凭证扫描面原本已有过滤）。存量行不做回写（启动只校验不迁移的同款纪律）；正常 UI 写不出 junk entries，触发面本就极窄。

**入口清单实况勘误**（§1 表 vs 2026-11-24 检出）：`RunPanelHost.vue` 已不存在（重构进 `useRunAssembly.ts:122`）；`CaseDataSetsList.vue` 已不存在；现行四个水化入口 = `useRunAssembly.ts:122`、`AssertionRegistryEditor.vue`（hydrate）、`CaseComposer.vue`（加载 + 水化重试两处）。保存路径现行 = ARE `save()` + `CaseComposer` 两处（本就把 `registry.value` 整体写回）。

重开条件不变（§4）。
