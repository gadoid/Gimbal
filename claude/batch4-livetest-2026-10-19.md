# 批4 活体验证记录(2026-10-19)

> 依据:归一方案 v1.0 §6.4;实施计划 v1.1 §6。环境:plate @8765
> (systems=仓库真源,artifacts=D:\Gimbal\plate-artifacts)、平台后端
> @8000、PG gimbal-pg-15432;第三方 = `jira`(定义入库于批3)。
> 全程 API 级(编排 UI 交互以保存闸/目录接口等效验证)。

## 链路记录(时序)

| # | 步骤 | 结果 |
|---|---|---|
| 1 | plate `/healthz` | `integration_definitions.jira=fcb98733…`(shape_hash 聚合)✓;**git_head 恒 null → 活体修复**:改读 `.git` 文件(子进程 git 在服务环境不可用),重启后 `git_head=64631b6c…` ✓ |
| 2 | `/api/catalog/services` | 全量三服务,jira 行带 `kind=integration` ✓(不得过滤面 + 聚合行带 kind,b2-7 活体) |
| 3 | 服务级默认别名 | `POST /api/service-aliases` `{aliasName:"jira", kind:external, baseUrl:…, baseService:"jira"}` → 201 ✓(external 显式 base_service + kind 校验链,b2-8 活体) |
| 4 | 场景保存 | `sc-b4-livetest`(锚点 `jira.jira.search`,call.service=jira,`meta.plate={jira:integration}`)→ **201** ✓(保存闸 validate→get_system_kind 放行 + plate 声明闸双向绑定通过) |
| 5 | 平台任务·未标 query_safe | 422 `not_read_only`(POST 未标)✓ —— **反转依据①端到端闭环** |
| 6 | 定义标 `query_safe: true` → 重启 plate | `/healthz` 标识**不变**(fcb98733…)✓ —— D-L「metadata 不进标识」活体证据 |
| 7 | 同请求立即重发 | 仍 422 ✓ —— 平台 `/full` 缓存 TTL(300s+回退窗)生效,即 §6.4「query_safe 生效时序」上界的实证;重启后端(运维等效动作)后同请求 **201**(任务 26)✓ |
| 8 | 个人任务 | identityMode=personal → **201**(任务 28,无 query_safe 拦截)✓ |
| 9 | 手动 run + 调度 | 两任务 run 均 `failed/transport`(jira.example 不可达,预期通道终态;定义解析/convert/物化全链 200)✓;任务 26 的 `lastRunAt` 出现第二次自动执行 —— **cron 调度链(scheduler_tick)活体确认** ✓ |
| 10 | 卡片 | `POST /api/integration/cards {ids:["fn:26","fn:28"]}` → 两卡,`runStatus=transport`、`checkStatus` 独立、`lastError` 带 SSL 详情 ✓ |
| 11 | 清理 | 两任务 removed=200、场景 DELETE 204(活体对象不残留;别名 `jira`/`jira-x` 保留为有效配置) |

## 悬置项结论(§7.1 → 关闭)

1. **只读场景对 Jenkins/Jira 推送类集成**:判定**不能** —— 平台模式只读闸
   按 method+query_safe 拦截,POST 推送无法标 query_safe(语义即写)。
   已写为已知边界(手册);个人模式写类任务不受此限。
2. **卡片「成功」语义**:确认 = **每次运行 check 结论**(`runStatus`),
   非配置成功 —— 卡片结构中 `runStatus`(check)与 `enabled/state`
   (配置面)分立,配置/凭证错误走 `lastError/pausedReason`,不冒充运行
   成功。**通过,无需修复批**。

## 活体发现与处置

- **[修复] git_head 恒 null**:`/healthz` 的 git_head 经子进程 `git
  rev-parse` 在服务进程环境下不可用(交互环境同调用正常)→ 改为直接读
  `.git/HEAD → refs → packed-refs`(无子进程依赖),含测试回归。
  提交:`fix(plate): b4 活体修复`(feat/ext-unify-b4)。
- **[正面证据] 缓存 TTL 语义**:定义改动后平台侧最长 `300s+回退窗`
  才放行新 query_safe —— 与方案 §2.3/§6.4 口径一致,写入手册时序节。
- **[正面证据] D-L 标识稳定性**:query_safe/description 类改动不翻标识;
  通道失败不产生误导性的「定义切换」标记。

## 手册落位

`docs/INTEGRATION-RUNBOOK.md`(v1.0 §6.4 全量 + 活体补充的生效时序)。
