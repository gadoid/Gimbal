// types/assertion-registry.ts
/** 断言管理注册表(spec v3 §2)— 平台侧偏离注入条目,场景级资产,
 *  住场景文档 payload.assertion_registry(与 orchestration 同级,引擎不感知)。 */

/** 定位面:锁定到该元素的地址。jsonpath 根 = 该步请求 body */
export interface EntryPath {
  stepIndex: number
  source: 'body'
  /** jsonpath 风格,$. 前缀(实例路径,数组带 [i]) */
  jsonpath: string
}

/** 期望偏离面:override 覆写既有断言(匹配键 = stepIndex+target)/ append 追加 */
export interface AssertPatch {
  stepIndex: number
  target: string
  operator: string
  expected: unknown
  mode: 'override' | 'append'
}

/** v3 条目三元组:定位 path + 注入值 + 期望配对(spec v3 §2) */
export interface AssertionEntry {
  id: string
  name: string
  path: EntryPath
  /** 注入面:替换该字段的值(字面量,原样覆写不 coerce;
   *  物化 = 引擎 Assign 直补 $.request_body,与 config.vars 零耦合) */
  value: unknown
  asserts: AssertPatch[]
}

/** v2 旧形状(anchor + injection)— 仅识别不编辑(spec v3 §8 灰显);
 *  保留原样不删,不可编辑、不可选中执行 */
export interface LegacyAssertionEntry {
  id: string
  name: string
  /** 判别键(spec v3 §8):v3 条目必有 path,旧条目禁止携带(never)。
   *  缺此键则 AssertionEntry 可赋给本类型 → isLegacyEntry 的否定分支
   *  收窄为 never,v-if="!isLegacyEntry(e)" 内访问 e.path 报 TS2339。 */
  path?: never
  anchor?: { stepIndex: number; source: 'body' | 'headers'; jsonpath: string; varName?: string }
  injection?: Array<{ varName: string; value: unknown }>
  asserts?: AssertPatch[]
}

/** 注册表容器:v3 条目与旧条目共存于同一 entries 数组(spec v3 §8) */
export interface AssertionRegistry {
  entries: Array<AssertionEntry | LegacyAssertionEntry>
}

/** v2 旧形状识别(spec v3 §7/§8):无 path 键 = 旧条目。 */
export function isLegacyEntry(e: AssertionEntry | LegacyAssertionEntry): e is LegacyAssertionEntry {
  return (e as AssertionEntry).path === undefined
}
