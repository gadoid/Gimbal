# 适配中心前端(P5)设计 spec

> 上位 spec:`2026-08-21-asset-domain-complete-design.md`(§5.5 流程、§5.4 op 契约、
> §9 C10/C12/C13 为权威)。本文档是 P5(前端适配闭环)的实现设计,冲突时以上位 spec 为准。

**日期**:2026-08-22
**状态**:已实现(2026-08-22;实施计划见
`../plans/2026-08-22-adaptation-center-frontend.md`;errata:§4 首发误写
src/pages/,视图实际为 src/views/,已于当日修正;§5.2 待适配卡片的
「变更徽标(字段增/删/值域)」随实现裁剪 —— CatalogDiffReport 仅含
endpoint 级 pending,无字段数据,字段级信息由影响抽屉承担)
**前置**:P1-P4 已完成(后端 185 tests 绿;`routers/adaptations.py` 八端点 admin-only)

## 1. 目标与范围

把 §5.5 的方案2 流程做成前端闭环:

```
变更徽章(admin)→ 适配中心总览(待适配清单/未索引警示/批次表)
  → 影响抽屉(按字段分组)→ 开批次 → 批次工作台
  → op 预览 → 逐条应用/跳过/人工构造(8 类)→ 整批回滚
```

范围:**前端两页面 + API 客户端 + store + 导航/路由** + **后端 4 个小端点增量**(见 §7)。
不含:方案1 插件自动应用(P6)、通知系统(明确不做,C13)、影响清单独立深链页(已裁:抽屉)。

## 2. 已裁定决策(2026-08-22,与用户确认)

| # | 决策 | 内容 |
|---|---|---|
| D1 | 人工 op 构造 | **全量 8 类**(renameVar/renameField/rebindField/renameDatasetColumn/mapDatasetValues/addField/removeField/mapValue 补值 + remove+add 合并为 renameField 交互) |
| D2 | owner 只读视图(C13) | **融入适配中心**:单页双形态,member 自动 `scope=mine`,不另立页面 |
| D3 | 徽章时机 | **admin 登录/刷新后静默 `POST /catalog/diff` 一次**(幂等,冷启动落基线属预期副作用),结果进 store 常显;打开适配中心强制刷新;member 零调用 |
| D4 | 页面组织 | **两路由 + 抽屉**:`/adaptations`(总览,影响清单右侧抽屉)+ `/adaptations/batches/:id`(工作台) |

## 3. 双形态模型

| 面 | admin | member(owner 视图) |
|---|---|---|
| 导航「适配中心」 | 可见 + 待适配徽章 | 可见,无徽章 |
| 未索引警示条 | 可见 | 隐藏 |
| 待适配清单 + 影响抽屉 | 可见,可开批次 | 隐藏 |
| 批次表 | 全量(`GET /batches`) | `GET /batches?scope=mine`,表头提示"仅显示触碰我场景的批次" |
| 批次工作台 | 全部操作(应用/跳过/构造/回滚) | 只读:op 列表与预览可见,操作按钮全部隐藏 |
| 徽章流 | 登录后静默 diff | 无任何 adaptations 写调用 |

实现:路由守卫只做 `requiresAuth`(两路由);admin 门槛在后端(403)与页面内
`auth.isAdmin` 条件渲染双保险(沿 `/admin/users` 模式)。

## 4. 前端结构

```
src/api/adaptations.ts               typed 客户端(契约照 §7 与后端 schemas camelCase)
src/stores/adaptations.ts            pinia:pendingCount + diffReport 缓存 + refresh()
src/views/AdaptationCenter.vue       总览页(视图沿既有 src/views/ 目录,非 pages)
src/views/AdaptationBatchDetail.vue  工作台
src/components/adaptations/
  ImpactDrawer.vue                   影响清单抽屉(按字段分组,直填/模板/数据集列标注)
  OpPreview.vue                      单条 op 预览(§6.2)
  OpConstructDialog.vue              8 类构造表单(§6.3)
  UnindexedAlert.vue                 未索引警示条 + 展开清单
```

- TopNav:`entries` 增 `{ path: '/adaptations', label: '适配中心', icon }, …`(非 adminOnly);
  徽章 = `el-badge :value="adaptations.pendingCount"`(仅 `auth.isAdmin` 时渲染数字)。
- router:`/adaptations` 与 `/adaptations/batches/:id`,`meta: { requiresAuth: true }`。

## 5. 总览页(`/adaptations`)

自上而下三块:

1. **未索引警示条**(admin,`UnindexedAlert`):`el-alert` warning,"N 个步骤缺 endpoint_id,
   未纳入适配保护";点开展开清单(`scenarioId · step N`),链接跳 `/scenarios/:id/detail`。
2. **待适配清单**(admin):diff 报告渲染为卡片,每 endpoint 一张:
   - `endpointId` + `fromVersion → toVersion`;
   - 变更徽标:字段增/删(形状 diff)、值域(mapValue 骨架);
   - **C12 异常卡**(updated_at 动了但 version 未动)用警告色,且**不提供开批次按钮**
     (spec:异常不自动适配、不建批次);
   - 点卡片 → `ImpactDrawer`:`GET /impact?endpointId=&field=` 按字段分组渲染
     `{scenarioId · step N · 直填/模板 · viaVar? → datasetId.datasetColumn?}` 条目
     (spec §5.2 形状),抽屉底部 [开批次] → `POST /batches` → 跳 `/adaptations/batches/:id`。
3. **批次表**:batchId / endpoint / from→to / 状态(open·applying·completed·rolled_back)/
   opCounts 徽标组(pending·applied·conflict·skipped)/ created_at / [详情]。

## 6. 批次工作台(`/adaptations/batches/:id`)

### 6.1 头部

endpoint、from→to、状态、opCounts 汇总、[整批回滚](admin 且 open/applying)。
回滚 = `ElMessageBox` 二次确认 → `POST /batches/{id}/rollback` → 结果面板:
restored 清单 + conflicts 清单(逐条 note:"该实体被批次外编辑/恢复写入被拒,已跳过")。

### 6.2 ops 列表(按 id 升序,每行 = OpPreview + 状态驱动的操作组)

预览数据源(**零后端改动**):

| op 类型 | 预览内容 |
|---|---|
| STEP_OPS(renameField/addField/removeField/rebindField/mapValue) | `GET /scenarios/{id}`(按 scenarioId 缓存)取 `steps[step]` 的 body/headers/query 片段;from/to/field/value/map 高亮标注 |
| renameVar | `${var.from} → ${var.to}` + 场景 payload 内 `${var.from}` 引用计数(前端统计) |
| renameDatasetColumn / mapDatasetValues | 数据集名 + 列 from→to / map 表(首行示例) |

操作组按 op.status:

- `pending`:[应用](`POST /ops/{id}/apply`)[跳过](`POST /ops/{id}/skip`)[编辑](`PATCH /ops/{id}`,仅 mapValue 补值与参数修正)
- `applied`:绿色徽标 + appliedAt
- `conflict`/`skipped`:灰色 + note tooltip

member:全部只读(仅预览 + 状态)。

### 6.3 构造 op(admin,[构造] 对话框,`POST /batches/{id}/ops`)

8 类表单,提交 payload 按 spec §5.4 契约(剥 "op" 键,类型在 op_type):

| 类型 | 表单要素 |
|---|---|
| renameVar | from/to 下拉(选项 = 场景 vars 调色板) |
| renameField | step 选择 + from/to 字段名 |
| rebindField | step + field + 目标 var(调色板下拉) |
| renameDatasetColumn | 数据集下拉(批次快照涉及的场景)+ from/to 列名 |
| mapDatasetValues | 数据集下拉 + column + map 键值编辑器 |
| addField / removeField | step + field(+value) |
| mapValue | step + field + map 键值编辑器(键手输;候选提示取场景该字段当前值/数据集列现值——草案 payload 不含值域,值域仅存在于后端 diff 计算瞬间) |

**合并交互**(§5.4:remove+add 草案 → renameField):ops 列表勾选**同一 step** 的一删一增
两条 pending 草案 → [合并为 renameField] → 预填 from=被删字段、to=新增字段 → 构造成功后
自动 `skip` 原两条(前端串联两次调用)。

### 6.4 快照清单

折叠面板:场景/数据集 before 存档条目计数(回滚安全网可见化);member 同样可见(知情)。

## 7. 后端增量(4 端点,挂现有 adaptations 路由)

| 端点 | 权限 | 语义 | 错误 |
|---|---|---|---|
| `GET /api/adaptations/unindexed-steps` | admin | 包 `endpoint_ref_index.unindexed_steps()`;响应 `[{scenarioId, stepIndex, reason}]`(camelCase,沿 `_CAMEL` 模式) | — |
| `GET /api/adaptations/batches?scope=mine` | **放宽**:普通用户可调 | `scope=mine` → 批次集合 = ops/snapshots 涉及的场景中存在 `owner_id == 当前用户` 的批次(去重,新→旧);无 scope 或 `scope=all` → 仍 admin-only(member → 403 admin_only) | 403 admin_only |
| `POST /api/adaptations/ops/{id}/skip` | admin | pending → status="skipped", note="skipped by operator";幂等(skipped 再调原样返回) | 404 op_not_found;400 op_not_applicable(applied/conflict 不可跳) |
| `PATCH /api/adaptations/ops/{id}` | admin | body = payload 局部更新;仅 pending 可改(否则 400 op_not_applicable);合并后整包替换 payload(仍剥 "op" 键) | 404;400 |

owner 过滤实现注记:`owner_id` 是归属唯一权威(`ComposerScenario.owner_id`,int user.id);
`owner` 字符串列仅展示快照,过滤不得使用。批次的"涉及场景"取
`AdaptationOp.scenario_id ∪ AdaptationSnapshot(entity_type=scenario).entity_id`。

## 8. 错误处理与空态

- 401 → 既有 http 拦截跳登录;
- 403 admin_only → 页面内"仅管理员"占位(member 误入操作面);
- plate 502(PlateUnavailableError 映射)→ alert"目录服务不可用,稍后重试",保留旧数据;
- `no_pending_change` → 待适配区空态文案"目录无待适配变更";
- `no_baseline` → 首次 diff 即建基线(后端已处理),前端按空态渲染;
- 批次详情 404 → "批次不存在或已清理" + 返回列表按钮。

## 9. 测试策略

- **store**:admin 登录 → 静默 diff 调用一次 → pendingCount;member → 零 adaptations 调用;
  适配中心打开 → 强制刷新。
- **总览页**:双形态渲染断言(member 无待适配/警示、批次表走 scope=mine);C12 异常卡无开批次
  按钮;抽屉分组条目渲染;未索引警示计数与展开。
- **工作台**:ops 按状态渲染对应操作组;STEP_OPS 预览片段与高亮;构造表单校验 + 提交 payload
  形状(8 类各一);合并交互(构造 + 两次 skip 串联);回滚确认 + restored/conflicts 面板;
  member 只读断言。
- **后端**:4 新端点 pytest(沿 P3+P4 conftest 基建;unindexed 2 / scope=mine 3~4 /
  skip 3 / patch 3,预计 +11~12)。

## 10. 验证标准(P5 完成定义)

1. 手动全流程走通:member 场景 + 数据集 → plate 改目录 → admin 徽章出现 → 总览见待适配 →
   影响抽屉 → 开批次 → 预览/应用/构造(mapValue 补值 + renameVar)/合并 renameField →
   completed 推戳 → 回滚一次成功;
2. member 视角:批次表只见自己的,工作台只读;
3. 未索引场景挂警示并出现在清单;
4. 后端 pytest 全绿(185 + 新增);前端 vitest 全绿(113 + 新增);`npm run build` 干净。

## 11. 明确不做(本期)

- 影响清单独立路由深链(D4 裁为抽屉);
- owner 确认流程(C13:与单管理员 MVP 冲突);
- 通知/轮询(D3:拉取时计算);
- paste 导入数据集行、§4.3 遗留 lint 项(URL 漂移等)——非本闭环路径,随后续前端迭代。
