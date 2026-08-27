<!--
  ScenarioExportMenu.vue — 复用的场景导出菜单
  - 通过 dropdown (Element Plus) 展示三个动作: JSON / YAML / 复制
  - 内部直接读 Pinia store (scenario-draft),所以挂载点不需要传 props
  - 没有进行中草稿时,菜单禁用并提示
  - 用法:
      <ScenarioExportMenu variant="topbar" />     <!-- 顶栏,中等大小按钮 -->
-->
<template>
  <el-dropdown
    trigger="click"
    :disabled="!hasDraft"
    @command="onCommand"
  >
    <button type="button" :class="['se-trigger', `se-${variant}`, { 'se-disabled': !hasDraft }]">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      <span>{{ labelText }}</span>
      <svg class="se-arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>
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
        <!-- 按方案导出(spec §8):方案的 envId/serviceBindings 物化进导出。
             首项 divided 与上方动作分组;统一走 exportJson(overlay)。 -->
        <el-dropdown-item
          v-for="(s, i) in schemes"
          :key="s.name"
          :command="`scheme:${s.name}`"
          :disabled="exporting"
          :divided="i === 0"
        >按方案导出 · {{ s.name }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useScenarioDraftStore, schemeToOverlay } from '@/stores/scenario-draft'
import { ElMessage } from 'element-plus'
import type { RunScheme } from '@/api/scenario-composer'
import type { Orchestration } from '@/types/scenario-composer'

/** Orchestration + 运行方案 sidecar 键(后端 Task 10 起收录 runSchemes,
 *  前端 Orchestration 类型尚未声明 — 与 CaseComposer.vue 同款约定)。 */
type OrchestrationWithSchemes = Orchestration & { runSchemes?: RunScheme[] }

withDefaults(defineProps<{
  variant?: 'topbar'
}>(), { variant: 'topbar' })

const store = useScenarioDraftStore()
const exporting = ref(false)

const hasDraft = computed(() => !!store.draft)
const labelText = computed(() => hasDraft.value ? '导出' : '导出 (无草稿)')

const schemes = computed<RunScheme[]>(() =>
  (store.draft?.orchestration as OrchestrationWithSchemes | undefined)?.runSchemes ?? [])

async function onCommand(cmd: string) {
  if (!hasDraft.value) {
    ElMessage.warning('当前没有正在编辑的草稿,请先在 CaseComposer 里打开 / 新建一个场景')
    return
  }
  exporting.value = true
  try {
    if (cmd.startsWith('scheme:')) {
      const s = schemes.value.find((x) => x.name === cmd.slice('scheme:'.length))
      if (!s) return // 菜单打开期间方案被改掉 — 静默不导出
      await store.exportJson(schemeToOverlay(s))
    } else if (cmd === 'json') await store.exportJson()
    else if (cmd === 'yaml') await store.exportYaml()
    else if (cmd === 'copy') await store.copyJson()
  } catch (e) {
    ElMessage.error(`导出失败: ${(e as Error).message}`)
  } finally {
    exporting.value = false
  }
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

.se-arrow { margin-left: 2px; opacity: 0.6; }
</style>