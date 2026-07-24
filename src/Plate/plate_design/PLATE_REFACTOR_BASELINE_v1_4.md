# Plate 重构需求定案 v1.4（Agent 驱动闭环 + ViewFinder + 对象世界收口）

> 版本:v1.4 · 2026-07-24 定稿
> 前置基线:[PLATE_REFACTOR_BASELINE_v1_3.md](./PLATE_REFACTOR_BASELINE_v1_3.md)
> 性质:在 v1.3 基础上的演化性升级,冻结范围同 v1.2/v1.3(需求、目录结构、纪律、裁剪决定)。
> 演化动机:围绕"Agent 如何端到端驱动测试流程"的多轮讨论——把 Plate/Gimbal 边界从"类型检查"收口到"对象世界完全内封",把 map(B9)从概念定为具体产物 ViewFinder,把 Meter 的运行形态从"skill"精确为"支持多轮工具调用的会话(ReAct)",并明确三方(人/Agent/机器)共用知识系统的并行访问模型。

---

## 0. 一句话定位(再演化)

**Plate 是人、Agent(Meter)、执行器(GIMBAL)三方并行共用、持续生长的知识系统**;GIMBAL 保持纯执行内核;Meter 是驱动测试流程的**默认入口**(不是架构强制的唯一入口)——它以支持多轮工具调用的会话形态运行,通过 MCP 消费 Plate、生成并驱动 scenario.json 交给 GIMBAL 执行,并把交互中产生的人的纠正写回 Plate,构成闭环。人保留直接消费 Plate(review/审计/冷启动认路)与直接驱动 GIMBAL(手写 scenario.json)的并行通道,不经过 Agent。

---

## 1. v1.4 相对 v1.3 的演化总览

| 维度 | v1.3 形态 | v1.4 形态 |
|---|---|---|
| `ResolveResult` 跨边界字段 | 同时向调用方暴露 `request_obj`/`response_obj`(Pydantic 实例)与 dict | **仅暴露 dict + plain 元信息**;Pydantic 实例(含 `model_validate`/`setattr`/`model_dump`)完整封装在 Plate 内部,一步不跨边界 |
| scenario 加载期路径校验的调用方 | B13.5 示例代码隐含 Gimbal 侧持有 `response_model: type[BaseModel]` | **Gimbal 只传字符串锚点**(service/method/path/status/field_path),`guard.validate_field_path()` 在 Plate 内部完成解析,消除与 D5 的矛盾 |
| 跨端点字段注入(FieldBinding 执行) | 待实现,形态未定(B13.4 提议 `execute_bindings(source_obj, target_obj, ...)`,对象世界签名) | **`apply_bindings()` / `assemble_request()`,dict-in/dict-out**,内部对象世界操作对调用方不可见 |
| map/catalog(B9) | 概念性定义:"skill-map 式 name+description 索引" | **正式命名 ViewFinder**;`describe()` 输出新增 `tags` 字段,ViewFinder 建 tags 倒排索引 |
| ViewFinder 生成时机 | 未定 | **纯函数,按需现算,不落盘不缓存**(否决了"事件触发重算 + lock 文件 + checksum 过期检测"方案) |
| Meter 消费 Plate 的入口 | `plate.describe()` 单入口 | **拆分为 `describe()`(浏览,被动静态) + `gather()`(意图驱动组装,主动触发 load)两个入口**,职责不重叠 |
| Meter 实现形态 | "做成 skill(与 gimbal-runner/Director 同运行时)" | **明确为支持交互式多轮工具调用的会话(ReAct)**,非批处理式单次脚本调用 |
| Plate 的消费者模型 | GIMBAL / Meter / 生成管线 / 人,未区分访问方式 | **三类角色(人/Agent/机器)对 Plate 有各自独立、并行、互不阻塞的访问通道**,机器走同步函数调用,Agent 走 MCP,人走 CLI/文件 |
| Agent 与 GIMBAL/Plate 的关系 | 未明确 | **Agent 是默认入口,不是架构强制的唯一入口**;人可以绕过 Agent 直接消费 Plate、直接驱动 GIMBAL |

---

## 2. 新增/修订需求项

### B14 · Plate/Gimbal 对象世界完全收口(强化 B13,修订 D5 的落地方式)

**背景**:B13 引入 `ResolveResult` 时,为"策略层 O(1) 属性访问"这一理由同时暴露了 `request_obj`/`response_obj`。经核算,dict 按 key 取值与属性访问性能无差异,该理由不成立;继续暴露会导致 Pydantic 实例事实上跨越 Plate/Gimbal 边界,与同一文档新增的 D5 纪律矛盾。

**修订**:

1. `ResolveResult` 面向 Gimbal 的公开字段收窄为 `request_dict` / `response_dict` / `errors` / `valid` / `spec.category` / `spec.mutates_state` 等 plain 值;`request_obj`/`response_obj` 不再对 Gimbal 可见。
2. 一切"对象世界"操作(`model_validate` / `setattr` / `model_dump`)封装为 **dict-in/dict-out 的 Plate 函数**,新增两个具体操作:
   - `apply_bindings(from_dict, to_dict, bindings) -> (dict, tuple[BindingError, ...])`——替代 B13.4 的 `execute_bindings`,签名改为纯 dict
   - `assemble_request(service, method, path, static: dict, context_values: dict) -> AssembleResult`——把 scenario 里 static + 上一步 extract 出的 context 变量合并、类型转换、跨字段一致性校验,一次性完成,Gimbal 不需要自己先拼好一个合法 dict 再让 Plate 挑错
3. `guard/scenario_loader.py` 内的路径校验函数改签名为纯字符串接口:
   ```python
   def validate_field_path(
       service: str, method: str, path: str, status: int | None, field_path: str
   ) -> ValidationIssue | None
   ```
   `type[BaseModel]` 一律不出现在 Gimbal 侧代码路径里,消解 B13.5 示例代码与 D5 的字面冲突。
4. `load()` 允许有**两种具体实现**,共享同一套内核(registry / path_resolver / assemble):
   - **in-process port**(供 Gimbal):函数引用,同进程零成本
   - **MCP JSON 网关**(供 Meter/外部 AI):每次调用是完整 JSON request/response,不传函数引用

### B15 · ViewFinder:分层组件发现 + tags 索引(细化 B9/B10)

**定名**:B9 的 map/catalog 正式命名为 **ViewFinder**(摄影术语链命名延续——"取景不感光"对应 describe 廉价、不触发 load)。

**组件发现协议**:复用 `spec.py` 现有的 `@runtime_checkable Protocol` 风格(与 `MockHook`/`ValidateHook`/`BuildRequestHook` 同构),新增:

```python
@runtime_checkable
class Describable(Protocol):
    def describe(self) -> dict: ...
```

任何组件只要在模块顶层挂一个满足此签名的 `describe`,即为"可被 ViewFinder 收集",不需要继承、不需要注册。

**两层发现,颗粒度不同**:

- **套件级(动态,复用现有机制)**:`suites/*/` 目录树增长时自动被 ViewFinder 扫到,复用 C1 定案的 `_aliases` 挂载机制与 `core.py` 已有的拉式收集模式,不新增代码。
- **内部层级(静态,人工策展)**:`contracts/knowledge/guard/projection/supply/mcp/ingest` 七层的 describe 入口是**写死在 `projection/viewfinder.py` 里的一份短列表**,加第八层需要人工改这份列表——刻意的摩擦,防止内部层级被自动发现机制悄悄插入"插件"。

**tags 字段**:`describe()` 输出新增 `tags` 字段,值来自既有 L1/L2 分类维度的机械拼接(`EndpointCategory` / `mutates_state` / L2 binding 的 `kind` / service 名 / `maturity`),不新造词表、不引入自由文本标注,遵守 D1(单一真理源)。

**索引**:ViewFinder 在一次遍历中同时产出 `entries` 与按 tag 分组的倒排索引 `by_tag: dict[str, list[str]]`,供 O(1) 查询。

**缓存决策(否决项)**:曾提议"事件触发重算(挂 guard 三时点)+ 落盘 `viewfinder.lock` + checksum 过期检测",经成本核算(describe() 本身内存级廉价 + registry 自带进程级 import 去重)否决——**ViewFinder 保持纯函数,每次调用现场遍历聚合,不落盘、无过期概念**。若未来规模增长到需要缓存,第一步应是进程内内存缓存(模仿 `core.py` 的 `_loaded: set[str]`),落盘/事件触发/checksum 校验属于更重的机制,仅在真实出现跨进程复用需求时启用。

**版本指纹**:若未来需要,直接复用 `manifest.py` 现成的 `compute_checksum`(SHA256,规范 JSON 序列化),聚合对象从"端点 dict 列表"换成"describe 输出列表",不新造哈希机制。

### B16 · `gather()`:意图驱动的知识组装(细化 B4,拆分自"需求一/需求二")

**问题拆分**:B4 原文"MCP 策略查询"这一表述实际混合了两种不同性质的需求,现予拆开:

- **需求一(浏览式)** = ViewFinder:被动、静态、Agent 还未确定具体目标时"看一眼有什么",数据来自 §B15 的现成聚合,零额外 IO。
- **需求二(意图驱动式)** = `gather()`:Agent 已带具体目的,需要主动组装一份上下文包,允许触发真实 load()。

**`gather()` 签名(第一版)**:

```python
def gather(
    *,
    tags: tuple[str, ...] = (),
    service: str | None = None,
    category: EndpointCategory | None = None,
) -> GatherResult:
    """
    1. 用 ViewFinder 的 tags 倒排索引筛出候选(读现成聚合结果,零额外 IO)
    2. 对候选逐个触发 load()/resolve(),拿到完整 schema + L2 binding + maturity
    3. 拼成面向本次请求的上下文包返回(含未覆盖到的 blindspots)
    """
```

**边界**:入参**只接受结构化过滤条件**,不接受自然语言;"人话需求 → 结构化 tags"这一步的翻译职责不属于 Plate(见 B18)。

### B17 · Meter 运行形态:多轮 ReAct 会话(修订 Meter 实现路线)

**定案**:Meter 的最终形态是**支持 chat 的多轮 ReAct agent**,不是单次工作流(workflow)实现。此前"Meter 做成 skill"的表述需精确为:**skill 必须运行在支持交互式多轮工具调用的会话载体上**(而非被 CLI 唤起、跑完退出的批处理式脚本)。

**对 Plate 的影响**:无新增设计负担。ReAct 循环所需的"已探索什么、当前决策到哪一步"等状态,完全是会话自身的上下文(LLM scratchpad),**Plate 不引入任何"会话"概念**,继续保持无状态、可重复调用的纯函数集合——这与既有的"Meter 无状态"原则是同一件事的两个表述,不冲突。

**分歧写回时机**:人在会话中对 Agent 决策的纠正,**按次立即写回 evidence**,不攒批到会话结束再提交——理由:会话不保证优雅结束;分级放权的信任积累需要保留纠正发生的时间顺序。

**待定项(未在本轮定案)**:Meter 具体挂载的会话载体(Claude Code 交互会话 / Claude Tag / 专用 chat 界面)尚未选定,留待独立讨论,因为不同载体的运行时约束(同步/异步、超时、唤起方式)会影响 MCP 工具的具体暴露方式。

### B18 · Plate 三方并行消费模型(新增)

**定案**:Plate 同时服务三类角色,各自独立、并行、互不阻塞:

| 角色 | 访问通道 | 用途 |
|---|---|---|
| 人(审计/维护角色) | CLI / 直接读 L1(Python)/L2(YAML) / api_doc / ViewFinder | review、冷启动认路、排障 |
| 人(使用角色) | 手写 scenario.json,经既有 guard 校验后交 GIMBAL | Meter 未上线阶段或 Agent 处理不了的边缘场景下的并行驱动路径 |
| Agent(Meter) | MCP:`describe()` / `gather()` / `resolve()` | 决策、编排、生成 scenario、驱动 GIMBAL |
| 机器(GIMBAL) | 同步函数调用:`resolve()` / `guard.validate_field_path()` / `assemble_request()` | 执行期校验与组装,不经 MCP、不经对话 |

**需求拆解职责**:"人话需求 → 结构化 tags/gather 参数"的翻译由 **Meter 负责**,Plate 只提供语料(tags/schema/L2 语义),不做自然语言理解——保持"Plate 不做决策、只供给事实"的既有判据。

**入口定位**:Agent 是驱动测试流程的**默认入口**,不是架构强制的唯一入口。人绕过 Agent 直接消费 Plate 或直接驱动 GIMBAL,不视为"逃生舱"(不需要监控使用频率或加访问限制)——因为 Plate/Gimbal 的接口设计本身不区分调用方是 LLM 还是人,B13 的"校验职责压回 L1 schema"这一收益对人手写 scenario 与 Agent 生成 scenario 是同等适用的。

---

## 3. 纪律更新

### D5 · Pydantic 类型边界(强化措辞,承接 v1.3)

不变更 v1.3 原文,但落地方式按 §B14 修订:**B13.5 示例代码里 `response_model: type[BaseModel]` 出现在"Gimbal scenario 加载器"内的写法作废**,标准写法见 §B14 第 3 条。

### D6 · MCP 序列化边界(新增)

`EndpointSpec` 中的 `mock_hook` / `validate_hook` / `build_request_hook` 为 Python callable,**禁止出现在任何面向 MCP 的输出里**(不可 JSON 序列化)。`describe()`/`resolve()` 面向 MCP 的视图必须显式排除所有 callable 字段,不得直接对 spec 做 `dataclasses.asdict` 全量吐出。in-process port(供 Gimbal)不受此限——同进程函数引用合法。

---

## 4. 目录结构增补(在 v1.3 基础上)

```
src/Plate/
├── contracts/
│   ├── resolve.py / resolve_result.py     # v1.3 既有,ResolveResult 按 B14 收窄字段
│   └── assemble.py                        # v1.4 新增:apply_bindings / assemble_request
├── guard/
│   └── scenario_loader.py                 # v1.4 明确:validate_field_path(纯字符串签名)
├── projection/
│   └── viewfinder.py                      # v1.4 新增:B15 描述的两层发现 + tags 索引,纯函数实现
├── mcp/
│   ├── describe.py                        # 浏览式入口(B15 数据源)
│   └── gather.py                          # v1.4 新增:意图驱动组装入口(B16)
└── ingest/
    └── (写回逻辑按 B17"按次写回"调整,不做会话级批量提交)
```

---

## 5. 裁剪/缺口记录新增

| 项目 | 状态 | 备注 |
|---|---|---|
| ViewFinder 事件触发重算 + lock 文件 + checksum 过期检测 | **否决** | 成本倒挂;describe() 本身廉价,现算优于缓存;若未来规模增长,先上进程内内存缓存,不直接跳到落盘方案 |
| queryable provenance 通道 | **已识别缺口,未解决** | static/flow/injectable 均有落地机制,queryable(运行时动态查询)目前无对应执行钩子;等待真实消费场景出现再设计,不为填补而强造机制 |
| 跨套件关联查询 | **维持原裁剪(归 B6)** | 不在 ViewFinder 构建聚合时预计算(避免 O(n²));按需触发、以单个实体为起点做局部扩展查询,消费者(Meter 流程编排)未上线前不启动 |
| 远端套件的缓存/过期处理 | **维持原裁剪(归 D3)** | 责任下放给具体套件自己的 load() 实现,复用已封存的 pin checksum / stale 检测机制,不由 ViewFinder 统一处理 |

---

## 6. 附录 · 待决项(回写区)

- [ ] Meter 具体挂载的会话载体选型(Claude Code / Claude Tag / 专用 chat 界面),影响 MCP 工具暴露方式与超时设计
- [ ] `gather()` 入参 schema 的最终字段集(当前草案:tags/service/category,是否需要 kind/maturity 等更多维度)
- [ ] `assemble_request()` 的详细错误结构(是否复用 `ResolveResult.errors` 的 `ValidationIssue` 类型)
- [ ] ViewFinder 内部层级"七条固定列表"具体存放位置(`projection/viewfinder.py` 内的模块级常量,已倾向但未最终落笔)
- [ ] 人绕过 Agent 手写 scenario.json 这条路径,在 Meter 上线后是否需要任何形式的可观测性(不做访问限制,但要不要至少做使用情况的被动统计,供 D4 季度自问参考)

---

## 7. v1.3 → v1.4 演化路径总览

```
v1.3(2026-07-24)                          v1.4(2026-07-24 同日续)
─────────────                             ─────────────
ResolveResult 暴露 obj+dict        ──────→  仅暴露 dict,对象世界完全内封(B14)
FieldBinding 待实现,签名对象世界    ──────→  apply_bindings/assemble_request,dict-in/dict-out
scenario 加载器隐含持有 BaseModel   ──────→  guard.validate_field_path 纯字符串接口
map/catalog 概念性定义             ──────→  ViewFinder 具体实现:分层发现 + tags 索引(B15)
map 生成时机未定                   ──────→  纯函数、按需现算、不缓存
describe() 单入口                  ──────→  describe()(浏览)+ gather()(组装)双入口(B16)
Meter="做成 skill"(表述含糊)        ──────→  Meter=多轮 ReAct 会话,非批处理脚本(B17)
Plate 消费者关系未分层              ──────→  人/Agent/机器三方并行访问模型(B18)
```

**演化方向的一致性**:v1.3 把校验职责从 scenario 压回 L1 schema;v1.4 在此基础上把"对象世界"完全收口进 Plate 内部,并把"谁、以什么方式访问 Plate"这件事从隐含假设变成了显式的三方并行模型——两次演化都是同一条主线的延伸:**边界越清晰,各方(人/Agent/机器)能各自安全地扩展的空间就越大**。
