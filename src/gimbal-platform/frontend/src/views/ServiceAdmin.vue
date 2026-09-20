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
          <span class="svc-rail-hint">{{ treeServices.length }} 系统 · {{ serviceCount }} 服务</span>
        </div>
        <p class="svc-rail-hint">按系统分组 · 只列到服务级</p>
        <div v-for="g in treeServices" :key="g.system">
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
                <th style="width:26%">别名</th>
                <th style="width:18%">所属服务</th>
                <th style="width:12%">分组</th>
                <th style="width:18%">凭证</th>
                <th style="width:10%">归属</th>
                <th style="width:132px" class="c-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in filtered" :key="a.aliasName" :data-testid="`alias-row-${a.aliasName}`">
                <td>
                  <span class="mono svc-key">{{ a.aliasName }}</span>
                  <span
                    v-if="a.aliasName === a.baseService"
                    class="svc-flag blue ml-1"
                    title="三层查找的中间层:精确命中别名 → 该服务的默认 → 全局共享默认"
                  >服务级默认</span>
                </td>
                <td class="mono muted">{{ a.baseService }}</td>
                <td>
                  <span v-if="a.groupTag" class="svc-flag">{{ a.groupTag }}</span>
                  <span v-else class="muted">未分组</span>
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
                <td colspan="6" class="c-center">
                  <span class="muted">
                    {{ selectedService ? '该服务下还没有登记别名' : '还没有登记别名 —— 别名 = <服务名>-<后缀>,前缀必须落在 Plate 目录内' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 新建 / 编辑 -->
        <div class="svc-panel mt-3.5">
          <div class="svc-panel-head">
            <span class="svc-panel-title">{{ editing ? '编辑别名' : '登记别名' }}</span>
            <span v-if="editing" class="svc-panel-desc">别名是主键,编辑态不可改</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Input
              v-model="draft.aliasName"
              class="w-[240px]"
              placeholder="<服务名>-<后缀>,如 fin-service-uat"
              :disabled="!!editing"
              data-testid="alias-name-input"
            />
            <Input v-model="draft.groupTag" class="w-[160px]" placeholder="分组(如:测试)" data-testid="alias-group-input" />
            <Input
              v-model="draft.credentialAlias"
              class="w-[220px]"
              list="alias-cred-options"
              placeholder="凭证别名(可选)"
              data-testid="alias-cred-input"
            />
            <datalist id="alias-cred-options">
              <option v-for="c in myCredentials" :key="c" :value="c" />
            </datalist>
            <Button data-testid="alias-save" :disabled="!draft.aliasName.trim() || !!saving" @click="save">
              {{ editing ? '保存' : '登记' }}
            </Button>
            <Button v-if="editing" variant="outline" data-testid="alias-cancel" @click="cancelEdit">取消</Button>
          </div>
          <p class="slib-note">
            凭证按<b>执行者本人</b>的认证管理池解析(团队共享别名同样各拿各的);登记校验强约束:Plate 目录不可达时暂不能登记。
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
  createAlias, deleteAlias, listAliases, patchAlias,
  type ServiceAliasRow,
} from '@/api/service-aliases'
import { list as listMyCredentials } from '@/api/auth_sessions'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const loading = ref(true)
const router = useRouter()
const aliases = ref<ServiceAliasRow[]>([])
const selectedService = ref('')
const selectedGroup = ref('')
const myCredentials = ref<string[]>([])
const saving = ref(false)
const editing = ref<ServiceAliasRow | null>(null)

const draft = ref<{ aliasName: string; groupTag: string; credentialAlias: string }>({
  aliasName: '', groupTag: '', credentialAlias: '',
})

interface ServiceRow { name: string; system: string; count: number }
interface ServiceGroup { system: string; services: ServiceRow[] }

// 左栏树:plate 目录(系统 → 服务两层,只到服务级)
const treeServices = computed<ServiceGroup[]>(() => {
  const byName = new Map<string, ServiceRow>()
  for (const e of catalogEntries.value) {
    const row = byName.get(e.service)
    if (row) row.count += 1
    else byName.set(e.service, { name: e.service, system: e.system, count: 1 })
  }
  const groups = new Map<string, ServiceRow[]>()
  for (const row of byName.values()) {
    if (!groups.has(row.system)) groups.set(row.system, [])
    groups.get(row.system)!.push(row)
  }
  return [...groups.entries()]
    .map(([system, services]) => ({
      system,
      services: services.sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => a.system.localeCompare(b.system))
})

const catalogEntries = ref<{ service: string; system: string }[]>([])

const serviceCount = computed(() => treeServices.value.reduce((n, g) => n + g.services.length, 0))

function aliasCount(service: string): number {
  return aliases.value.filter((a) => a.baseService === service).length
}

// 顶部分组筛选:别名表 groupTag 的去重集合(选服务前跨服务,选后服务内)
const groupChips = computed<string[]>(() => {
  const pool = selectedService.value
    ? aliases.value.filter((a) => a.baseService === selectedService.value)
    : aliases.value
  return [...new Set(pool.map((a) => a.groupTag).filter((t): t is string => !!t))].sort()
})

const filtered = computed<ServiceAliasRow[]>(() =>
  aliases.value
    .filter((a) => !selectedService.value || a.baseService === selectedService.value)
    .filter((a) => !selectedGroup.value || a.groupTag === selectedGroup.value),
)

function selectService(name: string): void {
  selectedService.value = name
  selectedGroup.value = '' // 切服务后分组域变化,重选
}

function clearFilters(): void {
  selectedService.value = ''
  selectedGroup.value = ''
}

function startEdit(a: ServiceAliasRow): void {
  editing.value = a
  draft.value = {
    aliasName: a.aliasName,
    groupTag: a.groupTag ?? '',
    credentialAlias: a.credentialAlias ?? '',
  }
}

function cancelEdit(): void {
  editing.value = null
  draft.value = { aliasName: '', groupTag: '', credentialAlias: '' }
}

async function save(): Promise<void> {
  const d = draft.value
  if (!d.aliasName.trim() || saving.value) return
  saving.value = true
  try {
    if (editing.value) {
      await patchAlias(editing.value.aliasName, {
        groupTag: d.groupTag.trim() || null,
        credentialAlias: d.credentialAlias.trim() || null,
      })
      toast.success('已保存')
    } else {
      await createAlias({
        aliasName: d.aliasName.trim(),
        groupTag: d.groupTag.trim() || null,
        credentialAlias: d.credentialAlias.trim() || null,
      })
      toast.success('已登记')
    }
    cancelEdit()
    aliases.value = await listAliases()
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
    aliases.value = await listAliases()
  } catch (e) {
    showError('删除别名', e)
  }
}

async function reload(): Promise<void> {
  try {
    aliases.value = await listAliases()
    catalogEntries.value = await loadCatalogEntries()
    myCredentials.value = (await listMyCredentials()).map((c) => c.alias)
  } catch (e) {
    showError('加载', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => { void reload() })
</script>
