<!-- MyScenariosCard.vue — 工作台注册卡:我的场景(→ /scenarios/mine)。
     分桶谓词必须与完整页同源(visibility !== 'public'),§7 第 6 条:
     计数徽标与进入后的页面一致,不另写一套判定。
     三档密度(§4):S = 总数 + 过期数结论;M/L = 最近编辑的场景行 5/8。
     行 testid 前缀 wb-mine-row-*(关注卡用 wb-sc-row-*,不可复用)。 -->
<template>
  <div data-testid="wb-card-my-scenarios" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="folder" :size="14" />
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
          class="sc-row wrow"
          :data-testid="`wb-mine-row-${s.meta.scenarioId}`"
        >
          <span class="sc-name-cell">
            <span class="wrow-name" :title="s.meta.name || s.meta.scenarioId">{{ s.meta.name || s.meta.scenarioId }}</span>
            <span v-if="s.meta.expire" class="sc-expired">已过期</span>
          </span>
          <span class="wrow-tag">{{ s.meta.module || '未分类' }}</span>
          <span class="wrow-time">{{ relTime(stampOf(s)) }}</span>
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
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
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
/* 形制在基座 scenario-lib.css(.wcard / .chead / .s-body / .wrow /
   .card-empty / .cta);我的场景卡只留 S 档双数字、行列宽与过期 chip。 */

/* S 档:总数 + 过期数两个结论(.s-stats/.s-stat 形制在基座) */
.st-expired b { color: var(--sl-warn); }

/* 场景行:名称 1fr / 模块 / 时间 */
.sc-row { grid-template-columns: minmax(0, 1fr) auto auto; }
.sc-name-cell { display: flex; align-items: center; gap: 6px; min-width: 0; }
.sc-expired {
  flex: none; padding: 1px 6px; font-size: 10px; font-weight: 600;
  color: var(--sl-warn); background: var(--sl-warn-soft); border-radius: 4px;
}
</style>
