# 外部接口定义归一 plate(工具定义)· 改造方案(v1.0 定稿)

> 日期:2026-10-18　代码基线:`feat/plate-s1 @ 03d46b4`(相对 e6db1591 仅文档提交;本版所有代码事实逐项核实)
> 状态:**v1.0.1 —— 批0-批4 全部交付(2026-10-19,tag ext-unify-b0/b1/b2/b3/b4-done);活体验证记录见 claude/batch4-livetest-2026-10-19.md,悬置项已关闭。原 v1.0 定稿 —— 机制路线重写(v0.9)+ 补全与三轮自评审(v0.9.1)+ 外部评审三轮全量吸收(v0.9.2/v0.9.3)+ 未覆盖面全量排查与三轮复审(v0.9.4)+ 第四轮验收评审与全量整理(v0.9.5)+ 第五轮:声明域/记录域分离、派发链回写、P-5 口径改为形状哈希(v0.9.6)+ 第六轮验收 2 P3(v0.9.7)+ 第七轮:分类器 INVALID+reason、前端记录域落点(v0.9.8)+ 第八轮:错误承载与分流位置精化(v0.9.9)+ 第九轮:resolve 域归属与 reason 转发(v0.9.10)+ **owner 决策轮:P-3/P-4/P-5/P-6 全部拍板,§8.2 清空(v1.0 定稿)**。外部系统由「`ext:` 内联执行 + 漂移检测」改为「plate 锚点 + 保留 ref `integration`,与被测系统同路径」。全部决策项已定(§8.1 D-A~D-O;§8.2 清空,D-N 含批0 盘点⑤复核检查点)。**批0 可立即排期;批1 待批1 小设计按本版重写后开工(P-5 已定 `shape_hash` 聚合、P-6 已定 422,小设计无待拍板项)。**
> 红线:本方案自带清理承诺(§5)与守门机制(§6)—— 反转而不清理 = 重蹈覆辙
>
> 核心口径(全文由此展开):
> 1. **第三方系统在 plate 声明 `kind: integration`,不发版**;
> 2. **场景用与被测系统相同的 plate 锚点引用它,`meta.plate` 对它声明保留值 `integration`**;
> 3. **执行与判定同源**(`/convert` 重投影),场景不存内联副本,因而不存在漂移;
> 4. **其余全部沿用被测系统的现有路径**(只读闸、服务实例解析、别名、编排、执行记录);
> 5. **整套设计只新增一个字段**(`ServiceDefinition.kind`),其余均为现有字段取值扩展、视图透出或现有校验加条件。

---

## 0. 背景

### 0.1 决策链(唯一口径)

| 时点 | 决策 | 落点 |
|---|---|---|
| 2026-10-08 架构设计 G6 | 外部系统进 plate(`ServiceDefinition.kind`) | 《GIMBAL-外部系统集成架构设计》§详细设计 1 |
| P1.0 拍板 | external 不进 plate | X1 设计 §1 引 |
| 2026-10-12 X1 登记 | 目录的家 = 平台新表 `external_endpoints` | `external-interface-registry-design.md` |
| 集成线 P2/v2 | 沿用平台目录;I4 两边各补一份 query_safe | 两份集成线文档 |
| 2026-10-16 本方案 v0.1–v0.8.1 | 定义源归一 plate;外部照常 release、`ext:` 内联执行、漂移检测兜底 | §9 |
| **2026-10-16/18 本方案 v0.9–v1.0** | **机制重写**:不发版 + `integration` ref + plate 锚点,与 sut 同路径 | 本版 |

### 0.2 反转依据(经代码核实)

1. 外部 `query_safe` 在闸上从未生效:`integration_runner.py:116-134` 内联 method 优先,真实 `ext:` 步骤必带内联 method,目录 query_safe 读不到;
2. 只读闸双分支(plate 锚点 / `ext:` 锚点两路两源);
3. 消费面双实现(契约视图对 `ext:` 另一套组装;平台自持 schema→declarations 转换);
4. 治理双动作(admin 登记页审计 vs plate repo 纪律);
5. 别名级目录双份定义(平台目录按 alias_name 键)。

### 0.3 为何重写机制

v0.2 起「外部照常 release」的依据是「plate 只服务冻结构件,读工作树 = 第三种服务模式」。**经核实不成立**:plate 本就把 working 作为正式服务模式(`routes_grammar.py:61-67`;平台 `plate_client.get_endpoint_full` 默认读 working 带缓存)。前提一倒,`ext:` 内联执行带来的整串补丁(漂移检测、形态匹配器、三条件闸、重填按钮、锚点名映射、导入重锚定外部分支)都失去存在理由 —— 让外部系统走 sut 的现有路径,只在「版本声明」这一个现有控制点上区分即可。

### 0.4 成立条件

**带清理**(§5)、**带守门**(§6)、**有增量收益**(P7/P9 工具定义地基;平台未上线,成本最低时点)。

---

## 1. 目标形态与边界

> **边界:plate 管「接口是什么、调用形态、是否 query_safe」;平台管「以谁的身份、用谁的凭证、什么时候跑」。**

### 1.1 目标形态总表

| 层 | 归属 | 说明 |
|---|---|---|
| 定义注册 | **plate** | 写 `systems/<系统>/`,`gimbal:system` 声明 `kind: integration` → 评审 → 合入;**不发版** |
| 定义生效 | plate 重启 | working 注册表在启动 lifespan 中加载(`http/app.py:33-41`);平台侧再等缓存 TTL;**此为对版本边界原则的有意例外**(§1.3) |
| 场景引用 | plate 锚点 + `meta.plate[系统] = integration` | 与 sut 同一锚点语法 |
| 执行 | `/convert` 重投影 | `integration` 走 working 注册表分支;场景不存 method/path,**无副本、无漂移** |
| 服务实例 | 平台别名 | 与 sut 同:按步骤 `call.service` 精确匹配别名名;优先级 显式绑定 > 场景声明 > 别名 base_url |
| 执行记录 | `plate_pins`(现有) | **测试执行与图执行**中 integration 系统记 `integration@<定义标识>`(§1.5,标识形态 = `shape_hash` 聚合(D-L);**该值只是记录值,不得作为声明写回场景或执行副本**,§1.4);**集成任务不入执行记录**(2026-10-08 决策),不记追溯,当前加载标识经 `/healthz` 查询 |
| 安全声明 | plate | 接口级 `query_safe`,仅平台模式硬约束 |
| 安全执行 | 平台,按身份模式 | 平台模式 = 现有只读闸;个人模式 = 读写均可 |
| 身份与环境 | 平台别名 | base_url/凭证只在 `service_aliases` |

### 1.2 系统侧:`ServiceDefinition.kind`(唯一新增字段)

- **位置**:`system.md` 的 `gimbal:system` 块(`ServiceDefinition`);
- **取值**:`sut`(**模型缺省**)/ `integration`;`extra="forbid"` 下须在模型显式声明;
- **必要性**:编排选单分组、`meta.plate` 双向校验、plate check 规则、别名一致性、sut 专属展示面过滤都需要系统侧标记;无法从现有信息推导(当前无 `line` 的系统只有 `common`,且「无 `line`」也可能是尚未声明版本线的 sut);现有字段语义均不合适 —— frontmatter 上的 `line_scheme` 约束 `line` 值的格式,`line` 是版本线本身,frontmatter `type` 是方言分派键,`gimbal:system` 的 `version` 是部署版本信息;
- **粒度**:字段在服务级声明,但 `meta.plate` 以**系统**为键 → **同一系统内所有服务的 kind 必须一致**(plate check 规则 1);系统 kind = 其服务的共同 kind;
- **为何放 `gimbal:system` 块而不放 `system.md` frontmatter**(防后人「顺手简化」):放 frontmatter 可省掉规则 1 与 `SystemView` 派生,但 frontmatter 从不进注册表 —— loader 只把 `gimbal:system` 块载入为 `ServiceDefinition` 并经视图透出(`loader.py` `_load_system_md`:`declare_system` 只存系统 id,`register_service` 载块),frontmatter 仅供校验与发版读取。放 frontmatter 须新铺「loader → 注册表 → 视图」通路,比规则 1 更重。规则 1 是该摆放的必要代价,不是冗余。(注:「放 frontmatter 会触发 M2 代际升级」不成立 —— 版本线字段即以「P8 加法字段、全部可缺省」加入 frontmatter 而未升代际,`dialect/models.py:258`;`M2_VERSION` 是 release 清单常量比对、`M2_GENERATION` 只管生成的 `_m2.py`,均不因方言模型加字段自动触发。)
- **透出**(均为视图透出,非新概念):`ServiceView.kind`、`SystemView.kind`(派生)、**`EndpointView.kind`**(端点所属服务的 kind,§3.1;端点级是平台重度消费面的实际数据源,消费方零 join);
- **存量**:三个存量系统不改;已发版构件冻结的是原始 dict(`release.py:593-596`),哈希不变,回读取缺省 `sut`(`read.py:169`);
- **代际:不升任何代际**。`ServiceDefinition` 属「M1/框架(非 M2)」(`schema/__init__.py:65-70`),加法字段为兼容变更。误升后果:用例侧 `M2_GENERATION` 只升 plate 一侧 → 执行全撞 `M2_GENERATION_MISMATCH`;知识侧 `M2_VERSION` → 已发版修订全部 `RELEASE_M2_INCOMPATIBLE`。**同批把 `service_definition.py` docstring 的「M2 不可变域」改为与 `__init__` 一致。**

### 1.3 不发版及其连带

- integration 系统**不得声明任何版本线字段**(plate check 规则 2,版本线字段在 `system.md` frontmatter);无 `line` 时 `release.py:427` 天然拒绝发版;
- **由修订驱动、自然不触发的面**:版本边界(`not_in_revision` 复核、`version_undeclared` 闸)、`working_preview`、基线冷化 —— 均以修订或钉定 ref 为前提(批0 钉测试证明);
- **必须显式跳过的面:适配**。`adaptation_service.py:1186/1290/1557` 以 `meta_plate.get(sys) or "working"` 作起点,**working → 目标修订的适配是现有能力**;integration 若不跳过,会把 `"integration"` 当线名进 plate diff → `release_not_found`。§3.2 的「适配跳过 integration 系统」是必要改动;
- 评审保证由「发版闸」改为「合入闸」:integration 系统主分支**不得有 `review: draft` 块**(plate check 规则 3;执行点见 §1.10);
- **对版本边界原则的有意例外**:plate 既定原则(2026-10-10)是「某系统发生版本变更即为版本边界,涉及该变更的用例执行应阻断」。integration 系统无版本,定义改动在 plate 重启后**直接作用于全部引用场景、不阻断** —— 这是第三方「恒取当前定义」语义的必然结果(第三方 API 的变化不由我们控制,阻断只会让集成任务全停),**不是漏洞,不得按版本边界原则「补」阻断**;对应保障是合入闸(禁 draft + git 评审)与执行记录追溯(D-J)。

### 1.4 场景引用:保留 ref `integration` 与双向绑定

- **ref 语法与声明域合法集(分开表述,消除既有歧义)**:ref 语法(取数域全集)由三种扩为四种:`<line>#<n>` / `<line>` / `working` / **`integration`**;**声明域(`meta.plate`)合法集只有三种:`<line>#<n>` / `working` / `integration`** —— 裸 `<line>` 是取数域形态(`?ref=<line>` 装载该线最新快照,`routes_grammar.py:61-67`,现役特性,不得破坏),作为声明则平台侧历来强制 `#`(`validate_meta_plate_refs` 现状)、且**测试执行路径今天就会拒它**(派发链对非 working 声明调 `resolve`,`resolve_effective` 开头即要求 `parse_ref` 结果为 revision,裸线 → `invalid_ref`,`read.py:365-368`)——「plate 照收」只发生在绕过 resolve 的路径(主要是集成任务,`integration_runner.py:533` 直调 `/convert`);本版起 **plate 声明闸对裸线声明对齐拒**(422,reason `missing_revision`),消除「平台拒、plate 收」的双口径;批0 盘点存量裸线声明场景(§3.5⑥,影响面 = 被集成任务引用的裸线场景),非空则批3 随迁移改写为 `<line>#<n>`;
- **ref 的语义分类**(写明以防消费点重新发明 `== "integration"` 特判):`<line>#<n>`、`<line>`、`working` 是**版本选择器**,回答「读哪个版本」;`integration` 是**定义源声明**,回答「此系统无版本、恒取当前定义」。两类混装于同一命名空间是四种候选里最优解(反转测试:让 integration 系统声明 `working` 会使语义随 kind 静默漂移、预览判定被迫 kind 感知、场景失去自描述),张力由分类器单点收口消化;
- **ref 类别分类器为唯一原语**:plate 侧 `parse_ref` 返回类别;平台侧 `run_semantics.ref_category(ref)` 与之对称(平台与 plate 分进程不可 import,以契约测试锁定两侧分类表一致);「是否按当前定义读取」等谓词退化为分类器上的便利函数;**分类分两个域,非法写法返回 `INVALID` 带原因,不得混用、不得在分类器之外另立判断**:
  - **声明域**(`meta.plate` 声明、执行副本、`/convert` 入参;**resolve 动作的入参同为声明,错误域 = 声明域(D-O:422)**):合法类别 `{WORKING, INTEGRATION, PIN}`;非法返回 **`INVALID` + reason ∈ {`record_value`, `missing_revision`, `malformed`}** —— `record_value` = `integration@<任意>`(看似「钉住第三方某一版」,实际 plate 仍按当前定义执行,放行即构成伪钉定);`missing_revision` = 非 working、无 `#`、非 integration(裸线);`malformed` = 其余形状非法(如 `#` 后非数字)。平台声明域入口三种 reason 全给;
  - **记录域**(`plate_pins` 及其下游:执行台账、趋势签名):值形如 `integration@<标识>`,分类器将 `integration@` 前缀归 INTEGRATION;执行台账比对正是拿记录值对声明值(§1.5),只认裸值则台账修法无法落地;**前端的记录域判定落在 `types/plate.ts` 的判定函数**(§3.3/§6.3,与后端共享样例 fixture 锁定);
  - **plate `parse_ref` 的分域规则(不改返回值形状,非法继续以异常表达)**:`parse_ref` 现契约即**抛** `ReleaseReadError("invalid_ref", …)`(`read.py:58-61`,调用方 `_registry`/`reproject`/`resolve_effective`/diff 等,改成返回值全要跟着动)—— 批1 只做两件事:①`integration@…` 加入抛出条件并**给异常附 reason(`record_value`)**;②现有「`#` 后非数字」抛出补 reason(`malformed`)。**裸线保留 line-kind 返回**(取数域现役特性);`missing_revision` 是声明域政策,由 **plate 声明闸**给出(判据:`parse_ref` 返回 line-kind 而声明域不接受)。**`INVALID` 枚举只存在于平台 `ref_category`**,plate 侧无此返回类别;
  - **落点**:平台 `ref_category` 提供声明域分类与记录域分类两个入口(同一函数的两个模式或两个便利函数,在既有模块内,不新增模块);**`plate_client` 等消费方按分类器返回的 reason 映射文案,不得自带前缀/形状字面判断**(v0.9.7 曾指导预检「按前缀识别」—— 该写法会被门禁③的前缀分支拦下,且构成 record-value 检测的第二处实现,违反 §6.2 第 1/3 条,本版订正);导入方向已核实:`run_semantics` 对 `plate_client` 为**函数内延迟导入**(`run_semantics.py:72-73`),`plate_client` 模块级调 `ref_category` 无循环导入(v0.9.2 §3.2 对 `:777` 改调分类器已预设此依赖);
  - **契约测试只锁声明域分类表**(两侧必须一致,**含非法行与 reason 码**:合法行 `{working→WORKING, integration→INTEGRATION, line#n→PIN}` + 非法行 `{integration@x→INVALID(record_value), 裸线→INVALID(missing_revision), 线#abc→INVALID(malformed)}`;plate 侧的「非法行一致性」以其抛出/声明闸拒绝的 reason 为准);**错误承载不新增错误码**:错误码沿用现有 `invalid_ref`(`envelope.py:33`),reason 放 `ErrorPayload.details.reason`(`envelope.py:46`)——「在已有字段上扩展」;**HTTP 状态码分域**:取数域沿 `_READ_ERROR_HTTP`(`routes_grammar.py:117`,invalid_ref → **400**)的状态码映射不动、**仅补 `details.reason` 转发**(§3.1 `_read_error` 行 —— 现只带 code+message,异常附了 reason 响应体也看不到),声明域(声明闸、`/convert`)返回 **422**,resolve 动作同为 422(D-O);三条路径 reason 一致;文案一致性靠 reason 码契约(分进程不共享文案串):plate `/convert` 422 与平台预检各自按同一 reason 表映射,用户两侧看到的口径一致;记录域识别是平台单侧逻辑(后端入口 + 前端 `types/plate.ts` 函数),由平台单测与前后端共享样例覆盖,不进 plate 契约测试——否则契约测试会反过来要求 plate 接受追溯态声明;
- **plate 侧**:`parse_ref`(`read.py:51-62`)增加 `integration` 类别,与 `working` 同列保留字;禁止任何版本线取名为该词;**全域非法(`integration@…`、形状非法)抛 `invalid_ref` 附 reason(record_value / malformed),返回值形状不变**;**声明闸对裸线声明返回 422 `missing_revision`**(§1.4 首条);plate 内其余按 ref 分支的位置(`reproject.py:83-107`、`routes_grammar.py` 各按 ref 读取路由与 `_needs_root:1381`)统一依据 `parse_ref` 的类别判断,不再散写字面量;
- **ref 解析失败映射为可读 4xx(仅声明域)**:现状 `reproject_raw` 内 `resolve_revision` 抛出的 `ReleaseReadError` 不在 `/convert` 捕获范围(`routes_grammar.py:1389` 只捕 `ReprojectError`),落全局 handler 变 500;批1 在 `/convert`(声明域)映射为 **422 + `invalid_ref` + `details.reason`**;取数路由**状态码不动**(沿 `_READ_ERROR_HTTP` 的 400,仅补 reason 转发)—— 「预检失败并提示,不静默」的直接要求;
- **双向绑定**:`integration` 只能用于 kind=integration 的系统;integration 系统只接受 `integration`(不接受修订、线、`working`);
- **单一实现在 plate**:规则落在 plate 声明闸(`routes_grammar.py:1350-1370`,`/convert` 必经);平台保存端 `validate_meta_plate_refs`(`plate_client.py:764-800`)现状对非 working 声明强制 `#`(`:777`),改为:`integration` 声明经 plate `SystemView.kind` 校验后放行;**错误文案一律按分类器的 reason 映射,本体不做前缀/形状字面判断**(`record_value` →「是执行记录值,声明只能写 `integration`」;`missing_revision` → 缺修订号;`malformed` → 形状非法)——错误映射属平台声明职责,规则口径以 plate 为准;
- **不是预览**:`run_semantics` 的预览判定只认 `working`,`integration` 不计为预览,也不受「声明 working 的场景拒绝触发集成」约束;
- 系统不在 plate 当前注册表 → 预检失败并提示,不静默;
- **双向绑定兼任「kind 不可随意变更」的执行点**:sut 系统若被改为 integration,引用它的钉定场景声明 `<line>#<n>` 即被拒,响亮失败;无需另设依赖构件根的 check 规则(plate check 入口 `validate_system_tree` 拿不到构件根,`validation.py:869`)。

### 1.5 执行、服务实例与执行记录(与 sut 同路径,已核实)

- plate 锚点步骤只存 `endpoint` + `call.{service, headers, path_params}`;binding 派生字段不落库,`/convert` 按声明 ref 重投影;
- `binding.auth` 经重投影透传到执行器 `Call.auth`(`_m2.py:49-54`);signer 不新增声明,custom 缺省 `md5sign`,第二签名器随 P4 再议;
- **服务实例**:按步骤 `call.service` **精确匹配别名名**解析 base_url 与凭证(`service_aliases.base_urls_for`,`:238-257`;`credential_aliases_for` 同形);优先级唯一组装点 `run_materialize._apply_services`(`:100-107`);集成任务同经运行方案 `serviceBindings`(`integration_runner.py:485`);
- 加步骤时 `call.service` 缺省 = plate 服务名(与 sut 同);要让它直接解析,须有**服务级默认别名**(`alias_name == 服务名`,与 sut 惯例同,`ServiceAdmin` 的「服务级默认行」);其他实例经编排器逐步骤切换 `call.service`(`CaseComposerCanvas.vue:1992-2014`)或运行方案显式绑定 —— **选实例与选接口解耦,无需先选别名**;
- **执行记录(范围:测试执行与图执行)**:`run_dispatcher.py:1648-1658` 对非 working 声明调 `plate_client.resolve` 取生效修订写入现有 `plate_pins`;`integration` 进入同一调用,plate `resolve` 对其返回 `effective = integration@<定义标识>`(扩展现有响应取值,无新字段;**分流位置见 §3.1 resolve 行 —— 须在 `resolve_effective` 之前**,`read.py:365-368` 开头即要求 revision,不前置分流 integration 会被直接拒);定义标识在 plate 启动 lifespan 中计算并记录(现 `app.state.snapshot_label = "working"` 处,`app.py:33-41`),并经**现有 `/healthz` 端点**(`app.py:137`)透出,供手册「变更语义」核对 —— 扩展现有端点,不新增路由;
- **派发链回写须按类别分流**:`run_dispatcher.py:1653-1658` 现对 `resolve` 返回的每个 `effective` 同时写 `plate_pins[sys_]` 与执行副本 `meta_plate[sys_]`(注释「`/convert` 按原值取修订」)。对 PIN 这是必需的(执行副本钉到具体修订);对 INTEGRATION **只写 `plate_pins`,执行副本保持声明值 `integration`**——`integration@<标识>` 是记录值,写进执行副本后 `/convert` 按声明域校验必然 422(§1.4),整条含 integration 的测试执行失败。改法:回写前取 `ref_category(eff)`(记录域),INTEGRATION 跳过执行副本回写;判据走分类器,不写 `eff.startswith("integration@")` 字面量(门禁③的 `integration@` 前缀分支会拦,§6.3);
- **集成任务不在 D-J 覆盖范围**:集成任务经 `integration_runner.py:533` 直调 `/convert`,不经 `resolve`;实例只保留最近一次状态,**按 2026-10-08 决策「集成执行记录不放入执行记录」不另设追溯**(`last_outputs` 是卡片用户输出,不混入系统元信息);需要核对时查 `/healthz` 当前加载标识 —— 已知边界(§6.4);
- **执行记录的下游消费须按 ref 类别解读**:执行详情修订台账(`Executions.vue:377-380`)以当时 `plate_pins` 与场景当前声明逐字比对判「不可对比」,趋势签名(`routers/scenarios.py:362`、`useScenarioRuns.ts:96`)按 `系统#值` 拼接判「修订切换」。integration 的当时值 `integration@<标识>` 与当前声明 `integration` 字面恒不等 → 每次执行都会被误标「不可对比」。批2 改为:台账对 integration 类别不做字面比对——**类别判定用 `types/plate.ts` 的记录域判定函数**(§1.4/§3.3;后端 `ref_category` 在前端够不着,组件内散写前缀判断会被门禁③拦;台账的「跳过比对」与「第三方实时定义」标注共用该函数);展示当时标识,标注「第三方实时定义」;趋势签名保留标识、只拼接不分类,不受影响(标识变化即定义变化,切换标记有意义 —— 前提是标识只随该系统定义变化(D-L));
- **图执行链同理**:`_g_pins`(`run_dispatcher.py:1269-1270`)不经 `resolve`、直接取图物化后的 `meta_plate`,现状会把 integration 记成裸值、丢失标识;在该点对 INTEGRATION 补调 `resolve`,结果只写 `_g_pins`(§3.2);
- **只有追溯类调用点让 `integration` 进入 `resolve`**(派发链 `run_dispatcher.py:1648/1655`、图执行台账 `:1270`,§3.2);钉定收集类与落库写路径严禁(`_bump_verified_to_effective` 等,分类器 `PIN` 自然排除);
- 执行器零改动:不引用 `ServiceDefinition`;`Meta.plate: Dict[str, str]`(`_m2.py:163`)可承载 `integration`,不据此分支。

### 1.6 别名与服务名解析

- 平台别名 `kind`(`plate|external`,现有字段)保留;一致性映射 **`plate ↔ sut`、`external ↔ integration`** 写死在一个校验函数(入台账);
- **外部别名 `base_service` 显式选择**(下拉按 kind 过滤),校验 ①服务存在于 plate 目录 ②kind 一致;不派生、不约束命名(alias_name 是主键且被场景 `call.service` 引用,改名代价不成比例);`service_aliases.py:92-96` 的 external 分支改为「不派生,接收并校验」;
- **sut 过滤的唯一出口在别名创建时的 sut 派生点**(`service_aliases.py:97-100` 的 sut 分支对 `derive_base` 传入 sut 子集),防止 `jira-prod` 之类 sut 别名派生到 integration 服务;sut 子集的数据来源 = `plate_client` 唯一访问件的**扁平名视图(带 kind)**(§3.3),派生点在调用处取子集;`catalog_service_names` 的全量名集合不变;
- **`service_names.catalog_service_names` 本身必须保持全量,过滤不得下沉到它**。其六个消费方中:
  - 别名存在性/分类校验(`service_aliases.py:97-100` 的全量用途)、导入映射校验(`scenario_import.py:361/481`)、导入重锚定(`endpoint_anchoring.py:95`,§3.3 外部裸调用重锚定依赖它)—— **须全量**;
  - carry 三处(`routers/carry.py:120`、`carry_injection.py:111`、`carry_store` 经端点清单)—— 按 D-M 落地(覆盖,别名表优先)。注意:carry 现以运行时 `derive_base` 按 `<服务名>-<后缀>` 规约推导基名,这本身是 `base_service` 之外的第二套映射,且与「外部别名不约束命名」(本节第 2 条)冲突 —— `corp-jira` 之类名字推导不出;D-M 取「覆盖」,别名表优先即为**必须**而非偏好;
- `patch_alias` 增加:设置 `base_service`(仅 external);kind 由 external 改为 plate(仅当所指系统已是 sut,支撑 §1.8 升级)。

### 1.7 编排器(D-F)

- 接口选单按端点行的 `kind`(§1.2 `EndpointView.kind`)分「被测接口 / 第三方集成」两组;编排目录直拉 plate `/api/endpoint`(`CaseComposerCatalog.vue:445`)与平台 `/api/endpoint-catalog/list` 的行均带 `kind`;
- 选中第三方接口:走**现有**加步骤流程,并自动写入 `meta.plate[系统] = integration`;
- 版本声明下拉(`CaseComposerMeta.vue:108-118`):integration 系统只显示固定项「integration · 第三方实时定义」;系统加入时默认声明(`:214-223`)按 kind 写 `integration`;
- 目录读取(`CaseComposerCatalog.vue:445-485`):`integration` 按 working 结果列出;
- 步骤徽标(`CaseComposerCanvas.vue:674-689`):「第三方 · 实时定义」;W11 三态中「外部·无版本」随 `ext:` 退役调整。

### 1.8 入库标准与升级路径

- 入库标准(版本模型 §4.3,执行记录 `baseline_eligible/block/evidence`):integration 锚点**归入现有 `external` 桶,不计入**;不扩 `baseline_block` 取值、不额外记证据;
- 实现 = `assess_baseline` 在按修订查评审**之前**短路。现状拿 `"integration"` 会走到 `revision_objects`,抛未捕获的 `PlateRejectedError(invalid_ref)`(`plate_client.py:732-735`),而非分桶结果 —— 批2 验收须含「sut 钉定 + integration 混装场景」用例,证明短路先于该异常;
- **需要可信 = 已成为被测对象 → 原地转为 sut**:

| 方向 | 规则 |
|---|---|
| integration → sut | **允许原地转换**:改 `kind: sut`、声明 `line`、发首个修订;发版前引用场景可暂声明 `working`;发版后改钉修订(即「进入被测范围」的确认动作);别名经 `patch_alias` 改为 plate |
| sut → integration | **禁止**(有发版记录时),须换新系统名;由 §1.4 双向绑定在使用时强制 |

### 1.9 明确不做

- 外部端点不挂取数视图(D-D;plate check 规则 4 编写侧强制);
- CLI 导入器不提前(挂 task 5);
- 不做 plate 热加载;
- 不新增 signer 声明。

### 1.10 plate check 规则(全部挂系统树校验区)

均挂 `validate_system_tree` 的系统级校验(与 F5 同区:该处持有 `system.md` frontmatter、`gimbal:system` 服务集与系统内全部端点)。**不挂 `EndpointSpec` 校验器**——`dialect/models.py:227` 的 query_views 护栏在单端点模型内,拿不到系统 kind。

1. 同一系统内所有服务的 `kind` 必须一致;
2. kind=integration 不得声明版本线字段(frontmatter);
3. integration 系统主分支不得有 `review: draft` 块。**执行点**:起草期出现 draft 是正常状态,故在 `validate_system_tree` 内为 `warning`(给编写反馈,不阻断本地 check);合入闸由 **`tests/plate` 下一条 pytest 用例**承担 —— 扫描 `systems/` 中 kind=integration 系统,存在 draft 块即失败;该用例随 `verify_all.sh` 第 1 步(`gimbal+plate pytest`,`:48`)运行,任何分支合入前必过(`verify_all` 现不跑 `plate check`,不能依赖 check 作合入闸)。复用现有测试与 CI,不新增工具;
4. integration 系统的端点不得声明 `query_views`。

---

## 2. 安全模型

### 2.1 只读闸(平台模式)

- 现有闸的 **plate 锚点分支**即可覆盖:方法取自定义 `binding.method`,非安全方法须 `metadata.query_safe=true`(`integration_runner.py:136-146`);判定与执行同源,**三条件闸不再需要**;
- 该分支对 ref 的判断(`:137`)改经 §1.4 分类器(读取类,§3.2);
- `ext:` DB 分支(`:119-134`)删除(批2);
- 调用点不变:保存 `routers/integration.py:189` + 执行前 `integration_runner.py:462`(同函数两时点)。

### 2.2 个人模式

不按 `query_safe` 拦截;边界 = 用户本人在第三方系统的权限(手册写明)。

### 2.3 可用性

- plate 不可达:沿用现有 fail-closed 出口(`integration_runner.py:465-467`);
- 外部步骤执行经 `/convert`,**与 sut 同等依赖 plate**(v0.8.1「外部执行不依赖 plate」的特性不再,换来两类系统口径一致);
- 平台缓存 TTL 沿 `DECLARED_PATHS_TTL_SEC` 先例,即 query_safe 撤标在平台侧的最迟生效上界。

---

## 3. 现状与改动面

### 3.1 plate 侧

| 触点 | 改动 | 批 |
|---|---|---|
| `schema/service_definition.py` | 加 `kind`(缺省 `sut`);docstring 更正 | 1 |
| `http/views.py` | `ServiceView` 显式加 `kind`;`SystemView` 加派生 `kind`;**`EndpointView` 加 `kind`**(三者均 `extra="forbid"`,须显式声明;端点 kind 经 `registry.system_of_service`/服务定义取得);`ServiceDetailView` 经 `extra` 自动透出 | 1 |
| `/api/endpoint`(全局与系统作用域)、`/api/service` | **全量返回,行带 `kind`**(不得过滤,§3.4) | 1 |
| `release/read.py` `parse_ref` | 增加 `integration` 类别;线名禁用该词;**全域非法继续抛 `ReleaseReadError(invalid_ref)` 并附 reason(`record_value`:`integration@…`;`malformed`:`#` 后非数字 —— 后者为现有抛出(`:58-61`)补 reason),返回值形状不变、调用方零改动**;裸线保留 line-kind(取数域) | 1 |
| `release/reproject.py`、`routes_grammar.py` 按 ref 分支处 | 依 `parse_ref` 类别处理,`integration` 走 working 注册表 | 1 |
| `_read_error`(`routes_grammar.py:124-127`) | **转发 `details.reason`**:现只带 code+message,异常附 reason 后**取数路由与 resolve 的响应体里看不到** —— 一行改动把 `reason` 带进 `ErrorPayload.details`;状态码分域不变,reason 在取数 / resolve / `/convert` 三条路径一致(若不转发,须在文档注明前两条路径的响应不带 reason) | 1 |
| `routes_grammar.py:1350-1370` 声明闸 | 加双向绑定;**加声明域合法集校验(裸线 422 `missing_revision`,§1.4)**(`ext:` 豁免的删除归 C12,批3) | 1 |
| `routes_grammar.py:1389` `/convert` | `ReleaseReadError` 映射 **422 + `invalid_ref` + `details.reason`(声明域;取数路由沿 `_READ_ERROR_HTTP`(`:117`)保持 400,仅补 reason 转发 —— 见 `_read_error` 行)**;**错误码沿用现有,不新增 ErrorCode** | 1 |
| `resolve` | **integration 在调 `resolve_effective` 之前分流**(`read.py:365-368` 开头即要求 `parse_ref` 结果为 revision、否则 invalid_ref —— 不前置分流 integration 会被直接拒),返回 `effective = integration@<定义标识>`(形态见 D-L);入参 `integration@…` 按非法声明拒绝;**错误域 = 声明域(D-O):异常出口改用声明域映射返回 422**(现经 `_read_error`(`:1242`)返回 400;平台侧对 4xx 统一 `PlateRejectedError`(`plate_client.py:465/489`),状态码变化无行为影响) | 1 |
| `http/app.py:33-41` lifespan + `/healthz`(`:137`) | 计算并记录各 integration 系统的定义标识(D-L:系统内各端点 `shape_hash` 的聚合哈希,聚合函数放既有 `dialect/canonical.py`);扩展现有 `/healthz` 响应透出(沿 `m2_pool` 先例,`:140-142`),不新增路由 | 1 |
| `validate_system_tree` 系统级校验(与 F5 同区) | §1.10 四条(规则 3 为 warning) | 1 |
| `tests/plate` | 新增「integration 系统无 draft 块」pytest 用例(规则 3 合入闸,§1.10;`test_http_health.py` 等同类用例可承载 `/healthz` 断言) | 1 |

### 3.2 平台后端:`"working"` 判断点 → ref 类别分类器

实测(`03d46b4`)`run_semantics.py` 之外共 **24 处**判断点(注释与 docstring 4 处不计;`run_semantics.py` 内 2 处为常量定义与预览返回,属门禁放行区)。调用点真实要问的是**五种**不同的问题,一个布尔谓词回答不了 —— v0.9.1 的「谓词 + 例外」即其证据。改为全部经 §1.4 分类器 `ref_category` 判断:

| 问题 | 判据 | 处数 | 位置 | 说明 |
|---|---|---|---|---|
| **读取**:读当前定义还是读修订? | `{WORKING, INTEGRATION}` → 当前定义;`PIN` → 修订 | 10 | `endpoint_declarations.py:210`、`endpoint_anchoring.py:143`、`carry_injection.py:47`、`plate_client.py:777`、`integration_runner.py:137`、`routers/endpoint_catalog.py:60/138/308`、`adaptation_service.py:1692`、`scenario_import.py:246` | `plate_client.py:777`(`validate_meta_plate_refs`)对 `INTEGRATION` 另走 §1.4 的 kind 预检,对 `INVALID` 按 reason 映射文案 |
| **钉定收集**:是版本钉定吗? | 仅 `PIN` | 5 | `suite_version.py:64/90`、`routers/suites.py:1582`、`run_dispatcher.py:827`(环境与场景版本线一致告警)、`scenario_store.py:777`(`_bump_verified_to_effective`) | 这些点对 ref 做 `split("#")[0]` 取线名或推进修订;`integration` 混入即被当成名为 integration 的线。**`_bump` 是唯一不经 `enforce_meta_plate` 改写落库 `meta.plate` 的写路径**(`:759-797`,普通保存后触发)—— `PIN` 判据自然排除 integration,杜绝「把 `integration` 改写为 `integration@<定义标识>` 落库、下次保存 422」;批0 钉测试 |
| **追溯**:要进 `resolve` 吗? | `{PIN, INTEGRATION}` | 3 | `run_dispatcher.py:1648/1655`(派发链)、`:1270`(图执行台账 `_g_pins`) | integration 经 `resolve` 取 `integration@<定义标识>` **只写 `plate_pins`**(§1.5,形态 D-L;分流位置见 §3.1 resolve 行);**`:1655-1658` 的执行副本回写对 INTEGRATION 跳过,执行副本保持 `integration`**(否则 `/convert` 422);**图执行链已核实不经 `resolve`**:`_g_pins`(`:1269-1270`)直接取 `graph_dispatch.materialize_graph` 产出的 `meta_plate`,其中钉定值来自 `check_and_resolve_suite_versions`(钉定收集类,PIN 判据排除 integration)经 `graph_dispatch.py:174-178` 回写——integration 不在 `suite_pins` 中,执行副本自然保持 `integration`(此回写点无需改),但 `_g_pins` 会记成裸值 `integration`、**丢失定义标识**;改法:在 `:1270` 对 INTEGRATION 类别系统补调 `plate_client.resolve`,结果只写 `_g_pins`,不动 `meta_plate` |
| **预览**:是预览吗? | `{UNDECLARED, WORKING}` | 2 | `scenario_import.py:314`(列出声明 working 的系统)、`adaptation_service.py:1703`(stale 原因标注「仍为预览」,含未声明) | 均改调 `run_semantics` 预览判定/分类器;`integration` 不标预览 |
| **适配**:跳过 | `INTEGRATION` → 跳过 | 4 | `adaptation_service.py:1186/1290/1557`(`or "working"` 起点)、`:1438`(推荐策略) | §1.3:working → 目标修订是现有能力,integration 不跳过会被当线名进 plate diff |

漏改多数表现为**响亮失败**(按修订取 → `release_not_found`;§1.8 的未捕获 `PlateRejectedError`);钉定收集类漏改会静默污染线名集合,故由 §6.3 ②③ 门禁兜底(字面量必须经分类器)。

### 3.3 平台后端:其他触点

| 位置 | 改动 | 批 |
|---|---|---|
| **plate 目录读取访问件收敛** | 现状三个独立访问件各带缓存:`routers/catalog.py:46`(`/api/endpoint` 聚合服务行,30s TTL)、`service_names.py:26-45`(`catalog_service_names`,`/api/service` 扁平名集)、`adaptation_service.py:52` `_plate_list_endpoints`(`/api/endpoint` 轻端点,供看板与 carry)。**收敛进现有 `plate_client`**(已是平台唯一的 plate 访问模块,不新建模块):一处取数、共享缓存与 kind 标签,三种视图形状(聚合行 / 扁平名(带 kind,供 sut 派生点取子集)/ 轻端点)分别出口;原三处改为调用它。与 §3.1 端点行带 kind 是同一动作的两面 —— 先有唯一访问件,kind 才有单一落点 | 2 |
| `run_semantics.ref_category` | 新增分类器函数(既有模块内,§1.4):**声明域**分类(合法 `{WORKING, INTEGRATION, PIN}` + **`INVALID` 带 reason:record_value / missing_revision / malformed**)+ **记录域**分类(`integration@<标识>` 归 INTEGRATION,仅供 `plate_pins` 下游);24 处判断点按 §3.2 改调,各点按所处的域选入口 | 2 |
| `plate_client.validate_meta_plate_refs` | `integration` 经 plate `SystemView.kind` 校验后放行(§1.4);**错误文案按分类器 reason 映射,本体不做前缀/形状字面判断**(v0.9.7「按前缀识别」写法会被门禁③拦下且构成第二处实现,v0.9.8 订正) | 2 |
| `run_semantics.assess_baseline` | integration 在修订评审查询前短路进 `external` 桶 | 2 |
| `service_aliases.py:92-100` | external 不派生,接收并校验显式 `base_service`;sut 分支派生候选为 sut 子集(§1.6) | 2 |
| `patch_alias` | 加 `base_service`、kind(external→plate) | 2 |
| `routers/catalog.py:44-80` 服务聚合 | 改经 `plate_client` 唯一访问件;**聚合行由端点行 `kind` 带出** | 2 |
| `routers/endpoint_catalog.py` 各 list | 透传端点行 `kind`(行形状同步) | 2 |
| `endpoint_anchoring`(导入重锚定) | `integration` 声明走现有已声明系统路径;**无声明的外部裸调用**(旧导出/手写):经 `call.service` → 别名 `base_service` → integration 系统,自动补 `meta.plate[系统]=integration` 后走现有反查(依赖 `catalog_service_names` 全量) | 2 |
| `board_assembler.py:91/197/317` | 改经 `plate_client` 轻端点视图 → **排除 integration 端点**(画像 = 被测覆盖) | 2 |
| carry 三处(`routers/carry.py:120/125/169`、`carry_store.py:94`、`carry_injection.py:111`) | 按 D-M 落地(覆盖分支:先查别名表 `base_service`,未登记裸服务键再走全量 `derive_base`;carry_store/配置面不排除 integration);**验收含「sut 场景 carry 解析结果与批0 基线一致」断言(R7)** | 2 |
| `integration_runner.py:119-134` | 删 `ext:` DB 分支(C5) | 2 |
| 执行记录下游消费(`frontend/src/views/Executions.vue:377-380` 修订台账、`routers/scenarios.py:362` 与 `frontend/src/composables/useScenarioRuns.ts:96` 趋势签名) | 按 ref 类别解读 `plate_pins`(§1.5):台账对 integration 不做字面比对——**类别判定用 `types/plate.ts` 的记录域判定函数(下行),组件内不散写前缀判断**;趋势签名保留定义标识、只拼接不分类 | 2 |
| **`frontend/src/types/plate.ts`** | 加**记录域判定函数**(识别 `integration@<标识>` pins 值;台账「跳过比对」与「第三方实时定义」标注共用);与后端 `run_semantics` 记录域入口**共享同一份样例 fixture,路径写死 `src/gimbal-platform/frontend/src/types/__fixtures__/ref-record-domain.json`**(仓库根相对;前端 vitest 就近读,后端 pytest 从测试文件位置回溯仓库根解析同一文件 —— 两侧测试运行目录不同,`verify_all.sh:51/54`,不写死路径会找不着);fixture 内 `integration@…` 字面量不命中门禁③(③只匹配比较式与 `startsWith(` 调用,JSON 的 `"key": "value"` 形态匹配不上);不需要前端版声明域分类器(编排器写常量即可,现状已是常量收口) | 2 |
| `routers/environments.py:108`(环境版本线声明写入) | 拒绝为 kind=integration 的系统声明版本线(经 `plate_client` 取 kind;现状对系统与线均不校验,本条只补 integration 一项;plate 不可达时跳过,与 `validate_meta_plate_refs` 保存端口径一致) | 2 |

### 3.4 消费面清单:sut 专属面与「不得过滤面」

**数据通路(已核实)**:平台重度消费面读的是**端点级清单** —— `routers/catalog.py` 聚合调 plate `/api/endpoint`;编排目录直拉 plate `/api/endpoint`;`adaptation_service._plate_list_endpoints`(`:53-70`)同接口,其消费方是 **看板与 carry**(`board_assembler.py`、`carry_store.py`、`routers/carry.py`),适配差异本体走 plate diff 接口(`plate_diff_for_adaptation`),不读此清单。扁平服务名集合 `catalog_service_names` 读 plate `/api/service`。三者批2 收敛为 `plate_client` 唯一访问件(§3.3)。由修订驱动的面(版本边界、基线冷化)天然排除 integration;适配须显式跳过(§1.3);其余逐面定处理:

| 面 | 位置 | 处理 |
|---|---|---|
| 服务画像落地页 | `views/ServicesIndex.vue`(`loadCatalogServiceRows`) | **只列 sut** |
| 工作台服务画像卡 | `components/workbench/ServicesCard.vue`(`loadCatalogServiceRows`) | **只列 sut**(与落地页同口径,`loadCatalogServiceRows` 一处按 kind 过滤) |
| 看板瓦片 | `board_assembler.py:91/197/317` | **排除 integration**(画像 = 被测覆盖) |
| 服务热力网格 | `views/ServiceGrid.vue` / `routers/service_profile.py` | 入口已由上三面收敛;直达 URL 不拦 |
| 服务信息管理 | `views/ServiceAdmin.vue`(`loadCatalogEntries`) | **全量,按 kind 分组**(第三方同样要配实例与凭证) |
| 别名详情 | `views/ServiceAliasDetail.vue` | `base_service` 下拉按别名 kind 过滤 |
| 编排器服务名集合 | `CaseComposer.vue`、`CaseComposerConfig.vue`、`CaseComposerCanvas.vue`(`loadCatalogServiceNames`) | **全量**(否则第三方步骤的服务引用被判「未挂目录服务」) |
| 编排器接口目录 | `CaseComposerCatalog.vue` | 按端点行 `kind` 分组(§1.7) |
| 版本声明下拉 | `CaseComposerMeta.vue` | integration 固定单项(§1.7) |
| 别名创建 sut 派生 | `service_aliases.py:97-100` sut 分支 | 只取 sut(sut 过滤唯一出口) |
| 别名校验/导入/重锚定 | `catalog_service_names` 全量消费方(§1.6) | **全量** |
| carry 快照/注入/配置面 | `carry_store`、`carry_injection`、`routers/carry.py` | **按 D-M 覆盖**(别名表优先;配置面不排除) |
| 取数视图挂载 | plate | check 规则 4 |

前端目录服务消费为 6 个文件经 `loadCatalogServiceRows`/`loadCatalogServiceNames` 两个具名函数,另 `ServiceAdmin.vue` 经 `loadCatalogEntries`(同一次拉取的模块级缓存)。

**不得过滤面**:plate `/api/endpoint`(全局与系统作用域)、plate `/api/service`、平台 `/api/catalog/services`、平台 `/api/endpoint-catalog` 各 list、`service_names.catalog_service_names` —— **均全量返回 + kind 标签,过滤只发生在消费方**。批1/批2 各加反向断言:integration 服务/端点必须出现在上述列表中。

### 3.5 存量盘点、迁移与过渡期

**批0 盘点**(空也出档):
1. `external_endpoints` 行数(预期 0,0023 注释记 2026-10-13 实测 0 行);
2. 审计表 `external_endpoint.query_safe` 行数;
3. 存量 external 别名清单及 `base_service` 现值;
4. 存量 `ext:` 锚点场景数;
5. 无锚点外部裸调用步骤数;
6. **存量裸线声明场景数**(`meta.plate` 中非 working、无 `#`、非 integration 的声明;平台 validate 历来强制 `#`、测试执行路径今天就被 `resolve_effective` 拒(`read.py:365-368`),**受影响的只有被集成任务引用的裸线场景** —— 集成任务直连 `/convert` 绕过 resolve,是唯一「照收」路径;§1.4 声明闸对齐拒的影响面)。

**迁移(批3)**:③ 非空 → 系统定义写入 plate 后,经 `patch_alias` 人工选 `base_service`;④ 非空 → 改写为 plate 锚点 + `meta.plate[系统]=integration`,经现有 `strip_binding_fields` 剥除内联 method/path;⑤ 按 D-N 维持合法(批0 盘点⑤复核,非 0 再议);**⑥ 非空 → 裸线声明改写为该线最新修订 `<line>#<n>`**(§1.4 声明闸对齐拒后为非法,响亮失败倒逼)。

**过渡期(批2 删闸 `ext:` 分支 → 批3 迁移与 C12 退役之间)**,存量 `ext:` 场景的行为:`_strip_ext_anchors` 仍在,执行照常;平台模式只读闸 —— 带内联 GET 的放行,带内联 POST 的拒绝(不再查目录,而目录 query_safe 本就从未生效,行为不劣化),无内联 method 的落入 plate 分支取不到定义 → fail-closed。平台未上线,可接受;若批0 盘点 ④ 为 0,过渡期不存在。

### 3.6 测试面(批0 特征化基线)

- 现有只读闸 plate 分支与 `ext:` 分支行为;
- 24 处 ref 判断点按类别的现有行为;**`_bump_verified_to_effective` 写路径现状**(保存后对各类声明的改写行为);
- **plate `/convert` 对裸线声明的现有行为**(照收、resolve 到线最新 —— §1.4 声明闸对齐拒前的行为基线;注意测试执行路径现状就跑不了裸线,「照收」仅集成任务路径);
- `assess_baseline` 现有分桶与异常路径;
- 执行器代际门、已发版修订回读(为「不升代际」断言打底);
- 版本边界(`not_in_revision` 复核、`version_undeclared` 闸)与 `working_preview` 现有触发条件;
- **适配 `from = working` 起点的现状**(working → 目标修订);
- 服务实例解析:`call.service` 命中服务级默认别名 / 切换到实例别名 / 显式绑定覆盖 / 无别名缺口报错;
- 导出 → 导入往返时 `meta.plate` 是否保留(决定 §3.3 重锚定自动补声明的触发面);
- **`catalog_service_names` 六个消费方现状**;**看板与 carry 的全量目录快照现状**(含 sut carry 基名解析结果样本 —— D-M 的「sut 行为不变」断言以此打底);
- `/api/catalog/services` 与端点清单的现有行形状;
- **执行台账与趋势签名对 `plate_pins` 的现有解读**(`Executions.vue:377-380`、`scenarios.py:362`、`useScenarioRuns.ts:96`);
- 已核实非问题(记录):plate 全局端点列表不分页(`per_page` 参数无效),第三方端点接入后无 500 条截断风险;
- **现存口径张力(仅记录)**:`anchored_systems`(`run_semantics.py:20-27`)不过滤 `ext:` 前缀,仅锚 `ext:` 的场景按代码会被判预览,与模块注释「external 不触发预览」相悖;本方案落地(C12)后自然消解。

---

## 4. 实施批次与验收门

每批过三侧门:后端 pytest / 前端 vitest+vue-tsc / plate pytest。依赖:批0 先行;批1 → 批2 → 批3 串行。**批1 先于批2 安全**:批2 之前平台不会写出 `integration` 声明。**P-4 已定(D-M):批2 carry 按覆盖分支落地。**

| # | 内容 | 规模 | 验收门 |
|---|---|---|---|
| **批0** | §3.5 盘点 + §3.6 基线 | S | 基线全绿;盘点档入库 |
| **批1(plate)** | §3.1 全部 | S~M | plate 门全绿;**已发版修订回读 + 两种代际未变断言**;`/api/endpoint` 与 `/api/service` 含 integration 且行带 kind 的反向断言;§1.10 四条规则正反例;`parse_ref`/重投影/`resolve` 对 integration 的用例;**`parse_ref` 非法用例:抛 `invalid_ref` 且 `details.reason` 正确(`integration@<x>` → record_value、`线#abc` → malformed),返回值形状不变(取数域 `?ref=<line>` 路由不回归)**;**声明闸对裸线声明对齐拒的正反例(422 `missing_revision`)**;**resolve 对 integration 的前置分流正反例(不前置分流即 invalid_ref)**;**`_needs_root`(`routes_grammar.py:1381`)把 integration 当 working 的正反例**(否则含 integration 声明的 convert 在无构件根时 503);**非法 ref 的状态码分域与 reason 全路径:声明域经 `/convert` 返回 422 + `invalid_ref` + `details.reason`,取数路由保持 400(沿 `_READ_ERROR_HTTP`)且响应体含 `details.reason`(`_read_error` 转发),resolve 返回 422 + `invalid_ref` + `details.reason` 正反例(D-O),**含 `integration@<x>` 作为声明的反例(消息指明是记录值)**;**不新增 ErrorCode(错误码集合不变断言)**;双向绑定正反例;`/healthz` 透出各 integration 系统定义标识;**定义标识稳定性断言:仅改 description/ui_kind 标识不变,改请求/响应声明、binding 或增删端点标识必变**;**`tests/plate` 无 draft 用例对正反样例生效** |
| **批2(平台)** | §3.2、§3.3、§3.4、§1.7 前端;只读闸删 `ext:` 分支 | M | 三侧门全绿;**`ref_category` 声明域与 plate(`parse_ref` 抛出 + 声明闸拒绝)reason 表契约测试:合法行两侧一致 + 非法行 reason 一致(record_value / missing_revision / malformed)**;**记录域单测(后端):`integration@<标识>` 归 INTEGRATION**;**前端记录域判定函数单测:读 `src/gimbal-platform/frontend/src/types/__fixtures__/ref-record-domain.json`,与后端同源(同一文件)**;**派发链回写断言:含 integration 的测试执行,`plate_pins` 记 `integration@<标识>`、执行副本 `meta.plate` 仍为 `integration`,`/convert` 成功;图执行同断言(`_g_pins` 记 `integration@<标识>` 而非裸值)**;**`validate_meta_plate_refs` 按 reason 映射断言:`integration@<x>` →「记录值」消息、裸线 →「缺修订号」、`线#abc` →「形状非法」,本体无前缀/形状字面判断**;ref 判断点按 §3.2 五问逐类用例(**含 `_bump` 写路径不改写 integration、钉定收集类不把 integration 当线名**);`plate_client` 唯一访问件三视图用例(原三处无独立取数残留);§3.4 逐面断言 + 不得过滤面反向断言;别名四项用例;D-F 分组与自动声明用例;`plate_pins` 记 `integration@<定义标识>`;**「sut 钉定 + integration」混装场景 `assess_baseline` 归 external 桶**;**carry 按 D-M 覆盖分支落地且 sut 场景 carry 解析与批0 基线一致**;**执行台账对 integration 不误标「不可对比」(经 `types/plate.ts` 判定函数)、趋势签名仅在定义标识变化时标切换(改 description 不触发)**;环境版本线声明拒绝 integration 系统;**POST 查询类第三方接口标 query_safe 后可进平台模式**(反转依据 1 闭环) |
| **批3(清理)** | §5 全清单;§3.5 迁移;0029 drop;W3 取代注记 + `docs/概念地图.md` 同批 | M | grep 门禁(§6.3)零残留;快照 fixture 真实执行 0029 |
| **批4(活体)** | 真实第三方全链路:写定义 → 合入 → plate 重启(`/healthz` 核对定义标识)→ 建服务级默认别名 → 编排(分组选接口)→ 集成任务(平台/个人各一)→ 定时 → 卡片;手册(§6.4) | S | 活体记录;悬置项两条结论入记录(§7.1) |

---

## 5. 冗余/重复设计清理清单

**纪律:下线 = 物理删除 + grep 零残留 + 文档同步;保留项防误删。**

| # | 下线对象 | 文件清单 | 批次 |
|---|---|---|---|
| C1 | `external_endpoints` 表 | `models/external_endpoint.py`;`models/__init__.py:20,51`;alembic 0021/0022/0023/0026 历史链保留,新增 0029 drop | 批3 |
| C2 | 外部目录服务 | `services/external_endpoints.py`(520 行) | 批3 |
| C3 | 登记路由 | `routers/external_endpoints.py`;`main.py:41,237` | 批3 |
| C4 | 前端登记面 + 审计动作 | `ServiceAliasDetail.vue` 登记交互;`api/external-endpoints.ts`;`auditText.ts` 保留只读映射标「已退役」(审计 0 行则删);`services/audit.py:28` | 批3 |
| C5 | 闸 `ext:` DB 分支 | `integration_runner.py:119-134` | 批2 |
| C6 | `ext:` 组装代码 | `endpoint_catalog.py:102-127`;`run_precheck.py:159-194` | 批3 |
| C7 | 重复 schema→declarations 转换 | 唯一实现在 plate | 批3 |
| C8 | 「平台目录」裁定段(文档) | 三份集成线文档 + 架构设计 §详细设计 1;文档清理 W3 承接 | 批3 |
| C9 | 一次性迁移脚本 | 批0 确认 0 行则不产生 | 批3 |
| C10 | 测试下线与改写 | `test_external_endpoints.py` 删;`test_empty_db_bootstrap.py` 表清单移除;**`test_metadata_invariants.py` 删 `ORDER_SENSITIVE` 中 `external_endpoints` 例外行(`:93`)**;`ServiceAliasDetail.ext.test.ts`/`auditText.test.ts` 随 C4;`test_query_safe_gate.py`/`test_integration.py` 的 `ext:` 段改写为 integration 用例 | 批3 |
| C11 | 活文档 | `docs/概念地图.md:17`(与批3 同提交);`runbook-pg.md:104` 历史段保留 | 批3 |
| C12 | `ext:` 特例整体退役 | `plate_client._strip_ext_anchors`(`:123-143`)及调用;`scenario_store.py:70/89` 豁免;`routes_grammar.py:1358` 豁免;`run_semantics`/`anchored_systems` 相关口径;`endpoint_ref_index.py` 的 `ext:` 行;前端 W11 依赖 `ext:` 的分支 | 批3 |

**保留(防误删)**:alembic 历史链;`scripts/fixtures/schema-snapshot-0023.sql`(增量门真实执行 0029)。

---

## 6. 防再发机制:「一个功能一个实现」守门

### 6.1 真源台账(批2 交付 `claude/single-source-registry.md`)

| 能力域 | 唯一真源 | 禁止 |
|---|---|---|
| 被测接口定义 | plate(kind=sut,修订/钉定) | 平台侧接口定义表 |
| 第三方接口定义 | plate(kind=integration,当前定义) | 平台目录表/别名级重复定义/场景内联副本 |
| 系统类别 | `ServiceDefinition.kind`(系统内一致;`Service/System/EndpointView` 透出) | 第二处类别声明/消费方自行 join 推导 |
| 版本声明语义 | `meta.plate` ref(声明域合法集:working/line#n/integration),类别判定 = plate `parse_ref` + 声明闸政策 | 第二种锚点语法/散写 ref 字面量 |
| ref ↔ kind 双向绑定 | plate 声明闸 | 平台另立规则口径(平台只预检与映射) |
| ref 类别判定(声明域) | plate:`parse_ref` **抛 `invalid_ref` + reason**(不改返回值形状)+ 声明闸声明域政策(missing_revision);平台:`run_semantics.ref_category`(与 plate 对称,**INVALID + reason,契约测试锁合法行与非法行 reason**) | 散写 `"working"`/`"integration"` 字面比较;一个谓词加例外;**把记录值 `integration@<标识>` 当声明接受或写回执行副本;消费方自带前缀/形状字面判断绕过 reason 映射** |
| ref 类别判定(记录域) | 后端 `run_semantics` 记录域入口 + 前端 `types/plate.ts` 判定函数,**共享样例 fixture(`src/gimbal-platform/frontend/src/types/__fixtures__/ref-record-domain.json`,写死路径)锁定两侧一致**;台账跳过比对与「第三方实时定义」标注共用 | 第三处实现;组件内散写 `startsWith('integration@')`(门禁③拦);plate 契约测试纳入记录域(会反向要求 plate 接受追溯态声明) |
| 非法 ref 的错误承载 | 错误码 = 现有 `invalid_ref`(`envelope.py:33`),reason = `ErrorPayload.details.reason`(`envelope.py:46`);取数域 400(`_READ_ERROR_HTTP`)、声明域 422;`_read_error` 转发 `details.reason`(取数 / resolve / `/convert` 三路径一致);resolve 动作错误域 = 声明域 422(D-O) | 新增 ErrorCode;取数路由改状态码;`_read_error` 丢弃 reason |
| `integration` 进入 `resolve` | 仅追溯类(派发链、图执行台账);结果只写 `plate_pins`;**integration 在 `resolve_effective` 之前分流**(§3.1) | 钉定收集类与落库写路径(`_bump_verified_to_effective` 等);**派发链把 integration 的 `effective` 回写执行副本** |
| sut 过滤 | 别名创建时 sut 派生点(唯一出口,数据取自 `plate_client` 扁平名视图的 kind)+ §3.4 列明的展示面 | 下沉到 `catalog_service_names` 或 plate 列表源头 |
| 服务目录 | plate `/api/endpoint`、`/api/service` → 平台 `/api/catalog/services`、`/api/endpoint-catalog`、`catalog_service_names`,全量带 kind | 源头过滤 |
| 平台读取 plate 目录 | `plate_client` 唯一访问件(聚合行 / 扁平名 / 轻端点三视图,共享缓存) | 各服务自建取数与缓存(现状三处,批2 收敛) |
| 别名 ↔ plate 系统映射 | `base_service`(外部显式,sut 派生;映射写死于校验函数) | 第二映射/别名即本体;**运行时按命名规约 `derive_base` 推导已登记别名的基名**(现存于 carry 三处,随 D-M 落地(条目保留)) |
| integration 系统无 draft 的合入闸 | `tests/plate` pytest 用例(随 `verify_all` 第 1 步) | 依赖开发者手动跑 `plate check` |
| 别名类别 `service_aliases.kind`(`plate\|external`) | **受控双轨,立合并路径**:现存职责只是在「sut 派生 / external 显式」两条解析路径间选择;若将来 `base_service` 对全部别名显式化,`kind` 变为 `base_service → plate 系统 → kind` 的纯推导值,第二词表消失。本批不做(sut 派生是现役工作流);前端 `serviceKinds`(`plate/external/unknown`)是同一词表的投影,随之合并 | 新增第三词表 |
| 服务实例解析 | `run_materialize._apply_services` | 第二处优先级裁决 |
| 执行版本追溯 | `plate_pins`(现有,范围:测试执行与图执行)+ plate lifespan 以 `shape_hash` 聚合计算定义标识、`/healthz` 透出 | 新增追溯字段;集成任务另设追溯(违反 10-08 决策);消费方对 `plate_pins` 做字面比对而不按 ref 类别解读 |
| base_url/凭证绑定 | 平台 service_aliases | plate 存环境值 |
| 执行身份/调度/订阅 | 平台 integration_tasks | plate 感知执行 |
| signer 实现 | 执行侧 `@register_authenticator` 注册表 | plate 承载执行逻辑 |
| 取数视图 | plate query_views(仅 sut) | integration 系统挂载 |
| 定时调用外部系统 | 集成任务 | 取数视图/脚本旁路 |
| query→declarations 转换 | plate | 平台副本 |
| 保存后修订推进 | `_bump_verified_to_effective` | **技术债(记账不扩 scope)**:绕过 `enforce_meta_plate` 的隐藏写路径 + `except Exception: pass` 吞异常(`scenario_store.py:281-284`);本批只做过滤改用分类器 + 批0 钉测试,重写另立 |

**规则:新表/新缓存/新转换/新字段先查台账;能在已有字段上扩展定义的不新增字段;无条目能力域评审先立条目再写代码。**

### 6.2 评审硬检查项

1. 第二真源/第二实现?(是 → 拒) 2. 两处消费走同一访问件?(否 → 拒) 3. 复制公共件而非复用?(是 → 拒) 4. 替换旧实现时删除落在哪个批?(无 → 拒) 5. 交付/取代某方案时文档状态行同步翻转?(无 → 拒) 6. 新增字段前是否确认无可扩展的现有字段?(否 → 拒)

### 6.3 CI 门禁(批3 后入 verify_all)

```bash
# ① 平台目录与 ext: 特例零残留
grep -rnE "ExternalEndpoint|external_endpoint|external-endpoints|ext_svc|_strip_ext_anchors|starts[wW]ith\(['\"]ext:" \
  src docs --exclude-dir=alembic --exclude-dir=node_modules
# ② ref 字面比较零残留(只允许 run_semantics.py 的分类器与预览判定)
grep -rnE "(ref|v|eff|declared)\s*[!=]=\s*['\"]working['\"]" src/gimbal-platform/backend/app \
  | grep -v "services/run_semantics.py"
# ③ 新保留字零散写(等值比较 + integration@ 前缀判断;后端只允许分类器;前端只允许 types/plate.ts 的常量与记录域判定函数)
grep -rnE "(ref|v|eff|declared|plateRef)\s*[!=]==?\s*['\"]integration['\"]|starts[wW]ith\(['\"]integration@" \
  src/gimbal-platform/backend/app src/gimbal-platform/frontend/src \
  | grep -vE "services/run_semantics.py|types/plate.ts|__tests__"
```

允许名单(①):`auditText.ts`「已退役」映射(若保留)、`runbook-pg.md` 历史段。③与②对称:批2 起 24 个判断点全要区分 integration,正是散写高发区,不设此门等于让新保留字重走 `"working"` 的散写老路;**前端 `integration` 相关逻辑收口在现有 `types/plate.ts`(常量 + 记录域判定函数,§3.3;共享 fixture 在 `types/__fixtures__/` 下,其 JSON 的 `"key": "value"` 形态不命中③的模式 —— ③只匹配比较式与 `startsWith(` 调用)**。

**③的边界(明示,防「门禁绿 = 完备」的错觉)**:按 ref 类变量名(ref|v|eff|declared|plateRef)限定是**防误报的妥协**,不是完备性保证 —— `"integration"` 在代码里已表示「集成任务」(`adaptationFlow.ts:76` 的 `'suite' | 'integration'`、`adaptation_service.py:1425`、`integration_runner.py:744` 通知类型、`routers/integration.py:30` 路由前缀),不限定会对其误报;代价是放走变量名不在集合内的比较(如 `adaptation_service.py:1438` 的 `target_revision`),此类点**完备性由 §3.2 逐点清单 + 评审语义判断兜底**。模式 `[!=]==?` 覆盖 Python 的 `==`/`!=` 与 JS 的 `===`/`!==` 四种写法 —— **`==?` 不是冗余**:`[!=]=` 在 `===` 上匹配完前两个 `=` 后紧跟第三个 `=` 而非引号,整式失败,前端严格比较会全部漏判(实测三行样例:`[!=]=` 命中 1、`[!=]==?` 命中 3);③扫描范围含 `frontend/src`,故必须保留。**`integration@` 前缀分支(v0.9.7 新增)**:派发链回写分流与前端台账识别的判据若散写 `startswith/startsWith("integration@")` 字面量,等值比较两支均拦不住(v0.9.6 曾误注「门禁①会拦」——①只匹配 `ext:` 前缀字面量),该分支与①的 `starts[wW]ith` 同构,只放行 `run_semantics.py` 与 `types/plate.ts`;**正因为有此分支,`plate_client` 等消费方的 reason 映射不得自带前缀字面判断(§1.4),前端台账必须调 `types/plate.ts` 判定函数(§3.3)—— 否则写出来就红**;**扩展后模式基线实跑零命中(v0.9.7 已验)**。①的 `starts[wW]ith` 兼容 Python `startswith` 与 JS `startsWith`。③整体基线实跑零命中。②在基线代码上实测命中 19 处(批2 后应为 0);两种引号与 `==`/`!=` 均覆盖;`endpoint_catalog.py:60` 等缺省值写法(`ref or "working"`)、`adaptation_service.py:1186/1290/1557` 的 `or "working"` 不在模式内,由 §3.2 清单逐点处理。

### 6.4 运行手册(批4 合入)

- **第三方系统接入**:`systems/<系统>/` 写定义,`gimbal:system` 声明 `kind: integration`(系统内所有服务一致),frontmatter 不写版本线字段 → **在分支上起草**(draft 是起草常态)→ 评审并全部置 `reviewed`(合入闸 pytest 拒绝 integration 系统的 draft 块)→ 合入 → plate 重启生效(`/healthz` 核对定义标识)→ 在服务信息管理为该服务建**服务级默认别名**(名称 = 服务名)并配 base_url/凭证;
- **使用**:编排器「第三方集成」分组选接口;多实例时逐步骤切换服务引用或在运行方案显式绑定(与被测系统相同);
- **query_safe**:仅平台模式硬约束;个人模式边界 = 用户本人在第三方的权限;
- **变更语义**:定义改动在 plate 重启后作用于所有引用场景,无逐场景确认 —— **对版本边界原则的有意例外**(§1.3),不得按该原则补阻断;测试执行与图执行的 `plate_pins` 记当时定义标识;**集成任务不记追溯**(不入执行记录,10-08 决策),核对当前加载标识查 `/healthz`;
- **声明写法**:第三方系统在场景中只写 `integration`;执行记录里看到的 `integration@<标识>` 是当时定义的指纹,不能抄回场景当作钉定(plate 返回 422,「是执行记录值」)——第三方无版本,无法钉定;只改说明文字(description 等)不改变标识;**被测系统的声明必须是 `<line>#<n>` 或 `working`,裸线名会被 422 拒(缺修订号)**
- **被测系统本身作为集成对象**(自有系统保活、自有接口定时查询):**直接用 sut 锚点 + 修订钉定**,不得重新登记为 integration(同一系统双源);
- **转为被测系统**:原地改 `kind: sut` + 声明 `line` + 发版(发版前场景可暂声明 `working`)→ 场景改钉修订 → 别名改 plate;
- **不得**:把已发版的 sut 系统改为 integration(须换新系统名);在 integration 系统挂取数视图;
- **真实差异**:同一第三方多实例 API 确不同 → 拆两个 plate 系统,别名分别指向;
- **下线第三方系统**:先用影响查询(`endpoint_ref_index`,integration 锚点与 sut 同样入索引)列出引用场景与集成任务,处置后再删定义;直接删除时引用场景在预检/`/convert` 响亮失败(系统不在注册表),不会静默执行;
- **已知边界**:只读场景不支撑 Jenkins/Jira 推送类集成(平台模式只读;推送须个人模式写类任务);
- **已知副作用**:plate 不可达时外部步骤与 sut 同样不可执行,外部别名无法新建;
- **已知边界(追溯)**:集成任务只保留最近一次状态,不追溯当时的定义标识。

---

## 7. 风险与悬置项

| # | 风险 | 评估 | 缓解 |
|---|---|---|---|
| R1 | plate 不可达 | 中;与 sut 同等 | 现有 fail-closed 出口;无新增依赖类别 |
| R2 | 定义改动立即作用于全部引用场景,无逐场景确认(对版本边界原则的有意例外,§1.3) | 中;有意语义 | git 评审 + 禁 draft 块(pytest 合入闸);测试/图执行 `plate_pins` 记定义标识可追溯;集成任务不追溯(已知边界);手册写明 |
| R3 | 生效需 plate 重启 | 低 | 手册写明;`/healthz` 透出定义标识;不做热加载 |
| R4 | ref 判断点漏改 / 误归类 | 中→低 | 分类器单一原语 + 契约测试 + §6.3 ②③ 门禁;读取类漏改为响亮失败,钉定收集类由门禁兜底 |
| R5 | **写路径误让 integration 进 resolve**(`_bump` 把 `integration` 改写落库) | 中影响、可预防 | 分类器 `PIN` 判据自然排除 + §3.2 单列 + 台账条目 + 批0 钉测试 + 批2 用例 |
| R6 | 过滤完备性双向:sut 专属面漏过滤(integration 出现在画像/看板)/不得过滤面误伤(第三方选不到、服务引用误报、锚定/别名/导入坏) | 中 | §3.4 逐面清单;sut 过滤唯一出口在派生点;批2 逐面断言 + 不得过滤面反向断言 |
| R7 | **D-M 覆盖分支改变 sut 既有 carry 解析次序**(别名表优先;`base_service` 冻结值与 `derive_base` 漂移值在边缘 case 可能不同) | 低影响、可预防 | 批0 钉 sut carry 基名解析样本;批2 验收「sut 场景 carry 解析与基线一致」断言(D-M);不覆盖分支天然保持现状(今日目录本就全 sut) |
| R8 | 误升代际 | 高影响、低概率 | §1.2;批1 验收含两种代际未变断言 |
| R9 | 个人模式写操作不受 query_safe 约束 | 低;有意 | 手册写明 |
| R10 | 无锚点外部裸调用绕开定义 | 低 | 平台模式闸按方法 fail-closed;导入自动重锚定;D-N |
| R11 | 执行记录下游把 `plate_pins` 当修订字面比对(integration 每次被误标「不可对比」,或标识随无关变化触发假「修订切换」) | 中(用户可见误导) | §1.5:台账按 ref 类别解读(前端经 `types/plate.ts` 判定函数、后端经记录域入口,共享样例锁定);趋势签名用只随执行与判定相关定义变化的标识(D-L:`shape_hash` 聚合,剔除纯展示字段);批2 验收 |
| R12 | 方向再次调整的决策疲劳 | 低 | 定义真源归 plate 的方向未变,本版只改机制且净删除为主;§0.3 写明重写依据 |
| R13 | **声明闸对裸线对齐拒的存量影响**(批1 起 plate 拒、平台本就拒;**影响面 = 被集成任务引用的裸线场景** —— 测试执行路径今天就被 `resolve_effective` 拒,`read.py:365-368`) | 低 | 批0 盘点⑥(影响面同口径);非空则批3 迁移⑥ 改写为 `<line>#<n>`;响亮失败不静默 |

### 7.1 悬置项(批4 活体核实)

1. 只读场景对 Jenkins/Jira 推送类集成的支撑 —— 判定:不能,写为已知边界(§6.4);个人模式写类任务不受此限;
2. 卡片「成功」语义 = 每次检查的 check 结论而非配置成功 —— 活体确认;不通过另立修复批,不阻塞批3。

---

## 8. 决策项

### 8.1 已定

| # | 问题 | 结论 |
|---|---|---|
| D-A | plate 建模 | 新增 `ServiceDefinition.kind`(`sut`缺省/`integration`),唯一新增字段;系统内一致;不升代际 |
| D-B | 锚点语法 | `ext:` 退役,统一 plate 锚点 |
| D-C | query_safe 治理 | git 口径;硬护栏 = 现有只读闸 plate 分支 |
| D-D | 外部端点挂取数视图 | 不挂;plate check 系统树校验区强制 |
| D-E | 漂移修复按钮 | 撤销(无内联副本,无漂移) |
| D-F | 编排器第三方入口 | 选单按端点行 kind 分组,选中自动写 `integration` 声明;实例沿用步骤服务引用 + 服务级默认别名,不前置选别名 |
| D-G | 第三方系统版本 | 不发版;`meta.plate` 保留 ref `integration`,读当前定义、非预览;双向绑定单一实现在 plate |
| D-H | 入库标准 | integration 归 `external` 桶不计入;需要可信则原地转 sut |
| D-I | 保留值命名 | **`integration`**(owner 同意,原 P-1)。注:该词在平台已表示「集成任务」(引用类型、通知类型、路由前缀),两者语义相关(集成任务恰是 integration 系统的主要消费者)不构成冲突,但代码中 ref 值一律经分类器常量引用,不与任务类型字面量混用(§6.3③ 按 ref 变量限定) |
| D-J | 执行追溯 | **做**(owner 同意,原 P-2):`plate_pins` 记 `integration@<定义标识>`,标识在 plate 启动 lifespan 计算、经现有 `/healthz` 透出;不进入库判定。**范围订正(v0.9.4)**:限测试执行与图执行;集成任务按 2026-10-08「集成执行记录不放入执行记录」不另设追溯(已知边界)。下游消费按 ref 类别解读(§1.5,含追溯态识别)。**标识形态 = D-L(shape_hash 聚合,owner 确认)** |
| D-K | **声明域合法集与非法 reason(v0.9.8;承载与分流精化 v0.9.9)** | **声明域 = `working` \| `<line>#<n>` \| `integration`;非法返回 INVALID + reason(`record_value` / `missing_revision` / `malformed`)。承载:错误码沿用现有 `invalid_ref`(`envelope.py:33`),reason 放 `ErrorPayload.details.reason`(`envelope.py:46`),不新增 ErrorCode;`parse_ref` 不改返回值形状,非法继续**抛** `ReleaseReadError(invalid_ref)` 附 reason(`read.py:58-61` 现契约,调用方零改动),INVALID 枚举只在平台 `ref_category`;HTTP 状态码分域:取数域沿 `_READ_ERROR_HTTP`(`routes_grammar.py:117`)保持 400,声明域(声明闸、`/convert`)422,两侧 reason 一致。裸 `<line>` 在取数域保留(?ref 线最新);plate 声明闸对裸线声明对齐拒。**论据(v0.9.9 补强)**:裸线声明**今天在测试执行本就跑不了** —— 派发链对非 working 声明调 `resolve`,`resolve_effective` 开头即拒非 revision(`read.py:365-368`);「plate 照收」只发生在绕过 resolve 的路径,主要是集成任务(`integration_runner.py:533` 直调 `/convert`)。故 D-K 对测试执行不是新限制,只是把集成任务对齐到同一口径;R13 影响面 = 被集成任务引用的裸线场景。plate 侧 integration 的 resolve 返回须在 `resolve_effective` **之前分流**(§3.1);resolve 动作错误域已定 D-O(422)** |
| **D-L** | **执行追溯定义标识(owner 确认 2026-10-18,原 P-5)** | **shape_hash 聚合**:系统内各端点 `shape_hash`(`dialect/canonical.py:101`)按端点 id 排序后的聚合哈希;聚合函数放既有 `dialect/canonical.py`(沿用其序列化纪律);`/healthz` 透出(沿 `m2_pool` 先例);`plate_pins` 只记内容哈希(HEAD 可同时透出作部署核对)。论证全文见 §9 v0.9.6 行(甲/乙案否决、有意不覆盖 metadata/服务对象、增删端点必翻转)与批1 稳定性断言 |
| **D-M** | **carry 覆盖第三方(owner 确认 2026-10-18,原 P-4)** | **覆盖,别名表优先**:carry 三处基名解析先查别名表 `base_service`(external 显式值、sut 已派生值),未登记裸服务键再走全量 `derive_base`;carry_store/carry 配置面不排除 integration 端点;sut 过滤仍只在别名创建派生点;验收含「sut 场景 carry 解析与批0 基线一致」断言(R7);运行时 `derive_base` 的台账条目保留 |
| **D-N** | **无锚点外部裸调用(owner 确认 2026-10-18,原 P-3)** | **维持合法**;批0 盘点⑤出数复核 —— 为 0 即终态;非 0 再议收紧(届时与 §3.3 重锚定同批) |
| **D-O** | **resolve 动作错误域(owner 确认 2026-10-18,原 P-6)** | **归声明域,422**:resolve 异常出口改用声明域映射(不走 `_READ_ERROR_HTTP` 的 invalid_ref 行),带 `details.reason`;平台侧对 4xx 统一 `PlateRejectedError`,状态码变化无行为影响;批1 落地并出正反例 |

### 8.2 待 owner 确认

(无 —— owner 2026-10-18 决策轮全部拍板:P-3 → D-N、P-4 → D-M、P-5 → D-L、P-6 → D-O,均取建议值。D-N 含批0 盘点⑤复核检查点:出数非 0 时重开该项。)
---

## 9. 修订记录

| 版本 | 轮次 | 要点 |
|---|---|---|
| v0.1 | 初稿 | 五批骨架 + 清单 + 台账 + 风险 |
| v0.2 | r1 / 10 | 照常 release,`ext:`=latest;删 ext-directory 与 CLI 提前;删上线类护栏;signer 留执行侧 |
| v0.3 | r2 / 13 | 执行按内联、判定按 latest;漂移检测;三条件闸;fail-closed |
| v0.4 | r3 / 10 | 目录按系统 + base_service 多对一;漂移进定时路径;形态匹配口径 |
| v0.5 | r4 / 8 | 处置按任务类型;占位符匹配;kind 一致校验;拆系统出口 |
| v0.6 | r5 / 16 | 代码审计:闸缺口定性更正;处置键改身份模式;直读点更正;C10/C11;grep 四模式 |
| v0.7 | r6 / 10 | 外部别名 base_service 显式选择;「不得过滤面」 |
| v0.8 / v0.8.1 | r7 / 4 + owner 轮 | 盘点四项;迁移空档;kind 不可变;D-F 定案;章节终态重排 |
| v0.9 | 2026-10-16/18 讨论 + 代码核实 | **机制重写**:外部系统不发版;保留 ref `integration`;`ext:` 退役,执行与判定同源,删除漂移检测/匹配器/三条件闸/D-E/锚点名映射/导入外部分支;`kind` 取值 `sut\|integration`、模型缺省、不升代际,否决扩展 `line_scheme`;D-F 简化;入库归 external 桶 + 原地转 sut;C12;新规则「先扩展后新增」 |
| v0.9.1 | 六处补全 + 三轮自评审 / 15 | sut 专属展示面清单与不得过滤面;check「有发版不得改 integration」改由双向绑定使用时强制;悬置项与手册补回;过渡期;系统内 kind 一致 + `SystemView.kind`;`validate_meta_plate_refs` 改动;追溯复用 `plate_pins`;适配目录差异排除;服务级默认别名;批次矛盾修正;门禁对基线实跑校准 |
| v0.9.2 | 外部评审第一轮 P1×3 / P2×6 / P3×7 + 第二轮(统一架构 × Clean Code)+ owner 意见 | **P1**:①端点级 kind 通路 —— `EndpointView.kind`,`/api/endpoint`(全局与系统作用域)行带 kind,平台 `/api/catalog/services`(实为聚合 `/api/endpoint`)与 `/api/endpoint-catalog` 各 list 透传,消费方零 join;②`_plate_list_endpoints` 消费方订正为看板与 carry(适配差异本体走 plate diff),§3.4 补看板瓦片(排除)与 carry(新增 P-4 拍板)两行;③`catalog_service_names` 六消费方分「过滤/全量」,sut 过滤唯一出口在别名创建派生点、不得下沉,台账立条目。**P2**:④`_bump_verified_to_effective` 为隐藏写路径,单列「谓词跳过、严禁走 resolve 例外」+ 风险 R5 + 批0/批2 用例;⑤§1.3 订正 —— 适配 `from=working` 是现有能力,跳过 integration 是必要改动;⑥`/convert` 的 `ReleaseReadError` 现落 500,批1 映射 422;⑦`assess_baseline` 异常路径(`revision_objects` 抛 `PlateRejectedError`)入批2 混装场景验收;⑧批0 基线补 `_bump`、`catalog_service_names` 六消费方、看板/carry 目录快照、适配 from=working 四项,并记录 `anchored_systems` 不过滤 `ext:` 的现存张力;⑨check 规则统一挂 `validate_system_tree` 系统级校验区(`EndpointSpec` 校验器拿不到系统 kind)。**P3**:判断点改按实测点名清单计数(`run_semantics.py` 外 24 处);前端消费订正为 6 文件两函数 + `ServiceAdmin` 的 `loadCatalogEntries`;C10 `test_metadata_invariants.py` 改为删 `ORDER_SENSITIVE` 例外行;§1.2 无 `line` 系统表述订正(仅 common;`line` 在 frontmatter);行号订正;`run_dispatcher.py:827` 归类订正为告警过滤;跨文档同步要求(见文末)。**owner**:P-1 → D-I;P-2 → D-J;P-3 维持并注明与重锚定同批。**第二轮**:Ⓐ统一度判定通过(残余不对称全部源自 kind 本身而非机制分叉);Ⓑref 类别分类器取代「谓词 + 例外」;Ⓒ门禁③;Ⓓplate 目录三访问件收敛进 `plate_client`;Ⓔref 语义分类;Ⓕ§1.2「为何不放 frontmatter」(M2 论据不成立,改以数据通路为据);Ⓖ台账补三条;Ⓗ批1 验收补 `_needs_root`;ⒾD-I 同名不冲突注记 |
| v0.9.3 | 第三轮评审(v0.9.2 验收)/ 2 P2 + 3 P3,全量并入 | **P2**:①P-4 任一分支验收补「sut 场景 carry 解析与批0 基线一致」断言,新增 R7;②门禁③模式「冗余修正」(`[!=]==?` → `[!=]=`)并写明变量名限定边界。**P3**:③§3.2 分类精化(`:1703` 移入预览类,读取 10 / 预览 2);④`service_names` 行号订正;⑤P-4 从批1 前置摘除。**第三轮同时验证 v0.9.2 全部新断言通过**:`EndpointView`/`system_of_service`/`types/plate.ts`/门禁③基线零命中/24 处账目;frontmatter 反驳裁定成立,§1.2 补全论据 |
| v0.9.4 | 未覆盖面全量排查 + 三轮复审 / 13 | **承接上轮遗留 6 项**:①D-J 范围订正为测试执行与图执行,集成任务按 10-08 决策不另设追溯;②P-4 补论证(carry 运行时 `derive_base` 是第二套映射);③追溯标识经现有 `/healthz` 透出;④sut 子集取自 `plate_client` 扁平名视图;⑤门禁①兼容 JS `startsWith`;⑥§1.3 版本边界原则有意例外。**修正 v0.9.3 回退**:⑦门禁③恢复 `[!=]==?`(`[!=]=` 漏判前端 `===`/`!==`,实测 1/3)。**新排查未覆盖面**:⑧执行记录下游误读(台账逐字比对/趋势签名),新增 R12(后调整为 R11);⑨规则 3 执行点(check warning + pytest 合入闸);⑩下线第三方系统流程入手册;⑪环境版本线声明拒绝 integration;⑫新增 P-5(内容哈希替代 HEAD);⑬核实非问题:plate 端点列表不分页。**三轮复审**:清理 `integration@<HEAD>` 残留口径;P-5 落点核实(`object_hash` 公开/`_dict_hash` 私有/`m2_pool` 先例/`tests/plate` 同类用例);环境校验 plate 不可达跳过;手册补起草流程;无新增模块/字段;D-A~D-J 不变 |
| v0.9.5 | 第四轮评审(v0.9.4 验收)+ 全量整理 / 2 P2 + 3 P3 | **P2**:①`ref_category` 补**追溯态识别** —— 台账要比对的 `plate_pins` 值是 `integration@<标识>` 而非裸 `integration`,分类器须将 `integration@` 前缀归 INTEGRATION 并入两侧契约测试(§1.4/§3.3/批2 验收/台账同补),否则 §1.5 台账修法落不了地;②P-5 增**哈希口径**拍板项 —— 甲案对象全量 vs 乙案重投影产物(建议乙案)。**P3(整理)**:③§0.1 决策链末行版本区间更新;④§3.6 过期自引改「本方案落地」;⑤风险表重排并重编号(执行记录下游误读 = R11,决策疲劳 = R12,§8.2 P-5 引用同步);⑥`_dict_hash` 行号订正为 release.py:130(**后经 v0.9.6 裁定此订正有误,实在 :131**)。**第四轮同时验证 v0.9.4 全部新断言通过**:门禁③反转成立;执行台账/趋势签名三处坐实;`verify_all.sh:48` 与 `tests/plate/test_http_health.py`;`environments.py` lines 盲写;哈希/健康检查锚点;integration_runner 无 resolve 调用;`per_page` 零命中;「不写执行记录」10-08 决策出处 |
| v0.9.6 | 第五轮评审(v0.9.5 验收)/ 4 P2 + 2 P3 | **P2**:①**声明域/记录域分离** —— v0.9.5「两种形态均入两侧契约测试」会迫使 plate `parse_ref` 接受 `integration@<x>` 声明,构成伪钉定;改为分类器分声明域(两侧契约锁定,`integration@…` 非法,plate 经声明闸与 `/convert` 返回 422)与记录域(`plate_pins` 下游,平台单侧识别、单测覆盖)(§1.4/§3.1/§3.3/批1 批2 验收/台账同改);②**派发链回写分流** —— `run_dispatcher.py:1653-1658` 现把 `effective` 同写 `plate_pins` 与执行副本,与①合并后若照现状回写,含 integration 的测试执行 `/convert` 必 422;改为 INTEGRATION 只写 `plate_pins`、执行副本保持 `integration`,经分类器判据(§1.5/§3.2 追溯行/批2 断言/台账)。**P2(口径)**:③**P-5 收敛为 `shape_hash` 聚合** —— 核实 `_call_projection`(`release.py:108-128`)不含请求/响应声明,乙案漏报、其「⇔」主张不成立;甲案有展示字段噪音;`shape_projection` 覆盖 binding + 声明树且剔除展示字段,已是适配中心与发版 corrections 的变更判据,口径与 sut 统一;P-5 由二选一改为单一建议待确认;批1 验收补标识稳定性断言。**P3**:④订正 v0.9.5 ⑥——`_dict_hash` 实在 `release.py:131`(`:129-130` 为空行),v0.9.5 改为 :130 有误;采用③后本方案不再引用 `_dict_hash`,亦无需将其提升为公开函数。**同轮核实**:⑤图执行链 `_g_pins`(`run_dispatcher.py:1269-1270`)不经 `resolve`,integration 会记成裸值丢失标识——改法落定为「在该点对 INTEGRATION 补调 `resolve`,只写 `_g_pins`」;`graph_dispatch.py:174-178` 回写由钉定收集类排除 integration,无需改(§1.5/§3.2/批2 断言);⑥手册补「声明写法」条。无新增模块/字段;D-A~D-J 不变 |
| v0.9.7 | 第六轮评审(v0.9.6 验收)/ 2 P3,全量并入 | **P3**:①订正 §1.5 误注「门禁①会拦」—— ①的模式只匹配以 `ext:` 开头的字面量,`startswith("integration@")` 在等值比较与①两支下**均无门禁可拦**;修法:门禁③新增 `starts[wW]ith\(['\"]integration@` 前缀分支(与①同构,只放行 `run_semantics.py`),§1.5 该处引用同步改为「门禁③的 `integration@` 前缀分支会拦」;扩展后模式基线实跑零命中。②平台预检 `validate_meta_plate_refs` 对 `integration@<x>`(无 `#`)会落入现有「缺修订号」分支、消息误导——§1.4/§3.3 增「按前缀识别并映射 plate 同款『记录值』消息」(**后经 v0.9.8 裁定此修法自相矛盾,被 reason 映射取代**),批2 验收增对应断言。**第六轮同时验证 v0.9.6 全部新断言通过**:`shape_hash`/`shape_projection`/`_DECL_SHAPE_EXCLUDE` 锚点无误;`_call_projection` 确不含请求/响应声明树(乙案漏报裁定成立);`shape_hash` 消费方 `views.py:182/232` 与 `release.py:608/634-640` 坐实;派发链双写、`_g_pins` 不经 resolve、`graph_dispatch.py:174-178` 回写源为 suite_pins 均确认;`_dict_hash` 实在 `release.py:131` |
| v0.9.8 | 第七轮评审(owner 提出 2 项)/ 均裁定成立,全量并入 | ①**订正 v0.9.7 自相矛盾**:预检「按前缀识别」会被本版新加的门禁③前缀分支拦下(放行仅 run_semantics/types/plate.ts),且构成 record-value 检测的**第二处实现**(违反 §6.2 第 1/3 条);根因 = 分类器返回值无 INVALID 类(v0.9.6 只说「归非法」未说怎么返回);修法(新决策 **D-K**):声明域分类返回 **INVALID + reason(`record_value`/`missing_revision`/`malformed`)**,`validate_meta_plate_refs` 按 reason 映射文案、本体不做前缀/形状字面判断,契约测试分类表**加非法行、锁 reason 表**,plate `/convert` 422 与平台预检按同一 reason 表映射。②**分域边界修正(评估补充)**:`missing_revision` 不进 plate `parse_ref` —— 裸线在取数域合法(`?ref=<line>` 线最新快照是现役特性,`routes_grammar.py:61-67`),parse_ref 的 INVALID 只含全域皆非法者(`record_value`/`malformed`),裸线保留 line-kind;`missing_revision` 由 **plate 声明闸**按声明域政策给出 —— 顺带钉死既有歧义:「四种写法」= ref 语法全集,**声明域合法集 = working \| line#n \| integration**,plate 声明闸对裸线声明**对齐拒**(消除「平台拒、plate convert 收」双口径);批0 盘点加⑥(存量裸线声明)、基线加 convert 现状、迁移加⑥、新增 R13;导入方向核实:`run_semantics` 对 `plate_client` 为函数内延迟导入(`:72-73`),`plate_client` 模块级调分类器**无循环导入**。③**前端记录域落点(评估补充采纳)**:`types/plate.ts` 加记录域判定函数(台账跳过比对与「第三方实时定义」标注共用),门禁③注释改「常量与记录域判定函数」(**模式零改动**,该文件本就整文件放行);批2 加前端单测,**与后端共享同一份 JSON 样例 fixture**(vitest/pytest 同读,防两侧样例漂移);§6.1 立条目:记录域分类 = 后端入口 + 前端函数、共享样例锁定、禁止第三处实现;趋势签名(`useScenarioRuns.ts:96`)只拼接不分类,不受影响 |
| **v0.9.9** | 第八轮评审(owner 提出 2 项 + 论据补强 + 1 小项)/ 均核实成立,全量并入 | ①**错误承载精化(修 D-K 的实现歧义)**:v0.9.8「422 + 可读错误码(带 reason)」照写会新增三个 ErrorCode —— 承载改定为:错误码**沿用现有 `invalid_ref`**(`envelope.py:33`),reason 放 `ErrorPayload.details.reason`(`envelope.py:46`),**不新增 ErrorCode**(「在已有字段上扩展」);②**`parse_ref` 不改返回值**:现契约即**抛** `ReleaseReadError("invalid_ref", …)`(`read.py:58-61`),调用方(`_registry`/`reproject`/`resolve_effective`/diff 等)零改动 —— 批1 只给异常附 reason(`integration@…` → record_value、现有 `# 后非数字` 抛出补 malformed),`INVALID` 枚举只存在于平台 `ref_category`(§1.4/§3.1/批1 验收/台账同步);③**HTTP 状态码分域**:`_READ_ERROR_HTTP`(`routes_grammar.py:117`)把 invalid_ref 映射 400 供取数路由 —— 取数域**保持 400 不动**,声明域(声明闸、`/convert`)返回 **422**,两侧 reason 一致(§1.4/§3.1/批1 验收);④**resolve 分流位置**:`resolve_effective` 开头即要求 `parse_ref` 结果为 revision、否则 invalid_ref(`read.py:365-368`)—— §3.1 resolve 行与 §1.5 点明 **integration 在调 `resolve_effective` 之前分流**,不前置分流即被直接拒(批1 加正反例);⑤**D-K 论据补强**:裸线声明**今天在测试执行本就跑不了**(派发链对非 working 调 resolve、`resolve_effective` 拒裸线)——「plate 照收」只发生在绕过 resolve 的路径(主要是集成任务 `integration_runner.py:533` 直连 `/convert`);D-K 对测试执行不是新限制,只是把集成任务对齐;R13 与批0 盘点⑥ 影响面收窄为「**被集成任务引用的裸线场景**」(§1.4/§3.5/§3.6/R13/D-K 同步);⑥**fixture 路径写死**:共享样例 fixture 定为 `src/gimbal-platform/frontend/src/types/__fixtures__/ref-record-domain.json`(仓库根相对;两侧测试运行目录不同,`verify_all.sh:51/54`,不写死会找不着;前端就近读、后端从测试文件回溯仓库根解析);fixture 内 `integration@…` 字面量不命中门禁③(③只匹配比较式与 `startsWith(` 调用,JSON `"key": "value"` 形态匹配不上)(§3.3/§6.1/§6.3/批2 验收同步) |

| **v0.9.10** | 第九轮评审(owner 提出 2 项)/ 均核实成立,全量并入;全量一致性检查 | ①**resolve 域归属补写**:resolve 入参是声明、语义属声明域,但错误现经 `_read_error`(`routes_grammar.py:1242`)返回 400,方案声明域只列了声明闸与 `/convert` —— 新增 **P-6** 决策项(建议归声明域 422;备选保持 400 注明例外),§1.4 域枚举/§3.1 resolve 行/D-K/批1 验收同步挂 P-6;平台侧对 4xx 统一 `PlateRejectedError`(`plate_client.py:465/489`),状态码变化无行为影响(已核实)。②**`_read_error` 转发 reason**:现只带 code+message(`:124-127`),异常附 reason 后取数路由与 resolve 的响应体里看不到 —— §3.1 新增一行改动(把 reason 带进 `ErrorPayload.details`),状态码分域不变,reason 在取数 / resolve / `/convert` 三条路径一致;§1.4/§6.1/批1 验收同步(取数路由 400 响应体含 `details.reason` 断言)。**全量检查**:版本串/域枚举/状态码措辞(「不动」→「状态码不动、补 reason 转发」)/D-K/P-6 交叉引用/R1-R13、D-A~D-K、C1-C12、批0-批4 编号与指向复核,无其他不一致 |
| **v1.0** | owner 决策轮(2026-10-18)/ 4 项全拍板,定稿 | P-3 → **D-N**(维持合法,批0 盘点⑤复核);P-4 → **D-M**(覆盖,别名表优先;验收含 sut 行为不变断言);P-5 → **D-L**(确认 shape_hash 聚合);P-6 → **D-O**(resolve 归声明域 422,异常出口改声明域映射)。§8.2 清空;全篇 P-3/P-4/P-5/P-6 引用改指对应 D 项;状态升「定稿」;顺带修复 v0.9.10 批1 验收的一处 `****` 重复星号。**定稿后动作**:同提交入库三同步(替换仓库 v0.8.1 旧档、翻转 `docs-cleanup-plan.md` 指针、批1 小设计状态行改「待按 v1.0 重写」);批0 排期;批1 小设计按本版重写(无待拍板项) |

**跨文档同步(§6.2 第 5 条)**:本版入库时同提交翻转 ——`docs-cleanup-plan.md` 头部联动与 §2.1 中「归一方案 v0.8/v0.8.1」指针改为 v1.0;`plate-external-batch1-design.md` 状态由「已确认」改为「待按 v1.0 重写」。
