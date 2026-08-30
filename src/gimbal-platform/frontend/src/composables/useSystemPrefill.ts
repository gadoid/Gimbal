/**
 * useSystemPrefill.ts — 选系统 → 场景骨架预填(新建场景一次性引导)。
 *
 * 数据来源(api/plate 统一查询层):
 *   - meta     : common 通用定义(common.default seed)的公共项
 *               (version/priority/expire/requirementRef);
 *               name/module/author 等用户字段与 system 选择永不采用。
 *   - config   : common 基座(timePolicy/retry/setup/teardown)
 *               + 各选中系统 services/users/vars 浅合并
 *               (命名约定 fin-service / fin_base_url 天然防碰撞)。
 *   - resource : 各选中系统资源并集(common 无资源)。
 *
 * 预填策略(用户确认「仅首次预填」):
 *   - 仅新建场景(isNew);编辑场景加载的是已存 definition,永不预填。
 *   - config/resource 已有内容(用户编辑过)→ 整体放弃,不部分覆盖。
 *   - 成功一次后不再重载(切换系统不重拉);plate 不可达静默降级,
 *     且失败不消耗首次机会 — 后续选择变化仍可重试。
 *
 * 调用方约定:CaseComposer setup 阶段调用一次,传入 definition ref
 * 与 isNew(路由参数派生);composable 自持 watch,无需外部驱动。
 */
import { ref, watch, type Ref } from 'vue'

import {
  fetchSystemConfig,
  fetchSystemMeta,
  fetchSystemResources,
} from '@/api/plate'
import type { ConfigView, ResourceView, ScenarioView } from '@/types/plate'

/** meta 中允许从 common 通用定义采用的公共项(其余归用户/本地)。 */
type CommonMetaFields = Pick<
  ScenarioView['meta'],
  'version' | 'priority' | 'expire' | 'requirementRef'
>

/** common 基座 + 各系统 config 业务段(services/users/vars)浅合并。 */
function mergeConfig(base: ConfigView | null, parts: ConfigView[]): ConfigView {
  return {
    setup: base?.setup ?? [],
    teardown: base?.teardown ?? [],
    timePolicy: base?.timePolicy ?? { kind: 'record' },
    retry: base?.retry ?? null,
    services: Object.assign({}, ...parts.map((c) => c.services)),
    users: Object.assign({}, ...parts.map((c) => c.users)),
    vars: Object.assign({}, ...parts.map((c) => c.vars)),
  }
}

export function useSystemPrefill(definition: Ref<ScenarioView>, isNew: Ref<boolean>): void {
  /** 首次预填是否已成功(成功后切换系统不重载)。 */
  const prefilled = ref(false)

  /** 守卫:仅「新建 + 未预填过 + config/resource 还是原始默认」时放行。 */
  function shouldPrefill(): boolean {
    if (!isNew.value || prefilled.value) return false
    const { config, resource } = definition.value
    const touched =
      Object.keys(config.services).length > 0 ||
      Object.keys(config.users).length > 0 ||
      Object.keys(config.vars).length > 0 ||
      Object.keys(resource).length > 0
    return !touched
  }

  watch(
    () => definition.value.meta.system,
    async (systems) => {
      if (!systems.length || !shouldPrefill()) return
      try {
        // 并行:common 基座/通用 meta + 各选中系统的 config 与资源全集
        const [commonConfig, commonMeta, ...systemParts] = await Promise.all([
          fetchSystemConfig('common'),
          fetchSystemMeta('common'),
          ...systems.map((s) =>
            Promise.all([fetchSystemConfig(s), fetchSystemResources(s)]) as Promise<
              [ConfigView | null, Record<string, ResourceView>]
            >),
        ])
        definition.value.config = mergeConfig(
          commonConfig,
          systemParts.map(([cfg]) => cfg).filter((cfg): cfg is ConfigView => !!cfg),
        )
        const resources = Object.assign(
          {}, ...systemParts.map(([, res]) => res),
        )
        if (Object.keys(resources).length) definition.value.resource = resources
        if (commonMeta) {
          const adopted: CommonMetaFields = {
            version: commonMeta.version,
            priority: commonMeta.priority,
            expire: commonMeta.expire,
            requirementRef: commonMeta.requirementRef,
          }
          definition.value.meta = { ...definition.value.meta, ...adopted }
        }
        prefilled.value = true
      } catch (e) {
        // 静默降级:保留前端默认结构;失败不置 prefilled,
        // 后续选择变化仍可重试。
        console.warn('[useSystemPrefill] plate 预填失败,保留默认结构:', e)
      }
    },
    // immediate:新建场景默认 system:['fin'] 视为已选,进页即预填
    { immediate: true, deep: true },
  )
}
