# Plate Release：按版本读取、平台消费与场景适配——设计与实现方案（v4.1）

> 日期：2026-10-10　基线：`feat/plate-s1` @ `87e8a1a`
> 状态：v4.1（2026-10-10 决策轮收口，Codfish）。版本的定义（版本线、修订、已验证修订、生效修订、发布闸门、发版流程）见《Plate 版本模型》（`claude/plate-version-model.md` v1.1），本文只写读取侧、平台消费与适配中心。待定项见 13.2。
> 姊妹文档：《Plate M2：用例 / 框架侧结构反转》（`claude/plate-m2-reversal-design.md` v2.3）。可行性与代码核实：`claude/plate-m2-release-feasibility.md`。
> 关联：`claude/plate-design.md`（7.1、8.2、8.3、9.1、S1.5）；`claude/plate-s1-review.md`；`GIMBAL-待实现功能与路线图-2026-09-28.md`（2.5 E1–E6）。
>
> 修订记录
> - v4.1（2026-10-10）：决策轮收口（Codfish）：L1 定多模式（版本模型 v1.1 2.4）、V5 定 B 环境组表（11、13.1，D-7）；Suite 交集改「可用集合」语义（2.3、6.3；版本模型 4.2/4.4，D-5）；取数视图统一用**生效修订**（4.7，D-9）；「plate 不可用降级读本地构件」正式否决（plate-design 7.1 修订十五删除，D-6）；13.2 的 D1 改号 **R32**（采纳：端点 status / replaced_by，RS4b 前）、D6 改号 **R33**（采纳：forked_from 谱系 + 陈旧清单，RS4a 前）；V1 转已定。
> - v4.0（2026-10-10）：接入版本模型（版本线 + 修订；场景声明已验证修订，执行用生效修订）。适配中心分为跨版本线适配与线内修正，新增保存检查（目标修订试算 + 引用检查 + 直接保存 / 保存为副本）、Suite 整体适配、注入条目与字段状态随 op 改写、跨所有者通知、回滚只作用于最近一次适配。拆除兼容设计：v1 构件读取、binding 派生字段的展示缓存、平台元数据写入定义再剥离、`catalog_versions` 观察期、平台调用 `ref` 可缺省。
> - v3.1（2026-10-10）：撤回用例变更插件；新增结构级适配能力。
> - v3.0（2026-10-10）：三方解耦，场景声明版本。

## 核心能力（已定，Codfish 2026-10-10）

**C1　三方解耦，plate 是结构定义与版本管理的唯一来源。** plate 负责接口、服务、协议的结构定义及其版本。执行器和平台都按「系统名 + 版本」向 plate 取定义：平台用来编排，执行器用来执行。plate 不知道谁在用哪个版本，也不调用其他两方。

**C2　适配中心是下发给全部成员的场景适配工具。** 任何成员都可以选一批自己能编辑的场景，查看适配到目标版本需要的变更，并在适配中心完成。不实现适配插件；能力由适配中心直接提供，覆盖字段增删改、接口变更、一个接口变为多接口请求过程等结构性改造。

**设计原则（Codfish）**：不为兼容现状放弃更好的设计；存在妥协时，宁可重新设计。

---

# 第一部分　设计

## 0. 现状

### 0.1 plate 侧

- 已实现写入侧（S1 批次 B）：发布闸门四项必检、冻结到内容寻址的对象池、manifest、`plate diff`（对象级）。
- 读取侧没有：加载器写死 `snapshot_id = "working"`（`loader.py:311`）；没有 `ref`；构件只写不读。
- 对象文件写成 `{"kind": <类型>, **model_dump()}`（`release.py:97`），Statement 自带的 `kind` 会覆盖类型标记。
- binding → call 投影有两份实现：`_call_projection`（`release.py:54`）与 `_render_call`（`export/gimbal.py:196`）。
- 取数视图（`QueryView`）是端点定义上的注记；`/api/query-views` 只从 working 构建全局索引。

### 0.2 平台侧

适配中心按接口全局管理版本：`catalog_versions` 每接口一行戳（存 shape_hash 与 `/full` 缓存）；`catalog_diff` 拉 plate working 比 shape_hash；`open_batch` 用 `diff_field_specs`（只比请求声明）起草 op，共 11 种：步骤类 renameField / addField / removeField / rebindField / mapValue，数据集类 renameDatasetColumn / mapDatasetValues，全局 renameVar，carry 类 renameCarryPath / addCarryBinding / removeCarryBinding。快照只覆盖 scenario、dataset、carry 三类实体。路由除 `GET /batches?scope=mine` 外全部为 `AdminUser`。

### 0.3 已发现的缺陷

1. 接口地址或方法变更不会同步到场景：`diff_field_specs` 只比请求声明树，零 op 批次直接完成并推进戳。
2. binding → call 投影三份实现（plate 两份 + 前端 `CaseComposerCanvas.vue` 新建步骤时手写）；场景存的 call 与 plate 定义脱钩。
3. 批次完成时重新拉 working 的 `/full` 写戳，戳可能比批次实际适配的形状更新。
4. 路径参数靠改写存储的 path 实现（platform 系统 126 个接口中 67 个带 path 模板）。
5. 平台对 plate 的读取全部指向 working：`/convert`（预览、run_dispatcher、graph_dispatch、integration_runner）、`/full`、取数视图、适配中心、前端直连的目录与默认模板。
6. 适配中心只面向最新形状，只有 admin 能用。
7. 适配中心只能改字段，不能改步骤结构。
8. **适配会让注入的断言静默失效。** `apply_op` 明确不处理 `assertion_registry`（`adaptation_service.py:770` 附近注释）；条目按 `{stepIndex, jsonpath}` 寻址，字段改名或删除后条目悬空，执行时 `filter_injection_entries` 只记 warning 并跳过（`run_dispatcher.py:634`），只有手动的运行预检会显示 `danglingEntryIds`。
9. **取数视图不区分版本。** 平台 `fetch_rows` 读 working 的视图索引，缓存键为 `(view, 凭证)`。

## 1. 目标与非目标

目标：

1. plate 能按修订提供 M1 定义，给出任意两个修订的结构化差异，并计算场景的生效修订。
2. 编排、执行、导出都按场景声明的已验证修订进行；plate 发修订不改变任何场景的执行（版本模型 I-1）。
3. 适配中心对全部成员开放，覆盖跨版本线适配与线内修正、字段级与步骤结构级改造。
4. 场景存储的定义是纯粹的 M2 实例；接口结构只存在于 plate。
5. 修复 0.3 的缺陷 1–9。
6. CLI / Agent 能离线按修订加载 M1 构件（第二阶段，随 task 5）。

非目标：用例侧 M2 的版本管理（见 M2 方案）；plate 的 HTTP 写入；评审界面；环境部署版本的自动探测；用例变更插件。

## 2. 核心模型

### 2.1 三方职责

| 组件 | 职责 | 与版本的关系 |
|---|---|---|
| **plate** | 结构定义与版本管理：按 `系统@版本线#修订` 提供定义；冻结修订；计算差异与生效修订 | 只被查询 |
| **执行器** | 按 M2 结构执行；按场景声明取定义 | 平台模式下，平台入队时把生效修订写入执行副本，plate `/convert` 按其重投影；CLI 模式自己取（第 7 节） |
| **平台** | 按场景声明的修订编排；提示新版本线、定义修正与环境不一致；提供适配中心 | 只提示，不限制 |

服务信息管理（服务别名的地址与分组、凭证、carry 默认值）与版本无关。carry 默认值按「服务 + 字段路径」存放，天然跨版本；字段改名时适配中心给出 carry 缺口提示。

### 2.2 场景的版本声明（R1）

见版本模型第 4 节，要点：

- `meta.plate: {系统: "<line>#<n>" | "working"}`，值为**已验证修订**，只在新建、复制、保存检查通过的保存、适配提交时改变。
- 执行使用**生效修订**：已验证修订所在版本线中最新的、场景用到的接口结构都与已验证修订相同的修订。
- `meta.system` 的每个系统都必须在 `meta.plate` 中声明；`step.endpoint` 的系统前缀必须在 `meta.plate` 中。缺失报 `VERSION_UNDECLARED`。
- 新建场景默认取该系统最新版本线的最新修订（V5 定后，可改为按所选环境声明的版本线）；尚无修订的系统默认 `working`。
- 编排页按**生效修订**加载定义；普通保存时校验通过后，已验证修订更新为当时的生效修订（版本模型 4.1）。
- 多版本并存通过适配时「保存为副本」实现（5.6）。

### 2.3 提示

| 提示 | 触发条件 | 入口 |
|---|---|---|
| 有新版本线 | 场景所在版本线之后存在新的版本线（按 `predecessor_line` 链） | 跨版本线适配 |
| 定义已修正 | 版本线最新修订不在场景的可用集合中（用到的接口结构发生变化） | 线内修正 |
| 仍为预览 | 场景有系统声明为 `working` | 跨版本线适配（试算模式） |
| 环境不一致 | 执行环境声明的版本线与场景的版本线不同（V5 已定，随 RS3 落地） | 执行详情、集成任务 |
| 版本线已退役 | 没有任何环境声明场景所在的版本线（V5 已定，随 RS3 落地） | 陈旧清单 |

### 2.4 接入即可编排（R21）

| 不变量 | 保证方式 |
|---|---|
| I1 目录不空 | 编排页按场景声明的修订加载目录；版本下拉总包含 `working`，首个修订之前也可以编排 |
| I2 新建步骤总用可用定义 | 新建步骤取场景生效修订的定义，与已有步骤同一修订 |
| I3 协议必然可执行 | binding 的 `protocol` 必须出现在执行器自描述快照（`executor_ext.json`）中；对已评审对象阻塞，对草稿告警（版本模型 3.2） |
| I4 服务必然可解析 | 接口引用的 service 在 `gimbal:system` 中声明，或由注册表自动建最小服务定义 |
| I5 构件丢失不致不可用 | 构件随签发入库；working 重载失败时保留旧快照 |

## 3. 构件

版本模型 3.5 定义 manifest 与对象信封。本文补充两点：

- **投影只有一份实现**：`_call_projection` 是唯一的 binding → call 投影；`_render_call` 改为调用它；投影作为对象（信封 `type` = `call`）进对象池。前端与平台后端都不再自行拼 call。
- **构件随签发入库**（R18）：`plate_artifacts/` 不再被 `.gitignore` 排除，签发提交包含新增的对象与 manifest。

## 4. 读取侧

### 4.1 快照装载

| 快照 | 装载方式 | 常驻 |
|---|---|---|
| `working` | 统一加载器全量解析 Markdown | 全量常驻 |
| `<系统>@<line>#<n>` | 首次访问时读 manifest，按 hash 取全部对象并逐个校验，用当前知识侧模型水合，构建完整 `PlateRegistry` | 按修订缓存整个快照，按容量淘汰 |

- 原子重载：新的 working 快照完整构建并校验后才替换；失败时保留旧快照。
- 16 个查询处理函数都经 `_registry(request)`（`http/routes_grammar.py:49`）取注册表，按 `ref` 返回对应快照只改这一处。
- hash 不一致报 `RELEASE_CORRUPT`；知识侧代际不同报 `RELEASE_M2_INCOMPATIBLE`。

### 4.2 `ref`

见版本模型第 7 节：`<line>#<n>`、`<line>`（最新修订）、`working`、缺省为 working。**平台的编排、执行、适配调用不传精确修订时报错**（`REF_REQUIRED`），由接口约束保证；浏览页可以使用 `<line>`。响应信封的 `snapshot` 字段标注所读快照。

### 4.3 版本线、修订与差异

| 接口 | 返回 |
|---|---|
| `GET /api/system/{id}/lines` | 版本线列表（按 `predecessor_line` 排序）：各线的修订数、最新修订 |
| `GET /api/system/{id}/lines/{line}/revisions` | 修订列表：编号、时间、签发人、摘要、`corrections` 摘要 |
| `GET /api/system/{id}/revisions/{rev}` | manifest |
| `GET /api/system/{id}/revisions/{a}/diff/{b}` | 对象级差异；每个变更接口的**变化部位**（`service` / `binding` / `request` / `responses`，以及 path 占位符差异）；请求与响应的字段级差异。`a`、`b` 可以跨版本线，也可以是 `working` |

字段级差异收归 plate（R7），覆盖请求与响应；平台删除 `diff_field_specs`。

### 4.4 生效修订

`POST /api/system/action/resolve`：入参为 `meta.plate` 与场景用到的接口列表；返回每个系统的生效修订，以及「已验证修订之后结构发生变化的接口」列表（即待处理的定义修正）。计算只依赖 manifest 的 `shape_hash`。平台用它决定执行使用的修订（6.3）、编排页加载的修订（6.1）和「定义已修正」提示（2.3）；结果对同一组修订不变，可以缓存。生效修订只在这一处计算。

### 4.5 `/convert`

`/convert` 按场景 `meta.plate` 的原值取修订，**不做解析**。平台在入队时已按 4.4（Suite 按 6.3 的交集）得出生效修订，并写入执行副本的 `meta.plate` 后再调用 `/convert`。对每个带 `step.endpoint` 的步骤：

1. 取该修订中该接口的 call 投影。
2. 合并为最终 call（R4）：**binding 派生字段取投影**（protocol、method、path 模板、timeout、binding headers）；**场景自有字段取存储**（service 引用、user、`path_params`、追加的 headers）。追加 header 与 binding headers 同名时报 `HEADER_CONFLICTS_BINDING`。存储中出现 binding 派生字段时报错（场景定义只存场景自有字段，6.2）。
3. 系统未声明 → `VERSION_UNDECLARED`；修订中没有该接口 → `ENDPOINT_NOT_IN_RELEASE`；修订不存在 → `RELEASE_NOT_FOUND`。

没有 `step.endpoint` 的步骤（手写原始调用）原样使用存储的 call。响应带回实际使用的生效修订表，平台写入 `plate_pins`。

### 4.6 路径参数（R5b）

- 模板属于 binding，随修订版本化。
- 值属于场景：http 协议的 call 增加场景自有字段 `path_params`，值可以是字面量或变量模板。
- 代入由执行器 http 协议适配器完成；缺键报 `PATH_PARAM_MISSING`。平台模式与 CLI 模式共用这一处实现。
- `path_params` 是 http 协议参数（C 类），不是 M2 结构变更。

### 4.7 取数视图按修订

- `/api/query-views` 支持 `ref`，按修订构建视图索引。
- 平台 `fetch_rows` 传入场景的**生效修订**（已定，D-9：取数属编排期行为，与编排页加载的修订一致；视图不影响执行结构，不纳入 shape_hash）；缓存键改为 `(view, 修订, 凭证)`。
- 字段的 `value_source.view` 在同一修订内解析。

### 4.8 投影查询（供编排页展示）

`GET /api/endpoint/{id}/projection?ref=<line>#<n>`：返回该修订中接口的 call 投影。编排页展示 method、path 等只读信息时调用它，不再从场景存储读取。结果不可变，前后端都可以永久缓存。

## 5. 适配中心

### 5.1 定位

| | 现状 | 设计 |
|---|---|---|
| 谁用 | admin | **全部成员**；权限跟随场景编辑权（R22） |
| 怎么发起 | admin 在 plate 变化后开批 | 成员自选场景与目标发起；提示（2.3）提供入口 |
| 能改什么 | 单个步骤内部的字段与值 | 字段级 + 步骤结构级（5.4） |
| 结果 | 推进全局戳 | 改写场景（或生成副本）并更新 `meta.plate` |

流程：**比较 → 影响 → 方案 → 保存检查与提交**，以及提交后的手工修正与回滚。

### 5.2 两类适配

| | 跨版本线适配 | 线内修正 |
|---|---|---|
| 含义 | 被测系统换了版本 | 被测系统没变，plate 修正了定义 |
| 触发 | 用户主动发起；入口为「有新版本线」「仍为预览」 | 「定义已修正」提示 |
| 范围 | 用户选定的场景或 Suite | 平台按 4.4 算出的受影响场景 |
| 比较 | 起点修订 vs 目标版本线的指定修订（缺省为最新） | 场景的已验证修订 vs 版本线最新修订 |
| `meta.plate` | 改为目标版本线的修订 | 改为同一版本线的新修订 |
| 保存方式 | 直接保存 / 保存为副本（5.6） | 只能直接保存 |

起点为 `working` 的场景没有固定基线，不使用差异，只按 5.6 的目标修订试算生成方案。

### 5.3 比较与影响

- **比较**：对每个起点修订调一次差异接口（4.3），合并结果；不选场景时这一页就是「版本差异浏览」。
- **影响**：叠加到所选场景上，逐场景、逐步骤给出需要的变更，分三组：

| 组 | 判定 | 处理 |
|---|---|---|
| 直接切换 | 场景用到的接口结构完全相同，或只有 binding 变化（占位符集合不变） | 只改 `meta.plate`，不改数据；可批量一键完成 |
| 字段级适配 | 请求、响应、占位符或服务有变化 | 起草字段级 op |
| 结构级改造 | 接口在目标修订中已删除，或用户判断需要改步骤结构 | 用户选择改造方式，或放弃适配该场景 |

- **影响面中的其他引用方**（不论所有者）：引用该场景的 Suite、集成任务（模板与持有人实例）、分享引用；场景内的 `assertion_registry` 条目与 `ui.fieldStates`；carry 缺口。

### 5.4 适配能力（R26）

现有 11 种 op 全部沿用。「草案」= 从差异自动起草；「用户指定」= 差异推断不出，由用户给出。

**字段级**

| 变化 | 能力 | 来源 |
|---|---|---|
| 仅 binding，占位符不变 | 无 op，直接切换 | 草案 |
| path 占位符改名 | `renamePathParam`（新增） | 草案 |
| 接口换服务 | `rebindField` | 草案 |
| 请求字段新增 / 删除 | `addField` / `removeField` | 草案 |
| 请求字段改名 | `renameField` | 用户指定（差异只能看到一删一增，由用户配对） |
| 请求字段值域变化 | `mapValue` | 草案给骨架，用户填映射 |
| 数据集列、全局变量 | `renameDatasetColumn` / `mapDatasetValues` / `renameVar` | 用户指定 |
| 响应字段删除或改名 | **评审项**：按 strategy 中 JSONPath 的根段列出受影响的提取与断言，逐项确认（R14） | 草案 |
| 需要计算的值变换 | 不提供 op，提交后在编排页修改（5.7） | — |

**步骤结构级（新增 op）**

| 改造 | op | 内容 |
|---|---|---|
| 接口被另一个接口取代 | `replaceEndpoint` | 步骤改指向目标修订中的另一个接口，可以属于另一个系统（此时同时在 `meta.system`、`meta.plate` 中加入该系统，版本由用户选择）。用户给出字段映射：旧字段 → 新字段，或丢弃；新接口的必填字段列为待填；涉及的响应路径进入评审项 |
| 一个接口变成多接口请求过程 | `splitStep` | 一个步骤就地替换为有序的 N 个步骤。用户为每个新步骤选择接口，并为每个请求字段指定来源：旧步骤的字段值、前序新步骤提取的变量、或新值。步骤间传值以前一步的 extract 加后一步的 `${变量}` 表达，草案生成 extract 骨架。旧步骤的每条 strategy 由用户归属到某个新步骤，缺省归最后一步 |
| 多个接口合并为一个 | `mergeSteps` | `splitStep` 的逆操作，降级时也会用到 |
| 新版本要求新增调用 | `insertStep` | 在指定位置插入一个接口步骤，字段来源规则同 `splitStep` |
| 新版本不再需要某个调用 | `removeStep` | 删除步骤；其他步骤引用它提取的变量时列为评审项 |

**每个 op 在同一事务内一并处理的场景内引用（D7）**

| 引用 | 处理 |
|---|---|
| `assertion_registry` 条目（`{stepIndex, jsonpath}`） | 字段改名、删除改写 `jsonpath`；步骤位置变化改写 `stepIndex`；无法映射的条目列为评审项，未确认前不能提交 |
| `ui.fieldStates`（按步骤位置索引） | 同上 |
| RunScheme 的执行区间 `stepTo` | 步骤位置变化时清空，并在批次页提示「调试区间已重置」。这是调试用参数，不做精确重映射 |
| 引用索引 `scenario_endpoint_refs` | 保存时重建 |

调试断点（执行器按步骤序号生成的 `step-NNN`）在每次启动时传入，不落库，不受影响。数据集通过 `${var}` 绑定，不受步骤位置影响。

### 5.5 方案

- 方案在批次内以草稿编辑，不改动任何场景。字段级 op 按「同一接口、同一变化」聚合，一次编辑作用于所有受影响场景；结构级改造可在一个场景上定好后「应用到同类步骤」，逐个场景确认。
- 方案中的 op 记录作用的场景与步骤，提交时按场景拆开。

### 5.6 保存检查

每个场景提交前执行，逐个提交与批量提交都适用。

**① 目标修订试算（阻断）**，是判断能否提交的唯一依据，差异只作参考：

- 按目标修订调用 `/convert` 校验；
- 逐步骤比对场景存储的请求字段与目标修订的声明：缺少必填字段、多余字段、类型不符；
- `assertion_registry` 与 `ui.fieldStates` 的每个条目能否在目标修订上定位；
- 响应评审项（R14）是否全部确认。

**② 引用检查**：列出引用该场景的 Suite、集成任务、分享引用，区分自己的与他人的。

**③ 选择保存方式**

| 方式 | 效果 |
|---|---|
| 直接保存 | 原场景改为目标修订；有他人引用时通知其所有者（5.9） |
| 保存为副本 | 原场景不动；新建副本，应用方案，`meta.plate` 设为目标修订，记录 `forked_from`；副本同时拷贝 RunScheme（`copy_scenario` 现在只拷贝 payload 与数据集） |

默认推荐规则（跨版本线适配；V5 已定按 B，环境组表落地前「环境」一项暂不参与判断）：
- 有环境仍声明起点版本线（旧版本仍在使用），或场景被他人的 Suite / 集成任务引用，或目标为 `working` → 推荐**保存为副本**；
- 否则推荐**直接保存**。

线内修正固定为直接保存：被测系统版本没变，没有需要保留的旧形态。

### 5.7 提交、手工修正与回滚

- **按场景单事务提交**：写快照（`adaptation_snapshots`）→ 应用该场景的全部 op（含 5.4 的场景内引用）→ 更新 `meta.plate` → 同步引用索引。场景要么完整适配，要么保持原样。
- **提交后手工修正**（R27）：op 表达不了的变更，在提交后用编排页修改。此时场景已是目标修订，目录与定义都按目标修订加载。批次页对每个已提交场景显示试算结果作为待办，通过才算完成。
- **回滚**：只能回滚场景**最近一次**提交的适配（按栈的顺序）；更早的适配须先依次回滚之后的。提交后被修改过的场景，由编辑者确认放弃这些修改后再按快照还原。保存为副本的提交，回滚即删除副本。快照从不删除。

### 5.8 Suite 整体适配

适配范围可以直接选一个 Suite。保存为副本时连同 Suite 一起复制：新 Suite 引用各成员的副本，记录 `forked_from`。直接保存时，Suite 内同一系统的成员须一起提交，否则提示该 Suite 将因版本线不一致而不能执行（R25）。

### 5.9 批次模型、权限、审计与通知

- **`adaptation_batches`**：`kind`（`cross_line` / `correction` / `carry`）、`system`、`from_revisions`（JSON 数组）、`to_revision`、`scope`（场景或 Suite id 列表）、`save_mode`；状态 `draft → committing → completed / rolled_back`。`carry` 类批次沿用 `carry:{service}` 标识，不使用版本字段。
- **`adaptation_ops`**：`payload` 带作用的场景、步骤与 `endpoint_id`。
- **`adaptation_snapshots`**：实体类型在 scenario、dataset、carry 之外，加上「保存为副本」时新建的 RunScheme（回滚时删除）。
- **权限**：创建批次、编辑方案、提交、回滚只要求对相关场景有编辑权，复用 `scenario_store.owned_scenario_ids`、`routers/_ownership.ensure_owner`；批次对创建者与 admin 可见；carry 类批次改团队共享配置，仍限 admin。
- **审计**：场景版本变更记入 `activity_events`，新增 `scenario.version_change`（from / to、批次 id、保存方式）；`audit.py` 中 `adaptation.op.apply` / `adaptation.batch.apply` 只对 carry 类批次保留。
- **通知**：直接保存影响他人的 Suite 或集成任务时，用现有 `notifications.py` 通知其所有者，说明场景从哪个修订改到了哪个修订、哪个 Suite 或任务受影响。

### 5.10 现有机制的去留

| 现有机制 | 处理 |
|---|---|
| `catalog_versions`、`POST /adaptations/catalog/diff`、首见落基线、`_advance_stamp` | 切换窗口内删除 |
| `GET /impact`、`/impact-bulk`、`/impact-summary` | 改造为 5.3 的影响查询 |
| `GET /unindexed-steps`、`/refs-drift` | 保留：引用索引的健康检查 |
| carry 批次与 3 种 carry op | 保留 |
| `diff_field_specs` | 删除，改调 plate 差异接口 |
| `rollback_batch` 的快照与重放 | 保留；判定规则按 5.7 |
| 前端 `AdaptationCenter.vue`、`AdaptationBatchDetail.vue`、工作台 `AdaptationCard.vue` | 重做为 5.1 的流程；工作台卡片改为「我的场景中有待处理提示的数量」 |

## 6. 平台消费

### 6.1 读取点

| 读取点 | 版本 |
|---|---|
| 编排页：接口目录、`/full`、新建步骤、投影展示、取数视图 | 场景的生效修订（4.4） |
| 执行：`run_dispatcher`、`graph_dispatch`、`integration_runner` 的 `/convert` 与执行物化读 `/full` | 生效修订（6.3） |
| 预览与导出（`preview-plate`） | 生效修订；导出文件的 `meta.plate` 写为生效修订（与已验证修订结构相同，可直接被 CLI 执行） |
| 浏览页（服务画像、端点目录） | 页面选择，默认各版本线的最新修订 |
| 适配中心 | 起点与目标修订 |
| 默认模板（新建场景） | working |

执行物化读 `/full` 时，plate 不可用的情况下 carry 注入降级为跳过；版本错误（`RELEASE_NOT_FOUND`、`ENDPOINT_NOT_IN_RELEASE`、`RELEASE_CORRUPT`、`RELEASE_M2_INCOMPATIBLE`）必须让执行失败。前端编排器的接口目录改为经平台后端（`routers/endpoint_catalog.py`）读取。

### 6.2 场景的存储形态

- **定义是纯 M2 实例。** `composer_scenarios.payload.definition` 只含 M2 字段，存储内容即可直接用于 forbid 校验，不再有「提交投影」。
- **接口步骤的 call 只存场景自有字段**：service 引用、user、`path_params`、追加的 headers。method、path 等 binding 派生字段不存储，展示时经 4.8 查询，执行时由 `/convert` 投影。
- **平台元数据不进定义**：`scenarioId`、`updateTime`、所有者等只在数据库行的列上；定义顶层的 `scenarioId`（M2 必填身份字段）在保存时由行写入。
- **编辑器状态放在定义之外**：`field_states` 移到 payload 的同级键 `ui.fieldStates`（按步骤位置索引），与 `orchestration`、`assertion_registry` 并列；`steps[].id` 删除（没有消费方）。
- **原则**：接口结构的任何变更只走 plate 的「变更 → 评审入库 → 签发」流程，平台不保留对接口结构的可写能力（R5）。

### 6.3 执行

- **入队**：调用 4.4 得到各系统的生效修订；Suite 按版本模型 4.4 取所有成员**可用集合**的交集（集合语义，版本模型 4.2/4.4——可用修订不一定是连续区间），交集为空则拒绝并列出需要线内修正的成员；同一系统各成员版本线不一致时拒绝（`SUITE_VERSION_MISMATCH`）。解析结果写入执行副本的 `meta.plate`，`/convert` 按原值取修订（4.5）。
- **预览**：任一系统为 `working` 时为预览执行，不计入入库标准；集成任务拒绝触发。
- **入库标准**：生效修订中场景用到的接口全部已评审，且不是预览（版本模型 4.3）。
- **注入条目**：存在悬空的 `assertion_registry` 条目时，正式执行失败并列出条目；预览执行放行并告警。
- **环境**：执行环境声明的版本线与场景不同时告警（V5 已定按 B，随 RS3 落地）。
- **记录**：执行落 `plate_pins`（生效修订表；预览执行记录 working 快照的来源 commit，否则无法追溯所用定义）与 `m2_hash`。重跑读取场景当前的 `meta.plate`；执行详情同时显示「当时的修订」与「重跑将使用的修订」，不同时提示。
- **趋势**：同一场景的执行趋势在修订或版本线变化处标出切换点。

### 6.4 平台侧缓存

`plate_client` 的缓存键包含修订；修订内容不可变，不设 TTL，只按容量淘汰；working 条目保留 TTL。plate 不可用时执行失败。

### 6.5 导入与导出（R19）

- **导出**：文件带 `meta.plate`（精确修订），可被 CLI 与其他平台实例直接使用。
- **导入**：文件声明的修订存在时，按其 `/convert` 校验后入库；不存在或没有 `meta.plate` 时，由导入人选择修订，按 5.6 的目标修订试算校验。不猜测来源版本。

### 6.6 Suite 的版本一致性（R25）

同一 Suite 内同一系统的版本线必须一致，并在执行时统一到同一修订（6.3）。编辑 Suite 时显示成员的版本分布。

## 7. CLI / Agent 离线加载（第二阶段，随 task 5）

`meta.plate` 是精确修订，离线加载不需要在线查询：读 manifest 与 call 投影（本地缓存或入库的构件），校验 hash，按 4.5 合并后编译。离线时使用已验证修订本身，不计算生效修订。声明为 `working` 的场景必须在线访问 plate 或加载本地源树。

## 8. 过渡与首个修订

1. **前置**：M2 方案步骤 4 完成；S1.5a 校验口子已收（工作区待随 D-0 提交）；step 分支表达力已验证（✅ 2026-10-10，无需改结构，`claude/plate-step-branch-expressiveness.md`）；L1 已定（多模式，版本模型 v1.1 2.4）。
2. **plate 侧**：版本模型落地（RS0）；fin、platform 各自声明首条版本线并发第一个修订。不读取任何旧格式构件。
3. **平台切换**（一次性脚本，默认演练模式，与 M2 步骤 4 同一窗口或紧随其后）：
   - `meta.plate` 回填为各系统首个修订；
   - 接口步骤删除存储的 binding 派生字段，按 binding 模板从存储的 path 中提取 `path_params`（平台库实测为空操作）；
   - `field_states` 移到 `ui.fieldStates`，删除 `steps[].id`，`meta.scenarioId` / `meta.updateTime` 移出定义（M2 方案第 8 节）；
   - 首个修订的接口结构与场景数据不一致的，列清单评审（对比 `catalog_versions.spec_json` 与首个修订）；
   - 消费点切换为按 `meta.plate`，`meta.plate` 设为必填；
   - 删除 `catalog_versions`、`catalog_diff` 与相关路由；删除 plate 的 HTTP 发版动作。
4. **过渡期**（首个修订之前）：平台继续读 working，`meta.plate` 缺省。

## 9. 保留与冷化

- 修订构件永久保留在仓库中；冷化指把不再被引用的修订移出 plate 进程的可装载范围（归档目录），manifest 保留。
- 「仍被引用」：被任一场景（含已归档场景）的 `meta.plate` 引用，或位于这些已验证修订与其版本线最新修订之间（可能成为生效修订），或被未清理的执行记录的 `plate_pins` 引用。
- 交付点只做判定查询（R10）。

## 10. 失败模式

| 情况 | 行为 |
|---|---|
| plate 不可用 | 执行失败，`plate_unavailable` |
| 声明的修订不存在或已冷化 | `RELEASE_NOT_FOUND`；冷化判定排除被引用的修订，正常不会发生 |
| 构件被改写或截断 | `RELEASE_CORRUPT`；从仓库恢复 |
| 知识侧代际与当前不同 | `RELEASE_M2_INCOMPATIBLE` |
| Suite 成员版本线不一致或可用修订无交集 | 拒绝执行，列出原因 |
| 存在悬空注入条目 | 正式执行失败，预览告警 |
| 适配提交时场景正被他人编辑 | 乐观检查，先提交者为准，后者重新生成该场景的方案 |
| 适配提交时场景正在执行 | 正在执行的那次已在入队时解析了修订，不受影响 |
| 结构级改造后场景内引用错位 | 由 op 内的引用改写保证（5.4），保存检查兜底 |

## 11. 数据与存储变更

| 位置 | 变更 |
|---|---|
| plate 源树 | `system.md` frontmatter 加 `line`、`predecessor_line` |
| plate 构件 | 版本模型 3.5 的 manifest 与对象信封；随签发入库 |
| 场景定义 | `meta.plate`（精确修订）；接口步骤去掉 binding 派生字段；平台元数据与 `field_states` 移出；`steps[].id` 删除 |
| `composer_scenarios.payload` | 新增同级键 `ui.fieldStates` |
| `catalog_versions` | 删除 |
| `adaptation_batches` / `adaptation_ops` / `adaptation_snapshots` | 5.9 的字段调整；新 op：`renamePathParam`、`replaceEndpoint`、`splitStep`、`mergeSteps`、`insertStep`、`removeStep`。线上两表为 0 行 |
| `executions` | 加 `plate_pins`、`m2_hash` |
| `activity_events` | 新 kind `scenario.version_change` |
| 执行器 `HttpCallParams` | 增加 `path_params` |
| `environments`（新表）+ `service_aliases` 迁移 | V5 已定按 B（D-7）：`environments` = id、name、description、owner_id、visibility、`lines`（JSON：{系统: 版本线}）；`service_aliases.group_tag` 改为 `environment_id` 外键，不保留双轨，存量 group_tag 值迁移为同名环境；执行环境由运行方案 serviceBindings 选中的服务别名推出，推出多个环境时告警（混合环境）；集成任务经其运行方案得到环境。支撑：环境比对告警、5.6 保存推荐、版本线退役判定、新建场景默认版本线 |

迁移纪律：默认演练、先备份、单事务、可重复执行。

---

# 第二部分　实现方案

全部落在既有包内；V5 若选 B，环境组表需单独评估。

## 12. 实现规格与步骤

### 12.1 plate

| 位置 | 内容 |
|---|---|
| `dialect/models.py`、`release/release.py` | 版本模型第 12 节 |
| `release/` 读取 | `list_lines`、`list_revisions`、`load_manifest`、`load_object`（校验 hash）、`diff(a, b)`（对象级 + 变化部位 + 请求与响应字段级）、`resolve(meta_plate, endpoints)` |
| `loader.py` / `registry/` | 快照抽象：working + 修订快照，按修订缓存；原子重载 |
| `http/` | `ref` 三种写法；版本线、修订、manifest、差异、生效修订、投影查询接口；`/query-views` 支持 `ref`；`/convert` 按 `meta.plate` 原值重投影并拒绝存储中的 binding 派生字段；删除 HTTP 发版动作 |
| `export/gimbal.py` | `_render_call` 改调 `_call_projection` |

错误码：`RELEASE_NOT_FOUND`、`RELEASE_CORRUPT`、`RELEASE_M2_INCOMPATIBLE`、`VERSION_UNDECLARED`、`ENDPOINT_NOT_IN_RELEASE`、`HEADER_CONFLICTS_BINDING`、`REF_REQUIRED`。

### 12.2 平台后端

| 位置 | 内容 |
|---|---|
| `services/plate_client.py` | `resolve`、`convert`、`get_endpoint_full(id, ref)`、`get_projection(id, ref)`、`list_lines`、`diff`；缓存键含修订；删除 `fill_plate_defaults` |
| `services/run_dispatcher.py`、`graph_dispatch.py`、`integration_runner.py` | 生效修订解析与 Suite 交集；预览判定；悬空注入条目使正式执行失败；`plate_pins`；护栏判重投影后的 call |
| `services/query_view_runner.py` | 传入修订；缓存键加修订 |
| `services/adaptation_service.py`、`adaptation_ops.py` | 按第 5 节重写；新增 6 种 op 与场景内引用改写；保存检查；副本（含 RunScheme）；Suite 整体适配；删除 `catalog_diff`、`_advance_stamp`、`diff_field_specs` |
| `routers/adaptations.py` | 权限改为场景编辑权（carry 批次保持 admin）；路由按第 5 节 |
| `routers/endpoint_catalog.py` | 目录、新建步骤、投影查询按修订；版本线与修订列表供下拉 |
| `services/scenario_store.py` | 定义存储为纯 M2（6.2）；保存校验 `meta.plate`；`copy_scenario` 拷贝 RunScheme |
| 提示 | 场景详情与列表返回 2.3 的提示（来自 4.4，按修订组合缓存） |
| `services/activity.py`、`notifications.py` | `scenario.version_change`；跨所有者通知 |
| 迁移 | alembic：`executions` 加列、适配三表调整、删除 `catalog_versions`；环境组表与 `group_tag`→`environment_id` 存量迁移；一次性脚本见第 8 节 |

### 12.3 平台前端

| 位置 | 内容 |
|---|---|
| 编排页基本信息 | 版本下拉（版本线 → 修订，另含 working）；改版本跳转到适配中心 |
| `CaseComposerCanvas.vue`、`CaseComposerCatalog.vue` | 目录与新建步骤按修订读后端；binding 信息经投影查询只读展示（现仅 `CaseComposerCanvas.vue` 一处读取存储的 binding 字段）；`path_params` 编辑组件；`field_states` 读写改到 `ui.fieldStates` |
| 场景列表与详情 | 版本标记与 2.3 的提示 |
| 适配中心 | 比较、影响、方案、保存检查与提交；版本差异浏览；结构级改造编辑界面；Suite 整体适配；陈旧清单 |
| Suite 编辑页 | 成员版本分布与不一致提示 |
| 执行详情与趋势 | 当时修订 / 重跑修订；切换点标记 |

### 12.4 执行器

| 位置 | 内容 |
|---|---|
| `protocols/builtin/http.py` | `HttpCallParams` 增加 `path_params`；发送前代入；缺键报 `PATH_PARAM_MISSING` |
| 其余 | `meta.plate` 由 M2 生成物带入；交付点内只透传 |

### 12.5 步骤与验收门

| 步骤 | 内容 | 验收门 | 体量 |
|---|---|---|---|
| RS0 版本模型（plate 写入） | 版本模型第 12 节全部；构件入库；删除 HTTP 发版 | fin / platform 演练：首条版本线发两个修订（第二个只改评审状态），`corrections` 为空；改一个接口的 binding 再发修订，`corrections` 含该接口；在 main 上为旧版本线发修订被祖先校验拒绝；草稿上的 C 类问题不挡发版并写入 `warnings` | 中 |
| RS1 读取侧 | 修订快照、`ref`、hash 校验、原子重载、版本线与修订列表、差异、生效修订、投影查询、取数视图按修订 | 修改定义后 working 变、修订不变；差异接口对六类变化（仅描述、仅路径、占位符改名、请求增删、响应改名、换服务）给出正确的变化部位；生效修订在「仅评审状态变化」时前进、在「用到的接口结构变化」时停住 | 中 |
| RS2 重投影与路径参数 | `/convert` 按 `meta.plate` 原值取修订、合并规则与错误码；执行器 `path_params` | 同一场景改 `meta.plate` 后 convert 得到对应修订的 path；存储中出现 binding 派生字段时报错；带占位符的 path 代入正确 | 小 |
| RS3 平台切换 | 第 8 节迁移；消费点按 `meta.plate`；编排页版本下拉与投影展示；提示；Suite 交集；悬空注入条目失败；`plate_pins` | 迁移脚本二次演练一致；平台全量测试零回归；浏览器验收：编排带路径参数的接口 → 执行 → 执行详情显示修订；plate 发只改评审状态的修订后，场景自动使用新修订且入库标准满足；发改结构的修订后，场景执行不变并出现「定义已修正」 | 大 |
| RS4a 适配中心：字段级 | 两类适配、比较、影响、方案、保存检查、直接保存 / 副本、手工修正、回滚、通知、成员权限、陈旧清单；注入条目与字段状态改写 | 六类变化各适配一次；响应改名出现评审项且未确认不能提交；字段改名后注入条目随之改写；被他人 Suite 引用时默认推荐副本，直接保存时对方收到通知；回滚只允许最近一次；非 admin 只能适配自己有编辑权的场景 | 大 |
| RS4b 适配中心：结构级 | 5 种结构级 op、场景内引用改写、`stepTo` 清空、应用到同类步骤、Suite 整体适配 | 「接口改名」「一拆二（中间以提取变量传值）」「二合一」「新增前置步骤」「删除步骤」各适配一次：试算通过、执行通过；拆分后注入条目指向正确步骤；回滚后与原场景逐字段一致；Suite 整体保存为副本后新 Suite 可执行 | 大 |
| RS5 冷化判定 | 列出可冷化修订的查询 | 被场景、可能成为生效修订的、或被执行记录引用的修订不出现在清单中 | 小 |

先后关系：RS0–RS2 只动 plate（RS2 另含执行器 `path_params`），可与 M2 方案步骤 0–3 并行；RS3 在 M2 方案步骤 4 之后——L1、V5 均已定（多模式 / B 环境组表），RS0 先按 free + manual 实现，环境组表随 RS3 落地；RS4a 依赖 RS3；RS4b 依赖 RS4a；CLI 离线加载随 task 5。

## 13. 决策记录

### 13.1 已定

| # | 事项 | 来源 |
|---|---|---|
| C1 | 三方解耦，plate 是结构定义与版本管理的唯一来源 | Codfish |
| C2 | 适配中心下发给全部成员；不实现适配插件 | Codfish |
| P | 不为兼容现状放弃更好的设计 | Codfish |
| R1 | 场景显式声明版本，编排、执行、导出都按声明 | Codfish |
| R4 | 重投影合并规则；追加 header 与 binding 同名即报错 | Codfish（随 R5） |
| R5 | 接口结构只走 plate 变更流程，平台不可写；场景只存场景自有字段（6.2） | Codfish |
| R5b | 路径参数：模板归 binding，值归场景，执行器统一代入 | 按建议 |
| R6 | 撤回：不实现用例变更插件 | Codfish |
| R7 | 字段级差异收归 plate，覆盖请求与响应 | 按建议 |
| R9 | 修订的知识侧代际与当前不同时拒读；用例侧 M2 只作溯源 | 纠错 |
| R10 | 冷化本次只做判定查询 | 按建议 |
| R11 | CLI / Agent 离线加载随 task 5 | 按建议 |
| R12 | `working` 即预览：不计入入库标准，集成任务不可用 | 按建议 |
| R14 | 响应字段变化作为评审项，未确认不能提交 | 按建议 |
| R18 | 构件随签发入库 | 按建议 |
| R19 | 导入导出以 `meta.plate` 为契约 | 按建议 |
| R21 | 接入即可编排，I1–I5 | Codfish |
| R22 | 适配权限跟随场景编辑权；carry 批次仍限 admin | Codfish（C2） |
| R25 | Suite 内同一系统版本线一致，执行时统一到同一修订 | 按建议 |
| R28 | 保存检查：目标修订试算为提交的唯一依据；直接保存 / 保存为副本（5.6） | Codfish |
| R29 | 适配提交同步更新 `meta.plate`（5.7） | Codfish |
| R30 | 场景内引用随 op 改写；`stepTo` 清空不重映射（5.4，D7） | Codfish（stepTo 为调试用途） |
| R31 | 拆除兼容设计：v1 构件读取、binding 展示缓存、平台元数据写入定义、`catalog_versions` 观察期、平台调用可缺省 `ref`、执行器 schema 子模块重导出 | Codfish（P） |
| L1 | 版本线标识多模式可配置：`line_scheme`（semver/iteration/date/free + pattern）、`line_source`（manual/service_version），缺省 free + manual；RS0 先按缺省实现 | Codfish（2026-10-10）；版本模型 v1.1 2.4 |
| V5 | 环境按 B：环境组表 `environments`；`service_aliases.group_tag` → `environment_id`，存量迁移为同名环境 | Codfish（2026-10-10，D-7） |
| V1 | 已验证修订 + 生效修订（原 13.2 待定，确认转已定） | Codfish（2026-10-10） |
| R32（原 13.2「D1」改号） | 端点增加 `status` / `replaced_by`（允许列表），沿用 Term 形式（知识侧加法字段）；差异据此自动起草 `replaceEndpoint` / `splitStep` 骨架；RS4b 前落地 | Codfish（2026-10-10） |
| R33（原 13.2「D6」改号） | 按 `forked_from` 显示谱系，陈旧清单提示合并或归档（场景与 Suite 复制底座已在：`suite_copy.py`、`POST /suites/{id}/fork`）；RS4a 前落地 | Codfish（2026-10-10） |

### 13.2 待定

待定仅剩三项。L1、V5、V1 已定（13.1）；原「D1 / D6」改号 R32 / R33 并已定（13.1）——改号以免与执行能力文档的 D1（执行指令，RunOptions）撞号（D-13）。

| # | 事项 | 当前写法 | 说明 |
|---|---|---|---|
| R26 | 第 5.4 节的适配能力清单与交互 | 已按此写入 | 已确认（D-10）：RS4b 前，等字段级适配运行后按真实场景细化 |
| R27 | 提交后在编排页手工修正；回滚确认后还原，只回滚最近一次 | 已按此写入 | — |
| I3 | 协议不可执行：对已评审对象阻塞、对草稿告警 | 已按此写入 | 随版本模型 3.2 |

### 13.3 欠账（非兼容原因，但仍是让步）

| # | 事项 | 处理时点 |
|---|---|---|
| Q12 | 平台 Suite 预检惰性 import 执行器编译器，违反「平台不依赖执行器包」 | task 5：改为调用执行器 server 的校验接口 |
| Q14 | JSONPath 三份实现靠对拍测试保持一致，只能发现漂移、不能消除 | 依赖方向调整时（如 task 5 的 CLI 归一）再定唯一实现 |

## 14. 与 M2 方案的接口

- `meta.plate` 是用例侧 M2 的字段（M11），取值为精确修订或 `working`。
- `step.endpoint`（M3）是重投影、影响分析与结构级改造的锚点，其系统前缀决定取 `meta.plate` 的哪一项。
- 场景定义存储为纯 M2 实例（M2 方案 M4）：平台元数据不进定义，没有提交投影。
- manifest 的 `m2_hash` / `m2_generation` 只作溯源；修订的水合门是知识侧 `m2_version`。
- m2 信息随执行请求发给执行器（M2 方案 5.1）；`meta.plate` 随场景定义下发。
- `Call` 在 M2 中保持开放、`protocol` 必填；`path_params` 是 http 协议参数。
- 首个修订在 M2 方案步骤 4 之后。

## 15. 需要同步修订的既有文档

| 文档 | 位置 | 修订 |
|---|---|---|
| `claude/plate-design.md` | 8.2、8v、8.3、7.1「多版本」、9.1「适配戳」 | 指向《Plate 版本模型》；删除 `YYYY.MM.N`、只冻结 reviewed、最新 release、适配戳的表述 |
| `claude/roadmap-2026-09.md` | 交付第 1、6、7 项 | 第 1 项：导入以 `meta.plate` 为契约；第 6 项：版本模型 + 适配中心成员化与结构级改造；第 7 项：场景版本变更记入活动 |
| `GIMBAL-待实现功能与路线图-2026-09-28.md` | E1–E6 | E1、E5 → 版本模型；E2 → 第 4 节；E3 → `meta.plate` + `plate_pins`；E4 → 撤回，由适配中心承担；E6 → 按修订查询（写入仍走 git） |
| `claude/plate-s1-review.md` | S1.5 触发点 | 标注落点 |

---

## 附录：功能点承接核对

| 来源 | 功能点 | 承接位置 |
|---|---|---|
| 路线图 E1 / E5 | 冻结流程；首个版本冻结时机 | 版本模型；第 8 节 |
| 路线图 E2 | 水合与按版本查询 | 4.1、4.2 |
| 路线图 E3 | 值记录关联版本 | `meta.plate` + `plate_pins` |
| 路线图 E4 | 用例变更插件；批量与惰性 | 插件撤回；批量由适配中心承担；惰性由提示承担 |
| 路线图 E6 | plate 版本支持 | 4.2–4.4；写入不提供 |
| plate-design 7.1 | 快照化、原子重载、`ref` 多版本、call 投影随版本冻结 | 4.1、4.2、第 3 节 |
| S1.5 | 快照、ref、`/convert` 按版本、构件目录可配置、shape_hash 入 manifest、投影内容寻址、两份投影合一、字段级 diff | 第 3、4 节；版本模型 3.5 |
| 缺陷 0.3-1 至 0.3-9 | — | 4.5 + 5.3；第 3 节 + 6.2；5.7；4.6；6.1；5.1、5.9；5.4；5.4 + 6.3；4.7 |
| 已定原则 | 不新增模块 | V5 选 B 时单独评估；其余全部落在既有包 |
| 已定原则 | plate 只被查询 | C1；生效修订由 plate 依据调用方传入的信息计算 |
