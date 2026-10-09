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
  position: relative; display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border: 1px solid rgb(100 116 139 / 22%);
  border-radius: 8px; font-size: 12.5px; background: rgb(100 116 139 / 3%);
  min-width: 0;
}
.mrow.hl { border-color: #2563eb; background: rgb(59 130 246 / 10%); }
.mrow-idx { flex: none; color: rgb(100 116 139); font-size: 11.5px; width: 16px; text-align: right; }
.mrow-source {
  flex: none; font-size: 11px; line-height: 1; padding: 2px 7px;
  border-radius: 999px; color: #1d4ed8;
  background: rgb(59 130 246 / 10%); border: 1px solid rgb(59 130 246 / 45%);
}
.mrow-name { flex: none; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.mrow-sid {
  flex: 1; min-width: 60px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; color: rgb(100 116 139);
}
.mrow-scheme {
  flex: none; font-size: 11px; padding: 2px 7px; border-radius: 999px;
  color: rgb(100 116 139); background: rgb(100 116 139 / 8%);
  border: 1px solid rgb(100 116 139 / 25%);
  max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.mrow-repeat {
  flex: none; font-size: 11px; font-weight: 600; color: #1d4ed8;
  padding: 2px 6px; border-radius: 6px; background: rgb(59 130 246 / 10%);
}
.mrow-multirow {
  flex: none; font-size: 11px; color: #b45309;
  background: rgb(245 158 11 / 10%); border: 1px solid rgb(245 158 11 / 40%);
  padding: 2px 7px; border-radius: 999px; cursor: help;
}
.mrow-row {
  flex: none; font-size: 11px; font-family: ui-monospace, monospace;
  color: #15803d; background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%); padding: 2px 7px; border-radius: 999px;
}
.mrow-ops { flex: none; display: flex; gap: 4px; }
.mrow-ops button {
  width: 24px; height: 22px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
  font-size: 10px; padding: 0;
}
.mrow-ops button:disabled { opacity: .35; cursor: not-allowed; }
.mrow-menu {
  position: absolute; right: 8px; top: calc(100% - 2px); z-index: 20;
  display: flex; flex-direction: column; min-width: 130px;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 8px;
  background: var(--c-bg, #fff); box-shadow: 0 6px 20px rgb(15 23 42 / 12%);
  padding: 4px;
}
.mrow-menu button {
  text-align: left; padding: 6px 10px; font-size: 12.5px; cursor: pointer;
  border: none; background: transparent; color: inherit; border-radius: 6px;
}
.mrow-menu button:hover { background: rgb(59 130 246 / 8%); }
.mrow-menu .danger { color: var(--sl-bad, #dc2626); }
</style>
