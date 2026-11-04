<!-- NotesCard.vue — 工作台便签卡(webhook v4 §8/D18;原型 NoteCard)。
     S = 只看结论(未完成前若干条);M = 明细 + 快速记录;L = 全部 +
     筛选与整理。数据存 ``notes`` 偏好(整值覆盖,后写为准);每条
     ≤ 200 字、共 ≤ 20 条,已完成 7 天后自动清理。 -->
<template>
  <div class="flex h-full flex-col gap-2">
    <div class="flex items-baseline justify-between">
      <h3 class="m-0 text-body font-semibold">便签</h3>
      <span class="text-caption text-signal-ink/60">
        <template v-if="size === 'L'">
          {{ items.length }} / 20 · 每条 200 字 · 已完成 7 天后自动清理
        </template>
        <template v-else-if="size === 'M'">{{ items.length }} / 20</template>
        <template v-else>{{ openCount }} 条未完成</template>
      </span>
    </div>

    <!-- S:只看结论 -->
    <template v-if="size === 'S'">
      <span
        v-for="n in openItems.slice(0, 4)" :key="n.id"
        class="block overflow-hidden text-ellipsis whitespace-nowrap text-caption"
      >· {{ n.text }}</span>
      <span v-if="!openItems.length" class="text-caption text-signal-ink/60">没有未完成的便签</span>
      <RouterLink class="text-caption text-signal no-underline" to="/home">+ 记一笔</RouterLink>
    </template>

    <!-- M:明细 + 快速记录 -->
    <template v-else-if="size === 'M'">
      <Input
        v-model="draft" placeholder="记一笔，回车保存" class="h-[30px] border-dashed"
        data-testid="notes-input" @keydown.enter.prevent="add"
      />
      <label
        v-for="n in items.slice(0, 8)" :key="n.id"
        class="flex items-start gap-2 border-b border-signal-line py-1.5 text-caption"
        :class="n.done ? 'text-signal-ink/50' : ''"
      >
        <input
          type="checkbox" class="mt-0.5 h-3.5 w-3.5 flex-none" :checked="n.done"
          @change="toggle(n)"
        />
        <span class="flex-1 break-all" :class="n.done ? 'line-through' : ''">{{ n.text }}</span>
      </label>
      <span v-if="!items.length" class="text-caption text-signal-ink/60">记下待办、命令片段、排查线索…</span>
    </template>

    <!-- L:全部 + 筛选与整理 -->
    <template v-else>
      <div class="flex items-center gap-2">
        <div class="flex-grow" />
        <div class="flex overflow-hidden rounded-md border border-signal-line" role="group" aria-label="筛选">
          <button
            v-for="f in NOTE_FILTERS" :key="f" type="button"
            class="h-6.5 border-0 px-2.5 text-caption"
            :class="filter === f ? 'bg-[#E7EFFF] text-[#1F55C4]' : 'bg-signal-card text-signal-ink'"
            :style="f !== 'all' ? 'border-left: 1px solid var(--color-signal-line)' : ''"
            @click="filter = f"
          >{{ { all: '全部', open: '未完成', done: '已完成' }[f] }}</button>
        </div>
      </div>
      <Input
        v-model="draft" placeholder="记一笔，回车保存" class="h-[30px] border-dashed"
        data-testid="notes-input" @keydown.enter.prevent="add"
      />
      <div
        v-for="n in filtered" :key="n.id"
        class="flex items-start gap-2.5 border-b border-signal-line py-2 text-caption"
        :class="n.done ? 'text-signal-ink/50' : ''"
      >
        <input
          type="checkbox" class="mt-0.5 h-3.5 w-3.5 flex-none" :checked="n.done"
          aria-label="完成" @change="toggle(n)"
        />
        <span class="flex-1 break-all" :class="n.done ? 'line-through' : ''">{{ n.text }}</span>
        <span class="whitespace-nowrap text-signal-ink/60">{{ relTime(n.createdAt) }}</span>
        <button
          type="button" class="h-5.5 w-5.5 border-0 bg-transparent p-0 text-signal-ink/60 hover:text-signal-failed"
          aria-label="删除" @click="remove(n)"
        >
          <Cross2Icon class="h-3.5 w-3.5" />
        </button>
      </div>
      <div class="flex justify-end">
        <button
          v-if="doneItems.length" type="button"
          class="h-6.5 rounded border border-signal-line bg-signal-card px-2.5 text-caption"
          @click="clearDone"
        >清空已完成（{{ doneItems.length }}）</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Cross2Icon } from '@radix-icons/vue'
import { Input } from '@/components/ui/input'
import http from '@/api/http'
import { toast } from '@/utils/toast'
import { useCardSize } from '../registry'

interface NoteItem {
  id: string
  text: string
  done: boolean
  createdAt: string
  doneAt?: string | null
}

const MAX_ITEMS = 20
const MAX_TEXT = 200
const DONE_RETAIN_DAYS = 7

const NOTE_FILTERS = ['all', 'open', 'done'] as const
type NoteFilter = (typeof NOTE_FILTERS)[number]

const size = useCardSize()
const items = ref<NoteItem[]>([])
const draft = ref('')
const filter = ref<NoteFilter>('all')

const openItems = computed(() => items.value.filter((n) => !n.done))
const doneItems = computed(() => items.value.filter((n) => n.done))
const filtered = computed(() =>
  filter.value === 'open' ? openItems.value
    : filter.value === 'done' ? doneItems.value : items.value)
const openCount = computed(() => openItems.value.length)

function nowIso() { return new Date().toISOString() }

function pruneDone(list: NoteItem[]): NoteItem[] {
  const cutoff = Date.now() - DONE_RETAIN_DAYS * 86400e3
  return list.filter((n) => !n.done || !n.doneAt || new Date(n.doneAt).getTime() > cutoff)
}

async function persist(next: NoteItem[]) {
  items.value = pruneDone(next).slice(0, MAX_ITEMS)
  try {
    await http.put('/me/preferences/notes', { value: { items: items.value } })
  } catch {
    toast.error('便签保存失败')
  }
}

function add() {
  const text = draft.value.trim().slice(0, MAX_TEXT)
  if (!text) return
  if (items.value.length >= MAX_ITEMS) {
    toast.error(`便签上限 ${MAX_ITEMS} 条,先清理几条`)
    return
  }
  draft.value = ''
  void persist([...items.value, {
    id: Math.random().toString(36).slice(2, 10),
    text, done: false, createdAt: nowIso(),
  }])
}

function toggle(n: NoteItem) {
  void persist(items.value.map((x) => x.id === n.id
    ? { ...x, done: !x.done, doneAt: !x.done ? nowIso() : null } : x))
}
function remove(n: NoteItem) {
  void persist(items.value.filter((x) => x.id !== n.id))
}
function clearDone() {
  void persist(items.value.filter((x) => !x.done))
}

function relTime(iso: string) {
  const d = new Date(iso)
  const today = new Date()
  const sameDay = d.toDateString() === today.toDateString()
  const yesterday = new Date(today.getTime() - 86400e3).toDateString() === d.toDateString()
  if (sameDay) return `今天 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  if (yesterday) return '昨天'
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(async () => {
  try {
    const prefs = await http.get<{ items: Record<string, { items?: NoteItem[] }> }>('/me/preferences')
    const saved = prefs.data.items['notes']
    if (saved && Array.isArray(saved.items)) items.value = pruneDone(saved.items)
  } catch { /* 偏好不可达 → 空便签 */ }
})
</script>
