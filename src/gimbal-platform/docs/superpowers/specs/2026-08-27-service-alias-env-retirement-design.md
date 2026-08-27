# 服务别名(per-endpoint service alias)+ 执行环境彻底退役 设计文档

- 日期:2026-08-27
- 状态:已拍板,待评审
- 前置:[2026-08-27-rundialog-overlay-observability-design.md](2026-08-27-rundialog-overlay-observability-design.md) §13 记录的四项验收反馈,本文档是 ①③(执行环境退役、服务源/别名)重新讨论后的拍板结果与修订设计;②已修复、④已实现,不在本文范围
- 关联勘明:本设计的影响面勘察结论(api.service 全触点、endpoint 重拉链路、引擎单 base_url 阻塞点)在本文各节内联记录

## 0. 拍板记录(2026-08-27,用户逐项确认)

> 上一版 spec 在 brainstorm→spec 阶段丢失了两条用户决策(§13 ①①③③)。本节逐条记录本次拍板,实施与后续 spec 不得偏离。

| # | 决策 | 内容 |
|---|---|---|
| D1 | 别名形态 | **每 endpoint(步骤)粒度**:步骤 `api.service` 可引用 `config.services` 声明的别名键(不同于 Plate 目录服务名);未配别名 = 沿用 Plate 服务名;同一服务多实例/多用户 = 多别名键各引各的 |
| D2 | 环境退役程度 | **彻底退役**:RunDialog tiles、RunRequest.env、RunEnv 模型、envs.yaml、/api/envs、RunScheme.envId、ExportOverlay.envId、materialize env 补缺层全部删除 |
| D3 | 绑定行范围 | **声明 ∪ 引用并集**:config.services 全部声明键 ∪ 步骤引用但未声明的名字(标红,可现场填 URL 救燃) |
| D4 | 持有方案 | **作者期直写 `api.service`(方案 A)**;否掉 orchestration sidecar 注入(方案 B,模板不一致深坑,见 §1.2) |
| D5 | 别名↔目录映射 | **前缀派生**:别名 = `<目录服务名>-<后缀>`,`-` 唯一分隔符、后缀不含 `-`(最后 `-` 唯一切分),UI 据目录名集合派生归属;零 sidecar、后端 schema 零增,映射编码在键名里随 definition 走(导入回路天然自洽,见 §1.3)。原 serviceMeta sidecar 方案否决 |
| D6 | 校验风格 | 警告级不阻塞(撞目录名黄警、跨服务引用黄警),与现有「降级预填不报废」一致 |
| D7 | 引擎改造 | **保留 per-step base_url 三触点改造**(业务确认:场景内部存在多服务地址需求);查表只用 `scenario.config.services`,bootstrap 零触碰零适配 |
| D8 | 配置文件 | 引擎 `config/env/*.yml` 零修改;平台唯一删除的配置文件是 `backend/app/core/envs.yaml` |

## 1. 服务别名模型

### 1.1 两字段与存储(全部落 `composer_scenarios.payload` JSON 列,不加表不加列)

```
composer_scenarios.payload
├─ definition                      # plate 契约层(外发/导出)
│   ├─ steps[N].api.service        # ① 别名引用 — 现有字段,值为全串别名键(方案 A 直写)
│   └─ config.services             # ② 别名声明 {全串别名: URL} — 现有字段,零结构变化
└─ orchestration                   # 平台 sidecar 层(plate 零感知,永不外发)
    └─ steps / resourceMeta / runSchemes   # 现有,别名零新增键
```

**后缀不单独存储**:存储单元永远是全串键 —— ① 引用与 ② 声明各存一份全串;「后缀」与「目录归属」都是 UI 渲染/创建时的派生视图,不落库。内联创建器把「目录名(固定)+ 后缀(输入)+ URL」拼成全串,一次动作双写 ①② 两个现有字段;此后系统里只有全串。

依据(勘明):
- plate `ApiSpec.service: str` 自由字符串,无注册名校验([api_spec.py](../../../../gimbal-plate/gimbal_plate/schema/endpoint/api_spec.py))
- 引擎 `_do_http_call` 语义就是「api.service 是查 config.services 的 key」([engine.py](../../../../gimbal/gimbal/statemachine/engine.py))
- 平台物化 `_referenced_services/_apply_services` 按引用键查绑定/声明([run_materialize.py](../backend/app/services/run_materialize.py))
- `${service.<key>}` 模板按声明 dict 解析([scenario_preprocessor.py](../../../../gimbal/gimbal/preprocessor/scenario_preprocessor.py))
- 数据库从不 SQL 查询 payload 内部([composer_scenario.py](../backend/app/models/composer_scenario.py) docstring)

**酸性测试**:派生输入(plate 目录服务列表)整体清空,执行结果与导出产物一个字节不变 —— 前缀失配仅令 UI 降级为裸声明黄警,派生是视图不是配置源。

### 1.2 方案 A(直写)与否掉方案 B(sidecar 注入)的理由

方案 B(orchestration 持 stepIdx→别名映射,物化期改写 api.service)的深坑:headers/path/body 里的 `${service.x}` 模板是作者手写字符串,物化改写只动 api.service 字段、扫不动模板 → 模板引用域与 api.service 改写结果不同步。方案 A 作者期一处一致(api.service 与 `${service.*}` 同写别名),执行链零注入零改写、画布所见即所跑。

### 1.3 前缀派生规则(D5 二次拍板,替代 serviceMeta sidecar)

```
别名形态:  <目录服务名>-<后缀>          如 fin-1、fin.tidb-test-2
分隔符:    "-" 为唯一分隔符;后缀非空且不含 "-"(创建期拦截)
           → 别名内最后一个 "-" 必是分隔符,切分唯一确定、不依赖目录
派生规则:  按最后一个 "-" 切出 base 与后缀;base ∈ plate 目录名集合 → 归属 = base
           (目录名本身可含 "-",如 fin.tidb-test / fin.tidb-test-qa,切分天然正确)
未配别名:  api.service = 目录名本身(现状),查 config.services 同名键
派生位点:  仅平台 UI(下拉过滤/归属标签/跨服务黄警);引擎与物化零感知,键查表语义不变
```

- 派生失败(base 不在目录名集合,如手改 JSON 造出后缀含 "-" 的违规键)= 裸声明降级(§1.5 黄警),不猜、运行零影响 —— 键 + URL 自洽
- 内联创建:前缀(目录名)固定不可改,只填后缀(非空、不含 `-`)与 URL;保存时拼全串双写 ①②
- Config 声明卡:归属列 = 派生只读标签,无手填;改后缀 = 删行重建(v1 不做键改名传播)
- 导入回路:映射编码在键名里随 definition 走,导入目标目录一致即自动恢复过滤/归属;目录漂移则降级裸声明(优于 sidecar 的必然丢失)
- 后端 schema 零增(Orchestration 不动),别名特性 = 纯前端 + 引擎

### 1.4 编辑交互

**步骤面板(别名消费点)双显** —— 现只读事实区([CaseComposerCanvas.vue](../frontend/src/components/composer/CaseComposerCanvas.vue))改为:

```
接口事实(目录,只读)              运行引用(可编辑)
method  POST                     服务引用 [fin.tidb-test-2 ▾]
目录服务 fin.tidb-test               ├─ fin.tidb-test        ← 目录服务名(默认/现状)
path    /order                       ├─ fin.tidb-test-2      ← 前缀派生归属 == 本endpoint目录服务
                                     ├─ fin.tidb-test-prod     (只列派生到本服务的)
                                     ├─ (其他声明键,置底灰显)  ← 选了黄警「跨服务引用」
                                     └─ + 为此服务新建别名…   ← 内联创建(前缀固定)
                                   URL 预览(按声明解析,只读)
```

- 内联创建:后缀 + URL → 拼全串一次双写 `config.services` 声明 + `steps[k].api.service` 引用切换(即用户描述的「配置每个 endpoint 时为服务起别名」)
- 目录插入(`onAddEndpoint`)默认写 Plate 服务名(现状不变)

**Config 页声明卡(别名定义点)**:现有服务映射卡每行加 `归属` 列(前缀派生只读标签;派生不出显示「未挂目录」)。

### 1.5 校验语义(全表警告级,不阻塞)

| 情形 | 表现 |
|---|---|
| 引用别名,前缀派生归属 = 本 endpoint 目录服务 | ✅ 主路径 |
| 引用别名,派生归属 ≠ 本服务(跨服务) | 🟡 黄警(网关/mock 场景可能故意跨) |
| 引用别名,base 不在目录名集合(裸声明) | 🟡 提示「未挂目录服务」,下拉置底 |
| 引用键完全未声明 | 🔴 红(RunDialog 并集行兜底可救燃;不救则引擎显式报错,现有语义) |
| 全串 == 目录服务名 | 非别名,即目录名直引(按 config.services 声明解析,现状) |

### 1.6 冲突矩阵与契约禁令

**plate 定义拉取与 api.service 的关系(勘明:现状无覆盖链路)**:

| 触点 | 时机 | 覆盖别名? |
|---|---|---|
| `onAddEndpoint` | 目录插入写一次 | 初值=规范名,此后无写入 |
| `/full` 会话缓存 | 每次配置 endpoint 现拉 | ❌ 只读渲染数据(字段表单/断言/响应参考),不回写 api 对象 |
| 适配中心 apply_op | plate 目录变更适配 | ❌ 按 view_hints.endpoint_id 定位,STEP_OPS 只动字段层 |

**契约禁令(写入实施约束)**:任何 plate 拉取驱动的回写(现存适配 ops、未来契约同步)**不得触碰 `api.service`** —— `view_hints.endpoint_id` 是目录锚点,`api.service` 是用户引用键,两权分立。禁令延伸覆盖未来导入链:导入按**不透明键**处理 `api.service`,不得对 plate 目录做存在性校验、不得按目录名规范化改写(违此则别名场景导入即坏)。

**命名约定**:别名 = `<目录服务名>-<后缀>`,`-` 为唯一分隔符,后缀非空且不含 `-`(内联创建与 Config 卡两处入口创建期拦截;目录名本身可含 `-`,不受影响);别名因此天然保持 `系统.名字` 前缀(config.services 分组展示与 checkSystemMismatch 的 `svc.split('.')[0]` 依赖前缀)。

## 2. 执行环境彻底退役(D2)

### 2.1 删除清单

| 区域 | 删除项 |
|---|---|
| 前端 RunDialog | 环境 tiles、「请选择执行环境」校验;confirm 签名 `confirm(envId, ds, opts)` → `confirm(ds, opts)` |
| 前端 CaseComposer | `loadEnvs` 调用、envs store/api、方案应用回填 envId、降级标记 env 部分 |
| 后端 schemas | `RunRequest.env`、`RunEnv` 模型、`RunScheme.envId`、`ExportOverlay.envId` |
| 后端 routers | `/api/envs` 端点;run-schemes 端点 envId 存在性校验 |
| 后端 dispatcher | env 比对告警、config_json 留痕 `envId` 键(历史记录旧键由前端 RECIPE_LABELS 标签保留可读) |
| 后端 materialize | `env_base_url` 参数与补缺层 |
| 配置文件 | `backend/app/core/envs.yaml`(含 data 目录 override 机制) |
| 「上次运行」派生 | 去 envId(只取 dataSetIds/serviceBindings) |

### 2.2 URL 优先级链简化

```
改前:显式绑定 url > 场景 authored > env.baseUrl 补缺
改后:显式绑定 url > config.services 声明值          (两层,env 层删除)
未声明且未绑定 → 引擎显式报错(现有语义,发现时机由 RunDialog 并集行提前)
```

服务默认 URL 唯一来源 = `config.services` 声明(勘明:plate 目录无 URL,`ServiceDefinition` 只有 name/title/version/description)。

## 3. RunDialog 用户与服务区(D3)

- 检索源从 `steps[].api.service` 引用面(CaseComposer `referencedServices`)改为 **config.services 全部声明键 ∪ 步骤引用名并集**
- 未声明引用行:标红「未声明」,URL 空可现场填(填了即绑定,能跑);或提示去 Config 页补声明
- 每行 [用户▾][URL____] 不变,URL 预填声明值
- RunScheme 随 D2 变为 `{name, dataSetIds, serviceBindings, plugins, logSub}`;「存为方案」快照、方案回填、schemeToOverlay、按方案导出跟随调整(旧含 envId 方案由 pydantic 静默忽略降级)

## 4. 引擎 per-step base_url 改造(D7)

### 4.1 现状与转正

原 rundialog spec §2 非目标表第一条「引擎 per-step base_url ——『同场景同 service 不同 URL』需求出现时立项;三触点已勘明」。**本设计即该触发条件成立**(用户确认:场景内部存在多服务地址需求;且多服务场景今天在引擎里就是错路由的 —— `_pick_base_url` 多键时取第一个 + warn「其他 service 的 step 会失败」)。非目标转正为本节。

### 4.2 三触点(全部可选参数、空值回落现行为,向后兼容)

```
scenario_preprocessor.py  run() 增返 scenario.config.services dict(_pick_base_url 保留兼容路径)
scenario_runner.py        StepRunner 构造增 services: dict = {}(空 → 回落现 base_url 行为)
statemachine/engine.py    _do_http_call: service_url = services.get(api.service)
                          回落 _service_base_url;都没有 → 现有显式报错语义不变
```

构造点唯一(勘明:`StepRunner`/`StepStateMachine` 真实构造只在 scenario_runner.py:149/276;`preprocessor.run()` 真实调用只在 scenario_runner.py:261,另一处为 docstring 示例)。

### 4.3 查表范围(拍板 D7:只查场景声明)

- 查表 dict = **`scenario.config.services` 一个 dict**,不合并、不 normalize bootstrap
- 模板解析 `root["service"]`(bootstrap+场景合并)维持现状不动 —— 与查表层只在场景声明键上交集,该部分天然一致
- bootstrap 独有键进不了 URL 解析 = 现状保持,零回归

### 4.4 明确不碰

模板解析、认证/users/AuthRegistry、StepRef、超时/重试、reporter/cli/scheduler/suite/plugins/ai(grep 勘明零涉及)、`config/env/*.yml`。唯一行为变化:多键场景从「错路由后 HTTP 层失败」变「正确路由」(严格改进;断言旧降级 warn 的测试更新)。

### 4.5 bootstrap 修缮不进本次

`bootstrap.services` 嵌套结构(`{name: {base_url, timeout}}`)在 `_pick_base_url` 兜底路径取出的 dict 从不可用作 URL —— 现状坏而不伤(平台/导出产物永远自带场景声明,该路径无真实消费者)。登记独立小项,触发条件:出现依赖 bootstrap 兜底 URL 的部署诉求。

## 5. 导出行为

| 层 | 默认导出(不带方案) | 按方案导出 |
|---|---|---|
| 别名声明 config.services | 编辑期已写,原样带出,**零合并** | 绑定 URL 覆盖对应别名键 |
| 别名引用 api.service | 原样带出 | 不动(键不变,变的是键指向 URL) |
| 用户凭证 | 定义自带 users | 绑定 authAlias 注入 users |
| 别名→目录归属 | 键名前缀编码,随定义走(§1.3 派生) | 同左 |
| runSchemes 本体 | 不导出 | 不导出(bindings 已物化进产物副本) |

按方案导出的物化 = **已实现**的 `materialize_run_copy`(spec §8 / commit 412bf95):方案 bindings 作为 overlay 参数显式传入,物化发生在产物副本,库里 definition 永不被改写。别名机制零新增合并 —— 绑定键就是别名键,现有「显式绑定 > 声明值」语义直接套用。导出产物与平台执行跑同一引擎,per-step 查表同时惠及两者。

**产物自洽性(导入安全基线)**:别名引用(`steps[].api.service`)与别名声明(`config.services`)同在 definition 随产物走 —— 产物对任何 gimbal 部署自包含可执行,消费方按「键查表」语义工作,零别名感知。**不存在「后续必须按别名导入」的约定**;且归属映射编码在键名里(前缀派生,§1.3),导入后目录一致即自动恢复过滤/归属/黄警,仅 `endpoint_id`(导出剥离,所有导入场景通用)丢失影响重链目录 —— 都只是编辑体验降级,不影响运行与再导出。导入侧硬约束见 §1.6 禁令延伸与 §7。

## 6. 变更点清单(文件级)

| 区域 | 内容 |
|---|---|
| 前端 CaseComposerCanvas | 步骤面板双显 + 服务引用下拉(按 of 过滤)+ 内联建别名;目录插入不变 |
| 前端 CaseComposerConfig | 声明卡归属列(前缀派生只读);删声明行即删键(无联动清理) |
| 前端 CaseComposer | referencedServices 改声明∪引用并集;env 装配删除 |
| 前端 RunDialog | 环境 tiles 删除;confirm 签名去 env;绑定行取并集;方案回填/降级去 envId |
| 前端 api/types/stores | envs api/store 删;RunScheme/RunRequest/ExportOverlay 类型去 env |
| 后端 schemas | RunRequest.env/RunEnv/RunScheme.envId/ExportOverlay.envId 删(别名零 schema 增) |
| 后端 routers | /api/envs 删;run-schemes 校验调整;preview-plate overlay 去 env |
| 后端 run_dispatcher | env 校验/config_json 键/上次运行派生调整 |
| 后端 run_materialize | env_base_url 补缺层删 |
| 后端 core | envs.yaml + 加载逻辑删 |
| 引擎 ×3 | §4.2 三触点 + 测试 |
| plate | **零改动** |

## 7. 非目标(带触发器)

| 项 | 触发器/时点 |
|---|---|
| bootstrap.services URL 兜底修缮 | 依赖 bootstrap 兜底 URL 的部署诉求出现 |
| 导入反向映射(产物 config → 平台实体) | feature-gaps #1 立项;立项时须守 §1.6 禁令延伸(api.service 不透明键:禁目录存在性校验、禁按目录名规范化改写);别名归属随键名前缀自动派生(§1.3,无需重建),仅 endpoint_id 重链为增强项(候选 = 按 method+path 匹配 / 导出 bundle 旁挂平台 meta) |
| 数据集行展开导出 | 沿袭原 spec §2 |
| gimbal 插件执行参数/日志订阅 | gimbal 侧就绪后接入(方案字段已预埋) |
| 团队共享方案 / 全局别名库(跨场景复用别名声明) | per-user 场景所有权语义下无需求;出现时评估独立于场景的声明面 |

## 8. 测试

- 引擎:per-step 查表命中 / 回落 base_url / 双缺失显式报错;单服务场景全量回归**逐字节不变**;旧「多服务降级取第一个 + warn」断言改为正确路由;run() 签名调用点与 docstring 示例同步
- 后端:RunScheme 去 envId 后窄端点往返;旧含 envId 方案静默降级;materialize 去 env 层等价;preview-plate overlay 无 env 路径;黄金等价测试随两层层级更新
- 前端:前缀派生单元(最后 `-` 切分/目录名含 `-`/后缀含 `-` 创建期拦截/违规键降级裸声明);步骤面板别名下拉过滤(派生归属)/内联创建拼串双写/跨服务黄警/未声明红;Config 卡归属派生展示;RunDialog 无环境版重写;并集绑定行(未声明行救燃);方案栏回填新签名
- 回归底线:plate 零改动;`vue-tsc --noEmit` 绿;现有套件只增不减全绿

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 未来契约同步功能覆盖 api.service | §1.6 契约禁令写入 spec + onAddEndpoint/适配处代码注释 |
| 别名键与模板 `${service.*}` 手写不一致(作者笔误) | 编辑期校验:${service.x} 引用的 x 不在声明面 → 悬空提示(tpl-refs 扩展,非阻塞;v1 可选增强,不进 §6 变更清单) |
| 旧方案含 envId / 旧 execution 含 env 键 | pydantic 静默忽略;RECIPE_LABELS 保留旧键标签可读 |
| 目录改名/下线致前缀失配 | 派生降级裸声明黄警(编辑期可见),运行零影响;目录侧变更本就经适配中心公告 |
| 引擎回归面 | 单服务回落路径 + 逐字节不变回归;构造点唯一已勘明 |

## 10. 实施顺序建议(计划期细化)

1. 引擎:三触点 + 测试(独立可先行,向后兼容无依赖)
2. 后端:schema 删改(env 退役;别名零 schema 增)+ materialize 去 env 层 + 端点调整
3. 前端:RunDialog 环境退役 + 并集绑定行;CaseComposer 装配调整
4. 前端:前缀派生工具 + 步骤面板别名配置 + Config 卡归属列
5. 清单收尾 + 全量回归
