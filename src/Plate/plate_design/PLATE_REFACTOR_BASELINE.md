# Plate 重构需求定案(基线文档)

> 版本:v1.2 · 2026-07-23 定稿(v1.1:四存储收缩为两层核心 + 端口预留,ontology 除名,evidence 后置。v1.2:B10 升级为"描述/装载"统一原语,catalog 定义为 describe 的机械聚合)
> 性质:需求与结构基线。实现期与 AI 协作时挂在上下文中,任何偏离本文档的改动需先修订本文档。
> 冻结范围:需求、目录结构、纪律、裁剪决定。实现级细节(map 条目粒度终切、L2 文件格式)授权动手时就地决定,但须回写本文档附录。

---

## 0. 一句话定位

**Plate 是被测系统的行为分身与测试体系的记忆器官**:让"了解被测系统"从散落在人脑、文档、脚本中的隐性状态,变成一个可查询、可校验、知道自己边界、且随每次分歧变厚的显性系统。

Plate 与 GIMBAL(内核执行器)、Meter(决策规划器)构成三件套。Meter 单向消费 Plate;需持久化的归 Plate,Meter 无状态。

---

## 1. 需求清单(终稿)

### A 组 — 既有需求(重构中保留)

| # | 需求 | 现有承载 |
|---|---|---|
| A1 | EndpointSpec 单轨数据模型,含契约保真护栏(role-aware extra 策略、禁用清单) | spec.py |
| A2 | category × mutates_state 交叉校验(CT 探测防误写业务) | spec.py |
| A3 | 线程安全、按需加载的解析能力(resolve / warm 语义) | core.py |
| A4 | byte-equal 序列化与 manifest 校验和(漂移检测) | serialization.py / manifest.py / version.py |
| A5 | FieldBinding 声明性跨端点依赖 + 点分路径静态解析 | binding.py / path_resolver.py |
| A6 | 文档投影(api_doc) | api_doc/ |

### B 组 — 定案的新需求(本次重构引入)

| # | 需求 | 定案要点 |
|---|---|---|
| B1 | 两层存储 + 端口预留 | 核心两层:contracts(L1)+ bindings(L2)。evidence(历史路径、决策留痕、盲区清单)仅定义端口(EvidencePort),实现随 Meter 上线落地(ndjson 追加日志)。ontology 除名:候选投影,由 L2 + evidence 推导,不设独立存储 |
| B2 | L2 binding 体系 | anchor + kind 五类(definition / constraint / behavior / relation / pitfall)+ 受控自然语言 statement;与 L1 物理解耦、独立 review;**数据载体**(非 Python) |
| B3 | 面向 Meter 的供给接口 | provenance 能力事实(queryable / flow / static / injectable)+ 知识覆盖度 / 成熟度申报 |
| B4 | MCP 投影 | Meter 第一版依赖 Plate 的 MCP 策略查询;第一入口为 `plate.describe()` |
| B5 | 分歧驱动的知识摄入 | 人的纠正、CT 漂移、执行失败归因留痕成分歧数据,反哺 L2(冷启动飞轮进料口) |
| B6 | 图投影 | 由 L1 / L2 / 流量推导生成 lock 文件,不手工维护;与 NEIGHBOR 模块级拓扑独立 |
| B7 | 联邦查询 | 易变内容走外部适配器,Plate 不落地存储;稳定知识内部维护 |
| B8 | evidence 写回通道 | Meter 决策输出写回 Plate(Meter 零存储) |
| B9 | map(catalog) | skill-map 式 name + description 渐进披露索引,Agent 概述入口;**纯投影**,description 源自 L2 definition,缺失降级为机械描述并标记盲区 |
| B10 | 接口化统一原语:描述 / 装载 | 一切知识层与组件实现同一对原语:`describe()`(廉价、静态,返回 name + description + 能力/模式 + 版本指纹,**不触发装载**)与 `load()`(按需装载,返回该层的访问端口)。catalog(map)= 全体组件 describe 的机械聚合;新层接入 = 实现这对原语,内核零改动。第一版仅 local 实现,协议签名先定 |
| B11 | 一致性检查(guard) | L1/L2 对称性、anchor 可解析性(靠 path_resolver)、evidence 引用完整性;在再生与摄入两个时点强制执行,并触发投影重算 |
| B12 | 套件规范 | 一个被测系统 = 契约代码(Python 包)+ L2/evidence 数据 + 策略组形状 + 套件 manifest;凭据"形状在套件里、值在套件外";Plate 摄入套件 manifest 的形状以供给 static / injectable 两类 provenance |

### C 组 — 结构性定案(讨论中拍板)

| # | 问题 | 定案 |
|---|---|---|
| C1 | fin/ 归属 | 迁出至 suites/fin/;套件自治,Plate 经 `_aliases` 机制按包名挂载收集 |
| C2 | L1 载体 | **Python**。Pydantic 模型即结构的一等描述,类型检查 / 值域 / extra 策略免费;不用数据再描绘一层结构。"机器可再生"= 生成 Python 代码 |
| C3 | L2 载体 | **数据文件**。L2 是语义断言非结构,按 C2 同一判据反向适用。doc.py / dannotations 为胚胎,废弃并作迁移源 |
| C4 | facade / server 双轨 | 整体删除(1090 行)。其设计意图(本地/远端多后端)由 B10 接口化正确继承 |
| C5 | 知识数据归属 | knowledge/ 目录只装**引擎**(schema + 读写器 + 校验器);被测系统的 L2/evidence 数据跟套件走,执行时绑定(存储卷式抽象) |

---

## 2. 目录结构(定案)

```
src/Plate/
├── contracts/     # L1:挂载收集 + registry + 验收门
│                  #   收编 spec.py / binding.py / path_resolver.py / core.py / _aliases.py
├── knowledge/     # 引擎 only:L2 binding 的 schema 定义与本地读写;evidence 仅端口定义
├── guard/         # L1/L2 对称性、anchor 解析、evidence 引用完整性;投影重算触发
├── projection/    # manifest(后续扩展覆盖 knowledge)/ catalog(map)/ api_doc;图 lock 后置
│                  #   收编 serialization.py / manifest.py / version.py / api_doc/
├── supply/        # 本地供给:provenance、成熟度、联邦路由;ports 协议定义(单文件)
├── mcp/           # supply 的 MCP 投影(薄):plate.describe() / plate.resolve() 打头
└── ingest/        # 分歧摄入、evidence 写回

suites/<system>/   # 被测系统套件:
│   ├── <契约 Python 包>        # L1
│   ├── bindings/*.yaml         # L2
│   ├── evidence.ndjson         # 后置(EvidencePort 实现落地时启用)
│   └── suite.manifest          # 策略组形状 + 环境形状(值在套件外)
```

七个目录,每个都有第一或第二实现片的职责,无占位目录(空壳仅限 README 声明职责)。

**近亲边界**(三者共用 projection 序列化地基,不重复):

- manifest:答"内容是否一致"(checksum,漂移检测)
- 图投影:答"业务上什么关联什么"(关联查询)
- catalog(map):答"这里有什么、多成熟、怎么查"(Agent 定向;MCP 第一入口)

---

## 3. 纪律(四条,违反即架构腐化)

**D1 · 投影红线**:一切派生物(map、图、manifest、api_doc)必须由存储推导生成,严禁手工维护。手工维护的投影就是项目自养的漂移源,与"漂移即缺陷"的中心论题自我矛盾。map 的 description 源头在 L2,人只写一处。

**D2 · 生成验收门**:AI 生成的契约代码以 `spec.py` 的 `__post_init__` 强校 + import 收集 0-spec 报错作为验收关卡——信任模型是"验收严格"而非"生成正确"。生成后强制 formatter + 字段排序约定(写入生成 skill 的硬行为规则区),保证再生 diff 可 review。

**D3 · 拉取纪律(远端启用时生效,当前封存)**:每个可拉取单元强制被 manifest 覆盖;本地缓存记录 pin 的 checksum;使用前 stale 检测,过期显式报错不静默;拉取的 contracts 只读,knowledge 可操作但经 ingest 写回;map 条目声明 `modes: [ref, pull]`。

**D4 · 切片规矩**:每一实现片必须有即时消费者;空壳目录半行实现不写;范围渗漏是半月计划失败的唯一方式。检验飞轮:每季度自问——"过去三个月,是否有一次测试决策,Agent 靠查 Plate 做对、靠 grep 代码库做不对?"连续两季答不上,停止加组件,回头补 L2。

---

## 4. 裁剪记录(砍了什么、为什么、何时回来)

| 砍除项 | 理由 | 回归条件 |
|---|---|---|
| 专用 codegen 引擎 | 生成侧全体系皆为 skill/Agent 运行时,确定性引擎是异类;验收门已足够强 | 无(D2 长期替代) |
| remote adapter / 拉取 / 物化 / stale 检测 / locator | 单套件单机下无真需求;Protocol 签名已定,后加零破坏 | 出现第二消费环境或跨团队共享需求 |
| facade/ + server/(1090 行) | Phase 2 过渡脚手架,意图被 B10 继承 | 不回归 |
| adapters/ 目录 | 仅 local 一个实现,不值一个目录;并入 supply | 远端回归时拆出 |
| 图投影 lock | 消费者(Meter 关联查询)未上线 | 第三实现片 |
| ontology 独立存储 | 无已定消费者;relation/behavior 语义已由 L2 承载;设为独立源将与 L2 漂移,违反 D1 | 不回归。若图查询有真实消费者,以投影形式从 L2 + evidence 推导 |
| evidence 存储实现 | 首个消费者是 Meter / 飞轮(第三片);先定 EvidencePort 协议,实现是一个 ndjson 追加日志 | 第三实现片 |

---

## 5. 首片计划:validate 替换(半个月)

**目标**:GIMBAL 执行器的响应校验切换到 Plate,Plate 上热路径。
**完成定义**:GIMBAL 全量场景走 Plate validate 跑绿 + 旧校验路径物理删除 + manifest 自证重构前后契约零漂移。

**体量账**:现存框架约 2800 行(4850 − fin 2038),其中 contracts 族约 1250 行原样保留;七成搬运删除、三成新写。核心能力总预算 ≤ 1 万行。

### 第一周 — 结构落位 + 门面成型

1. 目录重组:contracts/ 收编五文件;projection/ 收编四件;其余五目录建 README 空壳
2. 删除 facade/ + server/;doc.py / dannotations 标 deprecated(第二片迁移源)
3. fin 迁出 suites/fin/,验证 `_aliases` 挂载路径
4. 新写 validate 门面:`plate.validate(service, method, path, payload, status)` 单入口;内部 resolve → responses / response_data_models → role-aware 校验;错误信息保持"作者友好"水准

### 第二周 — 换接 + 收口

5. 摸清 GIMBAL 现有校验调用点与语义差异(**全片最大日程风险**);隐性行为要么补进门面、要么显式砍除并记录
6. 新旧路径对拍:同批响应双路校验,结论一致或差异可解释,之后删旧路径
7. manifest 生成跑通,输出重构前后 checksum 对比

**风险预案**:第二周中段仍未摸清语义差异 → 门面先兼容旧行为换接上线,差异砍除顺延第三片,不拖 deadline。

### 后续片(顺序既定,启动时间不定)

- **第二片**:L2 数据载体 + guard 对称性校验 + EvidencePort / IngestPort 协议签名(仅定义);fin 31 端点开始积语义(doc.py 胚胎字段迁移映射:summary→definition、notes→pitfall、requires→constraint、see_also→relation)
- **第三片**:evidence 实现落地(ndjson)+ ingest 写回 + provenance + 成熟度 + catalog(map)+ MCP describe/resolve,喂 Meter 第一版
- **第四片(封存)**:remote adapter 与拉取模式

---

## 6. 能力承诺(最终形态对照表)

| 消费者 | Plate 能答的问题 |
|---|---|
| 执行器(GIMBAL / Darkroom / CT) | 契约解析与校验;mutates_state 事实;manifest 漂移检测;FieldBinding 依赖注入 |
| Meter(决策层) | 字段 provenance 四通道;L2 语义按 anchor 检索;成熟度申报(知道自己不知道什么);图关联(后置);联邦代理易变查询 |
| 生成管线(Director / skill) | AI 生成契约的验收落地;分歧摄入;evidence 写回 |
| 人 | L1/L2 独立 review;知识可溯源(anchor 机械校验);投影可再生 |

**边界(不做)**:不做决策(阈值归 Meter);不存易变业务数据(联邦);不含被测系统业务代码(套件);不产日志报告(执行器)。

---

## 附录 · 授权就地决定项(决定后回写)

- [ ] map 条目粒度终切(倾向:两级——service/业务域 → 查询能力,总量数十条内;条目 = name + description(≤120 字符)+ 查询指针)
- [ ] L2 数据文件具体格式(YAML 倾向;anchor 采用 path_resolver 可校验的点分路径)
- [ ] suites/ 套件 manifest 的字段规范(喂 static / injectable provenance 的形状声明)
