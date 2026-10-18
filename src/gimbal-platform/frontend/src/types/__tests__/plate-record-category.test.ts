/**
 * b2-10a(归一方案 v1.0 §3.3):前端记录域判定函数单测 —— 与后端
 * run_semantics.record_category 读同一份 ref-record-domain.json(两侧
 * 同源,防样例漂移;后端侧见 backend/tests/test_ref_category_contract.py)。
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { plateRecordCategory } from '@/types/plate'

// vitest(jsdom)下 import.meta.url 非 file 协议 —— 用 cwd 相对定位
// (vitest 运行目录 = frontend/)
const fixturePath = resolve(
  process.cwd(), 'src/types/__fixtures__/ref-record-domain.json')

interface Case { value: string; category: string }
const cases: Case[] = JSON.parse(readFileSync(fixturePath, 'utf-8')).cases

describe('plateRecordCategory — 记录域(与后端共享 fixture)', () => {
  it('样例全覆盖且与 fixture 一致', () => {
    for (const c of cases) {
      expect(plateRecordCategory(c.value), JSON.stringify(c))
        .toBe(c.category)
    }
  })
  it('null/undefined/空白归 UNDECLARED', () => {
    expect(plateRecordCategory(null)).toBe('UNDECLARED')
    expect(plateRecordCategory(undefined)).toBe('UNDECLARED')
    expect(plateRecordCategory('  ')).toBe('UNDECLARED')
  })
})
