/**
 * SignalDots — W21 趋势切换点:相邻两次修订钉定签名不同处标蓝环。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SignalDots from '../SignalDots.vue'

describe('SignalDots — 修订切换点 (W21)', () => {
  it('相邻签名不同 → 该点带 switch 类;窗首不标;未钉(null)不标', () => {
    const w = mount(SignalDots, {
      props: {
        runs: ['done', 'done', 'failed', 'done', 'done'],
        pins: ['fin#1.0#1', 'fin#1.0#1', 'fin#1.0#2', 'fin#1.0#2', null],
      },
    })
    const dots = w.findAll('.signal-dots i')
    expect(dots).toHaveLength(5)
    // 索引 2 = 与前次(fin#1.0#1)不同的第一次 → 切换点
    expect(dots[0].classes()).not.toContain('switch')   // 窗首无前次
    expect(dots[1].classes()).not.toContain('switch')   // 同前次
    expect(dots[2].classes()).toContain('switch')
    expect(dots[3].classes()).not.toContain('switch')
    expect(dots[4].classes()).not.toContain('switch')   // null 不标
    expect(w.attributes('title')).toContain('1 处修订切换')
  })

  it('不传 pins → 行为与旧版一致(无 switch 类)', () => {
    const w = mount(SignalDots, {
      props: { runs: ['done', 'failed'] },
    })
    expect(w.attributes('title')).toBe('近 2 次执行')
    expect(w.findAll('.signal-dots i.switch')).toHaveLength(0)
  })

  it('未钉 → 已钉的切换也标(working 执行 → 钉定执行是切换)', () => {
    const w = mount(SignalDots, {
      props: { runs: ['done', 'done'], pins: [null, 'fin#1.0#1'] },
    })
    const dots = w.findAll('.signal-dots i')
    expect(dots[1].classes()).toContain('switch')
  })
})
