<!--
  ServiceAliasDetail.vue — 身份条目详情 / 服务子页(registry 重构 §3.2)。
  单键双模式,条目化口径(2026-11-16):
  * 条目键(route param = aliasName):概览(条目信息 + 账户装载)+ 地址
    就绪矩阵(API 地址 × 实例登录口/版本线)+ 字段默认值 + 账户装载 tab
    (凭证管理反查面板「N 条目」chip 的深链落点,?tab=credential);
  * 服务键(param = 服务名,主档 ∪ plate 目录):身份条目注册表 tab
    (服务端分页 + 行内搜索 + 登记/编辑/删除;登记带 环境/ref 维度)+
    说明编辑(service_meta 门面 → 主档 description)。
  四层落位:条目(env 必填)按 ref 引用账户池(default=取同坐标默认账户 |
  username=指定用户名);登录口/版本线在 (system, env) 实例;API 地址在
  deployments。系统归属自主档查得 —— 未登记主档的服务无实例坐标。
  2026-11-13 路由放开给全员:普通用户经凭证管理「被引用」深链进来;
  字段默认值 tab 按 ops.write 收起,返回按钮按能力分流。
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
      <p>找不到 <code class="mono">{{ key }}</code> —— 既不是已登记身份条目,也不在服务主档 / Plate 目录内。</p>
      <p class="slib-note mt-0">身份条目登记在服务子页;键拼错了也会落到这里。</p>
      <Button variant="outline" data-testid="back-admin" @click="backFromDetail">{{ backLabel }}</Button>
    </div>

    <template v-else>
      <!-- 键身份行:是什么键 / 环境 / 账户装载 ref,扫完再下钻 -->
      <div class="svc-stats">
        <span class="svc-flag" :class="isAliasMode ? (isDefaultEntry ? 'ink' : 'blue') : 'ink'">{{ isAliasMode ? (isDefaultEntry ? '默认条目' : '身份条目') : '服务' }}</span>
        <!-- 三态接入(P1.0):external = 第三方(无版本管理,不触发
             预览/不阻塞集成,单独统计不入基线);plate 受管不标(缺省)。 -->
        <span
          v-if="isAliasMode && row!.kind === 'external'"
          class="svc-flag amber"
          title="第三方服务(无版本管理);契约信息由步骤内联维护"
          data-testid="kind-external-flag"
        >外部</span>
        <!-- 条目环境(新架构必填;红 = 旧数据未指定,执行将报缺) -->
        <span
          v-if="isAliasMode"
          class="svc-flag"
          :class="row!.envId ? 'blue' : 'red'"
          data-testid="env-badge"
          :title="row!.envId ? '条目归属环境(实体键)' : '未指定环境 — 旧数据,执行预检将报缺'"
        >{{ row!.envId ? `环境 ${envNameOf(row!.envId)}` : '环境未指定' }}</span>
        <!-- 账户装载徽标:ref 默认 / ref 用户名(registry 头部徽标新口径) -->
        <span
          v-if="isAliasMode"
          class="svc-flag"
          :class="row!.refMode === 'default' ? 'green' : 'blue'"
          data-testid="ref-mode-badge"
          :title="row!.refMode === 'default'
            ? '取执行者池内该 system 的默认账户(0059 起按 (池, 系统) 唯一)'
            : '取同坐标下指定用户名的账户'"
        >{{ row!.refMode === 'default' ? 'ref 默认' : `ref 用户名·${row!.refUsername ?? '?'}` }}</span>
        <span class="flex-1" />
        <Button variant="outline" size="sm" data-testid="open-grid" @click="router.push(`/services/${encodeURIComponent(baseService)}`)">
          ↗ 打开 {{ baseService }} 的画像
        </Button>
        <Button variant="outline" size="sm" data-testid="back-admin" @click="backFromDetail">{{ backLabel }}</Button>
      </div>

      <!-- 服务说明(主档 description;子页是说明的自然编辑位,矩阵列同源)-->
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
          <!-- 身份条目 = 服务模式的注册表(服务端分页,读全员;登记/编辑
               仅 canManage)—— 服务是共用组件,一个服务可能挂大量条目,
               独立子页才摆得下 -->
          <TabsTrigger v-if="!isAliasMode" value="faces">身份条目</TabsTrigger>
          <!-- 字段默认值 = 写面(fields 取数 /carry/bindings/{s}/fields 是
               ops.write 门)—— 路由已放开给全员,此 tab 只对持能力者渲染 -->
          <TabsTrigger v-if="canManage" value="fields">字段默认值</TabsTrigger>
          <TabsTrigger v-if="isAliasMode" value="credential">账户装载</TabsTrigger>
        </TabsList>

        <!-- 概览:条目信息 + 地址就绪矩阵(API 地址 × 实例登录口/版本线,
             治理端就绪度,与执行配置枢纽的个人端就绪度成两半) -->
        <TabsContent value="overview">
          <div class="svc-panel">
            <div class="svc-panel-head">
              <span class="svc-panel-title">{{ isAliasMode ? '条目信息' : '服务信息' }}</span>
              <span class="svc-panel-desc">
                {{ isAliasMode
                  ? '身份条目 = 名字 → 基础服务 + 环境 + 账户引用(注册表行)'
                  : '服务主档行(系统归属决定实例坐标)' }}
              </span>
            </div>
            <table class="ov-table" data-testid="alias-overview">
              <tbody>
                <tr v-if="isAliasMode"><th>身份条目</th><td class="mono">{{ row!.aliasName }}</td></tr>
                <tr><th>{{ isAliasMode ? '基础服务' : '服务' }}</th><td class="mono">{{ baseService }}</td></tr>
                <tr><th>系统</th>
                  <td>
                    <span v-if="systemOf" class="mono">{{ systemOf }}</span>
                    <span v-else class="svc-flag amber" title="先在服务注册登记主档,才有 (系统, 环境) 实例坐标">未登记主档</span>
                  </td>
                </tr>
                <tr v-if="isAliasMode"><th>环境</th>
                  <td>
                    <span v-if="row!.envId" class="mono">{{ envNameOf(row!.envId) }}</span>
                    <span v-else class="svc-flag red">未指定(旧数据;执行预检将报缺)</span>
                  </td>
                </tr>
                <tr v-if="isAliasMode"><th>类别</th>
                    <td>{{ kindLabel(row!.kind) }}</td></tr>
                <tr v-if="isAliasMode"><th>账户装载</th>
                    <td data-testid="ref-line">
                      <template v-if="row!.refMode === 'default'">
                        ref 默认 — 取执行者池内系统 {{ systemOf ?? '?' }} 的默认账户(按系统唯一,跨环境共用)
                      </template>
                      <template v-else>
                        ref 用户名 — 取 username = <code class="mono">{{ row!.refUsername || '?' }}</code> 的账户
                      </template>
                    </td></tr>
              </tbody>
            </table>
          </div>
          <div class="svc-panel mt-3">
            <div class="svc-panel-head">
              <span class="svc-panel-title">地址就绪矩阵</span>
              <span class="svc-panel-desc">
                (服务, 环境) → API 地址(deployments);(系统, 环境) → 登录口/版本线(实例);
                缺口点跳「服务注册」
              </span>
            </div>
            <p v-if="!envs.length" class="cred-note">平台还没有环境 — 地址无从配置。</p>
            <table v-else class="ov-table" data-testid="alias-ready-matrix">
              <thead><tr><th>环境</th><th>API 地址</th><th>登录口</th><th>版本线</th></tr></thead>
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
                  <td>
                    <!-- 未登记主档 → 无系统归属,实例无从谈起 -->
                    <span v-if="!systemOf" class="muted" title="服务未登记主档,无 (系统, 环境) 实例坐标">—</span>
                    <span v-else-if="instOf(systemOf, e.id)?.loginUrl"
                          class="mono" :data-testid="`ready-login-${e.name}`"
                          :title="`实例登录口(系统 ${systemOf} 共享)— 拨测与登录走此地址`"
                    >{{ instOf(systemOf, e.id)!.loginUrl }}</span>
                    <router-link v-else-if="canManage"
                      to="/service-admin"
                      class="svc-link warn-link">缺 — 去服务注册 ↗</router-link>
                    <span v-else class="svc-flag amber">缺 — 由管理员维护</span>
                  </td>
                  <td>
                    <span v-if="systemOf && instOf(systemOf, e.id)?.line" class="mono">{{ instOf(systemOf, e.id)!.line }}</span>
                    <span v-else class="muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </TabsContent>

        <!-- 身份条目注册表(服务模式;服务端分页 + 行内搜索)──────── -->
        <TabsContent v-if="!isAliasMode" value="faces">
          <div class="svc-panel">
            <div class="svc-panel-head">
              <span class="svc-panel-title">身份条目</span>
              <span class="svc-panel-desc">
                「{{ key }}」登记的身份条目(条目名 → 本服务 + 环境 + 账户引用);
                执行注入按 ref 取执行者本人池的账户
              </span>
              <span class="svc-panel-right">
                <input
                  v-model="faces.qDraft" class="slib-search faces-q"
                  placeholder="搜条目 / 展示名" data-testid="faces-q"
                  @input="onFacesQ"
                />
                <Button v-if="canManage" size="sm" data-testid="faces-open-create"
                        @click="openFaceCreate">+ 登记身份条目</Button>
              </span>
            </div>

            <!-- 登记 / 编辑(canManage;条目名前缀恒为本服务)-->
            <div
              v-if="canManage && (facesOpen || !!faceEditing)"
              class="faces-form"
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
              <select
                v-model.number="faceEnv" class="face-select w-[9.375rem]"
                :disabled="!!faceEditing"
                :title="faceEditing ? '环境是条目实体键,不可改' : '条目归属环境(必填)'"
                data-testid="face-env"
              >
                <option v-for="e in envs" :key="e.id" :value="e.id">
                  {{ e.name }}{{ e.is_default ? ' · 默认' : '' }}
                </option>
              </select>
              <Input
                v-model="faceSlot" class="w-[11.25rem]"
                placeholder="展示名(可选,如 maker)" data-testid="face-slot"
              />
              <select
                v-model="faceRefMode" class="face-select w-[8.75rem]"
                title="账户引用:默认 = 取同坐标默认账户;用户名 = 指定账户"
                data-testid="face-ref-mode"
              >
                <option value="default">ref 默认账户</option>
                <option value="username">ref 指定用户名</option>
              </select>
              <Input
                v-if="faceRefMode === 'username'"
                v-model="faceRefUser" class="w-[10rem]"
                placeholder="账户用户名" data-testid="face-ref-username"
              />
              <Button data-testid="face-save" :disabled="faceSaveDisabled || faceSaving" @click="saveFace">
                {{ faceEditing ? '保存' : '登记' }}
              </Button>
              <Button variant="outline" data-testid="face-cancel" @click="cancelFace">取消</Button>
            </div>

            <table class="ov-table mt-2" data-testid="faces-table">
              <thead><tr>
                <th>身份条目</th><th>环境</th><th>账户装载</th><th>展示名</th>
                <th style="width:8.25rem" class="c-center">操作</th>
              </tr></thead>
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
                      title="无后缀条目 = 该服务的默认条目;三层查找:精确命中条目 → 默认条目 → 全局共享默认"
                    >默认条目</span>
                  </td>
                  <td>
                    <span v-if="a.envId" class="mono">{{ envNameOf(a.envId) }}</span>
                    <span v-else class="svc-flag red" title="旧数据;执行预检将报缺">未指定</span>
                  </td>
                  <td>
                    <span
                      v-if="a.refMode === 'default'" class="svc-flag green"
                      title="取执行者池内该 system 的默认账户(0059 起按 (池, 系统) 唯一)"
                    >默认账户</span>
                    <span
                      v-else class="mono"
                      :title="`取同坐标下用户名 ${a.refUsername || '?'} 的账户`"
                    >用户名 {{ a.refUsername || '?' }}</span>
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
                  <td colspan="5" class="c-center">
                    <span class="muted">
                      {{ faces.q ? '没有匹配的身份条目' : '该服务还没有登记身份条目 —— 条目名 = 服务名-后缀' }}
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
                账户装载
              </span>
              <span class="svc-panel-desc">条目按 ref 引用账户池;登录口按 (系统, 环境) 实例解析,不在凭证侧</span>
            </div>
            <p class="cred-line" data-testid="cred-ref-line">
              账户引用:<b>ref {{ row!.refMode === 'default' ? '默认' : '用户名' }}</b><template v-if="row!.refMode === 'username'">
                — <code class="mono font-semibold">{{ row!.refUsername || '?' }}</code></template>
            </p>
            <p class="cred-note">
              ref 默认 = 取<b>执行者本人池</b>({{ systemOf ?? '?' }} × {{ row!.envId ? envNameOf(row!.envId) : '?' }})的默认账户;
              ref 用户名 = 取同坐标下指定用户名的账户。同一账户可被多个条目装载 —— 改密一处,所有装载它的条目/场景同时生效。
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
 * ServiceAliasDetail —— 单键详情:概览(条目信息 + 地址就绪矩阵)+
 * 身份条目注册表(服务模式)+ 字段默认值编辑 + 账户装载展示。
 * 键的合法性判定:listAliases 命中 → 条目模式;否则服务名命中
 * (主档 ∪ plate 目录,§2.2 校验集合)→ 服务模式;都 miss → missing(不猜)。
 * ?tab=credential 支持外部深链(凭证管理反查面板的条目 chip)。
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
import { listServices, listInstances, type ServiceRow, type InstanceRow } from '@/api/services'
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
const baseService = computed(() => row.value?.baseService ?? key.value)
/** 无后缀条目 = 该服务的默认条目 */
const isDefaultEntry = computed(() =>
  row.value !== null && row.value.aliasName === row.value.baseService)

// ── 概览数据(读面;失败降级空表)──────────────────────────────
const envs = ref<EnvironmentRow[]>([])
const deploys = ref<Array<{ baseService: string; envId: number; baseUrl: string }>>([])
/** 主档(系统归属)+ 实例((system, env) → 登录口/版本线) */
const svcRows = ref<ServiceRow[]>([])
const instances = ref<InstanceRow[]>([])

function deployUrl(envId: number): string | null {
  const hit = deploys.value.find(
    (d) => d.baseService === baseService.value && d.envId === envId)
  return hit?.baseUrl ?? null
}
/** 系统归属自主档;未登记 → null(无实例坐标)。 */
const systemOf = computed(() =>
  svcRows.value.find((s) => s.name === baseService.value)?.system ?? null)
function instOf(system: string, envId: number): InstanceRow | undefined {
  return instances.value.find((i) => i.system === system && i.envId === envId)
}
function envNameOf(envId: number): string {
  return envs.value.find((e) => e.id === envId)?.name ?? `环境#${envId}`
}
function kindLabel(kind: string): string {
  if (kind === 'external') return '第三方(无版本管理)'
  if (kind === 'integration') return '集成件(Plate)'
  return '受管(Plate 目录)'
}

/** 键合法性:主档 ∪ plate 目录(§2.2;external 行不受目录可达性影响) */
const missing = computed(() =>
  !loading.value && row.value === null && !catalogNames.value.includes(key.value)
  && !svcRows.value.some((s) => s.name === key.value))

const pageTitle = computed(() =>
  loading.value ? '键详情' : isAliasMode.value ? '身份条目详情' : '服务详情')
/** 三层回退是这个页面存在的全部理由,所以写在副标而不是藏在卡里 */
const pageSubtitle = computed(() =>
  isAliasMode.value
    ? `绑定键 = 条目名;运行时解析:精确命中本条目 → ${baseService.value} 服务级默认 → 全局默认 → 无行 = 不注入`
    : '绑定键 = 服务名(服务级默认层);运行时解析:精确命中本服务 → 全局默认 → 无行 = 不注入')

/** query.tab → tab 值(fields 按能力收起:无 ops.write 的深链回落概览) */
function tabFromQuery(): string {
  const t = String(route.query.tab ?? '')
  if (t === 'credential') return 'credential'
  if (t === 'faces') return 'faces'
  if (t === 'fields' && auth.can('ops.write')) return 'fields'
  return 'overview'
}

/** credential tab 只在条目模式有内容(v-if=isAliasMode)—— 键切到
 *  服务模式(浏览器返回等)时停在 credential 会整屏空白 */
function tabValidForMode(t: string): boolean {
  return t !== 'credential' || isAliasMode.value
}

const activeTab = ref(tabFromQuery())
if (!tabValidForMode(activeTab.value)) activeTab.value = 'overview'

// ── 服务说明(主档 description;子页是说明的自然编辑位)──────────
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

// ── 身份条目注册表(服务模式;服务端分页,永不全量)──────────────
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
/** 条目实体维度:环境(必填,实体键不可改)+ 账户引用 ref */
const faceEnv = ref<number | null>(null)
const faceRefMode = ref<'default' | 'username'>('default')
const faceRefUser = ref('')
const faceSaving = ref(false)
const faceEditing = ref<string | null>(null)

/** 登记的 kind 由目录推导:integration 系统的第三方服务显式 external
 *  (b2-8:external 不派生,须带 baseService),sut 走 plate 派生。 */
const baseKind = ref<string>('sut')
const isExternalBase = computed(() => baseKind.value === 'integration')

const faceSaveDisabled = computed(() =>
  !faceEditing.value && (!faceSuffix.value.trim() || !faceEnv.value))

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
    showError('身份条目', e)
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
  // 环境缺省 = 平台默认环境(无默认取第一个;无环境 → 保存钮守门)
  faceEnv.value = envs.value.find((e) => e.is_default)?.id ?? envs.value[0]?.id ?? null
  faceRefMode.value = 'default'
  faceRefUser.value = ''
  facesOpen.value = true
}
function faceEdit(a: ServiceAliasRow): void {
  facesOpen.value = false
  faceEditing.value = a.aliasName
  // 输入框只写后缀(前缀恒为本服务)
  const prefix = `${key.value}-`
  faceSuffix.value = a.aliasName.startsWith(prefix)
    ? a.aliasName.slice(prefix.length) : a.aliasName
  faceEnv.value = a.envId
  faceRefMode.value = a.refMode === 'username' ? 'username' : 'default'
  faceRefUser.value = a.refUsername ?? ''
  faceSlot.value = a.display ?? ''
}
function cancelFace(): void {
  facesOpen.value = false
  faceEditing.value = null
  faceSuffix.value = ''
  faceSlot.value = ''
  faceEnv.value = null
  faceRefMode.value = 'default'
  faceRefUser.value = ''
}
async function saveFace(): Promise<void> {
  if (!faceEditing.value && !faceEnv.value) return
  faceSaving.value = true
  try {
    if (faceEditing.value) {
      // 条目名是主键:编辑只动展示名与账户引用(ref);环境是实体键不可改
      await patchAlias(faceEditing.value, {
        display: faceSlot.value.trim() || null,
        refMode: faceRefMode.value,
        refUsername: faceRefMode.value === 'username'
          ? (faceRefUser.value.trim() || null) : null,
      })
      toast.success('已保存')
    } else {
      const payload: Parameters<typeof createAlias>[0] = {
        aliasName: `${key.value}-${faceSuffix.value.trim()}`,
        display: faceSlot.value.trim(),
        kind: isExternalBase.value ? 'external' : 'plate',
        baseService: isExternalBase.value ? key.value : null,
        envId: faceEnv.value,
        refMode: faceRefMode.value,
      }
      if (faceRefMode.value === 'username' && faceRefUser.value.trim()) {
        payload.refUsername = faceRefUser.value.trim()
      }
      await createAlias(payload)
      toast.success('已登记')
    }
    cancelFace()
    faces.page = 1
    await loadFaces()
  } catch (e) {
    showError('保存身份条目', e) // 409(重名/裸声明)走统一错误文案
  } finally {
    faceSaving.value = false
  }
}
async function removeFace(a: ServiceAliasRow): Promise<void> {
  const ok = await confirmAction(
    '场景里引用该条目名的模板下次运行将报缺;carry 条目键的绑定行不在此表,不受影响。',
    `删除身份条目 ${a.aliasName}?`,
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await deleteAlias(a.aliasName)
    toast.success('已删除')
    await loadFaces()
  } catch (e) {
    showError('删除身份条目', e)
  }
}


/** 服务模式的旁路面:说明 + 目录 kind(登记 kind 推导)+ 条目分页。
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
  listServices()
    .then((out) => { svcRows.value = out.services })
    .catch(() => { /* 主档拉不到 — 系统列显「未登记」 */ })
  listInstances().then((rows) => { instances.value = rows }).catch(() => {})
  void loadServiceSides()
})

// 键变化(同页在 条目行详情 ↔ 服务模式 之间跳)→ 旁路面重置
watch(key, () => { void loadServiceSides() })
// query.tab 深链在同组件内变化也生效,且按当前键模式兜底(收尾 5a:
// 此前仅在 mount 求值一次 —— 键切回服务模式后 activeTab 停在
// credential,其内容 v-if=isAliasMode → 整屏空白无兜底)
watch([key, () => route.query.tab], () => {
  const t = tabFromQuery()
  activeTab.value = tabValidForMode(t) ? t : 'overview'
})
// 首次切到身份条目 tab 且未加载过 → 取数
watch(activeTab, (v) => {
  if (v === 'faces' && !isAliasMode.value && !faces.loaded) void loadFaces()
})

</script>

<style scoped>
.ov-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.ov-table th, .ov-table td {
  text-align: left;
  padding: 0.375rem 0.625rem;
  border-bottom: 1px solid var(--sl-divider);
}
.ov-table th { color: var(--sl-ink-3); font-weight: 600; width: 7.5rem; }
.desc-line { margin-top: -0.375rem; }
.desc-text { font-size: 0.75rem; }
.faces-q { height: 1.875rem; width: 12.5rem; }
/* 登记表单:条目名前缀 + 后缀 + 环境 + 展示名 + ref(自然换行) */
.faces-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding-top: 0.5rem;
}
.face-select {
  height: 2.25rem;
  padding: 0 0.5rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.face-select:disabled { opacity: 0.6; cursor: not-allowed; }
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
