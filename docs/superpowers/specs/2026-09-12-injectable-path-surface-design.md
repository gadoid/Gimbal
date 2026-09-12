# 可注入面:契约声明字段的地址化(spec v3.1)

**日期**: 2026-09-12
**状态**: 设计定稿待用户审
**分支**: feat/dataset-driven-refactor
**修订**: `2026-09-12-assertion-registry-v3-merge-injection-design.md`(spec v3)的 §2 悬空判定面 与 §1 裁定 2「任意字段直补」的成立范围;其余不动

---

## 0. 背景:用户实测发现的不一致

用户在断言管理编辑器里写 jsonpath 时,期望「按层提示该层有哪些字段」,实测**只提示到 form 面的字段**。追查后确认这不是提示层的缺陷,而是**判定层把可注入面定义窄了**。

以用户真实端点 `fin.order_entrust.order_add` 为例(契约 `/full` 的 `request.declarations`):

| 字段状态 | 声明数 | 样例 |
|---|---|---|
| `form` | **7** | `$.bl_no`、`$.action`、`$.status`、`$.create_time`… |
| `collapse` | 0 | (该端点无) |
| `carry` | **118** | `$.customer_id`、`$.client_expand_id`、`$.m_delivery_type`… |

而编辑器给出的候选只有那 7 个 —— 因为当前实现(`fieldPathsOf` / `bodyPathSetOf`)扫的是**该步 `request.body` 里已 materialize 的值**,body 里恰好只有 form 面字段。**125 个声明字段里,118 个 carry 与任何未落 body 的 collapse 字段都不可见,也不可作为注入地址。**

## 1. 事实基础(实测,非推断)

1. **字段状态是契约面的**:`DeclarationEntryView.state: 'form' | 'collapse' | 'carry'`(缺省按 form 解析,fail-closed);步骤里的 `field_states` 只是**覆盖意图**。三面语义:`form` = 表单区可编辑;`collapse` = 折叠区(有值才落 body);`carry` = 运行时由平台整包带入,「值表整包注入零感知」,故**不进请求树**。
2. **carry 值其实可被覆盖**:平台在 compose 阶段把 carry 值写进 **case 文件**的 body(`build_carry_context` → `_compose_scenario(carry_context=…)` → `_write_case_file` → CLI 子进程),而引擎的 Assign 在 **BEFORE_REQUEST** 阶段执行 —— 顺序上**注入条目在 carry 之后**,因此对 carry 字段的偏离**会生效**。
3. **今天被拦住的是判定**:后端 `entry_issues` 的 `path-unresolvable` 与前端 `registryIssues` 同构,判据都是「该 path 是否落在该步 request body 的字段树上」→ carry / 未落 body 的 collapse 路径的条目被判死,dispatch 时**静默跳过**、UI 里显灰。于是「任意字段可偏离」(spec v3 §1 裁定 2)在 carry/collapse 上**从未真正成立**。
4. **声明面的来源现成**:平台已代理 `GET {plate}/api/endpoint/{id}/full`(`app/routers/endpoint_catalog.py`,共用带熔断的 `plate_client`);dispatch 链路**本来就依赖 plate**(convert 走同一客户端),故取声明面不属新增依赖类别。
5. 后端本地**没有**全量声明索引:`scenario_endpoint_refs` 只登记**被引用**字段(该场景 step0 仅 9 行 vs 契约 125 条)。

## 2. 语义定义(本 spec 的核心)

### 2.1 可注入面(每步)

对步骤 `si`:

```
declared(si) = 端点契约 request.declarations 的全部 path(全状态 form/collapse/carry;
               children 递归展平;容器条目自身也是合法地址)
body(si)     = 该步 request.body 现有叶子路径
normalize(p) = 去掉数组实例下标($.items[0].sku → $.items.sku)
prefixes(S)  = S 中每个路径的各级容器前缀(段边界:. 之后 / [ 之前)

injectable(si) = body(si) ∪ prefixes(body(si)) ∪ normalize(declared(si))
                 ∪ prefixes(normalize(declared(si))) ∪ { "$" }
```

**`path-unresolvable` 重定义**:`entry.path.jsonpath` **两种形态都不命中** injectable 时判死 ——

```
resolvable(jp) ⇔  ( jp ∈ injectable )                                   # 实例形态:body 面
               ∨  ( normalize(jp) ∈ injectable )                        # 模板形态:声明面
               ∨  ( ∃ p ∈ injectable: p 以 jp 开头且下一字符是 . 或 [ )     # 容器前缀(v3 §2 规则)
               ∨  ( ∃ p ∈ injectable: p 以 normalize(jp) 开头且下一字符是 . 或 [ )
```

两种形态都试的理由见下;拼写错误仍能被抓到 —— 契约与 body 两边都没有它。

**下标归一的方向性**:契约声明是**模板路径**(无下标);条目路径与 body 都是**实例路径**(带下标)。所以判定必须**两种形态都试** —— 只归一化会把「body 里真实存在的实例路径」误判成死(归一一遍后它反而不在集合里),只按实例匹配则契约声明的模板路径永远命中不了。后端 body 面另有 `jsonpath.exists(body, jp)` 精确兜底;前端 body 集本就含实例路径。

### 2.2 降级(从严,安全方向)

拿不到声明面时(该步无 `endpoint_id` / plate 不可达 / 端点未知),`declared(si)` 视为**空集**:

- 判定退回 body 面 —— 只会**少认**一些地址,**绝不会把不可用的地址误判成可用**;
- 记一条**降级 warning**(同一端点在同一缓存窗口内至多一条,不刷屏);
- 绝不阻塞执行(与 carry 同纪律:增强不是前置条件)。

### 2.3 执行序(要在实现与文档里保持的事实)

```
平台:行值合入 vars → carry 值写入 case body → 落 case 文件
引擎:preprocess 渲染 vars → BEFORE_REQUEST Assign 写 $.request_body.<path> → 发请求
```

⇒ 注入条目对 **form / collapse / carry 三类字段一视同仁地生效**;carry 尤其意味着「偏离覆盖掉平台带入的值」。

## 3. 后端机制

1. **取声明面**:在 §2.5 悬空过滤**之前**,收集被选中条目实际引用到的步骤索引,对有 `endpoint_id` 者并发取 `/full` 的声明面。
2. **缓存**:进程级 `endpoint_id → frozenset[str]`(declared paths);**带 TTL(默认 300s,可配)**,因为后端进程可能长时间存活,而 plate 发版是运维事件 —— TTL 用来给"快照过期"兜一个上界。不落库、不写场景文档(与前端 `useEndpointFull` 同一条纪律:plate 是结构权威,零持久化)。
   **行为记录 — carry 面取数的缓存化(2026-09-12 取数合并,T3)**:`carry_injection` 原本**每次 dispatch 现取**契约,取数合并进本模块的共享缓存后,**carry 面的契约取数也从「每 dispatch 现取」变为「进程缓存 + TTL 300s」**。影响:plate 在**会话中途发版**时,carry 面最多**滞后一个 TTL** 才更新;其间 carry 按**旧**契约面注入。性质:**有界、可配**(`DECLARED_PATHS_TTL_SEC`,`core/config.py`),且比前端那份「会话级、无 TTL」的同类缓存(`useEndpointFull` 的模块级 `Map`)**更严**。
   **共用边界**(勿把本模块读作「唯一 `/full` 取数路径」):本缓存只收敛**两个**消费者 —— `declared_paths_of`(dispatch 悬空判定面)与 `declarations_of`(`carry_injection.build_carry_context` 的 carry 面);`adaptation_service._plate_full_endpoint`(其结果被 `routers/carry.py` / `carry_store.py` 当 declarations 读)与 `routers/endpoint_catalog.py` 各有**自己的**取数,**不共享**本缓存。
3. **`entry_issues` 签名**:增参
   `declared_paths_of: Callable[[int], set[str]]`(缺省 `lambda si: set()` 时行为等于今天);path 判定改为 §2.1 的 `injectable`。
4. **失败与告警**:取数失败 → 空集 + 降级 warning;熔断沿用既有 plate 熔断计数(P6),不新增机制。

## 4. 前端机制

1. **唯一投影 helper**:新增 `injectablePathSetOf(step, declarations)`(纯函数,含 `normalize` 与 `prefixes`),取代四处各自持有的
   `bodyPathSetOf(fieldPathsOf(step))`:
   - `views/AssertionRegistryEditor.vue`(悬空判定)
   - `views/CaseComposer.vue`(`deadEntryIds`)
   - `components/composer/RunPanelHost.vue`(同款)
   - `views/CaseDataSetsList.vue`(同款)
   终审已确认这四处本是「一份实现 + 四层薄接线」,本次只改**一处实现**,不新增分叉。
2. **提示层(用户最初诉求)**:请求侧候选改为 `injectable(si)`,并按契约 `state` 标注 **form / collapse / carry**;carry 条目附一句解释(「默认由平台从上游带入,注入条目会覆盖它」)。选择器仍**只做提示不阻断**;无声明面时退化为今天的 body 候选。
3. **响应侧 target 不受影响**:只认契约 `assertable` 面(已交付的 jsonpath 按层提示)。

## 5. 影响与风险

1. **存量条目由「死」转「活」(用户已确认接受)**:原先锚在 carry / 未落 body 的 collapse 上、被判悬空而在 dispatch 时静默跳过的条目,**升级后会真正执行**,其断言也可能因此失败 —— 老场景的执行结果会变化。这是放宽的必然结果,须在 spec 与发布说明里显式写明。
2. **只放宽、不收紧**:没有任何路径会变得更严,不会出现「原本能跑的条目突然被判死」。
3. **审计与回放不变**:审计三定位(datasetId + rowIndex + injectionId)与 stem 命名不动。
4. **降级可见**:plate 不可达时判定从严 + 一条 warning,不会静默放宽。

## 6. 边界与协议位(YAGNI,本次不做)

- headers 源(协议位,v1 只 body —— spec v3 §1 裁定 9 不变);
- 把字段状态写回契约 / 平台侧改状态;
- 审计里额外标注「该字段是 carry 面」;
- 给 carry 字段任何特殊执行语义(它与别的字段一样,只是一个可写地址);
- 契约声明面的持久化快照(明确选了 dispatch 取 + 缓存,不做快照表/快照字段)。

## 7. 验收要点(给实施计划)

- **后端纯函数**:`entry_issues` 以注入的 `declared_paths_of` 判定 —— 声明命中的 carry 路径不再 `path-unresolvable`;未声明且 body 无的路径仍判死;下标归一(`$.items[0].sku` 对齐模板 `$.items.sku`)。
- **后端集成**:契约(plate stub)含 carry 声明 → 该 carry 路径的条目**不再被 skip**、真的执行,且**真 stub 服务收到被覆盖的值**(沿用功能检查的 stub 手法:线上 wire 证据)。
- **降级**:plate 不可达 / 无 endpoint_id → 判定退回 body(条目仍判死)+ warning。
- **前端**:四处判定同构(同一 helper);契约声明但 body 无的路径**不再显灰**;提示带 form/collapse/carry 标注。
- **回归**:前端全量 + 后端全量 + `vue-tsc` 零错误;`plate`/执行核零改动。

## 8. 任务切分建议(供 writing-plans)

| # | 任务 | 层 |
|---|---|---|
| T1 | `injectablePathSetOf`(含 normalize/prefixes)+ 纯函数测试 | 前端 |
| T2 | 四处判定接线 + 提示层换源与状态标注 + 用例 | 前端 |
| T3 | 声明面取数:plate 客户端 + 进程缓存(TTL)+ fail-soft + 降级告警 | 后端 |
| T4 | `entry_issues` 判定放宽 + dispatcher §2.5 接线 + 纯函数/集成用例 | 后端 |
| T5 | 真链路验证:carry 字段注入落到 wire(功能检查式) | 全 |
| T6 | 文档(发布说明一句)+ 全量回归收口 | 全 |
