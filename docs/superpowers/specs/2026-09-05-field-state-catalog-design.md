# 字段状态目录化 — children 结构树 + state 共识默认 + 场景稀疏覆盖

> 状态:**设计定稿待评审后实施**(2026-09-05,与用户逐条确认 P/B/F/T 功能点清单后落稿)
> 日期:2026-09-05
> 前置:IO 声明归一化(2026-09-01,P3 已执行);场景级 binding 配置设计(2026-09-04,**本稿实质修订并取代其存储模型 §2/§3 与消费面 §4** —— 保留其 channel 退役主旨,更换承接机制)
> 分支:`feat/field-state-catalog`(自 `feat/io-declarations-and-strategy-badges` 切出)
> 实施注记:io_spec 重写(P1~P7)已在分支先行落地验证,以本稿为权威依据对齐

---

## 0. 背景与方案演进

### 0.1 从 2026-09-04 方案出发的三步演进

09-04 方案的骨架(channel 退役 + step.bindings 清单 + endpoint_binding_sets 基线表)在评审讨论中经三步演化定型:

| 步 | 演化 | 动因 |
|---|---|---|
| ① | **children 内联树取代 schema_** | schema_ 零真实消费方(前端不读、后端仅查存在性);嵌套结构需要"可声明、可追踪、可注入",结构真源应与字段身份同处 —— 条目直接挂 children,模板路径实例化归渲染器 |
| ② | **勾选清单 → 字段状态(state 属性)** | 清单与属性工作量等价(一个维护 list 供查询、一个在字段上定义供过滤);一致化裁决:字段的一切决策都应是字段上的属性 —— 全系统只剩一种查询形态(filter over fields),不再有 membership 查询 |
| ③ | **默认状态回归 plate + step 稀疏增量覆盖** | 判断分两级:共识级默认(低频,随接口版本/长期共识)与语境级定制(高频,每业务每场景)。高频流量被 step 覆盖抽干后,plate 承载低频共识的发版成本可承受;场景只存稀疏增量,未覆盖字段跟随默认(共识修复自动传播) |

### 0.2 与 09-04 方案的对照(本稿改了什么)

| 09-04 方案 | 本稿 | 理由 |
|---|---|---|
| channel 从条目删除,无线索字段 | 条目增 `state: form\|collapse\|carry`(三态) | 共识级默认住 plate(用户裁定);collapse 补足渐进披露的中间态 |
| `step.bindings: list[str]`(冻结全量) | `step.field_states: {path → state}`(稀疏增量,默认不存) | 读穿默认:零迁移、零存储;共识修复传播、显式覆盖受保护 |
| `endpoint_binding_sets`(PG 新表,seed 18 份) | **死亡** —— 基线就是条目上的 state | 少一张表、少一条读穿链、冷启动零配置 |
| 存量 step 一次性回填(M2 ③ 测试) | **死亡** —— 读穿即等价 | 无迁移 |
| Type C 残余(schema − 目录) | **死亡** —— 目录即宇宙;残留 body 键归前端「其他字段」区 | schema_ 退役后无差集来源 |
| 渐进披露 = 搜索框添加(唯一机制) | 字段状态控制为主(行尾控制/折叠面板),搜索框降级为定位手段 | 用户裁定:直接控制,不经过"添加进清单" |
| 挂账:refine 管线(身份勘误回流) | **溶解** —— 只有 absorb(生成,挂账)与手编(补全),皆 plate 家务 | 避免虚构子系统 |

### 0.3 沿用的事实与案例(09-04 §0.2)

- 规模:18 端点(fin 17 + account 1),631 声明 = 532 binding + 99 carry;
- `$.action` 通道分歧(entrust_order_add=binding / order_book=carry)→ 本稿下 = 两端点各自的 state 盖戳,且任何场景可即时覆盖,定错不堵人不发版;
- channel 定错的旧修复成本(plate 改码 + golden 重钉 + 发版,$.action 翻面 = 1253 行)→ 新形态下的逃生门是场景覆盖(即时),默认修正仍是发版(低频、git 评审留痕)。

### 0.4 需求追溯表(用户预期 → 设计落点)

| 预期需求(原话要义) | 设计落点 | 章节 |
|---|---|---|
| 统一的字段属性定义 | DeclarationEntry 单一模型;字段的一切决策皆属性(一致化) | §1.4 / §2.1 |
| 嵌套结构**可声明** | children 内联树(模板态 path,仅容器可带) | §2.1 / §2.4 |
| 嵌套结构**可注入** | carry 容器整传(子孙闭包)+ `${var}` 整体类型保持(§4 注) | §2.2 / §4 |
| 嵌套结构**可追踪** | 响应面同款 children 树 + assertable;path 寻址(三层宪法) | §1.1 / §2.6 |
| list 可填多个相同字段(含再嵌套) | buildNode 数组行组:行数跟 body、加行 = 模板壳、行内递归(list 套 list) | §5.2 / §5.3 |
| 可拿到完整的 list | 容器 state=carry ⇒ 整容器值表注入(类型保持) | §2.2 / §3.2 |
| 前端渲染嵌套结构(原不确定性) | 值 × 结构合并树,四节点分发,`[i]` 实例化仅渲染器 | §5 |
| 200+ 字段接口维护成本 | 目录全量一次登记;深实例条目缩并;absorb 挂账承接未来新端点 | §6 M1 / §10.1 |
| 判断成本降到接近零 | 共识(plate,低频)/ 语境(step,高频)两级分层 + 场景覆盖逃生门 | §1.2 / §1.3 |
| 默认规则放 plate | entry.state 共识默认,git 评审 + golden 留痕 | §2.1 / §3.3 |
| 平台存 scenario 映射配置 | step.field_states 稀疏增量(默认零存储) | §3.1 |
| 后续可对字段升降级 | 增量本身 = 统计语料;L1/L2 闭环挂账(人在环) | §10.2 |
| 不用勾选,用字段控制 | 字段行尾状态控制;搜索框降级为定位手段 | §5.4 |
| scenario 不自带接口定义 | 读穿默认 + 稀疏增量:未定制场景零存储 | §3.1 / §3.2 |
| absorb 暂不实现 | 挂账首位;18 文件迁移不依赖它(脚本吃现有数据) | §10.1 |

### 0.5 已否决形态存档

| 形状 | 否决理由 |
|---|---|
| step.bindings 勾选清单 | 与字段属性等价但不一致化;仍需外部基础集兜底,判断载体从字段漂移到清单 |
| 场景冻结全量状态 | 把所有场景当"有意见"处理:存储重、共识修复无法传播;漂移风险已由 plate 默认的 git 治理(评审+golden+可回滚)重新定价 |
| 默认状态住 platform PG | 心智模型分裂(字段属性两处)、冷启动需 seed、多一次 join;高频流量抽干后 plate 发版成本可承受 |
| scenario 私藏字段定义 | 场景自带接口定义 = 冗余副本 + 漂移(用户否决:"不又变成 scenario 自己保存一套接口定义了么") |
| 升降级自动写回 plate | 写代码文件丑;L2 统计本就挂账,过渡形态 = 统计建议 → 人在 absorb 重生成/手编时应用 |

---

## 1. 设计原则(硬性)

| # | 原则 | 内容 |
|---|---|---|
| 1.1 | 三层宪法 | **path**(语言,寻址真源)/ **DeclarationEntry**(数据,身份+结构+共识默认)/ **纯函数算法**(解析:渲染 buildNode、注入解析链)。三层解耦,任何新需求先过三问:是路径问题、数据问题还是算法问题 |
| 1.2 | 判断两级分层 | 共识级默认(plate `state`,低频,git 评审 + golden 留痕)/ 语境级定制(step `field_states`,高频,即时生效)。**高频住可编辑层,低频可住发布层** |
| 1.3 | 防复活护栏 | state ≠ channel 还魂,差别有且只有一条:**场景级覆盖权存在且即时生效**。默认是起点,不是裁决 |
| 1.4 | 一致化 | 字段的每个决策都是字段上的属性:渲染读 `state`、注入读 `type`、控件读 `ui_kind`、必填读 `required`。全系统唯一查询形态 = 遍历字段读属性(filter),无 membership 查询 |
| 1.5 | 模板/实例分离 | 目录 path 一律模板态(children 子树内禁 `[i]`);下标是渲染器实例化的产物。防第二套寻址系统 |
| 1.6 | 消费纪律(B6 软化) | default/example 全条目合法(表单角色元数据);注入只读 path/type,值不回流 —— 保证点从构造校验后撤到消费端 |
| 1.7 | 一次性切换 | 适配完全部存量后单部署翻面,内网单体无错配窗口;不做双轨 |

---

## 2. plate 目录模型

### 2.1 DeclarationEntry 定稿

```python
class DeclarationEntry(BaseModel):
    name: str
    path: str
    type: str                      # 升格:全条目必填,限六原语
    state: Literal["form", "collapse", "carry"] = "form"
    required: bool = True
    default: Any | None = None     # 表单角色元数据,全条目合法(§1.6)
    example: Any | None = None
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: ... = "unknown"
    source_kind: ... = "independent"
    assertable: bool = False       # 仅响应侧有意义
    children: list["DeclarationEntry"] | None = None   # 仅 object/array 容器
```

- **state 语义**:`form`=表单直渲染(值在 body)/ `collapse`=折叠面板内渲染(值仍在 body,纯布局,**不碰注入边界**)/ `carry`=不渲染,值表注入。响应面无视此键(§2.6);
- **默认 form 即 fail-closed**:目录残缺的表现是"全都渲染、零注入",字段不会莫名消失或被注入;
- **children**:递归内联树;仅容器(type=object/array)可带且须非空;child.path 为父 path 的模板态后代;
- **ui_kind / source_kind 留目录作基线**(无语境时的缺省渲染提示/值来源语义):v1 无覆写需求,装饰缝挂账(§10.4)将来可由 step 侧覆写 —— 归属铁律不破坏。

### 2.2 校验族谱

| 族 | 规则 | 去向 |
|---|---|---|
| B4 | body_type=none ⇒ 零声明 | **保留** |
| B5 | carry 条目 type 必填 | 消亡 → 无条件化(全条目必填) |
| B6 | carry 禁 default/example | 消亡 → 消费纪律(§1.6) |
| B7 | 通道-规格闭合 | 消亡(无通道;响应面单脸由"state 无视"实现) |
| D2 | 通道路径形态 | 消亡 → children 子树模板纪律(条目级)+ 配置编辑校验(平台侧) |
| D3 | 包含四格 | 消亡 → **单规则继任:carry 容器 ⇒ 子孙必 carry**(整容器传递,一树一主) |
| 新 | 模板纪律 | ① children 仅容器;② children 子树 path 仅 FIELD 节点(顶层条目路径形态自由 — 响应断言候选可带实例下标);③ path 全树唯一 + name 顶层全局唯一/同级唯一(fields_meta 键控面在顶层;树内节点前端键是 path) |
| 新 | 整传一致性 | carry 容器 ⇒ 子孙必 carry |

### 2.3 schema_ 退役

- RequestSpec/ResponseSpec 的 `schema_` 字段、`json_schema()` 方法、"body_type≠none 须 schema_" 规则全数删除;
- 依据:全仓消费方验证 —— 前端从不读取,plate 内部仅构造参数传递与存在性检查;结构职能由 children 内联树完整承接;
- wire 影响:/full 与导出产物不再含 `schema` 键(golden 重钉覆盖);Type C 第三落点(schema − 目录差集渲染)随之死亡,目录外 body 残留键由前端「其他字段」区兜底展示(§4)。

### 2.4 深实例 path 退役

`$.supplier[0].order_supplier_id` 类深实例条目从目录消失 → `$.supplier` 容器(模板)+ children。**请求面目录只存模板态**;实例化(`[i]`)唯一发生在渲染器 buildNode 的 array 分支(§5)。迁移时深实例条目的 default/example/enum 等元数据并入对应模板叶子。(校验口径:children 子树内 path 一律模板态;顶层条目路径形态自由 —— 响应断言候选可带实例下标,见 §2.2 新②。)

### 2.5 declare() 糖重写

`RequestSpec.declare(model, *, body_type, states)` / `ResponseSpec.declare(model, *, status, assert_paths)`:
- 递归走 schema properties:顶层成条目,object→properties 递归,array→items(object)递归;items 为原语或开放字典(additionalProperties)则无 children;
- type 从节点吸收(含 anyOf/oneOf 的 Optional 剥 null;`$ref` 单层解析),吸收不到即构造错误(拒静默垃圾条目);
- `states={path 或顶层短名 → state}` 盖戳共识默认;assert_paths 置 assertable(B3 保留);
- 旧通道参数(bindings/carry/view_only)删除。

### 2.6 响应面单脸

响应声明无 form/carry 之分:state 不被读取,面 = 全量 + `assertable` 标记。按场景挑断言/展示面为远期挂账(§10)。

### 2.7 公共投影工具

`iter_declarations(entries)`:深度优先展开 children 树(先序)—— field_defaults / export / 前端投影共用的唯一展开入口,防各处自行遍历漂移。

---

## 3. 场景侧稀疏覆盖(platform)

### 3.1 step.field_states 形态

- step 顶层新增 `field_states: {归一化 path → state}`,与 api/request/strategy 平级(描述 step 的配置意图);
- **默认不存**(空 step 零存储);仅存与共识默认不同的条目;
- 增删即稀疏写入:添加字段 = 增量[path]=form/collapse;移除 = 增量[path]=carry;任何状态值合法(新增与移除同机制);
- 随场景资产导出/导入保形(自含,不依赖平台库)。

### 3.2 状态解析链(单一实现)

```
state(path) = step.field_states[path] ?? entry.state ?? 'form'
```

所有消费方(注入/值表候选/导出/表单定面)共用同一实现函数,禁止各自散写。

### 3.3 漂移语义(与 09-04 冻结语义的差异)

- plate 默认变更 = 显式发布(改文件、过评审、golden 重钉、git 可回滚)→ 在此治理强度下,**共识修复理应传播**:未覆盖该字段的场景自动受益;
- **显式覆盖受保护**:场景明确表达过意图的字段,任何默认变更不动它;
- 这是标准分层覆盖语义(system → local):上层修复惠及下层,下层显式意见优先。冻结模型把所有场景当"有意见",存储与心智皆重,已否决(§0.4)。

### 3.4 兜底与防御

| 情形 | 行为 |
|---|---|
| step.field_states 缺失 | 读 entry.state(读穿,零迁移的等价性来源) |
| entry 无 state(理论不至:默认 form) | form —— fail-closed:零注入 |
| field_states 含目录外 path | 交集容忍(忽略),composer 显示 stale 警告 |
| plate 不可达(注入侧) | 空面 → 不注入(降级语义不变) |

### 3.5 配置编辑校验(平台侧,D2/D3 的语境继任)

| 校验 | 规则 |
|---|---|
| 树一致性 | **合成态**(plate 默认 + step 增量合并后)满足:carry 容器 ⇒ 子孙 carry |
| required 落 carry 软警告 | 必填字段被划出 form 面 → 提示"确认值表有兜底,否则请求必挂" |
| DESCRIPTIVE 软警告 | 备注族(remark/notes/cancel_remark 词表,platform 常量,seed 自 plate 政策测试)进 form 面 → 提示 |

---

## 4. 消费面改造

| 消费方 | 现状读法 | 新读法 |
|---|---|---|
| `carry_injection._carry_face` | /full 过滤 `channel=="carry"` | /full 读目录,解析态 == 'carry'(join step.field_states);T8 索引契约、降级语义不动 |
| carry 路由 `service_fields`(值表候选面) | carry 通道条目 | 解析态 == 'carry'(端点级:entry.state;值表是环境级,跟共识默认走) |
| plate `field_defaults` | binding 通道条目 | **全量**(iter_declarations 展开,含嵌套叶子 — 行壳预填用);platform 按解析态过滤 |
| plate `failed_resolver` | view_only + assertable | `assertable`(响应单脸) |
| plate `export/platform.py` | carry/binding/view_only 三面过滤 | carry 面 = state=='carry' 路径透传字面量(含整容器);form/collapse 面 = body 补全(fields_meta 顶层键控,树全量展开携带 state/children);响应 = 全量。场景解析态穿线为挂账细化(§10),M1 以 entry.state 为面基准(读穿等价) |
| 前端 `declarations.ts` | channelFields/carryPaths/assertablePaths | 状态过滤投影;deriveParent(D12)/deriveDeepRows(D9)死亡 |
| 前端渲染 | 平铺行 + 深层派生行 | **buildNode 值×结构合并树**(§5) |
| 前端「其他字段」区 | 顶层平铺键 | 扩展承接目录外 body 残留键(深浅皆收,Type C 继任) |
| 18 端点文件 | channel 逐条钉死 + 深实例条目 | state 盖戳 + type 回填 + children 树化(P8 迁移脚本) |

**机制依赖注**:整容器/整 list 注入依赖 gimbal 执行核 resolver 的 `${}` 整体类型保持(`_resolve_value`:整体为单个 `${}` 时保留原始类型,已代码验证)与 JSONPath 子导航 —— **本设计不改动 gimbal 执行核(resolver/jsonpath/context)一行**;platform 注入只是把值表值物化进 step,运行时解析走既有机制。

### 4.1 冗余/兼容代码清理清单(2026-09-05 全仓检索定性)

全仓 grep(channel / view_only / binding 通道轴 / fields_meta / parentChannel / schema_ / bindings)逐命中定性,分四类处置。**§4 表未列出的新发现:platform 后端 `carry_store` 与 `adaptation_ops` 两个通道读取轴**(09-04 §4 曾以"按轴 grep 盘点"挂账,本清单即盘点结果)。

**(a) platform 后端 — 通道读取轴(切读,非删除)**

| 文件:行 | 现状 | 处置 |
|---|---|---|
| `carry_injection.py:44` | `e.get("channel")=="carry"`(运行时注入面) | §4 表内:解析态 == 'carry' |
| `carry_store.py:91` | 同款 carry 面投影(值表绑定健康检测:bound − face = orphaned) | **切读**:解析态 == 'carry'(端点级 entry.state,与 service_fields 路由同口径 — 值表是环境级,跟共识默认走);注释"与 carry_injection 同款投影"同步更新 |
| `routers/carry.py:106` | `entry.get("channel") != "carry"`(service_fields 值表候选面) | §4 表内:解析态 == 'carry' |
| `adaptation_ops.py:41` | `_field_map` 过滤 `channel=="binding"`(catalog 版本 diff 的字段宇宙) | **切读**:全量目录(去通道过滤)—— diff 语义随之泛化:addField/removeField 对全目录生效,不再只盯 binding 面 |
| `routers/endpoint_catalog.py:43` | 注释提及 view_only/assertable | 注释更新(单脸语义) |
| `plate_client.py:129` | 注释提及 fields_meta | 注释更新(fields_meta 键控面随 M1 携带 state/children) |

**(b) 前端 — 投影与类型(重写)**

| 文件 | 内容 | 处置 |
|---|---|---|
| `types/plate.ts` | `DeclarationEntryView.channel`(L100)、`IOFieldBinding.parentPath/parentChannel`(L79-81)、`fields_meta` 类型(L256) | 类型重写:channel→state、parent 系删除(树由 children 承载)、fields_meta 值形更新 |
| `utils/declarations.ts` | channelFields / carryPaths / assertablePaths / deriveParent / deriveDeepRows | 全量重写(§4 表内:状态过滤投影;deriveParent/deriveDeepRows 死亡) |
| `CaseComposerCanvas.vue:1087`、`CaseComposerCatalog.vue:351` | `channelFields(…, 'view_only')` 响应面投影 | 改状态投影(响应面单脸 = 全量 + assertable) |
| `CaseComposerCanvas.vue:551/1011/1063` | fields_meta 废弃注释 / view_only 注释 | 注释更新 |
| `FieldForm.vue:581-588` | `parentChannel`/`parentPath` 行尾"上级 X(carry)"标题 | 删除(D12 消费点;children 树下由容器节点标题天然表达) |

**(c) 测试重钉**

| 范围 | 文件 | 处置 |
|---|---|---|
| plate 模型直测 | `test_deep_path_declarations.py`(D1-D3:D2/D3 死,D1 name 制存活)、`test_io_declarations_p1/p2/declare`(B5/B6/B7 用例死,新模板纪律/整传一致性用例) | 重写(§7②③) |
| plate 消费方 | `test_http_field_defaults.py`(全量化新形状)、`test_http_failed_resolved.py`(assertable 单脸) | 更新 |
| plate 导出系 | `test_v3_export_platform.py`、`test_v3_export_roundtrip.py`、`test_v3_export_gimbal.py`、`test_case_exporter.py`、`test_export_protocol.py` | 随 export 三面切读更新 |
| plate 政策守卫 | `test_v3_systems_fin.py::TestCarryFacesAllEndpoints` | 退役(§9 验收项) |
| plate 通用回归 | `test_v3_schema_closed.py`(pydantic 封闭性,非 schema_ 守卫)、`test_v3_schema_consistency.py`(§7.6 平台视图扩展契约,与通道无关) | 微调(channel 键从 fixture 消失后自动跟随,个别断言查引) |
| golden | `test_io_declarations_golden.py` | 全量 re-baseline(P9) |
| fixtures | `sample_endpoint.py`、`conftest.py` | 随新模型重写 |
| 前端 | `declarations.test.ts`(D12 套件)、`FieldForm.deep.test.ts`(裁定 14)、`FieldForm.test.ts`、`CaseComposerCanvas.test.ts` | 随投影/渲染器重写 |

**(d) 明确非清理项(登记防误伤)**

- `$.channel` 作为**数据字段名**出现于 carry-entries / carry-hint 测试 —— 是业务字段路径,不是通道轴;
- carry 值表自身的 `bindings` PG 概念(path→值映射)—— 与已死的 step.bindings 同名异义,保留(命名碰撞知悉即可);
- gimbal 执行核单测:`tests/unit/test_resolver_list_body.py` / `test_str_body.py` / `test_call_str_body.py` / `test_defects` —— `${}` 整体类型保持的机制守护测试,**本设计的依赖凭证,必须保留**;
- 09-04 §3.1 step.bindings 从未落地,全仓无残留,零清理;
- `scripts/` 目录零通道轴残留(已 grep 确认)。

---

## 5. 渲染模型(值 × 结构合并)

### 5.1 三输入

① 目录(plate /full:条目 + children 模板,含 state)/ ② 意图(step.field_states 增量)/ ③ 值(step body)。

### 5.2 buildNode 递归算法

```
buildNode(entry, templatePath, bodyValue):
  实例路径 = templatePath                      # 目录态无下标
  if entry.children is None:  return 叶子节点   # 元数据 × 值
  if entry.type == 'object':  return 对象节点   # 子节点 = children 递归(拼 '.key')
  if entry.type == 'array':                    # 行数跟 body、结构跟目录
    rows = (bodyValue ?? []).map((item, i) => children 递归(拼 '[i].key'))
    return 数组节点(行组, rows, children 模板)  # 加行 = 模板实例化空壳 [len]
```

三条铁律:模板路径与实例路径分离(`[i]` 只在 array 分支出现)/ 行数跟 body、结构跟目录 / children 是唯一结构真源。

### 5.3 四种节点

| 节点 | 组件 | 行为 |
|---|---|---|
| 叶子 | FieldForm 行 | ui_kind 选控件,required 标星,enum 下拉,default 预填 |
| 对象 | 折叠面板 | 标题 = name,展开递归 |
| 数组 | 动态行组 | 行内递归(支持 list 套 list);加行 = 模板壳;行尾删除 |
| 开放字典 | KV 编辑器 | object 无 children(additionalProperties 字典) |

### 5.4 定面与交互

- form 面 = 解析态 form 的条目(直接渲染);折叠区 = collapse;carry 不进树(搜索语料);
- 字段状态控制:字段行尾状态下拉/移除(写 step.field_states 增量);搜索框 = 定位手段(找到字段后改状态),不是添加机制;
- 值回写走 body(setValue + 既有 D8 深层剪枝);状态回写走 field_states —— 两通路分离。

---

## 6. 迁移(分支内分段验证,master 一次切换)

### M1 — plate 目录化

1. io_spec 重写(§2:P1~P7,已在分支落地);
2. 3 个运行时消费方切换(field_defaults 全量化 / failed_resolver 单脸 / export 按 state 定面);
3. **P8 迁移脚本**:18 端点文件 —— channel→state 盖戳(机械变换:binding→form、carry→carry、view_only→form 无视)、532 条 type 回填(schema_ 节点吸收;空 schema 端点自 default/example 值推断,推断不出显式补)、深实例条目缩并为容器模板 + children(元数据并入模板叶子);
4. golden 全量 re-baseline(新形状:无 channel、有 state、type 全备、children 树、模板 path),fixture 入库,意识性重钉。

**门禁**:plate 套件全绿 + golden 新基线入库。

### M2 — platform 配置器化

1. step.field_states 读写 + 解析链单一实现(§3.2);
2. 四线切读:carry_injection / 值表候选面 / field_defaults 消费 / export(§4);
3. 前端:declarations.ts 重写 + buildNode 渲染器 + 字段状态控制 UI + 「其他字段」区扩展 + 类型更新;
4. 配置编辑校验(§3.5)+ channel 读取轴全量 grep 清零(残读即事故)。

**门禁**:backend / frontend 套件 + vue-tsc 0 全绿。

### M3 — 对拍验证与切换

1. 三套件全绿(基线以切换时点实测重钉);
2. **A/B 对拍**:切换前后同批场景 dispatch 物化终值全等(等价性来源:盖戳 = 今日通道面 + 读穿语义 + 场景尚无增量);dispatch 基线重钉;
3. 单部署翻面;回滚 = revert 部署。

**与 09-04 迁移的差异**:无 PG 建表、无 seed、无存量 step 回填、无冻结机制。

---

## 7. 测试矩阵

| # | 测试 | 内容 | 阶段 |
|---|---|---|---|
| ① | golden 新形状 | 全 18 端点 /full declarations:无 channel、有 state、type 全备、children 树、模板 path | M1 |
| ② | 模板纪律校验 | 叶子带 children 拒 / children 带下标拒 / 非后代 path 拒 / path 全树唯一 / name 顶层+同级唯一 / carry 容器带非 carry 子孙拒 | M1 |
| ③ | declare() walker | 嵌套 schema → children 树;states 盖戳;$ref/Optional 吸收;无 type 节点构造错 | M1 |
| ④ | 增量解析链 | 空 step 读穿 / 增量命中 / entry 无 state → form / 目录外 path 交集容忍 | M2 |
| ⑤ | 配置校验 | 合成态树一致性拒;required 落 carry / DESCRIPTIVE 软警告触发 | M2 |
| ⑥ | 降级语义 | plate 不可达 → 空面不注入 | M2 |
| ⑦ | roundtrip | step.field_states 随场景导出/导入保形 | M2 |
| ⑧ | A/B 对拍 | 切换前后同批场景 dispatch 物化终值全等 | M3 |
| ⑨ | 三套件基线 | plate / backend / frontend + vue-tsc 0 | 各段门禁 |

---

## 8. 风险表

| 风险 | 缓解 |
|---|---|
| plate 默认变更影响面 = 所有未覆盖场景 | 设计意图(共识修复传播);git 评审 + golden 重钉 + A/B 对拍兜底;显式覆盖受保护 |
| state 沦为 channel 还魂 | 护栏 §1.3:覆盖权在场景侧且即时 —— 验收项(§9) |
| carry_injection 是运行时关键路径 | 解析链单一实现 + T8 索引契约不动 + 降级语义不变 + A/B 对拍(⑧) |
| children 树化迁移错漏(18 文件重构) | P8 脚本机械变换为主 + golden 全量对拍 + 计数断言(631 条守恒,深实例缩并单列) |
| 空数组渲染不出模板 | buildNode 结构跟目录:空数组 = 零行 + 加行按钮(模板壳) |
| 目录外 body 键静默丢失 | 「其他字段」区兜底展示(§4) |
| 全局默认同名 path 泄漏面变化 | 值表门控兜底(无值不注);漂移告警挂账(§10) |
| golden 重钉的自适应吸收 | fixture 入库,意识性 re-baseline 流程 |

---

## 9. 验收清单

- [ ] /full declarations:无 channel、有 state、type 全备、children 树、模板 path,golden 新基线入库(①);
- [ ] schema_ 全链清零(条目字段/方法/wire 键/Type C),grep 无残读;
- [ ] channel 读取轴 grep 清零(§4.1 四类清单全处置:plate 三消费方 + platform 六文件 + 前端投影/类型/注释 + 测试重钉;非清理项白名单除外);
- [ ] 同批场景切换前后 dispatch 物化终值 A/B 全等(⑧);
- [ ] 场景覆盖即时生效:改 field_states 增量 → 表单定面/注入面随动,零发版(护栏 §1.3 验收);
- [ ] buildNode 渲染:嵌套表单/数组行组(加行模板壳/list 套 list)/开放字典可用;D9/D12 死亡确认;
- [ ] 配置编辑校验 + 双软警告生效(⑤);
- [ ] `TestCarryFacesAllEndpoints` 退役,DESCRIPTIVE 词表落户 platform 常量;
- [ ] 三套件 + vue-tsc 0 全绿,dispatch 基线重钉(⑨)。

---

## 10. 挂账

1. **absorb CLI**(用户明示推迟):curl JSON → 端点文件一步生成(条目+children 树、类型推断、state 盖戳)—— 现有收集工具为零,新接口接入的产能环节,改造完成后立项;
2. **L1/L2 升降级闭环**:field_states 增量 = 天然统计语料;L1 错误驱动选完存默认、L2 频率统计建议调 plate 默认(人在环:absorb 重生成/手编应用);
3. **L3 流量挖掘**(collector 插件已存);
4. **装饰词表**(label/order/when/readonly/语境默认值):认领制;step.field_states 形状为 map,升级纯加性;
5. **响应面可配置**(按场景挑断言/展示面);
6. **export 场景解析态穿线**:M1 以 entry.state 为面基准,M2 细化 step 增量穿线或平台侧差集;
7. **值表同名 path 漂移告警**;
8. **carry 空转检测**;
9. **plate 存储形态升级**(文件 → 可写层):默认修正在低频下可承受发版;若频率上升,升级为 plate 内部事务,边界不动。
