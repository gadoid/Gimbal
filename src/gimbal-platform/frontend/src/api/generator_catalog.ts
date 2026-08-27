/** generator_catalog.ts — /api/generator-catalog(plate generators dim 代理,只读)。 */
import http from './http'
import type { GeneratorKindDetailView, GeneratorKindView } from '@/types/constants'

export function listGeneratorKinds() {
  return http.get<GeneratorKindView[]>('/generator-catalog').then((r) => r.data)
}

export function getGeneratorKindFull(kind: string) {
  return http
    .get<GeneratorKindDetailView>(`/generator-catalog/${kind}/full`)
    .then((r) => r.data)
}
