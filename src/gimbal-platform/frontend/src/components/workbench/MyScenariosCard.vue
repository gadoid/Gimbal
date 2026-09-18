<!-- MyScenariosCard.vue — 工作台注册卡:我的场景(→ /scenarios/mine)。
     分桶谓词必须与完整页同源(visibility !== 'public'),§7 第 6 条:
     计数徽标与进入后的页面一致,不另写一套判定。
     三档密度(§4):S = 总数 + 过期数结论;M/L = 最近编辑的场景行 5/8。
     行 testid 前缀 wb-mine-row-*(关注卡用 wb-sc-row-*,不可复用)。 -->
<template>
  <div data-testid="wb-card-my-scenarios" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        </svg>
      </span>
      <span class="chead-title">我的场景</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/scenarios/mine" class="manage-link">我的场景 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>我的场景</p>
        <p class="s-stat st-expired"><b>{{ expiredCount }}</b>已过期</p>
      </div>
    </div>

    <template v-else>
      <div v-if="rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.meta.scenarioId"
          :to="scenarioDetailUrl(s.meta.scenarioId)"
          class="sc-row"
          :data-testid="`wb-mine-row-${s.meta.scenarioId}`"
        >
          <span class="sc-name-cell">
            <span class="sc-name" :title="s.meta.name || s.meta.scenarioId">{{ s.meta.name || s.meta.scenarioId }}</span>
            <span v-if="s.meta.expire" class="sc-expired">已过期</span>
          </span>
          <span class="sc-module">{{ s.meta.module || '未分类' }}</span>
          <span class="sc-time">{{ relTime(stampOf(s)) }}</span>
        </router-link>
      </div>
      <div v-else-if="failed" class="card-empty">
        <p>场景加载失败 — 稍后在我的场景页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有属于你的场景 — 从空白开始编排</p>
        <router-link to="/scenarios/mine" class="cta">去我的场景 →</router-link>
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

// 与 ScenariosMine.vue 同一谓词:非 public 即我的 —— §7 第 6 条,卡上
// 计数必须与点进完整页看到的条数一致。filter 已产新数组,sort 不碰 store。
const rows = computed(() =>
  store.scenarios
    .filter((s) => s.visibility !== 'public')
    .sort((a, b) => stampOf(b).localeCompare(stampOf(a))),
)

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))
const expiredCount = computed(() => rows.value.filter((s) => s.meta.expire).length)
const failed = computed(() => store.scenariosStatus === 'error')

const wbT = (suffix: string) => `wb-card-my-scenarios-${suffix}`

// 三张场景卡同帧挂载,ensureScenarios 合流成一次请求(不复用 store 就是 3 连发)。
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
.ci-blue { color: #2f6fed; background: #e7effe; }
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
.st-expired b { color: #b45309; }

/* ── 场景行(网格列:名称 1fr / 模块 / 时间)────────────────── */
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
.sc-name-cell { display: flex; align-items: center; gap: 6px; min-width: 0; }
.sc-name {
  min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sc-expired {
  flex: none; padding: 1px 6px; font-size: 10px; font-weight: 600;
  color: #b45309; background: #fef3e2; border-radius: 4px;
}
.sc-module {
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
