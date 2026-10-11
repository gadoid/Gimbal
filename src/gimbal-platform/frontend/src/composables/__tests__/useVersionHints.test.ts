import { describe, it, expect } from 'vitest'
import { computeVersionHints } from '@/composables/useVersionHints'

const lines = (system: string, specs: Array<[string, number, number]>) =>
  ({ [system]: specs.map(([line, revs, latest]) => ({
    line, revisions: revs, latest: `${line}#${latest}`, line_scheme: 'free',
  })) })

describe('computeVersionHints', () => {
  it('working → preview hint when lines exist', () => {
    const hints = computeVersionHints({
      plate: { fin: 'working' },
      systemLines: lines('fin', [['1.0', 3, 3]]),
    })
    expect(hints).toHaveLength(1)
    expect(hints[0].key).toBe('preview:fin')
    expect(hints[0].level).toBe('warn')
    expect(hints[0].action).toBe('adapt')
  })

  it('working → no hint when system has no lines', () => {
    const hints = computeVersionHints({
      plate: { fin: 'working' },
      systemLines: {},
    })
    expect(hints).toHaveLength(0)
  })

  it('new version line available', () => {
    const hints = computeVersionHints({
      plate: { fin: '1.0#2' },
      systemLines: lines('fin', [
        ['1.0', 3, 3], ['2.0', 1, 1],
      ]),
    })
    expect(hints.some(h => h.key === 'new-line:fin')).toBe(true)
    expect(hints.find(h => h.key === 'new-line:fin')?.level).toBe('info')
  })

  it('definition corrected (latest > declared)', () => {
    const hints = computeVersionHints({
      plate: { fin: '1.0#2' },
      systemLines: lines('fin', [['1.0', 5, 5]]),
    })
    expect(hints.some(h => h.key === 'corrected:fin')).toBe(true)
    expect(hints.find(h => h.key === 'corrected:fin')?.level).toBe('warn')
  })

  it('up-to-date → no hints', () => {
    const hints = computeVersionHints({
      plate: { fin: '1.0#5' },
      systemLines: lines('fin', [['1.0', 5, 5]]),
    })
    expect(hints).toHaveLength(0)
  })

  it('multiple systems → multiple hints', () => {
    const hints = computeVersionHints({
      plate: { fin: 'working', platform: '1.0#1' },
      systemLines: {
        ...lines('fin', [['1.0', 2, 2]]),
        ...lines('platform', [['1.0', 3, 3]]),
      },
    })
    expect(hints).toHaveLength(2)
    expect(hints.find(h => h.key === 'preview:fin')).toBeDefined()
    expect(hints.find(h => h.key === 'corrected:platform')).toBeDefined()
  })

  it('invalid ref → no hints (defensive)', () => {
    const hints = computeVersionHints({
      plate: { fin: 'garbage' },
      systemLines: lines('fin', [['1.0', 1, 1]]),
    })
    expect(hints).toHaveLength(0)
  })
})
