<!-- ServiceAdmin.vue — 服务信息管理(服务画像方案 §4;P1 唯一净新增页面)。
     定位 = 配置池(与画像的「探索」心智分开,故意不合并):
     * 左栏只到服务级(系统 → 服务两层),服务是配置的最小锚点;
     * 分组在顶部筛选器(选系统得到服务、选分组得到别名,产出物不同层,
       不并列成第二棵树);不选服务时跨服务筛,选了服务在服务内筛,可叠加;
     * 表内显式画出「服务级默认」行(aliasName === baseService 的真实行),
       把三层查找顺序摊开:精确命中别名 → 该服务的默认 → 全局共享默认。
     写面 admin(同传递字段纪律);读面全员——但页面入口收在 admin。 -->
<template>
  <ListPage title="服务信息管理" width="wide" subtitle="配置池 — 别名登记与凭证 / 分组绑定;画像探索请用服务画像">
    <div v-if="loading" class="loading-state mt-3.5">加载中…</div>

    <div v-else class="mt-3 flex gap-3 items-stretch">
      <!-- 左栏:系统 → 服务两层树,只到服务级 -->
      <aside class="w-64 shrink-0 rounded-lg border border-signal-line bg-signal-card p-3">
        <div class="flex items-center justify-between">
          <span class="text-caption font-semibold text-signal-ink">全部服务</span>
          <span class="text-micro text-muted-foreground">{{ treeServices.length }}</span>
        </div>
        <p class="mt-0.5 text-micro text-muted-foreground">按系统 · 只列到服务级</p>
        <div class="mt-2 space-y-2.5">
          <div v-for="g in treeServices" :key="g.system">
            <div class="flex items-center gap-1.5 text-micro font-semibold text-muted-foreground">
              <span class="h-2 w-2 rounded-sm bg-[#7C5CBF]"></span>{{ g.system }}
              <span class="font-normal">({{ g.services.length }})</span>
            </div>
            <div
              v-for="s in g.services"
              :key="s.name"
              class="mt-0.5 flex w-full items-center gap-0.5 rounded px-1.5 py-1 transition-colors"
              :class="selectedService === s.name
                ? 'bg-[#E7EFFE] text-[#2F6FED]' : 'hover:bg-signal-canvas'"
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center justify-between text-left text-caption"
                :data-testid="`svc-tree-${s.name}`"
                @click="selectService(selectedService === s.name ? '' : s.name)"
              >
                <span class="mono truncate">{{ s.name }}</span>
                <span class="shrink-0 text-micro text-muted-foreground">{{ aliasCount(s.name) }}</span>
              </button>
              <button
                type="button"
                class="shrink-0 rounded px-1 text-micro text-muted-foreground hover:text-[#2F6FED]"
                title="配置该服务的字段默认值(服务级默认层)"
                :data-testid="`svc-config-${s.name}`"
                @click.stop="router.push(`/service-admin/${encodeURIComponent(s.name)}`)"
              >字段</button>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧:顶部分组筛选 + 别名表 -->
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2" data-testid="alias-group-chips">
          <span class="text-caption text-muted-foreground">
            {{ selectedService ? `${selectedService} 下` : '全部服务' }} · {{ filtered.length }} 条别名
          </span>
          <button
            v-for="c in groupChips"
            :key="c"
            type="button"
            class="rounded-full border px-2.5 py-0.5 text-caption font-medium transition-colors"
            :class="selectedGroup === c
              ? 'border-[#2F6FED] bg-[#E7EFFE] text-[#2F6FED]'
              : 'border-signal-line bg-signal-card text-muted-foreground hover:text-foreground'"
            :data-testid="`alias-chip-${c}`"
            @click="selectedGroup = selectedGroup === c ? '' : c"
          >{{ c }}</button>
        </div>

        <Table class="mt-2.5 min-w-[880px] table-fixed rounded-field border border-signal-line bg-signal-card">
          <TableHeader>
            <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
              <TableHead class="w-[26%] text-caption font-semibold text-muted-foreground">别名</TableHead>
              <TableHead class="w-[18%] text-caption font-semibold text-muted-foreground">所属服务</TableHead>
              <TableHead class="w-[12%] text-caption font-semibold text-muted-foreground">分组</TableHead>
              <TableHead class="w-[18%] text-caption font-semibold text-muted-foreground">凭证</TableHead>
              <TableHead class="w-[10%] text-caption font-semibold text-muted-foreground">归属</TableHead>
              <TableHead class="w-[16%] text-center text-caption font-semibold text-muted-foreground">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="a in filtered" :key="a.aliasName" :data-testid="`alias-row-${a.aliasName}`">
              <TableCell class="mono break-all">
                {{ a.aliasName }}
                <span
                  v-if="a.aliasName === a.baseService"
                  class="ml-1 rounded bg-[#E7EFFE] px-1.5 py-px text-micro font-medium text-[#2F6FED]"
                  title="三层查找的中间层:精确命中别名 → 该服务的默认 → 全局共享默认"
                >服务级默认</span>
              </TableCell>
              <TableCell class="mono dim">{{ a.baseService }}</TableCell>
              <TableCell>
                <span v-if="a.groupTag" class="rounded bg-signal-canvas px-1.5 py-px text-micro">{{ a.groupTag }}</span>
                <span v-else class="text-micro text-muted-foreground">未分组</span>
              </TableCell>
              <TableCell>
                <span v-if="a.credentialAlias" class="mono text-caption">{{ a.credentialAlias }}</span>
                <span v-else class="text-micro text-muted-foreground">不绑</span>
              </TableCell>
              <TableCell>
                <span class="text-micro">{{ a.ownerUserId == null ? '团队共享' : `个人(#${a.ownerUserId})` }}</span>
              </TableCell>
              <TableCell class="text-center">
                <div class="flex items-center justify-center gap-0.5">
                  <Button variant="link" size="sm" class="h-7 px-2" :data-testid="`alias-detail-${a.aliasName}`" @click="router.push(`/service-admin/${encodeURIComponent(a.aliasName)}`)">详情</Button>
                  <Button variant="link" size="sm" class="h-7 px-2" :data-testid="`alias-edit-${a.aliasName}`" @click="startEdit(a)">编辑</Button>
                  <Button variant="link" size="sm" class="h-7 px-2 text-destructive" :data-testid="`alias-del-${a.aliasName}`" @click="remove(a)">删除</Button>
                </div>
              </TableCell>
            </TableRow>
            <TableRow v-if="filtered.length === 0">
              <TableCell colspan="6" class="py-6 text-center text-caption text-muted-foreground">
                {{ selectedService ? '该服务下还没有登记别名' : '还没有登记别名 —— 别名 = <服务名>-<后缀>,前缀必须落在 Plate 目录内' }}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <!-- 新建 / 编辑 -->
        <div class="mt-3 rounded-lg border border-signal-line bg-signal-card p-3">
          <div class="text-caption font-semibold text-signal-ink">{{ editing ? '编辑别名' : '登记别名' }}</div>
          <div class="mt-2 flex flex-wrap items-center gap-2">
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
          <p class="mt-1.5 mb-0 text-micro text-muted-foreground">
            凭证按<b>执行者本人</b>的认证管理池解析(团队共享别名同样各拿各的);登记校验强约束:Plate 目录不可达时暂不能登记。
          </p>
        </div>
      </div>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
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
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'

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
