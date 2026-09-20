<!-- UsersSummaryCard.vue — 工作台注册卡:用户管理(adminOnly,→ /admin/users)。
     数据走 useUsersStore(与完整页同一个 store),不另开口子;停用判定
     与 UsersAdmin.vue 同一条谓词(!is_active)—— §7 第 6 条计数同源。
     三档密度(§4):S = 用户数 + 停用数;M/L = 用户行 5/8。 -->
<template>
  <div data-testid="wb-card-users" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="gear" :size="14" />
      </span>
      <span class="chead-title">用户管理</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/admin/users" class="manage-link">管理 →</router-link>
    </header>

    <!-- S 档:只出结论 -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <p class="s-stat"><b>{{ rows.length }}</b>个用户</p>
        <p class="s-stat" :class="{ 'st-warn': inactiveCount > 0 }"><b>{{ inactiveCount }}</b>已停用</p>
      </div>
    </div>

    <template v-else>
      <div v-if="store.fetchStatus === 'loading'" class="card-empty"><p>加载中…</p></div>
      <div v-else-if="rows.length" class="rows">
        <!-- 用户没有单条详情页,行是数据不是链接(hover 不给可点暗示) -->
        <div v-for="u in visible" :key="u.id" class="us-row wrow" :data-testid="`wb-us-row-${u.username}`">
          <span class="wrow-name mono" :title="u.username">{{ u.username }}</span>
          <span class="us-display" :title="u.display_name">{{ u.display_name || '—' }}</span>
          <span v-if="u.is_admin" class="wrow-tag tag-admin">管理员</span>
          <span v-if="!u.is_active" class="wrow-tag tag-inactive">已停用</span>
        </div>
        <p v-if="rows.length > visible.length" class="more-hint">
          还有 {{ rows.length - visible.length }} 个用户 — 到完整页查看
        </p>
      </div>
      <div v-else-if="store.fetchStatus === 'error'" class="card-empty">
        <p>用户列表加载失败 — 稍后在用户管理页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有其他用户 — 邀请同事进来一起编排</p>
        <router-link to="/admin/users" class="cta">去邀请 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { useUsersStore } from '@/stores/users'

const size = useCardSize()
const store = useUsersStore()

const rows = computed(() =>
  [...store.list].sort((a, b) => a.username.localeCompare(b.username)),
)

/** 与 UsersAdmin.vue 同一谓词。 */
const inactiveCount = computed(() => store.list.filter((u) => !u.is_active).length)

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))

const wbT = (suffix: string) => `wb-card-users-${suffix}`

onMounted(() => {
  // fetchAll 会抛(完整页靠它弹错),卡上只把状态留在 store.fetchStatus
  void store.fetchAll().catch(() => undefined)
})
</script>

<style scoped>
/* 形制在基座;这里只给行列宽与两种身份 chip。 */
.us-row { grid-template-columns: minmax(0, auto) minmax(0, 1fr) auto auto; }
.us-display {
  min-width: 0; color: var(--sl-ink-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.us-row:hover { background: none; }
.tag-admin { color: var(--sl-accent); background: var(--sl-accent-soft); }
.tag-inactive { color: var(--sl-warn); background: var(--sl-warn-soft); }
.st-warn b { color: var(--sl-warn); }
</style>
