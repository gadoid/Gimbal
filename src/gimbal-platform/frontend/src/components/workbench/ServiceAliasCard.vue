<!-- ServiceAliasCard.vue — 工作台注册卡:服务注册(adminOnly,→ /service-admin;
     2026-11-13 身份面与各环境地址并为同一页,卡片随页更名)。
     数据 = listAliases() 全集(与完整页同一端点,不另开口子)。
     registry 重做口径:行 tag = 条目 ref(默认账户/指定用户名);
     旧「未声明槽位」统计随槽概念退役(条目即注入键,恒有值)。
     三档密度(§4):S = 条目数 + 基础服务数;M/L = 条目行 5/8。 -->
<template>
  <div data-testid="wb-card-service-aliases" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="layers" :size="14" />
      </span>
      <span class="chead-title">服务注册</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/service-admin" class="manage-link">管理 →</router-link>
    </header>

    <!-- S 档:只出结论(装载与实例坐标去完整页看) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>个条目</p>
        <p class="s-stat"><b>{{ baseCount }}</b>个基础服务</p>
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
          <span class="wrow-tag">
            {{ a.refMode === 'username' ? `用户名·${a.refUsername || '—'}` : '默认账户' }}
          </span>
          <span class="wrow-time mono">{{ a.baseService }}</span>
        </router-link>
        <p v-if="rows.length > visible.length" class="more-hint">
          还有 {{ rows.length - visible.length }} 个条目 — 到完整页查看
        </p>
      </div>
      <div v-else-if="error" class="card-empty"><p>{{ error }} — 稍后在完整页重试</p></div>
      <div v-else class="card-empty">
        <p>还没有身份条目 — 登记一个就能给编排引用</p>
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

/** 基础服务数(条目 → base 去重;S 档结论位) */
const baseCount = computed(() =>
  new Set(rows.value.map((a) => a.baseService)).size)

/** M = 5 行;L = 8 行 */
const visible = computed(() =>
  [...rows.value]
    .sort((a, b) => a.aliasName.localeCompare(b.aliasName))
    .slice(0, size.value === 'L' ? 8 : 5),
)

const wbT = (suffix: string) => `wb-card-service-aliases-${suffix}`

onMounted(async () => {
  try {
    rows.value = (await listAliases()).items
  } catch {
    error.value = '身份条目清单加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 形制在基座(ci-blue 走共享 .ci-* 家族);这里只给行列宽。 */
.sa-row { grid-template-columns: minmax(0, 1fr) auto auto; }
</style>
