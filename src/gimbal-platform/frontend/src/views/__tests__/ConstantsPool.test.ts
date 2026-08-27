/**
 * ConstantsPool 管理页 — F14-F18:
 * F14 目录卡片渲染(kind/summary,展开拉 full);
 * F15 字面量新增(默认 string 类型,POST 载荷含 value 文本);
 * F16 生成器新增(目录驱动动态表单 + spec 预览,POST 载荷含 spec);
 * F17 编辑预填 + 删除确认流;
 * F18 目录降级(降级条 + 生成器不可选;字面量 CRUD 不受影响)。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus, { ElMessageBox } from 'element-plus'
import ConstantsPool from '@/views/ConstantsPool.vue'
import * as constantsApi from '@/api/constants'
import * as catalogApi from '@/api/generator_catalog'

vi.mock('@/api/constants', () => ({
  list: vi.fn().mockResolvedValue([]),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('@/api/generator_catalog', () => ({
  listGeneratorKinds: vi.fn(),
  getGeneratorKindFull: vi.fn(),
}))
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return { ...actual, ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') } }
})

const SEQ_FULL = {
  kind: 'seq',
  summary: '自增序号',
  description: '执行内自增序号:prefix 前缀 + width 位零填充,从 start 起。',
  params: [
    { name: 'prefix', type: 'string', required: false, default: '', enum: null, min: null, max: null, description: '序号前缀' },
    { name: 'width', type: 'integer', required: false, default: 6, enum: null, min: 1, max: 20, description: '零填充宽度' },
    { name: 'start', type: 'integer', required: false, default: 1, enum: null, min: null, max: null, description: '起始值' },
  ],
  example: { kind: 'seq', prefix: 'BL', width: 6, start: 1 },
}

const GEN_ROW = {
  id: 1,
  name: 'bl_no',
  description: '业务单号',
  entry_kind: 'generator',
  value: null,
  spec: { kind: 'random_decorated', length: 6, head: 'GIMBAL728' },
  created_at: '2026-08-26T00:00:00Z',
  updated_at: '2026-08-26T00:00:00Z',
}

function mountPage() {
  return mount(ConstantsPool, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(catalogApi.listGeneratorKinds).mockResolvedValue([
    { kind: 'uuid', summary: 'UUID' },
    { kind: 'seq', summary: '自增序号' },
  ])
  vi.mocked(catalogApi.getGeneratorKindFull).mockResolvedValue(SEQ_FULL as never)
  vi.clearAllMocks()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ConstantsPool — 目录', () => {
  it('F14: 渲染 kind 卡片;展开拉 full 并渲染参数表与示例', async () => {
    const w = mountPage()
    await flushPromises()
    const cards = w.findAll('.kind-card')
    expect(cards).toHaveLength(2)
    expect(cards[1].attributes('data-kind')).toBe('seq')
    expect(cards[1].text()).toContain('自增序号')

    await cards[1].find('.kind-head').trigger('click')
    await flushPromises()
    expect(catalogApi.getGeneratorKindFull).toHaveBeenCalledWith('seq')
    expect(w.find('[data-param="width"]').text()).toContain('零填充宽度')
    expect(w.text()).toContain('"kind": "seq"') // 示例 JSON
    w.unmount()
  })

  it('F18: 目录不可用 — 降级条 + 生成器类型禁用,条目表仍渲染', async () => {
    vi.mocked(catalogApi.listGeneratorKinds).mockRejectedValue(new Error('plate down'))
    vi.mocked(constantsApi.list).mockResolvedValue([GEN_ROW as never])
    const w = mountPage()
    await flushPromises()

    expect(w.find('.degraded').exists()).toBe(true)

    await w.find('[data-action="pool-create"]').trigger('click') // 字面量 CRUD 入口仍在
    await flushPromises()
    const radios = w.findAll('.el-radio-button')
    expect(radios.some((r) => r.classes().includes('is-disabled'))).toBe(true)
    expect(w.find('[data-testid="entry-dialog"]').exists()).toBe(true)
    expect(w.findAll('.el-table__row')).toHaveLength(1)
    w.unmount()
  })
})

describe('ConstantsPool — 条目 CRUD', () => {
  it('F15: 新增字面量(默认 string)→ create 载荷含值文本', async () => {
    vi.mocked(constantsApi.create).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="pool-create"]').trigger('click')
    await flushPromises()
    await w.find('[data-field="name"]').setValue('bank_id')
    await w.find('[data-field="valueStr"]').setValue('319666690256273408')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()

    expect(constantsApi.create).toHaveBeenCalledWith({
      name: 'bank_id',
      description: '',
      entry_kind: 'literal',
      value: '319666690256273408',
    })
    w.unmount()
  })

  it('F16: 新增生成器 — kind 芯片 → 动态参数(默认预填)+ spec 预览 → create 含 spec', async () => {
    vi.mocked(constantsApi.create).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="pool-create"]').trigger('click')
    await flushPromises()
    await w.find('[data-field="entry_kind"] input[value="generator"]').trigger('click')
    await flushPromises()
    await w.find('.kind-chip[data-kind="seq"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-field="param-prefix"]').exists()).toBe(true)
    // 默认预填: prefix='' 被剔除, width/start 取默认
    expect(w.find('[data-testid="spec-preview"]').text()).toContain('"kind":"seq"')

    await w.find('[data-field="name"]').setValue('order_seq')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()

    expect(constantsApi.create).toHaveBeenCalledWith({
      name: 'order_seq',
      description: '',
      entry_kind: 'generator',
      spec: { kind: 'seq', width: 6, start: 1 },
    })
    w.unmount()
  })

  it('F17: 编辑预填 + 删除确认', async () => {
    vi.mocked(constantsApi.list).mockResolvedValue([GEN_ROW as never])
    vi.mocked(catalogApi.getGeneratorKindFull).mockResolvedValue(SEQ_FULL as never)
    vi.mocked(constantsApi.patch).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="edit"]').trigger('click')
    await flushPromises()
    const nameInput = w.find('[data-field="name"]')
    expect((nameInput.element as HTMLInputElement).value).toBe('bl_no')
    expect(w.find('[data-testid="spec-preview"]').text()).toContain('random_decorated')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()
    expect(constantsApi.patch).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ description: '业务单号' }),
    )

    await w.find('[data-action="delete"]').trigger('click')
    await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(constantsApi.remove).toHaveBeenCalledWith(1)
    w.unmount()
  })

  it('F17b: 编辑降级 — full 拉取失败时提交不丢已存 spec 参数', async () => {
    vi.mocked(constantsApi.list).mockResolvedValue([
      { ...GEN_ROW, spec: { kind: 'seq', width: 6, start: 1 } } as never,
    ])
    vi.mocked(catalogApi.getGeneratorKindFull).mockRejectedValue(new Error('full down'))
    vi.mocked(constantsApi.patch).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="edit"]').trigger('click')
    await flushPromises() // ensureFull 拒绝 → genParams 空(目录降级编辑)
    await w.find('[data-field="description"]').setValue('只改说明')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()

    // 已存 width/start 不因目录 full 拉取失败而被从 spec 中丢弃
    expect(constantsApi.patch).toHaveBeenCalledWith(1, {
      description: '只改说明',
      spec: { kind: 'seq', width: 6, start: 1 },
    })
    w.unmount()
  })
})
