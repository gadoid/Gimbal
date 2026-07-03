# Plate 子系统 — 总体设计与设计哲学

> 本文档面向**完全不了解本项目**的读者,目的:在阅读完本文后,你能理解 Plate
> 子系统是什么、它解决什么问题、为什么采用当前的设计,以及各个模块之间的关系。

---

## 1. 一句话定义

**Plate** 是 Gimbal 测试体系下的一个**契约模型仓库**(contract model
repository)。它的核心职责是:用一份**机器可读、人类可审、byte-equal 可复现**
的数据,描述"被测系统"对外暴露的所有 HTTP 端点(包括方法、路径、请求/响应
模型、字段绑定、分类标签、人工注释等)。这份描述既被 mock server 用于按
契约生成响应,也被 contract check 用于验证真实服务是否符合契约,也被 AI
Skill 用于理解业务接口的语义,也被客户端 SDK 用于按版本 pin 契约执行测试。

---

## 2. 命名由来

`Plate`(感光板)这个命名来自摄影史。在摄影发明史上,Plate 是 Film(底片)之前
的形态,意思是"被测系统留存在测试系统中的'底片'";同时取 base plate(基座)
之意,与 `Gimbal`(万向稳定架,提供测试执行稳定姿态)、`Prism`(棱镜,提供
能力分光)共同构成一套**光学—机械仪器命名链路**。

这种命名不是装饰,而是给项目一个**家族感**,让所有子系统在文档、代码、错误
信息中保持一致的"光学—机械"语义空间。

---

## 3. 它解决什么问题

在测试领域有一个反复出现的问题:

> **被测系统的接口定义(Swagger / OpenAPI / Protobuf / 手写文档)与测试系统
> 实际使用的契约,长期处于"两份数据"状态。**

这带来三类成本:
1. **漂移成本**:被测系统改了接口,测试系统的"我的认知"没跟上,跑出 false
   pass / false fail。
2. **重复成本**:同一份契约在多个工具(测试 / mock / 文档 / SDK)里被反复
   手抄,任何一份都可能是 stale。
3. **理解成本**:测试系统里"为什么这个端点要这么调"很难追溯回设计意图,
   尤其对 AI Skill 而言。

Plate 通过以下方式集中解决:

| 措施 | 解决的问题 |
|---|---|
| **单轨化数据**:所有端点都是 `EndpointSpec` 单一数据类,一份数据,所有工具消费 | 重复成本 |
| **按需加载 + thread-safe registry**:测试启动只 import 引用的 service | 启动成本 + 内存成本 |
| **byte-equal 序列化**:序列化产物可校验、可缓存、可跨进程一致 | 漂移成本 + 跨进程一致性 |
| **L1/L2 物理解耦**:L1(机器可再生)与 L2(人工写)独立 review | 误改成本 |
| **契约保真护栏**:`extra="forbid"` + 禁用清单,禁止默默吞掉未知字段 | 漂移成本 |
| **category + mutates_state 业务标注**:让 CT 主动探测避开业务写入 | 事故成本 |
| **FieldBinding 声明性依赖**:AI Skill / Mock server 自动按依赖注入 | 调用编排成本 |

---

## 4. 总体架构图

```
                            ┌─────────────────────────────┐
                            │  业务场景代码 (scenario)     │
                            │  + AI Skill (director)      │
                            └──────────────┬──────────────┘
                                           │
                                           │  resolve(service, method, path)
                                           ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │                       Plate 子系统                                  │
   │                                                                    │
   │   ┌──────────────────────────────────────────────────────────────┐  │
   │   │   facade 子包(对外门面)                                      │  │
   │   │   ├── PlateFacade   (3 模式: LOCAL_ONLY / HYBRID / REMOTE)   │  │
   │   │   ├── PlateClient   (SDK 占位,Phase 3 换真 HTTP)             │  │
   │   │   ├── decide_resolve  (mode 决策纯函数)                       │  │
   │   │   └── legacy          (旧 API 桥接)                           │  │
   │   └──────────────────────────────────────────────────────────────┘  │
   │       │                                                             │
   │       │ LOCAL_ONLY                                                  │
   │       ▼                                                             │
   │   ┌──────────────────────────────────────────────────────────────┐  │
   │   │   core(单例 registry)                                         │  │
   │   │   ├── _Registry       (thread-safe 拉式收集)                  │  │
   │   │   ├── EndpointKey     (索引键)                                │  │
   │   │   └── BootstrapError  (聚合异常)                              │  │
   │   └──────────────────────────────────────────────────────────────┘  │
   │       │                                                             │
   │       │ collect("fin") / resolve(...)                               │
   │       ▼                                                             │
   │   ┌──────────────────────────────────────────────────────────────┐  │
   │   │   service 子包(各业务服务)                                    │  │
   │   │   ├── Plate.fin/                                              │  │
   │   │   │   ├── endpoints.py  (31 个 EndpointSpec 实例)             │  │
   │   │   │   ├── models.py     (Pydantic 数据类)                     │  │
   │   │   │   └── dannotations/ (L2 人工注释,空壳起步)               │  │
   │   │   └── ... (后续 service)                                      │  │
   │   └──────────────────────────────────────────────────────────────┘  │
   │       │                                                             │
   │       ▼                                                             │
   │   ┌──────────────────────────────────────────────────────────────┐  │
   │   │   核心数据类                                                  │  │
   │   │   ├── spec.EndpointSpec   (L1 机器可再生)                     │  │
   │   │   ├── spec.EndpointCategory (业务标注枚举)                    │  │
   │   │   ├── spec.MockHook / ValidateHook / BuildRequestHook         │  │
   │   │   ├── binding.FieldBinding  (声明性字段绑定)                  │  │
   │   │   ├── doc.EndpointDoc       (L2 人工注释)                     │  │
   │   │   ├── version.PlateVersion  (语义化版本)                      │  │
   │   │   ├── serialization        (L1 byte-equal 序列化)             │  │
   │   │   ├── path_resolver        (logical schema 路径解析)          │  │
   │   │   ├── _aliases             (service 名 → 目录名)              │  │
   │   │   └── manifest             (版本快照 + SHA256 校验)           │  │
   │   └──────────────────────────────────────────────────────────────┘  │
   │                                                                    │
   └────────────────────────────────────────────────────────────────────┘
                                           │
                                           │  HTTP (Phase 2)
                                           ▼
                            ┌─────────────────────────────┐
                            │  server(只读视图 HTTP server)│
                            │  ├── router     (URL 路由)   │
                            │  ├── response   (JSON 工具)  │
                            │  └── PlateServer (进程实例)  │
                            └─────────────────────────────┘
                                           │
                                           │  读
                                           ▼
                            ┌─────────────────────────────┐
                            │  api_doc(Markdown 渲染)      │
                            │  ├── render   (L1+L2 → MD)  │
                            │  └── cli      (plate doc)    │
                            └─────────────────────────────┘
```

---

## 5. 核心设计原则(对每一个模块的"为什么"都来自这里)

### 5.1 零侵入(Zero-intrusion)

> **承诺:import Plate 不会触发任何业务子包的 import。**

这是设计 §7 的硬约束。具体表现:
- `Plate/__init__.py` 只 import 自己的 `core` 模块,绝不能 import `facade` /
  `server` / `api_doc` / `fin` / 其他 service 子包。
- `Plate.facade` / `Plate.server` / `Plate.api_doc` / 各 `service` 子包都是
  **按需**进入(由 scenario / 测试 / CLI 显式触发)。
- 任何想"便利地自动 import"的代码都会被 review 拒绝。

为什么:这保证 Plate 是"可选依赖"。如果哪天某个新 service 想用 Plate,但
Plate 的依赖里有某个有问题的传递依赖,不会影响"我只是想 import registry 取
一个 EndpointSpec"这个最小用例。

### 5.2 L1/L2 物理解耦

> **L1 = 机器可再生(可由代码生成)。L2 = 人工写(不可机器生成)。**

- L1 放在 `Plate.<service>.endpoints.py`(与 models.py 同包,共享 Pydantic
  类引用)。
- L2 放在 `Plate.<service>.dannotations/__init__.py`(独立子包,独立 review
  流水线)。
- L1 与 L2 物理上互相**不**依赖:`Plate.spec` 不 import `Plate.doc`,
  `Plate.doc` 也不 import `Plate.spec`。

为什么:很多契约细节是"机器能从数据推导的"(比如 method、path、request 模
型),这部分让代码生成比手写更可靠;另一部分是"只有人能写的"(限流、时区、
单位、前置条件),这部分必须人工维护。物理分离后,L1 的修改由"代码自动
重新生成"覆盖,不会污染 L2;L2 的修改走独立 review 流程,不会因为 L1 重新
生成而丢失。

### 5.3 按需加载(Lazy loading)

> **未引用的 service 一个字节都不 import。**

具体表现:
- `registry.collect("fin")` 才 import `Plate.fin` 包。
- `_Registry._index` 是空 dict 起步,collect 一个 service 才会触发
  `importlib.import_module("Plate.fin")` 并把里面的 `EndpointSpec` 实例
  装进 index。
- `Plate.api_doc.cli` 走延迟 import — 只在用户真的调 `plate doc fin` 时
  才 import `Plate.fin.dannotations`。

为什么:一个测试体系可能有几十个 service 子包,但一次跑测试只关心几个。
全部 import 会拖慢启动、占用内存、可能引入冲突(比如不同 service 的相对
import 路径名撞了)。

### 5.4 线程安全

> **多个测试并发 collect / resolve 同一个 service,行为正确。**

具体表现:
- `_Registry` 持有一把 `threading.Lock`,所有改 `_index` 和 `_loaded`
  的操作都在锁内。
- **关键约束**:`resolve` / `warm` 必须把 "collect + dict 读取/迭代"放在
  **同一把锁**内。否则锁外的 `for k in self._index` 会被并发的 collect
  触发 `RuntimeError: dictionary changed size during iteration`。

为什么:Python 的 dict 迭代不是线程安全的;`EndpointSpec` 本身是 `frozen`
dataclass,锁内取出后到锁外用是安全的(无 TOCTOU 风险)。

### 5.5 Byte-equal 序列化

> **同一份 spec,无论 import 顺序、tag 顺序、dict 插入顺序如何,序列化
> 出来的 JSON byte 相等。**

实现细节:
- `EndpointSpec.to_dict()` 中所有 list 字段先排序(`tags` 用 `sorted`、
  `responses` 用 `sorted by status`)。
- Pydantic 引用转成字符串 `"module.ClassName"`。
- `PlateManifest.compute_checksum()` 用 `json.dumps(sort_keys=True,
  separators=(",", ":"))` + SHA256。

为什么:版本校验、跨进程缓存、跨语言 SDK 互通都依赖 "byte 相等"。如果
JSON 产物会随 dict 插入顺序漂移,校验和就会每次都不同,等价于没有校验。

### 5.6 契约保真(Contract fidelity)

> **契约模型必须"如实反映 wire 格式",不允许"为了好用"做静默改写。**

实现细节(在 `spec._assert_safe_model` 里强校):
- 必须声明 `model_config`。
- 响应壳必须 `extra="forbid"`(未知字段 = 服务端改了 spec,必须 fail-fast)。
- 禁用清单(`str_strip_whitespace` / `coerce_numbers_to_str` /
  `use_enum_values`)必须全部关闭(双向,不分 request / response)。

为什么:契约保真 = 测试的可信度。如果契约模型默默把 `" abc "` 改成
`"abc"`,那这条字段的 wire 格式就被悄悄改了,后续断言会基于改写后的值,
与真实服务的字节差异被掩盖。

### 5.7 声明性 vs 命令性

> **描述"是什么"和"做什么",不规定"何时做 / 怎么做"。**

具体表现:
- `FieldBinding` 只描述"从 from_path 取值,注入到 to_path",**不**规定
  调用顺序、注入时机、并发模型。
- 转换(`transform`)是描述性字符串,本模块**不**做语义执行,只通过白名单
  防拼写错误。

为什么:声明性数据可以被多种执行器消费(Mock server / CT 主动保活 / AI
Skill 编排),不绑定到某一种执行模型上。

### 5.8 业务标注驱动可观察性

> **接口的"业务角色"和"是否改业务"是端点自身的属性,不是外部维护的元数据。**

具体表现:
- `EndpointCategory`(BUSINESS / QUERY / TOOL)是给消费者用的分类标签。
- `mutates_state`(bool)是给 category 背书的可验证事实。
- `spec.__post_init__` 强校:QUERY/TOOL 必须 `mutates_state=False`(否则
  CT 主动探测会触发业务写入)。

为什么:契约测试里有一类高危行为叫"主动探活"(CT 主动发请求确认服务存活)。
如果"探活"和"业务写入"共用一个端点,后果可能是生产事故。**把这件事写
进 spec** 而不是依赖调用方自律,可以从数据源头 fail-fast。

---

## 6. 各模块职责一览

| 模块 | 路径 | 一句话职责 |
|---|---|---|
| `core` | `Plate/core.py` | 进程级单例 registry:collect / resolve / warm,线程安全 |
| `spec` | `Plate/spec.py` | `EndpointSpec` + 三个 hook Protocol + 契约保真护栏 |
| `manifest` | `Plate/manifest.py` | 某版本 Plate 的完整快照 + SHA256 校验 |
| `binding` | `Plate/binding.py` | 声明性字段绑定 `FieldBinding` |
| `serialization` | `Plate/serialization.py` | L1 byte-equal 序列化工具函数 |
| `path_resolver` | `Plate/path_resolver.py` | 逻辑 schema 路径解析器(支持 list / dict / Optional 透明穿过) |
| `doc` | `Plate/doc.py` | `EndpointDoc` L2 字段(物理上独立于 spec) |
| `version` | `Plate/version.py` | `PlateVersion` 语义化版本(major.minor.patch) |
| `_aliases` | `Plate/_aliases.py` | service 名 → 合法 Python 目录名 反向映射 |
| `facade` | `Plate/facade/` | 对外门面:3 mode 路由 + SDK 抽象 |
| `fin` | `Plate/fin/` | 31 个端点的 fin 服务契约(L1) |
| `server` | `Plate/server/` | 只读视图 HTTP server(stdlib,零三方依赖) |
| `api_doc` | `Plate/api_doc/` | Markdown 文档渲染(库 + CLI) |

---

## 7. 阅读路径建议

如果你要**改某个具体模块**,建议按以下顺序读相关文档:

1. **先读 `core.md`** — 理解 registry 的 collect / resolve / warm 三个
   公开方法的语义(其他模块几乎都依赖 registry)。
2. **再读 `spec.md`** — 理解 `EndpointSpec` 数据结构(所有 service 子包
   的内容都是 EndpointSpec 实例)。
3. **然后按需读**:
   - 想加新 service → `fin.md`(看 fin 是怎么组织 endpoints / models /
     dannotations 的)。
   - 想加新 mode 或 SDK 客户端 → `facade.md`。
   - 想加新路由或返回头 → `server.md` + `server/response.md`。
   - 想做契约校验 / 文档导出 → `api_doc.md` + `serialization.md` +
     `manifest.md`。
   - 想做跨端点字段绑定校验 → `binding.md` + `path_resolver.md`。

---

## 8. 不要做的事(从历史踩坑中沉淀)

| 反模式 | 后果 |
|---|---|
| `import Plate.fin` 出现在 `Plate/__init__.py` 或 `Plate/core.py` | 破坏"零侵入"承诺;启动所有测试都付出 import fin 的代价 |
| 不用 `EndpointSpec` 而用 `dict` 描述端点 | 失去类型保护、契约保真护栏、序列化、绑定;后续重构成本巨大 |
| 在 `__post_init__` 之外做"运行时校验" | 校验时机不可预测;不变量在测试中漏检的概率上升 |
| 用 `frozen=False` 的 dataclass 做 EndpointSpec | 失去 "锁内取出后到锁外用是安全的" 不变量;并发场景 TOCTOU |
| 给 `responses` 字典插入时不按 status 排序 | 序列化 byte-equal 失效;checksum 不稳定 |
| 跨 service 写 "共享" Pydantic 模型 | 引发"一个 service 改了模型,另一个 service 静默受影响"的耦合 |
| `mock_hook` / `validate_hook` / `build_request_hook` 用同步阻塞 IO | Mock server 吞吐下降,响应延迟毛刺;hook 应该尽快返回或显式标 async |
| service 命名用连字符或数字开头却不登记 alias | 启动报 "service 'xxx' 不符合 Python 包名规范",且不知道在哪改 |
| 给 `summary` 写超过 120 字 | AI 总结时被截断失真(`EndpointDoc` 强校,直接 raise) |
| 用 `extra="allow"` 而不是 `extra="ignore"` | 静默接受未知字段,等于"白名单"破功,契约保真失效 |
| 让 `_Registry.reset()` 进入生产路径 | 测试隔离用 reset,生产用 reset 会把已 collect 的服务清空,后续 resolve 再次触发 import |
