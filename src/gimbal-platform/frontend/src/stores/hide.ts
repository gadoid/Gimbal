/**
 * hide.ts — Pinia store for the "hidden spec fields" UI toggle.
 *
 * The YAML/JSON spec surfaces a long list of fields at L1 + L2 depths.
 * In spec-1 we hide a curated L3 set by default (boring/derived
 * headers + meta.requirementRef).  Users can toggle individual L1
 * paths on/off via the JSON-tree view.
 *
 * We use string equality on dot-paths like
 *   "api.headers[\"sec-ch-ua-platform\"]"
 * — not JSONPath.  Spec-1 surface is small enough that exact match is
 * sufficient and keeps the implementation trivial.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const L3_DEFAULTS: readonly string[] = [
  'api.headers["sec-ch-ua-platform"]',
  'api.headers["sec-ch-ua"]',
  'api.headers["sec-ch-ua-mobile"]',
  'api.headers["Sec-Fetch-Site"]',
  'api.headers["Sec-Fetch-Mode"]',
  'api.headers["Sec-Fetch-Dest"]',
  'meta.requirementRef',
]

export const useHideStore = defineStore('hide', () => {
  const hiddenPaths = ref<Set<string>>(new Set(L3_DEFAULTS))
  const showHidden = ref<boolean>(false)

  function isHidden(path: string): boolean {
    return hiddenPaths.value.has(path)
  }

  function toggleL1(path: string) {
    const next = new Set(hiddenPaths.value)
    if (next.has(path)) {
      next.delete(path)
    } else {
      next.add(path)
    }
    hiddenPaths.value = next
  }

  function reset() {
    hiddenPaths.value = new Set(L3_DEFAULTS)
    showHidden.value = false
  }

  function setPaths(paths: Iterable<string>) {
    hiddenPaths.value = new Set(paths)
  }

  function snapshot(): string[] {
    return Array.from(hiddenPaths.value)
  }

  const hiddenCount = computed(() => hiddenPaths.value.size)

  return {
    hiddenPaths,
    showHidden,
    hiddenCount,
    isHidden,
    toggleL1,
    reset,
    setPaths,
    snapshot,
  }
})
