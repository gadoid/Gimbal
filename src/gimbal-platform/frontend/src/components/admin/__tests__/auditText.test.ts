// auditText.test.ts — 审计可读性三件套:动作标签 / 对象名称回落 / 详情模板。
import { describe, expect, it } from 'vitest'
import {
  AUDIT_ACTION_LABELS, auditActionLabel, auditResourceName, auditResourceText,
  describeAuditDetail,
} from '../auditText'
import type { AuditLogRow } from '@/api/admin'

function row(partial: Partial<AuditLogRow>): AuditLogRow {
  return {
    id: 1, actorId: 1, actorName: '管理员', action: '', resourceType: null,
    resourceId: null, detail: {}, createdAt: '2026-10-14T00:00:00Z',
    ...partial,
  }
}

describe('auditActionLabel', () => {
  it('后端 AUDIT_ACTIONS 13 键全部有中文标签', () => {
    const all = [
      'user.create', 'user.role_change', 'user.delete', 'user.reset_password',
      'announcement.publish', 'carry.write', 'adaptation.op.apply',
      'adaptation.batch.apply', 'adaptation.batch.rollback', 'alias.write',
      'external_endpoint.query_safe',
      'share.admin_revoke', 'suite.admin_unpublish',
    ]
    for (const k of all) {
      expect(AUDIT_ACTION_LABELS[k], k).toBeTruthy()
      expect(auditActionLabel(k)).not.toBe(k)
    }
  })

  it('I4 只读标记:标记/撤销外部接口人话(名称快照优先)', () => {
    expect(describeAuditDetail(row({
      action: 'external_endpoint.query_safe',
      resourceType: 'external_endpoint', resourceId: '9',
      detail: { resource_name: 'jira-x.search', aliasName: 'jira-x',
                name: 'search', querySafe: true },
    }))).toContain('标记外部接口「jira-x.search」只读')
    expect(describeAuditDetail(row({
      action: 'external_endpoint.query_safe',
      resourceType: 'external_endpoint', resourceId: '9',
      detail: { aliasName: 'jira-x', name: 'search', querySafe: false },
    }))).toContain('撤销外部接口「jira-x.search」只读')
  })

  it('未知动作回落原键', () => {
    expect(auditActionLabel('x.unknown')).toBe('x.unknown')
  })
})

describe('auditResourceText', () => {
  it('resource_name 快照优先:类型「名」', () => {
    expect(auditResourceText(row({
      resourceType: 'user', resourceId: '12',
      detail: { resource_name: '张三', username: 'zhang' },
    }))).toBe('用户「张三」')
  })

  it('老记录回落类型专属字段(user→username)', () => {
    expect(auditResourceText(row({
      resourceType: 'user', resourceId: '12', detail: { username: 'zhang' },
    }))).toBe('用户「zhang」')
  })

  it('无任何名称回落 type:id 现状格式', () => {
    expect(auditResourceText(row({
      resourceType: 'user', resourceId: '12', detail: {},
    }))).toBe('user:12')
  })

  it('alias/carry 的 resource_id 本身是名称', () => {
    expect(auditResourceText(row({
      resourceType: 'alias', resourceId: 'my-alias', detail: { fn: 'create' },
    }))).toBe('别名「my-alias」')
    expect(auditResourceText(row({
      resourceType: 'carry', resourceId: 'defaults', detail: {},
    }))).toBe('carry 配置「defaults」')
  })

  it('无资源显示 —', () => {
    expect(auditResourceText(row({}))).toBe('—')
  })
})

describe('describeAuditDetail', () => {
  it('角色变更:从→到 完整句(用户的验收例)', () => {
    expect(describeAuditDetail(row({
      action: 'user.role_change', resourceType: 'user', resourceId: '12',
      detail: {
        username: '张三', changed: ['role'], role: 'admin', role_from: 'user',
        is_active: true, is_active_from: true,
      },
    }))).toBe('把「张三」的角色从 普通用户 改为 管理员')
  })

  it('角色变更:老记录没有 role_from 时不编造前值', () => {
    expect(describeAuditDetail(row({
      action: 'user.role_change', resourceType: 'user', resourceId: '12',
      detail: { username: '张三', changed: ['role'], role: 'admin' },
    }))).toBe('把「张三」的角色改为 管理员')
  })

  it('角色变更:多字段走列表句式', () => {
    expect(describeAuditDetail(row({
      action: 'user.role_change', resourceType: 'user', resourceId: '12',
      detail: {
        username: '张三', changed: ['display_name', 'is_active', 'role'],
        role: 'member', role_from: 'user',
        is_active: false, is_active_from: true,
      },
    }))).toBe('变更「张三」：角色从 普通用户 改为 成员；状态从 启用 改为 停用；修改显示名')
  })

  it('删号:处置方式 + 受让人 + 场景数', () => {
    expect(describeAuditDetail(row({
      action: 'user.delete', resourceType: 'user', resourceId: '9',
      detail: {
        username: '李四', disposal: 'transfer', transfer_to: 3,
        transfer_to_name: '王五', scenarios: 4,
      },
    }))).toBe('删除用户「李四」（资源转让他人，资源转给「王五」，涉及 4 个场景）')
  })

  it('公告 / 回滚 / 别名 / 下架', () => {
    expect(describeAuditDetail(row({
      action: 'announcement.publish',
      detail: { title: '停机维护', delivered: 7, resource_name: '停机维护' },
    }))).toBe('发布公告《停机维护》，送达 7 人')
    expect(describeAuditDetail(row({
      action: 'adaptation.batch.rollback', resourceType: 'adaptation_batch',
      resourceId: 'b-1', detail: { skipped: 2 },
    }))).toBe('回滚适配批次 b-1，跳过 2 条')
    expect(describeAuditDetail(row({
      action: 'alias.write', resourceType: 'alias', resourceId: 'fin-alias',
      detail: { fn: 'delete' },
    }))).toBe('删除别名「fin-alias」')
    expect(describeAuditDetail(row({
      action: 'suite.admin_unpublish', resourceType: 'suite', resourceId: '5',
      detail: { name: '回归套件', resource_name: '回归套件' },
    }))).toBe('下架公共套件「回归套件」')
  })

  it('认不出的动作回落 k=v 紧凑串(resource_name 不重复出镜)', () => {
    expect(describeAuditDetail(row({
      action: 'future.action', detail: { resource_name: 'X', n: 3 },
    }))).toBe('n=3')
    expect(describeAuditDetail(row({
      action: 'future.action', detail: {},
    }))).toBe('—')
  })
})

describe('auditResourceName', () => {
  it('空白串不算名称', () => {
    expect(auditResourceName(row({
      resourceType: 'user', resourceId: '1', detail: { resource_name: '  ' },
    }))).toBeNull()
  })
})
