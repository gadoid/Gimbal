<!-- CasesPublic.vue — 公共用例库 v2 (Spec-1 wireframe 5/v2).
     v2 变更：①去掉审核 tab（行内 tag） ②操作列 ⋯ dropdown ③作者可点击弹 profile popover -->
<template>
  <section class="cases-public">
    <header class="page-header">
      <div>
        <h2>公共用例库</h2>
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
          :pool="casesStore.publicLibrary"
          show-audited
        />
        <el-upload
          :show-file-list="false"
          :before-upload="handlePublicSubmit"
          accept=".yaml,.yml,.json"
        >
          <el-button type="primary">+ 提交公共用例</el-button>
        </el-upload>
      </div>
    </header>

    <el-table
      v-if="visibleCases.length > 0"
      v-loading="casesStore.fetchStatus === 'loading'"
      :data="visibleCases"
      :row-key="rowKey"
      :row-class-name="rowClassName"
      class="cases-table"
      @row-click="openCase"
    >
      <el-table-column label="⭐" width="54" align="center">
        <template #default="{ row }">
          <button
            class="favorite-button"
            type="button"
            :class="{ active: row.favorited_by_me }"
            :aria-label="row.favorited_by_me ? '取消收藏' : '收藏用例'"
            :title="row.favorited_by_me ? '取消收藏' : '收藏用例'"
            @click.stop="toggleFavorite(row)"
          >{{ row.favorited_by_me ? '★' : '☆' }}</button>
        </template>
      </el-table-column>

      <el-table-column label="用例名称" min-width="230">
        <template #default="{ row }">
          <button class="case-name" type="button" @click.stop="openCase(row)">
            {{ row.name || row.case_id }}
          </button>
          <div class="scenario-id">{{ row.case_id }}</div>
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

      <el-table-column label="审核" width="100">
        <template #default="{ row }">
          <span class="audit-tag" :class="row.audited ? 'audited' : 'pending'">
            {{ row.audited ? '✓ 已审核' : '⏳ 待审' }}
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
                  v-if="row.favorited_by_me"
                  command="unfavorite"
                  class="is-favorited"
                >
                  取消收藏
                </el-dropdown-item>
                <el-dropdown-item v-else command="favorite">
                  收藏
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="row.copied_by_me"
                  command="copy"
                >
                  再复制一份
                </el-dropdown-item>
                <el-dropdown-item v-else command="copy">
                  复制到我的
                </el-dropdown-item>
                <el-dropdown-item command="save-as">
                  另存为（重命名副本）
                </el-dropdown-item>
                <el-dropdown-item command="execute">
                  执行
                </el-dropdown-item>
                <el-dropdown-item divided command="open-yaml">
                  打开源 YAML
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="canDelete(row)"
                  divided
                  command="delete"
                  class="is-danger"
                >
                  删除公共用例
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-else-if="casesStore.fetchStatus !== 'loading'"
      description="暂无公共用例"
    />

    <div v-else class="loading-state" aria-label="正在加载用例">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 执行抽屉（Spec-2-2） -->
    <ExecutionDrawer
      v-if="executeTarget"
      v-model="executeOpen"
      :case-id="executeTarget.case_id"
      :case-name="executeTarget.name || executeTarget.case_id"
      :case-summary="executeTarget"
    />

    <!-- 复制 / 另存为 命名弹窗 -->
    <RenameInputDialog
      v-model="renameOpen"
      :default-name="renameDefault"
      :existing-names="renameExisting"
      :title="renameTitle"
      @submit="onRenameSubmit"
    />

    <!-- 删除公共用例二次确认（admin-only） -->
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
            <div class="del-head-eyebrow">
              Destructive action · 仅 admin 可执行
            </div>
            <h3 class="del-head-title">删除公共用例</h3>
          </div>
        </div>
      </template>

      <div v-if="deleteTarget" class="del-body">
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
            <div
              v-if="deleteTarget.tags.length"
              class="del-meta-row del-meta-tags"
            >
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
            <div class="del-meta-row">
              <span class="del-meta-label">归属</span>
              <span class="del-pill del-pill-public">公共</span>
            </div>
          </div>
        </div>

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
            立即从公共用例库移除,所有用户刷新后不可见
          </li>
          <li>
            <span class="del-impact-dot"></span>
            所有用户对此用例的收藏会被服务器自动清理
          </li>
          <li>
            <span class="del-impact-dot"></span>
            其他用户的私有副本不受影响(他们保留自己的本地版本)
          </li>
          <li class="del-impact-soft">
            <span class="del-impact-dot del-impact-dot-soft"></span>
            已生成的历史执行报告保留(不影响运行记录)
          </li>
        </ul>
      </div>

      <template #footer>
        <div class="del-foot">
          <span class="del-foot-hint">
            <span class="del-foot-hint-dot" aria-hidden="true"></span>
            公共用例删除后无法恢复,请确认影响范围
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
import RenameInputDialog from '@/components/RenameInputDialog.vue'
import { applyFiltersToList, emptyFilters, type CaseFilters } from '@/utils/filters'
import {
  MAX_VISIBLE_TAGS,
  authorOf,
  isSelfRow,
  priorityOf,
  rowClassName,
  rowKey,
} from '@/utils/case-row'

const casesStore = useCasesStore()
const authStore = useAuthStore()
const router = useRouter()
const searchQuery = ref('')
const executeOpen = ref(false)
const executeTarget = ref<CaseSummary | null>(null)

// 命名弹窗（用于「复制到我的」「另存为」）
const renameOpen = ref(false)
const renameDefault = ref('')
const renameExisting = ref<string[]>([])
const renameTitle = ref('为副本取个名字')
const renameMode = ref<'copy' | 'save-as'>('copy')
const renameTarget = ref<CaseSummary | null>(null)
const filters = ref<CaseFilters>(emptyFilters())

// admin-only 删除公共用例的状态
const deleteOpen = ref(false)
const deleteTarget = ref<CaseSummary | null>(null)
const deleteSubmitting = ref(false)
const deleteFileName = computed(() => {
  const fp = deleteTarget.value?.file_path
  if (!fp) return ''
  // Strip leading data/public/ for a tidier display.
  const parts = fp.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
})

// 当前登录用户是否为 admin —— 单一来源是 auth store
const isAdmin = computed(() => authStore.isAdmin)

const visibleCases = computed(() => {
  const all = applyFiltersToList(casesStore.publicLibrary, filters.value)
  const q = searchQuery.value.trim().toLocaleLowerCase()
  if (!q) return all
  return all.filter((item) =>
    [item.name, item.case_id, item.module, item.description, ...item.tags]
      .join(' ')
      .toLocaleLowerCase()
      .includes(q),
  )
})

const metaText = computed(() => {
  const total = casesStore.publicLibrary.length
  return `${total} 个公开用例 · 任意用户可查看、收藏、复制到我的`
})

onMounted(async () => {
  try {
    await casesStore.fetchPublic(true)
  } catch {
    ElMessage.error(casesStore.lastError || '加载公共用例失败')
  }
})

function openCase(row: CaseSummary): void {
  router.push(`/cases/${encodeURIComponent(row.case_id)}/config`)
}

function isSelf(row: CaseSummary): boolean {
  return isSelfRow(row, authStore.currentUser?.id)
}

// 行级权限：公共库里的删除按钮只对 admin 开放；与后端 cases.DELETE
// 的 public 分支一致（cases.py:794-797）。
function canDelete(_row: CaseSummary): boolean {
  return isAdmin.value
}

async function toggleFavorite(row: CaseSummary): Promise<void> {
  try {
    await casesStore.toggleFavorite(row.case_id)
  } catch {
    ElMessage.error(casesStore.lastError || '收藏操作失败')
  }
}

async function onRenameSubmit(newName: string | null): Promise<void> {
  if (!renameTarget.value) return
  const target = renameTarget.value
  try {
    if (renameMode.value === 'copy') {
      await casesStore.copyCase(target.case_id, newName ?? undefined)
      ElMessage.success(
        newName
          ? `已复制：${newName}`
          : `已复制到我的：${target.case_id}`,
      )
    } else {
      await casesApi.saveAs(target.case_id, {
        new_name: newName ?? undefined,
        visibility: 'private',
      })
      ElMessage.success(newName ? `已另存为：${newName}` : '已另存为')
    }
    await casesStore.fetchMine()
    casesStore.fetchPublic(true).catch(() => {})
  } catch (e) {
    ElMessage.error(
      (e as { msg?: string; message?: string }).msg ||
        (e as { message?: string }).message ||
        '操作失败',
    )
  } finally {
    renameTarget.value = null
  }
}

async function handlePublicSubmit(file: File): Promise<boolean> {
  try {
    const created = await casesApi.upload(file, 'public')
    ElMessage.success(`已提交到公共用例库：${created.case_id}`)
    await casesStore.fetchPublic(true)
  } catch (e) {
    const err = e as { msg?: string; message?: string }
    ElMessage.error(err.msg || err.message || casesStore.lastError || '提交失败')
  }
  return false
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value) return
  // 二次 guard: 防 UI/状态错乱时打到后端拿到 403 让用户体验更差
  if (!isAdmin.value) {
    ElMessage.error('仅 admin 可删除公共用例')
    deleteOpen.value = false
    return
  }
  deleteSubmitting.value = true
  try {
    await casesStore.removeCase(deleteTarget.value.case_id)
    ElMessage.success(`已删除公共用例：${deleteTarget.value.case_id}`)
    deleteOpen.value = false
    deleteTarget.value = null
  } catch (e) {
    const err = e as { msg?: string; message?: string }
    ElMessage.error(err.msg || err.message || casesStore.lastError || '删除失败')
  } finally {
    deleteSubmitting.value = false
  }
}

async function onCommand(cmd: string, row: CaseSummary): Promise<void> {
  try {
    switch (cmd) {
      case 'view':
        router.push(`/cases/${encodeURIComponent(row.case_id)}/config`)
        return
      case 'favorite':
      case 'unfavorite':
        await casesStore.toggleFavorite(row.case_id)
        return
      case 'copy':
        renameTarget.value = row
        renameMode.value = 'copy'
        renameDefault.value = row.case_id
        renameExisting.value = casesStore.mineUploads
          .concat(casesStore.publicLibrary)
          .map((c) => c.case_id)
        renameTitle.value = `复制「${row.name || row.case_id}」到我的工作台`
        renameOpen.value = true
        return
      case 'save-as':
        renameTarget.value = row
        renameMode.value = 'save-as'
        renameDefault.value = `${row.case_id}-save`
        renameExisting.value = casesStore.mineUploads.map((c) => c.case_id)
        renameTitle.value = `另存为：${row.name || row.case_id}`
        renameOpen.value = true
        return
      case 'open-yaml': {
        // Spec-1 stub: 跳详情页（实际"打开源 yaml"是 V1+ feature；路由占位先复用详情页）
        router.push(`/cases/${encodeURIComponent(row.case_id)}/config`)
        return
      }
      case 'execute': {
        // Spec-2-2: open execution drawer
        executeTarget.value = row
        executeOpen.value = true
        return
      }
      case 'delete':
        // Admin-only: 后端已校验 is_admin；前端再 guard 一次以免误触
        if (!canDelete(row)) {
          ElMessage.error('仅 admin 可删除公共用例')
          return
        }
        deleteTarget.value = row
        deleteOpen.value = true
        return
    }
  } catch {
    ElMessage.error(casesStore.lastError || `${cmd} 操作失败`)
  }
}
</script>

<style scoped>
.cases-public {
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

.favorite-button {
  padding: 2px;
  color: #cbd5e1;
  font-size: 17px;
  line-height: 1;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.favorite-button:hover,
.favorite-button.active {
  color: #d97706;
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

.audit-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 16px;
  border-radius: 4px;
}

.audit-tag.audited {
  color: #166534;
  background: #dcfce7;
  border: 0.5px solid #bbf7d0;
}

.audit-tag.pending {
  color: #92400e;
  background: #fff7ed;
  border: 0.5px solid #fed7aa;
}

.tag-list {
  display: flex;
  gap: 5px;
  align-items: center;
  min-width: 0;
}

.muted {
  color: var(--color-text-secondary);
  font-size: 11px;
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

:deep(.el-dropdown-menu__item.is-danger:not(.is-disabled)) {
  color: #b91c1c;
}

:deep(.el-dropdown-menu__item.is-danger:not(.is-disabled):hover) {
  color: #fff;
  background: #dc2626;
}

/* ── 删除公共用例二次确认弹窗 ─────────────────────────────────────
   所有 `.del-*` 类集中在 src/styles/_destructive-dialog.css
   (经 main.ts 全局 import)。本地 scoped 块不再重复。 */

@media (max-width: 900px) {
  .cases-public {
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
</style>