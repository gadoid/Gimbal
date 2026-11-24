<!-- ProjectMembersPanel.vue — 项目成员管理面板(从 ProjectsAdmin 抽出;
     项目管理员 ∨ Admin+ 用,canManage 由父级守门;末位项目管理员保护由
     后端 409 兜底,错误内联展示)。重塑:落 slib 表格 + 添加
     成员收进 Dialog(角色三选带说明);角色仍为行内原生 Select(高频
     快路径);移除走 confirmAction;新增「加入时间」列(addedAt 一直
     有数据未展示)。
     按 stitch 原型重排:顶部四张统计卡(总成员/管理员/
     开发者/只读 —— 成员列表客户端聚合)+ 角色筛选 Tab + 搜索(纯前端
     过滤);表格列面:成员(头像字 + 姓名 + 用户名)/ 角色徽章 / 加入
     时间 / 操作。原型的工号/部门/负责资产数量/最近活跃/CSV 导出/用户
     组批量导入/四级角色后端无字段,不渲染(排期见
     docs/project-detail-stitch-plan.md)。 -->
<template>
  <div class="panel" data-testid="prj-members-panel">
    <!-- ══ 原型 _5 · 成员统计卡(客户端聚合)═══════════════════ -->
    <div class="mem-stats" data-testid="prj-mem-stats">
      <div class="mem-stat">
        <span class="k">项目总成员</span>
        <span class="v">{{ members.length }}</span>
        <span class="d">位协作成员</span>
      </div>
      <div class="mem-stat">
        <span class="k">管理员</span>
        <span class="v">{{ roleCount('admin') }}</span>
        <span class="d">成员与配置全量管辖</span>
      </div>
      <div class="mem-stat">
        <span class="k">开发者</span>
        <span class="v">{{ roleCount('member') }}</span>
        <span class="d">场景构建与调试</span>
      </div>
      <div class="mem-stat">
        <span class="k">只读</span>
        <span class="v">{{ roleCount('user') }}</span>
        <span class="d">查看与执行</span>
      </div>
    </div>

    <div class="panel-head">
      <div class="role-tabs" data-testid="prj-mem-role-tabs">
        <button
          v-for="r in roleFilters"
          :key="r.key"
          type="button"
          class="rtab"
          :class="{ on: roleFilter === r.key }"
          :data-testid="`prj-mem-filter-${r.key}`"
          @click="roleFilter = r.key"
        >{{ r.label }}<span class="rtn">{{ r.key ? roleCount(r.key as ProjectRole) : members.length }}</span></button>
      </div>
      <input
        v-model="q"
        class="mem-search"
        placeholder="按姓名 / 用户名搜索"
        data-testid="prj-mem-q"
      />
      <span class="flex-1" />
      <!-- 权限清单 CSV(全量成员,不受前端筛选影响;
           papaparse unparse + BOM,Excel 打开中文不乱码) -->
      <Button v-if="members.length" variant="outline" size="sm" data-testid="prj-mem-export"
              @click="exportCsv">导出 CSV</Button>
      <Button size="sm" data-testid="prj-add-open" @click="openAdd">+ 添加成员</Button>
    </div>

    <div v-if="loadError" class="empty-note" data-testid="prj-mem-error">
      成员列表加载失败:{{ loadError }}
      <button type="button" class="svc-link" @click="reload">重试</button>
    </div>
    <div v-else-if="!members.length" class="empty-note">还没有成员。</div>
    <div v-else-if="!shownMembers.length" class="empty-note">没有匹配的成员 — 换个关键词或角色筛选。</div>
    <table v-else class="slib-table">
      <thead>
        <tr>
          <th>成员</th>
          <th style="width:9.375rem">项目角色</th>
          <!-- 负责资产数:owner 归属聚合 -->
          <th style="width:5.625rem" class="c-center">场景数</th>
          <th style="width:5.625rem" class="c-center">用例集数</th>
          <th style="width:8.75rem">加入时间</th>
          <th style="width:5rem" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in shownMembers" :key="m.userId" :data-testid="`prj-member-${m.userId}`">
          <td>
            <div class="m-cell">
              <span class="m-avatar" aria-hidden="true">{{ memberInitial(m) }}</span>
              <span>
                <span class="m-name">{{ m.displayName || m.username }}</span>
                <span class="m-user mono">{{ m.username }}</span>
              </span>
            </div>
          </td>
          <td>
            <!-- 行内改角色 = 快路径(末位管理员保护由后端 409 兜底) -->
            <span class="role-badge" :class="m.role" :data-testid="`prj-role-badge-${m.userId}`">
              {{ projectRoleLabel(m.role) }}
            </span>
            <select :value="m.role" class="role-select" :data-testid="`prj-role-${m.userId}`"
                    aria-label="改角色" @change="changeRole(m, $event)">
              <option v-for="r in ROLES" :key="r" :value="r">{{ PROJECT_ROLE_LABEL[r] }}</option>
            </select>
          </td>
          <td class="c-center">
            <span class="muted" :data-testid="`prj-mem-scen-${m.userId}`">{{ m.scenarioCount ?? 0 }}</span>
          </td>
          <td class="c-center">
            <span class="muted" :data-testid="`prj-mem-suite-${m.userId}`">{{ m.suiteCount ?? 0 }}</span>
          </td>
          <td><span class="muted">{{ m.addedAt ? shortDateTime(m.addedAt) : '—' }}</span></td>
          <td>
            <button type="button" class="rm-btn" :data-testid="`prj-rm-${m.userId}`" @click="rm(m)">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="mError" class="err" data-testid="prj-merr">{{ mError }}</p>

    <!-- 添加成员:用户 + 角色(带职责说明);原型 _5 的部门多选/通知
         开关后端无部门与通知配置,不做(排期) -->
    <Dialog :open="addOpen" @update:open="addOpen = $event">
      <DialogContent class="max-w-[27.5rem]">
        <DialogHeader>
          <DialogTitle>添加成员</DialogTitle>
        </DialogHeader>
        <div class="form">
          <label class="field">
            <span class="field-label">用户</span>
            <select v-model="addUserId" class="role-select w-full" data-testid="prj-add-user">
              <option value="0" disabled>选择用户…</option>
              <option v-for="u in roster" :key="u.id" :value="u.id">
                {{ u.display_name }}({{ u.username }})
              </option>
            </select>
          </label>
          <div class="field">
            <span class="field-label">角色</span>
            <label v-for="r in ROLES" :key="r" class="role-option">
              <input
                type="radio" name="prj-add-role" :value="r"
                :checked="addRole === r" :data-testid="`prj-add-role-${r}`"
                @change="addRole = r"
              />
              <span>
                <b>{{ PROJECT_ROLE_LABEL[r] }}</b>
                <span class="muted role-desc">{{ ROLE_DESC[r] }}</span>
              </span>
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="addOpen = false">取消</Button>
          <Button :disabled="!addUserId || adding" data-testid="prj-add" @click="add">
            {{ adding ? '添加中…' : '添加' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Papa from 'papaparse'
import {
  listMembers, addMember, patchMember, removeMember,
  type ProjectOut, type ProjectMember, type ProjectRole,
} from '@/api/projects'
import { PROJECT_ROLE_LABEL, projectRoleLabel } from '@/utils/projectRole'
import { getRoster } from '@/api/handoff'
import { shortDateTime } from '@/utils/datetime'
import { confirmAction } from '@/utils/confirmAction'
import { downloadFile } from '@/utils/download'
import { toast } from '@/utils/toast'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const props = defineProps<{ project: ProjectOut }>()
const emit = defineEmits<{ changed: [] }>()

const members = ref<ProjectMember[]>([])
const roster = ref<{ id: number; username: string; display_name: string }[]>([])
const mError = ref('')

// M2b Q1:项目用户 = 只读 + 执行(不能新建 / 修改 / 提升)
const ROLES: ProjectRole[] = ['admin', 'member', 'user']
const ROLE_DESC: Record<ProjectRole, string> = {
  admin: '管理成员与配置、签发项目令牌',
  member: '在项目内新建与修改内容',
  user: '只读 + 执行(不能改内容)',
}

// ── 原型 _5:角色筛选 + 搜索(纯前端过滤)────────────────────────
const roleFilter = ref('')
const q = ref('')
const roleFilters = [
  { key: '', label: '全部' },
  { key: 'admin', label: '管理员' },
  { key: 'member', label: '开发者' },
  { key: 'user', label: '只读' },
]

function roleCount(role: ProjectRole): number {
  return members.value.filter((m) => m.role === role).length
}

const shownMembers = computed(() => {
  let out = members.value
  if (roleFilter.value) out = out.filter((m) => m.role === roleFilter.value)
  const kw = q.value.trim().toLowerCase()
  if (kw) {
    out = out.filter((m) =>
      (m.displayName || '').toLowerCase().includes(kw)
      || m.username.toLowerCase().includes(kw))
  }
  return out
})

function memberInitial(m: ProjectMember): string {
  return (m.displayName || m.username || '?').trim().slice(0, 1).toUpperCase()
}

const addOpen = ref(false)
const addUserId = ref(0)
const addRole = ref<ProjectRole>('member')
const adding = ref(false)

function openAdd(): void {
  addUserId.value = 0
  addRole.value = 'member'
  mError.value = ''
  addOpen.value = true
}

/** 首载/刷新:失败显式呈现(此前裸 await → unhandled rejection +
 *  「还没有成员」假空态,403/网络错与真空池不可区分) */
const loadError = ref('')

async function load(): Promise<void> {
  try {
    members.value = await listMembers(props.project.id)
    loadError.value = ''
  } catch (e) {
    loadError.value = String((e as Error)?.message ?? e)
  }
}

async function reload(): Promise<void> {
  await load()
}

/** CSV 公式注入防护:以 = + - @ 或制表符/回车开头的单元格前缀单引号
 *  (Excel/Sheets 会把这类值当公式执行;姓名/用户名是用户可控串) */
function csvSafe(v: string): string {
  return /^[=+\-@\t\r]/.test(v) ? `'${v}` : v
}

/** 权限清单 CSV:导出全量成员(不受前端角色/
 *  搜索筛选影响 —— 筛选是浏览态,清单是台账);BOM 头保 Excel 中文。 */
function exportCsv(): void {
  const rows = members.value.map((m) => ({
    姓名: csvSafe(m.displayName || m.username),
    用户名: csvSafe(m.username),
    项目角色: projectRoleLabel(m.role) || m.role,
    场景数: m.scenarioCount ?? 0,
    用例集数: m.suiteCount ?? 0,
    加入时间: m.addedAt ? shortDateTime(m.addedAt) : '',
  }))
  const csv = '\uFEFF' + Papa.unparse(rows)
  const date = new Date().toISOString().slice(0, 10)
  const safeName = props.project.name.replace(/[\\/:*?"<>|]/g, '_')
  downloadFile(`项目成员权限清单-${safeName}-${date}.csv`, csv,
    'text/csv;charset=utf-8')
  toast.success(`已导出 ${rows.length} 位成员的权限清单`)
}

async function add(): Promise<void> {
  if (!addUserId.value) return
  mError.value = ''
  adding.value = true
  try {
    await addMember(props.project.id, { userId: addUserId.value, role: addRole.value })
    addUserId.value = 0
    addOpen.value = false
    toast.success('成员已添加')
    await load()
    emit('changed')
  } catch (e) {
    mError.value = String((e as Error)?.message ?? e)
  } finally {
    adding.value = false
  }
}

async function changeRole(m: ProjectMember, ev: Event): Promise<void> {
  mError.value = ''
  const role = (ev.target as HTMLSelectElement).value as ProjectRole
  try {
    await patchMember(props.project.id, m.userId, role)
    m.role = role
    toast.success(`${m.displayName || m.username} 已改为${PROJECT_ROLE_LABEL[role]}`)
    emit('changed')
  } catch {
    mError.value = '改角色失败(末位项目管理员不能降级?)'
  }
}

async function rm(m: ProjectMember): Promise<void> {
  mError.value = ''
  const ok = await confirmAction(
    `将 ${m.displayName || m.username}(${m.username})移出项目?TA 将失去项目内容的访问权(可重新添加)。`,
    '移除成员',
    { danger: true, confirmButtonText: '移除' },
  )
  if (!ok) return
  try {
    await removeMember(props.project.id, m.userId)
    toast.success(`已移除 ${m.displayName || m.username}`)
    await load()
    emit('changed')
  } catch {
    mError.value = '移除失败(末位项目管理员不能移除?)'
  }
}

async function loadAll(): Promise<void> {
  await load()
  try {
    roster.value = (await getRoster()).items
  } catch { roster.value = [] }
}

onMounted(loadAll)
// 跨项目直达(同路由复用组件,如浏览器回退 /projects/1?tab=members →
// /projects/2)→ 重载,不再展示上一项目的成员/名册
watch(() => props.project.id, () => void loadAll())
</script>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 0.875rem; }

/* ── 原型 _5 · 统计卡 ─────────────────────────────────────────── */
.mem-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11.25rem, 1fr));
  gap: 0.75rem;
}
.mem-stat {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.75rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
}
.mem-stat .k { font-size: 0.71875rem; color: var(--sl-ink-3); }
.mem-stat .v { font-size: 1.375rem; font-weight: 600; color: var(--sl-ink); font-variant-numeric: tabular-nums; }
.mem-stat .d { font-size: 0.6875rem; color: var(--sl-ink-3); }

/* ── 工具条:角色筛选 Tab + 搜索 ───────────────────────────────── */
.panel-head { display: flex; align-items: center; gap: 0.625rem; flex-wrap: wrap; }
.role-tabs {
  display: flex;
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  overflow: hidden;
}
.rtab {
  padding: 0.375rem 0.6875rem;
  font-size: 0.78125rem;
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--sl-ink-2);
  border-right: 1px solid var(--sl-line);
  white-space: nowrap;
}
.rtab:last-child { border-right: none; }
.rtab:hover { color: var(--sl-ink); }
.rtab.on { background: var(--sl-accent-soft); color: var(--sl-accent); font-weight: 600; }
.rtn {
  margin-left: 0.25rem;
  font-size: 0.6875rem;
  color: var(--sl-ink-3);
  font-variant-numeric: tabular-nums;
}
.rtab.on .rtn { color: var(--sl-accent); }
.mem-search {
  width: 14.375rem;
  padding: 0.4375rem 0.625rem;
  font-size: 0.78125rem;
  border-radius: 0.5rem;
  border: 1px solid var(--sl-line);
  background: transparent;
  color: inherit;
}
.mem-search:focus { outline: none; border-color: var(--sl-accent); }

/* ── 成员表 ────────────────────────────────────────────────────── */
.m-cell { display: flex; align-items: center; gap: 0.5rem; }
.m-avatar {
  flex: none;
  width: 1.875rem; height: 1.875rem;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 600; color: var(--sl-accent);
  background: var(--sl-accent-soft);
  border-radius: 50%;
}
.m-name { display: block; font-weight: 600; font-size: 0.8125rem; color: var(--sl-ink); }
.m-user { display: block; font-size: 0.6875rem; color: var(--sl-ink-3); }
.muted { color: var(--sl-ink-3); }

.role-badge {
  display: inline-block;
  margin-right: 0.375rem;
  font-size: 0.71875rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  border: 1px solid var(--sl-line);
  background: var(--soft-neutral-bg);
  color: var(--sl-ink-2);
}
.role-badge.admin { color: var(--sl-accent); border-color: var(--sl-accent-soft-border, var(--sl-accent)); background: var(--sl-accent-soft); }
.role-badge.member { color: var(--sl-ok); border-color: var(--sl-ok); background: var(--sl-ok-soft); }

.role-select {
  padding: 0.25rem 0.5rem;
  font-size: 0.78125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  cursor: pointer;
}
.role-select:focus { border-color: var(--sl-accent); outline: none; }

.rm-btn {
  padding: 0.1875rem 0.625rem;
  font-size: 0.75rem;
  color: var(--sl-bad);
  background: none;
  border: 1px solid var(--sv-bad-line, var(--sl-bad));
  border-radius: 0.375rem;
  cursor: pointer;
}
.rm-btn:hover { background: var(--sl-bad-soft); }

.err { color: var(--sl-bad); font-size: 0.8125rem; margin: 0; }
.empty-note { color: var(--sl-ink-3); font-size: 0.8125rem; }

.form { display: flex; flex-direction: column; gap: 0.875rem; }
.field { display: flex; flex-direction: column; gap: 0.375rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.role-option {
  display: flex; align-items: flex-start; gap: 0.5rem;
  padding: 0.4375rem 0.5625rem;
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  cursor: pointer;
}
.role-option:has(input:checked) { border-color: var(--sl-accent); background: var(--sl-accent-soft); }
.role-option input { margin-top: 0.1875rem; accent-color: var(--sl-accent); }
.role-option b { font-size: 0.78125rem; color: var(--sl-ink); }
.role-desc { display: block; font-size: 0.6875rem; }
</style>
