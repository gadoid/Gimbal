# 外部接口定义归一 plate(工具定义)· 改造方案(v0.8 全量整理版)

> 日期:2026-10-16　基线:`feat/plate-s1 @ e6db1591`
> 状态:**v0.8.1 —— 七轮评审共 71 项结论全量采纳 + owner 决策轮(D-F 定案);全部决策项已定(§8),无遗留待拍板。**
> 进度(2026-10-16):方案入库(00c7b3fc)→ D-F 定案(43e8eb2d)→ **批1 一页纸小设计已确认**(`plate-external-batch1-design.md`,26779603);文档清理 W0 完成、评审旧档删除方向已拍板;**批0(特征化基线 + 存量盘点四项)待排期 —— 唯一未开工项**;批1 已具备开工条件。
> 红线:本方案自带清理承诺(§5)与守门机制(§6)—— 反转而不清理 = 重蹈覆辙
>
> 核心口径(全文由此展开):
> 1. **plate 按「系统」建目录、照常 release;`kind=external` 只是过滤标签**;
> 2. **`ext:` 锚点 = 「执行按内联形态,判定按 latest 定义」**;
> 3. **别名与系统多对一,`base_service` 显式选择**(外部别名不派生、无命名规约);
> 4. **安全与漂移处置按身份模式分**(平台模式三条件闸 / 个人模式整任务阻断)。

---

## 0. 背景:第三次反转及其依据

### 0.1 决策链(唯一口径,评审引用以此为准)

| 时点 | 决策 | 落点 |
|---|---|---|
| 2026-10-08 架构设计 G6 | 外部系统**进 plate**(`ServiceDefinition.kind`) | 《GIMBAL-外部系统集成架构设计》§详细设计 1 |
| P1.0 拍板 | external **不进 plate** | X1 设计 §1 引 |
| 2026-10-12 X1 登记 | 目录的家 = **平台新表**;G6 不合流 | `external-interface-registry-design.md` §1/§8 |
| 集成线 P2/v2 | 沿用平台目录;I4 给 plate 与平台目录各补一份 query_safe | 同上两文档 |
| **本方案(2026-10-16)** | 定义源归一 plate | 第三次反转 |

### 0.2 反转依据(全部经代码核实)

1. **外部 `query_safe` 在闸上从未生效**:`integration_runner.py:116-132` 内联 method 优先,仅内联为空才查目录,而真实 `ext:` 步骤必带内联 method —— I4 给外部目录补的 query_safe 形同虚设,POST 查询类外部接口进不了平台模式;
2. **只读闸双分支**(plate 锚点 / ext: 锚点两条解析路径两个源);
3. **消费面双实现**(契约视图对 `ext:` 另一套组装;平台自持 schema→declarations 转换);
4. **治理双动作**(admin 登记页审计 vs plate repo/修订纪律,「交给谁管」两套答案);
5. **别名级目录双份定义**(平台目录按 alias_name 键,生产/测试两别名存两份相同定义)。

### 0.3 反转成立的三个条件(缺一不反转)

**带清理**(§5)、**带守门**(§6)、**有增量收益**(P7/P9 AI-native 工具定义地基;平台未上线,是成本最低时点)。

---

## 1. 目标形态与边界

> **边界一句话:plate 管「接口是什么、调用形态、是否 query_safe」;平台管「以谁的身份、用谁的凭证、什么时候跑」。**

### 1.1 目标形态总表(owner 确认)

| 层 | 归属 | 说明 |
|---|---|---|
| 定义注册与发布 | **plate** | 与 sut 同一条路:写 `systems/<系统>/` → 评审 → release;`kind=external` 只是过滤标签 |
| 定义消费 | **平台按需读取** | 读别名所指系统 latest release 投影(带缓存);plate 不推送、不感知平台 |
| 执行 | **场景内联副本** | 执行用步骤内联 method/path/body;新 release 不自动改写已有场景,偏离由漂移检测拦截 |
| 安全声明 | plate | 接口级 `query_safe`,随定义走评审;**仅平台模式下是硬约束**(个人模式边界 = 用户本人在第三方系统的权限,手册写明) |
| 安全执行 | **平台,按身份模式** | 平台模式 = 强制只读(三条件闸);个人模式 = 读写均可,漂移整任务阻断(§2) |
| 身份与环境 | **平台别名** | base_url/凭证只在 `service_aliases`,plate 永不持有 |

**「更轻」的准确含义**:注册与发布不比 sut 轻;轻在消费侧 —— 不钉版本、不参与版本线/环境组、不触发适配与版本边界、不进画像/覆盖统计,由漂移检测兜底。

### 1.2 plate 侧:系统定义与生命周期

- `ServiceDefinition.kind` = `sut`(缺省)/ `external`;**过滤标签**,不影响存储与服务路径;**已有 release 的系统不允许改 kind**(plate check 规则,批1 与 `line` 规则同批落地)—— 换 kind = 换新系统名重新接入,由代码强制而非手册自觉;
- **目录按系统建**:`systems/jira/` 一份定义,多别名共享;生命周期照常「编写(人或 Agent 写 md)→ 评审 → release」,对象池/构件/水合/投影全复用,生效时点 = release;
- **external 的 `system.md` 不写 `line`**(不参与版本线),plate check 增规则(否则 release 按版本线要求拒收);
- **不参与版本线与环境组**(latest 全局);冷化/基线随 release 主线;**版本边界触发面排除 external**(现状按钉定 ref 触发,`ext:` 无 ref 天然不触;同类机制 `working_preview` 已注释不受影响 —— 批0 钉测试);
- **kind 只影响过滤面,且受「不得过滤面」约束**(§3.3 两张清单);外部目录视图 = 现有投影按 kind 透出(**含 path 模板原形**),不新增 `/api/ext-directory`;
- **适配触发面排除 external**(承接机制 = 漂移检测,§2.2;外部变更不应触发成员级适配流程);
- `meta.plate` 声明闸豁免 `ext:` 锚点,**两处钉住**:plate 侧 `routes_grammar.py:1358` + 平台侧 `scenario_store.py:70/89`;
- 定义内容:method/path(模板)/请求响应 schema/auth 形态与 **signer 名称**(实现留执行侧,执行器已有 `@register_authenticator` 注册表)/展示元信息/query_safe;
- **永远不含**:base_url、凭证值、执行身份。

### 1.3 别名与系统映射(显式选择,多对一)

- **外部别名**:`base_service` 由用户在别名页下拉**显式选择**;保存时校验 ①所选服务存在于 plate 目录 ②kind 一致(经值域映射);不满足拒绝保存;**不派生、不约束命名** —— 理由:`alias_name` 是主键,场景 `call.service` 与 `ext:` 锚点均按别名名引用,改名 = 重写所有引用场景,代价不成比例;
- **sut 别名**:保持现有 `derive_base` 派生,不动;
- `services/service_aliases.py:92-96`(现状 external `base = alias_name`,「别名即服务本体」)改为「不派生,接收并校验显式 `base_service`」(批1);
- **kind 值域映射**:别名侧保持 `plate|external`(改值域要迁数据),plate 侧 `sut|external`,映射 `plate ↔ sut` 写死在校验函数(入台账);
- 别名页 `base_service` 下拉按 kind 过滤。

### 1.4 `ext:` 锚点语义与解析链

- **语义:执行按内联形态,判定按 latest 定义** —— 场景步骤内联 method/path/body(X1 前提,已核实),执行链不读 plate;latest release 只参与契约视图、预检、只读闸、漂移检测;
- **解析链:别名 → `base_service`(plate **服务名**,如 `fin-service`)→ 所属系统目录 → latest release**(服务名 ≠ 目录名);
- **无 release 的外部系统** → 预检失败并提示「该系统尚未 release」,不静默;
- `ext:` 锚点语法保留(D-B):语法外化判定口径与生命周期(latest、无钉定),存量场景零迁移。

### 1.5 平台侧不变项与明确不做

**不变**:service_aliases 持 base_url/凭证;执行身份(平台/个人模式)/订阅实例/调度/卡片全部不动;编排器 external 步骤表单加「按 latest 重填形态」按钮(D-E 已定案做,批2)。

**不做**:外部端点不挂取数视图(D-D —— 取数视图 = 被测数据校验,集成任务 = 第三方定时调用,防「定时查外部」双实现);CLI 导入器不提前(挂 task 5;批3 表→md 工具 = 一次性迁移脚本 C9,批0 确认 0 行则不产生);M2/Call 形态零改动(`kind` 按 M2 一次性适配)。

---

## 2. 安全与漂移模型

### 2.1 只读闸三条件(平台模式)

**现状缺口(已复核)**:闸内联 method 优先(`:116`),仅内联为空才查目录(`:119`);真实 `ext:` 步骤必带内联 method —— 「内联 POST + 目录 GET」实际会被拒绝,不存在错放行;**真实缺口是反向:目录 `query_safe=true` 从不被读到**,POST 查询类外部接口进不了平台模式。现有 Y5 测试用「纯锚点、无内联 method」载荷,恰好绕开真实形态。三条件闸正是让外部 query_safe **第一次真正生效**的修法。

| 条件 | 结论 |
|---|---|
| 内联 method 非安全方法(∉ GET/HEAD/OPTIONS) | 直接判非只读,不看定义 |
| 内联 method 安全 **且** 形态一致(§2.3)**且** query_safe 为真 | 放行 |
| 形态不一致 | 拒绝 |

闸的调用点:保存时 `routers/integration.py:189` + 执行前 `integration_runner.py:462`(同函数两个时点,一道闸非两道)。

### 2.2 漂移检测与处置(按身份模式,定时路径全覆盖)

漂移检测落在 `integration_runner` 执行前检查点(与闸共用一次 plate 投影读取)—— `run_precheck` 只是手工预检路由,定时集成任务不经过它。**实现要点:该检查点现状包在平台模式分支内,批2 须把「读 plate 投影 + 漂移检测」移到分支外、两种模式都执行;三条件闸仍只在平台模式下判定。**处置按身份模式分(个人模式也可以是纯只读任务,两处闸均按 `identity_mode` 分支):

| 身份模式 | 任一步骤漂移 | plate 不可达且无缓存 |
|---|---|---|
| 平台模式(强制只读) | 三条件闸拒绝 | fail-closed 拒绝 |
| 个人模式(读写均可) | **整任务阻断**(任一步骤漂移都可能经数据流把错误带进写操作;纯只读任务同此口径,略严于三条件闸,可接受,实现只有一个分支) | fail-closed 拒绝 |

plate 不可达的 fail-closed 出口沿用现例(`integration_runner.py:465-467`,`PlateUnavailableError` → run=channel + 固定前缀 lastError)。

### 2.3 形态匹配口径

- method 相等;
- path 分段比较:内联 `${...}` 段与定义 `{param}` 段**均视为通配**;比较**前剥离 query string**;匹配时机 = **变量展开之前**(执行前检查时场景未跑,拿到的即占位符形态);
- body 不参与一致性判定(仍走 schema 告警放行,R7 原样搬运)。

### 2.4 可用性

- 执行本身**不依赖** plate(内联形态);plate 停机影响预检/闸/漂移检测/契约视图/**别名新建**(`catalog_service_names` 空集,与 sut 别名现行为一致,可接受);
- 缓存 stale-while-error(命中 stale 可接受),**TTL + stale 总上界显式配置**(沿 `DECLARED_PATHS_TTL_SEC=300+stale` 先例 —— 即 query_safe 撤标的最迟生效上界;plate→平台无主动失效链路,列为可选增强不承诺);
- 无缓存 → 拒绝执行,不得放行(§2.2 表)。

---

## 3. 现状与迁移面

### 3.1 平台侧直读点(5 个表读者)与保留清单

| # | 消费点 | 现状 | 批次/去向 |
|---|---|---|---|
| 1 | `services/external_endpoints.py`(表属主:CRUD/OpenAPI 导入/转换/契约视图) | X1 主体,按 alias_name 键 | 批3 删;`check_body_against_schema` 告警放行语义搬到 plate 投影消费侧 |
| 2 | `routers/external_endpoints.py`(7 路由) | 登记/标记/审计 | 批3 删 |
| 3 | `routers/endpoint_catalog.py:102-127` | ext 契约视图组装 | 批2 切 plate 投影 |
| 4 | `routers/run_precheck.py:161-196`(手工预检) | 内联 body vs 目录 schema 告警 | 批2 切 plate latest + 漂移检测 |
| 5 | `services/integration_runner.py:119-132`(执行前;现状检查点包在 `if tpl.identity_mode == "platform"` 分支内) | 闸 ext 分支(内联优先) | **批2:漂移检测(读 plate 投影)移出平台模式分支,两种模式都执行;三条件闸仍只在平台模式下判定**(§2.2) |

**保留(非切源点)**:`plate_client.py:123-143` `_strip_ext_anchors`(`/convert` 前剥锚点,执行链依赖);`endpoint_ref_index.py`(ext 锚点按普通锚点入索引,只钉测试);alembic 0021/0022/0023/0026 历史链;`scripts/fixtures/schema-snapshot-0023.sql`(增量门从该快照真实执行 0029,正好验证下线迁移)。

**执行器触点(已核实)**:引擎无 `ext:` 解析,`/convert` 前剥锚点、内联执行,无第六直读点。

### 3.2 前端触点

| 消费点 | 去向 |
|---|---|
| `api/external-endpoints.ts`(仅别名详情页使用) | 批3 删 |
| `ServiceAliasDetail.vue` 登记 tab/query_safe 开关 | 批3 删;批1 加 `base_service` 下拉(kind 过滤) |
| `auditText.ts` 动作文案 | 保留只读映射标注「已退役」(删掉会让历史审计行退回原始 id);批0 查得审计表该动作 0 行则可删 |
| 编排器步骤选择器 | **现状无外部步骤新增入口**(目录列表 `endpoint_catalog.py:287` 不含 ext;前端无构造 `ext:` 锚点代码,只能经导入/手改 JSON)→ **D-F 已定案(§8)**:同一选单按 kind 分组补入口,批2 交付 |
| `IntegrationCenter.vue` | 文案不变,口径单源 |

### 3.3 plate 侧触点与两张过滤清单

| 触点 | 批1 动作 |
|---|---|
| `schema/service_definition.py` | 加 `kind`(M2 一次性适配) |
| `schema/endpoint/metadata.py` | 零改动(query_safe 已有) |
| 声明闸豁免 ext: 两处 | `routes_grammar.py:1358` + 平台 `scenario_store.py:70/89`,行为保持 + 钉用例 |
| external `line` 规则 + **release 后 kind 不可变** | plate check 增两条规则 |
| `service_aliases.py:92-96` | external 分支改显式接收与校验(§1.3) |
| 外部目录读取(系统级) | 现有投影按 kind 透出,含 path 模板原形;经公共投影访问件 |

**sut 过滤面(R5 清单 —— external 不出现)**:画像 / 覆盖统计 / **编排选单被测分组**(D-F 定案后口径:编排选单同列表按 kind 分组 ——「被测接口」分组纯 sut,「第三方集成」分组按 kind 展示 external;原「编排被测选单」整列表过滤口径废止)/ 取数视图挂载 / 适配触发 / 版本边界触发(含 working_preview)/ 版本线配置面 / 基线冷化展示 / 别名页 base_service 下拉。

**不得过滤面(`/api/service` 全量返回、按 kind 打标签,消费方自行筛选)**:它是 `catalog_service_names`(sut 派生数据源)与 base_service 下拉的共同数据源;误过滤 = 外部别名选不到外部系统、`classify_services` 把外部服务判 unknown。批1 加反向断言:外部服务必须出现在 `/api/service` 列表。

### 3.4 存量盘点与迁移空档

**批0 盘点四项**(空也出档):①`external_endpoints` 表行数(**预期 0** —— 0023 注释记录 2026-10-13 实测 0 行);②审计表 `external_endpoint.query_safe` 行数;③存量 external 别名清单及 `base_service` 现值;④**存量 `ext:` 锚点场景数**。

**迁移空档(①为 0 也覆盖不到 ③④)**:

- 存量外部别名现行规则 `base_service = alias_name`,批2 切源后按新解析链**解析不到任何 plate 系统**;
- 存量 `ext:` 场景从批2 切源起、直到外部系统定义写入 plate 并 release 之前,**预检持续失败**;
- 平台未上线,空档本身可接受,但必须回填:**③④ 任一不为 0 时,批3 增加收口步骤 —— 先为存量别名对应的外部系统写定义并 release(此步不能提前到批1,须等 plate 有了目标系统),再人工为每个存量别名选定 `base_service`;此为批3 的收口条件**;
- ③④ 均为 0 → 问题不存在,批3 仅 drop。

### 3.5 测试面(批0 特征化基线)

- `test_query_safe_gate.py` ext 段 / `test_integration.py` Y5 段:**改用真实形态载荷**(带内联 method 的 ext: 步骤)钉基线 ——「内联 POST + query_safe=true → **当前拒绝**」,批2 改判**放行**(形态一致时);
- 「内联 vs 定义不一致」现状基线;带路径参数三形态(字面值 / 占位符 `${pid}` / 带 query string);
- 双分支 / 取数视图 / 契约视图 / 预检 / 索引 / 执行器边界 / 声明闸两处豁免 / working_preview 面;
- 批1 反向断言:`/api/service` 含外部服务;批3:`test_external_endpoints.py` 删、`test_empty_db_bootstrap.py`/`test_metadata_invariants.py` 表清单移除、`ServiceAliasDetail.ext.test.ts` 删登记断言补下拉用例、`auditText.test.ts` 随处置调整。

---

## 4. 实施批次与验收门

每批过三侧门:后端 pytest / 前端 vitest+vue-tsc / plate pytest(不涉及则两侧)。依赖:批1→批2→批3 串行,批0 先行。

| # | 内容 | 规模 | 验收门 |
|---|---|---|---|
| **批0** | §3.4 四项盘点出档 + §3.5 特征化基线 | S | 基线全绿;盘点档入库(空也出档);据 ③④ 定批3 形态 |
| **批1** | plate:`kind` + 两张过滤清单落地(过滤面排除 + `/api/service` 全量打标签)+ `line` 规则 + **release 后 kind 不可变** + 声明闸两处钉住 + 投影按 kind 透出(含模板)+ 别名显式 `base_service` 接收/两项校验/下拉。**一页纸小设计已评审确认(2026-10-16,`claude/plate-external-batch1-design.md`)—— 九项细则 + 三微决策 + line 豁免 common 全定案** | S~M | plate 门全绿;过滤面逐面断言 + `/api/service` 反向断言;投影契约测试(含模板);别名校验用例 |
| **批2** | 平台切源:公共投影访问件(只覆盖外部消费点;query_views 迁移另立批,台账记目标态)+ §3.1 五直读点切源 + **三条件闸(外部 query_safe 首次生效)+ 漂移检测按身份模式处置** + fail-closed(沿用 channel 出口)+ TTL 上界显式配置 + **D-E 重填按钮 + D-F 编排器分组入口** | M | 三侧门全绿;基线改判用例(内联 POST+query_safe→放行);漂移三形态路径用例;**plate 停机演练三口径**(闸 fail-closed / 已缓存任务照常 / 写类无缓存拒绝) |
| **批3** | **批0 确认表 0 行则不写迁移脚本(C9 不产生)**,直接 drop;③④ 不为 0 则执行 §3.4 回填收口(定义→release→人工选 base_service);C1-C11 下线;0029 drop(编号已核空闲,head=0028);**W3 取代注记 + `docs/概念地图.md` 更新同批** | M | 三侧门全绿;grep 门禁(§6.3)零残留;迁移对账(若有迁移面);快照 fixture 真实执行 0029 通过 |
| **批4** | 活体收口:真实外部系统全链路(写定义→release→建场景(**D-F 不做则走导入,手册写明**)→集成任务→定时→卡片);手册合入(§6.4 + query_safe 作用范围 + 版本线/环境组 + 漂移修复路径);验收含「检查结果语义」(卡片「成功」须是每次检查的 check 结论;**验证不通过另立修复批,不阻塞批3**) | S | 活体验证记录;手册合入 |

---

## 5. 冗余/重复设计清理清单(实现后必须清)

**纪律:下线 = 物理删除 + grep 零残留 + 文档同步;保留项防误删。**

| # | 下线/处置对象 | 文件清单 | 批次 |
|---|---|---|---|
| C1 | `external_endpoints` 表 | 模型 `models/external_endpoint.py`;`models/__init__.py:20,51` 导出;alembic 0021/0022/0023/0026 历史链保留,新增 0029 drop | 批3 |
| C2 | 外部目录服务 | `services/external_endpoints.py`(520 行) | 批3 |
| C3 | 登记路由 | `routers/external_endpoints.py`(7 路由);`main.py:41,237` 两处注册 | 批3 |
| C4 | 前端登记面 + 审计动作 | `ServiceAliasDetail.vue` 登记交互;`api/external-endpoints.ts`;`auditText.ts` → 保留只读映射标「已退役」(审计 0 行则删);`services/audit.py:28` 动作表移除(历史审计行仍可读) | 批1(下拉)/批3(删) |
| C5 | 闸 ext: DB 分支 | `integration_runner.py:119-132`(含 `SessionLocal` 直连点) | 批2 |
| C6 | ext 组装代码 | `endpoint_catalog.py:102-127`;`run_precheck.py:161-196` | 批2 |
| C7 | 重复 schema→declarations 转换 | 唯一实现在 plate | 批2/3 |
| C8 | 「平台目录」裁定段(文档) | 三份集成线文档 + 架构设计 §详细设计 1;文档清理任务 W3 承接,与批3 同批 | 批3 |
| C9 | 一次性迁移脚本 | 批0 确认 0 行则不产生;产生则迁移完即删/置仓库外 | 批3 |
| C10 | 测试下线 | `test_external_endpoints.py`(删);`test_empty_db_bootstrap.py`/`test_metadata_invariants.py`(表清单移除);`ServiceAliasDetail.ext.test.ts`/`auditText.test.ts`(随 C4) | 批3 |
| C11 | 活文档更新 | `docs/概念地图.md:17`(外部锚点 → plate kind=external,与批3 同提交);`runbook-pg.md:104` 历史段保留 | 批3 |

---

## 6. 防再发机制:「一个功能一个实现」守门

### 6.1 真源台账(批2 交付 `claude/single-source-registry.md`)

| 能力域 | 唯一真源 | 禁止 |
|---|---|---|
| 被测接口定义 | plate(kind=sut,修订/钉定) | 平台侧接口定义表 |
| 外部工具定义(判定源) | plate(kind=external,系统级 latest) | 目录表/别名级重复定义/第二缓存 |
| 外部调用形态(执行源) | 场景步骤内联 | 执行链读 plate 取形态 |
| 别名 ↔ plate 系统映射 | `base_service`(外部显式选择,sut 派生;多对一;值域映射写死在校验函数;**release 后系统 kind 不可变**) | 第二映射/别名即本体/命名规约派生外部别名 |
| base_url/凭证绑定 | 平台 service_aliases | plate 存环境值 |
| 执行身份/调度/订阅 | 平台 integration_tasks | plate 感知执行 |
| signer 实现 | 执行侧 `@register_authenticator` 注册表 | plate 承载执行逻辑 |
| 取数视图 | plate query_views(仅 sut) | 外部挂载 |
| 定时调用外部系统 | 集成任务 | 取数视图/脚本旁路 |
| plate 投影缓存/熔断 | 公共投影访问件(query_views 迁移 = 目标态,另立批) | 自建缓存散用 |
| query→declarations 转换 | plate | 平台副本 |

**规则:新表/新缓存/新转换先查台账;无条目能力域评审先立条目再写代码。**

### 6.2 评审硬检查项(并入评审 checklist)

1. 第二真源/第二实现?(是 → 拒) 2. 两处消费走同一访问件?(否 → 拒) 3. 复制公共件而非复用?(是 → 拒) 4. 替换旧实现时删除落在哪个批?(无 → 拒) 5. 交付/取代某方案时文档状态行同步翻转?(无 → 拒)

### 6.3 技术锚点与 CI 门禁

- 投影缓存 = `query_view_cache.TtlLruCache` 载荷泛化件(三消费者共用先例),批2 公共投影访问件建于其上;
- **grep 门禁(四模式;单模式只扫到 10 文件漏 6 个)**:

```bash
grep -rnE "ExternalEndpoint|external_endpoint|external-endpoints|ext_svc" \
  src docs --exclude-dir=alembic --exclude-dir=node_modules
```

允许名单:`auditText.ts`「已退役」映射(若保留)、`runbook-pg.md` 历史段;快照 fixture 在 `scripts/` 不在扫描范围。批3 后入 verify_all。

### 6.4 运行手册:接入判定(批4 合入)

- **kind=external(轻)**:纯集成调用/工具;内联执行 + latest 判定 + 漂移检测;query_safe 仅平台模式硬约束,个人模式边界 = 用户本人在第三方的权限;
- **sut(正向接入)**:被测依赖;修订钉定/冷化/基线/覆盖统计;
- **被测系统本身作集成对象 → sut 锚点 + 修订钉定**,不得重登记 external;
- **两路互斥,一个系统一个 kind;改 kind = 换新系统名重新接入(plate check 强制)**;别名 kind 与系统 kind 一致(经值域映射);外部别名 `base_service` 显式选择,无命名规约;
- **真实差异出口**:同系统多实例 API 确不同 → 拆两个 plate 系统(`jira-dc8`/`jira-dc9`),两别名分别映射;
- **已知副作用**:plate 不可达时外部别名无法新建(与 sut 一致);漂移修复 = D-E 重填按钮 + 手工路径。

---

## 7. 风险与悬置项

| # | 风险 | 评估 | 缓解 |
|---|---|---|---|
| R1 | plate 停机影响面(执行不依赖;影响预检/闸/漂移/视图/别名新建) | 中可控 | §2.4:缓存 stale-while-error + TTL 总上界 + fail-closed;批2 停机演练三口径 |
| R2 | 外部定义编写门槛(UI 导入 → md+release) | 中 | 人/Agent 主线 + 手册样例;D-E 重填按钮;D-F 编排器分组入口(已定案);CLI 导入器留 task 5 |
| R3 | 治理现实(git 口径下 branch protection 单人结构强度有限) | 中 | 硬护栏 = 三条件闸 + 漂移检测(代码强制);branch protection 加分项 |
| R4 | 过渡期双源漂移 | 低(表预期 0 行) | 冻结→核对→drop;禁双写 |
| R5 | 过滤完备性双向(过滤面漏一处 external 漏进 / 不得过滤面误伤 `/api/service`) | 中 | 批1 过滤面逐面断言 + `/api/service` 反向断言 + plate check 反向断言 |
| R6 | 决策疲劳/第四次反转 | 低概率高代价 | §0.3 入档;批3 物理下线不可逆显性化;§0.1 唯一口径 |
| R7 | 第三方 schema 质量 | 低 | 告警放行语义原样搬运(C2);批0 基线 |
| R8 | 迁移空档(§3.4:存量别名解析断链、存量 ext: 场景预检失败) | 低(平台未上线) | 批0 ③④盘点;批3 回填收口(定义→release→人工选 base_service);0 则不存在 |

**悬置项(批4 活体核实)**:①只读场景对 Jenkins/Jira 推送类集成的支撑(判定:不能,已知边界;个人模式写类任务不受此限);②卡片「成功」语义(确认消费 check 结论;不通过另立修复批,不阻塞批3)。

---

## 8. 决策项

| # | 问题 | 结论 |
|---|---|---|
| D-A | plate 建模 | **定**:复用 `ServiceDefinition.kind`,过滤标签;值域映射 `plate ↔ sut` |
| D-B | `ext:` 语法 | **定**:保留;执行按内联、判定按 latest |
| D-C | query_safe 治理 | **定**:git 口径;硬护栏 = 闸 + 漂移检测 |
| D-D | 外部端点挂取数视图 | **定**:不挂 |
| D-E | 漂移修复动作 | **定**:做 ——「按 latest 重填形态」按钮,批2 交付 |
| **D-F** | 编排器外部步骤新增入口 | **定:做 · 同列表按 kind 分组(owner 2026-10-16 提议并确认)** —— 选接口的同一选单分两个 scope:「被测接口」分组(纯 sut,钉定修订语义)与「第三方集成」分组(按 kind 展示 external);选第三方后走 别名(实例)→ 该别名所指系统 latest 端点 → 生成 `ext:<alias>.<name>` 并按定义填内联形态 —— 与 D-E「按 latest 重填」**同一填充函数的两个触发点**,非新模块;防混淆 UI(如第三方步骤标注「latest 解析 · 漂移检测守护」)批1 小设计细化;过滤面口径同步调整为「编排选单被测分组」(§3.3) |

## 9. 修订记录(逐轮;评审记录不入仓,拍板见文档清理任务 §0 原则 6)

| 版本 | 轮次/项数 | 要点 |
|---|---|---|
| v0.1 | 初稿 | 五批骨架 + 清单 C1-C8 + 真源台账 + R1-R8 |
| v0.2 | r1 / 10 | 照常 release,`ext:`=latest;删 ext-directory 与 CLI 导入器提前;删上线类护栏;signer 留执行侧;执行器无 ext 解析;sut 作集成对象走 sut 锚点 |
| v0.3 | r2 / 13 | 执行按内联、判定按 latest;预检漂移检测;闸三条件;fail-closed;无 release 预检失败;批3 终点 release;不进版本线/环境组 |
| v0.4 | r3 / 10 | 目录按系统 + base_service 多对一;漂移进定时路径;形态一致口径;版本边界入清单;TTL 上界;归并对账 |
| v0.5 | r4 / 8 | 处置按任务类型;占位符匹配;kind 一致校验;拆系统出口;D-E 定案做 |
| v0.6 | r5 / 16(代码审计) | 闸缺口定性更正(内联优先,外部 query_safe 从不生效);处置键改身份模式;D-F 新增;外部别名派生改法;值域映射;`line` 规则;直读点 5 个+保留清单;C10/C11;grep 四模式;表预期 0 行 |
| v0.7 | r6 / 10 | 外部别名 base_service 显式选择(推翻派生+命名规约案);「不得过滤面」清单(`/api/service`);全文轮次出处清理 |
| **v0.8** | r7 / 4 + 全量整理(r7 为口头结论,未出评审记录) | ①**存量盘点增至四项**(增「存量 ext: 场景数」);②**迁移空档入档**(§3.4:存量别名解析断链/存量场景预检失败,批3 回填收口 = 定义→release→人工选 base_service,不能提前到批1);③**release 后系统 kind 不可变**(plate check 规则,批1 与 line 同批;手册条由代码强制);④文档口径统一(docs-cleanup 版本号与轮次残留清理)。**章节按终态全量重排**:背景论证(§0)/目标形态(§1)/安全与漂移模型(§2)/现状与迁移面(§3)/批次(§4)/清理(§5)/守门(§6)/风险(§7)/决策(§8),版本痕迹集中于 §9。 |
| **v0.8.1** | owner 决策轮(2026-10-16) | D-A~D-F 全部定案:**D-F = 做 · 同列表按 kind 分组**(owner 提议:第三方集成作为同选单的独立 scope;回到 G6 原案「选单按 kind 过滤」表述,机制与独立入口方案完全一致);§3.3 过滤面「编排被测选单」口径调整为「编排选单被测分组」;同轮拍板:W0 文档入库(00c7b3fc)、存量评审旧档三份删除方向、批0 暂缓待排期。§9 v0.8 行出处改 r7/4(口径统一);§3.1 第 5 行补「漂移检测移出平台模式分支」(§2.2 实现要点同步)。 |
