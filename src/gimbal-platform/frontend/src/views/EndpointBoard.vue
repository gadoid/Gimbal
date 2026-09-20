<!-- EndpointBoard.vue — 服务画像 · 接口级线索板(方案 §3)。
     四象限 + 中心主体 + Root 槽位;P1 测试象限完整(场景/执行/适配),
     需求/数据/拓扑三象限「未接入」占位(P2/P3 点亮,格位不迁移)。
     初始坐标按象限算死(方案 §5.4:不用力导向,每次打开位置一致);
     拖动坐标按主体存 localStorage(纯前端偏好,不进后端)。
     trails 由后端算好(方案 §3.2),前端只渲染红色高亮,不做业务推理。 -->
<template>
  <section class="slib">
    <PageHead
      icon="network"
      title="接口线索板"
      :count="endpointId"
      :subtitle="board ? `${board.subject.name} · ${service}` : `热力网格 · ${service}`"
      :hint="board ? `${board.subject.method} ${board.subject.path}` : undefined"
    >
      <template #right>
        <div class="svc-stats tight" data-testid="board-filters">
          <button
            v-for="q in viewChips"
            :key="q.key"
            type="button"
            class="svc-chip"
            :class="{ on: view === q.key }"
            :data-testid="`board-view-${q.key}`"
            @click="view = q.key"
          >{{ q.label }}</button>
        </div>
        <router-link class="goto-link" :to="`/services/${encodeURIComponent(service)}`">← 热力网格</router-link>
      </template>
    </PageHead>

    <div v-if="loading" class="slib-loading">加载中…</div>
    <div v-else-if="error" class="svc-banner bad" data-testid="board-error">
      {{ error }}
    </div>

    <div v-else-if="board" class="board-wrap">
      <!-- 画布:四象限 + 主体 + 告警链 -->
      <div class="board-canvas">
        <VueFlow
          :nodes-draggable="true"
          :min-zoom="0.3"
          fit-view-on-init
          @node-click="onNodeClick"
          @node-drag-stop="onDragStop"
        >
          <template #node-board="nodeProps">
            <div
              :data-testid="`board-node-${nodeProps.id}`"
              class="board-node select-none"
              :class="[nodeProps.data.kind === 'card' ? 'is-card' : 'is-plain',
                       nodeProps.data.kind === 'zone' ? 'w-[600px]' : 'w-[220px]']"
            >
              <!-- 象限占位区 -->
              <template v-if="nodeProps.data.kind === 'zone'">
                <div class="zone-box">
                  <div class="zone-label">{{ nodeProps.data.label }}</div>
                  <div v-if="nodeProps.data.state === 'unavailable'" class="zone-hint">
                    未接入 — {{ nodeProps.data.hint }}
                  </div>
                </div>
              </template>
              <!-- 主体 / 业务节点 -->
              <template v-else>
                <div class="flex items-center gap-1.5">
                  <span class="kind-tag">{{ kindLabel(nodeProps.data.kind) }}</span>
                  <span
                    v-if="nodeProps.data.kind === 'endpoint'"
                    class="svc-method"
                    :class="methodClass(methodOf(nodeProps.data.label))"
                  >{{ methodOf(nodeProps.data.label) }}</span>
                </div>
                <div class="mono node-title" :title="nodeProps.data.label">
                  {{ nodeProps.data.kind === 'endpoint' ? pathOf(nodeProps.data.label) : nodeProps.data.label }}
                </div>
                <div v-if="nodeProps.data.badge" class="node-badge" :class="nodeProps.data.badgeClass">
                  {{ nodeProps.data.badge }}
                </div>
              </template>
            </div>
          </template>
        </VueFlow>
        <!-- 图例 -->
        <div class="board-legend">
          <span class="lg"><span class="lg-line"></span>结构归属</span>
          <span class="lg"><span class="lg-line dashed"></span>注解/引用</span>
          <span class="lg"><span class="lg-line trail"></span>告警链</span>
        </div>
      </div>

      <!-- 右栏:节点详情 + 自建卡 -->
      <aside class="board-rail">
        <div class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">节点详情</span>
          </div>
          <div v-if="!selected" class="rail-empty" data-testid="board-detail-empty">
            单击画布节点查看
          </div>
          <div v-else :data-testid="`board-detail-${selected.id}`">
            <div class="mono node-detail-key">{{ selected.label }}</div>
            <dl class="svc-kv-list">
              <div v-for="(v, k) in selectedDetailRows" :key="k" class="svc-kv">
                <dt>{{ k }}</dt>
                <dd class="mono">{{ v }}</dd>
              </div>
            </dl>
            <button
              v-if="selected.kind === 'scenario'"
              type="button"
              class="svc-link mt-1"
              data-testid="board-expand"
              @click="expand(selected.id)"
            >{{ expanded === selected.id ? '收起二度' : '展开二度(它引用的其他接口)' }}</button>
            <!-- 配套方案附录:适配事件 → 处理闭环(带 focus 深链定位到该接口) -->
            <button
              v-if="selected.kind === 'adaptation'"
              type="button"
              class="svc-link mt-1"
              data-testid="board-go-adaptations"
              @click="router.push(`/adaptations?focus=${encodeURIComponent(endpointId)}`)"
            >→ 去适配中心处理</button>
          </div>
        </div>

        <div class="svc-panel flex-1 overflow-y-auto" data-testid="board-cards">
          <div class="svc-panel-head">
            <span class="svc-panel-title">自建卡</span>
            <span class="svc-panel-desc">{{ cards.length }} 张 · 只有你知道的上下文</span>
          </div>
          <div class="space-y-2">
            <div v-for="c in cards" :key="c.id" class="board-card" :data-testid="`board-card-${c.id}`">
              <div class="flex items-center justify-between gap-2">
                <span class="svc-flag ink">{{ c.isRoot ? 'ROOT' : quadrantLabel(c.quadrant) }}</span>
                <span v-if="!c.mine" class="card-readonly">他人只读</span>
              </div>
              <p class="card-body">{{ c.body }}</p>
              <div v-if="c.mine" class="card-acts">
                <button type="button" class="svc-link" @click="startEdit(c)">编辑</button>
                <button v-if="!c.isRoot" type="button" class="svc-link" :data-testid="`board-card-promote-${c.id}`" @click="promote(c)">↑ 设为 root</button>
                <button v-else type="button" class="svc-link" @click="demote(c)">↓ 降级</button>
                <button type="button" class="svc-link danger" @click="remove(c)">删除</button>
              </div>
            </div>
            <div v-if="cards.length === 0" class="rail-empty">
              还没有卡 —— 「这个坑当初为什么留下」只有你知道(方案 §3.3)。
            </div>
          </div>

          <!-- 新建/编辑 -->
          <div class="card-form">
            <div class="svc-panel-title">{{ editing ? '编辑卡' : '新建卡' }}</div>
            <textarea
              v-model="draft.body"
              rows="3"
              class="card-textarea"
              placeholder="例如:reason_code 是 09/18 契约新增,这次要拉订单组一起改"
              data-testid="board-card-body"
            ></textarea>
            <div class="flex items-center gap-1.5">
              <select v-model="draft.quadrant" class="card-select" data-testid="board-card-quadrant">
                <option v-for="q in quadrantOptions" :key="q.value" :value="q.value">{{ q.label }}</option>
              </select>
              <select v-model="draft.annotatesNodeId" class="card-select min-w-0 flex-1" data-testid="board-card-annotates">
                <option value="">不注解节点</option>
                <option v-for="n in annotatable" :key="n.id" :value="n.id">{{ n.label.slice(0, 24) }}</option>
              </select>
            </div>
            <div class="flex gap-2">
              <button type="button" class="svc-btn primary" data-testid="board-card-save" @click="save">{{ editing ? '保存' : '创建' }}</button>
              <button v-if="editing" type="button" class="svc-btn" @click="cancelEdit">取消</button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MarkerType, useVueFlow, VueFlow } from '@vue-flow/core'
import type { Edge, Node, NodeDragEvent, NodeMouseEvent } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  createCard, deleteCard, demoteCard, fetchBoard, patchCard, promoteCard,
  type BoardNode, type BoardResponse, type Quadrant,
} from '@/api/service-profile'
import { methodClass } from '@/utils/http-method'

// 节点/边经 store 驱动(替换 nodes prop 不会重挂 vue-flow 内部状态,
// 视角筛选/重载都走 setNodes/setEdges 才能稳定生效)
const { setNodes, setEdges } = useVueFlow()

const route = useRoute()
const router = useRouter()
const service = computed(() => String(route.params.name || ''))
const endpointId = computed(() => String(route.params.endpointId || ''))

const loading = ref(true)
const error = ref('')
const board = ref<BoardResponse | null>(null)
const expanded = ref<string | null>(null)
const selected = ref<BoardNode | null>(null)
const view = ref<'all' | Quadrant>('all')

interface CardRow {
  id: number; body: string; isRoot: boolean; quadrant: Quadrant
  annotatesNodeId: string | null; mine: boolean
}

const cards = computed<CardRow[]>(() =>
  (board.value?.nodes ?? [])
    .filter((n) => n.kind === 'card')
    .map((n) => ({
      id: Number(n.meta.cardId), body: String(n.meta.body ?? ''),
      isRoot: Boolean(n.meta.isRoot), quadrant: n.quadrant ?? 'test',
      annotatesNodeId: (n.meta.annotatesNodeId as string | null) ?? null,
      mine: Boolean(n.meta.mine),
    })),
)

const viewChips = [
  { key: 'all' as const, label: '全部' },
  { key: 'requirement' as const, label: '需求' },
  { key: 'data' as const, label: '数据' },
  { key: 'test' as const, label: '测试' },
  { key: 'topology' as const, label: '拓扑' },
]

const quadrantOptions = [
  { value: 'test' as Quadrant, label: '测试' },
  { value: 'requirement' as Quadrant, label: '需求' },
  { value: 'data' as Quadrant, label: '数据' },
  { value: 'topology' as Quadrant, label: '拓扑' },
]

// ── 象限固定坐标(方案 §5.4:算死不用力导向;拖动后存 localStorage)──
const ZONE_POS: Record<string, { x: number; y: number }> = {
  requirement: { x: -720, y: -400 },
  data: { x: -720, y: 100 },
  topology: { x: 300, y: -400 },
  test: { x: 300, y: 100 },
}
const QUAD_HINT: Record<string, string> = {
  requirement: 'P2 · Plate reference dim',
  data: 'P3 · Plate table dim',
  topology: 'P3 · Plate topology dim',
}

function basePosition(node: BoardNode, counters: Record<string, number>): { x: number; y: number } {
  if (node.kind === 'endpoint' && !node.meta.expanded) return { x: 0, y: 0 }
  if (node.kind === 'card' && node.meta.isRoot) return { x: 0, y: 190 }
  const q = node.quadrant ?? 'test'
  const zone = ZONE_POS[q]
  const i = counters[q] = (counters[q] ?? 0) + 1
  if (node.kind === 'scenario') return { x: zone.x + 60, y: 260 + i * 120 }
  if (node.kind === 'execution') return { x: zone.x + 400, y: 260 + i * 120 }
  if (node.kind === 'adaptation') return { x: zone.x + 60, y: zone.y + 60 + i * 110 }
  if (node.meta.expanded) return { x: ZONE_POS.test.x + 740, y: 320 + i * 120 }
  // 卡与其余:象限内纵向排
  return { x: zone.x + 60, y: zone.y + 40 + i * 110 }
}

function posKey(nodeId: string): string {
  return `board-pos:v1:${endpointId.value}:${nodeId}`
}

function badgeOf(node: BoardNode): { badge?: string; badgeClass?: string } {
  if (node.kind === 'execution') {
    const m = node.meta
    const ok = m.status === 'done'
    return { badge: `通过 ${m.passed ?? 0} / 失败 ${m.failed ?? 0}`, badgeClass: ok ? 'ok' : 'bad' }
  }
  if (node.kind === 'adaptation') {
    return { badge: `${node.meta.fromVersion} → ${node.meta.toVersion} · ${node.meta.openOps} 条未落定`, badgeClass: 'warn' }
  }
  if (node.kind === 'card') {
    return { badge: node.meta.isRoot ? '上下文底座' : undefined, badgeClass: 'mute' }
  }
  return {}
}

const flowNodes = computed<Node[]>(() => {
  const counters: Record<string, number> = {}
  const trailIds = new Set((board.value?.trails ?? []).flatMap((t) => t.path))
  const nodes: Node[] = [
    // 四象限占位区(测试象限也画框,但 state=ok)
    ...(['requirement', 'data', 'topology', 'test'] as const).map((q) => ({
      id: `zone:${q}`,
      type: 'board',
      position: ZONE_POS[q],
      draggable: false,
      selectable: false,
      data: {
        kind: 'zone', label: `${quadrantLabel(q)}象限`,
        state: board.value?.quadrants[q] ?? 'unavailable',
        hint: QUAD_HINT[q],
      },
    })),
  ]
  for (const n of board.value?.nodes ?? []) {
    const saved = localStorage.getItem(posKey(n.id))
    const position = saved ? (JSON.parse(saved) as { x: number; y: number }) : basePosition(n, counters)
    nodes.push({
      id: n.id,
      type: 'board',
      position,
      data: {
        kind: n.kind, label: n.label, quadrant: n.quadrant,
        inTrail: trailIds.has(n.id),
        ...badgeOf(n),
      },
    })
  }
  return nodes
})

const visibleNodes = computed<Node[]>(() =>
  view.value === 'all'
    ? flowNodes.value
    : flowNodes.value.filter((n) => {
        // 常驻:象限框、主体(无象限的 endpoint)、root 卡(方案 §3.3
        // 「切到任何视角都常驻」);其余按象限匹配
        const kind = n.data.kind as string
        if (kind === 'zone') return true
        if (kind === 'endpoint' && n.data.quadrant == null) return true
        if (kind === 'card' && n.data.isRoot) return true
        return n.data.quadrant === view.value
      }),
)

const flowEdges = computed<Edge[]>(() => {
  const b = board.value
  if (!b) return []
  const out: Edge[] = b.edges.map((e) => {
    const dashed = e.kind === 'annotates' || e.kind === 'refs'
    return {
      id: `e:${e.from}->${e.to}:${e.kind}`,
      source: e.from,
      target: e.to,
      style: dashed
        ? { stroke: '#A8B0BC', strokeWidth: 1.3, strokeDasharray: '6 4' }
        : { stroke: '#C7CDD6', strokeWidth: 1.4 },
    }
  })
  // 告警链:红粗线 + 箭头(方向即因果,方案 §3.5)
  for (const t of b.trails) {
    for (let i = 0; i + 1 < t.path.length; i++) {
      out.push({
        id: `trail:${t.path[i]}->${t.path[i + 1]}:${i}`,
        source: t.path[i],
        target: t.path[i + 1],
        animated: true,
        style: { stroke: '#DC2626', strokeWidth: 2.2 },
        markerEnd: MarkerType.ArrowClosed,
      })
    }
  }
  return out
})

function kindLabel(kind: string): string {
  return ({ endpoint: '接口', scenario: '场景', execution: '执行', adaptation: '适配', card: '卡' } as Record<string, string>)[kind] ?? kind
}

function quadrantLabel(q: string): string {
  return ({ requirement: '需求', data: '数据', test: '测试', topology: '拓扑' } as Record<string, string>)[q] ?? q
}

function methodOf(label: string): string {
  return label.split(' ')[0] || '?'
}

function pathOf(label: string): string {
  return label.split(' ').slice(1).join(' ') || label
}

const selectedDetailRows = computed<Record<string, string>>(() => {
  const n = selected.value
  if (!n) return {}
  const rows: Record<string, string> = { 类型: kindLabel(n.kind) }
  if (n.kind === 'scenario') rows.scenarioId = String(n.meta.scenarioId ?? '')
  if (n.kind === 'execution') {
    rows.status = String(n.meta.status ?? '')
    rows.finishedAt = String(n.meta.finishedAt ?? '')
  }
  if (n.kind === 'adaptation') rows.batch = String(n.id.slice(3))
  if (n.kind === 'card') rows.body = String(n.meta.body ?? '')
  return rows
})

const annotatable = computed<BoardNode[]>(() =>
  (board.value?.nodes ?? []).filter((n) => n.kind !== 'card' && n.quadrant !== null),
)

function onNodeClick({ node }: NodeMouseEvent): void {
  const raw = board.value?.nodes.find((n) => n.id === node.id)
  selected.value = raw ?? null
}

function onDragStop({ node }: NodeDragEvent): void {
  try {
    localStorage.setItem(posKey(node.id), JSON.stringify(node.position))
  } catch { /* 隐私模式等存储失败可容忍 */ }
}

// store 驱动:初始挂载 + 视角筛选/数据重载都走这里
watch([visibleNodes, flowEdges], ([nodes, edges]) => {
  setNodes(nodes)
  setEdges(edges)
}, { immediate: true })

async function reload(): Promise<void> {
  try {
    board.value = await fetchBoard(endpointId.value, expanded.value ?? undefined)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function expand(nodeId: string): Promise<void> {
  expanded.value = expanded.value === nodeId ? null : nodeId
  await reload()
}

// ── 卡片编辑 ────────────────────────────────────────────────────
const draft = reactive<{ body: string; quadrant: Quadrant; annotatesNodeId: string }>({
  body: '', quadrant: 'test', annotatesNodeId: '',
})
const editing = ref<CardRow | null>(null)

function startEdit(c: CardRow): void {
  editing.value = c
  draft.body = c.body
  draft.quadrant = c.quadrant
  draft.annotatesNodeId = c.annotatesNodeId ?? ''
}

function cancelEdit(): void {
  editing.value = null
  draft.body = ''
}

async function save(): Promise<void> {
  if (!draft.body.trim()) return
  try {
    if (editing.value) {
      await patchCard(editing.value.id, {
        body: draft.body,
        quadrant: draft.quadrant,
        annotatesNodeId: draft.annotatesNodeId || null,
      })
    } else {
      await createCard({
        subjectId: endpointId.value,
        body: draft.body,
        quadrant: draft.quadrant,
        annotatesNodeId: draft.annotatesNodeId || null,
      })
    }
    cancelEdit()
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  }
}

async function promote(c: CardRow): Promise<void> {
  await promoteCard(c.id).catch((e) => { error.value = String(e) })
  await reload()
}

async function demote(c: CardRow): Promise<void> {
  // 降级:腾出 root 槽位,卡回到自己所属象限(§3.3)
  await demoteCard(c.id).catch((e) => { error.value = String(e) })
  await reload()
}

async function remove(c: CardRow): Promise<void> {
  await deleteCard(c.id).catch((e) => { error.value = String(e) })
  await reload()
}

onMounted(async () => {
  try {
    board.value = await fetchBoard(endpointId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ── 两栏:画布 + 右栏 ─────────────────────────────────────────
   画布吃剩余宽度(节点坐标是绝对值,容器必须 min-width:0 才不会被
   内容撑开);右栏固定 340px,窄屏折到画布之后。 */
.board-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 14px;
  align-items: start;
}
.board-rail { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
@media (max-width: 1180px) {
  .board-wrap { grid-template-columns: minmax(0, 1fr); }
  .board-rail { flex-direction: row; align-items: stretch; }
  .board-rail > * { flex: 1; min-width: 0; }
}

/* ── 画布(方案「附」:#F7F9FB 底 + radial-gradient(#C8D1DB 1px) 18px)
   双层 inset 阴影 = 卡的"垫边",让象限框不与画布边线黏在一起 ── */
.board-canvas {
  position: relative;
  height: calc(100vh - 300px);
  min-height: 520px;
  overflow: hidden;
  background: #f7f9fb;
  border: 1px solid #aeb8c4;
  border-radius: 10px;
  box-shadow: inset 0 0 0 8px #dfe5ec, inset 0 0 0 9px #bfc8d3;
}
.board-canvas :deep(.vue-flow__pane) {
  background-color: #f7f9fb;
  background-image: radial-gradient(#c8d1db 1px, transparent 1px);
  background-size: 18px 18px;
}

/* ── 节点 ────────────────────────────────────────────────────── */
.board-node { border-radius: 10px; font-size: 12px; cursor: grab; }
.board-node.is-plain {
  padding: 10px;
  background: #fff;
  border: 1px solid var(--sl-line);
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
}
/* 自建卡 = 黑底,与图上其他节点用材质区分(它是人写的上下文,不是索引项) */
.board-node.is-card {
  padding: 10px;
  color: #fff;
  background: var(--sl-ink);
  border: 2px solid var(--sl-ink);
  box-shadow: 0 2px 8px rgba(16, 21, 28, 0.18);
}
.node-title {
  margin-top: 4px;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-badge { margin-top: 4px; font-size: 10px; font-weight: 500; }
.node-badge.ok { color: var(--sl-ok); }
.node-badge.bad { color: var(--sl-bad); }
.node-badge.warn { color: var(--sl-warn); }
.node-badge.mute { color: var(--sl-ink-2); }
.is-card .node-badge.mute { color: rgba(255, 255, 255, 0.68); }
.zone-box {
  display: flex;
  height: 300px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px dashed #bcc6d2;
  border-radius: 10px;
}
.zone-label { font-size: 12.5px; font-weight: 600; color: var(--sl-ink-2); }
.zone-hint { margin-top: 4px; font-size: 11px; color: var(--sl-ink-3); }
.kind-tag {
  border-radius: 4px; padding: 0 5px; font-size: 10px; font-weight: 600;
  background: var(--sl-canvas); color: var(--sl-ink-2);
}
.is-card .kind-tag { background: rgba(255, 255, 255, 0.14); color: rgba(255, 255, 255, 0.82); }

/* ── 图例 ────────────────────────────────────────────────────── */
.board-legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 10;
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 6px 10px;
  font-size: 10px;
  color: var(--sl-ink-2);
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  pointer-events: none;
}
.lg { display: inline-flex; align-items: center; gap: 5px; }
.lg-line { display: inline-block; width: 16px; height: 2px; background: var(--sl-star-off); }
.lg-line.dashed { height: 0; border-top: 1px dashed #a8b0bc; background: none; }
.lg-line.trail { height: 2px; background: var(--sl-bad); }

/* ── 右栏内容 ────────────────────────────────────────────────── */
.rail-empty { font-size: 11.5px; line-height: 1.6; color: var(--sl-ink-3); }
.node-detail-key {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--sl-ink);
  overflow-wrap: anywhere;
}
.svc-kv-list { margin: 0; }
.board-card {
  padding: 8px 10px;
  background: #fff;
  border: 1px solid var(--sl-line);
  border-radius: 8px;
  font-size: 11.5px;
}
.card-readonly { font-size: 10px; color: var(--sl-ink-3); }
.card-body { margin: 5px 0 0; white-space: pre-wrap; overflow-wrap: break-word; color: var(--sl-ink); }
.card-acts { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
.card-form { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--sl-divider); display: flex; flex-direction: column; gap: 6px; }
.card-textarea {
  width: 100%;
  padding: 7px 9px;
  font: inherit;
  font-size: 11.5px;
  color: var(--sl-ink);
  background: #fff;
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  outline: none;
  resize: vertical;
}
.card-textarea:focus { border-color: var(--sl-accent); }
.card-select {
  padding: 4px 8px;
  font: inherit;
  font-size: 11.5px;
  color: var(--sl-ink);
  background: #fff;
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  outline: none;
}
.card-select:focus { border-color: var(--sl-accent); }
</style>
