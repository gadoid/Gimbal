# 架构收敛(判定面、取数所有权与存储可迁移性)设计

**日期**: 2026-09-12
**状态**: 设计定稿待用户审
**分支**: feat/dataset-driven-refactor
**前置**: v3 断言管理(`cb1a867..24da73e`)、jsonpath 按层提示(`81b46d8`)、可注入面 v3.1(`fc6edb9..96edffe`)已落地并各自经复核
**输入**: 8 角度架构评审清单(`.superpowers/sdd/2026-09-12-injectable-path-surface/architecture-review-inventory.md`)

---

## 0. 背景与两阶段

可注入面 v3.1 交付后的一次架构级评审(正确性 / 移除行为 / 跨文件 / 复用 / 简化 / 效率 / 抽象高度 / 约定 八个角度)给出 **11 条真缺陷 + 15 条结构债/性能/文档**。逐条复盘后,真缺陷收敛到**两个结构成因**:

| 成因 | 表现 |
|---|---|
| **① 判定面(纯函数)被耦合进网络 I/O 与渲染路径** | 四处 dead 判定从 computed/渲染期函数发起 `/full`;失败无负缓存 ⇒ 重试自维持;基线这四处**一个请求都不发** |
| **② 同一判定契约双语言各写一版 + 四视图各接一遍** | 「可注入面」判定 TS/Python 各一份、「容器前缀」概念三份、适配器四份且**同波内已漂移**;parity 只靠两套手写镜像测试 |

用户裁定:**先做阶段一(新引入问题的架构梳理 + 优化),再做阶段二(整体架构设计收敛)**。

**阶段一(本 spec 的主体,可立即实施)**:修掉 9 条真缺陷,并把产生它们的两个结构成因**收敛掉**(而非点修)。
**阶段二(本 spec 只定范围与待裁定项)**:判定面单一定义、`/full` 取数所有权、归一化职责拆分等跨系统收敛。

## 1. 阶段一范围

### 1.1 九条真缺陷(逐条)

| # | 位置 | 修复 |
|---|---|---|
| **A** | `AssertionRegistryEditor.vue` `stateOfPendingPath` | 守卫只挡 falsy,**真值非字符串** `path`(如 `7`)在渲染期抛 TypeError 白屏。修:把"非空字符串"两边界守卫**收敛到 `iterFlat` 一处**(边界一次消毒),删除各投影函数里的重复守卫 |
| **B** | `run_dispatcher._declared_for` | 裸读 `step["api"]["view_hints"]`,缺 `isinstance(api, dict)` 守卫 ⇒ `{"api": "svc"}` 时 AttributeError 逃出 gather → `/runs` 500。修:补守卫(与 `carry_injection._endpoint_id` 同款) |
| **C** | `RunDialog` + 两宿主 | `contractPending` 时 `deadIds` 被**整体掩空** ⇒ 连不依赖契约的死因(step-oob / override-no-match)也失效禁选,窗口内可勾选真悬空条目并下发。修:`deadEntryIds` **按死因分组**返回,pending 时只掩「依赖契约」那组 |
| **D** | `endpoint_declarations` 失败分支 | TTL 到期刷新失败时 `_CACHE.pop()`,**丢掉仍可用的旧快照** ⇒ 同一次 dispatch 里 carry 面清空 + 判定退回 body ⇒ 条目静默 skip。修:**失败保留旧快照**(stale-while-error),仅在无旧值时才降级 |
| **F** | `useEndpointFull.ensureEndpointFull` | 不查 `failed` ⇒ plate 故障时每个渲染趟重发一次 `/full`,失败又 bump 版本号失效同一批 computed(自维持)。修:①判定面**不再在渲染期取数**(改显式预取,见 §2);②失败端点**负缓存 + 短退避** |
| **Y** | `run_dispatcher` `got or frozenset()` | 用真值合并把 `None`(降级)与"查了是空"抹平,而该区分正是 `endpoint_declarations` 存在的意义。修:显式 `is None` 判别,`None` 与空集**分别下传** |
| **Z2** | `run_dispatcher` 索引基数 | 声明面/body/asserts 投影走 `steps_from_payload`(**过滤非 dict 步**),而前端与 `compose_injection_scenario` 按**原始** steps 下标寻址(`carry_injection` docstring 明写「索引契约:原始列表索引」)⇒ 索引错位。修:投影统一走原始列表(或显式建立"过滤后 → 原始"的映射) |
| **Z3** | `stepIndex` 类型同构 | `Number.isInteger` ↔ `isinstance(si, int)` 不同构:JSON `1.0` 前端判整数/后端判 oob;`true` 后端当第 1 步/前端判死。修:**后端接受整数与整数值浮点(`1.0`),显式拒绝 `bool`**(JSON 只有一种数字类型 ⇒ 向前端语义看齐;bool 不是数字 ⇒ 两侧同拒) |
| **Z4** | `run_dispatcher` 同步段 | 新增的 `await gather(declared_paths_of)` 把 `/runs` 响应绑到 `PLATE_TIMEOUT_SEC=30s`,而前端 axios 超时同为 30s ⇒ 用户看到"失败"但后端已建出执行,重试得到**两条重复执行**。修:判定取数改**专用短超时(3s)**并在超时即降级从严 ⇒ 同步等待有界(契约见 §3.3) |

### 1.2 结构收敛(与修复同时完成,不可分离)

- **前端**:四处副本 → **一个 surface composable**(§2.1);`useEndpointFull` 手工版本号协议 → **Vue 原生响应式**(§2.2)。
- **后端**:判定取数 → **有界软取**(§3.3);universe **按 stepIndex 记忆化**(§3.2);缓存**复用既有 `TtlLruCache`**(§3.1)。
- **文档**:按 §6 收敛。

### 1.3 顺带收掉的性能/简化项(同一文件、同一批提交)

- **Q** 前端可注入面集合按 `(stepIndex, 契约版本)` 记忆化(随 §2.1 一并解决);
- **P** 后端 universe 每 entry 重建(随 §3.2 一并解决);`for p in universe` 的前缀扫描经两角度独立验证为**死代码**(前缀已全在集合内),简化之;
- **R** `declared_paths_of` 每次重算投影 → 缓存条目直接存 `(时刻, 原始列表, 投影集合)`(随 §3.1);
- **U** 缓存时间戳取在 `await` **之前** → 改取在成功之后(随 §3.1);
- **T** `steps_from_payload` 在条目循环内重复读取、条目筛选谓词写两遍 → 收成一次(与 Z2 同一处)。

## 2. 前端设计

### 2.1 `useInjectableSurface(steps, entries)`

新增 `src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts`,一处持有并只暴露消费面:

```ts
interface InjectableSurface {
  /** 该步可注入面(按 (stepIndex, 契约版本) 记忆化) */
  pathsOfStep(si: number): ReadonlySet<string>
  /** pending 与落定后的死条目,分死因两组(修 C) */
  dead: ComputedRef<{ contractDependent: string[]; intrinsic: string[] }>
  /** 提示行的字段状态标注(带契约依赖,修 A 的消费面) */
  stateOf(path: string): FieldState | undefined
  /** 契约是否尚未落定 */
  pending: ComputedRef<boolean>
  /** 唯一副作用:对"被条目引用的步骤"预取契约(修 F 的结构成因) */
  ensure(): void
}
```

- **取数时机**:`ensure()` 由宿主在 `onMounted` / `steps` 变化时调用 —— 渲染期**只读缓存**,判定面不再与网络 I/O 耦合。
- **失败策略**:失败端点负缓存 + 短退避;失败期间判定**从严**(只认 body 面,与 §3.3 的后端降级同向)。
- **四处视图只消费**:`AssertionRegistryEditor` / `CaseComposer` / `CaseDataSetsList` / `RunPanelHost` 各自删除 `injectablePathsOfStep` / `assertTargetsOf` / `deadOf` / `contractPending`,改调 composable(消掉 4-5 份副本与其漂移面)。
- **死因分组(修 C 的判据)**:两组**按死因**划分,定义如下 ——
  - `intrinsic` = **不依赖判定面**的死因:`step-oob`(stepIndex 越界/非整数)、`legacy`(无 `path` 的旧条目)、`override-no-match`(无匹配既有断言)。这些在任何面下都死 ⇒ **任何时刻都应禁选**;
  - `contractDependent` = 当前判为 `path-unresolvable` **但契约尚未落定**(`pending`)**或契约取数失败**的条目 —— 它们在契约到位后可能变活 ⇒ `pending` 期间**不禁选、不标悬空**,契约落定后再按实际结果收窄(只删不增,不覆盖用户此后手动勾选)。
  - 契约落定**且取数成功**时:`path-unresolvable` 即为真死,归入 `intrinsic` 一并禁选。
- `RunDialog` 只消费这两组:pending 时禁用 `intrinsic`、放过 `contractDependent`;confirm 前不做二次过滤(禁用态已经表达真死)。

### 2.2 `useEndpointFull`:手工版本号协议退场

- `fullByEndpoint` / `failed` 改 `reactive(new Map())` / `reactive(new Set())` —— Vue 3 原生跟踪 `Map.get` / `Map.has` / `Set.has` 作为依赖;
- 删除手写的 `endpointFullVersion` ref 与**全部 14 处消费者侧 `void endpointFullVersion.value` 语句**(L);
- 失败端点进入负缓存(带短退避窗口),不再每次调用重发(F);
- 保留:会话级缓存、fail-soft 降级与在飞收敛(浏览器侧只是一个 `Map<string, Promise>`;后端的取消安全语义另见 §3.1)。

### 2.3 边界消毒一次(修 A 的根因)

`utils/declarations.ts` 的 `iterFlat` 增加**唯一的**两边界路径守卫(`typeof path === 'string' && path !== ''`),`catalogPaths` / `assertablePaths` / `carryPaths` / `searchCorpus` / `formBindings` / `responseBindings` 的各自守卫随之删除(与后端 `composite_states` 既有的"守卫一次、下游继承"同款深度)。消费方(含 `stateOfPendingPath`)不再自行守卫。

## 3. 后端设计

### 3.1 缓存复用既有 `TtlLruCache` + 失败保留旧值

`app/services/query_view_cache.py` 的 `TtlLruCache` 已核实具备本模块需要的一切:**惰性过期**(读时判 TTL,无后台线程)/ **LRU 容量逐出**(`max_entries`)/ **stale-while-error 回退窗**(`stale_max_window`,`lookup` 的第二个返回值为 `False` 表示"过期但在回退窗内")/ 纪律「错误永不 put、空结果是合法答案可缓存」——与新模块自写的四条约完全相同。

- **载荷泛化(必要的先决改动)**:该类现有条目载荷是 query-view 形状的 `CacheEntry.rows: list[dict]`。把载荷泛化为 `payload`(保留 `truncated` / `fetched_wall` / `fetched_mono`),并机械更新其**唯一**既有消费者 `query_view_runner.py`(4 处 `stale_entry.rows` 等)与其单测 `tests/test_query_view_cache.py`(2 处)。理由:把声明列表塞进名叫 `rows` 的字段,正是本项目反复吃亏的"字段名撒谎";既然裁定收敛为"一套缓存",就要**字面成立**。波及面已量:约 7 处调用 + 该缓存自身的单测守护。
- `endpoint_declarations` 改为持有 `TtlLruCache`(TTL = `DECLARED_PATHS_TTL_SEC`,带 `max_entries` 上界与 `stale_max_window`),从而获得**上界**与**过期即回退**——D 的"失败保留旧快照"与 S 的"无界增长"由既有能力直接解决,而非另写一套。
- **在飞收敛(`asyncio.shield` + 完成回调)不在缓存内**,而是**叠在缓存之上**的一层:它管的是"并发调用收敛为一次 plate 往返",`TtlLruCache` 不管并发。该层连同其取消安全语义保留(它是本模块真正新增的能力)。
- 缓存条目存 `(原始声明列表, 投影 path 集合, 取数墙钟/单调时刻)` —— 投影一次算好复用(R);时刻取在**成功之后**(U)。
- `_WARNED` 加时间老化(不再只在"同 id 后来成功"时才清),避免调用方字符串驱动的无界增长(S)。

### 3.2 判定收口

- **universe 按 stepIndex 记忆化**(P);`_path_resolvable` 的前缀扫描(死代码)删除;
- **索引基数对齐原始 steps**(Z2):声明面 / body / asserts 三个投影共用同一基准,并在 docstring 注明该契约;
- **`stepIndex` 类型**:接受整数与整数值浮点、显式拒绝 `bool`(Z3);
- **`None` 不抹平**(Y):`declared_of` 回调返回 `None` 与空集**分别下传**,由判定侧显式 `is None` 判别;
- 补 `isinstance(api, dict)` 守卫(B);条目筛选与 `steps_all` 只算一次(T)。

### 3.3 有界软取(Z4)

判定取数使用**专用短超时(3s)**(独立于 `PLATE_TIMEOUT_SEC` 的 30s):

- 超时/失败 ⇒ 返回 `None`(降级)⇒ 判定从严(只认 body 面);
- **`/runs` 的同步等待因此有界**(≤3s),不再与前端 axios 的 30s 超时线相撞 ⇒ 不会出现"用户看到失败但执行已建出、重试变两条";
- 该超时**只作用于判定这一路软取**;convert 等既有链路超时不变。

## 4. 存储可迁移性约束(SQLite → PostgreSQL)

### 4.1 不新增持久化状态(设计规则)

判定面与契约缓存**全部在进程内 / 浏览器内**,运行时从 plate 契约派生。⇒ **PG 迁移不需要为它们写任何迁移**,也封闭了"是否落快照表/快照字段"的反复讨论(沿用可注入面 spec §6 的裁定)。

### 4.2 不依赖 JSON 键序

平台 JSON 列使用 SQLAlchemy 通用 `JSON`(SQLite TEXT / PG `JSON`)。PG 的 `JSON` 保留原文,但**未来若改 `JSONB` 会规范化键序与重复键** ⇒ 判定与投影一律基于 **Set**,写入一律 `model_dump`;**禁止**任何"按插入序读回"的假设。

### 4.3 显式 null 语义(与既有约定对齐)

`carry_binding` 模型已明文:「行存在即声明注入,`value=NULL` 注入 JSON null(**显式空**)」。阶段一涉及的判定与缓存一律**显式区分** `None` / `0` / `""` / `[]` / `False`(见 §5)。这条同时是 Y 的修法与跨引擎保护。

### 4.4 多 worker 视角(PG 部署的现实)

PG 部署下后端可能多 worker:`TtlLruCache`、`_WARNED`、在飞收敛**均为每进程一份**(有界、无害)。⇒ 它们**不得**被当作"全局唯一事实"来依赖(spec 明文记录该边界)。前端缓存是每浏览器会话一份,同理。

### 4.5 记录但不在本阶段范围

- `execution.config_json` 写入 `dataSetSelection` 等纯 JSON 值(无键序依赖 ✓);
- `Execution.started_at/finished_at` 是**无时区 naive** `DateTime`(SQLite TEXT ISO ↔ PG `timestamp`)—— 迁移时需统一时区语义,不在阶段一改动面内;
- 审计的 JSONL 文件(`DATA_DIR/runs/*.jsonl`)是否随之入库 —— 独立议题。

## 5. 全仓编码约定:禁止真值合并

**新增编码约定(用户裁定,全仓生效)**:

> 禁止用真值(falsy)判断合并**有意义但 falsy** 的值。`None` / `0` / `""` / `[]` / `False` 必须**显式判别**(`is None`、`== 0`、`len(x) == 0`),不得写成 `x or default` / `if x:`。

- 依据:本仓库已有同类约定(`carry_binding` 的 NULL≠空);且它是跨存储引擎最容易**静默改语义**的一处(§4.3)。
- 落地:阶段一把 Y 从"点修"改为"按此约定重写该处";并在 spec 立规,后续代码评审以此为准。
- 例外:`or` 仅可用于"双方同为该类型的缺省"场景,且必须能一眼看出 falsy 等价(例如 `cache.get(k) or {}` 当且仅当空 dict 与缺失同义时)—— 需要在注释里写明该等价性。

## 6. 文档收敛

| # | 文档 | 动作 |
|---|---|---|
| 6.1 | `docs/PLATFORM-SCENARIO-COMPOSER-API.md`(681 行,平台唯一 API 文档) | 只动会变假的节:§2.6 `RunRequest` 补 `dataSetSelection` / `injectionEntryIds` 与"两键同发本键优先";§4.18 `POST /api/runs` 补交叉公式、409 `row_index_out_of_range`、**有界软取与降级从严**、悬空 skip 的可见性;§5 持久化设计补 §4.1/§4.2/§4.3 三约束;**新增一节**「断言条目与可注入面」(三元组 / 可注入面定义 / 悬空三检 / `/endpoint-catalog/{id}/full` 代理职责) |
| 6.2 | `docs/adr/0003-retired-features-log.md` | 按其"退场知识唯一归宿"约定,为本阶段每处**退场实现**加行(候选:`useEndpointFull` 手工版本号协议、前端四处步骤面副本、`bodyPathSetOf`(退场后仅剩自测消费)、`endpoint_declarations._CACHE`);并清理代码中承载历史叙述的注释 |
| 6.3 | `docs/known-issues/` | 按 README 约定(一文件一主题、P0/P1/P2、修复时加「## 修复记录」不删文件)建记录:**阶段二待修**(Z1 `exists` 属性洞[P0 候选]、E `normalizeRegistry` 归一化写回[P0 候选]、G `${...}` 补键[P1])与**已接受局限**(前后端缓存新鲜度分歧、轻量页新增 `/full` 取数、`[*]` 归一无覆盖、声明面模板粒度) |
| 6.4 | v3.1 spec 头部 | 加一行修订标注指向本 spec(项目既定惯例) |
| 6.5 | `docs/architecture.md` / NEIGHBOR.md | **不改**,并写明理由:前者是**引擎**架构(平台侧不在其范围);后者约定未落地(全仓仅 1 份且在零改动区)。两条作为**决定**记录,避免后人误判为遗漏 |

## 7. 阶段二范围(本 spec 只定范围与待裁定项)

**待裁定(实施阶段二前必须拍板)**:

- **H 判定面单一定义的落点**:(a) 后端算、前端消费 —— `endpoint-catalog` 代理顺带返回解析好的可注入面;(b) 判定整体服务端化 —— 前端只渲染后端返回的 issue 列表;(c) 保持双实现但用**共享黄金表**驱动两侧测试与代码生成。**控制者倾向 (a)**:改动小、保留前端交互、且与 `routers/endpoint_catalog.py` 已是"前端读契约的唯一入口"这一现状契合。
- **E `normalizeRegistry` 职责拆分**:读侧容忍(渲染防御)与写侧保真(不得静默删用户数据)如何分家。
- **G `${...}` 类补键**:改为只对 `$.` 类补键(与 docstring 对齐、恢复旧行为),还是接受"变量存在但为 null 时静默写 null"并改文档。
- **Z1 `exists` 属性洞**:修它意味着**收紧**判定面(与可注入面 spec §5.2「只放宽不收紧」承诺相左)⇒ 需要显式裁定与 spec 修订。
- **I `/full` 取数所有权**:收编到 `plate_client.get_endpoint_full(eid, ttl=…)`(承接仓库既有的「plate_client 拥有 plate 契约知识」原则)。

## 8. 验收要点(阶段一)

- **A**:`path: 7` 的声明不再使编辑器抛错;守卫只在 `iterFlat` 一处(删除重复);
- **B**:`{"api": "svc"}` 的 step + 锚在其上的条目 → `/runs` **不再 500**;
- **C**:`pending` 期内 step-oob / legacy 条目**仍禁选**;依赖契约的死因在落定后按组收窄;
- **D**:TTL 到期且刷新失败 → **旧快照仍服务**该次 dispatch(用例:先成功入缓存 → 桩改失败 → 断言仍按旧面判定);
- **F**:plate 故障时渲染**不再逐趟重发**(用例:失败桩 + 多次触发判定 → 断言请求数有界);
- **Y**:`None` 与空集分别下传(用例:桩返回失败 vs 空目录 → 断言两条路径的判定不同);
- **Z2/Z3/Z4**:索引错位用例(`steps` 混入非 dict)、`1.0`/`true`/`null` 的 stepIndex 用例、以及**`/runs` 同步段有界**(慢桩断言响应上界与超时即从严);
- **结构**:四处视图不再各自定义判定函数(以 grep 断言);`void endpointFullVersion.value` 全仓 0 处;前端集合按 `(stepIndex, 版本)` 记忆化(以调用计数断言);
- **四道门**:后端全量 / 前端全量 / `vue-tsc` 零错误 / plate+执行核零改动,**均不得退步**;
- 每条修复配**证伪证据**(改坏 → 红 → 还原,哈希校验)。

## 9. 任务切分建议(供 writing-plans)

| # | 任务 | 层 | 依赖 |
|---|---|---|---|
| S1 | `iterFlat` 边界消毒一次 + 删除各投影重复守卫(修 A) | 前端 | — |
| S2 | `useEndpointFull` 改 reactive + 负缓存,删 14 处手工依赖(修 F/L) | 前端 | — |
| S3 | `useInjectableSurface` composable + 四视图接线 + 死因分组(修 C、消 K、收 Q) | 前端 | S1,S2 |
| S4 | 后端:`TtlLruCache` 载荷泛化(`rows`→`payload`,机械更新 `query_view_runner` 与其单测)+ `endpoint_declarations` 改持该缓存(旧值保留、投影一并缓存、时刻取在成功后、告警老化)(修 D/S/R/U) | 后端 | — |
| S5 | 后端:判定收口(记忆化、索引基数、类型同构、None 不抹平、守卫、死代码)(修 B/Y/Z2/Z3/P/T) | 后端 | S4 |
| S6 | 后端:判定取数有界软取 3s(修 Z4) | 后端 | S5 |
| S7 | 文档收敛(§6 五项) | 文档 | S1-S6 |
| S8 | 全量回归 + 四道门收口 | 全 | S1-S7 |

阶段二在 **H 落点裁定后**另立 spec 与计划。
