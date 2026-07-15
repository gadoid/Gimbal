<!-- TopNav.vue — Spec-1 top navigation bar.
     Fixed 48px high, dark chrome (#1f2933), font-size 12px.
     Only mounted when auth.isAuthenticated (caller in App.vue handles it). -->
<template>
  <header class="topnav">
    <!-- Left: brand (status dot + platform text) -->
    <div class="topnav-left">
      <span class="status-dot" :title="statusTitle"></span>
      <span class="brand-text">platform</span>
    </div>

    <!-- Middle: nav entries -->
    <nav class="topnav-middle">
      <router-link
        v-for="entry in navEntries"
        :key="entry.path"
        :to="entry.path"
        class="nav-entry"
        :class="{ active: isActive(entry.path) }"
      >{{ entry.label }}</router-link>
    </nav>

    <!-- Right: user identity + logout -->
    <div class="topnav-right">
      <span class="user-info" v-if="auth.currentUser">
        <span class="username">{{ auth.currentUser.display_name || auth.currentUser.username }}</span>
        <span class="role">({{ auth.currentUser.is_admin ? 'admin' : 'member' }})</span>
      </span>
      <el-button
        type="primary"
        plain
        size="small"
        class="logout-btn"
        @click="onLogout"
      >登出</el-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

interface NavEntry {
  path: string
  label: string
}

const navEntries: NavEntry[] = [
  { path: '/cases/mine', label: '📋 我的工作台' },
  { path: '/cases/public', label: '🌐 公共用例库' },
  { path: '/executions', label: '📊 执行历史' },
  { path: '/auths', label: '🔐 认证管理' },
  { path: '/admin/users', label: '⚙️ 用户管理' },
]

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

const statusTitle = '服务在线'

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.topnav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  background: #1f2933;
  color: #e2e8f0;
  font-size: 12px;
  z-index: 1000;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

.topnav-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 140px;
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 4px rgba(34, 197, 94, 0.6);
  flex-shrink: 0;
}

.brand-text {
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #f5f3ff;
}

.topnav-middle {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  justify-content: center;
}

.nav-entry {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 14px;
  border-radius: 4px;
  color: #cbd5e1;
  text-decoration: none;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease;
  cursor: pointer;
  user-select: none;
}

.nav-entry:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.nav-entry.active {
  background: #ede9fe;
  color: #1f2933;
  font-weight: 600;
}

.nav-entry.active:hover {
  background: #ede9fe;
  color: #1f2933;
}

.nav-entry.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.nav-entry.disabled:hover {
  background: transparent;
  color: #cbd5e1;
}

.topnav-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 140px;
  flex-shrink: 0;
  justify-content: flex-end;
}

.user-info {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #cbd5e1;
}

.username {
  color: #f5f3ff;
  font-weight: 500;
}

.role {
  color: #94a3b8;
  font-size: 11px;
}

.logout-btn {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}
</style>