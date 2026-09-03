<!--
  CaseComposerCanvas.vue — ④ 步骤编辑 (现代化设计)
  3 栏布局 + 嵌入式接口目录 (子流程)
-->
<template>
  <div class="canvas-shell">
    <!-- 子流程:覆盖右两栏 -->
    <CaseComposerCatalog
      v-if="subView === 'catalog'"
      :next-step-idx="local.length + 1"
      :adding="adding"
      @add="onAddEndpoint"
      @back="subView = null"
    />

    <!-- 主页:3 栏 -->
    <div v-else class="three-col">
      <!-- ① 步骤流 -->
      <aside class="col col-steps">
        <div class="col-head">
          <div>
            <h3>步骤流</h3>
            <p class="muted">{{ local.length }} 个 step · 按顺序执行</p>
          </div>
          <button class="add-step" @click="subView = 'catalog'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            添加接口
          </button>
        </div>
        <div class="step-list">
          <!-- vuedraggable 上下拖拽重排(#5):纵向手柄拖,不做 DAG。
               item-key 用 WeakMap 侧挂的稳定 key(step 数据本体不能加字段 —
               草稿原样进 /convert);local 已被 draggable 重排,onStepReordered
               同步 orch.steps 并让选中项跟随 -->
          <draggable
            :list="local"
            :item-key="stepKey"
            handle=".step-handle"
            :animation="150"
            tag="div"
            class="step-drag-area"
            @end="onStepReordered"
          >
            <template #item="{ element: s, index: i }">
              <div class="step-row"
                   :class="{ active: i === activeStepIdx, disabled: !orch.steps[i]?.enabled }"
                   @click="activeStepIdx = i">
                <span class="step-handle" title="拖拽调整顺序">⠿</span>
                <div class="step-idx">{{ i + 1 }}</div>
                <div class="step-info">
                  <div class="step-name">{{ orch.steps[i]?.name || s.api?.path || 'step' }}</div>
                  <div class="step-meta">
                    <span v-if="s.api?.method" class="method-badge" :class="`m-${s.api.method.toLowerCase()}`">{{ s.api.method }}</span>
                    <span v-if="s.api?.service" class="svc-tag">{{ s.api.service }}</span>
                    <span v-if="s.api?.path" class="ep-path">{{ s.api.path }}</span>
                    <!-- carry 只读提示:字段面∩值表非空才出现;悬停列键来源(服务绑定/全局默认) -->
                    <el-tooltip
                      v-if="carryInjectable(s).size"
                      placement="top"
                    >
                      <template #content>
                        <div v-for="[p, src] of carryInjectable(s)" :key="p">
                          {{ p }} ← {{ src }}
                        </div>
                      </template>
                      <span class="carry-badge">carry {{ carryInjectable(s).size }}</span>
                    </el-tooltip>
                  </div>
                </div>
                <el-switch v-if="orch.steps[i]" v-model="orch.steps[i].enabled" size="small" @click.stop />
                <button class="step-del" @click.stop="removeStep(i)" title="删除">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
                </button>
              </div>
            </template>
          </draggable>
          <div v-if="!local.length" class="step-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
            </svg>
            <p>还没有 step</p>
            <button class="empty-cta" @click="subView = 'catalog'">+ 从接口目录选</button>
          </div>
        </div>
      </aside>

      <!-- ② 字段编辑器 -->
      <main class="col col-fields">
        <div v-if="currentStep" class="fields-shell">
          <div class="fields-head">
            <div class="fields-head-row">
              <div class="fields-title">
                <span class="title-num">{{ activeStepIdx + 1 }}</span>
                <input
                  class="title-input"
                  :value="currentOrch?.name ?? ''"
                  @input="(e: any) => { if (currentOrch) currentOrch.name = e.target.value }"
                  placeholder="step 名称"
                />
              </div>
              <span class="step-kind">{{ inferProtocol(currentStep) }}</span>
            </div>
            <!-- 接口事实只读缩略: method/service/path 来自接口目录 (plate), 是选定接口的属性,
                 不是用例配置项。要换接口 → 删 step 从目录重选。 -->
            <div class="api-summary">
              <span v-if="currentStep.api?.method" class="method-badge" :class="`m-${currentStep.api.method.toLowerCase()}`">{{ currentStep.api.method }}</span>
              <span v-if="currentStep.api?.service" class="svc-tag">{{ currentStep.api.service }}</span>
              <span v-if="currentStep.api?.path" class="ep-path">{{ currentStep.api.path }}</span>
            </div>

            <!-- 运行引用(别名消费点,spec §1.4 双显):目录事实只读,引用可切 -->
            <div class="svc-ref">
              <span class="svc-ref-label">服务引用</span>
              <select
                class="svc-ref-select"
                :value="currentStep.api?.service"
                @change="onServiceRefChange(currentStep, ($event.target as HTMLSelectElement).value)"
              >
                <option
                  v-if="currentStep.api?.service && !serviceOptions.some(o => o.value === currentStep.api?.service)"
                  :value="currentStep.api.service"
                >{{ currentStep.api.service }}(未挂目录)</option>
                <option v-for="o in serviceOptions" :key="o.value" :value="o.value" :class="{ dim: o.dim }">{{ o.label }}</option>
                <option value="__create__">+ 为此服务新建别名…</option>
              </select>
              <span v-if="refWarning" class="svc-ref-warn" :class="refWarning.level">{{ refWarning.text }}</span>
              <div v-if="creatingAlias" class="alias-create">
                <span class="alias-prefix">{{ serviceAnchor }}-</span>
                <input v-model="aliasSuffix" placeholder="后缀(不含 -)" class="alias-suffix" />
                <input v-model="aliasUrl" placeholder="baseUrl(如 https://qa2.fin.local)" class="alias-url" />
                <button type="button" class="ghost-btn alias-create-confirm" @click="confirmAliasCreate(currentStep)">创建并切换</button>
                <button type="button" class="ghost-btn" @click="creatingAlias = false">取消</button>
              </div>
              <div class="svc-ref-url">URL: {{ declaredUrlOf(currentStep.api?.service || '') || '(未声明 — 运行前需补 URL)' }}</div>
            </div>
          </div>
          <el-form label-position="top" size="small" class="c-form">
            <!-- description 事实源是 plate /full(选定接口的契约描述,拉到即显);
                 step.description 是加入时落草稿的快照(老草稿可能存的是 name 兜底)——
                 展示链 plate 优先,老草稿显示侧自愈 — 只读展示 -->
            <el-form-item label="description">
              <p class="desc-readonly">{{ currentFull?.description || currentStep.description || '—' }}</p>
            </el-form-item>

            <!-- IO 重叠页签(Chrome 造型):选中签与下方 io-card 面板连体;
                 内容按 activeIoTab 切,值在 request.body / strategy 数组,
                 切换只切视图不切数据 -->
            <div class="io-tabs" role="tablist">
              <button
                type="button"
                :class="['io-tab', 'req', { active: activeIoTab === 'request' }]"
                role="tab"
                :aria-selected="activeIoTab === 'request'"
                @click="activeIoTab = 'request'"
              >
                Request
                <span v-if="fieldBindings(currentStep).length" class="count">{{ fieldBindings(currentStep).length }}</span>
              </button>
              <button
                type="button"
                :class="['io-tab', 'res', { active: activeIoTab === 'response' }]"
                role="tab"
                :aria-selected="activeIoTab === 'response'"
                @click="activeIoTab = 'response'"
              >
                Response
                <span v-if="currentRespSpecs.length" class="count">{{ currentRespSpecs.length }}</span>
              </button>
            </div>
            <div class="io-card">
            <!-- headers: KV 行编辑。value 支持 ${auth.<alias>.<field>} 模板 —
                 点 ⓘ 从认证列表选(草稿只存引用,token 明文永不进前端),
                 引用徽章提示悬空(alias 不在 /api/auths) -->
            <el-form-item v-if="activeIoTab === 'request'" label="headers (点 ⓘ 注入 ${auth.<alias>.<field>})">
              <div class="hdr-rows">
                <div v-for="(value, key) in currentStep.api.headers" :key="String(key)" class="hdr-row">
                  <!-- key: 常用预设下拉 + allow-create 手输(规范大小写由预设带出) -->
                  <el-select
                    :model-value="String(key)"
                    size="small"
                    filterable allow-create default-first-option
                    placeholder="选择或输入 header"
                    class="hdr-key"
                    @update:model-value="(v: string) => updateHeaderKey(currentStep, String(key), v)"
                  >
                    <el-option v-for="k in COMMON_HEADER_KEYS" :key="k" :value="k" :label="k" />
                  </el-select>
                  <el-input
                    :model-value="String(value)"
                    size="small"
                    placeholder="value (如 ${auth.qa1.token})"
                    class="hdr-val"
                    @update:model-value="(v: string) => updateHeaderValue(currentStep, String(key), v)"
                  />
                  <button type="button" class="c-kv-del hdr-pick" title="选择认证" @click="openAuthPicker(String(key), String(value))">ⓘ</button>
                  <button type="button" class="c-kv-del hdr-pick hdr-var" title="选择变量" @click="openVarPicker(String(key), String(value))">Ⓥ</button>
                  <button type="button" class="c-kv-del" title="删除" @click="removeHeader(currentStep, String(key))">×</button>
                  <div v-for="r in hdrRefs(String(value))" :key="r.raw" class="ref-chip" :class="hdrRefStatus(r)">
                    <span class="ref-chip-dot" />{{ r.raw }}
                    <span v-if="hdrRefStatus(r) === 'dangling'" class="ref-chip-note">
                      {{ r.domain === 'var' ? `变量 ${r.alias} 未注册` : `认证 ${r.alias} 不存在` }}
                    </span>
                  </div>
                </div>
                <button type="button" class="c-add" @click="addHeader(currentStep)">+ 新增 header</button>
              </div>
            </el-form-item>
            <!-- body: 由 plate /full 的 IOFieldBinding 实时驱动表单(会话级现拉,非持久快照) -->
            <el-form-item v-if="activeIoTab === 'request' && fieldBindings(currentStep).length" label="请求体 (由 IOFieldBinding 驱动)">
              <div class="field-form-wrap">
                <FieldForm
                  :bindings="fieldBindings(currentStep)"
                  :body="currentStep.request.body || {}"
                  :field-actions="true"
                  :var-choices="referenceVarChoices"
                  :inject-choices="injectVarChoices"
                  :unbound-fields="reqTypeC"
                  :strategy-tags="requestStrategyTags"
                  :injected="requestInjected"
                  :carry-roots="carryRoots"
                  @strategy-jump="onStrategyJump"
                  @update:body="(v: unknown) => currentStep.request.body = v"
                  @field-extract="onFieldExtract"
                  @field-assign="(f, name) => onFieldAssign(f, name)"
                  @field-assert="onFieldAssert"
                  @var-insert="onVarInsert"
                  @var-promote="onVarPromote"
                />
                <p class="field-form-hint">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                  来自 plate <code>/api/endpoint/.../full</code> 的 IOFieldBinding
                  · {{ fieldBindings(currentStep).length }} 个字段, plate 是结构权威源
                </p>
              </div>
            </el-form-item>
            <el-form-item v-else-if="activeIoTab === 'request' && fullState === 'loading' && hasEndpointRef(currentStep)" label="请求体">
              <p class="resp-spec-empty">正在从 plate 拉取接口字段契约…</p>
            </el-form-item>
            <el-form-item v-else-if="activeIoTab === 'request'" label="body (JSON)">
              <el-input
                :model-value="JSON.stringify(currentStep.request.body || {}, null, 2)"
                @update:model-value="(v: string) => currentStep.request.body = parseJson(v, {})"
                type="textarea"
                :rows="5"
                class="code-input"
              />
              <span v-if="fullState === 'failed' && hasEndpointRef(currentStep)" class="hint">plate 不可达,字段表单暂不可用 — 已降级为 JSON 编辑</span>
              <span v-else class="hint">提示: 该接口未声明请求字段契约,或 plate 拉取中</span>
            </el-form-item>
            <!-- 请求侧 Type C(schema 有、binding 无)已并入 FieldForm「其他字段」
                 折叠区(unbound-fields) — 可见可编辑,不再单独设只读块。 -->
            <!-- Response 页:/full responses 全状态码契约,只读参考(设计 §3.1)。
                 ☰ 菜单仅 提取/断言 两项,路径经 respPathFor → toScratchPath -->
            <template v-if="activeIoTab === 'response'">
              <div v-if="currentRespSpecs.length" class="resp-specs">
                <div v-for="spec in currentRespSpecs" :key="spec.status" class="resp-spec">
                  <div class="resp-spec-head">
                    <span class="resp-status-badge" :class="spec.status < 400 ? 'ok' : 'err'">{{ spec.status }}</span>
                    <span class="resp-spec-desc">{{ spec.description || '—' }}</span>
                  </div>
                  <FieldForm
                    v-if="spec.fields.length"
                    :bindings="spec.fields"
                    :body="null"
                    :readonly="true"
                    :domain="'response'"
                    :field-actions="true"
                    :assertable="spec.assertable"
                    :strategy-tags="responseStrategyTags"
                    @strategy-jump="onStrategyJump"
                    @field-extract="onFieldExtract"
                    @field-assert="onFieldAssert"
                  />
                  <p v-else class="resp-spec-empty">该状态码未声明字段契约</p>
                </div>
              </div>
              <p v-else class="resp-spec-empty">该接口未声明响应契约(或拉取中)</p>
              <!-- Type C 查看入口(响应侧,200 契约 schema 差集) -->
              <details v-if="respTypeC.length" class="typec-block">
                <summary>Schema 未绑定字段 ({{ respTypeC.length }})</summary>
                <div v-for="tf in respTypeC" :key="tf.name" class="typec-line">
                  <code>{{ tf.name }}</code>
                  <span class="resp-field-kind">{{ tf.type }}</span>
                  <span class="typec-path">{{ tf.path }}</span>
                </div>
              </details>
            </template>
            </div><!-- /io-card -->

            <!-- 策略区: plate 策略语法 dim 驱动;request/response 共用同一列表
                 (执行序即数组序,不按签页过滤 — 添加即见);失败降级 extract 专用 UI -->
            <el-form-item v-if="strategyKinds.length" label="策略 (request · response 共用)">
              <div class="strategy-area">
                <!-- B1 响应样本:端点无 assertable 时路径只能猜(数组丢 [0] 段)
                     → 粘真实样本解析候选,数组下标天然正确 -->
                <div class="sample-bar">
                  <button type="button" class="sample-toggle" @click="sampleOpen = !sampleOpen">
                    {{ sampleOpen ? '▾' : '▸' }} 响应样本(选填 — 解析路径候选)
                  </button>
                  <div v-if="sampleOpen" class="sample-body">
                    <textarea
                      v-model="sampleText"
                      class="sample-input"
                      rows="4"
                      placeholder='粘贴该步骤的真实响应 JSON,如 {"code":0,"data":{"data":[{"order_id":"BL1"}]}}'
                    />
                    <div class="sample-actions">
                      <button type="button" class="sample-parse" @click="onParseSample">解析路径</button>
                      <span v-if="sampleError" class="sample-error">{{ sampleError }}</span>
                      <span v-else-if="samplePaths.length" class="sample-ok">
                        已解析 {{ samplePaths.length }} 条候选 → 策略路径字段的 ▾ 可选
                      </span>
                    </div>
                  </div>
                </div>
                <StrategyForm
                  v-for="(s, idx) in currentStep.strategy"
                  :key="`${activeStepIdx}-${idx}`"
                  :id="`strategy-card-${idx}`"
                  :strategy="s"
                  :detail="strategyDetail(s)"
                  :start-expanded="idx === justAddedStrategyIdx"
                  :candidates="strategyCandidates(s)"
                  :tag-label="currentTagLabels[idx]"
                  :expand-when="jumpSeq > 0 && idx === jumpTargetIdx"
                  @remove="removeStrategy(currentStep, s)"
                />
                <el-dropdown trigger="click" @command="addStrategy(currentStep, $event as string)">
                  <!-- type="button": el-form 渲染原生 form,无 type 的按钮是 submit,
                       点击会触发整页表单提交丢掉 ?step= query -->
                  <button type="button" class="c-add add-strategy">
                    + 添加策略 ▾
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        v-for="k in strategyKinds"
                        :key="k.kind"
                        :command="k.kind"
                      >
                        {{ k.label }}<span class="strat-kind-tag">{{ k.kind }}</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </el-form-item>
            <el-form-item v-else label="extract (从响应提取变量 → strategy)">
              <div v-for="(ex, j) in extractStrategies(currentStep)" :key="j" class="extract-row c-kv-row">
                <el-input
                  :model-value="ex.target"
                  @update:model-value="(v: string) => ex.target = v"
                  placeholder="变量名 (target)"
                  size="small"
                />
                <span class="c-kv-sep">←</span>
                <el-input
                  :model-value="ex.expression"
                  @update:model-value="(v: string) => ex.expression = v"
                  placeholder="$.data.orderId"
                  size="small"
                  class="ex-path"
                />
                <button type="button" class="c-kv-del" @click="removeExtract(currentStep, ex)">×</button>
              </div>
              <button type="button" class="c-add add-extract" @click="addExtract(currentStep)">
                + 添加 extract
              </button>
            </el-form-item>
          </el-form>
        </div>
        <div v-else class="fields-empty">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <polyline points="14 2 14 8 20 8"/><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          </svg>
          <p>选一个 step 编辑</p>
          <p class="muted">或在左侧添加新 step</p>
        </div>
      </main>

      <!-- ③ 信息面板(拆分为独立卡堆: step 信息 / 变量注册表 / 常量池,
           间隔 12px 对齐 .three-col 功能块节奏) -->
      <aside class="col-info col-stack">
        <div class="col info-card">
          <div class="col-head">
            <h3>step 信息</h3>
          </div>
          <div v-if="currentStep" class="info-body">
            <div class="info-block">
              <div class="info-k">HTTP</div>
              <div class="info-v">
                <span v-if="currentStep.api?.method" class="method-badge" :class="`m-${currentStep.api.method.toLowerCase()}`">{{ currentStep.api.method }}</span>
                <code>{{ currentStep.api?.path || '—' }}</code>
              </div>
            </div>
            <div class="info-block">
              <div class="info-k">service</div>
              <div class="info-v"><code>{{ currentStep.api?.service || '—' }}</code></div>
            </div>
            <div class="info-block">
              <div class="info-k">kind</div>
              <div class="info-v"><span class="badge">{{ inferProtocol(currentStep) }}</span></div>
            </div>
            <div class="info-block">
              <div class="info-k">enabled</div>
              <div class="info-v">
                <span :class="['status-pill', currentOrch?.enabled ? 'on' : 'off']">
                  {{ currentOrch?.enabled ? '✓ 启用' : '✗ 禁用' }}
                </span>
              </div>
            </div>
            <!-- 右栏按签页分流(设计 §3.4):Request 页请求侧统计;
                 Response 页响应契约(全状态码,含 ✓ 标)。
                 需求1:extracts 信息块已删 — 策略信息迁到字段行角标 -->
            <template v-if="activeIoTab === 'request'">
              <div class="info-block">
                <div class="info-k">请求侧</div>
                <div class="info-v">
                  <span class="badge">{{ fieldBindings(currentStep).length }} 字段</span>
                  <span class="badge">{{ Object.keys(currentStep.api?.headers || {}).length }} headers</span>
                </div>
              </div>
            </template>
            <template v-else>
              <!-- 响应契约:全状态码(升级自旧"响应字段 (200)"块) -->
              <div v-if="currentRespSpecs.length" class="info-block">
                <div class="info-k">响应契约 (全状态码)</div>
                <div class="info-v">
                  <div v-for="spec in currentRespSpecs" :key="spec.status" class="resp-contract-group">
                    <span class="resp-status-badge" :class="spec.status < 400 ? 'ok' : 'err'">{{ spec.status }}</span>
                    <div class="resp-contract-fields">
                      <div v-for="rf in spec.fields" :key="rf.name" class="resp-field-line">
                        <code>{{ rf.name }}</code>
                        <span v-if="spec.assertable.includes(rf.path)" class="assertable-mark" title="可断言字段">✓</span>
                        <span class="resp-field-kind">{{ rf.ui_kind }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
          <div v-else class="info-empty muted">无选中 step</div>
        </div>

        <!-- 变量注册表(#1 变量工作台):从 ③ 配置步迁入 — 变量的生产与
             消费都发生在本页,就近总览;草稿级数据,无选中 step 也常驻 -->
        <VariableRegistryPanel
          :steps="local"
          :config-vars="draftStore.draft?.definition?.config?.vars"
        />

        <!-- 常量池(编排页常驻;必须保持 aside 最后一个子元素,F12) -->
        <ConstantPoolPanel
          :entries="constantsStore.entries"
          @seed-var="(n: string, s: Record<string, unknown>) => emit('seedVar', n, s)"
        />
      </aside>
    </div>

    <!-- 认证选择器(headers value 注入 ${auth.<alias>.<field>}) -->
    <AuthSelectorModal
      v-if="authPickerOpen"
      v-model="authPickerOpen"
      :auths="auths"
      @select="onAuthPicked"
    />
    <!-- 变量选择器(headers value 注入 ${var.<name>},#3) -->
    <VarSelectorModal
      v-if="varPickerOpen"
      v-model="varPickerOpen"
      :entries="varRegistryEntries"
      @select="onVarPicked"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import draggable from 'vuedraggable'
import CaseComposerCatalog from './CaseComposerCatalog.vue'
import FieldForm from './FieldForm.vue'
import StrategyForm from './StrategyForm.vue'
import VariableRegistryPanel from './VariableRegistryPanel.vue'
import ConstantPoolPanel from './ConstantPoolPanel.vue'
import AuthSelectorModal from '../AuthSelectorModal.vue'
import VarSelectorModal from './VarSelectorModal.vue'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { useConstantsStore } from '@/stores/constants'
import { deriveVarRegistry } from '@/utils/var-registry'
import { getFullEndpoint, listStrategyKinds, getStrategyKindFull, resolveResponsePaths } from '@/api/scenario-composer'
import { list as listAuths } from '@/api/auth_sessions'
import { getBindings as getCarryBindings, getDefaults as getCarryDefaults } from '@/api/carry'
import { parseTplRefs, refStatus } from '@/utils/tpl-refs'
import type { TplRef } from '@/utils/tpl-refs'
import type { AuthSession } from '@/api/auth_sessions'
import { deepDefaults } from '@/utils/jsonpath'
import { toScratchPath } from '@/utils/scratch-path'
import { assertablePaths, carryPaths, channelFields, deriveDeepRows } from '@/utils/declarations'
import { deriveBase } from '@/utils/service-alias'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import { carryHint } from '@/utils/carry-hint'
import type { CarrySource, CarryValues } from '@/utils/carry-hint'
import type {
  StepView, ExtractView, IOFieldBinding, EndpointFullView,
  StrategyView, StrategyKindView, StrategyKindDetailView,
} from '@/types/plate'
import type { Orchestration, StepOrchestration } from '@/types/scenario-composer'
import { parseJson } from '../../utils/json'

const props = defineProps<{
  steps: StepView[]
  orchestration: Orchestration
  /** 场景服务声明 dict(config.services)—— 别名下拉/双写消费(spec §1.4) */
  services?: Record<string, string>
}>()
const emit = defineEmits<{
  'update:steps': [StepView[]]
  'update:orchestration': [Orchestration]
  /** 内联创建别名双写的声明面(config.services 整表替换) */
  'update:services': [Record<string, string>]
  'varPromote': [name: string, value: unknown]
  'seedVar': [name: string, spec: Record<string, unknown>],
}>()

const local = reactive<StepView[]>([...(props.steps || [])])
const orch = reactive<Orchestration>(
  props.orchestration || { steps: [], resourceMeta: {} }
)
const activeStepIdx = ref(0)
const subView = ref<null | 'catalog'>(null)
const adding = ref(false)
/**
 * IO 双签卡片当前签页(request=请求体编辑 / response=响应契约参考)。
 * 切 step 重置回 request(设计 §3.1);值都在 request.body/strategy 数组,
 * 切换只切视图不切数据。
 */
const activeIoTab = ref<'request' | 'response'>('request')

const currentStep = computed(() => local[activeStepIdx.value])
const currentOrch = computed<StepOrchestration | undefined>(() => orch.steps[activeStepIdx.value])

/** plate Step 无顶层协议 kind;从 api 形状推断展示标签 (http/...) */
function inferProtocol(step: StepView | undefined): string {
  if (step?.api && step.api.method) return 'http'
  return 'step'
}

/** FieldForm 需要的 IOFieldBinding[] — 会话级按 endpoint_id 现拉 /full,
 *  不读持久化快照(旧 step.request.fields_meta 已废弃,不再作为数据源)。
 *  读 fullVersion 建立响应依赖:回填后模板/reqTypeC 自动重算。
 *  declarations 归一化后:请求表单面 = binding 通道投影。 */
function fieldBindings(step: StepView | undefined): IOFieldBinding[] {
  void fullVersion.value
  const eid = step?.api?.view_hints?.endpoint_id
  if (!eid) return []
  void ensureEndpointFull(eid)
  return channelFields(endpointFullByEndpoint.get(eid)?.request?.declarations, 'binding')
}

/** step 是否携带接口身份引用(决定 loading/failed 占位是否适用) */
function hasEndpointRef(step: StepView | undefined): boolean {
  return !!step?.api?.view_hints?.endpoint_id
}

/** strategy 里提取 extract 变体 */
function extractStrategies(step: StepView | undefined): ExtractView[] {
  if (!step?.strategy) return []
  return step.strategy.filter((s): s is ExtractView => s.kind === 'extract')
}
function addExtract(step: StepView) {
  step.strategy.push({
    kind: 'extract', expression: '', target: '',
    // scope=step 只写本 step scratch(step 结束清),跨步消费必死;
    // 手动入口默认 scenario promote(#8)
    scope: 'scenario', required: true,
  })
}
function removeExtract(step: StepView, ex: ExtractView) {
  const idx = step.strategy.indexOf(ex)
  if (idx >= 0) step.strategy.splice(idx, 1)
}

// ── 策略区(plate 语法 dim 驱动) ─────────────────────────────────
// kinds 加载失败 → strategyKinds 留空 → 模板降级到上方 extract 专用 UI。

const strategyKinds = ref<StrategyKindView[]>([])
/** detail 按 kind 懒加载 + 会话级缓存(语法全局不变)。ref 包对象 → 命中后模板自动重渲染 */
const strategyDetailCache = ref<Record<string, StrategyKindDetailView>>({})
/** 刚通过"添加策略"下拉新建的实例下标(渲染为展开引导填写);-1 = 无 */
const justAddedStrategyIdx = ref(-1)
// 切 step 时清"刚添加"标记(下标在新 step 语境无意义,防误展开);签页回 request
watch(activeStepIdx, () => { justAddedStrategyIdx.value = -1; jumpTargetIdx.value = -1; activeIoTab.value = 'request' })

async function loadStrategyKinds() {
  try {
    strategyKinds.value = await listStrategyKinds()
  } catch {
    // 降级:模板 v-if 落到 extract 专用 UI,不阻塞编排
  }
}
async function ensureStrategyDetail(kind: string): Promise<StrategyKindDetailView | undefined> {
  if (strategyDetailCache.value[kind]) return strategyDetailCache.value[kind]
  try {
    const d = await getStrategyKindFull(kind)
    strategyDetailCache.value = { ...strategyDetailCache.value, [kind]: d }
    return d
  } catch {
    return undefined
  }
}
/** 渲染期同步取 detail(缓存未命中返回 placeholder 并触发懒加载,完成后响应式刷新) */
function strategyDetail(s: StrategyView): StrategyKindDetailView {
  const hit = strategyDetailCache.value[s.kind]
  if (hit) return hit
  void ensureStrategyDetail(s.kind)
  return { kind: s.kind, label: s.kind, phase: 'verifying', fields: [], base_fields: [] }
}

async function addStrategy(step: StepView, kind: string) {
  const d = await ensureStrategyDetail(kind)
  if (!d) {
    ElMessage.error(`拉取策略 ${kind} 结构失败, 请重试`)
    return
  }
  // 骨架 = {kind 判别字段 + 按 detail.fields 的 default 展开}
  const inst: Record<string, unknown> = { kind }
  for (const f of d.fields) {
    if (f.default !== null && f.default !== undefined) inst[f.name] = f.default
  }
  step.strategy.push(inst as unknown as StrategyView)
  // 新实例引导填写 → 展开(仅最新的;预填/加载的保持折叠降噪)
  justAddedStrategyIdx.value = step.strategy.length - 1
}

function removeStrategy(step: StepView, s: StrategyView) {
  const idx = step.strategy.indexOf(s)
  if (idx >= 0) step.strategy.splice(idx, 1)
}

// ── headers KV 行 + 认证引用(模式照搬 EditableStepCard 成熟实现) ────
// headers 本就是 Record<string, string>;KV 行只是编辑形态,草稿/导出形状不变。

/** key 预设:标准头 + 内网网关/链路追踪高频头。下拉即选(规范大小写),
 *  自定义 key 走 el-select filterable+allow-create 手输,不锁死清单。 */
const COMMON_HEADER_KEYS = [
  'Authorization', 'Content-Type', 'Accept', 'Accept-Encoding', 'Accept-Language',
  'User-Agent', 'Cache-Control', 'Connection', 'Host', 'Origin', 'Referer', 'Cookie',
  'X-Request-ID', 'traceparent', 'X-Forwarded-For', 'X-Real-IP', 'X-API-Key', 'X-Trace-Id',
]

const auths = ref<AuthSession[]>([])
const authPickerOpen = ref(false)
const authPickerKey = ref<string | null>(null)
const authPickerVal = ref<string | null>(null)
const authPickerStep = ref<StepView | null>(null)

function addHeader(step: StepView) {
  const h = (step.api.headers ||= {})
  let k = 'X-Header'
  while (k in h) k += '1'
  h[k] = ''
}
function removeHeader(step: StepView, key: string) {
  delete step.api.headers?.[key]
}
function updateHeaderKey(step: StepView, oldKey: string, newKey: string) {
  if (oldKey === newKey || !step.api.headers) return
  const v = step.api.headers[oldKey]
  delete step.api.headers[oldKey]
  step.api.headers[newKey] = v ?? ''
}
function updateHeaderValue(step: StepView, key: string, value: string) {
  if (step.api.headers) step.api.headers[key] = value
}

/**
 * 打开选择器时记 key + 当时 value。key 在弹窗期间可能被改名
 * (rename 是 delete+set,弹窗里拿不到新 key),所以落注入时:
 * key 仍在 → 注入该 key;key 没了 → 找 value 等于当时 value 的唯一行。
 */
function openAuthPicker(key: string, value: string) {
  authPickerStep.value = currentStep.value ?? null
  if (!authPickerStep.value) return
  authPickerKey.value = key
  authPickerVal.value = value
  authPickerOpen.value = true
}
/** 头部注入共用:按 key(或唯一 value 定位)写入模板串。 */
function injectHeaderTpl(
  headers: Record<string, string> | undefined,
  key: string | null,
  val: string | null,
  tpl: string,
): void {
  if (!headers) return
  if (key && key in headers) {
    headers[key] = tpl
  } else {
    // key 被改:按当时 value 定位(唯一匹配才注入,防误写)
    const hits = Object.entries(headers).filter(([, v]) => v === val)
    if (hits.length === 1) headers[hits[0][0]] = tpl
  }
}

function onAuthPicked(tpl: string) {
  injectHeaderTpl(authPickerStep.value?.api?.headers, authPickerKey.value, authPickerVal.value, tpl)
  authPickerKey.value = null
  authPickerVal.value = null
  authPickerStep.value = null
}

/** header value 的引用徽章数据(auth + var 两域;var 为 #3 增) */
function hdrRefs(value: string): TplRef[] {
  return parseTplRefs(value).filter((r) => r.domain === 'auth' || r.domain === 'var')
}

/** 徽章悬空判定:auth 对 /api/auths 列表,var 对注册表(数据集列运行期
 *  注入,不在编辑期注册表 — 悬空提示核对拼写,不硬阻断) */
function hdrRefStatus(ref: TplRef): 'ok' | 'dangling' {
  if (ref.domain === 'var') {
    return varRegistryEntries.value.some((e) => e.name === ref.alias) ? 'ok' : 'dangling'
  }
  return refStatus(ref, authAliases.value)
}

// ── 变量选择器(#3):Ⓥ 从注册表选 ${var.<name>},不手打 ─────────────
// 注册表 = 共享 vars(config) + 全部 step 的 extract;config 来自共享
// draft store(CaseComposer watch 同步,含本页未编辑的最新值)。
const draftStore = useScenarioDraftStore()
const constantsStore = useConstantsStore()
const varPickerOpen = ref(false)
const varPickerKey = ref<string | null>(null)
const varPickerVal = ref<string | null>(null)

const varRegistryEntries = computed(() =>
  deriveVarRegistry(local, draftStore.draft?.definition?.config?.vars).entries)

// ── 字段动作菜单(#4/#5 变量工作台):子列表分流 + 快捷策略骨架 ──────

/** 引用子列表:仅 config/数据集出身(${var.x} 静态展开的合法来源) */
const referenceVarChoices = computed(() =>
  varRegistryEntries.value.filter((e) => e.origin === 'config'))

/**
 * 注入子列表:仅 extract 出身($.name 运行期语域的唯一入口是 assign)。
 * 时序门控:产出步 ≥ 当前步 → disabled(after_request 产出 vs
 * before_request 消费,同 step 不可用)。
 */
const injectVarChoices = computed(() => {
  const cur = activeStepIdx.value
  return varRegistryEntries.value
    .filter((e) => e.origin === 'extract')
    .map((e) => ({ ...e, disabled: (e.stepIdx ?? 0) >= cur }))
})

/**
 * 字段名 → 响应 JSONPath — 唯一来源是 plate 解析的候选,不猜:
 * ① 运行时样本(resolve-paths,最新鲜、数组天然 [idx])按字段名结尾匹配
 * ② 端点契约 assertable(注册时预解析的缓存)精确匹配
 * 无命中返回 ''(宁空勿错 — 旧兜底模板 $.data.<字段> 在数组响应上
 * 丢 [0] 段,静默错路径比空更糟;空引导用户粘样本/手填)。
 */
function respPathFor(fieldName: string): string {
  const sampleHit = samplePaths.value.find((p) => pathEndsWithField(p, fieldName))
  if (sampleHit) return toScratchPath(sampleHit)
  const assertableHit = currentAssertable.value.find(
    (p) => p === `$.data.${fieldName}` || p === `$.${fieldName}`
  )
  if (assertableHit) return toScratchPath(assertableHit)
  return ''
}

/** plate 域路径是否以字段名结尾:$.a.b / $.a['b'] / $.a[0]['b'] */
function pathEndsWithField(p: string, fieldName: string): boolean {
  const escaped = fieldName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(?:\\.|\\[')${escaped}(?:'\\])?$`).test(p)
}

/** 菜单"从响应提取":extract 骨架(target=字段名,scope=scenario) */
function onFieldExtract(f: IOFieldBinding) {
  if (!currentStep.value) return
  currentStep.value.strategy.push({
    kind: 'extract',
    target: f.name,
    expression: respPathFor(f.name),
    scope: 'scenario',
    required: true,
  })
  justAddedStrategyIdx.value = currentStep.value.strategy.length - 1
}

/** 菜单"注入响应变量":assign 骨架(source=$.<name>,target=request_body.<path>) */
function onFieldAssign(f: IOFieldBinding, name: string) {
  if (!currentStep.value) return
  currentStep.value.strategy.push({
    kind: 'assign',
    source: `$.${name}`,
    target: f.path.replace(/^\$\./, '$.request_body.'),
    scope: 'scenario',
    required: true,
  })
  justAddedStrategyIdx.value = currentStep.value.strategy.length - 1
}

/** 菜单"断言该字段":assertion 骨架(exists 起步,策略卡改 operator) */
function onFieldAssert(f: IOFieldBinding) {
  if (!currentStep.value) return
  currentStep.value.strategy.push({
    kind: 'assertion',
    target: respPathFor(f.name),
    operator: 'exists',
    expected: null,
    message: '',
    soft: false,
  })
  justAddedStrategyIdx.value = currentStep.value.strategy.length - 1
}

/** 菜单"引用共享变量":值追加已由 FieldForm 完成,此处给引导提示 */
function onVarInsert(_f: IOFieldBinding, name: string) {
  ElMessage.success(`已插入 \${var.${name}}(启动前展开,查不到将拒启)`)
}

/** 菜单"设为变量":FieldForm 已完成值替换与命名,默认值上报 CaseComposer 登记 config.vars */
function onVarPromote(_f: IOFieldBinding, name: string, value: unknown) {
  emit('varPromote', name, value)
  ElMessage.success(`已设为变量 ${name} — 默认值登记到 ③ 共享变量,保存草稿后生效`)
}

/** 同 openAuthPicker:key 在弹窗期间可能被改,落注入时按 key 或唯一 value 定位 */
function openVarPicker(key: string, value: string) {
  if (!currentStep.value) return
  varPickerKey.value = key
  varPickerVal.value = value
  varPickerOpen.value = true
}
function onVarPicked(tpl: string) {
  injectHeaderTpl(currentStep.value?.api?.headers, varPickerKey.value, varPickerVal.value, tpl)
  varPickerKey.value = null
  varPickerVal.value = null
}

// ── 策略角标(需求1):字段行尾显示已挂策略,点击跳转下方策略卡 ──────

/** 同 kind ≥2 → 按数组序编号 extract_1/extract_2;单条裸 kind。
 *  角标与策略卡头(Task 3 tagLabel)共用 → 对应关系可见。 */
function strategyTagLabels(strategies: StrategyView[]): string[] {
  const count = new Map<string, number>()
  for (const s of strategies) count.set(s.kind, (count.get(s.kind) ?? 0) + 1)
  const seq = new Map<string, number>()
  return strategies.map((s) => {
    const n = (seq.get(s.kind) ?? 0) + 1
    seq.set(s.kind, n)
    return (count.get(s.kind) ?? 0) > 1 ? `${s.kind}_${n}` : s.kind
  })
}

/** 策略 ↔ 字段匹配(双形态:scratch 域 + plate 域旧格式,老草稿兼容) */
function strategyMatchesField(s: StrategyView, domain: 'request' | 'response', f: IOFieldBinding): boolean {
  const sv = s as any
  if (domain === 'request') {
    return sv.kind === 'assign' && sv.target === f.path.replace(/^\$\./, '$.request_body.')
  }
  const scratch = toScratchPath(f.path)
  if (sv.kind === 'extract') return sv.expression === scratch || sv.expression === f.path
  if (sv.kind === 'assertion') return sv.target === scratch || sv.target === f.path
  return false
}

/** 请求字段匹配面(D9):声明 binding + body 深层派生行(deriveDeepRows
 *  单一真源,与 FieldForm 派生行同名同 path)— 注入只读态/请求侧策略
 *  角标按 path 匹配全部复用:派生行 assign 命中同得只读条/兜底行/角标。 */
function requestFieldSurface(step: StepView | undefined): IOFieldBinding[] {
  const declared = fieldBindings(step)
  return [...declared, ...deriveDeepRows(step?.request?.body, declared, carryRoots.value)]
}

/** 字段名 → 角标数组;响应侧字段取全状态码契约按名去重(同名字段同路径语义) */
function fieldStrategyTags(domain: 'request' | 'response'): Record<string, Array<{ label: string; idx: number }>> {
  const step = currentStep.value
  if (!step?.strategy.length) return {}
  const labels = strategyTagLabels(step.strategy)
  const fields = domain === 'request'
    ? requestFieldSurface(step)
    : currentRespSpecs.value.flatMap((spec) => spec.fields)
  const seen = new Set<string>()
  const tags: Record<string, Array<{ label: string; idx: number }>> = {}
  for (const f of fields) {
    if (seen.has(f.name)) continue
    seen.add(f.name)
    step.strategy.forEach((s, idx) => {
      if (strategyMatchesField(s, domain, f)) {
        ;(tags[f.name] ||= []).push({ label: labels[idx], idx })
      }
    })
  }
  return tags
}

const requestStrategyTags = computed(() => fieldStrategyTags('request'))
const responseStrategyTags = computed(() => fieldStrategyTags('response'))

/** 请求体字段动态注入态(已注入 → FieldForm 值控件换只读提示条):
 *  与 fieldStrategyTags 同源同匹配(assign target 精确命中
 *  $.request_body.<path>,匹配面 = requestFieldSurface 含派生行),
 *  但携带 source/target 供提示条悬停展示。
 *  响应侧无此概念(assign 不写响应)。 */
const requestInjected = computed<Record<string, Array<{ source: string; target: string }>>>(() => {
  const step = currentStep.value
  const out: Record<string, Array<{ source: string; target: string }>> = {}
  if (!step?.strategy.length) return out
  const seen = new Set<string>()
  for (const f of requestFieldSurface(step)) {
    if (seen.has(f.name)) continue
    seen.add(f.name)
    const hits = step.strategy.filter((s) => strategyMatchesField(s, 'request', f)) as Array<{
      source?: unknown; target?: unknown
    }>
    if (hits.length) {
      out[f.name] = hits.map((h) => ({ source: String(h.source ?? ''), target: String(h.target ?? '') }))
    }
  }
  return out
})

/** 角标跳转目标 + 脉冲序号(同 idx 重复点击靠 flash 重放感知,展开幂等) */
const jumpTargetIdx = ref(-1)
const jumpSeq = ref(0)
const currentTagLabels = computed(() => strategyTagLabels(currentStep.value?.strategy ?? []))

/** 角标点击:定位下方策略卡 — 滚动 + 展开(expandWhen 沿) + flash 重放 */
function onStrategyJump(idx: number) {
  jumpTargetIdx.value = idx
  jumpSeq.value++
  void nextTick(() => {
    const el = document.getElementById(`strategy-card-${idx}`)
    if (!el) return // 降级模式(kinds 拉取失败)无策略卡 → no-op
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.classList.remove('sf-flash')
    void (el as HTMLElement).offsetWidth // 重启动画
    el.classList.add('sf-flash')
  })
}

/** 模板里 refStatus 的第二参:已知 alias 集合 = 凭证池 ∪ 草稿 config.users
 *  (③ 用户认证快照 — 场景本地用户执行期由 Config.users 解析,不能误标悬空) */
const authAliases = computed(() => {
  const localUsers = Object.keys(draftStore.draft?.definition?.config?.users ?? {})
  return [...new Set([...auths.value.map((a) => a.alias), ...localUsers])]
})

onMounted(() => {
  // 首次进入策略区前预热:策略 kinds + 各 kind 的 detail(一次性)。
  // (onMounted 每实例只跑一次,无需 once-guard。)
  void loadStrategyKinds().then(() => {
    for (const k of strategyKinds.value) void ensureStrategyDetail(k.kind)
  })
  // 认证列表:ⓘ 选择器 + 悬空徽章判定共用。失败静默(ⓘ 打开时列表为空,可重进)
  listAuths().then((a) => { auths.value = a }).catch(() => {})
  // 常量池条目(CaseComposer rail 之外的第二拉取点;store 内 in-flight/
  // 已有数据短路保证只发一次)
  void constantsStore.ensureEntries().catch(() => {})
})

watch(() => props.steps, (v) => {
  // 父组件回写的是 emit 出去的同一份内容(引用不同)。deep-equal 时跳过,
  // 避免与下方 emit watch 互触形成递归更新环(Maximum recursive updates)。
  if (sameSteps(v, local)) return
  local.splice(0, local.length, ...(v || []))
}, { deep: true })

watch(() => props.orchestration, (v) => {
  if (v && v.steps.length === orch.steps.length && sameSteps(v.steps, orch.steps)
    && JSON.stringify(v.resourceMeta) === JSON.stringify(orch.resourceMeta)) return
  orch.steps.splice(0, orch.steps.length, ...(v?.steps || []))
  orch.resourceMeta = v?.resourceMeta || {}
}, { deep: true })

watch([local, orch], () => {
  emit('update:steps', [...local])
  emit('update:orchestration', { steps: [...orch.steps], resourceMeta: { ...orch.resourceMeta } })
}, { deep: true })

/** 两份 step 数组内容是否一致(浅比较 + 关键字段;step 对象在同步链上会被克隆,不能比引用)。
 *  参数是结构无关的 — steps watch 传 StepView[],orchestration watch 传 StepOrchestration[]。 */
function sameSteps(a: readonly unknown[] | undefined, b: readonly unknown[]): boolean {
  if (!a) return false
  if (a.length !== b.length) return false
  return a.every((s, i) => {
    const t = b[i]
    return s === t || JSON.stringify(s) === JSON.stringify(t)
  })
}

/**
 * 预填的 code 断言 target 探测顺序 —— 仅当断言面(view_only 通道
 * assertable=True 条目的 path 集)命中其一才追加业务码断言,避免给
 * 没有 code 语义的接口塞无效断言。
 */
const CODE_TARGET_CANDIDATES = ['$.code', '$.data.code'] as const

// ── /full 结构契约:单一会话缓存(容器原则) ─────────────────────────
// endpoint_id → plate /full 响应整包。所有结构渲染(请求字段表单/断言
// 候选/响应契约/Type C 差集)都是这份缓存的 computed 切片 — 每个 endpoint
// 会话内恰好一次请求。不随 draft 持久化:plate 是结构权威源,每次进
// 编辑器都拿最新结构,发版后零迁移。
const endpointFullByEndpoint = new Map<string, EndpointFullView>()
/** 进行中的 /full 请求(同 endpoint 并发收敛为同一 Promise) */
const fullInFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** 响应式触发器:Map 变更不触发 computed,版本号 bump */
const fullVersion = ref(0)
/** 最近一次拉取状态(控制表单 loading/失败占位) */
const fullState = ref<'loading' | 'failed' | ''>('')

/** 缓存 miss 时拉 /full 并回填(fail-soft:失败返回 undefined,消费方各自降级) */
function ensureEndpointFull(endpointId: string): Promise<EndpointFullView | undefined> {
  const cached = endpointFullByEndpoint.get(endpointId)
  if (cached) return Promise.resolve(cached)
  const inFlight = fullInFlight.get(endpointId)
  if (inFlight) return inFlight
  fullState.value = 'loading'
  const p = getFullEndpoint(endpointId)
    .then((full) => {
      endpointFullByEndpoint.set(endpointId, full)
      fullVersion.value++
      fullState.value = ''
      return full
    })
    .catch(() => {
      fullState.value = 'failed'
      return undefined
    })
    .finally(() => fullInFlight.delete(endpointId))
  fullInFlight.set(endpointId, p)
  return p
}

/** 当前 step 的 /full 结构契约(拉取中/失败 → undefined) */
const currentFull = computed<EndpointFullView | undefined>(() => {
  void fullVersion.value
  const eid = currentStep.value?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)
  return endpointFullByEndpoint.get(eid)
})

/** 当前 step 的断言候选列表;未知/拉取中 → 空(不渲染 ▾)
 *  declarations 归一化后:view_only 通道 assertable=True 条目的 paths */
const currentAssertable = computed<string[]>(
  () => assertablePaths(currentFull.value?.responses?.['200']?.declarations)
)

/** /full responses[status] 轻量投影(设计 §2.4);引用数据不进 draft */
interface RespSpecLite {
  status: number
  description: string
  fields: IOFieldBinding[]
  /** plate 域路径,渲染 ✓ 标用;写策略时过 toScratchPath */
  assertable: string[]
  /** 200 契约 schema(Type C 差集源);非 200 恒 undefined */
  schema?: Record<string, unknown>
}
/** 当前 step 的全状态码响应契约(状态码字典序)
 *  declarations 归一化后:fields = view_only 投影,assertable = 断言候选投影 */
const currentRespSpecs = computed<RespSpecLite[]>(() => {
  const full = currentFull.value
  if (!full) return []
  return Object.entries(full.responses || {})
    .map(([status, spec]) => ({
      status: Number(status),
      description: spec.description || '',
      fields: channelFields(spec.declarations, 'view_only'),
      assertable: assertablePaths(spec.declarations),
      schema: status === '200'
        ? spec.schema
        : undefined,
    }))
    .sort((a, b) => a.status - b.status)
})

/** 请求侧契约 schema(Type C 差集源) */
const currentReqSchema = computed<Record<string, unknown> | undefined>(
  () => currentFull.value?.request?.schema
)

// ── 策略区说明:request/response 共用 step.strategy 单数组(执行序即数组
//    序,plate Step 契约不变);不按签页过滤,避免"Request 页添加的策略
//    只在 Response 侧可见"的割裂。phase 分域仅保留在 detail 数据里。

// ── Type C 查看入口(设计 §3.5):schema 有、binding 无的隐藏字段差集 ───
interface TypeCField { name: string; type: string; path: string; default?: unknown }
/**
 * schema.properties 键集 与 已绑定 fields[].path(掐头 `$.`)求差集。
 * 响应侧仍为纯查看;请求侧经 reqTypeC 传入 FieldForm「其他字段」,
 * default 作契约行 placeholder(编辑写入 body)。
 */
function typeCFields(
  schema: Record<string, unknown> | undefined,
  knownPaths: string[]
): TypeCField[] {
  const props = (schema?.properties ?? {}) as Record<string, { type?: string; default?: unknown }>
  const known = new Set(knownPaths.map((p) => p.replace(/^\$\./, '')))
  return Object.keys(props)
    .filter((k) => !known.has(k))
    .map((k) => ({
      name: k,
      type: props[k]?.type ?? 'unknown',
      path: `$.${k}`,
      default: props[k]?.default,
    }))
}
/** 请求侧 Type C(挂 Request 签页底部;carry 键排除 — 传递面零感知)
 *  declarations 归一化后:carry 通道条目 path 集 */
const reqCarryPaths = computed<Set<string>>(() =>
  new Set(carryPaths(currentFull.value?.request?.declarations)))
/** carry 容器根键集(D7 警告行):carry 通道 path 归一根段去重 —
 *  $.cfg.timeout → 'cfg';传 FieldForm,深字段落 carry 容器渲染接管警告 */
const carryRoots = computed<string[]>(() =>
  [...new Set(carryPaths(currentFull.value?.request?.declarations)
    .map((p) => p.replace(/^\$\.?/, '').split(/[.[\]]/)[0]))])
const reqTypeC = computed<TypeCField[]>(() =>
  typeCFields(currentReqSchema.value, fieldBindings(currentStep.value).map((f) => f.path))
    .filter((f) => !reqCarryPaths.value.has(f.path))
)
/** 响应侧 Type C(200 契约 schema 差集,挂 Response 签页底部) */
const respTypeC = computed<TypeCField[]>(() => {
  const spec200 = currentRespSpecs.value.find((s) => s.status === 200)
  if (!spec200) return []
  return typeCFields(spec200.schema, spec200.fields.map((f) => f.path))
})

// ── 服务引用(别名消费点,spec §1.4 双显)─────────────────────────
// 目录事实(锚点)只读;引用(steps[k].api.service)可切可建别名。
// 目录名集合 = deriveBase 的唯一外部输入;拉取失败静默降级为空集合 →
// 全部裸声明黄警,不阻塞编排(酸性测试)。

/** plate 目录服务名全串集合(会话级,模块缓存由 loader 负责) */
const catalogNames = ref<Set<string>>(new Set())
onMounted(() => {
  loadCatalogServiceNames()
    .then((ns) => { catalogNames.value = new Set(ns) })
    .catch(() => { /* 目录不可达 → 派生降级裸声明黄警,不阻塞编排 */ })
})

/** 本 endpoint 的目录服务锚点:/full 的 service(权威)→ 派生当前引用 → null */
const serviceAnchor = computed<string | null>(() => {
  const fromFull = currentFull.value?.service
  if (fromFull && catalogNames.value.has(fromFull)) return fromFull
  return deriveBase(currentStep.value?.api?.service || '', catalogNames.value)
})

// ── carry 只读提示(spec §5)───────────────────────────────────────
// 编排器对 carry 零感知(值由 platform 运行时注入),这里只读提示:
// 字段面 ∩ 值表非空集 → step 卡灰徽标「carry N」,悬停列每个键的来源
// (服务绑定/全局默认)。值表拉取失败静默降级 → 无徽标,不阻塞编排
// (与目录名降级同策略);交集与绑定优先规则在 carryHint 纯函数。
const carryValues = ref<{ defaults: CarryValues; bindings: Record<string, CarryValues> } | null>(null)
onMounted(async () => {
  try {
    const [defaults, bindings] = await Promise.all([getCarryDefaults(), getCarryBindings()])
    carryValues.value = { defaults, bindings }
  } catch { /* 值表不可达 → 无提示,不阻塞编排 */ }
})

/** step → 可注入的 carry 键清单(path → 来源);别名经 deriveBase 归锚点服务 */
function carryInjectable(step: StepView): Map<string, CarrySource> {
  void fullVersion.value  // /full 会话缓存回填(fullVersion bump)后徽标重算
  if (!carryValues.value) return new Map()
  const eid = step.api?.view_hints?.endpoint_id
  const full = eid ? endpointFullByEndpoint.get(eid) : undefined
  const face = carryPaths(full?.request?.declarations)
  if (!face.length) return new Map()
  const base = deriveBase(step.api?.service || '', catalogNames.value)
  // base=null(未知服务)→ 运行时整步跳过注入(carry_injection derive_base
  // 失败短路),徽标不显示 — 与运行时行为对齐,不过度承诺
  if (!base) return new Map()
  const bound = carryValues.value.bindings[base] ?? {}
  return carryHint(face, bound, carryValues.value.defaults)
}

/**
 * 引用下拉选项:锚点(目录服务)居首 → 同基别名(deriveBase === 锚点)
 * → 其他声明键置底标跨服务(dim)。锚点缺失(未挂目录步骤,引用键派生
 * 不出目录归属)时列出全部目录名 — 否则目录名在下拉里根本不出现,
 * 裸声明步骤无路切回目录服务,与「无法创建别名」互相死锁。
 */
const serviceOptions = computed(() => {
  const anchor = serviceAnchor.value
  const declared = props.services ?? {}
  const opts: Array<{ value: string; label: string; dim?: boolean }> = []
  const seen = new Set<string>()
  const push = (value: string, label: string, dim = false) => {
    if (seen.has(value)) return
    seen.add(value)
    opts.push({ value, label, dim })
  }
  if (anchor) push(anchor, `${anchor}(目录服务)`)
  else for (const n of catalogNames.value) push(n, `${n}(目录服务)`)
  for (const key of Object.keys(declared)) {
    if (!anchor || key === anchor) continue
    if (deriveBase(key, catalogNames.value) === anchor)
      push(key, key)                                           // 本服务别名
  }
  for (const key of Object.keys(declared)) {                   // 其他键置底
    if (anchor && (key === anchor || deriveBase(key, catalogNames.value) === anchor)) continue
    push(key, `${key}(跨服务)`, true)
  }
  return opts
})

/** 引用告警(§1.5 全表警告级,永不阻断):裸声明黄 / 跨服务黄 / 未声明红 */
const refWarning = computed<{ text: string; level: 'warn' | 'error' } | null>(() => {
  const cur = currentStep.value?.api?.service || ''
  if (!cur) return null
  const anchor = serviceAnchor.value
  if (!anchor || deriveBase(cur, catalogNames.value) === null)
    return { text: '未挂目录服务(裸声明)', level: 'warn' }
  if (cur !== anchor && deriveBase(cur, catalogNames.value) !== anchor)
    return { text: '跨服务引用', level: 'warn' }
  if (!(cur in (props.services ?? {})))
    return { text: '未声明 — Config 或运行弹框补 URL 后可跑', level: 'error' }
  return null
})

/** 当前引用键的已声明 URL(未声明 → 空,模板给占位提示) */
const declaredUrlOf = (svc: string) => (props.services ?? {})[svc] || ''

function onServiceRefChange(step: StepView, value: string) {
  if (value === '__create__') { creatingAlias.value = true; return }
  creatingAlias.value = false
  step.api!.service = value          // local 直改,既有 watch 传播 update:steps
}

// 内联创建器:前缀(目录名)固定不可改,只收后缀 + URL(spec §1.3)
const creatingAlias = ref(false)
const aliasSuffix = ref('')
const aliasUrl = ref('')

function confirmAliasCreate(step: StepView) {
  const anchor = serviceAnchor.value
  const suffix = aliasSuffix.value.trim()
  const url = aliasUrl.value.trim()
  if (!anchor) { ElMessage.warning('未知目录服务,无法创建别名'); return }
  if (!suffix) { ElMessage.warning('后缀不能为空'); return }
  if (suffix.includes('-')) { ElMessage.warning('后缀不能含 "-"(分隔符保留)'); return }
  const full = `${anchor}-${suffix}`
  if (full in (props.services ?? {})) { ElMessage.warning(`别名 ${full} 已存在`); return }
  if (!url) { ElMessage.warning('baseUrl 不能为空'); return }
  // 一次动作双写 ①声明(config.services,经 emit 由父级落 definition)
  // ②引用(steps[k].api.service,local 直改经既有 watch 传播)
  emit('update:services', { ...(props.services ?? {}), [full]: url })
  step.api!.service = full
  creatingAlias.value = false
  aliasSuffix.value = ''
  aliasUrl.value = ''
  ElMessage.success(`已创建别名 ${full} 并切换引用`)
}

/** 策略表单候选映射(#2):kind 定字段名 — assertion 用 target,extract 用 expression */
function strategyCandidates(s: StrategyView): Record<string, string[]> {
  const fields = s.kind === 'assertion' ? ['target'] : s.kind === 'extract' ? ['expression'] : []
  // B1:候选 = 端点 assertable ∪ 响应样本解析(数组下标天然正确)
  const platePaths = [...currentAssertable.value, ...samplePaths.value]
  if (!fields.length || !platePaths.length) return {}
  // 候选列表 = 运行期真实语义(scratch 域),用户选了即正确
  return Object.fromEntries(
    fields.map((f) => [f, platePaths.map(toScratchPath)])
  )
}

// ── B1 响应样本路径推断 ──
const sampleOpen = ref(false)
const sampleText = ref('')
const sampleError = ref('')
/** plate 域候选路径(resolve-paths 产物);strategyCandidates 统一转 scratch 域 */
const samplePaths = ref<string[]>([])

async function onParseSample() {
  sampleError.value = ''
  let parsed: unknown
  try {
    parsed = JSON.parse(sampleText.value)
  } catch {
    sampleError.value = 'JSON 解析失败 — 请粘贴合法 JSON 响应体'
    return
  }
  try {
    const paths = await resolveResponsePaths(parsed)
    samplePaths.value = paths.map((p) => p.path)
    if (!samplePaths.value.length) {
      sampleError.value = '未解析出路径 — 样本需为 JSON 对象或数组'
    }
  } catch {
    sampleError.value = '解析失败 — plate 服务不可达或返回异常'
  }
}

/** 由 endpoint 契约(/full 原料)构造初始策略,替代硬编码 $.status eq 200 */
function buildInitialStrategies(full: EndpointFullView | undefined): StrategyView[] {
  // 保底第一条: HTTP 层状态断言(与旧行为一致)
  const strategies: StrategyView[] = [
    { kind: 'assertion', target: toScratchPath('$.status'), operator: 'eq', expected: 200, message: '', soft: false },
  ]
  if (!full) return strategies
  const r200 = full.responses?.['200']
  const assertable = assertablePaths(r200?.declarations)
  const successCriteria = full.metadata?.success_criteria || ''
  // 契约驱动追加: success_criteria 非空 且 响应确有 code 断言位
  if (successCriteria) {
    const codeTarget = CODE_TARGET_CANDIDATES.find((c) => assertable.includes(c))
    if (codeTarget) {
      strategies.push({
        kind: 'assertion', target: toScratchPath(codeTarget), operator: 'eq', expected: 0,
        message: successCriteria, soft: false,
      })
    }
  }
  return strategies
}

/**
 * 从接口目录把 endpoint 加入步骤流:拉 /full 组装初始 step(策略/初始 body)。
 * 契约禁令(spec 2026-08-27 §1.6):目录插入只此一次写 api.service(初值
 * = 规范目录名);任何 plate 拉取驱动的回写不得再触碰该字段 — 它是用户
 * 引用键(可为别名全串),view_hints.endpoint_id 才是目录锚点。
 */
async function onAddEndpoint(ep: any) {
  if (!ep) return
  adding.value = true
  try {
    // 拉 plate /api/endpoint/{id}/full 取字段契约 + 策略原料
    // (assertable 面 / success_criteria);失败仍以原始信息加入
    // (用户投诉过的"裸 JSON"兜底)。
    const full = await ensureEndpointFull(ep.id)
    if (!full) ElMessage.warning('拉取完整接口定义失败, 仍以原始信息加入')
    const fields = channelFields(full?.request?.declarations, 'binding')
    const strategy = buildInitialStrategies(full)
    // 初始 body:只合成绑定 default/example(carry/契约默认移交注入通道)
    const initialBody = deepDefaults(fields)
    const newStep: StepView = {
      kind: 'step',
      // plate 契约描述优先(/full → 目录行),name 仅最后兜底
      description: full?.description || ep.description || ep.name,
      api: {
        kind: 'api',
        service: ep.service,
        method: ep.api?.method || 'GET',
        path: ep.api?.path || '',
        headers: ep.api?.headers || {},
        // 接口身份持久化(#2):字段契约/断言/extract 候选懒拉 /full 的 key;
        // view_hints 是平台视图扩展,GimbalScenarioExporter 导出时剥离
        view_hints: { endpoint_id: ep.id },
      },
      request: {
        kind: 'request',
        body: initialBody,
      },
      strategy,
    }
    local.push(newStep)
    // 同步 orchestration (保持 index 对齐)
    orch.steps.push({ enabled: true, name: ep.name })
    activeStepIdx.value = local.length - 1
    subView.value = null  // 直接落盘, 关闭目录回到画布
    ElMessage.success(`已加入 step: ${ep.name} (${fields.length} 字段)`)
  } finally {
    adding.value = false
  }
}

function removeStep(i: number) {
  local.splice(i, 1)
  orch.steps.splice(i, 1)  // 保持与 local 同序同长
  if (activeStepIdx.value >= local.length) activeStepIdx.value = Math.max(0, local.length - 1)
}

// ── 步骤拖拽重排(#5) ─────────────────────────────────────────────
// item-key 不能写进 step 数据本体(草稿原样进 /convert,不能加字段),
// 用 WeakMap 给对象侧挂稳定 key — key 生命周期与对象引用一致,天然免清理。
const stepKeys = new WeakMap<object, number>()
let stepKeySeq = 0
function stepKey(s: object): number {
  let k = stepKeys.get(s)
  if (k === undefined) {
    k = ++stepKeySeq
    stepKeys.set(s, k)
  }
  return k
}

/**
 * draggable @end:同步 orch.steps(same splice)并让 activeStepIdx 跟随
 * 被拖动的 step。选中项身份从 orch.steps 取 — local 此刻是否已被
 * vuedraggable 重排取决于 sortable 内部事件序,而 orch 只有本函数一处写,
 * 时序自定;且 orch 与重排前的 local 下标对齐,activeStepIdx 正是旧下标。
 */
function onStepReordered(evt: { oldIndex?: number; newIndex?: number }) {
  const { oldIndex, newIndex } = evt
  if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
  const selected = orch.steps[activeStepIdx.value]
  const moved = orch.steps.splice(oldIndex, 1)[0]
  orch.steps.splice(newIndex, 0, moved)
  if (selected) {
    const next = orch.steps.indexOf(selected)
    if (next >= 0) activeStepIdx.value = next
  }
}

</script>

<style scoped>
/* 表单控件统一外观走 composer.css (.c-form) */
.canvas-shell { width: 100%; }

/* 三栏自适应: 宽屏 3 栏, 中屏两栏 (信息面板下移), 窄屏单列
   (gap 16px 对齐 ①-③ 页 .c-page 卡片间隔) */
.three-col {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(240px, 300px);
  gap: 16px;
  min-height: 600px;
  align-items: start;
}
@media (max-width: 1280px) {
  .three-col { grid-template-columns: minmax(240px, 300px) minmax(0, 1fr); }
  .col-info { grid-column: 1 / -1; }
  /* 全宽时三卡自适应并肩(step 信息横贯,VRP+CPP 并排;~640px 下自动单列) */
  .col-stack {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    align-items: start;
  }
  .col-stack .info-card { grid-column: 1 / -1; }
}
@media (max-width: 860px) {
  .three-col { grid-template-columns: minmax(0, 1fr); }
}

/* 右栏卡堆: step 信息 / 变量注册表 / 常量池 三张独立卡,块间隔对齐 .c-page */
.col-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

/* 列卡与 ①-③ 页 .c-card 同款(白卡 20px 24px + col-head 分隔线) */
.col {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 20px 24px;
  display: flex; flex-direction: column;
}

.col-head {
  margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid var(--c-divider);
  display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
}
.col-head h3 { margin: 0 0 2px; font-size: 14px; font-weight: 600; }
.col-head .muted { margin: 0; font-size: 11px; color: var(--c-text-tertiary); }

.add-step {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--c-accent);
  color: #fff; border: none; border-radius: 6px;
  padding: 6px 12px; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: background 0.15s;
  white-space: nowrap;
}
.add-step:hover { background: var(--accent-hover, #3730a3); }

/* step list */
.step-list { display: flex; flex-direction: column; gap: 6px; flex: 1; overflow-y: auto; }
/* draggable 容器接管行布局与行间距(行现在挂在这一层,不再直接挂 .step-list) */
.step-drag-area { display: flex; flex-direction: column; gap: 6px; }
/* 拖拽手柄:竖排点阵,grab 光标;仅手柄可发起拖拽(handle 限定),
   行其余区域仍是点击选中 */
.step-handle {
  flex-shrink: 0;
  width: 14px;
  color: var(--c-border-strong, #cbd5e1);
  cursor: grab;
  font-size: 13px;
  line-height: 1;
  user-select: none;
  text-align: center;
}
.step-handle:active { cursor: grabbing; }
.step-row:hover .step-handle { color: var(--c-text-tertiary); }
.step-row.sortable-ghost { opacity: 0.4; border-style: dashed; }
.step-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  background: var(--c-bg-secondary);
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.step-row:hover { background: var(--c-surface); border-color: var(--c-border); }
.step-row.active {
  background: var(--c-accent-soft);
  border-color: var(--c-accent-soft-border);
}
.step-row.disabled { opacity: 0.55; }
.step-idx {
  width: 26px; height: 26px; border-radius: 50%;
  background: var(--c-surface); color: var(--c-text-secondary);
  font-size: 12px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--c-border);
  flex-shrink: 0;
}
.step-row.active .step-idx {
  background: var(--c-accent);
  color: #fff; border-color: transparent;
}
.step-info { flex: 1; min-width: 0; }
.step-name { font-size: 13px; font-weight: 600; color: var(--c-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.step-row.active .step-name { color: var(--c-accent); }
.step-meta { display: flex; gap: 4px; align-items: center; margin-top: 3px; font-size: 10px; color: var(--c-text-secondary); flex-wrap: wrap; }
.method-badge {
  font-family: var(--font-mono); font-weight: 700;
  padding: 1px 5px; border-radius: 3px;
  background: #f1f5f9; color: #475569; font-size: 9px;
}
.method-badge.m-get { background: #dbeafe; color: #1e40af; }
.method-badge.m-post { background: #d1fae5; color: #065f46; }
.method-badge.m-put { background: #fef3c7; color: #92400e; }
.method-badge.m-delete { background: #fee2e2; color: #991b1b; }
.method-badge.m-patch { background: #f3e8ff; color: #6b21a8; }
/* carry 只读徽标:灰底中性色(platform 注入,编排器零感知,仅提示) */
.carry-badge {
  font-family: var(--font-mono); font-weight: 700;
  padding: 1px 5px; border-radius: 3px;
  background: #e2e8f0; color: #64748b; font-size: 9px;
  cursor: default;
}
.svc-tag { background: #f1f5f9; color: #475569; padding: 1px 5px; border-radius: 3px; font-size: 9px; }
.ep-path { font-family: var(--font-mono); font-size: 10px; color: var(--c-text-tertiary); }
.step-row :deep(.el-switch) { transform: scale(0.8); }
.step-del {
  width: 24px; height: 24px; background: transparent; border: none;
  border-radius: 4px; color: var(--c-text-tertiary); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s; opacity: 0;
}
.step-row:hover .step-del { opacity: 1; }
.step-del:hover { background: #fef2f2; color: #ef4444; }

.step-empty {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 40px 16px; text-align: center; color: var(--c-text-tertiary);
}
.step-empty svg { color: var(--c-border-strong); }
.step-empty p { margin: 0; font-size: 13px; }
.empty-cta {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--c-accent); color: #fff; border: none; border-radius: 6px;
  padding: 8px 16px; font-size: 12px; font-weight: 600;
  cursor: pointer;
}
.empty-cta:hover { background: var(--accent-hover, #3730a3); }

/* fields editor */
.fields-shell { flex: 1; }
.fields-head {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--c-divider);
  margin-bottom: 16px;
}
.fields-head-row { display: flex; align-items: center; gap: 10px; }
.api-summary {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-top: 8px; padding: 6px 10px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 6px;
}
.api-summary .ep-path { font-size: 11px; }

/* ── 服务引用双显(spec §1.4):目录事实只读缩略之上,引用下拉 + 内联创建 ── */
.svc-ref {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-top: 6px; padding: 6px 10px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  font-size: 11px;
}
.svc-ref-label {
  flex-shrink: 0;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  color: var(--c-text-tertiary);
}
.svc-ref-select {
  border: 1px solid var(--c-border);
  border-radius: 5px;
  background: var(--c-surface);
  color: var(--c-text);
  font-size: 11px; font-family: var(--font-mono);
  padding: 3px 6px;
  max-width: 260px;
  outline: none;
}
.svc-ref-select:focus { border-color: var(--c-accent); }
/* 跨服务键置底置灰(可选项,非禁用 — 显示级语义,不阻断选择) */
.svc-ref-select .dim { color: #94a3b8; }
/* 引用告警:黄=裸声明/跨服务(可跑但提示),红=未声明(运行前需补 URL) */
.svc-ref-warn { font-size: 10px; font-weight: 600; }
.svc-ref-warn.warn { color: #b45309; }
.svc-ref-warn.error { color: #dc2626; }
/* 内联创建器:前缀(目录名)固定只读,后缀 + URL 两输入 */
.alias-create {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  width: 100%;
  padding: 6px;
  background: var(--c-surface);
  border: 1px dashed var(--c-border);
  border-radius: 6px;
}
.alias-prefix {
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  color: var(--c-text-secondary);
}
.alias-suffix, .alias-url {
  border: 1px solid var(--c-border);
  border-radius: 5px;
  background: var(--c-bg-secondary);
  font-size: 11px; font-family: var(--font-mono);
  padding: 3px 6px;
  outline: none;
}
.alias-suffix { width: 110px; }
.alias-url { flex: 1; min-width: 180px; }
.alias-suffix:focus, .alias-url:focus { border-color: var(--c-accent); }
.svc-ref-url {
  width: 100%;
  font-family: var(--font-mono); font-size: 10px;
  color: var(--c-text-tertiary);
  word-break: break-all;
}
.desc-readonly {
  margin: 0;
  font-size: 12.5px;
  color: var(--c-text-secondary);
  line-height: 1.7;
}
.fields-title { display: flex; align-items: center; gap: 8px; flex: 1; }
.title-num {
  width: 28px; height: 28px; border-radius: 6px;
  background: var(--c-accent);
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.title-input {
  border: none; background: transparent;
  font-size: 18px; font-weight: 700; color: var(--c-text);
  flex: 1; outline: none;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  min-width: 0;
}
.title-input:focus { border-bottom-color: var(--c-accent); }
.step-kind {
  padding: 4px 10px; border-radius: 999px;
  background: #f3e8ff; color: #6b21a8;
  font-size: 11px; font-weight: 600;
}

.input-tag {
  display: inline-block; background: var(--c-accent);
  color: #fff; font-size: 10px; font-weight: 700;
  padding: 2px 6px; border-radius: 4px; margin-right: 4px;
}

.code-input :deep(.el-textarea__inner) {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.5;
  background: #1e1e2e; color: #a6e3a1;
  border-radius: 6px; box-shadow: 0 0 0 1px #313244;
  padding: 10px 12px;
}
.code-input :deep(.el-textarea__inner::placeholder) { color: #6c7086; }

/* 附带字段 (Type C) 折叠区 — 平面化: 去渐变,保留琥珀色语义 */
.extra-fields {
  margin-top: 10px;
  border: 1px solid #fde68a; border-radius: 8px;
  background: #fffbeb;
}
.extra-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; cursor: pointer;
  font-size: 12px; font-weight: 600; color: #92400e;
}
.extra-head svg { transition: transform 0.15s; }
.extra-head svg.open { transform: rotate(180deg); }
.extra-hint { margin-left: auto; font-size: 11px; font-weight: 400; color: #b45309; }
.extra-body { padding: 0 12px 10px; display: flex; flex-direction: column; gap: 4px; }
.extra-row {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; background: #fff; border-radius: 4px;
  font-size: 11px;
}
.extra-key { color: #4338ca; font-weight: 600; }
.extra-arrow { color: var(--c-text-tertiary); }
.extra-val { color: #15803d; }
.extra-tag {
  margin-left: auto; padding: 1px 6px; border-radius: 3px;
  font-size: 9px; font-weight: 700; text-transform: uppercase;
}
.t-c { background: #fde68a; color: #92400e; }

/* 字段栅格自适应 */
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0 14px; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0 14px; }

/* extract 行 — 走共享 kv 栅格 */
.extract-row { margin-bottom: 4px; }
.ex-path :deep(.el-input__wrapper) { font-family: var(--font-mono); }
.add-extract { width: 100%; }

/* 策略区(语法 dim 驱动) */
.strategy-area { width: 100%; }

/* B1 响应样本折叠条:折叠态只占一行;展开 textarea + 解析按钮 */
.sample-bar { margin-bottom: 6px; }
.sample-toggle {
  border: none; background: transparent; padding: 2px 0;
  font-size: 11px; color: #64748b; cursor: pointer;
}
.sample-toggle:hover { color: #4f46e5; }
.sample-body { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.sample-input {
  box-sizing: border-box; width: 100%;
  font-family: var(--font-mono); font-size: 12px;
  border: 1.5px solid #e6e8ec; border-radius: 8px;
  padding: 8px 10px; outline: none; resize: vertical;
  background: #fafbfc; color: #1a1d24;
}
.sample-input:focus { border-color: #4f46e5; background: #fff; }
.sample-actions { display: flex; align-items: center; gap: 10px; }
.sample-parse {
  border: 1px solid #c3ccdb; background: #f8fafc; border-radius: 6px;
  padding: 4px 12px; font-size: 12px; cursor: pointer;
}
.sample-parse:hover { background: #eef2ff; border-color: #4f46e5; }
.sample-error { font-size: 11px; color: #dc2626; }
.sample-ok { font-size: 11px; color: #059669; }
.add-strategy { width: 100%; }
.strat-kind-tag {
  margin-left: 8px;
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8;
}

/* headers KV 行 — 独立 flex 布局(元素数可变: key/val/ⓘ/×/chips,
   不能用 .c-kv-row 的固定 4 列 grid,多出的子元素会溢出格子叠层) */
.hdr-rows { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.hdr-row {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 6px;
  background: var(--c-bg-secondary);
  border-radius: 6px;
}
.hdr-key { width: 170px; flex-shrink: 0; }
.hdr-val { flex: 1; min-width: 200px; }
.hdr-pick { color: #4f46e5; flex-shrink: 0; }
.hdr-pick:hover { background: #e0e7ff; color: #3730a3; }
/* Ⓥ 变量选择器:绿系,与 ⓘ(认证,靛蓝)区分 */
.hdr-var { color: #047857; }
.hdr-var:hover { background: #d1fae5; color: #065f46; }
.hdr-row .c-kv-del { flex-shrink: 0; }
.ref-chip { margin-top: 2px; }

/* ${auth.*} 引用徽章:绿=可解析 / 红=悬空 */
.ref-chip {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: 10px;
  padding: 1px 7px; border-radius: 3px;
  background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0;
}
.ref-chip.dangling { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
.ref-chip-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.ref-chip-note { font-family: inherit; opacity: 0.85; }

/* fields empty */
.fields-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: var(--c-text-tertiary);
}
.fields-empty svg { color: var(--c-border-strong); }
.fields-empty p { margin: 0; font-size: 13px; }
.fields-empty .muted { font-size: 12px; }

/* info panel */
.info-body { display: flex; flex-direction: column; gap: 12px; }
.info-block {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 10px 12px; background: var(--c-bg-secondary); border-radius: 8px;
}
.info-k {
  width: 50px; flex-shrink: 0;
  font-size: 11px; color: var(--c-text-tertiary); text-transform: uppercase; font-weight: 600;
}
.info-v { flex: 1; font-size: 12px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.info-v code { font-family: var(--font-mono); font-size: 11px; color: var(--c-accent); background: var(--c-surface); padding: 1px 4px; border-radius: 3px; word-break: break-all; }
.badge { background: #f3e8ff; color: #6b21a8; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-pill { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-pill.on { background: #d1fae5; color: #065f46; }
.status-pill.off { background: #fee2e2; color: #991b1b; }
.extract-line { font-size: 10px; width: 100%; }
/* 响应字段行(#2):字段名 + ui_kind 小标,断言/extract 目标参考 */
.resp-field-line {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; width: 100%;
}
.resp-field-kind {
  font-family: var(--font-mono); font-size: 9px;
  color: #94a3b8; background: #f1f5f9;
  padding: 0 4px; border-radius: 3px;
}
.info-empty { padding: 40px 0; text-align: center; font-size: 12px; }

/* ── IO 重叠页签(Chrome 造型):选中签与面板连体,相邻签被压在下面 ── */
.io-tabs {
  display: flex;
  align-items: flex-end;
  position: relative;
  margin-bottom: -1px;               /* 压住面板上缘边框,连体 */
}
.io-tab {
  position: relative;
  box-sizing: border-box;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  flex: none;
  width: calc(50% + 8px);            /* 两签各占 1/2 + 中缝重叠各让 8px,与面板左右缘对齐 */
  height: 36px;
  padding: 0 18px;
  margin-right: -16px;               /* 重叠量 */
  border-radius: 10px 10px 0 0;
  background: #eef0f7;
  border: 1px solid var(--c-border, #e7e9f2);
  border-bottom: none;
  color: #8a90a3;
  font-size: 12.5px; font-weight: 600; font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.io-tab:hover { background: #e6e9f4; z-index: 2; }
.io-tab:last-child { margin-right: 0; }
.io-tab:focus-visible { outline: 2px solid #4f46e5; outline-offset: -2px; z-index: 8; }
/* 计数徽章:idle 灰;active 域色(request indigo / response emerald) */
.io-tab .count {
  min-width: 18px; height: 18px; padding: 0 6px;
  border-radius: 999px; display: grid; place-items: center;
  background: rgba(120, 128, 160, 0.16); color: #8a90a3;
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
  transition: background 0.15s, color 0.15s;
}
/* 选中态:浮到最上层,与面板同色连体 */
.io-tab.active {
  background: #fbfbfe;
  color: #1f2430;
  z-index: 6;
  box-shadow: 0 1px 0 0 #fbfbfe;     /* 遮住面板上缘边框 */
}
.io-tab.active .count { background: #4f46e5; color: #fff; }
.io-tab.res.active .count { background: #16a34a; }
/* 底部外弧(Chrome 造型),颜色随页签背景走 */
.io-tab::before, .io-tab::after {
  content: ""; position: absolute; bottom: 0;
  width: 10px; height: 10px;
  color: transparent; transition: color 0.15s;
  pointer-events: none;
}
.io-tab.active::before, .io-tab.active::after { color: #fbfbfe; }
.io-tab::before {
  left: -10px;
  background: radial-gradient(circle at 0 0, transparent 10px, currentColor 10.5px);
}
.io-tab::after {
  right: -10px;
  background: radial-gradient(circle at 100% 0, transparent 10px, currentColor 10.5px);
}
/* 内容面板:与选中页签连体 */
.io-card {
  position: relative;
  z-index: 5;
  background: #fbfbfe;
  border: 1px solid var(--c-border, #e7e9f2);
  border-radius: 0 0 12px 12px;      /* 上方下圆:上缘由选中页签收口,与签宽天然对齐 */
  padding: 16px 18px 4px;
  margin-bottom: 18px;
}
/* Response 页状态码分组 */
.resp-specs { display: flex; flex-direction: column; gap: 14px; }
.resp-spec { display: flex; flex-direction: column; gap: 8px; }
.resp-spec-head { display: flex; align-items: center; gap: 8px; }
.resp-status-badge {
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  padding: 1px 8px; border-radius: 4px;
}
.resp-status-badge.ok { background: #d1fae5; color: #065f46; }
.resp-status-badge.err { background: #fee2e2; color: #991b1b; }
.resp-spec-desc { font-size: 11px; color: #64748b; }
.resp-spec-empty { font-size: 11.5px; color: #94a3b8; padding: 6px 0; }
/* 右栏响应契约分组 */
.resp-contract-group { display: flex; align-items: flex-start; gap: 6px; width: 100%; margin-bottom: 4px; }
.resp-contract-fields { flex: 1; display: flex; flex-direction: column; gap: 2px; }
/* Type C 折叠块(schema 未绑定字段) */
.typec-block {
  margin-top: 10px; padding: 6px 10px;
  border: 1px dashed #cbd5e1; border-radius: 8px;
  font-size: 11.5px; color: #64748b;
}
.typec-block summary { cursor: pointer; font-weight: 600; color: #475569; }
.typec-line { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
.typec-line code { font-family: var(--font-mono); font-size: 11px; color: #334155; }
.typec-path { font-family: var(--font-mono); font-size: 10px; color: #94a3b8; }
</style>
