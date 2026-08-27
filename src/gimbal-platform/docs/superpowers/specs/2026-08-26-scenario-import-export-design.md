# Scenario 导入 + 按数据行导出

- 日期:2026-08-26
- 状态:设计定稿(已与用户逐节确认)
- 分支:`strbody_avaliable`
- 对应欠账:`docs/feature-gaps.md` 第 1 项"上传用例"(本设计落地后更新该项)

## 背景

- 平台 V3 只有导出(`ScenarioExportMenu` 全量导出 / 列表行级导出),没有导入;feature-gaps.md 将"上传用例"列为待实现第 1 项。
- 数据集(挂场景的参数化行表,运行期经 RunDispatcher 稀疏覆盖 `config.vars`)不随导出文件走;导出产物是"基线模板",不含任何数据集数据。
- 用户需要:① gimbal 可执行文件 → 平台场景(导入);② 导出时可选数据集行,行值烤入 `config.vars`(导出具体用例而非基线模板)。

## 目标

1. **导入**:`POST /api/scenarios/import` 接受 gimbal 可执行 JSON/YAML → 重建为平台场景(含视图字段回填 + orchestration 重建),新 scenarioId、owner=当前用户。
2. **导出(选数据行)**:导出对话框按"数据集分组表格"多选行,每行 → 一个完整 gimbal 可执行文件,行值稀疏覆盖 `config.vars`;不选 = 基线导出(现行为)。

## 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 导出产物形态 | **注入后的完整 scenario.json**,不是纯数据集;N 行 → N 个文件,文件间仅 `config.vars` 不同;文件内 `scenarioId` 保持原值(与运行时 fan-out 一致),行身份只在文件名 |
| 数据集随文件走的方式 | **烤进 config.vars**(稀疏覆盖),非独立 section/包装格式;导入不重建数据集,烤入值成为导入场景的 vars 基线 |
| 导出核心不变量 | **导出文件 ≡ RunDispatcher 运行该行时下发给 gimbal 的场景**;vars 合并 + 类型矫正必须提取 dispatcher 现有逻辑为共享函数,禁止平行实现 |
| 导入校验粒度 | **整场景一次** plate 校验(`Scenario.model_validate`,经 plate /convert),不逐 step 查询 |
| kind 改写 | **零改写**:落库 definition 的 kind 本就是 `"scenario"`(CaseComposer.vue:265 / types/plate.ts:332),与导出文件一致 |
| scenarioId 策略 | 导入总是生成新 ID(owner=当前用户,时间戳服务端重盖章);"备份恢复原场景"语义不做 |
| 视图字段回填 | 导入时按 `(method, path)` 匹配 plate 语法端点集,命中则回填 `view_hints.endpoint_id`;`fields_meta`(前端已废弃为数据源)与 `view_note`(装饰性)不回填;未命中保持缺失,draft-lint"未绑定端点"提示兜底,不阻塞 |
| 行选择 UI | **分组表格渲染 + 扁平选择状态**:按数据集分组的表格,每行 checkbox,组头"全选本组";状态为 `{datasetId, rowIndex, values}[]`,不用树控件 |
| 行值传递 | 确认请求随带选中行的**值**(对话框打开时 GET 的全量 rows 快照),用户看到什么导出什么,规避确认瞬间行被编辑的行号漂移;后端仍复跑调色板校验拦截手工构造请求 |

## 总体数据流

```
导出(每选中行一次):
  草稿 payload.definition ──deepcopy──▶ fill_plate_defaults
      ──▶ merge_row_vars(config.vars, 行值)   ← 共享函数(自 run_dispatcher._compose_scenario 提取,
      ──▶ plate /convert(consumer=gimbal)        含 _coerce_row_value 类型矫正)
      ──▶ 前端逐文件 downloadFile
  文件名: {scenarioId}-{数据集名}-r{行号1基}.json / 基线: {scenarioId}-{时间戳}.json

导入:
  上传文件(JSON/YAML 嗅探) ──▶ 解析 dict
      ──▶ fill_plate_defaults + plate /convert   ← 一次整场景校验,失败 422 透传 errors[]
      ──▶ view_hints.endpoint_id 回填            ← (method, path) × plate 语法端点集,一次性
      ──▶ orchestration 重建                     ← steps.map → {enabled: true, name: description 截断};resourceMeta = {}
      ──▶ scenario_store.create                  ← 新 scenarioId,owner 强制,时间戳服务端
```

## 后端:共享 vars 合并函数

- 从 `run_dispatcher._compose_scenario` 提取 vars 合并为独立纯函数(建议 `services/var_merge.py`,名称实现时定):
  - `merge_row_vars(config_vars: dict, row: dict) -> dict`:`dict(config_vars)` 起底 → 行键覆盖;沿用 `_coerce_row_value` 语义(按基线 var 类型矫正行值,如 `"30"`→`30`);缺键 = 继承基线,`""` = 显式空覆盖。
- dispatcher 与导出端点共同引用;提取后 dispatcher 行为零变化(重构由既有 dispatcher 测试守护)。

## 后端:导出端点

`POST /api/scenarios/{scenarioId}/export`

- 请求体:`{ rows: [{datasetId, rowIndex, values, datasetName}], format: "json" | "yaml" }`;`rows: []` = 基线导出(1 个文件)。
- 处理(**两阶段、all-or-nothing**):
  1. 加载该场景存储 draft,取 `payload.definition`;
  2. 阶段一(校验):对全部行复跑 `_validate_rows` 调色板校验(行键 ⊆ `config.vars` 标量键),任一行违规即整请求 422,不进入阶段二;
  3. 阶段二(组合):每行 deepcopy + `fill_plate_defaults` + `merge_row_vars` → `plate_client.convert`,任一行 convert 失败 → 整请求 422(`plate_rejected`,errors[] 透传),不产出部分文件。
- 响应:`{ files: [{filename, datasetName, rowIndex, converted}] }`;converted 为 dict,YAML/JSON 序列化沿用前端现有导出工具(与现菜单行为一致,序列化逻辑收敛一处)。
- 文件名:`{scenarioId}-{datasetName}-r{rowIndex+1}.json`(行号 1 基展示),基线文件沿用 `{scenarioId}-{时间戳}.json`。

## 后端:导入端点

`POST /api/scenarios/import`(multipart 文件上传,accept `.json/.yaml/.yml`,大小上限 2MB)

1. 按扩展名 + 内容嗅探解析为 dict;失败 → 400 `invalid_file`。
2. `fill_plate_defaults` → `plate_client.convert`(consumer=gimbal,仅作**校验**,丢弃输出);`PlateRejectedError` → 既有 422 `plate_rejected` 映射,errors[] 透传给前端。
3. **endpoint_id 回填**:拉一次 plate 语法端点集(routes_grammar 全量端点 dim 列表,确切路由实现时钉),建 `(method, path) → endpoint_id` 索引;对每个 step,命中则写 `step.api.view_hints = {endpoint_id}`(已有 view_hints 不覆盖——导入文件理论上没有,防御性保留)。`fields_meta` / `view_note` 不回填。
4. **orchestration 重建**:`steps.map((s, i) => ({enabled: true, name: s.description?.slice(0, 20) || \`步骤${i+1}\`}))`;`resourceMeta: {}`。
5. **身份**:`scenario_store.create` 既有语义——新 scenarioId、owner=当前用户强制覆盖;`meta.createTime`/`updateTime` 服务端重盖章(丢弃文件值);`meta.name/module/tags/priority/system/version/author` 保留文件值。
6. 响应:新场景 meta(scenarioId/name/stepCount);无数据集阶段,单事务,无半程失败面。

## 前端:导出对话框

- `ScenarioExportMenu` 下拉**追加**第 4 项"导出(可选数据行)…"打开对话框;既有三项(导出 JSON / 导出 YAML / 复制 JSON)不动,零回归。场景无数据集时隐藏该项(对话框无意义)。
- 对话框打开:按场景 GET 数据集列表(summary 仅 3 行 preview)→ 逐数据集 GET 全量 rows。
- UI:分组表格(组头 = 数据集名 + 行数 + "全选本组";列 = checkbox + 行号 + 各 var 列,与 DataSetEditor 网格语汇一致);底部"已选 N 行 → 导出 N 个文件" + 格式切换 JSON/YAML;未选任何行 = 基线导出 1 个文件。
- 确认 → POST 导出端点 → 顺序 `downloadFile`(浏览器会弹一次"允许下载多个文件",预期行为,N 大时 zip 属后续)。

## 前端:导入入口

- `Scenarios.vue`「+ 新建」旁加「导入」→ 文件选择(accept 同后端)→ 轻量确认弹框:客户端解析出 `meta.name` + step 数(解析失败直接报"文件格式无法识别",不发请求)→ 确认 POST → 成功 toast(场景名)+ 列表刷新,失败透传 errors[]。
- 前端 YAML 解析复用现有 yaml 库(导出已在用,含 load 则零新增依赖;实现时确认)。

## 边界与错误处理

1. **plate 校验失败**:统一走既有 `PlateRejectedError` → 422 + errors[] 字段级透传,不允许 500 黑盒。
2. **调色板校验复跑**:导出请求携带的行值虽来自 DB 快照,仍复跑 `_validate_rows`(拦截手工构造请求 + vars 事后编辑导致的越界行键)。
3. **语法端点未命中**(跨环境导入,grammar 无该 method+path):view_hints 保持缺失;composer 字段描述退化、draft-lint 提示"未绑定端点";执行不受影响(gimbal 导出本就剥视图字段)。
4. **config.users 凭证引用悬空**(目标环境凭证池无该别名):既有悬空徽章机制可见,不阻塞导入(内网语境,低息)。
5. **resource 非空场景**:resource 原样保留,仅 resourceMeta 重建为 `{}`(说明文字丢失,低损)。
6. **行号漂移**:行值随请求携带已规避;rowIndex 仅用于文件名展示。
7. **非法文件/超限**:400 `invalid_file` / 413;空 steps 等结构性问题由 plate 校验拦截。

## 测试策略

- **后端单测**:`merge_row_vars`(稀疏覆盖/类型矫正/`""` 显式空/缺键继承);导出端点(多行多文件、行名、all-or-nothing 422、基线 rows:[]);导入端点(回填命中/未命中、orchestration 重建、身份覆盖、400/422 透传)。
- **不变量测试**:导出产物 `config` ≡ dispatcher 为该行组合的 `config`(逐键断言,含矫正后类型)。
- **前端组件测试**:导出对话框(扁平选择状态、组内全选、空数据集态)、导入入口(解析预览、错误透传)。
- **E2E round-trip**:导出 2 行 → 导入 → composer 加载,字段描述正常(endpoint_id 回填生效)、draft-lint 无未绑定告警。

## 非目标(明确不做)

- 包装格式"参数化模板 + 数据集"备份语义及导入侧数据集重建(round-trip 不对称是本设计的固有语义:导出即物化为具体用例)
- V1 旧 Case 层 yaml 转换
- 多文件 zip 打包
- 列表页行级导出改造(保持基线 JSON)
- 保留原 scenarioId / 冲突交互
- plate convert `consumer="platform"` 渲染视图消费(草稿不存该形态,plate_client.py:130 注释口径不变)
