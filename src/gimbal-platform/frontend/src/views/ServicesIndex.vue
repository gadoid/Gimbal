<!-- ServicesIndex.vue — 服务画像落地页:列 plate 目录服务,点进热力网格。
     数据源 = utils/catalog-services(共享缓存,与编排器同一次拉取);
     plate 不可达 → 错误态提示重试,不白屏。
     页壳/页头/瓦片走场景库·工作台同一套语言(service-area.css)。 -->
<template>
  <section class="slib">
    <PageHead
      icon="grid"
      title="服务画像"
      :subtitle="loading ? '正在读取 Plate 目录…' : `${services.length} 个服务 · 选择服务进入热力网格`"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div
      v-else-if="error"
      class="svc-banner bad"
      data-testid="services-error"
    >
      <span>{{ error }}</span>
      <button type="button" class="svc-link" data-testid="services-retry" @click="load">重试</button>
    </div>

    <div v-else-if="services.length" class="svc-tiles" data-testid="services-grid">
      <button
        v-for="svc in services"
        :key="svc.name"
        type="button"
        :data-testid="`services-card-${svc.name}`"
        class="svc-tile"
        @click="open(svc.name)"
      >
        <div class="svc-tile-top">
          <span class="svc-tile-name mono">{{ svc.name }}</span>
          <SystemChip :sys="svc.system" />
        </div>
        <div class="svc-tile-meta">
          {{ svc.endpointCount }} 个接口
          <span class="svc-tile-go">进入热力网格 →</span>
        </div>
      </button>
    </div>

    <div v-else class="slib-empty">
      <p>Plate 目录里还没有服务 —— 服务清单由 plate 侧维护</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SystemChip from '@/components/SystemChip.vue'
import { loadCatalogServiceRows, type CatalogServiceRow } from '@/utils/catalog-services'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const services = ref<CatalogServiceRow[]>([])

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    // 聚合口径在 catalog-services 里,工作台「服务画像」卡读同一份 ——
    // 两处各算一次,卡上计数就会和点进来的页面对不上。
    services.value = await loadCatalogServiceRows()
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

<style scoped>
/* 瓦片里「进入 →」贴着计数右靠:一句话读完这格能干什么 */
.svc-tile-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
</style>
