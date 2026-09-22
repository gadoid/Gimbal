/**
 * useFollowLayout.ts — 关注页布局态:常驻席手动排序 + 上限。
 *
 * 后端 starred 只有布尔位,没有「常驻/顺序」字段,故常驻席顺序属于个人
 * 偏好。存档走 useUserPreference('follows.pinned'):服务端 user_prefs
 * 为准(换设备不丢)+ localStorage 镜像管首帧。镜像沿用迁移前的裸数组
 * 格式与键名(`gimbal.scenario-follows.pinned:<username>`),服务端 payload
 * 才包一层 `{ids}` —— 后端需要一个对象行来落 JSON 列,前端不必跟着改形。
 *
 * 首次进入(服务端与镜像都没存档)以关注列表前 PINNED_MAX 条播种;之后尊重
 * 已存值,**包括空值** —— 空 = 用户把常驻全部取消,不是"没存过"。
 */
import { useUserPreference } from './useUserPreferences'

export const FOLLOW_CAP = 20
export const PINNED_MAX = 5

/** 超上限时由 store 抛出 —— 视图据此给一句人话提示,而不是走通用错误兜底。 */
export class FollowCapError extends Error {}

const MIRROR_PREFIX = 'gimbal.scenario-follows.pinned'

function fromMirror(raw: string | null): string[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function useFollowLayout() {
  const pref = useUserPreference('follows.pinned', {
    mirrorPrefix: MIRROR_PREFIX,
    fromMirror,
    toMirror: (ids) => JSON.stringify(ids),
    toServer: (ids) => ({ ids }),
    fromServer: (raw) => {
      const ids = (raw as { ids?: unknown } | null)?.ids
      return Array.isArray(ids) ? ids.filter((x) => typeof x === 'string') : null
    },
  })
  const pinned = pref.value

  /** 首次进入播种前 PINNED_MAX 条。两个前置条件缺一不可:身份已到位
   *  (否则铺的是内存值,回头换镜像一重载就没了),以及**从没存过**
   *  —— hadStored 覆盖了"存了个空数组"那种情况,那是用户特意清空的,
   *  不能被他下次进页面时悄悄铺回去。 */
  function seed(followedIds: string[]) {
    if (!pref.identified.value || pref.hadStored.value) return
    pinned.value = followedIds.slice(0, PINNED_MAX)
    pref.save()
  }

  function isPinned(id: string) {
    return pinned.value.includes(id)
  }

  function pin(id: string): boolean {
    if (pinned.value.includes(id)) return true
    if (pinned.value.length >= PINNED_MAX) return false
    pinned.value = [...pinned.value, id]
    pref.save()
    return true
  }

  function unpin(id: string) {
    pinned.value = pinned.value.filter((x) => x !== id)
    pref.save()
  }

  /** 拖拽排序:把 id 移到 target 之前(target=null 表示移到末尾)。 */
  function move(id: string, target: string | null) {
    const rest = pinned.value.filter((x) => x !== id)
    const idx = target === null ? rest.length : rest.indexOf(target)
    if (idx < 0) return
    rest.splice(idx, 0, id)
    pinned.value = rest
    pref.save()
  }

  /** 剪掉已不在关注集内的 id。取消关注/删除场景后死 id 仍会白占
   *  PINNED_MAX 预算 —— 常驻区只显示交集,用户会撞"上限 5 个"却看
   *  不到任何占位卡,且没有逃生入口。 */
  function prune(validIds: string[]) {
    const valid = new Set(validIds)
    const next = pinned.value.filter((x) => valid.has(x))
    if (next.length === pinned.value.length) return
    pinned.value = next
    pref.save()
  }

  return {
    pinned, seed, isPinned, pin, unpin, move, prune,
    synced: pref.synced, whenReady: pref.whenReady,
  }
}
