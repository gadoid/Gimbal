/**
 * editMode.ts — Pinia store for the case-config edit session.
 *
 * Tracks:
 * - isEditMode: read-only <-> edit toggle (top-bar button)
 * - original: deep snapshot of the case payload when entering edit mode
 * - current:  live working copy the user mutates
 * - dirty:    computed (deep-equal original vs current)
 * - saving:   flag for the PATCH call
 *
 * On save: PATCH /api/cases/{id} with current, then markClean() so
 * dirty becomes false.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a === null || b === null) return false
  if (typeof a !== typeof b) return false
  if (typeof a !== 'object') return false
  if (Array.isArray(a) !== Array.isArray(b)) return false
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false
    }
    return true
  }
  const ak = Object.keys(a as Record<string, unknown>)
  const bk = Object.keys(b as Record<string, unknown>)
  if (ak.length !== bk.length) return false
  for (const k of ak) {
    if (!deepEqual((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k])) {
      return false
    }
  }
  return true
}

export const useEditModeStore = defineStore('editMode', () => {
  const isEditMode = ref(false)
  const original = ref<Record<string, unknown> | null>(null)
  const current = ref<Record<string, unknown> | null>(null)
  const saving = ref(false)
  const lastError = ref('')

  const dirty = computed(() => {
    if (!original.value || !current.value) return false
    return !deepEqual(original.value, current.value)
  })

  function enterEdit(payload: Record<string, unknown>) {
    original.value = JSON.parse(JSON.stringify(payload))
    current.value = JSON.parse(JSON.stringify(payload))
    isEditMode.value = true
  }

  function cancelEdit() {
    isEditMode.value = false
    current.value = null
    original.value = null
  }

  function markClean(saved: Record<string, unknown>) {
    original.value = JSON.parse(JSON.stringify(saved))
    current.value = JSON.parse(JSON.stringify(saved))
  }

  function patchCurrent(updater: (p: Record<string, unknown>) => void) {
    if (!current.value) return
    // Deep clone to keep mutations out of original
    const next = JSON.parse(JSON.stringify(current.value))
    updater(next)
    current.value = next
  }

  return {
    isEditMode,
    original,
    current,
    saving,
    lastError,
    dirty,
    enterEdit,
    cancelEdit,
    markClean,
    patchCurrent,
  }
})