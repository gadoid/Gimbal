<!--
  ConstantPoolPanel.vue — 常量池只读面板(编排四页常驻,两处挂载同一组件)

  挂载: ① CaseComposer 右栏 rail(步骤 0-2)② Canvas col-info(步骤 3,
  VariableRegistryPanel 之下)。数据由挂载点从 store 传入(纯 props),
  拉取(ensureEntries)是挂载点的职责 —— panel 保持 presentational。

  行结构(生成器双载荷,spec §复制/插入交互):
  - 字面量: value 复制/插入(插入=纯文本追加,无播种)
  - 生成器: key ${var.name} 与 value spec JSON 均可复制/插入;
    key 插入成功时 emit seedVar(由 CaseComposer 播种 config.vars 快照),
    value 插入=纯文本追加(它本身就是声明,无播种)。

  插入走 useSharedInsertTarget(composer 根 provide);无目标时
  ElMessage.info 提示且不播种。
-->
<template>
  <div class="cp-panel">
    <div class="cp-head">
      <span class="cp-title">常量池 <span class="cp-count">{{ entries.length }}</span></span>
      <router-link class="cp-manage" to="/constants" title="管理常量池">管理</router-link>
    </div>

    <div v-if="!entries.length" class="cp-empty">
      常量池为空 — 到「常量池」管理页添加常用值或生成器声明
    </div>

    <div v-for="e in entries" :key="e.id" class="cp-entry" :data-entry="e.name">
      <div class="cp-row cp-name-row">
        <span class="cp-name" :title="e.description || e.name">{{ e.name }}</span>
        <span class="cp-badge" :class="e.entry_kind">
          {{ e.entry_kind === 'generator' ? '生成器' : '常量' }}
        </span>
      </div>

      <!-- 生成器 key 载荷(字面量无此行) -->
      <div v-if="e.entry_kind === 'generator'" class="cp-row">
        <code class="cp-key" :title="keyText(e)">key&nbsp;&nbsp;{{ keyText(e) }}</code>
        <span class="cp-actions">
          <button class="cp-btn act-copy-key" title="复制引用" @click="copyKey(e)">复制</button>
          <button class="cp-btn act-insert-key" title="插入引用并播种 config.vars" @click="insertKey(e)">插入</button>
        </span>
      </div>

      <!-- value 载荷(字面量=值;生成器=spec JSON) -->
      <div class="cp-row">
        <code class="cp-value" :title="valueText(e)">value {{ displayValue(e) }}</code>
        <span class="cp-actions">
          <button class="cp-btn act-copy-value" title="复制内容" @click="copyValue(e)">复制</button>
          <button class="cp-btn act-insert-value" title="插入到字段" @click="insertValue(e)">插入</button>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { copyText } from '@/utils/clipboard'
import { useSharedInsertTarget } from '@/composables/useInsertTarget'
import type { ConstantEntry } from '@/types/constants'

const props = defineProps<{ entries: ConstantEntry[] }>()
const emit = defineEmits<{
  seedVar: [name: string, spec: Record<string, unknown>]
}>()

const inserter = useSharedInsertTarget()

const keyText = (e: ConstantEntry): string => `\${var.${e.name}}`
/** 复制/插入均为完整紧凑 JSON 文本;行内显示截断。 */
const valueText = (e: ConstantEntry): string =>
  e.entry_kind === 'generator' ? JSON.stringify(e.spec) : String(e.value)

const displayValue = (e: ConstantEntry): string => {
  const t = valueText(e)
  return t.length > 42 ? `${t.slice(0, 42)}…` : t
}

const NO_TARGET_MSG = '请先点击要插入的输入框'

function copyKey(e: ConstantEntry): void {
  void copyText(keyText(e)).then((ok) => {
    if (ok) ElMessage.success('已复制引用')
    else ElMessage.error('复制失败 — 请手动复制')
  })
}

function copyValue(e: ConstantEntry): void {
  void copyText(valueText(e)).then((ok) => {
    if (ok) ElMessage.success('已复制')
    else ElMessage.error('复制失败 — 请手动复制')
  })
}

/** key 插入: 追加引用文本;成功才 emit seedVar(快照播种,写入点在 CaseComposer)。 */
function insertKey(e: ConstantEntry): void {
  if (!inserter.appendValue(keyText(e))) {
    ElMessage.info(NO_TARGET_MSG)
    return
  }
  emit('seedVar', e.name, (e.spec ?? {}) as Record<string, unknown>)
}

/** value 插入: 纯文本追加 — 字面量=值文本,生成器=spec JSON(本身即声明,无播种)。 */
function insertValue(e: ConstantEntry): void {
  if (!inserter.appendValue(valueText(e))) {
    ElMessage.info(NO_TARGET_MSG)
  }
}
</script>

<style scoped>
/* 视觉对齐 VariableRegistryPanel(col-info 240-300px 适配) */
.cp-panel {
  padding: 10px 12px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cp-head { display: flex; align-items: center; justify-content: space-between; }
.cp-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.cp-count {
  font-family: var(--font-mono);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 0 6px;
  margin-left: 4px;
  font-size: 10px;
}
.cp-manage { color: var(--c-text-tertiary); text-decoration: none; font-size: 11px; }
.cp-manage:hover { color: var(--c-text-primary, #0f172a); }
.cp-empty { font-size: 11px; color: var(--c-text-tertiary); line-height: 1.6; }
.cp-entry {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 4px 6px;
  border-radius: 5px;
  background: var(--c-surface);
}
.cp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}
.cp-name {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cp-badge {
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  flex-shrink: 0;
}
.cp-badge.generator { background: #f3e8ff; color: #6b21a8; }
.cp-badge.literal { background: #f1f5f9; color: #334155; }
.cp-key,
.cp-value {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--c-text-secondary, #64748b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.cp-actions { display: inline-flex; gap: 3px; flex-shrink: 0; }
.cp-btn {
  border: 1px solid var(--c-border);
  background: transparent;
  color: var(--c-text-tertiary);
  border-radius: 4px;
  font-size: 10px;
  padding: 0 5px;
  cursor: pointer;
}
.cp-btn:hover { background: var(--c-bg-secondary); color: var(--c-text-primary, #0f172a); }
</style>
