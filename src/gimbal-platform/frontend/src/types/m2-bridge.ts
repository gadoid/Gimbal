/**
 * types/m2-bridge.ts — M2 生成物到前端 View 命名的桥接层。
 *
 * m2.ts 的类型名直接来自 JSON Schema（Meta、Step、Call 等）。本模块
 * 为仍消费 View 命名的存量代码提供过渡;新代码应直接使用
 * `@/types/m2` 的原始类型。
 *
 * 桥接策略：类型别名（`type MetaView = Meta`），不是字段重映射——
 * m2.ts 的 JSON Schema 由 plate Python 模型（camelCase alias）生成，
 * 字段名天然一致;平台旁挂扩展（如 ConfigView.var_locks）在消费方
 * 以交叉类型处理，不在桥接层膨胀。
 */
export type {
  Meta, Config, Step, Call, Request, Extract, Assign, Assertion,
  RetryPolicy, UserCredential, Setup, Teardown, RunOptions, DebugSpec,
  Mock, File as ResourceFile, ReportDefinition, SubscribeRule, LogSelector,
  SuiteGraph, UnitDecl, Control, CheckSelector, CheckDecl, GateDecl,
  NamedParams, PlanPolicy, AssertOperator,
  Scenario, TimeoutPolicy, RecordPolicy,
} from '@/types/m2'

// View 命名的桥接别名（deprecated——新代码直接用 m2.ts 原名）
import type {
  Meta, Config, Step, Call, Request, Extract, Assign, Assertion,
  RetryPolicy, UserCredential, TimeoutPolicy, RecordPolicy,
  Scenario, Mock, File,
} from '@/types/m2'

/** 工具:把 T 的指定键从可选变为必填(平台写入时保证这些字段) */
type WithRequired<T, K extends keyof T> = T & Required<Pick<T, K>>

/** @deprecated use Meta from '@/types/m2'(平台采集面保证 tags/system 在场) */
export type MetaView = WithRequired<Meta, 'system' | 'tags'>
/** @deprecated use Config from '@/types/m2'(平台旁挂 var_locks 用交叉类型) */
export type ConfigView = Omit<WithRequired<Config,
  'services' | 'users' | 'timePolicy' | 'retry' | 'vars'>,
  'setup' | 'teardown' | 'users' | 'timePolicy'> & {
    setup: unknown[]; teardown: unknown[]; var_locks?: string[];
    users: Record<string, UserAuthView>;
    timePolicy: TimePolicyView;
  }
/** @deprecated use Step from '@/types/m2' */
export type StepView = Omit<Step, 'call' | 'strategy'> & {
  call: CallView
  strategy: StrategyView[]
}
/** @deprecated use Call from '@/types/m2'(旧消费方依赖开放索引) */
export type CallView = Call & { [key: string]: unknown }
/** @deprecated use Request from '@/types/m2'(旧版 body=unknown) */
export type RequestView = Omit<Request, 'body'> & { body: unknown }
/** @deprecated use Extract from '@/types/m2' */
export type ExtractView = Extract
/** @deprecated use Assign from '@/types/m2' */
export type AssignView = Assign
/** @deprecated use Assertion from '@/types/m2' */
export type AssertionView = Assertion
/** @deprecated use (Extract | Assign | Assertion) from '@/types/m2' */
export type StrategyView = Extract | Assign | Assertion
/** @deprecated use RetryPolicy from '@/types/m2' */
export type RetryPolicyView = WithRequired<RetryPolicy, 'maxAttempts' | 'backoffSeconds' | 'retryOn'>
/** @deprecated use UserCredential from '@/types/m2'(expires_in 平台侧无 null) */
export type UserAuthView = Omit<UserCredential, 'expires_in'> & { expires_in?: number }
/** @deprecated use (TimeoutPolicy | RecordPolicy) from '@/types/m2' */
export type TimePolicyView = TimeoutPolicy | RecordPolicy
/** @deprecated use Scenario from '@/types/m2'(resource 平台侧=ResourceView 联合) */
export type ScenarioView = Omit<WithRequired<Scenario, 'kind'>, 'resource' | 'config' | 'meta'> & {
  resource: Record<string, ResourceView>
  config: ConfigView
  meta: MetaView
}
/** @deprecated use Mock from '@/types/m2' */
export type MockView = WithRequired<Mock, 'kind' | 'name' | 'image' | 'config' | 'portMapping'>
/** @deprecated use File from '@/types/m2' */
export type FileView = WithRequired<File, 'kind' | 'name' | 'path'>
/** @deprecated use (Mock | File) from '@/types/m2' */
export type ResourceView = MockView | FileView
