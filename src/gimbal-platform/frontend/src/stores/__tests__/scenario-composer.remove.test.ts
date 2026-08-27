/** removeDataSet:调 DELETE API 后按场景刷新列表。 */
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/scenario-composer'
import { useScenarioComposerStore } from '@/stores/scenario-composer'

beforeEach(() => setActivePinia(createPinia()))

it('removeDataSet 删后 refetch 该场景数据集', async () => {
  const del = vi.spyOn(api, 'deleteDataSet').mockResolvedValue(undefined)
  const list = vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  const store = useScenarioComposerStore()
  await store.removeDataSet('sc-a', 'ds-1')
  expect(del).toHaveBeenCalledWith('ds-1')
  expect(list).toHaveBeenCalledWith({ scenarioId: 'sc-a' })
})
