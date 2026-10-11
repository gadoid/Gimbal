<!-- NotificationsCard.vue — 工作台注册卡:通知(→ /notifications)。
     通知是唯一没有工作台摘要卡的一级模块(铃铛徽标只在顶栏闪)。
     卡头计数 = 未读数(与铃铛同源语义);行 = 最近通知,未读带点,
     点击走通知自带的 link(缺省进通知中心)。三档密度:S = 未读/总数
     结论;M/L = 最近通知行 5/8。 -->
<template>
  <div data-testid="wb-card-notifications" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-gold">
        <SlibIcon name="bell" :size="14" />
      </span>
      <span class="chead-title">通知</span>
      <span class="chead-count" :class="{ 'nt-unread': unread > 0 }">{{ unread }}</span>
      <span class="chead-spacer" />
      <router-link to="/notifications" class="manage-link">通知中心 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ unread }}</b>条未读</p>
        <p class="s-stat">共 {{ total }} 条</p>
      </div>
    </div>

    <template v-else>
      <div v-if="rows.length" class="rows">
        <router-link
          v-for="n in visible"
          :key="n.id"
          :to="n.link || '/notifications'"
          class="nt-row wrow"
          :data-testid="`wb-nt-row-${n.id}`"
        >
          <span class="nt-dot" :class="{ on: !n.readAt }" />
          <span class="wrow-name">{{ n.title }}</span>
          <span class="wrow-tag">{{ typeLabel(n.type) }}</span>
          <span class="wrow-time">{{ relTime(n.createdAt) }}</span>
        </router-link>
      </div>
      <div v-else-if="failed" class="card-empty">
        <p>通知加载失败 — 稍后在通知中心重试</p>
      </div>
      <div v-else class="card-empty">
        <p>没有通知 —— 干干净净</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import {
  list, NOTIFICATION_TYPE_LABELS, type NotificationItem,
} from '@/api/notifications'
import { relTime } from '@/utils/datetime'

const size = useCardSize()
const rows = ref<NotificationItem[]>([])
const unread = ref(0)
const total = ref(0)
const failed = ref(false)

/** M = 5 行;L = 8 行(最近在先 —— 后端按 createdAt 倒序) */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))

function typeLabel(t: string): string {
  return NOTIFICATION_TYPE_LABELS[t as keyof typeof NOTIFICATION_TYPE_LABELS] ?? t
}

const wbT = (suffix: string) => `wb-card-notifications-${suffix}`

onMounted(async () => {
  try {
    const env = await list({ pageSize: 8 })
    rows.value = env.items
    unread.value = env.unread
    total.value = env.total
  } catch {
    failed.value = true
  }
})
</script>

<style scoped>
/* 形制在基座 scenario-lib.css;本卡留行列宽、未读点与卡头未读高亮。 */
.nt-row {
  grid-template-columns: 8px minmax(0, 1fr) auto auto;
  align-items: center;
}
.nt-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: transparent; border: 1px solid rgb(100 116 139 / 40%);
}
.nt-dot.on { background: #d97706; border-color: #d97706; }
.nt-unread { color: #b45309; font-weight: 700; }
</style>
