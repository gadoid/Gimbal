<!-- NotificationBell.vue — 通知铃铛(P1b/M2.5,权限方案 §3.3)。
     挂点:侧栏底部(UserBadge footer/compact,anchor-rail)、收拢顶条(bar)。
     30s 轮询 unread-count(不上长连接:活跃执行页已有 1s 轮询先例,
     为一个铃铛引入 WebSocket/SSE 不划算);顺带比对 roleVersion,
     变了 → refetch me(localStorage 角色快照的收敛钩子,§1.3 第六轮)。
     下拉:最近通知(未读优先)+ 全部已读;底部「查看全部」→ 通知中心、
     「管理通知类型」→ 个人设置 #notify(2026-11-12 弹层内嵌按 type
     开关退役 —— 偏好管理收口到个人设置,弹层只管流水)。 -->
<template>
  <Popover v-model:open="open">
    <!-- 侧栏底部落点:320px 面板对 200px 侧栏,无论贴锚上弹还是左对齐
         都会挤进导航轨。改锚整条侧栏、向右侧栏外(浅色内容区)弹出。 -->
    <PopoverAnchor v-if="anchorRail" as-child>
      <span class="rail-anchor" aria-hidden="true"></span>
    </PopoverAnchor>
    <PopoverTrigger as-child>
      <button
        class="relative h-[26px] cursor-pointer rounded-chip border border-white/20 bg-transparent px-2 text-slate-300 transition-colors hover:border-signal hover:text-white"
        data-testid="notification-bell"
        aria-label="通知"
        @click="onOpen"
      >
        <BellIcon class="size-3.5" />
        <span
          v-if="count > 0"
          class="absolute -right-1 -top-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-red-500 px-0.5 text-[9px] font-semibold text-white"
          data-testid="notification-badge"
        >{{ count > 99 ? '99+' : count }}</span>
      </button>
    </PopoverTrigger>
    <PopoverContent :side="anchorRail ? 'right' : 'bottom'" align="end" :side-offset="6" class="w-80 p-0">
      <div class="flex items-center justify-between border-b px-3 py-2">
        <span class="text-sm font-medium">通知</span>
        <button
          class="text-caption text-slate-500 hover:text-signal"
          data-testid="notification-read-all"
          @click="onReadAll"
        >全部已读</button>
      </div>

      <div class="max-h-72 overflow-y-auto">
        <div v-if="loading" class="px-3 py-4 text-caption text-slate-500">加载中…</div>
        <div v-else-if="!items.length" class="px-3 py-4 text-caption text-slate-500">
          暂无通知
        </div>
        <button
          v-for="n in items"
          :key="n.id"
          class="block w-full border-b border-slate-100 px-3 py-2 text-left transition-colors last:border-0 hover:bg-slate-50"
          :class="{ 'bg-slate-50/60': !n.readAt }"
          :data-testid="`notification-item-${n.id}`"
          @click="onClickItem(n)"
        >
          <div class="flex items-center gap-1.5">
            <span v-if="!n.readAt" class="size-1.5 shrink-0 rounded-full bg-signal" />
            <span class="truncate text-body font-medium">{{ n.title }}</span>
          </div>
          <div class="mt-0.5 line-clamp-2 text-caption text-slate-500">{{ n.body }}</div>
          <div class="mt-0.5 text-[10px] text-slate-400">{{ relTime(n.createdAt) }}</div>
        </button>
      </div>

      <!-- F5(2026-09-23):弹层只留 30 条滚动,整页视图走通知中心 -->
      <button
        type="button"
        class="block w-full border-t px-3 py-2 text-center text-caption text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700"
        data-testid="bell-view-all"
        @click="open = false; router.push('/notifications')"
      >查看全部 →</button>

      <!-- 类型开关的管理收口到个人设置(2026-11-12):弹层不再内嵌
           按 type 开关 —— 偏好是低频设置,混在通知流水里既挤占弹层
           又让人误以为在这里调;个人设置 #notify 已有同一份偏好的
           开关面板(身份卡「通知偏好」同锚点)。 -->
      <button
        type="button"
        class="block w-full border-t px-3 py-2 text-center text-caption text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700"
        data-testid="bell-manage"
        @click="open = false; router.push('/profile/account#notify')"
      >管理通知类型 →</button>
    </PopoverContent>
  </Popover>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BellIcon } from '@radix-icons/vue'
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import * as api from '@/api/notifications'
import type { NotificationItem } from '@/api/notifications'
import { useAuthStore } from '@/stores/auth'
import { relTime } from '@/utils/datetime'

/** 锚整条侧栏轨道、面板弹到侧栏右侧内容区(侧栏底部铃铛专用)。
 * 默认 false = 锚铃铛本身、向下弹(收拢顶条等常规落点)。 */
defineProps<{ anchorRail?: boolean }>()

const POLL_MS = 30_000

const auth = useAuthStore()
const router = useRouter()
const open = ref(false)
const loading = ref(false)
const count = ref(0)
const items = ref<NotificationItem[]>([])
let timer: ReturnType<typeof setInterval> | null = null

async function poll() {
  // authz W6 只能改密门:强制改密期间其余接口一律 403 —— 轮询停摆
  // (评审 R4),改密成功后下一个 tick 自然恢复。
  if (auth.mustChangePassword) return
  try {
    const out = await api.unreadCount()
    count.value = out.count
    // 角色版本比对:变了 → refetch me(localStorage 快照收敛)
    const me = auth.currentUser
    if (out.roleVersion && me) {
      const localVer = (me as { updated_at?: string }).updated_at ?? ''
      if (localVer && out.roleVersion !== localVer) {
        void auth.fetchMe()
      }
    }
  } catch {
    /* 轮询软失败:下次再试 */
  }
}

async function loadList() {
  if (auth.mustChangePassword) return
  loading.value = true
  try {
    const out = await api.list({ page: 1, pageSize: 30 })
    items.value = out.items
    count.value = out.unread
  } finally {
    loading.value = false
  }
}

function onOpen() {
  if (!open.value) return
  void loadList()
}

async function onReadAll() {
  await api.markRead(null)
  await loadList()
  await poll()
}

async function onClickItem(n: NotificationItem) {
  if (!n.readAt) {
    await api.markRead([n.id]).catch(() => undefined)
    n.readAt = new Date().toISOString()
    count.value = Math.max(0, count.value - 1)
  }
  if (n.link) {
    open.value = false
    void router.push(n.link)
  }
}

onMounted(() => {
  void poll()
  timer = setInterval(poll, POLL_MS)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
/* 撑满侧栏轨道的隐形锚点:包含块刻意取最近定位祖先 = 侧栏根(fixed),
   与 DOM 层级无关 —— span 因此横跨侧栏全宽、贴其底缘,面板 side=right
   即从侧栏右缘弹入内容区、底部对齐页脚。pointer-events 关掉,只做几何。 */
.rail-anchor {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 8px;
  height: 44px;
  pointer-events: none;
}
</style>
