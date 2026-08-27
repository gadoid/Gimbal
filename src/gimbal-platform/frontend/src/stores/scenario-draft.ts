/**
 * stores/scenario-draft.ts — 平台侧共享的"进行中"场景草稿
 *
 * 目的: 让 CaseComposer 在编辑过程中随时把当前 definition/orchestration
 *       同步到这里,任何其他视图(顶栏导出菜单等)都能读取并导出。
 *
 * 设计:
 * - 模块级单例 (Pinia store): 跨组件、跨路由保持同一份草稿。
 * - 单一 setDraft() 入口: CaseComposer 每次变更整体覆盖,避免字段漂移。
 * - fetchConverted() 封装 plate /convert → download / copy。
 *
 * 调用方:
 *   CaseComposer.vue   → watch 同步 (definition/orchestration)
 *   ScenarioExportMenu → 顶栏触发
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as yaml from 'js-yaml'
import { previewPlateDraft } from '@/api/scenario-composer'
import { copyText } from '@/utils/clipboard'
import { downloadFile } from '@/utils/download'
import { exportTimestamp } from '@/utils/datetime'
import { ElMessage } from 'element-plus'
import type { ScenarioDraft, Orchestration } from '@/types/scenario-composer'
import type { ScenarioView } from '@/types/plate'
import type { RunScheme, RunOverlay } from '@/api/scenario-composer'

interface DraftSnapshot {
  definition: ScenarioView
  orchestration: Orchestration
  /** 编辑中场景的 id (新建时为 null) — 决定导出文件名 */
  scenarioId: string | null
}

/** RunScheme → 导出 overlay(spec §8):只带 serviceBindings — envId 已随
 *  D2 退役,dataSetIds 有意不带(导出是场景级产物,v1 忽略行语义)。 */
export function schemeToOverlay(s: RunScheme): RunOverlay {
  return { serviceBindings: s.serviceBindings }
}

/** 草稿 → plate /convert → 纯可执行结构(store 无关,列表页行级导出复用)。
 *  overlay(按方案导出)不传 → 行为与旧完全一致。 */
export async function convertDraftToExecutable(
  draft: ScenarioDraft, overlay?: RunOverlay,
): Promise<Record<string, any>> {
  const res = await previewPlateDraft(draft, overlay)
  if (!res.ok) {
    const errMsg = res.errors?.length
      ? res.errors.map((e) => `${e.path}: ${e.message}`).join('; ')
      : 'plate 拒绝该草稿'
    throw new Error(`plate 转换失败 — ${errMsg}`)
  }
  if (!res.converted) {
    throw new Error('plate 未返回转换结果')
  }
  return res.converted
}

export const useScenarioDraftStore = defineStore('scenario-draft', () => {
  // ── 平台侧始终持有的进行中对象 ────────────────────────────────
  const draft = ref<DraftSnapshot | null>(null)

  function setDraft(snapshot: DraftSnapshot) {
    draft.value = snapshot
  }

  /** 平台 → Plate /convert (consumer="gimbal") → 返回纯可执行结构
   *
   * 后端 plate_client.convert() 默认 consumer="gimbal",走
   * GimbalScenarioExporter.to_dict(),Plate 内部 model_dump(exclude=...)
   * 已经把 endpoints / navigation / config_summary 等平台视图扩展字段
   * 过滤掉,我们直接用 converted 即可。
   */
  async function fetchConverted(overlay?: RunOverlay): Promise<Record<string, any>> {
    if (!draft.value) {
      throw new Error('当前没有可导出的草稿')
    }
    // 容器形:definition 原样透传 plate /convert;orchestration 不进 plate。
    const { definition, orchestration } = draft.value
    return convertDraftToExecutable({ definition, orchestration }, overlay)
  }

  function fileBase(): string {
    const id = draft.value?.scenarioId
      || draft.value?.definition?.scenarioId
      || 'scenario'
    const ts = exportTimestamp()
    return `${id}-${ts}`
  }

  /** overlay(按方案导出,spec §8)不传 → 下载行为与旧完全一致。 */
  async function exportJson(overlay?: RunOverlay): Promise<void> {
    const converted = await fetchConverted(overlay)
    const base = fileBase()
    downloadFile(`${base}.json`, JSON.stringify(converted, null, 2), 'application/json')
    ElMessage.success(`已导出 ${base}.json (plate 转换后)`)
  }

  async function exportYaml(overlay?: RunOverlay): Promise<void> {
    const converted = await fetchConverted(overlay)
    const base = fileBase()
    const content = yaml.dump(converted, { lineWidth: 120, noRefs: true })
    downloadFile(`${base}.yaml`, content, 'application/x-yaml')
    ElMessage.success(`已导出 ${base}.yaml (plate 转换后)`)
  }

  async function copyJson(): Promise<void> {
    const converted = await fetchConverted()
    const ok = await copyText(JSON.stringify(converted, null, 2))
    if (ok) ElMessage.success('plate 转换后的 JSON 已复制到剪贴板')
    else ElMessage.error('复制失败 — 请手动复制')
  }

  return {
    draft,
    setDraft,
    fetchConverted,
    exportJson,
    exportYaml,
    copyJson,
  }
})