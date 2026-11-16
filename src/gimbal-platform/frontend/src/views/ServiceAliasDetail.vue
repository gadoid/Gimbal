<!--
  ServiceAliasDetail.vue — 身份面 / 目录服务详情(执行配置分层⑦:详情
  三 tab —— 概览(面信息+地址就绪矩阵)/ 字段默认值 / 凭证;配套方案
  §2.2,C2 拆分落点)。
  「服务就是没有后缀的别名」:同一详情页两种键 ——
  * 身份面键(route param = aliasName):字段默认值 tab = 本面覆盖层,
    凭证 tab = 凭证槽位 slot(凭证管理反查面板的跳转落点);
  * base 服务键(param = 目录服务名,未登记为身份面的裸服务):字段
    默认值 tab = 服务级默认层。
  锚点与槽位声明同处(以前配一个别名要在两个页面来回跳)。
  authz M2a S6:身份面不再带 baseUrl/环境归属/凭证别名 — 地址在「服务
  注册」(2026-11-13 起身份面与地址同一页),凭证改经「凭证槽位」指向
  执行者本人认证池的槽;编辑 slot 留在服务注册列表 — 本页只读键身份。
  2026-11-13 路由放开给全员(全量评估 #3):普通用户经凭证管理「被引用」
  深链进来;字段默认值 tab 按 ops.write 收起,返回按钮按能力分流。
  同日承接服务注册矩阵迁出的身份面注册(服务模式「身份面」tab:服务端
  分页 + 行内搜索 + 登记/编辑/删除;说明列的编辑位也落在本页)。
  形式与服务区域其余页共用 .slib 基座 + service-area.css 构件。
-->
<template>
  <section class="slib">
    <PageHead
      icon="key"
      :title="pageTitle"
      :count="loading ? '' : key"
      :subtitle="pageSubtitle"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div v-else-if="missing" class="slib-empty">
      <p>找不到 <code class="mono">{{ key }}</code> —— 既不是已登记身份面,也不在 Plate 目录服务内。</p>
      <p class="slib-note mt-0">身份面登记在服务注册;键拼错了也会落到这里。</p>
      <Button variant="outline" data-testid="back-admin" @click="backFromDetail">{{ backLabel }}</Button>
    </div>

    <template v-else>
      <!-- 键身份行:是什么键 / 槽位声明没声明,扫完再下钻 -->
      <div class="svc-stats">
        <span class="svc-flag" :class="isAliasMode ? 'blue' : 'ink'">{{ isAliasMode ? (isDefaultFace ? '默认面' : '身份面') : '目录服务' }}</span>
        <!-- 三态接入(P1.0):external = 第三方(无版本管理,不触发
             预览/不阻塞集成,单独统计不入基线);plate 受管不标(缺省)。 -->
        <span
          v-if="isAliasMode && row!.kind === 'external'"
          class="svc-flag amber"
          title="第三方服务(无版本管理);契约信息由步骤内联维护"
          data-testid="kind-external-flag"
        >外部</span>
        <!-- 原型 H-alias-detail:头部直接亮出槽位声明状态(红字 = 未声明) -->
        <span
          v-if="isAliasMode"
          class="svc-flag"
          :class="row!.slot ? 'green' : 'red'"
          :data-testid="row!.slot ? 'slot-bound-badge' : 'slot-unbound-badge'"
        >{{ row!.slot ? `槽位 ${row!.slot}` : '槽位未声明' }}</span>
        <span class="flex-1" />
        <Button variant="outline" size="sm" data-testid="open-grid" @click="router.push(`/services/${encodeURIComponent(baseService)}`)">
          ↗ 打开 {{ baseService }} 的画像
        </Button>
        <Button variant="outline" size="sm" data-testid="back-admin" @click="backFromDetail">{{ backLabel }}</Button>
      </div>

      <!-- 服务说明(service_meta;子页是说明的自然编辑位,矩阵列同源)-->
      <div v-if="!isAliasMode" class="svc-stats desc-line" data-testid="svc-desc-line">
        <span class="muted">说明</span>
        <template v-if="descEditing">
          <Input
            v-model="descDraft" class="max-w-[28.75rem]"
            placeholder="该服务的基本信息(做什么 / 负责人 / 注意点)"
            data-testid="svc-desc-input"
          />
          <Button size="sm" data-testid="svc-desc-save" @click="saveDesc">保存</Button>
          <Button variant="outline" size="sm" @click="descEditing = false">取消</Button>
        </template>
        <template v-else>
          <span :data-testid="`svc-desc-${key}`" class="desc-text">{{ svcDesc || '—' }}</span>
          <Button v-if="canManage" variant="outline" size="sm"
                  data-testid="svc-desc-edit" @click="startDescEdit">编辑说明</Button>
        </template>
      </div>

      <Tabs v-model="activeTab">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <!-- 身份面 = 服务模式的注册表(服务端分页,读全员;登记/编辑
               仅 canManage)—— 2026-11-13 自矩阵页迁入:服务是共用组件,
               一个服务可能挂大量身份面,独立子页才摆得下 -->
          <TabsTrigger v-if="!isAliasMode" value="faces">身份面</TabsTrigger>
          <!-- 字段默认值 = 写面(fields 取数 /carry/bindings/{s}/fields 是
               ops.write 门)—— 路由已放开给全员,此 tab 只对持能力者渲染 -->
          <TabsTrigger v-if="canManage" value="fields">字段默认值</TabsTrigger>
          <TabsTrigger v-if="isAliasMode" value="credential">凭证</TabsTrigger>
        </TabsList>

        <!-- ⑦ 概览:面信息 + 地址就绪矩阵(治理端就绪度,与执行配置
             枢纽的个人端就绪度成两半) -->
        <TabsContent value="overview">
          <div class="svc-panel">
            <div class="svc-panel-head">
              <span class="svc-panel-title">面信息</span>
              <span class="svc-panel-desc">身份面 = 名字 → 目录服务 + 凭证槽位声明(注册表行)</span>
            </div>
            <table class="ov-table" data-testid="alias-overview">
              <tbody>
                <tr v-if="isAliasMode"><th>身份面</th><td class="mono">{{ row!.aliasName }}</td></tr>
                <tr><th>目录服务</th><td class="mono">{{ baseService }}</td></tr>
                <tr v-if="isAliasMode"><th>类别</th>
                    <td>{{ row!.kind === 'external' ? '第三方(无版本管理)' : '受管(Plate 目录)' }}</td></tr>
                <tr v-if="isAliasMode"><th>凭证槽位</th>
                    <td class="mono">{{ row!.slot || '未声明(不注入该面携带的凭证)' }}</td></tr>
              </tbody>
            </table>
          </div>
          <div class="svc-panel mt-3">
            <div class="svc-panel-head">
              <span class="svc-panel-title">地址就绪矩阵</span>
              <span class="svc-panel-desc">各环境部署行((目录服务, 环境) → 地址);缺口点跳「服务注册」</span>
            </div>
            <p v-if="!envs.length" class="cred-note">平台还没有环境 — 地址无从配置。</p>
            <table v-else class="ov-table" data-testid="alias-ready-matrix">
              <thead><tr><th>环境</th><th>地址</th></tr></thead>
              <tbody>
                <tr v-for="e in envs" :key="e.id" :data-testid="`ready-env-${e.name}`">
                  <td>{{ e.name }}<template v-if="e.is_default"> · 默认</template></td>
                  <td>
                    <span v-if="deployUrl(e.id)" class="mono">{{ deployUrl(e.id) }}</span>
                    <!-- 缺口:持写权者深链服务注册矩阵补录;普通用户只读提示
                         (不再给一个点了会被弹回的链接) -->
                    <router-link v-else-if="canManage"
                      to="/service-admin"
                      class="svc-link warn-link">缺 — 去服务注册 ↗</router-link>
                    <span v-else class="svc-flag amber">缺 — 由管理员维护</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </TabsContent>

        <!-- ⑦ 身份面注册表(服务模式;服务端分页 + 行内搜索)──────── -->
        <TabsContent v-if="!isAliasMode" value="faces">
          <div class="svc-panel">
            <div class="svc-panel-head">
              <span class="svc-panel-title">身份面</span>
              <span class="svc-panel-desc">
                「{{ key }}」登记的身份面(名字 → 本服务 + 凭证槽位);
                执行注入按执行者本人认证池的同名槽解析
              </span>
              <span class="svc-panel-right">
                <input
                  v-model="faces.qDraft" class="slib-search faces-q"
                  placeholder="搜 alias / 槽位" data-testid="faces-q"
                  @input="onFacesQ"
                />
                <Button v-if="canManage" size="sm" data-testid="faces-open-create"
                        @click="openFaceCreate">+ 登记身份面</Button>
              </span>
            </div>

            <!-- 登记 / 编辑槽位(canManage;前缀恒为本服务)-->
            <div
              v-if="canManage && (facesOpen || !!faceEditing)"
              class="flex flex-wrap items-center gap-2 pt-2"
              data-testid="faces-form"
            >
              <span
                class="mono box-border inline-flex h-9 w-[9.375rem] shrink-0 items-center justify-center overflow-hidden rounded-md border bg-signal-hairline px-2 text-[0.8125rem] font-bold text-signal-think"
                data-testid="face-prefix"
              >{{ key }}-</span>
              <Input
                v-model="faceSuffix" class="w-[12.5rem]"
                placeholder="后缀(如 uat)" :disabled="!!faceEditing"
                data-testid="face-suffix"
              />
              <Input
                v-model="faceSlot" class="w-[11.25rem]"
                placeholder="展示名(可选,如 maker)" data-testid="face-slot"
              />
              <Button data-testid="face-save" :disabled="faceSaveDisabled || faceSaving" @click="saveFace">
                {{ faceEditing ? '保存' : '登记' }}
              </Button>
              <Button variant="outline" data-testid="face-cancel" @click="cancelFace">取消</Button>
            </div>

            <table class="ov-table mt-2" data-testid="faces-table">
              <thead><tr><th>身份面</th><th>展示名</th><th style="width:8.25rem" class="c-center">操作</th></tr></thead>
              <tbody>
                <tr v-for="a in faces.items" :key="a.aliasName" :data-testid="`face-row-${a.aliasName}`">
                  <td>
                    <span class="mono">{{ a.aliasName }}</span>
                    <span
                      v-if="a.kind === 'external'" class="svc-flag amber ml-1"
                      title="第三方服务(无版本管理):不触发预览、不阻塞集成"
                    >外部</span>
                    <span
                      v-else-if="a.aliasName === a.baseService" class="svc-flag blue ml-1"
                      title="无后缀身份面 = 该目录服务的默认面;三层查找:精确命中身份面 → 默认面 → 全局共享默认"
                    >默认面</span>
                  </td>
                  <td class="mono">{{ a.display || '—' }}</td>
                  <td class="c-center">
                    <div class="row-acts">
                      <button
                        type="button" class="svc-link"
                        :data-testid="`face-detail-${a.aliasName}`"
                        @click="router.push(`/service-admin/${encodeURIComponent(a.aliasName)}`)"
                      >详情</button>
                      <button
                        v-if="canManage" type="button" class="svc-link"
                        :data-testid="`face-edit-${a.aliasName}`" @click="faceEdit(a)"
                      >编辑</button>
                      <button
                        v-if="canManage" type="button" class="svc-link danger"
                        :data-testid="`face-del-${a.aliasName}`" @click="removeFace(a)"
                      >删除</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="faces.loaded && !faces.items.length">
                  <td colspan="3" class="c-center">
                    <span class="muted">
                      {{ faces.q ? '没有匹配的身份面' : '该服务还没有登记身份面 —— 身份面 = 服务名-后缀' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="faces.pageCount > 1" class="faces-pager">
              <button type="button" class="svc-link" :disabled="faces.page <= 1"
                      data-testid="faces-page-prev" @click="turnFacePage(-1)">← 上一页</button>
              <span class="muted">第 {{ faces.page }} / {{ faces.pageCount }} 页</span>
              <button type="button" class="svc-link" :disabled="faces.page >= faces.pageCount"
                      data-testid="faces-page-next" @click="turnFacePage(1)">下一页 →</button>
            </div>
          </div>
        </TabsContent>

        <TabsContent v-if="canManage" value="fields">
          <ServiceBindingEditor
            :service-key="key"
            :base-service="baseService"
          />
        </TabsContent>

        <TabsContent v-if="isAliasMode" value="credential">
          <div class="svc-panel">
            <div class="svc-panel-head">
              <span class="svc-panel-title">
                <span class="icon-badge" aria-hidden="true">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="4" y="11" width="16" height="10" rx="2" />
                    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                  </svg>
                </span>
                凭证槽位
              </span>
              <span class="svc-panel-desc">身份面声明的注入槽位(slot)— 执行注入按此槽取凭证,地址按环境取部署地址</span>
            </div>
            <p class="cred-line">
              凭证槽位:<code class="mono font-semibold">{{ row!.slot || '未声明' }}</code>
            </p>
            <p class="cred-note">
              执行时按<b>执行者本人</b>凭证管理池的同名槽解析 — 同一身份面被不同人执行时各拿各的同槽凭证;
              凭证本体的建 / 测连通 / 轮换在凭证管理。
            </p>
            <div class="mt-2">
              <Button variant="outline" size="sm" data-testid="open-auths" @click="router.push('/auths')">打开凭证管理</Button>
            </div>
          </div>
        </TabsContent>

      </Tabs>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * ServiceAliasDetail —— 单键详情(⑦ 三 tab):概览(面信息+地址就绪
 * 矩阵)+ 字段默认值编辑 + 凭证槽位展示。
 * 键的合法性判定:listAliases 命中 → 身份面模式;否则目录服务名命中 →
 * 服务模式;都 miss → missing(不猜)。?tab=credential 支持外部深链
 * (凭证管理反查面板的身份面 chip;M2a S6 起该 tab 展示凭证槽位 slot)。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { loadCatalogServiceNames, loadCatalogServiceRows } from '@/utils/catalog-services'
import {
  listAllAliases, listAliases, createAlias, patchAlias, deleteAlias,
  type ServiceAliasRow,
} from '@/api/service-aliases'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { listDeployments } from '@/api/deployments'
import { listServiceMeta, putServiceMeta } from '@/api/service-meta'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/** 字段默认值 tab 门:fields 取数是 ops.write 面(carry.py /fields)。
 *  返回分流:持写权者回治理页;普通用户(被引用深链进来)回凭证管理 —
 *  不给一个点了会被路由守卫弹回 /home 的「返回服务注册」。 */
const canManage = computed(() => auth.can('ops.write'))
const backLabel = computed(() => (canManage.value ? '返回服务注册' : '返回凭证管理'))
function backFromDetail(): void {
  router.push(canManage.value ? '/service-admin' : '/auths')
}

const key = computed(() => String(route.params.alias ?? ''))
const loading = ref(true)
const aliases = ref<ServiceAliasRow[]>([])
const catalogNames = ref<string[]>([])

const row = computed(() => aliases.value.find((a) => a.aliasName === key.value) ?? null)
const isAliasMode = computed(() => row.value !== null)
const missing = computed(() =>
  !loading.value && row.value === null && !catalogNames.value.includes(key.value))
const baseService = computed(() => row.value?.baseService ?? key.value)
/** 无后缀身份面 = 该目录服务的默认面(⑦ 术语降位) */
const isDefaultFace = computed(() =>
  row.value !== null && row.value.aliasName === row.value.baseService)

// ⑦ 概览:地址就绪矩阵数据(读面;失败降级空表)
const envs = ref<EnvironmentRow[]>([])
const deploys = ref<Array<{ baseService: string; envId: number; baseUrl: string }>>([])
function deployUrl(envId: number): string | null {
  const hit = deploys.value.find(
    (d) => d.baseService === baseService.value && d.envId === envId)
  return hit?.baseUrl ?? null
}

const pageTitle = computed(() =>
  loading.value ? '键详情' : isAliasMode.value ? '别名详情' : '服务详情')
/** 三层回退是这个页面存在的全部理由,所以写在副标而不是藏在卡里 */
const pageSubtitle = computed(() =>
  isAliasMode.value
    ? `绑定键 = 别名全名;运行时解析:精确命中本别名 → ${baseService.value} 服务级默认 → 全局默认 → 无行 = 不注入`
    : '绑定键 = 服务名(服务级默认层);运行时解析:精确命中本服务 → 全局默认 → 无行 = 不注入')

const activeTab = ref(
  route.query.tab === 'credential' ? 'credential'
  : route.query.tab === 'faces' ? 'faces'
  // fields tab 按能力收起:无 ops.write 的深链回落概览,不落空 tab
  : route.query.tab === 'fields' && auth.can('ops.write') ? 'fields' : 'overview')

// ── 服务说明(service_meta;子页是说明的自然编辑位)──────────────
const svcDesc = ref('')
const descEditing = ref(false)
const descDraft = ref('')

function startDescEdit(): void {
  descDraft.value = svcDesc.value
  descEditing.value = true
}
async function saveDesc(): Promise<void> {
  try {
    const row = await putServiceMeta(key.value, descDraft.value.trim())
    svcDesc.value = row.description
    descEditing.value = false
    toast.success('已保存')
  } catch (e) {
    showError('保存说明', e)
  }
}

// ── 身份面注册表(服务模式;服务端分页,永不全量)────────────────
const SUB_PAGE_SIZE = 10
const faces = reactive({
  items: [] as ServiceAliasRow[],
  total: 0,
  page: 1,
  pageCount: 1,
  q: '',
  qDraft: '',
  loading: false,
  loaded: false,
})
const facesOpen = ref(false)
const faceSuffix = ref('')
const faceSlot = ref('')
const faceSaving = ref(false)
const faceEditing = ref<string | null>(null)

/** 登记的 kind 由目录推导:integration 系统的第三方服务显式 external
 *  (b2-8:external 不派生,须带 baseService),sut 走 plate 派生。 */
const baseKind = ref<string>('sut')
const isExternalBase = computed(() => baseKind.value === 'integration')

const faceSaveDisabled = computed(() =>
  !faceEditing.value && !faceSuffix.value.trim())

function resetFaces(): void {
  faces.items = []
  faces.total = 0
  faces.page = 1
  faces.pageCount = 1
  faces.q = ''
  faces.qDraft = ''
  faces.loaded = false
  cancelFace()
}

async function loadFaces(): Promise<void> {
  faces.loading = true
  try {
    const env = await listAliases({
      base: key.value,
      q: faces.q.trim() || undefined,
      page: faces.page,
      page_size: SUB_PAGE_SIZE,
    })
    faces.items = env.items
    faces.total = env.total
    faces.pageCount = Math.max(1, Math.ceil(env.total / SUB_PAGE_SIZE))
    faces.loaded = true
  } catch (e) {
    showError('身份面', e)
  } finally {
    faces.loading = false
  }
}

const qTimer = ref<ReturnType<typeof setTimeout> | undefined>(undefined)
function onFacesQ(): void {
  clearTimeout(qTimer.value)
  qTimer.value = setTimeout(() => {
    faces.q = faces.qDraft
    faces.page = 1
    void loadFaces()
  }, 300)
}

function turnFacePage(delta: number): void {
  const next = faces.page + delta
  if (next < 1 || next > faces.pageCount) return
  faces.page = next
  void loadFaces()
}

function openFaceCreate(): void {
  faceEditing.value = null
  faceSuffix.value = ''
  faceSlot.value = ''
  facesOpen.value = true
}
function faceEdit(a: ServiceAliasRow): void {
  facesOpen.value = false
  faceEditing.value = a.aliasName
  // 输入框只写后缀(前缀恒为本服务)
  const prefix = `${key.value}-`
  faceSuffix.value = a.aliasName.startsWith(prefix)
    ? a.aliasName.slice(prefix.length) : a.aliasName
  faceSlot.value = a.display ?? ''
}
function cancelFace(): void {
  facesOpen.value = false
  faceEditing.value = null
  faceSuffix.value = ''
  faceSlot.value = ''
}
async function saveFace(): Promise<void> {
  faceSaving.value = true
  try {
    if (faceEditing.value) {
      // 身份面是主键:编辑只动展示名(registry:slot 恒=条目名,不可改)
      await patchAlias(faceEditing.value, { display: faceSlot.value.trim() || null })
      toast.success('已保存')
    } else {
      await createAlias({
        aliasName: `${key.value}-${faceSuffix.value.trim()}`,
        display: faceSlot.value.trim(),
        kind: isExternalBase.value ? 'external' : 'plate',
        baseService: isExternalBase.value ? key.value : null,
      })
      toast.success('已登记')
    }
    cancelFace()
    faces.page = 1
    await loadFaces()
  } catch (e) {
    showError('保存身份面', e) // 409(重名/裸声明)走统一错误文案
  } finally {
    faceSaving.value = false
  }
}
async function removeFace(a: ServiceAliasRow): Promise<void> {
  const ok = await confirmAction(
    '已声明的槽位随行删除;carry 别名键的绑定行不在此表,不受影响。',
    `删除身份面 ${a.aliasName}?`,
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await deleteAlias(a.aliasName)
    toast.success('已删除')
    await loadFaces()
  } catch (e) {
    showError('删除身份面', e)
  }
}


/** 服务模式的旁路面:说明 + 目录 kind(登记 kind 推导)+ 身份面分页。
 *  键切换(详情行点回服务等)时全部重置。 */
async function loadServiceSides(): Promise<void> {
  svcDesc.value = ''
  descEditing.value = false
  resetFaces()
  if (isAliasMode.value) return
  listServiceMeta()
    .then((rows) => {
      svcDesc.value = rows.find((r) => r.serviceName === key.value)?.description ?? ''
    })
    .catch(() => { /* 说明拉不到 — 显「—」 */ })
  loadCatalogServiceRows()
    .then((rows) => {
      baseKind.value = rows.find((r) => r.name === key.value)?.kind ?? 'sut'
    })
    .catch(() => { /* 目录拉不到 — 按 sut 派生 */ })
  await loadFaces()
}

onMounted(async () => {
  try {
    ;[aliases.value, catalogNames.value] = await Promise.all([
      listAllAliases(),
      loadCatalogServiceNames().catch((): string[] => []),
    ])
  } catch (e) {
    showError('加载', e)
  } finally {
    loading.value = false
  }
  // 概览旁路数据(失败静默降级)
  listEnvironments().then((rows) => { envs.value = rows }).catch(() => {})
  listDeployments().then((rows) => { deploys.value = rows }).catch(() => {})
  void loadServiceSides()
})

// 键变化(同页在 身份面行详情 ↔ 服务模式 之间跳)→ 旁路面重置
watch(key, () => { void loadServiceSides() })
// 首次切到身份面 tab 且未加载过 → 取数
watch(activeTab, (v) => {
  if (v === 'faces' && !isAliasMode.value && !faces.loaded) void loadFaces()
})

</script>

<style scoped>
.ov-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.ov-table th, .ov-table td {
  text-align: left; padding: 0.375rem 0.625rem;
  border-bottom: 1px solid var(--sl-divider);
}
.ov-table th { color: var(--sl-ink-3); font-weight: 600; width: 7.5rem; }
.desc-line { margin-top: -0.375rem; }
.desc-text { font-size: 0.75rem; }
.faces-q { height: 1.875rem; width: 12.5rem; }
.faces-pager {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 0.5rem;
  font-size: 0.71875rem;
}
.cred-line {
  margin: 0 0 0.375rem;
  font-size: 0.75rem;
  color: var(--sl-ink);
}

.cred-note {
  margin: 0;
  font-size: 0.6875rem;
  line-height: 1.7;
  color: var(--sl-ink-3);
}
</style>
