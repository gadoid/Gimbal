/**
 * types/m2-bridge.ts — M2 生成物到前端 View 命名的桥接层。
 *
 * m2.ts 的类型名直接来自 JSON Schema（Meta、Step、Call 等，snake_case
 * 字段），本模块为仍消费 camelCase View 类型的存量代码提供过渡：
 * 新代码应直接使用 `@/types/m2` 的原始类型。
 *
 * 桥接策略：类型别名（`type MetaView = Meta`），不是字段重映射——
 * snake_case → camelCase 的字段映射在 api/plate.ts 的响应解析层完成。
 */
export type {
  Meta, Config, Step, Call, Request, Extract, Assign, Assertion,
  RetryPolicy, UserCredential, Setup, Teardown, RunOptions, DebugSpec,
  Mock, File as ResourceFile, ReportDefinition, SubscribeRule, LogSelector,
  SuiteGraph, UnitDecl, Control, CheckSelector, CheckDecl, GateDecl,
  NamedParams, PlanPolicy, AssertOperator,
} from '@/types/m2'

// View 命名的桥接别名（deprecated——新代码直接用 m2.ts 原名）
import type {
  Meta, Config, Step, Call, Request, Extract, Assign, Assertion,
  RetryPolicy, UserCredential, TimeoutPolicy, RecordPolicy,
} from '@/types/m2'

/** @deprecated use Meta from '@/types/m2' */
export type MetaView = Meta
/** @deprecated use Config from '@/types/m2' */
export type ConfigView = Config
/** @deprecated use Step from '@/types/m2' */
export type StepView = Step
/** @deprecated use Call from '@/types/m2' */
export type CallView = Call
/** @deprecated use Request from '@/types/m2' */
export type RequestView = Request
/** @deprecated use Extract from '@/types/m2' */
export type ExtractView = Extract
/** @deprecated use Assign from '@/types/m2' */
export type AssignView = Assign
/** @deprecated use Assertion from '@/types/m2' */
export type AssertionView = Assertion
/** @deprecated use (Extract | Assign | Assertion) from '@/types/m2' */
export type StrategyView = Extract | Assign | Assertion
/** @deprecated use RetryPolicy from '@/types/m2' */
export type RetryPolicyView = RetryPolicy
/** @deprecated use UserCredential from '@/types/m2' */
export type UserAuthView = UserCredential
/** @deprecated use (TimeoutPolicy | RecordPolicy) from '@/types/m2' */
export type TimePolicyView = TimeoutPolicy | RecordPolicy
