<!--
  NotificationsCenter.vue — 通知中心(F5,2026-09-23 批次)。

  两个 tab:通知(全员)/ 审计(仅 admin)。审计面板 = AuditLogPanel
  从 /admin/users 原样迁来复用(组件不改,数据口径不变 —— 不做用户
  维度审计,普通场景 CRUD 恒不进 audit_logs,见方案 §5.3)。非 admin
  不渲染 tab 切换控件,只有通知列表;权限守卫双层:渲染层不出现 +
  后端 /admin/audit-logs 对非 admin 403。
  通知与审计数据形状不同(时间线卡片 vs 表格),不强行同组件,共享
  色板/间距/空态。
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { useAuthStore } from '@/stores/auth'
import {
  list, markRead, NOTIFICATION_TYPE_LABELS,
  type NotificationItem, type SwitchableType,
} from '@/api/notifications'
import AuditLogPanel from '@/components/admin/AuditLogPanel.vue'
import { Pagination } from '@/components/ui/pagination'
import { usePagerSize } from '@/composables/usePagerSize'
import { mediumDateTime } from '@/utils/datetime'

const auth = useAuthStore()
const router = useRouter()

const tab = ref<'notify' | 'audit'>('notify')
const items = ref<NotificationItem[]>([])
const unread = ref(0)
const loading = ref(false)
// 2026-09-23 分页批次:后端信封升级 page/pageSize/total,原「最近 50 条」
// 截断改为真分页(未读优先排序保持不变);每页行数存用户偏好。
const page = ref(1)
const { pageSize } = usePagerSize('notifications', 20)
const total = ref(0)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const typeLabel = (t: string) =>
  NOTIFICATION_TYPE_LABELS[t as SwitchableType] ?? t

async function load() {
  loading.value = true
  try {
    const r = await list({ page: page.value, pageSize: pageSize.value })
    items.value = r.items
    unread.value = r.unread
    total.value = r.total
    // 全部已读/过期清理后停在越界页 → 回末页重取一次。
    if (r.items.length === 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(r.total / pageSize.value))
      await load()
      return
    }
  } catch (e) {
    toast.error(`通知加载失败:${(e as Error).message}`)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(page, () => { void load() })
watch(pageSize, () => {
  if (page.value !== 1) page.value = 1
  else void load()
})

/** 点通知:未读先标读,再跳自带深链(通知的 link 是唯一去处)。 */
async function open(n: NotificationItem) {
  try {
    if (!n.readAt) {
      await markRead([n.id])
      n.readAt = new Date().toISOString()
      unread.value = Math.max(0, unread.value - 1)
    }
  } catch { /* 标读失败不拦跳转 */ }
  if (n.link) void router.push(n.link)
}

async function readAll() {
  try {
    await markRead(null)
    toast.success('已全部标读')
    await load()
  } catch (e) {
    toast.error(`操作失败:${(e as Error).message}`)
  }
}

const hasUnread = computed(() => unread.value > 0)
</script>

<template>
  <section class="nt-page">
    <header class="nt-head">
      <h1 class="nt-title">通知</h1>
      <p class="nt-sub">未读 {{ unread }} 条 · 通知类型可在「个人资料 → 通知偏好」按类关闭</p>
    </header>

    <div class="nt-tabs" data-testid="nt-tabs">
      <button
        type="button"
        class="nt-tab"
        :class="{ active: tab === 'notify' }"
        data-testid="nt-tab-notify"
        @click="tab = 'notify'"
      >通知<span v-if="hasUnread" class="nt-dot">{{ unread }}</span></button>
      <button
        v-if="auth.isAdmin"
        type="button"
        class="nt-tab"
        :class="{ active: tab === 'audit' }"
        data-testid="nt-tab-audit"
        @click="tab = 'audit'"
      >审计</button>
    </div>

    <!-- ── 通知 tab:时间线卡片 ─────────────────────────────── -->
    <div v-if="tab === 'notify'" class="nt-list">
      <div class="nt-toolbar">
        <span class="muted small">按时间倒序,未读优先</span>
        <span class="flex-1"></span>
        <button
          v-if="hasUnread"
          type="button"
          class="nt-ghost"
          data-testid="nt-read-all"
          @click="readAll"
        >全部已读</button>
        <button
          type="button"
          class="nt-ghost"
          data-testid="nt-refresh"
          :disabled="loading"
          @click="load"
        >{{ loading ? '加载中…' : '↻ 刷新' }}</button>
      </div>

      <p v-if="!items.length && !loading" class="nt-empty">
        还没有通知 —— 执行完成、分享、公告都会出现在这里。
      </p>

      <button
        v-for="n in items"
        v-else
        :key="n.id"
        type="button"
        class="nt-card"
        :class="{ unread: !n.readAt }"
        :data-testid="`nt-item-${n.id}`"
        @click="open(n)"
      >
        <div class="nt-card-head">
          <span class="nt-type">{{ typeLabel(n.type) }}</span>
          <span class="nt-title">{{ n.title }}</span>
          <span v-if="!n.readAt" class="nt-unread-dot" title="未读"></span>
        </div>
        <p v-if="n.body" class="nt-body">{{ n.body }}</p>
        <span class="nt-time">{{ mediumDateTime(n.createdAt) }}</span>
      </button>

      <div class="nt-pager">
        <Pagination
          v-if="pageCount > 1 || total > 0"
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="total"
          show-page-size
          show-jump
        />
      </div>
    </div>

    <!-- ── 审计 tab(仅 admin):复用面板,数据口径不变 ───────── -->
    <div v-if="tab === 'audit' && auth.isAdmin">
      <AuditLogPanel />
      <p class="muted small mt-2">
        审计只记特权写(角色变更/删号/重置密码/公告/carry/适配/别名);
        「我的资源发生过什么」看工作台时间线。
      </p>
    </div>
  </section>
</template>

<style scoped>
.nt-page { padding: 16px; max-width: 860px; margin: 0 auto; }
.nt-head { margin-bottom: 12px; }
.nt-title { font-size: 18px; font-weight: 700; margin: 0; }
.nt-sub { font-size: 12px; color: #64748b; margin: 4px 0 0; }
.nt-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--c-border, #e2e8f0); margin-bottom: 12px; }
.nt-tab {
  border: none; background: none; cursor: pointer;
  padding: 8px 14px; font-size: 13px; font-weight: 600; color: #64748b;
  border-bottom: 2px solid transparent;
}
.nt-tab.active { color: hsl(var(--primary)); border-bottom-color: hsl(var(--primary)); }
.nt-dot {
  margin-left: 6px; font-size: 11px; background: #ef4444; color: #fff;
  border-radius: 999px; padding: 1px 7px;
}
.nt-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.nt-ghost {
  border: 1px solid var(--c-border, #e2e8f0); background: none; border-radius: 6px;
  font-size: 12px; padding: 4px 10px; cursor: pointer; color: #334155;
}
.nt-ghost:hover { background: rgb(0 0 0 / 4%); }
.nt-list { display: flex; flex-direction: column; gap: 8px; }
.nt-card {
  text-align: left; border: 1px solid var(--c-border, #e2e8f0); border-radius: 8px;
  background: var(--c-surface, #fff); padding: 10px 12px; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px;
}
.nt-card:hover { border-color: hsl(var(--primary) / 40%); }
.nt-card.unread { border-left: 3px solid hsl(var(--primary)); }
.nt-card-head { display: flex; align-items: center; gap: 8px; }
.nt-type {
  font-size: 11px; flex: none; padding: 1px 8px; border-radius: 999px;
  background: rgb(100 116 139 / 10%); color: #64748b;
}
.nt-title { font-weight: 600; font-size: 13px; }
.nt-unread-dot { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; flex: none; }
.nt-body { font-size: 12px; color: #64748b; margin: 0; }
.nt-time { font-size: 11px; color: #94a3b8; }
.nt-empty { color: #94a3b8; text-align: center; padding: 32px 0; }
.nt-pager { display: flex; justify-content: flex-end; margin-top: 4px; }
.muted { color: #64748b; }
.small { font-size: 12px; }
</style>
