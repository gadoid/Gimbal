<!-- AuthSessionsCard.vue — 工作台注册卡:认证管理(→ /auths)。
     数据走 store(与完整页同一个 useAuthSessionsStore),不另开口子;
     「未被引用」谓词与 Auths.vue 摘要行一致(alias_ref_count 与
     scenario_ref_count 都空)—— §7 第 6 条计数同源。
     三档密度(§4):S = 凭证数 + 未被引用数;M/L = 凭证行 5/8。 -->
<template>
  <div data-testid="wb-card-auths" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="lock" :size="14" />
      </span>
      <span class="chead-title">认证管理</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/auths" class="manage-link">管理 →</router-link>
    </header>

    <!-- S 档:只出结论(未被引用的凭证是可以安全清掉的那批) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>条凭证</p>
        <p class="s-stat" :class="{ 'st-warn': unreferencedCount > 0 }"><b>{{ unreferencedCount }}</b>未被引用</p>
      </div>
    </div>

    <template v-else>
      <div v-if="store.fetchStatus === 'loading'" class="card-empty"><p>加载中…</p></div>
      <div v-else-if="rows.length" class="rows">
        <!-- 凭证没有单条详情页,行是数据不是链接(hover 不给可点暗示) -->
        <div v-for="a in visible" :key="a.id" class="ar-row wrow" :data-testid="`wb-ar-row-${a.alias}`">
          <span class="wrow-name mono" :title="a.alias">{{ a.alias }}</span>
          <span class="wrow-tag">{{ a.token_type }}</span>
          <span class="wrow-time">{{ refText(a) }}</span>
        </div>
        <p v-if="rows.length > visible.length" class="more-hint">
          还有 {{ rows.length - visible.length }} 条凭证 — 到完整页查看
        </p>
      </div>
      <div v-else-if="store.fetchStatus === 'error'" class="card-empty">
        <p>凭证池加载失败 — 稍后在认证管理页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有认证凭证 — 登记一条,Bearer/Basic 都能被编排引用</p>
        <router-link to="/auths" class="cta">去登记 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'

const size = useCardSize()
const store = useAuthSessionsStore()

const rows = computed(() =>
  [...store.list].sort((a, b) => a.alias.localeCompare(b.alias)),
)

/** 与 Auths.vue 摘要同一谓词。 */
const unreferencedCount = computed(
  () => store.list.filter((a) => !a.alias_ref_count && !a.scenario_ref_count).length,
)

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))

const refText = (a: AuthSession) => {
  const n = (a.alias_ref_count ?? 0) + (a.scenario_ref_count ?? 0)
  return n ? `${n} 处引用` : '未被引用'
}

const wbT = (suffix: string) => `wb-card-auths-${suffix}`

onMounted(() => {
  // fetchAll 会抛(完整页靠它弹错),卡上只把状态留在 store.fetchStatus
  void store.fetchAll().catch(() => undefined)
})
</script>

<style scoped>
/* 形制在基座;这里只给行列宽与"可清理"的琥珀提示。 */
.ar-row { grid-template-columns: minmax(0, 1fr) auto auto; }
.ar-row:hover { background: none; }
.st-warn b { color: var(--sl-warn); }
</style>
