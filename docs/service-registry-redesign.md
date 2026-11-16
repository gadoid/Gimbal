# 服务注册与凭证底座重构 · 设计方案

> 2026-11-16 与使用者多轮讨论定稿。前身:「服务配置(身份面)+部署表」二合一页。
> 本文是实施锚点;口径以本文为准,阶段推进中如有修订在此追加。
>
> **总原则(2026-11-16 拍板):开发环境,数据非最优先保障项 —— 架构完整闭环优先。**
> 不为存量数据保留过渡兼容;表结构一步到位;初始化可重建,转换脚本仅兜底。

## 0. 目标模型(四层)

| 层 | 回答的问题 | 形态 |
|---|---|---|
| 服务主档 `services` | 这是什么服务 | 唯一;plate 对账 + 说明 + external 登记(注册簿制,不是目录镜像) |
| 环境×系统实例 `system_env_instances` | 部署在哪、从哪登录、什么版本 | 唯一;登录口 + 版本线落这里;API 地址仍按服务粒度在 `deployments` |
| 身份条目 `service_identities` | 以什么身份登 | 多套;alias_name 引用键(命名规约延续),纯引用账户 |
| 账户(凭证池 `auth_accounts`) | 登录信息本身 | 按人/项目隔离;(pool, system, env, username) 唯一;一处改密处处生效 |

已拍板决策:

1. **主档=注册簿**:显式集合,不从 plate 目录镜像;plate 新服务不自动进(页面提示可拉入),
   plate 改名可对账出漂移;external 照常登记(kind 三态沿用)。
2. **URL 粒度=service**(可独立部署最小单位),系统层做聚合呈现与批量填充;
   系统级默认地址 fallback 不建(需要时是增量,不是欠账)。
3. **环境=平台级共享字典**(部署面横切,不按组织切)。
4. **实例唯一 + 配置 overlay**:同一 (env, system) 不并排多套实例;
   差异化走「多身份条目」(并排命名身份)与「配置值分层」(基础/项目/个人)。
   部署真有多套 → 拆多环境。
5. **账户实体化**:凭证行去槽位化,密码只存一份;条目引用账户(ref=默认账户|指定 username);
   登录地址上提到实例层,凭证表单「登录地址」退役。
6. **环境显式化**:身份条目与账户的 env **必填**(见 §2.3 收紧);管理面在环境配置页。
7. **场景键稳定 = 架构决策,非代码适配**:条目命名规约延续 `<服务名>-<后缀>`,
   存量场景键天然落在条目名域内 —— 新解析链只认条目名,**不写旧形态适配分支**。
8. **数据非保障项**:不做行为等价性保证、不做旧端点/旧字段过渡窗口、不做回退分支;
   迁移=可重建初始化 + 十行级转换脚本兜底。

## 1. 表结构(一步到位)

### 1.1 `services`(新) — 服务主档,结构面

```
id, name uq, system, kind('plate'|'external'|'integration'),
abbr?, description, timestamps
```

- 对账状态运行时算(目录未注册 N / 漂移 M / plate 不可达),不落库。
- 写 ops.write;读全员。

### 1.2 `system_env_instances`(新) — 环境×系统实例,配置面锚

```
id, system, env_id, uq(system, env_id)
login_url?          登录口(上提自凭证行 url;拨测 = login_url + 账户 secret)
line?               版本线(迁自 environments.lines JSON —— 版本线收口到实例)
note?, timestamps
```

**版本线收口**:原 `environments.lines = {系统名: 版本线}` JSON 散列退役,
版本线成为实例属性 —— (env, system) 的全部事实(登录口/版本线/说明)收敛一处。
环境比对告警、保存推荐、退役判定改读实例表,口径更直。

### 1.3 `service_identities`(新,替代 service_aliases) — 身份条目

```
id, alias_name uq     引用键;命名规约延续 <服务名>-<后缀>(存量场景键零迁移落位)
base_service          服务锚(resolve_base/地址解析不变)
env_id 必填           环境显式化(别名后缀模拟环境词缀的历史到此为止)
ref_mode('default'|'username'), ref_username?
display?, timestamps
```

- 表更名新表,不演进旧表 —— alias_name 是**键语义**保留,不是表结构保留。
- 退役:slot 列(不设兼容读)、kind 列(升到 services)。

### 1.4 `auth_accounts`(新,替代 auth_sessions) — 账户,个人池/项目池同构

```
id, owner_user_id?(个人池) / project_id?(项目池)   pool 判别
system, env_id 必填, username
uq(pool, system, env_id, username)      部分索引实现(见实施)
secret, token_type, expires_in, account_fields
is_default             ref_mode=default 的取用序(同池同(system,env)至多一)
timestamps
```

- 退役:url(上提实例)、alias(引用键移条目)、slot。
- **env 必填收紧**:登录打到具体环境实例,无环境的账户无意义;
  执行期环境链兜底「平台默认环境」已存在,预检在无环境时即报缺,不留 env 空回退分支。

### 1.5 `deployments`(不动) — (服务, 环境) → API 地址

### 1.6 `environments`(收窄) — 平台级环境字典

- 名称/描述/默认位保留;**lines 列迁出到实例后删除**。

### 1.7 `carry_service_bindings` / `carry_global_defaults`(演进) — 配置值坐标定死

```
+ env_id 可空          空 = 全环境基线;env 命中覆盖(稀疏覆盖,表达力保留)
service_name → config_key   键域 ∈ {条目名 > 服务名 > 系统名}(层内解析序,细到粗)
uq(scope, scope_id, env_id, config_key, field_path)
```

**坐标闭环**:配置值 = (scope: 公共项目|项目, env?, config_key, field_path)。
层内解析序:条目名 > 服务名 > 系统名 > 层默认 — 与 URL「服务为主、系统聚合」
同构,系统级配置(如 orgNo)可直接挂系统键,不必再复制到每个服务。

### 1.8 退役表

`service_aliases` → `service_identities`;`auth_sessions` → `auth_accounts`;
`service_meta`(并入 services.description);`environments.lines` 列。
旧表不保留影子读 —— 开发环境直切。

## 2. 架构边界(对外契约,不是数据兼容)

1. **模板语法**:`${auth.<条目名>}` / `${slot.<条目名>.<field>}` / `call.user=<条目名>`
   语法与键域不变;X 的语义 = 身份条目名(规约延续,见决策 7)。
2. **场景服务键**:base 服务名 ∪ 条目名;`resolve_base`/`derive_base` 逻辑不变,
   校验集合 = 主档 ∪ plate 目录(external 行不受 plate 可达性影响)。
3. **执行链模块边界**:`resolve_exec_auths` 输出 `ResolvedAuth{alias,url,username,
   password,token_type,expires_in,account_fields}` 形态不变 —— url 来源换实例
   login_url。下游 materialize/integration/dispatcher 零改动。
4. **不做**的兼容:旧 API 字段影子、旧端点代理窗口、slot 读侧保留、
   登录口回退 deployments、env 空账户回退 —— 全部不留。

## 3. 影响面矩阵(重做 / 适配 / 兼容三档)

### 3.1 后端

| 模块 | 依赖点 | 档 | 说明 |
|---|---|---|---|
| services/run_prepare.py | resolve_exec_auths / _slot_tier / _pool_clause | **重做** | 条目→ref→账户;输出形态不变(§2.3) |
| services/run_materialize.py | _substitute_slot_refs / _apply_users | 适配 | ${slot.X} 数据源经条目取账户;正则不变 |
| services/env_chain.py | resolve_environment | 兼容 | 环境链不变 |
| services/env_chain.py | deployment_urls | 兼容 | (base_service, env) 查表不变 |
| services/carry_injection.py | tier + 层内键链 | 适配 | config_key 三级键域 + env 覆盖(§1.7) |
| services/carry_store.py | 绑定读写 | 适配 | 列更名/加 env_id |
| services/service_names.py | derive_base / resolve_base_with_aliases | 适配 | 校验集合扩主档;形状不变 |
| services/auth_ref_scan.py / auth_references.py / data_set_store.py | 条目名扫描/计数 | 兼容 | 键域不变零改 |
| services/scenario_import.py / scenario_store.py | 条目校验/重锚定 | 适配 | 校验源同上 |
| services/access_token.py / routers/access_tokens.py / project_tokens.py | alias_name scope | 兼容 | 键域不变(读 service_identities) |
| services/integration_runner.py / adhoc_run.py / graph_dispatch.py / run_dispatcher.py / run_semantics.py / query_view_runner.py | resolve_exec_auths 输出 | 兼容 | §2.3 边界 |
| routers/service_aliases.py | CRUD | 适配 | 新表;端点键域不变,形状按条目模型 |
| routers/deployments.py | CRUD | 兼容 | 不动 |
| routers/environments.py | CRUD + lines | 适配 | lines 读写迁实例表 |
| routers/service_meta.py | CRUD | 适配 | 并入主档,端点退役 |
| routers/auth_sessions.py / project_credentials.py | 列表/表单/拨测 | 适配 | 账户化形状;拨测取实例 login_url |
| routers/run_precheck.py / runs.py / run_schemes.py / scenarios.py | 条目就绪/引用 | 兼容 | 键域不变 |
| routers/catalog.py | plate 代理 | 兼容 | 不动;对账读它 |

### 3.2 前端

| 模块 | 依赖点 | 档 | 说明 |
|---|---|---|---|
| views/ServiceAdmin.vue | 全页 | **重做** | 结构面:系统分组注册簿 + 对账条 + external 登记 |
| views/ServiceAliasDetail.vue | 身份面子页 | **重做** | 迁环境配置页;旧路由重定向(书签不 404) |
| (新)环境配置页 | — | **重做** | 环境优先:系统实例列表(URL/登录口/版本线/身份条目/字段默认值入口) |
| views/Auths.vue | 凭证表单/行/拨测 | 适配 | 账户化:表单去登录地址;分组仍 system×env |
| components/project/ProjectCredentialsPanel.vue | 同上 | 适配 | 项目池对称 |
| components/AuthSelectorModal.vue | preselectAlias | 兼容 | 键域不变 |
| components/composer/*(Canvas 别名下拉、RunConfigPanel) | listAllAliases | 兼容 | 键域不变(文案微调可选) |
| components/schemes/SchemeRunConfigSection.vue | listAllAliases | 兼容 | 同上 |
| components/project/ProjectConfigPanel.vue | 槽位状态/预览 | 适配 | 环境版本线取数改实例;槽位文案换「身份条目」 |
| views/ExecConfigsView.vue | 就绪度/深链 | 兼容 | 端点不变 |
| workbench 服务卡/服务画像 | catalog/aliases | 兼容 | 不动 |
| SuiteCompose / DataSetGridEditor / dataset-grid | ${slot} 扫描 | 兼容 | 不动 |

比例:兼容 ≈ 55%,适配 ≈ 30%,重做 ≈ 15%。

### 3.3 裁决原则

> 关联组件后续改造的影响点与已知变更,一组件一卡,见
> `docs/component-impact-ledger.md`(组件改造欠账台账,C1–C5)。

- **键域与模块输出形态不变 → 底座提供兼容**(§2 是边界清单,30+ 引用点零改)。
- **字段语义变化 → 消费方适配**,且**同步直切**(不再留 Phase 3 过渡窗口 —— 旧形状
  直接下线,消费方在同一变更内适配完成)。
- 场景契约(§2.1/§2.2)是**产品架构边界**,永久稳定;API 面是**内部边界**,随架构走。

## 4. 解析链

### 4.1 凭证解析(resolve_exec_auths 重写)

```
步骤服务键/${auth.X} → 条目清单(X=条目名)
  → service_identities 行(env 必填)
    ref_mode=default  → 账户(pool, system, env, is_default)
    ref_mode=username → 账户(pool, system, env, ref_username)
  → ResolvedAuth{alias=X, url=实例login_url, username, password, ...}
```

- 取用序:ref 命中 > 缺失即缺(无环境回退分支 —— 预检期报「未指定环境」)。
- MissingAuthAliases 语义不变(集成链 paused/missing_credential)。

### 4.2 ${slot.X.field}

fields_by_slot 数据源:条目 X → 账户 account_fields(键=条目名);正则零改。

### 4.3 地址链

deployment_urls 零改;登录口 = 实例 login_url(缺席 = 配置缺失,明确报,不回退)。

### 4.4 carry

层内链:条目键 > 服务键 > 系统键 > 层默认;env 命中 > env 空基线;
tier 序(公共项目层 < 项目层)不变。

## 5. 迁移(简化:重建优先;含用户数据清理)

**清理先行**(2026-11-16 授权:除 Administrator(id=1 admin)外均为测试用户,可删):
1. dump 备份(惯例命名,清理与迁移均可回放)。
2. 必删(架构相关):auth_sessions.owner_id ∉ {1}(4 行,pay-prod/pay-uat/
   fin-qa1/wms-token 随 owner=32 删 —— 两个迁移决策点就此消解);
   project_members.user_id ∉ {1}。
3. 可选清(测试账号本体及其场景/执行数据):迁移报告附「测试用户 × 数据量」
   清单与一键清理命令,人工确认后执行 —— 不与架构迁移捆绑。

**数据迁移**(清理后实量:凭证 2 行 / 别名 2 行 / 部署 2 行 / carry 238 行 / 环境 1 行):
1. alembic 单版本:建新表(services/instances/identities/accounts)、environments 删
   lines 列、carry 改列;**旧表直接 drop**(service_aliases/auth_sessions/
   service_meta)。
2. 转换脚本(读旧写新,同事务,幂等,输出迁移报告):
   - services:fin-service/pay-service 从 plate 目录拉入;jira 登记 external;
   - identities:旧别名 2 行平移(+env=测试);**admin 凭证行 alias 同步生成条目**
     (ref 回指账户,场景 ${auth.X} 键落位);
   - accounts:codfish/codfish2 两行 → (admin 池, fin-service, 测试, ×2),
     is_default 双 True 冲突取 codfish;
   - instances:(fin-service, 测试)/(jira, 测试) 建行,login_url 留白 ——
     候选 https://fin-tidb.21eflag.com/ 已列报告,人工在环境配置页选定;
   - carry 238 行:config_key 直传(fin-service 落「服务」档),env_id=NULL。
3. 存量场景不处理 —— 条目名规约延续,场景键自动落位(决策 7)。

## 6. 实施序列(三阶段,串行)

### 6.0 实施状态(2026-11-16)

> 详细进度、验证数字与后续计划见 `docs/service-registry-progress.md`。

| 阶段 | 状态 | 实际落地 |
|---|---|---|
| Phase 1 底座 | ✅ 完成 | 四表 + 解析链 + routers 全量切换 + alembic 0057(已在生产库执行);全量 1560 passed / 461 skipped,0 残余失败 |
| Phase 2 页面 | 🟡 进行中 | 凭证页/项目凭证账户化 ✅;服务注册页重做主档注册簿+对账+实例 ✅;身份条目子页(概览/凭证 tab)、ProjectConfigPanel 适配、导入映射重做待办 |
| Phase 3 清账 | ⬜ 未开始 | 「槽位」文案与文档同步 |

**实施中的偏离与决策**（记录以免后续误读）：

1. **环境配置页未拆独立页**：实例(login_url/版本线)配置并入服务注册页
   （system 组头「实例配置」+ 格内登录口小钮）。理由：服务注册页定位就是
   「服务关系 mapping 入口」，`(系统, 环境) → 地址` 是其自然组成；环境×系统
   规模仍小（当前 1 环境）。后续若膨胀可再拆。
2. **空库 bootstrap 语义变更**：`app/core/migrations.py` 空库分支改为
   `upgrade 0001_baseline` + `stamp head`。原因：0057 退役 `service_aliases`
   等模型后，baseline 的 `create_all`（当前模型）不再产出旧表，而 0006/0021/
   0045 等历史增量仍引用它们 —— 空库顺序重放必然失败。fresh = 模型即形态；
   存量库（有 `alembic_version`）仍走完整增量链。
3. **导入「挂认证」退役**：`scenario_import` 建条目时 `slot` 参数保留但忽略
   （条目模型无槽）。前端导入面板的认证下拉已下线；按 ref 语义重做留待 Phase 2。
4. **deployments 保留**：`deployments`(服务×环境 → API 地址)与
   `system_env_instances`(系统×环境 → 登录口/版本线)**语义不同、并存**，
   服务注册页分列展示与编辑。

**Phase 1 底座**:alembic 新表全量 + 解析链重写(4.1–4.4)+ service_names 校验源
+ routers 形状(旧形状直接下线,前端同批适配凭证/环境相关调用)。
验证:pytest 全量(新增架构语义测试:条目→ref→账户全路径/缺省序/missing/env 必填预检)
+ 存量场景试跑一条链。

**Phase 2 页面**:服务注册页(结构面+对账)/ 环境配置页(实例+条目+字段默认值)/
凭证页+项目凭证面板账户化适配 / AliasDetail 迁居重定向 / ProjectConfigPanel 适配。
验证:vitest + vue-tsc + eslint + 8188 构建(备份惯例)+ 双主题截图。

**Phase 3 清账**:「槽位」文案全面退场(条目/身份口径)、文档与 runbook 同步、
docs/概念地图更新。

## 7. 风险清单(架构闭环优先下的残余风险)

| 风险 | 缓解 |
|---|---|
| resolve_exec_auths 重写回归 | 架构语义测试全路径覆盖(非行为等价快照);集成链 paused 语义测试 |
| 环境必填收紧影响无环境存量执行 | 开发环境直切;预检明确报「未指定环境」,提示建默认环境 |
| 版本线迁实例的比对告警口径 | 告警读面同批切实例表;测试覆盖 lines→instance 读等价 |
| carry config_key 三级键域误配 | 层内解析序测试 + 配置页键选择器(条目/服务/系统三档显式选择) |
| 场景键落空(条目被删/改名) | 条目删除走 confirmAction+引用计数(沿用 auth_references);
  改名不做(引用键稳定是架构决策,改名=删旧建新) |
