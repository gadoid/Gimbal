<!--
  ServiceAliasDetail.vue — 别名 / 服务详情(配套方案 §2.2,C2 拆分落点)。
  「服务就是没有后缀的别名」:同一详情页两种键 ——
  * 别名键(route param = aliasName):字段默认值 tab = 本别名覆盖层,
    凭证 tab = credential_alias 绑定(认证管理反查面板的跳转落点);
  * base 服务键(param = 目录服务名,未登记为别名的裸服务):字段默认值
    tab = 服务级默认层。
  锚点与凭证绑定同处(以前配一个别名要在两个页面来回跳)。
  编辑别名本身(分组/凭证/删除)留在服务信息管理列表 — 本页只读键身份。
  形制与服务区域其余页共用 .slib 基座 + service-area.css 构件。
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
      <p>找不到 <code class="mono">{{ key }}</code> —— 既不是已登记别名,也不在 Plate 目录服务内。</p>
      <p class="slib-note mt-0">别名登记在服务信息管理;键拼错了也会落到这里。</p>
      <Button variant="outline" data-testid="back-admin" @click="router.push('/service-admin')">返回服务信息管理</Button>
    </div>

    <template v-else>
      <!-- 键身份行:是什么键 / 哪个分组 / 凭证绑没绑,扫完再下钻 -->
      <div class="svc-stats">
        <span class="svc-flag" :class="isAliasMode ? 'blue' : 'ink'">{{ isAliasMode ? '别名' : '目录服务' }}</span>
        <!-- 三态接入(P1.0):external = 第三方(无版本管理,不触发
             预览/不阻塞集成,单独统计不入基线);plate 受管不标(缺省)。 -->
        <span
          v-if="isAliasMode && row!.kind === 'external'"
          class="svc-flag amber"
          title="第三方服务(无版本管理);契约信息由步骤内联维护"
          data-testid="kind-external-flag"
        >外部</span>
        <span v-if="isAliasMode && row!.environmentName" class="svc-flag">{{ row!.environmentName }}</span>
        <!-- 原型 H-alias-detail:头部直接亮出凭证绑定状态(红字 = 未绑定) -->
        <span
          v-if="isAliasMode"
          class="svc-flag"
          :class="row!.credentialAlias ? 'green' : 'red'"
          :data-testid="row!.credentialAlias ? 'cred-bound-badge' : 'cred-unbound-badge'"
        >{{ row!.credentialAlias ? `凭证 ${row!.credentialAlias}` : '凭证未绑定' }}</span>
        <span class="flex-1" />
        <Button variant="outline" size="sm" data-testid="open-grid" @click="router.push(`/services/${encodeURIComponent(baseService)}`)">
          ↗ 打开 {{ baseService }} 的画像
        </Button>
        <Button variant="outline" size="sm" data-testid="back-admin" @click="router.push('/service-admin')">返回服务信息管理</Button>
      </div>

      <Tabs v-model="activeTab">
        <TabsList>
          <TabsTrigger value="fields">字段默认值</TabsTrigger>
          <TabsTrigger v-if="isAliasMode" value="credential">凭证</TabsTrigger>
          <!-- I4(集成线 v2 §3.2):外部接口登记 + 只读标记开关(admin) -->
          <TabsTrigger v-if="isExternalAlias" value="endpoints">外部接口</TabsTrigger>
        </TabsList>

        <TabsContent value="fields">
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
                凭证绑定
              </span>
              <span class="svc-panel-desc">别名行携带的凭证引用(名字,非外键)— 编排 config 选凭据、执行注入都从此带出</span>
            </div>
            <p class="cred-line">
              绑定凭证别名:<code class="mono font-semibold">{{ row!.credentialAlias }}</code>
            </p>
            <p class="cred-note">
              按<b>执行者本人</b>的认证管理池解析 — 同一别名被不同人执行时各拿各的同名凭证;
              凭证本体的建 / 测连通 / 轮换在认证管理。
            </p>
            <div class="mt-2">
              <Button variant="outline" size="sm" data-testid="open-auths" @click="router.push('/auths')">打开认证管理</Button>
            </div>
          </div>
        </TabsContent>

        <TabsContent v-if="isExternalAlias" value="endpoints">
          <div class="svc-panel">
            <div class="svc-panel-head">
              <span class="svc-panel-title">外部接口目录</span>
              <span class="svc-panel-desc">ext:{{ key }}.&lt;name&gt; 锚点的结构定义来源;query_safe = 平台模式只读标记(POST 查询标了即可进平台模式)</span>
            </div>
            <div v-if="endpointsLoading" class="ext-note">加载中…</div>
            <p v-else-if="!endpoints.length" class="ext-note">
              该别名下还没有登记外部接口 — OpenAPI 导入与登记走管理 API(/external-endpoints)。
            </p>
            <table v-else class="ext-table">
              <thead>
                <tr>
                  <th>接口</th><th>方法</th><th>路径</th><th>只读标记</th>
                  <th v-if="auth.isAdmin" style="text-align:right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="ep in endpoints" :key="ep.name">
                  <td>
                    <span class="mono">{{ ep.name }}</span>
                    <span v-if="ep.title" class="ext-title">{{ ep.title }}</span>
                  </td>
                  <td>
                    <span class="ext-method" :class="ep.method">{{ ep.method }}</span>
                  </td>
                  <td><code class="mono ext-path">{{ ep.path }}</code></td>
                  <td>
                    <span class="ext-qs" :class="ep.querySafe ? 'on' : 'off'"
                          :data-testid="`ext-qs-${ep.name}`">
                      {{ ep.querySafe ? 'query_safe' : '未标记' }}
                    </span>
                  </td>
                  <td v-if="auth.isAdmin" class="ext-ops">
                    <button
                      type="button" class="ext-toggle"
                      :data-testid="`ext-toggle-${ep.name}`"
                      :disabled="qsBusy === ep.name"
                      @click="toggleQuerySafe(ep)"
                    >{{ ep.querySafe ? '撤销只读' : '标记只读' }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <p class="ext-warn">
              标记即授权平台账号执行该接口 — 仅 admin 可操作,标记/撤销均写审计;误标可能让平台执行写操作。
            </p>
          </div>
        </TabsContent>
      </Tabs>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * ServiceAliasDetail —— 单键详情:字段默认值编辑(核心)+ 凭证绑定展示。
 * 键的合法性判定:listAliases 命中 → 别名模式;否则目录服务名命中 →
 * 服务模式;都 miss → missing(不猜)。?tab=credential 支持外部深链
 * (认证管理反查面板的别名 chip)。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import { showError } from '@/utils/errorFallback'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import { listAllAliases, type ServiceAliasRow } from '@/api/service-aliases'
import {
  listExternalEndpoints, setExternalQuerySafe,
  type ExternalEndpointItem,
} from '@/api/external-endpoints'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const key = computed(() => String(route.params.alias ?? ''))
const loading = ref(true)
const aliases = ref<ServiceAliasRow[]>([])
const catalogNames = ref<string[]>([])

const row = computed(() => aliases.value.find((a) => a.aliasName === key.value) ?? null)
const isAliasMode = computed(() => row.value !== null)
const isExternalAlias = computed(() => isAliasMode.value && row.value?.kind === 'external')
const missing = computed(() =>
  !loading.value && row.value === null && !catalogNames.value.includes(key.value))
const baseService = computed(() => row.value?.baseService ?? key.value)

const pageTitle = computed(() =>
  loading.value ? '键详情' : isAliasMode.value ? '别名详情' : '服务详情')
/** 三层回退是这个页面存在的全部理由,所以写在副标而不是藏在卡里 */
const pageSubtitle = computed(() =>
  isAliasMode.value
    ? `绑定键 = 别名全名;运行时解析:精确命中本别名 → ${baseService.value} 服务级默认 → 全局默认 → 无行 = 不注入`
    : '绑定键 = 服务名(服务级默认层);运行时解析:精确命中本服务 → 全局默认 → 无行 = 不注入')

const activeTab = ref(
  route.query.tab === 'credential' ? 'credential'
  : route.query.tab === 'endpoints' ? 'endpoints' : 'fields')

// ── I4(集成线 v2 §3.2):外部接口目录 + query_safe 只读标记开关 ──
const endpoints = ref<ExternalEndpointItem[]>([])
const endpointsLoading = ref(false)
const qsBusy = ref('')

async function loadEndpoints(): Promise<void> {
  if (!isExternalAlias.value) return
  endpointsLoading.value = true
  try {
    endpoints.value = await listExternalEndpoints(key.value)
  } catch (e) {
    showError('外部接口目录', e)
    endpoints.value = []
  } finally {
    endpointsLoading.value = false
  }
}

async function toggleQuerySafe(ep: ExternalEndpointItem): Promise<void> {
  const turningOn = !ep.querySafe
  if (turningOn && !window.confirm(
    `标记「${ep.name}」为只读查询(query_safe)?\n标记即授权平台账号执行该接口,请确认它没有写副作用。`)) {
    return
  }
  qsBusy.value = ep.name
  try {
    const out = await setExternalQuerySafe(key.value, ep.name, turningOn)
    ep.querySafe = out.querySafe
    toast.success(turningOn ? `已标记 ${ep.name} 只读(审计已记录)` : `已撤销 ${ep.name} 只读标记`)
  } catch (e) {
    showError('只读标记', e)
  } finally {
    qsBusy.value = ''
  }
}

watch(isExternalAlias, (v) => {
  if (v) void loadEndpoints()
}, { immediate: true })

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
})
</script>

<style scoped>
.cred-line {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--sl-ink);
}

.cred-note {
  margin: 0;
  font-size: 11px;
  line-height: 1.7;
  color: var(--sl-ink-3);
}
/* I4:外部接口目录 + query_safe 开关 */
.ext-note { margin: 8px 0; font-size: 12px; color: var(--sl-ink-3); }
.ext-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ext-table th {
  text-align: left; font-weight: 500; font-size: 11.5px;
  color: var(--sl-ink-3); padding: 6px 8px; border-bottom: 1px solid #e2e8f0;
}
.ext-table td { padding: 7px 8px; border-bottom: 1px solid rgb(226 232 240 / 60%); }
.ext-title { margin-left: 6px; color: var(--sl-ink-3); font-size: 11.5px; }
.ext-method {
  font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px;
  color: #4338ca; background: rgb(67 56 202 / 8%);
}
.ext-method.POST, .ext-method.PUT, .ext-method.PATCH, .ext-method.DELETE {
  color: #b45309; background: rgb(245 158 11 / 12%);
}
.ext-path { font-size: 11.5px; color: var(--sl-ink-2, #475569); }
.ext-qs { font-size: 11px; padding: 1px 8px; border-radius: 999px; }
.ext-qs.on { color: #15803d; background: rgb(34 197 94 / 12%); }
.ext-qs.off { color: var(--sl-ink-3); border: 1px solid rgb(100 116 139 / 30%); }
.ext-ops { text-align: right; white-space: nowrap; }
.ext-toggle {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft, #eef2ff);
  border: 1px solid var(--accent-soft-border, #c7d2fe);
}
.ext-toggle:disabled { opacity: .5; cursor: not-allowed; }
.ext-warn {
  margin: 10px 0 0; font-size: 11px; line-height: 1.6; color: #b45309;
}
</style>
