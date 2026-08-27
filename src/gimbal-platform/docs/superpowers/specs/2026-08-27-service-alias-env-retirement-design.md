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
| D5 | 别名↔目录映射 | `orchestration.serviceMeta` sidecar:`{别名: {of: 目录服务名}}`,plate 契约零破坏(见 §1.3) |
| D6 | 校验风格 | 警告级不阻塞(撞目录名黄警、跨服务引用黄警),与现有「降级预填不报废」一致 |
| D7 | 引擎改造 | **保留 per-step base_url 三触点改造**(业务确认:场景内部存在多服务地址需求);查表只用 `scenario.config.services`,bootstrap 零触碰零适配 |
| D8 | 配置文件 | 引擎 `config/env/*.yml` 零修改;平台唯一删除的配置文件是 `backend/app/core/envs.yaml` |

## 1. 服务别名模型

### 1.1 三字段与存储(全部落 `composer_scenarios.payload` JSON 列,不加表不加列)

```
composer_scenarios.payload
├─ definition                      # plate 契约层(外发/导出)
│   ├─ steps[N].api.service        # ① 别名引用 — 现有字段,值为别名键(方案 A 直写)
│   └─ config.services             # ② 别名声明 {别名: URL} — 现有字段,零结构变化
└─ orchestration                   # 平台 sidecar 层(plate 零感知,永不外发)
    ├─ steps / resourceMeta / runSchemes   # 现有
    └─ serviceMeta                 # ③ 新增 {别名: {of: "目录服务名"}} — 仅编辑期 UI 标签
```

依据(勘明):
- plate `ApiSpec.service: str` 自由字符串,无注册名校验([api_spec.py](../../../../gimbal-plate/gimbal_plate/schema/endpoint/api_spec.py))
- 引擎 `_do_http_call` 语义就是「api.service 是查 config.services 的 key」([engine.py](../../../../gimbal/gimbal/statemachine/engine.py))
- 平台物化 `_referenced_services/_apply_services` 按引用键查绑定/声明([run_materialize.py](../backend/app/services/run_materialize.py))
- `${service.<key>}` 模板按声明 dict 解析([scenario_preprocessor.py](../../../../gimbal/gimbal/preprocessor/scenario_preprocessor.py))
- 数据库从不 SQL 查询 payload 内部([composer_scenario.py](../backend/app/models/composer_scenario.py) docstring)

**酸性测试**:`serviceMeta` 从 payload 整体删除,执行结果与导出产物一个字节不变 —— 它是标签不是配置源。

### 1.2 方案 A(直写)与否掉方案 B(sidecar 注入)的理由

方案 B(orchestration 持 stepIdx→别名映射,物化期改写 api.service)的深坑:headers/path/body 里的 `${service.x}` 模板是作者手写字符串,物化改写只动 api.service 字段、扫不动模板 → 模板引用域与 api.service 改写结果不同步。方案 A 作者期一处一致(api.service 与 `${service.*}` 同写别名),执行链零注入零改写、画布所见即所跑。

### 1.3 `serviceMeta` 的写入与生命周期

| 触点 | 行为 |
|---|---|
| 写入 | 步骤面板内联建别名 / Config 声明卡,写 draft 后随编辑器 `PUT /scenarios/{id}` 正常保存(同一 payload 原子落库) |
| 窄端点 | **不需要** —— 只在编辑器内写(runSchemes 有窄端点是因为 RunDialog 在编辑器外写) |
| 后端 schema | `Orchestration` 加 `serviceMeta: dict[str, ServiceMeta] = {}`(旧 payload 反序列化自动空 dict) |
| 编辑器保存透传 | 按 runSchemes 同款「两条分支都原样带回」处理(CaseComposer.vue orchestration 重建处) |
| 适配中心 | 自动幸存 —— adaptation_service 保存时 orchestration 从现有 payload 原样透传 |
| 一致性清理 | 删声明行时同步删 serviceMeta 同名键(同一 UI 动作,同一 JSON,无跨存储事务) |
| 导出 | **永不导出**(orchestration 整层不外发;导入丢 of 映射 = 已知非目标) |

`of` 不能放 definition 的原因:config.services 值是 plate 契约 `dict[str,str]` 不能破;definition 会被 plate /convert 校验并外发,平台私有标签污染产物;view_hints 是步骤级,声明是场景级会重复漂移。

### 1.4 编辑交互

**步骤面板(别名消费点)双显** —— 现只读事实区([CaseComposerCanvas.vue](../frontend/src/components/composer/CaseComposerCanvas.vue))改为:

```
接口事实(目录,只读)              运行引用(可编辑)
method  POST                     服务引用 [fin.tidb-qa1 ▾]
目录服务 fin.tidb-test               ├─ fin.tidb-test      ← 目录服务名(默认/现状)
path    /order                       ├─ fin.tidb-qa1       ← of == 本endpoint目录服务的别名
                                     ├─ fin.tidb-prod         (只列映射到本服务的)
                                     ├─ (其他声明键,置底灰显)  ← 选了黄警「跨服务引用」
                                     └─ + 为此服务新建别名…   ← 内联创建
                                   URL 预览(按声明解析,只读)
```

- 内联创建:填 URL → 一次动作同时写 `config.services` 声明 + serviceMeta.of → 当前步骤引用立即切换(即用户描述的「配置每个 endpoint 时为服务起别名」)
- 目录插入(`onAddEndpoint`)默认写 Plate 服务名(现状不变)

**Config 页声明卡(别名定义点)**:现有服务映射卡每行加 `of 目录服务` 列(目录名自动补全,可选填)。

### 1.5 校验语义(全表警告级,不阻塞)

| 情形 | 表现 |
|---|---|
| 引用别名,of = 本 endpoint 目录服务 | ✅ 主路径 |
| 引用别名,of ≠ 本服务(跨服务) | 🟡 黄警(网关/mock 场景可能故意跨) |
| 引用别名,无 of(裸声明) | 🟡 提示「未挂目录服务」,下拉置底 |
| 引用键完全未声明 | 🔴 红(RunDialog 并集行兜底可救燃;不救则引擎显式报错,现有语义) |
| 别名撞 plate 目录服务名 | 🟡 黄警「与目录服务重名,将按 config.services 声明解析」 |

### 1.6 冲突矩阵与契约禁令

**plate 定义拉取与 api.service 的关系(勘明:现状无覆盖链路)**:

| 触点 | 时机 | 覆盖别名? |
|---|---|---|
| `onAddEndpoint` | 目录插入写一次 | 初值=规范名,此后无写入 |
| `/full` 会话缓存 | 每次配置 endpoint 现拉 | ❌ 只读渲染数据(字段表单/断言/响应参考),不回写 api 对象 |
| 适配中心 apply_op | plate 目录变更适配 | ❌ 按 view_hints.endpoint_id 定位,STEP_OPS 只动字段层 |

**契约禁令(写入实施约束)**:任何 plate 拉取驱动的回写(现存适配 ops、未来契约同步)**不得触碰 `api.service`** —— `view_hints.endpoint_id` 是目录锚点,`api.service` 是用户引用键,两权分立。

**命名约定**:别名保持 `系统.名字` 前缀(config.services 分组展示与 checkSystemMismatch 的 `svc.split('.')[0]` 依赖前缀)。

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
| serviceMeta.of | **不导出** | **不导出** |
| runSchemes 本体 | 不导出 | 不导出(bindings 已物化进产物副本) |

按方案导出的物化 = **已实现**的 `materialize_run_copy`(spec §8 / commit 412bf95):方案 bindings 作为 overlay 参数显式传入,物化发生在产物副本,库里 definition 永不被改写。别名机制零新增合并 —— 绑定键就是别名键,现有「显式绑定 > 声明值」语义直接套用。导出产物与平台执行跑同一引擎,per-step 查表同时惠及两者。

## 6. 变更点清单(文件级)

| 区域 | 内容 |
|---|---|
| 前端 CaseComposerCanvas | 步骤面板双显 + 服务引用下拉(按 of 过滤)+ 内联建别名;目录插入不变 |
| 前端 CaseComposerConfig | 声明卡 of 列;删声明联动 serviceMeta |
| 前端 CaseComposer | referencedServices 改声明∪引用并集;orchestration 重建透传 serviceMeta;env 装配删除 |
| 前端 RunDialog | 环境 tiles 删除;confirm 签名去 env;绑定行取并集;方案回填/降级去 envId |
| 前端 api/types/stores | envs api/store 删;RunScheme/RunRequest/ExportOverlay 类型去 env;ServiceMeta 类型 |
| 后端 schemas | RunRequest.env/RunEnv/RunScheme.envId/ExportOverlay.envId 删;Orchestration.serviceMeta 增 |
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
| 导入反向映射(产物 config → 平台实体,含 of 重建) | feature-gaps #1 立项 |
| 数据集行展开导出 | 沿袭原 spec §2 |
| gimbal 插件执行参数/日志订阅 | gimbal 侧就绪后接入(方案字段已预埋) |
| 团队共享方案 / 全局别名库(跨场景复用别名声明) | per-user 场景所有权语义下无需求;出现时评估独立于场景的声明面 |

## 8. 测试

- 引擎:per-step 查表命中 / 回落 base_url / 双缺失显式报错;单服务场景全量回归**逐字节不变**;旧「多服务降级取第一个 + warn」断言改为正确路由;run() 签名调用点与 docstring 示例同步
- 后端:serviceMeta 透传(编辑器保存/适配中心);RunScheme 去 envId 后窄端点往返;旧含 envId 方案静默降级;materialize 去 env 层等价;preview-plate overlay 无 env 路径;黄金等价测试随两层层级更新
- 前端:步骤面板别名下拉过滤(of)/内联建别名双写/跨服务黄警/未声明红;Config 卡 of 列与清理联动;RunDialog 无环境版重写;并集绑定行(未声明行救燃);方案栏回填新签名
- 回归底线:plate 零改动;`vue-tsc --noEmit` 绿;现有套件只增不减全绿

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 未来契约同步功能覆盖 api.service | §1.6 契约禁令写入 spec + onAddEndpoint/适配处代码注释 |
| 别名键与模板 `${service.*}` 手写不一致(作者笔误) | 编辑期校验:${service.x} 引用的 x 不在声明面 → 悬空提示(tpl-refs 扩展,非阻塞;v1 可选增强,不进 §6 变更清单) |
| 旧方案含 envId / 旧 execution 含 env 键 | pydantic 静默忽略;RECIPE_LABELS 保留旧键标签可读 |
| serviceMeta 与声明面漂移(手改 JSON) | 声明卡打开时清理孤儿 of 键(编辑期自愈,非运行期) |
| 引擎回归面 | 单服务回落路径 + 逐字节不变回归;构造点唯一已勘明 |

## 10. 实施顺序建议(计划期细化)

1. 引擎:三触点 + 测试(独立可先行,向后兼容无依赖)
2. 后端:schema 增删(serviceMeta/env 退役)+ materialize 去 env 层 + 端点调整
3. 前端:RunDialog 环境退役 + 并集绑定行;CaseComposer 装配调整
4. 前端:步骤面板别名配置 + Config 卡 of 列 + serviceMeta 透传
5. 清单收尾 + 全量回归
