# M2a S6 别名瘦身 + serviceBindings 收窄 — 实施细化(2026-11-08)

- 依据:`authz-m2a-plan-2026-11-07.md` §二 S6 行、§三 S6;consolidated §4.1「方案:只做选择,不存值」、§9.1/9.2
- 基线:`feat/authz-m1` @ `aad9dcdd`(S5 收口)
- 迁移:`0047_alias_slimming`(删列 + 存量方案清洗 + 地址回落部署表 + 报告/通知)
- 上线公告:**要**(见 §五)

## 一、待定项裁定(S6 前须定;用户未在线,按方案推荐先行,可推翻)

| # | 裁定 | 说明 |
|---|---|---|
| 原 5 | **采纳推荐**:私有区保留内置凭证(`config.users`)与直连地址(`config.services`);**项目区与公共区一律不生效** | 运行时规则(不改存量数据):场景 `project_id` 非空 → 内置凭证当空、authored 地址层跳过,地址只来自部署表。预检 / 生效预览 / 导出同口径 |
| 原 6 | **S6 维持现状**(属主带 overlay 导出含本人槽位明文;非属主为空;项目/公共区随原 5 不带内置凭证) | 「只导出槽位声明」与 S7「导入时内置凭证转槽位声明」一并做,避免导出文件先失去可执行性 |

## 二、`serviceBindings` 新语义:服务键 → 别名

- 线上形态(RunScheme / RunRequest / GraphSpec / GraphUnitSpec / ExportOverlay 五处同一模型):
  `serviceBindings: {<服务键>: {"alias": "<别名名>"}}`;**带 `url` / `authAlias` → 422 `binding_field_retired`**;其它未知键 422(extra=forbid)。
- 校验(写面 + 派发面):别名须存在(`binding_alias_unknown`),且与服务键同基础服务(`binding_alias_mismatch`;服务键的基础服务 = 其别名行 `base_service`,非别名即自身)。
- 生效面(唯一口径 `service_aliases.effective_alias`):
  - **槽位**:别名默认凭证按「选中别名」的槽位命中(原「按服务键自身」);
  - **carry**:层内别名键取「选中别名」(`fin → fin-maker` 吃 `fin-maker` 的别名键覆盖);
  - **地址**:不受影响 —— 同基础服务校验保证部署表地址一致(地址只由环境决定)。
- 方案绑定 authAlias 的旧语义(显式指定凭证槽、排除别名默认)整体退役:凭证 = 槽位绑定(S3),选哪个账号由槽位默认 / 环境决定。
- 重跑回放:归档 `config_json.serviceBindings` 中的 `url`/`authAlias` 剥离(历史数据,不 422),无 alias 的条目丢弃。
- `auth_references` 删方案扫描路径(方案不再存凭证引用)。

## 三、别名瘦身(删列)

| 列 | 去向 |
|---|---|
| `base_url` | 地址只来自部署表 `deployments[(base_service, env)]`;`base_urls_for` = 部署表单源(env 必需,无环境 = 无 ③);`merge_addresses` / `overrides_alias` 影子期分支退役;`/deployments/conflicts` 退役 |
| `environment_id` | 环境由执行时环境链决定;adhoc 版本线改按环境链取环境的 `lines`;混环境告警(`_check_env_consistency`,依赖 authAlias)退役;环境删除守卫去别名检查 |
| `owner_user_id` | 个人默认别名退役,全部共享;别名写面 = ops.write;删用户处置去别名分支 |
| `credential_alias` | `slot` 唯一口径(S3 起两列同步);线上字段 `credentialAlias` → `slot` |

### 0047 步骤
1. `slot = coalesce(slot, credential_alias)`。
2. 无默认环境且存在「无环境的别名地址」→ 建默认环境(D2 兜底不断)。
3. 地址回落部署表:无环境别名按基础服务聚合,一致 → upsert 默认环境(**别名地址胜**,保持「没人显式选环境」路径逐字节不变);挂环境别名一致 → 缺则补(部署表已有不覆盖,与显式选环境时部署表优先同口径);不一致不落。
4. 方案 payload 清洗:剥 `url`/`authAlias`,空条目删除;逐方案记录丢弃内容。
   4b. 被剥的绑定 url 按基础服务**补缺**落默认环境部署表(无已有行、各方案一致才落;冲突 / 已有行进报告)。
5. 报告:`audit_logs` 一行(action `migration.alias_slimming`,detail = 冲突组 / 丢失地址的别名 / 别名环境选择器 / 个人别名共享化 / 方案清洗清单);**通知**:方案属主各一条(列出受影响方案与丢弃字段)+ Admin+ 一条汇总(指向部署地址页)。
6. 删四列(含 FK / 索引)。
- downgrade:回加四列(可空);`credential_alias = slot`;`base_url` 从默认环境部署表回填;方案清洗与个人别名属主不可逆(报告留档)。

## 四、子切片

- S6.0 线上形态收窄 + 别名选择语义 + 消费点切换 + 重跑剥离 + auth_references
- S6.1 原 5 区规则(项目 / 公共区不吃直连地址与内置凭证)
- S6.2 别名瘦身 + 0047
- S6.3 前端(运行配置面板 / 方案页 → 别名选择;服务管理页去地址/环境/属主;部署页去冲突裁定)
- 收口:全量 + 迁移测试 + 四门 + dev 迁移 + 推送

## 五、上线公告要点

1. 方案 / 执行请求里手填的服务 URL 与凭证别名失效:地址由「环境 → 部署地址」给出,凭证由「我的槽位绑定」给出;带这两个字段的请求返回 422。存量方案已清洗,属主收到逐方案清单。
2. 「别名名即环境选择器」(如 `fin-dev` 固定打 dev)失效:地址随本次执行选中的环境走。
3. 项目区 / 公共区场景里写死的直连地址与内置凭证不再生效(私有区不变)。
4. 个人别名转为团队共享;别名的地址 / 环境字段移除(地址在「部署地址」页维护)。

---

## 六、实施记录(2026-11-08)

| 子片 | 交付 | 证据 |
|---|---|---|
| S6.0 | `ServiceBinding = {alias}`(extra=forbid,url/authAlias → 422 `binding_field_retired`);`effective_alias` 换名单源(槽位默认 + carry 别名键);`validate_binding_aliases`(方案写面 422 / 派发 409 / 预览·导出 422 / 编排 GraphDispatchError);`scrub_retired_bindings`(重跑回放 / 升级前入队配方 / 方案读面兜底);物化与预检去 ① 层;auth_references 删方案扫描路径;混环境告警退役(只剩「本次环境线 vs 场景钉定线」) | test_run_bindings_injection / graph / export overlay / suites_validate / auth_references 改写 |
| S6.1 | 原 5:`run_prepare.zone_allows_direct` 单口径;`built_in_users(project_id=必填)`;`ExecPrep.direct_addresses` → `materialize_run_copy(direct_addresses=)`(执行 / 导出 / 集成 / 编排四链);预检 / 生效预览 / 追溯 resolvedServices / 令牌范围(`used_sets_for_definition(project_id=必填)`)同口径 | test_authz_s60 区规则 3 例 + test_public_content_strips_credentials 矩阵加区维度 |
| S6.2 | 模型删四列;`base_urls_for` 部署表单源(无环境 = 无 ③);`env_chain.merge_addresses/overrides_alias` 退役;别名路由退役字段 422、slot 唯一口径、个人别名退役;`/deployments/conflicts` 退役;环境删除守卫去别名;删用户处置去别名分支;导入:URL 清除不变量改判部署表、新建别名共享 + slot;adhoc 版本线 / 地址走环境链;0047(slot 兜底 / 默认环境兜底 / 地址回落 / 方案清洗 / 审计报告 + 属主与 Admin+ 通知 / 删列);0044/0045/0046 补 fresh 链守卫 | test_migrations 19/19(含 test_0047)|
| S6.3 | 前端:运行配置面板 / 方案页「每服务选别名」(同基础服务候选、显示槽位、已删别名标红);服务管理页去地址 / 环境 / 属主,声明槽位;部署页去冲突裁定;Auths 去 scheme 引用类;Executions 兼容新旧绑定形态 | vitest 1319 / vue-tsc / eslint / build 四门绿 |

落地要点 / 偏差:

- **绑定校验错误码分面**:方案写面 / 预览 / 导出 = 422;单场景派发 = 409(派发层 `Conflict` 通道;语义 = 「配置与登记不一致」);编排 = `GraphDispatchError`。
- **绑定只对 steps 实际引用的服务键生效**:旧语义「绑定 authAlias 即使 steps 未引用也并入注入清单」随 authAlias 一并退役;依赖它的存量用例改为让场景引用被绑服务键。
- **令牌范围(安全)**:项目 / 公共区 authored 若仍按「直连范围外」算会让 authored 键绕过范围判定(执行实际走 ③)—— `used_sets_for_definition` 的 `project_id` 设为必填,所有调用方传场景区。③ 不再影响别名集归属(按环境只决定 URL),顺手删掉恒空的 ③ 查询。
- **顺手修复的存量缺陷**:编排单元 ③ 地址从未生效(`_all_referenced_services` 把已解包 definition 当容器取 steps 恒空),此前被绑定 url 层掩盖;S6 退役绑定 url 后暴露,修复 + 回归用例(test_authz_s60::test_graph_units_get_deployment_address)。
- **0047 fresh 链半形态**:0006 会在 fresh 链补回 `base_url`,其余三列不存在 —— 0047 先补齐为空列再走统一逻辑;0044 守卫改为两列齐全才回填。
- 原 6(导出明文)维持现状,随 S7「导入时内置凭证转槽位声明」一并定。
- **④b 方案绑定 url 补缺回落**(dev 迁移时发现后补):dev 的「平台保活探针」默认方案把 `platform-probe` 钉在本机地址,清洗后无处取址 —— 0047 加 ④b 把被剥的绑定 url 按基础服务补缺落默认环境部署表;dev 库已先跑过不含 ④b 的 0047,按同口径手工补行(`platform-probe@测试 = http://127.0.0.1:8000`)并补记审计报告。

### 收口证据

- 后端全量:1832 passed / 2 skipped / 0 failed(25:49);④b 补丁后迁移套件 19/19
- 前端四门:vitest 1319 passed / vue-tsc 0 / eslint 0 / build ✓
- dev 库:0046 → 0047(先 pg_dump 备份 service_aliases / composer_run_schemes / deployments / environments);报告:冲突 0、地址被取代 0、方案清洗 1(sc-keepalive 默认方案 platform-probe url)、通知 6 条(属主 1 + Admin+ 5);后端重启 health 200
