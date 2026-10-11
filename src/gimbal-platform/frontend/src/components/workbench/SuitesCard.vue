<!-- SuitesCard.vue — 工作台注册卡:我的用例集(→ /suites)。
     用例集组 2026-10-10 IA 调整新增,此前无工作台摘要卡。
     计数徽标 = 服务端 total(§7 第 6 条与完整页同源);行深链管理页
     (与 SuiteLibrary 行点击同语义:最近运行失败直达运行记录页签)。
     三档密度:S = 总数 + 最近更新时间;M/L = 最近用例集行 5/8。 -->
<template>
  <div data-testid="wb-card-suites" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="stack" :size="14" />
      </span>
      <span class="chead-title">我的用例集</span>
      <span class="chead-count">{{ total }}</span>
      <span class="chead-spacer" />
      <router-link to="/suites" class="manage-link">我的用例集 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ total }}</b>个用例集</p>
        <p class="s-stat">最近更新 {{ first ? relTime(first.updatedAt || '') : '—' }}</p>
      </div>
    </div>

    <template v-else>
      <div v-if="rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.suiteId"
          :to="openTarget(s)"
          class="su-row wrow"
          :data-testid="`wb-suite-row-${s.suiteId}`"
        >
          <span class="wrow-name">
            {{ s.name }}
            <span v-if="s.isDraft" class="su-draft" title="草稿">草稿</span>
          </span>
          <span class="wrow-tag">{{ MODE_LABEL[s.mode] || s.mode }}</span>
          <span class="wrow-time">{{ relTime(s.updatedAt || '') }}</span>
        </router-link>
      </div>
      <div v-else-if="failed" class="card-empty">
        <p>用例集加载失败 — 稍后在用例集页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有用例集 —— 把场景归组编排起来</p>
        <router-link to="/suites" class="cta">去新建 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { listSuites, type SuiteSummary } from '@/api/suites'
import { relTime } from '@/utils/datetime'
import { MODE_LABEL } from '@/utils/suiteStructure'

const size = useCardSize()
const rows = ref<SuiteSummary[]>([])
const total = ref(0)
const failed = ref(false)

const first = computed(() => rows.value[0])
/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))

/** 与 SuiteLibrary 行点击同语义:最近运行失败 → 运行记录页签。 */
function openTarget(s: SuiteSummary): string {
  const failedRun = s.latestRun
    && ['failed', 'error', 'halted'].includes(s.latestRun.status ?? '')
  return failedRun ? `/suites/${s.suiteId}?tab=runs` : `/suites/${s.suiteId}`
}

const wbT = (suffix: string) => `wb-card-suites-${suffix}`

onMounted(async () => {
  try {
    const env = await listSuites({ scope: 'mine', page_size: 8 })
    rows.value = env.items
    total.value = env.total
  } catch {
    failed.value = true
  }
})
</script>

<style scoped>
/* 形制在基座 scenario-lib.css;本卡只留行列宽与草稿章。 */
.su-row { grid-template-columns: minmax(0, 1fr) auto auto; }
.su-draft {
  font-size: 10px; color: #b45309; background: #fef3c7;
  border-radius: 3px; padding: 0 4px; margin-left: 4px;
}
</style>
