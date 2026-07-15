<!-- EditableConfigPanel.vue — Edit-mode config editor (services/users + vars).
     headers 引 auth 选择器：点 "ⓘ" 弹 AuthSelectorModal。-->
<template>
  <div class="econf">
    <h4 class="econf-title">✏️ Config</h4>

    <!-- services -->
    <section class="econf-section">
      <header class="section-h">
        <h5>services（API 地址）</h5>
        <el-button size="small" type="primary" plain @click="addService">+ 新增</el-button>
      </header>
      <draggable
        v-model="services"
        :animation="150"
        tag="div"
        class="kv-list"
        item-key="key"
      >
        <template #item="{ element, index }">
          <div class="kv-row">
            <span class="kv-handle">≡</span>
            <el-input
              v-model="services[index].key"
              size="small"
              placeholder="alias"
              class="kv-key"
            />
            <el-input
              v-model="services[index].value"
              size="small"
              placeholder="https://..."
              class="kv-val"
            />
            <el-button
              link
              type="danger"
              size="small"
              @click="services.splice(index, 1)"
            >×</el-button>
          </div>
        </template>
      </draggable>
    </section>

    <!-- Config.users -->
    <section class="econf-section">
      <header class="section-h">
        <h5>users（字面量凭证 — 与 /auths 池互不干扰）</h5>
        <el-button size="small" type="primary" plain @click="addUser">+ 新增</el-button>
      </header>
      <div
        v-for="(u, idx) in configUsers"
        :key="idx"
        class="user-row"
      >
        <el-input v-model="u.alias" size="small" placeholder="alias" class="kv-key" />
        <el-input v-model="u.url" size="small" placeholder="登录 URL" class="kv-val" />
        <el-input v-model="u.username" size="small" placeholder="username" class="kv-key" />
        <el-input v-model="u.password" size="small" type="password" show-password placeholder="password" class="kv-val" />
        <el-select v-model="u.token_type" size="small" class="tt-sel">
          <el-option label="Bearer" value="Bearer" />
          <el-option label="Basic" value="Basic" />
          <el-option label="Cookie" value="Cookie" />
          <el-option label="Authorization" value="Authorization" />
        </el-select>
        <el-button
          link
          type="danger"
          size="small"
          @click="configUsers.splice(idx, 1)"
        >×</el-button>
      </div>
    </section>

    <!-- Vars -->
    <section class="econf-section">
      <h5>vars（顶层变量 — Spec-2-5）</h5>
      <VarsEditor
        :model-value="vars"
        :readonly="false"
        @update:model-value="onVarsUpdate"
        @cancel="resetVars"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import draggable from 'vuedraggable'
import VarsEditor from './VarsEditor.vue'

interface ServiceRow { key: string; value: string }
interface UserRow {
  alias: string
  url: string
  username: string
  password: string
  token_type: string
  expires_in: number
}

const props = defineProps<{
  config: Record<string, unknown>
  auths: Array<{ alias: string }>
}>()

const emit = defineEmits<{
  'update': [c: { services: ServiceRow[]; users: UserRow[]; vars: Record<string, unknown> }]
}>()

const services = ref<ServiceRow[]>([])
const configUsers = ref<UserRow[]>([])
const vars = ref<Record<string, unknown>>({})
const originalVars = ref<Record<string, unknown>>({})

function loadFromProps() {
  const c = props.config
  services.value = Object.entries(c.services ?? {}).map(([k, v]) => ({ key: k, value: String(v) }))
  configUsers.value = Object.entries(c.users ?? {}).map(([k, v]) => {
    const u = v as Record<string, unknown>
    return {
      alias: k,
      url: String(u.url ?? ''),
      username: String(u.username ?? ''),
      password: String(u.password ?? ''),
      token_type: String(u.token_type ?? 'Bearer'),
      expires_in: Number(u.expires_in ?? 7200),
    }
  })
  vars.value = { ...(c.vars ?? {}) }
  originalVars.value = { ...vars.value }
}

loadFromProps()
// NOTE: no watcher on ``props.config`` — re-syncing from props after each
// edit would reset ``services``/``configUsers``/``vars`` to fresh array
// refs, which (a) clobbers the user's in-flight edits and (b) trips the
// ``[services, configUsers]`` watcher below into an emit-loop.  The panel
// only needs to load on mount; further parent-driven changes flow back
// in via the upper-level ``editStore``.

function onVarsUpdate(next: Record<string, unknown>) {
  vars.value = { ...next }
  // Replay the same upward emit shape so the parent's editStore stays in
  // sync (services + users were never touched by this handler).
  const out: Record<string, unknown> = {}
  for (const s of services.value) if (s.key) out[s.key] = s.value
  const usersOut: Record<string, unknown> = {}
  for (const u of configUsers.value) {
    if (!u.alias) continue
    usersOut[u.alias] = {
      url: u.url,
      username: u.username,
      password: u.password,
      token_type: u.token_type,
      expires_in: u.expires_in,
    }
  }
  emit('update', { services: out, users: usersOut, vars: vars.value })
}

function resetVars() {
  vars.value = { ...originalVars.value }
  onVarsUpdate(vars.value)
}

watch(
  [services, configUsers],
  () => {
    const out: Record<string, unknown> = {}
    for (const s of services.value) if (s.key) out[s.key] = s.value
    const usersOut: Record<string, unknown> = {}
    for (const u of configUsers.value) {
      if (!u.alias) continue
      usersOut[u.alias] = {
        url: u.url,
        username: u.username,
        password: u.password,
        token_type: u.token_type,
        expires_in: u.expires_in,
      }
    }
    emit('update', { services: out, users: usersOut, vars: vars.value })
  },
  { deep: true },
)

function addService() {
  services.value.push({ key: '', value: '' })
}

function addUser() {
  configUsers.value.push({
    alias: '',
    url: '',
    username: '',
    password: '',
    token_type: 'Bearer',
    expires_in: 7200,
  })
}
</script>

<style scoped>
.econf {
  padding: 14px 18px;
  background: #fff;
  border: 0.5px solid #c7d2fe;
  border-radius: 8px;
}

.econf-title {
  margin: 0 0 12px;
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
}

.econf-section {
  margin-bottom: 18px;
}

.econf-section h5 {
  margin: 0 0 8px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.section-h {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.kv-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kv-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.kv-handle {
  color: #cbd5e1;
  cursor: grab;
}

.kv-key {
  flex: 0 0 200px;
}

.kv-val {
  flex: 1;
}

.user-row {
  display: grid;
  grid-template-columns: 100px 1fr 1fr 1fr 110px 24px;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}

.tt-sel {
  width: 110px;
}
</style>