# GIMBAL Platform 需求文档 —— 2026-09 迭代批次

| 字段 | 内容 |
|------|------|
| 状态 | 修订稿 v2(2026-09-23 评审:4 项阻断定案;F4 拍板方案 B) |
| 分支 | feat/join-projection-caliber-unification |
| 范围 | gimbal-platform（backend + frontend） |
| 创建日期 | 2026-09-23 |
| 作者 | Codfish |

本文档包含本轮迭代的 5 个需求，按建议实现顺序排列：

1. 资源分发（Resource Handoff）
2. 场景重命名 / 另存为
3. 时间线事件日志化（activity_events）
4. 服务引用改造（服务信息管理接入 + 凭证自动注入）
5. 通知中心（含审计迁移）

需求 2、3 存在写入点复用关系，建议绑定实现；需求 5 依赖较弱，放最后。

---

# Feature 1: 资源分发（Resource Handoff）

## 1.1 背景与问题

当前平台上的场景（Scenario）等资源归属于创建者个人，团队成员之间无法将资源转交或共享给他人。团队协作中常见场景：A 写好一套场景，B 需要在此基础上本地修改；新人接手老场景需要完整复刻一份但不应影响原场景。当前只能手动导出/复制配置，效率低。

**目标**：提供一次性的「给一份副本」能力，让资源可以在用户之间流动，同时保持严格的所有权隔离。

## 1.2 语义定稿

> **分发 = Fork（副本），不是授权（共享访问）**

| 维度 | 行为 |
|------|------|
| 所有权 | 接收后资源归接收方所有，发送方不保留任何控制权 |
| 同步 | 发送方后续修改**不会**同步到接收方副本 |
| 撤回 | **不支持**（副本已独立，撤回无意义） |
| 凭据 | P1 **不随资源迁移**（引用保留但不迁移所有权，见 §1.8.1） |
| 生命周期 | 接收方可随意编辑、删除副本，与发送方完全解耦 |

## 1.3 功能范围（P1）

| 资源类型 | 支持 | 说明 |
|---------|------|------|
| Scenario | ✅ | 含 steps、spec、meta，数据集与运行方案随行 |
| DataSet | ⬜ | P2 |
| Auth Session | ⬜ | P2（凭据语义待定） |
| Constant | ⬜ | 暂不纳入 |

不在范围内：批量分发（多选一次性发给多人）、权限管理（二次分发限制）、常量表分发。

## 1.4 交互设计

### 触发入口
场景列表行操作菜单（`···`）→「分发给…」

### HandoffDialog 流程

```
1. 打开 HandoffDialog
2. 搜索/选择目标用户（GET /api/users/roster 加载成员列表）
3. 点击「确认分发」
4. 前端调用 POST /api/handoff，同步等待响应
5. 成功：弹出结果面板
   ┌─────────────────────────────────────────┐
   │ ✅ 已分发                               │
   │ 场景「order_env」已发送给 Alice         │
   │                                         │
   │ ⚠️ 目标用户已有同名场景，               │
   │    已自动重命名为「order_env (2)」      │
   └─────────────────────────────────────────┘
6. 失败：展示错误信息，可重试
```

### 名称冲突处理
接收方存在同名场景时，自动追加计数后缀（`order_env (2)`、`order_env (3)`…），不在名称中嵌入「来自 XXX」字样，结果面板明确告知发送方重命名情况。

### 「来自 XXX 的分享」悬浮标签

| 属性 | 设计 |
|------|------|
| 显示位置 | 场景列表，资源名称行末（hover/tooltip） |
| 显示条件 | 存在对应的 **unread** `resource_handoff` 通知 |
| 消失时机 | 首次点击进入该场景（前端标记通知已读） |
| 标签内容 | `来自 <发送方昵称> 的分享` |

```sql
-- 依赖 0006 加列(见 §1.6);查询走 0005 已建的 (user_id) 索引,量级足够
SELECT resource_id
FROM   notifications
WHERE  user_id       = :me
  AND  type          = 'resource_handoff'
  AND  resource_type = 'scenario'
  AND  read_at       IS NULL
```

服务端以轻量端点 `GET /api/notifications/handoff-unread` 返回
`[{id, resourceId, senderName}]`(只读未读 resource_handoff);前端以
`Set<scenario_id>` 维护,列表行渲染时 O(1) 查找。销账复用现有
`POST /api/notifications/read`(按通知 id 列表),mark_read 无需扩展。

## 1.5 后端设计

### `POST /api/handoff`

请求(scenario_id 形如 `sc-*`,user id 为 int):
```json
{
  "resource_type": "scenario",
  "resource_id": "sc-order-env",
  "target_user_id": 3
}
```

响应（成功）:
```json
{
  "status": "ok",
  "new_resource_id": "sc-order-env-2",
  "new_name": "order_env (2)",
  "renamed": true
}
```

错误码：403（非资源所有者，或按 §1.8.2 允许 admin 代理）、404（resource_id 不存在）、422（resource_type 不支持 / target_user_id 无效或不存在 / 目标是自己）。

### `GET /api/users/roster`
供 HandoffDialog 成员选择器使用，**新端点**——现有 `GET /api/users` 是
operator+ 可见且返回 role/is_admin 等管理字段，不能降级复用；User 表无
email 列，不为选人器加列。CurrentUser 可调；仅返回 `is_active` 用户、
排除自己；字段 `{id, username, displayName}`；不分页、上限 200，前端本地过滤。

### 处理逻辑

```
POST /api/handoff
    │
    ├─ 鉴权:resource.owner_id == current_user_id OR current_user.role == 'admin' → 否则 403
    ├─ target 校验:存在且 is_active 且 ≠ 发起人,否则 422
    │
    ├─ 冲突检测:target_user 名下是否存在同名 scenario?是 → 自动追加计数后缀
    │   (共享 helper resolve_name_conflict,见 Feature 2 §2.3;name 上限 64,
    │    拼后缀前先截断基名)
    │
    ├─ 调用 copy_scenario(
    │       scenario_id    = resource_id,
    │       new_owner      = target_user.display_name or username,
    │       new_owner_id   = target_user.id,
    │       new_name       = <resolved_name>,      # 见 Feature 2 的另存为扩展
    │       source_meta    = {"sourceScenarioId": resource_id}
    │   )
    │
    ├─ 写入 notifications(type='resource_handoff')      # 悬浮标签数据源
    ├─ 写入 activity_events(kind='scenario.handoff_received')  # 见 Feature 3
    │   (评审裁定:不再写 audit_logs —— notifications + activity_events
    │    双写已够,audit 维持「只记特权写」口径不破例,避免与 §5.3 自相矛盾)
    │
    └─ 返回 {status, new_resource_id, new_name, renamed}
```

> 说明：`copy_scenario` 的 `new_name` 参数由 Feature 2（另存为）引入，分发的冲突后重命名复用同一参数，不重复实现。

### 通知记录结构（`notifications` 表 + 0006 加列）

`notifications` 现有列为 id/user_id/type/title/body/link/batch_id/expires_at/
created_at/read_at，**没有** resource_type/resource_id/payload —— v1 的「零 DDL」
不成立（2026-09-22 分发方案评审同结论），0006 补三个可空列；存量行不受影响。
`payload` 用 JSON 列而非塞 body：悬浮标签要结构化取 sender_name，从 title
字符串抠值太脆。

| 字段 | 值 |
|------|---|
| `type` | `resource_handoff`（**新注册**；已预留的 `resource_transferred`/「资源转让」语义是所有权转移，留给离职处置线，不复用） |
| `resource_type` | `scenario` |
| `resource_id` | 新副本的 scenario_id |
| `user_id` | 接收方 user_id |
| `payload.sender_id` / `sender_name` | 发送方信息 |
| `payload.original_name` | 原始场景名 |
| `read_at` | NULL → 首次进入场景时经 POST /read 按 id 销账 |

类型注册三处（缺一不可）：后端 `NOTIFICATION_TYPES` 元组、前端 `SwitchableType`
联合 + `NOTIFICATION_TYPE_LABELS`（文案「收到分享」）；Profile 偏好页按 labels
全量渲染，自动出现。边界：用户关闭「收到分享」类型 → 通知不入库 → 悬浮标签
同步消失（同一数据源，可接受，写明即可）。

## 1.6 数据与结构影响

> **一处 0006 迁移** —— `composer_scenarios`（copy_scenario 写入）与
> `activity_events`（Feature 3 新增表）之外，`notifications` 加
> `resource_type/resource_id/payload` 三可空列；`service_aliases.base_url`
> （Feature 4 方案 B）并入同一 revision。**影响评估与执行清单见
> `docs/deployment/sqlite-to-pg-migration.md` §8**（存量零触碰、可在线执行、
> 0006 先行/代码后起的硬顺序、时间线冷启动空窗拍板、downgrade 路径）。

## 1.7 安全

| 方面 | 策略 |
|------|------|
| 所有权验证 | 资源 owner 或 admin 可发起分发 |
| 接收方过滤 | 仅支持 roster 内平台注册用户 |
| 凭据隔离 | 副本保留凭据引用但不迁移所有权（见 §1.8.1），执行时按接收方身份解析，无权限时报错但不泄露凭据值 |
| 信息泄露 | `GET /api/users/roster` 仅返回基础标识信息 |

## 1.8 决策点

### 1.8.1 凭据处理
场景 steps 中可能引用 Auth Session（`${auth.<alias>.token}` 模板，见 Feature 4 §4.5）。P1 选择：**保留引用但不迁移所有权**——接收方副本中模板原样保留，执行时按接收方本人的凭证池解析；若接收方无对应别名凭证，执行报错但不泄露发送方凭据值。P2 专项设计凭据随行迁移。

### 1.8.2 管理员代理分发
**允许**——Admin 角色可代替资源 owner 发起分发，后端判断 `resource.owner_id == current_user_id OR current_user.role == 'admin'`。

## 1.9 测试清单

| # | 测试场景 | 预期结果 |
|---|---------|---------|
| T1 | 正常分发：A 发给 B，B 无同名 | 副本创建，名称不变，通知写入 |
| T2 | 冲突分发：B 已有 `order_env` | 副本命名 `order_env (2)` |
| T3 | 二次冲突 | 副本命名 `order_env (3)` |
| T4 | 无权分发：A 尝试分发 C 的场景 | 403 |
| T5 | 目标用户不存在 / 是自己 | 422 |
| T6 | 分发后 B 登录场景列表 | 悬浮标签「来自 A 的分享」出现 |
| T7 | B 点击进入副本场景 | 标签消失（通知标记已读） |
| T8 | 发送方修改原场景 | 副本不受影响 |
| T9 | 副本中含 `${auth.xxx.token}` 引用，接收方无对应凭证 | 执行报错，不泄露凭据值 |
| T10 | 时间线 | B 的时间线出现 `scenario.handoff_received` 事件 |

## 1.10 分期

**P1**：0006 迁移（notifications 三列）、`POST /api/handoff`、`GET /api/users/roster`、`GET /api/notifications/handoff-unread`、冲突检测+计数后缀（共享 helper）、通知写入、activity_events 写入（不写 audit）、HandoffDialog、结果面板、悬浮标签。

**P2**：DataSet 分发、凭据随行策略、Auth Session 分发。

**暂不做**：常量表分发、批量分发、分发撤回。

---

# Feature 2: 场景重命名 / 另存为

## 2.1 背景

用户需要修改已创建场景的名称，或基于当前场景创建一份新命名的独立副本，当前均无入口。

## 2.2 现状代码基础（已核实，均可复用，无需新表）

`composer_scenarios.name` 是 STORED 生成列，源自 `payload.definition.meta.name`：

```python
name: Mapped[str | None] = mapped_column(
    String(64), Computed(json_path_text(payload, *_meta("name")), persisted=True)
)
```

DB 侧不可直写，但 `scenario_store.update()` 早已支持整份 draft 回写，`meta.name` 改动即可生效，生成列自动重算——**重命名无需任何 schema 改动或后端新增接口**。

`scenario_store.copy_scenario()`（挂载于 `POST /{scenario_id}/copy`）已实现深拷贝，包含数据集与运行方案：

```python
for ds in dss:
    ...  # 数据集深拷贝
await scheme_store.copy_schemes(db, scenario_id, new_sid)  # 方案深拷贝
```

当前名称写死为 `f"{meta.get('name')} (副本)"`，不支持自定义名称。

## 2.3 功能设计

### 重命名
- 入口：场景列表/详情页操作菜单「重命名」
- 交互：弹窗输入新名称 → 拉取当前 draft → 仅替换 `meta.name` → 调用现有 `PUT /scenarios/{id}`
- 后端改动：**无**
- 附加：写入 `activity_events(kind='scenario.rename')`（见 Feature 3）

### 另存为
- 入口：场景编辑页操作菜单「另存为」
- 交互：弹窗输入新场景名 → 调用 `POST /{scenario_id}/copy`（扩展后）
- 后端改动：`copy_scenario()` 新增可选参数 `new_name: str | None`；未传时保留现有 `(副本)` 后缀行为（向后兼容）
- 完成后跳转：**打开新副本**，原场景不受影响
- 随行内容：数据集、运行方案（复用现有 copy 逻辑，不新增）
- 附加：写入 `activity_events(kind='scenario.save_as')`，`detail.sourceScenarioId` 记录来源

```python
async def copy_scenario(
    db: AsyncSession,
    scenario_id: str,
    *,
    new_owner: str,
    new_owner_id: int,
    new_name: str | None = None,   # 新增
) -> Scenario:
    ...
    meta["name"] = new_name or f"{meta.get('name') or src.scenario_id} (副本)"
    ...
```

### 重名策略（评审修订：现状**不存在**任何场景重名校验）

v1 T4 所称「既有唯一性校验」不存在——`composer_scenarios.name` 是生成列、
无唯一约束，create/update/copy 全放行重名。本轮**不加 DB 约束**（存量重名
数据会让唯一索引迁移直接失败），改为共享 helper + 三场景策略：

```python
# scenario_store 新增；handoff 与 save_as 共用（一处实现，不各写一份）
async def resolve_name_conflict(db, owner_id, desired_name) -> tuple[str, bool]:
    """该 owner 名下已有同名 → (计数后缀名, True)；否则原样返回。"""
```

| 动作 | 策略 |
|------|------|
| handoff | 静默走 helper，自动 `order_env (2)` |
| 另存为 | 前端 pre-check 弹确认：用后缀名还是自己改名（发起人在场，不静默） |
| 重命名 | **只警告不拦截**（库里躺着历史重名，硬拦会卡死老数据编辑） |

注意 name 上限 64（`ScenarioMeta.name` max_length=64）：拼后缀前先截断基名。

## 2.4 数据与结构影响
零 DDL。`name` 列的生成列机制不变。

## 2.5 测试清单

| # | 场景 | 预期 |
|---|------|------|
| T1 | 重命名场景 | `name` 生成列更新，其余字段不变 |
| T2 | 重命名为空字符串 | 前端/后端校验拦截 |
| T3 | 另存为，不填名称 | 沿用 `(副本)` 后缀（向后兼容） |
| T4 | 另存为，自定义名称 | 副本用自定义名称；与自己已有场景重名 → 前端确认计数后缀或改名（共享 helper，无 DB 约束） |
| T5 | 另存为后跳转 | 打开的是副本，原场景 URL 不变 |
| T6 | 另存为随行 | 数据集、运行方案在副本中完整存在 |
| T7 | 时间线 | 对应 `scenario.rename` / `scenario.save_as` 事件出现 |

---

# Feature 3: 时间线事件日志化（activity_events）

## 3.1 背景与问题

现状 `GET /api/activity` 的 scenario 类事件是从 `composer_scenarios.updated_at` 反推的，不是真正的事件记录：

```python
scen = (await db.execute(
    select(ComposerScenario)
    .where(ComposerScenario.owner_id == user.id, ...)
    .order_by(ComposerScenario.updated_at.desc())
    ...
))
events.append(ActivityEvent(
    kind="scenario", at=iso_naive_utc(srow.updated_at) or "",
    scenarioId=srow.scenario_id, name=srow.name or srow.scenario_id, ...))
```

任何一次保存都显示成同一句「更新场景 X」，结构上无法区分编辑、重命名、另存为、被分发接收。Feature 1（分发）与 Feature 2（重命名/另存为）上线后，这个缺口会更明显——功能做了但时间线看不出差异。

## 3.2 方案选型

**不引入**发布订阅/事件总线（新增消费者注册、异步分发等机制）——平台现有的 `audit_logs`、`notifications` 都是「写路径同步落一条记录」的日志表形态，没有订阅者/分发器。引入完整的 pub/sub 属于新模块，收益与现状复杂度不成比例。

**采用**：新增一张**同构的事件日志表** `activity_events`，写入方式与现有 `audit.record()` 完全对齐（同步、同事务、best-effort 不阻断业务）。

## 3.3 数据结构

```python
class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_actor_created", "actor_id", "created_at"),
        Index("ix_activity_events_resource", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(64))          # scenario.rename / scenario.save_as / scenario.handoff_received / scenario.edit ...
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JsonVar, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=func.now())
```

写入范围**只覆盖 scenario 域**：execution（状态位已足够）、adaptation（批次表状态已足够）维持现有的实时派生查询，不迁移，避免无必要地扩大改动面。

```python
async def record(
    db: AsyncSession, *, actor_id: int | None, kind: str,
    resource_type: str, resource_id: str, detail: dict | None = None,
) -> None:
    """事件落一条记录(best-effort,失败不阻断业务,同 audit.record 口径)。"""
    ...
```

## 3.4 写入点

| kind | 触发位置 | detail |
|------|---------|--------|
| `scenario.edit` | `scenario_store.update()` 常规保存 | — |
| `scenario.rename` | Feature 2 重命名分支 | `{"oldName": ..., "newName": ...}` |
| `scenario.save_as` | `copy_scenario()` | `{"sourceScenarioId": ...}` |
| `scenario.handoff_received` | Feature 1 `POST /api/handoff` 成功后 | `{"senderId": ..., "senderName": ...}` |

两条评审补充：

- **autosave 合并**：CaseComposer 有 2.5s 防抖全量 PUT，`scenario.edit` 若逐次
  落库，持续编辑 10 分钟可产生约 240 条。同资源短窗（5 分钟）内连续 edit
  合并为一条（UPSERT 刷新 created_at），避免时间线被 edit 刷屏。
- **actor_id 语义**：`handoff_received` 的 `actor_id` 填**接收方**（时间线
  归属是"与我相关的事"），发送方进 detail —— 按直觉填发送方就会装反。

## 3.5 与 `notifications` 的关系

**两表各自独立写入，不合并**——分发场景既触发 `notifications`（驱动悬浮标签）又触发 `activity_events`（驱动时间线），职责不同：`notifications` 是「面向接收方的待处理提醒」，有已读/未读状态；`activity_events` 是「资源发生过什么」的只读历史记录，无状态流转。两者数据可能重叠但语义不同，不为省一次写入而混用同一张表。

## 3.6 `/api/activity` 改造

scenario 分支从查询 `ComposerScenario.updated_at` 改为查询 `activity_events`：

```python
try:
    rows = (await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.actor_id == user.id,
               ActivityEvent.resource_type == "scenario")
        .order_by(ActivityEvent.created_at.desc())
        .limit(SCEN_LIMIT)
    )).scalars().all()
    for r in rows:
        events.append(ActivityEvent_out(
            kind=r.kind, at=iso_naive_utc(r.created_at) or "",
            scenarioId=r.resource_id, detail=r.detail))
    sources["scenarios"] = True
except Exception:
    sources["scenarios"] = False
```

前端 `useActivityTimeline.ts` 的 `toTimelineEvent()` 按 `kind` 细分文案（「重命名场景」「另存为场景」「收到分享」「更新场景」）。

## 3.7 数据与结构影响

新增 1 张表 `activity_events`，需要一个 Alembic revision（新建表，双方言语法一致，无需特殊处理）。不改动现有表。

## 3.8 测试清单

| # | 场景 | 预期 |
|---|------|------|
| T1 | 常规编辑保存 | `activity_events` 出现 `scenario.edit` |
| T2 | 重命名 | 出现 `scenario.rename`，detail 含新旧名 |
| T3 | 另存为 | 出现 `scenario.save_as`，detail 含来源 id |
| T4 | 分发接收 | 接收方出现 `scenario.handoff_received` |
| T5 | 写入失败（模拟 DB 异常） | 不阻断主业务操作（best-effort） |
| T6 | `/api/activity` 三源之一失败 | 其余两源正常返回（降级语义不变） |

---

# Feature 4: 服务引用改造

## 4.1 背景

场景编辑页的步骤编辑中，「服务引用」卡片当前只能选目录服务（`fin-server(目录服务)` 形式），无法直接关联服务信息管理中登记的服务别名，导致别名/URL/凭证仍需手动配置。

## 4.2 现状代码基础（2026-09-23 复核修订）

`ServiceAlias` 表（`app/models/service_alias.py:29-55`）：alias_name（PK）/
base_service（**目录服务名，不是 URL**）/group_tag/credential_alias/
owner_user_id（非空=个人默认，空=团队共享）。**表里没有 URL 列**；全平台 URL
只有两个来源：场景 authored `services` 声明（Config 步）+ 执行请求显式绑定；
plate 目录聚合端点（`/api/catalog/services`）只返回 name/system/endpointCount。

服务键→URL 的**唯一组装点**是 `run_materialize.materialize_run_copy` 纯函数
（执行链 `run_dispatcher.py:946` 与导出链 `scenarios.py:189` 共用，黄金等价
测试锁死）：authored 打底 → `_apply_services` 对 steps 引用键做显式绑定 URL
覆盖 → 缺口留给引擎显式报错（RunDialog 并集行提前发现）。「dispatch 阶段
预解析、纯函数物化」的传参模式已有先例（`resolved_auths`、`CarryContext`）。

前端现状：服务引用下拉已是**三来源**（plate 目录 / config.services 声明 /
跨服务置底）+ **内联「+ 为此服务新建别名」已存在**（`CaseComposerCanvas.vue`
的 `confirmAliasCreate`，双写 ①声明 services[alias]=url ②引用
step.api.service）。本 Feature 真正缺的是三件：已登记别名进选项、来源三态
展示、headers 模板注入（此注入确为全新——`_apply_carry` 只写 body，全库
无任何位置写 headers 模板；`${auth.*}` 正则与按执行者本人池解析链已核实）。

命名派生 `derive_base`（别名 `<base>-<suffix>` 切尾杠、base 须落目录集合）
在 `app/services/service_names.py`，是前端 `utils/service-alias.ts` 的后端
移植——**已是两份实现**，base_url 不得再添第三份（见 §4.3 红线）。carry
预解析（`carry_injection.py:106`）靠该约定把步骤服务键解析回 base 服务：
注册表别名的命名必须保持 `<base>-<suffix>` 约定（base_service 须在目录内，
创建时 409 校验已有），否则 carry 面对整步跳过（黄警）。

## 4.3 功能设计（评审拍板：方案 B —— 别名 = 环境级端点默认层）

> 选 B 的理由（2026-09-23）：凭证的一处维护**已由别名表凭证默认实现**
> （P1 服务画像，执行期 `credential_aliases_for` 现查注入）；B 补的是 URL
> 的集中维护——服务器迁移/换端口只在服务信息管理改一处。

### 优先级链（唯一规则，唯一实现点）

```
services[key] = ① 执行请求显式绑定 url          # 最高（RunDialog 现场填）
              > ② 场景 authored 声明（config.services）
              > ③ service_aliases.base_url      # 本轮新增默认层
              > ④ 缺口 → 引擎显式报错            # 兜底不变
```

与凭证默认同款规则形态（「场景显式 > 注册表默认」），不发明新语义。
实现边界（**一处实现，严防多重实现**）：

| 件 | 位置 | 约束 |
|----|------|------|
| 组装规则 | `materialize_run_copy._apply_services` 加第 ③ 层 | 唯一规则实现点；执行/导出两链自动同源 |
| 预解析 helper | `service_aliases.base_urls_for(db, keys)` | 照 `credential_aliases_for` 模式；唯一 DB 查询实现 |
| 两个调用方 | dispatch 阶段 + 导出路由各自预解析后**传参**进纯函数 | 纯函数保持纯（与 resolved_auths/CarryContext 同款）；不在调用方各自拼规则 |
| 前端 | 只**展示**注册表 API 给的 base_url | 红线：前端不做任何 URL 派生/解析（derive_base 双实现的教训） |

### 选中行为

| 动作 | 写入 | 不写 |
|------|------|------|
| 选中**已登记**别名 | `step.api.service = alias_name`；有 credential_alias 则 `Authorization: ${auth.<alias>.token}` **直接写入**（2026-09-23 微调：不做「已有则跳过」的补缺守卫——选中即注入、换选即刷新；既有大小写 Authorization 键先清，保证只有一行） | **不写 services 声明**——写了就成快照，B 的动态性失效；编辑器该键显示「由别名 X 默认提供」 |
| 内联**新建**别名（现状保留） | 双写：声明 services[alias]=url + 引用 | ——（未登记别名没有注册表默认可走） |

### 来源三态展示

「服务引用」更名为「服务」；选项展示 `fin-server(服务名或别名) | 绑定用户名 | 来源`：

| 来源值 | 显示文本 | Tag 颜色 |
|--------|---------|---------|
| 系统自发现（plate 目录） | 系统 | 灰色 |
| config 声明 | 配置 | 蓝色 |
| 服务信息管理 | 已登记 | 绿色 |

「已登记」+ 场景已声明同键 → 显示声明值并标「配置覆盖」；「已登记」展示
`alias_name` 与属主用户名（owner_user_id 非空时）。

### 配套改造

- RunConfigPanel 声明∪引用并集行的「未声明」判定吸收第 ③ 层：注册表命中 →
  显示默认 URL（仍可现场覆盖），不再误报「未声明」。
- ServiceAdmin 表单/详情加 `base_url` 字段。2026-09-23 微调：列名改「URL」，
  登记必填（API 层 `AliasCreate.baseUrl` 缺省 422；编辑表单同样要求非空，
  存量空行触达时补齐；patch 保持可空兼容）；别名输入采用**常驻只读前缀
  槽**——槽恒在（未选服务时占位「服务名」，定宽），输入框永远只写后缀，
  点选服务只换槽内文字（选中态服务名加粗、字号加大）、后续输入框位置零
  跳动；换服务后缀随身、取消选中剥前缀回占位；编辑态槽显该别名自身所属
  服务、后缀只读；保存提交完整全串。
- 黄金等价测试（执行/导出同源）随第 ③ 层加入而更新。
- 别名删除后：引用它的步骤执行报「未知服务」、编辑器黄标。

## 4.4 数据与结构影响
`service_aliases` 加 `base_url String(512) nullable` 一列（并入 0006）。
v1 的「零 DDL」在 base_url 语义下不成立，已按实改；物化链/前端零新增表。

## 4.5 安全
- `credential_alias` 全程不落地 token 明文，只落模板引用
- 执行时按执行者本人凭证池解析（既有机制，见 `auth_references.py` 头部注释：「运行时按执行者本人池解析」）
- 接收方（Feature 1 分发场景）无对应凭证时执行报错，不泄露原凭据值（对应 §1.8.1、§1.9 T9）

## 4.6 测试清单

| # | 场景 | 预期 |
|---|------|------|
| T1 | 下拉选择已登记服务别名 | 写入服务键，来源 tag 显示「已登记」；**不写** services 声明 |
| T2 | 选择带 `credential_alias` 的别名 | headers 自动写入 `Authorization: ${auth.<alias>.token}` |
| T3 | 选择不带 `credential_alias` 的别名 | headers 不写入任何 Authorization |
| T4 | 服务信息管理中更新别名 base_url | 未显式声明的引用场景下次执行生效；显式声明的不受影响；导出物与执行同源 |
| T5 | 来源列三态展示 | 系统/配置/已登记 三种 tag 正确区分 |
| T6 | 已有 headers.Authorization 手工值 | 2026-09-23 微调后：注入**直接写入**该行（旧手工值被 `${auth.*}` 模板替换），大小写变体收敛为一行 |
| T7 | 优先级链 | 同键：绑定 > authored > base_url，三层用例各一；执行与导出同源（黄金等价） |
| T8 | 选中已登记别名后场景被导出/分发 | 导出物含解析后 URL（快照本性）；副本执行同链路解析 |

---

# Feature 5: 通知中心（含审计迁移）

> 2026-09-23 微调：对用户可见命名统一为「通知」（侧边栏条目与页面标题），
> 「通知中心」只作为本方案内的功能代号保留。

## 5.1 背景

当前通知只存在于铃铛弹层（一次拉 30 条、面板内滚动，**无**「查看更多」入口——v1 所称「最多 5 条」与现状不符），无独立通知中心页面；审计查询在 admin 用户管理页（`/admin/users`，`UsersAdmin.vue` + `AuditLogPanel.vue`）的 audit tab，与通知功能割裂，界面风格不统一。

## 5.2 功能设计

### 左侧菜单新增「通知」页
铃铛面板底部新增「查看全部」入口跳转至该页（现状无此入口，一并补）。

### 通知页内两个 tab
| Tab | 可见范围 | 数据来源 |
|-----|---------|---------|
| 通知 | 全部登录用户 | `notifications` 表（现有） |
| 审计 | **仅 admin**（不做用户维度审计，见 §5.3） | `audit_logs` 表（现有，原 Admin 用户管理页下的审计查询原样迁移） |

普通用户进入「通知」页只看到通知 tab，不出现 tab 切换控件；admin 看到两个 tab。

### 设计风格统一
通知（时间线/卡片式）与审计（表格式：操作人/操作类型/资源/时间）两者数据形状不同，不强行用同一组件，但共享色板、间距、字体、空状态设计，保持视觉一致。

## 5.3 决策说明：不做用户维度审计

已核实 `audit_logs` 现状口径：

```python
# audit.py
"""只记特权写——角色变更/删除用户/重置密码/公告/carry 写/适配 ops
应用/别名写;普通读与成员自身常规 CRUD 不记。"""
```

`list_page()` 明确 admin only。普通场景 CRUD 从不进这张表，若开放给普通用户，大多数人这个 tab 常年是空的，价值有限。**本次不扩大审计记录范围**，审计功能维持 admin 专属，仅做界面位置迁移（从 Admin 用户管理页移到通知中心下的子 tab），不改变数据口径。

若后续需要「用户查看自己资源发生过什么」，由 Feature 3 的 `activity_events` 承载（时间线），职责已经分开，无需让审计表承担双重语义。

## 5.4 数据与结构影响
零 DDL。`audit_logs`、`notifications` 表结构不变，仅前端路由/页面结构调整，后端仅需将审计查询接口的挂载路径按需调整（如需要）。

## 5.5 测试清单

| # | 场景 | 预期 |
|---|------|------|
| T1 | 普通用户访问通知页 | 只看到通知列表，无审计 tab |
| T2 | admin 访问通知页 | 看到通知/审计两个 tab |
| T3 | 铃铛「查看更多」 | 跳转到通知页，通知 tab 默认选中 |
| T4 | 审计 tab 内容 | 与原 Admin 用户管理页下的审计查询数据一致 |
| T5 | 非 admin 场景下的审计 tab | tab 不渲染且数据接口 403（页内 tab 无独立路由，守卫落在渲染层 + 后端双层） |

---

# 附录：实现顺序建议

```
Feature 2(重命名/另存为) ─┐
                          ├─→ Feature 3(activity_events) ─→ Feature 1(分发，复用 save_as 的 new_name 与 activity_events 写入点)
Feature 4(服务引用改造，独立)                                        │
                                                                      ▼
                                                          Feature 5(通知中心，纯前端信息架构，最后收尾)
```

Feature 2 与 Feature 3 建议绑定实现（Feature 2 的写入点是 Feature 3 的第一批调用方）；Feature 1 依赖 Feature 2 的 `copy_scenario(new_name=...)` 扩展和 Feature 3 的事件表；Feature 4 技术上独立，可并行——其 `service_aliases.base_url` 与 F1 的 notifications 三列并入同一 0006 迁移，activity_events 新表同批或相邻 revision；PG 上线手动 `alembic upgrade head`（启动只校验不迁移）。Feature 5 最后做，风险最低。

# 追记:全列表页分页批次(2026-09-23 下午,5-Feature 之后追加需求)

需求:所有带列表行的页面统一分页 — 页码点击 / 上一页下一页 / 每页行数 / 跳转,且**按各页自身数据流适配**(服务端信封的真分页 vs 客户端切片)。

## 落地形态

- **组件**:全站唯一分页器 `ui/pagination/Pagination.vue` 补 `showPageSize`(select,候选 `pageSizes`,当前值不在候选时补项防 select 错位)+ `showJump`(输入 + 跳转钮,Enter/点击都行,非法输入静默)+ `v-model:pageSize`。均默认关闭 → 既有调用点(审计面板)行为不变;开启 showPageSize 后**单页也渲染**(否则改不了行数)。
- **服务端分页基建**:`useServerList.pageSize` 定值 → ref + `setPageSize()`(改尺寸回页 1 重拉);`useScenarioListView` 的 `pageSize: LIST_PAGE_SIZE` 定值直传改为透传 ref。
- **新客户端分页**:`useClientPager(rowsGetter, size)` — 全量拉回、前端过滤页共用:切片渲染、行源收缩越界回落末页、改尺寸回页 1。

## 逐页适配(12 处)

| 页面 | 数据流 | 做法 |
|---|---|---|
| 我的/公共场景 | useServerList(20) | 分页器升级 showPageSize+showJump |
| 认证 | useServerList(50) | 同上(候选 [20,50,100,200]) |
| 用户管理 | useServerList(50) 但**从未渲染分页器** | 补上完整分页器(此前第 2 页起用户不可见) |
| 通知 | 后端原 `limit=50` 截断,无 total | **后端升级**:list 加 page/page_size/total(未读优先排序保持);铃铛 `limit:30`→`page:1,pageSize:30`;前端真分页 |
| 执行记录列表 | 固定 `limit:200` 截断 | 改 page/pageSize 下推 + 分页器;越界回末页;轮询刷当前页 |
| 适配中心批次表 | 信封就绪但没传页码 | 传 page/page_size + 分页器 |
| 服务信息别名表 | 全量 200 + 前端过滤 | useClientPager(树/分组筛选后切片) |
| 常量池 | 全量 200 | useClientPager(store 保持全量,编排页常量轨道/重名校验不受影响) |
| 传递默认值 | 整 dict 拉回可编辑 | useClientPager;删行/编辑按全局下标写草稿;`?path=` 深链先跳到命中行所在页 |
| 批次明细 ops | 单 GET 全量 | useClientPager(勾选集按 op.id,跨页保留) |
| 执行详情行级表 | 单页 500 上限 | useClientPager(50/页;store 轮询语义不动) |

**刻意不做的**:关注页(FOLLOW_CAP=20 上限即设计)、ServicesIndex/ServiceGrid(瓦片网格非列表行,且 plate per_page=500 硬截断)、Runner 选场景面板(搜索式选择器)、EndpointBoard(图画布)、场景详情/编排器(单对象文档/编辑器)、Sheet/Drawer 内嵌小表。

## 测试

Pagination 组件 +4 用例(选择器/补项/跳转钳位/未开启不变)、useClientPager 新文件 +4、通知页分页链路 +1(前端)+1(后端信封);适配中心断言补 page 参数。回归:前端 130 文件/1127 测试全绿,vue-tsc 净;后端通知/交接/处置 15/15。

## 追追记:每页行数存后台(2026-09-23 同日追加)

「每页默认条目数」落服务端,不再只活在内存:复用 `/me/preferences` 通用白名单机制(工作台布局/关注常驻/时间线配色同表同护栏,零 DDL)。

- **后端**:`user_preferences.py` 白名单加 `pager.sizes` 键,值 = `{页面slug: 行数}`(slug 1-64 字符、行数 StrictInt 1..500、至多 64 键、整值覆盖、16KB 上限照旧)。StrictInt 是必须的 — 默认 lax 模式会把 `"20"` 强转成 20。
- **前端**:新 `usePagerSize(pageKey, fallback)` 组合式函数,建立在 `useUserPreference` 同步层上 — localStorage 镜像管首帧(不闪)、服务端管跨设备、防抖 PUT、换账号重绑。12 页各拿一个 slug 接入:`useServerList`/`useClientPager` 加可选 `pagerKey` 参数(场景库两页/认证/用户走前者;服务信息/常量池/传递默认值/批次 ops/执行行级表走后者),通知/执行记录列表/适配中心三个手动页直连 `usePagerSize`。slug 清单:`scenarios-mine` `scenarios-public` `auths` `users` `notifications` `executions` `adaptation-batches` `service-admin` `constants-pool` `carry-defaults` `adaptation-ops` `execution-rows`。
- 行为:用户在某页改「每页行数」→ 合并进整值防抖 PUT;服务端回读优先于本机默认,但**手动改过未确认的值不被回读打回**(useUserPreference 既有规则 4)。同键全局单实例 → 12 页共享一次 GET、一发 PUT。
- 测试:后端 test_user_preferences +2(形态拒绝 4 例含 StrictInt、整值覆盖往返);前端 usePagerSize 新文件 5 用例(fallback/镜像首帧/服务端采纳/多页合并/非法值钳回)。回归:前端 131 文件/1132 测试绿 + vue-tsc 净;后端 8/8。
