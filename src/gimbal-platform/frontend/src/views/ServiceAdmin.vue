<!-- ServiceAdmin.vue — 服务信息管理(服务画像方案 §4;P1 唯一净新增页面)。
     定位 = 配置池(与画像的「探索」心智分开,故意不合并):
     * 左栏只到服务级(系统 → 服务两层),服务是配置的最小锚点;
     * 分组在顶部筛选器(选系统得到服务、选分组得到别名,产出物不同层,
       不并列成第二棵树);不选服务时跨服务筛,选了服务在服务内筛,可叠加;
     * 表内显式画出「服务级默认」行(aliasName === baseService 的真实行),
       把三层查找顺序摊开:精确命中别名 → 该服务的默认 → 全局共享默认。
     写面 admin(同传递字段纪律);读面全员——但页面入口收在 admin。 -->
<template>
  <section class="slib">
    <PageHead
      icon="layers"
      title="服务信息管理"
      :count="loading ? '' : `${aliases.length} 个别名`"
      subtitle="配置池 — 别名登记与凭证 / 分组绑定;探索覆盖与告警请用服务画像"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div v-else class="svc-split">
      <!-- 左栏:系统 → 服务两层树,只到服务级 -->
      <aside class="svc-rail">
        <div class="svc-rail-title">
          全部服务
          <span class="svc-rail-hint">{{ totalSystems }} 系统 · {{ serviceCount }} 服务</span>
        </div>
        <p class="svc-rail-hint">按系统分组 · 只列到服务级 · b2.5 按类别分区</p>
        <!-- b2.5(归一 v1.0 §3.4):被测 / 第三方两区,全量不隐藏 -->
        <div v-for="section in [
            { key: 'sut', label: '被测服务', groups: treeServices.sut },
            { key: 'integration', label: '第三方集成', groups: treeServices.integration }]"
             :key="section.key">
          <p v-if="section.groups.length"
             class="svc-rail-hint svc-kind-label"
             :data-testid="`svc-kind-${section.key}`">
            {{ section.label }}({{ section.groups.length }})</p>
          <div v-for="g in section.groups" :key="g.system">
            <div class="svc-tree-group">
              <SystemChip :sys="g.system" />
              <span class="n">({{ g.services.length }})</span>
            </div>
            <div
              v-for="s in g.services"
              :key="s.name"
              class="svc-tree-row"
              :class="{ on: selectedService === s.name }"
            >
              <button
                type="button"
                class="svc-tree-item"
                :data-testid="`svc-tree-${s.name}`"
                @click="selectService(selectedService === s.name ? '' : s.name)"
              >
                <span class="nm">{{ s.name }}</span>
                <span class="n">{{ aliasCount(s.name) }}</span>
              </button>
              <button
                type="button"
                class="svc-tree-act"
                title="配置该服务的字段默认值(服务级默认层)"
                :data-testid="`svc-config-${s.name}`"
                @click.stop="router.push(`/service-admin/${encodeURIComponent(s.name)}`)"
              >字段</button>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧:顶部分组筛选 + 别名表 -->
      <div>
        <div class="svc-stats" data-testid="alias-group-chips">
          <span>
            {{ selectedService ? `${selectedService} 下` : '全部服务' }} ·
            <b>{{ filtered.length }}</b> 条别名
          </span>
          <span v-if="groupChips.length" class="svc-stat-sep"></span>
          <button
            v-for="c in groupChips"
            :key="c"
            type="button"
            class="svc-chip"
            :class="{ on: selectedGroup === c }"
            :data-testid="`alias-chip-${c}`"
            @click="selectedGroup = selectedGroup === c ? '' : c"
          >{{ c }}</button>
          <button v-if="selectedService || selectedGroup" type="button" class="svc-link" @click="clearFilters">
            清掉筛选
          </button>
        </div>

        <div class="lib-card">
          <table class="slib-table">
            <thead>
              <tr>
                <th style="width:22%">别名</th>
                <th style="width:15%">所属服务</th>
                <th style="width:20%">URL</th>
                <th style="width:10%">分组</th>
                <th style="width:15%">凭证</th>
                <th style="width:8%">归属</th>
                <th style="width:132px" class="c-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in paged" :key="a.aliasName" :data-testid="`alias-row-${a.aliasName}`">
                <td>
                  <span class="mono svc-key">{{ a.aliasName }}</span>
                  <span
                    v-if="a.kind === 'external'"
                    class="svc-flag amber ml-1"
                    title="第三方服务(无版本管理):不触发预览、不阻塞集成;单独统计不入基线"
                    data-testid="alias-kind-external"
                  >外部</span>
                  <span
                    v-else-if="a.aliasName === a.baseService"
                    class="svc-flag blue ml-1"
                    title="三层查找的中间层:精确命中别名 → 该服务的默认 → 全局共享默认"
                  >服务级默认</span>
                </td>
                <td class="mono muted">{{ a.baseService }}</td>
                <td>
                  <!-- F4 方案 B:环境级端点(物化链第三档);登记必填,
                       「未填」只可能是加列前的存量行,编辑触达时补齐。 -->
                  <span v-if="a.baseUrl" class="mono svc-url" :title="a.baseUrl">{{ a.baseUrl }}</span>
                  <span v-else class="muted" title="存量行未填 URL;编辑补齐后生效">未填</span>
                </td>
                <td>
                  <span v-if="a.environmentName" class="svc-flag">{{ a.environmentName }}</span>
                  <span v-else class="muted">未归属环境</span>
                </td>
                <td>
                  <span v-if="a.credentialAlias" class="mono">{{ a.credentialAlias }}</span>
                  <span v-else class="muted">不绑</span>
                </td>
                <td>
                  <span class="svc-flag" :class="{ violet: a.ownerUserId == null }">
                    {{ a.ownerUserId == null ? '团队共享' : `个人(#${a.ownerUserId})` }}
                  </span>
                </td>
                <td class="c-center">
                  <div class="row-acts">
                    <button type="button" class="svc-link" :data-testid="`alias-detail-${a.aliasName}`" @click="router.push(`/service-admin/${encodeURIComponent(a.aliasName)}`)">详情</button>
                    <button type="button" class="svc-link" :data-testid="`alias-edit-${a.aliasName}`" @click="startEdit(a)">编辑</button>
                    <button type="button" class="svc-link danger" :data-testid="`alias-del-${a.aliasName}`" @click="remove(a)">删除</button>
                  </div>
                </td>
              </tr>
              <tr v-if="filtered.length === 0">
                <td colspan="7" class="c-center">
                  <span class="muted">
                    {{ selectedService ? '该服务下还没有登记别名' : '还没有登记别名 —— 别名 = <服务名>-<后缀>,前缀必须落在 Plate 目录内' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 2026-09-23 分页批次:客户端过滤后分页(树/筛选收紧 → 越界回落) -->
        <div v-if="pageCount > 1 || filtered.length > 0" class="mt-2 flex justify-end">
          <Pagination
            v-model:page="page"
            v-model:page-size="pageSize"
            :total="filtered.length"
            show-page-size
            show-jump
          />
        </div>

        <!-- 新建 / 编辑 -->
        <div class="svc-panel mt-3.5">
          <div class="svc-panel-head">
            <span class="svc-panel-title">{{ editing ? '编辑别名' : '登记别名' }}</span>
            <span v-if="editing" class="svc-panel-desc">别名是主键,编辑态不可改</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <!-- 三态接入(P1.0)/b2.5(归一 v1.0 §1.6):plate 受管(目录
                 派生强约束)/ external 第三方(不派生,须显式选 base_service
                 = plate 里 kind=integration 的服务)。编辑态 kind 不可改;
                 external→plate 升级走后端 patch(系统转 sut 后),UI 走删重建。 -->
            <Select v-model="draft.kind" :disabled="!!editing" :key="`kind:${draft.kind}:${!!editing}`">
              <SelectTrigger class="w-[128px]" data-testid="alias-kind-trigger"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="plate" title="落在 Plate 目录内的受管服务别名">受管服务</SelectItem>
                <SelectItem value="external" title="第三方服务,无版本管理">第三方</SelectItem>
              </SelectContent>
            </Select>
            <!-- b2.5(§1.6):external 不派生 —— 显式选 base_service(下拉
                 只列 plate 里 kind=integration 的服务);别名全名仍手填。 -->
            <template v-if="draft.kind === 'external' && !editing">
              <Select v-model="draft.baseService">
                <SelectTrigger class="w-[220px]" data-testid="alias-baseservice-trigger">
                  <SelectValue placeholder="选择第三方服务(base_service)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="svc in integrationServices"
                    :key="svc"
                    :value="svc"
                    :title="`plate 系统的第三方服务(${svc})`"
                  >{{ svc }}</SelectItem>
                </SelectContent>
              </Select>
              <Input
                v-model="draft.aliasName"
                class="w-[240px]"
                placeholder="别名全名(如 jira-x)"
                data-testid="alias-name-full-input"
              />
            </template>
            <!-- 常驻只读前缀槽 + 后缀输入(2026-09-23 三次微调):槽恒在
                 (未选服务时占位「服务」),点选服务只换槽内文字,输入框
                 位置零跳动;框内永远只写后缀,完整全串 = 前缀 + 后缀
                 (draft.aliasName 恒为全名,保存逻辑不变)。编辑态槽显
                 该别名自身的所属服务,输入框只读展示后缀。 -->
            <div v-if="draft.kind !== 'external' || !!editing" class="flex items-center gap-1.5">
              <span
                class="mono box-border inline-flex h-9 w-[150px] shrink-0 items-center justify-center overflow-hidden rounded-md border bg-slate-100 px-2"
                :class="aliasBase
                  ? 'text-[13px] font-bold text-slate-600'
                  : 'text-[11px] font-medium text-slate-400'"
                :title="aliasBase ? `${aliasBase}-` : '点选左侧服务后,此处显示服务名前缀'"
                data-testid="alias-prefix"
              >{{ aliasBase ? `${aliasBase}-` : '服务名' }}</span>
              <Input
                v-model="aliasSuffix"
                class="w-[240px]"
                placeholder="后缀(如 uat)"
                :disabled="!!editing"
                data-testid="alias-name-input"
              />
            </div>
            <!-- V5(B):groupTag 退役 —— 归属环境从 environments 选,不再自由填 -->
            <Select v-model="draft.environmentId" :key="`env:${draft.environmentId}`">
              <SelectTrigger class="w-[160px]" data-testid="alias-env-trigger"><SelectValue placeholder="环境(可选)" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="0">不归属</SelectItem>
                <SelectItem v-for="e in environments" :key="e.id" :value="String(e.id)">{{ e.name }}</SelectItem>
              </SelectContent>
            </Select>
            <!-- F4:URL 必填 —— 别名 = 环境端点的登记,该列就是它的本体
                 (引用场景未显式声明/绑定时执行取它)。 -->
            <Input
              v-model="draft.baseUrl"
              class="w-[280px]"
              placeholder="URL(必填,如 https://uat.fin.local)"
              data-testid="alias-url-input"
            />
            <!-- 凭证别名:样式化凭证下拉(与认证选择器同件),替掉 Input+datalist;
                 可选字段 → clearable 给清除钮。宽度走 flex-1 吃行内剩余空间
                 (组件根是 width:100%,固定 w-[260px] 会被盖掉占满整行) -->
            <CredentialSelect
              v-model="draft.credentialAlias"
              :credentials="myCredentials"
              class="min-w-[160px] flex-1"
              placeholder="凭证别名(可选)"
              clearable
              data-testid="alias-cred-input"
            />
            <Button data-testid="alias-save" :disabled="!draft.aliasName.trim() || aliasIncomplete || !draft.baseUrl.trim() || !!saving" @click="save">
              {{ editing ? '保存' : '登记' }}
            </Button>
            <Button v-if="editing" variant="outline" data-testid="alias-cancel" @click="cancelEdit">取消</Button>
          </div>
          <p class="slib-note">
            凭证按<b>执行者本人</b>的认证管理池解析(团队共享别名同样各拿各的);URL 必填;受管服务登记强约束:Plate 目录不可达时暂不能登记。<b>第三方</b>不经目录校验(无契约面/版本管理,执行按步骤内联协议字段)。
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SystemChip from '@/components/SystemChip.vue'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { loadCatalogEntries } from '@/utils/catalog-services'
import {
  createAlias, deleteAlias, listAllAliases, patchAlias,
  type ServiceAliasRow,
} from '@/api/service-aliases'
import { listAll as listMyCredentials, type AuthSession } from '@/api/auth_sessions'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/pagination'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useClientPager } from '@/composables/useClientPager'
import CredentialSelect from '@/components/credential/CredentialSelect.vue'

const loading = ref(true)
const router = useRouter()
const aliases = ref<ServiceAliasRow[]>([])
const selectedService = ref('')
const selectedGroup = ref('')
const myCredentials = ref<AuthSession[]>([])
const environments = ref<EnvironmentRow[]>([])
const saving = ref(false)
const editing = ref<ServiceAliasRow | null>(null)

const draft = ref<{
  aliasName: string; baseUrl: string; environmentId: string;
  credentialAlias: string; kind: 'plate' | 'external'; baseService: string;
}>({
  aliasName: '', baseUrl: '', environmentId: '0', credentialAlias: '',
  kind: 'plate',
  baseService: '',
})

/** 常驻前缀槽的基服务:登记态 = 左栏点选;编辑态 = 该别名自身所属服务;
 *  未选 = 空(槽显占位「服务」)。 */
const aliasBase = computed(() => editing.value?.baseService ?? selectedService.value)

/** 输入框只写后缀;写入时拼回完整全串(draft.aliasName 恒为全名,保存/
 *  校验逻辑不感知前缀拆分)。无基时暂存裸后缀,点选服务后组装。 */
const aliasSuffix = computed({
  get: () => {
    const base = aliasBase.value
    if (!base) return draft.value.aliasName
    const prefix = `${base}-`
    return draft.value.aliasName.startsWith(prefix)
      ? draft.value.aliasName.slice(prefix.length) : ''
  },
  set: (v: string) => {
    draft.value.aliasName = aliasBase.value ? `${aliasBase.value}-${v}` : v
  },
})

/** 登记完成度:受管态没选服务或后缀为空不可提交;external 无
 * 前缀/后缀拆分,全名非空即可(Button 的通用校验覆盖)。 */
const aliasIncomplete = computed(() =>
  !editing.value && draft.value.kind === 'plate'
  && (!aliasBase.value || !aliasSuffix.value.trim()))

interface ServiceRow { name: string; system: string; count: number; kind: string }
interface ServiceGroup { system: string; services: ServiceRow[]; kind: string }

// 左栏树:plate 目录(系统 → 服务两层,只到服务级)。b2.5(归一 v1.0
// §3.4):按系统 kind 分「被测服务 / 第三方集成」两区 —— 第三方同样要
// 配实例与凭证,全量不隐藏,只是分区呈现。
const treeServices = computed<{ sut: ServiceGroup[]; integration: ServiceGroup[] }>(() => {
  const byName = new Map<string, ServiceRow>()
  for (const e of catalogEntries.value) {
    const kind = e.kind ?? 'sut'
    const row = byName.get(e.service)
    if (row) row.count += 1
    else byName.set(e.service, { name: e.service, system: e.system, count: 1, kind })
  }
  const groups = new Map<string, ServiceRow[]>()
  for (const row of byName.values()) {
    if (!groups.has(row.system)) groups.set(row.system, [])
    groups.get(row.system)!.push(row)
  }
  const build = (kind: string): ServiceGroup[] =>
    [...groups.entries()]
      .filter(([, services]) => services.every((r) => r.kind === kind))
      .map(([system, services]) => ({
        system, kind,
        services: services.sort((a, b) => a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => a.system.localeCompare(b.system))
  return { sut: build('sut'), integration: build('integration') }
})

const catalogEntries = ref<{ service: string; system: string; kind?: string }[]>([])

// b2.5:external 别名的 base_service 下拉选项(plate kind=integration)
const integrationServices = computed(() =>
  [...new Set(catalogEntries.value
    .filter((e) => (e.kind ?? 'sut') === 'integration')
    .map((e) => e.service))].sort())

const totalSystems = computed(() =>
  treeServices.value.sut.length + treeServices.value.integration.length)
const serviceCount = computed(() =>
  [...treeServices.value.sut, ...treeServices.value.integration]
    .reduce((n, g) => n + g.services.length, 0))

function aliasCount(service: string): number {
  return aliases.value.filter((a) => a.baseService === service).length
}

// 顶部环境筛选(V5-B):别名按 environmentId 归属;chips 显示环境名
const groupChips = computed<string[]>(() => {
  const pool = selectedService.value
    ? aliases.value.filter((a) => a.baseService === selectedService.value)
    : aliases.value
  return [...new Set(pool.map((a) => a.environmentName).filter((t): t is string => !!t))].sort()
})

const filtered = computed<ServiceAliasRow[]>(() =>
  aliases.value
    .filter((a) => !selectedService.value || a.baseService === selectedService.value)
    .filter((a) => !selectedGroup.value || a.environmentName === selectedGroup.value),
)

// 客户端分页(2026-09-23 批次):全量拉回 + 前端过滤,页内切片渲染;
// 每页行数存用户偏好
const { page, pageSize, paged, pageCount } = useClientPager(() => filtered.value, 20, 'service-admin')

function selectService(name: string): void {
  const prev = selectedService.value
  selectedService.value = name
  selectedGroup.value = '' // 切服务后分组域变化,重选
  if (editing.value) return
  // 点选只换前缀槽文字,输入框位置不动;已写后缀随身携带
  // (无基时输入的裸串视作后缀;恰好是新前缀的全名则剥掉重组,不重复拼)。
  let rest = draft.value.aliasName
  if (prev && rest.startsWith(`${prev}-`)) rest = rest.slice(prev.length + 1)
  if (name && rest.startsWith(`${name}-`)) rest = rest.slice(name.length + 1)
  draft.value.aliasName = name ? `${name}-${rest}` : rest
}

function clearFilters(): void {
  selectedService.value = ''
  selectedGroup.value = ''
}

function startEdit(a: ServiceAliasRow): void {
  editing.value = a
  draft.value = {
    aliasName: a.aliasName,
    baseUrl: a.baseUrl ?? '',
    environmentId: a.environmentId != null ? String(a.environmentId) : '0',
    credentialAlias: a.credentialAlias ?? '',
    kind: a.kind ?? 'plate',
    baseService: a.baseService ?? '',
  }
}

function cancelEdit(): void {
  editing.value = null
  draft.value = {
    aliasName: '', baseUrl: '', environmentId: '0', credentialAlias: '',
    kind: 'plate', baseService: '',
  }
}

async function save(): Promise<void> {
  const d = draft.value
  if (!d.aliasName.trim() || saving.value) return
  saving.value = true
  try {
    if (editing.value) {
      await patchAlias(editing.value.aliasName, {
        baseUrl: d.baseUrl.trim() || null,
        environmentId: d.environmentId !== '0' ? Number(d.environmentId) : null,
        credentialAlias: d.credentialAlias.trim() || null,
      })
      toast.success('已保存')
    } else {
      await createAlias({
        aliasName: d.aliasName.trim(),
        baseUrl: d.baseUrl.trim(),
        environmentId: d.environmentId !== '0' ? Number(d.environmentId) : null,
        credentialAlias: d.credentialAlias.trim() || null,
        kind: d.kind,
        baseService: d.kind === 'external' ? d.baseService : null,
      })
      toast.success('已登记')
    }
    cancelEdit()
    aliases.value = await listAllAliases()
  } catch (e) {
    showError('保存别名', e) // 409(裸声明/plate 不可达)走统一错误文案
  } finally {
    saving.value = false
  }
}

async function remove(a: ServiceAliasRow): Promise<void> {
  const ok = await confirmAction(
    `已绑定的凭证 / 分组随行删除;carry 别名键的绑定行不在此表,不受影响。`,
    `删除别名 ${a.aliasName}?`,
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await deleteAlias(a.aliasName)
    toast.success('已删除')
    aliases.value = await listAllAliases()
  } catch (e) {
    showError('删除别名', e)
  }
}

async function reload(): Promise<void> {
  try {
    aliases.value = await listAllAliases()
    catalogEntries.value = await loadCatalogEntries()
    myCredentials.value = await listMyCredentials()
  } catch (e) {
    showError('加载', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => { void reload() })
</script>
