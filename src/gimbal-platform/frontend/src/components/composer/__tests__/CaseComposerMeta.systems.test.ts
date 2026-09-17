/**
 * CaseComposerMeta.vue — 归属系统下拉动态化回归测试。
 *
 * 选项不再硬编码 (fin/logi/wms/mall/common),改为挂载时经 Vite /plate
 * 代理拉取 plate /api/system 的已注册系统列表(同 Catalog 面板先例);
 * 失败静默降级为空列表,allow-create 手输不受影响。
 *
 * 弹层走真实 teleport,el-select 下拉项挂 document.body,用 document
 * 检索(同 ScenarioExportMenu.scheme.test.ts 先例,teleport stub 叠加
 * 在 jsdom 会递归更新爆表,故不用 teleport stub)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CaseComposerMeta from '@/components/composer/CaseComposerMeta.vue'
import { useAuthStore } from '@/stores/auth'
import type { MetaView } from '@/types/plate'

function meta(): MetaView {
  return {
    name: 'n', description: '', module: 'm', priority: 2,
    author: 'a', owner: 'o', tags: [], version: '',
    createTime: '', expire: false, requirementRef: [], system: [],
  }
}

function plateSystemsPayload(ids: string[]) {
  return {
    ok: true,
    json: async () => ({
      ok: true, dim: 'system',
      data: { items: ids.map((id) => ({ id })), total: ids.length },
    }),
  }
}

/** 归属系统选项文本(迁移后为内联 checkbox 芯片,不再有弹层)。
 *  候选直接渲染在 .sys-chips 里,兼容旧断言语义。 */
async function openSystemOptions(wrapper: ReturnType<typeof mount>): Promise<string[]> {
  await flushPromises()
  return wrapper.findAll('[data-testid="meta-system"] .sys-chip')
    .map((c) => c.text().trim())
}

describe('CaseComposerMeta 归属系统动态选项', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
    fetchMock = vi.fn().mockResolvedValue(plateSystemsPayload(['fin', 'crm']))
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('下拉选项来自 plate /api/system (带 token),而非硬编码', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    const w = mount(CaseComposerMeta, {
      props: { modelValue: meta() },
      global: { plugins: [] },
    })
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/plate/api/system',
      expect.objectContaining({ headers: { Authorization: 'Bearer tok' } }),
    )
    const texts = await openSystemOptions(w)
    expect(texts.join('\n')).toContain('fin')
    expect(texts.join('\n')).toContain('crm')
  })

  it('不再提供硬编码的 logi/wms/mall/common 默认项', async () => {
    const w = mount(CaseComposerMeta, {
      props: { modelValue: meta() },
      global: { plugins: [] },
    })
    await flushPromises()
    const all = (await openSystemOptions(w)).join('\n')
    for (const gone of ['logi', 'wms', 'mall', 'common']) {
      expect(all).not.toContain(gone)
    }
  })

  it('fetch 失败时静默降级为空列表,表单不崩', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))
    const w = mount(CaseComposerMeta, {
      props: { modelValue: meta() },
      global: { plugins: [] },
    })
    await flushPromises()
    expect(await openSystemOptions(w)).toHaveLength(0)
    expect(w.text()).toContain('归属系统')
  })
})
