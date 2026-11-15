<!-- MemberRow.vue — 成员行(原型 20:名称 / scenarioId 等宽 / 方案 chip /
     ×重复角标 / ▲▼ / ⋯;扇出源带「源」标;多行方案带警示 chip)。 -->
<template>
  <div
    class="mrow"
    :class="{ hl: highlight }"
    :data-testid="`suite-member-row-${member.scenarioId}`"
  >
    <span v-if="idx" class="mrow-idx">{{ idx }}</span>
    <span v-if="source" class="mrow-source" title="扇出源:先跑它,其余并行">源</span>
    <span class="mrow-name" :title="member.scenarioId">{{ member.name }}</span>
    <span class="mrow-sid">{{ member.scenarioId }}</span>
    <span v-if="schemeName" class="mrow-scheme">{{ schemeName }}</span>
    <span
      v-if="unit.repeat && unit.repeat > 1"
      class="mrow-repeat"
      title="×重复:该单元重复执行的遍数"
    >×{{ unit.repeat }}</span>
    <span
      v-if="multiRow"
      class="mrow-multirow"
      title="该单元的方案选了多行数据 —— 编排模式只会跑所选那行(约束 5)"
    >多行方案 · 只跑 1 行</span>
    <span
      v-if="unit.row"
      class="mrow-row"
      :title="`数据行:${unit.row.datasetId} 第 ${unit.row.rowIndex} 行`"
    >{{ unit.row.datasetId }}#{{ unit.row.rowIndex }}</span>
    <span class="mrow-ops">
      <template v-if="!readonly">
        <button type="button" title="上移" :disabled="busy" @click="$emit('move', -1)">▲</button>
        <button type="button" title="下移" :disabled="busy" @click="$emit('move', 1)">▼</button>
        <button type="button" class="more" title="更多操作" @click.stop="menuOpen = !menuOpen">⋯</button>
      </template>
    </span>
    <div v-if="menuOpen && !readonly" class="mrow-menu" @click.stop>
      <button type="button" @click="act('settings')">单元设置…</button>
      <button v-if="member.role !== 'main'" type="button" @click="act('main')">设为主体</button>
      <button v-if="member.role !== 'before'" type="button" @click="act('before')">设为前置</button>
      <button v-if="member.role !== 'after'" type="button" @click="act('after')">设为后置</button>
      <button type="button" class="danger" @click="act('remove')">移除</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { MemberRole, SuiteMemberItem, SuiteUnitConfig } from '@/api/suites'

defineProps<{
  member: SuiteMemberItem
  unit: SuiteUnitConfig
  idx?: number
  source?: boolean
  schemeName?: string
  orchestrate?: boolean
  readonly?: boolean
  multiRow?: boolean
  highlight?: boolean
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'move', delta: number): void
  (e: 'remove'): void
  (e: 'role', role: MemberRole): void
  (e: 'settings'): void
}>()

const menuOpen = ref(false)
function act(cmd: 'settings' | 'main' | 'before' | 'after' | 'remove'): void {
  menuOpen.value = false
  if (cmd === 'settings') emit('settings')
  else if (cmd === 'remove') emit('remove')
  else emit('role', cmd)
}
</script>

<style scoped>
.mrow {
  position: relative; display: flex; align-items: center; gap: 0.5rem;
  padding: 0.375rem 0.625rem; border: 1px solid rgb(100 116 139 / 22%);
  border-radius: 0.5rem; font-size: 0.78125rem; background: rgb(100 116 139 / 3%);
  min-width: 0;
}
.mrow.hl { border-color: var(--accent); background: var(--accent-soft); }
.mrow-idx { flex: none; color: rgb(100 116 139); font-size: 0.71875rem; width: 1rem; text-align: right; }
.mrow-source {
  flex: none; font-size: 0.6875rem; line-height: 1; padding: 0.125rem 0.4375rem;
  border-radius: 62.4375rem; color: #1d4ed8;
  background: var(--accent-soft); border: 1px solid var(--accent-soft-border);
}
.mrow-name { flex: none; max-width: 11.25rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.mrow-sid {
  flex: 1; min-width: 3.75rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.6875rem; color: rgb(100 116 139);
}
.mrow-scheme {
  flex: none; font-size: 0.6875rem; padding: 0.125rem 0.4375rem; border-radius: 62.4375rem;
  color: rgb(100 116 139); background: rgb(100 116 139 / 8%);
  border: 1px solid rgb(100 116 139 / 25%);
  max-width: 7.5rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.mrow-repeat {
  flex: none; font-size: 0.6875rem; font-weight: 600; color: #1d4ed8;
  padding: 0.125rem 0.375rem; border-radius: 0.375rem; background: var(--accent-soft);
}
.mrow-multirow {
  flex: none; font-size: 0.6875rem; color: var(--sl-warn);
  background: rgb(245 158 11 / 10%); border: 1px solid rgb(245 158 11 / 40%);
  padding: 0.125rem 0.4375rem; border-radius: 62.4375rem; cursor: help;
}
.mrow-row {
  flex: none; font-size: 0.6875rem; font-family: ui-monospace, monospace;
  color: var(--sl-ok); background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%); padding: 0.125rem 0.4375rem; border-radius: 62.4375rem;
}
.mrow-ops { flex: none; display: flex; gap: 0.25rem; }
.mrow-ops button {
  width: 1.5rem; height: 1.375rem; border-radius: 0.375rem; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
  font-size: 0.625rem; padding: 0;
}
.mrow-ops button:disabled { opacity: .35; cursor: not-allowed; }
.mrow-menu {
  position: absolute; right: 0.5rem; top: calc(100% - 0.125rem); z-index: 20;
  display: flex; flex-direction: column; min-width: 8.125rem;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 0.5rem;
  background: var(--c-bg, #fff); box-shadow: 0 6px 20px rgb(15 23 42 / 12%);
  padding: 0.25rem;
}
.mrow-menu button {
  text-align: left; padding: 0.375rem 0.625rem; font-size: 0.78125rem; cursor: pointer;
  border: none; background: transparent; color: inherit; border-radius: 0.375rem;
}
.mrow-menu button:hover { background: var(--accent-soft); }
.mrow-menu .danger { color: var(--sl-bad, var(--sl-bad)); }
</style>
