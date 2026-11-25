<!-- AccountCombosView.vue — 账户组合管理页(账户组合设计方案 §8.2,
     2026-11-25 批 4;壳 = 原执行配置页语义旋转,ADR-0003 #26)。

     v1 收敛四区:
     ① 组合列表(scope 分组:个人 / 我所在的项目;默认标记 + 引用计数);
     ② 组合编辑(服务 → 身份条目;条目名 datalist = 登记面单源);
     ④ 引用场景(引用计数 + 删除被引用 409 场景清单);
     ③ 就绪度 v1 = 条目登记态(未登记标红 + 深链凭证管理);
     完整池命中/地址矩阵/Ping All 随后续片按 v6 范式收编(§8.2 表)。

     执行配置页(ExecConfigsView)随本页语义旋转退役:表/端点/链路
     冻结保留(重跑回放不受影响),旧深链 /exec-configs 重定向至此。 -->
<template>
  <div class="ac-page">
    <header class="ac-head">
      <div>
        <h1>账户组合</h1>
        <p class="ac-sub">
          一组「服务 → 身份条目」的默认映射,跨场景复用:场景在编排器绑定一次,
          组合改动对全部绑定场景下次执行生效;组合永远垫底(步骤直引 &gt; 方案 &gt; 组合)。
        </p>
      </div>
      <Button size="sm" data-testid="ac-new" @click="openCreate">新建组合</Button>
    </header>

    <div v-if="loadError" class="ac-error" data-testid="ac-load-error">{{ loadError }}</div>

    <div class="ac-body">
      <!-- ① 组合列表(scope 分组) -->
      <aside class="ac-rail" data-testid="ac-list">
        <div class="ac-group">
          <div class="ac-group-title">个人</div>
          <button v-for="c in list.personal" :key="c.id" type="button"
            class="ac-item" :class="{ on: selectedId === c.id && mode === 'edit' }"
            :data-testid="`ac-item-${c.id}`" @click="pick(c.id)">
            <span class="ac-item-name">{{ c.name }}</span>
            <span v-if="c.isDefault" class="ac-badge">默认</span>
            <span class="ac-ref" :title="`被 ${c.referenceCount} 个场景引用`">
              引 {{ c.referenceCount }}</span>
          </button>
          <div v-if="!list.personal.length" class="ac-empty">暂无个人组合</div>
        </div>
        <div v-for="g in list.projects" :key="g.projectId" class="ac-group">
          <div class="ac-group-title">{{ g.projectName }}</div>
          <button v-for="c in g.items" :key="c.id" type="button"
            class="ac-item" :class="{ on: selectedId === c.id && mode === 'edit' }"
            :data-testid="`ac-item-${c.id}`" @click="pick(c.id)">
            <span class="ac-item-name">{{ c.name }}</span>
            <span v-if="c.isDefault" class="ac-badge">默认</span>
            <span class="ac-ref">引 {{ c.referenceCount }}</span>
          </button>
          <div v-if="!g.items.length" class="ac-empty">暂无项目组合</div>
        </div>
      </aside>

      <!-- ②/④ 编辑区 + 引用计数 -->
      <section class="ac-main">
        <div v-if="mode === 'create'" class="ac-card" data-testid="ac-create">
          <h2>新建组合</h2>
          <label class="ac-field">
            <span>名称</span>
            <input v-model="form.name" data-testid="ac-name" maxlength="64"
              placeholder="如:测试组合 / 商户B视角" />
          </label>
          <label class="ac-field">
            <span>说明</span>
            <input v-model="form.description" maxlength="2048" placeholder="可选" />
          </label>
          <div class="ac-field">
            <span>范围</span>
            <div class="ac-scope">
              <label><input type="radio" value="user" v-model="form.scope" /> 个人</label>
              <label v-if="writableProjects.length">
                <input type="radio" value="project" v-model="form.scope" /> 项目
              </label>
              <select v-if="form.scope === 'project'" v-model="form.projectId"
                data-testid="ac-project">
                <option v-for="p in writableProjects" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select>
            </div>
            <p class="ac-hint">v1 硬同区:个人组合仅可绑本人私有场景;项目组合仅可绑同项目场景。</p>
          </div>
          <EntriesEditor v-model:entries="form.entries" :alias-names="aliasNames" />
          <div class="ac-actions">
            <Button size="sm" variant="outline" @click="mode = 'view'">取消</Button>
            <Button size="sm" data-testid="ac-save" :disabled="saving || !form.name.trim()"
              @click="saveCreate">{{ saving ? '创建中…' : '创建' }}</Button>
          </div>
        </div>

        <div v-else-if="selected" class="ac-card" data-testid="ac-edit">
          <div class="ac-edit-head">
            <h2>{{ selected.name }}</h2>
            <span class="ac-meta">
              {{ selected.scope === 'user' ? '个人' : `项目 · ${scopeNameOf(selected)}` }}
              · 修订 {{ selected.revision }}
              <template v-if="selected.updatedByName"> · {{ selected.updatedByName }} 改</template>
              · <span :title="`被 ${selected.referenceCount} 个场景引用`"
                data-testid="ac-refcount">引用 {{ selected.referenceCount }}</span>
            </span>
          </div>
          <label class="ac-field">
            <span>名称</span>
            <input v-model="form.name" maxlength="64" />
          </label>
          <label class="ac-field">
            <span>说明</span>
            <input v-model="form.description" maxlength="2048" placeholder="可选" />
          </label>
          <!-- ②/③ 条目编辑 + 登记态(未登记标红 = 就绪度 v1) -->
          <EntriesEditor v-model:entries="form.entries" :alias-names="aliasNames" />
          <div class="ac-actions">
            <Button size="sm" variant="outline" data-testid="ac-delete"
              @click="del">删除</Button>
            <Button v-if="!selected.isDefault" size="sm" variant="outline"
              data-testid="ac-set-default" @click="makeDefault">设为默认</Button>
            <Button size="sm" data-testid="ac-save" :disabled="saving"
              @click="saveEdit">{{ saving ? '保存中…' : '保存' }}</Button>
          </div>
          <!-- ④ 删除被引用 → 409 场景清单(§5.1 不解绑不给删) -->
          <div v-if="inUseScenarios" class="ac-inuse" data-testid="ac-in-use">
            组合仍被以下场景引用,请先在场景内解除绑定:
            <ul>
              <li v-for="s in inUseScenarios" :key="s.scenarioId">
                <RouterLink :to="composerUrl(s.scenarioId)">{{ s.name }}</RouterLink>
              </li>
            </ul>
          </div>
        </div>

        <div v-else class="ac-card ac-placeholder" data-testid="ac-placeholder">
          从左侧选择一个组合,或新建 —— v1 应用入口在编排器「配置」页签
          (场景绑定组合);本页负责组合的治理与就绪度。
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 账户组合管理页(§8.2 四区 v1)。数据面 = api/accountCombos(后端
 * /api/account-combos + 场景绑定端点);条目名 datalist = 登记面
 * 单源(listAllAliases),保存面校验(别名未登记/异基础服务/重复服务)
 * 由后端 422 兜底,错误按码翻译成人话。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Button } from '@/components/ui/button'
import { toast } from '@/utils/toast'
import { composerUrl } from '@/utils/links'
import {
  createAccountCombo, deleteAccountCombo, listAccountCombos,
  setDefaultAccountCombo, updateAccountCombo,
  type AccountComboList, type AccountComboRow, type ComboEntry,
} from '@/api/accountCombos'
import { listProjects, type ProjectOut } from '@/api/projects'
import { listAllAliases } from '@/api/service-aliases'
import EntriesEditor from '@/components/account-combos/EntriesEditor.vue'
import { ApiError } from '@/api/http'

const list = reactive<AccountComboList>({ personal: [], projects: [] })
const aliasNames = ref<string[]>([])
const writableProjects = ref<ProjectOut[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'view' | 'create' | 'edit'>('view')
const saving = ref(false)
const loadError = ref('')
const inUseScenarios = ref<{ scenarioId: string; name: string }[] | null>(null)

const selected = computed<AccountComboRow | null>(() => {
  if (mode.value !== 'edit' || selectedId.value == null) return null
  return [...list.personal, ...list.projects.flatMap((g) => g.items)]
    .find((c) => c.id === selectedId.value) ?? null
})

const form = reactive({
  name: '',
  description: '',
  entries: [] as ComboEntry[],
  scope: 'user' as 'user' | 'project',
  projectId: undefined as number | undefined,
})

function resetForm() {
  form.name = ''
  form.description = ''
  form.entries = []
  form.scope = 'user'
  form.projectId = writableProjects.value[0]?.id
}

function scopeNameOf(c: AccountComboRow): string {
  return list.projects.find((g) => g.projectId === c.scopeId)?.projectName
    ?? String(c.scopeId)
}

async function load() {
  loadError.value = ''
  try {
    const out = await listAccountCombos()
    list.personal = out.personal
    list.projects = out.projects
  } catch (e) {
    loadError.value = '组合列表加载失败,请刷新重试'
  }
}

function pick(id: number) {
  mode.value = 'edit'
  selectedId.value = id
  inUseScenarios.value = null
  const c = [...list.personal, ...list.projects.flatMap((g) => g.items)]
    .find((x) => x.id === id)
  if (c) {
    form.name = c.name
    form.description = c.description ?? ''
    form.entries = c.entries.map((e) => ({ ...e }))
  }
}

function openCreate() {
  mode.value = 'create'
  selectedId.value = null
  inUseScenarios.value = null
  resetForm()
}

/** 保存面错误按码翻译(§5.2 码表;未识别码回落通用文案) */
function fmtComboError(e: unknown, act: string): string {
  if (e instanceof ApiError) {
    const code = String(e.detail?.code ?? e.code ?? '')
    const d = e.detail ?? {}
    if (code === 'account_combo_name_exists') return '同名组合已存在,请改名'
    if (code === 'account_combo_entry_invalid') {
      return `条目形状无效(一条一服务): ${String(d.message ?? '')}`
    }
    if (code === 'binding_alias_unknown') {
      return `身份条目未登记: ${String(d.alias ?? d.message ?? '')}(先在服务注册页登记)`
    }
    if (code === 'binding_alias_mismatch') {
      return `条目与服务不同基础服务(不许借道改地址): ${String(d.message ?? '')}`
    }
    if (code === 'public_project_create_forbidden') {
      return '公共项目不能直接新建,请选择普通项目'
    }
    if (code === 'project_role_readonly') return '项目用户只读,不能修改组合'
  }
  return `${act}失败,请重试`
}

async function saveCreate() {
  saving.value = true
  try {
    const row = await createAccountCombo({
      name: form.name.trim(),
      description: form.description.trim(),
      entries: form.entries.filter((e) => e.service.trim() && e.alias.trim()),
      scope: form.scope,
      ...(form.scope === 'project' && form.projectId != null
        ? { projectId: form.projectId } : {}),
    })
    toast.success('组合已创建')
    await load()
    pick(row.id)
  } catch (e) {
    toast.error(fmtComboError(e, '创建'))
  } finally {
    saving.value = false
  }
}

async function saveEdit() {
  if (!selected.value) return
  saving.value = true
  try {
    const entries = form.entries.filter((e) => e.service.trim() && e.alias.trim())
    const dirty = entries.length !== selected.value.entries.length
      || entries.some((e, i) => e.service !== selected.value!.entries[i]?.service
        || e.alias !== selected.value!.entries[i]?.alias)
    await updateAccountCombo(selected.value.id, {
      name: form.name.trim(),
      description: form.description.trim(),
      // 整体替换式;条目有实质变化后端 revision +1(元数据不加)
      ...(dirty ? { entries } : {}),
    })
    toast.success(dirty ? '已保存(条目变化,修订 +1)' : '已保存')
    await load()
    pick(selected.value.id)
  } catch (e) {
    toast.error(fmtComboError(e, '保存'))
  } finally {
    saving.value = false
  }
}

async function makeDefault() {
  if (!selected.value) return
  try {
    await setDefaultAccountCombo(selected.value.id)
    toast.success('已设为默认(新建场景时预选,不自动写入)')
    await load()
    pick(selected.value.id)
  } catch (e) {
    toast.error(fmtComboError(e, '设为默认'))
  }
}

async function del() {
  if (!selected.value) return
  inUseScenarios.value = null
  try {
    await deleteAccountCombo(selected.value.id)
    toast.success('组合已删除')
    selectedId.value = null
    mode.value = 'view'
    await load()
  } catch (e) {
    // ④ 被引用 409:展示引用场景清单(§5.1 不解绑不给删)
    if (e instanceof ApiError && e.detail?.code === 'account_combo_in_use') {
      inUseScenarios.value = (e.detail?.scenarios
        ?? []) as { scenarioId: string; name: string }[]
    } else {
      toast.error(fmtComboError(e, '删除'))
    }
  }
}

onMounted(async () => {
  void load()
  // 条目名 datalist(登记面单源)与可写项目(scope 选择)
  listAllAliases().then((rows) => {
    aliasNames.value = rows.map((r) => r.aliasName).filter(Boolean)
  }).catch(() => { aliasNames.value = [] })
  listProjects().then((rows) => {
    writableProjects.value = rows.filter((p) => p.kind === 'normal' && p.canWrite)
    if (!form.projectId) form.projectId = writableProjects.value[0]?.id
  }).catch(() => { writableProjects.value = [] })
})
</script>

<style scoped>
.ac-page { padding: 1.25rem 1.5rem; max-width: 75rem; margin: 0 auto; }
.ac-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.ac-head h1 { font-size: 1.125rem; margin: 0 0 0.25rem; }
.ac-sub { font-size: 0.75rem; color: var(--sl-ink-3, #5B6472); margin: 0; max-width: 40rem; line-height: 1.6; }
.ac-error { margin: 0.75rem 0; padding: 0.5rem 0.75rem; font-size: 0.75rem;
  color: #B42318; background: #FEE4E2; border-radius: 0.375rem; }
.ac-body { display: grid; grid-template-columns: 15rem 1fr; gap: 1rem; margin-top: 1rem; align-items: start; }
.ac-rail { border: 1px solid var(--sl-line, #E3E7EE); border-radius: 0.5rem;
  background: var(--c-surface, #fff); padding: 0.5rem; }
.ac-group + .ac-group { margin-top: 0.75rem; }
.ac-group-title { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); padding: 0.25rem 0.375rem; }
.ac-item { display: flex; align-items: center; gap: 0.375rem; width: 100%;
  padding: 0.375rem 0.5rem; border: 0; border-radius: 0.375rem; background: transparent;
  font-size: 0.8125rem; cursor: pointer; text-align: left; color: var(--sl-ink, #1F2430); }
.ac-item:hover { background: var(--sl-bg-2, #F3F5F8); }
.ac-item.on { background: var(--sl-bg-2, #EDF0F5); font-weight: 600; }
.ac-item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ac-badge { font-size: 0.625rem; color: #175CD3; background: #EFF4FF;
  border-radius: 0.25rem; padding: 0.0625rem 0.3125rem; }
.ac-ref { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); }
.ac-empty { font-size: 0.75rem; color: var(--sl-ink-3, #8B93A1); padding: 0.375rem; }
.ac-main { min-width: 0; }
.ac-card { border: 1px solid var(--sl-line, #E3E7EE); border-radius: 0.5rem;
  background: var(--c-surface, #fff); padding: 1rem 1.25rem; }
.ac-card h2 { font-size: 0.9375rem; margin: 0 0 0.75rem; }
.ac-edit-head { display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap; }
.ac-edit-head h2 { margin: 0; }
.ac-meta { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); }
.ac-field { display: grid; gap: 0.25rem; margin-bottom: 0.75rem; }
.ac-field > span { font-size: 0.6875rem; color: var(--sl-ink-3, #5B6472); }
.ac-field input, .ac-scope select { padding: 0.3125rem 0.5rem; font-size: 0.8125rem;
  border: 1px solid var(--sl-line, #D5DAE3); border-radius: 0.375rem;
  background: var(--c-surface, #fff); color: var(--sl-ink, #1F2430); max-width: 26rem; }
.ac-scope { display: flex; gap: 0.75rem; align-items: center; font-size: 0.8125rem; }
.ac-hint { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); margin: 0.25rem 0 0; }
.ac-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.75rem; }
.ac-placeholder { color: var(--sl-ink-3, #8B93A1); font-size: 0.8125rem; line-height: 1.7; }
.ac-inuse { margin-top: 0.75rem; padding: 0.625rem 0.75rem; font-size: 0.75rem;
  color: #B54708; background: #FEF0C7; border-radius: 0.375rem; }
.ac-inuse ul { margin: 0.375rem 0 0; padding-left: 1.125rem; }
.ac-inuse a { color: #B54708; }
</style>
