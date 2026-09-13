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

/** 编排器标记载荷(Canvas → CaseComposer)。字段路径的**落点分侧**:
 *  * `inject` 请求侧 —— 路径是**注入地址**,落 `entry.path`;`value`
 *    预填字段当前字面量。
 *  * `assert` 响应侧 —— 路径是**断言目标**(scratch 域),落
 *    `entry.asserts[0].target`;该条目没有注入面,注入地址留空待用户补齐
 *    (补齐前判 path-unresolvable,整条在运行期 skip)。
 *
 *  判别式**必填**:两种形状的必填面不同,给缺省推断会让响应侧标记静默按
 *  请求侧落条目 —— 路径落错域,且运行期永不生效。 */
export type RegistryMark =
  | { kind: 'inject'; stepIndex: number; source: 'body'; jsonpath: string; value: unknown }
  | { kind: 'assert'; stepIndex: number; target: string }

/** v2 旧形状识别(spec v3 §7/§8):path 非对象(缺键 / null / 数组 / 标量)
 *  = 旧条目或残缺条目。判据与后端 `run_injection.entry_issues` 的
 *  `isinstance(path, dict)` 同构 —— sidecar 是服务端/手改 JSON,形状不可信,
 *  `path: null` 若当 v3 条目处理,`entry.path.stepIndex` 会在模板渲染里
 *  TypeError,整页白屏。非对象条目(条目本身是标量)一并按旧形状处理:
 *  列表/详情都走灰显分支,不再解引用。 */
export function isLegacyEntry(e: AssertionEntry | LegacyAssertionEntry): e is LegacyAssertionEntry {
  const p = (e as { path?: unknown } | null | undefined)?.path
  return typeof p !== 'object' || p === null || Array.isArray(p)
}
