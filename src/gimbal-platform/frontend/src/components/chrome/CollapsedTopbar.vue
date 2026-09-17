<!-- CollapsedTopbar.vue — 编辑流页面的收拢 chrome(重构方案 Phase 1)。
     骨架规范强制一条:左侧统一放面包屑,层级感与返回路径由此承载;
     各页面(场景详情题头"返回"、编排器左上角收起图标)不再自造返回。
     面包屑 = 场景库 / <场景名||id>(→ 场景详情枢纽)/ 当前层级;
     常量池经工作台深链进入,面包屑 = 工作台 / 常量池。 -->
<template>
  <header class="collapsed-topbar">
    <div class="brand">
      <span class="status-dot" title="服务在线"></span>
      <span class="brand-text">platform</span>
    </div>

    <nav class="crumb" aria-label="面包屑">
      <template v-for="(seg, i) in segments" :key="`${seg.label}-${i}`">
        <span v-if="i > 0" class="crumb-sep">/</span>
        <router-link v-if="seg.to" :to="seg.to" class="crumb-link">{{ seg.label }}</router-link>
        <span v-else class="crumb-current">{{ seg.label }}</span>
      </template>
    </nav>

    <div class="topbar-right">
      <span class="user-info" v-if="auth.currentUser">
        <span class="username">{{ auth.currentUser.display_name || auth.currentUser.username }}</span>
        <span class="role">{{ auth.currentUser.is_admin ? 'admin' : 'member' }}</span>
      </span>
      <button class="logout-btn" @click="onLogout">登出</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useScenarioName } from '@/composables/useScenarioName'

interface CrumbSegment {
  label: string
  /** 可点的中间层级;末段不可点。 */
  to?: string
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

async function onLogout() {
  await auth.logout()
  router.push('/login')
}

const scenarioId = computed(() => String(route.params.scenarioId ?? ''))
const scenarioName = useScenarioName(scenarioId)

// 层级语义:composer=编排;schemes=方案;assertions=断言注册表;
// data-sets(Phase 2 批次 0 退役前仍可达)=数据集。
const LEVEL_LABELS: Record<string, string> = {
  '/composer': '编排',
  'schemes': '方案',
  'assertions': '断言注册表',
  'data-sets': '数据集',
}

const segments = computed<CrumbSegment[]>(() => {
  const path = route.path
  if (path.startsWith('/composer/')) {
    const id = scenarioId.value
    return [
      { label: '场景库', to: '/scenarios' },
      { label: scenarioName.value || id, to: `/scenarios/${id}/detail` },
      { label: LEVEL_LABELS['/composer'] },
    ]
  }
  if (scenarioId.value && path.includes('/schemes')) {
    return [
      { label: '场景库', to: '/scenarios' },
      { label: scenarioName.value || scenarioId.value, to: `/scenarios/${scenarioId.value}/detail` },
      { label: LEVEL_LABELS['schemes'] },
    ]
  }
  if (scenarioId.value && path.includes('/assertions')) {
    return [
      { label: '场景库', to: '/scenarios' },
      { label: scenarioName.value || scenarioId.value, to: `/scenarios/${scenarioId.value}/detail` },
      { label: LEVEL_LABELS['assertions'] },
    ]
  }
  if (scenarioId.value && path.includes('/data-sets')) {
    return [
      { label: '场景库', to: '/scenarios' },
      { label: scenarioName.value || scenarioId.value, to: `/scenarios/${scenarioId.value}/detail` },
      { label: LEVEL_LABELS['data-sets'] },
    ]
  }
  if (path.startsWith('/constants')) {
    return [{ label: '工作台', to: '/home' }, { label: '常量池' }]
  }
  return []
})
</script>

<style scoped>
.collapsed-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  background: #0b0e14;
  z-index: 1000;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 4px rgba(34, 211, 238, 0.6);
}

.brand-text {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #f8fafc;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  font-size: 12px;
}

.crumb-sep {
  color: #475569;
}

.crumb-link {
  color: #94a3b8;
  text-decoration: none;
  white-space: nowrap;
}

.crumb-link:hover {
  color: #e2e8f0;
}

.crumb-current {
  color: #f8fafc;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.user-info {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.username {
  font-size: 12px;
  color: #f8fafc;
  font-weight: 500;
}

.role {
  font-size: 11px;
  color: #64748b;
}

.logout-btn {
  height: 26px;
  padding: 0 10px;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: transparent;
  color: #cbd5e1;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.logout-btn:hover {
  border-color: #2f6fed;
  color: #ffffff;
}
</style>
