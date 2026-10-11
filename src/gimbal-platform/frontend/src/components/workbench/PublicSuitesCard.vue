<!-- PublicSuitesCard.vue — 工作台注册卡:公共用例集(→ /suites/public)。
     与 PublicScenariosCard 同构(§7:分桶谓词与完整页同源 —— 这里直接
     取 visibility=public 列表,计数徽标 = 服务端 total)。行深链公共
     Suite 只读管理页(公共资源先复制再跑,卡上不给运行入口)。
     三档密度:S = 总数 + 贡献者数(首屏样本,与公共场景卡同口径);
     M/L = 最新上架的用例集行 5/8。 -->
<template>
  <div data-testid="wb-card-public-suites" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-green">
        <SlibIcon name="globe" :size="14" />
      </span>
      <span class="chead-title">公共用例集</span>
      <span class="chead-count">{{ total }}</span>
      <span class="chead-spacer" />
      <router-link to="/suites/public" class="manage-link">公共用例集 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ total }}</b>公共用例集</p>
        <p class="s-stat"><b>{{ contributorCount }}</b>贡献者</p>
      </div>
    </div>

    <template v-else>
      <div v-if="rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.suiteId"
          :to="`/suites/${s.suiteId}`"
          class="psu-row wrow"
          :data-testid="`wb-pub-suite-row-${s.suiteId}`"
          title="打开(只读)"
        >
          <span class="wrow-name">{{ s.name }}</span>
          <span class="wrow-tag">{{ s.ownerName || '—' }}</span>
          <span class="wrow-time">{{ relTime(s.updatedAt || '') }}</span>
        </router-link>
      </div>
      <div v-else-if="failed" class="card-empty">
        <p>公共用例集加载失败 — 稍后在公共用例集页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>公共库还是空的 —— 在我的用例集「⋯」菜单发布后出现在这里</p>
        <router-link to="/suites" class="cta">去我的用例集 →</router-link>
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

const size = useCardSize()
const rows = ref<SuiteSummary[]>([])
const total = ref(0)
const failed = ref(false)

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))
/** 首屏样本的贡献者数(公共场景卡同口径:窗口内去重) */
const contributorCount = computed(
  () => new Set(rows.value.map((s) => s.ownerName).filter(Boolean)).size)

const wbT = (suffix: string) => `wb-card-public-suites-${suffix}`

onMounted(async () => {
  try {
    const env = await listSuites({ visibility: 'public', page_size: 8 })
    rows.value = env.items
    total.value = env.total
  } catch {
    failed.value = true
  }
})
</script>

<style scoped>
/* 形制在基座 scenario-lib.css;本卡只留行列宽。 */
.psu-row { grid-template-columns: minmax(0, 1fr) auto auto; }
</style>
