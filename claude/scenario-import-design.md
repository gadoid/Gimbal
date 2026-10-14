# 场景导入(流水线)· 设计方案(v2.3 终稿)

> 日期:2026-10-14　基线:`feat/plate-s1 @ 41a8b5af`
> 状态:**终稿待实施**。**取代 v1.x 信封方案**(信封/告警清单线整体废弃,§10)
> 与流水线评估稿(`scenario-import-pipeline-assessment-2026-10-14.md`)。
> 汇总:两轮方案评审 + 两轮风险问答 + 拍板 P1-P8(§10;P7 为终稿修正:
> registry 丢失语义写实 / 敏感字段禁手填进 carry / 认证引用栏前移 /
> plate 调用出事务 / 复用判定路径级规则 / 确认界面只读;P8 为导出收口:
> 统一单一导出入口,「可导入/可执行」双入口废除)。所有代码事实均经本仓
> 复核,标注出处;实施者无需回读对话即可动工。
> 方案形状:``解析文件 → 析出分析(按服务键) → 用户确认映射 → 一次性落库``。

## 0. 口径一览

| 项 | 口径 |
|---|---|
| 导出 | **可执行形态**(现有 `preview-plate` 产物,Gimbal 可直接执行);`/export` 对齐;不做信封、不做 formatVersion |
| 导入终态 | **首次创建态**:orchestration / registry / ui 不携带。**registry(偏离注入条目)不进 /convert、不随文件走,导入即丢失**——偏离注入在**执行时**按方案 injectionEntryIds 经 compose_injection_scenario 注入,preview_plate 全程不处理 registry;故只在不选注入条目的方案下行为等价,源场景靠注入条目跑的变体不可复现(首建态口径接受) |
| 导入语义 | **导入 = 新建**(P3):执行导入即与原场景无关,导入人全权维护——含凭证时效、carry 值轮换;不做快照时效告警 |
| 凭证 | **导入后由导入人自配**(P2,同日修正;导入时可配的只有 credentialAlias 下拉,其余自配都在导入后):`config.users` 清空落库(认证缺口前移确认界面,见"提示"行);**carry 面敏感字段禁止手填**(carry 列 Text 明文且 `GET /carry/bindings` 对 CurrentUser 开放),只能留空——留空即保留字面值(P5);认证凭证一律走 `credential_alias` / 导入人凭证池(它服务 `${auth.*}` 账号解析,不为 body carry 字段供值,两件事不混);非敏感 carry 值照文件值写入,**确认界面只读展示**(P7-⑥,无导入时改值) |
| 资源匹配 | 按**服务键析出映射**:本机解析值与文件完全一致 → 复用;本机存在但值不一致 → 映射到本机(本机为准);本机不存在 → 新建别名 |
| 字面值清除 | **硬不变量「有接管者才清除」**(P5,§3.3):body 字面值与 `config.services` URL 仅在本地有实际接管者时清除,否则一律保留——防静默丢值 |
| 提示 | **不做导入告警清单**(缺服务/working 声明等取消);预检只出 ①阻塞性错误 ②映射建议 ③**认证引用栏**——config.users 清空造成的 `${auth.*}` 缺口是导入决策自身的产物,不是环境未配置,必须前移到确认界面展示,不后移 run_precheck;导入成功 toast 引导先跑执行预检 |
| ID 冲突 | `idMode: keep`(默认,409)/ `new`(newId 回传,服务端校验格式+唯一性,重铸 definition 顶层+meta,P4);409 后前端自动重预检 |
| 权限 | `MemberUser`(P1):precheck/import 均收紧,含改造现有 R19 `/scenarios/import`;`user` 角色前端隐藏入口,后端 403 为权威 |
| 事务 | **单事务落库**(T1/T2 改造,§6):建别名+写 carry+改写 definition+建场景一次提交;审计主事务后写;**plate 调用全部在事务外**(P7-④) |
| plate 不可达 | 502(析出分析与别名登记都依赖目录可达,与导入本身口径一致) |

## 1. 文件格式 = 可执行形态

- 无信封。文件 = `preview-plate` 的 converted 产物;**只收 JSON**,选到前端
  导出的 YAML 文件给明确提示(`invalid_file`)。
- 内容事实(代码核实,`routers/scenarios.py preview_plate`):
  - carry 值已物化进 step body(**无条件**,spec §4.3 勘误);
  - `config.services` 已由别名 `base_url` 或方案绑定填充(别名 URL 预解析);
  - 带方案导出(overlay)时 `config.users` 含导出人凭证池的**明文账密**
    (处置见 §4:清空);
  - 顶层 `scenarioId` 与 `meta.plate` 保留(Meta 模型含 plate 字段,dump 不剥);
  - binding 派生字段存在,由 `create` 的 `strip_binding_fields` 剥离;
  - orchestration / registry / ui 不在文件中(orchestration 绝不外发;
    registry「引擎不感知,不进 plate convert」——偏离注入条目在**执行时**
    按方案 injectionEntryIds 经 compose_injection_scenario 注入,
    preview_plate 全程不处理 registry,文件里只有 steps 自带的断言)。
- 结构判别不存在也不需要:可执行 ≡ definition 同 schema("overlay 黄金
  等价"是平台设计目标,`export/gimbal.py` M2 步骤 4 后 exclude 清零直接
  dump)——本方案中可执行形态就是**唯一**导入格式,无判别问题。
- **体积上限 5MB**:两个端点收原始 `Request`,`Content-Length` 头预检 +
  限长流式读取,`len()` 复核后自行 `json.loads`——保证超大文件**在解析前**
  被拒(413 `payload_too_large`),不做形式作用。

## 2. 析出的底层模型(别名与 carry 的真实形状)

实施与文案都以此为准(依据:`models/service_alias.py`、`models/carry_binding.py`
模型注释;`services/carry_injection.py`):

**别名登记行是双态**:`owner_user_id` 非空 = 个人默认,空 = 团队共享;
`alias_name` 是主键,**同名全局唯一**(不存在两人各有一个同名别名)。

**base_url:每别名一个,不继承**。别名行上的一列,NULL = 不提供 URL 默认。
URL 解析链:显式绑定 > 场景声明 > `alias.base_url` > 缺口(引擎报错)。

**carry:三层链 + 稀疏覆盖,不是每别名一份拷贝**:

```
精确别名键(fin-service-qa 的绑定) → base 服务键(fin-service 的绑定) → 全局默认
```

- 多个别名指向同一 base 时默认**共享** base 键那套(别名键没写的路径都
  落过去);某别名"改字段" = 在自己键上落绑定,**只分叉被改的路径**,其余
  继续共享——稀疏覆盖语义,合并在 `carry_injection` 一处实现。只有两个
  别名把所有字段都写满不依赖 base 时,才是真正的"两套"。
- **对导入的含义**:新建别名写 carry 只写**接管的字段**,未接管路径自然
  继续命中 base/全局默认——导入不复制整套 carry,天然贴合稀疏模型;
- **"复用"判定按解析后的最终值比较,路径级规则写实**(P7-⑤):比较范围
  = 文件中该服务在 carry 面上的**字面值路径集合**,与按三层链解析后的
  本机值逐条对比。**全部路径有值且相等 → 复用**;本机在某条路径上没有
  值 → 该服务判"映射"(不判"复用"),该路径保留字面值(与 P5/不补值
  一致)。共享底座且值齐全的两个实例互导判"复用",不会误判"值不一致"。

**别名命名强约束**(`service_names.derive_base`,最后一个 `-` 切一刀):
`alias_name` 本身是目录服务名,或 `<目录服务名>-<后缀>`(单层)。源实例
别名(如 `fin-service-qa`)在本机 base 在目录时**可原样登记**,`call.service`
无需改写;两层后缀(`fin-service-qa-2`)不能原样登记,新建一路需换名
(precheck 的 `createNameAvailable` 字段提示)。

## 3. 导入流水线

### 3.1 预检 `POST /scenarios/import/precheck`(纯读,MemberUser)

结论走 200 信封,不抛错(fatal 作为字段返回,让确认对话框能渲染完整判定面):

```jsonc
{
  "blocking": true,                 // 格式错 / convert 失败 / 声明修订缺失
  "formatError": { "code": "invalid_file" },
  "convert": { "ok": false, "errors": ["..."] },
  "metaPlate": { "fin": "1.0#2" },
  "availableRevisions": { "1.0": ["1.0#2", "1.0#5"] },  // 声明缺失时
  "idConflict": true, "suggestedId": "sc-import-a1b2c3",
  "services": [{                    // 析出分析:按服务键
    "serviceKey": "fin-service-qa",
    "suggestion": "reuse|map|create",
    "localAlias": "fin-service-qa",
    "fieldsToAlias": 6,             // 将交由别名 carry 接管的字段数
    "fieldsKeptLiteral": 2,         // 保留字面值的字段数(取值不一致路径等)
    "createNameAvailable": true     // 新建一路:同名可原样登记?
  }],
  "authRefs": [                     // 认证引用栏数据(§3.2):config.users
    { "tag": "admin", "inMyPool": false }   // 清空后 ${auth.*} 的本地可解析性
  ]
}
```

析出分析组装(全部既有函数,零新判定逻辑):

| 步骤 | 来源 |
|---|---|
| 每步 carry 面 | `build_carry_context(db, definition, ui_field_states={})` → `step_fields[i] = {path: 类型}`;**无锚点步骤显式排除**(不沿用执行链降级门控候选集,防把非声明字段误判为 carry);`ext:` 锚点步骤不参与(external 无 plate carry 契约) |
| 字面值 vs 模板 | `${` / `$.` 前缀判定(与 `run_injection._is_context_readable` 同口径) |
| 本机某键 carry 值 | `carry_store.get_bindings` 按链(精确别名 → base → 全局默认)**合并后的最终值**(§2 复用判定的口径) |
| 服务键存在性 | 别名表 `alias_name` 精确 + `service_names.catalog_service_names()`(plate 目录) |
| 同名可登记 | `derive_base` 落回目录(§2 单层后缀约束) |
| convert / 可用修订 | `plate_client.convert`;`availableRevisions` 用 plate 既有 `GET /system/{id}/lines/{line}/revisions`(平台 `plate_client` 补薄包装——`list_lines` 只给线级 count+latest) |
| 认证引用 | `scan_auth_aliases(steps)` ⊕ 导入人 `AuthSession` 凭证池(有/无)——确认界面"认证引用栏"数据源 |

权限:`CurrentUser` 与 import 一致收紧为 `MemberUser`(§0 权限行)。

### 3.2 映射确认界面(前端,MemberUser 入口在场景库 Home)

- 按服务逐行:服务键、建议(复用/映射/新建)、交别名字段数、保留字面值
  字段数;可在"映射到已有 / 新建"间切换。
- **新建一行(P7-⑥:界面是确认单,不是编辑器)**:非敏感字段**只读展示**
  文件值(确认即照此写入 carry);**敏感字段没有输入入口**,显示"保留
  字面值"。要改非敏感值?导入后去 carry 配置页——P3"导入人自行维护"
  的口径,不在导入时开改值口。认证下拉(`credential_alias`)只服务
  `${auth.*}` 账号解析,与 carry 字段无关,两者不混。
- **认证引用栏**(P7-③):列出 `scan_auth_aliases` 扫出的 tag,逐个标注
  "你的凭证池中有 / 没有"——config.users 清空后 `${auth.*}` 的可解析性
  缺口是清空决策自身的产物,必须在这里可见;只展示,不阻塞。数据来自
  precheck 的 `authRefs`(复用现成函数,量小)。
- **新建一路的文案要说清全局副作用**(§7 事实口径):新建别名登记为导入人
  个人默认,但其 base_url 与 carry 绑定**平台全局生效**——其他引用同一
  服务键的场景也会命中这些值。
- ID 区:`idConflict` 时勾选「分配新 ID」(展示 `suggestedId`,确认即回传,
  展示与最终一致)。
- 409 自愈:别名或 ID 撞车 → 自动重新预检刷新建议,无需重选文件。
- **导入成功 toast 引导**:"建议先跑一次执行预检"——告警清单已取消,
  ext: 锚点悬空/URL 缺口等发现点后移到 run_precheck,导入即引导用户
  去那个发现面。
- 本地预拒:选文件后 `JSON.parse` 失败即 toast;超 5MB 本地即拒。

### 3.3 落库 `POST /scenarios/import`(单事务,MemberUser)

Request:`{bundle, idMode?, newId?, mappings: [{serviceKey, decision:
"reuse"|"map"|"create", createName?, credentialAlias?}]}`——**无值覆盖
字段**(P7-⑥:非敏感值照文件、敏感值不进 carry,均无用户改写;要改导入后
走 carry 配置页)。

**plate 调用全部在开事务之前完成**(P7-④):目录查询(derive_base)、
`build_carry_context`、convert 均为 plate 往返,先做完再开本地事务——
事务内只做本地读写,不持锁等网络。

落库前**按确认映射重新计算**(不信任预检快照,本地查询):别名是否仍
存在、新建名是否被占用、本机 carry 值是否变化——失效返回 409
`mapping_stale`,前端自动重预检。落库顺序:

1. 新建别名(`create_alias` 不提交版,§6-T2,`owner_user_id=导入人`——
   个人默认登记;配置面全局生效见 §7)→ 写 carry 绑定(`put_bindings`,
   **只写非敏感路径的文件值;敏感路径不写绑定**——carry 列 Text 明文且
   GET 全员可读,不收密码,对应字面值按 P5 保留在 body)→ 别名挂
   `credential_alias`(如选,只服务 `${auth.*}`);
2. 改写 `call.service`(需换名时);
3. **清除字面值/URL——硬不变量「有接管者才清除」(P5)**:body 的 carry 面
   字面值,仅当该路径在新配置下有实际接管者——新建别名且该路径有值
   (=文件值);复用=值一致;映射到已有且本机该路径有值——才清除,
   **否则保留字面值**。敏感路径因不写绑定,天然保留字面值;
   fieldStates 缺失导致面按 plate 默认态计算、与源场景不同而多算的
   路径,最坏也只是保留原值,不会误删。`config.services` URL 同一不变量:
   本机别名有 `base_url` 才清,否则保留源 URL(可见可改,不静默变 unbound);
4. **`config.users` 清空**(不持久化导出人明文凭证,§4);
5. ID 重铸(`new` 时:回传 newId,校验 `^sc-[a-z0-9-]+$` + 查库唯一性;
   重铸 `definition.scenarioId` 顶层 + meta;文件无容器件,无其他重铸点);
6. 建场景(`scenario_store.create` 不提交版,§6-T1);
7. `commit` → `ensure_default_scheme` 后置(`GET /run-schemes` 有自愈兜底,
   失败不破坏一致性)→ 审计后置(`alias.write` / `carry.write` / 场景创建,
   best-effort 语义与现行一致)。

冲突(别名名 / scenarioId / newId 被占)→ **整体回滚**(场景、别名、carry
均无残留)→ 409 → 前端自动重预检。

处理范围口径:只处理字面值;步骤间取值不一致的路径保留字面值;映射到已有
别名时别名缺值的路径保留字面值(**不向已有别名补值**——本机为准)。

**错误码表**:

| code | http | 场景 |
|---|---|---|
| `meta_plate_required` / `convert_rejected` | 422 | 现状语义 |
| `plate_unavailable` | 502 | plate 不可达(含析出/登记依赖) |
| `meta_plate_invalid_ref` | 422 | message 附本机可用修订集 |
| `scenario_id_exists` | 409 | keep 撞车 / newId 被占 |
| `alias_name_taken` | 409 | 新建别名名被占(落库时) |
| `mapping_stale` | 409 | 落库重算发现映射失效(别名消失/值变化)→ 前端重预检 |
| `payload_too_large` | 413 | >5MB(原始 Request,解析前拦截) |
| `invalid_file` | 422 | 非 JSON(YAML 提示)/ 结构不可解析 |

## 4. 凭证口径(P2,2026-10-14 拍板;同日修正)

内部系统,携带在技术上可接受;**产品口径取"清空 + 导入人自配"**:

- `config.users` 清空落库——导出人明文凭证**不持久化**进场景表,与平台
  既有秘密纪律对齐(执行链"明文只在内存值对象、绝不写回 ORM 行"、case
  目录明文凭证不等周期清扫)。**清空的代价写实**(P7-③):文件里的
  config.users 混着源场景内置认证基座(`_built_in_users`,内置认证以场景
  定义为唯一可信源;查询视图身份也取它的第一个键)与 overlay 注入的
  导出人凭证池账号,两者形状无判别特征、无法区分,只能一并清掉——步骤
  引用的 `${auth.<tag>}` 凡导入人凭证池没有同名的,执行时解析不到。
  这个缺口是清空决策自身的产物,不是环境未配置,故**前移到确认界面
  "认证引用栏"**(§3.2),不后移 run_precheck。
- **carry 面敏感字段禁止手填**(P7-②):`carry_service_bindings.value`
  是 Text 明文、无加密,`GET /carry/bindings` 对 CurrentUser 开放——手填
  密码等于把导入人的明文密码放进全员可读的表,与本节"不持久化明文"
  的理由正好相反。故敏感字段**只能留空**,留空即保留字面值(P5 不变量的
  直接应用);认证凭证一律走 `credential_alias` / 导入人凭证池——它提供
  `${auth.*}` 账号,不为 body carry 字段供值。当前 carry 面基本无密码类
  字段,不留输入入口的代价很小。
- 非敏感 carry 值照文件值写入(内部系统便利,配一次就好);**确认界面
  只读展示,不提供导入时改值**(P7-⑥)——要改值导入后走 carry 配置页,
  与 P3"导入人自行维护"同口径。
- 导入 = 新建:后续凭证过期、值轮换由导入人自行维护,系统不做时效告警。
- **敏感字段识别的残余(拍板接受)**:识别规则在面无 `ui_kind` 类型信息时
  退化为命名启发(password/secret/token/key),漏检残余接受(内网);
  实现时写实识别规则。

## 5. ID 重铸(P4,回归)

`idMode: keep`(默认,现状 409 语义不变)/ `new`(newId 回传 + 服务端校验
格式与唯一性);重铸 `definition.scenarioId` 顶层 + meta;409 自愈(§3.2)。

## 6. 事务改造(T1/T2,关键路径)

| # | 改造 | 要点 |
|---|---|---|
| T1 | `scenario_store.create` 拆不提交版本 | **保留提交包装器给既有调用方**(常规创建/copy/fork/迁移脚本,行为零变化);`IntegrityError → ValueError(scenario_id_exists)` 映射依赖"commit 在 try 内"的 autoflush 结构(store 注释明言),拆分后错误映射责任显式转移给导入调用方 |
| T2 | `service_aliases.create_alias` 拆不提交版本(内部 `db.add + commit` 已核实);`audit.record` 主事务后写(其内部 commit 已核实) | 同理保留包装器 |

量级:**中**——create 是核心写路径,调用方清单和错误映射迁移必须逐一过。

## 7. 系统影响

| 子系统 | 影响 | 级别 |
|---|---|---|
| 场景存储 | T1 拆分(包装器兼容);导入改写 definition(`call.service`/body/`config.services`/`config.users` 清空) | 中 |
| 服务别名 | T2 拆分;导入新建别名(个人默认登记),表增长("值一致即复用"抑制重复)。**事实口径**:登记行双态(个人/共享,同名全局唯一),但 `base_url` 为别名唯一权威、carry 绑定按 `service_name` 无 owner 维度——二者**平台全局生效**,"个人"只是登记归属不是配置隔离 | 中 |
| carry 绑定 | 新建别名时写入(复用 `put_bindings`,无新写入路径);**只写非敏感路径**(表列 Text 明文 + GET 对 CurrentUser 开放,见 §4);**不改已有别名绑定**;写入即全局生效(同上) | 低 |
| 执行链 | **无改动**——映射到已有别名的字段取本机值,执行结果可能与源实例不同("别名为业务真值"口径) | 无 |
| 审计 | `alias.write`/`carry.write`/场景创建,事务后写,资源名快照口径与审计可读性改造一致 | 低 |
| 权限 | `CurrentUser → MemberUser`(含现有 R19 端点);前端隐藏入口,后端 403 为权威 | 低 |
| plate | 析出/登记依赖目录可达,与 502 口径一致;调用全部在落库事务外(P7-④) | 无新增 |
| 前端 | 导入入口(MemberUser)+ 映射确认对话框(**敏感字段无自填入口、认证引用栏**、全局副作用文案、非敏感值只读展示)+ 409 自愈 + 预检引导 | 中 |
| suite/分享/适配/集成 | 导入只新建私有场景,不触碰既有行 | 无 |

## 8. 测试计划

- **回环(真实 plate,非 mock;标记 local-only 或 CI 起 plate——conftest 的
  plate client 是 mock 注入,CI 默认无 plate)**:导出 → 导入 → 导出的
  definition 与源等价(改写点外)。**断言语义(P7-①)**:steps 自带断言
  保留;导入后 registry 为空——不选注入条目的方案下行为等价;源场景靠
  registry 注入条目跑的变体不可复现(文档化断言,首建态接受的代价)。
- 析出分支:复用(值一致)/ 映射(值不一致,本机为准)/ 新建 / 步骤间
  不一致路径保留字面值 / 别名缺值保留(不补值)/ 无锚点步骤排除 /
  模板值排除 / 两层后缀别名需换名 / 复用判定按三层链解析后的最终值
  (共享底座互导判复用)。
- **「有接管者才清除」不变量(专项组)**:敏感字段(无输入入口)→ body
  字面值保留且新别名无该路径;映射到已有别名缺值路径 → 字面值保留;
  本机别名无 `base_url` → 源 `config.services` URL 保留;fieldStates
  缺失致面多算的路径 → 字面值保留(构造已知面 + 部分接管场景逐一断言
  "不清即不丢")。
- **凭证纪律断言**:导入后 `config.users` 为空;文件中的明文密码不出现在
  场景 payload / 新别名 carry / 任何日志;**敏感路径不进 carry 绑定、
  字面值保留在 body**(界面无输入入口);认证引用栏数据组装正确
  (`scan_auth_aliases` × 导入人凭证池,有/无标注)。
- **请求契约**:mappings 无值覆盖字段——携带任何值覆盖键的请求 422
  (pydantic `extra="forbid"` 或显式校验)。
- ID 重铸:keep 409;newId 格式非法 422、被占 409;201 响应 ID=回传值;
  重复导入两次 new 不撞。
- 事务:别名撞名/ID 撞车/映射失效 → 整体回滚(场景、别名、carry 均无
  残留);T1 包装器调用方(常规创建/copy/fork)行为不变;**事务内无
  plate 调用**(目录/carry 面/convert 均在事务外)。
- 权限:`user` 调 precheck/import 均 403。
- **存量契约迁移**:现有 R19 `/scenarios/import` 测试与新请求形状对齐
  (mappings/MemberUser);`/export` 形状变更的消费者回归(前端零调用已证,
  CLI 读本地文件不受影响)。
- 体积:>5MB 解析前 413;YAML 文件给明确提示。
- 落库重算:预检后别名被删/值被改 → `mapping_stale`。

## 9. 实施波次

| 波次 | 内容 | 量级 |
|---|---|---|
| W1 | `/export` 对齐可执行形态;真实 plate 回环测试基线(local-only/CI 起 plate) | 小 |
| W2 | 事务改造 T1/T2(含调用方清单与错误映射迁移) | **中** |
| W3 | precheck:原始 Request 体积拦截、格式/convert/修订阻塞项、析出分析与映射建议、认证引用数据(`plate_client` 补修订列表薄包装) | 中 |
| W4 | 落库:plate 调用全部出事务;重算 + 单事务(别名/carry/改写/清空/不变量/建场景)+ 409 族错误码 | 中 |
| W5 | 前端:入口(MemberUser)、映射确认对话框(敏感字段无自填、认证引用栏、全局副作用文案)、409 自愈、预检引导 | 中 |
| W6 | 测试(§8)+ 全量回归 | 中 |

依赖:W1、W2 并行 → W3 → W4 → W5 → W6。无 schema 变更、无权限模型
变更、无数据迁移。

## 10. 决策记录

**存续自 v1.x**(口径不变):首建态;版本按文件声明、缺失拒绝并列可用
修订;不加平台侧第二套版本权威;plate 不可达 502(与普通保存的不对称是
刻意的:导入无执行期兜底机会);体积拦截点写实(原始 Request)。

**v2.x 拍板(2026-10-14)**

| # | 决策 | 拍板 |
|---|---|---|
| P1 | 导入权限 `MemberUser`(含现有 R19 端点收紧) | ✅ 前序拍板 |
| P2 | **凭证:内部系统携带本可接受,取"清空+自配"**——config.users 清空(认证缺口前移确认界面,见 P7);新建别名敏感字段**只能留空保留字面值,无手填入口**(同日修正:carry 列明文且全员可读);认证走 credential_alias/凭证池;非敏感值照文件;敏感识别漏检残余接受(内网) | ✅ 2026-10-14(同日修正) |
| P3 | **导入 = 新建**:与源场景无关,导入人全权维护(含凭证时效),不做快照时效告警 | ✅ 2026-10-14 |
| P4 | **ID 重铸回归**:idMode keep/new + newId 回传 + 409 自愈 | ✅ 2026-10-14 |
| P5 | **「有接管者才清除」硬不变量**:body 字面值与 config.services URL 仅在本地有实际接管者时清除,未填/缺值一律保留(防"清除×自配留空"交互的静默丢值、防面漂移误删) | ✅ 2026-10-14(风险评审 A 项) |
| P6 | 风险评审 C-F 项采纳:导入成功 toast 引导跑预检;R19 存量契约迁移入 W6;真实 plate 回环测试 local-only/CI 起 plate;新建别名全局副作用文案(登记双态事实见 §2/§7) | ✅ 2026-10-14 |
| P7 | **终稿修正**:①registry(偏离注入)不随文件走、导入即丢失——"不选注入条目方案下行为等价"写实(推翻 v2.0"断言物化等价"的错误表述,§0/§1/§8 已改);②carry 面敏感字段禁手填进 carry(明文全员可读,与 §4 纪律相反),只能留空保留字面值;credential_alias 只管 `${auth.*}`,不与 carry 字段混;③认证引用栏入确认界面(config.users 清空缺口是导入决策产物,不后移 run_precheck);④plate 调用(目录/carry 面/convert)全部出事务,事务内只做本地读写;⑤复用判定路径级规则:文件面路径集 vs 三层链解析值逐条比,本机缺值路径判"映射"并保留字面值;⑥**确认界面只读、删 credentials 值覆盖字段**——非敏感值照文件写入、敏感值不进 carry,均无用户改写;要改值导入后走 carry 配置页(P3 同口径),服务端无值覆盖校验面 | ✅ 2026-10-14 |
| P8 | **导出收口(推翻 D9 的前端拆双入口)**:可执行形态 = 唯一文件格式,同一产物既可执行也可导入(对已保存场景,`/export` 与前端默认导出逐字节相同,同源测试钉死)——「导出场景(可导入)」与「导出可执行」双入口是 R1 修正的过渡残留,标签暗示两种格式,违背统一口径。收口:菜单回归单一「导出 JSON / YAML / 复制」;working 提示挪入全部导出路径的统一汇合点(`convertDraftToExecutable`);「按方案导出」保留并注明"产物含明文凭证,可导入(P2 清空)但不适合传递";`/export` 端点保留为服务端权威产物(CLI/API 消费,前端无需单独入口);前端 `exportScenarioBundle` 封装随之删除 | ✅ 2026-10-15 |

**v2.x 废弃清单**(相对 v1.x):信封与 formatVersion;可执行形态判别与
`executable_not_importable`(可执行形态即唯一格式);导入告警清单
(missingServices/working 提示等,发现点统一移交 run_precheck;**例外**:
认证引用栏因缺口是导入决策产物而保留在确认界面,见 P7);容器件携带
(orchestration/registry/ui——registry 丢失是首建态接受的**代价**,非
"等价兜底",语义见 §0/§1);working 导出提示(随告警清单取消)。
