<!-- UserDetailAdmin.vue — 用户管理 → 用户页(钻取子页,点行进入)。
     页面化而非直达功能页:概览 + 访问令牌两个 tab 起步,后续按用户维度的
     板块(使用情况/审计切片等)在此扩 tab,不再回到列表面加菜单项。
     * 概览:基础信息(用户名/昵称/角色/状态/创建时间);
     * 访问令牌:该用户的令牌 + 使用信息(经此令牌注册的任务/最近调用含
       被拒),复用 TokensSection(admin 定属主 + 强制失效)。
     面包屑返回 /admin/users(列表 syncUrl,搜索/页码不丢)。 -->
<template>
  <section class="slib udt">
    <header class="udt-head">
      <div class="flex flex-col gap-1">
        <span class="text-caption text-signal-ink/60">
          <RouterLink class="udt-link" to="/admin/users">用户管理</RouterLink>
          / {{ user?.username ?? '…' }}
        </span>
        <div class="flex flex-wrap items-center gap-2.5">
          <h1 class="m-0 text-[22px] leading-[30px] font-semibold" data-testid="udt-title">
            {{ user ? (user.display_name || user.username) : '…' }}
          </h1>
          <span v-if="user" class="udt-pill">{{ roleText }}</span>
          <span
            v-if="user"
            class="udt-pill"
            :class="user.is_active ? 'is-on' : 'is-off'"
          >{{ user.is_active ? '● 启用' : '○ 停用' }}</span>
        </div>
      </div>
      <Button
        variant="outline" size="sm" data-testid="udt-back"
        @click="router.push('/admin/users')"
      >← 返回用户管理</Button>
    </header>

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div v-else-if="missing" class="slib-empty">
      <p>找不到该用户(可能已被删除)。</p>
      <Button variant="outline" data-testid="udt-back" @click="router.push('/admin/users')">返回用户管理</Button>
    </div>

    <Tabs v-else-if="user" v-model="tab">
      <TabsList>
        <TabsTrigger value="overview" data-testid="udt-tab-overview">概览</TabsTrigger>
        <TabsTrigger value="tokens" data-testid="udt-tab-tokens">访问令牌</TabsTrigger>
      </TabsList>

      <!-- 概览:基础信息(扩展板块时在此加 TabsTrigger/TabsContent) -->
      <TabsContent value="overview">
        <div class="lib-card">
          <table class="udt-kv" data-testid="udt-overview">
            <tbody>
              <tr><th>用户名</th><td class="mono">{{ user.username }}</td></tr>
              <tr><th>昵称</th><td>{{ user.display_name || '—' }}</td></tr>
              <tr><th>角色</th><td>{{ roleText }}</td></tr>
              <tr><th>状态</th><td>{{ user.is_active ? '启用' : '停用' }}</td></tr>
              <tr><th>创建时间</th><td class="mono">{{ mediumDateTime(new Date(user.created_at)).slice(0, 10) }}</td></tr>
            </tbody>
          </table>
        </div>
      </TabsContent>

      <TabsContent value="tokens">
        <TokensSection
          variant="admin"
          :owner-id="user.id"
          :owner-name="user.display_name || user.username"
        />
      </TabsContent>
    </Tabs>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import TokensSection from '@/components/profile/TokensSection.vue'
import { get, type UserOut } from '@/api/users'
import { mediumDateTime } from '@/utils/datetime'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()

const user = ref<UserOut | null>(null)
const loading = ref(true)
const missing = ref(false)
const tab = ref('overview')

const ROLE_LABELS: Record<string, string> = {
  user: '用户', admin: '管理员', super_admin: '超级管理员',
}
const roleText = computed(() =>
  ROLE_LABELS[user.value?.role ?? 'user'] ?? '用户')

onMounted(async () => {
  const id = Number.parseInt(String(route.params.id), 10)
  if (!Number.isFinite(id) || id < 1) {
    missing.value = true
    loading.value = false
    return
  }
  try {
    user.value = await get(id)
  } catch {
    missing.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.udt { display: flex; flex-direction: column; gap: 16px; max-width: 980px; }
.udt-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
}
.udt-link { color: var(--color-signal, #2f6fed); text-decoration: none; }
.udt-link:hover { text-decoration: underline; }
.udt-pill {
  font-size: 11px; font-weight: 600; padding: 2px 8px;
  border-radius: 999px; white-space: nowrap;
  background: var(--color-signal-soft, #e7efff);
  color: var(--color-signal, #1f55c4);
}
.udt-pill.is-on { background: #e4f5ea; color: #15803d; }
.udt-pill.is-off { background: #eef0f3; color: #5b6472; }
.udt-kv { width: 100%; border-collapse: collapse; font-size: 13px; }
.udt-kv th {
  width: 96px; text-align: left; font-weight: 500;
  color: color-mix(in srgb, var(--color-signal-ink, #10151c) 60%, transparent);
  padding: 8px 12px; vertical-align: top;
}
.udt-kv td { padding: 8px 12px; }
.udt-kv tr + tr th, .udt-kv tr + tr td { border-top: 1px solid var(--color-signal-line, #e1e5eb); }
.mono { font-family: var(--font-mono, monospace); }
</style>
