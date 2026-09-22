/**
 * useUserPreferences.ts — 用户偏好的「服务端为准 + 本地镜像」同步层。
 *
 * 为什么还留一份 localStorage 镜像:工作台布局 / 关注常驻席 / 时间线配色
 * 都在组件 setup 里**同步**取值渲染。换成纯异步读服务端,首帧就会先按默认
 * 铺一遍再跳(卡片重排、圆点变色)。镜像管首帧,服务端管跨设备。
 *
 * 对齐规则(一账号一份,换账号整体重来):
 * 1. 首次用到任一偏好时一次批量 GET 拉回全部键;
 * 2. 服务端有值 → 以它为准并回填镜像(新设备 / 清过浏览器数据);
 * 3. 服务端没这个键而镜像有值 → 把镜像播种上去(存量本地存档的一次性搬家);
 * 4. 本机改过但 PUT 尚未确认的键不被 GET 回读覆盖 —— 否则"进页面立刻拖
 *    卡片"会被一个出发更早的 GET 打回去;PUT 成功后解除该豁免;
 * 5. 写:内存 + 镜像立即生效,PUT 防抖合并;GET 未回也照发(单键整值覆盖,
 *    不依赖整表状态)。
 *
 * 镜像键沿用迁移前的原名与原格式(由消费方给出 mirrorPrefix),所以对老
 * 用户这次迁移是"悄悄多了一份云端副本",不是"存档清零"。
 *
 * 同一键全局只有一个实例(模块级表):多处消费时间线配色时读到同一个 ref
 * —— 与迁移前那几个 composable 自己的模块级单例同形。
 */
import { computed, ref, watch, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useUserScopedStorage } from './useUserScopedStorage'
import { getPreferences, putPreference, type PrefKey, type PrefValues } from '@/api/preferences'
import { toast } from '@/utils/toast'

export interface PrefOptions<K extends PrefKey, T> {
  /** 迁移前的 localStorage 键前缀(实际键 = `${mirrorPrefix}:${username}`)。 */
  mirrorPrefix: string
  /** 镜像原始串 → 值(无存档时返回初值;损坏/缺字段在这里收敛,不抛)。
   *  第二参是当前用户名:v1 旧键这类"要按人再读一次别的键"的迁移用得上。 */
  fromMirror: (raw: string | null, username: string) => T
  /** 值 → 镜像串。 */
  toMirror: (v: T) => string
  /** 值 → 服务端 payload(常驻席要包一层 ids,其余原样)。 */
  toServer: (v: T) => PrefValues[K]
  /** 服务端 payload → 值;返回 null = 当作没有,保留镜像值。 */
  fromServer: (raw: unknown) => T | null
}

export interface UserPreference<T> {
  /** 当前生效值;服务端回读或换账号时由本层改写。 */
  value: Ref<T>
  /** 改完 value 之后调用:落镜像 + 防抖 PUT。 */
  save: () => void
  /** 服务端是否已就位(false = 现在用的是镜像值)。 */
  synced: Ref<boolean>
  /** 身份是否已知(false = 改了也存不了:镜像无键可落,PUT 会 401)。
   *  播种类调用方用它复现"身份未到位就先别动存档"的纪律。 */
  identified: Ref<boolean>
  /** 服务端或镜像任一**有过**存档(含"存了个空值")。播种类调用方用它
   *  区分"从没存过(可以铺默认)"和"用户特意清空了(必须尊重)"。 */
  hadStored: Ref<boolean>
  /** 等身份到位 + 首轮批量 GET 结束(成功/失败都 resolve)。 */
  whenReady: () => Promise<void>
}

interface LiveEntry {
  key: PrefKey
  pref: UserPreference<unknown>
  current: () => unknown
  apply: (v: unknown) => void
  hasMirror: () => boolean
  mirrorWrite: (v: unknown) => void
  toServer: (v: unknown) => PrefValues[PrefKey]
  fromServer: (raw: unknown) => unknown
  reloadFromMirror: () => void
  markStored: () => void
}

const entries = new Map<PrefKey, LiveEntry>()
const syncedFor = ref('')
/** PUT 尚未确认的键:豁免服务端回读覆盖(见文件头规则 4)。 */
const unconfirmed = new Set<PrefKey>()
const putTimers = new Map<PrefKey, ReturnType<typeof setTimeout>>()
let inflight: Promise<void> | null = null

/** PUT 合并窗口:同一键连续拖动/连改尺寸只发一次。测试也用它来等写落地。 */
export const PREFERENCE_PUT_DEBOUNCE_MS = 400

/** 与 useUserScopedStorage 的镜像键同源:两边口径必须一致,否则镜像读不回来。 */
function currentUsername(): string {
  return useAuthStore().currentUser?.username ?? ''
}

function schedulePut(key: PrefKey, payload: PrefValues[PrefKey]): void {
  clearTimeout(putTimers.get(key))
  putTimers.set(key, setTimeout(() => {
    putTimers.delete(key)
    putPreference(key, payload).then(
      () => { unconfirmed.delete(key) },
      (e: unknown) => {
        // 静默失败会让人误以为"换设备也在",所以必须冒一句;
        // 豁免不解除 —— 本机这份才是新值,不能被回读打回。
        toast.error(`偏好保存失败(仅本机生效):${e instanceof Error ? e.message : '网络异常'}`)
      },
    )
  }, PREFERENCE_PUT_DEBOUNCE_MS))
}

/** 首轮 / 换账号后的批量对齐;同一时刻只跑一次。 */
function pull(): Promise<void> {
  if (inflight) return inflight
  const username = currentUsername()
  if (!username) return Promise.resolve()
  inflight = new Promise<void>((resolve) => {
    const done = () => { inflight = null; resolve() }
    getPreferences().then((items) => {
      if (currentUsername() !== username) { done(); return }   // 人换号了,结果作废
      syncedFor.value = username
      for (const e of entries.values()) {
        const raw = items[e.key]
        if (raw !== undefined) {
          e.markStored()
          const v = e.fromServer(raw)
          if (v === null) continue                 // 脏值 → 保留镜像,不硬套
          e.mirrorWrite(v)                         // 服务端为准 → 回填镜像
          if (!unconfirmed.has(e.key)) e.apply(v)
          continue
        }
        if (e.hasMirror()) {
          e.markStored()
          schedulePut(e.key, e.toServer(e.current()))   // 存量存档搬家
        }
      }
      done()
    }).catch(() => {
      done()   // 拉不到就继续用镜像值:不闪、不阻塞,下次进页面再试
    })
  })
  return inflight
}

/** 换账号 → 各键按新账号的镜像重载,再拉一次服务端。 */
function rebind(): void {
  if (!currentUsername()) return
  syncedFor.value = ''
  unconfirmed.clear()
  for (const e of entries.values()) e.reloadFromMirror()
  void pull()
}

/** 等身份到位 + 首轮 GET 完成。身份还没回来时**不能**立即 resolve ——
 *  否则调用方会抢在绑定完成前动存档,写进匿名键(= 「刷新后设置丢了」)。 */
function waitReady(): Promise<void> {
  if (currentUsername()) return pull()
  const auth = useAuthStore()
  return new Promise((resolve) => {
    const stop = watch(
      () => auth.currentUser?.username ?? '',
      (u) => { if (u) { stop(); void pull().then(resolve) } },
    )
  })
}

export function useUserPreference<K extends PrefKey, T>(
  key: K, opts: PrefOptions<K, T>,
): UserPreference<T> {
  const live = entries.get(key)
  if (live) return live.pref as unknown as UserPreference<T>

  const auth = useAuthStore()
  const mirror = useUserScopedStorage(opts.mirrorPrefix)
  const value = ref(opts.fromMirror(mirror.read(), currentUsername())) as Ref<T>
  const hadStored = ref(mirror.exists())

  const entry: LiveEntry = {
    key,
    pref: null as unknown as UserPreference<unknown>,
    current: () => value.value,
    apply: (v) => { value.value = v as T },
    hasMirror: () => mirror.exists(),
    mirrorWrite: (v) => mirror.write(opts.toMirror(v as T)),
    toServer: (v) => opts.toServer(v as T),
    fromServer: (raw) => opts.fromServer(raw),
    reloadFromMirror: () => {
      value.value = opts.fromMirror(mirror.read(), currentUsername())
      hadStored.value = mirror.exists()
    },
    markStored: () => { hadStored.value = true },
  }
  const pref: UserPreference<T> = {
    value,
    save: () => {
      // 身份未知 → 本次只改内存:镜像写不进任何键,PUT 更是会 401 把会话
      // 踢回登录页(与 useUserScopedStorage 的"零写入"纪律同一口径)。
      if (!currentUsername()) return
      const json = opts.toMirror(value.value)
      // 镜像已经是这份值、且没有欠着服务端 → 不写不发。少了这一条,
      // 服务端回读套进 ref 会触发消费方的 deep watch,把同一份值再 PUT
      // 一次回去(每次进页面一发空写);而 v1→v2 迁移这类"镜像还没有"
      // 的写正好不等,照常落盘。
      if (mirror.read() === json && !unconfirmed.has(key)) return
      mirror.write(json)
      hadStored.value = true
      unconfirmed.add(key)
      schedulePut(key, opts.toServer(value.value))
    },
    synced: computed(() => {
      const u = currentUsername()
      return !!u && syncedFor.value === u
    }),
    identified: computed(() => !!currentUsername()),
    hadStored,
    whenReady: waitReady,
  }
  entry.pref = pref as unknown as UserPreference<unknown>
  entries.set(key, entry)

  watch(() => auth.currentUser?.username ?? '', rebind)
  void pull()

  return pref
}

/** 测试用:清空实例与在飞状态(换账号以外的场景不需要)。 */
export function resetUserPreferencesForTest(): void {
  entries.clear()
  putTimers.forEach((t) => clearTimeout(t))
  putTimers.clear()
  unconfirmed.clear()
  syncedFor.value = ''
  inflight = null
}
