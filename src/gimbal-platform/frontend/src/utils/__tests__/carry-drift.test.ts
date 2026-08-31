/**
 * carry-drift —— 漂移面板数据组装纯核心(T16,spec §7):
 *   - 三类 → 勾选项固定序(remove→add→rename),key 可回读;
 *   - 对齐服务(三列表全空)hasCarryDrift=False → 面板正向确认;
 *   - canGenerateCarryBatch:plateReachable=False 一票否决(T11 硬性契约:
 *     plate 挂时 drift 会把全表绑定误报 orphaned,禁批生成防误清空)。
 */
import { describe, expect, it } from 'vitest'
import type { ServiceDrift } from '@/api/carry'
import {
  canGenerateCarryBatch,
  carryCheckKey,
  checkedServices,
  driftCheckOptions,
  hasCarryDrift,
  parseCarryChecked,
} from '../carry-drift'

const DRIFTED: ServiceDrift = {
  service: 'fin.order',
  orphaned: ['$.legacy_fee'],
  uncovered: ['$.fee'],
  renamedSuggestions: [{ from: '$.legacy_fee', to: '$.fee' }],
}

const ALIGNED: ServiceDrift = {
  service: 'fin.settle',
  orphaned: [],
  uncovered: [],
  renamedSuggestions: [],
}

/** 局部形状别名:测试内构造不引出 util 未导出的类型。 */
interface CarryCheckItemLike {
  service: string
  opType: string
  payload: Record<string, unknown>
}

describe('driftCheckOptions — ServiceDrift → 勾选项', () => {
  it("三类固定序:孤儿移除 → 未绑定补绑(value='')→ 改名建议", () => {
    const opts = driftCheckOptions(DRIFTED)
    expect(opts.map((o) => o.text)).toEqual([
      '孤儿绑定 $.legacy_fee → 移除',
      '未绑定面字段 $.fee → 补绑定',
      '改名建议 $.legacy_fee → $.fee',
    ])
    expect(opts[0].item).toEqual({
      service: 'fin.order', opType: 'removeCarryBinding',
      payload: { service: 'fin.order', path: '$.legacy_fee' },
    })
    expect(opts[1].item.payload).toEqual(
      { service: 'fin.order', path: '$.fee', value: '' })
    expect(opts[2].item.opType).toBe('renameCarryPath')
  })

  it('对齐服务 → 空清单(hasCarryDrift=False,面板走正向确认分支)', () => {
    expect(hasCarryDrift(ALIGNED)).toBe(false)
    expect(driftCheckOptions(ALIGNED)).toEqual([])
    expect(hasCarryDrift(DRIFTED)).toBe(true)
  })
})

describe('勾选值回读 — parseCarryChecked / checkedServices', () => {
  it('key(JSON 串)↔ item 往返一致;服务去重保首见序', () => {
    const a = driftCheckOptions(DRIFTED)[0].item
    const b: CarryCheckItemLike = {
      service: 'fin.settle', opType: 'addCarryBinding',
      payload: { service: 'fin.settle', path: '$.fee', value: 'x' },
    }
    const raws = [carryCheckKey(a), carryCheckKey(b), carryCheckKey(a)]
    const items = parseCarryChecked(raws)

    expect(items).toHaveLength(3)                 // 勾选不去重(el-checkbox-group 语义)
    expect(checkedServices(items)).toEqual(['fin.order', 'fin.settle'])
    expect(items[0]).toEqual(a)
  })

  it('坏串防御性剔除,不整页失败', () => {
    const a = driftCheckOptions(DRIFTED)[0].item
    expect(parseCarryChecked(['not-json', '{}', carryCheckKey(a)]))
      .toEqual([a])
  })
})

describe('canGenerateCarryBatch — T11 硬性契约', () => {
  it('plate 不可达一票否决(勾了多少都禁)', () => {
    expect(canGenerateCarryBatch(false, 0)).toBe(false)
    expect(canGenerateCarryBatch(false, 3)).toBe(false)
  })

  it('plate 可达且已有勾选才放开', () => {
    expect(canGenerateCarryBatch(true, 0)).toBe(false)
    expect(canGenerateCarryBatch(true, 1)).toBe(true)
  })
})
