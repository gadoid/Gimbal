# RunDialog 重构 + 运行方案(overlay)+ 执行可观测性 设计文档

- 日期:2026-08-27
- 状态:已实现(15 任务 SHIP IT);**§13 设计回归待讨论**
- 分支:strbody_avaliable
- 前置:常量池(T1-T10 已合并)、run-launch-subprocess(2026-08-24)、认证改造(2026-08-25)

## 0. 问题陈述

1. **RunDialog 信息架构失序**:四大块平铺(环境/数据集/认证/高级),混杂 V1 残留语义(提单号前缀、凭证合并策略、硬编码预设),缺少实用运行时配置(用户与服务绑定、插件、日志订阅)。
2. **执行不可观测**:只有执行记录聚合计数器;行级状态只在 JSONL 按天文件(运维直读,无 API);步骤级明细落盘 result.json/reports 但未暴露;引擎 stderr 日志被 `communicate()` 整体丢弃。
3. **配置物化割裂**:执行链有注入套件(run_dispatcher 四函数),导出链零注入(plate convert 原样);「同一场景在不同环境/身份下物化」没有统一模型,导入(feature-gaps #1)将来还要第三遍。

## 1. 目标

- RunDialog 重构:信息架构分层(每次必看的主面板 + 未配置折叠区),剥离失效语义,新增实用配置
- 运行方案(RunOverlay)模型:场景级 sidecar 存储,统一「运行/导出(本次纳入)/导入(将来)」三消费点的配置覆盖层
- 执行可观测性:行级实时进度(轮询)+ 引擎日志流式落盘可查
- 注入归一化:`materialize_run_copy` 单函数,执行与导出两消费方,黄金等价测试锁住不漂移

## 2. 非目标(带触发器)

| 项 | 触发器/时点 |
|---|---|
| 引擎 per-step base_url(`_do_http_call` 按 `api.service` 查表) | 「同场景同 service 不同 URL」需求出现时立项;三触点已勘明:preprocessor 暴露 merged dict / StepRunner 传参 / engine 查表回落 |
| SSE/WebSocket 实时推送 | 行级轮询(总闸 200 行)不满足体验时 |
| 导入反向映射(产物 config → 平台实体) | feature-gaps #1 立项时复用 overlay 模型 |
| 数据集行展开导出 | 导出是场景级产物;行级需求出现时扩展 |
| gimbal 插件执行参数、细粒度日志订阅 | gimbal 侧能力就绪后接入(方案字段已预埋) |
| 团队共享方案 | per-user 场景所有权语义下无需求 |
| PG 新表 | 行状态走内存 registry + JSONL 回放;存储设计等 PG 迁移路线 |

## 3. 方案模型(RunOverlay)

### 3.1 数据结构

场景 payload 的 orchestration sidecar 层(plate 零感知,不外发):

```yaml
orchestration:
  steps: [...]              # 现有:展示名/启用开关
  resourceMeta: {...}       # 现有
  runSchemes:               # 新增:有序方案列表
    - name: "冒烟-qa1"       # 必填,场景内唯一
      envId: "dev"
      dataSetIds: ["ds-xxx"] # 空 = 基线
      serviceBindings:       # service → { authAlias, url? }
        fin.audit: { authAlias: "qa1", url: "https://x" }
      plugins: null          # 预埋键,v1 恒 null
      logSub: null           # 预埋键,v1 恒 null
```

- **不含 base_config**(nRuns/parallel/stepTo)— 每次执行的现场决策,不持久化,默认 `1/1/全量`
- **「上次运行」不入库**:RunDialog 打开时 `GET /executions?scenario_id=&limit=1` 从最新 `Execution.config_json` 派生,**只取 overlay 字段**(envId/dataSetIds/serviceBindings);base_config 不回填(每次现场决策)
- 凭证策略:明文物化(内网部署语境,账户为被测系统测试账户 — 用户决策 2026-08-27)

### 3.2 存取

新窄端点 `PUT /api/scenarios/{id}/run-schemes`(body = RunScheme 列表):
- 只读写 orchestration.runSchemes 一个键,不整 payload 替换(避免与编辑中草稿的 PUT 并发覆盖)
- name 场景内唯一校验(重名 409)
- 校验:envId 存在性、datasetId 归属、authAlias 为 owner 凭证池 ∪ 场景内置 users 别名(警告级,不拒 — 降级预填原则)

## 4. RunDialog 信息架构

```
┌ 方案栏: [临时手填 ▾] [存为方案]              ← 下拉:临时手填/上次运行/已存方案
├ 主面板(每次必看):
│   执行环境 tiles(保留)
│   数据集多选 + 基线(保留)
│   基础设置: 执行次数×并发 · 停止于步骤        ← 自"高级选项"提升
├ 折叠区(未配置 = 折叠 + 摘要行展示当前值):
│   ▸ 用户与服务:场景引用的每个 service 一行 [用户▾][URL____]
│   ▸ 插件列表(预埋:只读展示全局配置,"待 gimbal 侧支持")
│   ▸ 日志订阅(预埋:同上)
└ footer: 汇总 chips + 发起运行(保留)
```

- **剥离**:提单号前缀、凭证合并策略(四选一)、快捷预设(UI + RunRequest + 后端注入一并退役)
- **执行认证多选 chips 退役**,由「用户与服务」区取代(注入清单语义见 §5)
- **降级预填**:方案引用的 dataset/alias/env 已删 → 该项标红提示,不整单报废(常量池管理页降级模式)
- confirm 签名:`confirm(envId, dataSetIds, { stepTo?, nRuns?, parallel?, serviceBindings? })`

## 5. 认证注入语义

```
注入清单 = 场景 steps 扫描 ${auth.<alias>.*} 引用(后端算,平台侧 Python 版模板扫描)
         ∪ serviceBindings 各行 authAlias(绑定即注入)
```

- 扫描移到后端 dispatch 时(递归扫 headers/path/body/strategy 的字符串值;语义对齐前端 [tpl-refs.ts](../../frontend/src/utils/tpl-refs.ts))
- `RunRequest.auths` / `inject_credentials` 退役 — 单一事实源 = 场景内容 + 绑定
- 解析不到的 alias:告警继续(内置 users 已带的明文兜底可跑,`_resolve_exec_auths` 现语义)
- owner 凭证池「额外注入未引用 alias」的能力删除(注入未引用的 alias 无运行语义)
- 绑定 url 物化优先级:**显式绑定 > 场景 authored > env.baseUrl 补缺**

## 6. RunRequest 模型

```python
RunRequest:
  scenario_id, env, data_set_ids          # 不变
  service_bindings: dict[str, ServiceBinding]   # 新 {authAlias?, url?}
  step_to / n_runs / parallel             # 不变
  # 退役: auths, inject_credentials, prefix, merge_policy
```

- 退役字段从 schema 删除;FastAPI 对多余载荷静默忽略,旧客户端不 422 仅失效
- `plugins`/`logSub` **不进 RunRequest** — 只存在方案(orchestration)侧,等 gimbal 就绪再接执行链
- `config_json` 留痕键:删 `prefix`/`mergePolicy`/`injectCredentials`/`exec_auth_alias`;增 `serviceBindings`/`injectedAuths`(实际注入清单)— 「上次运行」派生依赖此对齐;历史记录旧键由前端 RECIPE_LABELS 保留标签可读

## 7. 注入归一化 — materialize_run_copy

### 7.1 现状盘点(一套实现 + 一个裸路径)

| 层 | 实现 |
|---|---|
| 编排期(编著) | config.vars/services/users 由 composer UI 编辑,存库 |
| 执行期 PRE-convert | `_compose_scenario`:数据行 → config.vars(行覆盖,过 plate 校验) |
| 执行期 POST-convert | `_inject_exec_users` / `_inject_prefix_vars` / `_inject_services`(run 副本,明文不过 plate) |
| 导出期 | **零注入**(preview-plate convert 原样) |
| 引擎期 | preprocess 模板物化(引擎内,非平台) |

PRE/POST convert 是刻意安全缝:明文凭证不过 plate。

### 7.2 重构

- POST-convert 注入器(**退役 prefix 后**剩 users/services)+ 绑定优先级 → 抽成 `materialize_run_copy(converted, *, env_base_url, bindings, resolved_auths, built_in_users)` 纯函数,保持 POST-convert 位点
- `_compose_scenario`(数据行)保持 dispatch 专属(导出无行语义)
- 消费方:dispatch(_fanout 逐行)与导出(preview-plate 带 overlay)— **同一函数**

### 7.3 元素 × 路径注入矩阵 + 黄金等价验收

| 元素 | 执行 case.json | 导出产物 |
|---|---|---|
| envId → baseUrl 补缺 | ✓ 已有 | ✓ materialize |
| bindings.url → services[svc] | ✓ 优先级升级 | ✓ 同函数 |
| bindings.authAlias → users | ✓ 已有 | ✓ 同函数 |
| 模板扫描 alias → 注入清单 | ✓ 新 | ✓ 同清单 |
| 场景内置 users | definition 自带 | convert 产物自带 |
| dataSetIds → vars 行覆盖 | ✓ 已有 | **v1 忽略**(场景级产物,§2 非目标) |
| plugins/logSub | no-op 预埋 | no-op 预埋 |

**黄金等价测试**:同一 overlay 下,导出产物 ≡ 基线单行执行 case.json(模掉执行专属字段:行 vars 合入、halt/stepTo)— 逐字段相等断言,锁死两路不漂移。

## 8. 导出 overlay(本轮纳入)

- `POST /api/scenarios/preview-plate` body 增**可选** `overlay: {envId?, serviceBindings?}`:
  - 传入:convert 后调 `materialize_run_copy` 物化(明文)再返回
  - 不传:现状行为(convert 原样),向后兼容
- 前端两入口加「按方案导出」:[ScenarioExportMenu.vue](../../frontend/src/components/ScenarioExportMenu.vue)(顶栏)、[Scenarios.vue exportRow](../../frontend/src/views/Scenarios.vue)(场景库行级)— 选方案 → preview-plate 带 overlay → 下载
- 产物格式不变(plate gimbal consumer dict)

## 9. 实时跟踪 + 日志落盘

### 9.1 行状态

- **内存 registry**:`dict[execution_id, list[RowState]]`;RowState `{seq, datasetId, rowIndex, rep, status, startedAt?, finishedAt?, caseDir}`;写点在 `_row` 各状态变迁;总闸 200 行无压力;执行生命周期与进程一致(restart = reconcile 僵尸,行状态随 JSONL 留存)
- **新端点** `GET /api/executions/{id}/rows`:活跃执行读 registry;历史/已重启执行读 JSONL 按 executionId 回放(dispatched+final 两行/row,后者覆盖前者)— 与 registry 共享 RowState 形状
- **case 工件白名单端点** `GET /api/executions/{id}/case-artifact?case=<stem>&file=engine-log|result` — 读 per-case 的 engine.log(引擎日志)与 result.json(步骤级明细);白名单固定这两项,**case.json 不暴露**(含明文凭证,无前端消费场景)
- **前端** [Executions.vue](../../frontend/src/views/Executions.vue):行级表格挂进现有 1s 轮询(stores/executions.ts);行展开经 case-artifact 端点看步骤明细与引擎日志;「明细只能服务端检索 JSONL」提示删除

### 9.2 引擎日志流式落盘

- [gimbal_launcher.launch](../../backend/app/services/gimbal_launcher.py) 改:`communicate()` → stdout 整体收 + stderr 逐行流式读,边读边写 `case_dir/engine.log`(新参数 `engine_log_path`);超时 kill/spawn 失败保留已读部分
- 引擎日志经 §9.1 case-artifact 端点读取
- stdout JSON 解析语义不变

## 10. 变更点与清理清单(文件级)

### 变更

| 区域 | 内容 |
|---|---|
| schemas/scenario_composer.py | RunRequest 字段增删(§6);Orchestration + RunScheme/ServiceBinding 模型;RunSchemesIn |
| run_dispatcher.py | 模板扫描;注入清单来源改;materialize_run_copy 抽取;绑定优先级;行状态 registry;config_json 键 |
| gimbal_launcher.py | 流式 stderr + engine_log_path |
| routers/scenarios.py | PUT run-schemes;preview-plate overlay |
| routers/executions.py | GET rows;GET case-artifact(engine.log/result.json 白名单);list 加 scenario_id 过滤 |
| 前端 RunDialog | §4 全部 |
| CaseComposer.vue | onRunConfirm 签名;方案列表拉取 |
| api/scenario-composer.ts / api/executions.ts / types | 接口同步;MergePolicy 删;rows/engine-log 调用 |
| Executions.vue + stores/executions.ts | 行级表格 + 日志查看;RECIPE_LABELS |
| ScenarioExportMenu.vue / Scenarios.vue | 按方案导出 |

### 清理/弃用

| 项 | 位置 | 处置 |
|---|---|---|
| `_inject_prefix_vars` | run_dispatcher.py | 删 |
| `_inject_exec_users` merge_policy/override 分支 | run_dispatcher.py | 删(固定 merge 语义) |
| append 冲突预检 | run_dispatcher.py dispatch_run | 删 |
| RunRequest.{auths,inject_credentials,prefix,merge_policy} | schemas | 删 |
| 前端 PRESETS/POLICIES/policyHint/prefix/authOptions/append 预检 | RunDialog.vue | 删 |
| `MergePolicy` 类型 | api/executions.ts + 双 import | 删 |
| Executions.vue JSONL 运维提示 | Executions.vue | 删(API 化) |

### 测试

- 后端改:test_run_m1_capabilities(prefix/override/append/default-merge 删,merge 改绑定语义)、test_scenario_visibility_and_copy(inject_credentials_false 删)、test_scenario_composer_plate_integration(auths 输入源改)
- 后端新增:模板扫描、绑定注入优先级、registry+JSONL 回放、流式 stderr(超时保留)、run-schemes 端点、导出 overlay、**黄金等价**、config_json 新键
- 前端:RunDialog.auths.test 重写(用户与服务区)、其余四测签名小调;新增方案栏/降级/存为方案/行级表格测试
- 回归底线:plate 与引擎(src/gimbal、src/gimbal-plate)零改动;现有套件只增不减全绿;`vue-tsc --noEmit` 绿

## 11. 风险与对策

| 风险 | 对策 |
|---|---|
| 两路物化漂移 | materialize 单函数 + 黄金等价测试(§7.3) |
| 模板扫描漏扫 body 嵌套 | 递归字符串值扫描 + 与前端 tpl-refs 语义对齐的测试;漏扫后果 = 运行期悬空可见(非静默),可接受有兜底 |
| config_json 键变化破坏读侧 | RECIPE_LABELS 保留旧键标签;「上次运行」只认新键(首跑空,可接受) |
| JSONL 回放形状与 registry 漂移 | 共享 RowState 模型,回放测试 |
| PUT run-schemes 与草稿编辑并发 | **runSchemes 键归窄端点专管**:`scenario_store.update` 落库时从现有 payload 透传保留 runSchemes(编辑器不管理该键),composer 保存永不覆盖方案 |
| 旧客户端发退役字段 | FastAPI 静默忽略,不 422 仅失效 |

## 12. 实施顺序建议(计划期细化)

1. 后端:materialize 抽取 + RunRequest 改造 + 模板扫描(执行链等价重构,先绿)
2. 后端:run-schemes 端点 + preview-plate overlay + 黄金等价测试
3. 后端:行状态 registry + rows/engine-log 端点 + launcher 流式
4. 前端:RunDialog 重构 + 方案栏 + 用户与服务区
5. 前端:Executions 行级表格 + 日志查看 + 按方案导出
6. 清理清单收尾 + 全量回归

## 13. 设计回归与开放问题(2026-08-27 验收反馈,待讨论)

> **2026-08-27 更新:①③已重新讨论并拍板,修订设计见 [2026-08-27-service-alias-env-retirement-design.md](2026-08-27-service-alias-env-retirement-design.md)(含本节全部待拍板点的结论与引擎 per-step base_url 非目标转正)。本节保留作为决策过程记录。**

实现完成后用户验收提出四项反馈。②为实现 bug(已修复);**①③为 brainstorm→spec 阶段丢失的用户决策,本节如实记录差异与待拍板点,等用户回来重新讨论后再改设计与实现**;④经查为②的级联失效,②修复后入口即显。

### ① 执行环境选择 — 用户决策:退役;spec 现状:保留

- spec §4 保留环境 tiles,env.baseUrl 为绑定 URL 优先级第三级(§5:显式绑定 > 场景 authored > env 补缺)
- 用户意图(2026-08-27):RunDialog 不再展示环境选择;执行直接使用「用户与服务绑定 + 默认服务配置」
- 待拍板:
  - 环境退役后,服务默认 URL 的来源(`config.services` 每服务自带默认 baseUrl?)
  - `data/envs.yaml` / RunEnv 数据层是否一并退役,还是仅 RunDialog UI 退场
  - `RunScheme.envId` 字段去留(方案模型三字段之一;退役则「上次运行」派生与按方案导出随之调整)

### ③ 用户与服务区 — 服务检索源与 spec 不符 + 服务别名未实现

- spec §4 写「场景**引用的**每个 service 一行」→ 实现 = `steps[].api.service` 去重(编排关联面)
- 用户决策(2026-08-27):检索源应为 `config.services`(场景服务声明面,服务名 → baseUrl),而非编排中接口的关联服务
- 服务别名机制(用户原始决策)未进 spec、未实现 — 具体形态待用户重述后补设计
- 待拍板:
  - 绑定行范围:`config.services` 声明集,还是声明 ∪ steps 引用的并集(steps 引用了未声明服务时需有绑定落点,否则 URL 补缺/绑定无受体)
  - 别名形态:同一服务多个命名实例(别名 → URL + 用户)?step 引用别名还是真名?执行/导出物化时别名如何解析回 `config.services`?
  - 与①联动:若环境退役且服务自带默认 URL,绑定行「覆盖 URL」与 authored URL 的优先级链需要重排

### ④ 方案覆盖与按方案导出 — 已实现,入口曾被②掩盖(已随②修复显现)

- 选方案回填 env/数据集/绑定:RunDialog 方案栏已实现(watch selectedScheme 整体替换)
- 按方案导出:ScenarioExportMenu 按已存方案动态渲染「按方案导出 · {方案名}」条目 + 场景库行级入口;「导出 JSON/YAML」= 默认配置(不带 overlay)。方案列表恒空(②存不上方案)时入口不渲染 — 曾表现为"功能不存在"
- 若需更显眼入口(如 CaseComposer 页内导出对话框选方案),随①③讨论一并定

### ②(已修)存为方案 404 — 根因与修复

新建场景首次保存后路由停留 `/scenarios/new`,而 onSaveScheme 用路由参数作场景 id → `PUT /api/scenarios/new/run-schemes` 404。修复:onSaveScheme / openRunDialog(上次运行查询同根)改用持久化 `scenario.meta.scenarioId`,未保存场景提示「请先保存场景,再存为方案」。
