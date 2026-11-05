<!-- IdentityCardSection.vue — 工作台身份卡自定义(webhook v4 §8/D17;
     原型 CardSettings)。常驻统计 ≤ 4(勾选 + 上/下移排序)、告警按类
     开关(与通知开关互不影响)、快捷入口 ≤ 4;右侧实时预览(与
     UserIdentityCard 同一组件、同一份数据)。偏好存 identity.card,
     改动即时保存。 -->
<template>
  <section class="flex flex-wrap items-start gap-5 rounded-card">
    <!-- 配置列 -->
    <div class="flex min-w-0 flex-1 flex-col gap-5">
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="m-0 text-[16px] leading-[22px] font-semibold">工作台身份卡</h2>
        <QTip text="改动即时保存，换设备同步" />
        <div class="flex-grow" />
        <Button variant="outline" size="sm" data-testid="card-reset" @click="reset">恢复默认</Button>
      </div>

      <!-- 常驻统计 -->
      <section class="flex flex-col gap-1.5 rounded-card border border-signal-line bg-signal-card p-5">
        <div class="mb-1.5 flex items-baseline gap-2">
          <h3 class="m-0 text-body font-semibold">常驻统计</h3>
          <QTip text="最多 4 项 · 上移排序" />
          <span class="text-caption text-signal-ink/60">已选 {{ cfg.stats.length }}</span>
        </div>
        <template v-for="(s, i) in STATS" :key="s.id">
          <label class="flex items-center gap-3 rounded-md px-3 py-2.5"
                 :class="selected(s.id) ? 'bg-signal-soft' : ''">
            <span class="flex w-7 flex-none flex-col gap-0.5">
              <button
                type="button" class="h-4 leading-none text-signal-ink/40 hover:text-signal disabled:opacity-30"
                :disabled="i === 0" aria-label="上移" @click="move(i, -1)"
              >▲</button>
              <button
                type="button" class="h-4 leading-none text-signal-ink/40 hover:text-signal disabled:opacity-30"
                :disabled="i === STATS.length - 1" aria-label="下移" @click="move(i, 1)"
              >▼</button>
            </span>
            <input
              type="checkbox" class="h-[15px] w-[15px] flex-none" :checked="selected(s.id)"
              :disabled="!selected(s.id) && cfg.stats.length >= 4"
              @change="toggleStat(s.id)"
            />
            <span class="min-w-0 flex-1">{{ s.label }}</span>
            <span class="flex-none text-right text-caption text-signal-ink/60">{{ s.hint }}</span>
          </label>
        </template>
      </section>

      <!-- 告警 -->
      <section class="flex flex-col rounded-card border border-signal-line bg-signal-card p-5">
        <div class="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <h3 class="m-0 text-body font-semibold">告警</h3>
          <QTip text="按严重程度排序，最多显示 3 条；与「通知」开关互不影响" />
        </div>
        <label
          v-for="a in ALERTS" :key="a.id"
          class="flex items-center gap-3 border-b border-signal-line py-3 last:border-0"
        >
          <span class="h-2 w-2 flex-none rounded-full" :class="a.severity === 'error' ? 'bg-red-600' : a.severity === 'warn' ? 'bg-amber-600' : 'bg-signal'" />
          <span class="flex min-w-0 flex-1 flex-col gap-1">
            <span>{{ a.label }}</span>
            <span class="text-caption leading-snug text-signal-ink/60">{{ a.hint }}</span>
          </span>
          <Switch :model-value="alertOn(a.id)" @update:model-value="(v: boolean) => toggleAlert(a.id, v)" />
        </label>
      </section>

      <!-- 快捷入口 -->
      <section class="flex flex-col gap-3 rounded-card border border-signal-line bg-signal-card p-5">
        <div class="flex items-baseline gap-2">
          <h3 class="m-0 text-body font-semibold">快捷入口</h3>
          <QTip text="最多 4 个" />
          <span class="text-caption text-signal-ink/60">已选 {{ cfg.shortcuts.length }}</span>
        </div>
        <div class="flex flex-wrap gap-2.5">
          <button
            v-for="s in SHORTCUTS" :key="s.id" type="button"
            class="h-8 rounded-full border px-3.5 text-caption"
            :class="shortcutOn(s.id)
              ? 'border-signal bg-[#E7EFFF] text-[#1F55C4]'
              : 'border-signal-line bg-white text-signal-ink'"
            :aria-pressed="shortcutOn(s.id)"
            @click="toggleShortcut(s.id)"
          >{{ s.label }}</button>
        </div>
      </section>
    </div>

    <!-- 预览列 -->
    <div class="flex w-[288px] flex-none flex-col gap-2">
      <span class="text-caption font-semibold text-signal-ink/60">预览</span>
      <UserIdentityCard :config="cfg" :summary="summary" preview />
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Button } from '@/components/ui/button'
import QTip from '@/components/scenario-lib/QTip.vue'
import { Switch } from '@/components/ui/switch'
import UserIdentityCard from '@/components/workbench/UserIdentityCard.vue'
import http from '@/api/http'
import { toast } from '@/utils/toast'

/** 统计项注册表(id 即后端 /me/summary 的 stats 键) */
const STATS = [
  { id: 'private_scenarios', label: '私有场景', hint: '点击进入我的场景' },
  { id: 'follows', label: '关注', hint: '' },
  { id: 'tokens', label: '访问令牌', hint: '有效令牌数' },
  { id: 'today_failed', label: '今日执行失败', hint: '本人发起，含令牌发起' },
  { id: 'subscribed_integrations', label: '订阅的集成任务', hint: '含已暂停' },
  { id: 'auths', label: '我的凭证', hint: '' },
  { id: 'unread', label: '未读通知', hint: '' },
] as const

/** 告警类注册表(id 即 /me/summary 的 alerts[].class) */
const ALERTS = [
  { id: 'token_invalidated', label: '访问令牌失效', severity: 'error',
    hint: '改密、停用、管理员强制失效；角色不足时令牌不可用' },
  { id: 'integration_paused', label: '集成任务暂停', severity: 'error',
    hint: '令牌吊销 / 失效 / 到期、超出令牌范围、场景非公共、缺凭证、连续失败' },
  { id: 'token_expiring', label: '访问令牌即将到期', severity: 'warn', hint: '7 天内到期' },
  { id: 'execution_failures', label: '近 24 小时执行失败', severity: 'warn', hint: '本人发起的执行' },
] as const

/** 快捷入口注册表(纯前端路由) */
const SHORTCUTS = [
  { id: 'tokens', label: '访问令牌' },
  { id: 'auths', label: '我的凭证' },
  { id: 'password', label: '修改密码' },
  { id: 'notify', label: '通知偏好' },
  { id: 'create_token', label: '创建令牌' },
] as const

export interface CardConfig {
  stats: string[]
  alerts: Record<string, boolean>
  shortcuts: string[]
}

const DEFAULT_CFG: CardConfig = {
  stats: ['private_scenarios', 'follows', 'tokens'],
  alerts: {
    token_invalidated: true, integration_paused: true,
    token_expiring: true, execution_failures: false,
  },
  shortcuts: ['tokens', 'auths', 'password'],
}

const cfg = ref<CardConfig>(JSON.parse(JSON.stringify(DEFAULT_CFG)))
type SummaryAlert = {
  id: string; class: string; severity: 'error' | 'warn' | 'info'
  title: string; action: string; link: string
}
const summary = ref<{ stats: Record<string, number>; alerts: SummaryAlert[] }>(
  { stats: {}, alerts: [] })

function selected(id: string) { return cfg.value.stats.includes(id) }
function alertOn(id: string) { return cfg.value.alerts[id] !== false }
function shortcutOn(id: string) { return cfg.value.shortcuts.includes(id) }

function toggleStat(id: string) {
  const has = selected(id)
  if (has) cfg.value.stats = cfg.value.stats.filter((x) => x !== id)
  else if (cfg.value.stats.length < 4) cfg.value.stats.push(id)
  else return
  void save()
}
function move(index: number, delta: number) {
  const arr = STATS.map((s) => s.id)
  const from = index
  const current = arr[from]
  const curIdx = cfg.value.stats.indexOf(current)
  if (curIdx < 0) {
    if (cfg.value.stats.length < 4) cfg.value.stats.push(current)
    return void save()
  }
  const next = cfg.value.stats[curIdx + delta]
  const nextIdx = cfg.value.stats.indexOf(next)
  if (nextIdx < 0) return
  ;[cfg.value.stats[curIdx], cfg.value.stats[nextIdx]] =
    [cfg.value.stats[nextIdx], cfg.value.stats[curIdx]]
  void save()
}
function toggleAlert(id: string, on: boolean) {
  cfg.value.alerts = { ...cfg.value.alerts, [id]: on }
  void save()
}
function toggleShortcut(id: string) {
  const has = shortcutOn(id)
  if (has) cfg.value.shortcuts = cfg.value.shortcuts.filter((x) => x !== id)
  else if (cfg.value.shortcuts.length < 4) cfg.value.shortcuts.push(id)
  else return
  void save()
}
function reset() {
  cfg.value = JSON.parse(JSON.stringify(DEFAULT_CFG))
  void save()
}

async function save() {
  try {
    await http.put('/me/preferences/identity.card', { value: cfg.value })
  } catch {
    toast.error('身份卡偏好保存失败')
  }
}

onMounted(async () => {
  try {
    const prefs = await http.get<{ items: Record<string, unknown> }>('/me/preferences')
    const saved = prefs.data.items['identity.card'] as CardConfig | undefined
    if (saved) {
      cfg.value = {
        stats: (saved.stats ?? DEFAULT_CFG.stats).slice(0, 4),
        alerts: { ...DEFAULT_CFG.alerts, ...(saved.alerts ?? {}) },
        shortcuts: (saved.shortcuts ?? DEFAULT_CFG.shortcuts).slice(0, 4),
      }
    }
  } catch { /* 偏好不可达 → 默认 */ }
  try {
    const out = await http.get<{ stats: Record<string, number>; alerts: SummaryAlert[] }>(
      '/me/summary')
    summary.value = out.data
  } catch { /* 摘要不可达 → 预览显示占位 */ }
})
</script>
