# 导航壳层统一：问题与改造建议

> 日期：2026-11-24
> 性质：产品与前端壳层改造建议
> 状态：仅调研，未实施

## 1. 结论

建议统一全局顶栏，但不建议所有页面机械地保留“左侧栏 + 顶栏”。

目标模型为：

- 普通业务页：**左侧栏 + 全局顶栏**；
- 场景编排、方案工作台等专注编辑页：**仅全局顶栏**，释放画布宽度；
- 未认证页面：不显示导航壳层。

这样既解决普通页面缺少全局导航的问题，也保留编辑流的专注模式。

## 2. 当前实现

当前 `App.vue` 有三态壳层：

| 状态 | 触发条件 | 当前表现 |
|---|---|---|
| 未认证 | `auth.isAuthenticated=false` | 裸 `RouterView` |
| `collapsed` | 路由 `meta.chromeMode='collapsed'` | 仅 48px 顶栏 |
| `full` | 默认 | 仅左侧栏 |

证据：[`App.vue:16`](../../src/gimbal-platform/frontend/src/App.vue#L16)、[`App.vue:27`](../../src/gimbal-platform/frontend/src/App.vue#L27)、[`App.vue:58`](../../src/gimbal-platform/frontend/src/App.vue#L58)。

`collapsed` 目前覆盖五类路由：

- `/composer/:scenarioId`；
- `/scenarios/:scenarioId/schemes`；
- `/scenarios/:scenarioId/assertions`；
- `/constants`；
- `/change-password`。

证据：[`router/index.ts:49`](../../src/gimbal-platform/frontend/src/router/index.ts#L49)、[`router/index.ts:75`](../../src/gimbal-platform/frontend/src/router/index.ts#L75)、[`router/index.ts:120`](../../src/gimbal-platform/frontend/src/router/index.ts#L120)、[`router/index.ts:177`](../../src/gimbal-platform/frontend/src/router/index.ts#L177)。

场景编排器在全局壳层之外，还有自己的操作顶栏、步骤条和底部导航，见 [`CaseComposer.vue:17`](../../src/gimbal-platform/frontend/src/views/CaseComposer.vue#L17)、[`CaseComposer.vue:109`](../../src/gimbal-platform/frontend/src/views/CaseComposer.vue#L109)。

## 3. 当前问题

### 3.1 普通页与编辑页使用两套割裂的全局导航

普通页只有侧栏，编辑页只有顶栏。用户切换页面时，品牌、用户信息、主题切换和返回路径的位置会发生变化。

这不是单纯的视觉不一致，而是全局导航心智不统一。

### 3.2 顶栏面包屑只覆盖编辑流

`CollapsedTopbar` 目前只处理编排、方案、断言和常量池，见 [`CollapsedTopbar.vue:63`](../../src/gimbal-platform/frontend/src/components/chrome/CollapsedTopbar.vue#L63)。

普通业务页没有全局面包屑，项目、资源、详情之间的层级关系主要依赖页面自身标题和返回按钮。

### 3.3 品牌、用户和主题控件存在重复设计

侧栏已经包含品牌、主题切换和用户信息，见 [`Sidebar.vue:17`](../../src/gimbal-platform/frontend/src/components/chrome/Sidebar.vue#L17)、[`Sidebar.vue:103`](../../src/gimbal-platform/frontend/src/components/chrome/Sidebar.vue#L103)。

如果直接给所有页面叠加顶栏，而不重新分配职责，会出现两套品牌、用户和主题入口。

### 3.4 页面标题与全局导航容易混淆

`ListPage` 的标题、说明和操作区属于内容页，不是全局导航，见 [`ListPage.vue:10`](../../src/gimbal-platform/frontend/src/layouts/ListPage.vue#L10)。

改造时不能把页面标题、筛选和业务操作全部搬进顶栏，否则顶栏会变成第二个不稳定的页头。

### 3.5 现有测试锁定旧壳层

`App.test.ts` 明确验证“full 只有侧栏、collapsed 只有顶栏”；路由元信息测试也钉住当前五条 `collapsed` 路由。

壳层改造必须同步更新这些测试，不能只改组件。

## 4. 建议的目标模型

### 4.1 路由元信息

建议将现有二值语义改为：

| 模式 | 左侧栏 | 全局顶栏 | 适用页面 |
|---|---|---|---|
| `full` | 有 | 有 | 工作台、项目、场景库、凭证、集成、执行等 |
| `focused` | 无 | 有 | 编排器、方案工作台、断言注册表、常量池、强制改密 |
| 未认证 | 无 | 无 | 登录、注册 |

是否保留 `collapsed` 名称是次要问题，关键是明确“隐藏侧栏”而不是“用顶栏替代整个壳层”。

### 4.2 全局顶栏职责

顶栏只承载跨页面稳定信息：

- 品牌或返回工作台入口；
- 全局面包屑；
- 当前用户；
- 主题切换；
- 后续确有需要时再增加全局通知或搜索。

页面标题、业务操作、筛选和保存状态继续留在内容区。

### 4.3 左侧栏职责

侧栏保留一级导航、分组、能力门和折叠状态。

品牌入口应只保留一处。普通页面建议由顶栏承担品牌，侧栏顶部改为导航起点或折叠控件，避免重复。

### 4.4 内容区偏移

当前普通内容区通过侧栏宽度设置 `margin-left`，编辑内容区通过 `pt-12` 让位顶栏，见 [`App.vue:27`](../../src/gimbal-platform/frontend/src/App.vue#L27)。

统一后建议：

- 顶栏高度成为单一壳层变量；
- 侧栏宽度继续独立控制；
- 页面内部不再各自猜顶栏高度；
- `ListPage`、编排器等只消费壳层提供的空间，不重复补偿。

## 5. 改造边界

建议改造顺序：

1. 先抽出不依赖侧栏的全局顶栏；
2. 扩展面包屑数据源，覆盖项目、资源列表和详情；
3. 普通页接入“侧栏 + 顶栏”；
4. 编辑流改为“仅顶栏”，保留现有专注布局；
5. 删除侧栏与顶栏之间重复的品牌、用户或主题入口；
6. 更新路由元信息测试、壳层测试和关键页面偏移测试。

不建议在同一轮同时重做侧栏信息架构、页面标题体系和移动端导航，否则改动面会失控。

## 6. 验收标准

- 所有认证页面都有同一位置、同一高度的全局顶栏；
- 普通业务页同时有侧栏和顶栏；
- 专注编辑页没有侧栏，且画布可用宽度不因改造缩小；
- 品牌、用户和主题入口不重复；
- 全局面包屑能回到项目、列表或工作台，不制造死路；
- 页面标题和业务操作仍属于内容区；
- 侧栏折叠时顶栏和内容区同步让位；
- 登录页不出现认证导航；
- 现有路由守卫、能力门和强制改密逻辑不退化。

## 7. 主要风险

- **顶栏面包屑爆炸**：不要为所有页面手写长链，优先使用路由和资源上下文生成。
- **重复补偿**：必须移除页面内旧的顶栏间距假设，避免出现双重空白。
- **编辑流宽度回退**：专注页不能为了形式一致重新引入侧栏。
- **视觉与交互同时变化**：先统一壳层职责，再处理细节样式，便于回归定位。
