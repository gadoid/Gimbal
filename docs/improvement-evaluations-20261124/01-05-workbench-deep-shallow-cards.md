# 工作台浅层卡与深层卡：问题与改造建议

> 日期：2026-11-24
> 性质：工作台卡片模型与交互改造
> 状态：仅调研，未实施

## 1. 定义

本次改造的核心不是“再做一种卡片皮肤”，而是统一工作台的资源展示模型：

- **一级维度只有卡片类型**；
- **浅层卡**：罗列对应页面的列表摘要信息；
- **深层卡**：允许用户从该页面选择一条具体数据，展示其详细信息和操作。

因此：

> 1:N 不再表现为 N 张一级卡片，而是“1 个类型卡 + N 条可选数据”。

## 2. 当前实现

### 2.1 静态卡片是类型模型

工作台注册表当前定义：

```ts
interface WorkbenchCardDef {
  id: string
  title: string
  description?: string
  component: () => Promise<Component>
  accent: CardAccent
  defaultSize?: CardSize
  cap?: string
  refreshMs?: number
}
```

证据：[`registry.ts`](../../src/gimbal-platform/frontend/src/components/workbench/registry.ts)。

卡槽只接收类型定义和尺寸，不包含选中资源 ID，见 [`WorkbenchCardSlot.vue:84`](../../src/gimbal-platform/frontend/src/components/workbench/WorkbenchCardSlot.vue#L84)。

### 2.2 集成被动态展开成 N 张类型卡

`WorkbenchView` 拉取全部可见集成任务，然后为每个任务生成：

```ts
id: `fn:${t.id}`
```

这些 `fn:<id>` 被加入卡片市场，相当于每个集成任务都成为一种“卡片类型”，见 [`WorkbenchView.vue:112`](../../src/gimbal-platform/frontend/src/views/WorkbenchView.vue#L112)。

`FunctionCard` 再从 `def.id` 解析任务 ID，并固定每 30 秒轮询，见 [`FunctionCard.vue:179`](../../src/gimbal-platform/frontend/src/components/workbench/FunctionCard.vue#L179)。

### 2.3 布局只保存类型 ID 和尺寸

当前布局结构为：

```ts
{
  order: string[],
  sizes: Record<string, CardSize>
}
```

并且对 `fn:` 前缀做特殊兼容，见 [`layout.ts:32`](../../src/gimbal-platform/frontend/src/components/workbench/layout.ts#L32)、[`layout.ts:45`](../../src/gimbal-platform/frontend/src/components/workbench/layout.ts#L45)。

布局中没有“选中了哪个资源”和“当前是浅层还是深层”的状态。

## 3. 当前问题

- 集成任务越多，卡片市场越膨胀；
- 同一资源类型被重复注册成多个类型 ID；
- 切换关注对象必须删卡、加卡，布局语义不稳定；
- 尺寸和排序绑定实例 ID，而不是卡片类型；
-  Credential、Project 等 1:N 资源没有统一的“选一项展示”组件；
- 动态卡轮询和错误状态各自实现，难以复用；
- 旧 `fn:` 特殊逻辑已经进入布局持久化和占位卡逻辑，继续扩展会加重兼容负担。

## 4. 建议的数据模型

### 4.1 卡片实例

建议布局保存：

```ts
interface WorkbenchCardInstance {
  id: string
  type: string
  mode: 'shallow' | 'deep'
  selectedId?: string
  size: CardSize
}
```

其中：

- `id`：稳定的卡片实例 ID；
- `type`：注册表中的卡片类型；
- `mode`：浅层或深层；
- `selectedId`：深层模式选中的资源；
- `size`：现有 S/M/L 尺寸。

同一类型默认只启用一张。用户切换对象时只改 `selectedId`，不新增卡片。

### 4.2 类型定义扩展

类型定义增加可选能力：

```ts
interface WorkbenchCardDef {
  id: string
  title: string
  supportsDeep?: boolean
  listLoader?: CardListLoader
  detailLoader?: CardDetailLoader
  component: () => Promise<Component>
}
```

具体加载器可以由独立组件提供，不强制所有静态卡都实现深层模式。

## 5. 浅层卡

浅层卡用于快速浏览，建议展示：

- 对应页面的列表摘要；
- 名称、状态、时间等关键列；
- 总数或筛选计数；
- 可选搜索；
- “查看全部”深链；
- 点击某项进入详情，或在深层模式下选中该项。

浅层卡不复制完整管理页，只复用现有列表 API 和列表语义。

## 6. 深层卡

深层卡用于持续关注一个对象，建议展示：

- 当前选中项名称和类型；
- 该项的详细状态、指标或关键字段；
- 允许的操作；
- 切换对象入口；
- 加载、空、无权限、已删除和加载失败状态。

交互流程：

1. 用户添加类型卡，默认进入浅层；
2. 点击“深入查看”或选择某项；
3. 卡片切换为深层，弹出同源列表选择器；
4. 选中后加载详情；
5. 切换对象只更新当前卡片；
6. 可随时切回浅层，选中项保留。

## 7. 推荐适用场景

| 类型 | 浅层卡 | 深层卡 |
|---|---|---|
| 集成任务 | 任务列表、状态、下次触发 | 单个任务状态、输出、执行/暂停 |
| 凭证 | 账户列表、系统、环境、状态 | 单个账户脱敏详情、拨测、编辑入口 |
| 项目 | 项目列表、角色、资源计数 | 单个项目摘要、成员/环境/执行概况 |
| 场景 | 场景列表、模块、优先级、最近执行 | 单个场景状态、方案、最近执行 |
| 执行记录 | 最近执行列表 | 单次执行详情入口和实时状态 |

纯计数卡、固定说明卡和全局汇总卡不必强行支持深层模式。

## 8. 组件与数据复用

- 列表选择器复用各页面现有列表 API；
- 详情展示复用现有详情组件或明确的数据投影；
- 不在工作台建立第二份凭证、项目或集成数据源；
- 深层卡不展示凭证明文；
- 列表和详情都必须经过与页面相同的权限过滤；
- 已删除、已移出项目或已失去权限的资源显示不可用状态，不继续展示旧详情。

## 9. 布局迁移

现有 `fn:<id>` 布局不应静默合并成一张集成卡，因为用户可能有意保留多个任务。

建议：

- 新布局使用新的实例结构；
- 旧 `fn:<id>` 卡继续兼容显示；
- 提供显式“合并为集成类型卡”操作；
- 合并时展示将保留哪个选中项，以及哪些重复卡会被移除；
- 用户确认后再写回布局；
- 不做无人确认的批量数据改写。

## 10. 实施顺序

1. 先实现浅层/深层的通用卡槽状态和选择器；
2. 以集成任务作为第一个完整样板；
3. 再接入凭证或项目；
4. 最后扩展其他 1:N 资源；
5. 完成旧 `fn:` 布局的显式迁移。

不建议一次性改造全部卡片类型。

## 11. 验收标准

- 添加卡片时，同一类型只出现一次；
- N 条集成数据不再生成 N 个一级卡片类型；
- 浅层卡展示对应页面列表摘要；
- 深层卡可从同源列表选择一条数据；
- 切换对象不新增、删除或重排卡片；
- 深层选中项在刷新和跨设备后保留；
- 切回浅层不丢失选中项；
- 卡片权限与来源页面一致；
- 凭证明文不会出现在任何卡片状态；
- 资源删除、移出项目或失去权限后有明确降级状态；
- 旧布局不会被静默合并或覆盖。
