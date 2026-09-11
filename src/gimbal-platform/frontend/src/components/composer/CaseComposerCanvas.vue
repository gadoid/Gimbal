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
        <div class="step-list" ref="stepListRef">
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
                <!-- 四区卡片(2026-09-08):左列全高拖拽把手(加大命中面积)+
                     右侧内容列 — ①名称行(序号+名+开关) ②meta 行(method/
                     service/carry 同行定高) ③path 独占行 ④功能控制行(复制/删除) -->
                <span class="step-handle" title="拖拽调整顺序">⠿</span>
                <div class="step-body">
                  <div class="step-main">
                    <div class="step-idx">{{ i + 1 }}</div>
                    <div class="step-name">{{ orch.steps[i]?.name || s.api?.path || 'step' }}</div>
                    <el-switch v-if="orch.steps[i]" v-model="orch.steps[i].enabled" size="small" @click.stop />
                  </div>
                  <div class="step-meta">
                    <span v-if="s.api?.method" class="method-badge" :class="`m-${s.api.method.toLowerCase()}`">{{ s.api.method }}</span>
                    <span v-if="s.api?.service" class="svc-tag">{{ s.api.service }}</span>
                    <!-- carry 只读提示:字段面∩值表非空才出现;悬停列键来源(服务绑定/全局默认);
                         与 method/service 同行定高(2026-09-08 免抖:预拉 /full 后点击不再补显) -->
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
                  <div v-if="s.api?.path" class="ep-path">{{ s.api.path }}</div>
                  <div class="step-actions">
                    <button class="step-act step-copy" @click.stop="copyStep(i)" title="复制此步骤(插入到紧随其后)">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                      复制
                    </button>
                    <button class="step-act step-del" @click.stop="removeStep(i)" title="删除">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
                      删除
                    </button>
                  </div>
                </div>
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
            <!-- 字段状态找回(2026-09-07 §2.2):独立于渲染树挂载 ——
                 全 carry 树空时也须可达(找回入口恰在最需要时不得消失) -->
            <el-form-item v-if="activeIoTab === 'request' && fieldSearchCorpus.length" label="字段状态">
              <FieldStateSearch
                :corpus="fieldSearchCorpus"
                @select="onSearchFieldState"
                @reset="onSearchFieldReset"
              />
            </el-form-item>
            <!-- body: 由 plate /full 目录实时驱动渲染树(会话级现拉,非持久快照;
                 §5 值×结构合并:行数跟 body、结构跟目录,carry 不进树) -->
            <el-form-item v-if="activeIoTab === 'request' && requestNodes.length" label="请求体 (由字段状态目录驱动)">
              <div class="field-form-wrap">
                <FieldForm
                  :nodes="requestNodes"
                  :body="currentStep.request.body || {}"
                  :field-actions="true"
                  :var-choices="referenceVarChoices"
                  :inject-choices="injectVarChoices"
                  :unbound-fields="reqTypeC"
                  :deep-extras="requestExtras"
                  :strategy-tags="requestStrategyTags"
                  :injected="requestInjected"
                  :extracted="requestExtracted"
                  :state-control="true"
                  :overlay="currentStep.field_states"
                  :query-badges="vsBadges"
                  @strategy-jump="onStrategyJump"
                  @update:body="(v: unknown) => currentStep.request.body = v"
                  @field-extract="(f) => onFieldExtract(f, 'request')"
                  @field-assign="(f, name) => onFieldAssign(f, name)"
                  @field-assert="(f) => onFieldAssert(f, 'request')"
                  @var-insert="onVarInsert"
                  @var-promote="onVarPromote"
                  @field-state="onFieldState"
                  @field-query="onFieldQuery"
                />
                <p class="field-form-hint">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                  来自 plate <code>/api/endpoint/.../full</code> 的字段状态目录
                  · {{ requestNodes.length }} 个顶层节点 · 行尾下拉切换 form/collapse/carry
                </p>
              </div>
            </el-form-item>
            <el-form-item v-else-if="activeIoTab === 'request' && currentFullState === 'loading' && hasEndpointRef(currentStep)" label="请求体">
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
              <span v-if="currentFullState === 'failed' && hasEndpointRef(currentStep)" class="hint">plate 不可达,字段表单暂不可用 — 已降级为 JSON 编辑</span>
              <span v-else class="hint">提示: 该接口未声明请求字段契约,或 plate 拉取中</span>
            </el-form-item>
            <!-- 请求侧 Type C(schema 有、binding 无)已并入 FieldForm「其他字段」
                 折叠区(unbound-fields) — 可见可编辑,不再单独设只读块。 -->
            <!-- Response 页:/full responses 全状态码契约,只读参考(设计 §3.1)。
                 ☰ 菜单仅 提取/断言 两项;提取/断言域感知 — 响应侧路径经
                 respPathOf → toScratchPath,请求侧见各自 handler 域分流 -->
            <template v-if="activeIoTab === 'response'">
              <div v-if="currentRespSpecs.length" class="resp-specs">
                <div v-for="spec in currentRespSpecs" :key="spec.status" class="resp-spec">
                  <div class="resp-spec-head">
                    <span class="resp-status-badge" :class="spec.status < 400 ? 'ok' : 'err'">{{ spec.status }}</span>
                    <span class="resp-spec-desc">{{ spec.description || '—' }}</span>
                  </div>
                  <!-- P7 渲染一致性:响应契约走树模式(contractTree 模板树,
                       与请求侧同构 — 嵌套容器/容器头角标/☰ 菜单齐平);
                       body=null → 叶值回落 binding.example 只读展示 -->
                  <FieldForm
                    v-if="spec.fields.length"
                    :nodes="spec.nodes"
                    :body="null"
                    :readonly="true"
                    :domain="'response'"
                    :field-actions="true"
                    :assertable="spec.assertable"
                    :strategy-tags="responseStrategyTags"
                    @strategy-jump="onStrategyJump"
                    @field-extract="(f) => onFieldExtract(f, 'response')"
                    @field-assert="(f) => onFieldAssert(f, 'response')"
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
                  :sibling-perturbs="siblingPerturbs"
                  :expand-when="jumpSeq > 0 && idx === jumpTargetIdx"
                  @remove="removeStrategy(currentStep, s)"
                  @exp-promote="onExpPromote(idx)"
                  @exp-restore="onExpRestore(idx)"
                  @exp-nav="onExpNav"
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
                        {{ strategyLabelOf(k.kind, k.label) }}<span class="strat-kind-tag">{{ k.kind }}</span>
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
    <!-- 动态取数源选择器(§7 一查多填):行集/列序/降级态由 Canvas 拉取后
         传入,选择器只做呈现与本地过滤 -->
    <ValueSourcePicker
      v-if="vsPicker.open"
      v-model="vsPicker.open"
      :view="vsPicker.group?.view ?? ''"
      :label="vsPicker.label"
      :columns="vsPicker.columns"
      :rows="vsPicker.rows"
      :truncated="vsPicker.truncated"
      :fetched-at="vsPicker.fetchedAt"
      :stale="vsPicker.stale"
      :loading="vsPicker.loading"
      :error="vsPicker.error"
      :param-fields="vsPicker.paramFields"
      :param-prefill="vsPicker.paramPrefill"
      @select="onVsSelect"
      @refresh="onVsRefresh"
      @query="onVsQuery"
      @back-params="vsPicker.error = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import draggable from 'vuedraggable'
import CaseComposerCatalog from './CaseComposerCatalog.vue'
import FieldForm from './FieldForm.vue'
import FieldStateSearch from './FieldStateSearch.vue'
import StrategyForm from './StrategyForm.vue'
import VariableRegistryPanel from './VariableRegistryPanel.vue'
import ConstantPoolPanel from './ConstantPoolPanel.vue'
import AuthSelectorModal from '../AuthSelectorModal.vue'
import VarSelectorModal from './VarSelectorModal.vue'
import ValueSourcePicker from './ValueSourcePicker.vue'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { useConstantsStore } from '@/stores/constants'
import { deriveVarRegistry } from '@/utils/var-registry'
import { expectVarNameOf, TPL_FULL_RE } from '@/utils/dataset-segments'
import {
  getFullEndpoint, listStrategyKinds, getStrategyKindFull, resolveResponsePaths,
  validateEndpointFieldStates,
} from '@/api/scenario-composer'
import { list as listAuths } from '@/api/auth_sessions'
import { getBindings as getCarryBindings, getDefaults as getCarryDefaults } from '@/api/carry'
import { fetchQueryViewIndex, fetchQueryViewRows } from '@/api/query-views'
import type { QueryViewIndexEntry } from '@/api/query-views'
import { ApiError } from '@/api/http'
import { parseTplRefs, refStatus } from '@/utils/tpl-refs'
import type { TplRef } from '@/utils/tpl-refs'
import type { AuthSession } from '@/api/auth_sessions'
import { deepDefaults, setByPath } from '@/utils/jsonpath'
import { toScratchPath } from '@/utils/scratch-path'
import { strategyLabelOf } from '@/utils/strategy-labels'
import {
  assertablePaths, buildTree, carryPaths, cascadeIncrements, containerSurface,
  contractTree, extraBodyPaths, extraSurfaceBindings, formBindings,
  groupValueSources, iterFlat, leafSurface, prefillBindings, responseBindings,
  searchCorpus, toTemplatePath,
} from '@/utils/declarations'
import type { FieldTreeNode, ValueSourceGroup } from '@/utils/declarations'
import { deriveBase } from '@/utils/service-alias'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import { carryHint } from '@/utils/carry-hint'
import type { CarrySource, CarryValues } from '@/utils/carry-hint'
import type {
  StepView, ExtractView, IOFieldBinding, EndpointFullView,
  StrategyView, StrategyKindView, StrategyKindDetailView, FieldState,
} from '@/types/plate'
import type { Orchestration, StepOrchestration } from '@/types/scenario-composer'
import { parseJson } from '../../utils/json'

const props = defineProps<{
  steps: StepView[]
  orchestration: Orchestration
  /** 场景服务声明 dict(config.services)—— 别名下拉/双写消费(spec §1.4) */
  services?: Record<string, string>
  /** 跨路由跳转消费(spec §5.3 期望列头→断言卡):挂载后一次性切步+定位 */
  focusJump?: { stepIdx: number; strategyIdx: number } | null
}>()
const emit = defineEmits<{
  'update:steps': [StepView[]]
  'update:orchestration': [Orchestration]
  /** 内联创建别名双写的声明面(config.services 整表替换) */
  'update:services': [Record<string, string>]
  'varPromote': [name: string, value: unknown]
  /** 期望还原上报(§5.2 逆动作):CaseComposer 删 config.vars 键 */
  'varDemote': [name: string]
  'seedVar': [name: string, spec: Record<string, unknown>],
  /** 断言卡"↗ 数据集"导航:跳列表页由 CaseComposer 落(不知具体 datasetId) */
  'expNav': [],
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

/** 当前 step 的请求目录(会话级按 endpoint_id 现拉 /full,不读持久化
 *  快照 — 旧 step.request.fields_meta 已废弃,不再作为数据源)。
 *  读 fullVersion 建立响应依赖:回填后树/reqTypeC 自动重算。 */
function stepDecls(step: StepView | undefined) {
  void fullVersion.value
  const eid = step?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)
  return endpointFullByEndpoint.get(eid)?.request?.declarations
}

/** 请求表单面平铺投影(解析态 != carry,先序)— reqTypeC 差集/描述
 *  索引消费;渲染树走 requestNodes(buildTree 值×结构合并,§5)。 */
function fieldBindings(step: StepView | undefined): IOFieldBinding[] {
  return formBindings(stepDecls(step), step?.field_states)
}

/** 请求体渲染树(§5.1 三输入:目录 + 意图 field_states + 值 body)。
 *  行数跟 body、结构跟目录;carry 不进树(值表整包注入零感知)。 */
const requestNodes = computed<FieldTreeNode[]>(() => {
  const step = currentStep.value
  return buildTree(stepDecls(step), step?.field_states, step?.request?.body)
})

/** 字段找回搜索语料(2026-09-07 §2.1):全量目录含 carry(carry 正是
 *  搜索语料,09-05 §5.4);仅请求签挂载(响应面 state 无视)。 */
const fieldSearchCorpus = computed(() =>
  searchCorpus(stepDecls(currentStep.value), currentStep.value?.field_states))

/** 「其他字段」区 body 残留行(§4:目录外深浅皆收,Canvas 投影单一真源) */
const requestExtras = computed(() =>
  extraBodyPaths(currentStep.value?.request?.body, stepDecls(currentStep.value), currentStep.value?.field_states))

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

/** 步骤流视口跟随(2026-09-08 6 卡滚动视口):选中/增删后选中卡滚入可视区
 *  (nearest — 已可见则不动,新增末卡/删除收紧时兜住选中项)。
 *  jsdom 无 scrollIntoView → 可选调用,挂载级测试零桩也稳。 */
const stepListRef = ref<HTMLElement | null>(null)
watch([activeStepIdx, () => local.length], ([idx]) => {
  void nextTick(() => {
    stepListRef.value?.querySelectorAll('.step-row')[idx]
      ?.scrollIntoView?.({ block: 'nearest' })
  })
})

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
 * 响应侧字段 → scratch 域路径(提取/断言共用):响应树与绑定面同源
 * (模板路径),字段自带的就是确定地址;运行时样本(resolve-paths,
 * 数组天然带 [idx])按字段名结尾命中时优先 — 比模板路径更贴近运行期
 * 真实形态。数组容器取整容器引用(元素级下标编排期不可知,模板态是
 * 接受的设计)。
 */
function respPathOf(f: IOFieldBinding): string {
  const sampleHit = samplePaths.value.find((p) => pathEndsWithField(p, f.name))
  return toScratchPath(sampleHit ?? f.path)
}

/**
 * 请求侧字段 → 响应断言位(仅断言用;请求侧提取走 requestBodyTargetOf
 * 取发出的请求体)。请求字段自身路径是请求域的,只能按字段名找响应
 * 断言位,且只信 plate 解析,不猜:
 * ① 运行时样本按字段名结尾 ② 字段路径恰好 ∈ assertable(同名同位)
 * ③ 惯例形状 $.data.<名>/$.<名> ④ 无命中 ''(宁空勿错 — B1c)
 */
function respPathByName(f: IOFieldBinding): string {
  const sampleHit = samplePaths.value.find((p) => pathEndsWithField(p, f.name))
  if (sampleHit) return toScratchPath(sampleHit)
  if (currentAssertable.value.includes(f.path)) return toScratchPath(f.path)
  const assertableHit = currentAssertable.value.find(
    (p) => p === `$.data.${f.name}` || p === `$.${f.name}`
  )
  if (assertableHit) return toScratchPath(assertableHit)
  return ''
}

/** plate 域路径是否以字段名结尾:$.a.b / $.a['b'] / $.a[0]['b'] */
function pathEndsWithField(p: string, fieldName: string): boolean {
  const escaped = fieldName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(?:\\.|\\[')${escaped}(?:'\\])?$`).test(p)
}

/**
 * 菜单"提取该字段"(域感知):request 侧提取**本步发出的请求体字段**
 * (after_request 时 scratch 已有 request_body — 整容器提出/下一步注入
 * 复用的既定工作流),表达式确定 = requestBodyTargetOf(与 assign target
 * 同源);response 侧走 respPathOf。target=字段名,scope=scenario。
 */
function onFieldExtract(f: IOFieldBinding, domain: 'request' | 'response') {
  if (!currentStep.value) return
  currentStep.value.strategy.push({
    kind: 'extract',
    target: f.name,
    expression: domain === 'request' ? requestBodyTargetOf(f.path) : respPathOf(f),
    scope: 'scenario',
    required: true,
  })
  justAddedStrategyIdx.value = currentStep.value.strategy.length - 1
}

/**
 * assign target 派生(单一真源,修轮 R1):`$.request_body` + 字段 rel 路径。
 * 根 list(Task 10)`$[0].sku` 剥后 rel 以 `[` 开头 → 前缀直拼无点
 * (`$.request_body[0].sku`);平铺/深层 `$.a[0].b` → `$.request_body.a[0].b`
 * (行为不变)。onFieldAssign 落 target 与 strategyMatchesField 匹配同走此处,
 * 双侧同式不漂移。
 */
function requestBodyTargetOf(path: string): string {
  const rel = path.replace(/^\$\.?/, '')
  return `$.request_body${rel.startsWith('[') ? '' : '.'}${rel}`
}

/** 菜单"向该字段动态注入"(P7 更名,原"注入响应变量"):assign 骨架(source=$.<name>,target=request_body.<path>) */
function onFieldAssign(f: IOFieldBinding, name: string) {
  if (!currentStep.value) return
  currentStep.value.strategy.push({
    kind: 'assign',
    source: `$.${name}`,
    target: requestBodyTargetOf(f.path),
    scope: 'scenario',
    required: true,
  })
  justAddedStrategyIdx.value = currentStep.value.strategy.length - 1
}

/** 菜单"断言该字段"(域感知):response 侧直取自身路径;request 侧按名
 *  找响应断言位。assertion 骨架(exists 起步,策略卡改 operator) */
function onFieldAssert(f: IOFieldBinding, domain: 'request' | 'response') {
  if (!currentStep.value) return
  currentStep.value.strategy.push({
    kind: 'assertion',
    target: domain === 'request' ? respPathByName(f) : respPathOf(f),
    operator: 'exists',
    expected: null,
    message: '',
    soft: false,
  })
  justAddedStrategyIdx.value = currentStep.value.strategy.length - 1
}

/** 菜单"引用共享变量":值写入(先清空再写入 ${var.x})已由 FieldForm
 *  完成,此处给引导提示 */
function onVarInsert(_f: IOFieldBinding, name: string) {
  ElMessage.success(`已插入 \${var.${name}}(启动前展开,查不到将拒启)`)
  warnMultiViewVar(name)
}

/** 菜单"设为变量":FieldForm 已完成值替换与命名,默认值上报 CaseComposer 登记 config.vars */
function onVarPromote(_f: IOFieldBinding, name: string, value: unknown) {
  emit('varPromote', name, value)
  ElMessage.success(`已设为变量 ${name} — 默认值登记到 ③ 共享变量,保存草稿后生效`)
  warnMultiViewVar(name)
}

/** §5.1 多视图前移提示:引用该 var 的字段,其端点声明 value_source 视图 >1
 *  → 软提示(§8.4 查钮将退化手输)。声明面复用 vs 查钮的既有分组查找
 *  (valueSourceGroups,onFieldQuery 同源 — 模板路径键控,剥 [i] 匹配)。 */
function warnMultiViewVar(name: string) {
  const step = currentStep.value
  if (!step) return
  const views = new Set<string>()
  const visit = (v: unknown, fullPath: string): void => {
    if (typeof v === 'string') {
      if (v === `\${var.${name}}`) {
        const tmpl = toTemplatePath(`$.${fullPath}`)
        const g = valueSourceGroups.value.find((x) => x.fields.some((f) => f.path === tmpl))
        if (g) views.add(g.view)
      }
    } else if (Array.isArray(v)) v.forEach((item, i) => visit(item, `${fullPath}[${i}]`))
    else if (v && typeof v === 'object') {
      for (const [k, child] of Object.entries(v)) visit(child, fullPath ? `${fullPath}.${k}` : k)
    }
  }
  visit(step.request?.body, '')
  if (views.size > 1) {
    ElMessage.warning(`同 var 多视图(${[...views].join('、')})— 数据集查钮将退化手输(§8.4);统一视图绑定或拆 var 名可解除`)
  }
}

// ── 期望变量提升(spec §5.2):断言卡动作行的值落地 ───────────────────
//    StrategyForm 只发事件,跨层动作(expected 模板化/还原 + varPromote/
//    varDemote 上抛)在此单一真源;命名用 Task 1 的 expectVarNameOf。

/** 期望提升(spec §5.2):expected → ${var.exp_*};撞名对话框改名,不静默 _2。
 *  手输名也过同一闸:改名后仍撞既有 var → 循环再问,直到唯一(不静默覆写)。 */
function onExpPromote(idx: number) {
  const step = currentStep.value
  if (!step) return
  const st = step.strategy[idx] as { expected?: unknown; target?: unknown }
  const base = expectVarNameOf(String(st.target ?? ''))
  const vars = (draftStore.draft?.definition?.config?.vars ?? {}) as Record<string, unknown>
  if (Object.prototype.hasOwnProperty.call(vars, base)) {
    void promptUniqueExpName(base, vars).then((name) => {
      if (name) applyExpPromote(st, name)
    })
    return
  }
  applyExpPromote(st, base)
}

/** 撞名改名循环(§5.2):prompt 直到名字不在 config.vars;空输入 = 取消;
 *  cancel → null。每轮把撞上的名字带进文案,用户看到的是具体冲突而非笼统报错。 */
async function promptUniqueExpName(
  base: string, vars: Record<string, unknown>,
): Promise<string | null> {
  let collided = base
  for (;;) {
    let value: string
    try {
      const r = await ElMessageBox.prompt(
        `期望变量 ${collided} 已存在(③ 共享变量里有同名键)。请换一个名字:`,
        '撞名 — 改名后继续',
        {
          confirmButtonText: '确定', cancelButtonText: '取消',
          inputPattern: /^[A-Za-z_][A-Za-z0-9_]*$/,
          inputErrorMessage: '变量名须以字母/下划线开头,仅含字母/数字/下划线',
        },
      )
      value = (r.value ?? '').trim()
    } catch {
      return null   // 取消 = 放弃提升(不静默选别的名)
    }
    if (!value) return null                       // 空输入视为取消
    if (!Object.prototype.hasOwnProperty.call(vars, value)) return value
    collided = value                              // 二次撞名:带着撞上的名字再问一轮
  }
}

function applyExpPromote(st: { expected?: unknown; target?: unknown }, name: string) {
  const baseline = st.expected ?? null
  ;(st as { expected?: unknown }).expected = `\${var.${name}}`
  emit('varPromote', name, baseline)
  ElMessage.success(`期望已模板化 \${var.${name}} — 数据集行可逐行供值;不挂数据集 = 基线`)
}

/** 逆动作:expected 写回基线字面量 + varDemote 删键;死键软提示(spec §5.2) */
function onExpRestore(idx: number) {
  const step = currentStep.value
  if (!step) return
  const st = step.strategy[idx] as { expected?: unknown }
  const m = TPL_FULL_RE.exec(String(st.expected ?? ''))
  if (!m) return
  const name = m[1]
  const vars = (draftStore.draft?.definition?.config?.vars ?? {}) as Record<string, unknown>
  st.expected = (vars[name] as unknown) ?? null
  emit('varDemote', name)
  ElMessage.warning(`已还原为字面量;数据集行若引用 ${name} 将成死键(运行无效果,可在编辑器看到提示)`)
}

/** 断言卡"↗ 数据集"导航:跳列表页由 CaseComposer 落(编排器不知具体 datasetId) */
function onExpNav() {
  emit('expNav')
}

// ── 字段状态控制(§5.4 + 2026-09-07 §2.3/§2.4)───────────────────────
//    行尾下拉与搜索框共用级联批量通路:状态意图落 step 顶层键,
//    与值回写两通路分离,不碰 request.body。

/**
 * 级联批量落地(§2.4,单事务):increments 键 → 目标态,null = 清除
 * 该条增量(↺ 重置,仅自身)。合并后空 → 整键删除(§3.1 空 step
 * 零存储)。写后即调 §3.5 校验(整批一次):errors 非空 = 拒,
 * **整批回滚**;warnings 仅提示;plate 不可达不阻塞编辑(保存链路兜底)。
 */
async function applyFieldStates(increments: Record<string, FieldState | null>) {
  const step = currentStep.value
  if (!step || !Object.keys(increments).length) return
  const before = step.field_states ? { ...step.field_states } : undefined
  const next: Record<string, FieldState> = { ...(step.field_states ?? {}) }
  for (const [p, s] of Object.entries(increments)) {
    if (s === null) delete next[p]
    else next[p] = s
  }
  if (Object.keys(next).length) step.field_states = next
  else delete step.field_states
  const eid = step.api?.view_hints?.endpoint_id
  if (!eid) return
  try {
    const verdict = await validateEndpointFieldStates(eid, step.field_states ?? {})
    if (verdict.errors.length) {
      if (before) step.field_states = before
      else delete step.field_states
      ElMessage.error(`字段状态被拒:${verdict.errors[0].message}`)
      return
    }
    if (verdict.warnings.length) {
      ElMessage.warning(verdict.warnings.map((w) => w.message).join(';\n'))
    }
  } catch {
    // 校验服务不可达 → 不阻塞编辑(§3.5 门禁在保存链路兜底)
  }
}

/**
 * 行尾下拉(§5.4):级联增量(§2.3 —— surface 拉起 carry 祖先落
 * collapse / sink 压平非 carry 子孙,行尾 carry 容器由此一次成功);
 * state = null = ↺ 重置(仅清该条增量)。
 */
async function onFieldState(path: string, state: FieldState | null) {
  const step = currentStep.value
  if (!step) return
  if (state === null) {
    await applyFieldStates({ [path]: null })
    return
  }
  await applyFieldStates(
    cascadeIncrements(stepDecls(step), step.field_states, path, state))
}

/** 搜索框(§2.2):命中行 select/reset —— 与行尾同通路,级联归此。 */
async function onSearchFieldState(path: string, target: FieldState) {
  await onFieldState(path, target)
}
async function onSearchFieldReset(path: string) {
  await onFieldState(path, null)
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

// ── 动态取数源(2026-09-07 spec §7):一查多填选择器状态机 ──────────

/** picker 全量状态(group 是扇出面:选行后按 g.fields 逐列落值)。 */
interface VsPickerState {
  open: boolean
  group: ValueSourceGroup | null
  /** 查钮点击字段的实例路径(数组语境锚:扇出写值沿它定位行实例) */
  anchorPath: string
  /** label 列名(= 投影行首键;行集到位后回填) */
  label: string
  /** 呈现列序(label 打头 + 绑定显式列;行集到位后回填) */
  columns: string[]
  rows: Array<Record<string, unknown>>
  truncated: boolean
  fetchedAt: string
  stale: boolean
  loading: boolean
  error: { code: string; message: string } | null
  /** §13.5 参数面:stage params→rows;params = 最近一次携参(refresh 复用) */
  stage: 'params' | 'rows'
  paramFields: string[]
  paramPrefill: Record<string, string>
  params: Record<string, string> | null
}
const vsPicker = reactive<VsPickerState>({
  open: false, group: null, anchorPath: '', label: '', columns: [], rows: [],
  truncated: false, fetchedAt: '', stale: false, loading: false, error: null,
  stage: 'rows', paramFields: [], paramPrefill: {}, params: null,
})

/** 已查字段来源徽标(§7.5):path → view + 取数时间(会话级线索,
 *  重查覆写;钉 view 不钉 group — 拆组是渲染层视角)。 */
const vsBadges = ref<Record<string, { view: string; fetchedAt?: string }>>({})

/** 当前 step 的 value_source 绑定分组(§7.3:group = vs.group || vs.view;
 *  两组同 view 各自打开选择器,前端不复用结果、不跨组覆写)。 */
const valueSourceGroups = computed<ValueSourceGroup[]>(() =>
  groupValueSources(stepDecls(currentStep.value)))

/** 同步骤扰动位(spec §5.3):当前步请求侧值整串 ${var.x} 的 var 名集 */
const siblingPerturbs = computed<string[]>(() => {
  const step = currentStep.value
  if (!step) return []
  const names = new Set<string>()
  const visit = (v: unknown): void => {
    if (typeof v === 'string') {
      const m = TPL_FULL_RE.exec(v)
      if (m) names.add(m[1])
    } else if (Array.isArray(v)) v.forEach(visit)
    else if (v && typeof v === 'object') Object.values(v).forEach(visit)
  }
  visit(step.request?.body)
  const headers = step.api?.headers
  if (headers && typeof headers === 'object') visit(headers)
  return [...names]
})

/**
 * 查询上下文(§7.2/§6.1):服务 URL 与查询别名同源于**当前 step** —
 * 服务 URL 走 authored services 声明(svc → URL 平表,Canvas 唯一可达的
 * URL 源);查询别名 = headers auth 引用首命中(修订 11)▸ 该服务同域的
 * users 条目(修订 10)。后端凭证闸把 alias=None 视作「无凭证」(bearer
 * 视图 422 query_credential_required)。
 */
function resolveQueryContext(step: StepView): { serviceUrl?: string; queryAlias: string | null } {
  const svc = step.api?.service || ''
  return {
    serviceUrl: declaredUrlOf(svc) || undefined,
    queryAlias: headerAuthTagOf(step) ?? queryAliasOf(svc),
  }
}

/** 查询别名·首选(§6.1 修订 11,2026-09-10 同域多用户裁定):当前 step
 *  headers 的 `${auth.<tag>.…}` 引用首命中 → 该 tag 即查询别名 —— headers
 *  引用就是该步执行身份的声明,查询视角 = 执行视角(构造消解恢复至每凭证
 *  粒度:为 B 的列查到的候选就是 B 能用的)。解析复用 utils/tpl-refs
 *  (悬空徽章同源);不校验域/存在性:悬空照发,后端诚实 422「未找到查询
 *  凭证」(悬空另有徽章显形,不回退猜测)。无引用 → null → 域内首键
 *  fallback(修订 10 行为,单用户场景零变化)。 */
function headerAuthTagOf(step: StepView): string | null {
  for (const v of Object.values(step.api?.headers ?? {})) {
    const ref = parseTplRefs(String(v ?? '')).find(r => r.domain === 'auth' && r.alias)
    if (ref?.alias) return ref.alias
  }
  return null
}

/** 查询别名(§6.1 修订 10,2026-09-10 多服务混编裁定:查询身份 = 执行
 *  身份的域内首键)= 与当前 step 服务**同域**的 users 条目,键序首命中
 *  (确定性;users 条目自带登录域 url)。单服务退化 = 同域唯一命中即
 *  首键,行为与修订 8 一致;组合期查询用执行账号,钉的值执行时必然查
 *  得到(§6.3 权限腐烂由构造消解)。零命中(该服务域没配用户,含条目
 *  缺 url)→ null 诚实 422 —— 不回退异域首键:错域 token 必被 SUT 拒,
 *  业务码 401/407 还会拉黑该凭证,污染其本域查询(§13.8 实证)。服务
 *  URL 自身未知 → 首键回退(服务侧 422 先炸,凭证侧无独立信号)。
 *  config.users 键与凭证池同一命名空间;池无该别名 → 后端诚实 422
 *  「未找到查询凭证」。 */
function queryAliasOf(svc: string): string | null {
  const users = draftStore.draft?.definition?.config?.users ?? {}
  const keys = Object.keys(users)
  const first = keys[0]?.trim() || null
  const origin = urlOriginOf(declaredUrlOf(svc))
  if (!origin) return first
  return keys.find(k => urlOriginOf(users[k]?.url) === origin) ?? null
}

/** url → origin(scheme+host+port 归一);空/非串/解析失败 → null。 */
function urlOriginOf(u: unknown): string | null {
  if (typeof u !== 'string' || !u) return null
  try { return new URL(u).origin } catch { return null }
}

/** 行集首键 = label 列(后端投影列序:label 恒行首;空行集不进选择态)。 */
function firstRowKeyLabel(row: Record<string, unknown>): string {
  return Object.keys(row)[0] ?? ''
}

/** 数组容器模板面(目录 type=array 条目 path)— 扇出写值的数组语境判据。 */
function arrayContainerTemplates(step: StepView | undefined): Set<string> {
  return new Set(
    iterFlat(stepDecls(step)).filter((e) => e.type === 'array' && !!e.path).map((e) => e.path))
}

/** 模板边界前缀($.a 是 $.a.b 的容器前缀;$.ab 不算 $.a 的)。 */
function underTmpl(t: string, prefix: string): boolean {
  return t === prefix || t.startsWith(prefix + '.')
}

/**
 * 点击行实例的数组语境:实例路径每个 [i] 段截出的容器实例前缀 →
 * 其模板前缀(buildNode 只在数组分支插 [i],故 [i] 即数组容器标记)。
 */
function arrayContextOf(instancePath: string): Map<string, string> {
  const ctx = new Map<string, string>()
  const re = /\[\d+\]/g
  for (let m = re.exec(instancePath); m; m = re.exec(instancePath)) {
    const inst = instancePath.slice(0, m.index + m[0].length)
    ctx.set(toTemplatePath(inst), inst)
  }
  return ctx
}

/**
 * 组字段写值路径(数组语境锚定):无数组祖先 → 模板即写值路径;最深
 * 数组祖先在点击行语境内 → 替换为点击行实例前缀(嵌套数组的浅层下标
 * 已含于实例前缀,最深一处替换即完备);在异数组容器下(无可导出
 * 实例)→ null = 跳过(同缺列,值保留)— 杜绝模板路径把数组物化成 dict。
 */
function anchorWritePath(
  tmpl: string, ctx: Map<string, string>, arrTmpls: Set<string>,
): string | null {
  const deepest = [...arrTmpls]
    .filter((c) => underTmpl(tmpl, c))
    .sort((a, b) => b.length - a.length)[0]
  if (!deepest) return tmpl
  const inst = ctx.get(deepest)
  return inst ? inst + tmpl.slice(deepest.length) : null
}

/** 查钮(§7.3):叶子绑定携带实例路径(数组行内含 [i]),分组键是
 *  模板路径 — 剥下标后匹配;命中 → 先定参数面(§13.5 索引)再开
 *  picker(锚定实例路径);无参视图直拉行集(现状零变化)。 */
async function onFieldQuery(field: IOFieldBinding) {
  const tmpl = toTemplatePath(field.path)
  const g = valueSourceGroups.value.find((x) => x.fields.some((f) => f.path === tmpl))
  if (!g || !currentStep.value) return
  vsPicker.group = g
  vsPicker.anchorPath = field.path
  await primeParamFace(g)          // §13.5:先定参数面(索引),再开选择器
  vsPicker.error = null            // R1 开壳清错:残错门控 template v-else 会困住参数面
  vsPicker.open = true
  if (!vsPicker.paramFields.length) void vsLoad(g, false, null)
}

/** §13.5 参数面:索引读 query_params;同名约定预填当前 step body 顶层
 *  字面量(模板串/空 → 留空手输 §13.6);索引不可达按无参处理(rows 侧降级)。 */
async function primeParamFace(g: ValueSourceGroup) {
  let entry: QueryViewIndexEntry | undefined
  try {
    const idx = await fetchQueryViewIndex()
    entry = idx.find((v) => v.name === g.view)
  } catch {
    entry = undefined
  }
  const fields = entry?.query_params ?? []
  vsPicker.paramFields = fields
  const prefill: Record<string, string> = {}
  for (const p of fields) {
    const v = (currentStep.value?.request?.body as Record<string, unknown> | undefined)?.[p]
    prefill[p] = typeof v === 'string'
      ? (v && !v.includes('${') ? v : '')
      : (typeof v === 'number' || typeof v === 'boolean') && v !== null ? String(v) : ''
  }
  vsPicker.paramPrefill = prefill
  vsPicker.stage = fields.length ? 'params' : 'rows'
}

/** 参数段确认(§13.5):空值剔除(未填 = 未供给,后端缺键 422 兜底)→ 携参拉数。 */
function onVsQuery(values: Record<string, string>) {
  if (!vsPicker.group) return
  const params: Record<string, string> = {}
  for (const [k, v] of Object.entries(values)) {
    const t = v.trim()
    if (t) params[k] = t
  }
  void vsLoad(vsPicker.group, false, params)
}

/** 刷新钮:bypass L1/L2 缓存重拉(§7.3 refresh=1;§13.5 复用最近携参)。 */
function onVsRefresh() {
  if (vsPicker.group) vsLoad(vsPicker.group, true, vsPicker.params)
}

/** 拉行集:呈现列 = 行首键 label + 绑定显式列;ApiError → 降级态(§7.5)。
 *  发起前清空上一组行集/列序 — 加载期不显示他组残留。 */
async function vsLoad(g: ValueSourceGroup, refresh: boolean, params: Record<string, string> | null) {
  const step = currentStep.value
  if (!step) return
  vsPicker.params = params
  vsPicker.loading = true
  vsPicker.error = null
  vsPicker.rows = []
  vsPicker.columns = []
  vsPicker.label = ''
  try {
    const ctx = resolveQueryContext(step)
    const res = await fetchQueryViewRows(g.view, {
      refresh, serviceUrl: ctx.serviceUrl, queryAlias: ctx.queryAlias,
      ...(params && Object.keys(params).length ? { params } : {}),
    })
    const label = firstRowKeyLabel(res.rows[0] ?? {})
    const cols = new Set<string>([label])
    for (const f of g.fields) if (f.column) cols.add(f.column)
    vsPicker.rows = res.rows
    vsPicker.label = label
    vsPicker.columns = [...cols]
    vsPicker.truncated = res.truncated
    vsPicker.fetchedAt = res.fetched_at
    vsPicker.stale = res.stale
  } catch (e) {
    vsPicker.error = e instanceof ApiError
      ? { code: String(e.code ?? ''), message: e.message }
      : { code: '', message: e instanceof Error ? e.message : String(e) }
  } finally {
    vsPicker.loading = false
  }
}

/**
 * 选行扇出(§7.3):组内字段逐列落值(column 空 = label 列 = 行首键);
 * 缺列跳过保留原值;组外/未绑定字段恒不被写;数组嵌套字段锚定点击行
 * 实例(异数组容器无实例可导 → 跳过同缺列)。徽标随落值字段同步亮起。
 */
function onVsSelect(row: Record<string, unknown>) {
  const g = vsPicker.group
  const step = currentStep.value
  if (!g || !step) return
  const ctx = arrayContextOf(vsPicker.anchorPath)
  const arrTmpls = arrayContainerTemplates(step)
  const body = JSON.parse(JSON.stringify(step.request.body ?? {}))
  const filled: Array<{ path: string }> = []
  for (const f of g.fields) {
    const col = f.column || firstRowKeyLabel(row)      // column 空 = label 列(= 行首键)
    if (row[col] === undefined || row[col] === null) continue   // 缺列跳过(§7.3)
    const writePath = anchorWritePath(f.path, ctx, arrTmpls)
    if (!writePath) continue                                    // 异数组不可锚 → 跳过
    setByPath(body, writePath.replace(/^\$\.?/, ''), row[col])
    // 徽标键 = 落值写路径(数组嵌套叶即实例路径 $.fees[0].cost_id)—
    // FieldForm 叶子行按实例路径查 queryBadges,与写值同径才亮(修轮 2)
    filled.push({ path: writePath })
  }
  step.request.body = body
  for (const { path } of filled) {
    vsBadges.value[path] = { view: g.view, fetchedAt: vsPicker.fetchedAt }
  }
  vsPicker.open = false
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
    if (sv.kind === 'assign') return sv.target === requestBodyTargetOf(f.path)
    // 请求侧提取(取发出的请求体)角标:expression 命中 $.request_body<path>
    if (sv.kind === 'extract') return sv.expression === requestBodyTargetOf(f.path)
    return false
  }
  const scratch = toScratchPath(f.path)
  if (sv.kind === 'extract') return sv.expression === scratch || sv.expression === f.path
  if (sv.kind === 'assertion') return sv.target === scratch || sv.target === f.path
  return false
}

/** 请求字段匹配面(§5 值×结构合并树继任 D9):树叶子 + 容器节点
 *  (实例路径,含数组行 [i];容器面 = 注入粒度 P6,整容器 assign 与
 *  叶子同式命中)+ 目录外残留合成行 — 注入只读态/请求侧策略角标按
 *  path 匹配全部复用;与 FieldForm 渲染同源(buildTree/extraBodyPaths
 *  单一真源),防键漂移。 */
function requestFieldSurface(step: StepView | undefined): IOFieldBinding[] {
  const decls = stepDecls(step)
  if (!decls) return []
  const fs = step?.field_states
  const tree = buildTree(decls, fs, step?.request?.body)
  return [
    ...leafSurface(tree),
    ...containerSurface(tree),
    ...extraSurfaceBindings(step?.request?.body, decls, fs),
  ]
}

/** 字段 path → 角标数组(key = 实例地址:数组行各得其所,name 行间共享
 *  会整列误挂);响应侧字段取全状态码契约(path 天然唯一)。 */
function fieldStrategyTags(domain: 'request' | 'response'): Record<string, Array<{ label: string; idx: number }>> {
  const step = currentStep.value
  if (!step?.strategy.length) return {}
  const labels = strategyTagLabels(step.strategy)
  const fields = domain === 'request'
    ? requestFieldSurface(step)
    : currentRespSpecs.value.flatMap((spec) => spec.fields)
  const tags: Record<string, Array<{ label: string; idx: number }>> = {}
  for (const f of fields) {
    step.strategy.forEach((s, idx) => {
      if (strategyMatchesField(s, domain, f)) {
        ;(tags[f.path] ||= []).push({ label: labels[idx], idx })
      }
    })
  }
  return tags
}

const requestStrategyTags = computed(() => fieldStrategyTags('request'))
const responseStrategyTags = computed(() => fieldStrategyTags('response'))

/** 请求体字段动态注入态(已注入 → FieldForm 值控件换只读提示条):
 *  仅 assign(写入才覆盖 — extract 只读取不锁值控件,提示另见
 *  requestExtracted)。与 fieldStrategyTags 同源同匹配(assign target
 *  精确命中 $.request_body<path> — 平铺/深层加点($.request_body.a.b),
 *  根 list 直拼无点($.request_body[0].sku,见 requestBodyTargetOf)),
 *  key = path(实例地址唯一;name 在数组行间共享会整列误标),携带
 *  source/target 供提示条悬停展示。响应侧无此概念(assign 不写响应)。 */
const requestInjected = computed<Record<string, Array<{ source: string; target: string }>>>(() => {
  const step = currentStep.value
  const out: Record<string, Array<{ source: string; target: string }>> = {}
  if (!step?.strategy.length) return out
  for (const f of requestFieldSurface(step)) {
    const hits = step.strategy.filter(
      (s) => s.kind === 'assign' && strategyMatchesField(s, 'request', f)
    ) as Array<{ source?: unknown; target?: unknown }>
    if (hits.length) {
      out[f.path] = hits.map((h) => ({ source: String(h.source ?? ''), target: String(h.target ?? '') }))
    }
  }
  return out
})

/** 请求体字段提取态(域感知提取,2026-09-05):expression 命中
 *  $.request_body<path> 的 extract → 携带 varName/expression 供提示
 *  悬停。提取运行时只读取不覆盖 — FieldForm 值控件保持可编辑,仅显
 *  「已提取」提示(与 assign 注入态的只读化分面,key 同为 path)。 */
const requestExtracted = computed<Record<string, Array<{ varName: string; expression: string }>>>(() => {
  const step = currentStep.value
  const out: Record<string, Array<{ varName: string; expression: string }>> = {}
  if (!step?.strategy.length) return out
  for (const f of requestFieldSurface(step)) {
    const hits = step.strategy.filter(
      (s) => s.kind === 'extract' && strategyMatchesField(s, 'request', f)
    ) as Array<{ target?: unknown; expression?: unknown }>
    if (hits.length) {
      out[f.path] = hits.map((h) => ({ varName: String(h.target ?? ''), expression: String(h.expression ?? '') }))
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

/** focusJump 一次性消费(spec §5.3):跨路由到达后切步 + 定位策略卡
 *  (sf-flash/展开复用 B4 角标跳转通路)。focusApplied 防重放 — 后续
 *  props 更新(父级 query 再变)不再触发,跳转语义是"到达即定位"。 */
let focusApplied = false
watch(() => props.focusJump, (j) => {
  if (!j || focusApplied) return
  focusApplied = true
  const maxIdx = Math.max(0, (props.steps?.length ?? 1) - 1)
  activeStepIdx.value = Math.min(Math.max(0, j.stepIdx), maxIdx)
  nextTick(() => onStrategyJump(Math.max(0, j.strategyIdx)))
}, { immediate: true })

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
/** 拉取失败端点记录(scoped 占位判定;Set 无响应性,经 fullVersion 触发重算) */
const fullFailed = new Set<string>()

/** 缓存 miss 时拉 /full 并回填(fail-soft:失败返回 undefined,消费方各自降级) */
function ensureEndpointFull(endpointId: string): Promise<EndpointFullView | undefined> {
  const cached = endpointFullByEndpoint.get(endpointId)
  if (cached) return Promise.resolve(cached)
  const inFlight = fullInFlight.get(endpointId)
  if (inFlight) return inFlight
  const p = getFullEndpoint(endpointId)
    .then((full) => {
      endpointFullByEndpoint.set(endpointId, full)
      fullVersion.value++
      return full
    })
    .catch(() => {
      fullFailed.add(endpointId)
      fullVersion.value++   // 失败也是状态变更:占位/徽标重算
      return undefined
    })
    .finally(() => fullInFlight.delete(endpointId))
  fullInFlight.set(endpointId, p)
  return p
}

/** 当前 step 的 /full 拉取状态(scoped,2026-09-08):预拉让全部端点并发,
 *  全局单值会跨端点串台(另一步失败盖到当前步头);改按当前端点判 —
 *  缓存命中 → '' / 失败记录 → failed / 其余(未回填)→ loading。 */
const currentFullState = computed<'loading' | 'failed' | ''>(() => {
  void fullVersion.value
  const eid = currentStep.value?.api?.view_hints?.endpoint_id
  if (!eid) return ''
  if (endpointFullByEndpoint.has(eid)) return ''
  return fullFailed.has(eid) ? 'failed' : 'loading'
})

/** 当前 step 的 /full 结构契约(拉取中/失败 → undefined) */
const currentFull = computed<EndpointFullView | undefined>(() => {
  void fullVersion.value
  const eid = currentStep.value?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)
  return endpointFullByEndpoint.get(eid)
})

/** carry 免抖预拉(2026-09-08):进页即拉全部 step 的 /full — 徽标从进页起
 *  即终值,点击卡片不再触发徽标补显(布局抖动根因)。同端点经会话缓存/
 *  in-flight 去重;这些请求原本在逐个点开时也要发,只是提前。 */
const stepEndpointIds = computed(() =>
  local.map((s) => s.api?.view_hints?.endpoint_id).filter((v): v is string => !!v))
watch(stepEndpointIds, (ids) => {
  for (const id of ids) void ensureEndpointFull(id)
}, { immediate: true })

/** 当前 step 的断言候选列表;未知/拉取中 → 空(不渲染 ▾)
 *  declarations 归一化后:view_only 通道 assertable=True 条目的 paths */
const currentAssertable = computed<string[]>(
  () => assertablePaths(currentFull.value?.responses?.['200']?.declarations)
)

/** /full responses[status] 轻量投影(设计 §2.4);引用数据不进 draft */
interface RespSpecLite {
  status: number
  description: string
  /** 全量条目投影(模板路径,含容器)— 角标/断言候选匹配面(§4 单脸) */
  fields: IOFieldBinding[]
  /** 响应契约树(P7):与请求侧同构的只读模板树(渲染面,state 无视) */
  nodes: FieldTreeNode[]
  /** plate 域路径,渲染 ✓ 标用;写策略时过 toScratchPath */
  assertable: string[]
  /** 200 契约 schema(Type C 差集源);非 200 恒 undefined */
  schema?: Record<string, unknown>
}
/** 当前 step 的全状态码响应契约(状态码字典序)
 *  响应面单脸:fields = 全量条目投影,state 不被读取(§4);
 *  assertable = 断言候选投影 */
const currentRespSpecs = computed<RespSpecLite[]>(() => {
  const full = currentFull.value
  if (!full) return []
  return Object.entries(full.responses || {})
    .map(([status, spec]) => ({
      status: Number(status),
      description: spec.description || '',
      fields: responseBindings(spec.declarations),
      nodes: contractTree(spec.declarations),
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
  const known = new Set(knownPaths.map((p) => p.replace(/^\$\.?/, '')))
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
 *  目录化后:解析态 carry 面 path 集(端点级读穿 — 值表跟共识默认走) */
const reqCarryPaths = computed<Set<string>>(() =>
  new Set(carryPaths(currentFull.value?.request?.declarations)))
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
    // 预填面:解析态 != carry 的浅层叶子(新步骤零增量 → 读共识默认);
    // 深层/数组子孙不落库(D7:深层默认只展示,防挡 carry 整包注入,
    // 模板路径落数组子孙会物化 dict 顶替 array 的错误形态)
    const fields = prefillBindings(full?.request?.declarations)
    const strategy = buildInitialStrategies(full)
    // 初始 body:只合成浅层 default/example(carry/契约默认移交注入通道)
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

/**
 * 控制行「复制」(2026-09-08):深拷贝 step + orch 元数据,插入紧随其后。
 * step 数据本体不可加字段(草稿原样进 /convert),JSON 深克隆即纯副本;
 * WeakMap 侧挂 key 对新对象按需分配,无需处理。
 */
function copyStep(i: number) {
  const clone = JSON.parse(JSON.stringify(local[i])) as StepView
  local.splice(i + 1, 0, clone)
  const name = orch.steps[i]?.name || local[i].api?.path || 'step'
  orch.steps.splice(i + 1, 0, {
    ...(orch.steps[i] ?? { enabled: true, name: '' }),
    name: `${name}(副本)`,
  })
  activeStepIdx.value = i + 1
  ElMessage.success(`已复制 step ${i + 1}(副本插入其后,可改名单独编排)`)
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

/* step list — 6 卡滚动视口(2026-09-08):>6 卡出滚动条,卡定高 90px;
   细滚动条 6px 圆角(进度条观感) */
.step-list {
  display: flex; flex-direction: column; gap: 6px; flex: 1;
  overflow-y: auto; min-height: 0;
  max-height: calc(6 * 90px + 5 * 6px);   /* 570px:6 卡 + 行间隙 */
  scrollbar-width: thin;
}
.step-list::-webkit-scrollbar { width: 6px; }
.step-list::-webkit-scrollbar-track { background: transparent; }
.step-list::-webkit-scrollbar-thumb {
  background: var(--c-border-strong, #cbd5e1); border-radius: 3px;
}
.step-list::-webkit-scrollbar-thumb:hover { background: var(--c-text-tertiary); }
/* draggable 容器接管行布局与行间距(行现在挂在这一层,不再直接挂 .step-list) */
.step-drag-area { display: flex; flex-direction: column; gap: 6px; }
/* 拖拽手柄:左列全高把手条(2026-09-08 加大命中面积 — 整条左缘 24×74
   皆可发起拖拽),grab 光标;仅手柄列可拖(handle 限定),
   行其余区域仍是点击选中 */
.step-handle {
  flex-shrink: 0;
  width: 24px;
  display: flex; align-items: center; justify-content: center;
  color: var(--c-border-strong, #cbd5e1);
  cursor: grab;
  font-size: 14px;
  line-height: 1;
  user-select: none;
  border-radius: 4px;
  margin-left: -2px;
}
.step-handle:active { cursor: grabbing; }
.step-row:hover .step-handle { color: var(--c-text-tertiary); }
.step-row.sortable-ghost { opacity: 0.4; border-style: dashed; }
/* 四区卡片(2026-09-08):左把手列 + 右内容列;定高 90px = 8pad + 名称行
   (flex≈20) + 3gap + meta 15 + 3gap + path 13 + 3gap + 控制行 17 + 8pad;
   定高同时是 6 卡视口计量基准与徽标补显免抖兜底 */
.step-row {
  display: flex; align-items: stretch; gap: 6px;
  height: 90px; box-sizing: border-box; overflow: hidden;
  padding: 8px 12px 8px 4px;
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
/* 内容列:名称/meta/path/控制 四行纵向 */
.step-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
/* ① 名称行:序号 + 名(ellipsis)+ 开关 */
.step-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; }
/* 序号圆徽:line-height 1 + border-box 消字体度量偏移(数字视觉居中);
   20px 直径撑足名称行,双位数也不挤 */
.step-idx {
  width: 20px; height: 20px; border-radius: 50%;
  box-sizing: border-box;
  background: var(--c-surface); color: var(--c-text-secondary);
  font-size: 11px; font-weight: 700; line-height: 1;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--c-border);
  flex-shrink: 0;
}
.step-row.active .step-idx {
  background: var(--c-accent);
  color: #fff; border-color: transparent;
}
.step-name { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; color: var(--c-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.step-row.active .step-name { color: var(--c-accent); }
/* ② meta 行:method/service/carry 同行定高(nowrap) */
.step-meta {
  display: flex; gap: 4px; align-items: center;
  height: 15px; min-width: 0;
  font-size: 10px; color: var(--c-text-secondary);
  flex-wrap: nowrap;
}
.method-badge, .svc-tag, .carry-badge {
  display: inline-flex; align-items: center;
  height: 15px; padding: 0 5px; border-radius: 3px;
  font-size: 9px; flex-shrink: 0; line-height: 1;
}
.method-badge { font-family: var(--font-mono); font-weight: 700; background: #f1f5f9; color: #475569; }
.method-badge.m-get { background: #dbeafe; color: #1e40af; }
.method-badge.m-post { background: #d1fae5; color: #065f46; }
.method-badge.m-put { background: #fef3c7; color: #92400e; }
.method-badge.m-delete { background: #fee2e2; color: #991b1b; }
.method-badge.m-patch { background: #f3e8ff; color: #6b21a8; }
/* carry 只读徽标:灰底中性色(platform 注入,编排器零感知,仅提示) */
.carry-badge {
  font-family: var(--font-mono); font-weight: 700;
  background: #e2e8f0; color: #64748b; cursor: default;
}
.svc-tag {
  background: #f1f5f9; color: #475569;
  max-width: 96px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* ③ path 独占行(2026-09-08):不再与 meta 挤一行,尾部截断;
   api-summary 里同名 span 沿用(行内 13px 定高不破坏其 flex 行) */
.ep-path {
  flex: 0 1 auto; min-width: 0; height: 13px; line-height: 13px;
  font-family: var(--font-mono); font-size: 10px; color: var(--c-text-tertiary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.step-row :deep(.el-switch) { transform: scale(0.8); }
/* ④ 功能控制行:复制/删除,幽灵文字按钮(无边框压进 17px 行高) */
.step-actions { height: 17px; display: flex; align-items: center; gap: 10px; }
.step-act {
  display: inline-flex; align-items: center; gap: 3px;
  background: transparent; border: none; padding: 0;
  font-size: 10px; font-family: inherit; line-height: 1;
  color: var(--c-text-tertiary); cursor: pointer;
  transition: color 0.15s;
}
.step-act:hover { color: var(--c-accent); }
.step-act.step-del:hover { color: #ef4444; }

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
