# 判定面与取数收敛(阶段二·①)设计

**日期**: 2026-09-13
**状态**: 设计定稿待用户审
**分支**: feat/dataset-driven-refactor
**前置**: 阶段一(`bd99740..0ea902e`)已封版 —— 9 条真缺陷 + 两项结构成因收敛,四道门由控制者在最终 HEAD 亲手复跑
**输入**: 8 角度架构评审清单(`.superpowers/sdd/2026-09-12-injectable-path-surface/architecture-review-inventory.md`)、阶段一 spec §7(范围与待裁定)
**范围限定**: 本 spec **只覆盖四簇分解中的 ①**。②③④ 的去向见 §0.3

---

## 0. 背景与本次范围

### 0.1 阶段二从哪来

阶段一的 8 角度评审给出 **11 条真缺陷 + 15 条结构债**。阶段一收掉了 9 条真缺陷(A/B/C/D/F/Y/Z2/Z3/Z4)与两项结构成因,把剩余项连同其裁定项留给阶段二。阶段一 spec §7 列了 **5 项必须先拍板的裁定**,`:204` 明写「阶段二在 H 落点裁定后另立 spec 与计划」。

**5 项已全部拍板**(裁定与代价见 §1)。本 spec 是那次裁定的落地设计。

### 0.2 ① 的内容

判定面单一定义(H)、`/full` 取数所有权(I)、`exists` 属性洞(Z1),外加三项与它们同区的外围:`canvas-render-path-fetch`、`no-retry-after-degradation`、M 剩余半与 N。

### 0.3 ②③④ 的去向(记录,不在本 spec 范围)

| 簇 | 内容 | 状态 |
|---|---|---|
| **② 归一化写回分家** | E:写侧原样透传(裁定已定) | 独立工作流,另立 spec |
| **③ run journal 并发原子性** | `jsonl-append-race`:`_append_jsonl` 并发 append 非原子(Windows `asyncio.to_thread`),撕裂行有物证(`backend/data/runs/2026-09-12.jsonl:6764`),并连带让两条测试误报 | 独立工作流,另立 spec |
| **④ 文档收敛** | G 改 docstring/API 段(裁定已定)+ `platform-api-doc-false-sections` 五节端点级重写 | 独立工作流,另立 spec |

**为什么这样分**:①②③④ 之间无共享文件、无接口依赖。① 的接口改动最重,应单独受一次完整设计审查;②③④ 不受它阻塞。E 与 G 的**裁定**已在 §1 记录,实施时各自 spec 直接引用,不必重新裁定。

---

## 1. 裁定汇总

本节是**裁定的唯一记录**。每条附「代价 / 若不成立会怎样」,便于日后复核。

| # | 裁定 | 代价 / 若错 |
|---|---|---|
| **H** | **(a) 后端算、前端消费**,且实现形态取 **a1**:代理返回**归一化后的端点面与规则展开结果作为数据**,前端仍就地算集合。否决 a2(前端往返取判定结果)与 a3(共享黄金表 + codegen) | a2 会把取数放回判定路径,与阶段一成因①「判定面不耦合网络 I/O」正面冲突,并引入 pending 窗口(阶段一缺陷 C 的同类);a3 引入 codegen 机制,与仓库轻量风格相悖 |
| **I** | 取数**统一到 `plate_client`**;前端 `/full` 缓存从「会话级无 TTL」改为**与后端同量级的 300s TTL** | 放弃 `cache-freshness-divergence.md:§1.1` 的「会话冻结」收益 ⇒ 会话中途会**换面**,必须配 §3.3 的 policy。若不做,则 I 未完成,「编辑器判活 / dispatch 判死」在快照层复发 |
| **Z1** | **收紧 + 写侧拦截,两者都做** | 必须同步修订 `2026-09-12-injectable-path-surface-design.md:105` 的「只放宽、不收紧」**公开承诺**并在发布说明写明哪类路径将新判死(§4.3) |
| **E** | 写侧**原样透传**,只有渲染层消费归一结果 | 服务端 `scenario_composer.py:144` 是 `dict[str, Any]`,**无任何防线** ⇒ 垃圾条目照原样落库,数据质量只由渲染层容忍度承担。此残余须在 ② 的 spec 里显式登记,不得写成「问题已解决」 |
| **G** | **改文档接受现状** | docstring + API 文档改为「`${...}` 类**也**补键;变量为 null 时静默写 null」,「不可兜」收窄为「变量缺失时兜不住(预处理器先抛)」 |
| **换面 policy** | **换面即重判 + 非阻断提示**(§3.3) | 否决「冻结已触条目」:那会在**用户最可能踩中的条目**上重建 I 要消灭的分歧 |
| **N** | **不做**,记为「已评估,不做」并写明理由(§7.2) | 若硬做,等于用「统一」的名义删掉按层提示特性 |

---

## 2. 判定面单一定义(H / a1)

### 2.1 现状:后端已单一定义,前端有重复的半边

**后端已有那个纯函数**,阶段一 P/R 两项就是为它做的:

```python
# src/gimbal-platform/backend/app/services/run_injection.py:115
def injectable_universe(body: Any, declared: Any) -> set[str]:
    """body 叶子 ∪ 其容器前缀 ∪ normalize(declared) ∪ 其前缀 ∪ {"$"}"""
```

声明侧贡献 = `∪_{p ∈ declared} { _template_path(p) } ∪ _container_prefixes(_template_path(p))`(`:135-140`)。它把各级容器前缀 **materialize 成集合成员**,所以 `_path_resolvable` 里不需要前缀扫描 —— 阶段一已把那段扫描作为死代码删除(`:159-164`)。

**前端走的是另一条路**:

```ts
// src/gimbal-platform/frontend/src/utils/assertion-registry.ts:26
export function injectablePathSetOf(bodyLeaves, declarations?): ReadonlySet<string> {
  const out = new Set<string>(['$'])
  for (const p of bodyPathSetOf(bodyLeaves)) out.add(p)
  for (const p of catalogPaths(declarations)) out.add(toTemplatePath(p))
  return out
}
```

它**只放叶子与声明路径,不预展开前缀**,于是 `pathResolvable`(`:39`)必须在 `:47-49` 做前缀扫描。该文件的注释(`:42-46`)亲口确认了这个分叉,并写明「后端那边同形的扫描才可省」。

**「容器前缀」一个概念三份**即由此而来:前端 `pathResolvable` 的内联扫描、后端 `_container_prefixes`,以及 `path-suggest.prefixesOf`。

### 2.2 代理契约

`GET /api/endpoint-catalog/{endpoint_id:path}/full`(`routers/endpoint_catalog.py:41`)**保持 `item` 原样**并**增加**一个字段:

```jsonc
{
  // ...plate 的 item 原样透传(不得裁剪)...
  "declared_surface": ["$", "$.customer", "$.customer.id", "$.customer[*].id", ...]
}
```

- **`item` 必须保留且不得改动**:它还有第二个消费者 —— **候选树 UI**(`buildTree` / `prefillBindings`,给新条目挑字段)。a1 只替换**判定**的输入,不碰渲染候选。
- **`declared_surface` 是扁平字符串集合**,而非「规则 + 原始声明」。理由:这才真正兑现 a1 —— 后端把该端点侧的一切算完(**归一化、容器前缀、模板形态全部展开**),前端在声明半上只剩**纯成员判定**:零归一化、零前缀、零形态转换。
- **降级语义**:`declared_paths_of` 返回 `None`(降级)时,`declared_surface` 取**显式 `null`**(不是缺席、更不得用 `[]` 冒充)。选显式 null 而非缺席:与阶段一 spec §4.3「显式 null 语义」的既有约定对齐,且让「降级」在 JSON 里是**可读的一个值**而不是一个需要靠 `in` 判断的缺口。空目录(`frozenset()`)与降级是两件事(`endpoint_declarations.py:267` 明文):前者给 `["$"]`,后者给 `null`。前端见 `null` 即从严(只认 body 面)。

**后端实现近乎免费**:`declared_paths_of(endpoint_id)` 已返回随取数入缓存的投影(`endpoint_declarations.py:264`,P/R 的产物),故

```python
paths = await declared_paths_of(endpoint_id)
# 降级判定必须在调 injectable_universe 之前 —— 它对 None 与 () 不加区分
# (run_injection.py:132-134 明文),先算就会把降级错报成「只有 $」
declared_surface = None if paths is None else sorted(injectable_universe(None, paths))
```

`injectable_universe` 传入空 body 即退化为「声明半 + `{"$"}`」,正是所需。**不新写投影逻辑。**

### 2.3 前端改造

1. `injectablePathSetOf` 的声明半改为**直接并入 `declared_surface`**(不再调 `catalogPaths` + `toTemplatePath`)。
2. **body 半改为物化前缀**:`bodyPathSetOf` 展平各级容器前缀,与后端 `_container_prefixes` 同构。
3. 完成 1+2 后,`pathResolvable:47-49` 的前缀扫描**成为死代码**,与阶段一在后端删掉的那段**同形同理**,可删。删前必须证明等价(见 §9)。
4. `toTemplatePath` 从**判定路径**上退场(后端已给双形态);它若仍被候选 UI 消费则保留,但不再是判定面的一环。

### 2.4 a1 的诚实边界(**不得写成「H 已解决」**)

可注入面 = `body 半 ∪ declared 半 ∪ {"$"}`。**declared 半归后端**(§2.2),但 **body 半来自草稿态** —— 编辑中的请求体未保存,后端拿不到。

- **死掉的**:「容器前缀」三份里的**两份**(`pathResolvable` 内联扫描、后端 `_container_prefixes` 的声明侧调用),以及 `toTemplatePath` ↔ `_template_path` 的跨语言同构负担。
- **活下来的**:**body 半的叶子 + 容器前缀逻辑仍在 TS**(§2.3 第 2 条)。

因此 ① 交付后的准确表述是:

> **判定面的声明侧已单一定义;body 侧仍是双实现,但两侧共享同一份由后端产出的归一化口径。**

只有选 a2 才能连 body 半一起收,而那与阶段一成因①冲突(§1 已否决)。

**残留风险**:`bodyPathSetOf` 的前缀物化必须与 `_container_prefixes` **同构**。该函数按段边界取前缀(`.` 之后 / `[` 之前,`run_injection.py:112`),含点键与数组下标的行为都要对齐 —— 必须配**跨语言对拍测试**(§9),否则这个新的一致性点会变成下一个漂移点。

---

## 3. 取数所有权(I)

### 3.1 契约取数缓存收敛到 `plate_client`

现状(设计时刻):`routers/endpoint_catalog.py:54-56` 用 `get_client().get(f"/api/endpoint/{endpoint_id}/full")` **自己直取**;`endpoint_declarations` 另有自己的一套取数与缓存 ⇒ 同一进程内两条路径、两份缓存。

改:`plate_client.get_endpoint_full(endpoint_id, *, timeout=None)` 承载这条共享缓存 —— `endpoint_declarations`(判定面 / carry 面)与 `routers/endpoint_catalog.py` 的 `/full` 代理(编辑浏览面)**都经它取** ⇒ 同进程内**同一条缓存条目**,dispatch 与编辑浏览看到同快照。**TTL 不是形参**:它在缓存实例构造时从 `DECLARED_PATHS_TTL_SEC` 冻结(裁定 C21 —— `get_endpoint_full` 按当前 cfg 惰性重建实例,settings 热改即刻生效);`timeout` 才是逐请求形参,缺省取软取上限 `DECLARED_PATHS_TIMEOUT_SEC`(§3.5)。

**收敛的边界(勿读大)**:本阶段做到的是 **dispatch 判定与 `/full` 代理共用同一条缓存条目**,不是把取数收成一条路径。`adaptation_service._plate_full_endpoint`(`carry_store` / `routers/carry.py` 的契约面)与 `routers/endpoint_catalog.py` 的 `field-states/validate` **仍是各自独立的取数路径**,不共享本缓存。

**缓存载体**:复用既有 `TtlLruCache`(`query_view_cache.py`,阶段一已把载荷泛化为 `payload`),缓存的载荷是 **plate 的完整 `item`**(而非仅 declarations)—— 因为代理要透传 `item`,而 `endpoint_declarations` 要从同一份 item 里派生声明与投影。

### 3.2 必须保住阶段一的 D 修复

阶段一的 D(失败保留旧快照)语义**实现在 `endpoint_declarations` 的缓存消费路径上**(设计时刻的落点:`declarations_of` 的过期分支,`endpoint_declarations.py:222` 起;回退窗 3600s,`config.py:99`)。

**取数上移时,回退语义必须一并上移且不被削弱** —— 失败时返回旧快照、仅在**无旧值**时才降级。这是 ① 里**回归风险最高的一处**:移动缓存是机械的,而以「取数失败就报错」的直觉重写这段是错的。任务必须显式携带:回退窗与「无旧值才降级」两条,并保留/搬运既有用例(`stale-snapshot` 系列)。

### 3.3 换面 policy(前端 TTL 300s 的配套)

前端 `useEndpointFull` 的模块级 Map 加 **300s TTL**,与后端同量级。到期重取后:

1. **重算 dead 集合** —— 面变即判定变,两侧永远同面;
2. 因契约更新而变悬空的条目:**灰显 + 一条非阻断提示**(说明是契约更新所致),**勾选状态保留**;
3. 勾选保留的后果交给 **dispatch 侧既有的 dangling skip** 兜底(`run_dispatcher.py` 的 skip + 告警),不新造失败态。

**明确保留不变的**:`useInjectableSurface` 的 `pending` 语义(`neededEndpoints` 只含被条目引用的端点,`:82-95`)不因换面而改 —— 换面是「面变了」,不是「面悬置」,两者不得混为一谈。

### 3.4 连带重开的记录

本裁定触发 `docs/known-issues/platform/declaration-cache/cache-freshness-divergence.md` 的「何时重开」第 2 条(原文:*H 落点裁定:若判定面收为「后端算、前端消费」,前端这份缓存的意义与 TTL 必须重新定*)。该记录状态须从「已接受」改为**已按本 spec 收口**,并追加 `## 修复记录` 段(README 约定:改记录、保留历史、不删文件)。

### 3.5 超时统一

§3.1 的取数统一把 `/full` 代理接到同一条缓存上,而那条取数是**软取**(`DECLARED_PATHS_TIMEOUT_SEC`,3s)⇒ **代理随之受这个上限约束**。这不是为代理另挑一个超时,而是取数统一的**推论**:

- **不能用 30s**(`PLATE_TIMEOUT_SEC`)。30s 恰是阶段一 Z4 修掉的那条线:判定那一路跑在 `/runs` 的**同步**段,30s 会把「前端 axios 超时」与「后端 plate 超时」钉在同一条线上 —— plate 慢时前端报失败、后端其实已建执行,用户重试即**重复执行**。让代理走 30s 等于在代理这条链上推翻 Z4,而代理与判定读的是同一条取数:同一进程内同一次取数不可能有两个上限。
- **也不能「按调用方各传超时」**。该方案已被代码库否决,论证在 `config.py` 的 `DECLARED_PATHS_TIMEOUT_SEC` 注释里:取数在飞收敛(同端点同一个任务),按调用方分别传超时会让上限取决于「谁恰好先建了那个在飞任务」,更不确定。

故 **3s 是推论而非选择**。要认下来的**行为变更与其方向**(候选树):

1. **冷缓存 + 慢 plate** ⇒ 代理 **3s 就失败**(此前等到 30s);
2. **有缓存(含回退窗内的旧快照)** ⇒ 改为**供上一份契约**而不是报错 —— 与 §3.2 保住的 D(stale-while-error)同向,是 fail-open-to-old 在浏览面上的显影。

**本条覆盖谁**:共享 §3.1 那条缓存的**判定面**(`declared_paths_of`)、**carry 面**(`declarations_of`)与**编辑浏览面**(`/full` 代理)。不共享那条缓存的取数路径(见 §3.1「收敛的边界」)**不受本条约束** —— 它们各有各的超时语义。

---

## 4. Z1 `exists` 属性洞

### 4.1 现状与危害

```python
# run_injection.py:169-172
for form in (jsonpath, _template_path(jsonpath)):
    if form in universe:
        return True
return exists(body or {}, jsonpath)
```

`exists` 走 `_eval_nodes`,其 FIELD 分支对**非 dict** 容器改用 `getattr`(`jsonpath.py:381-389`)。实测:`exists({'note':'hello'}, '$.note.replace')` → **True**(拿到绑定的 `replace` 方法)。于是 `$.note.replace` / `.upper` / `.format` 一律"可解析",而前端 `fieldPathsOf` 只产叶子 ⇒ **前端判死**。

UI 路径被前端挡下,但**绕过 UI 的下发**(直接 `POST /runs` 带 `injectionEntryIds`,或脚本/其它客户端)不会被 skip,compose 出 `target='$.request_body.note.replace'`,引擎 `_set_at` 遇非 dict 即 `data={}` ⇒ **把字符串 `note` 整体换成 `{"replace": v}`** —— 请求体被改形。

### 4.2 收紧判据

`exists` 兜底**前**加类型判别:宿主非 dict 时不走属性可达性。**唯一保留项**:空容器宽容 —— `body={"items":[]}` 的 `$.items` 无叶子、无前缀,后端靠 `exists` 判活而前端判死;这是 `run_injection.py:166-168` **明文容许**的既有行为,方向是「少判死」。**收紧时不得把这一类一起收掉**,它与属性洞是两件事。

### 4.3 写侧拦截

`compose_injection_scenario` 物化前判**目标路径的宿主类型**,非 dict 即按**悬空**处置(skip + warn),与既有的 dangling 走同一条路。**不新造失败态**:**不加**新错误码、**不**把整单变 500。

### 4.4 外溢:必须修订一份公开承诺

`docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md:105` 写着:

> 只放宽、不收紧 —— 没有任何路径会变得更严,不会出现「原本能跑的条目突然被判死」

Z1 收紧**直接违反**它。该条是**对用户的公开承诺**(同文件 `:104` 存量条目后果说明),因此:

- 必须**显式修订**该 spec,写明收紧的范围(仅「非 dict 宿主上的属性可达性」);
- 必须在**发布说明**里写明哪一类路径将新判死;
- 修订须由用户过目 —— 改的是已交付 spec 的承诺,不是内部注释。

---

## 5. 渲染路径取数收口(`canvas-render-path-fetch`)

### 5.1 与 known-issue 记载的两处出入

核对实物后更正:

1. **`stepDecls` 是 `function`,不是 computed**(`CaseComposerCanvas.vue:635`)。但它**确实在渲染路径上** —— 被 `:658`(computed 内)、`:1132`、`:1215`、`:1409` 及模板调用。**问题成立,形态记错。**
2. **`currentFull`(`:1591-1596`)里那次取数是冗余的**。

### 5.2 修法:删两行,不新建机制

画布在 `:1603-1605` 已有覆盖**全部** step 端点的预拉:

```ts
watch(stepEndpointIds, (ids) => { for (const id of ids) void ensureEndpointFull(id) }, { immediate: true })
```

因此删掉 `:638`(`stepDecls` 内)与 `:1594`(`currentFull` 内)的 `void ensureEndpointFull(eid)`,`stepDecls` / `currentFull` 变为**纯缓存读**。响应性不受影响:读 `shallowReactive` 容器即建立依赖,与编辑器 `AssertionRegistryEditor.vue:354-356` 的既有做法(裁定 C19)同款。

**唯一风险**:若 `stepDecls` 被传入**不在 `local` 里**的 step,预拉不覆盖它 ⇒ 该 step 的声明树**永远为空**且无告警。故本条必须配**断言预拉覆盖全部调用点**的测试,否则将来新增调用点会静默退化。

---

## 6. 降级重试通道(`no-retry-after-degradation`)

### 6.1 现状

`ensure()` 只在挂载 / 步骤面变化时触发(`useInjectableSurface.ts` 的 `watch(stepEndpointIds, …)`)。失败写 10s 负缓存(`FAILED_RETRY_MS`,`useEndpointFull.ts:52`),而 **10s 后没有任何东西再来触发** ⇒ 整会话判定从严,**契约声明上的条目被误标悬空且不可勾选**,用户不知情。

### 6.2 修法:有界自动退避重试 **+** 失败态可见(两者都要)

只给按钮不够 —— 本条缺陷的本质正是**故障对用户不可见**,用户不会知道自己该点。

1. **有界自动退避**:负缓存窗口到期后,若仍有**被引用端点**处于 failed 且无在飞,自动重试一次;退避**必须有界**(如 10s → 30s → 60s 后停),不得变成自维持重试循环。
2. **定时器落在组合式(取数方)里**,不得落在 computed 里 —— 它属于「取」,与挂载时的 `ensure()` 同类,**不违反读/取分离**(C18)。
3. **失败态可见**:被引用端点 failed 时给出可见信号(与 §3.3 的换面提示复用同一呈现位)。

---

## 7. M 剩余半与 N

### 7.1 M:裁定为**有意差异**,写进文档

a1 后「声明面那半」自动消散。剩下的差异是**服务对象不同**,不是谁写错:

| | 来源 | 服务对象 | 理由 |
|---|---|---|---|
| 画布 `strategyCandidates`(`CaseComposerCanvas.vue:1819-1828`) | `currentAssertable ∪ samplePaths` | **策略路径** | `:1821` 自述「数组下标天然正确」,而真实下标**只有样本能给** |
| 编辑器 `targetCandidates`(`AssertionRegistryEditor.vue:357-363`) | 纯声明面 | **断言目标** | 该页**没有粘样本的入口** |

裁定:**两者都对**,写进文档,**不强行统一**。

**该裁定的前提**(须在文档中一并写明):画布那条候选链是**用户显式触发**的(`onParseSample` 点「解析」才走 `resolveResponsePaths`),**没有把取数塞进渲染路径** —— 与 §5 是两件事。

### 7.2 N:记为「已评估,不做」

清单自评「低风险清理项」,核对实物后**方向是反的**:`JsonPathInput` 是自绘的**分层**选择器(点选补全、**容器补 `.`**、↑↓/Enter/Esc、无候选退化普通输入 —— 按层提示 `81b46d8` 的交付物),而 `el-autocomplete` 是**扁平**补全。换成它**会丢掉按层语义**,那是拿功能换一致。

裁定:**不做**,在 known-issues 记录「已评估,不做」及理由。若需求是**视觉**统一,另开一条只做样式的极小任务,与判定面无关。

---

## 8. 外溢与依赖

| # | 外溢项 | 归属 | 处理 |
|---|---|---|---|
| 1 | `2026-09-12-injectable-path-surface-design.md:105` 的「只放宽不收紧」承诺 | **另一份已交付 spec** | 本 spec 的 Z1(§4.4)要求修订;须用户过目 |
| 2 | `cache-freshness-divergence.md` 状态由「已接受」改「已收口」+ 补 `## 修复记录` | known-issues | §3.4 |
| 3 | `canvas-render-path-fetch.md` 的两处记载更正 | known-issues | §5.1,按 README 约定改记录不删 |
| 4 | `no-retry-after-degradation.md` 补 `## 修复记录` | known-issues | §6 |
| 5 | E 的服务端无防线残余 | **② 的 spec** | §1 表格 E 行 |

**known-issues README 索引行须同步更新**(阶段一遗留过一处「登记簿滞后」,见 `platform-api-doc-false-sections` 的记录,本次不得重犯)。

---

## 9. 验收要点

- **H/a1**:同一端点在编辑器与 dispatch 侧得到**同一判定**(以对拍用例断言);`pathResolvable:47-49` 的前缀扫描删除后,**既有全部用例仍绿**(等价性证明);`bodyPathSetOf` 的前缀物化与 `_container_prefixes` **跨语言对拍**(含点键 `$.a.b` 之于 `{"a":{"b.c":1}}`、数组下标 `$.tags[9]` 之于 `{"tags":["a","b"]}`);
- **I**:同一进程内 dispatch 与代理**命中同一份缓存**(以请求计数断言 plate 只被打一次);**D 不回退** —— 过期 + 刷新失败时旧快照仍服务(既有 `stale-snapshot` 系列必须仍绿);
- **换面 policy**:契约版本变化后 dead 集合**重算**、悬空条目标灰显 + 提示、**勾选保留**;`pending` 语义不因换面改变;
- **Z1**:`$.note.replace` 类路径**不再判活**;**空容器宽容不变**(`body={"items":[]}` 的 `$.items` 仍判活);绕过 UI 的下发被写侧按悬空 skip,**不 500、不新错误码**;
- **canvas**:`stepDecls` / `currentFull` 内零取数(以 grep + 调用计数断言);**预拉覆盖面**有测试钉住;
- **no-retry**:退避**有界**(以调用计数断言不再增长);失败态**可见**;
- **四道门**:后端全量 / 前端全量 / `vue-tsc` 零错误 / plate+执行核零改动,**均不得退步**;
- 每条修复配**证伪证据**(改坏 → 红 → 还原,哈希校验)。

---

## 10. 任务切分建议(供 writing-plans)

| # | 任务 | 层 | 依赖 |
|---|---|---|---|
| T1 | `plate_client.get_endpoint_full(eid, *, timeout=…)` 统一取数(TTL 不是形参,见 §3.1;缓存载荷 = 完整 item);`endpoint_declarations` 改为消费它,**回退窗与「无旧值才降级」一并搬运**(保 D) | 后端 | — |
| T2 | 代理返回 `declared_surface`(复用 `declared_paths_of` + `injectable_universe`),`item` 原样保留;降级时缺席而非 `[]` | 后端 | T1 |
| T3 | 前端消费 `declared_surface`;`bodyPathSetOf` 物化前缀;删 `pathResolvable` 前缀扫描;配跨语言对拍 | 前端 | T2 |
| T4 | `useEndpointFull` 加 300s TTL + 换面 policy(重判 / 灰显 / 非阻断提示 / 勾选保留) | 前端 | T3 |
| T5 | Z1:收紧 `exists`(保空容器宽容)+ 写侧按悬空拦截 | 后端 | — |
| T6 | `canvas-render-path-fetch`:删两处取数 + 预拉覆盖面测试 | 前端 | T4 |
| T7 | `no-retry`:有界退避重试 + 失败态可见 | 前端 | T4 |
| T8 | 文档:M/N 裁定、known-issues 四条记录 + README 索引、可注入面 spec `:105` 修订稿 | 文档 | T1-T7 |
| T9 | 全量回归 + 四道门收口 | 全 | T1-T8 |

---

## 11. 全局约束(沿阶段一,逐条仍生效)

- **P8 名字不得跑在实物前面**:§2.4 已给出 ① 交付后的**准确表述**,文档与提交信息不得写成「H 已解决」。
- **§5 禁止用真值合并有意义但 falsy 的值**:`None`/`[]`/`""`/`0`/`False` 不得被 `or` 抹平;例外须注释说明等价性。本 spec 的 §2.2(降级 vs 空目录)、§3.2(无旧值才降级)、§6 均受此约束。
- **ADR-0003**:退场知识只在该 ADR;代码注释只描述**当前**行为,不写历史对照。本 spec 涉及的退场(前端声明半归一化、`toTemplatePath` 退出判定路径、`pathResolvable` 前缀扫描)须在 T8 登记 ADR。
- **plate 与执行核零改动**:① 全部改动在 `gimbal-platform` 侧。
- **不 push**:分支保持现状,除非用户明确要求。

---

## 12. 风险与未决

| 风险 | 等级 | 处置 |
|---|---|---|
| T1 移动缓存时削弱 D 的回退语义 | **高** | §3.2 显式约束;T1 必须搬运既有 `stale-snapshot` 用例 |
| `bodyPathSetOf` 前缀物化与后端不同构 | **中** | §2.4;T3 配跨语言对拍 |
| 换面重判打断编辑体验 | 中 | §3.3 非阻断 + 勾选保留;若实测干扰大,再评估「提示 + 手动应用」 |
| 退避重试退化为自维持循环 | 中 | §6.2 有界;以调用计数断言 |
| 删 `pathResolvable` 前缀扫描引入静默判死 | **高** | §9 要求等价性证明 + 既有用例全绿 |
| ③ `jsonl-append-race` 未修期间,后端全量测试的既有两条误报仍在 | 低 | 属 ③ 的范围;本 spec 的验收须**显式区分**「既有误报」与「本次引入的失败」 |
