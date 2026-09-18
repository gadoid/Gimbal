# 执行注入溯源 — injection manifest 落账设计

> 日期:2026-09-18
> 状态:待评审(未实施)
> 范围:Gimbal-platform 后端执行链(dispatch 落账 + 读侧 API)
+ 前端执行详情页展示。P2 预留执行前预览,本 spec 不实施。
> 前置:执行链现行为(run_dispatcher._fanout,2026-09 时点)、
> carry 注入(spec §4)、断言注册条目物化(spec v3 §3)、
> run 副本物化(spec §7 黄金等价)。

## 1. 背景

一次执行里,参数写入发生在 **7 个 dispatch 侧阶段 + 2 个引擎侧阶段**,
彼此覆盖语义各不相同(填缺失 / 覆盖 / 正交叠加 / 预处理展开)。用户排查
"这个值怎么不对"时,没有任何一处能看到"该值由哪个阶段、从哪个来源
写入、是否被后续层覆盖"——只能读代码或翻零散日志。

当前权威注入链(逐 case = 数据集行 × 重复次数):

| # | 阶段 | 代码位置 | 写入语义 |
|---|---|---|---|
| 0 | plate meta 补缺 | `plate_client.fill_plate_defaults`(整单一次,就地) | 缺失补默认 |
| 1 | 数据集行值合入 | `_compose_scenario`:行键 → `config.vars`,按基线类型还原 | 基线 |
| 2 | 注册条目偏离 | `compose_injection_scenario`:Assign 直补 + asserts patch | 与 1 正交,偏离最后生效 |
| 3 | plate convert | 校验 + 剥平台视图字段(**剥除**也是观测对象) | 剥除 |
| 4 | 服务 URL 绑定 | `materialize_run_copy._apply_services` | 绑定 > 场景 authored |
| 5 | auth users 合并 | `materialize_run_copy._apply_users`:`{**内置, **authored}` 后 resolved 覆盖 | resolved 最优先 |
| 6 | carry 填充 | `materialize_run_copy._apply_carry`:绑定 > 默认,`setdefault` | body 显式值永不覆盖 |
| 7 | 引擎预处理 | `${var}/${auth}` 模板展开、`$.` JSONPath 解析(缺变量 ValueError) | 展开覆写 |
| 8 | 运行时策略 | extract/assign 改写上下文 | 动态,静态不可知 |

其中 #0–#6 全部发生在 `_fanout` 的局部变量里——**落账信息零额外 IO**;
#7 的引用面可以静态扫描,#8 只能标记。

## 2. 目标 / 非目标

目标:

- 任一次执行(新执行)能按 case → 步骤 → 参数回答:最终值、写入阶段、
  来源明细(数据集列 / carry 层 / auth 别名 / 注册条目 / body 显式)、
  覆盖与被覆盖关系、跳过及原因。
- **零行为变化**:manifest 收集不得改动任何注入语义;收集自身故障降级
  为"该 case 无 manifest",绝不阻塞执行(同 carry 降级纪律)。

非目标:

- 不做执行预言(断言成败、运行时数据流)。
- 不回填历史执行(旧执行详情页显示"早于落账上线")。
- 执行前预览(RunDialog 预检 tab)留 P2,复用本 spec 的生成器内核。

## 3. 数据结构

每条 manifest 条目:

```json
{
  "case": {"dataset_id": "ds-…", "row_index": 2, "repeat": 0},
  "stage": "dataset_row | registry_entry | plate_defaults | convert_strip
            | service_binding | auth_users | carry
            | engine_preprocess | runtime",
  "target": "steps[3].request.body.$.amount"
          | "config.vars.orderNo"
          | "config.services[fin.order]"
          | "config.users[alias]"
          | "steps[3].strategy[+assign $.request_body.note]",
  "value": <写入的最终值>,
  "source": {"kind": "dataset_column", "dataset_id": "ds-…", "column": "amount"}
          | {"kind": "carry", "path": "$.amount", "layer": "binding | default"}
          | {"kind": "auth", "alias": "…", "auth_id": 3}
          | {"kind": "registry_entry", "entry_id": "…"}
          | {"kind": "body_literal"}
          | {"kind": "engine_template", "ref": "${var.amount}"},
  "effect": "written | skipped | overridden",
  "reason": "host_conflict | no_value_both_layers | service_unresolved
             | body_explicit_kept | overridden_by_auth | …"
}
```

- `target` 用统一的寻址串;strategy 追加(#2)与 convert 剥除(#3)
  不是 body 叶子写入,各自定 target 形态。
- **脱敏**:`auth_users` 阶段的 password / token 一律落 `"***"`
  (明文凭证不过 plate 的安全缝原则,延伸为不过 manifest)。carry 值、
  数据集行值照落(库内本就明文)。
- `engine_preprocess` 条目(P1 只做静态引用面):dispatch 侧扫描
  steps 里的 `${var.x}` / `${auth.x}` 引用,记 `{ref, 是否在 vars/users 中}`,
  不记展开值(展开发生在引擎,值在既有 step 日志可见)。
- `runtime` 阶段 P1 不产条目,前端展示层固定渲染一行说明。

## 4. 落账路线:内部插桩(事实落账),非外部重放

两条路线的取舍:

- **内部插桩(选定)**:在 `_fanout` 各注入点旁收集条目(值均为局部
  变量);`materialize_run_copy` / `compose_injection_scenario` /
  `_apply_carry` 返回值不变,**manifest 收集以旁路 collector 传入**
  (可选参数,缺省 None = 零开销、既有调用方与黄金测试不动)。
- 外部重放(否决):dispatch 后用相同输入重算 manifest——重放与事实
  漂移正是本模块要消灭的故障模式。

漂移防线(黄金测试):对 fixture 输入,断言 manifest 中 #1–#6 的
`written` target 集合 == materialize 前后深 diff 的键集合
(「账不漏写」);collector 自身在 try/except 内,异常 = 丢弃该 case
manifest + 一次 warning,不影响执行。

## 5. 存储 / API / 前端

- 存储:执行 case 目录旁挂单文件
  `DATA_DIR/runs/cases/<runId>/injection-manifest.json`(全部 case 一份,
  与 result evidence 同目录惯例;DB 行不膨胀)。
- API:`GET /api/executions/{id}/injection-manifest` → 404 = 无落账
  (旧执行或收集降级);owner 校验同既有执行读侧。
- 前端:Executions 详情页新增「注入清单」区块——按 case 折叠 → 步骤
  分组 → 条目行(target mono、stage chip 分色、effect 图标、reason
  灰字);跳过/被覆盖条目默认收进「被跳过的注入」折叠组。

## 6. 分期

- **P1(本 spec)**:dispatch 落账(#0–#6 + #7 静态引用面)+ 读端点 +
  Executions 页区块 + 黄金覆盖测试。
- **P2(预留)**:RunDialog 执行前预览(同一 collector 对计划态干跑);
  #7 展开值回填(引擎 step 日志对账);#8 运行时策略条目(需引擎侧
  配合,另立 spec)。

## 7. 测试

- collector 单测:每阶段条目形状与 reason 分类(纯函数级)。
- 黄金:manifest 覆盖完整性 vs materialize diff(§4)。
- 降级:collector 抛异常 → 执行照常、无 manifest 文件。
- API:owner 隔离、404 语义。
