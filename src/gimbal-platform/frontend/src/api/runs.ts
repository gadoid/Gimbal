/**
 * api/runs.ts —— 运行读面 client(S7.3 起:生效预览)。
 *
 * 契约对齐后端 app/routers/runs.py POST /runs/preview(S5 落地):
 * 本次执行将生效的 地址/条目装载/carry 逐值带来源,不含明文凭证;
 * 读闸同预检(不可读场景 404,不泄露存在性)。环境随身份标签链解析
 * (§8.2:身份 > 项目默认 > 平台默认),与执行同源。
 */
import http from './http'

export interface PreviewRequest {
  scenarioId: string
  schemeId?: string
  /** 服务键 → {alias}(S6 后唯一形态;url/authAlias 后端 422) */
  serviceBindings?: Record<string, { alias: string }>
  /** authz M2a S8:凭证来源(同执行请求;'project' = 项目凭证池) */
  credentialSource?: 'personal' | 'project'
  /** 执行配置分层②:显式选定(缺省 = 默认链,默认配置占 env 位④/
   *  私有区 carry);与执行同链 */
  execConfigId?: number
}

/** 来源标签 → 中文(S7.3 生效预览展示;口径 = run_prepare.resolve_effective_config)。
 *  环境标签链(§8.2):身份 > 项目默认 > 平台默认;explicit/scheme/
 *  preference/exec_config* 只出现在历史快照回放面,原样透出仅作展示。 */
export const PREVIEW_SOURCE_LABELS: Record<string, string> = {
  authored: '场景声明',
  deployment: '服务注册',
  identity: '身份标签',
  project: '项目默认',
  default: '平台默认',
  explicit: '本次指定',
  scheme: '方案',
  preference: '我的偏好',
  exec_config: '执行配置',
  exec_config_default: '默认执行配置',
}

/** carry 来源形如 "{scope}:{scopeId}:base|alias|instance:{envId}"(scope
 * = project/user;scopeId 为公共项目 id 时即「全局层」);分层②的配置
 * 覆盖层另有 'exec_config' 一档;§8.9 实例档来源带环境坐标(系统×环境
 * 部署默认,压过服务档)。拆层名供展示。 */
export function carrySourceLabel(source: string): string {
  if (source === 'exec_config') return '执行配置覆盖'
  const m = /^(project|user):(\d+):(base|alias)$/.exec(source)
  if (m) {
    const scope = m[1] === 'project' ? '项目层' : '个人层'
    return m[3] === 'alias' ? `${scope}·别名` : scope
  }
  const mi = /^(project|user):(\d+):instance:(\d+)$/.exec(source)
  if (mi) {
    return `${mi[1] === 'project' ? '项目层' : '个人层'}·实例`
  }
  // FE-06(2026-11-20 审计):层默认值是两段式 `{scope}:{scopeId}`(后端
  // defaults_out 无档位后缀)—— 此前不匹配任何分支,来源列原样显示坐标串。
  const md = /^(project|user):(\d+)$/.exec(source)
  if (md) return md[1] === 'project' ? '项目层默认' : '个人层默认'
  return source
}

export interface PreviewEnv {
  environmentId: number | null
  environmentSource: string | null
}

export interface PreviewService {
  url: string
  source: string
  alias?: string
}

export interface PreviewAuth {
  bindingId: number
  system: string
  envId: number | null
  isDefault: boolean
  /** authz M2a S8:取用池('personal' | 'project') */
  source?: string
  /** 分层②:条目被执行配置绑定换用时标 'exec_config'(键 = 声明条目,
   *  取用行 = configuredSlot;缺省 = 别名声明槽) */
  slotSource?: string
  configuredSlot?: string
}

export interface PreviewCarryValue {
  value: unknown
  source: string
}

export interface EffectiveConfigPreview {
  env: PreviewEnv | null
  services: Record<string, PreviewService>
  auths: Record<string, PreviewAuth>
  missingAuths: string[]
  carry: Record<string, Record<string, PreviewCarryValue>>
  carryDefaults: Record<string, PreviewCarryValue>
}

export function previewEffectiveConfig(
  body: PreviewRequest,
): Promise<EffectiveConfigPreview> {
  return http.post<EffectiveConfigPreview>('/runs/preview', body)
    .then((r) => r.data)
}
