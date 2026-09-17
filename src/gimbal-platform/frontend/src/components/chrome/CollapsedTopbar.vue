<!-- CollapsedTopbar.vue — 编辑流页面的收拢 chrome(重构方案 Phase 1)。
     骨架规范强制一条:左侧统一放面包屑,层级感与返回路径由此承载;
     各页面(场景详情题头"返回"、编排器左上角收起图标)不再自造返回。
     面包屑 = 场景库 / <场景名||id>(→ 场景详情枢纽)/ 当前层级;
     新建草稿(/composer/new)无实体可指,中间段只显示"新建场景"且不可
     点、不发起取名请求;常量池经工作台深链进入,面包屑 = 工作台 / 常量池。
     颜色全部经 Signal token(@apply/工具类),组件内零散 hex 为零。 -->
<template>
  <header class="collapsed-topbar fixed inset-x-0 top-0 z-[1000] flex h-12 items-center gap-4 bg-signal-sidebar px-4">
    <div class="flex shrink-0 items-center gap-2">
      <span class="status-dot h-2 w-2 rounded-full bg-signal-dot" title="服务在线"></span>
      <span class="brand-text text-body font-semibold tracking-wide text-slate-50">platform</span>
    </div>

    <nav class="crumb flex min-w-0 flex-1 items-center gap-2 text-body" aria-label="面包屑">
      <template v-for="(seg, i) in segments" :key="`${seg.label}-${i}`">
        <span v-if="i > 0" class="crumb-sep text-slate-600">/</span>
        <router-link
          v-if="seg.to"
          :to="seg.to"
          class="crumb-link whitespace-nowrap text-slate-400 no-underline transition-colors hover:text-slate-200"
        >{{ seg.label }}</router-link>
        <span v-else class="crumb-current truncate whitespace-nowrap font-semibold text-slate-50">{{ seg.label }}</span>
      </template>
    </nav>

    <UserBadge />
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import UserBadge from '@/components/chrome/UserBadge.vue'
import { useScenarioName } from '@/composables/useScenarioName'

interface CrumbSegment {
  label: string
  /** 可点的中间层级;末段不可点。 */
  to?: string
}

const route = useRoute()

// 'new' = /composer/new 新建草稿,不是实体 id;置空以跳过取名请求
const scenarioId = computed(() => {
  const raw = String(route.params.scenarioId ?? '')
  return raw === 'new' ? '' : raw
})
const scenarioName = useScenarioName(scenarioId)

// 层级语义:composer=编排;schemes=方案;assertions=断言注册表。
// 数据集页已退役(D1,批次 0),不设面包屑。
const LEVEL_LABELS: Record<string, string> = {
  '/composer': '编排',
  'schemes': '方案',
  'assertions': '断言注册表',
}

function scenarioCrumb(level: string): CrumbSegment[] {
  if (!scenarioId.value) {
    // /composer/new:无实体场景,中间段不可点
    return [{ label: '场景库', to: '/scenarios' }, { label: '新建场景' }, { label: level }]
  }
  return [
    { label: '场景库', to: '/scenarios' },
    { label: scenarioName.value || scenarioId.value, to: `/scenarios/${scenarioId.value}/detail` },
    { label: level },
  ]
}

const segments = computed<CrumbSegment[]>(() => {
  const path = route.path
  if (path.startsWith('/composer/')) return scenarioCrumb(LEVEL_LABELS['/composer'])
  if (scenarioId.value && path.includes('/schemes')) return scenarioCrumb(LEVEL_LABELS['schemes'])
  if (scenarioId.value && path.includes('/assertions')) return scenarioCrumb(LEVEL_LABELS['assertions'])
  if (path.startsWith('/constants')) {
    return [{ label: '工作台', to: '/home' }, { label: '常量池' }]
  }
  return []
})
</script>

