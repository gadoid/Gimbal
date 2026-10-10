<!-- SuitesPublic.vue — 公共用例集页(2026-10-10 IA 调整;同日样式/功能
     适配轮对齐 SuiteLibrary 规范)。

     原 D-3「公共 Suite 与公共场景同页(ScenariosPublic 分区)」被
     2026-10-10 信息架构调整推翻:侧栏「用例集」组下独立成页。
     数据源 GET /suites?visibility=public(出参含 ownerName = 发布者);
     公共读者不可运行(不变量 7:公共资源先复制再跑),行点击进管理页
     只读态,行内「复制到我的」(fork 深拷贝含编排)跳副本管理页。
     搜索 / 模式筛选与「我的用例集」同款(客户端过滤,百条内)。 -->
<template>
  <section class="slib">
    <PageHead icon="globe" title="公共用例集"
      subtitle="已发布到公共库的 Suite —— 不可直接运行,复制到我的后即可编辑与运行" />

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
        >{{ m.label }}</button>
      </div>
      <router-link class="slib-public-link" to="/suites"
        data-testid="suites-public-back-mine">我的用例集</router-link>
    </div>

    <div v-if="loading" class="slib-loading">加载中…</div>
    <div v-else-if="error" class="card-empty">
      <p>加载失败</p>
      <button type="button" class="cta" @click="reload">重试</button>
    </div>
    <div v-else-if="!filtered.length" class="card-empty" data-testid="suites-public-empty">
      <p>{{ filtering ? '没有匹配的公共用例集 — 换个关键词或筛选条件' : '暂无公共用例集 —— 属主在我的用例集「⋯」菜单发布后出现在这里' }}</p>
    </div>

    <div v-else class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>Suite</th>
            <th style="width:100px">模式</th>
            <th style="width:70px">成员</th>
            <th style="width:110px">发布者</th>
            <th style="width:150px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in filtered"
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

    <p class="slib-note">
      公共用例集没有「+ 新建」——创建永远发生在我的用例集,这里只做浏览与复用。复制得到的是完整深拷贝:编排结构、成员场景与数据集一并落地为自己的私有副本,与源互不影响;源后续的修改不会同步到副本。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { forkPublicSuite, listSuites, type SuiteSummary } from '@/api/suites'
import { MODE_LABEL } from '@/utils/suiteStructure'
import { toast } from '@/utils/toast'

const router = useRouter()
const items = ref<SuiteSummary[]>([])
const loading = ref(true)
const error = ref(false)
const q = ref('')
const modeFilter = ref('')

const modeFilters = [
  { key: '', label: '全部' },
  { key: 'aggregate', label: MODE_LABEL.aggregate },
  { key: 'chain', label: MODE_LABEL.chain },
  { key: 'fanout', label: MODE_LABEL.fanout },
  { key: 'compose', label: MODE_LABEL.compose },
]

const filtering = computed(() =>
  Boolean(q.value.trim() || modeFilter.value))

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return items.value
    .filter((s) => !modeFilter.value || s.mode === modeFilter.value)
    .filter((s) => !needle
      || s.name.toLowerCase().includes(needle)
      || (s.description || '').toLowerCase().includes(needle)
      || (s.ownerName || '').toLowerCase().includes(needle))
})

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const env = await listSuites({ visibility: 'public', page_size: 100 })
    items.value = env.items
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

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

onMounted(reload)
</script>

<style scoped>
/* 与 SuiteLibrary(我的用例集)同一套列表规范:lib-card 容器、
   13px 表格、indigo 主按钮系、card-empty 空态。 */
.slib { display: flex; flex-direction: column; gap: 14px; }
.slib-toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.slib-search {
  flex: none; width: 300px; padding: 8px 12px; font-size: 13px;
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 8px;
  background: transparent; color: inherit;
}
.slib-search:focus { outline: none; border-color: var(--accent-soft-border); }
.slib-modes {
  display: flex; border: 1px solid rgb(100 116 139 / 30%);
  border-radius: 8px; overflow: hidden;
}
.slib-mode {
  padding: 6px 12px; font-size: 12.5px; cursor: pointer;
  border: none; background: transparent; color: inherit;
  border-right: 1px solid rgb(100 116 139 / 20%);
}
.slib-mode:last-child { border-right: none; }
.slib-mode.on { background: var(--accent-soft); color: #4338ca; font-weight: 600; }
.slib-public-link {
  font-size: 12.5px; color: #4338ca; text-decoration: none; white-space: nowrap;
  padding: 7px 10px; border-radius: 8px; border: 1px solid var(--accent-soft-border);
}
.slib-public-link:hover { background: var(--accent-soft); }
.lib-card { border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px; overflow: hidden; }
.slib-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.slib-table th {
  text-align: left; font-weight: 500; font-size: 12px; color: rgb(100 116 139);
  padding: 8px 14px; background: rgb(100 116 139 / 6%);
}
.slib-row { cursor: pointer; }
.slib-row td { padding: 9px 14px; border-bottom: 1px solid rgb(100 116 139 / 10%); }
.slib-row:hover { background: rgb(59 130 246 / 5%); }
.slib-row:last-child td { border-bottom: none; }
.sl-name { display: flex; align-items: center; gap: 6px; min-width: 0; }
.sl-name .nm { font-weight: 500; }
.sl-sid { font-size: 11.5px; color: rgb(100 116 139); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mode-chip {
  font-size: 11.5px; padding: 2px 9px; border-radius: 999px;
  white-space: nowrap;
  color: rgb(100 116 139); background: rgb(100 116 139 / 8%);
  border: 1px solid rgb(100 116 139 / 22%);
}
.mode-chip.chain, .mode-chip.fanout, .mode-chip.compose {
  color: #6d28d9; background: rgb(139 92 246 / 8%); border-color: rgb(139 92 246 / 30%);
}
.num { font-size: 12.5px; }
.muted { color: rgb(100 116 139); font-size: 12px; }
.ops { display: flex; gap: 8px; align-items: center; }
.run-btn {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.run-btn:hover { background: var(--accent-soft-border); }
.slib-loading { color: rgb(100 116 139); font-size: 13px; padding: 8px 2px; }
.card-empty { padding: 34px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.cta {
  margin-top: 10px; padding: 6px 16px; font-size: 12.5px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border); border-radius: 8px;
}
.slib-note {
  font-size: 12px; color: rgb(100 116 139); line-height: 1.7;
  border-top: 1px solid rgb(100 116 139 / 15%); padding-top: 12px;
}
</style>
