<!-- ServiceGrid.vue — 服务画像 · 服务级热力网格(方案 §2)。
     一屏全接口瓦片 + 顶部盲区统计与筛选 chip;纯读,编辑与关系展开都在
     接口级线索板。四格状态条位置恒定(①需求 ②用例 ③最近执行 ④适配告警),
     用户扫竖直色块模式;槽① P1 为「未接入」占位格(斜纹),P2 reference
     dim 落地后点亮,格位不迁移。取色对齐方案「附:设计系统取值」。 -->
<template>
  <ListPage title="服务画像" width="wide" :subtitle="`热力网格 · ${service}`">
    <div v-if="loading" class="loading-state mt-3.5">加载中…</div>

    <div
      v-else-if="error"
      class="mt-3.5 rounded-field border border-signal-line bg-signal-card p-4 text-sm text-muted-foreground"
      data-testid="grid-error"
    >
      {{ error }}
    </div>

    <template v-else>
      <!-- 降级横幅:瓦片清单来自 plate 轻量列表,不可达 ≠ 白屏(§2.4) -->
      <div
        v-if="!grid!.plateReachable"
        class="mt-3.5 rounded-field border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        data-testid="grid-plate-down"
      >
        Plate 目录不可达,接口清单暂不可用——覆盖 / 执行 / 告警信号仍按索引计算,恢复后刷新即可。
      </div>

      <!-- 统计条 + 筛选 chip(§2.1):点一下即筛 -->
      <div class="mt-3.5 flex flex-wrap items-center gap-2" data-testid="grid-stats">
        <span class="text-caption text-muted-foreground">
          {{ grid!.stats.total }} 个接口 · {{ grid!.stats.noCases }} 个没有用例覆盖 ·
          {{ grid!.stats.hasAlarm }} 个有未处理适配告警 · {{ grid!.stats.neverRun }} 个从未执行
        </span>
        <span class="mx-1 h-4 w-px bg-signal-line"></span>
        <button
          v-for="c in chips"
          :key="c.key"
          type="button"
          :data-testid="`grid-chip-${c.key}`"
          class="rounded-full border px-2.5 py-0.5 text-caption font-medium transition-colors"
          :class="filter === c.key
            ? 'border-[#2F6FED] bg-[#E7EFFE] text-[#2F6FED]'
            : 'border-signal-line bg-signal-card text-muted-foreground hover:text-foreground'"
          @click="filter = c.key"
        >
          {{ c.label }}（{{ c.count }}）
        </button>
      </div>

      <!-- 瓦片网格(§2.3):180px 底宽,有告警时边框转红 -->
      <div
        v-if="filtered.length > 0"
        class="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(180px,1fr))]"
      >
        <button
          v-for="ep in filtered"
          :key="ep.id"
          type="button"
          :data-testid="`grid-tile-${ep.id}`"
          class="group rounded-lg border bg-white p-3 text-left transition-shadow hover:shadow-sm"
          :class="ep.signals.alarm ? 'border-[#F3CBCB]' : 'border-[#E1E5EB]'"
          :title="`${ep.method} ${ep.path} — 点开线索板`"
          @click="openBoard(ep.id)"
        >
          <div class="flex items-center gap-1.5">
            <span
              class="shrink-0 rounded px-1.5 py-px text-micro font-bold"
              :style="methodStyle(ep.method)"
            >{{ ep.method || '?' }}</span>
            <span class="truncate text-small font-medium">{{ ep.name || ep.id }}</span>
          </div>
          <div class="mono mt-1 truncate text-micro text-muted-foreground">{{ ep.path }}</div>
          <!-- 四格状态条:位置固定是关键(§2.3) -->
          <div class="mt-2.5 flex gap-1" :data-testid="`grid-slots-${ep.id}`">
            <span
              class="h-1.5 flex-1 rounded-sm bg-[repeating-linear-gradient(45deg,#E4E8EE_0_3px,#F3F5F8_3px_6px)]"
              title="需求关联:未接入(P2)"
            ></span>
            <span
              class="h-1.5 flex-1 rounded-sm"
              :class="ep.signals.cases ? 'bg-[#15803D]' : 'bg-[#F0B429]'"
              :title="ep.signals.cases ? `有用例(${ep.caseCount} 个场景)` : '无用例'"
            ></span>
            <span
              class="h-1.5 flex-1 rounded-sm"
              :class="ep.signals.lastRun === 'pass' ? 'bg-[#15803D]'
                : ep.signals.lastRun === 'fail' ? 'bg-[#DC2626]' : 'bg-[#E4E8EE]'"
              :title="lastRunTitle(ep)"
            ></span>
            <span
              class="h-1.5 flex-1 rounded-sm"
              :class="ep.signals.alarm ? 'bg-[#DC2626]' : 'bg-[#E4E8EE]'"
              :title="ep.signals.alarm ? '有未处理适配告警' : '无未处理告警'"
            ></span>
          </div>
        </button>
      </div>

      <div
        v-else-if="grid!.plateReachable"
        class="mt-6 text-sm text-muted-foreground"
        data-testid="grid-empty"
      >
        {{ filter === 'all' ? '该服务下没有登记接口' : '当前筛选下没有接口' }}
      </div>
    </template>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { fetchGrid, type GridEndpoint, type ServiceGrid } from '@/api/service-profile'

const route = useRoute()
const router = useRouter()
const service = computed(() => String(route.params.name || ''))

const loading = ref(true)
const error = ref('')
const grid = ref<ServiceGrid | null>(null)

type FilterKey = 'all' | 'noCases' | 'hasAlarm' | 'neverRun'
const filter = ref<FilterKey>('all')

const chips = computed(() => {
  const s = grid.value?.stats
  return [
    { key: 'all' as FilterKey, label: '全部', count: s?.total ?? 0 },
    { key: 'noCases' as FilterKey, label: '无用例覆盖', count: s?.noCases ?? 0 },
    { key: 'hasAlarm' as FilterKey, label: '有告警', count: s?.hasAlarm ?? 0 },
    { key: 'neverRun' as FilterKey, label: '从未执行', count: s?.neverRun ?? 0 },
  ]
})

const filtered = computed<GridEndpoint[]>(() => {
  const eps = grid.value?.endpoints ?? []
  switch (filter.value) {
    case 'noCases': return eps.filter((e) => !e.signals.cases)
    case 'hasAlarm': return eps.filter((e) => e.signals.alarm)
    case 'neverRun': return eps.filter((e) => e.signals.lastRun === null)
    default: return eps
  }
})

/** HTTP 方法配色(方案「附」):文字色/底色成对 */
const METHOD_STYLES: Record<string, { color: string; background: string }> = {
  GET: { color: '#2F6FED', background: '#E7EFFE' },
  POST: { color: '#15803D', background: '#E4F5EA' },
  PUT: { color: '#B45309', background: '#FEF3E2' },
  DELETE: { color: '#DC2626', background: '#FEE2E2' },
}

function methodStyle(method: string) {
  const s = METHOD_STYLES[method.toUpperCase()]
  return s ? { color: s.color, background: s.background } : { color: '#5B6472', background: '#F3F5F8' }
}

function lastRunTitle(ep: GridEndpoint): string {
  if (ep.signals.lastRun === 'pass') return `最近执行通过（${ep.lastRunAt?.slice(0, 19).replace('T', ' ') || ''}）`
  if (ep.signals.lastRun === 'fail') return `最近执行失败（${ep.lastRunAt?.slice(0, 19).replace('T', ' ') || ''}）`
  return '从未执行'
}

function openBoard(endpointId: string): void {
  void router.push(
    `/services/${encodeURIComponent(service.value)}/endpoints/${encodeURIComponent(endpointId)}`,
  )
}

onMounted(async () => {
  try {
    grid.value = await fetchGrid(service.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>
