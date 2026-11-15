<!-- Auths.vue — 凭证池管理页(2026-11-13 形态重塑:槽位卡片看板)。
     槽位是执行取凭证的键,所以一槽一卡:卡面 = 槽名 + 状态徽章(测败/
     无默认/未声明)+ 引用聚合;绑定行卡内直渲染(>5 条折叠),行级操作
     (测试一键/设默认/编辑/删除)与被引用侧板原样。状态色顶边:红=有
     测败记忆、琥珀=无默认∨未声明、绿=健康;问题槽排前,「只看问题」
     一键滤出。取数单一链路(200 封顶与旧分组口径一致),搜索/类型过滤
     照旧下推服务端。创建/编辑(渐进披露)/删除/测试弹框/反查侧板不动。 -->
<template>
  <section class="slib">
    <PageHead
      icon="lock"
      title="凭证管理"
      :count="rowsTotal ? `${slotCount} 槽 · ${rowsTotal} 绑定` : undefined"
      :meta="metaText"
    />

    <div class="slib-toolbar">
      <input
        v-model="searchQuery"
        class="slib-search"
        placeholder="搜索 alias / username / url"
        data-testid="auth-search"
      />
      <span class="svc-stats tight" data-testid="tt-filter-group">
        <button
          v-for="t in TT_FILTERS"
          :key="t"
          type="button"
          class="svc-chip"
          :class="{ on: tokenTypeFilter === t }"
          :data-testid="`tt-filter-${t}`"
          @click="tokenTypeFilter = t"
        >{{ t === 'all' ? '全部类型' : t }}</button>
      </span>
      <!-- 状态优先:只看有问题的槽(无默认 · 上次测试失败) -->
      <button
        type="button" class="svc-chip" :class="{ on: problemOnly }"
        data-testid="problem-filter" @click="problemOnly = !problemOnly"
      >只看问题</button>
      <button type="button" class="slib-create" data-testid="open-create" @click="openCreate()">+ 新增认证</button>
    </div>

    <!-- 槽位卡片看板 -->
    <div v-if="slotCards.length" class="auth-board">
      <div
        v-for="card in slotCards" :key="card.slot"
        class="slot-card" :class="`tone-${card.tone}`"
        :data-testid="`slot-card-${card.slot}`"
      >
        <div class="sc-head">
          <span class="sc-slot">槽 <b class="mono">{{ card.slot }}</b></span>
          <span class="muted sc-n">{{ card.binds.length }} 绑定</span>
          <span v-if="!card.hasDefault" class="svc-chip warn">无默认</span>
          <!-- 状态聚合:本机记录的上次测试失败数(卡面一眼看穿) -->
          <span
            v-if="card.failCount" class="svc-flag red"
            :data-testid="`slot-fail-${card.slot}`"
            title="本机记录:该槽存在上次测试失败的绑定"
          >✕{{ card.failCount }} 测败</span>
          <!-- 槽位主轴直连:该槽在服务注册的身份面注册表里无声明 -->
          <span
            v-if="slotsReady && !declaredSlots.has(card.slot)"
            class="svc-flag amber"
            :data-testid="`slot-undeclared-${card.slot}`"
            title="服务注册无身份面声明此槽 — 经别名注入不会取用;仅场景 ${slot.X} 直接引用可达"
          >✕ 未声明</span>
          <span class="flex-1" />
          <!-- 引用聚合(点开 = 该槽默认绑定的被引用侧板) -->
          <button
            v-if="card.aliasRefs" type="button" class="svc-chip"
            :data-testid="`slot-refs-${card.slot}`" @click="openSlotRefs(card)"
          >{{ card.aliasRefs }} 别名</button>
          <button
            v-if="card.scenarioRefs" type="button" class="svc-chip"
            @click="openSlotRefs(card)"
          >{{ card.scenarioRefs }} 场景</button>
        </div>

        <div class="sc-binds">
          <div v-for="row in card.visible" :key="row.id" class="sc-bind" :data-testid="`auth-row-${row.id}`">
            <div class="bind-line">
              <span class="mono svc-key">{{ row.alias }}</span>
              <span
                v-if="row.isDefault" class="svc-chip"
                style="font-size:11px" :data-testid="`default-chip-${row.id}`"
                title="名字解析与环境未命中时的取用行">默认</span>
              <span
                v-if="testMemory[row.id]" class="svc-flag"
                :class="testMemory[row.id].ok ? 'green' : 'red'"
                style="font-size:11px" :data-testid="`test-mem-${row.id}`"
                :title="`上次测试:${testMemory[row.id].ok ? '成功' : '失败'} · ${shortDateTime(new Date(testMemory[row.id].at))}(本机记录)`"
              >{{ testMemory[row.id].ok ? '✓ 测通' : '✗ 测败' }} {{ shortDateTime(new Date(testMemory[row.id].at)) }}</span>
              <span class="flex-1" />
              <span class="svc-flag" :class="ttClass[row.token_type] ?? 'ink'">{{ row.token_type }}</span>
              <span class="muted" style="font-size:11px">{{ formatExpires(row.expires_in) }}</span>
            </div>
            <div class="bind-line sub">
              <span class="mono muted">{{ row.url }}</span>
              <span
                v-if="row.system || row.envId" class="muted"
                style="font-size:11px" :data-testid="`binding-ctx-${row.id}`"
              >{{ row.system || '未归类' }}<template v-if="row.envId"> · 环境#{{ row.envId }}</template></span>
            </div>
            <div class="bind-line acts">
              <div class="flex flex-wrap items-center gap-1">
                <button
                  v-if="row.alias_ref_count" type="button" class="svc-chip"
                  :data-testid="`refs-open-${row.alias}`" @click="openRefs(row)"
                >{{ row.alias_ref_count }} 别名</button>
                <button
                  v-if="row.scenario_ref_count" type="button" class="svc-chip"
                  :data-testid="`refs-open-scenario-${row.alias}`" @click="openRefs(row)"
                >{{ row.scenario_ref_count }} 场景</button>
                <span
                  v-if="!row.alias_ref_count && !row.scenario_ref_count" class="muted"
                  title="别名绑定与场景引用均为零(快照类不计)— 删除不触发 409 拦截"
                >未被引用 · 可安全删除</span>
                <span class="flex-1" />
                <span class="mono muted" style="font-size:11px">{{ row.username }}</span>
              </div>
              <div class="row-acts">
                <!-- 高频操作升为一键:测试连通不进菜单(结果回写行内状态) -->
                <button
                  type="button" class="svc-link"
                  :data-testid="`auth-test-inline-${row.id}`"
                  @click="runTest(row)"
                >测试</button>
                <DropdownMenu>
                  <DropdownMenuTrigger
                    class="more-btn"
                    aria-label="更多操作"
                    :data-testid="`auth-more-${row.id}`"
                  >⋯</DropdownMenuTrigger>
                  <DropdownMenuContent align="end" class="sl-menu">
                    <DropdownMenuItem
                      v-if="!row.isDefault"
                      class="sl-menu-item" data-testid="auth-set-default"
                      @click="makeDefault(row)"
                    >设为槽默认</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" data-testid="auth-edit" @click="openEdit(row)">编辑</DropdownMenuItem>
                    <DropdownMenuItem
                      class="sl-menu-item danger"
                      data-testid="auth-del"
                      @click="openDelete(row)"
                    >删除</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
          <button
            v-if="card.collapsible" type="button" class="sc-more"
            :data-testid="`slot-more-${card.slot}`" @click="toggleSlot(card.slot)"
          >{{ expandedSlots.has(card.slot) ? '收起' : `还有 ${card.hiddenCount} 条绑定` }}</button>
        </div>
      </div>
    </div>

    <div v-else-if="rowsLoading" class="py-10 text-center text-body text-muted-foreground">加载中…</div>
    <div v-else class="empty-cta" data-testid="auths-empty">
      <p>暂无认证 — 复制用例中的 alias 在此登记</p>
      <Button variant="outline" size="sm" @click="openCreate()">+ 新增认证</Button>
    </div>

    <!-- ── 创建 / 编辑(定稿表单范式)──────────────────────────── -->
    <Dialog :open="createOpen" @update:open="createOpen = $event">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ editingId ? '编辑认证' : '+ 新增认证' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onSubmitForm">
          <FormField v-slot="{ componentField }" name="alias">
            <FormItem>
              <FormLabel>alias<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" :disabled="!!editingId"
                  placeholder="例 qa1 / staging-codfish（同 owner 内唯一）" data-testid="f-alias" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <!-- S7.3:槽位/系统/环境/账号字段 —— 创建时可指定槽(缺省=alias,
               同槽多绑定按环境/默认分层取用);编辑态槽位不可改(改名=重建) -->
          <FormField v-slot="{ componentField }" name="slot">
            <FormItem>
              <FormLabel>槽位 slot</FormLabel>
              <FormControl>
                <Input v-bind="componentField" :disabled="!!editingId"
                  placeholder="缺省 = alias;场景经 ${slot.X} 引用" data-testid="f-slot" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="url">
            <FormItem>
              <FormLabel>登录 URL<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="https://target/auth/login" data-testid="f-url" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>username<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="登录用户名" data-testid="f-username" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="password">
            <FormItem>
              <FormLabel>password<span v-if="!editingId" class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" type="password"
                  :placeholder="editingId ? '留空表示不修改' : '登录密码'" data-testid="f-password" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <!-- 渐进披露:90% 场景是 alias+账号密码+URL;系统/环境/账号字段/
               token 类型/有效期收进「高级」折叠区(默认收起;编辑态有非
               缺省值时自动展开;v-show 保持字段常驻,vee-validate 不感知) -->
          <button
            type="button" class="adv-toggle" data-testid="f-advanced-toggle"
            @click="advancedOpen = !advancedOpen"
          >{{ advancedOpen ? '▾' : '▸' }} 高级(系统 / 环境 / 账号字段 / token 类型 / 有效期)</button>

          <div v-show="advancedOpen" class="flex flex-col gap-3" data-testid="f-advanced-body">
            <div class="grid grid-cols-2 gap-3">
              <FormField v-slot="{ componentField }" name="system">
                <FormItem>
                  <FormLabel>系统</FormLabel>
                  <FormControl>
                    <Input v-bind="componentField" placeholder="例 fin-service(空=未归类)" data-testid="f-system" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
              <FormField v-slot="{ componentField }" name="envId">
                <FormItem>
                  <FormLabel>环境</FormLabel>
                  <FormControl>
                    <Select v-bind="componentField">
                      <SelectTrigger data-testid="f-env"><SelectValue placeholder="不限" /></SelectTrigger>
                      <SelectContent>
                        <!-- Radix Select 禁空串 value → 'none' 哨兵 = 不限 -->
                        <SelectItem value="none">不限</SelectItem>
                        <SelectItem v-for="e in envs" :key="e.id" :value="String(e.id)">
                          {{ e.name }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
            </div>

            <!-- FormField 外置 KV 行(vee-validate 不管控,提交时聚合) -->
            <div class="flex flex-col gap-1.5">
              <label class="text-label font-medium text-signal-ink">账号字段(供 ${slot.X.field} 注入,如 orgNo)</label>
              <div class="flex flex-col gap-2">
                <div v-for="(af, i) in accountFields" :key="i" class="flex items-center gap-2">
                  <Input v-model="af.key" placeholder="字段名,例 orgNo" class="flex-1"
                    :data-testid="`f-af-key-${i}`" />
                  <Input v-model="af.value" placeholder="值" class="flex-1"
                    :data-testid="`f-af-value-${i}`" />
                  <Button type="button" variant="ghost" size="sm" :data-testid="`f-af-del-${i}`"
                    @click="accountFields.splice(i, 1)">✕</Button>
                </div>
                <Button type="button" variant="outline" size="sm" data-testid="f-af-add"
                  @click="accountFields.push({ key: '', value: '' })">+ 加字段</Button>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <FormField v-slot="{ componentField }" name="token_type">
                <FormItem>
                  <FormLabel>token_type</FormLabel>
                  <FormControl>
                    <Select v-bind="componentField">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Bearer">Bearer</SelectItem>
                        <SelectItem value="Basic">Basic</SelectItem>
                        <SelectItem value="Cookie">Cookie</SelectItem>
                        <SelectItem value="Authorization">Authorization（整段头）</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
              <FormField v-slot="{ componentField }" name="expires_in">
                <FormItem>
                  <FormLabel>expires_in（秒）</FormLabel>
                  <FormControl>
                    <Input v-bind="componentField" type="number" :min="0" :max="86400" class="w-[140px]" data-testid="f-expires" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
            </div>
          </div>

          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="createOpen = false">取消</Button>
            <Button type="submit" :disabled="submitting">{{ editingId ? '保存' : '创建' }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 测试结果弹框(状态主视觉式)─────────────────────────── -->
    <Dialog :open="testOpen" @update:open="testOpen = $event">
      <DialogContent class="max-w-[460px]">
        <DialogHeader>
          <DialogTitle>认证测试</DialogTitle>
        </DialogHeader>
        <div v-if="testTarget" class="test-hero">
          <div class="test-sub">{{ testTarget.alias }} · {{ testTarget.url }}</div>

          <div v-if="testPhase === 'testing'" class="test-state testing">
            <span class="test-icon spinner" />
            <span class="test-word">认证中…</span>
          </div>

          <template v-else-if="testResult">
            <div class="test-state" :class="testPhase">
              <span class="test-icon">{{ testPhase === 'success' ? '✓' : '✗' }}</span>
              <span class="test-word">{{ testPhase === 'success' ? '认证成功' : '认证失败' }}</span>
              <span v-if="testResult.status_code != null" class="test-code">
                HTTP {{ testResult.status_code }}
              </span>
            </div>
            <button class="detail-toggle" type="button" @click="testDetailOpen = !testDetailOpen">
              {{ testDetailOpen ? '▾' : '▸' }} 详情
            </button>
            <code v-if="testDetailOpen" class="mono detail">{{ testResult.message }}</code>
          </template>
        </div>
        <DialogFooter>
          <Button v-if="testPhase !== 'testing' && testTarget" variant="outline" @click="runTest(testTarget)">
            重新测试
          </Button>
          <Button @click="testOpen = false">关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── 删除确认(输入 alias 硬确认)────────────────────────── -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>删除认证</DialogTitle>
        </DialogHeader>
        <div v-if="deleteTarget" class="flex flex-col gap-3">
          <p class="m-0 text-body leading-relaxed">
            此操作不可撤销。alias <code class="rounded-chip bg-signal-failed/10 px-1.5 font-mono text-signal-failed">{{ deleteTarget.alias }}</code>
            将从凭证池中移除（已使用此 alias 的历史执行记录不受影响）。
          </p>
          <p class="m-0 text-body">要继续请输入 <code class="font-mono">{{ deleteTarget.alias }}</code> 确认：</p>
          <Input v-model="deleteConfirmInput" :placeholder="`输入 ${deleteTarget.alias} 以确认`" data-testid="del-confirm" />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="deleteOpen = false">取消</Button>
          <Button variant="destructive" :disabled="!deleteConfirmed || deleteSubmitting" data-testid="del-submit" @click="submitDelete">
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <!-- ── 被引用反查侧板(配套方案 §1.2/§1.3)──────────────────
         原型 H-auths-v2 = 右侧滑入面板:用 Sheet(side=right)。项目的 vaul
         Drawer 是底部抽屉,先前把 max-w 加在它上面 = 底部居中窄条(位置不对)。 -->
    <Sheet :open="refsOpen" @update:open="refsOpen = $event">
      <SheetContent
        side="right"
        class="flex w-[460px] max-w-[92vw] flex-col gap-0 p-0 sm:max-w-[460px]"
        data-testid="refs-sheet"
      >
        <SheetHeader class="border-b border-signal-line px-4 py-3">
          <SheetTitle class="text-left">被引用 · {{ refsTarget?.alias }}</SheetTitle>
          <SheetDescription class="text-left">
            名字引用 — 场景与别名解析按执行者本人凭证池,非本条凭证对象(§1.4)
          </SheetDescription>
        </SheetHeader>
        <div class="flex-1 overflow-y-auto px-4 py-3 text-caption">
          <p v-if="refsLoading" class="m-0 py-4 text-center text-muted-foreground">扫描场景引用中…</p>
          <template v-else-if="refsData">
            <h4 class="m-0 mb-1.5 text-label font-semibold text-signal-ink">
              别名绑定({{ refsData.alias_refs.length }})
            </h4>
            <div v-for="a in refsData.alias_refs" :key="a.alias_name" class="ref-row">
              <router-link
                :to="`/service-admin/${encodeURIComponent(a.alias_name)}?tab=credential`"
                class="mono link"
              >{{ a.alias_name }}</router-link>
              <span class="ref-dim">→ {{ a.base_service }}</span>
            </div>
            <p v-if="!refsData.alias_refs.length" class="ref-dim m-0">无别名绑定</p>

            <h4 class="m-0 mb-1.5 mt-4 text-label font-semibold text-signal-ink">
              场景引用(可见 {{ refsData.scenario_refs.visible.length }})
            </h4>
            <div v-for="v in refsData.scenario_refs.visible" :key="v.scenario_id" class="ref-row">
              <router-link :to="`/scenarios/${v.scenario_id}/detail`" class="link">
                {{ v.name }}
              </router-link>
              <span
                v-for="k in v.kinds"
                :key="k"
                class="svc-flag"
                :class="KIND_TONE[k] ?? 'ink'"
                :title="kindTitle(k)"
              >{{ kindLabel(k) }}</span>
            </div>
            <p v-if="!refsData.scenario_refs.visible.length" class="ref-dim m-0">无可见场景引用</p>
            <p
              v-if="refsData.scenario_refs.hidden_count"
              class="ref-dim m-0 mt-1"
              data-testid="refs-hidden-count"
            >另有 {{ refsData.scenario_refs.hidden_count }} 条不可见(他人私有场景,仅计数不显名)</p>

            <!-- 原型 H-auths-v2 抽屉底部淡红预警:与 DELETE 409 同口径
                 (本人场景的模板引用才拦截;M2a S6 后方案绑定不再点名凭证)
                 提前告知,避免撞 409 -->
            <div v-if="drawerBlocking.length" class="drawer-warn" data-testid="refs-block-warn">
              <p class="m-0 font-semibold">删除会被拦截:仍有 {{ drawerBlocking.length }} 个本人场景引用(模板)</p>
              <p class="m-0 mt-0.5">先解除别名绑定,或先清理场景里的模板引用;他人场景与快照不会阻断删除。</p>
            </div>
          </template>
        </div>
      </SheetContent>
    </Sheet>
  </section>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed, onMounted, ref, watch } from 'vue'
import { toTypedSchema } from '@/utils/zod-typed-schema'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import { useAuthStore } from '@/stores/auth'
import {
  getReferences, list as apiList, setDefault as apiSetDefault,
  type AuthReferences, type AuthSession, type TestResult,
} from '@/api/auth_sessions'
import { listAllAliases } from '@/api/service-aliases'
import { listEnvironments } from '@/api/environments'
import { shortDateTime } from '@/utils/datetime'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const store = useAuthSessionsStore()

/** 引用类型 → 徽标配色档:模板引用绿、快照(不拦截)灰。
 *  scheme(方案绑定)已随 authz M2a S6 退役 — serviceBindings 选注册表
 *  别名,不再点名凭证,反查不会再报该种类。 */
const KIND_TONE: Record<string, string> = {
  template: 'green',
  snapshot: 'ink',
}
/** token_type → 徽标配色档(与 .svc-flag 同族) */
const ttClass: Record<string, string> = {
  Bearer: 'blue',
  Basic: 'amber',
  Cookie: 'green',
  Authorization: 'red',
}

// ── filters(M4:检索/类型过滤下推服务端,Page 信封)───────────────
// useServerList 观察 params 签名:q/类型任一变化 → 300ms 防抖重拉 + 回页 1。
// username 是服务端 Fernet 密文不可检索(q 只打 alias/url,占位文案如实)。
const route = useRoute()
// W3:凭证角标跳转带 ?q=别名 定位缺失项(无路由环境守卫)
const searchQuery = ref(
  typeof route?.query?.q === 'string' ? route.query.q : '')
const TT_FILTERS = ['all', 'Bearer', 'Basic', 'Cookie', 'Authorization'] as const
type TtFilter = typeof TT_FILTERS[number]
const tokenTypeFilter = ref<TtFilter>('all')

// ── 数据(单一链路:200 封顶取回;搜索/类型过滤下推服务端)────────
const rows = ref<AuthSession[]>([])
const rowsTotal = ref(0)
const rowsLoading = ref(false)
const tokenTypeCounts = ref<Record<string, number>>({})

async function reloadList(): Promise<void> {
  rowsLoading.value = true
  try {
    const env = await apiList({
      q: searchQuery.value.trim() || undefined,
      token_type: tokenTypeFilter.value === 'all' ? undefined : tokenTypeFilter.value,
      page: 1, page_size: 200,
    })
    tokenTypeCounts.value = env.tokenTypeCounts ?? {}
    rows.value = env.items
    rowsTotal.value = env.total
  } finally {
    rowsLoading.value = false
  }
}

let filterDebounce: ReturnType<typeof setTimeout> | undefined
watch([searchQuery, tokenTypeFilter], () => {
  clearTimeout(filterDebounce)
  filterDebounce = setTimeout(() => { void reloadList() }, 300)
})

// ── 槽位主轴直连:该槽在服务注册的身份面注册表里有无声明 ──────────
// 读面全员(listAllAliases);拉不到不亮 chip(静默降级,不阻塞凭证池)
const declaredSlots = ref<Set<string>>(new Set())
const slotsReady = ref(false)

/** 只看问题:无默认 ∨ 有测败的槽(卡片级过滤)。 */
const problemOnly = ref(false)

// ── 槽位卡片看板 ──────────────────────────────────────────────
const BIND_CAP = 5   // 单卡绑定行折叠阈值(>5 收起为「还有 N 条」)

interface SlotCard {
  slot: string
  binds: AuthSession[]
  visible: AuthSession[]
  collapsible: boolean
  hiddenCount: number
  hasDefault: boolean
  failCount: number
  tone: 'bad' | 'warn' | 'ok'
  aliasRefs: number
  scenarioRefs: number
}

const expandedSlots = ref<Set<string>>(new Set())
function toggleSlot(slot: string): void {
  const next = new Set(expandedSlots.value)
  if (next.has(slot)) next.delete(slot)
  else next.add(slot)
  expandedSlots.value = next
}

/** 卡片序:问题槽(测败 ∨ 无默认)排前,其余字典序;槽内默认在前。 */
const slotCards = computed<SlotCard[]>(() => {
  const bySlot = new Map<string, AuthSession[]>()
  for (const a of rows.value) {
    const k = a.slot || a.alias
    const arr = bySlot.get(k)
    if (arr) arr.push(a)
    else bySlot.set(k, [a])
  }
  const cards: SlotCard[] = []
  for (const [slot, list] of bySlot) {
    const binds = [...list].sort((x, y) =>
      Number(y.isDefault) - Number(x.isDefault) || x.alias.localeCompare(y.alias))
    const failCount = binds.filter((r) => testMemory.value[r.id]?.ok === false).length
    const hasDefault = binds.some((r) => r.isDefault)
    const undeclared = slotsReady.value && !declaredSlots.value.has(slot)
    const open = expandedSlots.value.has(slot)
    cards.push({
      slot, binds,
      visible: open ? binds : binds.slice(0, BIND_CAP),
      collapsible: binds.length > BIND_CAP,
      hiddenCount: Math.max(0, binds.length - BIND_CAP),
      hasDefault, failCount,
      tone: failCount ? 'bad' : (!hasDefault || undeclared) ? 'warn' : 'ok',
      aliasRefs: binds.reduce((n, r) => n + (r.alias_ref_count ?? 0), 0),
      scenarioRefs: binds.reduce((n, r) => n + (r.scenario_ref_count ?? 0), 0),
    })
  }
  const weight = (c: SlotCard) => (c.failCount ? 1 : 0) + (c.hasDefault ? 0 : 1)
  const kept = problemOnly.value ? cards.filter((c) => weight(c) > 0) : cards
  return kept.sort((x, y) => weight(y) - weight(x) || x.slot.localeCompare(y.slot))
})
const slotCount = computed(() => slotCards.value.length)

/** 卡面引用聚合 → 打开该槽默认(或首个)绑定的被引用侧板。 */
function openSlotRefs(card: SlotCard): void {
  const target = card.binds.find((r) => r.isDefault) ?? card.binds[0]
  if (target) openRefs(target)
}

const metaText = computed(() => {
  const total = rowsTotal.value
  if (total === 0) return '用户级独立凭证池 · 与 yaml 文件 Config.users 解耦'
  const unref = rows.value.filter(
    (a) => !a.alias_ref_count && !a.scenario_ref_count,
  ).length
  // 原型 H-auths-v2 统计行:「N 条凭证 · …未被任何引用」(已过期无数据源,不列)。
  // 类型计数走 tokenTypeCounts(全量口径,M4 服务端聚合;unref 是当前页口径)。
  const unrefSeg = unref ? ` · ${unref} 条未被任何引用` : ''
  const bearer = tokenTypeCounts.value.Bearer ?? 0
  const wholeHeader = tokenTypeCounts.value.Authorization ?? 0
  return `${total} 条凭证${unrefSeg} · ${bearer} Bearer · ${wholeHeader} 整段头`
})

function formatExpires(seconds: number): string {
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`
  if (seconds >= 60) return `${Math.round(seconds / 60)}m`
  return `${seconds}s`
}

// ── create / edit(定稿范式;password 条件必填在 submit 内补判)──
const createOpen = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
/** 渐进披露:高级区(系统/环境/账号字段/token/有效期)默认收起 */
const advancedOpen = ref(false)

const schema = toTypedSchema(z.object({
  alias: z.string()
    .min(1, '请输入 alias')
    .regex(/^[A-Za-z0-9_-]{1,64}$/, '1-64 位字母数字下划线连字符'),
  // S7.3 槽位(缺省 = alias;编辑态禁改,改名=重建)
  slot: z.string()
    .regex(/^[A-Za-z0-9_-]{0,64}$/, '0-64 位字母数字下划线连字符'),
  system: z.string(),
  // 环境选值是字符串 id('none' 哨兵 = 不限),提交时转 number
  envId: z.string(),
  // authz C2:静态令牌认证(自举系统 platform 等)—— 登录 URL 可空
  url: z.string().url('URL 格式不正确').or(z.literal('')),
  username: z.string().min(1, '请输入 username'),
  // 编辑态可留空(= 不修改) — 创建态必填由 onSubmitForm 补判
  password: z.string(),
  token_type: z.enum(['Bearer', 'Basic', 'Cookie', 'Authorization']),
  expires_in: z.coerce.number().int('整数秒').min(0).max(86400, '最大 86400'),
}))

const { handleSubmit, resetForm, setFieldError } = useForm({
  validationSchema: schema,
  initialValues: {
    alias: '', slot: '', system: '', envId: 'none',
    url: '', username: '', password: '',
    token_type: 'Bearer' as const, expires_in: 7200,
  },
})

// ── S7.3 表单辅面:环境选项 + 账号字段 KV 行(vee-validate 外置)──
const envs = ref<Array<{ id: number; name: string }>>([])
const accountFields = ref<Array<{ key: string; value: string }>>([])

function accountFieldsFromRow(row: AuthSession): Array<{ key: string; value: string }> {
  const src = (row as AuthSession & { accountFields?: Record<string, unknown> }).accountFields
  if (!src || typeof src !== 'object') return []
  return Object.entries(src).map(([k, v]) => ({ key: k, value: v == null ? '' : String(v) }))
}

function accountFieldsToObject(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const af of accountFields.value) {
    const k = af.key.trim()
    if (k) out[k] = af.value
  }
  return out
}

/** ``slot``:预填槽位(S7.5 导入结果「去绑定」深链 ?newSlot=);
 *  ``system``/``envId``:执行配置枢纽「缺失深链预填直达」(分层③)。 */
function openCreate(slot = '', system = '', envId = '') {
  editingId.value = null
  accountFields.value = []
  // 高级区:深链带 system/envId 预填时自动展开(否则默认收起)
  advancedOpen.value = Boolean(system || envId)
  resetForm({
    values: {
      alias: slot, slot, system, envId: envId || 'none',
      url: '', username: '', password: '', token_type: 'Bearer', expires_in: 7200,
    },
  })
  createOpen.value = true
}

/** authz M2a S3:置为该槽默认(同槽旧默认由后端原子清除)。 */
async function makeDefault(row: AuthSession) {
  try {
    await apiSetDefault(row.id)
    toast.success(`已将 ${row.alias} 设为槽「${row.slot || row.alias}」的默认绑定`)
    await reloadList()
  } catch (e) {
    showError('设为默认', undefined, (e as Error).message)
  }
}

function openEdit(row: AuthSession) {
  editingId.value = row.id
  accountFields.value = accountFieldsFromRow(row)
  // 编辑态:高级项有非缺省值时自动展开,一眼看到全部存量
  advancedOpen.value = Boolean(
    row.system || row.envId != null || accountFields.value.length
    || row.token_type !== 'Bearer' || row.expires_in !== 7200)
  resetForm({
    values: {
      alias: row.alias,
      slot: row.slot || row.alias,
      system: row.system || '',
      envId: row.envId != null ? String(row.envId) : 'none',
      url: row.url,
      username: row.username,
      password: '',
      // AuthSession.token_type 是宽 string;schema 是枚举 — 数据源即四选一
      token_type: row.token_type as 'Bearer' | 'Basic' | 'Cookie' | 'Authorization',
      expires_in: row.expires_in,
    },
  })
  createOpen.value = true
}

const onSubmitForm = handleSubmit(async (values) => {
  if (submitting.value) return
  // 创建态 password 必填(schema 静态化,条件规则在此单点补判)
  if (!editingId.value && !values.password) {
    setFieldError('password', '请输入 password')
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      const patch: Record<string, unknown> = {
        url: values.url,
        username: values.username,
        token_type: values.token_type,
        expires_in: values.expires_in,
        // S7.3 槽位辅面(槽不可改;env none=清空,显式 null 语义由值本身表达)
        system: values.system,
        envId: values.envId === 'none' ? null : Number(values.envId),
        accountFields: accountFieldsToObject(),
      }
      if (values.password) patch.password = values.password
      await store.patchAuth(editingId.value, patch)
      toast.success('已保存')
    } else {
      await store.createAuth({
        alias: values.alias,
        // 槽位:显式且 ≠ alias 才送(缺省 = alias 是后端口径)
        ...(values.slot && values.slot !== values.alias ? { slot: values.slot } : {}),
        system: values.system,
        ...(values.envId !== 'none' ? { envId: Number(values.envId) } : {}),
        accountFields: accountFieldsToObject(),
        url: values.url,
        username: values.username,
        password: values.password,
        token_type: values.token_type,
        expires_in: values.expires_in,
      })
      toast.success(`已创建 ${values.alias}`)
    }
    createOpen.value = false
    void reloadList()
  } catch (e) {
    // store 的 mutation 不维护 lastError — 必须用捕获到的错误本身，
    // 否则会显示上一次 fetch 的陈旧错误。
    showError('保存', undefined, (e as Error).message)
  } finally {
    submitting.value = false
  }
})

// ── test ───────────────────────────────────────────────────────
// 状态机:开弹框即 testing(修复历史 bug — 标题三元把 null 折叠成
// "连通失败",在途假失败);返回/异常切终态。失败详情默认展开。
const testOpen = ref(false)
const testPhase = ref<'testing' | 'success' | 'fail'>('testing')
const testResult = ref<TestResult | null>(null)
const testTarget = ref<AuthSession | null>(null)
const testDetailOpen = ref(true)

async function runTest(row: AuthSession) {
  testTarget.value = row
  testResult.value = null
  testPhase.value = 'testing'
  testDetailOpen.value = true
  testOpen.value = true
  try {
    testResult.value = await store.testConnection(row.id)
    testPhase.value = testResult.value.ok ? 'success' : 'fail'
    // 成功默认收起(信息就一行 token 预览);失败保持展开直接看到原因
    if (testPhase.value === 'success') testDetailOpen.value = false
  } catch (e) {
    testResult.value = {
      ok: false,
      status_code: null,
      message: (e as Error).message || '请求失败',
    }
    testPhase.value = 'fail'
  }
  // 终态回写本机记忆(行内 chip / 组头聚合;仅本浏览器,不落库)
  rememberTest(row.id, testPhase.value === 'success')
}

// ── 测试结果本机记忆(状态优先:列表回答"哪些还能用")─────────────
// 后端无测试历史面,v1 以 localStorage 记每条凭证的最近一次结果
// (per-browser;跨设备不同步 — chip 标注"本机记录"如实降级)。
const TEST_MEM_KEY = 'auths.test-memory:v1'
const testMemory = ref<Record<number, { ok: boolean; at: number }>>({})

function loadTestMemory(): void {
  try {
    const raw = localStorage.getItem(TEST_MEM_KEY)
    if (raw) testMemory.value = JSON.parse(raw) as typeof testMemory.value
  } catch { testMemory.value = {} }
}

function rememberTest(id: number, ok: boolean): void {
  testMemory.value = { ...testMemory.value, [id]: { ok, at: Date.now() } }
  try { localStorage.setItem(TEST_MEM_KEY, JSON.stringify(testMemory.value)) }
  catch { /* 隐私模式等写入失败 — 内存态仍生效 */ }
}

// ── delete ─────────────────────────────────────────────────────
const deleteOpen = ref(false)
const deleteSubmitting = ref(false)
const deleteTarget = ref<AuthSession | null>(null)
const deleteConfirmInput = ref('')

// ── 被引用反查侧板(配套方案 §1.2/§1.3)──────────────────────────
const auth = useAuthStore()
const refsOpen = ref(false)
const refsTarget = ref<AuthSession | null>(null)
const refsLoading = ref(false)
const refsData = ref<AuthReferences | null>(null)

/** 删除拦截预告(与后端 DELETE 409 同口径):可见引用里
 *  「本人场景 × template」的条数(M2a S6 后 scheme 种类已退役)—
 *  抽屉底部淡红警示。 */
const drawerBlocking = computed(() => {
  const me = auth.currentUser?.id
  if (!refsData.value || me == null) return []
  return refsData.value.scenario_refs.visible.filter(
    (v) => v.owner_id === me && v.kinds.includes('template'),
  )
})

function openRefs(row: AuthSession) {
  refsTarget.value = row
  refsData.value = null
  refsOpen.value = true
  void loadRefs()
}

async function loadRefs() {
  if (!refsTarget.value) return
  refsLoading.value = true
  try {
    refsData.value = await getReferences(refsTarget.value.alias)
  } catch (e) {
    showError('反查', undefined, (e as Error).message)
    refsData.value = null
  } finally {
    refsLoading.value = false
  }
}

const KIND_LABELS: Record<string, string> = {
  template: '模板', snapshot: '快照',
}
const KIND_TITLES: Record<string, string> = {
  template: 'steps 里的 ${auth.<alias>.*} 模板 — 下次运行会用到',
  snapshot: 'config.users 的同名快照副本 — 自足,不随凭证池轮换',
}

function kindLabel(k: string): string {
  return KIND_LABELS[k] ?? k
}

function kindTitle(k: string): string {
  return KIND_TITLES[k] ?? k
}

const deleteConfirmed = computed(() =>
  Boolean(deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.alias),
)

function openDelete(row: AuthSession) {
  deleteTarget.value = row
  deleteConfirmInput.value = ''
  deleteOpen.value = true
}

async function submitDelete() {
  if (!deleteTarget.value || !deleteConfirmed.value) return
  deleteSubmitting.value = true
  try {
    await store.deleteAuth(deleteTarget.value.id)
    toast.success(`已删除 ${deleteTarget.value.alias}`)
    deleteOpen.value = false
    void reloadList()
  } catch (e) {
    // 409 = 本人场景的模板/方案引用拦截(配套方案 §1.5 窄口径):
    // 错误信息带场景清单 — 保持弹框开着让用户看完再处理
    showError('删除', undefined, (e as Error).message)
  } finally {
    deleteSubmitting.value = false
  }
}

// ── init ───────────────────────────────────────────────────────
onMounted(async () => {
  loadTestMemory()
  // 槽位声明反查(服务注册身份面注册表,读面全员;失败静默不亮 chip)
  listAllAliases()
    .then((rows) => {
      declaredSlots.value = new Set(
        rows.map((a) => a.slot).filter((s): s is string => Boolean(s)))
      slotsReady.value = true
    })
    .catch(() => { /* 注册表拉不到 — ✕ 未声明 chip 不亮 */ })
  // S7.5:导入结果「去绑定」→ 直接开新建表单并预填槽位;分层③:执行配置
  // 枢纽的缺失深链补 system/envId 预填(?newSlot=&system=&envId=)
  const q = route?.query ?? {}
  const newSlot = typeof q.newSlot === 'string' ? q.newSlot : ''
  const qSystem = typeof q.system === 'string' ? q.system : ''
  const qEnv = typeof q.envId === 'string' ? q.envId : ''
  if (newSlot || qSystem || qEnv) openCreate(newSlot, qSystem, qEnv)
  // 环境选项给表单下拉
  listEnvironments()
    .then((rows) => { envs.value = rows.map((e) => ({ id: e.id, name: e.name })) })
    .catch(() => { /* 表单环境下拉退化为「不限」单项 */ })
  try {
    await reloadList()
  } catch {
    // useServerList 默认 onError 已弹全局提示;这里静默即可。
  }
})
</script>

<style scoped>
/* 高级区折叠开关(渐进披露):贴表单节奏的弱化文字钮 */
.adv-toggle {
  align-self: flex-start;
  padding: 0;
  border: 0;
  background: none;
  font-size: 11.5px;
  color: var(--sl-ink-3, #5b6472);
  cursor: pointer;
}
.adv-toggle:hover { color: var(--sl-ink, #10151c); }

/* ── 槽位卡片看板(借 .svc-tile 语言:白卡 + 状态色 3px 顶边)────── */
.auth-board {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  align-items: start;
}
.slot-card {
  background: #fff;
  border: 1px solid var(--sl-line, #e1e5eb);
  border-top: 3px solid var(--sl-divider, #c3c9d4);
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(16, 21, 28, 0.06);
  padding: 10px 13px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.slot-card.tone-ok { border-top-color: var(--sl-ok, #22a55e); }
.slot-card.tone-warn { border-top-color: var(--sl-warn, #e0a03c); }
.slot-card.tone-bad { border-top-color: var(--sl-bad, #d9534f); }
.sc-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.sc-slot { font-size: 12.5px; color: var(--sl-ink, #10151c); }
.sc-slot b { font-size: 13px; }
.sc-n { font-size: 11px; }
.sc-binds {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sc-bind {
  border: 1px solid var(--sl-divider, #e8ebf0);
  border-radius: 8px;
  padding: 7px 9px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--sl-canvas, #fbfcfe);
}
.bind-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}
.bind-line.sub { justify-content: space-between; }
.bind-line.sub .mono {
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bind-line.acts { justify-content: space-between; }
.sc-more {
  align-self: flex-start;
  padding: 2px 0;
  border: 0;
  background: none;
  font-size: 11.5px;
  color: var(--sl-accent, #2f6fed);
  cursor: pointer;
}
.sc-more:hover { text-decoration: underline; }

/* ── 反查侧板 ─────────────────────────────────────────────── */
.drawer-warn {
  margin-top: 14px;
  padding: 8px 10px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--sl-bad);
  background: var(--sl-bad-soft);
  border: 1px solid var(--sv-bad-line);
  border-radius: 8px;
}

.ref-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  flex-wrap: wrap;
}

.ref-dim { font-size: 11px; color: var(--sl-ink-3); }

.link { color: var(--sl-accent); }
.link:hover { text-decoration: underline; }

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}

/* ── 测试弹框:状态主视觉式(开框即认证中 → 成功/失败终态)──── */
.test-hero { text-align: center; }

.test-sub {
  margin-bottom: 18px;
  overflow: hidden;
  font-size: 12px;
  color: var(--sl-ink-2);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-state {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  margin: 6px 0 14px;
}

.test-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  font-size: 20px;
  font-weight: 700;
  border-radius: 50%;
}

.testing .test-icon {
  border: 3px solid var(--sl-line);
  border-top-color: var(--sl-accent);
  animation: test-spin 0.9s linear infinite;
}

.success .test-icon { color: var(--sl-ok); background: var(--sl-ok-soft); }
.fail .test-icon { color: var(--sl-bad); background: var(--sl-bad-soft); }

.test-word { font-size: 16px; font-weight: 600; }
.testing .test-word { color: var(--sl-ink-2); }
.success .test-word { color: var(--sl-ok); }
.fail .test-word { color: var(--sl-bad); }

.test-code {
  padding: 2px 8px;
  font-size: 11px;
  color: var(--sl-ink-2);
  background: var(--sl-canvas);
  border-radius: 4px;
}

.detail {
  display: block;
  padding: 8px 10px;
  color: var(--sl-ink);
  background: var(--sl-canvas);
  border-radius: 4px;
  word-break: break-all;
}

.detail-toggle {
  background: none;
  border: none;
  color: var(--sl-ink-2);
  cursor: pointer;
  font-size: 12px;
}

@keyframes test-spin { to { transform: rotate(360deg); } }
</style>
