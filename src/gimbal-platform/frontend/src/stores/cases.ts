/**
 * cases.ts — Pinia store for case-library state.
 *
 * Three buckets the spec cares about:
 *   - publicLibrary: all public cases (cached 5s)
 *   - mineUploads:   cases owned by the current user (visibility=private, owner=me)
 *   - mineFavorites: cases the user has favorited (favorited_by_me=true,
 *                    regardless of visibility)
 *
 * Plus fetchOne(id) and toggleFavorite(id) for single-item flows.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as casesApi from '@/api/cases'
import type { CaseSummary, CaseDetailOut, CaseShow, CopyOut } from '@/api/cases'
import { useAuthStore } from '@/stores/auth'
import { useSetStatus } from '@/utils/useSetStatus'

const PUBLIC_CACHE_MS = 5_000

export const useCasesStore = defineStore('cases', () => {
  const publicLibrary = ref<CaseSummary[]>([])
  const mineUploads = ref<CaseSummary[]>([])
  const mineFavorites = ref<CaseSummary[]>([])
  const lastFetchedPublic = ref<number>(0)
  const { fetchStatus, lastError, setStatus } = useSetStatus()

  async function fetchPublic(force = false): Promise<CaseSummary[]> {
    const now = Date.now()
    if (
      !force &&
      publicLibrary.value.length > 0 &&
      now - lastFetchedPublic.value < PUBLIC_CACHE_MS
    ) {
      return publicLibrary.value
    }
    setStatus('loading')
    try {
      const out = await casesApi.publicList()
      publicLibrary.value = out.items
      lastFetchedPublic.value = Date.now()
      setStatus('idle')
      return out.items
    } catch (e) {
      setStatus('error', e instanceof Error ? e.message : 'fetch failed')
      throw e
    }
  }

  async function fetchMine(): Promise<CaseSummary[]> {
    const auth = useAuthStore()
    // 防御：刷新后 currentUser 可能是 null（只恢复了 token）。这里 lazy 拉一次，
    // 否则 mineUploads 的 owner_id === me 过滤会因为 me === undefined 而丢光。
    if (auth.accessToken && !auth.currentUser) {
      try {
        await auth.fetchMe()
      } catch {
        // 401 由 http 拦截器处理，这里吞掉
      }
    }
    setStatus('loading')
    try {
      const out = await casesApi.mine()
      // /mine returns: public (favorited or not) + private (owned by me).
      // Split by visibility/owner for the two tabs.
      // 容忍 me 为空：后端已经把范围限定为「公共 + 当前用户的私有」，所以
      // 任意可见 private 都安全地视为「我的」（同时仍排除 owner_id 明确属于别人的）。
      const me = auth.currentUser?.id
      mineUploads.value = out.items.filter((s) => {
        if (s.visibility !== 'private') return false
        if (me == null) return true
        if (s.owner_id == null) return true
        return s.owner_id === me
      })
      mineFavorites.value = out.items.filter((s) => s.favorited_by_me)
      setStatus('idle')
      return out.items
    } catch (e) {
      setStatus('error', e instanceof Error ? e.message : 'fetch failed')
      throw e
    }
  }

  async function fetchOne(caseId: string): Promise<CaseDetailOut> {
    const out = await casesApi.get(caseId)
    // keep summary in publicLibrary up-to-date
    const idx = publicLibrary.value.findIndex((s) => s.case_id === caseId)
    if (idx >= 0) {
      publicLibrary.value[idx] = out.summary
    }
    return out
  }

  async function toggleFavorite(caseId: string): Promise<boolean> {
    const inLib = publicLibrary.value.find((s) => s.case_id === caseId)
    const inUploads = mineUploads.value.find((s) => s.case_id === caseId)
    const inFavorites = mineFavorites.value.find((s) => s.case_id === caseId)
    const summary = inLib ?? inUploads ?? inFavorites
    const wasFav = Boolean(summary?.favorited_by_me || inFavorites)

    if (wasFav) {
      await casesApi.unfavorite(caseId)
      if (inLib) inLib.favorited_by_me = false
      if (inUploads) inUploads.favorited_by_me = false
      mineFavorites.value = mineFavorites.value.filter(
        (s) => s.case_id !== caseId,
      )
      return false
    }

    await casesApi.favorite(caseId)
    if (inLib) inLib.favorited_by_me = true
    if (inUploads) inUploads.favorited_by_me = true
    if (summary && !inFavorites) {
      mineFavorites.value.push({ ...summary, favorited_by_me: true })
    }
    return true
  }

  async function copyCase(caseId: string, newName?: string): Promise<CopyOut> {
    const out = await casesApi.copy(caseId, { new_name: newName })
    const inLib = publicLibrary.value.find((s) => s.case_id === caseId)
    if (inLib) inLib.copied_by_me = true
    return out
  }

  async function removeCase(caseId: string): Promise<void> {
    await casesApi.remove(caseId)
    // Remove from every local bucket so the UI immediately drops the row.
    mineUploads.value = mineUploads.value.filter((s) => s.case_id !== caseId)
    mineFavorites.value = mineFavorites.value.filter((s) => s.case_id !== caseId)
    publicLibrary.value = publicLibrary.value.filter((s) => s.case_id !== caseId)
  }

  async function publishCase(caseId: string): Promise<CaseSummary> {
    const out = await casesApi.publish(caseId)
    // Drop from private lists (file moved out of data/users/<id>/) and
    // let the next fetchPublic() catch the new public row.
    mineUploads.value = mineUploads.value.filter((s) => s.case_id !== caseId)
    return out
  }

  async function renameCase(
    caseId: string,
    newCaseId: string,
  ): Promise<CaseSummary> {
    try {
      const out = await casesApi.rename(caseId, newCaseId)
      // Replace old case_id with the new one across every local bucket so
      // the UI doesn't keep pointing at the now-orphaned old stem.
      const swap = (s: CaseSummary) =>
        s.case_id === caseId ? { ...s, case_id: out.case_id } : s
      mineUploads.value = mineUploads.value.map(swap)
      mineFavorites.value = mineFavorites.value.map(swap)
      publicLibrary.value = publicLibrary.value.map(swap)
      // Drop cached show data for the old case_id (the new one won't
      // share the cache key — the case_id changes via rename).
      delete showCache.value[caseId]
      delete showLoading.value[caseId]
      delete showError.value[caseId]
      setStatus('idle')
      return out
    } catch (e) {
      // Surface the real server message (FastAPI's ``detail``) instead of
      // letting the view fall back to a generic toast.
      setStatus('error', e instanceof Error ? e.message : 'rename failed')
      throw e
    }
  }

  // ── gimbal run show cache ─────────────────────────────────
  // Per-caseId cache for ``getShow()``.  The step picker is opened
  // repeatedly from the same ExecutionDrawer; caching avoids a fresh
  // subprocess per open.  ``removeCase`` / ``renameCase`` bust entries
  // (above).  ``force=true`` re-fetches (used after a file upload that
  // changes the on-disk yaml).
  const showCache = ref<Record<string, CaseShow>>({})
  const showLoading = ref<Record<string, boolean>>({})
  const showError = ref<Record<string, string>>({})

  async function fetchShow(
    caseId: string,
    force = false,
  ): Promise<CaseShow> {
    if (!force && showCache.value[caseId]) {
      return showCache.value[caseId]
    }
    showLoading.value[caseId] = true
    showError.value[caseId] = ''
    try {
      const out = await casesApi.getShow(caseId)
      showCache.value[caseId] = out
      return out
    } catch (e) {
      showError.value[caseId] =
        e instanceof Error ? e.message : 'show fetch failed'
      throw e
    } finally {
      showLoading.value[caseId] = false
    }
  }

  return {
    publicLibrary,
    mineUploads,
    mineFavorites,
    fetchStatus,
    lastError,
    fetchPublic,
    fetchMine,
    fetchOne,
    toggleFavorite,
    copyCase,
    removeCase,
    publishCase,
    renameCase,
    // show (gimbal run show) API
    showCache,
    showLoading,
    showError,
    fetchShow,
  }
})
