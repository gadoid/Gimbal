/** M2a S1.8:项目区 API 层单测(路径/方法/载荷;http 走 axios mock)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import http from '@/api/http'
import {
  listProjects, createProject, addMember, patchMember, removeMember,
  transferMaintenance, platformizeTask,
} from '@/api/projects'

vi.mock('@/api/http', () => ({
  default: {
    get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
  },
}))
const mocked = vi.mocked(http, { partial: true }) as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

describe('api/projects', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('listProjects → GET /projects', async () => {
    mocked.get.mockResolvedValue({ data: [] })
    await listProjects()
    expect(mocked.get).toHaveBeenCalledWith('/projects')
  })

  it('createProject 携带 firstAdminUserId', async () => {
    mocked.post.mockResolvedValue({ data: { id: 1 } })
    await createProject({ name: 'p', firstAdminUserId: 3 })
    expect(mocked.post).toHaveBeenCalledWith('/projects', {
      name: 'p', firstAdminUserId: 3 })
  })

  it('成员面:add/patch/remove 路径与载荷', async () => {
    mocked.post.mockResolvedValue({ data: {} })
    mocked.patch.mockResolvedValue({ data: {} })
    mocked.delete.mockResolvedValue({})
    await addMember(7, { userId: 5, role: 'admin' })
    expect(mocked.post).toHaveBeenCalledWith('/projects/7/members',
      { userId: 5, role: 'admin' })
    await patchMember(7, 5, 'member')
    expect(mocked.patch).toHaveBeenCalledWith(
      '/projects/7/members/5', { role: 'member' })
    await removeMember(7, 5)
    expect(mocked.delete).toHaveBeenCalledWith('/projects/7/members/5')
  })

  it('transferMaintenance / platformizeTask(S1-e / D9)', async () => {
    mocked.post.mockResolvedValue({ data: { transferredTo: 9 } })
    await transferMaintenance('scenarios', 'sc-x-public', 9)
    expect(mocked.post).toHaveBeenCalledWith(
      '/scenarios/sc-x-public/transfer', { toUserId: 9 })
    await platformizeTask(12)
    expect(mocked.post).toHaveBeenCalledWith(
      '/integration/tasks/12/platformize')
  })
})
