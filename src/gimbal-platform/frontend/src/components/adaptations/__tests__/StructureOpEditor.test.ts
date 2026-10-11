/**
 * StructureOpEditor —— RS4b 结构级改造编辑器(Release §5.4)。
 *
 * 锁三条链路:
 *   - 编辑上抛:opType/config 的任何编辑经 update:items 到达父组件
 *     (断链即提交静默丢结构 op —— 2026-10-11 曾断,此为回归闸);
 *   - toOps 转换:编号 1 起 → 引擎 0 起;call 不在前端拼
 *     (场景自有字段由后端继承/由目录 service 带出);
 *   - incompleteReason:跨系统缺修订/必填空/JSON 非法在提交口拦下。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import StructureOpEditor, {
  toOps, incompleteReason, type StructureItem,
} from '@/components/adaptations/StructureOpEditor.vue'

const structure = [
  { step: 0, endpoint: 'fin.order_entrust.order_add', reason: 'path 变更' },
  { step: 2, endpoint: 'fin.order.order_detail', reason: '接口下线' },
]

describe('StructureOpEditor 编辑上抛', () => {
  it('挂载即上抛初始 items(opType 空,条目数与 structure 对齐)', async () => {
    const w = mount(StructureOpEditor, { props: { structure } })
    await nextTick()
    const emitted = w.emitted('update:items')
    expect(emitted).toBeTruthy()
    const items = emitted!.at(-1)![0] as StructureItem[]
    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({ step: 0, opType: '', config: {} })
  })

  it('选择 opType 后上抛带 opType 的条目', async () => {
    const w = mount(StructureOpEditor, { props: { structure } })
    await w.find('[data-testid="soe-type"]').setValue('removeStep')
    const items = w.emitted('update:items')!.at(-1)![0] as StructureItem[]
    expect(items[0].opType).toBe('removeStep')
  })

  it('父组件改 structure(重新比对)时重铸本地副本', async () => {
    const w = mount(StructureOpEditor, { props: { structure } })
    await w.setProps({ structure: [structure[0]] })
    const items = w.emitted('update:items')!.at(-1)![0] as StructureItem[]
    expect(items).toHaveLength(1)
    expect(items[0].opType).toBe('')
  })
})

describe('toOps 转换(编号 1 起 → 0 起;不拼 call)', () => {
  const base = (over: Partial<StructureItem>): StructureItem => ({
    step: 0, endpoint: 'fin.a', reason: '', opType: '', config: {},
    ...over,
  })

  it('空 opType 与 __skip 跳过', () => {
    expect(toOps([base({}), base({ opType: '__skip' })])).toEqual([])
  })

  it('removeStep 原样提交基座', () => {
    expect(toOps([base({ opType: 'removeStep' })]))
      .toEqual([{ op: 'removeStep', step: 0, endpoint: 'fin.a' }])
  })

  it('replaceEndpoint 解析 old=new 行映射;无 call 构造', () => {
    const ops = toOps([base({
      opType: 'replaceEndpoint',
      config: { endpoint: 'fin.b', fieldMapping: 'order_id=orderId\n\nuser_id = userId' },
    })])
    expect(ops).toEqual([{
      op: 'replaceEndpoint', step: 0, endpoint: 'fin.b',
      fieldMapping: { order_id: 'orderId', user_id: 'userId' },
    }])
  })

  it('mergeSteps 编号 1 起(如 "1,3" → [0,2]);mergedStep 只带 service', () => {
    const ops = toOps([base({
      opType: 'mergeSteps',
      config: { steps: '1, 3, x', endpoint: 'fin.merged', service: 'svc-2' },
    })])
    expect(ops[0].steps).toEqual([0, 2])
    expect(ops[0].endpoint).toBe('fin.merged')
    expect(ops[0].mergedStep).toEqual({ service: 'svc-2' })
  })

  it('insertStep at 1 起(at=3 → 2);newStep 只带 endpoint+service', () => {
    const ops = toOps([base({
      opType: 'insertStep',
      config: { at: 3, endpoint: 'fin.auth', service: 'auth-svc' },
    })])
    expect(ops[0].at).toBe(2)
    expect(ops[0].newStep).toEqual({ endpoint: 'fin.auth', service: 'auth-svc' })
  })

  it('splitStep body JSON 容错为空对象;跨系统带 targetRevision', () => {
    const ops = toOps([base({
      opType: 'splitStep',
      config: { revision: '2.0#3', newSteps: [
        { endpoint: 'fin.c', body: '{"a":1}' },
        { endpoint: 'fin.d', body: 'not-json' },
      ] },
    })])
    expect(ops[0].targetRevision).toBe('2.0#3')
    const ns = ops[0].newSteps as Array<{ body: unknown }>
    expect(ns[0].body).toEqual({ a: 1 })
    expect(ns[1].body).toEqual({})
  })
})

describe('incompleteReason 提交口校验', () => {
  const base = (over: Partial<StructureItem>): StructureItem => ({
    step: 0, endpoint: 'fin.a', reason: '', opType: '', config: {},
    ...over,
  })

  it('全部未配置/跳过 → 可提交', () => {
    expect(incompleteReason([base({}), base({ opType: '__skip' })])).toBeNull()
  })

  it('必填接口缺失 → 拦下', () => {
    expect(incompleteReason([base({
      opType: 'replaceEndpoint', config: { endpoint: '' },
    })])).toContain('未选择目标接口')
  })

  it('合并少于 2 个有效编号 → 拦下', () => {
    expect(incompleteReason([base({
      opType: 'mergeSteps', config: { steps: '1', endpoint: 'fin.m' },
    })])).toContain('至少要 2 个')
  })

  it('拆分 JSON 非法 → 拦下(不再悄悄当空对象)', () => {
    expect(incompleteReason([base({
      opType: 'splitStep',
      config: { newSteps: [{ endpoint: 'fin.c', body: 'not-json' }] },
    })])).toContain('不是合法 JSON')
  })

  it('跨系统接口缺修订 → 拦下', () => {
    expect(incompleteReason([base({
      opType: 'replaceEndpoint',
      config: { endpoint: 'log.audit.push', _system: 'log', revision: '' },
    })])).toContain('必须填该系统的修订')
    // 填了修订 → 通过
    expect(incompleteReason([base({
      opType: 'replaceEndpoint',
      config: { endpoint: 'log.audit.push', _system: 'log', revision: '2.0#3' },
    })])).toBeNull()
  })
})
