<!-- ServicesIndex.vue — 服务画像落地页:列 plate 目录服务,点进热力网格。
     数据源 = utils/catalog-services(共享缓存,与编排器同一次拉取);
     plate 不可达 → 错误态提示重试,不白屏。 -->
<template>
  <ListPage title="服务画像" width="wide" subtitle="选择服务进入热力网格">
    <div v-if="loading" class="loading-state mt-3.5">加载中…</div>

    <div
      v-else-if="error"
      class="mt-3.5 rounded-field border border-signal-line bg-signal-card p-4 text-sm"
      data-testid="services-error"
    >
      <p class="text-muted-foreground">{{ error }}</p>
      <button
        type="button"
        class="mt-2 text-caption font-medium text-[#2F6FED]"
        data-testid="services-retry"
        @click="load"
      >重试</button>
    </div>

    <div v-else class="mt-3.5 grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(220px,1fr))]">
      <button
        v-for="svc in services"
        :key="svc.name"
        type="button"
        :data-testid="`services-card-${svc.name}`"
        class="rounded-lg border border-[#E1E5EB] bg-white p-3.5 text-left transition-shadow hover:shadow-sm"
        @click="open(svc.name)"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="mono truncate text-small font-semibold">{{ svc.name }}</span>
          <span class="shrink-0 rounded bg-signal-canvas px-1.5 py-px text-micro text-muted-foreground">
            {{ svc.system }}
          </span>
        </div>
        <div class="mt-1.5 text-caption text-muted-foreground">{{ svc.endpointCount }} 个接口 · 进入热力网格 →</div>
      </button>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { loadCatalogEntries } from '@/utils/catalog-services'

const router = useRouter()

interface ServiceRow { name: string; system: string; endpointCount: number }

const loading = ref(true)
const error = ref('')
const services = ref<ServiceRow[]>([])

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const entries = await loadCatalogEntries()
    const byName = new Map<string, ServiceRow>()
    for (const e of entries) {
      const row = byName.get(e.service)
      if (row) row.endpointCount += 1
      else byName.set(e.service, { name: e.service, system: e.system, endpointCount: 1 })
    }
    services.value = [...byName.values()].sort((a, b) => a.name.localeCompare(b.name))
  } catch {
    error.value = 'Plate 目录不可达,服务清单拉取失败。'
  } finally {
    loading.value = false
  }
}

function open(name: string): void {
  void router.push(`/services/${encodeURIComponent(name)}`)
}

onMounted(() => { void load() })
</script>
