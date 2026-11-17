<!-- ServiceAdmin.vue — 服务注册(重构 2026-11-16:注册簿制 + 四层映射)。
     心智模型(§0 四层):
       ① 服务主档 services —— 系统概念的唯一登记处(name/system/kind/abbr/
          说明);**不从 plate 目录镜像**,目录只用于对账(未登记候选/漂移)。
       ② 环境 × 系统实例 —— (system, env) → login_url / 版本线 / 说明。
          同一 system 下多个服务共享同一份登录口/版本线,格内小钮编辑。
       ③ 服务 × 环境 API 地址 —— deployments(执行请求的 base_url)。
       ④ 身份条目 —— 服务子页(/service-admin/{服务名})。
     本页职责 = ①②③ 的结构面 + 对账;服务名点击进子页看身份条目。
     行 = 主档服务(按 system 分组,组头显示该系统的登录口覆盖);列 = 环境
     (chip 聚焦 = 只显该环境缺 API 地址的服务 + 环境管理条);格 = API
     地址(行内编辑/登记)+ 实例配置小钮(登录口/版本线弹框)。
     词汇规约(2026-11-17 用户口径):「实例」= 服务 × 环境的部署存在,
     格即实例;「实例配置」入口编辑的是 (system, env) 共享的登录口/版本线。
     沿革:2026-11-13 矩阵化(服务×环境地址 + 说明);2026-11-16 registry
     重构 —— 服务全集从「目录∪部署」切到主档,新增登记/对账/删除,
     登录口/版本线从环境表单迁到 (system, env) 实例弹框。 -->
<template>
  <section class="slib">
    <PageHead
      icon="layers"
      title="服务注册"
      :count="loading ? '' : `${services.length} 服务 · ${envs.length} 环境`"
      subtitle="服务主档(注册簿)+ 各环境 API 地址与登录口;服务名点进子页管理身份条目;探索覆盖与告警请用服务画像"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- 工具条:服务搜索 + 环境列聚焦 + 登记入口 -->
      <div class="slib-toolbar" data-testid="mx-toolbar">
        <input
          v-model="svcSearch" class="slib-search"
          placeholder="搜索服务名 / 系统" data-testid="svc-search"
        />
        <span class="svc-stats tight" data-testid="dep-envs">
          <button
            v-for="e in envs" :key="e.id" type="button" class="svc-chip"
            :class="{ on: focusedEnv === e.id }"
            :data-testid="`dep-env-${e.id}`" @click="toggleFocus(e.id)"
          >
            {{ e.name }}<span v-if="e.is_default" class="svc-flag green">默认</span>
            <span
              v-if="missingInEnv(e.id)"
              class="svc-flag amber"
              :title="`该环境还有 ${missingInEnv(e.id)} 个服务缺 API 地址`"
            >缺{{ missingInEnv(e.id) }}</span>
          </button>
        </span>
        <button
          v-if="unregistered.length" type="button" class="svc-chip"
          :class="{ on: reconOpen }" data-testid="recon-toggle"
          @click="reconOpen = !reconOpen"
        >对账 · {{ unregistered.length }} 未登记</button>
        <button type="button" class="slib-create" data-testid="svc-new"
                @click="openCreateSvc()">+ 登记服务</button>
        <button type="button" class="slib-create" data-testid="dep-env-new"
                @click="openCreateEnv">+ 新建环境</button>
      </div>

      <div v-if="error" class="svc-banner bad" data-testid="dep-err">{{ error }}</div>

      <!-- 对账条:plate 目录里还没拉入主档的服务名(一键登记候选)/
           目录不可达 / 主档与目录漂移 -->
      <div v-if="reconOpen || !plateReachable" class="svc-panel recon" data-testid="recon-panel">
        <div class="svc-panel-head">
          <span class="svc-panel-title">与 plate 目录对账</span>
          <span class="svc-panel-desc">
            主档是注册簿 —— 目录里的服务不会自动进;登记后才有身份条目/账户挂靠。
          </span>
        </div>
        <p v-if="!plateReachable" class="recon-note" data-testid="recon-unreachable">
          plate 目录当前不可达 —— 对账暂停(主档读面不受影响)。
        </p>
        <template v-else>
          <div v-if="unregistered.length" class="recon-row" data-testid="recon-unregistered">
            <span class="muted">目录中未登记({{ unregistered.length }}):</span>
            <button
              v-for="n in unregistered" :key="n" type="button" class="svc-chip"
              :data-testid="`recon-add-${n}`" @click="openCreateSvc(n)"
            >+ {{ n }}</button>
          </div>
          <p v-else class="recon-note">目录服务已全部登记。</p>
          <div v-if="drifted.length" class="recon-row" data-testid="recon-drifted">
            <span class="muted">主档 plate 行已不在目录(漂移,{{ drifted.length }}):</span>
            <span v-for="n in drifted" :key="n" class="svc-flag amber">{{ n }}</span>
          </div>
        </template>
      </div>

      <!-- 环境表单(新建/编辑;版本线落 (system, env) 实例,读面形状不变)-->
      <div v-if="envFormOpen" class="svc-panel" :data-testid="`dep-env-form-${envFormMode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ envFormMode === 'create' ? '新建环境' : `编辑环境:${focusedCurrent?.name}` }}
          </span>
          <span class="svc-panel-desc">
            版本线 = 每个系统部署的版本(落环境×系统实例;执行期按此解析版本;
            第三方 integration 系统不可声明)
          </span>
        </div>

        <div class="form-grid">
          <template v-if="envFormMode === 'create'">
            <label class="lb">名称</label>
            <Input v-model="envForm.name" placeholder="如 SIT / UAT"
                   data-testid="dep-env-name" />
          </template>
          <label class="lb">描述</label>
          <Input v-model="envForm.description" placeholder="可选"
                 data-testid="dep-env-desc" />
        </div>

        <div v-for="(r, i) in lineRows" :key="i" class="line-row">
          <Input v-model="r.sys" class="flex-1" placeholder="系统名"
                 :data-testid="`dep-env-sys-${i}`" />
          <Input v-model="r.line" class="flex-1" placeholder="版本线,如 1.0"
                 :data-testid="`dep-env-line-${i}`" />
          <button type="button" class="svc-link danger" :data-testid="`dep-env-rm-${i}`"
                  @click="lineRows.splice(i, 1)">移除</button>
        </div>

        <div class="svc-foot">
          <Button variant="outline" size="sm" data-testid="dep-env-add-line"
                  @click="lineRows.push({ sys: '', line: '' })">+ 添加版本线</Button>
          <span class="svc-foot-right">
            <Button size="sm" data-testid="dep-env-save" @click="saveEnv">保存</Button>
            <Button variant="outline" size="sm" @click="envFormOpen = false">取消</Button>
          </span>
        </div>
      </div>

      <!-- 聚焦态环境管理条(环境优先工作流:新开环境 → 聚焦补地址)-->
      <div v-if="focusedCurrent" class="svc-stats" data-testid="dep-current">
        <span>当前环境</span>
        <b>{{ focusedCurrent.name }}</b>
        <span v-if="focusedCurrent.is_default" class="svc-flag green">默认</span>
        <span v-if="focusedCurrent.description" class="muted">{{ focusedCurrent.description }}</span>
        <span class="flex-1" />
        <Button v-if="!focusedCurrent.is_default" variant="outline" size="sm"
                data-testid="dep-set-default" @click="makeDefault">设为默认环境</Button>
        <Button v-else variant="outline" size="sm"
                data-testid="dep-unset-default" @click="clearDefault">取消默认</Button>
        <Button variant="outline" size="sm" data-testid="dep-env-edit"
                @click="openEditEnv">编辑环境</Button>
        <template v-if="!envDelArmed">
          <Button variant="outline" size="sm" class="text-signal-failed"
                  data-testid="dep-env-del" @click="envDelArmed = true">删除环境</Button>
        </template>
        <template v-else>
          <span class="svc-flag red">该环境的 API 地址/实例配置将一并删除</span>
          <Button variant="destructive" size="sm" data-testid="dep-env-del-ok"
                  @click="delEnv">确认删除</Button>
          <Button variant="outline" size="sm" @click="envDelArmed = false">取消</Button>
        </template>
      </div>

      <!-- 主档注册簿 × 环境矩阵(按 system 分组)-->
      <div v-if="matrixGroups.length" class="lib-card mx-wrap" data-testid="mx-matrix">
        <table class="slib-table mx-table">
          <thead>
            <tr>
              <th class="mx-svc-col">服务</th>
              <th class="mx-desc-col">说明</th>
              <th
                v-for="e in envs" :key="e.id"
                :class="{ 'mx-focus': focusedEnv === e.id }"
              >{{ e.name }}</th>
              <th style="width:4.5rem">操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="g in matrixGroups" :key="g.key">
              <!-- 系统组头:系统名 + 服务数 + 该系统的登录口覆盖情况 -->
              <tr class="mx-kind" :data-testid="`sys-group-${g.key}`">
                <td :colspan="envs.length + 3">
                  <div class="grp-in">
                    <b class="mono">{{ g.system || '未归类' }}</b>
                    <span class="muted">{{ g.services.length }} 服务</span>
                    <span
                      class="svc-flag"
                      :class="g.instReady === envs.length ? 'green' : 'amber'"
                      :title="`该系统的登录口/版本线在 ${g.instReady}/${envs.length} 个环境已配置`"
                      :data-testid="`sys-inst-${g.key}`"
                    >登录口 {{ g.instReady }}/{{ envs.length }}</span>
                    <span class="flex-1" />
                  </div>
                </td>
              </tr>
              <tr v-for="svc in g.services" :key="svc.name" :data-testid="`mx-row-${svc.name}`">
                <td class="mx-svc-cell">
                  <RouterLink
                    class="mx-svc-link mono"
                    :to="`/service-admin/${encodeURIComponent(svc.name)}`"
                    :data-testid="`mx-svc-link-${svc.name}`"
                    :title="`打开 ${svc.name} 的身份条目`"
                  >{{ svc.name }}</RouterLink>
                  <span v-if="svc.abbr && svc.abbr !== svc.name" class="muted mx-abbr" :title="`缩写 ${svc.abbr}`">{{ svc.abbr }}</span>
                  <span
                    v-if="svc.kind === 'plate' && !svc.inCatalog"
                    class="svc-flag amber" :data-testid="`mx-drift-${svc.name}`"
                    title="主档 plate 行已不在 plate 目录(漂移)"
                  >漂移</span>
                </td>
                <!-- 说明列:主档 description,格内点击即编辑 -->
                <td class="mx-desc-cell">
                  <template v-if="descEdit && descEdit.svc === svc.name">
                    <Input v-model="descEdit.text" class="h-8 w-full min-w-[10rem]"
                           placeholder="该服务的基本信息(做什么/负责人/注意点)"
                           :data-testid="`meta-input-${svc.name}`" />
                    <div class="row-acts mt-1">
                      <button type="button" class="svc-link"
                              :data-testid="`meta-save-${svc.name}`" @click="saveDesc">保存</button>
                      <button type="button" class="svc-link" @click="descEdit = null">取消</button>
                    </div>
                  </template>
                  <button
                    v-else type="button" class="mx-desc"
                    :title="svc.description || '点击填写服务说明'"
                    :data-testid="`meta-cell-${svc.name}`"
                    @click="startDescEdit(svc.name, svc.description)"
                  >{{ svc.description || '—' }}</button>
                </td>
                <td
                  v-for="e in envs" :key="e.id"
                  class="mx-cell" :class="{ 'mx-focus': focusedEnv === e.id }"
                >
                  <!-- API 地址(deployments):有则行内编辑,缺则就地登记 -->
                  <template v-if="depOf(svc.name, e.id)">
                    <template v-if="cellEdit && cellEdit.svc === svc.name && cellEdit.envId === e.id">
                      <Input v-model="cellEdit.url" class="h-8 w-full min-w-[10rem]"
                             :data-testid="`mx-url-${svc.name}-${e.id}`" />
                      <div class="row-acts mt-1">
                        <button type="button" class="svc-link"
                                :data-testid="`mx-save-${svc.name}-${e.id}`" @click="saveCell">保存</button>
                        <button type="button" class="svc-link danger"
                                :data-testid="`mx-del-${svc.name}-${e.id}`" @click="delCell">删除</button>
                        <button type="button" class="svc-link" @click="cellEdit = null">取消</button>
                      </div>
                    </template>
                    <button
                      v-else type="button" class="mono mx-url"
                      :title="depOf(svc.name, e.id)!.baseUrl"
                      :data-testid="`mx-cell-${svc.name}-${e.id}`"
                      @click="startCellEdit(svc.name, e.id)"
                    >{{ depOf(svc.name, e.id)!.baseUrl }}</button>
                  </template>
                  <template v-else>
                    <template v-if="cellNew && cellNew.svc === svc.name && cellNew.envId === e.id">
                      <Input v-model="cellNew.url" class="h-8 w-full min-w-[10rem]"
                             placeholder="https://…" :data-testid="`mx-new-url-${svc.name}-${e.id}`" />
                      <div class="row-acts mt-1">
                        <button type="button" class="svc-link"
                                :data-testid="`mx-register-${svc.name}-${e.id}`" @click="registerCell">登记</button>
                        <button type="button" class="svc-link" @click="cellNew = null">取消</button>
                      </div>
                    </template>
                    <button
                      v-else type="button" class="svc-link warn-link"
                      :data-testid="`mx-miss-${svc.name}-${e.id}`"
                      @click="startCellNew(svc.name, e.id)"
                    >缺 · 登记</button>
                  </template>
                  <!-- 实例配置(登录口/版本线):小钮,已配绿 / 未配琥珀;同系统共享 -->
                  <button
                    type="button" class="inst-btn"
                    :class="{ ready: !!instOf(svc.system, e.id)?.loginUrl }"
                    :data-testid="`mx-inst-${svc.name}-${e.id}`"
                    :title="instOf(svc.system, e.id)?.loginUrl
                      ? `实例配置:登录口 ${instOf(svc.system, e.id)!.loginUrl}(系统 ${svc.system} 共享)`
                      : `系统 ${svc.system} 在该环境未配置登录口 — 点击配置`"
                    @click="openInstance(svc.system, svc.name, e.id)"
                  >{{ instOf(svc.system, e.id)?.loginUrl ? '🔑 实例配置' : '🔑 实例未配置' }}</button>
                </td>
                <td class="c-center">
                  <DropdownMenu>
                    <DropdownMenuTrigger class="more-btn" aria-label="服务操作"
                      :data-testid="`svc-more-${svc.name}`">⋯</DropdownMenuTrigger>
                    <DropdownMenuContent align="end" class="sl-menu">
                      <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-edit-${svc.name}`"
                        @click="openEditSvc(svc)">编辑信息</DropdownMenuItem>
                      <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-faces-${svc.name}`"
                        @click="router.push(`/service-admin/${encodeURIComponent(svc.name)}`)">身份条目</DropdownMenuItem>
                      <DropdownMenuItem class="sl-menu-item danger" :data-testid="`svc-del-${svc.name}`"
                        @click="removeSvc(svc)">删除实例</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            </template>
            <tr v-if="!matrixGroups.length">
              <td :colspan="envs.length + 3" class="c-center">
                <span class="muted">
                  {{ svcSearch ? '没有匹配的服务' : '主档为空 —— 先「登记服务」,或从上方对账条一键拉入目录服务' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-cta" data-testid="mx-empty">
        <p>还没有登记任何服务。</p>
        <Button variant="outline" size="sm" @click="openCreateSvc()">+ 登记服务</Button>
      </div>
    </template>

    <!-- ── 服务主档登记 / 编辑 ─────────────────────────────── -->
    <Dialog :open="svcFormOpen" @update:open="svcFormOpen = $event">
      <DialogContent class="max-w-[30rem]">
        <DialogHeader>
          <DialogTitle>{{ svcEditing ? '编辑服务' : '登记服务' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="saveSvc">
          <div class="grid grid-cols-2 gap-3">
            <label class="field">
              <span class="field-label">服务名<span class="req">*</span></span>
              <input v-model="svcForm.name" class="field-input mono"
                data-testid="svc-form-name" :disabled="!!svcEditing"
                placeholder="与 plate 目录一致" />
            </label>
            <label class="field">
              <span class="field-label">系统<span class="req">*</span></span>
              <input v-model="svcForm.system" class="field-input mono"
                data-testid="svc-form-system" placeholder="账户/实例的 system 维度" />
            </label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="field">
              <span class="field-label">类型</span>
              <select v-model="svcForm.kind" class="field-input" data-testid="svc-form-kind"
                :disabled="!!svcEditing">
                <option value="plate">plate(目录受管)</option>
                <option value="external">external(第三方)</option>
                <option value="integration">integration(plate 集成件)</option>
              </select>
            </label>
            <label class="field">
              <span class="field-label">缩写</span>
              <input v-model="svcForm.abbr" class="field-input mono"
                data-testid="svc-form-abbr" placeholder="可选" />
            </label>
          </div>
          <label class="field">
            <span class="field-label">说明</span>
            <textarea v-model="svcForm.description" class="field-input field-area"
              data-testid="svc-form-desc" rows="3"
              placeholder="做什么 / 负责人 / 注意点" />
          </label>
          <p v-if="svcFormError" class="err">{{ svcFormError }}</p>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="svcFormOpen = false">取消</Button>
            <Button type="submit" data-testid="svc-form-save" :disabled="svcSaving">
              {{ svcSaving ? '保存中…' : '保存' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 环境 × 系统实例(登录口 / 版本线 / 说明)──────────── -->
    <Dialog :open="instFormOpen" @update:open="instFormOpen = $event">
      <DialogContent class="max-w-[30rem]">
        <DialogHeader>
          <DialogTitle>
            实例配置 · {{ instForm.system }} × {{ envNameOf(instForm.envId) }}
          </DialogTitle>
        </DialogHeader>
        <p class="inst-hint">
          (系统, 环境) 的部署事实,同系统下
          {{ siblingsOf(instForm.system) }} 个服务共享;登录口用于凭证拨测,
          版本线用于执行期版本解析。
        </p>
        <form class="flex flex-col gap-3" @submit="saveInstance">
          <label class="field">
            <span class="field-label">登录地址(login URL)</span>
            <input v-model="instForm.loginUrl" class="field-input mono"
              data-testid="inst-form-url" placeholder="https://target/auth/login" />
            <span class="field-hint">拨测把账户凭据发往该地址;缺席时拨测明确报错</span>
          </label>
          <label class="field">
            <span class="field-label">版本线</span>
            <input v-model="instForm.line" class="field-input mono"
              data-testid="inst-form-line" placeholder="如 1.0(可选)" />
          </label>
          <label class="field">
            <span class="field-label">说明</span>
            <input v-model="instForm.note" class="field-input"
              data-testid="inst-form-note" placeholder="可选" />
          </label>
          <p v-if="instFormError" class="err">{{ instFormError }}</p>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="instFormOpen = false">取消</Button>
            <Button type="submit" data-testid="inst-form-save" :disabled="instSaving">
              {{ instSaving ? '保存中…' : '保存' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  type Deployment,
} from '@/api/deployments'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  createEnvironment, updateEnvironment, deleteEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import {
  listServices, createService, patchService, deleteService,
  listInstances, putInstance,
  type ServiceRow, type InstanceRow,
} from '@/api/services'
import { confirmAction } from '@/utils/confirmAction'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const loading = ref(true)
const router = useRouter()
const error = ref('')

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  if (d && typeof d === 'object' && 'msg' in d) return String((d as { msg: unknown }).msg)
  return String((e as Error)?.message ?? e)
}

// ── 数据面(主档 = 服务全集;目录只用于对账)──────────────────
const services = ref<ServiceRow[]>([])
const unregistered = ref<string[]>([])
const plateReachable = ref(true)
const envs = ref<EnvironmentRow[]>([])
const deployments = ref<Deployment[]>([])
const instances = ref<InstanceRow[]>([])

async function refreshServices(): Promise<void> {
  const out = await listServices()
  services.value = out.services
  unregistered.value = out.unregistered
  plateReachable.value = out.plateReachable
}
async function refreshDeps(): Promise<void> {
  deployments.value = await listDeployments()
}
async function refreshEnvs(): Promise<void> {
  envs.value = await listEnvironments()
}
async function refreshInstances(): Promise<void> {
  instances.value = await listInstances()
}

function depOf(service: string, envId: number): Deployment | undefined {
  return deployments.value.find(
    (d) => d.baseService === service && d.envId === envId)
}

/** 实例索引:(system, env) → 实例行(同系统多服务共享)。 */
const instKey = (system: string, envId: number) => `${system}::${envId}`
const instIndex = computed(() => {
  const m = new Map<string, InstanceRow>()
  for (const i of instances.value) m.set(instKey(i.system, i.envId), i)
  return m
})
function instOf(system: string, envId: number): InstanceRow | undefined {
  return instIndex.value.get(instKey(system, envId))
}
function envNameOf(envId: number): string {
  return envs.value.find((e) => e.id === envId)?.name ?? `环境#${envId}`
}
function siblingsOf(system: string): number {
  return services.value.filter((s) => s.system === system).length
}

/** 该环境缺 API 地址的主档服务数(环境 chip 的「缺N」)。 */
function missingInEnv(envId: number): number {
  const hit = new Set(deployments.value
    .filter((d) => d.envId === envId)
    .map((d) => d.baseService))
  return services.value.filter((s) => !hit.has(s.name)).length
}

// ── 工具条:搜索 + 环境聚焦 + 对账面板 ───────────────────────
const svcSearch = ref('')
const focusedEnv = ref<number | null>(null)
// 对账条默认展开(未登记候选要可发现;用户可收起)
const reconOpen = ref(true)

function toggleFocus(id: number): void {
  focusedEnv.value = focusedEnv.value === id ? null : id
  cellEdit.value = null
  cellNew.value = null
  descEdit.value = null
}
const focusedCurrent = computed(() =>
  envs.value.find((e) => e.id === focusedEnv.value) ?? null)

/** 漂移:主档 plate 行已不在目录(plate 不可达时不判)。 */
const drifted = computed(() => plateReachable.value
  ? services.value.filter((s) => s.kind === 'plate' && !s.inCatalog).map((s) => s.name)
  : [])

interface MatrixGroup {
  key: string
  system: string
  services: ServiceRow[]
  instReady: number
}

/** 矩阵:按 system 分组(服务=系统概念的呈现),组内按缺口数降序 →
 *  名字;svcSearch 客户端收窄;聚焦环境时只显该环境缺 API 地址的服务。 */
const matrixGroups = computed<MatrixGroup[]>(() => {
  const q = svcSearch.value.trim().toLowerCase()
  const gapOf = (svc: ServiceRow) => envs.value.length - envs.value.filter(
    (e) => depOf(svc.name, e.id)).length
  const pool = services.value
    .filter((svc) => !q || svc.name.toLowerCase().includes(q)
      || svc.system.toLowerCase().includes(q))
    .filter((svc) => focusedEnv.value == null || !depOf(svc.name, focusedEnv.value))
    .sort((x, y) => gapOf(y) - gapOf(x) || x.name.localeCompare(y.name))
  const bySys = new Map<string, ServiceRow[]>()
  for (const s of pool) {
    const k = s.system || ''
    const arr = bySys.get(k)
    if (arr) arr.push(s)
    else bySys.set(k, [s])
  }
  return [...bySys.entries()].map(([system, list]) => ({
    key: system || 'uncategorized',
    system,
    services: list,
    instReady: envs.value.filter((e) => instOf(system, e.id)?.loginUrl).length,
  })).sort((a, b) =>
    Number(a.key === 'uncategorized') - Number(b.key === 'uncategorized')
    || a.key.localeCompare(b.key))
})

// ── API 地址格(行内编辑 / 缺格登记)──────────────────────────
const cellEdit = ref<{ svc: string; envId: number; url: string } | null>(null)
const cellNew = ref<{ svc: string; envId: number; url: string } | null>(null)

function startCellEdit(svc: string, envId: number): void {
  const dep = depOf(svc, envId)
  if (!dep) return
  cellNew.value = null
  descEdit.value = null
  cellEdit.value = { svc, envId, url: dep.baseUrl }
}
async function saveCell(): Promise<void> {
  const c = cellEdit.value
  if (!c) return
  const dep = depOf(c.svc, c.envId)
  if (!dep) return
  error.value = ''
  try {
    await updateDeployment(dep.id, c.url.trim())
    cellEdit.value = null
    await refreshDeps()
  } catch (e) { error.value = msg(e) }
}
async function delCell(): Promise<void> {
  const c = cellEdit.value
  if (!c) return
  const dep = depOf(c.svc, c.envId)
  if (!dep) return
  error.value = ''
  try {
    await deleteDeployment(dep.id)
    cellEdit.value = null
    await refreshDeps()
  } catch (e) { error.value = msg(e) }
}
function startCellNew(svc: string, envId: number): void {
  cellEdit.value = null
  descEdit.value = null
  cellNew.value = { svc, envId, url: '' }
}
async function registerCell(): Promise<void> {
  const c = cellNew.value
  if (!c || !c.url.trim()) return
  error.value = ''
  try {
    await createDeployment({ baseService: c.svc, envId: c.envId, baseUrl: c.url.trim() })
    cellNew.value = null
    await refreshDeps()
  } catch (e) { error.value = msg(e) }
}

// ── 说明列(主档 description,读写经 services)──────────────────
const descEdit = ref<{ svc: string; text: string } | null>(null)

function startDescEdit(svc: string, description: string): void {
  cellEdit.value = null
  cellNew.value = null
  descEdit.value = { svc, text: description }
}
async function saveDesc(): Promise<void> {
  const d = descEdit.value
  if (!d) return
  error.value = ''
  try {
    await patchService(d.svc, { description: d.text.trim() })
    descEdit.value = null
    await refreshServices()
  } catch (e) { error.value = msg(e) }
}

// ── 服务主档:登记 / 编辑 / 删除 ─────────────────────────────
const svcFormOpen = ref(false)
const svcEditing = ref<ServiceRow | null>(null)
const svcSaving = ref(false)
const svcFormError = ref('')
const svcForm = ref({
  name: '', system: '', kind: 'plate' as ServiceRow['kind'],
  abbr: '', description: '',
})

function openCreateSvc(prefillName = ''): void {
  svcEditing.value = null
  svcForm.value = {
    name: prefillName, system: '', kind: 'plate', abbr: '', description: '',
  }
  svcFormError.value = ''
  svcFormOpen.value = true
}
function openEditSvc(svc: ServiceRow): void {
  svcEditing.value = svc
  svcForm.value = {
    name: svc.name, system: svc.system, kind: svc.kind,
    abbr: svc.abbr, description: svc.description,
  }
  svcFormError.value = ''
  svcFormOpen.value = true
}
async function saveSvc(): Promise<void> {
  svcFormError.value = ''
  const f = svcForm.value
  if (!f.name.trim()) { svcFormError.value = '请输入服务名'; return }
  if (!f.system.trim()) { svcFormError.value = '请输入系统名(与 Plate 侧一致)'; return }
  svcSaving.value = true
  try {
    if (svcEditing.value) {
      // 实体键 name/kind 不可改;可改 system/abbr/description
      await patchService(svcEditing.value.name, {
        system: f.system.trim(), abbr: f.abbr.trim(),
        description: f.description.trim(),
      })
    } else {
      await createService({
        name: f.name.trim(), system: f.system.trim(), kind: f.kind,
        abbr: f.abbr.trim(), description: f.description.trim(),
      })
    }
    svcFormOpen.value = false
    await refreshServices()
  } catch (e) {
    svcFormError.value = msg(e)
  } finally {
    svcSaving.value = false
  }
}
async function removeSvc(svc: ServiceRow): Promise<void> {
  const ok = await confirmAction(
    `删除「${svc.name}」?该服务的登记及其在所有环境下的实例将一并移除;有身份条目或部署地址挂靠时会被拦截。`,
    '删除实例',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  error.value = ''
  try {
    await deleteService(svc.name)
    await refreshServices()
  } catch (e) { error.value = msg(e) }
}

// ── 实例(环境 × 系统):登录口 / 版本线 / 说明 ─────────────────
const instFormOpen = ref(false)
const instSaving = ref(false)
const instFormError = ref('')
const instForm = ref({
  system: '', envId: 0, loginUrl: '', line: '', note: '',
})

function openInstance(system: string, _svcName: string, envId?: number): void {
  const targetEnv = envId ?? focusedEnv.value ?? envs.value[0]?.id
  if (!targetEnv) { error.value = '先建一个环境'; return }
  const row = instOf(system, targetEnv)
  instForm.value = {
    system, envId: targetEnv,
    loginUrl: row?.loginUrl ?? '', line: row?.line ?? '', note: row?.note ?? '',
  }
  instFormError.value = ''
  instFormOpen.value = true
}
async function saveInstance(): Promise<void> {
  instFormError.value = ''
  const f = instForm.value
  instSaving.value = true
  try {
    await putInstance(f.system, f.envId, {
      loginUrl: f.loginUrl.trim(), line: f.line.trim(), note: f.note.trim(),
    })
    instFormOpen.value = false
    await refreshInstances()
  } catch (e) {
    instFormError.value = msg(e)
  } finally {
    instSaving.value = false
  }
}

// ── 环境管理(聚焦态环境条 + 表单)────────────────────────────
const envFormOpen = ref(false)
const envFormMode = ref<'create' | 'edit'>('create')
const envForm = ref({ name: '', description: '' })
const lineRows = ref<Array<{ sys: string; line: string }>>([])
const envDelArmed = ref(false)

async function makeDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await setDefaultEnvironment(focusedEnv.value)
  await refreshEnvs()
}
async function clearDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await unsetDefaultEnvironment(focusedEnv.value)
  await refreshEnvs()
}
function openCreateEnv(): void {
  envFormMode.value = 'create'
  envForm.value = { name: '', description: '' }
  lineRows.value = []
  envDelArmed.value = false
  envFormOpen.value = true
}
function openEditEnv(): void {
  const cur = focusedCurrent.value
  if (!cur) return
  envFormMode.value = 'edit'
  envForm.value = { name: cur.name, description: cur.description }
  lineRows.value = Object.entries(cur.lines ?? {})
    .map(([sys, line]) => ({ sys, line }))
  envDelArmed.value = false
  envFormOpen.value = true
}
function linesOf(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const r of lineRows.value) {
    const sys = r.sys.trim()
    if (sys) out[sys] = r.line.trim()
  }
  return out
}
async function saveEnv(): Promise<void> {
  error.value = ''
  const sysList = lineRows.value.map((r) => r.sys.trim()).filter(Boolean)
  if (new Set(sysList).size !== sysList.length) {
    error.value = '版本线里系统名重复'
    return
  }
  try {
    if (envFormMode.value === 'create') {
      if (!envForm.value.name.trim()) {
        error.value = '环境名不能为空'
        return
      }
      const created = await createEnvironment({
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      await refreshEnvs()
      focusedEnv.value = created.id   // 建完聚焦新列(逐服务补地址)
    } else {
      if (focusedEnv.value == null) return
      await updateEnvironment(focusedEnv.value, {
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      await refreshEnvs()
    }
    await refreshInstances()   // 版本线落实例行
  } catch (e) { error.value = msg(e) }
}
async function delEnv(): Promise<void> {
  if (!focusedCurrent.value) return
  error.value = ''
  try {
    await deleteEnvironment(focusedCurrent.value.id)
    envDelArmed.value = false
    await refreshEnvs()
    await Promise.all([refreshDeps(), refreshInstances()])
    focusedEnv.value = null
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  try {
    await Promise.all([
      refreshServices(), refreshEnvs(), refreshDeps(), refreshInstances(),
    ])
  } catch (e) {
    error.value = msg(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 矩阵:首两列 sticky(服务/说明)+ 环境列聚焦高亮(卡片内双向滚动) */
.mx-wrap { overflow: auto; max-height: 42rem; }
.mx-table th:first-child,
.mx-table td.mx-svc-cell,
.mx-table th:nth-child(2),
.mx-table td.mx-desc-cell {
  position: sticky;
  background: var(--c-surface);
}
.mx-table th:first-child,
.mx-table td.mx-svc-cell { left: 0; }
.mx-table th:nth-child(2),
.mx-table td.mx-desc-cell { left: 18.75rem; }
.mx-table thead th { z-index: 2; }
.mx-table td.mx-svc-cell {
  min-width: 18.75rem;
  max-width: 21.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mx-svc-link {
  color: var(--sl-ink, var(--sl-ink));
  text-decoration: none;
  margin: 0 0.125rem;
  font-weight: 600;
}
.mx-svc-link:hover {
  color: var(--sl-accent, var(--sl-accent));
  text-decoration: underline;
}
.mx-abbr { font-size: 0.6875rem; margin-left: 0.25rem; }
.mx-desc-cell { min-width: 11.25rem; max-width: 16.25rem; }
.mx-desc {
  display: block;
  max-width: 15rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  padding: 0.125rem 0.25rem;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--sl-ink, var(--sl-ink));
}
.mx-desc:hover { color: var(--sl-accent, var(--sl-accent)); }
.mx-cell { min-width: 11.875rem; }
.mx-cell.mx-focus, .mx-table th.mx-focus { background: var(--sl-accent-soft, #eef4ff); }
.mx-url {
  display: block;
  max-width: 16.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  padding: 0.125rem 0.25rem;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--sl-ink, var(--sl-ink));
}
.mx-url:hover { color: var(--sl-accent, var(--sl-accent)); }
.mx-kind td {
  background: var(--sl-canvas, #f7f8fa);
  font-size: 0.75rem;
  font-weight: 600;
}
.grp-in { display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem; }

/* 登录口小钮:已配绿点、未配琥珀(格内第二行) */
.inst-btn {
  display: inline-block;
  margin-top: 0.25rem;
  padding: 0;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 0.6875rem;
  color: var(--sl-warn);
}
.inst-btn.ready { color: var(--sl-ok); }
.inst-btn:hover { text-decoration: underline; }

/* 对账面板 */
.recon-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-top: 0.375rem;
}
.recon-note { margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--sl-ink-3); }

/* 环境表单(自原独立部署页随迁) */
.form-grid {
  display: grid;
  grid-template-columns: 3rem minmax(0, 1fr);
  gap: 0.5rem 0.625rem;
  align-items: center;
  max-width: 40rem;
  margin-bottom: 0.625rem;
}
.form-grid .lb { font-size: 0.71875rem; color: var(--sl-ink-3); }
.line-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 40rem;
  margin-top: 0.375rem;
}

/* 弹框表单 */
.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.field-hint { font-size: 0.6875rem; color: var(--sl-ink-3); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
.field-input {
  height: 2.125rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.field-input:focus { border-color: var(--sl-accent); }
.field-input:disabled { opacity: 0.6; cursor: not-allowed; }
.field-area { height: auto; padding: 0.5rem 0.625rem; resize: vertical; }
.inst-hint { margin: 0; font-size: 0.75rem; color: var(--sl-ink-3); line-height: 1.5; }
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
</style>
