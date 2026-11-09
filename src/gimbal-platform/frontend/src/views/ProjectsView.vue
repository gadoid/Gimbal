<!-- ProjectsView.vue — M2a S7.1:项目列表页(/projects,一级入口)。
     公共项目置顶(后端排序保证);我参与的普通项目随后;Admin+ 有
     「新建项目」(原 /admin/projects 的创建面收编进来)。点卡片进
     /projects/:id 详情(页签:场景/用例集/集成任务/成员)。 -->
<template>
  <section class="page">
    <header class="head">
      <h1>项目</h1>
      <p class="sub">公共项目置顶 —— 团队共享的场景与用例集都在其中;普通项目按成员可见。</p>
      <button
        v-if="auth.can('ops.write')"
        type="button"
        class="btn primary"
        data-testid="prj-create"
        @click="creating = !creating"
      >新建项目</button>
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
        <button type="button" class="btn primary" data-testid="prj-save" @click="save">创建</button>
        <button type="button" class="btn" @click="creating = false">取消</button>
      </div>
      <p v-if="error" class="err" data-testid="prj-err">{{ error }}</p>
    </div>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else class="grid">
      <router-link
        v-for="p in projects"
        :key="p.id"
        class="card proj"
        :to="`/projects/${p.id}`"
        :data-testid="`prj-card-${p.id}`"
      >
        <div class="row-title">
          <span class="name">{{ p.name }}</span>
          <span v-if="p.kind === 'public'" class="badge pub" data-testid="prj-public-badge">公共</span>
          <span v-else-if="p.myRole === 'admin'" class="badge">管理</span>
          <span v-else-if="p.myRole === 'user'" class="badge">项目用户</span>
          <span v-else-if="p.myRole" class="badge">成员</span>
        </div>
        <p class="desc">{{ p.description || '—' }}</p>
        <p class="meta">{{ p.memberCount }} 名成员<template v-if="p.kind !== 'public' && p.defaultEnvironmentId"> · 默认环境 {{ p.defaultEnvironmentId }}</template></p>
      </router-link>
    </div>
    <p v-if="!loading && !projects.length" class="empty">暂无可见项目</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listProjects, createProject, type ProjectOut } from '@/api/projects'
import { getRoster } from '@/api/handoff'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

const auth = useAuthStore()
const router = useRouter()
const projects = ref<ProjectOut[]>([])
const roster = ref<{ id: number; username: string; display_name: string }[]>([])
const loading = ref(true)
const creating = ref(false)
const form = ref({ name: '', description: '', firstAdminUserId: 0 })
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  try {
    projects.value = await listProjects()
  } finally {
    loading.value = false
  }
}
async function save(): Promise<void> {
  error.value = ''
  try {
    const created = await createProject({ ...form.value })
    creating.value = false
    form.value = { name: '', description: '', firstAdminUserId: 0 }
    toast.success(`项目已创建:${created.name}`)
    await router.push(`/projects/${created.id}?tab=members`)
  } catch (e) {
    error.value = (e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail?.message ?? String(e)
  }
}
onMounted(async () => {
  await load()
  if (auth.can('ops.write')) {
    try { roster.value = (await getRoster()).items } catch { roster.value = [] }
  }
})
</script>

<style scoped>
.page { padding: 1rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.head { display: flex; align-items: baseline; gap: 1rem; }
.sub { color: #64748b; font-size: 0.85rem; flex: 1; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.75rem; }
.card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.85rem 1rem; background: #fff; color: inherit; text-decoration: none; display: flex; flex-direction: column; gap: 0.4rem; }
.card:hover { border-color: #94a3b8; }
.form { max-width: 28rem; }
.form label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; }
.row { display: flex; gap: 0.5rem; align-items: center; }
.row-title { display: flex; align-items: center; gap: 0.5rem; }
.name { font-weight: 600; }
.desc { color: #475569; font-size: 0.85rem; margin: 0; min-height: 1.2em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: #94a3b8; font-size: 0.78rem; margin: 0; }
.badge { font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
.badge.pub { background: rgb(37 99 235 / 8%); color: #2563eb; border-color: rgb(37 99 235 / 30%); }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem; background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.err { color: #dc2626; font-size: 0.8rem; }
.empty { color: #94a3b8; }
</style>
