/**
 * workbench/registry.ts — 工作台卡片注册中心(§7 规范,仿 router 集中式)。
 *
 * 规范六条的落点:
 * 1. 卡片是独立摘要组件,不是页面缩小版 — 复用 store 取数,不复用页面;
 * 2. registry 集中注册,卡片懒加载(component: () => Promise<Component>);
 * 3. 三态由工作台包装层统一提供,卡片只喂 loading/empty/error 数据面;
 * 4. 故障隔离:每卡套 ErrorBoundary(渲染期异常不白屏整个工作台);
 * 5. 数据契约:卡片复用既有 list API,不拉全量截断(常量池本身小数据量);
 * 6. 深链语义:目标页 meta.chromeMode 照旧;计数徽标与完整页同源。
 *
 * 组装能力(v3,设计文档 workbench-cards-design 落地):layout.ts 管
 * 启用集/顺序/每卡尺寸(S/M/L 三档密度,localStorage 按用户分键),
 * 卡片市场 = registry 里未被启用的卡;拖拽 = vuedraggable。
 * 仍显式延后:卡片间联动(禁止)、⌘K(另立项)、服务端布局同步。
 */
import { inject, ref, type InjectionKey, type Ref, type Component } from 'vue'

/** 卡片尺寸三档(设计文档 §4):高度全卡统一,档只定宽度 ——
 *  S = 1/4(只出结论)、M = 1/2(出明细)、L = 1/1(跨满行加辅助操作)。
 *  轨数映射见 WorkbenchCardSlot SPAN_TRACKS。 */
export type CardSize = 'S' | 'M' | 'L'

export const CARD_SIZES: readonly CardSize[] = ['S', 'M', 'L'] as const

export const CARD_SIZE_LABELS: Record<CardSize, string> = {
  S: '紧凑',
  M: '标准',
  L: '展开',
}

/** 分类色(设计文档 §2:顶部 3px 色边复用图标语义色,不引入新颜色)。 */
export type CardAccent = 'blue' | 'green' | 'gold'

/** slot → 卡片组件的尺寸注入键(inject 缺省 'M',卡片可独立渲染)。 */
export const cardSizeKey: InjectionKey<Ref<CardSize>> = Symbol('workbench-card-size')

/** 卡片组件侧取尺寸的便捷入口(缺省 M — 组件脱离 slot 也能渲染)。 */
export function useCardSize(): Ref<CardSize> {
  return inject(cardSizeKey, null) ?? ref<CardSize>('M')
}

export interface WorkbenchCardDef {
  id: string                    // 'constants' | 'recent-executions' | ...
  title: string
  /** 市场画廊里的一句话说明 */
  description?: string
  component: () => Promise<Component>   // 懒加载
  /** 分类色边 + 图标语义色(§7 v3) */
  accent: CardAccent
  /** 初始尺寸(用户未调过时);缺省 'M'。用户级尺寸存 layout v2。 */
  defaultSize?: CardSize
  adminOnly?: boolean           // 复用侧栏同一权限判定源,不另写一套
  /** M2.5 角色白名单(adminOnly 的泛化;优先于 adminOnly) */
  roles?: string[]
  refreshMs?: number            // 需要轮询的卡(执行状态)声明;缺省不刷
}

/** 注册顺序 = 默认布局顺序;工作台组装(添加/删除/拖拽)的候选全集 */
export const workbenchRegistry: WorkbenchCardDef[] = [
  {
    id: 'constants',
    title: '常量池',
    description: '业务常量与生成器,一键复制引用键',
    accent: 'blue',
    component: () => import('./ConstantsSummaryCard.vue'),
  },
  {
    id: 'recent-executions',
    title: '最近执行',
    description: '最近 5 次执行的状态、通过率与直达详情',
    accent: 'green',
    component: () => import('./RecentExecutionsCard.vue'),
  },
  {
    id: 'my-scenarios',
    title: '我的场景',
    description: '私有编排速览 — 最近编辑直达 + 过期提醒',
    accent: 'blue',
    component: () => import('./MyScenariosCard.vue'),
  },
  {
    id: 'public-scenarios',
    title: '公共场景',
    description: '公共库最新上架的编排与贡献者,直达详情',
    accent: 'green',
    component: () => import('./PublicScenariosCard.vue'),
  },
  {
    id: 'starred-scenarios',
    title: '关注场景',
    description: '★ 关注的场景快捷入口,直达场景详情;卡头进关注页',
    accent: 'gold',
    component: () => import('./StarredScenariosCard.vue'),
  },
  {
    id: 'services',
    title: '服务画像',
    description: '目录里的服务与端点数,直达热力网格',
    accent: 'blue',
    component: () => import('./ServicesCard.vue'),
  },
  {
    id: 'auths',
    title: '认证管理',
    description: '凭证池概况 — 多少条、多少条已没人引用可清理',
    accent: 'blue',
    component: () => import('./AuthSessionsCard.vue'),
  },
  {
    id: 'adaptations',
    title: '适配中心',
    description: '待适配端点数与最近批次,直达批次详情',
    accent: 'gold',
    component: () => import('./AdaptationCard.vue'),
  },
  {
    id: 'runner',
    title: '执行器',
    description: '能跑几个场景、哪些还缺方案 —— 卡住的那步先补上',
    accent: 'green',
    component: () => import('./RunnableScenariosCard.vue'),
  },
  {
    id: 'service-aliases',
    title: '服务信息管理',
    description: '服务别名清单与未分组提醒(operator+)',
    accent: 'blue',
    roles: ['operator', 'admin'],
    component: () => import('./ServiceAliasCard.vue'),
  },
  {
    id: 'carry',
    title: '默认值',
    description: '服务级传递默认值,行深链直达定位(operator+)',
    accent: 'blue',
    roles: ['operator', 'admin'],
    component: () => import('./CarryDefaultsCard.vue'),
  },
  {
    id: 'users',
    title: '用户管理',
    description: '成员数与停用提醒(admin)',
    accent: 'blue',
    defaultSize: 'S',
    adminOnly: true,
    component: () => import('./UsersSummaryCard.vue'),
  },
]
