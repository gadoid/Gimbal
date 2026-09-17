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
 * 显式延后(§7):拖拽布局/卡片市场(v2)、卡片间联动(禁止)、⌘K(另立项)。
 */
import type { Component } from 'vue'

export interface WorkbenchCardDef {
  id: string                    // 'constants' | 'recent-executions' | ...
  title: string
  component: () => Promise<Component>   // 懒加载
  span?: 1 | 2                  // 两列栅格占位,缺省 1
  adminOnly?: boolean           // 复用侧栏同一权限判定源,不另写一套
  refreshMs?: number            // 需要轮询的卡(执行状态)声明;缺省不刷
}

/** 注册顺序 = 默认渲染顺序;首个注册卡 = 常量池卡(§7 落地节奏) */
export const workbenchRegistry: WorkbenchCardDef[] = [
  {
    id: 'constants',
    title: '常量池',
    component: () => import('./ConstantsSummaryCard.vue'),
  },
]
