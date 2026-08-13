<!--
  ScenarioExportMenu.vue — 复用的场景导出菜单
  - 通过 dropdown (Element Plus) 展示三个动作: JSON / YAML / 复制
  - 内部直接读 Pinia store (scenario-draft),所以挂载点不需要传 props
  - 没有进行中草稿时,菜单禁用并提示
  - 用法:
      <ScenarioExportMenu variant="topbar" />     <!-- 顶栏,中等大小按钮 -->
      <ScenarioExportMenu variant="row"    />     <!-- 表格行内,小尺寸 -->
      <ScenarioExportMenu variant="ghost"  />     <!-- 透明背景 -->
-->
<template>
  <el-dropdown
    trigger="click"
    :disabled="!hasDraft"
    @command="onCommand"
    @visible-change="onVisibleChange"
  >
    <component :is="triggerTag" :class="['se-trigger', `se-${variant}`, { 'se-disabled': !hasDraft }]">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      <span>{{ labelText }}</span>
      <svg v-if="!hideArrow" class="se-arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </component>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="json" :disabled="exporting">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 6"/></svg>
          导出 JSON
        </el-dropdown-item>
        <el-dropdown-item command="yaml" :disabled="exporting">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          导出 YAML
        </el-dropdown-item>
        <el-dropdown-item command="copy" :disabled="exporting" divided>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          复制 JSON
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed, ref, h } from 'vue'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { ElMessage } from 'element-plus'

const props = withDefaults(defineProps<{
  variant?: 'topbar' | 'row' | 'ghost'
  hideArrow?: boolean
}>(), { variant: 'topbar', hideArrow: false })

const store = useScenarioDraftStore()
const exporting = ref(false)

const hasDraft = computed(() => !!store.draft)
const labelText = computed(() => hasDraft.value ? '导出' : '导出 (无草稿)')

// 顶栏/行/ghost 三种变体 — 用 render function 切标签
const triggerTag = computed(() => (props.variant === 'row' ? 'button' : 'button'))

async function onCommand(cmd: string) {
  if (!hasDraft.value) {
    ElMessage.warning('当前没有正在编辑的草稿,请先在 CaseComposer 里打开 / 新建一个场景')
    return
  }
  exporting.value = true
  try {
    if (cmd === 'json') await store.exportJson()
    else if (cmd === 'yaml') await store.exportYaml()
    else if (cmd === 'copy') await store.copyJson()
  } catch (e) {
    ElMessage.error(`导出失败: ${(e as Error).message}`)
  } finally {
    exporting.value = false
  }
}

function onVisibleChange(_visible: boolean) {
  // 占位 — 留作未来埋点
}
</script>

<style scoped>
.se-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.15s;
  border-radius: 8px;
  font-weight: 600;
  user-select: none;
}
.se-trigger:focus { outline: none; }
.se-trigger.se-disabled { cursor: not-allowed; opacity: 0.45; }

.se-topbar {
  background: #fff;
  border: 1px solid #e6e8ec;
  color: #5a6273;
  padding: 7px 12px;
  font-size: 13px;
}
.se-topbar:hover:not(.se-disabled) { background: #f5f6fa; color: #1a1d24; }

.se-row {
  background: transparent;
  border: 1px solid transparent;
  color: #5a6273;
  padding: 4px 8px;
  font-size: 12px;
}
.se-row:hover:not(.se-disabled) { background: #eef2ff; color: #4f46e5; border-color: #c7d2fe; }

.se-ghost {
  background: transparent;
  border: 1px dashed #c7d2fe;
  color: #4f46e5;
  padding: 8px 14px;
  font-size: 13px;
}
.se-ghost:hover:not(.se-disabled) { background: #eef2ff; }

.se-arrow { margin-left: 2px; opacity: 0.6; }
</style>