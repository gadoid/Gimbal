# M2a S3 槽位绑定 — 实施细化（2026-11-08）

- 依据：`authz-m2a-plan-2026-11-07.md` §二 S3 行、§三 S3、裁定 F6/F7 与「项目凭证」节
- 代码基线：`feat/authz-m1` @ `206076a8`（S2 全部收口，head 迁移 `0044_deployments_env_chain`）
- 迁移序号：**S3 = 0045**

---

## 〇、调研结论（决定了切法）

| # | 现状 | 对 S3 的含义 |
|---|---|---|
| G1 | auth_sessions = `(id, owner_id, alias, url, username_enc, password_enc, token_type, expires_in)`,UNIQUE(owner, alias);一切引用按**名字**(模板 `${auth.X}`、`call.user`、别名 `credential_alias`、users 注入键、引用面板、query_view 缓存、drop_credential) | 名字缝必须保活:存量行的槽名 = 原别名,注入键/模板引用零变化 |
| G2 | 唯一 FK = `access_token_scopes.auth_id → auth_sessions.id CASCADE`;check_scope 按 id 判权 | **行 id 保持稳定**(ALTER 加列,不重建表)→ 令牌范围天然不受影响;迁移测试只须钉「范围行存活」 |
| G3 | 引擎 UserCredential `extra='forbid'`(六字段) | `account_fields` 只能存槽位行上,经 `${slot.X.field}`(S4/S5)进 carry/模板,不进 users 条目(F6) |
| G4 | 静态令牌 = `url == ''`(空 url 跳过登录拨测,密码即令牌) | 不受改键影响,原样保留 |
| G5 | dev 存量:5 个会话,4 个无别名引用(system 推断不出)、1 个 fin-service | 「未归类」路径真实存在;PG 16.15 支持 `UNIQUE NULLS NOT DISTINCT`(env 可空进键) |

## 一、模型定义

**绑定键**:`(owner_id, system, env_id, slot)`(NULLS NOT DISTINCT;env 空 = 不限环境的绑定,存量全落这层)。

- `system`:String(128) NOT NULL default `''` —— `''` = 未归类(存量推断不出/用户未认领);推断来源 = 引用该凭证的别名的 `base_service` 唯一值,多个或零个 → `''`,由用户在写面认领。
- `env_id`:FK environments.id SET NULL,空 = 不限环境。
- `slot`:String(64) NOT NULL —— 槽名 = 注入键/模板名(存量 = 原别名)。**不可改名**(与 alias 同规则:改名 = 重建)。
- `account_fields`:JsonVar dict(账号级字段,如 orgNo/opId;明文非密)——S3 只存取,**消费在 S4/S5**(`${slot.X.field}`)。
- `is_default`:Boolean NOT NULL default false;部分唯一索引 `(owner_id, slot) WHERE is_default` —— 每槽至多一个默认(名字解析 / 环境未命中时用)。存量行全部置默认。
- `alias` 列保留(展示名);**应用层**仍按 (owner, alias) 唯一校验(409)——所有按名消费的缝(引用面板 / 缓存 / drop_credential)保持无歧义,DB 层权威键是四元组。

**别名声明槽位**:`service_aliases.slot` String(64) 可空;回填 `slot = credential_alias`;S3 期间两列由写面保持同步(credential_alias 是 S6 别名瘦身的删除项)。

**解析层**(名字兼容 + 环境感知):
按槽名解析(模板 `${auth.X}` / `call.user=X` / 绑定 authAlias=X → slot=X):
1. `(owner, slot)` 里 env 命中本次环境(或 env 空)且 system 匹配的行;
2. env 空的绑定(存量层,旧行为);
3. `is_default` 行;4. 首行(id 序)。
存量库每槽恰一行(env 空、is_default)→ 解析结果与旧链**逐行相同**。

**令牌范围**:auth_id 不动、id 不变;`check_scope` 的 (owner, alias) 映射查询改按 (owner, slot) 同义执行(存量 slot=alias,行为不变)。

## 二、子切片

### S3.0 模型 + 迁移 0045
- auth_sessions 加五列 + 换唯一键(`uq_auth_owner_alias` → `uq_auth_owner_system_env_slot` NULLS NOT DISTINCT)+ 默认槽部分唯一索引;service_aliases 加 slot 列
- 回填:slot=alias;system 按 G1 推断;env 空;存量行 is_default=true;别名 slot=credential_alias
- fresh 链守卫;downgrade 还原(回删列/回建旧唯一键)
- 测试:三形态(可推断 / 引用冲突 → 未归类 / 无引用)+ **范围行存活**(F7 目标的行为面证据)+ downgrade 往返

### S3.1 解析与写面
- `resolve_exec_auths(owner, names, *, env_id=None)`:槽名解析分层(§一);prepare_exec / dispatch fail-fast / graph / precheck / 集成 strict 链带环境
- `credential_alias_hits` 走别名 slot(与 credential_alias 同步)
- /auths 写面:POST 增 system/envId/slot(默认 = alias)/accountFields;PATCH 增 system/envId/accountFields/is_default;POST /{id}/default 原子切换(同槽清旧默认);alias 应用层唯一(409)
- 静态令牌(url='')路径不动
- 测试:分层解析(环境命中 / env 空回退 / 默认行)、同槽多绑定、写面校验、静态令牌不回归、token check_scope 存量不回归

### S3.2 引用/计数面
- auth_references / counts / GET /{alias}/references:按名缝继续工作(应用层 alias 唯一保证无歧义);列表响应带 system/env/slot/isDefault/accountFields(掩码:accountFields 原样,非密)
- 测试:引用计数跨改造不变

### S3.3 前端
- Auths.vue:列表加 系统/环境/槽/默认 列;新建与编辑表单加 system/envId/accountFields;「设为默认」动作;api 类型更新
- (整页改造为「槽位绑定」主体归 S7 配置项页;S3.3 只做字段面)

## 三、清理项
- `uq_auth_owner_alias` 的 DB 约束退役(应用层校验顶上);相关注释更新
- `test_auth_sessions.py` 唯一性用例改按新键 + alias 应用层 409 口径

## 四、不在 S3
- `${slot.X.field}` 模板解析与 carry 注入(S4/S5;account_fields 本片只存取)
- 项目凭证(归属维度 个人/项目):S3 只立键,归属列随项目凭证细化在 S5 前单独裁定落地
- credential_alias 列删除(S6 别名瘦身)

---

## 五、实施记录(2026-11-08)

| 子片 | 提交 | 门禁 |
|---|---|---|
| S3.0 模型 + 迁移 0045 | 本批 | 迁移 16/16;全量 1809 passed(1 守卫白名单计数误报已修) |
| S3.1 解析分层 + /auths 写面 | 本批 | 见下 |
| S3.2 引用/计数面 | 并入 S3.1 | 名字缝未动,test_auth_references 原样绿 |
| S3.3 前端字段面 | 本批 | 前端四门 1317 / tsc / eslint / build |

落地要点(与 §二 的差异/补充):

- **行 id 稳定**:0045 用 ALTER 加列 + 换约束,不重建表 ——
  `access_token_scopes.auth_id` 的 CASCADE 从未触发,令牌范围零动作
  (F7 的重映射预防不需要执行;迁移测试钉「范围行存活」)。
- **PG 事务内 ALTER 陷阱**:回填 UPDATE 会在迁移事务留下延迟触发器
  (auth_sessions 的 owner FK 是 DEFERRABLE INITIALLY DEFERRED),挂起的
  触发事件拦住后续 `ALTER TABLE` —— 换约束前 `SET CONSTRAINTS ALL
  IMMEDIATE` 先把待查触发掉(0045 注释与迁移测试守着)。
- **ORM 槽名缺省取 alias**(`default=lambda ctx: ctx.current_parameters
  .get("alias")`):直接构造 `AuthSession(alias=X)` 的存量调用方零改动。
- **解析分层**(`_slot_tier`):环境命中 > env 空且默认 > env 空 > 默认
  > 首行(id 序);users 注入键 = 槽名(存量 slot=alias → 逐行相同)。
  prepare_exec / dispatch fail-fast 带环境;graph/预检/套件校验暂不带
  (S5 统一解析入口收口)。
- **check_scope** 名字→id 映射切槽名(同槽多绑定取默认行,保守面)。
- **别名 slot 与 credential_alias 由写面同步**(create/patch 同写);
  凭证默认命中取 `coalesce(slot, credential_alias)`。
- **写面**:POST 支持 slot/system/envId/accountFields(应用层
  (owner, alias) 名字唯一保名字缝无歧义;四元组键 DB 权威);PATCH
  支持 system/envId(显式 null 清空)/accountFields/isDefault(同槽清旧
  默认);`POST /auths/{id}/default` 原子切换。
- 前端:Auths 列表槽位/默认/系统·环境展示 + ⋯ 菜单「设为槽默认」;
  api 类型与 setDefault;创建/编辑表单的槽位字段留 S7 配置项页整页
  改造时一并(当前 API 已全支持)。

### 已知留到后续

- `${slot.X.field}` 模板解析与 carry 注入(S4/S5;account_fields 已存取)
- 项目凭证(绑定归属维度 个人/项目):S5 前单独裁定落地
- credential_alias 列删除(S6);Auths 页整页改「槽位绑定」主体(S7)
