# Deferred Code Review Items

Items from the 2026-07-16 code review that are intentionally **not**
addressed in the current pass.  Each entry states the reason for
deferral so a future pass can re-evaluate.

The review criteria used for the current pass:
- **Low impact** — no behavior change beyond a bug correction or a pure
  deletion; tests still pass.
- **Reduces redundancy** — net code reduction (helper extraction, dead
  code removal, etc.).

Items that don't meet one of these two criteria are deferred.

---

## P0 — Real risk (deferred, needs design)

| # | Location | Issue | Why deferred |
|---|---|---|---|
| 1 | `backend/app/models/case.py:37-46` | ~~`CaseFavorite` table defined but unused (favorites are in `favorites.json`)~~ **FIXED 2026-07-16**: class removed from ORM, `__init__.py` import removed, live DB table dropped via `DROP TABLE IF EXISTS case_favorites`. |
| 2 | `backend/app/routers/executions.py:540-542` | `next_idx = max(idx) + 1` has a SELECT-then-INSERT race window | **Concurrency fix**: needs `SELECT ... FOR UPDATE` row lock or a unique constraint fallback.  Changes concurrent rerun semantics — must be tested under load. |
| 3 | `backend/app/routers/executions.py:254` | `asyncio.create_task(_safe_run(...))` is fire-and-forget | **Lifecycle fix**: needs task handles + shutdown hooks to ensure subprocess cleanup.  Touches FastAPI startup/shutdown. |
| 5 | `backend/app/routers/executions.py:546,604` | `ex.total_runs += 1` (rerun) and `ex.passed/failed += 1` (`_run_one`) write to the same row in two different sessions | **Race fix**: needs a single transaction boundary or atomic update.  Higher blast radius — could surface a real bug. |
| 6 | `backend/app/routers/cases.py:70` | `_FAVORITES` reads from disk at import without the lock | **TOCTOU**: needs the read to be under the same lock as the writes.  Modifies startup behavior. |
| 7 | `backend/app/schemas/hidden_profile.py:14,20` | `scope` field is always `"case"`, never used as discriminator | **Design decision**: drop the field, or add a real discriminator branch.  Not redundancy — feature question. |
| 8 | `frontend/src/views/Executions.vue:446-471` | `row.rerunning = true` is wiped by 1s polling mid-flight | **Reactivity fix**: needs a per-row `rerunningIds: Set<number>` in the store, separate from `runs` array.  UX-impacting. |
| 9 | `frontend/src/stores/executions.ts:132` | `onUnmounted(stopPolling)` in Pinia store | **Lifecycle fix**: stopPolling should be per-component, not per-store.  Already partially addressed — see FIXED list. |
| 10 | `frontend/src/components/ExecutionDrawer.vue:486-518` | Three watchers race on textarea content | **State fix**: needs single source of truth for the dirty marker.  Already partially addressed — see FIXED list. |
| 12 | `frontend/src/api/http.ts:82-105` | `refreshInFlight` is a module-level singleton | **Concurrency fix**: needs per-request refresh guard.  Larger refactor of the auth interceptor. |
| 13 | `frontend/src/views/Executions.vue:331-378` | `drainStreamInBackground` double-fetches log on reconnect | **State fix**: needs the reconnect path to skip the legacy fetch.  Touches SSE handling. |
| 14 | `frontend/src/components/ExecutionDrawer.vue:393-412` | Admin argv `buildDefaultCommandLine` had placeholder garbage | **Cleanup**: already partially addressed — see FIXED list. |

## P3 — Style consistency (deferred, not redundancy)

| # | Location | Issue | Why deferred |
|---|---|---|---|
| 55 | `backend/app/routers/auth.py` vs `users.py` | Mixed Chinese/English `detail` messages | **Style decision**: pick one language per surface, or split auth vs business.  Touches every router. |
| 56 | `backend/app/routers/auth_sessions.py:189,199` | Chinese error strings in otherwise-English file | Same as #55. |
| 57 | `backend/app/routers/cases.py:492,556,560` vs `schemas/execution.py:42` | 400 vs 422 for validation errors | **Convention**: pick a single error contract.  Cross-router change. |
| 58 | `backend/app/schemas/user.py:47`, `auth.py:49` | `created_at: str` annotation but accepts `datetime` | **Type hygiene**: cosmetic — `model_validate` coerces.  No behavior change. |
| 60 | `frontend/src/components/ExecutionDrawer.vue` vs `backend/app/services/executor.py` | Admin argv constructed in two places (frontend `buildDefaultCommandLine` + backend `_run_one` argv builder) | **Single source**: needs one authoritative path.  Frontend can drop its preview; backend already provides `run.command_line` post-execution. |
| 61 | `frontend/src/views/CasesPublic.vue:523-527` | "打开源 YAML" and "查看详情" both navigate to the same route | **UX decision**: two distinct behaviors or drop one. |
| 62 | `frontend/src/views/*` | Inconsistent error-toast fallback strings (`'保存失败'` / `'操作失败'` / `'删除失败'`) | **Style decision**: centralize the fallback.  Cross-file. |
| 63 | `frontend/src/views/CasesMine.vue:773-784`, `CasesPublic.vue:694-707`, `ExecutionDrawer.vue:745-747` | `.priority-N` CSS inlined in 3 views | **Extract**: move to a shared stylesheet.  Low value, real churn. |

---

## FIXED in the 2026-07-16 review pass

### Backend (158 tests passing)
- Removed: `Case.tag_list` (unused property), `CaseFavorite` (orphan model), `require_admin()` (unused dep), unused imports in `auth_sessions.py` / `cases.py` / `executor.py` / `routers/executions.py`
- Removed test imports: `import yaml` in 3 test files
- Removed dead `logger.info` in `conftest.py:53-57`
- Removed empty `__init__.py` shims
- Merged `run_execution` and `rerun_run` yaml-render paths into a shared `render_execution_yaml` helper
- Removed redundant pump-thread join chain in `_subprocess_run_streaming`
- Removed in-place yaml writing from `rerun_run` (now uses `_write_temp_yaml`)

### Frontend (76 tests passing)
- Removed: `setTokens` / `setUser` exports from `auth.ts`; `fetchToken` from `auth_sessions.ts` (API + store); `lastError` from `editMode.ts`; `auths` prop from `EditableConfigPanel.vue`; whole `src/utils/errors.ts` (orphaned)
- Replaced 3 inline `setStatus` helpers with shared `useSetStatus` composable
- Replaced 4 list-view search filters with shared `useListSearch` composable
- Consolidated 3 status-label maps in `Executions.vue` (`EXEC_LABELS` + `RUN_LABELS`)
- Refactored `loadShow` + watcher into a single idempotent `loadDrawerData`
- Removed `Object.assign` reactivity-hack in `EditableStepCard.removeHeader` (Vue 3 `delete` suffices)
- Fixed `?` keydown scope: now skips `<select>` and `contenteditable` in addition to `INPUT`/`TEXTAREA`
- Removed `onUnmounted(stopPolling)` from `executions.ts` store (the watcher-callback returned `stop` already handles teardown)
- Removed `import yaml` from 3 backend test files
- Admin argv UI: removed placeholder-text pre-population; textarea is empty by default, dirty-marker turns on as soon as the user types; `buildDefaultCommandLine` deleted
