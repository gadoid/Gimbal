<!--
  FieldForm.vue —— 字段状态目录的渲染器(2026-09-05 spec §5 值×结构合并树)

  两种模式(互斥,由 props 决定):
  - 树模式(nodes):Canvas 请求体场景。buildTree(declarations.ts)产出
    四种节点,本组件递归渲染 ——
      叶子:目录叶子 × 实例路径(数组行内含 [i]),ui_kind 选控件
      对象:折叠面板(标题 = name,展开递归;collapse 态默认收起)
      数组:动态行组(行数跟 body、结构跟目录;加行 = 模板实例化空壳,
            行尾删除;支持 list 套 list)—— 同款区块折叠,头部行数常显
      开放字典:object 无 children(additionalProperties)→ KV 编辑器
            (区块折叠同款;三类区块 collapse 态默认收起,点击展开,
             加行/添键自动展开 —— 嵌套过长目录盖 collapse 治噪)
    三类容器区块头均带策略菜单(P3):提取/注入/断言作用于整容器值
    (目录化前整容器叶子的快捷入口;值写入类动作不适用 → structured 门控)
    collapse 的两副面孔:容器(对象/数组/字典)原地折叠面板;叶子
    不占直接渲染面,收进「已折叠字段」区(§5.4 折叠区 — 顶部汇总,
    展开编辑,行尾状态下拉可翻回 form;合成标量行随容器折叠,不收)。
    carry 不进树(值表整包注入,编排面零感知);深层残留不在此 ——
    「其他字段」区承接目录外 body 键(深浅皆收)。
  - 平铺模式(bindings):StrategyForm / 响应契约参考。IOFieldBinding[]
    直渲染叶子行,无树无 extras 深层扩展。

  值回写走 body(setValue + D8 深层清空剪枝);状态回写走 step.field_states
  (fieldState 事件上抛,§5.4 两通路分离)。行尾状态下拉 = 字段状态控制
  (form/collapse/carry;× 重置 = 清除该条增量,回落目录共识默认)。

  path 字段是 JSONPath(如 "$.customer_id" / "$.supplier[0].sku")—
  表单值通过 path 写入 body;typed 字段(number/boolean/select)的模板
  值支持:值为 ${var.x} 串时控件降级为 text 输入(浏览器 number input
  拒显非数字、checkbox/select 无法承载串值;运行期引擎对整串模板按
  变量原类型解析,前端只需可见可编辑)。
-->
<template>
  <div class="field-form">
    <template v-for="item in renderItems" :key="item.n ? item.n.path : item.f.path">

      <!-- ── 对象节点:折叠面板(§5.3)────────────────────────── -->
      <div v-if="item.n && item.n.kind === 'object'" class="obj-node">
        <div class="node-head">
          <button type="button" class="obj-toggle" @click="toggleSection(item.n)">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :class="{ open: isOpen(item.n) }"><polyline points="9 6 15 12 9 18"/></svg>
          </button>
          <span class="label-text">{{ item.n.entry.name }}</span>
          <span class="path-badge" :title="item.n.path">{{ item.n.path }}</span>
          <span v-if="item.n.entry.type" class="ui-tag k-json">{{ item.n.entry.type }}</span>
          <!-- P6:整容器策略角标/注入徽标 — 与叶子行同式(path 键控,
               assign target 命中 $.request_body<容器实例路径>) -->
          <button
            v-for="t in strategyTags?.[item.n.path] ?? []"
            :key="t.idx"
            type="button"
            class="strategy-tag"
            :title="`跳转到下方策略 ${t.label}`"
            @click.stop="emit('strategyJump', t.idx)"
          >{{ t.label }}</button>
          <span v-if="nodeInjected(item.n)" class="node-injected" :title="injectedTitle(nodeBinding(item.n))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
            <span>已注入 · 运行时覆盖整个区块</span>
          </span>
          <span v-if="nodeExtracted(item.n)" class="node-extracted" :title="extractedTitle(nodeBinding(item.n))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <span>已提取 · 运行时读取整个区块</span>
          </span>
          <FieldStateSelect
            v-if="stateControl"
            :state="item.n.state"
            :overlay="hasOverlay(item)"
            @change="(s) => emit('fieldState', templatePathOf(item), s)"
            @reset="() => emit('fieldState', templatePathOf(item), null)"
          />
          <!-- 容器级策略菜单(P3):提取/注入/断言作用于整容器值,
               恢复目录化前整容器叶子的快捷入口 -->
          <span v-if="fieldActions && item.n.path !== '$'" class="node-fa">
            <FieldActionMenu
              :field="nodeBinding(item.n)"
              structured
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :injected="nodeInjected(item.n)"
              :open="menuField === nodeBinding(item.n).name"
              @toggle="toggleMenu(nodeBinding(item.n))"
              @close="menuField = null"
              @field-extract="(field: IOFieldBinding) => emit('fieldExtract', field)"
              @field-assign="(field: IOFieldBinding, name: string) => emit('fieldAssign', field, name)"
              @field-assert="(field: IOFieldBinding) => emit('fieldAssert', field)"
            />
          </span>
        </div>
        <div v-show="isOpen(item.n)" class="obj-body" :class="{ 'body-locked': nodeInjected(item.n) }">
          <FieldForm
            nested
            :nodes="item.n.children"
            :body="body"
            :field-actions="fieldActions"
            :var-choices="varChoices"
            :inject-choices="injectChoices"
            :candidates="candidates"
            :readonly="readonly"
            :domain="domain"
            :assertable="assertable"
            :strategy-tags="strategyTags"
            :injected="injected"
            :state-control="stateControl"
            :overlay="overlay"
            @update:body="(v: any) => emit('update:body', v)"
            @strategy-jump="(i: number) => emit('strategyJump', i)"
            @field-extract="(f: IOFieldBinding) => emit('fieldExtract', f)"
            @field-assign="(f: IOFieldBinding, n: string) => emit('fieldAssign', f, n)"
            @field-assert="(f: IOFieldBinding) => emit('fieldAssert', f)"
            @var-insert="(f: IOFieldBinding, n: string) => emit('varInsert', f, n)"
            @var-promote="(f: IOFieldBinding, n: string, v: unknown) => emit('varPromote', f, n, v)"
            @field-state="(p: string, s: FieldState | null) => emit('fieldState', p, s)"
          />
        </div>
      </div>

      <!-- ── 数组节点:动态行组(§5.3;行数跟 body、结构跟目录;──────
           区块级折叠:与对象节点同机制,collapse 态默认收起,头部行数
           可见,点击展开;加行自动展开(P2)) -->
      <div v-else-if="item.n && item.n.kind === 'array'" class="arr-node">
        <div class="node-head">
          <button type="button" class="obj-toggle" @click="toggleSection(item.n)">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :class="{ open: isOpen(item.n) }"><polyline points="9 6 15 12 9 18"/></svg>
          </button>
          <span class="label-text">{{ item.n.entry.name }}</span>
          <span class="path-badge" :title="item.n.path">{{ item.n.path }}</span>
          <span class="ui-tag k-json">array</span>
          <span class="arr-count">{{ item.n.rows.length }} 行</span>
          <!-- P6:整容器策略角标/注入徽标(同对象节点) -->
          <button
            v-for="t in strategyTags?.[item.n.path] ?? []"
            :key="t.idx"
            type="button"
            class="strategy-tag"
            :title="`跳转到下方策略 ${t.label}`"
            @click.stop="emit('strategyJump', t.idx)"
          >{{ t.label }}</button>
          <span v-if="nodeInjected(item.n)" class="node-injected" :title="injectedTitle(nodeBinding(item.n))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
            <span>已注入 · 运行时覆盖整个区块</span>
          </span>
          <span v-if="nodeExtracted(item.n)" class="node-extracted" :title="extractedTitle(nodeBinding(item.n))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <span>已提取 · 运行时读取整个区块</span>
          </span>
          <FieldStateSelect
            v-if="stateControl"
            :state="item.n.state"
            :overlay="hasOverlay(item)"
            @change="(s) => emit('fieldState', templatePathOf(item), s)"
            @reset="() => emit('fieldState', templatePathOf(item), null)"
          />
          <!-- 容器级策略菜单(P3):整容器快捷策略入口(如 $.container
               整体提取/注入/断言),行组编辑不动 — 目录化前整容器叶子同款 -->
          <span v-if="fieldActions && item.n.path !== '$'" class="node-fa">
            <FieldActionMenu
              :field="nodeBinding(item.n)"
              structured
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :injected="nodeInjected(item.n)"
              :open="menuField === nodeBinding(item.n).name"
              @toggle="toggleMenu(nodeBinding(item.n))"
              @close="menuField = null"
              @field-extract="(field: IOFieldBinding) => emit('fieldExtract', field)"
              @field-assign="(field: IOFieldBinding, name: string) => emit('fieldAssign', field, name)"
              @field-assert="(field: IOFieldBinding) => emit('fieldAssert', field)"
            />
          </span>
          <!-- 注入态隐藏加行(I1 防编辑误导的容器面:写入必被覆盖) -->
          <button
            v-if="!readonly && !nodeInjected(item.n)"
            type="button"
            class="arr-add"
            title="同容器下一可用下标实例化模板空壳行"
            @click="addArrayRow(item.n)"
          >+ 加行</button>
        </div>
        <div v-show="isOpen(item.n)" class="arr-body" :class="{ 'body-locked': nodeInjected(item.n) }">
        <div v-for="(row, i) in item.n.rows" :key="i" class="arr-row">
          <span class="arr-idx">{{ i }}</span>
          <div class="arr-row-body">
            <FieldForm
              nested
              :nodes="row"
              :body="body"
              :field-actions="fieldActions"
              :var-choices="varChoices"
              :inject-choices="injectChoices"
              :candidates="candidates"
              :readonly="readonly"
              :domain="domain"
              :assertable="assertable"
              :strategy-tags="strategyTags"
              :injected="injected"
              :extracted="extracted"
              :state-control="stateControl"
              :overlay="overlay"
              @update:body="(v: any) => emit('update:body', v)"
              @strategy-jump="(i: number) => emit('strategyJump', i)"
              @field-extract="(f: IOFieldBinding) => emit('fieldExtract', f)"
              @field-assign="(f: IOFieldBinding, n: string) => emit('fieldAssign', f, n)"
              @field-assert="(f: IOFieldBinding) => emit('fieldAssert', f)"
              @var-insert="(f: IOFieldBinding, n: string) => emit('varInsert', f, n)"
              @var-promote="(f: IOFieldBinding, n: string, v: unknown) => emit('varPromote', f, n, v)"
              @field-state="(p: string, s: FieldState | null) => emit('fieldState', p, s)"
            />
          </div>
          <button
            v-if="!readonly"
            type="button"
            class="arr-del"
            title="删除该行(splice,后续行下标前移)"
            @click="removeArrayRow(item.n, i)"
          >×</button>
        </div>
        <p v-if="!item.n.rows.length" class="arr-empty">
          空数组 —「+ 加行」按目录模板实例化空壳行
        </p>
        </div>
      </div>

      <!-- ── 开放字典节点:KV 编辑器(§5.3)────────────────────── -->
      <div v-else-if="item.n && item.n.kind === 'dict'" class="dict-node">
        <div class="node-head">
          <button type="button" class="obj-toggle" @click="toggleSection(item.n)">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :class="{ open: isOpen(item.n) }"><polyline points="9 6 15 12 9 18"/></svg>
          </button>
          <span class="label-text">{{ item.n.entry.name }}</span>
          <span class="path-badge" :title="item.n.path">{{ item.n.path }}</span>
          <span class="ui-tag k-json">object</span>
          <span class="arr-count">{{ item.n.entries.length }} 键</span>
          <!-- P6:整容器策略角标/注入徽标(同对象/数组节点) -->
          <button
            v-for="t in strategyTags?.[item.n.path] ?? []"
            :key="t.idx"
            type="button"
            class="strategy-tag"
            :title="`跳转到下方策略 ${t.label}`"
            @click.stop="emit('strategyJump', t.idx)"
          >{{ t.label }}</button>
          <span v-if="nodeInjected(item.n)" class="node-injected" :title="injectedTitle(nodeBinding(item.n))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
            <span>已注入 · 运行时覆盖整个区块</span>
          </span>
          <span v-if="nodeExtracted(item.n)" class="node-extracted" :title="extractedTitle(nodeBinding(item.n))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <span>已提取 · 运行时读取整个区块</span>
          </span>
          <FieldStateSelect
            v-if="stateControl"
            :state="item.n.state"
            :overlay="hasOverlay(item)"
            @change="(s) => emit('fieldState', templatePathOf(item), s)"
            @reset="() => emit('fieldState', templatePathOf(item), null)"
          />
          <!-- 容器级策略菜单(P3):整字典快捷策略入口,同对象/数组区块 -->
          <span v-if="fieldActions && item.n.path !== '$'" class="node-fa">
            <FieldActionMenu
              :field="nodeBinding(item.n)"
              structured
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :injected="nodeInjected(item.n)"
              :open="menuField === nodeBinding(item.n).name"
              @toggle="toggleMenu(nodeBinding(item.n))"
              @close="menuField = null"
              @field-extract="(field: IOFieldBinding) => emit('fieldExtract', field)"
              @field-assign="(field: IOFieldBinding, name: string) => emit('fieldAssign', field, name)"
              @field-assert="(field: IOFieldBinding) => emit('fieldAssert', field)"
            />
          </span>
          <button
            v-if="!readonly && !nodeInjected(item.n)"
            type="button"
            class="arr-add"
            title="新增开放键(目录未声明,键自由命名)"
            @click="addDictKey(item.n)"
          >+ 添加键</button>
        </div>
        <div v-show="isOpen(item.n)" class="arr-body" :class="{ 'body-locked': nodeInjected(item.n) }">
        <div v-for="kv in dictKvs(item.n)" :key="kv.key" class="kv-row">
          <input
            type="text"
            class="kv-key"
            :value="kv.key"
            :disabled="readonly"
            @change="e => renameDictKey(kv.node, kv.key, (e.target as HTMLInputElement).value)"
          >
          <div class="kv-value">
            <textarea
              v-if="isStructured(kv.value)"
              class="ctl ctl-code"
              rows="3"
              :value="formatJson(kv.value)"
              :disabled="readonly"
              @input="e => setDictValue(kv.node, kv.key, parseJsonOrRaw((e.target as HTMLTextAreaElement).value))"
            />
            <input
              v-else
              type="text"
              class="ctl"
              :value="String(kv.value ?? '')"
              :disabled="readonly"
              @input="e => setDictValue(kv.node, kv.key, (e.target as HTMLInputElement).value)"
            >
          </div>
          <button
            v-if="!readonly"
            type="button"
            class="arr-del"
            title="删除该键"
            @click="removeDictKey(kv.node, kv.key)"
          >×</button>
        </div>
        <p v-if="!item.n.entries.length" class="arr-empty">空字典 —「+ 添加键」自由落键</p>
        </div>
      </div>

      <!-- ── 叶子节点:字段行(ui_kind 选控件,§5.3)──────────────
           v-else-if="item.f" 显式判别(vue-tsc 无法反演上方三个
           item.n && kind 守卫的合取否定;f 真值直接收窄叶子分支)。
           isFoldedLeaf 剪除:collapse 目录叶子不占直接渲染面(§5.4
           折叠区收纳;合成标量行随容器折叠,不剪) -->
      <div
        v-else-if="item.f && !isFoldedLeaf(item)"
        class="field"
        :class="['sk-' + item.f.source_kind, { required: item.f.required }]"
      >
      <label class="field-label">
        <span class="label-text">{{ item.f.name }}</span>
        <span v-if="item.f.required" class="req-mark">*</span>
        <!-- 深层字段 path 角标(D5):path ≠ $.+name(深层/别名)→ path 即治理线索;
             平铺字段维持灰 chip,零噪音 -->
        <span v-if="item.f.path !== '$.' + item.f.name" class="path-badge">{{ item.f.path }}</span>
        <span v-else class="field-path">{{ item.f.path }}</span>
        <span class="ui-tag" :class="`k-${item.f.ui_kind}`">{{ item.f.ui_kind }}</span>
        <span v-if="assertable?.includes(item.f.path)" class="assertable-mark" title="可断言字段">✓</span>
        <span class="src-tag" :class="`s-${item.f.source_kind}`">
          <template v-if="item.f.source_kind === 'independent'">literal</template>
          <template v-else-if="item.f.source_kind === 'lookup'">static · ${ var }</template>
          <template v-else-if="item.f.source_kind === 'generated'">dynamic · Assign</template>
          <template v-else>{{ item.f.source_kind }}</template>
        </span>
        <!-- 字段状态控制(§5.4):行尾状态下拉,写 step.field_states 增量
             (状态回写与值回写两通路分离) -->
        <FieldStateSelect
          v-if="stateControl"
          :state="stateOf(item)"
          :overlay="hasOverlay(item)"
          @change="(s) => emit('fieldState', templatePathOf(item), s)"
          @reset="() => emit('fieldState', templatePathOf(item), null)"
        />
        <button
          v-for="t in strategyTags?.[item.f.path] ?? []"
          :key="t.idx"
          type="button"
          class="strategy-tag"
          :title="`跳转到下方策略 ${t.label}`"
          @click.stop="emit('strategyJump', t.idx)"
        >{{ t.label }}</button>
      </label>
      <div class="field-control">
        <!-- 动态注入态(assign 覆盖值):只读提示条代替值控件 — 原值仍存
             body,策略失败且 onFailure=continue 时兜底出网(下行透出) -->
        <div v-if="isInjected(item.f)" class="ctl-injected-wrap">
          <div class="ctl-injected" :title="injectedTitle(item.f)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
            <span>已使用动态策略注入 · 运行时覆盖此值</span>
          </div>
          <FieldActionMenu
            v-if="fieldActions"
            :field="item.f"
            :value="String(getValue(item.f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :injected="true"
            :open="menuField === item.f.name"
            @toggle="toggleMenu(item.f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(item.f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>
        <!-- text / unknown (Type B fallback) -->
        <div v-else-if="item.f.ui_kind === 'text' || item.f.ui_kind === 'unknown'" class="ctl-with-var">
          <div class="ctl-cand-wrap">
            <input
              type="text"
              class="ctl"
              :value="getValue(item.f) as string"
              :placeholder="placeholderFor(item.f)"
              :disabled="readonly"
              @input="e => setValue(item.f, (e.target as HTMLInputElement).value)"
            />
            <!-- 候选下拉(#2 策略改造):assertion.target / extract.expression
                 从响应字段选 JSONPath,不手打。候选由调用方按字段名映射传入 -->
            <button
              v-if="candidatesFor(item.f).length"
              type="button"
              class="cand-btn"
              title="从候选值选择"
              @click="candOpenField = candOpenField === item.f.name ? null : item.f.name"
            >▾</button>
            <!-- 字段动作菜单(#4/#5 变量工作台):引用/提取/注入/断言。
                 fieldActions 门控 — 仅 Canvas 请求体场景传 -->
            <div v-if="candOpenField === item.f.name" class="cand-list">
              <button
                v-for="c in candidatesFor(item.f)"
                :key="c"
                type="button"
                class="cand-item"
                @click="applyCandidate(item.f, c)"
              >
                <code>{{ c }}</code>
              </button>
            </div>
            <FieldActionMenu
              v-if="fieldActions"
              :field="item.f"
              :value="String(getValue(item.f) ?? '')"
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :open="menuField === item.f.name"
              @toggle="toggleMenu(item.f)"
              @close="menuField = null"
              @var-insert="(name) => onMenuVarInsert(item.f, name)"
              @field-extract="(field) => emit('fieldExtract', field)"
              @field-assign="(field, name) => emit('fieldAssign', field, name)"
              @field-promote="(field) => onFieldPromote(field)"
              @field-assert="(field) => emit('fieldAssert', field)"
            />
          </div>
        </div>

        <!-- number(值为模板串 → 降级 text 输入,见文件头注释) -->
        <div v-else-if="item.f.ui_kind === 'number'" class="ctl-with-var">
          <div class="ctl-cand-wrap">
            <input
              v-if="isTpl(getValue(item.f))"
              type="text"
              class="ctl tpl"
              :value="getValue(item.f) as string"
              :placeholder="placeholderFor(item.f)"
              :disabled="readonly"
              @input="e => setValueTplNum(item.f, (e.target as HTMLInputElement).value)"
            />
            <input
              v-else
              type="number"
              class="ctl"
              :value="getValue(item.f) as number | string"
              :placeholder="placeholderFor(item.f)"
              :disabled="readonly"
              @input="e => setValueNum(item.f, e)"
            />
            <FieldActionMenu
              v-if="fieldActions"
              :field="item.f"
              :value="String(getValue(item.f) ?? '')"
              :var-choices="varChoices ?? []"
              :inject-choices="injectChoices ?? []"
              :domain="domain"
              :open="menuField === item.f.name"
              @toggle="toggleMenu(item.f)"
              @close="menuField = null"
              @var-insert="(name) => onMenuVarInsert(item.f, name)"
              @field-extract="(field) => emit('fieldExtract', field)"
              @field-assign="(field, name) => emit('fieldAssign', field, name)"
              @field-promote="(field) => onFieldPromote(field)"
              @field-assert="(field) => emit('fieldAssert', field)"
            />
          </div>
        </div>

        <!-- boolean(值为模板串 → 降级 text 输入) -->
        <div v-else-if="item.f.ui_kind === 'boolean'" class="ctl-with-var">
          <input
            v-if="isTpl(getValue(item.f))"
            type="text"
            class="ctl tpl"
            :value="getValue(item.f) as string"
            :placeholder="placeholderFor(item.f)"
            :disabled="readonly"
            @input="e => setValue(item.f, (e.target as HTMLInputElement).value)"
          />
          <label v-else class="ctl-bool">
            <input
              type="checkbox"
              :checked="Boolean(getValue(item.f))"
              :disabled="readonly"
              @change="e => setValue(item.f, (e.target as HTMLInputElement).checked)"
            />
            <span>{{ getValue(item.f) ? 'true' : 'false' }}</span>
          </label>
          <FieldActionMenu
            v-if="fieldActions"
            :field="item.f"
            :value="String(getValue(item.f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === item.f.name"
            @toggle="toggleMenu(item.f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(item.f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- select(值为模板串 → 降级 text 输入:选项列表不含模板值) -->
        <div v-else-if="item.f.ui_kind === 'select' && item.f.enum" class="ctl-with-var">
          <input
            v-if="isTpl(getValue(item.f))"
            type="text"
            class="ctl tpl"
            :value="getValue(item.f) as string"
            :placeholder="placeholderFor(item.f)"
            :disabled="readonly"
            @input="e => setValue(item.f, (e.target as HTMLInputElement).value)"
          />
          <select
            v-else
            class="ctl"
            :value="getValue(item.f) as string"
            :disabled="readonly"
            @change="e => setValue(item.f, (e.target as HTMLSelectElement).value)"
          >
            <option value="">— select —</option>
            <option v-for="opt in item.f.enum" :key="String(opt)" :value="String(opt)">{{ String(opt) }}</option>
          </select>
          <FieldActionMenu
            v-if="fieldActions"
            :field="item.f"
            :value="String(getValue(item.f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === item.f.name"
            @toggle="toggleMenu(item.f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(item.f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- textarea -->
        <div v-else-if="item.f.ui_kind === 'textarea'" class="ctl-with-var col">
          <textarea
            class="ctl ctl-area"
            rows="3"
            :value="getValue(item.f) as string"
            :placeholder="placeholderFor(item.f)"
            :disabled="readonly"
            @input="e => setValue(item.f, (e.target as HTMLTextAreaElement).value)"
          />
          <FieldActionMenu
            v-if="fieldActions"
            :field="item.f"
            :value="String(getValue(item.f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === item.f.name"
            @toggle="toggleMenu(item.f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(item.f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- json (dark code editor) -->
        <div v-else-if="item.f.ui_kind === 'json'" class="ctl-with-var col">
          <textarea
            class="ctl ctl-code"
            rows="4"
            :value="formatJson(getValue(item.f))"
            placeholder="JSON object"
            :disabled="readonly"
            @input="e => setValue(item.f, parseJsonOrRaw((e.target as HTMLTextAreaElement).value))"
          />
          <FieldActionMenu
            v-if="fieldActions"
            :field="item.f"
            :value="String(getValue(item.f) ?? '')"
            :var-choices="varChoices ?? []"
            :inject-choices="injectChoices ?? []"
            :domain="domain"
            :open="menuField === item.f.name"
            @toggle="toggleMenu(item.f)"
            @close="menuField = null"
            @var-insert="(name) => onMenuVarInsert(item.f, name)"
            @field-extract="(field) => emit('fieldExtract', field)"
            @field-assign="(field, name) => emit('fieldAssign', field, name)"
            @field-promote="(field) => onFieldPromote(field)"
            @field-assert="(field) => emit('fieldAssert', field)"
          />
        </div>

        <!-- file (placeholder) -->
        <div v-else-if="item.f.ui_kind === 'file' || item.f.ui_kind === 'binary'" class="ctl-file">
          <span class="file-tag">{{ item.f.ui_kind }}</span>
          <span class="file-hint">文件上传 — TODO</span>
        </div>

        <!-- unknown (Type B) — text fallback -->
        <input
          v-else
          type="text"
          class="ctl"
          :value="getValue(item.f) as string"
          :placeholder="placeholderFor(item.f)"
          @input="e => setValue(item.f, (e.target as HTMLInputElement).value)"
        />
      </div>
      <p v-if="item.f.description" class="field-desc">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        {{ item.f.description }}
      </p>
      <!-- 兜底原值行(注入态):策略失败且 onFailure=continue 时以此值发送 -->
      <p v-if="isInjected(item.f)" class="injected-fallback">
        原值 <code>{{ fallbackText(item.f) }}</code> · 策略失败且继续(continue)时以此发送
      </p>
      <!-- 提取提示行(域感知提取):运行时读取此值 → 变量;只读取不覆盖,
           值控件上方照常可编辑(与注入态的只读提示条分面) -->
      <p v-if="isExtracted(item.f)" class="extracted-hint" :title="extractedTitle(item.f)">
        已提取 → 变量 <code>{{ extractedVars(item.f) }}</code> · 运行时读取此值(可编辑)
      </p>
      </div>
    </template>

    <!-- 已折叠字段(§5.4 折叠区 = collapse):目录叶子解析态 collapse 不占
         直接渲染面,深浅皆收于此;展开编辑走同一 body 通路(setValue + D8
         剪枝),行尾状态下拉可翻回 form。容器(对象/数组/字典)collapse
         原地折叠面板,不进此区;合成标量行随容器折叠,亦不收。 -->
    <div v-if="!nested && foldedLeaves.length" class="folded" data-testid="folded-fields">
      <button type="button" class="folded-toggle" @click="foldedOpen = !foldedOpen">
        <span class="folded-arrow" :class="{ open: foldedOpen }">▸</span>
        <span class="folded-title">已折叠字段 · {{ foldedLeaves.length }}</span>
        <span class="folded-hint">折叠面板收纳 · 值仍在请求体</span>
      </button>
      <div v-if="foldedOpen" class="folded-body">
        <div v-for="r in foldedLeaves" :key="r.f.path" class="folded-row">
          <label class="folded-label">
            <span class="label-text">{{ r.f.path.replace(/^\$\.?/, '') }}</span>
            <span class="path-badge" :title="r.f.path">{{ r.f.path }}</span>
            <!-- P6:策略角标同叶子行(path 键控,跳转策略卡入口不因折叠丢) -->
            <button
              v-for="t in strategyTags?.[r.f.path] ?? []"
              :key="t.idx"
              type="button"
              class="strategy-tag"
              :title="`跳转到下方策略 ${t.label}`"
              @click.stop="emit('strategyJump', t.idx)"
            >{{ t.label }}</button>
            <FieldStateSelect
              v-if="stateControl"
              :state="r.lf.state"
              :overlay="overlay?.[r.lf.templatePath] !== undefined"
              @change="(s: FieldState) => emit('fieldState', r.lf.templatePath, s)"
              @reset="() => emit('fieldState', r.lf.templatePath, null)"
            />
          </label>
          <div class="folded-control">
            <!-- 注入只读态(同叶子行 I1):值控件换提示条 — 折叠不丢提示 -->
            <div v-if="isInjected(r.f)" class="ctl-injected-wrap">
              <div class="ctl-injected" :title="injectedTitle(r.f)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
                <span>已使用动态策略注入 · 运行时覆盖此值</span>
              </div>
            </div>
            <!-- 提取提示行(同叶子行):折叠不丢提示,值控件照常可编辑 -->
            <p v-else-if="isExtracted(r.f)" class="extracted-hint" :title="extractedTitle(r.f)">
              已提取 → 变量 <code>{{ extractedVars(r.f) }}</code> · 运行时读取此值(可编辑)
            </p>
            <!-- 控件随 ui_kind 分形(同叶子行惯例;typed 值为模板串 →
                 降级 text 输入,不拒显) -->
            <textarea
              v-else-if="r.f.ui_kind === 'json' || isStructured(getValue(r.f))"
              v-if="r.f.ui_kind === 'json' || isStructured(getValue(r.f))"
              class="ctl ctl-code"
              rows="3"
              :value="formatJson(getValue(r.f))"
              :placeholder="placeholderFor(r.f)"
              :disabled="readonly"
              @input="e => setValue(r.f, parseJsonOrRaw((e.target as HTMLTextAreaElement).value))"
            />
            <label v-else-if="r.f.ui_kind === 'boolean'" class="ctl-bool">
              <input
                type="checkbox"
                :checked="Boolean(getValue(r.f))"
                :disabled="readonly"
                @change="e => setValue(r.f, (e.target as HTMLInputElement).checked)"
              />
              <span>{{ getValue(r.f) ? 'true' : 'false' }}</span>
            </label>
            <input
              v-else-if="r.f.ui_kind === 'number' && !isTpl(getValue(r.f))"
              type="number"
              class="ctl"
              :value="getValue(r.f) as number | string"
              :placeholder="placeholderFor(r.f)"
              :disabled="readonly"
              @input="e => { const v = (e.target as HTMLInputElement).value; setValue(r.f, v === '' ? '' : Number(v)) }"
            />
            <select
              v-else-if="r.f.ui_kind === 'select' && r.f.enum && !isTpl(getValue(r.f))"
              class="ctl"
              :value="getValue(r.f) as string"
              :disabled="readonly"
              @change="e => setValue(r.f, (e.target as HTMLSelectElement).value)"
            >
              <option value="">— select —</option>
              <option v-for="opt in r.f.enum" :key="String(opt)" :value="String(opt)">{{ String(opt) }}</option>
            </select>
            <input
              v-else
              type="text"
              class="ctl"
              :value="getValue(r.f) as string"
              :placeholder="placeholderFor(r.f)"
              :disabled="readonly"
              @input="e => setValue(r.f, (e.target as HTMLInputElement).value)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 其他字段(§4:目录外 body 残留,深浅皆收 + 契约差集行)。树模式
         行集由 Canvas 投影(deepExtras = extraBodyPaths 单一真源);平铺
         模式维持顶层平铺键 − binding 根段(StrategyForm 复用不受影响)。
         实有键随请求发送;契约字段编辑即写入 body — 默认折叠。 -->
    <div v-if="!nested && extraRows.length" class="extras" data-testid="extra-fields">
      <button type="button" class="extras-toggle" @click="extrasOpen = !extrasOpen">
        <span class="extras-arrow" :class="{ open: extrasOpen }">▸</span>
        <span class="extras-title">其他字段 · {{ extraRows.length }}</span>
        <span class="extras-hint">不在接口目录中 · 已写入的随请求发送</span>
      </button>
      <div v-if="extrasOpen" class="extras-body">
        <div v-for="row in extraRows" :key="row.path" class="extra-row">
          <label class="extra-label">
            <span class="label-text">{{ row.key }}</span>
            <span class="field-path">{{ row.path }}</span>
            <span
              class="extra-src"
              :class="row.source"
              :title="row.source === 'schema'
                ? (row.inBody ? 'plate 契约声明,已写入请求体' : 'plate 契约声明;编辑后写入请求体')
                : '请求体实有键,随请求发送'"
            >{{ row.source === 'schema' ? '契约' : '实有' }}</span>
          </label>
          <div class="extra-control">
            <textarea
              v-if="isStructured(extraValue(row)) || row.type === 'object' || row.type === 'array'"
              class="ctl ctl-code"
              rows="3"
              :value="formatJson(extraValue(row))"
              :placeholder="extraPlaceholder(row)"
              :disabled="readonly"
              @input="e => setExtra(row, parseJsonOrRaw((e.target as HTMLTextAreaElement).value))"
            />
            <label v-else-if="row.type === 'boolean'" class="ctl-bool">
              <input
                type="checkbox"
                :checked="Boolean(extraValue(row))"
                :disabled="readonly"
                @change="e => setExtra(row, (e.target as HTMLInputElement).checked)"
              />
              <span>{{ extraValue(row) ? 'true' : 'false' }}</span>
            </label>
            <input
              v-else-if="row.type === 'number'"
              type="number"
              class="ctl"
              :value="extraValue(row) ?? ''"
              :placeholder="extraPlaceholder(row)"
              :disabled="readonly"
              @input="e => setExtra(row, (e.target as HTMLInputElement).value === '' ? '' : Number((e.target as HTMLInputElement).value))"
            />
            <input
              v-else
              type="text"
              class="ctl"
              :value="String(extraValue(row) ?? '')"
              :placeholder="extraPlaceholder(row)"
              :disabled="readonly"
              @input="e => setExtra(row, (e.target as HTMLInputElement).value)"
            />
            <button
              v-if="row.inBody"
              type="button"
              class="extra-del"
              title="从请求体移除该字段(深层清空连锁剪枝容器)"
              :disabled="readonly"
              @click="removeExtra(row)"
            >×</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FieldState, IOFieldBinding } from '@/types/plate'
import type { VarEntry } from '@/utils/var-registry'
import { getByPath, pruneByPath, setByPath } from '@/utils/jsonpath'
import type {
  FieldArrayNode, FieldDictNode, FieldLeafNode, FieldObjectNode, FieldTreeNode,
} from '@/utils/declarations'
import FieldActionMenu from './FieldActionMenu.vue'
import FieldStateSelect from './FieldStateSelect.vue'
import { parseJson } from '../../utils/json'

/** 递归内部标记:嵌套渲染不重复「其他字段」区/策略角标引导(顶层专属)。 */
const props = defineProps<{
  /** 平铺模式行集(StrategyForm / 响应契约参考);树模式不传。 */
  bindings?: IOFieldBinding[]
  /** 树模式节点集(Canvas 请求体:buildTree 产物,值×结构合并树 §5)。 */
  nodes?: FieldTreeNode[]
  body: any
  /**
   * 字段动作菜单门控(#4/#5 变量工作台):仅 Canvas 请求体场景传。
   * 开启后每个字段控件挂 ☰ 菜单(引用/提取/注入/断言);
   * StrategyForm 复用本组件处不传 → 模板零变化。
   */
  fieldActions?: boolean
  /** 引用子列表(config/数据集出身,插 ${var.x} 文本)— Canvas 传入 */
  varChoices?: VarEntry[]
  /** 注入子列表(extract 出身 + 时序门控 disabled 标记)— Canvas 传入 */
  injectChoices?: Array<VarEntry & { disabled?: boolean }>
  /**
   * 候选值映射(#2 策略改造):字段名 → 候选 JSONPath 列表。
   * 策略表单场景:assertion.target / extract.expression 从响应
   * assertable_fields 选,不手打;缺省无候选按钮。
   */
  candidates?: Record<string, string[]>
  /**
   * 只读门控(IO 双签卡片 Response 页):契约参考用 — 控件 disabled、
   * 不发 update:body;☰ 菜单保留(提取/断言仍可用)。
   */
  readonly?: boolean
  /**
   * 字段域(IO 双签卡片):'request'(默认四项菜单)|
   * 'response'(契约参考,菜单仅 提取/断言 两项)。
   */
  domain?: 'request' | 'response'
  /** 可断言字段的 plate 域路径列表(Response 页 ✓ 标线) */
  assertable?: string[]
  /**
   * plate 契约差集行(schema 有、目录渲染面无 — Canvas 的 reqTypeC):
   * 并入「其他字段」折叠区,可编辑;编辑即写入 body(未编辑不随请求发送)。
   */
  unboundFields?: Array<{ name: string; path: string; type?: string; default?: unknown }>
  /** 目录外 body 残留行(Canvas 投影:extraBodyPaths 单一真源,深浅皆收) */
  deepExtras?: Array<{ path: string; top: boolean }>
  /** 策略角标(需求1):字段 path → 角标数组(label 由 Canvas 预计算含编号,
   *  idx = step.strategy 数组下标);点击上抛 strategyJump 由 Canvas 定位
   *  下方策略卡。key = path(实例地址,唯一)— name 在数组行间共享会
   *  误挂全行;StrategyForm 复用本组件处不传 → 零角标。 */
  strategyTags?: Record<string, Array<{ label: string; idx: number }>>
  /** 请求体字段动态注入态(Canvas 传入):path → 命中的 assign 策略
   *  (source/target 供提示条悬停)。命中字段值被 assign 运行时覆盖 →
   *  值控件换只读提示条,原值降级为 continue 兜底(见 injected-fallback)。
   *  仅 assign(写入才覆盖;extract 只读取,另见 extracted)。
   *  StrategyForm/响应页复用处不传 → 零影响。 */
  injected?: Record<string, Array<{ source: string; target: string }>>
  /** 请求体字段提取态(Canvas 传入,域感知提取):path → 命中的 extract
   *  策略(varName/expression 供提示悬停)。提取运行时只读取不覆盖 →
   *  值控件保持可编辑,仅显「已提取」提示行;容器头徽标不锁体。
   *  复用处不传 → 零影响。 */
  extracted?: Record<string, Array<{ varName: string; expression: string }>>
  /** 字段状态控制门控(§5.4):行尾状态下拉写 step.field_states —
   *  仅 Canvas 请求体场景传;只读/响应/策略表单复用处不传 → 零控件。 */
  stateControl?: boolean
  /** step.field_states 增量(Canvas 传入):标记显式覆盖行(可重置)。 */
  overlay?: Record<string, FieldState>
  /** 递归内部标记(容器/行组嵌套渲染)— 外部调用方不传。 */
  nested?: boolean
}>()
const emit = defineEmits<{
  'update:body': [any]
  /** 策略角标点击(需求1):idx = step.strategy 数组下标,Canvas 定位策略卡 */
  'strategyJump': [idx: number]
  /** 快捷策略创建(菜单动作,Canvas 落地为策略骨架) */
  'fieldExtract': [field: IOFieldBinding]
  'fieldAssign': [field: IOFieldBinding, varName: string]
  'fieldAssert': [field: IOFieldBinding]
  /** 插入 ${var.<name>} 文本(原 Ⓥ 行为,Canvas 可用于引导提示) */
  'varInsert': [field: IOFieldBinding, name: string]
  /** 设为变量(D8 提升):值整串替换为 ${var.<name>},原值随事件上抛登记默认值 */
  'varPromote': [field: IOFieldBinding, name: string, value: unknown]
  /**
   * 字段状态控制(§5.4):path = 模板路径(增量 keyed 于目录态);
   * state = form/collapse/carry,null = 清除该条增量(重置回共识默认)。
   * Canvas 落地为 step.field_states 稀疏写入(§3.1)。
   */
  'fieldState': [path: string, state: FieldState | null]
}>()

// ─── 渲染行集:树模式(四节点)或平铺模式(叶子行)─────────────────

/** 判别联合:容器行(仅 n)/ 叶子行(f 必有)— v-else 叶子分支内
 *  item.f 由联合收窄保证非空,模板免逐一非空断言。 */
type RenderItem =
  | { n: FieldObjectNode | FieldArrayNode | FieldDictNode; f?: undefined; lf?: undefined }
  | { n?: undefined; f: IOFieldBinding; lf?: FieldLeafNode }

const renderItems = computed<RenderItem[]>(() => {
  if (props.nodes) {
    return props.nodes.map((n): RenderItem => {
      if (n.kind === 'leaf') return { f: n.binding, lf: n }
      return { n }
    })
  }
  return (props.bindings ?? []).map((f): RenderItem => ({ f }))
})

/** 字段状态控制辅助:解析态 / 模板路径 / 显式覆盖标记。 */
function stateOf(item: RenderItem): FieldState {
  return item.lf?.state ?? item.n?.state ?? 'form'
}
function templatePathOf(item: RenderItem): string {
  return item.lf?.templatePath ?? item.n?.templatePath ?? item.f?.path ?? ''
}
function hasOverlay(item: RenderItem): boolean {
  const p = templatePathOf(item)
  return !!p && props.overlay?.[p] !== undefined
}

// ─── 折叠区(§5.4 折叠区 = collapse):叶子收区,容器原地折叠 ──────

/** 折叠区叶子:目录叶子解析态 collapse → 不占直接渲染面,收进顶部
 *  「已折叠字段」区。合成标量行(synthetic)随所属数组容器原地折叠,
 *  不收 —— 收了会把折叠数组的行搬空(展开容器反而没行)。 */
function isFoldedLeaf(item: RenderItem): boolean {
  return item.lf?.state === 'collapse' && !item.lf.synthetic
}

/** 折叠区行集:全树收集 collapse 目录叶子(深浅皆收,文档序;仅顶层
 *  渲染区块 — 嵌套实例不重复收集)。 */
const foldedLeaves = computed<Array<{ lf: FieldLeafNode; f: IOFieldBinding }>>(() => {
  if (props.nested || !props.nodes) return []
  const out: Array<{ lf: FieldLeafNode; f: IOFieldBinding }> = []
  const walk = (ns: FieldTreeNode[]): void => {
    for (const n of ns) {
      if (n.kind === 'leaf') {
        if (n.state === 'collapse' && !n.synthetic) out.push({ lf: n, f: n.binding })
      } else if (n.kind === 'object') {
        walk(n.children)
      } else if (n.kind === 'array') {
        for (const row of n.rows) walk(row)
      }
    }
  }
  walk(props.nodes)
  return out
})

/** 折叠区默认收起(挂载即折,不跨步骤记忆 — 同「其他字段」约定) */
const foldedOpen = ref(false)

// ─── 区块折叠面板:开合状态(path 键控,跨 body 重算保持;────────────
//     对象/数组/开放字典三类区块共用;未见过 = 目录解析态默认:
//     collapse 收起,form 展开 —— 嵌套内容过长时目录盖 collapse,
//     需要时点击展开(2026-09-05 注入粒度 P2))

type SectionNode = FieldObjectNode | FieldArrayNode | FieldDictNode

const sectionOpen = ref<Record<string, boolean>>({})
function isOpen(n: SectionNode): boolean {
  const v = sectionOpen.value[n.path]
  return v === undefined ? n.state !== 'collapse' : v
}
function toggleSection(n: SectionNode) {
  sectionOpen.value[n.path] = !isOpen(n)
}

/**
 * 容器区块头策略菜单的合成载体:目录条目 → IOFieldBinding(path 用
 * 实例路径,行内嵌套容器如 $.container[1].box_no 与叶子同源寻址;
 * 2026-09-05 注入粒度 P3 —— 恢复目录化前整容器叶子的快捷策略入口,
 * 提取/注入/断言作用于整个容器值)。
 */
function nodeBinding(n: SectionNode): IOFieldBinding {
  return {
    name: n.entry.name,
    path: n.path,
    required: n.entry.required,
    default: n.entry.default ?? null,
    example: n.entry.example ?? null,
    description: n.entry.description,
    enum: n.entry.enum ?? null,
    ui_kind: n.entry.ui_kind,
    source_kind: n.entry.source_kind,
  }
}

/**
 * 整容器注入态(2026-09-05 注入粒度 P6):assign target 命中容器实例
 * 路径(Canvas requestInjected 键,path 键控与叶子同源)— 头部徽标 +
 * 体锁定 + 菜单值写入项禁用,叶子行 I1 只读语义的容器面继任。
 */
function nodeInjected(n: SectionNode): boolean {
  return isInjected(nodeBinding(n))
}

/** 整容器提取态:extract expression 命中容器实例路径 — 头部绿色徽标,
 *  不锁体不藏加行(提取只读取,与 P6 注入徽标的锁定面分家) */
function nodeExtracted(n: SectionNode): boolean {
  return isExtracted(nodeBinding(n))
}

// ─── 数组行组:加行(模板空壳)/删行(splice,§5.3 行尾删除)────────

/** body 浅拷贝(数组根保形):数组根 spread 保数组性 — 对象 spread
 *  {...body} 会把数组洗成 {0:…} 数字键对象;空 body 按 rel 首段形态
 *  建容器:`[` 开头建 [],否则 {}。 */
function copyBody(rel: string): any {
  if (Array.isArray(props.body)) return [...props.body]
  if (props.body && typeof props.body === 'object') return { ...props.body }
  return rel.startsWith('[') ? [] : {}
}

function addArrayRow(n: FieldArrayNode) {
  if (props.readonly) return
  const rel = n.path.replace(/^\$\.?/, '')
  const next = copyBody(rel)
  const cur = getByPath(next, rel)
  const arr = Array.isArray(cur) ? cur : []
  // 模板实例化空壳(§5.2):对象模板 → {};嵌套数组模板 → [](行内递归);
  // 标量数组(无模板)→ 标量空壳 ''(push {} 会洗掉字符串数组的标量性)
  arr.push(
    n.templates.length
      ? (n.templates[0].type === 'array' ? [] : {})
      : '',
  )
  setByPath(next, rel, arr)
  sectionOpen.value[n.path] = true   // 加行自动展开:新行立即可见
  emit('update:body', next)
}

function removeArrayRow(n: FieldArrayNode, i: number) {
  if (props.readonly) return
  const rel = n.path.replace(/^\$\.?/, '')
  const next = copyBody(rel)
  const arr = getByPath(next, rel)
  if (!Array.isArray(arr)) return
  arr.splice(i, 1) // 行删除 = splice(下标前移;与清空剪枝 pruneByPath 语义分流)
  setByPath(next, rel, arr)
  emit('update:body', next)
}

// ─── 开放字典:KV 编辑器(§5.3;键重命名/删键/添键整字典回写)──────

function writeDict(
  n: FieldDictNode,
  mutator: (o: Record<string, unknown>) => void,
) {
  if (props.readonly) return
  const rel = n.path.replace(/^\$\.?/, '')
  const cur = getByPath(props.body, rel)
  const o: Record<string, unknown> =
    cur && typeof cur === 'object' && !Array.isArray(cur)
      ? { ...(cur as Record<string, unknown>) }
      : {}
  mutator(o)
  if (!rel) {
    emit('update:body', o) // 根字典:next 即对象本体(setByPath 空 rel no-op)
    return
  }
  const next = copyBody(rel)
  setByPath(next, rel, o)
  emit('update:body', next)
}

/** dict KV 行绑定:收窄后的 dict 节点随行携带 —— 嵌套 v-for 的行内
 *  事件闭包里 item.n 的属性收窄不传播(vue-tsc 降回容器联合),
 *  kv.node 静态定型 FieldDictNode 即免收窄。 */
function dictKvs(n: FieldObjectNode | FieldArrayNode | FieldDictNode): Array<{
  node: FieldDictNode; key: string; value: unknown
}> {
  return n.kind === 'dict'
    ? n.entries.map((kv) => ({ node: n, ...kv }))
    : []
}

function setDictValue(n: FieldDictNode, key: string, val: unknown) {
  writeDict(n, (o) => { o[key] = val })
}

function renameDictKey(n: FieldDictNode, oldKey: string, newKey: string) {
  const k = newKey.trim()
  if (!k || k === oldKey) return
  writeDict(n, (o) => {
    if (!(oldKey in o) || k in o) return
    o[k] = o[oldKey]
    delete o[oldKey]
  })
}

function removeDictKey(n: FieldDictNode, key: string) {
  writeDict(n, (o) => { delete o[key] })
}

function addDictKey(n: FieldDictNode) {
  writeDict(n, (o) => {
    let base = 'key'
    let i = 2
    while (base in o) base = `key_${i++}`
    o[base] = ''
  })
  sectionOpen.value[n.path] = true   // 添键自动展开:新键行立即可见
}

// ─── 候选下拉 / 动作菜单 / 变量插入(既有行为,平移)────────────────

/** 候选下拉开合状态(同屏至多一个)— 存字段名而非对象引用:
 *  props.bindings 被 Vue 包 reactive proxy,v-for 元素与原始对象
 *  === 不等(菜单 menuField 踩过同坑,存 name 后列表才能展开) */
const candOpenField = ref<string | null>(null)
function candidatesFor(f: IOFieldBinding): string[] {
  return props.candidates?.[f.name] ?? []
}
function applyCandidate(f: IOFieldBinding, c: string) {
  setValue(f, c)
  candOpenField.value = null
}

/**
 * 字段动作菜单开合状态(同屏至多一个;与候选下拉互斥)。
 * 存字段名而非对象引用 — props.bindings 会被 Vue 包 reactive proxy,
 * v-for 元素与调用方原始对象引用不等(=== 失败,菜单不开)。
 */
const menuField = ref<string | null>(null)
function toggleMenu(f: IOFieldBinding) {
  candOpenField.value = null
  menuField.value = menuField.value === f.name ? null : f.name
}

/**
 * 菜单"引用共享变量"插值:字符串现值追加(部分模板 ORD-${var.x});
 * 非字符串(number/boolean)或空值整串替换 — String(5) 拼出
 * '5${var.x}' 是垃圾值,typed 字段模板只能整串。
 */
function onMenuVarInsert(f: IOFieldBinding, name: string) {
  const cur = getValue(f)
  const tpl = `\${var.${name}}`
  setValue(f, typeof cur === 'string' && cur !== '' ? cur + tpl : tpl)
  emit('varInsert', f, name)
  menuField.value = null
}

/**
 * 菜单"设为变量"(D8 提升语义):与"引用共享变量"的**追加**不同 —
 * ① 值整串替换为 ${var.<name>};② 变量名默认取字段名,同名(共享
 * 变量/extract 任一出身)自动加 _2/_3 后缀;③ 原值随 varPromote
 * 上抛,由 Canvas → CaseComposer 登记进 definition.config.vars。
 */
function onFieldPromote(f: IOFieldBinding) {
  const original = getValue(f)
  const base = f.name.replace(/[^A-Za-z0-9_.]/g, '_').replace(/^_+|_+$/g, '') || 'var'
  const taken = new Set([
    ...(props.varChoices ?? []).map((v) => v.name),
    ...(props.injectChoices ?? []).map((v) => v.name),
  ])
  let name = base
  let n = 2
  while (taken.has(name)) name = `${base}_${n++}`
  setValue(f, `\${var.${name}}`)
  emit('varPromote', f, name, original)
  menuField.value = null
}

/**
 * 值是否为模板串(${...})— number/boolean/select 控件遇模板降级
 * text 输入:number input 拒显非数字、checkbox/select 无法承载串值。
 * 运行期引擎(resolve_template)对整串模板按变量原类型解析,合法。
 */
function isTpl(v: unknown): boolean {
  return typeof v === 'string' && v.includes('${')
}

/** 动态注入态:该字段命中 assign(target=$.request_body.<path>)→ 值控件只读化
 *  (key = path:数组行实例各得其所,name 在行间共享会整列误标) */
function isInjected(f: IOFieldBinding): boolean {
  return (props.injected?.[f.path]?.length ?? 0) > 0
}

/** 提示条悬停:命中策略的 source → target(多条全列) */
function injectedTitle(f: IOFieldBinding): string {
  return (props.injected?.[f.path] ?? [])
    .map((h) => `${h.source} → ${h.target}`)
    .join('\n')
}

/** 提取态(域感知提取,2026-09-05):该字段命中 extract(expression=
 *  $.request_body<path>,Canvas requestExtracted 键)→ 值控件保持可编辑
 *  (提取只读取),提示行标"运行时读取此值"(与 assign 注入态只读化分面) */
function isExtracted(f: IOFieldBinding): boolean {
  return (props.extracted?.[f.path]?.length ?? 0) > 0
}

/** 提取提示悬停:命中策略的 expression → 变量名(多条全列) */
function extractedTitle(f: IOFieldBinding): string {
  return (props.extracted?.[f.path] ?? [])
    .map((h) => `${h.expression} → ${h.varName}`)
    .join('\n')
}

/** 提取提示行内变量名串(多条 · 连接) */
function extractedVars(f: IOFieldBinding): string {
  return (props.extracted?.[f.path] ?? []).map((h) => h.varName).join('、')
}

/** 兜底原值展示:空 → (空);对象 JSON 化;长值靠 CSS 截断 */
function fallbackText(f: IOFieldBinding): string {
  const v = getValue(f)
  if (v === '' || v === null || v === undefined) return '(空)'
  return typeof v === 'object' ? JSON.stringify(v) : String(v)
}

/** number 控件输入:清空存 ''(对齐「其他字段」分支约定,不落幻影 0) */
function setValueNum(f: IOFieldBinding, e: Event) {
  const v = (e.target as HTMLInputElement).value
  setValue(f, v === '' ? '' : Number(v))
}

/** number 字段模板态输入:纯数字串回归 number;模板/混排保持字符串 */
function setValueTplNum(f: IOFieldBinding, v: string) {
  if (v !== '' && !isTpl(v) && !Number.isNaN(Number(v))) {
    setValue(f, Number(v))
    return
  }
  setValue(f, v)
}

// ─── 「其他字段」区(§4:目录外 body 残留深浅皆收 + 契约差集)────────

/**
 * 其他字段行视图:
 * - 树模式:deepExtras(Canvas 投影的目录外 body 残留,深浅皆收)+
 *   unboundFields(契约差集行)按 path 去重合并(body 实有的契约键
 *   归并为 schema 行 inBody=true,旧语义保持);
 * - 平铺模式:body 顶层键 − binding 根段 + unboundFields(StrategyForm
 *   复用路径,行为与旧版一致)。
 * source=行来源标签;inBody=是否已写入 body(决定随请求发送 + 可删除)。
 */
interface ExtraRowView {
  key: string
  path: string
  source: 'body' | 'schema'
  inBody: boolean
  /** schema 声明类型(body 实有行无) — 控件按此渲染:boolean 勾选/number 数字框/object·array JSON 域 */
  type?: string
  /** schema 默认值(契约行):未写入 body 时以 placeholder 透出,编辑写入 */
  default?: unknown
}

const extraRows = computed<ExtraRowView[]>(() => {
  if (props.nested) return []
  const relOf = (p: string) => p.replace(/^\$\.?/, '')
  const rows: ExtraRowView[] = []
  if (props.nodes) {
    const byPath = new Map<string, ExtraRowView>()
    for (const r of props.deepExtras ?? []) {
      const row: ExtraRowView = {
        key: relOf(r.path), path: r.path, source: 'body', inBody: true,
      }
      byPath.set(r.path, row)
      rows.push(row)
    }
    for (const f of props.unboundFields ?? []) {
      const p = f.path || `$.${f.name}`
      const ex = byPath.get(p)
      if (ex) {
        // 契约键已被 body 实有 → 归并为契约行(旧 dedupe 语义)
        ex.source = 'schema'
        ex.type = f.type
        ex.default = f.default
        continue
      }
      rows.push({
        key: relOf(p), path: p, source: 'schema', inBody: false,
        type: f.type, default: f.default,
      })
    }
    return rows
  }
  // 平铺模式(StrategyForm / 无目录步骤):顶层平铺键 − binding 根段
  const bodyObj =
    props.body && typeof props.body === 'object' && !Array.isArray(props.body)
      ? (props.body as Record<string, unknown>)
      : null
  // binding 覆盖面的根段(数组下标不拆根,容器整体归入覆盖面)
  const roots = new Set(
    (props.bindings ?? []).map((b) => b.path.replace(/^\$\.?/, '').split(/[.[\]]/)[0]),
  )
  const schemaTypes = new Map(
    (props.unboundFields ?? []).map((f) => [f.name, f.type ?? 'string']),
  )
  for (const k of bodyObj ? Object.keys(bodyObj) : []) {
    if (roots.has(k)) continue
    rows.push({
      key: k, path: `$.${k}`,
      source: schemaTypes.has(k) ? 'schema' : 'body',
      inBody: true, type: schemaTypes.get(k),
    })
  }
  const schemaDefaults = new Map(
    (props.unboundFields ?? []).map((f) => [f.name, f.default]),
  )
  for (const f of props.unboundFields ?? []) {
    if (bodyObj && f.name in bodyObj) continue
    if (roots.has(f.name)) continue
    rows.push({
      key: f.name, path: f.path || `$.${f.name}`,
      source: 'schema', inBody: false,
      type: f.type ?? 'string', default: schemaDefaults.get(f.name),
    })
  }
  return rows
})

/** 折叠区默认收起(挂载即折叠,不跨步骤记忆) */
const extrasOpen = ref(false)

function extraValue(row: ExtraRowView): unknown {
  return getByPath(props.body, row.path.replace(/^\$\.?/, ''))
}

/** 结构值(对象/数组)走 JSON 域,其余按原始值文本编辑(未声明 → 类型未知,text 是诚实兜底) */
function isStructured(v: unknown): boolean {
  return typeof v === 'object' && v !== null
}

function setExtra(row: ExtraRowView, val: unknown) {
  if (props.readonly) return
  const rel = row.path.replace(/^\$\.?/, '')
  const next = copyBody(rel)
  setByPath(next, rel, val)
  emit('update:body', next)
}

function removeExtra(row: ExtraRowView) {
  if (props.readonly) return
  const rel = row.path.replace(/^\$\.?/, '')
  const next = copyBody(rel)
  pruneByPath(next, rel) // 深层残留删除连锁剪枝空容器(D8 同款)
  emit('update:body', next)
}

/** 契约行未写入时以 schema 默认值作 placeholder(灰字提示 ≠ 值,不随请求发送) */
function extraPlaceholder(row: ExtraRowView): string {
  if (row.inBody || row.default === undefined || row.default === null) return ''
  if (typeof row.default === 'object') return JSON.stringify(row.default, null, 2)
  return String(row.default)
}

// ─── 值读写(path 寻址;深层清空 D8 剪枝)────────────────────────────

function getValue(f: IOFieldBinding): unknown {
  if (!props.body) return f.default ?? f.example ?? ''
  return getByPath(props.body, f.path.replace(/^\$\.?/, '')) ?? f.default ?? f.example ?? ''
}

function setValue(f: IOFieldBinding, val: unknown) {
  if (props.readonly) return
  const rel = f.path.replace(/^\$\.?/, '')
  const next = copyBody(rel)
  if (val === '' && /[.\[]/.test(rel)) {
    // D8:深层清空=删叶子+容器级剪枝(防幻影容器残留);
    // 平铺字段清空维持 ''(现状,见 setValueNum 同约定)
    pruneByPath(next, rel)
  } else {
    setByPath(next, rel, val)
  }
  emit('update:body', next)
}

function placeholderFor(f: IOFieldBinding): string {
  const ex = f.example
  if (ex !== null && ex !== undefined) return String(ex)
  if (f.description) return f.description
  return f.required ? `${f.name} (必填)` : f.name
}

/** JSON field semantics: empty → null, non-JSON → raw string (user is typing). */
function parseJsonOrRaw(s: string): unknown {
  return s.trim() ? parseJson(s, s) : null
}

function formatJson(v: unknown): string {
  if (v === null || v === undefined || v === '') return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v, null, 2)
}
</script>

<style scoped>
.field-form {
  display: flex; flex-direction: column; gap: 14px;
}
.field { display: flex; flex-direction: column; gap: 4px; padding-left: 6px; }
.field.required .label-text { color: #1a1d24; }

/* ── 容器节点(§5.3):对象折叠面板 / 数组行组 / 开放字典 KV ── */
.obj-node, .arr-node, .dict-node {
  display: flex; flex-direction: column; gap: 6px;
  border-left: 3px solid #c7d2fe; border-radius: 4px;
  background: #f8fafc; padding: 8px 10px;
}
.node-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 500;
}
.obj-toggle {
  width: 20px; height: 20px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 4px; background: transparent;
  color: #64748b; cursor: pointer; transition: all 0.15s;
}
.obj-toggle:hover { background: #e2e8f0; color: #334155; }
.obj-toggle svg { transition: transform 0.15s; }
.obj-toggle svg.open { transform: rotate(0deg); }
.obj-toggle svg:not(.open) { transform: rotate(-90deg); }
/* 容器级策略菜单锚点(P3):☰ 绝对定位需要 positioned 祖先;
   显式 22×20 占位(0 宽锚点会让 ☰ 向左溢出压到角标/状态下拉) */
.node-fa {
  position: relative; flex-shrink: 0;
  width: 22px; height: 20px;
  margin-left: 2px;
}
.obj-body {
  display: flex; flex-direction: column; gap: 12px;
  padding: 8px 0 2px 10px; border-left: 1px dashed #cbd5e1; margin-left: 4px;
}
/* 数组/字典区块体:与 obj-body 同款缩进导轨(区块级折叠 P2) */
.arr-body {
  display: flex; flex-direction: column; gap: 10px;
  padding: 8px 0 2px 10px; border-left: 1px dashed #cbd5e1; margin-left: 4px;
}
.arr-count {
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8; background: #f1f5f9; padding: 1px 5px; border-radius: 3px;
}
.arr-add {
  flex-shrink: 0; margin-left: auto;
  border: 1px dashed #a5b4fc; border-radius: 4px;
  background: transparent; color: #6366f1;
  font-size: 10.5px; font-family: var(--font-mono); font-weight: 600;
  padding: 1px 8px; line-height: 1.5; cursor: pointer; transition: all 0.15s;
}
.arr-add:hover { background: #eef2ff; border-color: #6366f1; }
.arr-row { display: flex; gap: 6px; align-items: flex-start; }
.arr-idx {
  flex-shrink: 0; width: 20px; margin-top: 4px; text-align: center;
  font-family: var(--font-mono); font-size: 10.5px; font-weight: 700;
  color: #6366f1; background: #eef2ff; border-radius: 3px; padding: 1px 0;
}
.arr-row-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.arr-del, .extra-del {
  flex-shrink: 0; width: 26px; height: 32px;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  color: #94a3b8; cursor: pointer; font-size: 14px; line-height: 1;
  transition: all 0.15s;
}
.arr-del:hover:not(:disabled), .extra-del:hover:not(:disabled) {
  border-color: #fca5a5; background: #fef2f2; color: #ef4444;
}
.arr-del:disabled, .extra-del:disabled { cursor: not-allowed; opacity: 0.5; }
.arr-empty, .dict-empty {
  margin: 0; font-size: 11px; color: #94a3b8; font-style: normal;
}
.kv-row { display: flex; gap: 6px; align-items: flex-start; }
.kv-key {
  flex-shrink: 0; width: 130px; box-sizing: border-box;
  background: #fafbfc; border: 1.5px dashed #e6e8ec; border-radius: 8px;
  padding: 7px 10px; font-size: 12px;
  font-family: var(--font-mono); color: #475569;
}
.kv-key:focus { outline: none; border-color: #6366f1; background: #fff; }
.kv-value { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }

/* 控件 + Ⓥ 按钮同排(text)/叠排(textarea/json) */
.ctl-with-var { display: flex; gap: 6px; align-items: stretch; }
.ctl-with-var .ctl { flex: 1; min-width: 0; }
.ctl-with-var.col { flex-direction: column; align-items: flex-end; }
.var-btn {
  flex-shrink: 0;
  width: 30px;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  color: #047857; cursor: pointer; font-size: 13px;
  transition: all 0.15s;
}
.ctl-with-var.col .var-btn { width: 30px; height: 24px; font-size: 11px; }
.var-btn:hover { border-color: #6ee7b7; background: #d1fae5; }
.var-btn.dark { background: #313244; border-color: #45475a; color: #a6e3a1; }
.var-btn.dark:hover { border-color: #6ee7b7; }

/* 候选下拉(#2):输入框内嵌 ▾ + 绝对定位候选列表 */
.ctl-cand-wrap { position: relative; flex: 1; min-width: 0; display: flex; }
.ctl-cand-wrap .ctl { flex: 1; }
.cand-btn {
  position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
  width: 20px; height: 20px;
  border: none; border-radius: 4px; background: transparent;
  color: #94a3b8; cursor: pointer; font-size: 10px; line-height: 1;
  display: flex; align-items: center; justify-content: center;
}
.cand-btn:hover { background: #e2e8f0; color: #475569; }
.cand-list {
  position: absolute; top: calc(100% + 2px); left: 0; right: 0;
  z-index: 30;
  max-height: 200px; overflow-y: auto;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
  padding: 3px;
}
.cand-item {
  display: block; width: 100%; text-align: left;
  padding: 5px 8px; border: none; border-radius: 4px;
  background: transparent; cursor: pointer;
}
.cand-item:hover { background: #f1f5f9; }
.cand-item code {
  font-family: var(--font-mono); font-size: 11px; color: #334155;
}

.field-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 500;
}
.label-text { color: #1a1d24; font-weight: 600; }
.req-mark { color: #ef4444; font-weight: 700; }
.field-path {
  font-family: var(--font-mono); font-size: 10px;
  color: #94a3b8; background: #f1f5f9; padding: 1px 4px; border-radius: 3px;
}
/* 深层字段 path 角标(D5):path ≠ $.+name 的字段以角标替代灰 chip —
   mono 小字 slate 族(对齐 .fa-note/策略角标惯例) */
.path-badge {
  font-family: var(--font-mono); font-size: 9.5px;
  padding: 1px 5px; border-radius: 3px;
  background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0;
  cursor: default;
  max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ui-tag {
  font-size: 9px; font-weight: 700; text-transform: uppercase;
  padding: 1px 4px; border-radius: 3px;
  background: #eef2ff; color: #4f46e5;
}
.ui-tag.k-number { background: #fef3c7; color: #92400e; }
.ui-tag.k-boolean { background: #d1fae5; color: #065f46; }
.ui-tag.k-select { background: #f3e8ff; color: #6b21a8; }
.ui-tag.k-textarea { background: #fce7f3; color: #9d174d; }
.ui-tag.k-json { background: #1e1e2e; color: #a6e3a1; }
.ui-tag.k-file, .ui-tag.k-binary { background: #f1f5f9; color: #475569; }
.ui-tag.k-unknown { background: #fee2e2; color: #991b1b; }
/* assertable ✓ 标(Response 页契约参考线) */
.assertable-mark {
  font-size: 11px; font-weight: 700; color: #059669;
}
/* PRD §5.6 4 色 source_kind 视觉区分 (literal / static / dynamic / auto) */
.src-tag {
  font-size: 9px; font-weight: 600;
  padding: 1px 6px; border-radius: 3px;
  background: #f1f5f9; color: #475569;        /* literal 灰 */
}
.src-tag.s-lookup { background: #faf5ff; color: #7c3aed; }   /* static 紫 */
.src-tag.s-generated { background: #ede9fe; color: #7c3aed; } /* dynamic 紫 */
/* 策略角标(需求1):字段已挂策略 → 行尾定位入口,点击跳转下方策略卡 */
.strategy-tag {
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
  padding: 1px 6px; border-radius: 3px; border: none; cursor: pointer;
  background: #e0e7ff; color: #4338ca;
}
.strategy-tag:hover { background: #c7d2fe; color: #3730ea; }
/* 字段行 4 色左边框 */
.field.sk-independent { border-left: 3px solid #cbd5e1; }    /* literal 灰 */
.field.sk-lookup { border-left: 3px solid #7c3aed; }            /* static 紫 */
.field.sk-generated { border-left: 3px solid #f59e0b; }         /* dynamic 橙 (auto-extract 提示色) */

/* 动态注入态提示条:琥珀族与 sk-generated 橙同源 — 值由 assign 运行时覆盖。
   wrap 相对定位给 ☰ 菜单浮层做锚(同 ctl-cand-wrap)。 */
.ctl-injected-wrap { position: relative; display: flex; gap: 6px; width: 100%; }
.ctl-injected {
  flex: 1; min-width: 0;
  display: flex; align-items: center; gap: 6px;
  background: #fffbeb; border: 1.5px dashed #f59e0b; border-radius: 8px;
  padding: 7px 10px;
  font-size: 12px; color: #92400e;
  cursor: default; user-select: none;
}
.ctl-injected svg { flex-shrink: 0; }
/* 容器头注入徽标(P6):同琥珀族紧凑形态 — 整区块运行时被 assign 覆盖 */
.node-injected {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 8px; border-radius: 999px;
  background: #fffbeb; border: 1.5px dashed #f59e0b;
  font-size: 11px; color: #92400e;
  cursor: default; user-select: none; flex-shrink: 0;
}
.node-injected svg { flex-shrink: 0; }
/* 注入容器体锁定(P6):原值仍在(策略失败 continue 兜底)但只读 —
   惨淡化 + 拦截交互(I1 防编辑误导的容器面) */
.body-locked { pointer-events: none; opacity: 0.55; }
/* 提取态(域感知提取):绿色族(与变量注册表 extract 出身徽章同源)—
   只读取不覆盖,值控件不锁,仅提示运行时读取 */
.node-extracted {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 8px; border-radius: 999px;
  background: #ecfdf5; border: 1.5px dashed #059669;
  font-size: 11px; color: #065f46;
  cursor: default; user-select: none; flex-shrink: 0;
}
.node-extracted svg { flex-shrink: 0; }
.extracted-hint {
  display: flex; align-items: center; gap: 4px;
  margin: 1px 0 0;
  font-size: 11px; color: #047857;
}
.extracted-hint code {
  font-family: var(--font-mono); font-size: 10.5px;
  background: #d1fae5; border-radius: 3px; padding: 0 5px;
  max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* 兜底原值行:continue 语义透出,长值 code 内截断 */
.injected-fallback {
  display: flex; align-items: center; gap: 4px;
  margin: 1px 0 0;
  font-size: 11px; color: #b45309;
}
.injected-fallback code {
  font-family: var(--font-mono); font-size: 10.5px;
  background: #fef3c7; border-radius: 3px; padding: 0 5px;
  max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.ctl {
  width: 100%;
  /* border-box: content-box 下 100% + padding + 边框会超出策略卡/字段行容器 */
  box-sizing: border-box;
  background: #fafbfc; border: 1.5px solid #e6e8ec; border-radius: 8px;
  padding: 7px 10px;
  font-size: 13px; color: #1a1d24; font-family: inherit;
  transition: all 0.15s;
  outline: none;
}
.ctl:hover { border-color: #c7d2fe; }
.ctl:focus { background: #fff; border-color: #4f46e5; box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15); }
.ctl::placeholder { color: #cbd5e1; }

/* 模板态降级输入(typed 字段值为 ${...}):等宽字体 + 靛蓝底提示语域切换 */
.ctl.tpl {
  font-family: var(--font-mono); font-size: 12px;
  border-color: #c7d2fe; background: #f5f7ff;
}

.ctl-area { resize: vertical; min-height: 60px; }
.ctl-code {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.5;
  background: #1e1e2e; color: #a6e3a1; border-color: #313244;
}
.ctl-code:focus { background: #1e1e2e; color: #a6e3a1; border-color: #6366f1; }

.ctl-bool {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; cursor: pointer;
}
.ctl-bool input { width: 16px; height: 16px; accent-color: #4f46e5; }

.ctl-file {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; background: #fafbfc; border: 1.5px dashed #cbd5e1; border-radius: 8px;
  color: #5a6273; font-size: 12px;
}
.file-tag { font-weight: 700; color: #475569; }
.file-hint { font-size: 11px; }

.field-desc {
  display: flex; align-items: flex-start; gap: 5px;
  margin: 1px 0 0;
  font-size: 11.5px; color: #64748b; line-height: 1.5;
}
.field-desc svg { flex-shrink: 0; margin-top: 2px; color: #94a3b8; }

/* ── 已折叠字段区(§5.4 折叠区):中性 slate —— 渐进披露而非警示
   (与「其他字段」琥珀警示区分;值仍在 body,仅布局收纳) ── */
.folded {
  padding: 8px 10px 8px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #94a3b8;
  border-radius: 8px;
}
.folded-toggle {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 0; border: none; background: transparent;
  font-size: 12px; text-align: left; cursor: pointer;
}
.folded-arrow {
  display: inline-block; font-size: 10px; color: #64748b;
  transition: transform 0.15s;
}
.folded-arrow.open { transform: rotate(90deg); }
.folded-title { font-weight: 600; color: #475569; }
.folded-hint { margin-left: auto; font-size: 11px; color: #94a3b8; }
.folded-body { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.folded-row { display: flex; flex-direction: column; gap: 4px; padding-left: 6px; }
.folded-label { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.folded-control .ctl { width: 100%; }

/* ── 其他字段折叠区:琥珀警示(浅底 + 左条),与 sk-generated 橙同族 ── */
.extras {
  padding: 8px 10px 8px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-left: 3px solid #f59e0b;
  border-radius: 8px;
}
.extras-toggle {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 0; border: none; background: transparent;
  font-size: 12px; text-align: left; cursor: pointer;
}
.extras-arrow {
  display: inline-block; font-size: 10px; color: #b45309;
  transition: transform 0.15s;
}
.extras-arrow.open { transform: rotate(90deg); }
.extras-title { font-weight: 600; color: #92400e; }
.extras-hint { margin-left: auto; font-size: 11px; color: #b45309; }
.extras-body { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.extra-row { display: flex; flex-direction: column; gap: 4px; padding-left: 6px; }
.extra-label { display: flex; align-items: center; gap: 6px; font-size: 12px; }
/* 来源标签:实有(body 键,随请求发送)/ 契约(plate 契约声明) */
.extra-src {
  font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px;
  background: #fef3c7; color: #92400e; cursor: default;
}
.extra-src.schema { background: #ecf5ff; color: #409eff; }
.extra-control { display: flex; gap: 6px; align-items: flex-start; }
.extra-control .ctl { flex: 1; min-width: 0; }
</style>
