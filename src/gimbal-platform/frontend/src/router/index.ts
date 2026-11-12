/**
 * router/index.ts — Spec-1 routing table + simple auth guard.
 *
 * Views are dynamic imports so Vite lazy-loads them.  The guard is
 * intentionally lightweight: it checks for an access token in localStorage
 * (via the Pinia auth store) and redirects; token validity is verified by
 * fetchMe() on first protected visit.
 */
import { createRouter, createWebHistory, type RouteLocationGeneric } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/** D1 退役路由兜底:旧数据集深链/书签 → 方案工作台(能力承接处),不白屏 */
const dataSetsFallback = (to: { params: Record<string, string | string[]> }) =>
  `/scenarios/${encodeURIComponent(String(to.params.scenarioId))}/schemes`

const routes = [
  // F-sitemap v2:登录后默认落地 = 用户工作台 /home(原为 /scenarios)
  { path: '/', redirect: '/home' },
  { path: '/home', component: () => import('@/views/WorkbenchView.vue'), meta: { requiresAuth: true } },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  // protected
  // ── 场景编排 V3 ────────────────────────────────────────────
  // 场景库拆三页(我的场景 / 公共场景 / 关注);/scenarios 旧入口重定向到
  // 我的场景页(2026-11-10 IA:侧栏「我的 → 场景」)。
  { path: '/scenarios', redirect: '/scenarios/mine' },
  {
    path: '/scenarios/mine',
    component: () => import('@/views/ScenariosMine.vue'),
    meta: { requiresAuth: true },
  },
  {
    // S7.1 IA 修正:公共场景并入公共项目(项目页场景页签);旧深链
    // 重定向(公共项目 id 运行时解析,见 PublicProjectRedirect)
    path: '/scenarios/public',
    component: () => import('@/views/PublicProjectRedirect.vue'),
    meta: { requiresAuth: true, tab: 'scenarios' },
  },
  {
    path: '/scenarios/follows',
    component: () => import('@/views/ScenarioFollows.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 用例编排 (V3) 专用页面 — 一个页面承载 4 步流程 (Meta → Resource → Config → Canvas)
    // /composer/new         新建 (空白草稿)
    // /composer/:scenarioId 编辑已有
    // ?step=1..4            直接跳到某一步
    path: '/composer/:scenarioId',
    component: () => import('@/views/CaseComposer.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // /scenarios/:scenarioId/detail — 场景详情页(数据驱动的可读渲染,
    // 数据源 = composer_scenarios 读侧结构)
    path: '/scenarios/:scenarioId/detail',
    component: () => import('@/views/ScenarioDetailView.vue'),
    meta: { requiresAuth: true },
  },
  // 数据集独立路由已退役(D1,重构方案 Phase 2 批次 0):数据集是方案的
  // 实现模块,能力由方案工作台 SchemeDataSection 承接,不设独立入口。
  // 旧深链/书签兜底重定向到方案工作台,不白屏。
  {
    path: '/scenarios/:scenarioId/data-sets',
    redirect: dataSetsFallback,
  },
  {
    path: '/scenarios/:scenarioId/data-sets/:datasetId',
    redirect: dataSetsFallback,
  },
  {
    // 断言管理编辑器 — 场景级注册表(spec v2 §7)
    path: '/scenarios/:scenarioId/assertions',
    component: () => import('@/views/AssertionRegistryEditor.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // /scenarios/:scenarioId/schemes — 方案工作台(spec 2026-09-14 §6)
    path: '/scenarios/:scenarioId/schemes',
    component: () => import('@/views/SchemeWorkbench.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // S7.3:/carry-config 退役 —— 全局默认落公共项目「配置」页签
    // (?path= 深链透传;「我的默认」层迁个人设置 /profile/config)
    path: '/carry-config',
    component: () => import('@/views/PublicProjectRedirect.vue'),
    meta: { requiresAuth: true, tab: 'config' },
  },
  {
    path: '/admin/users',
    component: () => import('@/views/UsersAdmin.vue'),
    // authz W8:用户管理 = users.manage(表 A:super_admin)
    meta: { requiresAuth: true, requiresCap: 'users.manage' },
  },
  {
    // 用户管理 → 用户页(钻取子页,点行进入):概览 + 访问令牌起步,
    // 后续按用户维度的板块在此扩 tab;替代原全局平铺令牌 tab
    path: '/admin/users/:id(\\d+)',
    component: () => import('@/views/UserDetailAdmin.vue'),
    meta: { requiresAuth: true, requiresCap: 'users.manage' },
  },
  {
    // 旧令牌直达路径 → 用户页(改版前的短期兼容)
    path: '/admin/users/:id(\\d+)/tokens',
    redirect: (to: RouteLocationGeneric) => `/admin/users/${to.params.id}`,
  },
  {
    // S7.1 IA 修正:项目管理页退役 —— Admin+ 建项目/管成员收编进
    // /projects(列表新建 + 详情成员页签)
    path: '/admin/projects',
    redirect: '/projects',
  },
  {
    path: '/admin/deployments',
    component: () => import('@/views/DeploymentsAdmin.vue'),
    // M2a S2.3:部署表维护 = ops.write(Admin+;写面同后端闸)
    meta: { requiresAuth: true, requiresCap: 'ops.write' },
  },
  {
    // authz W6 强制改密页:管理员重置密码后(me.must_change_password)
    // 路由守卫把一切页面重定向到这里,改密成功回原目标(见 beforeEach)。
    path: '/change-password',
    component: () => import('@/views/ChangePassword.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // 通知页(F5,2026-09-23;侧边栏入口名「通知」):全员;审计 tab 仅
    // admin(渲染层隐藏 + 后端 /admin/audit-logs 403 双层守卫,方案 §5.5 T5)
    path: '/notifications',
    component: () => import('@/views/NotificationsCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 执行配置(执行配置分层①,2026-11-11):个人面·全员 —— 环境/槽位
    // 绑定/carry 覆盖的跨场景载体,唯一入口(决策 8 终局;「我的配置」
    // 页随批次⑥退役后由本页承接)
    path: '/exec-configs',
    component: () => import('@/views/ExecConfigsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 个人设置(P2-1;原型 Main/Tokens/CardSettings = 子页面而非同页
    // 锚点):Profile.vue 只做布局(头 + 分区导航 + RouterView),内容
    // 在三个子页;'' 重定向吞掉旧 #tokens/#card 深链(书签兼容)。
    // 通知与账号同页(Main.html):#notify 落账号子页并保留锚点,由
    // ProfileAccount 滚到通知区(此前锚点被丢弃,停在账号卡顶部)。
    path: '/profile',
    component: () => import('@/views/Profile.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        // hash: '' 显式丢弃旧锚点 —— 不给 hash 时重定向会继承
        redirect: (to: { hash: string }) => ({
          path: to.hash === '#tokens' ? '/profile/tokens'
            : to.hash === '#card' ? '/profile/card'
              : '/profile/account',
          hash: to.hash === '#notify' ? '#notify' : '',
        }),
      },
      // Main.html:账号(昵称/改密)+ 通知
      { path: 'account', component: () => import('@/views/ProfileAccount.vue') },
      // Tokens.html:访问令牌(个人视角)
      { path: 'tokens', component: () => import('@/views/ProfileTokens.vue') },
      // CardSettings.html:工作台身份卡
      { path: 'card', component: () => import('@/views/ProfileCard.vue') },
      // 分层⑥(决策 8):「我的配置」页退役 —— 三卡全迁执行配置
      // (/exec-configs):env 偏好收编 + 个人 carry 层收编 + 漂移面板
      // 迁配置详情;旧深链重定向(书签兼容)。
      { path: 'config', redirect: '/exec-configs' },
    ],
  },
  {
    path: '/auths',
    component: () => import('@/views/Auths.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/constants',
    component: () => import('@/views/ConstantsPool.vue'),
    // 常量池:从顶导航降级,经工作台深链进入(侧边栏收起,见 H-constants)
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // RS4a（Release v4.4 §5.10 重做）：新适配流程为主体（R22 全员）
    // + 批次表 + carry 漂移
    path: '/adaptations',
    component: () => import('@/views/AdaptationCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 兼容：旧链接 /adaptations/new 重定向到主页
    path: '/adaptations/new',
    redirect: '/adaptations',
  },
  {
    path: '/adaptations/batches/:batchId',
    component: () => import('@/views/AdaptationBatchDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 执行器(执行设计 §1):发起入口从运行对话框升为页面 — 队列挑 N 条
    // 逐条顺序发起,按批次在执行记录归并;对话框(编排页)保留单条路径。
    path: '/run',
    component: () => import('@/views/Runner.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/executions',
    component: () => import('@/views/ExecutionsList.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/executions/:id(\\d+)',
    component: () => import('@/views/Executions.vue'),
    meta: { requiresAuth: true },
  },
  {
    // P2-07/C10:日志分析页(单执行事件/日志组合筛选)
    path: '/executions/:id(\\d+)/events',
    component: () => import('@/views/ExecutionEvents.vue'),
    meta: { requiresAuth: true },
  },
  {
    // C6/P3-04:调试台(运行中调试执行的命令/输出/事件代理)。
    // 正则须写 \\d+(普通字符串里 \d 就是字母 d,路由永远匹配不上 —
    // 2026-11-05 前端评审 P1-1 复现修复)
    path: '/executions/:id(\\d+)/debug',
    component: () => import('@/views/DebugConsole.vue'),
    meta: { requiresAuth: true },
  },
  // ── 项目(M2a S7.1 IA 修正:一级入口;公共项目 = 置顶默认项目) ──
  {
    path: '/projects',
    component: () => import('@/views/ProjectsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 详情页签 ?tab=scenarios|suites|tasks|members(成员 = canManage)
    path: '/projects/:id(\\d+)',
    component: () => import('@/views/ProjectDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // Suite(Suite 层重构:成员层 + 编排层单实体)。/suites = 场景集
    // (02 独立成组;2026-11-10 IA:并入侧栏「我的」组,页面更名场景集);
    // /suites/:id = 管理页
    // (20 编排 / 21 运行记录,含只读态)。旧 /suites/composer 已随重构删除。
    path: '/suites',
    component: () => import('@/views/SuiteLibrary.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 公共用例集 → S7.1 IA 修正:并入公共项目(项目页用例集页签);
    // 旧深链重定向;:id 路由带 \d+ 约束,静态段不冲突。
    path: '/suites/public',
    component: () => import('@/views/PublicProjectRedirect.vue'),
    meta: { requiresAuth: true, tab: 'suites' },
  },
  {
    // 画布(重构方案 10–13):新建(/suites/new,不落库,首次拖入建草稿)
    // 与改结构(/suites/:id/compose)同一路由记录 —— alias 导航时组件
    // 实例复用,首次拖入建草稿换 URL 不丢画布状态(vue-router 对静态
    // 别名缺参的 warn 不影响匹配,已由 SuiteCompose.test 钉住);非属主
    // 在页面内重定向到 20 只读态。
    path: '/suites/:id(\\d+)/compose',
    alias: '/suites/new',
    component: () => import('@/views/SuiteCompose.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/suites/:id(\\d+)',
    component: () => import('@/views/SuiteManage.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 集成(外部系统集成 P1):功能(定时任务 → 工作台卡片)+
    // 平台凭证(admin)。
    path: '/integrations',
    component: () => import('@/views/IntegrationCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 集成详情(webhook v4 §8;原型 IntegrationDetail × 9 变体):
    // 暂停横幅按 §3.3 分型,身份与令牌/最近运行;?task= 旧深链由
    // IntegrationCenter 重定向进来。
    path: '/integrations/:taskId',
    component: () => import('@/views/IntegrationDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 数据分析(执行设计 §4:本期延后)— 说明页:前置(行级/步骤级结果
    // 落库)+ 已在别处的两个去向。侧边栏入口置灰但可点(§4.4:留个灰
    // 入口,点进来撞上那条说明;本页正常高亮 + 琥珀「延后」小标)。
    path: '/analytics',
    component: () => import('@/views/AnalyticsDeferred.vue'),
    meta: { requiresAuth: true },
  },
  // ── 服务画像 P1(服务画像方案 §5.4)───────────────────────────
  {
    // 落地页:列 plate 目录服务,点进 /services/:name 热力网格
    path: '/services',
    component: () => import('@/views/ServicesIndex.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 服务级热力网格(方案 §2);service 名可含 '-',路由段天然安全
    path: '/services/:name',
    component: () => import('@/views/ServiceGrid.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 接口级线索板(方案 §3);endpoint_id 是点分命名空间(如 fin.order.add)
    path: '/services/:name/endpoints/:endpointId',
    component: () => import('@/views/EndpointBoard.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 服务信息管理(方案 §4;P1 唯一净新增页面)— 配置池,admin 写面
    path: '/service-admin',
    component: () => import('@/views/ServiceAdmin.vue'),
    // authz W8:服务信息管理 = ops.write(表 A:admin+;原 member+ 更名)
    meta: { requiresAuth: true, requiresCap: 'ops.write' },
  },
  {
    // 键详情(配套方案 §2.2):别名全名或 base 服务名同一详情页,
    // 字段默认值 tab 在此编辑;?tab=credential 供认证管理反查深链
    path: '/service-admin/:alias',
    component: () => import('@/views/ServiceAliasDetail.vue'),
    // ops.write+:别名属主要在本页管理入站/回调(后端按 admin ∨ 属主判定),
    // 入站调用方(个人 gtk_ 令牌)也走这里的绑定面 —— 旧 requiresAdmin 把
    // 属主与调用方一并挡在门外(全量评估 2026-11-02 #3)。令牌的签发/管理
    // 面在 /profile/tokens(webhook v4)。写面权限仍由后端与子面板的
    // canManage 把关,放开路由不扩大写权限。
    meta: { requiresAuth: true, requiresCap: 'ops.write' },
  },
  // /dev/dual-stack 双栈验证页已随 Phase 3 退役(EP 摘除,使命完成)

  // catch-all 404(评审 P2-5):坏深链落 NotFound,而不是空白页
  {
    path: '/:pathMatch(.*)*',
    component: () => import('@/views/NotFound.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.accessToken) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // authz W8:能力门(meta.requiresCap,表 A 能力名;取代 requiresRoles/
  // requiresAdmin)。后端同门 403 —— 这里只是 UX:无能力者不落到必 403
  // 的页面。capabilities 来自 /auth/me(登录/刷新/首挂载都已就位)。
  const needCap = to.meta.requiresCap as string | undefined
  if (needCap && !auth.can(needCap)) {
    return { path: '/home' }
  }
  // authz W6 只能改密门:must_change_password 为真 → 一切页面重定向到
  // /change-password(改密成功回 redirect 目标)。登录/注册/改密页
  // 本身放行;令牌路径后端已天然覆盖(重置即失效)。
  if (
    auth.mustChangePassword &&
    !['/change-password', '/login', '/register'].includes(to.path)
  ) {
    return { path: '/change-password', query: { redirect: to.fullPath } }
  }
  if ((to.path === '/login' || to.path === '/register') && auth.accessToken) {
    return { path: '/home' }
  }
})

export default router