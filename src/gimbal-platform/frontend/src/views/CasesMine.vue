<!-- CasesMine.vue — 我的工作台 v2 (与公共用例库共享样式)
     v2 变更：① 与 CasesPublic.vue 同款 ⋯ dropdown + 表格列布局
              ② ⋯ 增加「删除」选项（仅限用户自己拥有的私有副本）
              ③ 启用「执行」按钮 → ExecutionDrawer（之前是 disabled） -->
<template>
  <section class="cases-mine">
    <header class="page-header">
      <div>
        <h2>用例工作台</h2>
        <p>{{ metaText }}</p>
      </div>

      <div class="header-actions">
        <el-input
          v-model="searchQuery"
          class="search-input"
          clearable
          placeholder="🔍 按名 / 模块 / tags 搜索"
        />
        <FilterPopover
          v-model="filters"
          :pool="currentCases"
          show-visibility
        />
        <el-upload
          :show-file-list="false"
          :before-upload="handleUpload"
          accept=".yaml,.yml,.json"
        >
          <el-button type="primary">+ 上传用例</el-button>
        </el-upload>
      </div>
    </header>

    <el-tabs v-model="activeTab" class="case-tabs">
      <el-tab-pane
        :label="`📁 我的副本 (${casesStore.mineUploads.length})`"
        name="uploads"
      />
      <el-tab-pane
        :label="`⭐ 我的收藏 (${casesStore.mineFavorites.length})`"
        name="favorites"
      />
    </el-tabs>

    <el-table
      v-if="visibleCases.length > 0"
      v-loading="casesStore.fetchStatus === 'loading'"
      :data="visibleCases"
      :row-key="rowKey"
      :row-class-name="rowClassForMine"
      class="cases-table"
      @row-click="openCase"
    >
      <el-table-column label="⭐" width="54" align="center">
        <template #default="{ row }">
          <button
            class="favorite-button"
            type="button"
            :class="{ active: isFavorited(row) }"
            :aria-label="isFavorited(row) ? '取消收藏' : '收藏用例'"
            :title="isFavorited(row) ? '取消收藏' : '收藏用例'"
            @click.stop="toggleFavorite(row)"
          >{{ isFavorited(row) ? '★' : '☆' }}</button>
        </template>
      </el-table-column>

      <el-table-column label="用例名称" min-width="230">
        <template #default="{ row }">
          <button class="case-name" type="button" @click.stop="openCase(row)">
            {{ row.name || row.case_id }}
          </button>
          <div class="scenario-id">{{ row.case_id }}</div>
          <span v-if="row.visibility === 'public'" class="source-badge">公共</span>
        </template>
      </el-table-column>

      <el-table-column label="模块" width="130">
        <template #default="{ row }">
          <TagPill :label="row.module || '未分类'" />
        </template>
      </el-table-column>

      <el-table-column label="优先级" width="82" align="center">
        <template #default="{ row }">
          <span
            v-if="priorityOf(row)"
            class="priority-pill"
            :class="`priority-${priorityOf(row)}`"
          >P{{ priorityOf(row) }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="作者" width="130">
        <template #default="{ row }">
          <el-popover
            :width="280"
            placement="bottom-start"
            trigger="click"
            :show-arrow="false"
            popper-class="author-popover"
          >
            <template #reference>
              <button
                class="author-link"
                type="button"
                :class="{ self: isSelf(row) }"
                @click.stop
              >
                {{ authorOf(row) }}
                <span v-if="isSelf(row)" class="you-mark">你</span>
              </button>
            </template>
            <AuthorProfile :author="authorOf(row)" />
          </el-popover>
        </template>
      </el-table-column>

      <el-table-column label="Tags" min-width="210">
        <template #default="{ row }">
          <div v-if="row.tags.length" class="tag-list">
            <TagPill
              v-for="tag in row.tags.slice(0, MAX_VISIBLE_TAGS)"
              :key="tag"
              :label="tag"
              tone="accent"
            />
            <TagPill
              v-if="row.tags.length > MAX_VISIBLE_TAGS"
              :label="`+${row.tags.length - MAX_VISIBLE_TAGS}`"
            />
          </div>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="更新时间" width="118">
        <template #default="{ row }">
          <span class="updated-at" :title="formatAbsoluteTime(row.updated_at)">
            {{ formatRelativeTime(row.updated_at) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <el-dropdown
            trigger="click"
            @command="(cmd: string) => onCommand(cmd, row)"
          >
            <button
              class="more-button"
              type="button"
              aria-label="更多操作"
              @click.stop
            >⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="view">查看详情</el-dropdown-item>
                <el-dropdown-item
                  v-if="isFavorited(row)"
                  command="unfavorite"
                  class="is-favorited"
                >
                  取消收藏
                </el-dropdown-item>
                <el-dropdown-item v-else command="favorite">
                  收藏
                </el-dropdown-item>
                <el-dropdown-item divided command="execute">
                  执行
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="canPublish(row)"
                  command="publish"
                >
                  分享到公共用例库
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="canDelete(row)"
                  divided
                  command="delete"
                  class="is-danger"
                >
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-else-if="casesStore.fetchStatus !== 'loading'"
      description="暂无用例 — 去 🌐 公共用例库 ⭐ 收藏或 ⋯ → 复制到我的"
    >
      <el-button type="primary" plain @click="router.push('/cases/public')">
        前往公共用例库
      </el-button>
    </el-empty>

    <div v-else class="loading-state" aria-label="正在加载用例">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 执行抽屉 -->
    <ExecutionDrawer
      v-if="executeTarget"
      v-model="executeOpen"
      :case-id="executeTarget.case_id"
      :case-name="executeTarget.name || executeTarget.case_id"
      :case-summary="executeTarget"
    />

    <!-- 删除二次确认 -->
    <el-dialog
      v-model="deleteOpen"
      :width="520"
      :show-close="false"
      class="del-dialog"
    >
      <template #header>
        <div class="del-head">
          <div class="del-head-icon" aria-hidden="true">
            <span class="del-head-icon-bang">!</span>
          </div>
          <div class="del-head-text">
            <div class="del-head-eyebrow">Destructive action · 不可恢复</div>
            <h3 class="del-head-title">删除用例</h3>
          </div>
        </div>
      </template>

      <div v-if="deleteTarget" class="del-body">
        <!-- 元数据卡 -->
        <div class="del-meta-card">
          <div class="del-meta-name">
            {{ deleteTarget.name || deleteTarget.case_id }}
          </div>
          <div class="del-meta-grid">
            <div class="del-meta-row">
              <span class="del-meta-label">scenarioId</span>
              <code class="del-mono">{{ deleteTarget.case_id }}</code>
            </div>
            <div class="del-meta-row">
              <span class="del-meta-label">模块</span>
              <TagPill :label="deleteTarget.module || '未分类'" />
            </div>
            <div v-if="deleteTarget.author" class="del-meta-row">
              <span class="del-meta-label">作者</span>
              <span>{{ deleteTarget.author }}</span>
            </div>
            <div v-if="deleteTarget.tags.length" class="del-meta-row del-meta-tags">
              <span class="del-meta-label">Tags</span>
              <span class="del-meta-tag-list">
                <TagPill
                  v-for="t in deleteTarget.tags.slice(0, 5)"
                  :key="t"
                  :label="t"
                  tone="accent"
                />
              </span>
            </div>
          </div>
        </div>

        <!-- 影响列表 -->
        <h4 class="del-section-title">
          <span class="del-section-bullet" aria-hidden="true">⚠</span>
          将发生什么
        </h4>
        <ul class="del-impact">
          <li>
            <span class="del-impact-dot"></span>
            从磁盘删除 <code class="del-mono">{{ deleteFileName }}</code>
          </li>
          <li>
            <span class="del-impact-dot"></span>
            从你的「我的副本」&amp;「我的收藏」立即移除
          </li>
          <li>
            <span class="del-impact-dot"></span>
            其他用户对此用例的收藏会被服务器自动清理
          </li>
          <li class="del-impact-soft">
            <span class="del-impact-dot del-impact-dot-soft"></span>
            已生成的历史执行报告保留（不影响运行记录）
          </li>
        </ul>
      </div>

      <template #footer>
        <div class="del-foot">
          <span class="del-foot-hint">
            <span class="del-foot-hint-dot" aria-hidden="true"></span>
            输入确认前请确认这是你的私有副本
          </span>
          <div class="del-foot-buttons">
            <el-button @click="deleteOpen = false">取消</el-button>
            <el-button
              type="danger"
              :loading="deleteSubmitting"
              class="del-confirm"
              @click="confirmDelete"
            >
              <span class="del-confirm-icon" aria-hidden="true">🗑</span>
              确认删除
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 分享到公共库二次确认 -->
    <el-dialog
      v-model="publishOpen"
      :width="520"
      :show-close="false"
      class="pub-dialog"
    >
      <template #header>
        <div class="pub-head">
          <div class="pub-head-icon" aria-hidden="true">⇪</div>
          <div class="pub-head-text">
            <div class="pub-head-eyebrow">Promote to public · 不可逆变更</div>
            <h3 class="pub-head-title">分享到公共用例库</h3>
          </div>
        </div>
      </template>

      <div v-if="publishTarget" class="pub-body">
        <div class="pub-meta-card">
          <div class="pub-meta-name">
            {{ publishTarget.name || publishTarget.case_id }}
          </div>
          <div class="pub-meta-grid">
            <div class="pub-meta-row">
              <span class="pub-meta-label">scenarioId</span>
              <code class="del-mono">{{ publishTarget.case_id }}</code>
            </div>
            <div class="pub-meta-row">
              <span class="pub-meta-label">模块</span>
              <TagPill :label="publishTarget.module || '未分类'" />
            </div>
            <div v-if="publishTarget.tags.length" class="pub-meta-row pub-meta-tags">
              <span class="pub-meta-label">Tags</span>
              <span class="pub-meta-tag-list">
                <TagPill
                  v-for="t in publishTarget.tags.slice(0, 5)"
                  :key="t"
                  :label="t"
                  tone="accent"
                />
              </span>
            </div>
            <div class="pub-meta-row">
              <span class="pub-meta-label">当前状态</span>
              <span class="pub-pill pub-pill-private">私有</span>
            </div>
          </div>
        </div>

        <h4 class="pub-section-title">
          <span class="pub-section-bullet" aria-hidden="true">→</span>
          将发生什么
        </h4>
        <ul class="pub-impact">
          <li>
            <span class="pub-impact-dot"></span>
            把 <code class="del-mono">{{ publishFileName }}</code> 从私有目录移到 <code class="del-mono">data/public/</code>
          </li>
          <li>
            <span class="pub-impact-dot"></span>
            标记为 <span class="pub-pill pub-pill-public">公共</span> · 审核 <span class="pub-pill pub-pill-pending">待审核</span>
          </li>
          <li>
            <span class="pub-impact-dot"></span>
            从你的「我的副本」移除，出现在「公共用例库」
          </li>
          <li class="pub-impact-soft">
            <span class="pub-impact-dot pub-impact-dot-soft"></span>
            此操作不可逆（要从公共库收回应联系 admin）
          </li>
        </ul>
      </div>

      <template #footer>
        <div class="pub-foot">
          <span class="pub-foot-hint">
            <span class="pub-foot-hint-dot" aria-hidden="true"></span>
            分享后所有登录用户都可搜索与收藏
          </span>
          <div class="pub-foot-buttons">
            <el-button @click="publishOpen = false">取消</el-button>
            <el-button
              type="primary"
              :loading="publishSubmitting"
              class="pub-confirm"
              @click="confirmPublish"
            >
              <span class="pub-confirm-icon" aria-hidden="true">⇪</span>
              确认分享
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import * as casesApi from '@/api/cases'
import { useCasesStore } from '@/stores/cases'
import { useAuthStore } from '@/stores/auth'
import type { CaseSummary } from '@/api/cases'
import TagPill from '@/components/TagPill.vue'
import AuthorProfile from '@/components/AuthorProfile.vue'
import ExecutionDrawer from '@/components/ExecutionDrawer.vue'
import FilterPopover from '@/components/FilterPopover.vue'
import { applyFiltersToList, emptyFilters, type CaseFilters } from '@/utils/filters'
import {
  authorOf,
  isMyPrivateCopy,
  isSelfRow,
  priorityOf,
  rowClassName,
  rowKey,
} from '@/utils/case-row'

type MineTab = 'uploads' | 'favorites'

const MAX_VISIBLE_TAGS = 3
const casesStore = useCasesStore()
const authStore = useAuthStore()
const router = useRouter()

const activeTab = ref<MineTab>('uploads')
const searchQuery = ref('')
const executeOpen = ref(false)
const executeTarget = ref<CaseSummary | null>(null)
const deleteOpen = ref(false)
const deleteTarget = ref<CaseSummary | null>(null)
const deleteSubmitting = ref(false)
const deleteFileName = computed(() => {
  const fp = deleteTarget.value?.file_path
  if (!fp) return ''
  // Strip leading data/users/<id>/ for a tidier display
  const parts = fp.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
})

const publishOpen = ref(false)
const publishTarget = ref<CaseSummary | null>(null)
const publishSubmitting = ref(false)
const publishFileName = computed(() => {
  const fp = publishTarget.value?.file_path
  if (!fp) return ''
  const parts = fp.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
})

// 高级过滤（FilterPopover v-model）
const filters = ref<CaseFilters>(emptyFilters())

const currentCases = computed<CaseSummary[]>(() =>
  activeTab.value === 'uploads'
    ? casesStore.mineUploads
    : casesStore.mineFavorites,
)

const visibleCases = computed(() => {
  const filtered = applyFiltersToList(currentCases.value, filters.value)
  const q = searchQuery.value.trim().toLocaleLowerCase()
  if (!q) return filtered
  return filtered.filter((item) =>
    [item.name, item.case_id, item.module, item.description, ...item.tags]
      .join(' ')
      .toLocaleLowerCase()
      .includes(q),
  )
})

const metaText = computed(() => {
  const uploads = casesStore.mineUploads.length
  const favorites = casesStore.mineFavorites.length
  return `共 ${uploads + favorites} 个用例（${uploads} 副本 · ${favorites} 收藏）— 副本来自「+ 上传」或从 🌐 公共用例库复制`
})

onMounted(async () => {
  try {
    await casesStore.fetchMine()
  } catch {
    ElMessage.error(casesStore.lastError || '加载用例失败')
  }
})

function openCase(row: CaseSummary): void {
  router.push(`/cases/${encodeURIComponent(row.case_id)}/config`)
}

function isFavorited(row: CaseSummary): boolean {
  return (
    row.favorited_by_me ||
    casesStore.mineFavorites.some((item) => item.case_id === row.case_id)
  )
}

// 行级权限：当前用户拥有此私有副本（无论是「分享」还是「删除」前置条件）。
function canDelete(row: CaseSummary): boolean {
  return isMyPrivateCopy(row, authStore.currentUser?.id)
}
function canPublish(row: CaseSummary): boolean {
  return isMyPrivateCopy(row, authStore.currentUser?.id)
}

function isSelf(row: CaseSummary): boolean {
  return isSelfRow(row, authStore.currentUser?.id)
}

async function toggleFavorite(row: CaseSummary): Promise<void> {
  try {
    await casesStore.toggleFavorite(row.case_id)
  } catch {
    ElMessage.error(casesStore.lastError || '收藏操作失败')
  }
}

async function onCommand(cmd: string, row: CaseSummary): Promise<void> {
  switch (cmd) {
    case 'view':
      router.push(`/cases/${encodeURIComponent(row.case_id)}/config`)
      return
    case 'favorite':
    case 'unfavorite':
      try {
        await casesStore.toggleFavorite(row.case_id)
      } catch {
        ElMessage.error(casesStore.lastError || '收藏操作失败')
      }
      return
    case 'execute':
      executeTarget.value = row
      executeOpen.value = true
      return
    case 'delete':
      deleteTarget.value = row
      deleteOpen.value = true
      return
    case 'publish':
      publishTarget.value = row
      publishOpen.value = true
      return
  }
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value) return
  deleteSubmitting.value = true
  try {
    await casesStore.removeCase(deleteTarget.value.case_id)
    ElMessage.success(`已删除：${deleteTarget.value.case_id}`)
    deleteOpen.value = false
    deleteTarget.value = null
  } catch {
    ElMessage.error(casesStore.lastError || '删除失败')
  } finally {
    deleteSubmitting.value = false
  }
}

async function confirmPublish(): Promise<void> {
  if (!publishTarget.value) return
  publishSubmitting.value = true
  try {
    const out = await casesStore.publishCase(publishTarget.value.case_id)
    ElMessage.success(`已分享到公共用例库：${out.case_id}`)
    publishOpen.value = false
    publishTarget.value = null
    // Refresh /mine (item is now removed) and /public in background
    casesStore.fetchPublic(true).catch(() => {})
  } catch {
    ElMessage.error(casesStore.lastError || '分享失败')
  } finally {
    publishSubmitting.value = false
  }
}

async function handleUpload(file: File): Promise<boolean> {
  try {
    const created = await casesApi.upload(file, 'private')
    ElMessage.success(`已上传：${created.case_id}`)
    await casesStore.fetchMine()
  } catch {
    ElMessage.error(casesStore.lastError || '上传失败')
  }
  return false
}

/** Per-row className: shared base from utils + mine-only signals
 *  (favorited/visibility).  Public view doesn't need the favorited flag
 *  added locally (it's in the summary already). */
function rowClassForMine({ row }: { row: CaseSummary }): string {
  const extra: string[] = []
  if (isFavorited(row)) extra.push('favorited-row')
  return rowClassName({ row }, extra)
}

function formatRelativeTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'

  const now = new Date()
  const diffMs = Math.max(0, now.getTime() - date.getTime())
  const minutes = Math.floor(diffMs / 60_000)
  const hours = Math.floor(diffMs / 3_600_000)
  const days = Math.floor(diffMs / 86_400_000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) {
    return `昨天 ${twoDigits(date.getHours())}:${twoDigits(date.getMinutes())}`
  }

  if (days < 7) return `${days} 天前`
  return `${date.getFullYear()}-${twoDigits(date.getMonth() + 1)}-${twoDigits(date.getDate())}`
}

function formatAbsoluteTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

function twoDigits(value: number): string {
  return String(value).padStart(2, '0')
}
</script>

<style scoped>
.cases-mine {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
  line-height: 1.25;
}

.page-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.search-input {
  width: 260px;
}

.case-tabs {
  margin-bottom: 2px;
}

.cases-table {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  cursor: pointer;
}

.case-name {
  display: block;
  max-width: 100%;
  padding: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font: inherit;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
  text-overflow: ellipsis;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.case-name:hover,
.case-name:focus-visible {
  color: var(--accent);
  outline: none;
}

.scenario-id {
  max-width: 100%;
  margin-top: 2px;
  overflow: hidden;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 10px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.source-badge {
  display: inline-flex;
  padding: 0 5px;
  margin-top: 4px;
  color: #64748b;
  font-size: 9px;
  line-height: 16px;
  background: #f1f5f9;
  border-radius: 8px;
}

.favorite-button {
  padding: 2px;
  color: #cbd5e1;
  font-size: 19px;
  line-height: 1;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.favorite-button:hover,
.favorite-button:focus-visible,
.favorite-button.active {
  color: #d97706;
  outline: none;
}

.priority-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 31px;
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  border-radius: 10px;
}

.priority-1 {
  color: #991b1b;
  background: #fee2e2;
}
.priority-2 {
  color: #9a3412;
  background: #ffedd5;
}
.priority-3 {
  color: #5b21b6;
  background: #ede9fe;
}

.tag-list {
  display: flex;
  gap: 5px;
  align-items: center;
  min-width: 0;
}

.author-link {
  padding: 0;
  color: var(--accent);
  font: inherit;
  font-size: 11.5px;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
}
.author-link:hover,
.author-link:focus-visible {
  color: var(--accent);
  background: var(--accent-soft);
  outline: none;
}
.author-link.self {
  font-weight: 600;
}
.you-mark {
  display: inline-block;
  padding: 0 4px;
  margin-left: 4px;
  color: #5b21b6;
  font-size: 9px;
  font-weight: 600;
  background: #ede9fe;
  border-radius: 3px;
}

.updated-at,
.muted {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.mono {
  font-family: var(--font-mono);
}

.more-button {
  padding: 3px 9px;
  color: #64748b;
  font-size: 14px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 5px;
  cursor: pointer;
}

.more-button:hover,
.more-button:focus-visible {
  color: var(--color-text-primary);
  border-color: var(--accent);
  outline: none;
}

.loading-state {
  padding: 28px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
}

:deep(.el-tabs__header) {
  margin-bottom: 12px;
}
:deep(.el-tabs__item) {
  height: 38px;
  font-size: 12px;
}

:deep(.el-table th.el-table__cell) {
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  background: #f8fafc;
}
:deep(.el-table td.el-table__cell) {
  padding: 9px 0;
  font-size: 12px;
}

:deep(.el-table .favorited-row > td.el-table__cell) {
  background: #faf9ff;
}
:deep(.el-table .copied-row > td.el-table__cell) {
  background: #f0fdf4;
}
:deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--accent-soft) !important;
}

:deep(.el-dropdown-menu__item) {
  justify-content: flex-start;
  padding: 8px 14px;
  font-size: 12px;
  text-align: left;
}
:deep(.el-dropdown-menu__item.is-favorited) {
  color: #166534;
  font-weight: 600;
  background: #f0fdf4;
}
:deep(.el-dropdown-menu__item.is-danger) {
  color: #b91c1c;
}
:deep(.el-dropdown-menu__item.is-danger:hover) {
  background: #fef2f2;
  color: #991b1b;
}

@media (max-width: 900px) {
  .cases-mine {
    padding: 20px 16px 36px;
  }
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .search-input {
    width: min(100%, 320px);
  }
}

/* ─── Delete confirmation dialog ────────────────────────────
   All `.del-*` classes live in src/styles/_destructive-dialog.css
   (imported globally via main.ts).  Keep this section as a no-op so
   the surrounding scoped styles stay grouped together.
*/

/* ─── Publish dialog ─────────────────────────────────────── */
:deep(.pub-dialog .el-dialog__header),
:deep(.pub-dialog .el-dialog__body),
:deep(.pub-dialog .el-dialog__footer) {
  padding: 0;
}

.pub-head {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 20px 24px 16px;
  background: linear-gradient(180deg, var(--accent-soft) 0%, #ffffff 100%);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.pub-head-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  color: var(--accent);
  font-size: 22px;
  font-weight: 700;
  background: white;
  border: 2px solid var(--accent-soft-border);
  border-radius: 50%;
  box-shadow: 0 0 0 4px var(--accent-soft);
  flex-shrink: 0;
}

.pub-head-text { flex: 1; min-width: 0; }

.pub-head-eyebrow {
  color: var(--accent);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.pub-head-title {
  margin: 4px 0 0;
  color: var(--color-text-primary);
  font-size: 19px;
  font-weight: 700;
}

.pub-body { padding: 18px 24px 8px; }

.pub-meta-card {
  padding: 14px 16px;
  background: #fafbff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}

.pub-meta-name {
  margin-bottom: 10px;
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 700;
}

.pub-meta-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pub-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.pub-meta-label {
  min-width: 78px;
  color: var(--color-text-secondary);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.pub-meta-tags { align-items: flex-start; }

.pub-meta-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pub-pill {
  display: inline-flex;
  padding: 1px 8px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  border-radius: 4px;
}
.pub-pill-private { color: #64748b; background: #f1f5f9; }
.pub-pill-public { color: var(--accent); background: var(--accent-soft); }
.pub-pill-pending { color: #92400e; background: #fff7ed; }

.pub-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 16px 0 8px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.pub-section-bullet {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 11px;
  background: var(--accent-soft);
  border-radius: 4px;
}

.pub-impact {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  margin: 0;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.pub-impact li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--color-text-primary);
  font-size: 12px;
  line-height: 1.5;
}
.pub-impact-soft { color: var(--color-text-secondary); }

.pub-impact-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 5px;
  height: 5px;
  margin-top: 7px;
  background: var(--accent);
  border-radius: 50%;
  flex-shrink: 0;
}
.pub-impact-dot-soft { background: var(--color-text-tertiary); }

.pub-foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 16px;
  background: #fafbff;
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.pub-foot-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.pub-foot-hint-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.pub-foot-buttons { display: flex; gap: 8px; }

.pub-confirm { font-weight: 600; }

.pub-confirm-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-right: 4px;
  font-size: 10px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 4px;
}
</style>
