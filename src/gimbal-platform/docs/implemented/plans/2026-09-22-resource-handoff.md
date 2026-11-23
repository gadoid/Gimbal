# 资源分发(Handoff)设计方案 — v2(评审拍板版)

> **用途**:用户隔离下的点对点资源分发能力。沉淀 2026-09-22 两轮评审:
> 语义裁定(交接 = fork 副本)→ 范围确认 → v2 补丁评审(冲突策略/接收
> 侧标签)→ 三项拍板:**只做场景分享(常量移除)**、**标签走 B 线
> (0006 加列)**、执行记录维持硬隔离。
> **状态**:已拍板待实施。**配套**:权限域语义见
> `用户权限与用户管理-设计方案`;读侧基础见
> `2026-09-22-join-projection-and-caliber-unification.md`(已实施)。

---

## 0. 背景与问题

用户隔离把资源锁在 owner 名下后,协作只剩两条路,各有硬伤:

* **public 中转**:A 发布公共 → B 复制自取 → A 忘记下架,公共库被当
  传输介质,越来越臃肿;且 B 拿到的是 fork,A 修复后 B 跑旧版。
* **admin 越权代看**:不可持续,也不解决"B 要自己跑/自己改"。

需求陈述(评审原话):一个人想用另一个人写的用例执行,或**基于该版本
再做调整**;分发即交接,受让人获得归自己的副本。

## 1. 语义定稿:分享 = 交接(fork 副本),不是授权(live-link)

* 分享的语义是"我基于这个版本再做调整"——受让人要一份归自己的副本,
  漂移是本意;
* "只读跑一次"不需要分享概念;高频"非 owner 直接执行"若成需求,
  另立运行授权,不与分发捆绑;
* 不做授权表、不做 TTL、不做共享状态管理:发起方分完即无后续负担,
  接收方落地即 owner。

对照被否掉的方案(取舍记录):

| 方案 | 否因 |
|---|---|
| `scenario_shares` 授权表 + 谓词扩展 + TTL | 解决"共享维护一份",非本需求 |
| 公共场景直接执行(放开 run 闸) | 要连带放宽数据集读闸,推翻已评审的跨用户泄露收紧 |
| ~~常量同名计数后缀自动重命名(v2 补丁一)~~ | 随常量整体移除而失效;且核出常量**不可改名**(`ConstantEntryPatchIn` 无 name),归一路径断裂 |

## 2. 范围矩阵(v2 拍板版)

| 资源 | 结论 | 说明 |
|---|---|---|
| **场景(含全部数据集 + 方案)** | **一期做(唯一)** | `copy_scenario` 深拷;副本 private 归受让人;meta 记 `sourceScenarioId` 溯源;**场景名无唯一约束,恒原名落地,无冲突面** |
| ~~常量池条目~~ | **移除(二轮拍板)** | 核出两个硬伤:① 名字与 `${var.<name>}` 插入模板耦合(`ConstantPoolPanel.vue:70`),改名副本破坏模板语义;② 常量不可改名(PATCH 无 name),"落地后归一"路径断裂。若未来需要共享常量 → 另立**全局常量层**概念(operator/admin 维护、全员只读、解析序 个人 > 全局,镜像 carry 三层链先例),不走分发 |
| 凭证(auth_sessions) | **二期,单独拍板** | 密文整行复制 = 给用不给看;但"任意用户可转账号使用权"是安全姿势变化,一期跑通后再拍 允许/永不 |
| 执行记录 | **不做** | §5.1 硬隔离,admin 也无旁路(已核实 `get_owned_execution` 无 admin 分支且 404/403 合并);要给人看用导出快照 |
| board 卡 / 服务画像 | 无需 | 本就全局可读 |
| carry 值表 / 服务别名 | 不属此列 | 全局技术资产(operator+),本身是共享层 |
| ~~查询视图~~ | 勘误移除(一轮) | plate 侧共享目录代理,非用户隔离资源 |

## 3. 交互设计

发起方(Alice 分发场景给 Bob/Carol):

1. **入口**:场景库列表行操作菜单"分发…"(与 发布/复制/删除 同级,
   详情页头部同给)。**仅场景有此入口。**
2. **分发对话框**(统一 `HandoffDialog`):
   * 上半资源摘要:场景名 + "含 N 数据集 · M 方案";
   * 选人:前缀实时搜索(名册端点),多选 chip;
   * 留言(可选,≤200 字,进接收方通知正文);
   * 确认按钮带计数:"分发给 N 人"。
3. **提交与逐人结果**(同步单请求,原地翻成结果面板):
   ```
   ✓ 张三  已分发(新场景 sc-order-main-copy-a1b2)
   ✗ 李四  失败:账号已注销
   ```
   **只有 ✓/✗ 两态**——场景名无唯一约束,不存在同名冲突,没有 ⚠ 跳过;
   单人失败不影响他人(逐人独立提交)。
4. Alice 到此为止:原件不动,无共享状态;再分发重复一次即可(新副本
   新 id `-copy-<hex>`)。

接收方(Bob):

1. **站内通知**:"Alice 分发给你场景《下单主链路》(含 3 数据集、
   2 方案)"+ 留言,深链直达;
2. **列表来源标签(v2 补丁二,B 线)**:副本落地后,场景库列表行显示
   轻量 chip「**来自 Alice 的分享**」;**首次进入该场景详情(含深链
   直达)即标记通知已读,标签消失**;再次返回列表不再出现。标签状态
   在服务端通知表,跨设备一致。
3. 副本归 Bob 所有:改/跑/配方案一切如常;列表行与详情页带"分叉自
   sc-order-main"溯源标记(`meta.sourceScenarioId`);
4. **级联自然成立**:Bob 可把改好的副本再分发给 Carol。

边界:不带走执行历史;不带凭证(二期前,依赖凭证时首跑见既有引导);
副本恒 private,发布与否 Bob 自定。

## 4. 后端设计

### 4.1 接口

```
POST /api/handoff
{ "resource_type": "scenario",            // 二期 + "auth_session"
  "resource_id": "sc-order-main",
  "target_user_ids": [2, 3, 5],
  "message": "…" }                         // 可选
→ 200 { "results": [
    {"user_id": 2, "user_name": "张三", "status": "delivered",
     "new_resource_id": "sc-order-main-copy-a1b2"},
    {"user_id": 5, "user_name": "李四", "status": "failed",
     "detail": "账号已注销"} ] }
```

* 状态只有 `delivered` / `failed`(无 skipped——无冲突面);
* 发起权限 = 资源 owner,admin 可代发(与 `ensure_owner` 口径一致);
  非 owner 403、不存在 404;目标含发起人 → 422;
* 逐人独立提交:一人失败不回滚他人(分发是幂等可重试的独立副本,
  不值得整批原子)。

### 4.2 Adapter 契约

| adapter | 实现 | 冲突面 |
|---|---|---|
| scenario | `copy_scenario(scenario_id, new_owner, new_owner_id, *, source=…)`:现函数已参数化 owner,加 `meta.sourceScenarioId = 原 id` | **无**(副本恒新 id;场景名无唯一约束,原名落地) |
| auth_session(二期) | 密文原样拷行(FERNET_KEY 全局同钥)、owner 切换 | `uq_auth_owner_alias` 同 alias → 拍板后定(届时用计数后缀则需先给 PATCH 加 name) |

### 4.3 名册端点(member 可用,解决选人)

```
GET /api/users/roster?q=张   → { items: [{id, display_name, username}] }
```

`CurrentUser`;前缀匹配;上限 20;不回其他字段。枚举面增量 ≈ 0
(display_name/username 本就在台账对全员可见)。

### 4.4 通知与接收侧标签(B 线:0006 加列)

**0006 migration**:`notifications` 加三个可空列,仅 handoff 行填充,
既有查询/响应零影响:

```sql
ALTER TABLE notifications ADD COLUMN resource_type VARCHAR(32);
ALTER TABLE notifications ADD COLUMN resource_id    VARCHAR(128);
ALTER TABLE notifications ADD COLUMN sender_name    VARCHAR(128);
```

models `Notification` 同步;创建 handoff 通知时填 `resource_type/
resource_id/sender_name`(title/link 语义不变,深链照发)。

**标签实现**(列表加载一次批量查询,`dataset_counts` 先例,无 N+1):

```sql
SELECT resource_id, sender_name, array_agg(id) AS notif_ids
FROM   notifications
WHERE  user_id = :me AND type = 'resource_handoff'
  AND  resource_type = 'scenario' AND read_at IS NULL
GROUP  BY resource_id, sender_name
```

* 同一资源多条未读 → **取最新 sender** 作标签文案,聚合全部 id;
* 详情页进入(含深链)→ 前端对聚合的 ids 调 **`POST /api/notifications/
  read` body `{ids}`**(既有批量接口——注意**不是** v2 补丁原文写的
  `PATCH /:id/read`,勘误)→ 标签全消;
* 已读耦合语义(拍板记录):进入详情即消铃铛未读数——"看过资源 =
  通知已处理",刻意行为;
* **勘误记录**:v2 补丁原文的 SQL 直接引用了 `resource_type` 等列并
  声称"零 DDL"——当时表里没有这些列,方案不成立;B 线以 0006 落列
  修正。勿照抄补丁原文。

### 4.5 审计

`audit_logs` 记 `action="handoff"`,`detail = {resource_type,
resource_id, targets, results 摘要}`——"谁把什么分给了谁"全链路可查。

## 5. 数据与结构影响

* **一个 0006 migration**(notifications 三可空列,B 线拍板理由:恰在
  迁移后表结构确认期,接受字段变更;换干净的资源寻址,不做 link 字符串
  解析);其余**零 DDL**;
* 副本即普通行;溯源进 payload.meta(无新列);
* 权限谓词、可见性模型、§5.1 全部不动;
* 与 0005/交互字段轮无依赖,可独立上线、独立回滚(代码回退 + 0006
  downgrade)。

## 6. 安全口径

* 名册枚举面增量 ≈ 0;分发不含凭证期间,账号共享仍只有 operator 的
  carry/别名一条正路;
* 无共享状态 = 无授权悬挂风险面;全链路审计;403/404 口径与
  `_ownership` 一致。

## 7. 决策点(拍板记录)

1. **只做场景分享,常量移除**(2026-09-22 二轮):硬伤为 name-模板
   耦合 + 不可改名;共享常量的真实需求若出现 → 独立立项"全局常量层"。
2. **标签走 B 线(0006 加列)**:迁移后表结构确认期,接受字段变更;
   否掉 A 线(link/title 字符串解析 = 双口径)。
3. **凭证二期**:一期跑通后再拍 允许/永不。
4. **admin 可代发他人资源**:允许(与 `ensure_owner` admin bypass
   同口径)。
5. **副本命名保持原名**(id 带 `-copy-<hex>` 区分),与 copy 先例一致。
6. **留言上限 200 字**。
7. **已读耦合**:进详情即标记通知已读、消标签与铃铛未读,刻意行为。

## 8. 测试清单

* handoff 主线:delivered / failed(目标注销)/ 多目标混合互不污染 /
  逐人独立提交;
* 权限:非 owner 403、不存在 404、admin 代发 ✓、目标含自己 422;
* 场景深拷完整性:数据集/方案随拷、`sourceScenarioId` 落 meta、副本
  private、原名落地;
* 通知:逐人送达 + 深链 + 留言;0006 三列正确填充;
* 标签(B 线):分发落地后列表标签可见且 sender 正确;首次进详情
  (含深链)标签消失,返回列表不再现;跨设备已读一致;同一资源多条
  未读 dedupe 取最新 sender、一次已读全消;非 handoff 通知不影响;
* 级联:Bob 再发给 Carol;名册前缀搜索与上限;
* 前端:对话框两态(选择/结果)、入口菜单项、溯源标记、标签 chip。

## 9. 分期

* **一期**:handoff 服务 + 场景 adapter + 名册端点 + 0006(三列)+
  通知/审计 + `HandoffDialog` + 列表来源标签;
* **二期**:凭证 adapter(决策点 3 拍板后;若需计数后缀,先给凭证
  PATCH 补 name 字段);
* **缓议**:执行记录只读分享(动 §5.1,须独立评审);全局常量层
  (决策点 1 的后续可能形态)。
