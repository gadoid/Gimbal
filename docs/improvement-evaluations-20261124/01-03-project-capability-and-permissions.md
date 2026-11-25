# 项目能力对齐与权限隔离：问题与改造建议

> 日期：2026-11-24
> 性质：能力矩阵、真实缺陷与收口顺序
> 状态：仅调研，未实施
> **状态追记（2026-11-25）**：§4.1 / §4.2 两缺陷**已修复落地**
> （提交 `f5982dad` / `c0cc35d2`，known-issues 三记录）；§5 缺口留拍板。
> 当前进度索引见本目录 README。

## 1. 结论

项目尚未完整继承个人/私有资源的能力。

当前项目已经具备团队治理、项目凭证、项目令牌、加入审批和核心资源协作骨架，但以下能力仍不完整：

- 套件非创建者的能力投影错误，并存在必然失败的复制入口；
- 项目场景的导出、发布、删除、导入等操作没有完整前端通路；
- 项目集成只有列表、执行和详情，没有项目内创建与常规管理闭环；
- 项目执行配置后端完整，但前端已撤下；
- 普通项目报告定义尚未实现。

此外，集成模板 owner 仍存在绕过当前项目成员关系的权限缺陷。

## 2. 评估口径

本文件判断“能力是否支持”的标准是：

> 项目成员能否从项目入口或项目资源详情完成同一业务闭环，而不是只在项目列表看到该资源。

据此分为：

- **完整**：项目上下文内有完整入口和闭环；
- **部分支持**：核心操作可用，但仍有入口或能力缺口；
- **前端未接通**：后端支持，前端无法维护；
- **未实现**：普通项目没有对应模型或 API；
- **设计上不适用**：该能力本来就不应成为项目独立资源。

## 3. 能力矩阵

| 能力 | 私有/个人当前能力 | 项目现状 | 判定 |
|---|---|---|---|
| 项目本身 | 不适用 | 列表、详情、新建、编辑、默认环境、删除 | 完整 |
| 成员与角色 | 不适用 | 添加、移除、三级角色、末位管理员保护、CSV 导出 | 完整，项目特有增强 |
| 项目令牌 | 个人访问令牌是另一体系 | 签发、范围、续期、重生成、吊销、回调、负责人换绑 | 完整，项目特有增强 |
| 加入申请 | 私有资源可申请加入项目 | 分析、申请、审批、冲突处理、撤回 | 完整，项目特有增强 |
| 项目凭证 | 个人池 CRUD、默认、拨测 | 独立项目池 CRUD、默认、拨测 | 完整 |
| 场景 | 新建、编辑、重命名、导出、发布、下架、复制、删除、执行 | 项目内新建、列表、查看、执行、复制；编辑和方案可进详情；导出/发布/删除无项目入口，导入不支持项目目标 | 部分支持 |
| 执行方案 | 新建、编辑、复制派生、删除、运行参数 | 随父场景完整支持，入口在方案工作台 | 能力完整，不在项目页平铺 |
| 数据集 | 新建、编辑、导入导出、删除 | 随父场景完整支持，入口在方案工作台 | 能力完整，不在项目页平铺 |
| 套件 | 新建、编排、运行、历史、复制、发布、下架、删除 | 项目内新建、列表、快速执行；非 owner 详情能力位错误，复制入口失败 | 有明确缺陷 |
| 集成任务 | 新建、查看、执行、订阅、暂停、恢复、退订、删除 | 项目列表、执行、详情；项目创建和常规编辑未接通 | 部分支持 |
| 执行配置 | 完整个人配置前端 | 后端支持项目 scope，项目配置页已撤下 UI | 前端未接通 |
| 执行历史 | 本人列表、详情、报告、取消、重跑、删除 | 项目成员可查看项目全部执行；控制操作仍限发起人 | 查看完整，控制权不对等 |
| 报告定义 | 后端支持私有/公共定义 | 普通项目无创建、分配和过滤 API | 未实现 |
| 服务注册、部署、环境、身份条目 | 平台共享注册簿 | 项目通过默认环境和身份引用消费 | 设计上不适用项目独立 CRUD |

项目页签结构见 [`ProjectDetailView.vue:366`](../../src/gimbal-platform/frontend/src/views/ProjectDetailView.vue#L366)。

## 4. 明确缺陷

### 4.1 集成模板 owner 绕过项目成员关系

`_can_manage()` 只要当前用户是模板 owner 就直接放行，不检查普通项目成员关系，见 [`integration.py:53`](../../src/gimbal-platform/backend/app/routers/integration.py#L53)。

PATCH 和 DELETE 都使用该判断，见 [`integration.py:507`](../../src/gimbal-platform/backend/app/routers/integration.py#L507)、[`integration.py:646`](../../src/gimbal-platform/backend/app/routers/integration.py#L646)。

结果是：创建者被移出项目后，模板已经不可见，但仍可通过已知 ID 修改或删除。

#### 调度与项目凭证旁路

集成执行时，成员复核位于 `consent_gate` 内，而模板 owner 被排除，见 [`integration_runner.py:1038`](../../src/gimbal-platform/backend/app/services/integration_runner.py#L1038)。

项目凭证池也根据模板项目直接选择，没有重新确认 owner 仍是项目成员，见 [`integration_runner.py:529`](../../src/gimbal-platform/backend/app/services/integration_runner.py#L529)。

因此被移出的创建者可能继续通过自己的实例定时使用项目凭证。

#### 建议

- 将集成模板的 read/write/delete/run 权限收编到统一对象权限规则；
- 普通项目模板的 owner 身份不能替代当前成员关系；
- 所有实例执行前复核 holder 的当前成员关系，不排除 owner；
- 成员被移除时同步暂停其 owner 实例；
- 补充“移出创建者后 PATCH、DELETE、定时执行、项目凭证使用”回归测试。

### 4.2 套件能力投影把普通项目成员当成公共读者

后端套件写闸允许普通项目可写成员管理套件，见 [`suites.py:81`](../../src/gimbal-platform/backend/app/routers/suites.py#L81)。

但 `_access_and_caps()` 将 `project_id` 非空的非 owner 一律标为 `access='public'`，并返回 `canEdit=false`、`canRun=false`，见 [`suites.py:163`](../../src/gimbal-platform/backend/app/routers/suites.py#L163)。

前端直接使用这些能力位：

- 隐藏运行按钮；
- 将编排区设为只读；
- 显示“复制到我的”。

证据：[`SuiteManage.vue:35`](../../src/gimbal-platform/frontend/src/views/SuiteManage.vue#L35)、[`SuiteManage.vue:87`](../../src/gimbal-platform/frontend/src/views/SuiteManage.vue#L87)、[`SuiteManage.vue:239`](../../src/gimbal-platform/frontend/src/views/SuiteManage.vue#L239)。

但普通项目的非 owner 又不允许 fork，见 [`suites.py:438`](../../src/gimbal-platform/backend/app/routers/suites.py#L438)。

#### 结果

非创建者的项目成员：

- 能在项目列表执行套件；
- 进详情后却变成公共只读；
- 看到的“复制到我的”入口必然失败。

#### 建议

- 后端按普通项目/公共项目分别计算能力位；
- 普通项目可写成员应获得与 Table B 一致的 edit/run 能力；
- 公共项目读者继续只读；
- 在跨区复制策略未确定前，不要向普通项目成员展示必然失败的 fork 入口；
- 增加普通项目 admin、member、user 和公共读者的能力矩阵测试。

## 5. 功能缺口

### 5.1 项目场景操作面不完整

私有场景菜单包含编辑、重命名、分享、导出、发布、下架和删除，见 [`ScenariosMine.vue:166`](../../src/gimbal-platform/frontend/src/views/ScenariosMine.vue#L166)。

项目场景菜单只有查看、执行和复制到我的，见 [`ProjectScenariosTab.vue:108`](../../src/gimbal-platform/frontend/src/components/project/ProjectScenariosTab.vue#L108)。

项目场景已从“我的场景”排除，见 [`useScenarioListView.ts:37`](../../src/gimbal-platform/frontend/src/composables/useScenarioListView.ts#L37)，因此不能依赖个人页补足这些入口。

导出 API 本身支持项目成员读取，见 [`scenarios.py:1402`](../../src/gimbal-platform/backend/app/routers/scenarios.py#L1402)；缺的是前端入口。导入则连项目目标参数也没有，落库仍创建私有场景，见 [`scenario_import.py:945`](../../src/gimbal-platform/backend/app/services/scenario_import.py#L945)。

#### 建议

- 项目场景行菜单补编辑、导出、发布、删除等有权操作；
- 编辑继续进入现有编排器，不另造编辑器；
- 明确项目场景导入策略：直接落入项目，或先私有导入再走加入项目审批；
- 所有操作按项目角色显示，后端仍是权威。

### 5.2 项目集成创建与管理未接通

后端支持 `projectId` 创建，但前端创建请求类型没有该字段，见 [`integration.ts:152`](../../src/gimbal-platform/frontend/src/api/integration.ts#L152)；创建表单也没有项目选择，见 [`IntegrationCenter.vue:473`](../../src/gimbal-platform/frontend/src/views/IntegrationCenter.vue#L473)。

项目页只提供过滤列表、执行和详情，见 [`ProjectDetailView.vue:212`](../../src/gimbal-platform/frontend/src/views/ProjectDetailView.vue#L212)。

#### 建议

- 项目页增加“在本项目新建集成”；
- 场景候选限定为当前项目可执行场景；
- 创建请求显式携带 `projectId`；
- 集成详情补常规编辑、凭证来源和删除入口；
- 项目成员的管理权限按统一项目角色规则计算，不能继续只认模板 owner。

### 5.3 项目执行配置只有后端

后端项目执行配置 API 完整，见 [`exec_configs.py:204`](../../src/gimbal-platform/backend/app/routers/exec_configs.py#L204)；前端 API 也支持 `projectId`，见 [`execConfigs.ts:58`](../../src/gimbal-platform/frontend/src/api/execConfigs.ts#L58)。

但项目配置页已明确撤下该 UI，见 [`ProjectConfigPanel.vue:203`](../../src/gimbal-platform/frontend/src/components/project/ProjectConfigPanel.vue#L203)，现有配置页也只加载个人配置，见 [`ExecConfigsView.vue:1465`](../../src/gimbal-platform/frontend/src/views/ExecConfigsView.vue#L1465)。

#### 建议

先拍板：

- 项目恢复与个人对等的执行配置池；
- 或项目继续只保留一套默认配置，同时简化个人配置心智。

不应长期保持“个人有池、项目只有默认值”的隐式不对称。

### 5.4 报告定义不支持普通项目

报告定义模型有 `project_id`，但创建接口只在私有与公共之间切换，没有普通项目创建或分配，见 [`report_definitions.py:121`](../../src/gimbal-platform/backend/app/routers/report_definitions.py#L121)。

同时前端没有报告定义管理页，因此这不是项目独有的界面缺口，而是整条能力尚未产品化。

#### 建议

如果报告定义进入近期范围，再补普通项目 API 和管理入口；否则应明确标注为预留，不算当前项目闭环的必做项。

## 6. 设计上应有差异的能力

以下能力不应为了“完全一致”而强行对齐：

- 服务注册、部署、环境、身份条目：平台共享注册簿；
- 公共维护者转移：只适用于公共副本；
- 公共下架：普通项目没有对应语义；
- 执行记录控制：是否允许项目管理员取消、重跑或删除他人执行，需要单独制定治理策略。

## 7. 建议收口顺序

1. **修复套件能力投影和复制死路**；
2. **修复集成 owner 权限旁路**；
3. **补齐项目场景关键操作与导入策略**；
4. **接通项目集成创建和常规管理**；
5. **裁定项目执行配置是否恢复配置池**；
6. **按产品范围决定报告定义普通项目支持**。

## 8. 验收标准

- 普通项目 admin、member、user 对套件看到的能力位与后端权限一致；
- 普通项目成员不会看到必然失败的“复制到我的”；
- 被移出项目的集成创建者不能修改、删除或继续调度项目集成；
- 项目集成可从项目页创建，创建后落在正确项目；
- 项目场景可从项目入口完成导出、发布、删除等有权操作；
- 项目执行配置是否有前端有明确结论；
- 项目成员、项目用户、公共读者和平台 Admin 的能力矩阵有测试锁定；
- 以上改造不扩大个人凭证、项目凭证和跨区数据的可见范围。
