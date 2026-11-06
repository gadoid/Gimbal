/**
 * zod-typed-schema.ts — vee-validate × zod 4 的本地 toTypedSchema(2026-11-05)。
 *
 * 官方 @vee-validate/zod 停在 zod 3(peer ^3.24.0),而 zod 4.6.6 是
 * GHSA-mrhx-c7xc-m3w5(超大集合校验内存耗尽)的修复版——桥没有官方
 * zod 4 支持,按其 v4.15.1 适配器语义移植到本地:
 *  - parse:safeParseAsync → issue 按 vee 路径语法聚合(数组下标转
 *    中括号),invalid_union 展平子错误(zod4 子路径相对,拼父路径);
 *  - cast:parse 失败时退 defaults 合并(zod 不支持不校验的 cast);
 *  - describe:按路径走 shape 判 required/exists。
 * 内部探测从 zod3 的 _def.typeName 换成 zod4 的 instanceof。
 */
import { ZodArray, ZodDefault, ZodObject, z, type ZodType } from 'zod'

interface IssueLike {
  code?: string
  message: string
  path: (string | number | symbol)[]
  /** zod4 invalid_union:每个分支一组子 issue(二维);子 issue 的 path
   * 相对 union 自身(zod3 的 unionErrors 是绝对路径) */
  errors?: IssueLike[][]
}

type FieldError = { errors: string[]; path?: string }

export interface ZodTypedSchema<TInput, TOutput> {
  __type: 'VVTypedSchema'
  parse(value: unknown): Promise<{ value?: TOutput; errors: FieldError[] }>
  cast(values: unknown): TInput
  describe(path?: string): { required: boolean; exists: boolean }
}

const isObject = (obj: unknown): obj is Record<string, unknown> =>
  obj !== null && typeof obj === 'object' && !Array.isArray(obj)

function isIndex(value: string): boolean {
  return Number(value) >= 0
}

/** vee-validate 路径语法:a.0.b → a[0].b(数组下标中括号化) */
function normalizeFormPath(path: string): string {
  const pathArr = path.split('.')
  if (!pathArr.length) return ''
  let fullPath = String(pathArr[0])
  for (let i = 1; i < pathArr.length; i++) {
    fullPath += isIndex(pathArr[i]) ? `[${pathArr[i]}]` : `.${pathArr[i]}`
  }
  return fullPath
}

function merge(target: Record<string, unknown>, source: Record<string, unknown>) {
  for (const key of Object.keys(source)) {
    if (isObject(source[key]) && isObject(target[key])) {
      target[key] = merge({ ...(target[key] as Record<string, unknown>) }, source[key] as Record<string, unknown>)
      continue
    }
    target[key] = source[key]
  }
  return target
}

function processIssues(issues: IssueLike[], errors: Record<string, FieldError>): void {
  for (const issue of issues) {
    const path = normalizeFormPath(issue.path.map(String).join('.'))
    if (issue.code === 'invalid_union') {
      // 子 issue 路径拼上 union 自身路径,才能挂到 vee 字段上
      processIssues((issue.errors ?? []).flat().map((sub) => ({
        ...sub, path: [...issue.path, ...sub.path],
      })), errors)
      if (!path) continue
    }
    if (!errors[path]) errors[path] = { errors: [], path }
    errors[path].errors.push(issue.message)
  }
}

/** zod 不支持不校验的 cast,失败时退默认值合并(与官方桥同策) */
function getDefaults(schema: ZodType): Record<string, unknown> | undefined {
  if (!(schema instanceof ZodObject)) return undefined
  return Object.fromEntries(Object.entries(schema.shape).map(([key, value]) => {
    if (value instanceof ZodDefault) {
      // zod4 的 def.defaultValue 是值本身(工厂形态 .default(() => …) 也是
      // getter 每次取新值),不是 zod3 的 _def.defaultValue() 函数
      return [key, (value as ZodDefault<ZodType>).def.defaultValue]
    }
    if (value instanceof ZodObject) return [key, getDefaults(value)]
    return [key, undefined]
  }))
}

function getSchemaForPath(path: string, schema: ZodType | null): ZodType | null {
  if (!(schema instanceof ZodObject)) return null
  const paths = (path || '').split(/\.|\[(\d+)\]/).filter(Boolean)
  let current: ZodType | null = schema
  for (const p of paths) {
    if (!current) return null
    if (current instanceof ZodObject) {
      current = (current.shape[p] as ZodType | undefined) ?? null
      continue
    }
    if (current instanceof ZodArray && isIndex(p)) {
      current = current.element as ZodType | undefined ?? null
    }
  }
  return current
}

export function toTypedSchema<TSchema extends ZodType>(
  zodSchema: TSchema,
  opts?: Parameters<ZodType['safeParseAsync']>[1],
): ZodTypedSchema<z.input<TSchema>, z.output<TSchema>> {
  return {
    __type: 'VVTypedSchema',
    async parse(value) {
      const result = await zodSchema.safeParseAsync(value, opts)
      if (result.success) {
        return { value: result.data as z.output<TSchema>, errors: [] }
      }
      const errors: Record<string, FieldError> = {}
      processIssues(result.error.issues as unknown as IssueLike[], errors)
      return { errors: Object.values(errors) }
    },
    cast(values) {
      try {
        return zodSchema.parse(values) as z.input<TSchema>
      } catch {
        const defaults = getDefaults(zodSchema)
        if (isObject(defaults) && isObject(values)) {
          return merge(defaults, values) as z.input<TSchema>
        }
        return values as z.input<TSchema>
      }
    },
    describe(path) {
      try {
        if (!path) {
          return { required: !zodSchema.isOptional(), exists: true }
        }
        const description = getSchemaForPath(path, zodSchema)
        if (!description) return { required: false, exists: false }
        return { required: !description.isOptional(), exists: true }
      } catch {
        return { required: false, exists: false }
      }
    },
  }
}
