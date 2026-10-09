<!-- StructureGuideDialog.vue — 四种结构说明(原型 11;画布/管理页共用)。
     四张模式卡(缩略图、怎么画、怎么跑、适合、留意)+ 识别规则表;
     「用这个结构开始」让父级在画布上放好骨架空位;「不再自动弹出」
     由父级写 localStorage,状态条「?」随时再打开。 -->
<template>
  <Teleport to="body">
    <Transition name="pop">
  <div v-if="modelValue" class="sgd-mask" data-testid="structure-guide-mask" @click.self="close">
      <div role="dialog" aria-labelledby="sgd-title" class="sgd">
        <header class="sgd-head">
          <div class="sgd-head-main">
            <h2 id="sgd-title">四种结构,画出来就是模式</h2>
            <p>
              不用先选。画布上怎么连,Suite 就怎么跑;底部状态条会实时告诉你当前识别成了哪一种。
              想从某个形状开始,点卡片下方的按钮,画布会放好骨架,你只需把场景拖进空位。
            </p>
          </div>
          <button type="button" class="sgd-x" aria-label="关闭说明" data-testid="structure-guide-close" @click="close">✕</button>
        </header>

        <div class="sgd-grid">
          <article v-for="m in cards" :key="m.key" class="sgd-card" :data-testid="`structure-guide-card-${m.key}`">
            <div class="sgd-card-top">
              <div class="sgd-thumb" aria-hidden="true">
                <span
                  v-for="t in m.thumb" :key="t.label"
                  class="sgd-thumb-node" :class="{ src: t.src }"
                  :style="{ left: `${t.x}px`, top: `${t.y}px` }"
                >{{ t.label }}</span>
                <span
                  v-for="(ln, i) in m.lines" :key="i"
                  class="sgd-thumb-line"
                  :style="{ left: `${ln.x1}px`, top: `${ln.y}px`, width: `${ln.x2 - ln.x1}px` }"
                ></span>
              </div>
              <div class="sgd-card-main">
                <p class="sgd-one">{{ m.glyph }} <strong>{{ m.label }}</strong></p>
                <p class="sgd-one-text">{{ m.one }}</p>
                <p class="sgd-draw"><b>怎么画:</b>{{ m.draw }}</p>
              </div>
            </div>
            <dl class="sgd-dl">
              <dt>怎么跑</dt><dd>{{ m.run }}</dd>
              <dt>适合</dt><dd>{{ m.fit }}</dd>
              <dt>留意</dt><dd class="muted">{{ m.note }}</dd>
            </dl>
            <div class="sgd-card-act">
              <button
                type="button"
                :data-testid="`structure-guide-start-${m.key}`"
                @click="$emit('start-skeleton', m.key)"
              >用这个结构开始</button>
            </div>
          </article>
        </div>

        <section class="sgd-rules">
          <div class="sgd-rules-head">
            <h3>识别规则</h3>
            <span>自上而下,命中第一条即止;每次拖入或连线后重新识别</span>
          </div>
          <table>
            <thead>
              <tr><th class="col-shape">画布上的结构</th><th class="col-mode">识别为</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in rules" :key="r.shape">
                <td>{{ r.shape }}</td>
                <td><span class="sgd-chip">{{ r.mode }}</span></td>
                <td class="muted">{{ r.why }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <footer class="sgd-foot">
          <label class="sgd-noshow">
            <input v-model="dontShow" type="checkbox" data-testid="structure-guide-dontshow" />
            下次新建时不再自动弹出(状态条旁的「?」随时可再打开)
          </label>
          <button type="button" class="sgd-start" data-testid="structure-guide-blank" @click="close">从空白开始</button>
        </footer>
      </div>
    </div>
  </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { SuiteMode } from '@/api/suites'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'start-skeleton', mode: SuiteMode): void
  (e: 'dont-show-again'): void
}>()

const dontShow = ref(false)
watch(() => props.modelValue, (open) => { if (open) dontShow.value = false })

function close(): void {
  if (dontShow.value) emit('dont-show-again')
  emit('update:modelValue', false)
}

interface ThumbNode { label: string; x: number; y: number; src?: boolean }
interface ThumbLine { x1: number; x2: number; y: number }

const NW = 44
const cards = computed(() => {
  const line = (a: ThumbNode, b: ThumbNode): ThumbLine =>
    ({ x1: a.x + NW, x2: b.x, y: (a.y + b.y) / 2 + 11 })
  const aggNodes: ThumbNode[] = [
    { label: 'S1', x: 46, y: 20 }, { label: 'S2', x: 156, y: 20 },
    { label: 'S3', x: 46, y: 68 }, { label: 'S4', x: 156, y: 68 },
  ]
  const chainNodes: ThumbNode[] = [
    { label: 'S1', x: 8, y: 44 }, { label: 'S2', x: 72, y: 44 },
    { label: 'S3', x: 136, y: 44 }, { label: 'S4', x: 200, y: 44 },
  ]
  const fanSrc: ThumbNode = { label: '源', x: 16, y: 44, src: true }
  const fanT: ThumbNode[] = [
    { label: 'V1', x: 170, y: 8 }, { label: 'V2', x: 170, y: 44 }, { label: 'V3', x: 170, y: 80 },
  ]
  const dagA: ThumbNode = { label: 'A', x: 8, y: 44 }
  const dagB: ThumbNode = { label: 'B', x: 100, y: 12 }
  const dagC: ThumbNode = { label: 'C', x: 100, y: 76 }
  const dagD: ThumbNode = { label: 'D', x: 192, y: 44 }
  return [
    {
      key: 'aggregate' as SuiteMode, glyph: '‖', label: '聚合',
      one: '一组互不相关的场景,各跑各的。',
      draw: '只拖入,不连线。',
      run: '批次通道:每个成员用它的默认运行方案独立发起一次执行(支持多行数据与注入),归入同一批次;某个失败不影响其他。',
      fit: '冒烟集、回归集这类「把一批场景一起跑一遍」。',
      note: '没有上下文传递,也不保证先后;要先后就连线。',
      thumb: aggNodes, lines: [],
    },
    {
      key: 'chain' as SuiteMode, glyph: '→', label: '串联',
      one: '首尾相接的一条链,上一步做完再做下一步。',
      draw: '一个接一个连成一条直线。',
      run: '一次编排执行;按链路顺序执行,上游产出自动传给下游,可只跑到某一步;每个单元只跑一行数据。',
      fit: '下单 → 支付 → 发货 → 退款这类业务流程。',
      note: '画成一条直线就是串联;依赖编排里画出的直线运行结果相同,串联额外支持「只跑到某一步」。',
      thumb: chainNodes,
      lines: [line(chainNodes[0], chainNodes[1]), line(chainNodes[1], chainNodes[2]), line(chainNodes[2], chainNodes[3])],
    },
    {
      key: 'fanout' as SuiteMode, glyph: '⋔', label: '扇出',
      one: '一个源场景,其余场景都依赖它。',
      draw: '从一个节点拉出多条线,下游之间不再互连。',
      run: '一次编排执行;源先跑,其余单元在它之后执行,每个单元可设 ×重复 放大,只跑一行数据。',
      fit: '一次登录后并发打多个接口、同一订单上验证多个分支。',
      note: '下游之间一旦再连线,就会变成依赖编排。',
      thumb: [fanSrc, ...fanT],
      lines: fanT.map((t) => line(fanSrc, t)),
    },
    {
      key: 'compose' as SuiteMode, glyph: '⋈', label: '依赖编排',
      one: '任意有向无环图:每个单元声明它依赖谁。',
      draw: '自由连线,允许分叉和汇合;不允许成环。',
      run: '一次编排执行;执行器按依赖层级调度,同层可并行;每个单元只跑一行数据。',
      fit: '先准备数据,再多路并行,最后汇总校验。',
      note: '连出环时连线会被拒绝并提示是哪一条。',
      thumb: [dagA, dagB, dagC, dagD],
      lines: [line(dagA, dagB), line(dagA, dagC), line(dagB, dagD), line(dagC, dagD)],
    },
  ]
})

const rules = [
  { shape: '没有任何连线(含只有一个单元)', mode: '聚合', why: '单元之间互不依赖。' },
  { shape: '所有单元连成一条直线,无分叉无汇合', mode: '串联', why: '执行器把串联编译成按顺序的线性依赖,与画成直线的依赖编排相同,无需选择。' },
  { shape: '恰有一个单元指向其余全部,其余之间无连线', mode: '扇出', why: '这个单元自动成为源。' },
  { shape: '其他无环结构(有分叉、汇合或多层)', mode: '依赖编排', why: '每条连线即一条 needs。' },
  { shape: '部分相连、部分孤立', mode: '依赖编排', why: '孤立单元按「无依赖」处理,状态条提示有几个孤立单元,以免是漏连。' },
]
</script>

<style scoped>
.sgd-mask {
  position: fixed; inset: 0; z-index: 60; display: flex; align-items: flex-start;
  justify-content: center; padding: 4vh 16px; overflow-y: auto;
  background: rgb(15 23 42 / 55%);
}
.sgd {
  width: min(1240px, 100%); background: #fff; border-radius: 10px;
  box-shadow: 0 20px 50px rgb(0 0 0 / 25%); display: flex; flex-direction: column;
  color: var(--color-text-primary);
}
.sgd-head {
  display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap;
  padding: 20px 24px 14px; border-bottom: 1px solid #f1f5f9;
}
.sgd-head-main { flex: 1 1 480px; display: flex; flex-direction: column; gap: 4px; }
.sgd-head h2 { margin: 0; font-size: 18px; }
.sgd-head p { margin: 0; color: var(--color-text-secondary); font-size: 12.5px; }
.sgd-x {
  width: 32px; height: 32px; border: 1px solid var(--color-border-tertiary); border-radius: 6px;
  background: #fff; color: var(--color-text-secondary); cursor: pointer;
}
.sgd-grid {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px; padding: 20px 24px;
}
.sgd-card {
  border: 1px solid var(--color-border-tertiary); border-radius: 10px; display: flex;
  flex-direction: column; overflow: hidden;
}
.sgd-card-top {
  display: flex; gap: 16px; flex-wrap: wrap; padding: 16px;
  background: #f8fafc; border-bottom: 1px solid #f1f5f9;
}
.sgd-thumb {
  position: relative; width: 240px; height: 110px; flex: none;
  border-radius: 8px; border: 1px solid var(--color-border-tertiary); background: #fff;
  background-image: radial-gradient(var(--color-border-tertiary) 1px, transparent 1px);
  background-size: 12px 12px;
}
.sgd-thumb-node {
  position: absolute; width: 44px; height: 22px; box-sizing: border-box;
  border-radius: 4px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--color-border-secondary); background: #fff; color: var(--color-text-primary);
  font-family: ui-monospace, Menlo, monospace; font-size: 10px;
}
.sgd-thumb-node.src { border: 1.5px solid #4338ca; background: var(--accent-soft); color: #4338ca; }
.sgd-thumb-line { position: absolute; height: 1.5px; background: var(--color-text-tertiary); }
.sgd-card-main { flex: 1 1 200px; display: flex; flex-direction: column; gap: 6px; }
.sgd-one { margin: 0; font-size: 15px; }
.sgd-one strong { font-size: 16px; }
.sgd-one-text { margin: 0; }
.sgd-draw { margin: 0; font-size: 12px; color: var(--color-text-secondary); }
.sgd-draw b { color: var(--color-text-primary); }
.sgd-dl {
  margin: 0; padding: 12px 16px; display: grid;
  grid-template-columns: 64px minmax(0, 1fr); gap: 6px 12px; font-size: 12px;
}
.sgd-dl dt { color: var(--color-text-secondary); }
.sgd-dl dd { margin: 0; }
.sgd-card-act { margin-top: auto; padding: 0 16px 14px; display: flex; justify-content: flex-end; }
.sgd-card-act button {
  height: 32px; padding: 0 12px; border: 1px solid var(--accent-soft-border); border-radius: 6px;
  background: var(--accent-soft); color: #4338ca; font-weight: 600; font-size: 12px; cursor: pointer;
}
.sgd-rules { margin: 0 24px 16px; border: 1px solid var(--color-border-tertiary); border-radius: 10px; overflow: hidden; }
.sgd-rules-head {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  padding: 10px 16px; background: #f8fafc; border-bottom: 1px solid var(--color-border-tertiary);
}
.sgd-rules-head h3 { margin: 0; font-size: 14px; }
.sgd-rules-head span { font-size: 12px; color: var(--color-text-secondary); }
.sgd-rules table { width: 100%; border-collapse: collapse; }
.sgd-rules th {
  text-align: left; padding: 8px 16px; font-size: 12px; font-weight: 500;
  color: var(--color-text-secondary); border-bottom: 1px solid var(--color-border-tertiary);
}
.sgd-rules td { padding: 10px 16px; border-bottom: 1px solid #f1f5f9; font-size: 12.5px; }
.sgd-rules tr:last-child td { border-bottom: 0; }
.col-shape { width: 44%; } .col-mode { width: 18%; }
.sgd-chip {
  display: inline-flex; padding: 1px 8px; border-radius: 4px;
  font-weight: 600; font-size: 12px; color: #4338ca; background: var(--accent-soft);
}
.sgd-foot {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 14px 24px 20px; border-top: 1px solid #f1f5f9;
}
.sgd-noshow { display: flex; align-items: center; gap: 6px; flex: 1 1 260px; font-size: 12px; color: var(--color-text-secondary); }
.sgd-start {
  height: 36px; padding: 0 16px; border: 0; border-radius: 6px;
  background: #4338ca; color: #fff; font-weight: 600; cursor: pointer;
}
.muted { color: var(--color-text-secondary); }
</style>
