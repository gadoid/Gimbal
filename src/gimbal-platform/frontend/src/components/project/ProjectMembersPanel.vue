<!-- ProjectMembersPanel.vue — M2a S7.1:项目成员管理面板(从
     ProjectsAdmin 抽出;项目管理员 ∨ Admin+ 用,canManage 由父级守门;
     末位项目管理员保护由后端 409 兜底,错误内联展示)。 -->
<template>
  <div class="card" data-testid="prj-members-panel">
    <header class="row">
      <h2>{{ project.name }} · 成员</h2>
      <span class="muted">{{ members.length }} 人</span>
    </header>
    <div class="row add">
      <select v-model="addUserId" data-testid="prj-add-user">
        <option value="0" disabled>选择用户…</option>
        <option v-for="u in roster" :key="u.id" :value="u.id">
          {{ u.display_name }}({{ u.username }})
        </option>
      </select>
      <select v-model="addRole" data-testid="prj-add-role">
        <option value="member">member</option>
        <option value="admin">admin</option>
      </select>
      <button type="button" class="btn sm primary" data-testid="prj-add"
              @click="add">添加</button>
    </div>
    <table class="tbl">
      <thead><tr><th>用户</th><th>角色</th><th></th></tr></thead>
      <tbody>
        <tr v-for="m in members" :key="m.userId" :data-testid="`prj-member-${m.userId}`">
          <td>{{ m.displayName }}({{ m.username }})</td>
          <td>
            <select :value="m.role" :data-testid="`prj-role-${m.userId}`"
                    @change="changeRole(m, $event)">
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
          </td>
          <td>
            <button type="button" class="btn sm danger"
                    :data-testid="`prj-rm-${m.userId}`" @click="rm(m)">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="mError" class="err" data-testid="prj-merr">{{ mError }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  listMembers, addMember, patchMember, removeMember,
  type ProjectOut, type ProjectMember,
} from '@/api/projects'
import { getRoster } from '@/api/handoff'

const props = defineProps<{ project: ProjectOut }>()
const emit = defineEmits<{ changed: [] }>()

const members = ref<ProjectMember[]>([])
const roster = ref<{ id: number; username: string; display_name: string }[]>([])
const addUserId = ref(0)
const addRole = ref<'member' | 'admin'>('member')
const mError = ref('')

async function load(): Promise<void> {
  members.value = await listMembers(props.project.id)
}
async function add(): Promise<void> {
  if (!addUserId.value) return
  mError.value = ''
  try {
    await addMember(props.project.id, { userId: addUserId.value, role: addRole.value })
    addUserId.value = 0
    await load()
    emit('changed')
  } catch (e) {
    mError.value = String((e as Error)?.message ?? e)
  }
}
async function changeRole(m: ProjectMember, ev: Event): Promise<void> {
  mError.value = ''
  const role = (ev.target as HTMLSelectElement).value as 'admin' | 'member'
  try {
    await patchMember(props.project.id, m.userId, role)
    m.role = role
    emit('changed')
  } catch {
    mError.value = '改角色失败(末位项目管理员不能降级?)'
  }
}
async function rm(m: ProjectMember): Promise<void> {
  mError.value = ''
  try {
    await removeMember(props.project.id, m.userId)
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
.card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.row { display: flex; gap: 0.5rem; align-items: center; }
.add { margin-bottom: 0.5rem; }
.muted { color: #94a3b8; font-size: 0.8rem; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.tbl th, .tbl td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eef2f7; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem; background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.sm { padding: 0.15rem 0.5rem; font-size: 0.78rem; }
.btn.danger { color: #dc2626; border-color: #fca5a5; }
.err { color: #dc2626; font-size: 0.8rem; }
</style>
