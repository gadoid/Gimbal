<!-- AdaptationCard.vue — 工作台注册卡:适配中心(→ /adaptations)。
     两条数据面各自复用既有端点,不另开口子:
       · 待处理数 = adaptations store(侧栏徽章已 ensureBadgeLoaded,
         卡上再调一次是单飞合流,零额外请求;member 侧栏不发,这里也不发)
       · 批次列表 = listBatches(admin 全量 / member 'mine'),与完整页同口径
     三档密度(§4):S = 待处理 + 批次数结论;M/L = 批次行 5/8。 -->
<template>
  <div data-testid="wb-card-adaptations" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-gold">
        <SlibIcon name="activity" :size="14" />
      </span>
      <span class="chead-title">适配中心</span>
      <span class="chead-count">{{ headline }}</span>
      <span class="chead-spacer" />
      <router-link to="/adaptations" class="manage-link">全部 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p v-if="auth.isAdmin" class="s-stat" :class="{ 'st-warn': store.pendingCount > 0 }">
          <b>{{ store.pendingCount }}</b>待适配
        </p>
        <p class="s-stat"><b>{{ batches.length }}</b>个批次</p>
      </div>
    </div>

    <template v-else>
      <div v-if="loading" class="card-empty"><p>加载中…</p></div>
      <div v-else-if="batches.length" class="rows">
        <router-link
          v-for="b in visible"
          :key="b.batchId"
          :to="`/adaptations/batches/${encodeURIComponent(b.batchId)}`"
          class="ad-row wrow"
          :data-testid="`wb-ad-row-${b.batchId}`"
        >
          <span class="wrow-name mono" :title="b.endpointId">{{ b.endpointId }}</span>
          <span class="ad-ver mono">{{ b.fromVersion }}→{{ b.toVersion }}</span>
          <span class="wrow-tag">{{ BATCH_LABEL[b.status] }}</span>
          <span class="wrow-time">{{ relTime(b.createdAt) }}</span>
        </router-link>
        <p v-if="batches.length > visible.length" class="more-hint">
          还有 {{ batches.length - visible.length }} 个批次 — 到完整页查看
        </p>
      </div>
      <div v-else-if="error" class="card-empty"><p>{{ error }} — 稍后在适配中心重试</p></div>
      <div v-else class="card-empty">
        <p>{{ auth.isAdmin ? '目录还没有需要适配的变更' : '你还没有发起过适配批次' }}</p>
        <router-link to="/adaptations" class="cta">去适配中心 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { useAdaptationsStore } from '@/stores/adaptations'
import { useAuthStore } from '@/stores/auth'
import { BATCH_LABEL } from '@/composables/useActivityTimeline'
import { listBatches, type BatchOut } from '@/api/adaptations'
import { relTime } from '@/utils/datetime'

const size = useCardSize()
const store = useAdaptationsStore()
const auth = useAuthStore()

const batches = ref<BatchOut[]>([])
const loading = ref(true)
const error = ref('')

/** 卡头计数与 S 档结论同一个数:admin 看待处理,member 看自己的批次。 */
const headline = computed(() =>
  auth.isAdmin ? `${store.pendingCount} 个待处理` : `${batches.value.length} 个批次`,
)

/** M = 5 行;L = 8 行(按发起时间倒序,最近在先) */
const visible = computed(() => batches.value.slice(0, size.value === 'L' ? 8 : 5))

const wbT = (suffix: string) => `wb-card-adaptations-${suffix}`

onMounted(async () => {
  if (auth.isAdmin) void store.ensureBadgeLoaded()
  try {
    const env = await listBatches({ scope: auth.isAdmin ? undefined : 'mine' })
    const list = env.items
    batches.value = list.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  } catch {
    error.value = '适配批次加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 形制在基座;这里只给行列宽、版本箭头灰阶与"有事要做"的琥珀。 */
.ad-row { grid-template-columns: minmax(0, 1fr) auto auto auto; }
.ad-ver { color: var(--sl-ink-3); white-space: nowrap; }
.st-warn b { color: var(--sl-warn); }
</style>
