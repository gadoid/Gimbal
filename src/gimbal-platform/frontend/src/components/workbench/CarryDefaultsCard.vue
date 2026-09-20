<!-- CarryDefaultsCard.vue — 工作台注册卡:默认值(adminOnly,→ /carry-config)。
     数据 = getDefaults() 全集(与完整页同一端点);行深链带 ?path=,
     落地页会定位并高亮那一行(CarryConfig 已支持)。
     三档密度(§4):S = 条数结论;M/L = 路径行 5/8。 -->
<template>
  <div data-testid="wb-card-carry" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="sliders" :size="14" />
      </span>
      <span class="chead-title">默认值</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/carry-config" class="manage-link">管理 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <p class="s-num">{{ rows.length }}</p>
      <p class="s-label">条服务级默认值</p>
    </div>

    <template v-else>
      <div v-if="loading" class="card-empty"><p>加载中…</p></div>
      <div v-else-if="rows.length" class="rows">
        <router-link
          v-for="r in visible"
          :key="r.path"
          :to="`/carry-config?path=${encodeURIComponent(r.path)}`"
          class="cy-row wrow"
          :data-testid="`wb-cy-row-${r.path}`"
        >
          <span class="wrow-name mono" :title="r.path">{{ r.path }}</span>
          <span class="cy-value mono" :class="{ 'is-null': r.isNull }" :title="r.isNull ? '未填值' : r.value">
            {{ r.isNull ? '未填' : r.value }}
          </span>
        </router-link>
        <p v-if="rows.length > visible.length" class="more-hint">
          还有 {{ rows.length - visible.length }} 条 — 到完整页查看
        </p>
      </div>
      <div v-else-if="error" class="card-empty"><p>{{ error }} — 稍后在默认值页重试</p></div>
      <div v-else class="card-empty">
        <p>还没有服务级默认值 — 配一条,编排里就不用每次手填</p>
        <router-link to="/carry-config" class="cta">去配置 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { getDefaults } from '@/api/carry'

interface CarryRow { path: string; value: string; isNull: boolean }

const size = useCardSize()

const rows = ref<CarryRow[]>([])
const loading = ref(true)
const error = ref('')

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))

const wbT = (suffix: string) => `wb-card-carry-${suffix}`

onMounted(async () => {
  try {
    const map = await getDefaults()
    rows.value = Object.entries(map)
      .map(([path, v]) => ({
        path,
        isNull: v === null || v === undefined || v === '',
        value: v === null || v === undefined ? '' : String(v),
      }))
      .sort((a, b) => a.path.localeCompare(b.path))
  } catch {
    error.value = '默认值加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 形制在基座;默认值行 = 路径 1fr / 值 1fr(值可能很长,截断 + title) */
.cy-row { grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); }
.cy-value {
  min-width: 0; color: var(--sl-ink-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cy-value.is-null { color: var(--sl-ink-3); font-style: italic; }
</style>
