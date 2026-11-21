# 服务注册与凭证底座重构 · 设计方案

> 2026-11-16 与使用者多轮讨论定稿。前身:「服务配置(身份面)+部署表」二合一页。
> 本文是实施锚点;口径以本文为准,阶段推进中如有修订在此追加。
>
> **2026-11-17 追加 §8「环境降级为轻量标签」** —— 对本章既定口径的修订以 §8 为准。
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
3. **环境=平台级共享字典**(部署面横切,不按组织切)。2026-11-17 起降级为
   轻量标签轴(仍是平台级字典;角色收窄见 §8)。
4. **实例唯一 + 配置 overlay**:同一 (env, system) 不并排多套实例;
   差异化走「多身份条目」(并排命名身份)与「配置值分层」(基础/项目;个人层
   后收编为默认执行配置 —— 分层⑥,原文「基础/项目/个人」系写作时旧三层口径,
   2026-11-17 复核订正)。
   部署真有多套 → 拆多环境。
5. **账户实体化**:凭证行去槽位化,密码只存一份;条目引用账户(ref=默认账户|指定 username);
   登录地址上提到实例层,凭证表单「登录地址」退役。
6. **环境显式化**:身份条目与账户的 env **必填**(见 §2.3 收紧);管理面在环境配置页。
   (2026-11-17 修订:必填保留,语义降为归档标签 —— 条目 env 决定执行标签、
   账户 env 归档+登录口坐标;「同 env 匹配」门槛退役,见 §8.3。)
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

**实施注记(2026-11-17)**:实际列名 `owner_id` / `password_enc`(密文语义
显式);pool 判别 = CHECK(owner/project 恰一非空),uq(pool, system, env_id,
username) 用唯一约束 + `NULLS NOT DISTINCT` 实现(与预告的「部分索引」语义
严格等价);真正的部分唯一索引只有 is_default 那枚(WHERE is_default)。
「可空」列全库统一 NOT NULL + 空串缺省(仓库约定,功能等价)。

**2026-11-17 修订(§8.3,实施 M2)**:is_default 取用位改按 **(池, system)**
唯一(部分唯一索引重建,迁移 0059);env_id 保留为归档标签,身份引用不再
校验同 env,登录口按**账户 env** 取(密码与登录口同源不变式)。

### 1.5 `deployments`(不动) — (服务, 环境) → API 地址

### 1.6 `environments`(收窄) — 平台级环境字典

- 名称/描述/默认位保留;**lines 列迁出到实例后删除**。

### 1.7 `carry_service_bindings`(演进;`carry_global_defaults` 不动) — 配置值坐标定死

```
+ env_id 可空          空 = 全环境基线;env 命中覆盖(稀疏覆盖,表达力保留)
service_name → config_key   键域 ∈ {条目名 > 服务名 > 系统名}(层内解析序,细到粗)
uq(scope, scope_id, env_id, config_key, field_path)
```

**实施注记(2026-11-17)**:坐标/env 维度只落 bindings —— 「层默认」是三级
键域的粗端,无 config_key 可挂(给它加键坐标在语义上不成立),global_defaults
维持 (scope, scope_id, field_path) 三列形态;env 覆盖在执行/预览/编排三链
与凭证、地址同一位生效(透传曾缺失,见 §6.0 偏离 6,同日补齐)。

**2026-11-17 退役(§8.4,实施 M1)**:env 覆盖维整体删除(生产 238 行绑定
0 覆盖行)—— 本节 env 相关描述保留为历史;现行坐标 = (scope, config_key,
field_path),唯一约束随迁移 0058 重建为三键形态。

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
5. **2026-11-17 增补(§8.2)**:`RunRequest.environmentId`、`graph.environmentId`、
   预览 environmentId 入参与方案/执行配置/偏好三个环境链位 —— 显式注入通道
   全部退役(UI/API/webhook 均不再接受)。

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

> 本表为 2026-11-16 轮实态。2026-11-17 环境降级轮的增量影响面
> (env_chain / run_precheck / carry / auth 相关档位变化)见 §8.2–§8.5、§8.7。

### 3.2 前端

| 模块 | 依赖点 | 档 | 说明 |
|---|---|---|---|
| views/ServiceAdmin.vue | 全页 | **重做** | 结构面:系统分组注册簿 + 对账条 + external 登记 |
| views/ServiceAliasDetail.vue | 身份面子页 | **重做** | 条目化子页;路由路径未变(`/service-admin/{服务}`),书签天然有效 —— 无被替换的旧路径,重定向条款空转(§6.0 偏离 8 同族) |
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

> 2026-11-17 修订(§8.3):ref 取用不再校验同 env —— username 引用
> 同 tag 优先 → system 内唯一 → 歧义拦截;default 引用取 system 唯一默认;
> 登录口按**账户 env** 取。「未指定环境」根因改为「标签不可解析」。

### 4.2 ${slot.X.field}

fields_by_slot 数据源:条目 X → 账户 account_fields(键=条目名);正则零改。

### 4.3 地址链

deployment_urls 零改;登录口 = 实例 login_url(缺席 = 配置缺失,明确报,不回退)。

### 4.4 carry

层内链:条目键 > 服务键 > 系统键 > 层默认;tier 序(公共项目层 < 项目层)不变。
(2026-11-17:「env 命中 > env 空基线」的覆盖维随 §8.4 退役。)

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
2. 转换(内联 0057 `upgrade()`,PG DDL 单事务;无独立脚本,见 §6.0 偏离 5):
   - services:**旧表扫描进册**(deployments/别名/凭证行提及的服务;kind 沿
     旧别名值,system=服务名占位待对账页校正)—— 不依赖 plate 目录可达性,
     也更合注册簿制「存量行显式进册」;pay-service 无存量行未进册,由对账
     条「未登记候选」一键补登自愈;
   - identities:旧别名 2 行平移(+env=测试);**admin 凭证行 alias 同步生成条目**
     (ref 回指账户,场景 ${auth.X} 键落位);
   - accounts:codfish/codfish2 两行 → (admin 池, fin-service, 测试, ×2),
     is_default 双 True 冲突取 codfish(codfish2 曾被 ON CONFLICT DO NOTHING
     连带吞行,手工补插非默认行 —— 一次性迁移的人工兜底,事件记 commit
     `1af0795f`);
   - instances:(fin-service, 测试)/(jira, 测试) 建行,login_url **直写旧
     凭证 url**(在用地址,保行为连续;原「留白人工选定」是设计期对地址
     正确性没把握的谨慎,实况无歧义);
   - carry 238 行:config_key 直传(fin-service 落「服务」档),env_id=NULL。
3. 存量场景不处理 —— 条目名规约延续,场景键自动落位(决策 7)。

## 6. 实施序列(三阶段,串行)

### 6.0 实施状态(2026-11-16)

> 详细进度、验证数字与后续计划见 `docs/service-registry-progress.md`。

| 阶段 | 状态 | 实际落地 |
|---|---|---|
| Phase 1 底座 | ✅ 完成 | 四表 + 解析链 + routers 全量切换 + alembic 0057(已在生产库执行);全量 1560 passed / 461 skipped,0 残余失败 |
| Phase 2 页面 | ✅ 欠账全销 | 凭证页/项目凭证账户化(含 system 主档选择);服务注册页重做主档注册簿+对账+实例;身份条目子页条目化;ProjectConfigPanel+生效预览条目口径;ExecConfigs 装载就绪新链(C3a);carry 三档键选择器+env 覆盖开关+后端系统键面聚合(C3b,新用例待 PG 环境);导入映射按 ref 重做(P2-B.6:call.user→条目名统一改写,回报 authEntries/authRenames,13 用例恢复) |
| Phase 3 清账 | ✅ 完成 | 「槽位」字样全站退场(server 槽号/入站参数槽/看板 Root 槽等别概念保留);conftest P1-7 垫片删除;概念地图/运行手册核验零残留(migrations 时代造形同日落地,19 条重放用例恢复) |

**实施中的偏离与决策**（记录以免后续误读）：

1. **环境配置页未拆独立页**：实例(login_url/版本线)配置并入服务注册页
   （格内「实例配置」小钮；system 组头重复入口已于 2026-11-17 交互收口时
   移除）。理由：服务注册页定位就是
   「服务关系 mapping 入口」，`(系统, 环境) → 地址` 是其自然组成；环境×系统
   规模仍小（当前 1 环境）。后续若膨胀可再拆。
2. **空库 bootstrap 语义变更**：`app/core/migrations.py` 空库分支改为
   `upgrade 0001_baseline` + `stamp head`。原因：0057 退役 `service_aliases`
   等模型后，baseline 的 `create_all`（当前模型）不再产出旧表，而 0006/0021/
   0045 等历史增量仍引用它们 —— 空库顺序重放必然失败。fresh = 模型即形态；
   存量库（有 `alembic_version`）仍走完整增量链。
3. **导入「挂认证」退役与重做（P2-B.6）**：`scenario_import` 建条目时旧
   `slot`/`credentialAlias` 映射键退役（条目模型无槽，`create_alias_in_
   transaction` 已删该参数）。重做语义：注入键 = 条目名 —— 服务的唯一
   未被模板引用的 `call.user` 标签在导入时统一改写为生效条目名（映射到
   已有条目或本次新建同样处理）；模板引用的标签按同名条目装载；多标签/
   无条目如实回报（`no_identity`/`multi_user`）。落库回报
   `authEntries`（含条目登记坐标 system/envId 供深链）+ `authRenames`。
4. **deployments 保留**：`deployments`(服务×环境 → API 地址)与
   `system_env_instances`(系统×环境 → 登录口/版本线)**语义不同、并存**，
   服务注册页分列展示与编辑。
5. **迁移初始化与转换实态**(2026-11-17 复核追认,§5.2 已按实态改写)：
   主档初始化未「从 plate 目录拉入」而走**旧表扫描**——注册簿制语义
   (存量行显式进册)+ 迁移期不依赖 plate 可达性;pay-service 未进册由
   对账条自愈;instances login_url 直写旧凭证 url(非留白);转换内联
   0057、无独立脚本/报告输出(downgrade 本即 NotImplementedError,重放
   不可能,幂等诉求随之缩水);清理条件较 §5 授权面多删 owner IS NULL
   的项目池凭证行(实况空集,防御性硬化)。
6. **carry env 覆盖层:写面先行、执行链后补**：C3b 首落时仅管理面(编辑器
   覆盖开关 + bindings API envId)与读面(get_bindings 基线/覆盖合成)支持
   env 维度,三处执行链消费点(prepare_exec / 生效预览 / 编排单元)未透传
   env_id —— 覆盖行存而不生效。2026-11-17 复核补齐(见下),现执行/
   预览/编排与凭证、地址同一位生效。
   **同日反转**:当晚「环境降级」拍板(§8)整体退役 env 覆盖维 —— 本条的
   透传补齐与 `test_carry_env_overlay` 4 用例随 M1(迁移 0058)移除;
   记录保留为演进史,以免后续误读。
7. **请求层 slot 入参退役延期**：P2-B.6 曾保留 AliasCreate/AliasPatch 的
   slot 兼容入参(接受但忽略)并注「Phase 3 一并清扫」—— Phase 3 实际只
   清了文案,入参延至 2026-11-17 复核才删除(extra=forbid,发送即 422;
   输出面 `slot`=条目名是 §2 键域契约,保留)。
8. **书签兼容的双形态**：Auths 收链侧保留 `?newSlot=` 查询参数作 system
   预填兜底(发链侧深链已退役;与「书签不 404」同族的低成本连续性,代码
   内显式注释记档);ServiceAliasDetail 路由路径自始未变,重定向条款空转
   (§3.2 措辞已修)。
9. **交互词汇收口（2026-11-17，用户口径）**：「实例」一词在交互词面保留给
   **服务 × 环境的部署存在**（矩阵一格即一实例，行尾菜单删除动作称
   「删除实例」，确认文案写明连登记带全部环境实例一并移除、挂靠拦截）；
   格内「实例配置」小钮编辑的是 `(system, env)` 共享的**登录口/版本线**
   （按内容命名，不再与「实例」抢词），组头同名重复入口删除；末列补
   显名列头「操作」。**纯词面与入口调整，数据键域零改动** ——
   `system_env_instances` 存储形态与 API 不变。(2026-11-17 环境降级轮:
   「环境」UI 词面按 stitch 原型口径保留、呈现为 Tag 芯片,模型语义见 §8.1;
   「实例 = 服务 × 环境」词汇不变。)

**2026-11-17 一致性复核与修复**(代码 vs 本文档逐节比对;偏离 5–8 为该轮
追认,另修四项实现缺口):

| 项 | 修复 | 验证 |
|---|---|---|
| carry env 执行链透传 | `prepare_exec` / `resolve_effective_config` / `unit_carry_contexts`(graph_dispatch 逐单元环境位经 meta 下传)三处补传 env_id | `test_carry_env_overlay.py` 4 用例 + store 读面用例;carry 簇 58 回归绿 |
| 预检「未指定环境」 | `PrecheckResult` 新增 `envUnspecified`(环境链全空且场景用到条目 → 点名根因;Runner 提示先建默认环境) | 预检簇 13 绿(对照用例:建默认环境后信号熄灭);§1.4/§7「明确报」至此字面成立 |
| 漂移徽章 testid | ServiceAdmin `mx-drift-*` 缺 `:` 绑定(恒字面量)修复 | ServiceAdmin 套件 + 正向断言;前端全量 1435 绿 |
| slot 请求入参清扫 | 见偏离 7 | 别名/导入/令牌簇 83 绿 |
| 交互词汇收口 | 见偏离 9（实例=服务×环境；登录口/版本线按内容命名；删除动作随行称「删除实例」） | ServiceAdmin 套件 15 绿 + 前端全量 1435 绿 |

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
| 环境降级轮(§8)改动面广(~55 文件+3 迁移) | 里程碑 M1–M6 分批、每批全量绿;
  「密码与登录口同 env」不变式测试三例钉死(§8.3) |
| 预检硬门改变错误时机(步骤级报错 → 派发前 409) | 三路径统一错误码+标签上下文;
  开发环境直切(决策 8) |

## 8. 环境降级为轻量标签(2026-11-17 拍板,实施未启动)

> 本节是对 §0–§7 既定口径的修订,**冲突处以本节为准**。动因:服务注册页按
> stitch 原型(`claude/stitch_ux/`)重排牵出的概念审计 —— 「环境」同时承担
> 部署坐标 / 凭证匹配门槛 / carry 配置层 / 七级默认链四种角色;数据与缺陷
> 审计判定后三者为过度设计(生产实量:1 环境、carry env 覆盖 **0** 行、
> 方案/执行配置/项目默认/个人偏好环境全 **0**,且 13 个潜伏缺陷全部长在
> 多余角色上 —— 预检三处环境解析口径不一、suites 预检漏传 user_id、
> carry env 透传漏三处等,详见 progress「环境降级」节)。

### 8.0 拍板决策(用户口径)

1. **环境=轻量部署标签**:全局字典(`environments` 表与 id 保留)只做三件事
   —— 分类/筛选、地址/登录口/版本线的坐标、项目/平台默认位。不再承载
   carry 配置层、凭证匹配门槛、多层默认链。
2. **carry 去 env 维**:键域 = 条目 > 服务 > 系统 > 层默认(项目 > 公共)。
3. **凭证去 env 匹配**:身份引用不校验 env;username 引用同 tag 优先 →
   system 内唯一 → 歧义拦截;默认账户按 system 唯一。
4. **标签解析链 = 有效调用身份标签 > 项目默认 > 平台默认**;显式
   `environmentId` 全链退役(UI/API/webhook 均不注入);多身份标签不一致
   = 混拼硬拦截,无逃生口;换环境 = 改身份标签或项目默认。
5. **预检硬拦截 + 明确上下文**,UI/JWT、access token、webhook 三条派发路径
   统一硬门、一步到位。

### 8.1 词面规约(2026-11-17 按 stitch 原型定稿)

- 代码/表/列/历史 API 字段名**不动**:`environments`/`env_id`/快照里的
  `environmentId` 照旧。
- 模型与文档立「标签」新义;**UI 用户可见文案保留「环境」字样**(原型口径:
  筛选轴叫「环境/部署环境」,Tag 只指芯片形态);「实例 = 服务 × 环境」
  (偏离 9)词汇不变。
- 旧章节不改词,仅以本节声明词面规约。

### 8.2 标签解析链(修订 §3.1 env_chain「环境链不变」)

```
resolve_execution_tag:
  有效调用身份的标签(多个不一致 → env_mixed 硬拦截)
    > 项目默认标签(project.default_environment_id 保留)
    > 平台默认标签(environments.is_default 保留)
  全空 → env_unspecified 硬拦截
```

- **有效身份** = 执行配置「换用条目」(slot_map)∪ 场景声明条目 ∪ 行级
  `@slot` 覆盖,取**换用后**实际取用集合 —— 标签从换用条目取,不是声明条目。
- suite/graph **逐单元**独立解析(每单元各自身份集合;与旧「全图一个环境」
  不同,属预期语义变更);无身份场景直落项目/平台默认位。
- 简化链:query_views / integration 为单身份场景,标签 = 该身份 env;
  adhoc 无项目归属,链 = 身份标签 > 平台默认。
- **退役**:方案环境、执行配置环境、个人偏好三个链位;`RunRequest
  .environmentId`、`graph.environmentId`、预览 environmentId 入参;
  `env_chain.EnvironmentNotFound`(仅显式位触发)。
- **快照兼容**:`EnvChoice` 形状不变,`source ∈ identity|project|default`;
  历史 `config_json.environmentId/Source` 只读回放,环境行不删除。

### 8.3 凭证规则(修订 §1.4 / §4.1)

- 账户唯一键**保留** `(池, system, env, username)`,env = 归档标签
  (测试/生产同用户名不同密码可共存);身份引用**不校验** env。
- `ref_mode=username`:同 tag(条目 env)账户优先 → system 内唯一命中 →
  多行报 `account_ambiguous`。
- `ref_mode=default`:system 唯一默认账户;`uq_account_default` 重建为
  `(owner_id, project_id, system) WHERE is_default`(迁移 0059)。
- **正确性不变式:登录口按「账户 env」取** —— 密码与登录口必须同源
  (同账户 tag),钉死测试三例:同 tag 命中 / 跨 tag 用账户 tag / 多 tag 歧义。
- 消费点同步去 env 匹配:`auth_references`、`access_token` 范围复核、
  `projects.slot_status`、`auth_sessions` CRUD/拨测、`project_credentials`、
  `integration_runner`、导入、`query_views`。

### 8.4 carry 去 env(修订 §1.7 / §4.4)

键域 = 条目 > 服务 > 系统 > 层默认;坐标 `(scope, config_key, field_path)`;
迁移 **0058**(fresh 守卫 → 0 行去重 → drop 列/约束 → 重建三键唯一约束)。
管理面(编辑器覆盖开关 + bindings API envId)与执行链透传一并退役。

### 8.5 预检硬门(修订 §3.1 run_precheck「兼容」)

- 共用校验器(纯 DB + 请求内缓存):标签解析**一次**复用 —— 替换现有
  三处不一致的 `resolve_environment` 调用;`builtin_auth_shadowed` 同源。
- **硬拦截(409)**,错误码表:`env_unspecified | env_mixed |
  address_missing | login_missing | identity_missing | account_missing |
  account_ambiguous`;detail 必带 标签名/服务/系统/身份 上下文。
- **提示不拦截**:账户/身份 env 与执行标签不同(凭证解耦,401 自然暴露)。
- 契约扩展:`PrecheckItem` 增可选 `execConfigId` 等;`PrecheckResult` 增
  `envContext / envMixed / envWarnings`(全部可选,旧字段兼容;
  `envUnspecified` 根因语义改「标签不可解析」);修 suites `_precheck_one`
  漏传 `user_id` 的既有缺陷。

### 8.6 迁移(0057 之后)

| 迁移 | 内容 | 数据风险 |
|---|---|---|
| 0058 | drop `carry_service_bindings.env_id` + 重建三键唯一约束 | 0(覆盖行 0) |
| 0059 | `uq_account_default` → `(池, system) WHERE is_default` | 0(1 环境) |
| 0060 | drop `exec_configs.environment_id` | 0(表 0 行) |

均带 fresh 守卫(空库走 baseline+stamp);downgrade 不可逆(决策 8 口径);
迁移前 pg_dump(限定 schema;主库 1915 个测试残留 schema 不动,清理另议)。

### 8.7 影响面与实施里程碑

后端 ~35 文件 / 前端 ~20 文件。五个消费点全部切同一标签解析实现:
生效预览(`runs.py`)、adhoc、integration、query_views、suites。

- **M1** carry 去 env(含前端编辑器/API);
- **M2** 标签解析链 + 凭证规则 + 三链位与显式通道退役(0059/0060);
- **M3** 预检硬门(三路径统一);
- **M4** 前端契约(类型清理 + 各页面文案;运行面板/方案/执行配置的环境
  控件随链位删除消失);
- **M5** ServiceAdmin 按 stitch 原型重排(服务卡片流 + 实例表 + 「服务配置
  管理」抽屉;实例 = 服务×环境、配置就绪度替代探针、调用身份卡只显引用
  与可见性);
- **M6** 收尾(全量验证 + 文档复核表 + webhook guide / PLATFORM_
  REQUIREMENTS / PLATFORM-SCENARIO-COMPOSER-API 三外部文档随实现同步)。

每批全量绿再进下一批;测试改动清单与验证命令见 progress「环境降级」节。

### 8.8 不做

同环境多节点/多标签实例、环境表合并、carry 两表合并、历史数据清洗、
主库残留测试 schema 自动清理(如需另出脚本单独确认)。将来若需按部署
差异化配置:挂到实例(服务×环境)上,不回到环境层。

### 8.9 carry 实例档(系统档 → 实例档;2026-11-19 定稿)

§8.8 留的"挂实例"方向落地,同时把**系统档粗档退场**(用户决策:按部署
实例做默认值差异化 —— 测试/预发布/生产同字段不同值 —— 远比"跨部署
同值"常见;系统档前端写入口已随项目配置页手写退场撤空,替换代价小)。

- **新链序(层内,细到粗)**:`条目 > 实例(system, env) > 服务 > 层默认`。
  服务与实例是正交维度(服务 × 环境),链序是设计选择 —— 按部署差异化
  诉求**实例必须压过服务**(服务 timeout=30、SIT 实例 60 → SIT=60、
  无实例行的环境回落 30;条目键压过一切)。与旧三档"条目 > 服务 >
  系统"不同:实例不是替换系统档的位置(最粗端),而是**档位上移**。
- **实例词义统一**:实例 = `system_env_instances` 行 = (system, env);
  §8.1 的"服务×环境"是交互词面。值表坐标 =
  `(scope, config_key=系统名, instance_env_id, field_path)`;sentinel
  `instance_env_id=0` = 条目/服务档基线行(避开 NULL 唯一性陷阱),
  五键唯一约束。**与 §8.4 退役的"任意键 env 覆盖"语义不同**:那是
  env 维覆盖任意档,这是独立实例档 —— 环境只作实例键坐标,不构成覆盖层。
- **实例档环境 = 执行标签**(与地址取数同源:`有效身份 > 项目默认 >
  平台默认`;env_mixed 已被预检硬拦,执行级恒单值)。`env=None`
  (标签链全空 / 导入析出)→ 实例档跳过,按 服务 < 条目 合成。
- **同名碰撞**:服务名 = 系统名时(0057 主档初始化即如此),同
  config_key 的服务档行(env=0)与实例档行(envId)并存,靠
  instance_env_id 区分,实例压过服务;键判定"纯系统名"= ∈ 系统名集合
  且 ∉ 已登记服务名(同名按服务名放行)。
- **API**:值表 `GET/PUT /api/carry/bindings/{system}/instances/{envId}`
  (system 须命中主档、(system, env) 须有实例行,否则 404;权限门随
  既有值端点同口径)。裸系统名值端点 422 `carry_system_key_retired`;
  字段面端点 `/{key}/fields` 不动 —— 系统名键面(成员服务声明并集)
  原样复用给实例键(plate 声明面无环境维)。变更适配/导入走 store
  直连,系统键封堵落在 **op 校验层**(`create_op` / `_apply_carry_op`
  双保险);实例键进适配 op 为后续缺口。
- **消费面同步**:`build_carry_context` 加 `env_id` 参数(`prepare_exec`
  传执行标签;`unit_carry_contexts` 经 graph_dispatch 逐单元下传);
  预览 `resolve_effective_config` 同序(顺手修既有口径差:预览此前
  只查 base+alias 两档漏粗档),逐值 source 扩
  `{scope}:{scopeId}:instance:{envId}`;漂移报告实例行单列
  (`instanceEnvId` 标注,face = 系统成员并集,不进适配批)。
- **迁移 0063**:加列(server_default 0)→ 守卫报告并删除纯系统键行
  (预计 0 行:无 UI 写入口、0057 存量 238 行全落服务档)→ 重建五键
  唯一约束。fresh 链(baseline create_all)直建终态,守卫空转。
- **前端**:ServiceAdmin 配置管理抽屉新增「carry 默认值(实例)」分区
  (`ServiceBindingEditor` instanceEnvId 模式:字段面复用系统名键,
  值表走实例端点,「来源」列降两态);预览来源标签扩"·实例"档;
  CarryDriftPanel 实例行只读。**同批:ExecConfigsView 表单 v3** ——
  配置级 `carryOverrides` 写面退场(业务参数随调用身份走,本页收敛为
  "选身份"),存量值只读回写、执行链照常消费。
- **边界记档(2026-11-19 复核)**:实例档坐标的 system 半边取**步骤
  base 服务**的主档 system(`build_carry_context` 的
  `system_of[base]`),不跟随换用条目的 base —— 新写已限定同服务
  换用;存量跨服务换用(bindings 声明键指向他服务条目)时,实例/
  服务档仍按步骤服务解析、换用条目键照常压顶。边缘形态,非缺陷。

### 8.10 配置圈定调用身份集合(2026-11-19 定稿)

配置页痛点:选服务/实例后身份条目表**全量摊开**注册表行,用户只有
「换用为」一个动作 —— 配置本身不记录"用了哪些调用身份"。定稿:**配置
显式圈定采用的调用身份集合**(用户决策)。

- **字段**:`SystemSubConfig.aliases: list[条目名]`(声明侧;命名对齐
  前端身份条目注册表术语,规避 carry 字段面/登录 faces 撞名)。payload
  JSON 列零迁移;copy/patch 自动携带;`_flatten` 只取 bindings/
  carryOverrides —— **执行链不消费**(弱语义闸门,链路测试钉死)。
- **语义 = 管理范围**(用户拍板,两候选中选弱):圈定配置页就绪度/
  Ping All 拨测/凭证引导的展示范围;执行时场景声明条目仍按原链解析
  (不在集合内不拦截)。预检提示/硬拦截为后续可选增强,不在本期。
- **交互**:身份条目表首列「纳入」勾选;取消纳入一并移除该行换用
  bind(不用即不换);未勾行灰显只余条目名/坐标;换用控件只挂勾选行。
- **口径统一**:就绪度装载面板/服务列表概况/Ping All 拨测目标/节点
  摘要全部改**表单态勾选集**口径(取用 = 换用后条目;未换用的所选行
  也进面板 —— 修复此前只看换用绑定的盲区);装载面板注明"按当前
  编辑态(保存后生效)"。
- **存量兼容**:旧行缺省 `aliases=[]` = 未圈定 → 前端按 bindings 声明
  键推导展示,保存时固化;存量绑定节(声明 ∉ 注册表)的声明键恒视为
  已纳入(payloadOf 并入,无行可勾)。
- **字段配置呈现**(用户拍板):所选身份的字段只读概览 + 深链(坐标/
  ref 列已有;carry 值在服务注册实例档、账户字段在凭证管理),本页不
  恢复编辑(v3 退场决策延续)。


## 9. 服务引用注册化(架构终态;2026-11-21 落地)

### 定位

场景是**纯引用容器**:步骤引用服务键(注册域 = 主档 ``services``
∪ 身份条目表),凭证引用条目名;**地址/环境/实例是执行期事实**
(部署表 × 标签链),一律不进场景 payload。本节 = 第 ② 层
(``config.services`` authored 直连地址)的整体退役 —— 与 §4
解析链的终态收敛、与身份条目「引用即登记」(enforce)同一治理
口径在服务域的对偶。

### 终态形态

* **数据**:``definition.config.services`` 不再承载地址(存量已全清,
  保存闸 enforce 拒收带值声明 ``service_url_declared``);裸键
  (不在注册域)同样拒收 ``service_not_registered``。
* **解析链**(唯一组装点 ``run_materialize._apply_services``):
  ③ 环境部署地址 > ④ 缺口引擎显式报错(① 绑定 url 随 M2a S6、
  ② authored 随本终态先后退役;区规则 direct_addresses 一并消失,
  全区域一态)。
* **编辑面**:配置页「服务引用与解析」卡 = 步骤引用键 × 注册事实/
  身份面/实例/逐环境地址/缺口(只读;``GET /{id}/service-resolution``
  单源投影);改绑在步骤侧下拉(已登记条目);「自建服务」= 服务
  注册页登记(Admin+;编排器内联创建器改深链,不再场景内写声明)。
* **执行环境**:标签链(身份条目 > 项目默认 > 平台默认)在预览/
  解析面只读呈现;要固定 = 治理动作(换条目标签/项目默认),
  场景无「固定环境」字段。

### 保存闸(``REGISTRY_ONLY_SERVICES`` 三态)

off(测试缺省)/ audit(``X-Service-Warnings`` 头,导入响应
``serviceWarnings`` 键)/ enforce(422 两码,未注册先报)。挂路由层
create/PUT + 导入链(与身份闸同位);copy/share 不走闸,enforce
前提下库内已清账,口径闭环。**生产 .env 已切 enforce(2026-11-21,
清账三面 0/0/0 亲验后)**。

### 迁移记录(2026-11-21 执行)

审计(``scripts/audit_authored_services.py``):45 场景 / 2 键 ——
``fin-service``(9 场景 3 值)+ ``platform-service``(36 场景,
bootstrap 自拨测,未注册)。清账(``cleanup_authored_services.py
--apply --force``):注册 platform-service 入主档;fin-service
部署表对齐主流声明值(``https://fin-tidb.21eflag.com/``);43 场景
声明经属主保存链清空;2 个噪音值场景(模板串 / 一次性测试地址)
人工裁决清声明;重审计 **0/0/0**。

### 刻意不做

* 场景级「固定环境」字段(环境 = 标签链事实,快照化即失效);
* 部署表/主档的写权限下放(全局共享资源,Admin+ 治理与身份条目
  同口径;普通用户的自建诉求走申请/管理员登记);
* ``config.services`` 键域的新编辑入口(引用键只能来自步骤,
  卡内只呈现与迁移清除)。

### 范围收敛面(实例层;2026-11-21 架构一致性轮修订)

「每步从全量里选」的反模式修正:**服务 → 实例(服务×环境)→ 调用身份**。

* **数据**:``definition.config.service_scope: Array<{service: string,
  envId: number}>`` —— **只存实例引用**(2026-11-21 交互收敛:服务级
  引用退役,不再有 ``{service}`` / 旧 ``string[]``)。实例下可用的
  调用身份由 ``service_identities`` 按 ``(base_service, env_id)``
  派生,**不落范围 payload**(身份仍是解析事实)。
  旧形态已由 ``scripts/normalize_service_scope.py`` 清理(丢弃服务级/
  未知键,只保留可解析的实例引用);保存/导入闸严格拒收旧形态。
* **实例 = 组合读模型,不新增表**:``(service, env)`` 实例 = 
  ``deployments``(API 地址)+ ``system_env_instances``(系统×环境
  登录口/版本线)+ ``service_identities``(该实例下的身份)。新增
  ``GET /api/services/instance-overview`` 一次返回服务→实例→身份;
  ``PUT /api/services/{service}/instances`` 单事务写三张表(可选同时
  登记一条调用身份),Admin/ops.write,写入即自动出现在服务注册页。
* **自动收敛落库**:打开场景时先把步骤引用键解析为实例引用
  (身份条目 → 其 ``base_service + env_id``;服务名 → 服务级),与
  存储值不同则上抛一次;已收敛场景二次打开 no-op。
* **闸与解析**:``service_reference_audit`` 键集 = 步骤 ∪ 范围服务名
  ∪ 范围实例派生身份名(仅预选同样须注册;范围不参与 same_base 闸、
  不掺入 envMixed —— 派发只看步骤);``service-resolution`` 返回
  scope 派生身份键 ∪ 步骤 + 逐键 ``stepRefs``。token 范围/物化/预检
  不动(仍按步骤实际引用,预选不扩权)。
* **编排器**:配置页「服务范围」卡 = 实例行(服务 + 环境、API 地址、
  身份数、移除);选择器两层(先服务、再实例);
  Admin 可「创建实例」(环境/API 地址/登录口/版本线/可选默认身份)。
  步骤页下拉 = 范围实例派生身份 ∪ 步骤键中
  **base==锚点** 的键 + 域外当前值兜底 + ``__manage__`` 管理入口;
  注册表降级期实例 ref 回退为服务键。新建漏斗统一走配置页
  (``__create__`` 切配置页,不再深链服务注册页)。
* **刻意不做**:范围条目携带完整实例配置(URL/登录口仍是注册表
  解析事实,范围只存 service+envId);「步骤引用域外键」保存闸
  (UI 已收敛,注册闸/同 base 闸兜底);读取态主动写 payload
  (收敛只在下次保存随用户操作落库)。

