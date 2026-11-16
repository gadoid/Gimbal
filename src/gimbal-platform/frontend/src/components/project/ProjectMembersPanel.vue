<!-- ProjectMembersPanel.vue — 项目成员管理面板(从 ProjectsAdmin 抽出;
     项目管理员 ∨ Admin+ 用,canManage 由父级守门;末位项目管理员保护由
     后端 409 兜底,错误内联展示)。2026-11-16 重塑:落 slib 表格 + 添加
     成员收进 Dialog(角色三选带说明);角色仍为行内原生 Select(高频
     快路径);移除走 confirmAction;新增「加入时间」列(addedAt 一直
     有数据未展示)。 -->
<template>
  <div class="panel" data-testid="prj-members-panel">
    <div class="panel-head">
      <h2>{{ project.name }} · 成员 <span class="muted n">{{ members.length }} 人</span></h2>
      <span class="flex-1" />
      <Button size="sm" data-testid="prj-add-open" @click="openAdd">+ 添加成员</Button>
    </div>

    <div v-if="!members.length" class="empty-note">还没有成员。</div>
    <table v-else class="slib-table">
      <thead>
        <tr>
          <th>用户</th>
          <th style="width:9.375rem">角色</th>
          <th style="width:8.75rem">加入时间</th>
          <th style="width:5rem" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in members" :key="m.userId" :data-testid="`prj-member-${m.userId}`">
          <td>
            <div class="m-name">{{ m.displayName || m.username }}</div>
            <div class="m-user mono">{{ m.username }}</div>
          </td>
          <td>
            <!-- 行内改角色 = 快路径(末位管理员保护由后端 409 兜底) -->
            <select :value="m.role" class="role-select" :data-testid="`prj-role-${m.userId}`"
                    @change="changeRole(m, $event)">
              <option v-for="r in ROLES" :key="r" :value="r">{{ PROJECT_ROLE_LABEL[r] }}</option>
            </select>
          </td>
          <td><span class="muted">{{ m.addedAt ? shortDateTime(m.addedAt) : '—' }}</span></td>
          <td>
            <button type="button" class="rm-btn" :data-testid="`prj-rm-${m.userId}`" @click="rm(m)">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="mError" class="err" data-testid="prj-merr">{{ mError }}</p>

    <!-- 添加成员:用户 + 角色(带职责说明) -->
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
import { onMounted, ref } from 'vue'
import {
  listMembers, addMember, patchMember, removeMember,
  type ProjectOut, type ProjectMember, type ProjectRole,
} from '@/api/projects'
import { PROJECT_ROLE_LABEL } from '@/utils/projectRole'
import { getRoster } from '@/api/handoff'
import { shortDateTime } from '@/utils/datetime'
import { confirmAction } from '@/utils/confirmAction'
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

async function load(): Promise<void> {
  members.value = await listMembers(props.project.id)
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

onMounted(async () => {
  await load()
  try {
    roster.value = (await getRoster()).items
  } catch { roster.value = [] }
})
</script>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 0.75rem; }
.panel-head { display: flex; align-items: center; gap: 0.5rem; }
.panel-head h2 { margin: 0; font-size: 0.9375rem; font-weight: 600; color: var(--sl-ink); }
.panel-head .n { font-size: 0.75rem; font-weight: 400; margin-left: 0.25rem; }

.m-name { font-weight: 600; font-size: 0.8125rem; color: var(--sl-ink); }
.m-user { font-size: 0.6875rem; color: var(--sl-ink-3); }
.muted { color: var(--sl-ink-3); }

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
