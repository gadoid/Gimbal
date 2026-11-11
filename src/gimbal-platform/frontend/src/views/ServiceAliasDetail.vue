<!--
  ServiceAliasDetail.vue — 身份面 / 目录服务详情(执行配置分层⑦:详情
  三 tab —— 概览(面信息+地址就绪矩阵)/ 字段默认值 / 凭证;配套方案
  §2.2,C2 拆分落点)。
  「服务就是没有后缀的别名」:同一详情页两种键 ——
  * 身份面键(route param = aliasName):字段默认值 tab = 本面覆盖层,
    凭证 tab = 凭证槽位 slot(认证管理反查面板的跳转落点);
  * base 服务键(param = 目录服务名,未登记为身份面的裸服务):字段
    默认值 tab = 服务级默认层。
  锚点与槽位声明同处(以前配一个别名要在两个页面来回跳)。
  authz M2a S6:身份面不再带 baseUrl/环境归属/凭证别名 — 地址在「环境
  与地址」,凭证改经「凭证槽位」指向执行者本人认证池的槽;编辑 slot 留
  在服务配置列表 — 本页只读键身份。
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
      <p>找不到 <code class="mono">{{ key }}</code> —— 既不是已登记身份面,也不在 Plate 目录服务内。</p>
      <p class="slib-note mt-0">身份面登记在服务配置;键拼错了也会落到这里。</p>
      <Button variant="outline" data-testid="back-admin" @click="router.push('/service-admin')">返回服务配置</Button>
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
        <Button variant="outline" size="sm" data-testid="back-admin" @click="router.push('/service-admin')">返回服务配置</Button>
      </div>

      <Tabs v-model="activeTab">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="fields">字段默认值</TabsTrigger>
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
              <span class="svc-panel-desc">各环境部署行((目录服务, 环境) → 地址);缺口点跳「环境与地址」</span>
            </div>
            <p v-if="!envs.length" class="cred-note">平台还没有环境 — 地址无从配置。</p>
            <table v-else class="ov-table" data-testid="alias-ready-matrix">
              <thead><tr><th>环境</th><th>地址</th></tr></thead>
              <tbody>
                <tr v-for="e in envs" :key="e.id" :data-testid="`ready-env-${e.name}`">
                  <td>{{ e.name }}<template v-if="e.is_default"> · 默认</template></td>
                  <td>
                    <span v-if="deployUrl(e.id)" class="mono">{{ deployUrl(e.id) }}</span>
                    <router-link v-else to="/admin/deployments"
                      class="svc-link warn-link">缺 — 去环境与地址 ↗</router-link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </TabsContent>

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
                凭证槽位
              </span>
              <span class="svc-panel-desc">身份面声明的注入槽位(slot)— 执行注入按此槽取凭证,地址按环境取部署地址</span>
            </div>
            <p class="cred-line">
              凭证槽位:<code class="mono font-semibold">{{ row!.slot || '未声明' }}</code>
            </p>
            <p class="cred-note">
              执行时按<b>执行者本人</b>认证管理池的同名槽解析 — 同一身份面被不同人执行时各拿各的同槽凭证;
              凭证本体的建 / 测连通 / 轮换在认证管理。
            </p>
            <div class="mt-2">
              <Button variant="outline" size="sm" data-testid="open-auths" @click="router.push('/auths')">打开认证管理</Button>
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
 * (认证管理反查面板的身份面 chip;M2a S6 起该 tab 展示凭证槽位 slot)。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import { showError } from '@/utils/errorFallback'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import { listAllAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { listDeployments } from '@/api/deployments'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()
useAuthStore()

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
  : route.query.tab === 'fields' ? 'fields' : 'overview')


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
})



</script>

<style scoped>
.ov-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.ov-table th, .ov-table td {
  text-align: left; padding: 6px 10px;
  border-bottom: 1px solid var(--sl-divider);
}
.ov-table th { color: var(--sl-ink-3); font-weight: 600; width: 120px; }
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
</style>
