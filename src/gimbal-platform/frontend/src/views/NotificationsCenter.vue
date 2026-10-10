<!--
  NotificationsCenter.vue — 通知中心(F5,2026-09-23 批次;2026-10-10
  风格轮对齐平台规范:根容器复用全站 .slib 三壳标准、页头换 PageHead、
  主色回归 indigo --accent 系,弃用本页自带的 860px 窄居中布局与
  shadcn hsl(primary) 色板)。

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
import PageHead from '@/components/scenario-lib/PageHead.vue'
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
  <section class="slib nt-page">
    <PageHead icon="bell" title="通知"
      :subtitle="`未读 ${unread} 条 · 按时间倒序,未读优先 · 通知类型可在「个人资料 → 通知偏好」按类关闭`">
      <template #right>
        <button
          v-if="tab === 'notify' && hasUnread"
          type="button"
          class="nt-action"
          data-testid="nt-read-all"
          @click="readAll"
        >全部已读</button>
        <button
          v-if="tab === 'notify'"
          type="button"
          class="nt-action ghost"
          data-testid="nt-refresh"
          :disabled="loading"
          @click="load"
        >{{ loading ? '加载中…' : '↻ 刷新' }}</button>
      </template>
    </PageHead>

    <div class="nt-body">
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
        <p class="nt-note">
          审计只记特权写(角色变更/删号/重置密码/公告/carry/适配/别名);
          「我的资源发生过什么」看工作台时间线。
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 容器/页头/主色全部走全站规范:根节点挂全局 .slib(1480 三壳标准),
   主按钮 indigo --accent 系,卡片 lib-card 同款边框与圆角。 */
.nt-body { display: flex; flex-direction: column; gap: 14px; margin-top: 14px; }
.nt-tabs { display: flex; gap: 4px; border-bottom: 1px solid rgb(100 116 139 / 15%); }
.nt-tab {
  border: none; background: none; cursor: pointer;
  padding: 8px 14px; font-size: 13px; font-weight: 600; color: rgb(100 116 139);
  border-bottom: 2px solid transparent;
}
.nt-tab.active { color: var(--accent, #4338ca); border-bottom-color: var(--accent, #4338ca); }
.nt-dot {
  margin-left: 6px; font-size: 11px; background: #ef4444; color: #fff;
  border-radius: 999px; padding: 1px 7px;
}
.nt-action {
  font-size: 12px; padding: 5px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.nt-action:hover { background: var(--accent-soft-border); }
.nt-action.ghost {
  color: inherit; background: transparent;
  border: 1px solid rgb(100 116 139 / 30%);
}
.nt-action.ghost:hover { background: rgb(0 0 0 / 4%); }
.nt-action:disabled { opacity: .5; cursor: not-allowed; }
.nt-list { display: flex; flex-direction: column; gap: 8px; }
.nt-card {
  text-align: left; border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  background: transparent; padding: 10px 14px; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px;
}
.nt-card:hover { border-color: var(--accent-soft-border); background: rgb(59 130 246 / 3%); }
.nt-card.unread { border-left: 3px solid var(--accent, #4338ca); }
.nt-card-head { display: flex; align-items: center; gap: 8px; }
.nt-type {
  font-size: 11px; flex: none; padding: 2px 8px; border-radius: 999px;
  background: rgb(100 116 139 / 8%); color: rgb(100 116 139);
  border: 1px solid rgb(100 116 139 / 22%);
}
.nt-title { font-weight: 500; font-size: 13px; }
.nt-unread-dot { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; flex: none; }
.nt-body { font-size: 12px; color: rgb(100 116 139); margin: 0; }
.nt-time { font-size: 11px; color: rgb(100 116 139 / 70%); }
.nt-empty {
  padding: 34px 0; text-align: center; color: rgb(100 116 139); font-size: 13px;
}
.nt-pager { display: flex; justify-content: flex-end; margin-top: 4px; }
.nt-note { font-size: 12px; color: rgb(100 116 139); margin-top: 8px; }
</style>
