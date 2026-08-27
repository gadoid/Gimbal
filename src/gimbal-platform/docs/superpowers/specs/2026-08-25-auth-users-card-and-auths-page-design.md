# 认证功能改造:配置页用户卡片 + 认证管理页 UI 重整

- 日期:2026-08-25
- 状态:设计定稿(已与用户逐节确认)
- 分支:`strbody_avaliable`

## 背景

- 场景编排配置页(③ CaseComposerConfig)对 `config.users` 只有 3 处透传、无任何编辑 UI;用户信息目前只能靠导入外部 JSON 进入场景。
- 认证管理页(Auths.vue)存在三个体验问题:操作列 140px 过窄导致测试/编辑/删除换行;测试弹框标题三元 `testResult?.ok ? '连通成功' : '连通失败'` 在请求在途时把 null 折叠成"连通失败"(先失败后成功的假象);弹框信息布局陈旧。
- auth 迁移阶段已完成(用户 2026-08-25 确认;c5cab10 提交信息仍写 wip,以用户口径为准)。遗留的 2 个红测试 `test_test_endpoint_*` 不再豁免,随本改造修绿。多组件通用功能迁移到 gimbal-core 属后续大重构,本设计不动 gimbal 主仓 `src/gimbal/auth`。

## 目标

1. 配置页新增"用户认证"卡片:可手动配置用户/认证信息(字段与认证管理新增表单一致),也可从认证管理(凭证池)导入快照;导出产物携带用户信息。
2. 认证管理页:三按钮同行;测试弹框状态主视觉式重构;状态流 认证中 → 认证成功/认证失败。

## 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 凭证池选择的存储语义 | **快照拷贝**:选择时把 url/username/password(解密明文)/token_type/expires_in 完整拷进场景 `config.users[alias]`,之后凭证池修改不影响场景 |
| 明文获取机制 | **方案 A 按需详情解密**:`GET /api/auths/{id}?include_secrets=true`;列表接口维持不带密 |
| 明文展示策略 | 用户名/密码在配置页卡片明文展示(公司内网测试环境,用户明确认可);认证管理列表不展示密码 |
| 测试弹框形态 | 状态主视觉式(居中大图标 + 状态文案 + 分层信息) |

## 总体数据流

```
凭证池(auth_sessions 表,Fernet 加密)
   │ ① 配置页"从凭证池导入" → GET /api/auths/{id}?include_secrets=true(按需解密)
   ▼
场景草稿 config.users[alias] = {url, username, password, token_type, expires_in}   ← 快照,明文
   │ ② 保存草稿(payload JSON 原样存,已有链路,零改动)
   │ ③ 导出:草稿 → POST /api/scenarios/preview-plate → 前端下载 JSON/YAML(config.users 随产物携带,零改动)
   │ ④ 执行:run_dispatcher 以 definition.config.users 为注入基座(已有链路,零改动)
   ▼
${auth.<alias>.<field>} 运行期由 gimbal 引擎解析
```

兼容性依据:plate `AuthSession` 所有字段均有默认值(gimbal_plate/schema/auth.py),5 字段快照可无障碍通过 convert;`GimbalScenarioExporter.render` 不排除 `config.users`。导出与执行链路零改动。

## 后端:include_secrets 按需解密

- `GET /api/auths/{id}` 新增查询参数 `include_secrets: bool = False`;为 true 时返回新响应模型 `AuthSessionSecretsOut`(`AuthSessionOut` + `password: str`)。
- 复用 `_get_owned` owner 隔离(跨 owner 一律 404)。
- 严解密:username/password 任一解密失败 → **422**,消息"加密凭据已损坏或密钥已轮换,请先在认证管理重新编辑保存"(应对 `FERNET_KEY` 未配置时进程重启轮换)。
- 策略放宽仅限内网测试环境,本节即记录依据。

## 前端:配置页"用户认证"卡片

CaseComposerConfig.vue 新增第 7 张卡片"用户认证(users)":

- **表格列**:alias / url / username / password(明文列)/ token_type / expires_in / 操作(编辑、删除)。
- **手动新增/编辑弹框**:字段与认证管理一致——alias(校验 `/^[A-Za-z0-9_-]{1,64}$/`)、url/username/password 必填、token_type(Bearer/Basic/Cookie/Authorization 整段头)、expires_in(0-86400,默认 7200)。差异:password 用明文输入框(`type="text"`);编辑态 alias 禁改(users 字典 key)。
- **从凭证池导入弹框**:多选列表(alias/username/url);确认后逐条拉含密详情写入快照;单条请求 422(密钥轮换/凭据损坏)→ ElMessage 报出后端消息并跳过该条,其余继续;场景已存在的 alias 置灰不可选,tooltip"已存在,如需刷新请先删除该行"。v1 不做覆盖导入。
- 快照形状与 run_dispatcher 注入器写入一致:`{url, username, password, token_type, expires_in}`。
- 类型:`ConfigView.users` 收紧为 `Record<string, UserAuthView>`;`authSessions` store 增加 `fetchDetail(id, includeSecrets)`。
- 卡片头部提示:"此处的用户信息将随场景导出,并可在步骤 header 中以 `${auth.<alias>.*}` 引用"。

## 前端:画布悬空徽章修正

CaseComposerCanvas.vue 的 `${auth.<alias>.*}` 悬空判定从"仅凭证池(/api/auths)"改为**凭证池 ∪ 草稿 `config.users` keys**,避免引用场景本地用户被误标悬空(执行实际可解析)。

## 前端:认证管理页三处

1. **按钮同行**:操作列 `width` 140 → 200,测试/编辑/删除单行。
2. **测试弹框重构(状态主视觉式)**:
   - 标题固定"认证测试";状态机 `testPhase: 'testing' | 'success' | 'fail'`。
   - testing:旋转图标 + "认证中…" + alias·url 副标题。
   - success:绿 ✓ + "认证成功" + HTTP 状态码 badge(仅 status_code 非空时显示;probe 失败路径恒为 None)。
   - fail:红 ✗ + "认证失败" + 同规则 badge。
   - 详情区可折叠:失败默认展开,成功默认收起。
   - 弹框底部"重新测试"按钮。
3. `runTest`:开弹框即 `testing`,请求返回/异常后切终态;消灭 null 折叠。

## 后端:async 阻塞修 + 红测试收口

- `/auths/{id}/test` 端点内同步 `auth_probe.probe` 改为 `await asyncio.to_thread(auth_probe.probe, ...)`;不动认证器同步接口(迁移刚稳定,接口改造留给 gimbal-core 大重构)。
- 修复 `test_test_endpoint_*` 2 红测试:mock 从 `httpx.AsyncClient` 改为同步 `httpx.post`;4xx 用例断言对齐现行为(`ok=False, status_code=None, message` 含"认证失败")。

## 测试策略

- **后端 pytest**:include_secrets 用例(happy path 含密 / 跨 owner 404 / 解密失败 422);红测试修绿;现有套件无回归。
- **前端 vitest**:CaseComposerConfig 补 users 卡片用例(增删改 round-trip、alias 冲突置灰);auth_sessions store 补 `fetchDetail`;CaseComposerCanvas 补徽章 union 用例;Auths 弹框状态机用例。
- 完成标准:`vue-tsc --noEmit`、`vitest run`、后端 pytest 全绿。

## 非目标

- 认证管理列表不显示密码列(明文仅配置页快照与导出产物)。
- 不做引用模式/凭证池自动同步;不做 users 条目逐条"测试"按钮。
- RunDialog 不新增认证 alias 选择(`RunRequest.auths` 维持不填;运行时同名 alias 与场景 users 冲突的 409 预检因此实际不可达)。
- 不动 gimbal 主仓 `src/gimbal/auth`;gimbal-core 整合留待后续大重构。
