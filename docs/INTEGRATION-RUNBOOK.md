# 第三方集成运行手册(INTEGRATION-RUNBOOK)

> 依据:《外部接口定义归一 plate 改造方案》v1.0 §6.4(批4 落位,2026-10-19)。
> 面向:接入第三方系统、使用集成任务的运维与用户。

## 接入(第三方系统入 plate)

1. `systems/<系统>/` 写定义:`system.md` 的 `gimbal:system` 块声明
   `kind: integration`(系统内所有服务一致),frontmatter **不写任何版本线
   字段**;端点文件照 sut 写法(binding/method/path/声明树)。
2. **在分支上起草**(draft 是起草常态)→ 评审 → 全部置 `review: reviewed`
   (合入闸 pytest 拒绝 integration 系统的 draft 块)→ 合入。
3. 重启 plate 生效;`GET /healthz` 核对 `integration_definitions.<系统>`
   (定义标识 = 端点 shape_hash 按 id 排序聚合)与 `git_head`。
4. 在服务信息管理为该服务建**服务级默认别名**(名称 = 服务名,如
   `jira`),配 base_url/凭证;多实例再加实例别名逐步骤切换
   `call.service`,或在运行方案显式绑定(与被测系统相同)。

## 使用

- 编排器「第三方集成」分组选接口;选中自动写 `meta.plate[系统]=
  integration`(sut 系统固定单项「integration · 第三方实时定义」)。
- 集成任务:平台模式(平台凭证,只读闸)或个人模式(个人凭证,无
  query_safe 拦截);cron 定时;工作台卡片(POST /api/integration/cards,
  `fn:<taskId>`)。

## query_safe(只读标记)

- 仅**平台模式**硬约束:非 GET/HEAD/OPTIONS 步骤须在端点定义
  `metadata.query_safe: true`,否则创建/执行被 422 `not_read_only` 拒。
- 个人模式边界 = 用户本人在第三方的权限。
- **生效时序**:改定义 → plate 重启 → 平台 `/full` 缓存过期
  (`DECLARED_PATHS_TTL_SEC`,缺省 300s + 回退窗;重启平台后端可立即
  生效)。

## 变更语义(有意例外)

- 定义改动在 plate 重启后作用于**全部**引用场景,无逐场景确认、不阻断
  (对版本边界原则的有意例外:第三方无版本,阻断只会让集成任务全停)。
- 测试执行与图执行的 `plate_pins` 记当时定义标识(`integration@<hash>`,
  可追溯);**集成任务不入执行记录**(2026-10-08 决策),核对当前加载
  标识查 `/healthz`。
- 标识只随**接口形状**变化(binding/请求/响应声明树/增删端点);
  `query_safe`、description 等展示/治理字段**不**改变标识。

## 转换与禁例

- **被测系统本身作为集成对象**(自有系统保活/定时查询):直接用 sut
  锚点 + 修订钉定,不得登记为 integration(同一系统双源)。
- **转为被测系统**:原地改 `kind: sut` + 声明 `line` + 发版(发版前
  场景可暂声明 `working`)→ 场景改钉修订 → 别名经 patch 改 plate
  (前提:base_service 所指系统已是 sut)。
- **不得**:把已发版的 sut 系统改为 integration(须换新系统名);
  integration 系统挂取数视图。
- 同一第三方多实例 API 确不同 → 拆两个 plate 系统,别名分别指向。

## 已知边界

- 只读场景不支撑 Jenkins/Jira 推送类集成(平台模式只读;推送须个人
  模式写类任务)。
- plate 不可达时外部步骤与 sut 同样不可执行,外部别名无法新建。
- 卡片「成功」= 每次运行 check 结论(`runStatus`),非配置成功;
  配置/凭证错误走 `lastError`/`pausedReason`。
- 下线第三方系统:先用影响查询(`endpoint_ref_index`)列出引用场景与
  集成任务,处置后再删定义;直接删除时引用在预检/`/convert` 响亮失败。
