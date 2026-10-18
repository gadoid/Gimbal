// auditText.ts — 审计面板可读文本(2026-10-14 可读性收口):
// * 动作:AUDIT_ACTIONS 12 键的中文标签表(unknown 回落原键);
// * 对象:resource_name 快照优先(后端写审计时随 detail 落库,资源删了
//   仍可读),老记录按类型回落 detail 里的名称字段,再回落 type:id;
// * 详情:按动作渲染中文模板,原始 JSON 由组件收进展开区。
import type { AuditLogRow } from '@/api/admin'

/** 审计动作中文标签;键集 = 后端 services/audit.py AUDIT_ACTIONS。 */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  'user.create': '新建用户',
  'user.role_change': '人事变更',
  'user.delete': '删除用户',
  'user.reset_password': '重置密码',
  'announcement.publish': '发布公告',
  'carry.write': 'carry 写入',
  'adaptation.op.apply': '应用适配单',
  'adaptation.batch.apply': '应用适配批次',
  'adaptation.batch.rollback': '回滚适配批次',
  'alias.write': '别名变更',
  // I4(集成线 v2 §3.2):外部目录只读标记 admin 写
  'external_endpoint.query_safe': '只读标记变更(已退役:b3/C4 外部接口登记下线,历史审计只读)',
  'share.admin_revoke': '管理员撤销分享',
  'suite.admin_unpublish': '下架公共套件',
  // 词表外存量动作:suites fork 落审计但未登记进 AUDIT_ACTIONS
  'suite.owner_fork': '复制私有套件',
  'suite.public_fork': '复制公共套件',
}

export function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action
}

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  user: '用户',
  announcement: '公告',
  carry: 'carry 配置',
  alias: '别名',
  external_endpoint: '外部接口(已退役)',
  scenario: '场景',
  suite: '套件',
  adaptation_op: '适配单',
  adaptation_batch: '适配批次',
}

// resource_name 快照上线前的老记录:各类型 detail 里可当名称用的字段
const LEGACY_NAME_KEYS: Record<string, readonly string[]> = {
  user: ['username'],
  announcement: ['title'],
  suite: ['name'],
}

function asName(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : null
}

/** 对象列的名称解析:快照 → 老记录类型字段;无名称返回 null。 */
export function auditResourceName(row: AuditLogRow): string | null {
  const type = row.resourceType ?? ''
  let name = asName(row.detail?.resource_name)
  if (!name) {
    for (const k of LEGACY_NAME_KEYS[type] ?? []) {
      name = asName(row.detail?.[k])
      if (name) break
    }
  }
  // alias/carry 的 resource_id 本身就是别名/服务名,直接当名称
  if (!name && (type === 'alias' || type === 'carry')) {
    name = asName(row.resourceId)
  }
  return name
}

/** 对象列文本:有名称「类型「名」」,老记录回落 type:id(现状格式)。 */
export function auditResourceText(row: AuditLogRow): string {
  const type = row.resourceType ?? ''
  const typeLabel = RESOURCE_TYPE_LABELS[type] ?? type
  const name = auditResourceName(row)
  if (name) return `${typeLabel}「${name}」`
  if (type || row.resourceId) {
    return `${type}${type && row.resourceId ? ':' : ''}${row.resourceId ?? ''}`
  }
  return '—'
}

// ── 详情模板 ────────────────────────────────────────────────────────
const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  member: '成员',
  user: '普通用户',
}

const DISPOSAL_LABELS: Record<string, string> = {
  publicize: '资源转为公共',
  transfer: '资源转让他人',
  purge: '资源彻底清除',
}

const ALIAS_FN_LABELS: Record<string, string> = {
  create: '登记',
  patch: '修改',
  delete: '删除',
}

function s(v: unknown): string {
  return typeof v === 'string' && v ? v : ''
}

function roleLabel(v: unknown): string {
  return typeof v === 'string' ? (ROLE_LABELS[v] ?? v) : '未知'
}

function onOff(v: unknown): string {
  return v ? '启用' : '停用'
}

function num(v: unknown): string {
  return typeof v === 'number' ? String(v) : '0'
}

/** 详情列:按动作渲染中文一句话;认不出的动作回落 k=v 紧凑串。 */
export function describeAuditDetail(row: AuditLogRow): string {
  const d = row.detail ?? {}
  const rid = row.resourceId ?? ''
  switch (row.action) {
    case 'user.create':
      return `新建用户「${s(d.username) || rid}」，初始角色 ${roleLabel(d.role)}`
    case 'user.role_change': {
      const who = s(d.username) || rid
      const changed: unknown[] = Array.isArray(d.changed) ? d.changed : []
      const parts: string[] = []
      if (changed.includes('role')) {
        parts.push(d.role_from !== undefined
          ? `角色从 ${roleLabel(d.role_from)} 改为 ${roleLabel(d.role)}`
          : `角色改为 ${roleLabel(d.role)}`)
      }
      if (changed.includes('is_active')) {
        parts.push(d.is_active_from !== undefined
          ? `状态从 ${onOff(d.is_active_from)} 改为 ${onOff(d.is_active)}`
          : `状态${onOff(d.is_active)}`)
      }
      if (changed.includes('display_name')) parts.push('修改显示名')
      if (changed.includes('new_password')) parts.push('设置新密码')
      if (!parts.length) return `变更「${who}」的人事属性`
      if (parts.length === 1 && changed.includes('role')) {
        return `把「${who}」的${parts[0]}`
      }
      return `变更「${who}」：${parts.join('；')}`
    }
    case 'user.reset_password':
      return `${d.self ? '本人' : '管理员'}重置「${s(d.username) || rid}」的密码`
    case 'user.delete': {
      const who = s(d.username) || rid
      const disp = DISPOSAL_LABELS[s(d.disposal)] ?? s(d.disposal)
      const to = s(d.transfer_to_name)
      return `删除用户「${who}」（${disp}${to ? `，资源转给「${to}」` : ''}，涉及 ${num(d.scenarios)} 个场景）`
    }
    case 'announcement.publish':
      return `发布公告《${s(d.title) || '无标题'}》，送达 ${num(d.delivered)} 人`
    case 'carry.write':
      return s(d.service)
        ? `修改服务「${s(d.service)}」的 carry 绑定`
        : `修改 carry 默认配置（${(Array.isArray(d.keys) ? d.keys : []).join('、') || '无'}）`
    case 'adaptation.op.apply': {
      const t = s(d.op_type)
      return `应用适配单 #${rid}${t ? `（${t}）` : ''}，状态 ${s(d.status) || '未知'}`
    }
    case 'adaptation.batch.apply':
      return `应用适配批次 ${rid}`
    case 'adaptation.batch.rollback':
      return `回滚适配批次 ${rid}，跳过 ${num(d.skipped)} 条`
    case 'alias.write':
      return `${ALIAS_FN_LABELS[s(d.fn)] ?? '变更'}别名「${rid}」`
    case 'external_endpoint.query_safe': {
      const ep = auditResourceName(row) || `${s(d.aliasName)}.${s(d.name)}` || rid
      return `${d.querySafe ? '标记' : '撤销'}外部接口「${ep}」只读(query_safe)`
    }
    case 'share.admin_revoke':
      return d.granteeUserId != null
        ? `管理员撤销分享引用（被分享用户 #${String(d.granteeUserId)}）`
        : '管理员撤销分享引用'
    case 'suite.admin_unpublish':
      return `下架公共套件「${s(d.name) || s(d.resource_name) || rid}」`
    case 'suite.owner_fork':
    case 'suite.public_fork': {
      const from = s(d.resource_name) || `#${rid}`
      const copy = s(d.name) || (d.copyId != null ? `#${String(d.copyId)}` : '新副本')
      return `复制套件「${from}」→「${copy}」`
    }
    default: {
      const kv = Object.entries(d)
        .filter(([k]) => k !== 'resource_name')
        .map(([k, v]) => `${k}=${typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}`)
      return kv.join(' ') || '—'
    }
  }
}
