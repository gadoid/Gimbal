# 集成个人侧 · 实现方案(v1.3,4 项待拍板)

> 日期:2026-10-19　基线:`feat/plate-s1 @ 652514d5`(`ext-unify-b2-6`,本版全部断言核实于此提交)
>
> 定位:兑现《GIMBAL-外部系统集成架构设计》分期计划 **P2 的个人模式收口** ——
> 后端 Y3 已落(2026-10-12);本方案补**前端缺口**与**个人模式在订阅场景下的安全前提**(订阅知情同意),并按《外部接口定义归一 plate 改造方案》v1.0(批0–批4 + b2.5 + b2.6 已落,下称「归一方案」)对齐口径。
>
> 接续关系:`claude/integration-p2-design.md` §4(Y3)的个人模式**前端**增量以本文为准;该文档 §2(外部系统定义落平台目录 / `ext:` 锚点)已被归一方案取代,个人侧一律不再引用。
>
> 修订:v1.3 —— 三点评审吸收:①指纹纳入 **base_url 集合**(G-F:别名表执行期活解析、共享别名 member+ 可改、凭证与 URL 同 case 注入,原指纹不含 → 主机重定向无感知);新增 R8「凭证不与主机绑定」单列另开工单。②**任一别名缺失即暂停**(G-G:原「全缺才暂停、部分缺照跑」在写模式下留半成品;S0② 一行修,`missingCredentials` 与暂停口径统一,R7 删除)。③指纹**有意不覆盖**项写明(plate 定义、展示性字段)。④W0 拆 **W0a(开放门槛:订阅收口+知情同意+visibility 联动)/ W0b(消费面:字段+自管)**;⑤S0 扩为两项先修批;⑥P-4 必要性随 base_url 入指纹增强。
> 修订:v1.4 —— 拍板落定(§3:P-1=b / P-2=维持 private / P-3=删实例行 / P-4=a,2026-10-19);S0② 写明**共享解析函数不动**(只改集成侧判定,常规测试执行依赖宽松语义);W0a③ 补**指纹失败口径**(别名查询失败 → 本轮不执行、按运行失败收口,不误判不跳过);§2.2 开发排期,S0 即刻开工。
> 修订:v1.5/v1.6 —— S0/W0a/W0b 实现落档(§2.2 排期状态、§2.2.1 指纹小设计定稿;细节见 §5 修订记录)。

## 0. 归一方案对齐点(与旧 P2 方案的差异)

| 主题 | 旧 P2 方案(v1.0,2026-10-12) | 现口径(归一方案 v1.0 + b2.6) |
|---|---|---|
| 外部系统定义 | 平台外部目录(kind=external 别名,`ext:` 锚点,Y5) | plate `ServiceDefinition.kind=integration`,不发版;`ext:` 锚点与 `external_endpoints` 表已退役(批2/批3) |
| 场景引用外部系统 | `ext:` 锚点步骤走外部目录下拉 | plate 锚点;`meta.plate` 声明 `integration`;编排器选单按端点行 kind 分组、选中自动写声明(D-F,已落);**双向绑定**(b2.6/F2):kind=integration 系统只接受 `integration` 声明(plate 声明闸与平台保存预检同文案 422) |
| 平台模式只读闸 | 目录条目 `query_safe`(ext: 分支) | plate 契约 `metadata.query_safe` 单一真源;无锚点手写调用只认 method,fail-closed |
| 外部定义版本 | 目录无版本概念 | `integration` ref 读当前定义、非预览(D-G);无漂移检测(定义真源唯一) |
| 执行追溯 | 未涉及 | `plate_pins` 记 `integration@<标识>`(D-L shape_hash 聚合)限**测试执行与图执行**;**集成任务(含个人实例)不另设追溯**(D-J 范围订正,已知边界) |
| carry | 未涉及 | carry 覆盖第三方端点;别名表 `base_service` 优先(D-M,已落)——个人场景与 sut 同口径 |
| 声明合法性 | 未涉及 | 裸 `<line>` 声明 422 + `missing_revision`(D-K/b2.6 F4);`working` 声明场景集成拒绝触发(A-4/W6,保存/执行双闸外手动面 409) |

### 0.1 两种执行身份的定位

| | 平台模式 | 个人模式 |
|---|---|---|
| 身份 | 平台凭证(admin 维护) | 持有人本人凭证池(`auth_sessions`) |
| 能做什么 | **只读**:GET/HEAD/OPTIONS 或 plate 标 `query_safe` 的接口 | 读写皆可,边界 = 持有人在第三方系统的权限;**不按 `query_safe` 拦截** |
| 典型产物 | 公共只读同步信息卡片(保活、看板统计) | 个人任务;公共个人模板供他人订阅后以各自身份执行 |
| 可信来源 | 定义可信(plate 评审)+ 调用无副作用(只读闸)+ 平台身份 | 定义可信(plate 评审)+ 持有人身份 + **持有人对执行内容的知情同意**(§1.3) |

写操作必须个人身份(架构决策 5);平台不做任何人写操作的代理。

## 1. 实现进度盘点(2026-10-19,代码逐项核实 @ 652514d5)

### 1.1 已落 —— 后端(Y3,2026-10-12 起;行号为当前基线)

| 能力 | 落点 | 备注 |
|---|---|---|
| personal 任务创建 | `routers/integration.py:170`、`:198-207` | `identityMode=personal` 接受;owner 即首个持有人,创建即播种自己的实例 |
| 保存闸:个人放行写操作 | `routers/integration.py:188-196` | 只读闸(含 query_safe 判定)仅 platform;personal 全开 |
| 执行闸:个人免二次检查 | `integration_runner.py:447-456` | plate 不可达的 channel 收口同样仅 platform |
| `working` 预览拒绝 | `integration_runner.py:458-467` | 全模式;手动触发面在路由层先行 409(`:279-288`) |
| 订阅即建(幂等) | `integration_runner.py:869-911` `ensure_instance` | personal = holder 实例;platform = 平台系统用户唯一实例(P1 行为);播种即 `enabled=True` + `next_run_at=now` |
| 实例播种点(**4 处**) | 列表 `:163`/创建 `:223`/卡片 `:363`/手动执行 `:289`(均经 `_tpl_instance`→`ensure_instance`,`:67-82`) | ⚠️ 列表与手动执行两处属未经同意播种 —— 见 §1.3-3、§1.4 G-B |
| 缺凭证暂停 | `integration_runner.py:488-504` | **现状(缺陷 G-G):暂停条件 = 注入清单全缺**(`:500` `if aliases and not exec_auths`),部分缺失照跑、缺的别名在 Gimbal 侧步骤级报错;缺失清单只写入 `last_error` 文本 → S0② 改**任一缺失即暂停** |
| 凭证失效暂停 + 按模式通知 | `integration_runner.py:596`、`:697-715` | auth 不重试(防锁号);个人通知持有人,文案带「我的凭证」;结论通知(D3)个人=持有人、平台=模板 owner |
| 凭证复活钩子 | `integration_runner.py:914-947`;`auth_sessions.py:183`、`:251-256` | 更新/重存凭证 → `auth_failed`/`missing_credential` 实例自动恢复调度(`manual` 暂停不受影响) |
| 手动执行冷却 | `routers/integration.py:299-309` | 仅 platform 60s;personal 持有人无冷却(Y3 口径) |
| 服务地址解析 | `integration_runner.py:520-534` | **执行期活解析**:每次执行现调 `service_aliases.base_urls_for`(场景引用服务 → 别名表 base_url),与凭证注入同一个 case;物化优先链「显式绑定 > 场景声明 > **base_url** > 报错」(`service_aliases.py:297-306`)—— ⚠️ 别名表全局且**共享行 member+ 可改**(`routers/service_aliases.py:129-135`/`:168-175`),见 §1.4 G-F/R8 |
| run/check 拆分、双触发过期、通知边沿合并 | v2 改造 I1–I4(已落,2026-10-14) | 模式无关,个人实例同口径 |
| G1 认证链 / G2 outputs / 卡片模板 / 跨次游标 | P2 Y1/Y2/Y4(已落) | `call.auth`+签名器、`error_kind`、kv/counter/list、`state_vars` |
| 凭证面 | `auth_sessions`(我的凭证,既有)+ `/integration/platform-credentials`(admin) | 注入清单 = 执行方案 `serviceBindings.authAlias` ∪ 场景 `${auth.<name>.}` 模板扫描(`_auth_aliases_of`,`integration_runner.py:390-399`;**不经别名表 `credential_alias` 映射**);解析在 `_resolve_exec_auths`(`run_dispatcher.py:2675`,公开别名 `:3020`):**按别名名称 + `owner_id == 持有人`** 过滤(`:2704-2707`),同名约束见 §2.1 |

### 1.2 未做 —— 前端

| 缺口 | 现状(核实) |
|---|---|
| 创建个人模式任务 | `IntegrationCenter.vue:5`/`:79` 表单仅平台模式,不传 `identityMode`(服务端缺省 platform) |
| 订阅 / 退订 | `api/integration.ts` 无订阅接口;播种全靠后端隐式(列表/卡片/手动执行) |
| 订阅状态呈现 | 列表无「订阅 / 已订阅」概念,看不出这个实例是不是我的 |
| 凭证引导 | `FunctionCard.vue:145-151` 有角标(凭证失效/缺凭证)、`:248` 有立即执行,但**无「去配置我的凭证」入口**,也不显示缺哪个别名的凭证 |
| 创建前置提示 | 建 personal 任务时不知道场景涉及的 integration 系统对应哪个别名凭证;`working` 声明的场景首跑必被拒,创建时无预警 |

### 1.3 未做 —— 后端(订阅场景的安全前提:订阅即凭证委托)

个人实例执行的内容与去向大部分来自模板主人,而身份来自持有人(`integration_runner.py:423-534`):

| 要素 | 来源 |
|---|---|
| 场景 | 模板主人(创建时「只能引用自己创建的场景」,`routers/integration.py:183-185`;执行时**活引用**加载,无快照) |
| 执行方案(服务绑定、数据集选择) | 模板主人 |
| 数据行 | 主人数据集首行(`:471-483`) |
| 调度 cron | 模板主人 |
| **服务地址(base_url)** | **全局别名表**(执行期活解析,`:520-526`;非模板、非持有人,共享行 member+ 可改 —— 见 G-F) |
| 凭证 | **持有人**(`_resolve_exec_auths`,按别名同名解析) |
| 只读约束 | 个人模式无(`:447` 仅 platform) |

由此产生三个缺口:

1. **内容可在同意之后被改写**:执行链对场景/方案/数据集全部活引用、无指纹(`IntegrationTask` 全字段核实,无可复用快照位);`TaskPatch` 允许 owner 改 `schemeId`/`triggerCron`,场景本体 owner 可随时在编排器编辑 —— 订阅者实例下次调度即以订阅者身份执行新内容(含写操作),无感知。「写操作必须个人身份」的意图(动作归属到决策者本人)被打穿。
2. **订阅时看不到执行内容**:场景读闸 = public ∨ 属主 ∨ admin ∨ 引用,而「引用」只含 ShareRef 直接引用与经 suite 引用(`_ownership.py:76-97`),**集成订阅不在内**;场景 visibility 缺省 private → 订阅者对主人场景 404。
3. **隐式播种造成未经同意的执行(机制成立;本库尚未发生)**:四环俱全 —— 列表播种 → 播种即 `enabled=True` + `next_run_at=now`(`:894-897`)→ `_claim_due` 只看 idle/enabled/due、无身份/同意过滤(`:788-797`)→ 凭证按别名同名在持有人池解析。恰持有同名凭证者,其身份会被用于执行他人场景。**活库实测(2026-10-19):personal 实例行 0 条** —— 本环境尚无人创建过 personal 任务;W0a② 存量清理在本库为空操作,保留以防其他环境。

本方案 W0a③ 以**订阅知情同意**补齐(指纹存放见 §3 P-4)。它不是审批流:不引入第三方审批人,只是持有人对「用我的凭证、向这些地址、执行这些内容」的确认。

### 1.4 复核新增缺口(v1.2/v1.3,均有代码实证)

| # | 级别 | 缺口 | 实证 | 处置 |
|---|---|---|---|---|
| **G-A** | **P1·安全(平台模式同中招,与订阅无关)** | **方案/数据集归属校验缺失 → 跨用户数据注入与泄露**。利用链:`schemeId` 创建/PATCH 均不校验归属(`integration.py:199`、`:245-246`)→ runner 按**全局** scheme_id 取方案、不限场景(`integration_runner.py:430-432`)→ 他人方案的 `dataSetSelection` 生效,数据集取行也无归属过滤(`data_set_store.get_row`,`:162-176`,归属检查只在 data_sets 路由层)→ **他人数据集首行注入物化**,值进请求体与 `last_outputs`,出现在攻击者自己实例的卡片上。scheme_id/dataset_id 为顺序可枚举 `rs-NNN`/`ds-NNN`(`scheme_store.py:55-62`)。对比:常规执行链方案**按场景限定**(`run_precheck.py:99`),集成路径是唯一偏离点 | 上述五处行号 | **S0①** |
| **G-B** | P1·同意面 | **手动执行是第 4 个隐式播种点**:`POST /tasks/{id}/run` 对 personal 先 `ensure_instance(user.id)` 再立即执行(`integration.py:289`)—— 未订阅用户点一次「立即执行」= 播种 + 立即以本人凭证执行,会绕穿知情同意 | `:289` | W0a①:run 面对未确认实例先走确认,不建不跑 |
| **G-C** | P2 | **visibility 转 private 不停既有订阅实例**:PATCH 无联动(`:249-250`);`_claim_due` 不看 visibility(`:788-797`)。订阅者实例继续以其凭证按时执行,但列表/卡片因 `_visible` 失败转「已移除」态 —— **还在跑,但看不到也退不掉**(叠加 G-D);与缺口 1 组合是放大器 | 三处行号 | W0a⑤ |
| **G-D** | P2 | **订阅者无任何自管端点**:路由全集 9 个,PATCH/DELETE 均要求 `_can_manage`(owner/admin)—— 订阅者没有「暂停/停用我的实例」手段,唯一停止方式是尚未实现的退订 | 端点清单 | W0b⑥ |
| **G-E** | P3 | **模板删除对订阅者无通知**:软删后订阅者实例靠 `_claim_due` 下一拍 `enabled=False` 兜底,卡片有「已移除」态但不产生通知,按 cron 等结果的订阅者只见「过期」 | `:258-268`、`:800-803` | W2 |
| **G-F** | **P1·安全/同意面(v1.3)** | **内容指纹漏服务地址 —— 订阅者凭证可被发往别的主机**。base_url 执行期活解析自全局别名表(`integration_runner.py:520-526`),与持有人凭证注入同一 case(`:527-534`);共享别名行 **member+ 即可改 base_url**(`routers/service_aliases.py:129-135`/`:168-175`)。别名一改,下次调度凭证即发往新主机;而指纹(场景+方案+数据集行+cron)不含别名表 → 不触发重新确认。边界:集成路径凭证别名不经别名表 `credential_alias` 映射(`:485`),风险面即 base_url 重定向 | 四处行号 | **W0a③**:指纹纳入「场景引用服务经 `base_urls_for` 解析出的 base_url 集合」;更大范围的「凭证不与主机绑定」单列 **R8 另开工单**,本方案不解决 |
| **G-G** | P2(v1.3) | **部分缺凭证不应照跑**:`:500` 只在全缺时暂停,部分缺失照跑 —— 个人模式允许写操作,缺一个别名 = 场景跑到一半失败,**前面的写步骤已执行,第三方系统留半成品** | `:500`;存量测试仅钉全缺(`test_integration.py:664`) | **S0②**:判定改「任一别名缺失即暂停为 `missing_credential`,一步不执行」;`missingCredentials` 与暂停口径就此统一(原 R7 删除);平台模式同受益 |

## 2. 批次计划

| # | 侧 | 内容 | 规模 | 验收 |
|---|---|---|---|---|
| **S0** | 后端·安全/正确性先修批(独立,先于一切;与订阅无关,平台模式同受益) | **①方案/数据集归属收口**(G-A):创建、PATCH、runner 三处把方案限定到 `tpl.scenario_id` 之下(对齐 `run_precheck` 的场景限定惯例;创建/PATCH 对不属于该场景的方案 422 响亮拒绝,runner 侧找不到即回退场景默认方案 —— 与「方案被删」既有行为一致);数据集注入按「方案所属场景」校验。**②缺凭证判定收紧**(G-G):`integration_runner.py:500` 改「注入清单任一别名未解析即暂停 `missing_credential`」,一步不执行;补部分缺失新用例。**收紧只落集成侧判定,共享解析函数 `_resolve_exec_auths` 行为不变** —— 常规测试执行依赖其宽松语义(「缺 alias 只是注入不到 users、告警后继续」,V1 一致口径) | S | pytest:枚举他人 `rs-NNN` 方案 → 不生效;引用非方案所属场景的数据集 → 不注入;**两个别名缺其一 → 暂停(新用例)**;全缺暂停既有用例不破;**常规测试执行在部分缺凭证时行为与现状一致(不暂停,步骤级报错照旧)**;平台/个人两种模式同测;常规执行链行为不变;三侧门全绿 |
| **W0a ✅** | 后端(个人模式**开放门槛**;已落 2026-10-19,小设计与行为清单见 §2.2.1) | **①显式订阅/退订 + 播种收口(4 处)**:`POST /integration/tasks/{id}/subscribe`、`DELETE .../subscription`;列表 `:163` 摘除只查不建;卡片 fetch 改显式;**run 面未确认实例不建不跑、先走确认**(G-B);创建保留 owner 播种;退订 = 删持有人实例行(P-3)。**②存量清理**:删除「持有人 ≠ owner」的全部 personal 实例行(本库为空操作,保留流程)。**③订阅知情同意**:subscribe 返回执行内容摘要(步骤系统·接口·方法,非只读步骤标记;所需凭证别名;**服务地址**;数据集名);订阅成立记录**内容指纹** = 场景定义 + 执行方案 + 所选数据集行 + cron + **base_url 集合(经 `base_urls_for` 解析)** 的规范化哈希;调度与手动执行前比对,不一致 → 非 owner 实例 `paused/template_changed` 并通知「模板内容已变更,请重新确认」;重新确认 = 刷新指纹恢复调度;owner 自有实例不受此闸。**⑤visibility→private 联动**(G-C):非 owner 实例暂停 + 通知;转回 public 不自动恢复,需订阅者重新确认。**指纹失败口径**:别名查询失败(`base_urls_for` 异常;现执行链按「增强项,失败跳过」处理)时**不得**以空集算指纹(会把未变的模板误判成 template_changed,逼订阅者空确认)也**不得**跳过比对(等于绕闸)—— **本轮不执行,按运行失败(`run=channel`)收口**,`lastError` 注明「服务地址解析失败」 | M | pytest:两用户订阅同一公共 personal 模板各建各实例互不可见;列表/卡片 **GET 无写入副作用**;**未确认用户 run → 引导确认而非直接执行**;退订后重订幂等重建且须重新确认;owner 改场景/方案/数据集/cron 任一项 → 订阅者实例 `template_changed` 暂停、owner 实例照常,确认后恢复;**别名 base_url 改动 → 订阅者实例同样 `template_changed`**(指纹含 base_url 集合的正反例);**别名查询失败 → 本轮运行失败(channel),不翻 template_changed、不跳过比对(反例钉死)**;**visibility→private → 非 owner 实例暂停 + 通知** |
| **W0b ✅** | 后端(消费面字段与自管;已落 2026-10-19) | **④结构化字段**:`_tpl_out` 加 `authAliases`(同 `_auth_aliases_of` 口径);`_inst_out` 加 `missingCredentials`(缺失别名全集;**与暂停判定同口径 = 任一缺失即列**——S0② 后两者天然一致)与 `subscribed`(当前用户是否持有实例);卡片出参同带两字段。**⑥订阅者自管**(G-D):暂停/恢复「我的实例」(`paused/manual`;复活钩子既有语义不覆盖 manual,`:917-922`);resume 仅 manual 可恢复,template_changed/made_private → 409 引导重新订阅确认、missing_credential → 409 引导补凭证 | S-M | pytest:`missingCredentials` 与执行期暂停判定一致(S0② 口径);自暂停不受凭证复活影响;`subscribed` 两账号互不可见 —— **已落**:tests/test_integration_w0b.py 4 用例(字段生命周期含补凭证清空/平台任务恒 False/卡片带字段/自暂停复活边界+resume 409 边界) |
| **W1 ✅** | 前端 | 集成中心创建表单加「执行身份」(platform/personal);personal 时隐藏只读闸提示,显示**凭证前置提示**(取 `authAliases` → 我的凭证是否已配)与 `working` 声明预警;personal + public 时提示「订阅者将以其本人凭证执行本模板,你后续的修改需订阅者重新确认」 | M | vitest + vue-tsc;平台模式行为不变;personal 任务创建 201 即返回自己的实例;`working` 场景创建时前端先提示。**已落(2026-10-19)**:后端补 `GET /integration/scenario-preview`(注入别名/我的缺失/working 标记;归属校验同创建闸,`scenario_aliases` 单一实现);前端 `fetchScenarioPreview` + 表单执行身份/三段提示;vitest 7+2 新用例、全量 1278 绿、vue-tsc 零错 |
| **W2 ✅** | 前端 | 订阅/退订 UI:列表对公共 personal 模板显示「订阅 / 已订阅 / 退订」(取 `subscribed`);**订阅确认弹窗**渲染 W0a③ 摘要(非只读步骤高亮、所需凭证别名、**服务地址**、数据集归属提示),确认后才调用 subscribe;工作台加卡库对 personal 模板标注「订阅后按我的凭证执行」,加卡即走同一确认流程;`template_changed` 与「转 private 暂停」实例显示「内容已变更/已转私有 · 重新确认」入口(同一弹窗);**订阅者暂停/恢复入口**(G-D);**模板删除通知渲染**(G-E) | M | 两账号浏览器走查(**随收尾批部署后进行,新后端未部署前无法实机**)。**已落(2026-10-19)**:`SubscriptionDialog` 组件(摘要/读写高亮/确认/重新确认共用);IntegrationCenter 订阅/退订/暂停恢复入口 + 三新暂停态文案;FunctionCard 未订阅订阅入口、待确认/本人暂停恢复入口;WorkbenchView 加卡标注;**后端补 delete_task 订阅者通知(G-E)与 notify_subscribers**;加卡确认入口落位为「卡片首渲染引导订阅」(卡片 state=none 即出确认入口,等效覆盖加卡路径,画廊通用组件不做特判 —— 实现口径与方案文本的小偏差已记);浏览器走查移收尾批 |
| **W3 ✅** | 前端 | 卡片个人语义补全:`auth_failed`/`missing_credential` 角标可点 → 我的凭证页,按 `missingCredentials` 定位缺失别名;通知文案既有不动 | S-M | 浏览器走查(**随收尾批**)。**已落(2026-10-19)**:五个角标位统一可点,凭证类角标 → `/auths?q=<缺失别名>`;Auths 页 ?q 预填搜索(无路由环境守卫) |

顺序:**S0 立即**;W0a(开放门槛)→ W0b → W1/W2(可并行,**均依赖 W0b④ 字段**)→ W3。上线口径:个人模式对外开放 = S0 + W0a 完成;W0b/W1–W3 是消费面补齐。门:每批 vitest + vue-tsc;S0/W0a/W0b 加平台后端 pytest;W2/W3 走查截图存证。

### 2.2 开发排期(2026-10-19 定,拍板后执行)

| 阶段 | 批 | 交付物 | 门/备注 |
|---|---|---|---|
| 先修(即刻) | **S0** | 归属收口 + 任一缺失即暂停 + 用例 | 后端 pytest 全量;不依赖任何拍板,先行合入。**✅ 已落(2026-10-19)**:路由创建/PATCH 归属闸(`scheme_not_owned` 422)+ runner 方案/数据集场景限定 + `:500` 任一缺失即暂停(共享 `_resolve_exec_auths` 未动);新用例 4(归属正反例/跨场景方案忽略+数据集不注入对照/部分缺失暂停/共享函数宽松钉死);平台后端 1035+2s 全绿 |
| 开放门槛 | **W0a** | 指纹小设计定稿(规范化哈希口径/正反例)→ 迁移(`consent_fingerprint`/`consented_at`,**手工 alembic + 库备份先行**)→ 订阅/退订端点 + 播种收口(4 处)+ 存量清理 + `template_changed` + visibility 联动 + 用例 | 后端 pytest 全量;活体两账号 curl 走查 |
| 消费面 | **W0b** | `authAliases`/`missingCredentials`/`subscribed` + 订阅者自管端点 + 用例 | 后端 pytest;W1/W2 的前置。**✅ 已落(2026-10-19)**:任务行/卡片出参带三字段;`subscription/pause`/`resume`(manual);4 用例 |
| 前端 | W1 → W2 → W3 | 创建表单 / 订阅确认弹窗 / 卡片凭证引导 | 每批 vitest + vue-tsc;W2/W3 浏览器走查截图(5173 实机) |
| 收尾 | — | 三侧全量回归 + 部署(重启 gimbal-platform、发布 dist;plate 不动)+ 提交打 tag | 三侧门 + 活体验证;按批次也可分批合入 |

依赖:S0 与一切并行安全;W0a 依赖 S0(指纹读方案,归属收口在前);W1/W2 依赖 W0b④。每批独立提交、独立可回退。

### 2.2.1 W0a 指纹小设计(定稿,随实现落地)

**投影与算法**(`integration_runner.consent_fingerprint_of`,canonical JSON `sort_keys` + 紧凑分隔符 → sha256 hex):

| 要素 | 取值 |
|---|---|
| 场景 | `definition.steps`(逐 step **剔除 `description`** 展示字段)+ `definition.config` |
| 方案 | `serviceBindings` / `dataSetSelection` / `dataSetIds`(去方案名) |
| 数据集 | 选中数据集**首行注入值**(经 S0① 场景归属校验后的 `row_dict`) |
| cron | `tpl.trigger_cron` |
| base_url | `base_urls_for`(场景引用服务)解析出的集合,执行期活取 |

**有意不覆盖**(R3):plate 接口定义;场景/方案/步骤的名称与描述。owner 改展示字段不触发重确认。

**失败口径**:consent 实例(非 owner 的 personal)在 `base_urls_for` 查询失败时**本轮不执行**,按 `run=channel` 普通失败收口(`lastError` 前缀「服务地址解析失败」)—— 不以空集算指纹(会把未变模板误判成 template_changed)、不跳过比对(绕闸);owner/platform 实例维持「增强项失败跳过」旧口径。

**行为清单(实现落点)**:
- 播种点 4 处收口:列表/详情/卡片 GET 只查不建(`_my_instance`);run 面未订阅 → **409 `subscription_required`**(不建不跑);创建保留 owner 播种并**留底指纹**(best-effort);
- 端点:`GET /tasks/{id}/subscription-summary`(结构摘要:步骤系统·方法·只读标记/凭证别名/服务地址/数据集名/cron;不含场景全文与数据值)、`POST /tasks/{id}/subscribe`(幂等;建实例 + 刷指纹 + `consented_at`;对 `template_changed`/`made_private` 暂停实例 = 重新确认恢复调度;别名查询失败 503 `alias_unavailable` 不留半确认)、`DELETE /tasks/{id}/subscription`(P-3 删行);
- 暂停原因:`template_changed`(指纹不一致,**含未留指纹的存量行** —— 按未确认处理;非运行失败:不动 `last_run_at`/`fail_streak`,直接通知持有人)、`made_private`(W0a⑤);
- 执行闸位置:`run_instance` 内、凭证解析**之前**(同意不成立不碰凭证);
- 迁移 `0030_integration_consent`:加列 `consent_fingerprint`/`consented_at` + 存量清理(非 owner personal 实例行删除;活库 0 条)。

**✅ W0a 已落(2026-10-19)**:上述全部实现;`tests/test_integration_w0a.py` 6 用例(订阅主链/未订阅 409+GET 零副作用/cron 与 base_url 双正例触发 template_changed/owner 免闸/再订阅恢复/退订重建、别名查询失败 channel 反例、private 联动正反例、无指纹存量行按未确认、平台任务 422);`test_personal_mode_lifecycle` 已切新语义。

### 2.1 约束与手册口径

- **凭证按别名名称匹配**:订阅者须持有与模板执行方案 `authAlias`(及场景 `${auth.<name>.}`)**同名**的凭证(`_resolve_exec_auths` 的 owner + alias 双过滤);凭证提示与手册写明,否则配了凭证仍报缺失;
- **缺凭证口径(S0② 后)**:注入清单**任一**别名缺失 → 实例暂停 `missing_credential`,一步不执行;凭证补齐后复活钩子自动恢复。`missingCredentials` 列缺失全集,与暂停判定一致;
- **服务地址**:base_url 来自全局别名表,执行期活解析;共享别名 member+ 可改。订阅场景以指纹感知变化(重新确认);**个人自有任务不受指纹保护** —— 凭证与主机不绑定是平台级问题,见 R8 另开工单;
- **数据归属**:订阅者执行使用主人数据集首行(可能含主人特有值,如指派人、项目号),订阅确认弹窗提示;订阅者自带数据不在本方案范围;
- **调度归属**:cron 由模板主人设定,订阅者继承;cron 变更纳入内容指纹;
- **私有场景的可见性**:订阅确认摘要只暴露执行所需的结构信息(系统、接口、方法、所需凭证别名、服务地址、数据集名),不暴露场景全文与数据值。

**明确不做**(沿用既有拍板,不因本文重开):任务级审批流(独立工作单,另行排期;订阅知情同意不是审批流,见 §1.3);集成执行历史(维持只留最近一次);订阅者级通知(沿 v2 D3 后置口径;`template_changed`/转私有/删除通知属执行身份通知,不在此列);MeterSphere 签名器与知识类拉取(原设计 P4);订阅者自带数据集;**凭证-主机绑定**(R8,独立工作单)。

## 3. 拍板记录(owner,2026-10-19 全部落定)

**P-1 = b(收口为「加卡 + 显式订阅 + 确认」才播种,存量清理);P-2 = 维持 private;P-3 = 删持有人实例行;P-4 = a(实例行新增 `consent_fingerprint` + `consented_at`,随 W0a 迁移)。** §2 批次按此执行。

| # | 问题 | 现状 / 选项 | 拍板 |
|---|---|---|---|
| **P-1** 订阅播种时机 | 列表与手动执行路由对所有可见 personal 模板播种 —— 浏览或点一次「执行」即订阅并入调度,与架构「工作台加卡时订阅」原意不符,且是未经同意执行的入口(§1.3-3、G-B) | a 维持现状 / b 收口为「加卡 + 显式订阅 + 确认」才播种 | **b**;存量非 owner 实例全部清理(W0a②;本库实测 0 条,空操作),需要者重新显式订阅并确认 |
| **P-2** personal 任务默认可见性 | `TaskIn.visibility` 缺省 `private`;private 的 personal 任务无订阅面(仅自用),public 才可被订阅 | 默认改 public / 维持 private | **维持 private**(显式选 public 才可被订阅);W1 表单提示可见性含义与订阅者重新确认机制;转 private 的联动见 W0a⑤ |
| **P-3** 退订语义 | 无现成行为 | 删持有人实例行(模板不动,重订即重建)/ 停用实例行 | **删实例行**(幂等,不留僵尸行);重订须重新走订阅确认 |
| **P-4** 内容指纹的存放 | 订阅知情同意(W0a③)需在实例上记录确认时的内容指纹;`IntegrationTask` 现有字段无可复用者(`state_vars` 为跨次游标、`last_outputs` 为卡片输出,语义不同) | a 实例行新增 `consent_fingerprint`(+ 可选 `consented_at`)/ b 不加字段,非 owner 持有的实例一律过只读闸(公共个人模板对他人只读) | **a,且随 v1.3 必要性增强**:指纹现已含 base_url 集合(G-F)—— 没有此字段,不止内容改写,**主机重定向也无从感知**;b 使写类模板不可共享,与「可复用任务模板」定位冲突。属新增字段(alembic 迁移),交 owner 评估 |

## 4. 风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 订阅者凭证执行主人改写后的内容,或被发往变更后的主机 | W0a③ 内容指纹(含 base_url 集合)+ `template_changed` 暂停 + 重新确认 |
| R2 | 隐式播种产生的非 owner 实例在执行 | W0a① 播种收口(含 run 面)+ W0a② 存量清理;本库实测 0 条,风险主要在其他环境 |
| R3 | 指纹口径过窄(漏掉影响执行的要素)或过宽(无关编辑频繁打扰) | 指纹**覆盖**:场景定义 + 执行方案 + 所选数据集行 + cron + base_url 集合;**有意不覆盖**(实现时勿再纠结):①plate 接口定义 —— 走 git 评审、全员共享同一份、有 check 门,纳入只会造成全员频繁重确认;②场景展示性字段(名称、描述)。口径在 W0a 小设计中定死并出正反例 |
| R4 | 凭证同名约束导致「配了仍缺」 | `missingCredentials` 精确列出所需别名名称;手册写明 |
| R5 | 订阅者对主人数据集内容不知情 | 订阅确认提示数据集归属;不暴露数据值 |
| R6 | 顺序 ID(`rs-NNN`/`ds-NNN`)的残余枚举面 | S0① 后集成路径已限定场景归属,枚举仅剩「猜中他人场景的方案 id 且恰属同一场景」—— 即归属校验本身;风险归零依赖 S0 用例钉死 |
| R8(v1.3) | **凭证不与主机绑定(平台级,独立于订阅)**:别名 base_url 共享行 member+ 可改,改后所有引用该别名的执行 —— **包括个人自有任务与平台模式** —— 都把凭证发往新主机;指纹只保护订阅场景,自有任务无感知 | 本方案内只做「订阅场景指纹感知」;**另开工单**:凭证-主机绑定(如凭证按 URL 域绑定/告警)、别名变更审计与通知;手册先行写明该边界 |

## 5. 修订记录

| 版本 | 内容 |
|---|---|
| v1.0 | 初稿:盘点 Y3 后端已落/前端缺口;W0–W3;P-1~P-3 |
| v1.1 | 评审吸收:①§0.1 两种执行身份定位、§1.3 订阅即凭证委托三缺口(内容可改写/订阅时不可见/隐式播种);②W0 扩为显式订阅收口 + 存量清理 + 订阅知情同意 + 结构化字段;③W1/W3 基于结构化字段渲染;④P-1 存量改清理;⑤新增 P-4;⑥§2.1 凭证同名/数据归属/调度归属/可见性;⑦风险表;⑧知情同意非审批流 |
| v1.2 | 全量核实合并:①三处订正(§1.3-3「机制成立、本库 0 实例」;`_auth_aliases_of`/`_resolve_exec_auths` 行号与别名关系;缺凭证两形态口径);②新增 §1.4 五缺口 G-A~G-E(G-A 独立批 S0);③W0 验收扩三条;④R6/R7 |
| v1.3 | 三点评审吸收:①**G-F**(指纹漏 base_url:别名表执行期活解析 `:520-526`、共享别名 member+ 可改、凭证同 case 注入;指纹纳入 `base_urls_for` 解析集;**R8** 凭证-主机不绑定单列另开工单);②**G-G**(部分缺凭证照跑留半成品;S0② 改任一缺失即暂停 `:500`,口径统一,原 R7 删除);③R3 写明指纹**有意不覆盖**(plate 定义/展示性字段);④**W0 拆 W0a(①②③⑤,开放门槛)/ W0b(④⑥,消费面)**,依赖注记 W1/W2 依赖 W0b④;⑤S0 扩为两项先修批;⑥P-4 必要性增强(base_url 入指纹后,无字段则主机重定向无从感知);⑦§1.1 增服务地址解析行,§1.3 委托表增 base_url 行,§2.1 摘要与手册口径同步 |
| v1.4 | 拍板与实现口径:①§3 四项全落定(P-1=b/P-2=private/P-3=删行/P-4=a `consent_fingerprint`+`consented_at`);②S0② 写明**共享解析函数 `_resolve_exec_auths` 不动**(常规测试执行依赖宽松语义),验收加「常规链部分缺凭证行为不变」;③W0a③ 补**指纹失败口径**:`base_urls_for` 查询失败 → 本轮不执行、按 `run=channel` 收口,不以空集算指纹(误判)、不跳过比对(绕闸),验收加反例;④新增 §2.2 开发排期(S0 即刻 → W0a[指纹小设计+迁移] → W0b → W1–W3 → 收尾部署),每批独立提交 |
| v1.5 | W0a 实现定稿:新增 **§2.2.1 指纹小设计**(投影五要素/有意不覆盖/失败口径/行为清单/迁移 0030);S0 与 W0a 状态标记(§2.2/§2.2.1);`test_personal_mode_lifecycle` 切新语义(未订阅 409 + 显式订阅) |
| v1.6 | W0b 实现落档:④消费面字段(`authAliases`/`missingCredentials`/`subscribed`,任务行 + 卡片出参;missing 持有人 = personal 当前查看者 / platform 平台实例持有人)、⑥订阅者自管(`POST .../subscription/pause`/`resume`;manual 仅本人可恢复,其他暂停原因 409 引导各自路径);状态标记 §2 W0b ✅ |
| v1.7 | W1 实现落档:后端 `GET /integration/scenario-preview`(W1 前置提示数据源;`_load_exec_shape` 签名改 scheme_id 直传 + `scenario_aliases` 公共面;修复签名改造时体内残留的 `tpl.scheme_id` 引用 —— 带方案路径 NameError 被创建面 best-effort 吞掉后在 `_tpl_out_full` 显形为 MissingGreenlet,集成族 69 用例复验全绿);前端 `fetchScenarioPreview` + 表单执行身份/凭证前置提示/working 预警/订阅者提示;状态标记 §2 W1 ✅;后端三批已提交 b09c4c99(**推送被 GitHub 凭据阻塞:远端无 feat/plate-s1,SSH key 未登记、HTTPS 无凭据,待 owner 推送**) |
| v1.8 | W2/W3 实现落档:①**SSH key 已登记,远端切 SSH 并推送成功**(feat/plate-s1@b09c4c99 + tag ext-unify-b2-6 上远端);②W2:`SubscriptionDialog`(摘要/读写高亮/订阅与重新确认共用)+ IntegrationCenter 订阅/退订/暂停恢复入口与三新暂停态文案 + FunctionCard 未订阅订阅入口、待确认/本人暂停恢复入口 + WorkbenchView 加卡标注 + **后端补 G-E(delete_task → notify_subscribers 通知持有人)**;加卡确认入口落位为卡片首渲染引导(实现口径小偏差已记);③W3:凭证角标五处统一可点 → `/auths?q=缺失别名`,Auths ?q 预填;④浏览器走查移收尾批(新后端未部署);前端 vitest 1283/154 文件全绿、vue-tsc 零错;W1–W3 合并提交 |
