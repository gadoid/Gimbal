<!--
  RunDialog.vue — 运行对话框弹层壳(执行设计 §1.5:剥壳后的壳)。

  内容本体在 RunConfigPanel.vue(方案 chip 两路径 + 绑定行 + 基础设置 +
  另存 + footer);本文件只负责 Teleport 弹层(overlay / 标题 / 关闭钮)。
  执行器页右栏不经过这里 —— 它直接内嵌 RunConfigPanel(footer=false,
  宽度自适应容器)。装配逻辑在 useRunAssembly;纯函数在 utils/run-bindings。
-->
<template>
  <Teleport v-if="visible" to="body">
    <div class="run-overlay" @click.self="$emit('close')">
      <div class="run-dialog" role="dialog" aria-modal="true">
        <header class="run-header">
          <div>
            <h2>运行编排</h2>
            <p class="muted">从 <code>{{ scenario?.meta?.name || scenario?.meta?.scenarioId || '—' }}</code> 触发执行</p>
          </div>
          <button class="icon-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </header>

        <div class="run-body">
          <RunConfigPanel
            v-bind="panelProps"
            @cancel="$emit('close')"
            @confirm="(sel, opts) => $emit('confirm', sel, opts)"
            @save-as-scheme="(body) => $emit('saveAsScheme', body)"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RunConfigPanel from './RunConfigPanel.vue'
import type { DataSetSelection, ServiceBinding, SchemeV2 } from '@/api/scenario-composer'
import type { Scenario, DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'

const props = withDefaults(defineProps<{
  /** 弹层显隐(父级亦可直接 v-if;默认 true 兼容外部 v-if 用法) */
  visible?: boolean
  scenario?: Scenario | null
  /** 数据集清单:自建方案失效判定/概要行数与数据集名展示用 */
  dataSets?: DataSetSummary[]
  running?: boolean
  lastRunId?: string | null
  lastRunError?: string | null
  /** 运行方案(阶段② CRUD wire;default 置顶由宿主保证) */
  schemes: SchemeV2[]
  /** 深链预选(工作台「▶ 运行此方案」);null/不在列表 = 默认方案 */
  initialSchemeId?: string | null
  /** 绑定行 = 声明 ∪ 引用并集(D3);declaredUrl null = 未声明引用行 */
  serviceRows: { service: string; declaredUrl: string | null }[]
  /** 绑定下拉选项:owner 凭证池 ∪ 场景内置 users 别名(宿主供给) */
  authOptions: string[]
  /** 平台编排展示名(orchestration.steps[i].name,与 steps 同序) */
  stepOrchestrationNames?: string[]
  /** 断言注册表条目(spec v3 §2/§4):自建方案注入条目失效判定面 */
  assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>
  /** 死条目(悬空)id — 宿主预计算(useInjectableSurface 分组),失效判定沿用 */
  deadEntryIds?: string[]
}>(), {
  visible: true,
  scenario: null,
  dataSets: () => [] as DataSetSummary[],
  running: false,
  lastRunId: null,
  lastRunError: null,
  initialSchemeId: null,
  stepOrchestrationNames: () => [] as string[],
  assertionEntries: () => [] as AssertionEntry[],
  deadEntryIds: () => [] as string[],
})

const emit = defineEmits<{
  close: []
  confirm: [
    dataSetSelection: DataSetSelection[],
    opts: {
      /** 溯源:本次执行按哪个方案发起(两态都带) */
      schemeId: string
      schemeName: string
      stepTo?: number
      nRuns?: number
      parallel?: number
      serviceBindings?: Record<string, ServiceBinding>
      injectionEntryIds?: string[]
    },
  ]
  /** 另存为方案(仅默认方案态):当前绑定与参数存为自建方案 */
  saveAsScheme: [body: Omit<SchemeV2, 'schemeId' | 'isDefault'>]
}>()

/** 面板 props = 壳 props 去掉 visible(visible 是弹层概念,面板没有) */
const panelProps = computed(() => {
  const { visible: _visible, ...rest } = props
  return rest
})
void emit
</script>

<style scoped>
.run-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 18, 25, 0.5);
  backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.run-dialog {
  width: 720px; max-width: 92vw; max-height: 88vh;
  background: #fff; border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.25);
  display: flex; flex-direction: column;
  animation: slideUp 0.25s ease-out;
}
@keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.run-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 24px 28px 20px;
  border-bottom: 1px solid #e6e8ec;
}
.run-header h2 { margin: 0 0 4px; font-size: 20px; }
.run-header .muted { font-size: 13px; color: #5a6273; }
.run-header .muted code { font-family: var(--font-mono); background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }

.icon-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; border-radius: 6px;
  color: #5a6273; cursor: pointer; transition: all 0.15s;
}
.icon-btn:hover { background: #f5f6fa; color: #1a1d24; }

.run-body { padding: 20px 28px; flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
</style>
