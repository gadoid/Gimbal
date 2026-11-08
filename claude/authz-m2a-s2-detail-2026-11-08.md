# M2a S2 环境选择链 + 部署表 — 实施细化（2026-11-08）

- 依据：`authz-m2a-plan-2026-11-07.md` §二 S2 行、§三 S2、裁定 D2 / D4 / D11
- 代码基线：`feat/authz-m1` @ `3fa85364`（S1 全部收口，head 迁移 `0043_drop_visibility`）
- 迁移序号：S1 占用 0040–0043，**S2 = 0044**

---

## 〇、调研结论（决定了切法）

| # | 现状 | 对 S2 的含义 |
|---|---|---|
| E1 | 地址链 = ① 绑定 `serviceBindings.url` > ② 作者声明 `config.services` > ③ `service_aliases.base_url`（`base_urls_for`，按**别名名**精确查）> ④ 缺口；装配单点 `run_materialize._apply_services` | 只改 ③ 的数据源，①②④ 与装配单点不动 |
| E2 | `base_urls_for` 调用方 9 处：prepare_exec（单场景 / 集成 / 导出）、graph_dispatch、run_precheck、integration 指纹、access_token 范围集、runs 追溯 ×2、adhoc 地址检查 | 加可选 `env_id` 形参：传了走部署表、缺省 = 旧行为；需要环境的调用方逐个接 |
| E3 | 运行时**没有**选环境；环境只影响 adhoc 版本线与混环境告警 | 环境链是全新链路 |
| E4 | `Environment.visibility` 只有列定义 + 响应字段，零逻辑消费 | 直接删（列 / 视图字段 / 前端类型 / 守卫豁免） |
| E5 | 方案字段由客户端摊平进 RunRequest（`scheme_id` 只是溯源记录） | 服务端兜底：请求没给环境但带了 `schemeId` 时回查方案的 `environmentId` |
| E6 | dev 存量：1 个环境、3 个别名（2 个有地址、1 个挂环境、0 冲突）、1 个项目 | 回填简单；仍按通用规则写（冲突按别名名首个胜出） |

## 一、链路定义

**环境**：本次显式（`RunRequest.environmentId`）> 方案（`RunScheme.environmentId`）> 项目默认（`projects.default_environment_id`，仅项目场景）> 个人偏好（`user_prefs['run.environment']`）> 默认环境（`environments.is_default`，D2：Admin 指定）> 无。

**地址 ③**（服务键 `svc` = 步骤 `call.service`）：
1. `base_service` = 别名表里 `svc` 行的 `base_service`；不是别名则 `svc` 本身（D11：部署表键 = plate 服务名）；
2. 环境来自**显式选择**（本次 / 方案 / 项目 / 个人偏好）→ 部署表优先，未命中回退别名 `base_url`；
3. 环境只来自**默认环境兜底**（或无环境）→ 别名自带 `base_url` 优先，部署表只补别名没有地址的键。

理由（S2.0 实测发现）：存量里「别名名即环境选择器」（`fin-dev` / `fin-sit` 各带地址）很常见；若默认环境的部署表一律覆盖别名地址，引用 `fin-sit` 的老场景会在上线当天被改指 dev 地址，违反 D2。影子期规则：**没人显式选环境时行为与旧链逐字节相同**（只补旧链的缺口）；显式选了环境才让部署表接管。S6 删别名 `base_url` 时两支合一。

**指纹**（D4）：第七要素 `base_urls` 改为「按上面链路解析出的地址集」。上线当天无人显式选环境 → 解析结果与旧链相同 → 指纹不变 → **不触发全员暂停**；之后改部署地址或改环境选择，只让受影响订阅暂停待确认（比原计划一次性全员暂停更窄，且符合 D2）。

## 二、子切片

### S2.0 模型与迁移 0044
- 新表 `deployments(id, base_service, env_id FK environments CASCADE, base_url, created_at, updated_at)`，`UNIQUE(base_service, env_id)`
- `environments.is_default`（bool，部分唯一索引：至多一行为 true）；**删 `environments.visibility`**
- `projects.default_environment_id`（FK environments，SET NULL）
- 回填（固定顺序）：① 存量恰 1 个环境 → 置为默认；② 别名地址按 (基础服务, 环境) 聚合成部署行 —— 挂环境的别名落其环境，没挂环境的落默认环境（无默认则不落）；**同键地址不一致的键不落行**（冲突留 Admin 在部署表页裁定；运行时各别名回退自带地址，保 D2 逐字节不变）
- fresh 链守卫（baseline 按当前模型建表）；downgrade 删表 / 列、回加 visibility
- 测试：迁移三形态（单环境 / 多环境无默认 / 无环境）× 回填断言 × 一致聚合 / 冲突不落 × downgrade 往返

### S2.1 环境链 + ③ 层切部署表
- `services/env_chain.py`：`resolve_environment(...) -> (env_id, source)`；`base_urls_for(db, names, *, env_id=None)` 走部署表 + 别名回退
- 线上形态加 `environmentId`：`RunRequest`、`RunScheme`、`GraphSpec`
- 接线：dispatch_target 解析环境 → `config_json.environmentId/environmentSource`（重跑按快照回放）→ 任务配方 → `_fanout` / `_fanout_graph` → `prepare_exec(environment_id=...)`；precheck、导出、集成执行 + 指纹同链
- 测试：链路优先级全排列；部署命中 / 回退 / 无环境旧行为；dispatch 快照与重跑回放；precheck 按环境判缺口；指纹（地址不变不暂停 / 改部署地址暂停）

### S2.2 接口
- `/api/deployments` CRUD（读 = 登录；写 = ops.write；409 同键重复；审计 `deployment.write`）
- 环境：`isDefault` 进出（置默认 = ops.write，原子切换）；响应删 `visibility`
- 项目：`defaultEnvironmentId`（项目管理员可改）
- 偏好：白名单加 `run.environment`
- 删除环境：被部署行 / 项目默认引用时的处置（部署行 CASCADE；项目默认 SET NULL）

### S2.3 前端
- 部署表维护页（Admin，环境 × 服务网格编辑）+ 路由 / 侧栏
- 运行弹窗与方案配置区加环境选择（缺省显示将生效的环境与来源）
- `api/environments.ts` 删 `visibility`、加 `isDefault`；`api/deployments.ts`；偏好类型加 `run.environment`

## 三、清理项
- `Environment.visibility` 列 + `EnvironmentView.visibility` + 前端 `EnvironmentRow.visibility` + `ServiceAdmin.test` 的 mock 字段
- `test_grep_guard_visibility.py` 的 `environment.py` 豁免（列删后守卫无豁免）
- `run_dispatcher` / `scenario_composer` 里「执行环境键已随 D2 退役」等过期注释随新字段改写

## 四、不在 S2
- adhoc 地址仍走旧 ③（无场景无方案，环境语义留 S5 统一解析入口）
- `access_token` 范围集只判「是否可解析」，回退保证结果不变，不接环境
- 删别名 `base_url` / `environment_id`（S6）
