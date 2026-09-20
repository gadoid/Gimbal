<!--
  ServiceAliasDetail.vue — 别名 / 服务详情(配套方案 §2.2,C2 拆分落点)。
  「服务就是没有后缀的别名」:同一详情页两种键 ——
  * 别名键(route param = aliasName):字段默认值 tab = 本别名覆盖层,
    凭证 tab = credential_alias 绑定(认证管理反查面板的跳转落点);
  * base 服务键(param = 目录服务名,未登记为别名的裸服务):字段默认值
    tab = 服务级默认层。
  锚点与凭证绑定同处(以前配一个别名要在两个页面来回跳)。
  编辑别名本身(分组/凭证/删除)留在服务信息管理列表 — 本页只读键身份。
-->
<template>
  <ListPage width="wide" :title="pageTitle" :subtitle="pageSubtitle">
    <div v-if="loading" class="loading-state mt-3.5">加载中…</div>

    <div v-else-if="missing" class="mt-6 rounded-lg border border-signal-line bg-signal-card p-6 text-center">
      <p class="text-body text-signal-ink">找不到 <code class="mono">{{ key }}</code></p>
      <p class="mt-1 text-caption text-muted-foreground">
        既不是已登记别名,也不在 Plate 目录服务内。别名登记请回服务信息管理。
      </p>
      <div class="mt-3">
        <Button variant="outline" data-testid="back-admin" @click="router.push('/service-admin')">返回服务信息管理</Button>
      </div>
    </div>

    <template v-else>
      <!-- 键身份卡 -->
      <div class="mt-3 rounded-lg border border-signal-line bg-signal-card p-3.5">
        <div class="flex flex-wrap items-center gap-2">
          <code class="mono text-body font-semibold text-signal-ink">{{ key }}</code>
          <span class="rounded px-1.5 py-px text-micro font-medium" :class="isAliasMode ? 'bg-[#EDF7ED] text-[#2F6F4F]' : 'bg-[#E7EFFE] text-[#2F6FED]'">
            {{ isAliasMode ? '别名' : '目录服务' }}
          </span>
          <span v-if="isAliasMode && row!.groupTag" class="rounded bg-signal-canvas px-1.5 py-px text-micro">{{ row!.groupTag }}</span>
          <!-- 原型 H-alias-detail:头部直接亮出凭证绑定状态(红字 = 未绑定) -->
          <span
            v-if="isAliasMode"
            class="rounded px-1.5 py-px text-micro font-medium"
            :class="row!.credentialAlias
              ? 'bg-[#EDF7ED] text-[#2F6F4F]'
              : 'bg-[#FDECEC] text-[#B42318]'"
            :data-testid="row!.credentialAlias ? 'cred-bound-badge' : 'cred-unbound-badge'"
          >{{ row!.credentialAlias ? `凭证 ${row!.credentialAlias}` : '凭证未绑定' }}</span>
          <span class="flex-1" />
          <Button variant="outline" size="sm" data-testid="open-grid" @click="router.push(`/services/${encodeURIComponent(baseService)}`)">
            ↗ 打开 {{ baseService }} 的画像
          </Button>
          <Button variant="outline" size="sm" data-testid="back-admin" @click="router.push('/service-admin')">返回服务信息管理</Button>
        </div>
        <p v-if="isAliasMode" class="mt-1.5 mb-0 text-micro text-muted-foreground">
          绑定键 = 别名全名;运行时解析:<b>精确命中本别名</b> → {{ baseService }} 服务级默认 → 全局默认 → 无行 = 不注入
        </p>
        <p v-else class="mt-1.5 mb-0 text-micro text-muted-foreground">
          绑定键 = 服务名(服务级默认层);运行时解析:精确命中本服务 → 全局默认 → 无行 = 不注入
        </p>
      </div>

      <Tabs v-model="activeTab" class="mt-3">
        <TabsList>
          <TabsTrigger value="fields">字段默认值</TabsTrigger>
          <TabsTrigger v-if="isAliasMode" value="credential">凭证</TabsTrigger>
        </TabsList>

        <TabsContent value="fields">
          <ServiceBindingEditor
            :service-key="key"
            :base-service="baseService"
          />
        </TabsContent>

        <TabsContent v-if="isAliasMode" value="credential">
          <div class="c-card">
            <div class="c-card-head">
              <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
              <div>
                <h3>凭证绑定</h3>
                <p class="c-head-desc">别名行携带的凭证引用(名字,非外键)— 编排 config 选凭据、执行注入都从此带出</p>
              </div>
            </div>
            <div class="cred-body">
              <template v-if="row!.credentialAlias">
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
              </template>
              <p v-else class="cred-note">
                未绑定凭证 — 执行时走场景显式绑定 / 无凭证路径;可在服务信息管理编辑本别名补绑。
              </p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </template>
  </ListPage>
</template>

<script setup lang="ts">
/**
 * ServiceAliasDetail —— 单键详情:字段默认值编辑(核心)+ 凭证绑定展示。
 * 键的合法性判定:listAliases 命中 → 别名模式;否则目录服务名命中 →
 * 服务模式;都 miss → missing(不猜)。?tab=credential 支持外部深链
 * (认证管理反查面板的别名 chip)。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import { showError } from '@/utils/errorFallback'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import { listAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()

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
  loading.value ? '键详情' : `${key.value}${isAliasMode.value ? ' · 别名详情' : ' · 服务详情'}`)
const pageSubtitle = computed(() =>
  '字段默认值按层回退:本键 → 服务级(derive_base 归一)→ 默认值;删行 = 不注入,null = 显式注入 JSON null')

const activeTab = ref(route.query.tab === 'credential' ? 'credential' : 'fields')

onMounted(async () => {
  try {
    ;[aliases.value, catalogNames.value] = await Promise.all([
      listAliases(),
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
.cred-body {
  padding: 10px 2px 2px;
}

.cred-line {
  font-size: var(--text-caption, 12px);
  margin-bottom: 6px;
}

.cred-note {
  font-size: var(--text-micro, 11px);
  color: var(--muted-foreground, #6b7280);
  margin-bottom: 0;
}
</style>
