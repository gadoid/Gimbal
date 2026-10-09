<!-- SuiteDetail.vue — 用例组详情(权限域二期 P1)。

     成员页签:添加(scope=mine 的场景选择器)/排序/移除 —— 安全世界面:
     只能加自己创建的场景(后端组合外键库层兜底,admin 也无豁免)。
     模式页签:P1 只有聚合模式(逐个跑成员、无执行策略),非聚合模式
     (1:N/拼接/地图)归执行器侧,随 P3 接入(定稿 §6.6/§13.2)。
     运行:POST /suites/{id}/run → 跳批次归并视图。 -->
<template>
  <section class="sud">
    <div class="sud-head">
      <router-link to="/suites" class="sud-back">← 用例组</router-link>
      <PageHead icon="layers" :title="detail?.name ?? '…'" :subtitle="subtitle" />
      <div class="sud-actions">
        <button
          type="button"
          class="btn-primary"
          data-testid="suite-run"
          :disabled="running || !detail?.memberCount"
          @click="onRun"
        >▶ 运行整组</button>
        <button
          type="button"
          class="btn-danger"
          data-testid="suite-delete"
          :disabled="running"
          @click="onDelete"
        >删除</button>
        <button
          type="button"
          class="btn-primary"
          data-testid="suite-share"
          @click="shareOpen = true"
        >分享…</button>
        <button
          v-if="detail?.visibility !== 'public'"
          type="button"
          class="btn-primary"
          data-testid="suite-publish"
          :disabled="running || !detail?.memberCount"
          @click="onPublish"
        >发布到公共库</button>
        <button
          v-else
          type="button"
          class="btn-danger"
          data-testid="suite-unpublish"
          @click="onUnpublish"
        >下架为私有</button>
      </div>
    </div>

    <div v-if="status === 'loading'" class="sud-loading">加载中…</div>
    <div v-else-if="status === 'error'" class="sud-empty">
      <p>加载失败</p>
      <button type="button" class="btn-primary" @click="load">重试</button>
    </div>

    <template v-else-if="detail">
      <Tabs v-model="tab" class="sud-tabs">
        <TabsList>
          <TabsTrigger value="members">成员({{ detail.members.length }})</TabsTrigger>
          <TabsTrigger value="mode">模式</TabsTrigger>
        </TabsList>

        <TabsContent value="members" class="sud-pane">
          <div class="sud-toolbar">
            <button
              type="button"
              class="btn-secondary"
              data-testid="suite-add-member"
              @click="pickerOpen = true"
            >+ 添加场景</button>
            <span class="sud-hint">只能添加你创建的场景(安全边界,库层兜底)</span>
          </div>

          <div v-if="!detail.members.length" class="sud-empty">
            <p>还没有成员 —— 添加场景后即可整组运行</p>
          </div>
          <div v-else class="sud-table">
            <div class="sud-tr sud-th">
              <span style="width:36px">#</span>
              <span>场景</span>
              <span style="width:90px">模块</span>
              <span style="width:64px">可见性</span>
              <span style="width:150px">操作</span>
            </div>
            <div
              v-for="(m, idx) in detail.members"
              :key="m.scenarioId"
              class="sud-tr"
              :data-testid="`suite-member-${m.scenarioId}`"
            >
              <span class="muted">{{ idx + 1 }}</span>
              <span class="sud-name" :title="m.scenarioId">
                {{ m.name }}
                <em v-if="m.visibility === 'public'" class="su-pub">公共</em>
              </span>
              <span class="muted">{{ m.module || '—' }}</span>
              <span class="muted">{{ m.visibility === 'public' ? '公共' : '私有' }}</span>
              <span class="sud-ops">
                <button type="button" :disabled="idx === 0 || busy" @click="move(idx, -1)">↑</button>
                <button type="button" :disabled="idx === detail.members.length - 1 || busy" @click="move(idx, 1)">↓</button>
                <button type="button" class="danger" :disabled="busy" @click="remove(m.scenarioId)">移除</button>
              </span>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="mode" class="sud-pane">
          <div class="sud-mode">
            <p><b>聚合模式</b>(默认,P1 唯一模式)</p>
            <p class="muted">
              语义 = 逐个运行每个成员、无执行策略:按上方顺序,每个场景用其
              <b>默认运行方案</b>发起一次独立执行,共享一个批次键 —— 批次视图、
              按批聚合通知现成可用。单成员失败不连坐(跳过并记录原因)。
            </p>
            <p class="muted">
              1:N / 拼接 / 地图等编排模式需要执行器侧的编译与判定链路,
              随后续阶段接入;一次性 graph 编排在「Suite 编排」页,与用例组
              是正交概念。
            </p>
          </div>
        </TabsContent>
      </Tabs>
    </template>

    <!-- 添加成员:scope=mine 的场景选择器(检索下推) -->
    <Dialog :open="pickerOpen" @update:open="pickerOpen = $event">
      <DialogContent class="su-dialog">
        <DialogHeader>
          <DialogTitle>添加场景到「{{ detail?.name }}」</DialogTitle>
        </DialogHeader>
        <input
          v-model="pickerQ"
          class="su-input"
          data-testid="suite-picker-search"
          placeholder="搜索我的场景…"
        />
        <div class="su-picker-list">
          <div v-if="!pickerFiltered.length" class="muted">没有匹配的场景</div>
          <label
            v-for="o in pickerFiltered"
            :key="o.scenarioId"
            class="su-picker-item"
          >
            <input
              type="checkbox"
              :value="o.scenarioId"
              v-model="pickerSelected"
            />
            <span class="su-picker-name" :title="o.scenarioId">{{ o.name || o.scenarioId }}</span>
            <span class="muted">{{ o.scenarioId }}</span>
          </label>
        </div>
        <DialogFooter>
          <button type="button" class="btn-ghost" @click="pickerOpen = false">取消</button>
          <button
            type="button"
            class="btn-primary"
            data-testid="suite-picker-submit"
            :disabled="!pickerSelected.length || busy"
            @click="submitAdd"
          >添加 {{ pickerSelected.length || '' }}</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <!-- P2:分享弹窗(引用/副本;现有引用可撤销) -->
    <ShareDialog
      v-model:open="shareOpen"
      :resource="shareResource"
      @changed="void 0"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  addSuiteMembers, deleteSuite, getSuite, removeSuiteMember,
  reorderSuiteMembers, runSuite, type SuiteDetail,
} from '@/api/suites'
import { listScenarioOptions } from '@/api/scenario-composer'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import { executionsBatchUrl } from '@/utils/links'
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()

const suiteId = computed(() => Number(route.params.id))
const status = ref<'loading' | 'ready' | 'error'>('loading')
const detail = ref<SuiteDetail | null>(null)
const tab = ref('members')
const busy = ref(false)
const running = ref(false)
const shareOpen = ref(false)
const shareResource = computed(() => detail.value ? {
  type: 'suite' as const,
  id: String(suiteId.value),
  name: detail.value.name,
} : null)

const subtitle = computed(() => detail.value
  ? `${detail.value.memberCount} 个成员 · 聚合模式 · 创建于 ${detail.value.createdAt?.slice(0, 10) ?? '—'}`
  : '')

async function load(): Promise<void> {
  status.value = 'loading'
  try {
    detail.value = await getSuite(suiteId.value)
    status.value = 'ready'
  } catch {
    status.value = 'error'
  }
}

/** 上/下移:与相邻成员交换后整表重排(后端要求全集)。 */
async function move(idx: number, delta: number): Promise<void> {
  const ids = detail.value?.members.map((m) => m.scenarioId) ?? []
  const j = idx + delta
  if (j < 0 || j >= ids.length) return
  ;[ids[idx], ids[j]] = [ids[j], ids[idx]]
  busy.value = true
  try {
    detail.value = await reorderSuiteMembers(suiteId.value, ids)
  } catch (e) {
    toast.error('调整顺序失败:' + (e as Error).message)
  } finally {
    busy.value = false
  }
}

async function remove(scenarioId: string): Promise<void> {
  busy.value = true
  try {
    await removeSuiteMember(suiteId.value, scenarioId)
    detail.value = await getSuite(suiteId.value)
  } catch (e) {
    toast.error('移除失败:' + (e as Error).message)
  } finally {
    busy.value = false
  }
}

async function onPublish(): Promise<void> {
  // §7.9 确认框:级联发布成员及其数据集;后端回执级联清单事实面
  if (!detail.value) return
  const ok = window.confirm(
    '发布用例组到公共库?未发布的成员及其数据集将一并公开。')
  if (!ok) return
  try {
    const { postSuitePublish } = await import('@/api/suites')
    const out = await postSuitePublish(suiteId.value)
    const cascaded = (out.publishedMembers ?? []).length
    toast.success(cascaded
      ? `已发布(级联公开了 ${cascaded} 个未发布成员)`
      : '已发布到公共库')
    await load()
  } catch (e) {
    toast.error(`发布失败:${(e as Error).message}`)
  }
}

async function onUnpublish(): Promise<void> {
  if (!detail.value) return
  if (!window.confirm('下架用例组?成员场景的公共状态独立保留。')) return
  try {
    const { deleteSuitePublish } = await import('@/api/suites')
    await deleteSuitePublish(suiteId.value)
    toast.success('已下架为私有')
    await load()
  } catch (e) {
    toast.error(`下架失败:${(e as Error).message}`)
  }
}

async function onRun(): Promise<void> {
  running.value = true
  try {
    const r = await runSuite(suiteId.value)
    if (r.skipped.length) {
      toast.error(`${r.skipped.length} 个成员被跳过(原因见批次)`)
    }
    if (r.dispatchWarnings.length) {
      toast.error(`${r.dispatchWarnings.length} 个成员分发异常但已入队(见警告)`)
    }
    toast.success(`批次已发起:${r.started.length} 个执行`)
    void router.push(executionsBatchUrl(r.batchId))
  } catch (e) {
    toast.error('运行失败:' + (e as Error).message)
  } finally {
    running.value = false
  }
}

async function onDelete(): Promise<void> {
  if (!window.confirm(`删除用例组「${detail.value?.name}」?成员场景不受影响。`)) return
  try {
    await deleteSuite(suiteId.value)
    toast.success('用例组已删除')
    void router.push('/suites')
  } catch (e) {
    toast.error('删除失败:' + (e as Error).message)
  }
}

// ── 添加成员选择器(scope=mine;已排除已在组内的)─────────────────
const pickerOpen = ref(false)
const pickerQ = ref('')
const pickerSelected = ref<string[]>([])
const pickerOptions = ref<{ scenarioId: string; name: string }[]>([])

const memberIds = computed(
  () => new Set(detail.value?.members.map((m) => m.scenarioId) ?? []))
const pickerFiltered = computed(() => {
  const q = pickerQ.value.trim().toLowerCase()
  return pickerOptions.value
    .filter((o) => !memberIds.value.has(o.scenarioId))
    .filter((o) => !q
      || (o.name || '').toLowerCase().includes(q)
      || o.scenarioId.toLowerCase().includes(q))
})

let pickerSeq = 0
watch([pickerOpen, pickerQ], ([open]) => {
  if (!open) return
  const seq = ++pickerSeq
  setTimeout(() => {
    if (seq !== pickerSeq) return
    void listScenarioOptions({ page_size: 100, q: pickerQ.value || undefined, scope: 'mine' })
      .then((env) => { pickerOptions.value = env.items })
      .catch(() => { pickerOptions.value = [] })
  }, 300)
})
watch(pickerOpen, (open) => {
  if (open) pickerSelected.value = []
})

async function submitAdd(): Promise<void> {
  if (!pickerSelected.value.length) return
  busy.value = true
  try {
    detail.value = await addSuiteMembers(suiteId.value, pickerSelected.value)
    toast.success(`已添加 ${pickerSelected.value.length} 个成员`)
    pickerOpen.value = false
    pickerSelected.value = []
  } catch (e) {
    toast.error('添加失败:' + (e as Error).message)
  } finally {
    busy.value = false
  }
}

onMounted(() => void load())
</script>

<style scoped>
.sud { display: flex; flex-direction: column; gap: 14px; }
.sud-head { display: flex; align-items: flex-start; gap: 14px; }
.sud-head :deep(.phead) { flex: 1; }
.sud-back { font-size: 12.5px; color: #2563eb; text-decoration: none; padding-top: 4px; white-space: nowrap; }
.sud-actions { display: flex; gap: 8px; padding-top: 6px; }
.sud-tabs { display: flex; flex-direction: column; gap: 12px; }
.sud-pane { display: flex; flex-direction: column; gap: 10px; }
.sud-toolbar { display: flex; align-items: center; gap: 12px; }
.sud-hint { font-size: 12px; color: rgb(100 116 139); }
.sud-table { display: flex; flex-direction: column; border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px; overflow: hidden; }
.sud-tr {
  display: grid; grid-template-columns: 36px minmax(0, 1fr) 90px 64px 150px;
  gap: 10px; align-items: center; padding: 8px 14px; font-size: 13px;
  border-bottom: 1px solid rgb(100 116 139 / 14%);
}
.sud-tr:last-child { border-bottom: none; }
.sud-th { font-size: 12px; color: rgb(100 116 139); background: rgb(100 116 139 / 6%); }
.sud-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sud-ops { display: flex; gap: 6px; }
.sud-ops button {
  padding: 3px 10px; font-size: 12px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.sud-ops button:disabled { opacity: .4; cursor: not-allowed; }
.sud-ops .danger { color: var(--sl-bad, #dc2626); border-color: rgb(220 38 38 / 40%); }
.su-pub {
  font-style: normal; font-size: 10.5px; margin-left: 6px; padding: 2px 6px;
  border-radius: 999px; color: #15803d;
  background: rgb(34 197 94 / 12%); border: 1px solid rgb(34 197 94 / 45%);
}
.sud-mode { display: flex; flex-direction: column; gap: 8px; max-width: 640px; }
.sud-mode p { margin: 0; font-size: 13px; }
.muted { color: rgb(100 116 139); font-size: 12.5px; }
.sud-loading, .sud-empty { padding: 34px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.btn-primary {
  padding: 7px 16px; font-size: 13px; font-weight: 600; border: none;
  border-radius: 8px; cursor: pointer; color: #fff; background: #2563eb;
}
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-secondary {
  padding: 7px 14px; font-size: 13px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgb(59 130 246 / 45%); color: #2563eb; background: rgb(59 130 246 / 8%);
}
.btn-danger {
  padding: 7px 14px; font-size: 13px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgb(220 38 38 / 45%); color: #dc2626; background: transparent;
}
.btn-ghost {
  padding: 7px 16px; font-size: 13px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.su-dialog { display: flex; flex-direction: column; gap: 12px; }
.su-input {
  padding: 8px 10px; font-size: 13px; border-radius: 8px;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.su-picker-list {
  display: flex; flex-direction: column; gap: 2px; max-height: 320px;
  overflow-y: auto; border: 1px solid rgb(100 116 139 / 20%); border-radius: 8px;
  padding: 6px;
}
.su-picker-item {
  display: flex; align-items: center; gap: 10px; padding: 6px 8px;
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
.su-picker-item:hover { background: rgb(59 130 246 / 8%); }
.su-picker-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
