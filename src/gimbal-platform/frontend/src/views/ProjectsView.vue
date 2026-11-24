<!-- ProjectsView.vue — M2a S7.1:项目列表页(/projects,一级入口)。
     重塑:落全站 slib 设计系统(PageHead + slib-toolbar +
     卡片网格)。公共项目置顶(后端排序保证);卡片 = 名称/角色 + 描述 +
     统计行(场景/用例集/集成任务,列表端点批量补齐)+ 默认环境名 +
     ⋯ 菜单(编辑信息/成员管理/删除);整卡可点进详情,菜单事件止冒泡。
     Admin+ 的创建面收进 Dialog(原内联表单退役)。 -->
<template>
  <section class="slib">
    <PageHead
      icon="layers"
      title="项目"
      subtitle="公共项目置顶 —— 团队共享的场景与用例集都在其中;普通项目按成员可见。"
      :count="projects.length ? `${projects.length} 个项目` : undefined"
      :meta="metaText"
    />

    <div class="slib-toolbar">
      <input
        v-model="query"
        class="slib-search"
        placeholder="搜索项目名 / 描述"
        data-testid="prj-search"
      />
      <span class="svc-stats tight" data-testid="prj-view-group">
        <button
          v-for="v in VIEW_FILTERS"
          :key="v.key"
          type="button"
          class="svc-chip"
          :class="{ on: view === v.key }"
          :data-testid="`prj-view-${v.key}`"
          @click="view = v.key"
        >{{ v.label }}<span v-if="viewCounts[v.key]" class="n">{{ viewCounts[v.key] }}</span></button>
      </span>
      <button
        v-if="canCreate"
        type="button"
        class="slib-create"
        data-testid="prj-create"
        @click="openCreate"
      >+ 新建项目</button>
    </div>

    <!-- 骨架(列表页统一:卡位 shimmer,不再用一行文字) -->
    <div v-if="loading" class="proj-grid">
      <div v-for="i in 4" :key="i" class="proj-card skel" :data-testid="`prj-skel-${i}`" />
    </div>

    <div v-else-if="filtered.length" class="proj-grid">
      <div
        v-for="p in filtered"
        :key="p.id"
        class="proj-card"
        :data-testid="`prj-card-${p.id}`"
        @click="open(p)"
      >
        <div class="pc-top">
          <span class="pc-name" :title="p.name">{{ p.name }}</span>
          <span v-if="p.kind === 'public'" class="pc-badge pub" data-testid="prj-public-badge">公共</span>
          <span v-else-if="p.myRole === 'admin'" class="pc-badge">管理</span>
          <span v-else-if="p.myRole === 'user'" class="pc-badge">项目用户</span>
          <span v-else-if="p.myRole" class="pc-badge">成员</span>
          <span class="flex-1" />
          <!-- 整卡可点;菜单区止冒泡,点菜单不进详情 -->
          <span v-if="hasCardMenu(p)" class="pc-menu" @click.stop>
            <DropdownMenu>
              <DropdownMenuTrigger class="more-btn" aria-label="项目操作" :data-testid="`prj-more-${p.id}`">⋯</DropdownMenuTrigger>
              <DropdownMenuContent align="end" class="sl-menu">
                <DropdownMenuItem
                  v-if="p.canManage && p.kind !== 'public'"
                  class="sl-menu-item" :data-testid="`prj-edit-${p.id}`"
                  @click="openEdit(p)"
                >编辑信息</DropdownMenuItem>
                <DropdownMenuItem
                  v-if="p.canManage && p.kind !== 'public'"
                  class="sl-menu-item" :data-testid="`prj-members-${p.id}`"
                  @click="openMembers(p)"
                >成员管理</DropdownMenuItem>
                <DropdownMenuItem
                  v-if="canCreate && p.kind !== 'public'"
                  class="sl-menu-item danger" :data-testid="`prj-del-${p.id}`"
                  @click="removeProject(p)"
                >删除项目</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </span>
        </div>
        <p class="pc-desc">{{ p.description || '—' }}</p>
        <div class="pc-stats">
          <span class="pc-stat"><b>{{ p.scenarioCount ?? '—' }}</b>场景</span>
          <span class="pc-sep" />
          <span class="pc-stat"><b>{{ p.suiteCount ?? '—' }}</b>用例集</span>
          <span class="pc-sep" />
          <span class="pc-stat"><b>{{ p.taskCount ?? '—' }}</b>集成任务</span>
        </div>
        <div class="pc-foot">
          <span class="pc-env">默认环境 {{ p.defaultEnvironmentName || '未设置' }}</span>
          <span class="flex-1" />
          <span class="pc-members">{{ p.memberCount }} 名成员</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-cta" data-testid="prj-empty">
      <p>{{ query.trim() || view !== 'all' ? '没有匹配的项目' : '暂无可见项目' }}</p>
      <Button v-if="canCreate && !query.trim() && view === 'all'" variant="outline" size="sm" @click="openCreate">+ 新建项目</Button>
    </div>

    <!-- ── 新建项目(Admin+;Dialog + 字段级校验)────────────────── -->
    <Dialog :open="createOpen" @update:open="createOpen = $event">
      <DialogContent class="max-w-[30rem]">
        <DialogHeader>
          <DialogTitle>新建项目</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onCreate">
          <FormField v-slot="{ componentField }" name="name">
            <FormItem>
              <FormLabel>名称<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="项目名(≤128 字)" data-testid="prj-name" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="description">
            <FormItem>
              <FormLabel>描述</FormLabel>
              <FormControl>
                <Textarea v-bind="componentField" rows="3" placeholder="一句话说明项目的用途(可空)"
                  data-testid="prj-desc" class="resize-none" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="adminId">
            <FormItem>
              <FormLabel>首个项目管理员<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Select v-bind="componentField">
                  <SelectTrigger data-testid="prj-admin"><SelectValue placeholder="选择用户…" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="u in roster" :key="u.id" :value="String(u.id)">
                      {{ u.display_name }}({{ u.username }})
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormDescription>项目建好后由 TA 管理成员与配置;须为在职、非系统用户</FormDescription>
              <FormMessage />
            </FormItem>
          </FormField>

          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="createOpen = false">取消</Button>
            <Button type="submit" :disabled="creating" data-testid="prj-save">
              {{ creating ? '创建中…' : '创建' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- 编辑信息(与详情页头共用件) -->
    <ProjectEditDialog
      :open="editOpen"
      :project="editing"
      @update:open="editOpen = $event"
      @saved="reload"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toTypedSchema } from '@/utils/zod-typed-schema'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import {
  listProjects, createProject, deleteProject, type ProjectOut,
} from '@/api/projects'
import { getRoster } from '@/api/handoff'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import ProjectEditDialog from '@/components/project/ProjectEditDialog.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription } from '@/components/ui/form'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const auth = useAuthStore()
const router = useRouter()
const canCreate = computed(() => auth.can('ops.write'))

const projects = ref<ProjectOut[]>([])
const loading = ref(true)

// ── 工具条:搜索(客户端)+ 视角 chips ──────────────────────────
const query = ref('')
type ViewKey = 'all' | 'managing' | 'mine' | 'public'
const VIEW_FILTERS: Array<{ key: ViewKey; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'managing', label: '我管理' },
  { key: 'mine', label: '我参与' },
  { key: 'public', label: '公共' },
]
const view = ref<ViewKey>('all')

const viewCounts = computed<Record<ViewKey, number>>(() => ({
  all: projects.value.length,
  managing: projects.value.filter((p) => p.kind !== 'public' && p.myRole === 'admin').length,
  mine: projects.value.filter((p) => p.kind !== 'public' && p.myRole && p.myRole !== 'admin').length,
  public: projects.value.filter((p) => p.kind === 'public').length,
}))

/** 视角 + 搜索都在端上滤(项目量级小;后端序[公共置顶]保留) */
const filtered = computed(() => {
  const kw = query.value.trim().toLowerCase()
  return projects.value.filter((p) => {
    if (view.value === 'managing' && !(p.kind !== 'public' && p.myRole === 'admin')) return false
    if (view.value === 'mine' && !(p.kind !== 'public' && p.myRole && p.myRole !== 'admin')) return false
    if (view.value === 'public' && p.kind !== 'public') return false
    if (kw && !(`${p.name}${p.description ?? ''}`.toLowerCase().includes(kw))) return false
    return true
  })
})

const metaText = computed(() => {
  if (!projects.value.length) return undefined
  const c = viewCounts.value
  return `${c.managing} 个我管理 · ${c.mine} 个我参与 · ${c.public} 个公共`
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    projects.value = await listProjects()
  } finally {
    loading.value = false
  }
}

function open(p: ProjectOut): void {
  void router.push(`/projects/${p.id}`)
}

// ── 卡片 ⋯ 菜单(编辑/成员/删除;公共项目后端保护,入口不展示)─────
function hasCardMenu(p: ProjectOut): boolean {
  return Boolean((p.canManage && p.kind !== 'public') || (canCreate.value && p.kind !== 'public'))
}

const editOpen = ref(false)
const editing = ref<ProjectOut | null>(null)

function openEdit(p: ProjectOut): void {
  editing.value = p
  editOpen.value = true
}

function openMembers(p: ProjectOut): void {
  void router.push(`/projects/${p.id}?tab=members`)
}

async function removeProject(p: ProjectOut): Promise<void> {
  const ok = await confirmAction(
    `删除项目「${p.name}」?成员关系随项目消失;项目内有场景 / 用例集 / 集成任务时会被拒绝,须先清空或迁走。`,
    '删除项目',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await deleteProject(p.id)
    toast.success(`项目已删除:${p.name}`)
    await reload()
  } catch (e) {
    showError('删除项目', undefined, (e as Error).message)
  }
}

// ── 新建(Admin+)──────────────────────────────────────────────
const createOpen = ref(false)
const creating = ref(false)
const roster = ref<Array<{ id: number; username: string; display_name: string }>>([])

const schema = toTypedSchema(z.object({
  name: z.string().min(1, '请输入项目名').max(128, '最多 128 字'),
  description: z.string().max(2000, '最多 2000 字'),
  // 管理员选值是字符串 id,提交时转 number
  adminId: z.string().min(1, '请选择首个项目管理员'),
}))

const { handleSubmit, resetForm } = useForm({
  validationSchema: schema,
  initialValues: { name: '', description: '', adminId: '' },
})

function openCreate(): void {
  resetForm({ values: { name: '', description: '', adminId: '' } })
  createOpen.value = true
}

const onCreate = handleSubmit(async (values) => {
  if (creating.value) return
  creating.value = true
  try {
    const created = await createProject({
      name: values.name,
      description: values.description,
      firstAdminUserId: Number(values.adminId),
    })
    createOpen.value = false
    toast.success(`项目已创建:${created.name}`)
    await router.push(`/projects/${created.id}?tab=members`)
  } catch (e) {
    showError('创建项目', undefined, (e as Error).message)
  } finally {
    creating.value = false
  }
})

onMounted(async () => {
  await reload()
  if (canCreate.value) {
    try { roster.value = (await getRoster()).items } catch { roster.value = [] }
  }
})
</script>

<style scoped>
/* ── 项目卡片网格(信息密度升级:统计行 + 底栏,整卡可点)────────── */
.proj-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
  align-items: stretch;
}
.proj-card {
  display: flex;
  flex-direction: column;
  gap: 0.4375rem;
  padding: 0.75rem 0.875rem 0.625rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.04);
  cursor: pointer;
  min-width: 0;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.proj-card:hover {
  border-color: var(--sl-accent);
  box-shadow: 0 2px 6px rgba(16, 21, 28, 0.08);
}
.proj-card.skel {
  height: 8.75rem;
  cursor: default;
  background: linear-gradient(
    100deg,
    var(--sl-canvas) 40%,
    var(--surface-raised) 50%,
    var(--sl-canvas) 60%
  );
  background-size: 200% 100%;
  animation: skel-slide 1.2s ease-in-out infinite;
}
@keyframes skel-slide { to { background-position: -200% 0; } }

.pc-top { display: flex; align-items: center; gap: 0.375rem; min-width: 0; }
.pc-name {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--sl-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-badge {
  flex: none;
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--soft-neutral-bg);
  color: var(--color-text-strong);
  border: 1px solid var(--sl-line);
}
.pc-badge.pub {
  background: var(--sl-accent-soft);
  color: var(--sl-accent);
  border-color: rgb(47 111 237 / 30%);
}
.pc-menu { flex: none; display: inline-flex; }

.pc-desc {
  margin: 0;
  font-size: 0.75rem;
  color: var(--sl-ink-2);
  line-height: 1.5;
  min-height: 2.25rem;                 /* 空描述也占两行,统计行对齐 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pc-stats { display: flex; align-items: center; gap: 0.5rem; }
.pc-stat { font-size: 0.6875rem; color: var(--sl-ink-3); white-space: nowrap; }
.pc-stat b {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--sl-ink);
  margin-right: 0.25rem;
}
.pc-sep { width: 0.0625rem; height: 0.75rem; background: var(--sl-divider); }

.pc-foot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: auto;
  padding-top: 0.375rem;
  border-top: 1px solid var(--sl-divider);
  font-size: 0.6875rem;
  color: var(--sl-ink-3);
}
.pc-members { white-space: nowrap; }

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}
</style>
