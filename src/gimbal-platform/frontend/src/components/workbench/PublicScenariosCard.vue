<!-- PublicScenariosCard.vue — 工作台注册卡:公共场景(→ /scenarios/public)。
     分桶谓词必须与完整页同源(visibility === 'public'),§7 第 6 条:
     计数徽标与进入后的页面一致,不另写一套判定。
     三档密度(§4):S = 公共数 + 贡献者数结论;M/L = 最新上架的场景行 5/8。
     行 testid 前缀 wb-pub-row-*(关注卡用 wb-sc-row-*,不可复用)。 -->
<template>
  <div data-testid="wb-card-public-scenarios" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-green">
        <SlibIcon name="globe" :size="14" />
      </span>
      <span class="chead-title">公共场景</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/scenarios/public" class="manage-link">公共场景 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>公共场景</p>
        <p class="s-stat"><b>{{ authorCount }}</b>贡献者</p>
      </div>
    </div>

    <template v-else>
      <div v-if="rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.meta.scenarioId"
          :to="scenarioDetailUrl(s.meta.scenarioId)"
          class="sc-row wrow"
          :data-testid="`wb-pub-row-${s.meta.scenarioId}`"
        >
          <span class="wrow-name">
            {{ s.meta.name || s.meta.scenarioId }}
            <span v-if="s.starred" class="sc-starred" title="已关注">★</span>
          </span>
          <span class="wrow-tag">{{ s.meta.author || s.meta.owner || '—' }}</span>
          <span class="wrow-time">{{ relTime(stampOf(s)) }}</span>
        </router-link>
      </div>
      <div v-else-if="failed" class="card-empty">
        <p>场景加载失败 — 稍后在公共场景页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>公共库还是空的 — 在我的场景里把可复用的编排发布上来</p>
        <router-link to="/scenarios/public" class="cta">去公共场景 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'
import { scenarioDetailUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const size = useCardSize()
const store = useScenarioComposerStore()

const stampOf = (s: ScenarioListItem) => s.meta.updateTime || s.meta.createTime || ''

// 与 ScenariosPublic.vue 同一谓词:public 才进本卡 —— §7 第 6 条计数同源。
const rows = computed(() =>
  store.window
    .filter((s) => s.visibility === 'public')
    .sort((a, b) => stampOf(b).localeCompare(stampOf(a))),
)

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))
const authorCount = computed(
  () => new Set(rows.value.map((s) => s.meta.author || s.meta.owner).filter(Boolean)).size,
)
const failed = computed(() => store.windowStatus === 'error')

const wbT = (suffix: string) => `wb-card-public-scenarios-${suffix}`

onMounted(() => { void store.ensureWindow() })
</script>

<style scoped>
/* 形制在基座 scenario-lib.css(.wcard / .chead / .s-body / .s-stats /
   .wrow / .card-empty / .cta);公共卡只留行列宽与那颗星。 */
.sc-row { grid-template-columns: minmax(0, 1fr) auto auto; }
.sc-starred { color: var(--sl-star); }
</style>
