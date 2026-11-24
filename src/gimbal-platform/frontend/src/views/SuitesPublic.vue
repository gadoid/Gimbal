<!-- SuitesPublic.vue — 公共用例集页(IA 调整;样式/功能
     适配轮对齐 SuiteLibrary 规范)。
     原 D-3「公共 Suite 与公共场景同页(ScenariosPublic 分区)」被
     信息架构调整:侧栏「用例集」组下独立成页。
     数据源 GET /suites?visibility=public(出参含 ownerName = 发布者);
     公共读者不可运行(不变量 7:公共资源先复制再跑),行点击进管理页
     只读态,卡内「复制到我的」(fork 深拷贝含编排)跳副本管理页。
     搜索 / 模式筛选走服务端(分页前过滤);模式计数按当前搜索词逐模式
     取 total(5 个轻查询,模式切换不重复拉)。
     按 stitch 原型重排:公共用例集卡片流(模式徽章 /
     草稿 chip / 描述 / 用例场景数 / 最近更新 / 发布者 / 复制·查看),
     保留表格为「列表视图」;原型的优先级徽章、收藏 ★、通过率、平均耗时
     后端无字段(通过率/耗时无历史台账),不渲染,排期见
     docs/project-detail-stitch-plan.md。
     embedded prop —— 项目详情页公共项目用例集页签复用
     本页时隐藏自身 PageHead(消除双页头),独立路由态不变。 -->
<template>
  <section class="slib" :class="{ embedded }">
    <PageHead v-if="!embedded" icon="globe" title="公共用例集"
      :subtitle="pageTip" />

    <!-- ══ 原型 _1 · 公共用例集展示规范(常驻说明条)══════════════ -->
    <div class="pub-note" data-testid="suites-public-note">
      <span class="ni" aria-hidden="true">i</span>
      <p>
        公共用例集展示规范:属主在「我的用例集」⋯ 菜单发布为公共后在此全员可见;
        <b>公共用例集不可直接运行</b> —— 复制到我的后即可编辑与运行。
      </p>
    </div>

    <div class="slib-toolbar">
      <input
        v-model="q"
        class="slib-search"
        data-testid="suites-public-search"
        placeholder="按名称 / 描述 / 发布者搜索"
      />
      <div class="slib-modes" data-testid="suites-public-mode-filter">
        <button
          v-for="m in modeFilters"
          :key="m.key"
          type="button"
          class="slib-mode"
          :class="{ on: modeFilter === m.key }"
          :data-testid="`suites-public-filter-${m.key || 'all'}`"
          @click="modeFilter = m.key"
        >{{ m.label }}<span
            v-if="modeCount(m.key) != null"
            class="mc"
          >{{ modeCount(m.key) }}</span></button>
      </div>
      <span class="flex-1" />
      <!-- 图形/列表视图切换(原型 _1 卡片流 ⇄ 原表格) -->
      <div class="view-toggle" data-testid="suites-public-view-toggle">
        <button
          type="button" class="vt-btn" :class="{ on: viewMode === 'grid' }"
          data-testid="suites-public-view-grid" title="卡片视图"
          @click="viewMode = 'grid'"
        >▦</button>
        <button
          type="button" class="vt-btn" :class="{ on: viewMode === 'list' }"
          data-testid="suites-public-view-list" title="列表视图"
          @click="viewMode = 'list'"
        >☰</button>
      </div>
      <router-link class="slib-public-link" to="/suites"
        data-testid="suites-public-back-mine">我的用例集</router-link>
    </div>

    <div v-if="loading" class="slib-loading">加载中…</div>
    <div v-else-if="error" class="card-empty">
      <p>加载失败</p>
      <button type="button" class="cta" @click="reload">重试</button>
    </div>
    <div v-else-if="!items.length" class="card-empty" data-testid="suites-public-empty">
      <p>{{ filtering ? '没有匹配的公共用例集 — 换个关键词或筛选条件' : '暂无公共用例集 —— 属主在我的用例集「⋯」菜单发布后出现在这里' }}</p>
    </div>

    <!-- ══ 原型 _1 · 卡片流(默认)═══════════════════════════════ -->
    <div v-else-if="viewMode === 'grid'" class="pub-grid">
      <article
        v-for="s in items"
        :key="s.suiteId"
        class="pub-card"
        :data-testid="`public-suite-${s.suiteId}`"
        @click="router.push(`/suites/${s.suiteId}`)"
      >
        <header class="pc-top">
          <span class="mode-chip" :class="s.mode">{{ MODE_LABEL[s.mode] || s.mode }}编排</span>
          <span v-if="s.isDraft" class="draft-chip">草稿</span>
          <span class="flex-1" />
          <button
            type="button" class="icon-btn" title="查看(只读)"
            :data-testid="`public-suite-view-${s.suiteId}`"
            @click.stop="router.push(`/suites/${s.suiteId}`)"
          >→</button>
        </header>
        <h3 class="pc-name">{{ s.name }}</h3>
        <p class="pc-desc">{{ s.description || '—' }}</p>
        <div class="pc-stats">
          <div class="pc-stat">
            <span class="k">用例场景</span>
            <span class="v">{{ s.memberCount }}</span>
          </div>
          <!-- 原型的 通过率 / 平均耗时 无历史台账(仅本人最近一次),不渲染 -->
          <div class="pc-stat">
            <span class="k">最近更新</span>
            <span class="v">{{ s.updatedAt ? formatTime(s.updatedAt) : '—' }}</span>
          </div>
        </div>
        <footer class="pc-foot">
          <span class="pc-owner" :title="s.ownerName ?? undefined">
            <span class="av" aria-hidden="true">{{ ownerInitial(s) }}</span>
            {{ s.ownerName || '—' }}
          </span>
          <span class="pc-ops" @click.stop>
            <button
              type="button" class="run-btn"
              :data-testid="`public-suite-copy-${s.suiteId}`"
              @click="forkPublic(s)"
            >复制到我的</button>
          </span>
        </footer>
      </article>
    </div>

    <!-- ══ 列表视图(原表格,列面口径不变)════════════════════════ -->
    <div v-else class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>Suite</th>
            <th style="width:6.25rem">模式</th>
            <th style="width:4.375rem">成员</th>
            <th style="width:6.875rem">发布者</th>
            <th style="width:9.375rem">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in items"
            :key="s.suiteId"
            class="slib-row"
            :data-testid="`public-suite-${s.suiteId}`"
            title="打开(只读)"
            @click="router.push(`/suites/${s.suiteId}`)"
          >
            <td>
              <div class="sl-name">
                <span class="nm">{{ s.name }}</span>
              </div>
              <div class="sl-sid">{{ s.description || '—' }}</div>
            </td>
            <td><span class="mode-chip" :class="s.mode">{{ MODE_LABEL[s.mode] || s.mode }}</span></td>
            <td><span class="num">{{ s.memberCount }}</span></td>
            <td><span class="muted">{{ s.ownerName || '—' }}</span></td>
            <td class="ops" @click.stop>
              <button
                type="button"
                class="run-btn"
                :data-testid="`public-suite-copy-${s.suiteId}`"
                @click="forkPublic(s)"
              >复制到我的</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination
      v-if="pageCount > 1"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      show-page-size
      show-jump
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Pagination } from '@/components/ui/pagination'
import { forkPublicSuite, listSuites, type SuiteSummary } from '@/api/suites'
import { usePagerSize } from '@/composables/usePagerSize'
import { shortDateTime } from '@/utils/datetime'
import { MODE_LABEL } from '@/utils/suiteStructure'
import { toast } from '@/utils/toast'

/** 项目详情页嵌入态:隐藏自身 PageHead(公共项目用例集页签复用本页) */
defineProps<{ embedded?: boolean }>()

const router = useRouter()

/** 页头问号弹层 = 短定位 + 原页脚长说明(逐页收纳批:页脚不再常驻) */
const pageTip = '已发布到公共库的 Suite —— 不可直接运行,复制到我的后即可编辑与运行'
  + '\n\n'
  + '公共用例集没有「+ 新建」——创建永远发生在我的用例集,这里只做浏览与复用。复制得到的是完整深拷贝:编排结构、成员场景与数据集一并落地为自己的私有副本,与源互不影响;源后续的修改不会同步到副本。'

const items = ref<SuiteSummary[]>([])
const loading = ref(true)
const error = ref(false)
const q = ref('')
const modeFilter = ref('')
// 服务端分页(搜索含发布者名/模式过滤同样走服务端 —— q 由后端在
// 分页前匹配 name/description/属主名,客户端不再二次过滤当前页)
const total = ref(0)
const page = ref(1)
const { pageSize } = usePagerSize('suite-public', 10)
/** 默认卡片视图(原型 _1);列表视图保留原表格列面 */
const viewMode = ref<'grid' | 'list'>('grid')

const modeFilters = [
  { key: '', label: '全部' },
  { key: 'aggregate', label: MODE_LABEL.aggregate },
  { key: 'chain', label: MODE_LABEL.chain },
  { key: 'fanout', label: MODE_LABEL.fanout },
  { key: 'compose', label: MODE_LABEL.compose },
]

const filtering = computed(() =>
  Boolean(q.value.trim() || modeFilter.value))

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const formatTime = shortDateTime
function ownerInitial(s: SuiteSummary): string {
  return (s.ownerName?.trim()?.[0] ?? '?').toUpperCase()
}

/** 模式计数(原型 _1 筛选钮计数):按当前搜索词逐模式取 total,
 *  与列表本身同一服务端过滤口径(公共套件量小,5 个轻查询)。 */
const modeCounts = ref<Record<string, number>>({})
function modeCount(key: string): number | null {
  return modeCounts.value[key] ?? null
}
async function loadModeCounts(): Promise<void> {
  try {
    const qv = q.value.trim() || undefined
    const keys = ['', 'aggregate', 'chain', 'fanout', 'compose']
    const pages = await Promise.all(keys.map((k) => listSuites({
      visibility: 'public',
      q: qv,
      mode: k || undefined,
      page: 1, page_size: 1,
    })))
    modeCounts.value = Object.fromEntries(
      keys.map((k, i) => [k, pages[i].total]))
  } catch {
    modeCounts.value = {}   // 计数是装饰面:失败不阻塞列表
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const env = await listSuites({
      visibility: 'public',
      q: q.value.trim() || undefined,
      mode: modeFilter.value || undefined,
      page: page.value, page_size: pageSize.value,
    })
    items.value = env.items
    total.value = env.total
    if (env.items.length === 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(env.total / pageSize.value))
      return
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

// 搜索(防抖)/模式筛选 → 回第 1 页重拉;翻页直接拉
let qTimer: ReturnType<typeof setTimeout> | undefined
watch(q, () => {
  clearTimeout(qTimer)
  qTimer = setTimeout(() => {
    if (page.value !== 1) page.value = 1
    else void load()
    void loadModeCounts()
  }, 300)
})
watch(modeFilter, () => {
  if (page.value !== 1) page.value = 1
  else void load()
})
watch(page, () => void load())
watch(pageSize, () => {
  if (page.value !== 1) page.value = 1
  else void load()
})

function reload(): void {
  void load()
}

async function forkPublic(s: SuiteSummary): Promise<void> {
  try {
    const out = await forkPublicSuite(s.suiteId)
    toast.success(`已复制为我的用例集「${out.suiteName}」(${out.memberCount} 个成员)`)
    void router.push(`/suites/${out.suiteId}`)
  } catch (e) {
    toast.error(`复制失败:${(e as Error).message}`)
  }
}

onMounted(() => {
  void load()
  void loadModeCounts()
})
</script>

<style scoped>
/* 嵌入项目详情页页签时去掉页壳垫/最小高/居中,只留列表本体 */
.slib.embedded { padding: 0; min-height: 0; max-width: none; margin: 0; }
.slib { --lib-card-max: 51.25rem; }
.slib { display: flex; flex-direction: column; gap: 0.875rem; }

/* ── 原型 _1 · 规范说明条 ─────────────────────────────────────── */
.pub-note {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.625rem 0.875rem;
  background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
}
.pub-note .ni {
  flex: none;
  width: 1.125rem; height: 1.125rem;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.6875rem; font-weight: 700;
  color: var(--sl-accent);
  background: var(--sl-accent-soft);
  border-radius: 50%;
}
.pub-note p { margin: 0; font-size: 0.75rem; color: var(--sl-ink-2); line-height: 1.5; }
.pub-note b { color: var(--sl-ink); }

.slib-toolbar { display: flex; gap: 0.625rem; align-items: center; flex-wrap: wrap; }
.slib-search {
  flex: none; width: 18.75rem; padding: 0.5rem 0.75rem; font-size: 0.8125rem;
  border: 1px solid var(--sl-line); border-radius: 0.5rem;
  background: var(--c-surface); color: var(--sl-ink);
}
.slib-search:focus { outline: none; border-color: var(--sl-accent); }
.slib-modes {
  display: flex; border: 1px solid var(--sl-line);
  border-radius: 0.5rem; overflow: hidden; flex-wrap: wrap;
}
.slib-mode {
  padding: 0.375rem 0.75rem; font-size: 0.78125rem; cursor: pointer;
  border: none; background: transparent; color: var(--sl-ink-2);
  border-right: 1px solid var(--sl-line);
}
.slib-mode:last-child { border-right: none; }
.slib-mode:hover { color: var(--sl-ink); }
.slib-mode.on { background: var(--sl-accent-soft); color: var(--sl-accent); font-weight: 600; }
.slib-mode .mc {
  margin-left: 0.25rem; font-size: 0.6875rem; color: var(--sl-ink-3);
  font-variant-numeric: tabular-nums;
}
.slib-mode.on .mc { color: var(--sl-accent); }
.view-toggle { display: flex; border: 1px solid var(--sl-line); border-radius: 0.5rem; overflow: hidden; }
.vt-btn {
  width: 2rem; height: 1.875rem; border: none; background: transparent;
  color: var(--sl-ink-2); cursor: pointer; font-size: 0.875rem; line-height: 1;
  border-right: 1px solid var(--sl-line);
}
.vt-btn:last-child { border-right: none; }
.vt-btn.on { background: var(--sl-accent-soft); color: var(--sl-accent); }
.slib-public-link {
  font-size: 0.78125rem; color: var(--sl-accent); text-decoration: none; white-space: nowrap;
  padding: 0.4375rem 0.625rem; border-radius: 0.5rem; border: 1px solid var(--sl-accent-soft-border, var(--sl-accent));
}
.slib-public-link:hover { background: var(--sl-accent-soft); }
.flex-1 { flex: 1; }

/* ── 原型 _1 · 卡片流 ─────────────────────────────────────────── */
.pub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(21.25rem, 1fr));
  gap: 0.875rem;
}
.pub-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.875rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
  cursor: pointer;
}
.pub-card:hover { border-color: var(--sl-accent); }
.pc-top { display: flex; align-items: center; gap: 0.375rem; }
.icon-btn {
  border: none; background: none; cursor: pointer;
  color: var(--sl-ink-3); font-size: 0.9375rem; line-height: 1;
  padding: 0.125rem 0.25rem;
}
.icon-btn:hover { color: var(--sl-accent); }
.mode-chip {
  font-size: 0.71875rem; padding: 0.125rem 0.5625rem; border-radius: 62.4375rem;
  white-space: nowrap;
  color: var(--sl-ink-2); background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
}
.mode-chip.chain, .mode-chip.fanout, .mode-chip.compose {
  color: #6d28d9; background: rgb(139 92 246 / 8%); border-color: rgb(139 92 246 / 30%);
}
.draft-chip {
  font-size: 0.65625rem; font-weight: 600; padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--sl-warn-soft); color: var(--sl-warn);
}
.pc-name { margin: 0; font-size: 0.9375rem; font-weight: 600; color: var(--sl-ink); }
.pc-desc {
  margin: 0; font-size: 0.75rem; color: var(--sl-ink-3);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; min-height: 2.125rem;
}
.pc-stats { display: flex; gap: 1.75rem; }
.pc-stat .k { display: block; font-size: 0.6875rem; color: var(--sl-ink-3); }
.pc-stat .v {
  font-size: 0.875rem; font-weight: 600; color: var(--sl-ink);
  font-variant-numeric: tabular-nums;
}
.pc-foot {
  display: flex; align-items: center; gap: 0.5rem;
  padding-top: 0.5rem; border-top: 1px solid var(--sl-line);
}
.pc-owner {
  flex: 1; display: flex; align-items: center; gap: 0.375rem;
  min-width: 0; font-size: 0.75rem; color: var(--sl-ink-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pc-owner .av {
  flex: none; width: 1.375rem; height: 1.375rem;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.625rem; font-weight: 700; color: #fff;
  background: var(--sl-accent); border-radius: 50%;
}
.pc-ops { display: flex; gap: 0.375rem; }

/* ── 列表视图(原表)─────────────────────────────────────────── */
.lib-card { border: 1px solid var(--sl-line); border-radius: 0.625rem; }
.slib-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
.slib-table th {
  text-align: left; font-weight: 500; font-size: 0.75rem; color: var(--sl-ink-3);
  padding: 0.5rem 0.875rem; background: var(--soft-neutral-bg);
}
.slib-row { cursor: pointer; }
.slib-row td { padding: 0.5625rem 0.875rem; border-bottom: 1px solid var(--sl-line); }
.slib-row:hover { background: var(--sl-accent-soft); }
.slib-row:last-child td { border-bottom: none; }
.sl-name { display: flex; align-items: center; gap: 0.375rem; min-width: 0; }
.sl-name .nm { font-weight: 500; color: var(--sl-ink); }
.sl-sid {
  font-size: 0.71875rem; color: var(--sl-ink-3);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.num { font-size: 0.78125rem; font-variant-numeric: tabular-nums; }
.muted { color: var(--sl-ink-3); font-size: 0.75rem; }
.ops { display: flex; gap: 0.5rem; align-items: center; }
.run-btn {
  font-size: 0.75rem; padding: 0.25rem 0.75rem; border-radius: 0.375rem; cursor: pointer;
  color: var(--sl-accent); background: var(--sl-accent-soft);
  border: 1px solid var(--sl-accent-soft-border, var(--sl-accent));
  white-space: nowrap;
}
.run-btn:hover { background: var(--sl-accent); color: #fff; }
.slib-loading { color: var(--sl-ink-3); font-size: 0.8125rem; padding: 0.5rem 0.125rem; }
.card-empty { padding: 2.125rem 0; text-align: center; color: var(--sl-ink-3); font-size: 0.8125rem; }
.cta {
  margin-top: 0.625rem; padding: 0.375rem 1rem; font-size: 0.78125rem; cursor: pointer;
  color: var(--sl-accent); background: var(--sl-accent-soft);
  border: 1px solid var(--sl-accent-soft-border, var(--sl-accent)); border-radius: 0.5rem;
}
</style>
