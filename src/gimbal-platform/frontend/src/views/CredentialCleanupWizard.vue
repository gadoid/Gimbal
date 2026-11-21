<!-- CredentialCleanupWizard.vue — 凭证清账向导(阶段 3;合并路线 §10)。

     双存量清账「两步走」的管理面收口:① 未登记引用 → 登记条目
     (sb/gitlab 类;登记后引用场景即刻合规)或改绑(深链编排器);
     ② 明文快照 → 属主走保存链显式清空(W3 admin 无旁路,向导只
     指路不代刀);③ 方案绑定目标(历史存量面)。
     三面全空 = 「引用皆真条目 + 存量无明文」→ 就绪面板亮绿灯:
     切 enforce = backend/.env 置 REGISTRY_ONLY_IDENTITIES=enforce +
     重启(拍板:清账完成即切;切闸本身是运维动作,不经本页)。
     盘点数据 = GET /admin/cleanup-survey(live,只读)。 -->
<template>
  <ListPage title="凭证清账向导" icon="gear" width="wide" :meta="metaText">
    <template #actions>
      <Button variant="outline" size="sm" data-testid="cw-refresh" :disabled="loading"
              @click="reload">重新盘点</Button>
    </template>

    <!-- 就绪面板(置顶:三面清零 → 可切 enforce) -->
    <div class="lib-card mt-1 p-4" :class="ready ? 'cw-ready' : 'cw-pending'"
         data-testid="cw-readiness">
      <template v-if="survey">
        <p v-if="ready" class="cw-verdict ok">✓ 三面已清零 —— 可以切换 enforce</p>
        <p v-else class="cw-verdict pending">
          切换 enforce 前余项:未登记引用 <b>{{ survey.unregistered.length }}</b> 场景 ·
          明文快照 <b>{{ survey.snapshots.length }}</b> 场景 ·
          方案绑定 <b>{{ survey.bindings.length }}</b> 条
        </p>
        <p class="text-caption text-signal-muted mt-1">
          当前闸态:<b class="mono">{{ survey.gateMode }}</b> · 注册表
          {{ survey.registrySize }} 条。切换 = backend/.env 置
          <code class="mono">REGISTRY_ONLY_IDENTITIES=enforce</code>
          后重启后端(拍板:清账完成即切;切闸是运维动作)。
        </p>
      </template>
      <p v-else-if="loadFailed" class="cw-verdict pending"
         data-testid="cw-load-failed">
        ✗ 盘点读取失败 —— 余项未知,不能视作清零;请「重新盘点」(FE-02:
        失败不悬置为「盘点中」,更不亮绿灯)
      </p>
      <p v-else class="text-caption">盘点中…</p>
    </div>

    <!-- ① 未登记引用(登记条目 / 改绑) -->
    <section class="lib-card mt-2 p-4" data-testid="cw-unregistered">
      <h3 class="cw-h">① 未登记引用</h3>
      <template v-if="survey?.unregistered.length">
        <p class="text-caption text-signal-muted">
          distinct 名 —— 登记同名条目后所有引用场景即刻合规;或逐场景改绑:
        </p>
        <div class="flex flex-wrap gap-2 mt-1">
          <span v-for="n in distinctRefs" :key="n" class="cw-name">
            <b class="mono">{{ n }}</b>
            <button type="button" class="cw-link" :data-testid="`cw-register-${n}`"
                    :disabled="registering === n" @click="registerName(n)">
              {{ registering === n ? '登记中…' : '登记条目' }}
            </button>
          </span>
        </div>
        <Table class="mt-3">
          <TableHeader>
            <TableRow>
              <TableHead>场景</TableHead>
              <TableHead>属主</TableHead>
              <TableHead>未登记引用</TableHead>
              <TableHead class="w-[7.5rem] text-center">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in survey.unregistered" :key="row.scenarioId"
                      :data-testid="`cw-unreg-row-${row.scenarioId}`">
              <TableCell>
                <span class="mono cw-sid">{{ row.scenarioId }}</span>
                <span class="text-caption text-signal-muted ml-2">{{ row.name }}</span>
              </TableCell>
              <TableCell>{{ row.owner }}</TableCell>
              <TableCell><b class="mono">{{ row.refs.join('、') }}</b></TableCell>
              <TableCell class="text-center">
                <button type="button" class="cw-link"
                        @click="openScenario(row.scenarioId)">打开场景改绑</button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </template>
      <p v-else class="text-caption">✓ 无未登记引用</p>
    </section>

    <!-- ② 明文快照(属主保存链显式清空;admin 无旁路) -->
    <section class="lib-card mt-2 p-4" data-testid="cw-snapshots">
      <h3 class="cw-h">② 明文快照(config.users)</h3>
      <template v-if="survey?.snapshots.length">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>场景</TableHead>
              <TableHead>属主</TableHead>
              <TableHead>快照键</TableHead>
              <TableHead class="w-[10rem] text-center">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in survey.snapshots" :key="row.scenarioId"
                      :data-testid="`cw-snap-row-${row.scenarioId}`">
              <TableCell>
                <span class="mono cw-sid">{{ row.scenarioId }}</span>
                <span class="text-caption text-signal-muted ml-2">{{ row.name }}</span>
              </TableCell>
              <TableCell>{{ row.owner }}</TableCell>
              <TableCell>
                <b class="mono">{{ row.keys.join('、') }}</b>
                <span v-if="row.referencedKeys.length" class="cw-ref-badge"
                      :title="`键被步骤引用,须先登记同名条目再清,否则执行面悬空`">
                  先登记:{{ row.referencedKeys.join('、') }}
                </span>
              </TableCell>
              <TableCell class="text-center">
                <template v-if="isMine(row)">
                  <button type="button" class="cw-link" :data-testid="`cw-clear-${row.scenarioId}`"
                          :disabled="clearing === row.scenarioId"
                          @click="clearSnapshot(row)">
                    {{ clearing === row.scenarioId ? '清空中…' : '清空快照并保存' }}
                  </button>
                </template>
                <template v-else>
                  <span class="text-caption text-signal-muted">属主执行</span>
                  <button type="button" class="cw-link ml-2"
                          @click="openScenario(row.scenarioId)">去场景</button>
                </template>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </template>
      <p v-else class="text-caption">✓ 无明文快照存量</p>
    </section>

    <!-- ③ 方案绑定目标(历史存量面) -->
    <section class="lib-card mt-2 p-4" data-testid="cw-bindings">
      <h3 class="cw-h">③ 方案绑定目标</h3>
      <template v-if="survey?.bindings.length">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>方案</TableHead>
              <TableHead>场景</TableHead>
              <TableHead>未登记目标</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in survey.bindings" :key="row.schemeId"
                      :data-testid="`cw-bind-row-${row.schemeId}`">
              <TableCell>{{ row.name }}</TableCell>
              <TableCell><span class="mono cw-sid">{{ row.scenarioId }}</span></TableCell>
              <TableCell><b class="mono">{{ row.unregisteredTargets.join('、') }}</b></TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </template>
      <p v-else class="text-caption">✓ 绑定目标全部已登记</p>
    </section>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { Button } from '@/components/ui/button'
import {
  Table, TableHeader, TableRow, TableHead, TableBody, TableCell,
} from '@/components/ui/table'
import { fetchCleanupSurvey, type CleanupSurvey, type CleanupSnapshotRow } from '@/api/admin'
import { createAlias } from '@/api/service-aliases'
import { getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import { confirmAction } from '@/utils/confirmAction'
import { toast } from '@/utils/toast'
import { composerUrl } from '@/utils/links'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const survey = ref<CleanupSurvey | null>(null)
const loadFailed = ref(false)
const loading = ref(false)
const registering = ref<string | null>(null)
const clearing = ref<string | null>(null)

const ready = computed(() => !!survey.value
  && !survey.value.unregistered.length
  && !survey.value.snapshots.length
  && !survey.value.bindings.length)

const metaText = computed(() => {
  if (!survey.value) return '盘点中…'
  return `闸态 ${survey.value.gateMode} · 注册表 ${survey.value.registrySize} 条`
})

/** distinct 未登记名(登记一个名 = 收编其全部引用场景)。 */
const distinctRefs = computed(() =>
  [...new Set((survey.value?.unregistered ?? []).flatMap((r) => r.refs))])

/** 快照清空走属主保存链(W3 admin 无旁路)—— 只有属主本人在此页能清。 */
function isMine(row: CleanupSnapshotRow): boolean {
  const u = auth.currentUser
  if (!u) return false
  return row.owner === u.username || row.owner === u.display_name
}

async function reload(): Promise<void> {
  loading.value = true
  try {
    survey.value = await fetchCleanupSurvey()
    loadFailed.value = false
  } catch {
    loadFailed.value = true
    toast.error('盘点读取失败 —— 请稍后重试(盘点失败≠已清零,不亮绿灯)')
  } finally {
    loading.value = false
  }
}

/** 登记同名条目(plate 强约束:base 落已知服务集;主档没有该服务时
 *  先去「服务注册」补主档 —— 409 文案会点名)。 */
async function registerName(name: string): Promise<void> {
  registering.value = name
  try {
    await createAlias({ aliasName: name, kind: 'plate', refMode: 'default' })
    toast.success(`已登记条目 ${name}(default 引用)—— 重新盘点看余项`)
    await reload()
  } catch (e) {
    toast.error(`登记 ${name} 失败:${errMsg(e)}`
      + ' —— plate 条目 base 须落主档/目录(先到「服务注册」补主档服务);'
      + '第三方服务条目属 external,请直接在「服务注册」页以 external 登记后重试')
  } finally {
    registering.value = null
  }
}

/** 清空快照并保存:草稿读 → config.users={} → 保存链 PUT
 *  (§7 显式清空口径;同 base/登记闸随保存链生效)。 */
async function clearSnapshot(row: CleanupSnapshotRow): Promise<void> {
  const ok = await confirmAction(
    `将保存场景(快照值不可恢复;凭证改由注册条目解析)。`,
    `清空场景 ${row.scenarioId} 的明文快照(${row.keys.join('、')})?`)
  if (!ok) return
  clearing.value = row.scenarioId
  try {
    const draft = await getScenarioDraft(row.scenarioId)
    draft.definition.config = { ...(draft.definition.config ?? {}), users: {} }
    await updateScenario(row.scenarioId, draft)
    toast.success(`已清空 ${row.scenarioId} 的明文快照`)
    await reload()
  } catch (e) {
    toast.error(`清空失败:${errMsg(e)}`)
  } finally {
    clearing.value = null
  }
}

function openScenario(id: string): void {
  void router.push(composerUrl(id))
}

function errMsg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) {
    return String((d as { message: unknown }).message)
  }
  return e instanceof Error ? e.message : String(e)
}

onMounted(() => { void reload() })
</script>

<style scoped>
.cw-h {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
}
.cw-verdict { font-weight: 600; }
.cw-verdict.ok { color: var(--signal-ok, #16a34a); }
.cw-verdict.pending { color: var(--signal-warn, #b45309); }
.cw-ready { border-left: 3px solid var(--signal-ok, #16a34a); }
.cw-pending { border-left: 3px solid var(--signal-warn, #b45309); }
.cw-name {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.375rem;
  padding: 0.25rem 0.625rem;
  font-size: 0.8125rem;
}
.cw-link {
  color: var(--link, #2563eb);
  cursor: pointer;
  font-size: 0.8125rem;
}
.cw-link:disabled { opacity: 0.5; cursor: default; }
.cw-sid { font-size: 0.8125rem; }
.cw-ref-badge {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  color: var(--signal-warn, #b45309);
  border: 1px dashed currentColor;
  border-radius: 0.25rem;
  padding: 0 0.375rem;
}
</style>
