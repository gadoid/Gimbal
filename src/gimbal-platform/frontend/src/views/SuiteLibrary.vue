<!-- SuiteLibrary.vue — 用例组管理页(权限域二期 P1)。

     suite 的本体是「一组用例的管理与绑定」(《Suite成员层、引用分享与
     浏览镜头-设计方案》§6):本页是列表与新建入口,成员管理与聚合模式
     运行在详情页。一次性 graph 编排在 /suites/composer(概念正交,
     关系待 §13.2-2 拍板)。 -->
<template>
  <section class="slib">
    <PageHead icon="layers" title="用例组" :subtitle="subtitle" />

    <div class="slib-toolbar">
      <input
        v-model="q"
        class="slib-search"
        data-testid="suite-search"
        placeholder="按名称搜索"
      />
      <button
        type="button"
        class="slib-create"
        data-testid="suite-create"
        @click="creating = true"
      >+ 新建用例组</button>
    </div>

    <div v-if="status === 'loading'" class="slib-loading">加载中…</div>
    <div v-else-if="status === 'error'" class="card-empty">
      <p>加载失败</p>
      <button type="button" class="cta" @click="load">重试</button>
    </div>
    <div v-else-if="!filtered.length" class="card-empty">
      <p>还没有用例组 —— 新建一个,把场景归组后整组执行</p>
    </div>

    <div v-else class="rows">
      <router-link
        v-for="s in filtered"
        :key="s.suiteId"
        :to="`/suites/${s.suiteId}`"
        class="su-row wrow"
        :data-testid="`suite-row-${s.suiteId}`"
      >
        <span class="su-name" :title="s.name">
          {{ s.name }}
          <span v-if="sharedOutSuites.has(s.suiteId)"
            class="ref-badge" title="此用例组正被引用分享">已引用分享</span>
        </span>
        <span class="su-desc">{{ s.description || '—' }}</span>
        <span class="su-members">{{ s.memberCount }} 个场景</span>
        <span class="su-time">{{ fmt(s.updatedAt) }}</span>
        <span class="su-open">打开 →</span>
      </router-link>
    </div>

    <!-- P2 §7.11:「共享给我的」分区(suite 引用;引用 ⇒ 可整组执行)。 -->
    <div v-if="sharedInSuites.length" class="shared-in" data-testid="shared-in-suites">
      <p class="shared-in-label">共享给我的(引用)</p>
      <div
        v-for="r in sharedInSuites"
        :key="r.id"
        class="su-row wrow shared-row"
        :data-testid="`shared-suite-${r.suiteId}`"
      >
        <span class="su-name">
          {{ r.suiteName || `#${r.suiteId}` }}
          <span class="ref-in-badge">引用 · 来自 {{ r.grantedByName }}</span>
        </span>
        <span class="su-members">{{ r.memberCount }} 个场景</span>
        <button class="cta" :data-testid="`shared-suite-open-${r.suiteId}`"
                @click="$router.push(`/suites/${r.suiteId}`)">打开</button>
        <button class="unsub-btn" :data-testid="`shared-suite-unsub-${r.suiteId}`"
                @click="unsubscribe(r)">退订</button>
      </div>
    </div>

    <!-- 新建对话框 -->
    <Dialog :open="creating" @update:open="creating = $event">
      <DialogContent class="su-dialog">
        <DialogHeader>
          <DialogTitle>新建用例组</DialogTitle>
        </DialogHeader>
        <form class="su-form" @submit.prevent="submitCreate">
          <label class="su-label">
            <span>名称</span>
            <input
              v-model="newName"
              class="su-input"
              data-testid="suite-name-input"
              maxlength="128"
              placeholder="如:冒烟集 / 回归集"
              required
            />
          </label>
          <label class="su-label">
            <span>描述(可选)</span>
            <input
              v-model="newDesc"
              class="su-input"
              maxlength="512"
              placeholder="这个组是干什么的"
            />
          </label>
          <p v-if="createError" class="su-error">{{ createError }}</p>
        </form>
        <DialogFooter>
          <button type="button" class="btn-ghost" @click="creating = false">取消</button>
          <button
            type="button"
            class="btn-primary"
            data-testid="suite-create-submit"
            :disabled="creatingBusy || !newName.trim()"
            @click="submitCreate"
          >创建</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { createSuite, listSuites, type SuiteSummary } from '@/api/suites'
import { listShares, deleteShare, type ShareRefItem } from '@/api/shares'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'

const router = useRouter()

const q = ref('')
const status = ref<'loading' | 'ready' | 'error'>('loading')
const items = ref<SuiteSummary[]>([])

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  if (!needle) return items.value
  return items.value.filter((s) => s.name.toLowerCase().includes(needle))
})
const subtitle = computed(() => `共 ${filtered.value.length} 个用例组`)

// ── P2 徽标 + 共享给我的(§7.11)────────────────────────────────
const sharedOutSuites = ref(new Set<number>())
const sharedInSuites = ref<ShareRefItem[]>([])

async function loadShareBadges() {
  try {
    const [out, inn] = await Promise.all([
      listShares({ direction: 'out' }).catch(() => []),
      listShares({ direction: 'in', resourceType: 'suite' }).catch(() => []),
    ])
    sharedOutSuites.value = new Set(
      out.filter((r) => r.resourceType === 'suite' && r.suiteId)
        .map((r) => r.suiteId as number))
    sharedInSuites.value = inn
  } catch { /* 静默留白 */ }
}

async function unsubscribe(r: ShareRefItem) {
  try {
    await deleteShare(r.id)
    sharedInSuites.value = sharedInSuites.value.filter((x) => x.id !== r.id)
    toast.success('已退订该引用')
  } catch (e) {
    toast.error(`退订失败:${(e as Error).message}`)
  }
}

function fmt(v: string | null): string {
  return v ? shortDateTime(v) : ''
}

async function load(): Promise<void> {
  status.value = 'loading'
  try {
    // 浏览镜头(§5.1):默认 mine;admin 需要全量时走 P2 之后的入口
    const env = await listSuites({ scope: 'mine', page_size: 100 })
    items.value = env.items
    status.value = 'ready'
  } catch {
    status.value = 'error'
  }
}

const creating = ref(false)
const creatingBusy = ref(false)
const newName = ref('')
const newDesc = ref('')
const createError = ref('')

async function submitCreate(): Promise<void> {
  if (creatingBusy.value || !newName.value.trim()) return
  creatingBusy.value = true
  createError.value = ''
  try {
    const s = await createSuite({
      name: newName.value.trim(), description: newDesc.value.trim(),
    })
    toast.success(`用例组「${s.name}」已创建`)
    creating.value = false
    newName.value = ''
    newDesc.value = ''
    void router.push(`/suites/${s.suiteId}`)
  } catch (e) {
    createError.value = (e as Error).message || '创建失败'
  } finally {
    creatingBusy.value = false
  }
}

onMounted(() => void load())
onMounted(() => void loadShareBadges())
</script>

<style scoped>
.slib { display: flex; flex-direction: column; gap: 14px; }
.slib-toolbar { display: flex; gap: 10px; }
.slib-search {
  flex: 1; max-width: 340px; padding: 8px 12px; font-size: 13px;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 8px;
  background: transparent; color: inherit;
}
.slib-create {
  padding: 8px 14px; font-size: 13px; font-weight: 600; white-space: nowrap;
  border-radius: 8px; border: none; cursor: pointer;
  color: #fff; background: #2563eb;
}
.slib-create:hover { background: #1d4ed8; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.su-row {
  display: grid; grid-template-columns: minmax(140px, 220px) minmax(0, 1fr)
    auto auto auto;
  gap: 12px; align-items: center; padding: 10px 14px;
  border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  text-decoration: none; color: inherit;
}
.su-row:hover { border-color: rgb(59 130 246 / 55%); background: rgb(59 130 246 / 6%); }
.su-name { font-weight: 600; font-size: 13.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.su-desc { font-size: 12.5px; color: rgb(100 116 139); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.su-members, .su-time { font-size: 12px; color: rgb(100 116 139); white-space: nowrap; }
.su-open { font-size: 12px; color: #2563eb; white-space: nowrap; }
.su-form { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.su-label { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; }
.su-input {
  padding: 8px 10px; font-size: 13px; border-radius: 8px;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.su-error { font-size: 12.5px; color: var(--sl-bad, #dc2626); }
.btn-primary {
  padding: 7px 16px; font-size: 13px; font-weight: 600; border: none;
  border-radius: 8px; cursor: pointer; color: #fff; background: #2563eb;
}
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-ghost {
  padding: 7px 16px; font-size: 13px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.card-empty { padding: 34px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.cta { margin-left: 10px; color: #2563eb; background: none; border: none; cursor: pointer; font-size: 13px; }
</style>

<style scoped>
.ref-badge {
  font-size: 11px; line-height: 1; padding: 2px 8px; border-radius: 999px;
  color: #6d28d9; background: rgb(139 92 246 / 10%);
  border: 1px solid rgb(139 92 246 / 40%); margin-left: 6px;
}
.ref-in-badge {
  font-size: 11px; line-height: 1; padding: 2px 8px; border-radius: 999px;
  color: #15803d; background: rgb(34 197 94 / 10%);
  border: 1px solid rgb(34 197 94 / 40%); margin-left: 6px;
}
.shared-in { margin-top: 20px; }
.shared-in-label {
  font-size: 13px; color: rgb(100 116 139); margin: 8px 0;
}
.shared-row { cursor: default; }
.unsub-btn {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #b45309; background: rgb(245 158 11 / 8%);
  border: 1px solid rgb(245 158 11 / 35%);
}
</style>
