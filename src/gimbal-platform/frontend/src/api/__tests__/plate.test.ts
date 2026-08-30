/**
 * plate.ts — Plate 直连查询层单测。
 *
 * 锁定三件事:
 * 1. 走 Vite /plate 代理的原生 fetch + auth store 的 Bearer token
 *    (axios baseURL=/api 会拼错路径,见 CaseComposerCatalog 先例)。
 * 2. plate snake_case 信封响应 → 前端 camelCase 视图类型的映射收敛。
 * 3. 空数据优雅降级(config/meta 无 seed → null;resource → 空集)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import {
  fetchPlateSystems,
  fetchSystemConfig,
  fetchSystemMeta,
  fetchSystemResources,
} from '@/api/plate'

function plateEnvelope(items: unknown[]) {
  return { ok: true, json: async () => ({ ok: true, dim: 'x', data: { items, total: items.length } }) }
}

describe('api/plate', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('fetchPlateSystems: 请求 /plate/api/system 并映射为 id 列表', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    fetchMock.mockResolvedValue(plateEnvelope([{ id: 'common' }, { id: 'fin' }]))

    const systems = await fetchPlateSystems()

    expect(fetchMock).toHaveBeenCalledWith('/plate/api/system', {
      headers: { Authorization: 'Bearer tok' },
    })
    expect(systems).toEqual(['common', 'fin'])
  })

  it('无 token 时不带 Authorization 头', async () => {
    fetchMock.mockResolvedValue(plateEnvelope([]))
    await fetchPlateSystems()
    expect(fetchMock).toHaveBeenCalledWith('/plate/api/system', { headers: {} })
  })

  it('fetchSystemConfig: snake_case → ConfigView 映射,空列表 → null', async () => {
    fetchMock.mockResolvedValue(plateEnvelope([{
      setup: [], teardown: [],
      services: { 'fin-service': 'https://x' },
      users: { tester_a: { username: 'a', token_type: 'Bearer' } },
      time_policy: { kind: 'record' },
      vars: { fin_base_url: 'https://x' },
    }]))

    const cfg = await fetchSystemConfig('fin')

    expect(fetchMock).toHaveBeenCalledWith(
      '/plate/api/systems/fin/config', expect.objectContaining({}),
    )
    expect(cfg).not.toBeNull()
    expect(cfg!.timePolicy).toEqual({ kind: 'record' })
    expect(cfg!.services['fin-service']).toBe('https://x')
    expect(cfg!.users.tester_a.token_type).toBe('Bearer')
    expect(cfg!.retry).toBeNull()

    fetchMock.mockResolvedValue(plateEnvelope([]))
    expect(await fetchSystemConfig('none')).toBeNull()
  })

  it('fetchSystemMeta: create_time/requirement_ref → camelCase', async () => {
    fetchMock.mockResolvedValue(plateEnvelope([{
      name: '', description: '', module: '', priority: 1,
      author: '', owner: '', tags: [],
      version: '1.0.0', create_time: '2026-01-01T00:00:00Z',
      expire: false, requirement_ref: [], system: ['common'],
    }]))

    const meta = await fetchSystemMeta('common')

    expect(fetchMock).toHaveBeenCalledWith(
      '/plate/api/systems/common/meta', expect.objectContaining({}),
    )
    expect(meta).not.toBeNull()
    expect(meta!.createTime).toBe('2026-01-01T00:00:00Z')
    expect(meta!.requirementRef).toEqual([])
    expect(meta!.version).toBe('1.0.0')
    expect(meta!.system).toEqual(['common'])
  })

  it('fetchSystemResources: 走 /full,按 name 建键,extra 展开进视图', async () => {
    fetchMock.mockResolvedValue(plateEnvelope([
      { name: 'fin.tidb_test', kind: 'mock', extra: { image: 'pingcap/tidb:v7.1', config: { region: 'test' }, portMapping: { 4000: 4000 } } },
      { name: 'fin.readme', kind: 'file', extra: { path: '/share/readme.md' } },
    ]))

    const resources = await fetchSystemResources('fin')

    expect(fetchMock).toHaveBeenCalledWith(
      '/plate/api/systems/fin/resource/full', expect.objectContaining({}),
    )
    expect(Object.keys(resources).sort()).toEqual(['fin.readme', 'fin.tidb_test'])
    expect(resources['fin.tidb_test']).toEqual({
      kind: 'mock', name: 'fin.tidb_test',
      image: 'pingcap/tidb:v7.1', config: { region: 'test' }, portMapping: { 4000: 4000 },
    })
    expect(resources['fin.readme']).toEqual({ kind: 'file', name: 'fin.readme', path: '/share/readme.md' })
  })

  it('fetchSystemResources: 未知 kind (mock_ref 等) 跳过,空 extra 给默认值', async () => {
    fetchMock.mockResolvedValue(plateEnvelope([
      { name: 'x.ref', kind: 'mock_ref', extra: {} },
      { name: 'y.mock', kind: 'mock', extra: {} },
    ]))

    const resources = await fetchSystemResources('fin')

    expect(Object.keys(resources)).toEqual(['y.mock'])
    expect(resources['y.mock']).toEqual({
      kind: 'mock', name: 'y.mock', image: '', config: {}, portMapping: {},
    })
  })
})
