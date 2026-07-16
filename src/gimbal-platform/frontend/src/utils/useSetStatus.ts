/**
 * useSetStatus — small composable used by the three list-view stores
 * (cases / users / auth_sessions).  Bundles `fetchStatus` + `lastError`
 * refs and a `setStatus(s, err?)` writer so each store stops inlining
 * the same 3-line helper.
 *
 * Usage:
 *   const { fetchStatus, lastError, setStatus } = useSetStatus()
 *   async function fetchAll() {
 *     setStatus('loading')
 *     try { ... ; setStatus('idle') }
 *     catch (e) { setStatus('error', e.message); throw e }
 *   }
 */
import { ref, type Ref } from 'vue'

export type FetchStatus = 'idle' | 'loading' | 'error'

export interface SetStatusApi {
  fetchStatus: Ref<FetchStatus>
  lastError: Ref<string>
  setStatus: (s: FetchStatus, err?: string) => void
}

export function useSetStatus(): SetStatusApi {
  const fetchStatus = ref<FetchStatus>('idle')
  const lastError = ref('')

  function setStatus(s: FetchStatus, err: string = '') {
    fetchStatus.value = s
    lastError.value = err
  }

  return { fetchStatus, lastError, setStatus }
}
