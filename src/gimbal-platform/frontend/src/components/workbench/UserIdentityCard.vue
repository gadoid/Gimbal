<!-- UserIdentityCard.vue — 工作台右侧栏顶端身份卡(webhook v4 §8/D17;
     原型 IdentityCard)。按 ``identity.card`` 偏好渲染:常驻统计(≤ 4,
     可点跳转)、告警(按类开关过滤、严重度排序、最多 3 条 +「另有 N
     条」)、快捷入口 ≤ 4;数据来自 ``/me/summary``(一次取回)。偏好与
     预览由 IdentityCardSection 经 props 注入(preview 模式不再自取)。 -->
<template>
  <section v-if="user" class="id-card" data-testid="wb-rail-identity">
    <div class="id-hero">
      <div class="id-text">
        <h3 class="id-name" :title="displayName">{{ displayName }}</h3>
        <p class="id-welcome">{{ greeting }}，欢迎回来</p>
        <div class="id-chips">
          <span class="id-user mono">@{{ user.username }}</span>
          <span class="id-role" :class="auth.role">{{ { user: '用户', admin: '管理员', super_admin: '超级管理员' }[auth.role] }}</span>
        </div>
      </div>
      <span class="avatar" :style="{ background: avatarColor(user.id) }" :title="displayName" aria-hidden="true">
        {{ initial }}
      </span>
    </div>

    <!-- 常驻统计(≤ 4;两列网格自适应) -->
    <div class="id-stats" :class="{ grid2: statItems.length > 2 }">
      <RouterLink
        v-for="s in statItems" :key="s.id" class="id-stat"
        :to="s.to" :title="s.hint"
      >
        <span class="label">{{ s.label }}</span>
        <span class="value mono" :class="s.danger ? 'danger' : ''">
          {{ loaded ? s.value : '—' }}
        </span>
      </RouterLink>
    </div>

    <!-- 告警(按类开关过滤;最多 3 条 +「另有 N 条」) -->
    <div v-if="alertItems.length" class="id-alerts">
      <RouterLink
        v-for="a in alertItems" :key="a.id" class="id-alert"
        :class="a.severity" :to="a.link"
      >
        <span class="flex min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap">{{ a.title }}</span>
        <span class="action">{{ a.action }}</span>
      </RouterLink>
      <RouterLink
        v-if="moreAlerts > 0" class="more" to="/notifications"
      >另有 {{ moreAlerts }} 条 · 查看全部</RouterLink>
    </div>

    <!-- 快捷入口(≤ 4) -->
    <div v-if="shortcutItems.length" class="id-shortcuts">
      <RouterLink v-for="s in shortcutItems" :key="s.id" class="pill" :to="s.to">{{ s.label }}</RouterLink>
    </div>

    <div v-if="!preview" class="id-footer">
      <RouterLink class="link" to="/profile/card">自定义身份卡</RouterLink>
      <RouterLink class="link" to="/profile">个人设置</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { avatarColor, avatarInitial } from '@/utils/avatarColor'
import http from '@/api/http'

const props = defineProps<{
  /** 偏好注入(IdentityCardSection 预览);缺省自取 identity.card */
  config?: { stats: string[]; alerts: Record<string, boolean>; shortcuts: string[] }
  /** 摘要注入(预览);缺省自取 /me/summary */
  summary?: { stats: Record<string, number>; alerts: AlertItem[] }
  /** 预览模式:不自取数据、不出底部链接 */
  preview?: boolean
}>()

interface AlertItem {
  id: string
  class: string
  severity: 'error' | 'warn' | 'info'
  title: string
  action: string
  link: string
}

const auth = useAuthStore()
const user = computed(() => auth.currentUser)
const displayName = computed(() => user.value?.display_name || user.value?.username || '')
const initial = computed(() => avatarInitial(displayName.value))

/** 问候语按进入页面那一刻的时段取一次 —— 挂着页面跨时段不刷新是
 *  刻意的:它是一句招呼,不是需要守时数的状态。 */
const HOUR = new Date().getHours()
const greeting = HOUR < 6 ? '凌晨好' : HOUR < 11 ? '早上好' : HOUR < 13 ? '中午好'
  : HOUR < 18 ? '下午好' : '晚上好'

// ── 注册表(id 与后端 /me/summary、identity.card 的键对齐)────────
const STAT_DEFS: Record<string, { label: string; to: string; hint?: string; danger?: boolean }> = {
  private_scenarios: { label: '私有场景', to: '/scenarios/mine', hint: '点击进入我的场景' },
  follows: { label: '关注', to: '/scenarios/follows' },
  tokens: { label: '访问令牌', to: '/profile/tokens', hint: '有效令牌数' },
  today_failed: { label: '今日执行失败', to: '/executions?status=failed', danger: true },
  subscribed_integrations: { label: '订阅的集成任务', to: '/integrations', hint: '含已暂停' },
  auths: { label: '我的凭证', to: '/auths' },
  unread: { label: '未读通知', to: '/notifications' },
}

const SHORTCUT_DEFS: Record<string, { label: string; to: string }> = {
  tokens: { label: '访问令牌', to: '/profile/tokens' },
  auths: { label: '我的凭证', to: '/auths' },
  password: { label: '修改密码', to: '/profile/account' },
  notify: { label: '通知偏好', to: '/profile/account#notify' },
  create_token: { label: '创建令牌', to: '/profile/tokens' },
}

const DEFAULT_STATS = ['private_scenarios', 'follows', 'tokens']

// ── 数据(注入或自取)──────────────────────────────────────────
const ownCfg = ref<{ stats: string[]; alerts: Record<string, boolean>; shortcuts: string[] } | null>(null)
const ownSummary = ref<{ stats: Record<string, number>; alerts: AlertItem[] } | null>(null)
const loaded = computed(() => !!(props.summary ?? ownSummary.value))

const cfg = computed(() => props.config ?? ownCfg.value ?? {
  stats: DEFAULT_STATS, alerts: {}, shortcuts: [],
})
const summary = computed(() => props.summary ?? ownSummary.value)

const statItems = computed(() => {
  const stats = summary.value?.stats ?? {}
  return cfg.value.stats
    .filter((id) => STAT_DEFS[id])
    .map((id) => ({
      id,
      ...STAT_DEFS[id],
      value: stats[id] ?? 0,
    }))
})

const alertItems = computed(() => {
  const all = summary.value?.alerts ?? []
  const on = all.filter((a) => cfg.value.alerts[a.class] !== false)
  return on.slice(0, 3)
})
const moreAlerts = computed(() => {
  const all = summary.value?.alerts ?? []
  return Math.max(0, all.filter((a) => cfg.value.alerts[a.class] !== false).length - 3)
})

const shortcutItems = computed(() =>
  cfg.value.shortcuts
    .filter((id) => SHORTCUT_DEFS[id])
    .map((id) => ({ id, ...SHORTCUT_DEFS[id] })))

onMounted(async () => {
  if (props.preview) return
  try {
    const prefs = await http.get<{ items: Record<string, unknown> }>('/me/preferences')
    const saved = prefs.data.items['identity.card'] as
      { stats: string[]; alerts: Record<string, boolean>; shortcuts: string[] } | undefined
    if (saved) ownCfg.value = saved
  } catch { /* 偏好不可达 → 默认 */ }
  try {
    const out = await http.get<{ stats: Record<string, number>; alerts: AlertItem[] }>(
      '/me/summary')
    ownSummary.value = out.data
  } catch { /* 摘要不可达 → 统计显示 — */ }
})
</script>

<style scoped>
/* 与 registry 卡同一套形制(顶部 3px 分类色边 + 圆角 12),静止阴影比
   卡片区深一档:右栏是常驻层,视觉上要比可组装的卡更"重"。
   饱和色一律走 Signal token(@apply),组件里不写 accent/status hex 字面量。 */
.id-card {
  @apply overflow-hidden rounded-card border border-signal-line border-t-signal bg-signal-card;
  border-top-width: 3px;
  box-shadow: 0 2px 10px rgba(16, 21, 28, 0.07);
}

.id-hero {
  @apply flex items-start justify-between gap-3 border-b border-signal-line bg-signal-soft;
  padding: 16px;
}
.id-text { @apply flex flex-col gap-0.5 min-w-0; }
.id-name {
  @apply m-0 text-display font-bold text-signal-ink;
  font-size: 18px; line-height: 24px; letter-spacing: -0.4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.id-welcome { @apply m-0 text-body text-signal-ink/70; }
.id-chips { @apply flex items-center gap-1.5 mt-1; }
.id-user { @apply text-caption text-signal-ink/45; }
.id-role {
  @apply text-micro font-bold text-signal-ink/70 bg-signal-canvas;
  padding: 1px 8px; border-radius: 999px;
}
.id-role.admin { @apply text-signal bg-signal-card; }

.avatar {
  @apply inline-flex items-center justify-center flex-none text-white;
  width: 56px; height: 56px; font-size: 22px; font-weight: 700; border-radius: 50%;
  box-shadow: 0 0 0 4px white, 0 4px 14px rgba(16, 21, 28, 0.16);
}

/* 常驻统计:≤ 2 项单列两块;3 项三列;4 项两列网格(原型口径)。
   间距微调(2026-11-05):tile 内 label/value 留 3px、块间 10px ——
   原 1px/8px 在 288px 预览宽下数字贴标签,读起来挤。 */
.id-stats { @apply flex gap-2.5 m-0; padding: 14px 16px 12px; }
.id-stats.grid2 { @apply grid grid-cols-2; flex: none; }
.id-stat {
  @apply flex flex-col gap-[3px] flex-1 bg-signal-canvas/60 border border-signal-line rounded-empty;
  padding: 10px 12px;
}
.id-stat .label { @apply text-micro text-signal-ink/45; }
.id-stat .value { @apply m-0 text-signal-ink; font-size: 19px; font-weight: 700; line-height: 26px; }
.id-stat .value.danger { @apply text-signal-failed; }

/* 告警条:error 红 / warn 琥珀;action 右对齐 */
.id-alerts { @apply flex flex-col gap-2; padding: 0 16px 12px; }
.id-alert {
  @apply flex items-center gap-2 rounded-empty text-caption no-underline;
  padding: 8px 12px;
}
.id-alert.error { background: #fee2e2; color: #991b1b; }
.id-alert.warn { background: #fef3c7; color: #92400e; }
.id-alert .action { @apply font-semibold whitespace-nowrap; }
.more { @apply text-[11px] text-signal-ink/60 no-underline self-end; }

.id-shortcuts { @apply flex flex-wrap gap-2.5; padding: 0 16px 14px; }
.pill {
  @apply inline-flex items-center border border-signal-line rounded-full text-caption text-signal-ink no-underline;
  height: 26px; padding: 0 12px;
}

.id-footer {
  @apply flex justify-between border-t border-signal-line;
  padding: 9px 16px;
}
.link { @apply text-caption text-signal no-underline; }
.mono { font-family: var(--font-mono, monospace); }
</style>
