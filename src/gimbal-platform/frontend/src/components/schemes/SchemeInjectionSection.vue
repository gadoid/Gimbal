<script setup lang="ts">
/** 方案工作台 · 断言注入区:注册表条目复选(死条目禁选 + 灰显 + 悬空 title)、
 *  快建弹层(步骤号 + jsonpath → quickCreate)、「管理断言」跳编辑器(manage)。
 *  纯展示组件:条目/死集进 props,勾选/快建/管理出事件;持久化与导航归壳。 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: string[]                 // injectionEntryIds(受控)
  entries: Array<{ id: string; label?: string }>   // 壳从 assertion_registry.entries 映射
  deadIds: Set<string>                 // 死条目(禁选 + 灰显 + 死因 title)
  locked?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [v: string[]]
  quickCreate: [draft: { stepIndex: number; jsonpath: string }]  // 快建弹层确认
  manage: []                                                      // 跳断言编辑器
}>()

function toggle(id: string, on: boolean) {
  const has = props.modelValue.includes(id)
  if (on === has) return
  emit('update:modelValue',
    on ? [...props.modelValue, id] : props.modelValue.filter((x) => x !== id))
}

// ── 快建弹层(展开行;与数据区同款 inline 约定)───────────────────────
// 步骤号输入用 el-input(type=number)而非 el-input-number:el-input 把
// $attrs(含 data-testid)透传到原生 input,el-input-number 留在根 div 上 —
// 测试的 setValue 只对原生 input/textarea/select 生效(其余元素直接 throw)。
const showQuick = ref(false)
const pendingStep = ref<number | string>(0)
const pendingJsonpath = ref('')

function confirmQuick() {
  const stepIndex = Number(pendingStep.value)
  if (pendingStep.value === '' || pendingStep.value === null
    || !Number.isInteger(stepIndex) || stepIndex < 0) {
    ElMessage.warning('要填步骤号(从 0 开始)')
    return
  }
  if (!pendingJsonpath.value.startsWith('$')) {
    ElMessage.warning('注入路径需以 $ 开头(例:$.amount)')
    return
  }
  emit('quickCreate', { stepIndex, jsonpath: pendingJsonpath.value })
  showQuick.value = false
  pendingJsonpath.value = ''
}
</script>

<template>
  <section class="wb-section">
    <header class="zone-head">
      <span class="zone-name">断言注入</span>
      <div class="zone-ops">
        <el-button size="small" text type="primary" data-testid="quick-add"
          @click="showQuick = !showQuick">+ 快建条目</el-button>
        <el-button size="small" text type="primary" data-testid="manage-assertions"
          @click="emit('manage')">管理断言</el-button>
      </div>
    </header>

    <div v-if="showQuick" class="quick-row">
      <el-input v-model="pendingStep" data-testid="qa-step" type="number"
        :disabled="locked" class="qa-step" placeholder="步骤号" />
      <el-input v-model="pendingJsonpath" data-testid="qa-path"
        :disabled="locked" class="qa-path" placeholder="注入路径,如 $.amount" />
      <el-button size="small" type="primary" data-testid="qa-ok"
        :disabled="locked" @click="confirmQuick">创建</el-button>
    </div>

    <div class="inj-list">
      <!-- 原生 checkbox(与数据区同款):禁选/灰显/悬空 title 三态齐备 -->
      <label v-for="e in entries" :key="e.id" class="inj-item"
        :class="{ dead: deadIds.has(e.id) }" :title="deadIds.has(e.id) ? '已悬空' : undefined">
        <input type="checkbox" :checked="modelValue.includes(e.id)"
          :disabled="deadIds.has(e.id) || locked"
          @change="toggle(e.id, ($event.target as HTMLInputElement).checked)" />
        {{ e.label ?? e.id }}
      </label>
      <p v-if="!entries.length" class="hint">暂无断言条目 — 可「+ 快建条目」或到断言管理器维护。</p>
    </div>
  </section>
</template>

<style scoped>
.wb-section { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }
.zone-head { display: flex; align-items: center; justify-content: space-between; }
.zone-name { font-weight: 600; }
.zone-ops { display: flex; gap: 4px; }
.quick-row { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px dashed var(--el-border-color); border-radius: 6px; }
.quick-row .qa-step { width: 110px; flex: none; }
.quick-row .qa-path { flex: 1; }
.inj-list { display: flex; flex-direction: column; gap: 4px; }
.inj-item { cursor: pointer; }
.inj-item.dead { color: var(--el-text-color-secondary); cursor: not-allowed; text-decoration: line-through; }
.hint { color: var(--el-text-color-secondary); }
</style>
