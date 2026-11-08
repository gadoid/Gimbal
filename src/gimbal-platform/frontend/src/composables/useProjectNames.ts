/**
 * useProjectNames — M2a S7.1:projectId → 项目名映射(列表/详情页
 * 「所属项目」徽标)。模块级单次拉取(公共项目 + 我所在的;他人项目
 * 不可见,徽标回落「项目 #id」),失败静默空表。
 */
import { ref } from 'vue'
import { listProjects } from '@/api/projects'

const names = ref(new Map<number, string>())
let loaded = false
let inflight: Promise<void> | null = null

async function fetchOnce(): Promise<void> {
  if (loaded) return
  if (!inflight) {
    inflight = (async () => {
      try {
        names.value = new Map((await listProjects()).map((p) => [p.id, p.name]))
        loaded = true
      } catch { /* 静默:徽标回落 #id */ }
      finally { inflight = null }
    })()
  }
  await inflight
}

export function useProjectNames() {
  void fetchOnce()
  return {
    names,
    nameOf: (id: number | null | undefined): string | null =>
      id == null ? null : (names.value.get(id) ?? `项目 #${id}`),
  }
}
