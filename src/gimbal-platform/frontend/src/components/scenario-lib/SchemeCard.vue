<!-- SchemeCard.vue — 我的场景内联预览面板里的方案卡片(210px)。
     顶部状态色描边 = 该方案最近一次执行结果;卡头两行(全名 / 默认徽章
     + 状态 chip + 相对时间);卡底「次数」「并发」小徽章点击即编辑,
     最右「▶ 执行」。深度编辑不在本卡(跳方案管理)。 -->
<template>
  <div class="scheme-card" :class="borderTone">
    <div class="sc-head">
      <div class="sc-name" :title="scheme.name">{{ scheme.name }}</div>
      <div class="sc-sub">
        <span v-if="scheme.isDefault" class="badge-default">默认</span>
        <span class="status-chip" :class="chipTone">{{ chipText }}</span>
        <span class="sc-time">{{ relTime(lastRun?.at) || '—' }}</span>
      </div>
    </div>
    <div class="sc-foot">
      <!-- 非编辑态是真 <button>(可 Tab 聚焦、Enter 触发);编辑态换成 span
           包 input —— 输入框不能嵌在 button 里。 -->
      <button
        v-if="editing !== 'nRuns'"
        type="button"
        class="mini-badge"
        :aria-label="`修改执行次数(当前 ${scheme.nRuns})`"
        @click.stop="startEdit('nRuns')"
      >次数 <b>{{ scheme.nRuns }}</b></button>
      <span v-else class="mini-badge editing">
        <input
          ref="inputEl"
          v-model="draft"
          type="number"
          min="1"
          max="500"
          aria-label="执行次数"
          @blur="commit"
          @keyup.enter="commit"
          @keyup.esc="cancel"
        />
      </span>
      <button
        v-if="editing !== 'parallel'"
        type="button"
        class="mini-badge"
        :aria-label="`修改并发数(当前 ${scheme.parallel})`"
        @click.stop="startEdit('parallel')"
      >并发 <b>{{ scheme.parallel }}</b></button>
      <span v-else class="mini-badge editing">
        <input
          ref="inputEl"
          v-model="draft"
          type="number"
          min="1"
          max="200"
          aria-label="并发数"
          @blur="commit"
          @keyup.enter="commit"
          @keyup.esc="cancel"
        />
      </span>
      <button type="button" class="run-link" @click.stop="$emit('run', scheme)">▶ 执行</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { toast } from '@/utils/toast'
import type { SchemeV2 } from '@/api/scenario-composer'
import { relTime } from '@/utils/datetime'

const props = defineProps<{
  scheme: SchemeV2
  lastRun: { status: string; at: string | null } | null
}>()
const emit = defineEmits<{
  run: [scheme: SchemeV2]
  update: [scheme: SchemeV2, patch: { nRuns?: number; parallel?: number }]
}>()

const editing = ref<'nRuns' | 'parallel' | null>(null)
const draft = ref('')
/** 两个输入框同一时刻只渲染一个,共用一个模板 ref。 */
const inputEl = ref<HTMLInputElement | null>(null)

const borderTone = computed(() => {
  const s = props.lastRun?.status
  if (s === 'done') return 'st-ok'
  if (s === 'failed') return 'st-bad'
  if (s === 'running' || s === 'queued') return 'st-run'
  return ''
})
const chipTone = computed(() => {
  const s = props.lastRun?.status
  if (s === 'done') return 'ok'
  if (s === 'failed') return 'bad'
  if (s === 'running' || s === 'queued') return 'run'
  return 'none'
})
const chipText = computed(() => {
  const s = props.lastRun?.status
  if (s === 'done') return '完成'
  if (s === 'failed') return '失败'
  if (s === 'running' || s === 'queued') return '执行中'
  return '未执行'
})

function startEdit(field: 'nRuns' | 'parallel') {
  editing.value = field
  draft.value = String(field === 'nRuns' ? props.scheme.nRuns : props.scheme.parallel)
  // 键盘进来就该落在输入框上(否则 Enter 打开后焦点还停在已消失的按钮上)
  void nextTick(() => { inputEl.value?.focus(); inputEl.value?.select() })
}

function cancel() {
  editing.value = null
}

/** 上界与 input 的 max 同源 —— HTML max 只是原生 spinner 的装饰,
 *  手动键入的越界值必须由 commit 自己拦,否则一路透传到后端。 */
const MAX: Record<'nRuns' | 'parallel', number> = { nRuns: 500, parallel: 200 }
const FIELD_LABEL: Record<'nRuns' | 'parallel', string> = { nRuns: '次数', parallel: '并发' }

function commit() {
  const field = editing.value
  editing.value = null
  if (!field) return
  const n = Number.parseInt(draft.value, 10)
  const cur = field === 'nRuns' ? props.scheme.nRuns : props.scheme.parallel
  if (Number.isNaN(n) || n === cur) return
  if (n < 1 || n > MAX[field]) {
    toast.error(`${FIELD_LABEL[field]} 取值范围 1–${MAX[field]}`)
    return
  }
  emit('update', props.scheme, { [field]: n })
}
</script>
