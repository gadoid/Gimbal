<!-- AddToSuiteDialog.vue — 场景库批量「加入 Suite」的目标选择弹窗
     (权限域二期 P1 尾巴①:《Suite成员层、引用分享与浏览镜头-设计方案》§6.5)。

     库侧入口增强:场景库勾选 N 个场景 → 本弹窗单选一个**自己的**
     suite(scope=mine)→ POST /suites/{id}/members 批量加入。
     加成员能力本身已由 SuiteDetail 的成员选择器覆盖(§6.5 主路径),
     本弹窗只是反向入口(从场景侧聚到组)。

     安全边界(§6.3):成员必须是 suite 属主自己的场景 —— 调用方
     (ScenariosMine)已在「我的」镜头下才开放勾选;若仍命中 404/409
     (他人场景/超上限),原样 toast 后端人话。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="ats-dialog">
      <DialogHeader>
        <DialogTitle>把 {{ scenarios.length }} 个场景加入 Suite</DialogTitle>
      </DialogHeader>

      <div v-if="loading" class="muted">加载 Suite 列表…</div>
      <template v-else>
        <div v-if="!suites.length" class="ats-empty" data-testid="add-to-suite-empty">
          你还没有 Suite —— 先到
          <RouterLink to="/suites" class="linklike">Suite</RouterLink>
          新建一个,再回来批量加入。
        </div>
        <div v-else class="ats-list">
          <label
            v-for="s in suites"
            :key="s.suiteId"
            class="ats-item"
            :class="{ on: picked === s.suiteId }"
            :data-testid="`add-to-suite-item-${s.suiteId}`"
          >
            <input type="radio" :value="s.suiteId" v-model="picked" />
            <span class="ats-name" :title="s.name">{{ s.name }}</span>
            <span class="muted">{{ s.memberCount }} 成员</span>
          </label>
        </div>
      </template>

      <DialogFooter>
        <button type="button" class="btn-ghost" @click="emit('update:open', false)">取消</button>
        <button
          type="button"
          class="btn-primary"
          data-testid="add-to-suite-submit"
          :disabled="!picked || !suites.length || busy"
          @click="submit"
        >{{ busy ? '加入中…' : '加入' }}</button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  addSuiteMembers, listSuites, suiteErrDetail, type SuiteSummary,
} from '@/api/suites'
import { confirmAction } from '@/utils/confirmAction'
import { toast } from '@/utils/toast'

const props = defineProps<{
  open: boolean
  /** 待加入的场景(库侧勾选产物;id 唯一,名称仅用于结果文案兜底)。 */
  scenarios: { id: string; name: string }[]
}>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  /** 加入成功:suite 摘要 + 实际提交数(调用方据此清勾选/跳转)。 */
  added: [payload: { suiteId: number; suiteName: string; count: number }]
}>()

const loading = ref(false)
const busy = ref(false)
const suites = ref<SuiteSummary[]>([])
const picked = ref<number | null>(null)

watch(() => props.open, (open) => {
  if (!open) return
  picked.value = null
  loading.value = true
  listSuites({ scope: 'mine', page_size: 100 })
    .then((page) => { suites.value = page.items })
    .catch(() => {
      suites.value = []
      toast.error('Suite 列表加载失败,请重试')
    })
    .finally(() => { loading.value = false })
}, { immediate: true })  // 挂载即开(库侧直接带 open=true 挂载)也能加载

/** 提交(重构方案:公共 Suite 加私有成员的发布确认分支,与管理页/
 * 画布三处一致):409 suite_member_publish_required → 确认框列出
 * 待公开成员(「这些成员及其数据集将一并公开」)→ 带
 * publishUnpublished 重提;不确认则不加入。 */
async function submit(): Promise<void> {
  if (picked.value == null || busy.value) return
  busy.value = true
  try {
    const ids = props.scenarios.map((s) => s.id)
    try {
      await addSuiteMembers(picked.value, ids)
    } catch (e) {
      const det = suiteErrDetail(e)
      if (det?.code !== 'suite_member_publish_required') throw e
      const pending = ((det.pendingPublish as string[]) ?? [])
        .map((id) => props.scenarios.find((s) => s.id === id)?.name ?? id)
      const ok = await confirmAction(
        `这是公共 Suite:加入的私有成员及其数据集将一并公开(${pending.join('、')})。确认公开并加入?`,
        '发布确认',
        { type: 'warning', confirmButtonText: '公开并加入', cancelButtonText: '不加入' },
      )
      if (!ok) return
      await addSuiteMembers(picked.value, ids, true)
    }
    const suite = suites.value.find((s) => s.suiteId === picked.value)
    const suiteName = suite?.name ?? `#${picked.value}`
    toast.success(`已把 ${props.scenarios.length} 个场景加入「${suiteName}」`)
    emit('added', {
      suiteId: picked.value, suiteName,
      count: props.scenarios.length,
    })
    emit('update:open', false)
  } catch (e) {
    // 404 = 含非本人场景(§6.3);409 = 成员上限 —— 后端人话直接透出
    const det = suiteErrDetail(e)
    toast.error(`加入失败:${(det?.message as string) || (e as Error).message}`)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.ats-dialog { min-width: 380px; }
.ats-list { display: flex; flex-direction: column; gap: 4px; max-height: 320px; overflow: auto; }
.ats-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 8px; cursor: pointer;
  border: 1px solid transparent;
}
.ats-item:hover { background: rgb(100 116 139 / 8%); }
.ats-item.on { border-color: rgb(59 130 246 / 55%); background: rgb(59 130 246 / 10%); }
.ats-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ats-empty { padding: 12px 4px; font-size: 13px; color: var(--c-text-secondary, #64748b); }
.muted { color: var(--c-text-tertiary, #94a3b8); font-size: 12px; }
.linklike {
  background: none; border: none; padding: 0; cursor: pointer;
  color: var(--c-accent, #2563eb); text-decoration: underline;
}
</style>
