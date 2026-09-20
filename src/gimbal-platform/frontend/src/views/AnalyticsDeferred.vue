<!-- AnalyticsDeferred.vue — 数据分析(执行设计 §4,按 4 号原型实现)。
     本期延后,这一页是说明页,不是空洞:延后之后没有任何日常能力跟着消失
     — 该在别处的已经在了(§4.1);解锁它的唯一前置是行级/步骤级结果
     落库(§4.2)。侧边栏入口置灰保留(§4.4):延后的东西藏起来,过几个
     月没人记得它存在,那条落库前置也就跟着沉了;点进来撞上这条说明,
     前置就一直可见。本页自身正常渲染(当前路由高亮如常)+ 琥珀「延后」小标。
     纪律:不渲染示意性假数据 — 落库后的四块只给名称与理由,不给编造的图。 -->
<template>
  <ListPage title="数据分析" width="standard"
    subtitle="「最近整体怎么样、问题集中在哪」 — 跨执行聚合。单次执行的问题,执行记录和字段来源分析已经回答得了">
    <template #actions>
      <span class="deferred-badge" data-testid="analytics-deferred-badge">延后 · 等行级落库</span>
    </template>

    <!-- 前置说明(琥珀:待办/前置族) -->
    <div class="deferred-notice">
      <div class="notice-title">本期延后 — 解锁它的唯一前置:行级 / 步骤级结果落库</div>
      <p class="notice-body">
        行级状态今天靠扫 <code class="mono">data/runs/*.jsonl</code> 按 executionId 逐条回放,步骤级明细只在 case 目录的
        <code class="mono">result.json</code> 工件里 — <strong>单执行读得出,跨执行聚合不出来</strong>。
        侧边栏入口因此置灰保留、而不是删掉:留个灰入口,点进来就撞上这条说明,前置就一直看得见。
      </p>
    </div>

    <!-- 延后不是空洞:日常最需要的几个数已经在别处(§4.1) -->
    <div class="ana-card">
      <div class="card-title">延后不是空洞 — 日常最需要的几个数已经在别处</div>
      <div class="moved-row">
        <span class="moved-tag">已在别处</span>
        <span class="moved-body">
          近 7 天执行 / 通过率 / 配置漂移 / 反复失败 / 执行时长
          <span class="moved-dim">— 执行记录顶部那条 KPI 带,Execution 计数器就能算</span>
        </span>
        <router-link class="moved-link" to="/executions" data-testid="analytics-goto-executions">去执行记录 →</router-link>
      </div>
      <div class="moved-row">
        <span class="moved-tag">已在别处</span>
        <span class="moved-body">
          「从未被执行的用例」这个覆盖盲区
          <span class="moved-dim">— 服务画像的热力网格,② 格「无用例覆盖」</span>
        </span>
        <router-link class="moved-link" to="/services" data-testid="analytics-goto-services">去服务画像 →</router-link>
      </div>
    </div>

    <!-- 落库之后这一页给什么(设计保留;只给名称与理由,不渲染假数据) -->
    <div class="ana-card">
      <div class="card-title">落库之后,这一页给什么 <span class="card-dim">(设计已保留 — 图表规范:一张图只有一根 y 轴;单序列不给图例;四色分类已过 CVD 校验)</span></div>
      <div class="wait-row">
        <span class="wait-tag">需落库</span>
        <div class="wait-body">
          <div class="wait-name">失败原因构成 — 配置类 vs 用例类</div>
          <p class="wait-desc">
            断言失败 / 字段注入 / 连接认证 / 超时。这条切分是这一页存在的最强理由:它直接决定下一步去服务信息管理还是去编排页,
            而且只有平台算得出来 — 失败行的字段落在 carry 层还是 form 层,字段来源分析那条链已经算过了。
          </p>
        </div>
      </div>
      <div class="wait-row">
        <span class="wait-tag">需落库</span>
        <div class="wait-body">
          <div class="wait-name">失败聚类 · 按接口</div>
          <p class="wait-desc">问题集中在哪几个接口 — 行级失败明细按 endpoint 归并。</p>
        </div>
      </div>
      <div class="wait-row">
        <span class="wait-tag">需落库</span>
        <div class="wait-body">
          <div class="wait-name">不稳定用例的步骤级粒度</div>
          <p class="wait-desc">翻转次数在 execution 级算得出,落到哪一步要解析 result.json。</p>
        </div>
      </div>
      <div class="wait-row">
        <span class="wait-tag">需落库</span>
        <div class="wait-body">
          <div class="wait-name">行级耗时分布</div>
          <p class="wait-desc">execution 级时长已在 KPI 带;行级分布要等落库。</p>
        </div>
      </div>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import ListPage from '@/layouts/ListPage.vue'
</script>

<style scoped>
/* 琥珀「延后」小标(§4.4:本页正常高亮 + 延后小标;附录 待办/前置 族) */
.deferred-badge {
  display: inline-flex; align-items: center;
  padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
  background: #FEF3C7; color: #B45309;
}

.deferred-notice {
  margin-top: 16px;
  padding: 14px 16px;
  background: #FFFFFF; border: 1px solid #E1E5EB; border-left: 3px solid #B45309;
  border-radius: 10px;
}
.notice-title { font-size: 13px; font-weight: 700; color: #10151C; }
.notice-body {
  margin: 8px 0 0; font-size: 12px; color: #5B6472; line-height: 1.8;
}
.notice-body strong { color: #B45309; }
.notice-body code {
  font-family: var(--font-mono, monospace); font-size: 11px;
  background: #EEF0F3; border-radius: 4px; padding: 0 5px;
}

.ana-card {
  margin-top: 14px;
  padding: 14px 16px;
  background: #FFFFFF; border: 1px solid #E1E5EB; border-radius: 10px;
  display: flex; flex-direction: column; gap: 10px;
}
.card-title { font-size: 13px; font-weight: 700; color: #10151C; }
.card-dim { font-size: 11px; font-weight: 400; color: #8B93A1; }

/* 已在别处(通过族) */
.moved-row {
  display: flex; align-items: baseline; gap: 10px;
  padding: 10px 12px; border: 1px solid #EEF0F3; border-radius: 8px;
}
.moved-tag {
  flex: none; font-size: 10px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
  background: #E4F5EA; color: #15803D;
}
.moved-body { flex: 1; min-width: 0; font-size: 12px; color: #10151C; line-height: 1.7; }
.moved-dim { color: #5B6472; }
.moved-link { flex: none; font-size: 12px; color: #2F6FED; white-space: nowrap; }
.moved-link:hover { text-decoration: underline; }

/* 需落库(待办琥珀族) */
.wait-row {
  display: flex; align-items: baseline; gap: 10px;
  padding: 10px 12px; border: 1px dashed #E1E5EB; border-radius: 8px;
}
.wait-tag {
  flex: none; font-size: 10px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
  background: #FEF3C7; color: #B45309;
}
.wait-body { flex: 1; min-width: 0; }
.wait-name { font-size: 12.5px; font-weight: 600; color: #10151C; }
.wait-desc { margin: 4px 0 0; font-size: 11.5px; color: #5B6472; line-height: 1.7; }

.mono { font-family: var(--font-mono, monospace); }
</style>
