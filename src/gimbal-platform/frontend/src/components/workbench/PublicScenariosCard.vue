<!-- PublicScenariosCard.vue — 工作台注册卡:公共场景(→ /scenarios/public)。
     分桶谓词必须与完整页同源(visibility === 'public'),§7 第 6 条:
     计数徽标与进入后的页面一致,不另写一套判定。
     三档密度(§4):S = 公共数 + 贡献者数结论;M/L = 最新上架的场景行 5/8。
     行 testid 前缀 wb-pub-row-*(关注卡用 wb-sc-row-*,不可复用)。 -->
<template>
  <div data-testid="wb-card-public-scenarios" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-green">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
        </svg>
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
          class="sc-row"
          :data-testid="`wb-pub-row-${s.meta.scenarioId}`"
        >
          <span class="sc-name">
            {{ s.meta.name || s.meta.scenarioId }}
            <span v-if="s.starred" class="sc-starred" title="已关注">★</span>
          </span>
          <span class="sc-author">{{ s.meta.author || s.meta.owner || '—' }}</span>
          <span class="sc-time">{{ relTime(stampOf(s)) }}</span>
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
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { scenarioDetailUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const size = useCardSize()
const store = useScenarioComposerStore()

const stampOf = (s: Scenario) => s.meta.updateTime || s.meta.createTime || ''

// 与 ScenariosPublic.vue 同一谓词:public 才进本卡 —— §7 第 6 条计数同源。
const rows = computed(() =>
  store.scenarios
    .filter((s) => s.visibility === 'public')
    .sort((a, b) => stampOf(b).localeCompare(stampOf(a))),
)

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))
const authorCount = computed(
  () => new Set(rows.value.map((s) => s.meta.author || s.meta.owner).filter(Boolean)).size,
)
const failed = computed(() => store.scenariosStatus === 'error')

const wbT = (suffix: string) => `wb-card-public-scenarios-${suffix}`

onMounted(() => { void store.ensureScenarios() })
</script>

<style scoped>
.wcard { display: flex; flex-direction: column; gap: 8px; min-height: 0; }

/* ── 题头(卡形制统一:图标+标题+计数+深链+分隔线,§2)─────── */
.chead {
  display: flex; align-items: center; gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e1e5eb;
}
.chead-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 7px; flex: none;
}
.ci-green { color: #15803d; background: #e4f5ea; }
.chead-title { font-size: 13.5px; font-weight: 700; color: #10151c; }
.chead-count {
  @apply text-caption font-bold;
  padding: 0 7px;
  color: #64748b; background: #f1f5f9; border-radius: 999px;
}
.chead-spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

/* ── S 档:结论面 ───────────────────────────────────────────── */
.s-body { display: flex; flex-direction: column; gap: 2px; }
.s-stats { display: flex; gap: 14px; }
.s-stat { margin: 0; font-size: 11px; color: #64748b; }
.s-stat b { display: block; font-size: 22px; font-weight: 700; line-height: 1.15; color: #10151c; }

/* ── 场景行(网格列:名称 1fr / 作者 / 时间)────────────────── */
.rows { display: flex; flex-direction: column; gap: 2px; }
.sc-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  margin: 0 -8px;
  font-size: 12px;
  color: inherit; text-decoration: none;
  border-radius: 7px;
  transition: background 0.12s ease;
}
.sc-row:hover { background: #f6f8fa; }
.sc-name {
  min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sc-starred { color: #eab308; }
.sc-author {
  padding: 1px 7px; font-size: 10.5px; font-weight: 600;
  color: #475569; background: #f1f5f9; border-radius: 4px; white-space: nowrap;
}
.sc-time { font-size: 11px; color: #94a3b8; white-space: nowrap; }

.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 16px 0 8px; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta {
  padding: 4px 14px; font-size: 12.5px; font-weight: 600;
  color: #2f6fed; text-decoration: none;
  border: 1px solid #bcd0f7; border-radius: 6px;
  transition: background 0.12s ease;
}
.cta:hover { background: #e7efff; }
</style>
