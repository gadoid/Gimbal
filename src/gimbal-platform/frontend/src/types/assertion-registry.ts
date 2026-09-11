// types/assertion-registry.ts
/** 断言管理注册表(spec v2 §3)— 平台侧偏离注入条目,场景级资产,
 *  住场景文档 payload.assertion_registry(与 orchestration 同级,引擎不感知)。 */

/** 溯源面:编排器标记自动带来;编辑器联动/展示用,执行不依赖 */
export interface AssertionAnchor {
  stepIndex: number
  source: 'body' | 'headers'
  /** jsonpath 风格,$. 前缀(实例路径,数组带 [i]) */
  jsonpath: string
  varName?: string
}

/** 值偏离面:物化 = 基线 vars 覆写 */
export interface AssertionInject {
  varName: string
  value: unknown
}

/** 期望偏离面:override 覆写既有断言(匹配键 = stepIndex+target)/ append 追加 */
export interface AssertPatch {
  stepIndex: number
  target: string
  operator: string
  expected: unknown
  mode: 'override' | 'append'
}

export interface AssertionEntry {
  id: string
  name: string
  anchor?: AssertionAnchor
  injection: AssertionInject[]
  asserts: AssertPatch[]
}

export interface AssertionRegistry {
  entries: AssertionEntry[]
}
