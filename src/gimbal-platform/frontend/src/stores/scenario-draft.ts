/**
 * stores/scenario-draft.ts — 平台侧共享的"进行中"场景草稿
 *
 * 目的: 让 CaseComposer 在编辑过程中随时把当前 meta/steps/config/resource
 *       同步到这里,任何其他视图(场景库 / 执行历史 / ...)都能读取并导出。
 *
 * 设计:
 * - 模块级单例 (Pinia store): 跨组件、跨路由保持同一份草稿。
 * - 单一 setDraft() 入口: CaseComposer 每次变更整体覆盖,避免字段漂移。
 * - exportDraft() 封装 plate /convert → download / copy。
 *
 * 调用方:
 *   CaseComposer.vue   → watch 同步 (meta/steps/config/resource)
 *   Scenarios.vue      → 顶部 "导出当前编辑" 按钮
 *   ScenarioExportMenu → 行级 / 顶栏 触发
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as yaml from 'js-yaml'
import { previewPlateDraft, getScenarioDraft } from '@/api/scenario-composer'
import { ElMessage } from 'element-plus'
import type {
  ScenarioMeta, ScenarioStep, ScenarioConfig, ScenarioResource,
} from '@/types/scenario-composer'

interface DraftSnapshot {
  meta: ScenarioMeta
  steps: ScenarioStep[]
  config: ScenarioConfig
  resource: ScenarioResource
  /** 编辑中场景的 id (新建时为 null) — 决定导出文件名 */
  scenarioId: string | null
}

export const useScenarioDraftStore = defineStore('scenario-draft', () => {
  // ── 平台侧始终持有的进行中对象 ────────────────────────────────
  const draft = ref<DraftSnapshot | null>(null)

  function setDraft(snapshot: DraftSnapshot) {
    draft.value = snapshot
  }

  function clearDraft() {
    draft.value = null
  }

  /** 从场景库点行级导出时,把已保存 scenario 的整稿拉进来,然后正常 export* */
  async function loadFromSaved(scenarioId: string): Promise<void> {
    const saved = await getScenarioDraft(scenarioId)
    draft.value = {
      meta: saved.meta,
      steps: saved.steps ?? [],
      config: saved.config ?? ({
        timePolicyKind: 'record',
        retryMaxAttempts: 0,
        retryIntervalMs: 500,
        vars: [],
        services: {},
        users: {},
        setup: [],
        teardown: [],
      } as ScenarioConfig),
      resource: saved.resource ?? { items: [] } as ScenarioResource,
      scenarioId,
    }
  }

  /** 平台 → Plate /convert (consumer="gimbal") → 返回纯可执行结构
   *
   * 后端 plate_client.convert() 默认 consumer="gimbal",走
   * GimbalScenarioExporter.to_dict(),Plate 内部 model_dump(exclude=...)
   * 已经把 endpoints / navigation / config_summary 等平台视图扩展字段
   * 过滤掉,我们直接用 converted 即可。
   */
  async function fetchConverted(): Promise<Record<string, any>> {
    if (!draft.value) {
      throw new Error('当前没有可导出的草稿')
    }
    const { meta, steps, config, resource } = draft.value
    const res = await previewPlateDraft({
      meta,
      steps,
      config,
      resource,
    } as any)
    if (!res.ok) {
      const errMsg = res.errors?.length
        ? res.errors.map((e: any) => `${e.path}: ${e.message}`).join('; ')
        : 'plate 拒绝该草稿'
      throw new Error(`plate 转换失败 — ${errMsg}`)
    }
    if (!res.converted) {
      throw new Error('plate 未返回转换结果')
    }
    return res.converted
  }

  function fileBase(): string {
    const id = draft.value?.scenarioId || draft.value?.meta?.scenarioId || 'scenario'
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    return `${id}-${ts}`
  }

  function downloadFile(filename: string, content: string, mime: string) {
    const blob = new Blob([content], { type: `${mime};charset=utf-8` })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function exportJson(): Promise<void> {
    const converted = await fetchConverted()
    const base = fileBase()
    downloadFile(`${base}.json`, JSON.stringify(converted, null, 2), 'application/json')
    ElMessage.success(`已导出 ${base}.json (plate 转换后)`)
  }

  async function exportYaml(): Promise<void> {
    const converted = await fetchConverted()
    const base = fileBase()
    const content = yaml.dump(converted, { lineWidth: 120, noRefs: true })
    downloadFile(`${base}.yaml`, content, 'application/x-yaml')
    ElMessage.success(`已导出 ${base}.yaml (plate 转换后)`)
  }

  async function copyJson(): Promise<void> {
    const converted = await fetchConverted()
    const text = JSON.stringify(converted, null, 2)
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success('plate 转换后的 JSON 已复制到剪贴板')
    } catch {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      ElMessage.success('plate 转换后的 JSON 已复制到剪贴板')
    }
  }

  return {
    draft,
    setDraft,
    clearDraft,
    loadFromSaved,
    fetchConverted,
    exportJson,
    exportYaml,
    copyJson,
  }
})