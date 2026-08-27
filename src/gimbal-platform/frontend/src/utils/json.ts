/** json.ts — tolerant JSON.parse (converged from 4 per-component copies). */

/** Parse ``s`` as JSON; return ``fallback`` on empty input or parse error. */
export function parseJson<T>(s: string, fallback: T): T {
  if (!s || !s.trim()) return fallback
  try {
    return JSON.parse(s) as T
  } catch {
    return fallback
  }
}
