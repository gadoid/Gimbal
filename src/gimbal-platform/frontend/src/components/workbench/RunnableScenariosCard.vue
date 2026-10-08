<!-- RunnableScenariosCard.vue — 工作台注册卡:执行器(→ /run)。
     执行器本身是动作台,没有自己的列表端点;这张卡回答的是"我现在能跑
     几个、哪些还跑不起来"。可执行口径 = 自己创建的全部(scope=mine,
     含已发布——owner 可跑自己的公共场景),与 Runner.vue 一致;卡内
     自带查询而不复用共享 window(默认 all):admin 的 window 上过滤
     visibility!=='public' 会把全员的 private 都算进「我的可执行」,
     与场景库同款淹没 bug。缺方案的场景排进行里 —— 那是真正卡住的一步。 -->
<template>
  <div data-testid="wb-card-runner" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-green">
        <SlibIcon name="play" :size="14" />
      </span>
      <span class="chead-title">执行器</span>
      <span class="chead-count">{{ runnableCount }} 可跑</span>
      <span class="chead-spacer" />
      <router-link to="/run" class="manage-link">去执行 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ runnableCount }}</b>可执行</p>
        <p class="s-stat" :class="{ 'st-warn': blocked.length > 0 }"><b>{{ blocked.length }}</b>缺方案</p>
      </div>
    </div>

    <template v-else>
      <div v-if="status !== 'ready'" class="card-empty">
        <p>{{ status === 'error' ? '场景加载失败 — 稍后在执行器页重试' : '加载中…' }}</p>
      </div>
      <div v-else-if="blocked.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.meta.scenarioId"
          :to="`/scenarios/${encodeURIComponent(s.meta.scenarioId)}/schemes`"
          class="rn-row wrow"
          :data-testid="`wb-rn-row-${s.meta.scenarioId}`"
        >
          <span class="wrow-name" :title="s.meta.name || s.meta.scenarioId">{{ s.meta.name || s.meta.scenarioId }}</span>
          <span class="wrow-tag">{{ s.meta.module || '未分类' }}</span>
          <span class="rn-no-scheme">无方案</span>
        </router-link>
        <p v-if="blocked.length > visible.length" class="more-hint">
          还有 {{ blocked.length - visible.length }} 个场景没有方案 — 到完整页查看
        </p>
      </div>
      <div v-else class="card-empty">
        <p>你的场景都配好方案了 — 可以直接发起执行</p>
        <router-link to="/run" class="cta">去执行器 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import * as api from '@/api/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'

const size = useCardSize()

const stampOf = (s: ScenarioListItem) => s.meta.updateTime || s.meta.createTime || ''

// 可执行范围 = 自己创建的全部(scope=mine,与 Runner.vue 同口径)。
const items = ref<ScenarioListItem[]>([])
const status = ref<'loading' | 'ready' | 'error'>('loading')
onMounted(async () => {
  try {
    const env = await api.listScenarios({ page: 1, page_size: 100, scope: 'mine' })
    items.value = env.items
    status.value = 'ready'
  } catch {
    status.value = 'error'
  }
})

const mine = computed(() =>
  items.value.slice().sort((a, b) => stampOf(b).localeCompare(stampOf(a))))
const runnableCount = computed(() => mine.value.filter((s) => s.schemeCount).length)
const blocked = computed(() => mine.value.filter((s) => !s.schemeCount))

/** M = 5 行;L = 8 行 */
const visible = computed(() => blocked.value.slice(0, size.value === 'L' ? 8 : 5))

const wbT = (suffix: string) => `wb-card-runner-${suffix}`
</script>

<style scoped>
/* 形制在基座;这里只给行列宽与"跑不起来"的红警。 */
.rn-row { grid-template-columns: minmax(0, 1fr) auto auto; }
.rn-no-scheme {
  padding: 1px 7px; font-size: 10.5px; font-weight: 600;
  color: var(--sl-bad); background: var(--sl-bad-soft);
  border-radius: 4px; white-space: nowrap;
}
.st-warn b { color: var(--sl-warn); }
</style>
