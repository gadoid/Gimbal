<!-- ServicesCard.vue — 工作台注册卡:服务画像(→ /services)。
     聚合复用 loadCatalogServiceRows(),与完整页同一份口径 —— §7 第 6 条:
     卡上的服务数/端点数必须与点进完整页看到的一致。
     三档密度(§4):S = 服务数 + 端点合计;M/L = 服务行 5/8。
     形制(卡头/结论面/行骨架/空态)在基座 scenario-lib.css。 -->
<template>
  <div data-testid="wb-card-services" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="grid" :size="14" />
      </span>
      <span class="chead-title">服务画像</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/services" class="manage-link">全部 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>个服务</p>
        <p class="s-stat"><b>{{ endpointTotal }}</b>个端点</p>
      </div>
    </div>

    <template v-else>
      <div v-if="loading" class="card-empty"><p>加载中…</p></div>
      <div v-else-if="rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.name"
          :to="`/services/${encodeURIComponent(s.name)}`"
          class="svc-row wrow"
          :data-testid="`wb-svc-row-${s.name}`"
        >
          <span class="wrow-name mono">{{ s.name }}</span>
          <span class="wrow-tag">{{ s.system }}</span>
          <span class="wrow-time">{{ s.endpointCount }} 端点</span>
        </router-link>
        <p v-if="rows.length > visible.length" class="more-hint">
          还有 {{ rows.length - visible.length }} 个服务 — 到完整页查看
        </p>
      </div>
      <div v-else-if="error" class="card-empty">
        <p>{{ error }} — 稍后在服务画像页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>plate 目录里还没有服务</p>
        <router-link to="/services" class="cta">去服务画像 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { loadCatalogServiceRows, type CatalogServiceRow } from '@/utils/catalog-services'

const size = useCardSize()

const rows = ref<CatalogServiceRow[]>([])
const loading = ref(true)
const error = ref('')

const endpointTotal = computed(() => rows.value.reduce((n, s) => n + s.endpointCount, 0))

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))

const wbT = (suffix: string) => `wb-card-services-${suffix}`

// loadCatalogEntries 是模块级缓存的同一次拉取:与服务画像页、服务信息管理
// 卡同帧挂载时合流,不打第二次 plate。
onMounted(async () => {
  try {
    rows.value = await loadCatalogServiceRows()
  } catch {
    error.value = 'Plate 目录不可达'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 服务行:名称 1fr / 系统 chip / 端点数 */
.svc-row { grid-template-columns: minmax(0, 1fr) auto auto; }
</style>
