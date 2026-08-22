<!-- AdaptationBatchDetail —— 批次工作台(spec §6):
     头部(版本/状态/回滚)→ ops 列表(预览 + 状态驱动操作组 + 合并勾选)
     → 构造对话框 → 快照折叠。member 全只读。 -->
<template>
  <section v-if="detail" class="batch-detail">
    <header class="page-header">
      <div>
        <h2>
          批次 <span class="mono">{{ detail.batchId }}</span>
          <el-tag size="small" class="status-tag">{{ detail.status }}</el-tag>
        </h2>
        <p class="mono">{{ detail.endpointId }} · {{ detail.fromVersion }} → {{ detail.toVersion }}</p>
        <p class="hint">
          <el-tag
            v-for="(n, s) in detail.opCounts"
            :key="s"
            size="small"
            class="op-tag"
          >{{ s }} {{ n }}</el-tag>
        </p>
      </div>
      <div v-if="auth.isAdmin" class="actions">
        <el-button data-action="construct" @click="constructOpen = true">
          构造 op
        </el-button>
        <el-button
          data-action="merge"
          :disabled="!mergeReady"
          @click="startMerge"
        >合并为 renameField</el-button>
        <el-button
          v-if="detail.status === 'open' || detail.status === 'applying'"
          data-action="rollback"
          type="danger"
          @click="onRollback"
        >整批回滚</el-button>
      </div>
    </header>

    <el-alert
      v-if="!auth.isAdmin"
      type="info"
      :closable="false"
      title="owner 只读视图:仅查看 op 与快照,操作请联系管理员"
    />

    <div class="ops">
      <div v-for="op in detail.ops" :key="op.id" class="op-row">
        <div class="op-head">
          <el-checkbox
            v-if="auth.isAdmin && selectable(op)"
            :model-value="selectedIds.has(op.id)"
            @change="toggleSelect(op)"
          />
          <el-tag size="small" class="mono">{{ op.opType }}</el-tag>
          <el-tag size="small" :type="statusTagType(op.status)">
            {{ op.status }}
          </el-tag>
          <span v-if="op.appliedAt" class="hint">{{ op.appliedAt }}</span>
          <span v-if="op.note" class="hint note">{{ op.note }}</span>
          <span v-if="auth.isAdmin && op.status === 'pending'" class="op-actions">
            <el-button
              size="small"
              type="primary"
              class="op-action"
              data-action="apply"
              @click="onApply(op)"
            >应用</el-button>
            <el-button
              size="small"
              class="op-action"
              data-action="skip"
              @click="onSkip(op)"
            >跳过</el-button>
            <el-button
              size="small"
              class="op-action"
              data-action="edit"
              @click="onEdit(op)"
            >编辑</el-button>
          </span>
        </div>
        <OpPreview :op="op" />
      </div>
    </div>

    <el-collapse class="snapshots">
      <el-collapse-item :title="`快照(${detail.snapshots.length})`">
        <ul>
          <li v-for="(s, i) in detail.snapshots" :key="i" class="mono">
            {{ s.entityType }} · {{ s.entityId }}
          </li>
        </ul>
      </el-collapse-item>
    </el-collapse>

    <OpConstructDialog
      v-model="constructOpen"
      :batch-id="detail.batchId"
      :merge-seed="activeSeed"
      @created="onCreated"
    />

    <el-dialog v-model="editOpen" title="编辑 payload(JSON,仅 pending)" width="520px">
      <el-input
        v-model="editJson"
        type="textarea"
        :rows="8"
        class="mono"
      />
      <p class="hint">mapValue 骨架在此补 map 值;保存即整包替换</p>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reportOpen" title="回滚报告" width="520px">
      <h4>已恢复</h4>
      <ul>
        <li v-for="(r, i) in rollbackReport?.restored ?? []" :key="i" class="mono">
          {{ r.entityType }} · {{ r.entityId }}
        </li>
      </ul>
      <h4>冲突(跳过)</h4>
      <ul>
        <li v-for="(c, i) in rollbackReport?.conflicts ?? []" :key="i">
          <span class="mono">{{ c.entityType }} · {{ c.entityId }}</span>
          <span class="hint"> — {{ c.note }}</span>
        </li>
      </ul>
    </el-dialog>
  </section>
  <el-empty v-else-if="loaded" description="批次不存在或已清理">
    <router-link to="/adaptations" class="link">返回适配中心</router-link>
  </el-empty>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/adaptations'
import type { OpOut, RollbackReport } from '@/api/adaptations'
import { useAuthStore } from '@/stores/auth'
import OpPreview from '@/components/adaptations/OpPreview.vue'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import { mergeSeedFrom } from '@/utils/adaptation-merge'

const auth = useAuthStore()
const route = useRoute()

const detail = ref<api.BatchDetail | null>(null)
const loaded = ref(false)
const selectedOps = ref<OpOut[]>([])
const constructOpen = ref(false)
const activeSeed = ref<api.MergeSeed | null>(null)
const editOpen = ref(false)
const editJson = ref('')
const editingOp = ref<OpOut | null>(null)
const reportOpen = ref(false)
const rollbackReport = ref<RollbackReport | null>(null)

const selectedIds = computed(
  () => new Set(selectedOps.value.map((o) => o.id)))
const mergeReady = computed(() => mergeSeedFrom(selectedOps.value) !== null)

function selectable(op: OpOut): boolean {
  return op.status === 'pending'
    && (op.opType === 'removeField' || op.opType === 'addField')
}

function toggleSelect(op: OpOut): void {
  const idx = selectedOps.value.findIndex((o) => o.id === op.id)
  if (idx >= 0) selectedOps.value.splice(idx, 1)
  else selectedOps.value.push(op)
}

function statusTagType(s: string): 'success' | 'danger' | 'info' | 'warning' {
  if (s === 'applied') return 'success'
  if (s === 'conflict') return 'danger'
  if (s === 'skipped') return 'info'
  return 'warning'
}

async function reload(): Promise<void> {
  try {
    detail.value = await api.getBatch(String(route.params.batchId))
  } catch (e) {
    ElMessage.error(api.errMsg(e, '批次加载失败'))
  } finally {
    loaded.value = true
  }
}

async function onApply(op: OpOut): Promise<void> {
  try {
    await api.applyOp(op.id)
    await reload()
  } catch (e) {
    ElMessage.error(api.errMsg(e, '应用失败'))
  }
}

async function onSkip(op: OpOut): Promise<void> {
  try {
    await api.skipOp(op.id)
    await reload()
  } catch (e) {
    ElMessage.error(api.errMsg(e, '跳过失败'))
  }
}

function onEdit(op: OpOut): void {
  editingOp.value = op
  editJson.value = JSON.stringify(op.payload, null, 2)
  editOpen.value = true
}

async function saveEdit(): Promise<void> {
  if (!editingOp.value) return
  try {
    const payload = JSON.parse(editJson.value) as Record<string, unknown>
    await api.patchOp(editingOp.value.id, payload)
    editOpen.value = false
    await reload()
  } catch (e) {
    ElMessage.error(e instanceof SyntaxError
      ? 'JSON 解析失败' : api.errMsg(e, '保存失败(可能已非 pending)'))
  }
}

function startMerge(): void {
  const seed = mergeSeedFrom(selectedOps.value)
  if (!seed) {
    ElMessage.warning('需勾选同一 step 的一删一增两条 pending 草案')
    return
  }
  activeSeed.value = seed
  constructOpen.value = true
}

async function onCreated(op: OpOut): Promise<void> {
  // 合并流:构造成功后跳过两条源 op(前端串联,§6.3)
  if (activeSeed.value) {
    for (const src of selectedOps.value) {
      await api.skipOp(src.id)
    }
    selectedOps.value = []
    activeSeed.value = null
  }
  void op
  await reload()
}

async function onRollback(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '整批回滚将恢复快照 before 像(冲突实体跳过不盲写),确认?',
      '回滚确认', { type: 'warning' },
    )
  } catch {
    return   // 用户取消
  }
  try {
    rollbackReport.value = await api.rollbackBatch(
      String(route.params.batchId))
    reportOpen.value = true
    await reload()
  } catch (e) {
    ElMessage.error(api.errMsg(e, '回滚失败(批次可能尚未 completed)'))
  }
}

defineExpose({ selectedOps, startMerge })

onMounted(reload)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header p { margin: 6px 0 0; }
.hint { color: #909399; font-size: 12px; }
.status-tag { margin-left: 8px; }
.op-tag { margin-right: 4px; }
.op-row {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 10px;
}
.op-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.op-actions { margin-left: auto; }
.note { max-width: 340px; overflow: hidden; text-overflow: ellipsis; }
.snapshots { margin-top: 18px; }
.snapshots ul { padding-left: 18px; }
.link { color: #409eff; }
.mono { font-family: monospace; }
</style>
