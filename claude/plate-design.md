# Plate 结构设计

> 基线：`feat/executor-v2.1-fusion` @ 8281802。
> 版本：2026-10-07 按「核心需求 → 核心定义」重写；同日修订：原生写作取代抽取器流水线、增加承载度一节、NEIGHBOR 列入延后事项；确立主线流程「编写 → 评审 → 入库」，自动生成工具归为非主线（冲突记录见附录 C）；协议表述按执行器已协议中立修正；补充平台依赖能力的影响评估、消费方版本规则、逻辑闭环核对、面向 Agent 的补充、使用指南，以及第三、四轮 review 的一致性修正（删除接口时间戳与契约版本、交付件清单与 gaps 统一、块信封、交付物「类型」改名、补齐设计类模板）。2026-09-29 ~ 10-07 期间提出、后被取代的方案移入附录 A。同日修订二（按当前实现核对后定稿）：`consumes` / `produces` 定为生产 / 消费语义（存量 MIME 取值弃置）；成功基准 = 数值最小的已声明 2xx；「无损往返」定义为语义等价并确立规范形规则；前端直连 plate 的 4 个 dim 查询与 1 处 `endpoint` 直拉补入影响评估；批次 A 拆分为 A1 / A2 并上调估算；`spec_json` 迁移增加前置检查。勘误：8i 的 `kind` 改 `type`、twin 装入数 26→25、`find_by_route` 实为 (service, method, path) 精确键查、`EndpointDetailView` 为嵌套 `api` 对象、platform 现无 `dimensions.py`、「可手改 / `--force`」约定在 contract_gen_py、`updated_at` 实为 `datetime.now(UTC)`。同日修订三：落实全量评审五项决策——`/convert` 的 run 级 ref 钉住（8.3）、common 通用默认落点 `system.md`（第 5 节目录）、endpoint 轻列表平铺坐标口径（7.2）、CI 接入列为批次 D 交付项并澄清 `per_page` 现被忽略、纪律测试方言版纳入 A1。同日修订四：采纳架构评审十项优化——CLI 入口独立为 `plate`（附录 D）、构件含 call 投影 + 全局对象池 + manifest 记方言 / M2 版本（7.1）、系统目录路径可配置与部署拓扑成文（7.1）、`[[term-id]]` 降为纯约定（第 5 节）、框架 dim 全局挂载（7.2）、review 信封缺省 draft / 迁移置 reviewed / 零块按 F2 拒（第 6 节）、P8 加法演进原则（S1-0）；新增 9.1 能力接线表（plate 能力 ↔ 平台消费功能，画像 P2 / P3 解锁路径），A7 修订《服务画像-设计与改造方案》的 P2 / P3 表述。同日修订五（第五轮 review）：补 8v–8y 四项待确认（release 对 draft 的处理与引用闭包、片段 / 交付物 id 规则、CLI 入口与路线图 G1 / G2、分隔符改判）；8.3 补「查看现状类读 working」行；A6 纳入 G1 / G2；若干「种类」残留改「类型」、发布闸门补 F4、8j 原则数改 P1–P8。同日修订六（第五轮 review 验证后的收口）：第 6 项建议同步 8y 改判 (a)；第 9 / 10 项与附录 A 的「种类」残留改「类型」；8v 并入 8.2 发布闸门正文（冻结范围与引用闭包）；8.3「目录浏览」收紧为「浏览类页面（服务画像、端点目录页）」并注明编排页选单走编排版口径。同日修订七（决策轮）：除 8n 外第 1–10 项全部按建议定稿；新发现并补登五项——N1 responses 键即 outcome 不双写字段（6.2）、N2 release_id 命名 `YYYY.MM.N`（8.2）、N3 common 随引用系统 manifest 冻结（8.2）、N4 `plate review` 评审置位命令（附录 D）、N5 YAML 块冲突处理约定（第 5 节）；核实 `version` 的唯一真实消费方为适配中心开批的 semver 门（`adaptation_service.py:381`，建于不递增常量上、事实失效），影响评估表新增对应行；8n 补版本管理去向说明，维持待最终确认。修订七补：量化适配中心修改面（`catalog_diff` 双门——semver pending 门与 `updated_without_bump` C12 异常门——及基线戳 / 展示标签 / ops 比对共六处）；plate 轻列表与 `/full` 新增 `content_hash` 字段（7.2）作为 O(1) 变更检测信号，两道假信号门与一类误报坍缩为一道 hash 比较。同日修订八（8n 定稿）：删除 `version` / `updated_at` 确认；正文全部「待确认」标记翻「已定」，第 12 节仅剩 8g / 11 / 12 三个触发点延后项；适配触发补充「开批后 ops 为空 → 自动按 skipped 关批」作为 description-only 编辑的噪声出口；content_hash 的存储与归属补进 7.1（plate 零新增存储；平台适配戳复用列、ref 无关、按接口粒度推进），归属总表与平台自持理由补进 9.1。同日修订九（实施前评审，A1 前定稿）：① hash 规范序列化**排除等于默认值的字段**（`exclude_defaults`；对象 hash / call 投影 hash / shape_hash 共用）——否则 P8 加法演进下每次新增默认字段，全部接口 hash 齐变（适配风暴 + 对象去重失效）；② 适配检测信号从整对象 hash 改为 **shape_hash**（binding + 请求 / 响应声明树，不含 description / metadata / capability / consumes / produces / query_views）——批次 E 为 151 个接口补 capability 不触发开批，「ops 空自动关批」退为兜底；对象 hash 仅存 manifest 与快照内存索引，不经 HTTP 暴露；③ N2 改「年月 + 当月序号」；④ 8v 词条口径与块统一：孤儿 draft 词条不挡发布，仅被待冻结内容引用时由闭包阻塞；⑤ N3 补 common 变更须对全部引用系统重新校验。
> 原则：不新增模块（新增需给出确凿必要性并单独评估）；不构造过度代码，变更确认后由 Agent 一次性适配。
> 标注：每项结论标「已定」或「待确认」，待确认项集中在第 12 节。2026-10-08 修订十（实现评审 P0 收口 + S1.5 降级）：
> - hash 口径定型（修订九①②细化）：binding 段排除缺省值；hash 输入层对全部 dict 键排序（书写序不携带语义）；shape 投影剔除声明条目的 description/ui_kind（保留 default/example——影响用例取值）。
> - YAML 口径改判：方言按 **YAML 1.1（PyYAML）** 解析 + 重复键即报错；渲染对 1.1/1.2 任一口径会误读的标量强制双引号（'08'/'1e3'/'12:30'/on/off 等）。原「按 YAML 1.2 解析」不作数（ruamel 属新增依赖）。
> - 发布闸门补强（修订九未竟项）：C 类不一致阻塞发布（清零后方可发出）；引用闭包沿 refers/父节点/replaced_by 传递展开；common 词条只冻结被引用到的子集且须 reviewed（N3 落地）；对象写临时文件后原子 rename、复用前校验内容；release_id 目录 O_EXCL 防并发覆盖；签发人必填。
> - S1.5（自本分支显式降级，合入条件 = P0 清零 + 本清单）：7.1 快照化/原子重载/ref 多版本与 /convert 钉住；G5 快照带 commit 标识；reload 触达运行服务；term/statement/deliverable dim 与 doc/paths/references 动作（9.1 画像 P2/P3 接线依赖此项）；diff --base working/main；N4 单块回写；批次 C 自描述深度（订阅/参数登记/报告/计划/调试的字段级对拍）；路径可配置贯穿 CLI/HTTP。
> 2026-10-07 修订八：全部定稿（8g / 11 / 12 按触发点延后），正文各节的「待确认」标记已同步翻为「已定」。

---

## 1. 核心需求（已定）

| # | 需求 | 验收标准 |
|---|---|---|
| R1 | 为软件交付流程中的交付物提供归一化管理 | 任何一类交付物都能作为文件纳入 plate；有版本、可评审、可冻结；新增一类交付物不改 schema |
| R2 | 统一形式的编写与归档方案 | 所有交付物使用同一种 Markdown 方言（frontmatter + 围栏块 + 正文），任意 Markdown 编辑器可编辑；归档 = release 冻结的文件快照 |
| R3 | 从 Markdown 到结构化定义的转换能力 | 解析 → 校验 → 投影为结构化对象；可无损反向渲染回 Markdown；报错定位到文件与行 |
| R4 | plate 侧为此所做的定义简洁清晰 | M2 概念数量少；块类型固定；只有一套语法 |

归一化同时包含两层（已定）：

| | 形式归一化 | 语义归一化 |
|---|---|---|
| 含义 | 所有交付物用同一种格式编写 | 不同交付物中的同一概念对齐到同一词条 |
| 依赖 | 方言 + Frontmatter + 块 | 再加 Term 与 Statement 的槽位 |
| 能力 | 统一编写、归档、转换 | 跨交付物一致性检查、语义偏移检测 |

形式归一化是语义归一化的载体：先有统一的文件与块，词条才能挂上去。

**主线流程（已定）：** 被测系统的全部定义与设计文档，正规流程都是 **编写（人或 Agent）→ 评审 → 入库**，不走自动生成。此前的自动生成工具（contract_gen、twin_generator）属于尝试性实现，不在主线上；它们与本设计的冲突记录在附录 C，后续按主线原则另行说明变更。

## 2. 组件职责与依赖（已定）

| 组件 | 职责 | 持有的数据 |
|---|---|---|
| **plate** | 事实源：结构定义、语义知识、版本冻结、治理（评审、闸门） | M1 定义（Markdown 方言）、release 构件 |
| **gimbal-platform** | 编排与运营：用例组装、值管理、调度执行、报告与台账 | M0 值、Scenario 实例、执行记录 |
| **gimbal 执行器** | 执行：编译、调度、协议调用、事件 | 无状态，只消费构件与用例 |

CLI 与 Agent 是三者的共同消费方，不承担职责。

```
                 plate（不依赖任何其他组件）
                 ▲                      ▲
   查询定义 / 视图 / 序列化        离线加载 release 构件
                 │                      │
          gimbal-platform ──调度──▶ gimbal 执行器
                         ◀──事件流──
          CLI / Agent 可调用三者
```

- plate 只被查询，不调用任何其他组件。
- 派生分析（覆盖率、值复用等）在平台侧计算；plate 不存运行态。
- 执行器运行时不依赖 plate 的 HTTP 服务，按 F2 离线加载指定版本构件。
- plate 是内部服务，只以内部接口提供，不做认证；访问控制靠内网边界。写入归属由调用方在请求中写明操作人（平台传当前用户、CLI 取 git 身份），plate 作为受信字段记录。需要用户体系的界面（评审 / 标注）放在平台前端或 CLI 一侧。
- 部署：plate 现为独立进程（平台经 `PLATE_BASE_URL`，默认 `http://127.0.0.1:8765` 访问），API 契约独立。

## 3. plate 的核心边界（已定）

**plate 核心 = 输入 Markdown，输出结构化定义，加上版本管理。** 原件如何变成 Markdown、结构化定义被拿去做什么，都不在核心之内。

| 概念 | 对应需求 | 去向 |
|---|---|---|
| 交付物文件 + frontmatter | R1、R2 | 核心 |
| 定义块（`endpoint` / `system` / `defaults`） | R3 | 核心 |
| 片段块（Statement） | R1、R3 | 核心 |
| 词条块（Term） | R1（语义归一化） | 核心 |
| 解析、校验、反向渲染 | R3 | 核心 |
| release（检查、冻结；语义矫正以普通变更完成） | R1 | 核心 |
| 交付物类型模板 | R1 | 核心（数据，不是 schema） |
| 编写 → 评审 → 入库 | R1、R2 | 主线流程；plate 提供校验、差异与检索支撑（见第 8 节） |
| Agent 编写 skill | — | 移出核心：编写方之一，读原件、写方言，经评审入库 |
| 自动生成工具（contract_gen、twin_generator）、迁移工具 | — | 非主线（附录 C） |
| 图、边、覆盖率 | — | 移出核心：派生消费 |
| RAG、向量索引 | — | 移出核心：消费方 |
| EndpointDoc | — | 移出核心：查询投影（聚合规则见 7.2） |
| Agent 评审简报 | — | 移出核心：建立在结构化差异之上 |
| 标准层、`aligns` | — | 延后（随系统间关系） |

框架自描述（策略、协议、模式、事件订阅、参数登记表、报告定义、执行计划、调试命令）是 plate 原有职责，不在 R1–R4 范围内，保持现状；收回执行器 v2.1 定义的工作见第 11 节批次 C。

plate 只存定义态知识；运行态（用例值、场景实例、执行记录、环境值）归平台 / 执行器；原件只存出处。

## 4. 三个概念（已定）

| 概念 | 是什么 | 在文件中 |
|---|---|---|
| **交付物** | 一个 Markdown 文件，对应软件过程中的一份交付物 | 文件本身；frontmatter 写 id、类型（type） |
| **块** | 交付物中的内容单元：定义块（可执行与配置）、片段块（语义） | 定义块：`gimbal:endpoint` / `gimbal:system` / `gimbal:defaults`；片段块：`gimbal:statement` |
| **词条** | 概念身份 | `gimbal:term` 块，集中放在词典文件中 |

**每个交付物 = 一个文件；文件里是定义块或片段块；片段引用词条。** 其余都是视图或派生。

语义的两个维度分开锁定：片段的 kind 锁定「说的是哪一类事」，槽位中的词条锁定「说的是哪个东西」。

引用方向：语义关联只经词条（定义块与片段块都只通过 Term 建立语义关联）；定义块从不引用片段。片段可以用 `spec_path` 锚点指向某个接口的位置，这是出处定位，不是语义引用（已定）。

## 5. 方言语法（已定，块类型按本版收敛）

- 用户应用层用 Markdown；Python 工具链负责解析、校验、投影、反向渲染。方言是全部被测系统 M1 的唯一编辑形态与真源（框架自描述不在此列）；不生成 Python 实例文件。M2 仍是 Python。没有任何消费方直接读 Markdown。
- 块：围栏代码块 `gimbal:endpoint` / `gimbal:system` / `gimbal:defaults` / `gimbal:statement` / `gimbal:term`，块体为 YAML。`gimbal:system` 声明系统与服务（取代 `system_info.py`，服务后续承接 D6）；`gimbal:defaults` 声明该系统用例的默认模板（Meta / Config / Resource / Scenario，取代 `meta.py` / `config.py` / `defaults.py` 等）。块体按 YAML 1.2 解析，结果码键写成字符串。一个块可以是单个对象，也可以是对象列表。
- 行内引用：`[[term-id]]`——S1 为纯书写约定（不解析、不校验、不进规范形），出现真实消费方（Obsidian 反链、RAG 前缀）时再升级为语法（已定）。
- 片段原文 = 块后紧跟的段落，直到下一个块或标题。
- 同一文件内位置不携带语义，所有关联必须显式写 id / 槽位。
- 交付物以原生方言编写，文件本身就是原件。作者（人或 Agent）可以只写普通 Markdown 正文，片段块事后在同一文件上补标注；没有块的正文作为普通内容保留。所有文件都经评审入库，不存在「生成后不可手改」的文件。
- 回写：plate 只替换结构块内部，不动块外散文。「无损往返」定义为**语义等价而非字节等价**（已定），配套规范形规则：块内 YAML 经 plate 渲染产出的形态即规范形（键序按 M2 模型定义序、不含注释）；人工手写文件一经 plate 回写（CLI 反向渲染）即转为规范形；评审 diff 以规范形为基线，评审者看到的是语义差异而非格式差异。YAML 块合并冲突的约定（已定，N5）：解决冲突后必跑 `plate check`；规范形重渲染只作用于被改的块。
- 迁移：确定性脚本将现有 Python 实例（fin 25 个、platform 126 个接口，以及 `system_info.py` / 默认模板）`model_dump` → Markdown，逐字段比较一致后删除 Python 实例并切换加载器（顺带替换 `app.py` 中写死的系统导入）。这是对**已评审内容的格式转换**，不属于主线所禁止的自动生成；转换结果以等价校验作为评审依据。等价校验按语义比较（`model_dump` 相等）并设白名单：`consumes` / `produces` 语义重定义为生产 / 消费的词条引用（已定），存量 ApiSpec 上的 MIME 取值（默认 `["application/json"]`）弃置、迁后为空列表；`version` / `updated_at` 按第 12 节 8n 删除。

目录：

```
systems/
  common/                       # 通用层：跨系统词条（横切实体等）+ system.md（common 通用默认
                                #   gimbal:system + gimbal:defaults——现状 common.default config/meta
                                #   种子的落点，编排页「选系统 → 骨架预填」依赖）
  platform/
    system.md                   # gimbal:system + gimbal:defaults
    dictionary/*.md             # gimbal:term
    endpoints/*.md              # gimbal:endpoint
    deliverables/*.md           # 原生交付物：PRD、用户故事等（gimbal:statement）
  fin/ ...
types/*.yaml                    # 交付物类型模板（plate 全局配置）
```

示例（PRD 交付物，原生编写）：

````markdown
---
id: platform.prd.user-management
type: prd
---
## A2 用户管理

```gimbal:statement
id: st.user-mgmt.last-admin
kind: rule
slots: {about: [cap:user.update, attr:user.role], violation: outcome:user.last_admin}
anchor: "A2"
```
不能降级最后一个管理员。
````

## 6. M2 定义

新增 3 个模型：Frontmatter、Statement、Term；`gimbal:system` 块复用现有 `ServiceDefinition`（外加系统 id / 名称 / 描述的薄包装），`gimbal:defaults` 块复用现有 Meta / Config / Resource / Scenario 模型；EndpointSpec 按 6.2 修订。

**块信封（已定）**：所有块（endpoint / system / defaults / statement / term）共用一个由方言层处理的信封字段 `review: draft | reviewed`，不进入各自的 M2 模型；交付物的评审状态由其所含块派生（全部 reviewed 即 reviewed），frontmatter 不再单独记录。这样 EndpointSpec 等现有模型无需为评审状态加字段。缺省值为 `draft`；迁移内容（已评审内容的格式转换）一律置 `reviewed`；零块交付物按 F2 视为不满足 required（消灭「空集全 reviewed」的真空值）。

结构风格沿用 EndpointSpec：封闭 pydantic 模型（`extra="forbid"`），引用用字符串 id，扩展点用判别联合。模型内只做自身校验；跨对象校验放在加载 / release 时。不照搬 `declare()` 等语法糖。

### 6.1 Frontmatter（已定）

```python
class Frontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None               # 交付物 id，缺省取文件路径；一旦被引用须显式写出（已定，见 8w）
    type: str                           # 交付物类型模板 id（原称「种类」；改名以免与片段 kind、词条 kind 混淆，已定）
    system: str | None = None           # 缺省按目录推断
    # 公共默认值供文件内接口块继承
    service: str | None = None
```

### 6.2 EndpointSpec 修订（已定）

```python
class HttpBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: Literal["http"] = "http"
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    path: str
    headers: dict[str, str] = {}
    timeout_seconds: float = 30.0
    auth: Literal["none", "bearer", "basic", "cookie", "custom"] = "none"
    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    def locator(self) -> tuple: return (self.method, self.path)
    def side_effect_free(self) -> bool: return self.method == "GET"
    # 成功结果：任意 2xx；成功基准 = 数值最小的已声明 2xx（已定）

Binding = Annotated[Union[HttpBinding], Field(discriminator="protocol")]

class ResponseSpec(BaseModel):
    # outcome 即 responses 的键（键为唯一真源，不双写字段——N1 已定；原 status: int，http 为三位数字字符串）
    description: str = ""
    declarations: list[DeclarationEntry] = []
    # 不设 term 字段：业务结果语义走 Statement（已定）

class RequestSpec(BaseModel):
    declarations: list[DeclarationEntry] = []   # body_type 已移入 binding

class EndpointSpec(BaseModel):
    id: str; system: str; service: str; name: str; description: str = ""
    capability: str | None = None          # cap 类 Term id；是否必填由交付件清单按版本决定
    consumes: list[str] = []               # 生产 / 消费的词条引用（cap / attr，已定）；存量 ApiSpec 同名字段为 MIME 取值，弃置不迁移
    produces: list[str] = []
    binding: Binding                       # 取代 api；service 移出坐标，只在外壳
    request: RequestSpec | None = None
    responses: dict[str, ResponseSpec] = {}
    query_views: list[QueryView] | None = None
    metadata: EndpointMetadata = EndpointMetadata()
    # 删除 version / updated_at（已定，8n）：updated_at 现由构造时 datetime.now() 填充，
    # 每次加载都不同，破坏内容寻址去重与迁移等价校验；版本由 release 承担，历史由 git 承担。
```

`HttpBinding.auth` 描述被测接口自身的认证方式，与 plate 服务是否认证无关。

| 原规则 | 新规则 |
|---|---|
| responses 必须含 200 | 至少声明一个成功结果（http：任意 2xx） |
| status ∈ [100, 599] | outcome 合法性由 binding 判定 |
| `api.service == service` | 删除 |
| 非 GET 挂 query_views 须 `query_safe` | `not binding.side_effect_free()` 时须 `query_safe` |
| body_type=none ⇒ 零声明 | 保留，读 `binding.body_type` |
| 路由索引 (service, method, path) | `(protocol, service, *binding.locator())` |

- 协议：执行器已是通用请求过程（`call{protocol}` + ProtocolRegistry，协议适配器各带 `params_model`）。plate 的 Binding 联合与执行器注册的协议一一对应：协议的 binding 模型属于框架自描述，由批次 C 从执行器收回；`HttpBinding` 只是第一个实例，不是范围限制。新增协议 = 执行器注册适配器 + plate 联合加对应 Binding 类型 + export 加一段映射，EndpointSpec 外壳不改。D9（以真实第二协议验证外壳）仍保留为验证项。
- export 映射（binding → call）：`timeout_seconds` → `timeout`；`service` 取自外壳；`HttpBinding.auth` 是被测接口自身的认证方式，与执行器按 `user` 标签注入凭证不是同一概念，export 不直接对应。
- 语义文本字段（preconditions / success_criteria / failed_criteria / business_notes）原样保留，约定不再新增使用；后续迁移为 Statement（failed_criteria 试点）。
- 成功基准（已定）：`field_defaults` / `failed_resolver` 的取数来源从 `responses.get(200)` 改为成功基准——http 下数值最小的已声明 2xx（存量唯一成功键即 200，迁移后行为不变）；其他协议由该协议的 Binding 定义。
- `consumes` / `produces`（已定）：生产 / 消费语义的词条引用，与 MIME 无关；`body_type` 已覆盖所需媒介信息，存量 MIME 取值弃置（见第 5 节迁移白名单）。
- responses 键即 outcome（已定，N1）：不双写 `ResponseSpec.outcome` 字段，键为唯一真源；`spec_path` 锚点的 `@outcome` 段与 C 类规则均读键。
- `metadata.module` 保留为自由字段，不入词典。
- QueryView 约束：平台的取数执行器（`query_view_runner.py`）直接用 httpx 发请求，因此 QueryView 目前只对 http binding 有效；非 http 协议的取数要等取数执行改走执行器后再支持（已定）。
- 迁移：一次性硬切换，不做构造桥与 `/full` 过渡输出。范围：plate schema 与消费方、fin + platform 共 151 个接口、平台前后端、平台 PG 适配版本戳中的嵌套 `api`（`catalog_versions.spec_json` 存整份 /full item，`stamp_json` 为读取处局部变量名；第 12 节第 8m 项）、测试与 golden 基线。验收：三侧全量测试通过，全局无 `ApiSpec` / `.api.` / `responses.get(200)` 残留。

### 6.3 Statement（已定）

```python
class Statement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str                                        # 评审、结构化差异、语义矫正、追溯都依赖它（已定，见 8w）
    kind: Literal["mention", "define", "rule", "outcome", "transition", "step", "note"]
    slots: dict[str, str | int | list[str]] = {}   # 槽位 → Term id（step 的 order 为整数）
    anchor: str = ""                               # 在原件中的位置，按交付物类型的锚点语法解析
    text: str = ""                                 # 原文：解析时由块后段落派生，不写入块内
```

| kind | 锁定的语义 | 必填槽位 | 可选槽位 |
|---|---|---|---|
| mention | 原件此处提到某词条 | `subject`: 任意 | — |
| define | 某概念是什么 | `subject`: 任意 | — |
| rule | 必须成立 / 禁止发生的约束；含前置条件 | `about`: attr / value / cap | `before`: cap（前置条件）；`violation`: outcome |
| outcome | 动作在某条件下的结果；含跨实体影响 | `cap` | `outcome`；`when`: value 或 value 列表（列表表示「且」，已定）；`target`: entity / attr（影响）。`outcome` 与 `target` 至少一个 |
| transition | 状态从 A 到 B | `cap`；`from` / `to`: value（同一 attr） | — |
| step | 有序业务动作 | `cap`；`order`: 整数 | `branch_on`: outcome / value |
| note | 兜底：放不进其他 kind 的内容 | — | `terms`: 任意 |

- 一事一处：cap 与接口的对应只写在 `EndpointSpec.capability`，不用 mention 片段重复登记。
- 放不进任何 kind 的内容作为 note 保留原文，不硬塞进最接近的 kind。
- 粒度：标注集中在粗粒度（cap、outcome、rule、step）；字段级 mention 只在有消费方需要时才写。
- 词条按需建立：被片段、Spec 或断言引用到才建，不穷举。

### 6.4 Term（已定）

kind 五类，由 id 前缀解析，固定深度，父节点由 id 推导：

| 前缀 | 形式 | 父节点 | 例 |
|---|---|---|---|
| `entity` | `entity:<e>` | — | `entity:user` |
| `attr` | `attr:<e>.<a>` | entity | `attr:user.role` |
| `value` | `value:<e>.<a>.<v>` | attr | `value:user.role.admin` |
| `cap` | `cap:<e>.<action>` | entity | `cap:user.delete` |
| `outcome` | `outcome:<e>.<name>` | entity | `outcome:user.last_admin` |

段规则 `[a-z][a-z0-9_]*`，value 段放宽为 `[a-z0-9_]+`；实体名单段；id 不改，改名 = 废弃 + `replaced_by`。分隔符保留 `:`（已定，第 6 项 / 8y）。

```python
class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str                     # 业务名称：词表、展示、RAG 前缀
    aliases: list[str] = []        # 口语同义词
    gloss: str = ""
    status: Literal["active", "deprecated"] = "active"
    replaced_by: str | None = None
    refers: str | None = None      # 仅 attr → attr（外键 → 主键），已定
```

解析顺序：本系统 → `systems/common`。横切概念用专门实体承接（`entity:auth` 等），各系统通用的放 common。

### 6.5 交付物类型模板（数据，已定）

```yaml
- id: system
  blocks: [system, defaults]
  required: {system: 1}
- id: dictionary
  blocks: [term]
- id: endpoints
  blocks: [endpoint, statement]
  statement_kinds: [outcome, rule, note]
  anchor: spec_path
- id: prd
  label: 需求文档
  blocks: [statement]
  statement_kinds: [define, rule, outcome, step, note, mention]
  anchor: section
- id: user_story
  blocks: [statement]
  statement_kinds: [step, note]
  required: {step: 1}
  anchor: section
- id: ui_design
  blocks: [statement]
  statement_kinds: [mention, rule, note]
  anchor: ui
- id: db_design
  blocks: [statement]
  statement_kinds: [define, mention, rule, outcome, note]
  anchor: table_column
- id: state_design
  blocks: [statement]
  statement_kinds: [define, transition, rule, note]
  anchor: section
```

`blocks` 限定允许的块类型，`statement_kinds` 限定片段块允许的 kind，`required` 按块类型或片段 kind 计数。

锚点语法：`section`（标题路径）、`table_column`（`表.列[=值]`）、`spec_path`（`<endpoint_id> <JSONPath>[@outcome][=value]`）、`ui`（`页面 / 区块 / 控件`，已定）。新增一类交付物 = 加一份模板，不改 schema；新增锚点语法需实现对应解析与校验。

模板存放在 plate 全局配置目录（`types/*.yaml`），不随被测系统；修改走评审但不算 schema 变更；release manifest 记录所用模板版本（已定）。

新出现的交付物先判断能否用现有片段 kind 表达；表达不了的，才考虑新增片段 kind 或块类型（schema 变更，单独评估）。不为某一类交付物单独定义结构类型。

### 6.6 承载度（已定）

- 形式层面：任何交付物都能作为文件承载；结构化不了的内容作为 note 或块外正文保留，不会丢失。
- 语义层面，**需求 → 设计 → 功能实现**路径（只看功能语义）可以覆盖：

| 阶段 | 交付物 | 承载方式 |
|---|---|---|
| 需求 | PRD / 功能需求 | define / rule / outcome / step |
| 需求 | 用户故事 | step（顺序 + 按结果分支） |
| 需求 | 验收标准 | rule（`before`）+ cap + outcome（`when` 列表） |
| 设计 | 接口设计 | Spec 块 |
| 设计 | 数据库设计 | mention / define / rule + `refers` |
| 设计 | 状态设计 | transition |
| 设计 | UI 原型 | mention / rule（`ui` 锚点）；视觉内容只引用原件 |
| 实现 | 错误码、枚举、前端校验、配置开关 | outcome / mention / rule；代码侧只描述方法签名与能力（见第 9 节） |

- 已知限制：带并行与汇合的流程表达不了（step 只有整数顺序 + 分支）。fin 交叉检验时评估是否需要给 step 增加并行组；在此之前用 note + transition 兜底。
- 当前范围外：非功能需求（性能、容量、SLA、监控告警）与边界校验（长度、范围、正则）。二者共同根因是槽位不能写字面量；将来如需支持，可增加 `metric` 词条类型与 rule 的 `threshold {op, value, unit}`，并与执行器 suite 的 `gates: [{metric, op, value}]` 对齐，一次解决两者。
- 不在范围：项目管理类（排期、会议纪要）；运行态（自动化用例、测试数据、执行报告，归平台）；技术架构与运维手册（随拓扑维度，见第 13 节 NEIGHBOR）。

## 7. 能力（已定）

| 能力 | 说明 |
|---|---|
| parse | 扫描 `systems/` 下全部 Markdown，按块类型解析为 M2 对象，按 id 组装 |
| validate | 结构校验（M2）+ 引用校验 + 一致性校验，规则见下 |
| render | 结构化对象 → Markdown，只替换块内部，无损往返 |
| release | 冻结构件、生成 manifest、执行全部检查、记录矫正日志 |

校验规则：

| # | 规则 | 违反时 |
|---|---|---|
| F1 | frontmatter 合法；块类型与片段 kind 在该类型模板的 `blocks` / `statement_kinds` 内 | 阻塞 |
| F2 | 每个交付物满足其类型模板的 `required` | release 时阻塞 |
| F4 | 满足本版本交付件清单（以 `gaps` 的判定项 + 阈值表达，见 8.2） | release 时阻塞 |
| F3 | 同一系统内交付物 id、接口 id、片段 id 唯一；接口路由键 `(protocol, service, *locator)` 唯一 | 阻塞（取代现有注册表「先注册者胜 / 后写覆盖」的顺序依赖语义） |
| T1 | Term id 合语法、系统内唯一，且不与 `systems/common` 中的 id 重名 | 阻塞 |
| T2 | 父节点存在 | 阻塞 |
| T3 | replaced_by 存在、同 kind、active、不成环 | 阻塞 |
| T4 | 同 kind label 重复 | 告警 |
| T5 | alias 与他词条 label / alias 冲突 | 告警 |
| T6 | refers 仅 attr、目标为 active attr、不成环（已定） | 阻塞 |
| S1 | 片段槽位符合其 kind 的必填 / 可选定义与词条 kind 约束 | 阻塞 |
| S2 | 槽位与 Spec 的 capability / consumes / produces 引用全部可解析 | 不存在阻塞；已废弃告警 |
| S3 | transition 的 from / to 属于同一 attr | 阻塞 |
| S4 | anchor 符合所在类型的锚点语法；`spec_path` 能解析到接口、声明路径、enum | 告警（按版本升级为阻塞） |
| C1 | 引用同一 outcome 的 rule / outcome 片段，在各来源中引用的 cap 集合一致 | 列入语义矫正 |
| C2 | 同一 cap 的 `before` 前置条件在各来源中一致 | 列入语义矫正 |
| C3 | 同一 attr 的取值集合在各来源中一致（DB、Spec enum、前端等） | 列入语义矫正 |

C1 的实例：`outcome:user.last_admin` 在 PRD 中只关联「降级」，在接口文档中只关联「删除」，C1 检出不一致。

### 7.1 运行时与存储（已定）

不引入数据库。存储分三层：

| 层 | 内容 | 性质 |
|---|---|---|
| 真源 | `systems/` 下的 Markdown（git 工作区） | 可编辑；经评审入库 |
| 构件 | release 冻结产物，内容寻址：`plate_artifacts/objects/<hash>.json`（**全局对象池**，每个对象一份，跨版本、跨系统共享——hash 全局唯一，common 词条对象天然去重、跨系统引用无路径尴尬）+ `plate_artifacts/<系统>/releases/<release_id>/manifest.json`（对象 id → hash 清单、call 投影清单、模板版本、方言 / M2 schema 版本、矫正日志） | 不可变；只追加；磁盘增长与「变更量」成正比，而不是与「版本数 × 全量」成正比 |
| 运行时索引 | 内存中的 registry（各 dim 索引 + 词条反查索引） | 派生；随时可从真源或构件重建 |

现有「全部加载到内存」的方式保留，补三点：

- **快照化（按系统分区）**：每个系统一个不可变快照，标识为 `<系统>@working:<commit>` 或 `<系统>@release:<id>`；系统之间独立加载、独立重载，未被访问的系统可延迟加载。`systems/common` 作为公共快照被各系统引用（common 变更时，入库闸门与重载须对全部引用系统重新校验，见 8.2 N3）。加载失败（解析或阻塞级校验不通过）时保留旧快照继续服务，并返回错误报告。
- **原子重载**：新快照完整构建并校验后再整体替换旧快照，不存在半加载状态。触发方式：CLI / 内部接口显式触发（S1 不做文件监听）。
- **多版本**：HTTP 查询以 `ref`（`working` 或 release_id）选择快照；缺省为最新 release，尚无 release 时为 `working`（与 8.3 一致）。内存中常驻的只有 `working` 全量快照；release 只常驻 manifest（体积小），对象按 hash 按需加载，LRU 缓存以对象为单位——未变化的对象在各版本间是同一个 hash，缓存天然共享。
- 多版本的典型访问都是**对象级**而不是全量快照级：执行器只加载钉住的一个版本；两版本差异 = 比较两份 manifest 的 hash，只加载变化的对象；单个对象的历史 = 沿各版本 manifest 取 hash；用例变更插件只需某接口在两个版本中的对象。
- 旧版本冷化：不再被任何平台值记录 / 场景引用的 release，可整体移入归档存储；manifest 保留以便追溯。
- **call 投影随 release 冻结**：冻结时对每个接口按 6.2 的 export 映射同时产出可执行 call 投影（内容寻址、进 manifest）。执行器（S3）与平台 convert 只消费投影，不在执行器侧复制 binding→call 转换（避免第二次真源）；副产品：plate 服务不可用时，平台可降级读本地构件做 convert（只读、确定性），P6 熔断「plate 挂 → 执行停」有了出路。
- **hash 的存储与归属**：plate 侧**零新增存储**——release 期对象 hash 即 manifest 里的对象条目（本节已有），working 期在快照构建时对每个接口按规范序列化（键序按 M2 模型定义序、排除等于默认值的字段，见 7.2）各算一次**对象 hash**（整对象：构件去重与 release 差异）与 **shape_hash**（形状：binding + 请求 / 响应声明树，适配检测信号）存内存索引（快照不可变，算一次即可）。平台侧唯一的持有点是适配版本戳（`catalog_versions`）：`version` 列复用存 shape_hash（随 8m 的 alembic 一并），语义 = 「已适配到的定义形状指纹」——**与 ref 无关**（过渡期 working 与 release 期同一机制），且按接口粒度各自推进（适配批次异步落定：A 已推进、B 仍 pending，各持各的指纹）。戳的 `spec_json` 旧形状缓存在批次 B 的 `diff --json` 就绪后可瘦身为「shape_hash + 快照标识」（旧形状按需从构件取），过渡期保留。平台持有的版本信息共两处、各司其职：适配戳的 shape_hash 管「适配到了哪个形状」；值记录的 release_id（第 12 节第 11 项）管「执行基于哪个版本」。归属总表与平台自持的理由见 9.1。
- **系统目录路径可配置**：统一加载器按「路径列表」发现系统，缺省单仓 `systems/`。被测系统定义将来可放独立仓（如 fin 团队在自己的 PR 里评审自己的交付物）；NEIGHBOR 的外部仓读取（第 13 节②）复用同一机制。
- **部署拓扑前提（成文）**：`working` = 主干最新提交隐含两个前提——plate 主机有仓库 checkout、CI 可触发 plate 主机的 reload；多实例部署时重载信号需广播（已列触发条件表）。

规模估算：数百个接口（fin 完整约 700+）、数千条片段与词条，冷启动解析在秒级，内存在几十 MB 量级，不构成瓶颈。plate 为单一独立进程，不存在多进程间索引一致性问题；若将来多实例部署，重载信号需要广播。

多系统接入后仍不默认转数据库：规模随系统数线性增长，按系统分区快照 + 延迟加载即可承接。即使将来引入数据库，它也只是**派生索引**（可从真源与构件重建），真源始终是 git 中的 Markdown，评审入库的治理方式不变；优先复用平台已有的 PG，不新增基础设施。触发条件（满足任一再评估）：

| 触发条件 | 说明 | 首选应对 |
|---|---|---|
| 单进程内存或冷启动不可接受 | 例如全部系统常驻内存超过数百 MB，或全量加载超过分钟级 | 先做按系统延迟加载与淘汰；仍不够再把索引外置 |
| 多实例部署（高可用） | 多个 plate 实例需要一致视图 | 各实例从同一 git 提交 / 构件加载，重载信号广播；必要时索引外置 |
| HTTP 并发写入（评审 / 标注界面） | 多人同时编辑 | 写入仍落文件 + git；数据库仅作草稿暂存 |
| 全文 / 向量检索 | RAG、模糊检索 | 专用检索索引，不是通用数据库 |

### 7.2 新能力的统一设计（已定）

原则：**一个 registry、一套 dim 语法**。新结构 = 新 dim（索引 + 视图 + 动作），投影 = dim 上的动作或视图，版本 = 快照。不新增路由体系，沿用现有 `/systems/{system}/{dim}…`、`/{dim}/{id}/full`、`/{dim}/{id}/references`、`…/action/{name}` 语法。

| dim / 动作 | 内容 | 来源 |
|---|---|---|
| `endpoint`（已有，改造） | EndpointSpec；`/full` 带 capability；路由索引按 `(protocol, service, *locator)` | `gimbal:endpoint` |
| `system` / `service`（已有，改造） | 系统与服务声明 | `gimbal:system` |
| `meta` / `config` / `resource` / `scenario`（已有，改数据源） | 默认模板 | `gimbal:defaults` |
| `strategy` / `generators`（已有，不变） | 框架自描述 | 代码 |
| `term`（新增） | 词条；动作 `search`（label / aliases 匹配，供编写方先查再建）、`references`（反查引用方） | `gimbal:term` |
| `statement`（新增） | 片段；按 kind / 槽位词条 / 交付物过滤 | `gimbal:statement` |
| `deliverable`（新增） | 交付物文件级视图（frontmatter + 所含块） | 文件 |
| `type`（新增） | 交付物类型模板 | `types/*.yaml` |
| 动作 `doc` | 按 cap 聚合片段（原 EndpointDoc 投影） | `statement` |
| 动作 `paths` | user_story 展开为路径 | `statement`（step） |
| 动作 `check` / `diff` / `release` | 校验报告、结构化差异（`ref` 对比）、冻结 | 全部 |

dim 注册由 plate 核心的统一目录完成：加载器发现系统后为每个系统挂载同一套**数据** dim；框架自描述 dim（strategy / generators 及批次 C 收回的 protocol / subscribe / param_registry / report / plan / debug）全局挂载一次、不走 `/systems/{system}/…`——修正现状框架 dim 注册在 fin 装配点的 pragmatic 拍板。删除各系统的 `dimensions.py`。

endpoint 轻列表与过滤参数的口径（已定）：轻列表条目保持平铺坐标字段（`method` / `path`，http 专属便捷投影，取自 `binding.locator()`）并新增 `protocol` 字段；`method=` 查询过滤标注为 http-only 便捷过滤，协议中立的坐标过滤走 locator。平铺坐标是平台 grid 聚合与前端目录直拉的兼容面，完整 `binding` 对象只在 `/full` 出现。轻列表与 `/full` 条目另带 **shape_hash**（形状 hash，修订九）——只覆盖影响用例值的部分：`binding` 与 request / responses 的声明树；**不含** `description`、`metadata`、`capability`、`consumes` / `produces`、`query_views`（语义标注不触发适配批次——批次 E 为 151 个接口补 capability 不会开批）。**对象 hash**（整对象）只存在于 manifest 与快照内存索引，用于构件去重与 release 差异，不经 HTTP 暴露。两种 hash 与 call 投影 hash 共用规范序列化规则（修订九，A1 实现前置）：键序按 M2 模型定义序、**排除等于默认值的字段**（`exclude_defaults=True`）——保证 P8 加法演进下新增带默认值的字段不改变未使用它的对象的 hash，否则每次加字段全部接口 hash 齐变（适配风暴 + 跨版本对象去重失效）。`endpoint id` 变更不经 hash（走 missing_on_plate / 首见基线路径）。shape_hash 是平台适配中心的 O(1) 变更检测信号（`≠` 戳内指纹即 pending），不必拉全量自算 diff。

**EndpointDoc（视图）**：EndpointSpec 的可理解形态保留，但不再是存储结构。编写形态 = 接口文件中紧跟 `gimbal:endpoint` 块的片段块；阅读形态 = `endpoint` dim 上的 `doc` 动作，聚合两类片段的并集：① 锚点为 `spec_path` 且指向该接口 id 的片段；② 槽位 `cap` 等于该接口 `capability` 的片段（来自 PRD、用户故事等任意交付物）。

**面向 Agent 的补充（已定）**：

| # | 补充 | 落点 |
|---|---|---|
| G1 | 方言自描述：各块的 JSON Schema、片段 kind 槽位表、锚点语法、id 规则 | `type` dim + `schema` 视图 |
| G2 | 无写入校验：请求体为文件内容，返回错误码、位置、修复提示 | `POST /deliverable/action/validate`；`plate check --stdin` |
| G3 | 词条检索返回候选与匹配原因（label / alias / 字符串相似度），不只返回精确命中 | `term` 的 `search` 动作 |
| G4 | 投影中的锚点返回解析后的结构（`{endpoint, path, outcome, value}` 等） | `doc` / `references` |
| G5 | 每个响应标明所读快照（如 `platform@release:2026.10.1`） | 响应信封 |
| G6 | 定义完整性缺口清单（缺 capability 的接口、缺 define 的 cap、无结果片段的结果码、无用户故事的主干业务） | `gaps` 动作 |
| G7 | 结构化差异的 JSON 输出，附词条表述的摘要 | `diff` 动作；`plate diff --json` |

G1–G7 满足路线图「Agent 可消费」的四条验收项：机器可读输出（G1 / G5 / G7）、结构化错误（G2）、写操作可 dry-run / validate（G2）、plate 知识与平台走同一 HTTP 服务（dim 体系）。

`plate check` 提供 `--json` 输出（与路线图 Q4 / G4 一致）：规则编号（F1…C3）即错误码，每条结果带文件与行号。

## 8. 治理与版本

### 8.1 主线流程：编写 → 评审 → 入库（已定）

两道闸门，分别作用于「一次变更」和「一个版本」：

| 环节 | 单元 | plate 提供 | 闸门 |
|---|---|---|---|
| 编写 | 工作区中的一个或多个交付物文件 | 类型模板（新建骨架）、`plate check --json`、词条检索（编写方先查再建） | — |
| 评审 | 一次变更（S1 为 git 提交 / PR，可含多个交付物文件） | 结构化差异（工作区 vs 基线，按交付物、按块、按字段）；C 类一致性告警。要点简报由核心之外的评审 Agent 基于差异产出（不给结论） | 人在变更内按交付物逐一评审 |
| 入库 | 合入工作版本 | — | **入库闸门**：F / T / S 阻塞级规则全部通过（CI 执行）；C 类规则只告警 |
| 发布 | 一个版本 | 冻结构件、manifest、矫正日志 | **发布闸门**：类型模板 required（F2）、交付件清单（F4）、C 类不一致全部经语义矫正处理、人签发 |

- S1 不提供 HTTP 写入：编写只在本地工作区进行（编辑器 + CLI），评审与入库走 git；反向渲染只通过 CLI 作用于工作区。HTTP 写入路径与评审 / 标注界面一起延后设计。
- 部署环境中的 `working` 指主干分支的最新提交，不是某个人的本地工作区。合入后由 CI 拉取代码并调用重载接口，快照标识记录该提交（已定）。
- **发布闸门只检查、不编辑**：检出的 C 类不一致通过普通变更修正（编写 → 评审 → 入库），全部合入后再发起发布；manifest 的矫正日志记录这些矫正变更的引用（提交 / PR），而不是在发布环节直接改文件（已定）。
- 评审状态的落点：入库即代表变更已评审；块信封上的 `review` 表示「内容是否已确认可用于发布」，由评审人在评审中置为 `reviewed`；交付物的状态由其所含块派生。

### 8.2 版本与发布（已定）

- 工作版本在 `systems/<系统>/`，允许不完整；结构槽位预埋，逐步增加交付物。
- 发布闸门：① 机械检查（第 7 节阻塞级规则、F2、F4）→ ② 一致性检查（C 类不一致与**被待冻结内容引用的** draft 词条须已通过矫正变更处理，否则阻塞）→ ③ 版本级结构化差异与要点（由评审 Agent 产出，不给结论）→ ④ 人签发（签发人由调用方传入）。发布环节不编辑任何文件。冻结范围与引用闭包（8v）：冻结只收 `reviewed` 块，draft 块留在 working 继续演进；已冻结块只能引用已冻结的块与词条，违反即阻塞。宽严口径（修订九，词条与块同一口径）：未被引用的 draft 词条与 draft 块一样，只是不进入本次 release、不阻塞；被**待冻结内容**引用的 draft 词条由引用闭包阻塞——闭包本身即保证「已发布的内容只引用已评审的词条」，不要求发布时系统内不存在任何 draft 词条（否则 Agent 提议的孤儿词条会挡住整个系统的发布）。common 层不单独发版（已定，N3）：被引用的 common 对象以内容寻址方式随引用系统的 manifest 一并冻结，8v 闭包对跨系统词条天然成立。common 有变更时，入库闸门（CI）与重载须对**所有引用它的系统**重新校验（T2 / S2）——在 common 里删掉一个词条可能悄悄破坏另一系统的引用，不得只校验改动来源系统。release_id 命名（已定，N2）：`YYYY.MM.N`（**年月 + 当月序号**，系统内单调递增；示例 `2026.10.1` = 2026 年 10 月第 1 个 release），与快照标识 `release:<id>` 一致。
- 交付件清单按版本收紧（例：v1 只要 Spec + 最小词典；后续要求每个 cap 有 define、主干业务有 user_story），属于 release manifest。清单与 `gaps` 共用同一组判定项（缺 capability 的接口、缺 define 的 cap、无结果片段的结果码等），清单只是为判定项加上阈值；`gaps` 给出当前缺口，F4 在发布时检查阈值（已定）。
- 语义矫正：

| 输入（机器检出） | 矫正动作（人决定） |
|---|---|
| 新提议的词条 | 确认 / 合并到已有词条 / 驳回 |
| 引用已废弃词条的片段 | 改为引用 `replaced_by` |
| C1–C3 不一致 | 修正源头，或拆分 / 合并词条 |
| label / alias 冲突 | 合并或改名（废弃 + 新建） |
| 原文与槽位疑似不符（Agent 标记） | 重新填槽位，或改为另一种 kind |

  矫正动作以普通变更完成（见 8.1），manifest 的矫正日志记录变更引用。已发布的片段只能引用评审过的词条。
- 结构化差异按结构、按字段计算，同时服务：评审简报、判断哪些接口需要用例变更插件、检查 M2 读兼容；差异可用词条表述。
- 评审 Agent 只拿结构化交付物和评审规则，不带生产过程上下文。
- 归档：发布事件触发的结构化投影，形式不限；旧版本构件保留在 plate。若归档目标同时是接入来源，必须从接入中排除归档产物。
- 评审单元：一次变更可以包含多个交付物文件；评审意见按交付物组织，`review` 状态落在块信封上。

### 8.3 消费方的版本使用规则（已定）

| 场景 | 使用的快照 |
|---|---|
| 平台编排、执行、值记录 | 最新 release；值记录写入所基于的 release_id（第 12 节第 11 项） |
| `/convert` | 请求带 `ref`，取该场景编排时所基于的 release；缺省最新 release |
| 预览（编写者查看刚合入的定义在编排页的效果） | `working`；基于 working 编排的用例不计入入库标准 |
| 执行器 | 离线加载钉住的 release 构件（M2 对象 + call 投影，见 7.1；S3 前经 `/convert` 获得可执行 dict） |
| 查看现状类（浏览类页面：服务画像、端点目录页） | `working`（见 9.1）；不参与编排、执行与值记录——编排页的接口选单走「平台编排」行口径（最新 release；预览态例外按预览行走 `working`） |
| 首个 release 冻结之前（过渡期） | 平台继续使用 `working`，行为与现状一致；首个 release 冻结后切换为上述规则 |

ref 的实现口径（已定）：`/convert` 的结果缓存键包含 `ref`；一次 run 开始时解析一次「最新 release」，所得 release_id 随 run 携带，run 内全部 convert 与值记录钉住同一 release_id——避免发布瞬间造成的同 run 版本漂移。

## 9. 核心之外：生产方与消费方

| 方向 | 内容 | 说明 |
|---|---|---|
| 编写方 | **人**：直接用方言编写；可只写普通 Markdown，片段块事后补标注（结构细节后续定） | 主线 |
| 编写方 | **Agent 编写 skill**：读原件（代码、文档、OpenAPI），按类型模板写方言文件，必须先检索已有词条再提议新词条 | 主线；产物与人工编写同样经评审入库 |
| 编写方 | **代码侧事实**：只描述方法签名与能力；后续在项目代码中增加 NEIGHBOR，既作工程内模块间参考，也作为 plate 管理的交付数据（见第 13 节） | 主线 |
| — | 自动生成工具、存量迁移工具 | 非主线（附录 C） |
| 消费方 | EndpointDoc（聚合规则见 7.2） | 查询投影 |
| 消费方 | 词条图（节点 = Term，边由 Spec 字段、片段槽位、`refers`、`replaced_by` 派生）、反查索引 | 加载时由 registry 物化；不引入图数据库 |
| 消费方 | 覆盖率（业务路径、业务结果）、值复用 | 平台侧查询 plate 后计算 |
| 消费方 | RAG：词条图检索；带词条前缀的向量切片（label 入嵌入文本，id / kind / release / review 入元数据，按块切分，只用已评审片段，索引在 release 时生成） | 向量索引与嵌入模型属新增，延后到图检索覆盖不足时评估（fin 数据敏感，需考虑本地部署） |
| 消费方 | UserStory → 路径 → Scenario：展开 step 片段的分支得到路径（plate 投影），Agent 绑定接口并填值，Scenario meta 记 storyRef + pathId | 见第 9 项（已定） |
| 消费方 | 服务画像（热力网格 / 线索板 / 需求信号）：轻列表平铺坐标、`doc` / `references` / `gaps`、capability 链 | 见 9.1 接线；P2 需求象限的内容解锁点在批次 E |

### 9.1 能力接线（plate 重构后 ↔ 平台消费方）

plate 重构后的能力与平台侧需要的功能一一接线如下（查询面均沿用 7.2 的 dim 语法；「解锁批次」指管道就绪点，内容就绪另见备注）。平台侧画像功能（`board_assembler` / `service_profile` 路由 / `ServiceGrid.vue` / `EndpointBoard.vue`）的四象限与 node / edge / trail 形状不变，只是往占位象限里填节点。

| plate 能力 | 查询面 | 平台侧消费功能 | 现状 | 解锁批次 |
|---|---|---|---|---|
| capability 链（endpoint → cap 词条 → rule / outcome / step 片段 → 交付物） | `endpoint/{id}/action/doc`、`term/{id}/references` | 画像需求象限（P2）、网格槽①需求信号与 `noRequirement` 统计 / chip、编排表单的接口业务语境 | 占位（`requirement="unavailable"`、`req=null`） | 管道 B；内容 E（platform 域 PRD 词条标注存量） |
| `gaps` 判定项（缺 capability 的接口、缺 define 的 cap、无结果片段的结果码、无 user_story 的主干） | `gaps` 动作 | 网格槽①统计（与 8p 交付件清单共用判定项）、平台待办卡、L6 循环起点 | 无 | B |
| 词条 / 片段（db_design 交付物 + `attr` + `refers` + `表.列` 锚点） | `term` / `statement` dim 过滤、`references` | 画像数据象限（P3）、值语义提示 | 占位 | 管道 B；内容持续标注 |
| 结构化差异 | `diff --json`、`?ref=` 对比 | 适配中心（判定哪些接口需用例变更插件，替代平台自算 `spec_json` 比对）、画像适配告警链 | 平台自算 stamp 比对 | B |
| release 快照 + `ref` | `?ref=`、构件 | 值记录关联 release_id（第 12 节第 11 项）、执行 run 级钉住（8.3）、画像执行象限的版本时间轴 | working 单态 | B |
| call 投影构件 | 构件文件 | 执行链（S3 前经 `/convert`）、plate 不可用时平台降级 convert | 无 | B |
| `paths` 动作（user_story → 路径） | `paths` | 消费 Agent 生成用例（L6）、业务路径覆盖率 | 无 | B / E |
| EndpointDoc 投影 | `doc` | 画像主体节点描述增强、编排表单业务说明 | `/full` 无 capability | B（形状）/ E（内容） |
| `type` dim + 方言自描述（G1） | `type` / `schema` 视图 | Agent 编写、平台前端模板化「新建交付物」入口 | 无 | D |
| 响应信封 `snapshot`（G5） | 响应信封 | `plate_client` 缓存按快照失效校验、画像降级横幅标注当前快照 | 无 | A2 |
| NEIGHBOR（延后） | — | 画像拓扑象限、双击换主体跨服务顺链、按变更影响选回归用例 | 占位 | 延后（第 13 节） |

平台侧配套改动：`board_assembler` 主体读 `binding`、subject 的 `version` 槽改填信封 snapshot 标识（批次 A2，轻列表平铺坐标口径已保住 grid 与降级链）；需求象限聚合调 `doc` / `references`、槽①调 `gaps`（画像 P2）；适配中心变更检测改 shape_hash 比较（见对外能力影响评估表的完整修改面行）；node id 扩 `term:` / `st:` 前缀、expand 支持词条二度关联；`affects` 边由 outcome 片段的 `target` 槽位驱动；trails 风险链扩展「C 类不一致 → 矫正告警」语义链。画像读 `working` 快照（属「查看现状」类，按 8.3 与编排 / 执行的 release 钉住分流；`plate_client` 缓存按 G5 的 snapshot 字段做失效校验）。

**版本 hash 的存储归属（plate ↔ 平台）**：

| 持有方 | 存什么 | 存哪 | 性质 |
|---|---|---|---|
| plate | release 期对象 hash | manifest | 不可变构件（7.1） |
| plate | working 期对象 hash + shape_hash | 快照内存索引（构建时按规范序列化各算一次，快照不可变） | 派生，零新增存储 |
| 平台 · 适配 | 「已适配到的定义形状指纹」（shape_hash） | `catalog_versions.version` 列复用（随 8m 的 alembic 一并） | 进度记录 + 派生缓存 |
| 平台 · 执行 | 「执行基于哪个版本」 | 值记录 release_id（第 12 节第 11 项） | 运行态台账 |

平台必须**自持**适配指纹的三个理由：① 适配进度异步、按接口粒度推进（A 批已落定、B 批仍 pending，各持各的指纹）——plate 不知道平台的适配进度，无法代持；② P6：适配进度是运行态，归平台；③ 不违反「平台不落 plate 权威副本」——戳是进度记录与派生缓存（冷启动首见自动落基线、可重拉重建，`catalog_version.py` 文件头本就如此自称），不是 plate 数据的镜像；hash 只是把原本的假 semver 换成真指纹。指纹与 ref 无关（过渡期 working 与 release 期同一比较逻辑，见 7.1）；戳的 `spec_json` 旧形状缓存在批次 B 的 `diff --json` 就绪后可瘦身为「hash + 快照标识」（旧形状按需从构件取），平台对 plate 形状的持有面进一步缩小。

## 10. 最终产物形态（已定）

最终产物是以词条为骨架的多层图谱：原件层（外部）、Spec 与片段（挂在词条上的内容）、运行层（平台派生）、时间轴（每个 release 是整张图的不可变快照）。图是产物形态，不是存储形态；存储是 Markdown 文件。节点是否可信，看是否有评审过的定义 + 稳定通过的用例支撑。

### 10.1 逻辑闭环核对

| 闭环 | 路径 | 状态 |
|---|---|---|
| L1 编写入库 | 编写（人 / Agent，G1–G3 支撑）→ `check` / `validate` → PR → 评审（`diff`、C 类告警、简报）→ 入库闸门（CI）→ 合入 → CI 拉取并重载 working 快照 | 通（CI 载体由批次 D 接入，此前入库闸门靠本地 `plate check` 自律执行） |
| L2 发布 | 发布闸门检查（F2、F4、C 类）→ 不通过则以普通变更修正并回到 L1 → 通过后人签发 → 冻结为内容寻址构件 + manifest | 通（发布只检查不编辑，避免绕过入库闸门） |
| L3 消费执行 | 平台按 8.3 选快照 → `/full` 编排 → `/convert?ref=` → 执行器执行；值记录 release_id | 通（首个 release 前按过渡规则使用 working） |
| L4 版本演进 | 新 release → 结构化差异 → 判断需用例变更插件的接口 → 存量值迁移 → 旧 release 无引用后冷化 | 通（变更插件实现属 E4） |
| L5 语义一致性 | C 类规则在入库时告警、发布时必须处理 → 矫正变更走 L1 → manifest 记录引用 | 通 |
| L6 Agent 工作循环 | `gaps` → 编写 → `validate` → PR → 评审 → 入库 → 消费 Agent 用 `doc` / `paths` 生成用例 → 平台执行 → 平台侧覆盖率 → 新的待办 | 通（定义完整性缺口由 plate 的 `gaps` 给出，测试覆盖缺口由平台给出） |
| L7 可信度 | 评审过的定义（plate）+ 稳定通过的用例（平台）→ 平台侧计算可信度 | 通（执行结果不回流 plate，符合 P6） |

## 11. 实施计划

### S1-0 清理（结构重构的前置，已定）

目的：先把与本设计原则冲突、但不需要等结构重构的内容清掉，让重构的 Agent 面对的是一份没有矛盾的文档集与代码基线。清理不改变任何对外行为（三侧全量测试保持通过）。

**原则清单**（清理与重构都以此为准）：P1 Markdown 方言是被测系统 M1 的唯一真源；P2 主线流程为编写 → 评审 → 入库，不走自动生成；P3 一事一处，不存在双真源与镜像；P4 位置与注册顺序不携带语义，关联必须显式写 id；P5 协议中立，Binding 与执行器协议注册一一对应；P6 plate 只存定义态；P7 文件为全部数据的存放地，内存只是派生索引；P8 M2 只做加法演进——新增字段必带默认、`extra="forbid"` 兜底未知字段，破坏性变更走一次性迁移脚本 + golden 更新（本次重构即该原则的第一次执行）。

**A. 文档清理**

| # | 对象 | 冲突 | 处理 |
|---|---|---|---|
| A1 | `design/PLATE_DESIGN.md`、`PLATE_EVOLUTION.md`、`PLATE_PHASE1_FINAL.md`、`status.md`（ModelRegistry 时代、`src/Plate/server` 已不存在） | 过时，与 P1 / P5 冲突 | 移入 `design/archive/`，文件头标注「已被 claude/plate-design.md 取代」 |
| A2 | `gimbal_plate/design/ENDPOINT_SPEC_V1.md`、`ENDPOINT_SPEC_V2.md`、`PLATE_V3_DESIGN.md`、`PHASE6_CONSISTENCY.md`（`ApiSpec`、`schema_`、`models.py`、`status: int`） | 与 6.2 修订冲突 | 同 A1 归档；`design/README.md` 改为指向本设计 |
| A3 | `design/schema-skill copy.md` | 与 `schema-skill.md` 重复且内容不一致（P3） | 比对后合并或删除副本 |
| A4 | `docs/PLATE-API-SURFACE.md`、`docs/http-api.md`、`docs/architecture.md`（`ApiSpec`、`schema_`、`channel` 三分类） | 描述的是已退役结构 | 清理阶段标注过时；重构完成后按 7.2 节重写 |
| A5 | `docs/adr/0002-plate-http-routing-grammar.md`（仍提 `schema_`） | 部分过时 | 追加修订说明；新增 ADR 记录「方言 + 三概念 + 主线流程 + 内容寻址构件」 |
| A6 | 路线图 `GIMBAL-待实现功能与路线图-2026-09-28.md`：D2 写作「`api` 改为 `binding`」仍以 ApiSpec 为前提；D5 过渡期从执行器 `ext list` 取 binding schema（方案 A）；E1 构件布局为「每版本全量快照」；P4 验收门以第二协议为准；G1 / G2 以统一 `gimbal` 入口挂载 `gimbal plate` 命令组 | 与 6.2、7.1、第 11 节路线图调整、附录 D 冲突 | 按本设计更新 D2 / D5 / E1 / P4 / G1 / G2；D5 改为「binding 模型随批次 C 收回 plate」；G2 改为独立 `plate` 入口 |
| A7 | 同目录《服务画像-设计与改造方案》（§2.4 / §3.1 / §5.2 / §5.5 / §5.6 以 Plate `reference` / `table` / `topology` dim + 外部系统集成为前提） | 与 7.2 / 9.1 的新 dim 体系冲突（`statement` / `deliverable` / `term` + capability 链、db_design + `attr` / `refers`、NEIGHBOR） | P2 / P3 表述按本设计修订（2026-10-07 已完成，见该文档修订记录） |

**B. 代码清理（不改行为）**

| # | 对象 | 冲突 | 处理 |
|---|---|---|---|
| B1 | `src/gimbal-plate/tmp/twin_gen/`（727 个已入库文件） | 非主线产物入库（P2，附录 C X2） | 移出仓库或加入 `.gitignore`；工具代码保留，标注为实验 |
| B2 | `ServiceDefinition.endpoints_module` / `models_module` | 指向 Python 模块路径，与 P1 冲突；全仓无消费方 | 删除字段 |
| B3 | `export/platform.py` `_ep_key_map`「同坐标先注册者胜」、`registry/index.py` by_route「后写静默覆盖」 | 注册顺序携带语义（P4）；统一加载器按目录发现后顺序不确定 | step 与端点关联改为优先 `view_hints.endpoint_id`；重复路由键在注册时报错（对应 F3）。若存量存在同坐标端点（如 `fin.order.order_add_demo`），先改为显式 id 关联 |
| B4 | `action_system_register` / `action_system_sync`（C1 / C2） | 与 P1 冲突（附录 C X4） | 停用：返回明确的「已停用」错误码；平台侧如有调用一并移除 |
| B5 | `release/release.py`（恒返回失败的占位） | 无冲突，但会被误用 | 保留至批次 B，文件头注明 |
| B6 | JSONPath 三份实现（`gimbal/utils`、`gimbal_plate/utils`、平台 `services/jsonpath.py` 镜像） | 镜像维护（P3） | 不在 plate 清理范围；记入 S3 反转（与 F4 field_states 镜像同批处理） |

**C. 随结构重构处理（批次 A1 / A2，不在清理阶段动）**

`ApiSpec` 及全部消费方、`responses: dict[int]` 与 `responses.get(200)`、`RequestSpec.body_type`、`systems/*/dimensions.py`、`app.py` 写死导入、`systems/fin/models.py` 与 `declare()`、Python 接口实例 → Markdown（见第 11 节影响清单）。

验收：A / B 完成后，三侧全量测试通过；仓库内除 `design/archive/` 外不再有描述已退役结构的文档；注册表不再存在依赖注册顺序的行为。

### S1 plate 结构定义（当前）

| 批次 | 内容 | 估算（工作日） |
|---|---|---|
| A1 方言内核 | Spec 改造（Binding 联合、outcome 字符串键、删 version / updated_at）+ Frontmatter / Statement / Term 的 M2 + 方言解析 / 校验 / 渲染（含规范形）+ 迁移脚本与 151 个接口的等价校验（plate 自身测试闭环，暂不切消费方）+ 纪律测试改写为方言版（一文件一交付物；M2 封闭与无反向 import 守卫保留） | 4–6 |
| A2 消费方切换 | 统一加载器替换 `app.py` 写死导入、删除 Python 实例与按系统的 dim 注册 + 平台前后端适配（含前端直连面）+ `spec_json` 存量迁移 + 响应信封标明快照（G5）与锚点结构化（G4） | 4–6 |
| B release | 冻结（内容寻址构件 + call 投影 + 全局对象池）、manifest（模板 / 方言 / M2 版本）、交付件清单与 `gaps`（G6）、类型模板、结构化差异、校验规则全量、矫正日志 | 3–5 |
| C 收回自描述 | 执行器 v2.1 的协议 / 模式 / 订阅 / 参数登记表 / 报告定义 / 计划 / 调试原样复制进 plate + 契约测试 | 1–2（与 A1 / A2 并行） |
| D 编写与评审支撑 | 方言自描述（G1）、`check --json` 与无写入校验（G2）、词条候选检索（G3）、`diff --json`（G7）、Agent 编写 skill 初版、CI 接入（入库闸门的执行载体：plate 校验挂进 PR 流程——仓库现无任何 CI 配置，此项为运营前置）、CLI 入口（独立 console script `plate`，不用 `gimbal plate` 子命令——避免执行器包反向依赖 plate，见附录 D） | 2–3 |
| E 自举切片 | 以 gimbal-platform 为被测系统，「管理员管理成员」：原生编写 PRD 片段 + 词条 + user_story + 派生 Scenario + 执行 + 过闸门 | 3–5（瓶颈在人工评审与标注） |

另加 S1-0 清理约 1–2 个工作日，合计约 18–29 个工作日（原 A 批 3–5 天的估算在方言层全新、前端直连面补入后上调并拆分）。关键路径：清理 → A1 → A2 → B / D → E；C 与 A1 / A2 并行。提前里程碑：A2 完成后做不过闸门的简化版 E。注意 A2 与 B 之间存在弱护栏窗口：T / S 级校验规则要等批次 B 才全量就位，期间 Markdown 只有 M2 自身校验与迁移等价校验兜底。

风险：Markdown 回写边界情况、前端 api→binding 适配面、PG 存量迁移、step 片段对分支的表达能力、评审简报迭代。不含：fin 交叉检验（2–3 天）、规模化标注（持续进行）。

自举约束：工具与被测对象分离（固定稳定版 Gimbal 测工作版本平台，独立实例与库）；接入侧 Agent 可读原件，使用侧 Agent 只能用对外暴露面。

### 现有实现的影响清单（批次 A1 / A2 / B 的输入）

| 现有功能 | 位置 | 影响 | 处理 |
|---|---|---|---|
| 系统加载 | `http/app.py` lifespan 写死导入 fin / platform；`systems/*/dimensions.py` 按系统注册 dim（现仅 fin / common 有，platform 无） | 重写 | 统一加载器扫描 `systems/` 解析 Markdown，统一目录注册 dim |
| 内存注册表 | `registry/registry.py`、`registry/index.py`（by_route = service, method, path） | 改造 | 快照化 + 原子重载；路由键改为 `(protocol, service, *locator)` |
| 路由查询 | `http/grammar.py` `EndpointIndex.find_by_route`（经 registry by_route 按 (service, method, path) 精确键查） | 改造 | 路由键加 protocol，按 binding 协议分派 |
| 端点详情视图 | `http/views.py` `EndpointDetailView`（嵌套内嵌 `api` 对象，非平铺镜像） | 改造 | 嵌套 `api` 改 `binding`、outcome 字符串键、capability；顶层 `version` / `updated_at` 随 8n 删除 |
| gimbal 导出 | `export/gimbal.py` `_render_call` | 改造 | 按 6.2 的 binding → call 映射 |
| 平台导出 | `export/platform.py` `_render_endpoint_view`（api.method / path / auth / timeout）、`_ep_key_map` / `_call_coords`（按 method, path 关联 step 与端点） | 改造 | 读 binding；step 与端点的关联优先用 `view_hints.endpoint_id`，坐标匹配降为兜底 |
| 字段默认值 / 失败判据 | `service/field_defaults.py`、`service/failed_resolver.py`（`responses.get(200)`） | 改造 | 改读成功基准（http：数值最小 2xx）；failed_resolver 的正则解析保留到 failed_criteria 迁移为片段 |
| 取数视图 | `service/query_views.py`（api.method / path / auth / timeout） | 改造 | 读 binding |
| 服务到系统映射 | `service/system_from_service.py`、`paths_resolver.py` | 改数据源 | 读 `gimbal:system` |
| 默认模板 dim | Config / Meta / Resource / Scenario 索引 | 改数据源 | 读 `gimbal:defaults` |
| 场景转换 | `action_scenario_convert`（平台主链 `/convert`） | 契约不变 | 随导出改造回归 |
| 系统动态注册 | `action_system_register` / `action_system_sync`（C1 / C2） | 停用 | 附录 C X4 |
| 框架自描述 dim | `http/strategy_dim.py`、`http/generator_dim.py` | 不受影响 | 批次 C 扩充 |
| release | `release/release.py`（占位） | 新实现 | 批次 B |
| 平台侧 | `plate_client`（`/full`、`/convert`）、前端编排器 | 适配 | 批次 A2 |
| 测试 | `tests/plate` golden fixture | 更新 | 批次 A1 / A2 |
| 时间戳与契约版本 | `EndpointSpec.updated_at`（构造时取 `datetime.now(UTC)`）、`version`；`http/grammar.py` 用 `updated_at` 计算系统时间戳、`http/views.py` 镜像该字段 | 删除 | 见 6.2；系统时间戳改取快照提交时间 |
| 响应信封 | `http/envelope.py` | 改造 | 增加 `snapshot`（G5） |

### 对外能力的影响评估（平台、执行器现在依赖的 plate 能力）

| 现有能力 | 调用方 | 重构后 | 处理 |
|---|---|---|---|
| `GET /api/endpoint`（列表；平台传的 `per_page` 现被 plate 忽略、全量返回） | 平台目录聚合（`catalog.py`）、适配服务 | 保留；数据源改为 Markdown；条目中 `api` 改为 `binding`；重构时实现分页或移除该参数（接口规模到 700+ 时需要） | 平台 `board_assembler.py` 读 `item.api.method/path` 处改读 binding |
| `GET /api/endpoint/{id}/full` | 编排表单、适配、端点目录 | 保留；形状变化（binding、outcome 字符串键、capability），新增 `ref` | 平台后端 + 前端 `types/plate.ts`、编排器适配 |
| `POST /api/scenario/action/convert` | 执行主链 | 契约保留；新增 `ref`（见 8.3） | 回归 |
| `POST /api/endpoint/action/resolve-paths` | 响应路径选择器 | 纯函数，不受影响 | — |
| `GET /api/service` | 服务名列表 | 保留；数据源改为 `gimbal:system` | — |
| `GET /api/query-views` | 组合期取数 | 保留；QueryView 读 binding；非 `side_effect_free` 的 binding 须 `query_safe` | — |
| `GET /api/strategy…`、`/api/generators…` | 策略 / 生成器目录 | 不受影响（框架自描述） | 批次 C 扩充 |
| `GET /api/system`、`GET /api/systems/{s}/config` / `meta` / `resource/full` | 前端直连（`frontend/src/api/plate.ts`，经 `/plate` 代理） | 保留；数据源改 `gimbal:system` / `gimbal:defaults`；信封加 `snapshot`（G5）同样波及 | 前端 `types/plate.ts`、`api/plate.ts` 适配（批次 A2） |
| `GET /api/endpoint`（前端直拉） | 前端 `CaseComposerCatalog.vue` 经 `/plate` 代理 | 同后端条目：`api` 改 `binding` | 编排器直连处适配（批次 A2） |
| 适配版本戳中持久化的 `api.method/path`（`catalog_versions.spec_json` 存整份 /full item，`api` 为嵌套结构；`stamp_json` 是读取处局部变量名） | 平台 PG（`adaptation_service.py`） | 存量数据形状过时；不迁移则新旧比对必不等、触发全量假漂移 | 批次 A2 的 PG 检查项落到这里：倾向 alembic 迁移；实施前先全量确认 `spec_json` 无审计 / 档案用途的其他读点，若有则改新列或读时兼容 |
| 适配中心的变更检测与版本戳（完整修改面） | 平台适配中心（`adaptation_service.py`）：① `catalog_diff` 的 pending 门（:163，`_semver_gt` 比列表 `version`）；② `catalog_diff` 的 C12 异常门（:173-180，`updated_at > synced_at` → `updated_without_bump`）；③ `open_batch` 门（:380-407）；④ 基线落戳 / stamp 写回（:157-160、:611-613）；⑤ `from_version` / `to_version` 落库与展示（:407、:586、:875 的 `"-"` 占位路径；画像适配节点徽章）；⑥ 字段级 ops 的 `spec_json.api` 比对 | `version` / `updated_at` 删除后①③失去输入；②随之整条删除——hash 天然覆盖「改了忘 bump」，且消灭假时间戳导致的「plate 一重启即误报」类噪声；现状①③建于从不递增的常量上、事实上已失效 | 批次 A2：①③合并为一道 **shape_hash** 比较（轻列表 / `/full` 新增字段，见 7.2；`≠` 戳内指纹即 pending）；④戳的 version 列复用存 shape_hash（随 8m 的 alembic 一并）；⑤语义改为快照 / release 标识或 shape hash 前缀，`"-"` 路径自然消亡；⑥随 api→binding 形状适配（本就在 A2 范围）。净效果：两道假信号门 + 一类误报坍缩为一道 shape hash 比较；语义标注（capability / description / metadata）不触发适配批次——批次 E 为 151 个接口补 capability 不产生开批噪声；「ops 为空 → 自动按 skipped 关批」退为兜底（shape_hash 未覆盖但影响 ops 的边缘变更） |
| C1 / C2 系统注册 | 平台无调用 | 停用 | S1-0 清理 B4 |
| 执行器 | 不在运行时调用 plate；只消费 `/convert` 产物（`call{protocol}` + `view_hints.endpoint_id`） | 不受影响 | export 映射按 6.2 |

结论：平台后端依赖的 8 个 plate 接口全部保留；另有前端经 `/plate` 代理直连的 4 个 dim 查询与 1 处 `endpoint` 直拉，同样保留、随信封与 endpoint 形状一并适配。变化集中在 `endpoint` 的返回形状与新增 `ref` 参数；唯一的存量数据影响是 `catalog_versions.spec_json` 中的嵌套 `api`。另：生产部署若保留前端直连模式，内网边界即用户边界——当前全部为只读面且 S1 无 HTTP 写入，风险可控，与第 12 节 8g 一并评估。

### S2 适配 / S3 反转

- S2：平台与执行器按 plate 的定义工作；过渡期两份定义并存，用契约测试比对 JSON Schema 防漂移。
- S3：所有结构定义以 plate 为真源；执行器通过 release 构件（F1 / F2）消费。

### 路线图调整

- P4 验收门：`systems/platform` 上自举纵向切片端到端走通，存量定义零改动；D9 移入后置储备。
- S1 期间撰写只用本地编辑器（Obsidian / VS Code）+ `plate check` + git。

## 12. 待确认事项

| # | 事项 | 建议 |
|---|---|---|
| 1 | 核心边界（第 3 节）与三概念模型（第 4 节） | **已定** |
| 2 | Statement 的 7 种 kind 与槽位表（第 6.3 节）；Mapping 并入 mention | **已定** |
| 3 | Frontmatter 字段与交付物类型模板（第 6.1、6.5 节） | **已定** |
| 4 | ResponseSpec 不设 term，业务结果语义走 Statement | **已定** |
| 5 | HTTP 成功结果为任意 2xx；成功基准（字段默认 / 失败判据取数源）= 数值最小的已声明 2xx | **已定** |
| 6 | Term id 分隔符：(a) 保留 `:`，页面按实体命名，链接由 plate 解析；(b) 改为文件名可用的分隔符，便于 Obsidian 原生解析 | **已定**（(a)，由 8y 改判：`[[term-id]]` 已为纯约定、词条非一词一页，(b) 的 Obsidian 理由不再成立） |
| 7 | Term 加 `refers`（仅 attr → attr） | **已定**（加） |
| 8 | 横切结果（如 401）的 mention：`spec_path` 锚点允许接口通配 | **已定**（允许） |
| 8a | Statement 与 Frontmatter 增加 `id`（同步生成内容的 id 确定性派生） | 已并入 8w（旧表述取代） |
| 8b | outcome 的 `when` 允许列表（「且」）；增加 `ui` 锚点语法 | **已定** |
| 8c | 类型模板放 plate 全局配置目录，manifest 记录模板版本 | **已定** |
| 8d | 主线流程两道闸门（入库闸门 / 发布闸门）与 S1 不提供 HTTP 写入（第 8.1 节） | **已定** |
| 8e | 系统与服务声明用 `gimbal:system` 块（`type: system` 文件）；默认模板用 `gimbal:defaults` 块；按系统写的 dim 注册改由统一加载器完成 | **已定** |
| 8f | 词条、片段在现有 HTTP grammar 中注册为 `term` / `statement` 维度；`/full` 带 capability | **已定** |
| 8g | 原件放入 plate 后，内网边界是否足以保护 fin 的文档（含前端经 `/plate` 代理直连 plate 的只读链路——该模式下内网边界即用户边界） | fin 接入前确认 |
| 8h | 运行时与存储：不引入数据库；真源 / 构件 / 运行时索引三层；快照化、原子重载、`ref` 选版本（第 7.1 节） | **已定** |
| 8i | 新能力统一为 dim：新增 `term` / `statement` / `deliverable` / `type` dim（`kind` 系 8r 改名前的残留写法，以 `type` 为准），投影与 check / diff / release 作为动作（第 7.2 节） | **已定** |
| 8j | S1-0 清理：原则清单 P1–P8 与 A / B 两组清理项；清理先于结构重构执行（第 11 节） | **已定** |
| 8k | 面向 Agent 的补充 G1–G7（第 7.2 节） | **已定** |
| 8l | 消费方版本使用规则与首个 release 前的过渡（第 8.3 节）；部署环境 `working` = 主干最新提交，合入后 CI 拉取并重载（第 8.1 节） | **已定** |
| 8m | 适配版本戳（`catalog_versions.spec_json` 嵌套 `api`）的存量处理：迁移 / 读时兼容；迁移前先确认 `spec_json` 无审计 / 档案用途的其他读点 | **已定**（迁移，前置检查后执行） |
| 8n | 删除 `EndpointSpec.version` / `updated_at`（第 6.2 节）。版本管理去向：**历史归 git**（Markdown 文件行级 blame / log）、**版本归 release 快照 + manifest**（对象 hash，见 7.1）、**变更归结构化 diff**（两 manifest 比 hash，G7 / 9.1）、**消费侧钉住归 release_id**（8.3 / 第 11 项）；系统级 `1.1.0` 若有含义落 `gimbal:system`。现状核实：`version` 为每系统常量（fin 全部 `FIN_DEFAULT_VERSION="1.1.0"`、platform 全部 `"1.0.0"`），`updated_at` 为构造期 `datetime.now(UTC)`（假时间戳）；唯一真实消费方是适配中心开批的 semver 门（`adaptation_service.py:381`），建立在不递增的常量上、事实上已失效，重构改以 hash 级差异为触发（见影响评估表） | **已定**（删除） |
| 8o | 片段的 `spec_path` 锚点视为出处定位而非语义引用（第 4 节） | **已定** |
| 8p | 交付件清单与 `gaps` 共用判定项，新增 F4（第 7、8.2 节） | **已定** |
| 8q | QueryView 目前只对 http binding 有效（第 6.2 节） | **已定** |
| 8r | 术语：交付物的「种类 kind」改名为「类型 type」（frontmatter `type`、`types/*.yaml`、`type` dim），`kind` 只用于片段与词条 | **已定**（改名） |
| 8s | 块信封：`review` 由方言层统一处理，不进各 M2；交付物评审状态由块派生（第 6 节） | **已定** |
| 8t | 补齐类型模板 `db_design`、`state_design`，使 6.6 承载度表中的每类交付物都有对应模板（第 6.5 节） | **已定** |
| 8u | 架构评审十项优化 + 画像接线：CLI 入口独立 `plate`（附录 D）、构件含 call 投影 + 全局对象池 + manifest 记方言 / M2 版本（7.1）、系统目录路径可配置与部署拓扑成文（7.1）、`[[term-id]]` 纯约定（第 5 节）、框架 dim 全局挂载（7.2）、review 缺省 draft / 迁移置 reviewed / 零块拒（第 6 节）、P8 加法演进（S1-0 原则清单）、能力接线表（9.1）、A7 画像方案文档修订 | **已定** |
| 8v | release 对 draft 内容的处理：冻结只收 `reviewed` 块，draft 留在 working 继续演进；引用闭包检查——已冻结块只能引用已冻结的块与词条，违反即阻塞；词条与块同一口径：孤儿 draft 词条不挡发布，仅被待冻结内容引用时由闭包阻塞（已并入第 8.2 节发布闸门正文） | **已定** |
| 8w | 片段 id 规则（取代 8a 中「同步生成内容的 id 确定性派生」的旧表述，主线已无生成内容）：编写方分配，格式约定由 G1 暴露；交付物 id 缺省取路径，但一旦被引用须在 frontmatter 显式写出，否则改名即断引用（第 6.1 节「改名时保持不变」须以显式写出为前提） | **已定** |
| 8x | CLI 独立入口 `plate` 与路线图 G1 / G2「各组件命令组挂入统一 `gimbal` 入口」冲突，A6 需一并更新 G1 / G2 | **已定**（更新路线图，最小改法：只改 G2 为独立入口） |
| 8y | 第 6 项分隔符：`[[term-id]]` 已定为纯约定、词条也不是「一词一页」，(b) 的 Obsidian 原生解析理由不再成立 | **已定**（(a)，第 6 项已同步） |
| 9 | user_story 作为交付物类型（依赖 step 槽位能否表达分支，切片中验证）；Scenario meta 记 storyRef + pathId；路径展开放 plate | **已定** |
| 10 | 缺陷 / 事故作为交付物类型，内容为 rule / outcome + note | **已定** |
| 11 | 平台值记录关联 release_id；批量与惰性迁移都支持 | 关联（S2 前定） |
| 12 | 第二协议目标 | D9 启动时再定 |

第 8j 项已确认，S1-0 清理可启动。2026-10-07 确认记录（修订七 / 八）：第 1–10 项**全部定稿**——8n 亦确认删除，版本管理由 git 历史 + release 快照 / manifest（对象 hash；适配检测用 shape_hash）+ 结构化 diff + release_id 钉住承担；8g / 11 / 12 维持触发点延后。待确认项清零，第 6.2 节可合并为变更说明，交由 Agent 一次性适配（批次 A1 / A2）。

## 13. 延后事项

- 系统间关系：当前只支持单系统；`systems/common` 只放共享词条。标准层（跨系统标准词条 wiki）与 `aligns` 对齐（exact / close / broader / narrower）随系统间关系一起延后；届时标准层自底向上在语义矫正中提升，结算领域可用行业标准（ISO 4217、ISO 20022、Incoterms）作种子。
- 被测系统信息的时间维度（release 链、版本差异、用例变更插件实例）与拓扑维度（服务 / 协议 / 连接形态，D6）。
- 方言编辑器、评审 / 标注界面、原文件标注助手：plate 侧后续路线；片段块的标注细节后续定。
- 存量迁移工具：需要时单独实现。
- NEIGHBOR 接入（已有 `docs/NEIGHBOR-SPEC.md` v1.0，组件旁的 `NEIGHBOR.md` 声明拓扑层：依赖、被依赖、影响面）：NEIGHBOR 补上的正是词条覆盖不到的技术拓扑维度。接入时需定三点：① 格式——保留 NEIGHBOR 自身表格，还是在同一文件中增加 `gimbal:` 块供 plate 解析（R4 只允许一套语法，倾向后者）；② 位置——NEIGHBOR 在被测系统代码仓库中，plate 需按系统配置读取外部仓库路径，release 时冻结快照；③ 业务与技术的衔接——模块声明自己实现了哪些 `cap`，由此打通「需求 → cap → Spec → 代码模块 → 影响面」，可用于按变更影响选择回归用例。
- 非功能需求与边界校验（`metric` + `threshold`），见第 6.6 节。
- step 并行组，见第 6.6 节。
- 向量索引与嵌入模型。

---

## 附录 A：被取代的方案（2026-09-29 ~ 10-07）

| 方案 | 取代者 | 原因 |
|---|---|---|
| SurfaceMapping（spec / code / db / doc 四种强类型 locator） | Statement `mention` + 类型模板的锚点语法 | 与语义片段本质相同，合并以减少概念 |
| 8 种语义组件（定义 / 规则 / 前置 / 结果 / 迁移 / 影响 / 步骤 / 说明） | Statement 7 种 kind | 前置并入 rule（`before`），影响并入 outcome（`target`） |
| Artifact + ArtifactKind 结构 | 文件 + Frontmatter；类型模板为数据 | M1 已是 Markdown，一个交付物就是一个文件 |
| UserStory 独立 M2 | `user_story` 交付物类型 + step 片段 | 减少类型 |
| EndpointDoc 作为容器（含 DocAnchor 与分面） | 按 cap 聚合 Statement 的投影 | Doc 不直接引用 Spec；内容单元统一为片段 |
| `ResponseSpec.term` | Statement（outcome 片段 + spec_path 锚点） | 同一 HTTP 结果码下有多个业务结果，语义在值层 |
| 显式边目录作为待定稿结构 | 词条图由 registry 派生 | 图是派生消费，不属于核心定义 |
| 「每列都有 attr」的实体完成度判据 | 词条按需建立 | 穷举细粒度拆解会放大语义偏移 |
| 抽取器流水线（原件 → 生成方言副本；DB / 错误码 / PRD 抽取器） | 主线流程：人或 Agent 编写 → 评审 → 入库 | 原件即方言文件，消除原件与副本的偏移、哈希复核与敏感原文复制问题 |
| 生成内容的人工覆盖机制、原文 `text_policy` | 不再需要 | 随抽取器流水线一并取消 |

## 附录 C：非主线冲突记录（后续按主线原则说明变更）

| # | 对象 | 现状 | 与主线的冲突 | 主线原则下的方向 |
|---|---|---|---|---|
| X1 | contract_gen + contract_gen_py（`gimbal-bootstrap`） | 从平台 OpenAPI 生成结构化 py 接口定义（contract_gen 出中间形态、contract_gen_py 出 py；「可手改，重新生成默认不覆盖，`--force` 覆盖」的约定在 contract_gen_py 及其 CLI） | 主线不走自动生成；输出仍是 Python 实例 | 降为 Agent 编写的参考输入；产物经评审入库 |
| X2 | twin_generator（`gimbal-plate/tools`） | 从 fin PHP 源码（AST）抽取路由、Validator 规则、前端信息；`tmp/twin_gen` 下生成 715 个接口，已装入 25 个 | 同上；其抽取的长度 / 范围规则属当前范围外的边界校验 | 同上；边界规则在补上字面量机制前只能进 description |
| X3 | 「生成文件不可手改」与「capability 由人确认」 | 文档旧版第 5 / 9 节 | 主线下不存在生成文件，冲突消失 | 已从正文删除 |
| X4 | HTTP 动态注册系统（C1 `action_system_register`，内存态，重启即失）与 C2 同步占位 | plate HTTP 现有动作 | Markdown 为唯一真源时，系统必须对应文件 | S1 停用；随 HTTP 写入路径重新设计 |
| X5 | `systems/fin/models.py`（pydantic 体类，供 `declare()`） | 两个 fin 接口仍在使用 | 方言迁移后不再需要 | 迁移时把 `declare()` 展开为声明树，之后删除 |
| X6 | 执行器协议中立 vs 文档旧版「先只做 HTTP」 | 执行器已为通用请求过程 | 旧表述把 HTTP 写成范围限制 | 已修正第 6.2 节：Binding 联合与执行器协议注册一一对应 |

## 附录 D：使用指南（以「管理员管理成员」为例）

文件：

```
systems/platform/
  system.md                    # type: system     → gimbal:system + gimbal:defaults
  dictionary/user.md           # type: dictionary → 成员相关词条
  endpoints/users.md           # type: endpoints  → 成员接口 + 紧跟的片段（EndpointDoc 的编写形态）
  deliverables/prd-a2.md       # type: prd        → rule / outcome 片段
  deliverables/story-admin.md  # type: user_story → step 片段
```

常用操作（命令名为建议，以 CLI 归一 G2 定稿为准；入口已定：独立 console script `plate`——根 pyproject 增加一行 entry point，**不用 `gimbal plate` 子命令**，避免执行器包反向依赖 plate、与 `test_v3_no_reverse_import` 守卫的单向纪律一致，S3 执行器独立部署不被连带）：

| 场景 | 操作 |
|---|---|
| 新建交付物 | `plate new <type>`（按模板生成骨架） |
| 写之前查词条 | `plate term search <词>` |
| 本地校验 | `plate check --json`；未落盘内容 `--stdin` |
| 评审置位 | `plate review <交付物 id | 块 id> [--set reviewed\|draft]`（评审人批量置块信封，防手改 YAML 出错；随批次 D CLI 定稿——N4） |
| 查看本次改动 | `plate diff --base main --json` |
| 查看待办 | `plate gaps <系统>` |
| 合入后刷新服务 | `plate reload <系统>`（部署环境由 CI 触发） |
| 发布 | `plate release <系统>` |

角色：

| 角色 | 用法 |
|---|---|
| 编写者（人） | 在 Obsidian / VS Code 里写 Markdown；可先写正文，片段块后补 |
| 编写者（Agent） | 读代码与文档，按模板写方言文件；先 `term search` 再提议词条（draft）；提交前 `validate` |
| 评审者 | 看结构化差异与简报，按交付物评审，用 `plate review` 把确认可发布的内容置为 `reviewed` |
| 平台 | `/endpoint/{id}/full?ref=…` 渲染编排表单；`/convert?ref=…` 转换场景 |
| 执行器 | 离线加载 release 构件（S3），之前消费 `/convert` 产物 |
| 消费 Agent | `term/{id}/references`、`endpoint/{id}/action/doc`、`paths`：查能力的全部规则、结果与故事路径，用于生成用例与覆盖分析 |

## 附录 B：参考资料

- SKOS：<https://www.w3.org/TR/skos-primer/>、<https://www.w3.org/TR/skos-reference/>
- DataHub 元数据模型与 Business Glossary：<https://docs.datahub.com/docs/metadata-modeling/metadata-model>、<https://docs.datahub.com/docs/glossary/business-glossary>
- Ontology Development 101：<https://protege.stanford.edu/publications/ontology_development/ontology101.pdf>
- SHACL：<https://www.w3.org/TR/shacl/>；PROV：<https://www.w3.org/TR/prov-overview/>；Wikidata 数据模型：<https://www.wikidata.org/wiki/Wikidata:Data_model>
- Contextual Retrieval：<https://www.anthropic.com/engineering/contextual-retrieval>
- GraphRAG：<https://arxiv.org/abs/2404.16130>；LightRAG：<https://arxiv.org/abs/2410.05779>
- Knowledge Graphs 综述：<https://arxiv.org/abs/2003.02320>；LLM × KG 路线：<https://arxiv.org/abs/2306.08302>
- Bounded Context：<https://martinfowler.com/bliki/BoundedContext.html>
