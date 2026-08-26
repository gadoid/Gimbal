/**
 * stores/constants.ts — 常量池(条目 + 生成器目录)共享 store。
 *
 * 两个消费方: 编排页 ConstantPoolPanel(条目)/ 管理页 ConstantsPool
 * (条目 CRUD + 目录文档)。条目与目录相互独立拉取、独立降级 ——
 * 目录(plate 代理)挂了不影响字面量 CRUD 与 Panel。
 * ensureEntries/ensureCatalog in-flight 去重: 双挂载点(CaseComposer
 * rail 与 Canvas)同时触发也只发一次请求。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as constantsApi from '@/api/constants'
import * as catalogApi from '@/api/generator_catalog'
import type {
  ConstantEntry,
  ConstantEntryCreateIn,
  ConstantEntryPatchIn,
  GeneratorKindView,
} from '@/types/constants'
import { useSetStatus } from '@/utils/useSetStatus'

const byName = (a: ConstantEntry, b: ConstantEntry) => a.name.localeCompare(b.name)

export const useConstantsStore = defineStore('constants', () => {
  const entries = ref<ConstantEntry[]>([])
  const catalog = ref<GeneratorKindView[]>([])
  const catalogError = ref('')
  const { fetchStatus, lastError, setStatus } = useSetStatus()

  let entriesInFlight: Promise<ConstantEntry[]> | null = null
  let catalogInFlight: Promise<GeneratorKindView[]> | null = null

  async function fetchEntries(): Promise<ConstantEntry[]> {
    setStatus('loading')
    try {
      entries.value = await constantsApi.list()
      setStatus('idle')
      return entries.value
    } catch (e) {
      setStatus('error', e instanceof Error ? e.message : 'fetch failed')
      throw e
    }
  }

  /** 幂等拉取(已有数据/已在途时短路)— 挂载点可直接 void 调用。 */
  function ensureEntries(): Promise<ConstantEntry[]> {
    if (entriesInFlight) return entriesInFlight
    if (entries.value.length) return Promise.resolve(entries.value)
    entriesInFlight = fetchEntries().finally(() => {
      entriesInFlight = null
    })
    return entriesInFlight
  }

  /** 目录拉取不 throw — 失败落 catalogError,消费方渲染降级条。 */
  function ensureCatalog(): Promise<GeneratorKindView[]> {
    if (catalogInFlight) return catalogInFlight
    if (catalog.value.length || catalogError.value) return Promise.resolve(catalog.value)
    catalogInFlight = catalogApi
      .listGeneratorKinds()
      .then((items) => {
        catalog.value = items
        catalogError.value = ''
        return items
      })
      .catch((e: unknown) => {
        catalogError.value = e instanceof Error ? e.message : '生成器目录不可用'
        return []
      })
      .finally(() => {
        catalogInFlight = null
      })
    return catalogInFlight
  }

  async function createEntry(payload: ConstantEntryCreateIn): Promise<ConstantEntry> {
    const en = await constantsApi.create(payload)
    entries.value = [...entries.value, en].sort(byName)
    return en
  }

  async function patchEntry(id: number, payload: ConstantEntryPatchIn): Promise<ConstantEntry> {
    const en = await constantsApi.patch(id, payload)
    const idx = entries.value.findIndex((x) => x.id === id)
    if (idx >= 0) entries.value[idx] = en
    return en
  }

  async function removeEntry(id: number): Promise<void> {
    await constantsApi.remove(id)
    entries.value = entries.value.filter((x) => x.id !== id)
  }

  return {
    entries,
    catalog,
    catalogError,
    fetchStatus,
    lastError,
    ensureEntries,
    ensureCatalog,
    createEntry,
    patchEntry,
    removeEntry,
  }
})
