<!-- ServiceAliasCard.vue — 工作台注册卡:服务信息管理(adminOnly,→ /service-admin)。
     数据 = listAliases() 全集(与完整页同一端点,不另开口子);未分组判定
     与完整页同一条谓词(!groupTag)—— §7 第 6 条计数同源。
     三档密度(§4):S = 别名数 + 未分组数;M/L = 别名行 5/8。 -->
<template>
  <div data-testid="wb-card-service-aliases" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="layers" :size="14" />
      </span>
      <span class="chead-title">服务信息管理</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/service-admin" class="manage-link">管理 →</router-link>
    </header>

    <!-- S 档:只出结论(未分组是这页真正要人盯的那件事) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>个别名</p>
        <p class="s-stat" :class="{ 'st-warn': ungroupedCount > 0 }"><b>{{ ungroupedCount }}</b>未分组</p>
      </div>
    </div>

    <template v-else>
      <div v-if="loading" class="card-empty"><p>加载中…</p></div>
      <div v-else-if="rows.length" class="rows">
        <router-link
          v-for="a in visible"
          :key="a.aliasName"
          :to="`/service-admin/${encodeURIComponent(a.aliasName)}`"
          class="sa-row wrow"
          :data-testid="`wb-sa-row-${a.aliasName}`"
        >
          <span class="wrow-name mono" :title="a.aliasName">{{ a.aliasName }}</span>
          <span class="wrow-tag" :class="a.groupTag ? '' : 'tag-warn'">
            {{ a.groupTag || '未分组' }}
          </span>
          <span class="wrow-time mono">{{ a.baseService }}</span>
        </router-link>
        <p v-if="rows.length > visible.length" class="more-hint">
          还有 {{ rows.length - visible.length }} 个别名 — 到完整页查看
        </p>
      </div>
      <div v-else-if="error" class="card-empty"><p>{{ error }} — 稍后在完整页重试</p></div>
      <div v-else class="card-empty">
        <p>还没有服务别名 — 登记一个就能给编排引用</p>
        <router-link to="/service-admin" class="cta">去登记 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { listAliases, type ServiceAliasRow } from '@/api/service-aliases'

const size = useCardSize()

const rows = ref<ServiceAliasRow[]>([])
const loading = ref(true)
const error = ref('')

/** 与 ServiceAdmin.vue 左栏同一谓词:没有 groupTag 就是没分组。 */
const ungroupedCount = computed(() => rows.value.filter((a) => !a.groupTag).length)

/** M = 5 行;L = 8 行 */
const visible = computed(() =>
  [...rows.value]
    .sort((a, b) => a.aliasName.localeCompare(b.aliasName))
    .slice(0, size.value === 'L' ? 8 : 5),
)

const wbT = (suffix: string) => `wb-card-service-aliases-${suffix}`

onMounted(async () => {
  try {
    rows.value = await listAliases()
  } catch {
    error.value = '服务别名清单加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 形制在基座;这里只给行列宽、紫色图标底与"要人盯"的琥珀上色。 */
.sa-row { grid-template-columns: minmax(0, 1fr) auto auto; }
.ci-violet { color: #6d28d9; background: #f1ecfd; }
.tag-warn { color: var(--sl-warn); background: var(--sl-warn-soft); }
.st-warn b { color: var(--sl-warn); }
</style>
