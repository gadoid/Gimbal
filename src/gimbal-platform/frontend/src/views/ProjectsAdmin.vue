<template>
  <section class="page">
    <header class="head">
      <h1>项目管理</h1>
      <p class="sub">Admin+ 创建项目并指定首个项目管理员;项目管理员管理成员(末位项目管理员受保护)。</p>
      <button type="button" class="btn primary" data-testid="prj-create"
              @click="creating = true">新建项目</button>
    </header>

    <div v-if="creating" class="card form" data-testid="prj-form">
      <label>名称 <input v-model="form.name" data-testid="prj-name" /></label>
      <label>描述 <input v-model="form.description" data-testid="prj-desc" /></label>
      <label>首个项目管理员
        <select v-model="form.firstAdminUserId" data-testid="prj-admin">
          <option v-for="u in roster" :key="u.id" :value="u.id">
            {{ u.display_name }}({{ u.username }})
          </option>
        </select>
      </label>
      <div class="row">
        <button type="button" class="btn primary" data-testid="prj-save"
                @click="save">创建</button>
        <button type="button" class="btn" @click="creating = false">取消</button>
      </div>
      <p v-if="error" class="err" data-testid="prj-err">{{ error }}</p>
    </div>

    <table class="tbl" v-if="projects.length">
      <thead><tr><th>名称</th><th>描述</th><th>成员</th><th>我的角色</th><th></th></tr></thead>
      <tbody>
        <tr v-for="p in projects" :key="p.id" :data-testid="`prj-row-${p.id}`">
          <td>{{ p.name }}</td>
          <td>{{ p.description }}</td>
          <td>{{ p.memberCount }}</td>
          <td>{{ p.myRole ?? '—' }}</td>
          <td>
            <button type="button" class="btn sm" :data-testid="`prj-members-${p.id}`"
                    @click="openMembers(p)">成员</button>
            <button type="button" class="btn sm danger" :data-testid="`prj-del-${p.id}`"
                    @click="del(p)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">暂无项目</p>

    <div v-if="managing" class="card" data-testid="prj-members-panel">
      <header class="row">
        <h2>{{ managing.name }} · 成员</h2>
        <button type="button" class="btn sm" @click="managing = null">关闭</button>
      </header>
      <div class="row add">
        <select v-model="addUserId" data-testid="prj-add-user">
          <option v-for="u in roster" :key="u.id" :value="u.id">{{ u.username }}</option>
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
  </section>
</template>

<script setup lang="ts">
/** ProjectsAdmin.vue — M2a S1.8:项目管理页(Admin+ 建项目/删项目、
 * 项目管理员管成员;末位项目管理员保护由后端 409 兜底,错误内联展示)。 */
import { ref, onMounted } from 'vue'
import {
  listProjects, createProject, deleteProject,
  listMembers, addMember, patchMember, removeMember,
  type ProjectOut, type ProjectMember,
} from '@/api/projects'
import { getRoster } from '@/api/handoff'
const projects = ref<ProjectOut[]>([])
const roster = ref<{ id: number; username: string; display_name: string }[]>([])
const creating = ref(false)
const form = ref({ name: '', description: '', firstAdminUserId: 0 })
const error = ref('')
const managing = ref<ProjectOut | null>(null)
const members = ref<ProjectMember[]>([])
const addUserId = ref(0)
const addRole = ref<'member' | 'admin'>('member')
const mError = ref('')

async function load(): Promise<void> {
  projects.value = await listProjects()
}
async function save(): Promise<void> {
  error.value = ''
  try {
    await createProject({ ...form.value })
    creating.value = false
    form.value = { name: '', description: '', firstAdminUserId: 0 }
    await load()
  } catch (e) {
    error.value = (e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail?.message ?? String(e)
  }
}
async function del(p: ProjectOut): Promise<void> {
  try { await deleteProject(p.id); await load() } catch { /* 409 内容闸 */ await load() }
}
async function openMembers(p: ProjectOut): Promise<void> {
  managing.value = p
  mError.value = ''
  members.value = await listMembers(p.id)
}
async function add(): Promise<void> {
  if (!managing.value || !addUserId.value) return
  mError.value = ''
  try {
    await addMember(managing.value.id, { userId: addUserId.value, role: addRole.value })
    members.value = await listMembers(managing.value.id)
  } catch (e) {
    mError.value = String((e as Error)?.message ?? e)
  }
}
async function changeRole(m: ProjectMember, ev: Event): Promise<void> {
  if (!managing.value) return
  mError.value = ''
  const role = (ev.target as HTMLSelectElement).value as 'admin' | 'member'
  try {
    await patchMember(managing.value.id, m.userId, role)
    m.role = role
  } catch {
    mError.value = '改角色失败(末位项目管理员不能降级?)'
  }
}
async function rm(m: ProjectMember): Promise<void> {
  if (!managing.value) return
  mError.value = ''
  try {
    await removeMember(managing.value.id, m.userId)
    members.value = await listMembers(managing.value.id)
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
.page { padding: 1rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.head { display: flex; align-items: baseline; gap: 1rem; }
.sub { color: #64748b; font-size: 0.85rem; flex: 1; }
.card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.form { max-width: 28rem; }
.form label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; }
.row { display: flex; gap: 0.5rem; align-items: center; }
.add { margin-bottom: 0.5rem; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.tbl th, .tbl td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eef2f7; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem; background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.sm { padding: 0.15rem 0.5rem; font-size: 0.78rem; }
.btn.danger { color: #dc2626; border-color: #fca5a5; }
.err { color: #dc2626; font-size: 0.8rem; }
.empty { color: #94a3b8; }
</style>
