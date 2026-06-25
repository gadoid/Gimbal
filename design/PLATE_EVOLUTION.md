# Plate 演进过程文档

> 记录 Plate 从 GIMBAL 内嵌静态模块演化为多系统共享接口真值服务的完整路径。
> 配套设计见 `PLATE_DESIGN.md`。

---

## 0. 演进总览

Plate 的演化分四个阶段，核心顺序逻辑：

> **先把数据模型的边界画对（Phase 1），再解决"谁该缓存什么"（Phase 2），
> 最后才扩展面向外部消费者的能力（Phase 3 / 4）。**
>
> 如果跳过 Phase 1 直接做服务化，会在"客户端该拉哪些数据"这个问题上反复返工——
> 因为 MCP 查询到的数据模型还在变，会反复破坏 skill 侧的假设。

```
Phase 0  ModelRegistry v3 RC        静态契约模块,已落地
   │     (拉式收集 + 锁内一致性 + EndpointSpec 形状契约)
   ▼
Phase 1  Plate 静态模块内部改造      不引入任何新服务,纯粹画对数据边界
   │     (category / FieldBinding / EndpointDoc / L1-L2 解耦)
   ▼
Phase 2  服务化基础设施              远端权威服务 + 轻量客户端 SDK
   │     (按需拉取 + 版本 pin + 离线兜底)
   ▼
Phase 3  动态服务能力                API doc / Mock / Plate-MCP
   │
   ▼
Phase 4  CT 主动保活(较后期)         只读端点定时探测 → drift report
```

---

## 1. Phase 0 —— ModelRegistry v3 RC（起点 / 已落地）

当前状态，作为演进基线记录。

**已具备**：
- `EndpointSpec`：`@final` + `frozen=True` 的纯契约形状描述（method/path/request/
  responses + 文档元数据 + 预留 hook）。
- 拉式收集：遍历 service 子包模块命名空间，`type(attr) is EndpointSpec` 严格匹配。
- 线程安全：`threading.Lock` 保护 `_index`/`_loaded`，"collect + 读"包进同一把锁。
- 按需加载：未引用的 service 一个字节都不 import。
- 共用 `warm()`：contract check 与 mock 启动同一入口，多 service 异常合并 fail-fast。
- 契约保真护栏：`_assert_safe_model` 检查 `extra="forbid"` + 禁用清单全关。
- `_aliases.py`：service 名 → 合法 Python 包名的反向映射兜底。
- `fin` 服务实例（`models.py`）：31 个端点的请求/响应模型 + `PATH_MODELS` 查询表。

**尚不具备（Phase 1 补齐）**：
- 接口角色分类（category）。
- 字段级依赖边（FieldBinding，目前 `required_bindings` 还活在 scenario 层靠流量挖掘）。
- 业务语义标注层（EndpointDoc）。
- L1 / L2 物理解耦。

---

## 2. Phase 1 —— Plate 静态模块内部改造

**目标**：不引入任何新服务，纯粹把数据模型的边界画对。这是后续一切的地基。

**任务**：

1. **重命名落地**：`ModelRegistry` → `Plate`（目录、import 路径、错误信息文案、
   docstring 引用全部跟随）。
2. **EndpointSpec 加 `category` 字段**：`EndpointCategory` 三值枚举
   （BUSINESS / QUERY / TOOL）。
3. **EndpointSpec 加 `mutates_state` 字段**：给 category 做可验证背书；
   `__post_init__` 加断言 `category in (QUERY, TOOL) ⇒ mutates_state is False`。
4. **FieldBinding 收编进 EndpointSpec**：对齐 `gimbal-traffic-to-scenario` skill
   现有的 `required_bindings` 概念，把字段级取值来源从 scenario 层的启发式产出
   提升为 Plate 的权威契约数据。`__post_init__` 校验 `field_path` 能在本接口
   request 模型字段树中解析到。
5. **设计独立的 EndpointDoc 注册表**：物理解耦存储（`docs.py`），通过
   `(service, method, path)` 外键关联；明确 GIMBAL 执行态不加载 L2。
6. **确认 TOOL 类边界**：核实"工具类"是否全部对应真实 wire 端点；若存在非 wire 的
   纯函数式业务规则，剥离到 GIMBAL 主框架层，不进 EndpointSpec。

**验收标准**：
- GIMBAL 现有执行链路无回归（L1 改造对执行态透明）。
- 导入 Plate 顶层不 import 任何子包（零侵入承诺不破）。
- `fin` 服务的 31 个端点全部补上 category；BUSINESS 类至少完成关键链路的
  field_bindings 标注。

**为什么这步不碰服务化**：数据模型边界没画对之前谈服务化，等于在流沙上盖楼。
Phase 1 的全部产出都是本地可验证的纯数据结构改造，风险可控、可独立交付。

---

## 3. Phase 2 —— 服务化基础设施

**目标**：把 Plate 拆成"远端权威服务 + 轻量客户端 SDK"，解决"谁该缓存什么"。

**背景动机**：Plate 从 GIMBAL 内嵌模块，演化为多系统（GIMBAL / Capture / Prism /
AI skill）共享的接口真值中间件——单一事实来源（single source of truth）。各消费方
不再各自维护一份接口结构，统一向 Plate 查。

**任务**：

1. **拆分形态**：
   - **远端权威服务**：承载既有 CI/CT/AI/human review pipeline，是接口真值的
     唯一权威来源。
   - **轻量客户端 SDK**：GIMBAL / Capture / Prism 统一依赖，不再内嵌全量契约。
2. **按需拉取 + 版本 pin**：
   - 客户端启动时检查本地缓存的数据类库，缺失则只拉取所需 service 子集
     （不是全量下载）。
   - 版本 pin 是**硬前提，不是建议**——只有 pin 住版本，才能保证执行可复现
     （同一份 scenario 在不同时间跑，依赖的契约必须是同一份）。
3. **离线兜底分层**：
   - 离线时只保留 `EndpointSpec`（L1，执行刚需的冷数据，可缓存可 pin）。
   - `EndpointDoc`（L2，查询时才需要的热数据，可容忍网络往返）离线时不强制保留。
   - 这样客户端不会因为带上全部文档而变重，离线时执行能力（结构化检查）仍完整，
     只是 AI 语义查询能力优雅退化。

**冷热数据分层（决定客户端缓存策略）**：

| 数据 | 冷/热 | 客户端策略 | 离线行为 |
|---|---|---|---|
| `EndpointSpec`（L1 契约） | 冷 | 缓存 + 版本 pin | 完整可用 |
| `field_bindings`（L1 依赖边） | 冷 | 随 EndpointSpec 一起缓存 | 完整可用 |
| `EndpointDoc`（L2 标注） | 热 | 按需向远端查,不预缓存 | 退化(AI 语义查询不可用) |

> 这正是 Phase 1 必须先做完的原因：L1/L2 边界没画清,客户端要么变重(把文档全下载),
> 要么离线时 AI 语义能力直接整体退化。

**验收标准**：
- GIMBAL 执行可在完全离线（仅本地缓存 L1）下完成结构化检查。
- 版本 pin 后,同一 scenario 重复执行依赖的契约字节级一致。

---

## 4. Phase 3 —— 动态服务能力

**目标**：面向外部消费者扩展能力。三项按成本从低到高排序交付。

### 4.1 API doc 服务（最先做，成本最低）

`PATH_MODELS` / `EndpointDoc` 现成结构直接渲染。合并 L1（字段、类型、状态码）+ L2
（业务语义、流程位置），按 category 分组展示，给阅读者一个业务流程整体地图，
而非按字母序平铺。

### 4.2 Mock server（成本中等）

`spec.py` 里 `MockHook` 协议已预留好，主要工作是补实现而非设计：
- 通用 mock：用 `spec.responses[status]` + `Field(examples=)` 填字段。
- `MockHook` 返回 `None` → 走通用逻辑；返回 `dict` → 用该 dict 作响应 body。
- 复用 `warm()` 入口启动。

### 4.3 Plate-MCP（成本最高，需服务分层稳定后才做）

**形态定位**：库 + MCP 双形态，按消费者分，不统一包成一个 MCP。

- **确定性脚本**（analyze_flow / validate_scenario / build_catalog）若与 GIMBAL
  同进程/同环境 → 直接 `from plate import ...` **库导入**：快、类型安全、无服务依赖。
  给脚本套 MCP 是无谓的进程边界。
- **模型装配时的交互式查询**（"order_id 该从哪取""这个 assign target 在
  EndpointSpec 里存在吗"）→ **MCP 的正当场景**：消费者是 agent，运行时按需问。

**与现有图谱设计同构**：Plate-MCP 是 kg-mcp（知识图谱）/ exec-mcp（GIMBAL 执行）
之后的**第三个 sibling**，落在"确定性结构脊柱 + 可选语义 RAG"的图谱设计里。

**对 skill 的三个增强点**（都做成可选增强，Plate 不可达时优雅退化回流量挖掘——
保住 skill 纯 stdlib、可直接丢进 `~/.claude/skills/` 跑的可移植性）：

1. **catalog**：`build_lookup_catalog` 优先用 Plate 的声明式响应 schema +
   field_bindings 生成解析边（权威路径，零启发式）；Plate 未覆盖的接口再退回抓包挖。
2. **validate_scenario**：加类型检查——每个 assign 的 target 字段在消费者
   EndpointSpec 里是否存在、类型是否匹配；每个 extract 路径在生产者响应 spec 里
   是否存在。把"防幻觉"从"能在某条响应里解析"升级到"符合契约"。
3. **上下文补全**：scenario 装配时按需查 field_bindings / EndpointDoc，
   帮 AI 排出正确调用顺序、理解业务流转。

> **为什么 MCP 排在最后**：MCP 查询到的数据模型必须稳定，否则会反复破坏 skill 侧的
> 假设。所以 Plate-MCP 应在 Phase 2 的客户端/服务分层稳定之后才做。

---

## 5. Phase 4 —— CT 主动保活（较后期）

**目标**：让 Plate 主动检测契约 drift，而非被动等抓包发现。

**机制**：
- **读侧（主动）**：CT 组件定时主动探测**只读端点**，检测响应结构是否偏离已登记的
  `EndpointSpec`，把 drift 写进 drift report，**喂进 review pipeline 而非自动更新
  spec**（自动更新会绕过人工评审，风险高）。
- **写侧（被动）**：写接口的结构更新仍走 Prism 抓包被动捕获（写接口不能主动探测，
  会产生真实业务副作用）。

**硬性前置依赖**：
1. **category / mutates_state 必须可靠**（Phase 1 产物）：只有
   `category in (QUERY, TOOL)` 且 `mutates_state is False` 的端点才能安全探测。
   标错类目 = 探测脚本可能在生产意外触发业务写入（真实事故风险）。
2. **版本 pin 机制**（Phase 2 产物）：drift 检测的基准是"已 pin 的某版本契约"，
   没有 pin 就没有可比对的基准。

**为什么排最后**：依赖前三阶段的全部产出（可靠分类 + 服务化 + 版本 pin），
且本身价值是"提前发现 drift"的优化项，不是阻塞项。

---

## 6. 阶段依赖关系图

```
Phase 1 (数据边界)
  ├─ category / mutates_state ──────────────┐
  ├─ FieldBinding (收编 required_bindings)   │
  ├─ EndpointDoc (L2 解耦)                    │
  └─ L1/L2 边界 ──────┐                       │
                      ▼                       │
Phase 2 (服务化)  冷热数据分层缓存             │
  ├─ 远端服务 + 客户端 SDK                     │
  ├─ 按需拉取 + 版本 pin ──────┐               │
  └─ 离线兜底(只留 L1)         │               │
                              ▼               ▼
Phase 3 (动态服务)        Plate-MCP      Phase 4 (保活)
  ├─ API doc (最先)       (需服务分层稳定)  └─ CT 主动探测
  ├─ Mock server                            (需可靠分类 + 版本 pin)
  └─ Plate-MCP
```

**关键依赖**：
- Phase 1 的 L1/L2 边界 → 决定 Phase 2 的冷热缓存策略。
- Phase 2 的版本 pin → 是 Phase 3 Plate-MCP 数据稳定 与 Phase 4 drift 检测基准的
  共同前提。
- Phase 1 的 category/mutates_state → 是 Phase 4 主动探测安全性的硬前提。

---

## 7. 演进过程中保持不变的承诺

无论演化到哪个阶段，以下不变：

1. **零侵入**：导入 Plate 顶层不 import 任何子包；"导入 Plate 不破坏任何东西"。
2. **按需加载**：未引用的 service 不 import；执行态不加载 L2。
3. **契约保真**：模型不改写 wire 格式（extra=forbid + 禁用清单全关）。
4. **互补而非替代**：Plate 提供静态契约级真值，流量挖掘提供动态实例级值流向，
   两者始终互补。
5. **优雅降级**：服务化后，Plate 不可达时消费方退回本地缓存 / 流量挖掘，
   不硬绑必须在线的服务。
