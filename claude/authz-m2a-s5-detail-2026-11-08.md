# M2a S5 唯一解析入口 — 实施细化(2026-11-08)

- 依据:`authz-m2a-plan-2026-11-07.md` §二 S5 行、§三 S5、裁定 D4
- 基线:`feat/authz-m1` @ `5e5da425`(S4 收口);**纯代码,无迁移**
- 前提修正:N1 归一(2026-11-01)后 `prepare_exec` **已是**唯一装载入口
  (执行/集成/导出/预检四调用方全部经由它或其子函数)——S5 的实际增量
  是「读面统一 + 来源于标注 + 失败即中止 + 指纹收口」,不是再造一个入口。

## 一、交付物

1. **槽位取用单源**:`run_prepare.pick_bindings(db, owner, slots, env)`
   ——分层取行(不解密);`resolve_exec_auths` 改调它(同一份 tier 裁决)。
2. **`resolve_effective_config`**(run_prepare):组合环境/地址/槽位绑定/
   carry,逐值带来源(地址:binding_url/authored/deployment/alias;绑定:
   bindingId+system+envId;carry:作用域+键层级),**只读**、复用与执行
   同一份子构建器(不另立解析规则,结构上不可能漂移)。
3. **生效预览端点** `POST /api/runs/preview`(读闸 = can_read_scenario_row;
   响应不含任何明文凭证)。
4. **指纹纳入槽位绑定**(D4):`projection["slot_bindings"]` = 别名默认
   命中集合的 取用绑定 id,按**模板属主池**算 —— 保持「同一模板全订阅
   者同一指纹」不变量(按持有人算会破坏它;此收窄与模板环境同口径,
   记录于实施记录)。上线 = 一次性全员暂停(计划已预告)。
5. **预检失败即中止**:dispatch_target 在注入清单解不到(执行人池缺槽
   位)→ 409 `auth_aliases_missing` 整单拒发(此前告警继续、执行期步骤
   级报错)。预检端点形态不变(其告警即硬失败预告)。
6. **adhoc 地址切统一链**:`check_addresses` 改走 `base_urls_for(env=)`
   (S2 留的旧③退役;环境 = 偏好/默认)。
7. **F5 修复**:编排页 carry 提示补别名键层(carry-hint + Canvas 传
   raw 键)。
8. **全等测试**:同一输入跑 执行物化 / 预览 / 预检 / 指纹要素,断言
   地址集、槽位集、carry 值一致。

## 二、子切片

- S5.0 pick_bindings 单源 + 指纹 slot_bindings + 全等测试(执行/指纹)
- S5.1 resolve_effective_config + POST /runs/preview + adhoc 统一 + 全等(预览/预检)
- S5.2 dispatch 缺槽拒单(相关过期用例改写)
- S5.3 F5 前端修复 + 前端四门
- 收口:全量 + 推送(无迁移,dev 只需重启)

## 三、不在 S5
- exclusive 系统同账号约束(需先有独占性数据模型,未在任何切片落地;
  指纹/预览结构已为其预留扩展位)
- 项目凭证归属维度(裁定落点仍开放)

---

## 四、实施记录(2026-11-08)

| 子片 | 交付 | 证据 |
|---|---|---|
| S5.0 | pick_bindings 单源 + ResolvedAuth.binding_id + 指纹 slot_bindings | 集成/订阅 37 例绿 |
| S5.1 | resolve_effective_config + POST /runs/preview + adhoc 统一 | test_authz_s50 3 例 |
| S5.2 | dispatch 缺槽拒单(auth_aliases_missing 409) | 新正测 + 4 处存量改写 |
| S5.3 | F5 别名键覆盖层(carry-hint + Canvas) | carry-hint 8 例 + 四门 |

落地要点:

- **影子比对的落地形态**:N1 归一后四个调用方已同源;「新旧并算」在结构上
  退化为「预览/执行复用同一份子构建器」+ 全等测试(test_authz_s50:
  预览地址/绑定/carry ↔ 执行物化逐值相等;缺槽预览如实报 ↔ 派发拒发)。
- **指纹 slot_bindings 口径(收窄,有意为之)**:只含**别名默认命中**
  集合的取用绑定 id、按**模板属主池**算 —— 保持「同一模板全订阅者同一
  指纹」不变量(按持有人池算会破坏它);绑定 authAlias 的身份已由方案
  投影覆盖。上线即一次性全员暂停(计划已预告)。
- **失败即中止**:dispatch_target 在注入清单算出后用 pick_bindings 查
  执行人池,缺槽 → 409 auth_aliases_missing(带槽名清单);adhoc/图/集成
  链原有 strict 语义不动。
- **adhoc 地址统一**:check_addresses 改 base_urls_for(env=偏好/默认
  环境),S2 影子期的「adhoc 只读别名 base_url」退役。
- **预览端点**:POST /api/runs/preview(PrincipalIn;读闸
  can_read_scenario_row;响应无明文)。exclusive 系统同账号约束未建模
  (§三),结构已留扩展位。
