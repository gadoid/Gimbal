/** zod-typed-schema — zod 4 形态的两处移植偏差(2026-11-05 修复轮评审 P3-1):
 * ① ZodDefault 的 def.defaultValue 是值本身,不是 zod3 的工厂函数;
 * ② invalid_union 子错误在 issue.errors(二维,子路径相对 union),
 *    不是 zod3 的 unionErrors。 */
import { describe, it, expect } from 'vitest'
import { z } from 'zod'
import { toTypedSchema } from '@/utils/zod-typed-schema'

describe('toTypedSchema — zod 4', () => {
  it('cast 失败时按 ZodDefault 默认值合并(值形态与工厂形态)', () => {
    const schema = toTypedSchema(z.object({
      name: z.string().min(1),
      ttl: z.string().default('90'),
      tags: z.array(z.string()).default(() => ['a']),
      nested: z.object({ on: z.boolean().default(true) }),
    }))
    expect(schema.cast({ name: '' })).toEqual({
      name: '', ttl: '90', tags: ['a'], nested: { on: true },
    })
  })

  it('invalid_union 子错误展平到各自的完整字段路径', async () => {
    const schema = toTypedSchema(z.object({
      auth: z.union([
        z.object({ kind: z.literal('basic'), user: z.string() }),
        z.object({ kind: z.literal('bearer'), token: z.string() }),
      ]),
    }))
    const { errors } = await schema.parse({ auth: { kind: 'none' } })
    const paths = errors.map((e) => e.path).sort()
    expect(paths).toEqual(['auth', 'auth.kind', 'auth.token', 'auth.user'])
    // 两个分支的 kind 报错归并到同一字段
    expect(errors.find((e) => e.path === 'auth.kind')!.errors).toHaveLength(2)
  })
})
