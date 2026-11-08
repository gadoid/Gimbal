<!--
  ServiceAliasDetail.vue — 别名 / 服务详情(配套方案 §2.2,C2 拆分落点)。
  「服务就是没有后缀的别名」:同一详情页两种键 ——
  * 别名键(route param = aliasName):字段默认值 tab = 本别名覆盖层,
    槽位 tab = 声明槽位 slot(认证管理反查面板的跳转落点);
  * base 服务键(param = 目录服务名,未登记为别名的裸服务):字段默认值
    tab = 服务级默认层。
  锚点与槽位声明同处(以前配一个别名要在两个页面来回跳)。
  authz M2a S6:别名不再带 baseUrl/环境归属/凭证别名 — 地址在「部署地址」,
  凭证改经「声明槽位」指向执行者本人认证池的槽;编辑 slot 留在服务信息
  管理列表 — 本页只读键身份。
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
      <!-- 键身份行:是什么键 / 槽位声明没声明,扫完再下钻 -->
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
        <Button variant="outline" size="sm" data-testid="back-admin" @click="router.push('/service-admin')">返回服务信息管理</Button>
      </div>

      <Tabs v-model="activeTab">
        <TabsList>
          <TabsTrigger value="fields">字段默认值</TabsTrigger>
          <TabsTrigger v-if="isAliasMode" value="credential">声明槽位</TabsTrigger>
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
                声明槽位
              </span>
              <span class="svc-panel-desc">别名声明的注入槽位(slot)— 执行注入按此槽取凭证,地址按环境取部署地址</span>
            </div>
            <p class="cred-line">
              声明槽位:<code class="mono font-semibold">{{ row!.slot || '未声明' }}</code>
            </p>
            <p class="cred-note">
              执行时按<b>执行者本人</b>认证管理池的同名槽解析 — 同一别名被不同人执行时各拿各的同槽凭证;
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
 * ServiceAliasDetail —— 单键详情:字段默认值编辑(核心)+ 声明槽位展示。
 * 键的合法性判定:listAliases 命中 → 别名模式;否则目录服务名命中 →
 * 服务模式;都 miss → missing(不猜)。?tab=credential 支持外部深链
 * (认证管理反查面板的别名 chip;M2a S6 起该 tab 展示声明槽位 slot)。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import { showError } from '@/utils/errorFallback'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import { listAllAliases, type ServiceAliasRow } from '@/api/service-aliases'
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

const pageTitle = computed(() =>
  loading.value ? '键详情' : isAliasMode.value ? '别名详情' : '服务详情')
/** 三层回退是这个页面存在的全部理由,所以写在副标而不是藏在卡里 */
const pageSubtitle = computed(() =>
  isAliasMode.value
    ? `绑定键 = 别名全名;运行时解析:精确命中本别名 → ${baseService.value} 服务级默认 → 全局默认 → 无行 = 不注入`
    : '绑定键 = 服务名(服务级默认层);运行时解析:精确命中本服务 → 全局默认 → 无行 = 不注入')

const activeTab = ref(
  route.query.tab === 'credential' ? 'credential' : 'fields')


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
</style>
