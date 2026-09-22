<!-- ServiceGrid.vue — 服务画像 · 服务级热力网格(方案 §2)。
     一屏全接口瓦片 + 顶部盲区统计与筛选 chip;纯读,编辑与关系展开都在
     接口级线索板。四格状态条位置恒定(①需求 ②用例 ③最近执行 ④适配告警),
     用户扫竖直色块模式;槽① P1 为「未接入」占位格(斜纹),P2 reference
     dim 落地后点亮,格位不迁移。
     形制走服务区域共用语言:.slib 页壳 + PageHead + .svc-tile / .svc-chip。 -->
<template>
  <section class="slib">
    <PageHead
      icon="grid"
      :title="`服务画像 · ${service}`"
      :subtitle="loading ? '正在读取覆盖与执行信号…' : `${stats.total} 个接口 · 点瓦片进线索板`"
    >
      <template #right>
        <router-link class="goto-link" to="/services">← 服务清单</router-link>
      </template>
    </PageHead>

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div
      v-else-if="error"
      class="svc-banner bad"
      data-testid="grid-error"
    >
      {{ error }}
    </div>

    <template v-else>
      <!-- 降级横幅:瓦片清单来自 plate 轻量列表,不可达 ≠ 白屏(§2.4) -->
      <div
        v-if="!grid!.plateReachable"
        class="svc-banner warn"
        data-testid="grid-plate-down"
      >
        Plate 目录不可达,接口清单暂不可用——覆盖 / 执行 / 告警信号仍按索引计算,恢复后刷新即可。
      </div>

      <!-- 统计条 + 筛选 chip(§2.1):点一下即筛 -->
      <div class="svc-stats" data-testid="grid-stats">
        <b>{{ stats.total }}</b> 个接口 ·
        <b>{{ stats.noCases }}</b> 个没有用例覆盖 ·
        <b>{{ stats.hasAlarm }}</b> 个有未处理适配告警 ·
        <b>{{ stats.neverRun }}</b> 个从未执行
        <span class="svc-stat-sep"></span>
        <button
          v-for="c in chips"
          :key="c.key"
          type="button"
          :data-testid="`grid-chip-${c.key}`"
          class="svc-chip"
          :class="{ on: filter === c.key }"
          @click="filter = c.key"
        >
          {{ c.label }}（{{ c.count }}）
        </button>
      </div>

      <!-- 关键词 + 方法筛选(2026-09-22 增补):与状态 chip 叠加过滤 -->
      <div class="grid-filter-row">
        <input
          v-model="search"
          class="grid-search"
          data-testid="grid-search"
          placeholder="按 path / 名称筛选"
        />
        <select v-model="methodFilter" class="grid-method" data-testid="grid-method" aria-label="按方法筛选">
          <option value="">全部方法</option>
          <option v-for="m in methodOptions" :key="m" :value="m">{{ m }}</option>
        </select>
        <span v-if="search || methodFilter" class="grid-filter-meta">
          筛到 {{ filtered.length }} / {{ stats.total }}
        </span>
      </div>

      <!-- 瓦片网格(§2.3):告警瓦片顶部色边转红 -->
      <div
        v-if="filtered.length > 0"
        class="svc-tiles dense"
      >
        <button
          v-for="ep in filtered"
          :key="ep.id"
          type="button"
          :data-testid="`grid-tile-${ep.id}`"
          class="svc-tile"
          :class="{ 'st-bad': ep.signals.alarm }"
          :title="`${ep.method} ${ep.path} — 点开线索板`"
          @click="openBoard(ep.id)"
        >
          <div class="svc-tile-top">
            <span class="svc-method" :class="methodClass(ep.method)">{{ ep.method || '?' }}</span>
            <span class="svc-tile-name">{{ ep.name || ep.id }}</span>
          </div>
          <div class="svc-tile-sub">{{ ep.path }}</div>
          <!-- 四格状态条:槽位顺序固定是关键(§2.3) -->
          <div class="svc-slots" :data-testid="`grid-slots-${ep.id}`">
            <span class="na" title="需求关联:未接入(P2)"></span>
            <span
              :class="ep.signals.cases ? 'ok' : 'warn'"
              :title="ep.signals.cases ? `有用例(${ep.caseCount} 个场景)` : '无用例'"
            ></span>
            <span :class="lastRunClass(ep)" :title="lastRunTitle(ep)"></span>
            <span :class="{ bad: ep.signals.alarm }" :title="ep.signals.alarm ? '有未处理适配告警' : '无未处理告警'"></span>
          </div>
        </button>
      </div>

      <div
        v-else-if="grid!.plateReachable"
        class="slib-empty"
        data-testid="grid-empty"
      >
        <p>{{ filter === 'all' && !search && !methodFilter ? '该服务下没有登记接口' : '当前筛选下没有接口' }}</p>
        <button v-if="filter !== 'all' || search || methodFilter" type="button" class="svc-chip" @click="clearFilters">看全部接口</button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { fetchGrid, type GridEndpoint, type ServiceGrid } from '@/api/service-profile'
import { methodClass } from '@/utils/http-method'

const route = useRoute()
const router = useRouter()
const service = computed(() => String(route.params.name || ''))

const loading = ref(true)
const error = ref('')
const grid = ref<ServiceGrid | null>(null)

type FilterKey = 'all' | 'noCases' | 'hasAlarm' | 'neverRun'
const filter = ref<FilterKey>('all')

// 关键词(path/name/id 子串,大小写不敏感)+ 方法下拉 — 与状态 chip 叠加
const search = ref('')
const methodFilter = ref('')

const EMPTY_STATS = { total: 0, noCases: 0, hasAlarm: 0, neverRun: 0 }
const stats = computed(() => grid.value?.stats ?? EMPTY_STATS)

const chips = computed(() => [
  { key: 'all' as FilterKey, label: '全部', count: stats.value.total },
  { key: 'noCases' as FilterKey, label: '无用例覆盖', count: stats.value.noCases },
  { key: 'hasAlarm' as FilterKey, label: '有告警', count: stats.value.hasAlarm },
  { key: 'neverRun' as FilterKey, label: '从未执行', count: stats.value.neverRun },
])

const methodOptions = computed<string[]>(() =>
  [...new Set((grid.value?.endpoints ?? []).map((e) => e.method).filter(Boolean))].sort())

const filtered = computed<GridEndpoint[]>(() => {
  let eps = grid.value?.endpoints ?? []
  switch (filter.value) {
    case 'noCases': eps = eps.filter((e) => !e.signals.cases); break
    case 'hasAlarm': eps = eps.filter((e) => e.signals.alarm); break
    case 'neverRun': eps = eps.filter((e) => e.signals.lastRun === null); break
  }
  if (methodFilter.value) eps = eps.filter((e) => e.method === methodFilter.value)
  const kw = search.value.trim().toLowerCase()
  if (kw) {
    eps = eps.filter((e) =>
      e.path.toLowerCase().includes(kw)
      || (e.name || '').toLowerCase().includes(kw)
      || e.id.toLowerCase().includes(kw))
  }
  return eps
})

function lastRunClass(ep: GridEndpoint): string {
  if (ep.signals.lastRun === 'pass') return 'ok'
  if (ep.signals.lastRun === 'fail') return 'bad'
  return ''
}

function lastRunTitle(ep: GridEndpoint): string {
  if (ep.signals.lastRun === 'pass') return `最近执行通过（${ep.lastRunAt?.slice(0, 19).replace('T', ' ') || ''}）`
  if (ep.signals.lastRun === 'fail') return `最近执行失败（${ep.lastRunAt?.slice(0, 19).replace('T', ' ') || ''}）`
  return '从未执行'
}

function clearFilters(): void {
  filter.value = 'all'
  search.value = ''
  methodFilter.value = ''
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

<style scoped>
/* 关键词 + 方法筛选行:与 ExecutionsList 的 filter 行同族观感 */
.grid-filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.grid-search {
  width: 220px;
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  background: #fff;
}
.grid-search:focus { outline: none; border-color: var(--sl-accent); }
.grid-method {
  padding: 5px 8px;
  font-size: 12px;
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  background: #fff;
}
.grid-filter-meta { font-size: 11px; color: var(--sl-ink-3); }
</style>
