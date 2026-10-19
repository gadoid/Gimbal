"""integration_runner — 集成任务执行器(外部系统集成 P1)。

《GIMBAL-外部系统集成架构设计》§5 + 评审(2026-10-09)定稿口径:
- **不写任何执行记录**(决策 3):行台账/事件/case.json 案卷全不落,
  状态只回写 integration_tasks 实例行(评审 E3:P1 无 outputs 消费,
  G2 随 P2/task 3c);
- **复用执行链既有零件**:compose → plate convert → materialize →
  gimbal server 通道,与 run_dispatcher 同一份实现(经公共别名),
  不另开漂移面;
- **半常驻通道**(评审 E4-A):执行后保留 N 分钟,空闲即收口 ——
  不引入常驻池的看护逻辑;
- **E1**:state_vars/last_outputs 不接收敏感键(脱敏键表口径),
  token 复用走执行器会话缓存,不落库;
- 调度入口 :func:`scheduler_tick`(15s,后台任务注册表驱动):短持
  advisory lock 选主(评审 E5)→ 认领到期实例 → 准入 → 执行。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import select, text, update

from ..core import db as db_module
from ..core.config import settings
from ..models.composer_scenario import ComposerScenario
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.integration_task import IntegrationTask
from ..models.user import User
from .cron_expr import next_fire
from .run_materialize import materialize_run_copy, referenced_services
from .run_semantics import INTEGRATION, PIN, UNDECLARED, WORKING, invalid_reason, record_category, ref_category
from .scenario_store import definition_from_payload, steps_from_payload

# 与 gimbal/protocols/result.py 同口径(评审 E1:state_vars 不收敏感键)
_REDACT_KEYS = ("authorization", "cookie", "x-auth-token", "token",
                "secret", "password")

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# 准入上限(P1 定值;上线检查项随真实数据复核)
GLOBAL_INFLIGHT_CAP = 2        # = 通道数
PER_SYSTEM_CAP = 2
PER_HOLDER_SYSTEM_CAP = 2
# 运行租约:超时回收(running_since 超过 → idle + run_status=timeout)
RUN_LEASE_SECONDS = 15 * 60
# 半常驻通道空闲收口
CHANNEL_IDLE_SECONDS = 5 * 60
MANUAL_COOLDOWN_SECONDS = 60
FAIL_STREAK_NOTIFY = 3

_AUTH_TEMPLATE = re.compile(r"\$\{auth\.([A-Za-z0-9_.\-]+)\.")


def _now() -> datetime:
    # aware UTC(utcnow 3.12 起废弃;与 UtcDateTime/ensure_aware 口径同向)
    return datetime.now(timezone.utc)


def _json_of(value: Any) -> str:
    """D8:on_change 的 outputs 比较口径 —— 脱敏后序列化比较
    (sort_keys 键序稳定、深度覆盖、实现一行)。"""
    return json.dumps(value or {}, sort_keys=True, ensure_ascii=False,
                      default=str)


# D3(2026-10-13):跨次游标键豁免(与引擎 Engine._CURSOR_KEYS 同表)——
# nextToken/pageToken 命中 "token" 子串会被脱敏,Y4 state_mapping 跨次
# 注入的即 ***redacted***,游标失效。仅精确键名豁免。
_CURSOR_KEYS = frozenset({"nexttoken", "pagetoken", "cursor", "next_cursor"})


def _scrub(value, key_hint: str = "") -> None:
    """就地脱敏 dict 的敏感键(评审 E1:同键表口径,子串不敏感处理)。"""
    if not isinstance(value, dict):
        return
    for k in list(value.keys()):
        lk = str(k).lower()
        if (any(rk in lk for rk in _REDACT_KEYS)
                and lk not in _CURSOR_KEYS):
            value[k] = "***"
        else:
            _scrub(value[k], lk)


async def is_scenario_read_only(payload: dict | None) -> tuple[bool, list[str]]:
    """平台模式只读护栏 —— I4(集成线 v2 §3.1)补全 query_safe 口径,
    与取数视图消费**同一个真源**(plate 契约元数据):

    一个步骤满足任一即视为只读:
    * 方法 ∈ GET / HEAD / OPTIONS;
    * plate 锚点:端点 ``metadata.query_safe = true``(钉修订场景按
      meta.plate 修订取,与 method 同路径;R-E 已核实 /full 投影带
      metadata);
    * 无锚点手写原始调用:只认 method,fail-closed(存量 ``ext:`` 步骤
      必带内联 method,同此口径 —— 手写即自担)。

    契约不可得即按不安全处理(fail-closed:只读闸不得因取不到契约而
    放行)。不满足时列出判定依据「步骤 i(POST,未标 query_safe)」。
    """
    from . import plate_client

    meta_plate = (((definition_from_payload(payload) or {}).get("meta") or {})
                  .get("plate") or {})
    offenders: list[str] = []
    for i, step in enumerate(steps_from_payload(payload)):
        call = step.get("call") if isinstance(step, dict) else None
        method = str((call or {}).get("method") or "").upper()
        endpoint = str(step.get("endpoint") or "") if isinstance(step, dict) else ""
        query_safe = False
        # b2-11(归一 v1.0 §2.1/C5):ext: DB 分支删除 —— 存量 ext: 步骤
        # 必带内联 method,落入下方 plate 分支取不到定义即 fail-closed
        # (过渡期行为见 §3.5;ext: 整体退役在批3/C12)。
        if not method and endpoint:
            ref = meta_plate.get(endpoint.split(".")[0])
            if ref_category(ref) == PIN:  # b2-3:读取按类别
                item = await plate_client.get_endpoint_full_at(endpoint, ref)
            else:
                item = (await plate_client.get_endpoint_full(endpoint)).item
            binding = ((item or {}).get("binding")
                       if isinstance(item, dict) else None) or {}
            meta = ((item or {}).get("metadata")
                    if isinstance(item, dict) else None) or {}
            method = str(binding.get("method") or "").upper() or "未知方法"
            query_safe = bool(meta.get("query_safe"))
        if method and method not in _SAFE_METHODS and not query_safe:
            # 判定依据(§3.2)只给锚点步骤(可去标 query_safe);
            # 手写原始调用无锚点可标、契约不可得同理,只报方法
            offenders.append(
                f"步骤 {i}({method},未标 query_safe)"
                if endpoint and "未知" not in method
                else f"步骤 {i}({method})")
    return (not offenders, offenders)


async def get_platform_user_id() -> int | None:
    """平台系统用户 id(迁移 0015 种子)。每次一查:单行等值查询,
    不做跨测试会话的模块级缓存(测试库逐测试重建,缓存会串 id)。"""
    async with db_module.SessionLocal() as db:
        row = (await db.execute(
            select(User.id).where(User.is_system == True)  # noqa: E712
        )).scalar()
    return row


# ── 集成线 v2(I2):运行状态 × 检查结论 分立(方案 §2.2/§2.3)─────

# 规则 3:单元超时(plan.py)与协作取消(scenario_runner)的标记 —— 不经
# calling 阶段类型化,error_kind 是 logic,不补会落兜底错判 contract
_TIMEOUT_PHASES = frozenset({"timeout", "cancelled"})
# 规则 4:提取/前置失败 = 契约不符(被检系统结构变了);双拼写兼容
# before_request/after_request(引擎 StrategyPhase 值)
_CONTRACT_PHASES = frozenset({
    "preparing", "extracting", "before_request", "after_request"})


def _steps_of(details: Any) -> list[dict]:
    """details[](LaunchResult 行,与 _detail_row 同形)摊平成 step 行。"""
    steps: list[dict] = []
    for d in details or []:
        if isinstance(d, dict):
            steps.extend(s for s in d.get("steps") or [] if isinstance(s, dict))
    return steps


def classify_outcome(
    *, launch_status: str, exit_code: int | None,
    details: Any, has_assertions: bool,
) -> tuple[str, str, str]:
    """§2.2 分类算法(纯函数,表驱动可测)→ (run, check, check_message)。

    输入为 LaunchResult 的真实字段(launch_status / exit_code / details),
    不经 ``run_result`` counts-only 投影。按序判定命中即停:
    检查规则的唯一来源是场景断言 —— run 面(能不能跑完)与 check 面
    (被检对象是否健康)分立,断言失败 = run ok + check fail。
    """
    steps = _steps_of(details)
    # 1 通道/平台面。launch=timeout 是真实的「超时」(墙钟);error/
    # 其余 launch 故障、M2 校验拒绝(exit 2,case 形态问题,与被检系统
    # 无关)、调试链 halted → channel
    if launch_status == "timeout":
        return "timeout", "unknown", ""
    if launch_status != "ok":
        return "channel", "unknown", ""
    if any(bool(d.get("halted")) for d in details or []
           if isinstance(d, dict)):
        return "channel", "unknown", ""
    overall = "passed" if exit_code == 0 else (
        "gimbal_rejected" if exit_code == 2 else "failed")
    if overall == "gimbal_rejected":
        return "channel", "unknown", ""
    # 2 auth(先于 verifying:响应 401 断言的 [auth_status:] 标记在此归位,
    # 凭证失效暂停的面)
    if any(s.get("error_kind") == "auth" for s in steps):
        return "auth", "unknown", ""
    # 3 超时与网络分立(v1.3,不可再合并 —— 并入 timeout 会让角标
    # 「网络异常」永远出不来)
    if any(s.get("error_kind") == "timeout"
           or s.get("error_phase") in _TIMEOUT_PHASES for s in steps):
        return "timeout", "unknown", ""
    if any(s.get("error_kind") == "transport" for s in steps):
        return "transport", "unknown", ""
    # 4 契约不符:提取/前置失败(依赖 I1 执行器修复)
    if any(s.get("error_phase") in _CONTRACT_PHASES for s in steps):
        return "contract", "unknown", ""
    # 5 断言失败:运行正常,检查不通过
    for s in steps:
        if s.get("error_phase") == "verifying" and s.get("error"):
            return "ok", "fail", str(s.get("error"))[:500]
    # 6 全部通过:有断言 pass / 无断言 none(仅软失败按通过计,D6)
    if overall == "passed":
        return ("ok", "pass" if has_assertions else "none", "")
    # 7 兜底:logic 未归类 → 宁报运行异常,不误报检查不通过
    return "contract", "unknown", ""


def _has_assertions(case: dict | None) -> bool:
    """编译后 case 是否存在 verifying 阶段断言(§2.2 规则 6 输入)。
    集成链不注入断言注册表条目(那是执行队列的 injection 面),
    步骤 strategy 里的 assertion 即唯一来源;disabled 不计。"""
    for step in (case or {}).get("steps") or []:
        if not isinstance(step, dict):
            continue
        for st in step.get("strategy") or []:
            if (isinstance(st, dict) and st.get("kind") == "assertion"
                    and st.get("enabled", True)):
                return True
    return False


STALE_GRACE_SECONDS = 120   # 调度节拍 15s + 准入顺延余量(§2.3)


def is_stale(tpl_cron: str, last_run_at: datetime | None,
             now: datetime | None = None) -> bool:
    """§2.3 双触发法(D10):``now > next_fire(cron, next_fire(cron,
    last_run_at)) + 2min`` 判过期(错过两次应有的触发)。

    取代旧「now - last_run_at > 1h」:*/1 保活任务停摆 1h 才变灰、
    每天一次的任务每天误报;双触发对不规则 cron(仅工作日)同样成立。
    无 cron / 解析失败 / 从未跑过 → 回退旧口径 fail-open(1h / 不过期)。
    """
    from ..core.timeutil import ensure_aware

    now = now or _now()
    if last_run_at is None:
        return False
    lr = ensure_aware(last_run_at)
    try:
        nf1 = next_fire(tpl_cron, lr)
        nf2 = next_fire(tpl_cron, nf1)
        return now > ensure_aware(nf2) + timedelta(seconds=STALE_GRACE_SECONDS)
    except Exception:  # noqa: BLE001 — cron 坏 = 回退旧行为
        return (now - lr) > timedelta(hours=1)


def _period_seconds(cron: str, anchor: datetime | None) -> float:
    """通知节流间隔 = 周期(§2.3,口径同过期计算的双触发法:nf2 -
    nf1)。两步前瞻的触发间距与锚点落点无关 —— 手动执行发生在周期内
    任意时刻(如整点 cron 前两分钟),旧「nf - 锚点」口径会把周期算
    成 2 分钟、节流随之偏松;nf2 - nf1 恒为真实周期。解析失败回退
    1 小时。下限 60s 防畸形 cron。"""
    from ..core.timeutil import ensure_aware

    try:
        base = ensure_aware(anchor) if anchor is not None else _now()
        nf1 = ensure_aware(next_fire(cron, base))
        nf2 = ensure_aware(next_fire(cron, nf1))
        return max(60.0, (nf2 - nf1).total_seconds())
    except Exception:  # noqa: BLE001
        return 3600.0


# ── 半常驻通道(评审 E4-A)───────────────────────────────────────

class _ChannelSlot:
    def __init__(self) -> None:
        self.session: object | None = None
        self.last_used: datetime | None = None
        # 忙闲标记(整体评审 2026-10-15 #1):「有会话」≠「忙」—— 半常驻
        # 通道跑完保留会话,旧实现按 session is None 选槽,两槽预热后恒
        # 回落 slots[0],并发两次挤同一单 run server(409)并在异常分支
        # 关掉另一次正在用的会话。busy 只在借出期间为 True。
        self.busy: bool = False


class IntegrationChannels:
    """N 槽半常驻 gimbal server 通道:执行时借/按需拉起,空闲超
    CHANNEL_IDLE_SECONDS 由调度循环收口(reap_idle)。单槽串行(引擎
    /runs 单 run 设计),槽间并行。

    借还语义:``_acquire`` 在条件变量下独占一个空闲槽(优先已有会话的
    热槽,其次冷槽),全忙则等待归还;``_release`` 归还并唤醒等待者。
    会话层异常只关闭**本次独占**的会话(其他槽不受影响)。
    """

    def __init__(self, size: int = GLOBAL_INFLIGHT_CAP) -> None:
        self.size = max(1, size)
        self.slots = [_ChannelSlot() for _ in range(self.size)]
        self._cond = asyncio.Condition()

    async def _acquire(self) -> _ChannelSlot:
        async with self._cond:
            while True:
                free = [s for s in self.slots if not s.busy]
                if free:
                    # 热槽优先(省一次冷启动);同为热槽取最近使用者
                    warm = [s for s in free if s.session is not None]
                    slot = (max(warm, key=lambda s: s.last_used or _now())
                            if warm else free[0])
                    slot.busy = True
                    return slot
                await self._cond.wait()

    async def _release(self, slot: _ChannelSlot) -> None:
        async with self._cond:
            slot.busy = False
            slot.last_used = _now()
            self._cond.notify()

    async def run_case(self, case_path: str | Path) -> object:
        slot = await self._acquire()
        try:
            from .gimbal_server_session import ServerSession
            if slot.session is None:
                sess = ServerSession()
                await sess.start()
                slot.session = sess
            slot.last_used = _now()
            try:
                return await slot.session.run_case(case_path)
            except Exception:
                # 会话层故障:只收口本槽(独占中,不会误伤别的执行),
                # 下次借到该槽时重新拉起;异常上抛
                sess, slot.session = slot.session, None
                try:
                    await sess.close()
                except Exception:  # noqa: BLE001
                    pass
                raise
        finally:
            await self._release(slot)

    async def reap_idle(self) -> int:
        """回收空闲超时的会话 —— 借出中的槽不回收(长执行不被腰斩)。"""
        to_close: list[object] = []
        async with self._cond:
            for s in self.slots:
                if (not s.busy and s.session is not None
                        and s.last_used is not None
                        and (_now() - s.last_used).total_seconds()
                        > CHANNEL_IDLE_SECONDS):
                    to_close.append(s.session)
                    s.session = None
        for sess in to_close:
            try:
                await sess.close()
            except Exception:  # noqa: BLE001
                pass
        return len(to_close)

    async def close_all(self) -> None:
        for s in self.slots:
            if s.session is not None:
                try:
                    await s.session.close()
                except Exception:  # noqa: BLE001
                    pass
                s.session = None


channels = IntegrationChannels()


# ── 执行 ────────────────────────────────────────────────────────

class IntegrationRunError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _auth_aliases_of(payload: dict, bindings: dict) -> list[str]:
    """注入清单 = serviceBindings 的 authAlias ∪ ${auth.<name>.} 模板
    扫描(与 runs.py「模板扫描 ∪ 绑定」同口径)。"""
    aliases: set[str] = set()
    for b in (bindings or {}).values():
        if isinstance(b, dict) and b.get("authAlias"):
            aliases.add(str(b["authAlias"]))
    aliases.update(_AUTH_TEMPLATE.findall(json.dumps(
        definition_from_payload(payload), ensure_ascii=False, default=str)))
    return sorted(aliases)


# ── W0a(个人侧方案 v1.4 §2):订阅知情同意 ──────────────────────

def _canonical_json(x) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str)


def consent_fingerprint_of(
    scen_payload: dict, scheme_payload: dict, row_dict: dict,
    cron: str, alias_urls: dict,
) -> str:
    """订阅知情同意的内容指纹(小设计 §2.2.1)。

    投影 = 执行形态五要素:场景步骤(逐 step 去 description 展示字段)
    + definition.config、方案(serviceBindings/dataSetSelection/
    dataSetIds,去方案名)、数据集首行注入值、cron、别名 base_url 集合。
    **有意不覆盖**(R3,实现勿再纠结):plate 接口定义(git 评审、
    全员共享同一份,纳入只会全员频繁重确认)、名称/描述等展示性字段。
    canonical JSON(sort_keys)→ sha256 hex。
    """
    definition = definition_from_payload(scen_payload) or {}
    steps = []
    for st in (definition.get("steps") or []):
        steps.append({k: v for k, v in st.items() if k != "description"}
                     if isinstance(st, dict) else st)
    projection = {
        "scenario": {"steps": steps,
                     "config": definition.get("config") or {}},
        "scheme": {k: scheme_payload.get(k) for k in (
            "serviceBindings", "dataSetSelection", "dataSetIds")},
        "dataset_row": row_dict,
        "cron": cron,
        "base_urls": dict(alias_urls or {}),
    }
    return hashlib.sha256(
        _canonical_json(projection).encode("utf-8")).hexdigest()


async def _load_exec_shape(
    db, scheme_id: str | None, scen: ComposerScenario,
) -> tuple[ComposerRunScheme | None, dict, dict, dict, str | None]:
    """执行形态装载(W0a 抽出,run_instance 与订阅面单一实现):
    场景限定的方案(S0①;跨场景/已删 scheme_id → 本场景默认回退)、
    方案载荷、服务绑定、数据集首行(S0① 场景归属收口)、数据集名。
    W1 起 scheme_id 直传(创建前置预览无模板行)。"""
    from .run_dispatcher import find_dataset_by_id
    scheme = None
    if scheme_id:
        scheme = (await db.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id,
            ComposerRunScheme.scenario_id == scen.scenario_id,
        ))).scalar()
    if scheme is None:
        row = (await db.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scen.scenario_id,
            ComposerRunScheme.is_default == True,  # noqa: E712
        ))).scalar()
        scheme = row or (await db.execute(
            select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == scen.scenario_id)
        )).scalars().first()
    scheme_payload = (scheme.payload if scheme else {}) or {}
    bindings = dict(scheme_payload.get("serviceBindings") or {})
    # P1 取一行:首个选中数据集的首行;未选 = 裸基线
    row_dict: dict = {}
    dataset_name: str | None = None
    sel = scheme_payload.get("dataSetSelection") or []
    ds_id = None
    if sel and isinstance(sel[0], dict) and sel[0].get("datasetId"):
        ds_id = str(sel[0]["datasetId"])
    if not ds_id:
        ids = scheme_payload.get("dataSetIds") or []
        ds_id = str(ids[0]) if ids else None
    if ds_id:
        ds = await find_dataset_by_id(db, ds_id)
        # S0①(G-A):数据集必须属于本场景 —— get_row 按 dataset_id
        # 全局查(归属检查只在 data_sets 路由层),跨场景不注入
        if ds is not None and ds.scenario_id == scen.scenario_id:
            dataset_name = ds.name or None
            if ds.rows:
                row_dict = dict(ds.rows[0] or {})
    return scheme, scheme_payload, bindings, row_dict, dataset_name


async def _alias_urls_of(db, scen_payload: dict) -> dict[str, str]:
    """场景引用服务的 base_url 集合(执行期活解析;指纹与物化共用)。

    查询异常**向上抛** —— consent 闸调用方按失败口径收口(本轮不执行
    run=channel):不得以空集算指纹(误判 template_changed)、不得跳过
    比对(绕闸)。非 consent 路径(owner/platform)沿用「增强项失败
    跳过」旧口径,由调用方 try/except。
    """
    from . import service_aliases
    return await service_aliases.base_urls_for(
        db, sorted(referenced_services(
            definition_from_payload(scen_payload).get("steps") or [])))


async def refresh_consent(
    db, tpl: IntegrationTask, scen: ComposerScenario,
    inst: IntegrationTask,
) -> str:
    """写入当前内容指纹与确认时刻(创建/订阅/重新确认共用)。
    别名查询失败向上抛(订阅面 503;创建面 best-effort 跳过)。"""
    _, scheme_payload, _, row_dict, _ = await _load_exec_shape(db, tpl.scheme_id, scen)
    alias_urls = await _alias_urls_of(db, scen.payload)
    fp = consent_fingerprint_of(
        scen.payload, scheme_payload, row_dict, tpl.trigger_cron, alias_urls)
    inst.consent_fingerprint = fp
    inst.consented_at = _now()
    return fp


async def subscription_view(db, tpl: IntegrationTask) -> dict:
    """订阅确认摘要(W0a③):只暴露执行所需结构信息(步骤系统·方法·
    只读标记、凭证别名、服务地址、数据集名、cron),不含场景全文与
    数据值(私有场景可见性边界,§2.1)。"""
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
        if tpl.scenario_id else None
    if scen is None:
        raise IntegrationRunError(
            "scenario_not_found", f"场景不存在: {tpl.scenario_id}")
    _, scheme_payload, bindings, row_dict, dataset_name = \
        await _load_exec_shape(db, tpl.scheme_id, scen)
    aliases = _auth_aliases_of(scen.payload, bindings)
    alias_urls = await _alias_urls_of(db, scen.payload)
    fp = consent_fingerprint_of(
        scen.payload, scheme_payload, row_dict, tpl.trigger_cron, alias_urls)
    steps = []
    for st in (steps_from_payload(scen.payload) or []):
        call = (st or {}).get("call") or {}
        method = str(call.get("method") or "")
        steps.append({
            "service": call.get("service"), "method": method,
            "path": call.get("path"),
            "endpoint": (st or {}).get("endpoint"),
            "readonly": method.upper() in ("GET", "HEAD", "OPTIONS"),
        })
    return {"fingerprint": fp, "steps": steps, "authAliases": aliases,
            "baseUrls": alias_urls, "datasetName": dataset_name,
            "cron": tpl.trigger_cron}


async def scenario_aliases(
    db, scen: ComposerScenario, scheme_id: str | None,
) -> list[str]:
    """场景+方案(可选)的注入清单(W1 创建前置预览用;与执行期
    `_auth_aliases_of` 同口径:方案 authAlias ∪ ${auth.*} 扫描)。"""
    _, _, bindings, _, _ = await _load_exec_shape(db, scheme_id, scen)
    return _auth_aliases_of(scen.payload, bindings)


async def auth_aliases_view(db, tpl: IntegrationTask) -> list[str]:
    """任务当前注入清单(W0b④;与执行期 `_auth_aliases_of` 同口径:
    方案 authAlias ∪ 场景 ${auth.*} 扫描)。场景缺失返回空。"""
    scen = (await db.execute(select(ComposerScenario).where(
        ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
        if tpl.scenario_id else None
    if scen is None:
        return []
    return await scenario_aliases(db, scen, tpl.scheme_id)


async def _pause_consent_changed(
    db, inst: IntegrationTask, tpl: IntegrationTask, *,
    paused_reason: str, message: str,
) -> dict:
    """知情同意闸暂停(非运行失败:不动 last_run_at/fail_streak,不走
    运维/结论通知通道;直接通知持有人)。"""
    inst.state = "paused"
    inst.paused_reason = paused_reason
    inst.last_error = message[:500]
    inst.running_since = None
    await db.commit()
    if inst.holder_id:
        try:
            from .notifications import create_notification
            async with db_module.SessionLocal() as ndb:
                await create_notification(
                    ndb, user_id=inst.holder_id, type_="integration",
                    title=f"集成任务「{tpl.name}」需要重新确认",
                    body=message, link="/integrations")
        except Exception:  # noqa: BLE001 — 通知是增强
            logger.warning("integration: consent notify failed")
    return {"status": "paused", "durationMs": 0, "error": message}


async def notify_subscribers(
    tpl: IntegrationTask, *, title: str, message: str,
) -> int:
    """W2(G-E):向全部非 owner 持有人发通知(模板删除等管理事件)。"""
    async with db_module.SessionLocal() as db:
        holders = (await db.execute(select(IntegrationTask.holder_id).where(
            IntegrationTask.template_id == tpl.id,
            IntegrationTask.holder_id.is_not(None),
            IntegrationTask.holder_id != tpl.owner_id,
        ))).scalars().all()
    for uid in holders:
        try:
            from .notifications import create_notification
            async with db_module.SessionLocal() as ndb:
                await create_notification(
                    ndb, user_id=uid, type_="integration",
                    title=title, body=message, link="/integrations")
        except Exception:  # noqa: BLE001
            logger.warning("integration: subscriber notify failed")
    return len(holders)


async def pause_subscriber_instances(
    tpl: IntegrationTask, *, paused_reason: str, message: str,
) -> int:
    """W0a⑤(G-C):模板转 private 等 —— 暂停全部非 owner 订阅实例并
    逐持有人通知;已暂停/运行中的不动(运行中跑完即停)。返回暂停数。"""
    async with db_module.SessionLocal() as db:
        rows = (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl.id,
            IntegrationTask.holder_id.is_not(None),
            IntegrationTask.holder_id != tpl.owner_id,
            IntegrationTask.state == "idle",
        ))).scalars().all()
        for r in rows:
            r.state = "paused"
            r.paused_reason = paused_reason
            r.last_error = message[:500]
        await db.commit()
        holders = [r.holder_id for r in rows]
        name = tpl.name
    for uid in holders:
        try:
            from .notifications import create_notification
            async with db_module.SessionLocal() as ndb:
                await create_notification(
                    ndb, user_id=uid, type_="integration",
                    title=f"集成任务「{name}」已暂停",
                    body=message, link="/integrations")
        except Exception:  # noqa: BLE001
            logger.warning("integration: pause notify failed")
    return len(holders)


async def run_instance(instance_id: int) -> dict:
    """执行一个实例并回写状态。不写执行记录;明文凭证只存在于
    materialize 产物与通道请求内(case 落临时目录,执行后删除)。

    返回 {status, durationMs, error}(手动执行回显用)。
    """
    from . import plate_client
    from .run_dispatcher import (
        built_in_users, compose_scenario, resolve_exec_auths,
    )

    started = _now()
    async with db_module.SessionLocal() as db:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is None or inst.template_id is None:
            raise IntegrationRunError("instance_not_found", "实例不存在")
        tpl = await db.get(IntegrationTask, inst.template_id)
        if tpl is None or tpl.removed_at is not None:
            raise IntegrationRunError(
                "template_removed", "功能已移除,不可执行")
        scen = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
            if tpl.scenario_id else None
        if scen is None:
            raise IntegrationRunError(
                "scenario_not_found", f"场景不存在: {tpl.scenario_id}")
        scheme, scheme_payload, bindings, row_dict, _ds_name = \
            await _load_exec_shape(db, tpl.scheme_id, scen)

        # 平台模式只读闸(方案 §3:执行前二次检查,保存是第一闸);
        # §3.3:撤销标记后的闸失败 → run=channel,lastError 固定前缀。
        # plate 不可达同样闸失败而非裸抛 —— 裸抛会被 _spawn 吞成
        # warning,实例卡 running 到租约回收,用户看不到任何原因。
        if tpl.identity_mode == "platform":
            try:
                ok, offenders = await is_scenario_read_only(scen.payload)
            except plate_client.PlateUnavailableError:
                return await _finish(
                    db, inst, tpl, "channel", "只读检查未通过: plate 不可达")
            if not ok:
                return await _finish(
                    db, inst, tpl, "channel",
                    f"只读检查未通过: {'、'.join(offenders)}")

        # A-4/W6(版本模型 §6):声明 working 的场景拒绝触发集成 ——
        # 不计入入库标准的预览执行不进集成链。external 不受影响
        # (working_preview 只看锚点系统的钉定状态)。调度路径与手动
        # 触发路由的双闸之一;手动面在 routers/integration.py 先行 409。
        from .run_semantics import working_preview
        if working_preview(scen.payload):
            return await _finish(
                db, inst, tpl, "channel",
                "场景声明 working(预览执行),集成任务拒绝触发:"
                "请在编排器钉定修订后重试(外部服务不受影响)")

        aliases = _auth_aliases_of(scen.payload, bindings)

        # W0a③:订阅知情同意闸 —— 非 owner 的 personal 实例执行前比对
        # 内容指纹,不一致 → paused/template_changed 并通知持有人重新
        # 确认;owner 自有实例不受此闸。别名地址集挪入主会话(指纹与
        # 物化共用):consent 实例查询失败按失败口径收口(本轮不执行
        # run=channel —— 不以空集算指纹、不跳过比对),其余实例维持
        # 「增强项失败跳过」旧口径。
        consent_gate = (tpl.identity_mode == "personal"
                        and inst.holder_id is not None
                        and inst.holder_id != tpl.owner_id)
        try:
            alias_urls = await _alias_urls_of(db, scen.payload)
        except Exception as e:  # noqa: BLE001
            if consent_gate:
                return await _finish(
                    db, inst, tpl, "channel",
                    f"服务地址解析失败,本轮未执行: {e}")
            alias_urls = {}
        if consent_gate:
            fp = consent_fingerprint_of(
                scen.payload, scheme_payload, row_dict,
                tpl.trigger_cron, alias_urls)
            if (inst.consent_fingerprint or "") != fp:
                return await _pause_consent_changed(
                    db, inst, tpl,
                    paused_reason="template_changed",
                    message="模板内容已变更(场景/方案/数据集/周期/服务"
                            "地址),请重新确认订阅后恢复执行")

        holder = (await get_platform_user_id()) \
            if tpl.identity_mode == "platform" else inst.holder_id
        # Y3/方案 §8:缺凭证 → paused/missing_credential(卡片提示去
        # 配置;凭证补齐后复活钩子恢复),不是普通失败
        try:
            exec_auths = await resolve_exec_auths(
                db_module.SessionLocal, holder or -1, aliases)
        except Exception as e:  # noqa: BLE001
            if aliases:
                return await _finish(
                    db, inst, tpl, "auth", f"凭证解析失败: {e}",
                    pause_reason="missing_credential")
            exec_auths = []
        else:
            # S0②(个人侧方案 G-G):任一别名未解析即暂停,一步不执行
            # —— 个人模式允许写操作,部分缺凭证照跑会在第三方系统留
            # 半成品。收紧只落本判定;共享 _resolve_exec_auths 维持
            # 宽松语义(常规测试执行依赖:缺 alias 注入不到 users、
            # 告警后继续)。
            if aliases:
                got = {getattr(a, "alias", "") for a in exec_auths}
                missing = sorted(set(aliases) - got)
                if missing:
                    return await _finish(
                        db, inst, tpl, "auth",
                        f"缺少凭证: {','.join(missing)}",
                        pause_reason="missing_credential")

        scen_payload = scen.payload
        builtins = built_in_users(scen_payload)
        inst_state_vars = dict(inst.state_vars or {})

    # 转换 + 物化 + 执行(DB 会话外跑,避免长事务)
    try:
        # Y4/方案 §5:跨次状态注入 —— state_vars(上次执行按
        # state_mapping 回写的游标)先注入,数据集行覆盖(与
        # 行值 > 场景 vars 同链:显式选择最强)。纯调用点合并,
        # compose_scenario 公共签名不动。
        composed = compose_scenario(
            scen_payload, {**(inst_state_vars or {}), **row_dict})
        converted = (await plate_client.convert(composed)).get("converted") or {}
        case = materialize_run_copy(
            converted,
            service_bindings=bindings,
            resolved_auths=exec_auths,
            built_in_users=builtins,
            carry_context=None,
            alias_base_urls=alias_urls,
        )
        with tempfile.TemporaryDirectory(prefix="integration-case-") as td:
            case_path = Path(td) / "case.json"
            case_path.write_text(
                json.dumps(case, ensure_ascii=False, default=str),
                encoding="utf-8")
            result = await channels.run_case(case_path)
        # I2:直接消费 LaunchResult 真实字段 —— 旧代码读 run_result 投影
        # 的 .get("status")/.get("details"),而该投影按设计 counts-only,
        # 真实链路失败跑不出 failed/auth/outputs(测试桩伪造的形状掩盖
        # 了这一点);分类函数据此判定 run/check(§2.2)
        launch_status = str(getattr(result, "launch_status", "ok") or "ok")
        exit_code = getattr(result, "exit_code", None)
        details = list(getattr(result, "details", None) or [])
        chan_error = str(getattr(result, "error", "") or "")
        # G2/Y2:outputs = 各单元 outputs 合并(场景作用域变量,执行器侧
        # 已脱敏);分类(§2.2)用同一个 details
        outputs: dict = {}
        for d in details:
            if isinstance(d, dict) and isinstance(d.get("outputs"), dict):
                outputs.update(d["outputs"])
        run_status, check_status, check_message = classify_outcome(
            launch_status=launch_status, exit_code=exit_code,
            details=details, has_assertions=_has_assertions(case))
        if launch_status == "timeout":
            error = f"执行超时: {chan_error}"
        elif launch_status != "ok":
            error = f"通道故障({launch_status}): {chan_error}"
        elif run_status == "channel":
            error = f"case 校验拒绝(exit {exit_code}): {chan_error}"
        else:
            error = next(
                (str(s["error"]) for s in _steps_of(details) if s.get("error")),
                "") or (chan_error if run_status != "ok" else "")
    except Exception as e:  # noqa: BLE001 — plate/通道任何故障 = 失败收口
        # 平台内部异常(含 plate convert)→ channel(§2.2 规则 1)
        run_status, check_status, check_message = "channel", "unknown", ""
        error, outputs = str(e)[:500], {}

    async with db_module.SessionLocal() as db:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is None or inst.template_id is None:
            raise IntegrationRunError("instance_gone", "实例已删除")
        tpl = await db.get(IntegrationTask, inst.template_id)
        if tpl is None:
            raise IntegrationRunError("template_gone", "模板已删除")
        return await _finish(
            db, inst, tpl, run_status, error,
            check_status=check_status, check_message=check_message,
            outputs=outputs,
            duration_ms=int((_now() - started).total_seconds() * 1000))


async def _finish(
    db, inst: IntegrationTask, tpl: IntegrationTask, run_status: str,
    error: str, *, check_status: str = "unknown", check_message: str = "",
    outputs: dict | None = None, duration_ms: int = 0,
    pause_reason: str | None = None,
) -> dict:
    """结果回写(集成线 v2 §2.3 重写):run/check 分立落库。

    - **暂停只看 run**:`run=auth` 立即暂停(auth_failed,不按周期重试,
      防错凭证反复登录锁号,方案 §8);missing_credential 原样;
    - **fail_streak / 运维通知**只在 `run ≠ ok` 时累加(D2:check=fail
      不累加、不通知、不暂停);
    - **check**:run ≠ ok(unknown)保留上次结论与文案(卡片标「结论
      可能过期」);run = ok 写新结论,`check_changed_at` 记翻转时刻;
    - **结论变化通知 = 边沿合并**(D9):仅 pass↔fail 翻转发送,
      none↔有结论不发;`check_notified_status ∈ {'', unknown}` 静默
      回写(不落 `check_notified_at` = 间隔按已满足,首拍真翻转不被
      节流挡);被节流的翻转下次执行自动补发;
    - **outputs**:run ≠ ok 不覆盖(卡片继续显示上次数据);run = ok
      无论 check 都写入(fail 的输出本身就是证据)。on_change 落盘
      基准 = 结论翻转**或** outputs 序列化变化(D8);
    - 通知对象:auth 面按身份模式定向(个人=持有人,平台=全体
      admin/operator);结论通知按 D3(个人=持有人,平台=模板 owner)。
    """
    from ..core.timeutil import ensure_aware

    now = _now()
    prev_check = inst.check_status or ""
    prev_outputs_json = _json_of(inst.last_outputs)
    prev_last_run = inst.last_run_at

    if run_status == "auth" and pause_reason is None:
        pause_reason = "auth_failed"
    if pause_reason:
        inst.state = "paused"
        inst.paused_reason = pause_reason
    else:
        inst.state = "idle"
    inst.running_since = None
    inst.last_run_at = now
    inst.run_status = run_status
    inst.last_error = (error or "")[:500]

    # check:run=ok 写新结论;run≠ok 保留上次(§2.3)
    if run_status == "ok":
        if check_status != (inst.check_status or ""):
            inst.check_changed_at = now
        inst.check_status = check_status
        inst.check_message = (check_message or "")[:500]

    # outputs + on_change 基准(§2.3)
    new_outputs = dict(outputs or {})
    _scrub(new_outputs)
    if run_status == "ok":
        changed_out = _json_of(new_outputs) != prev_outputs_json
        if (tpl.result_policy != "on_change"
                or check_status != prev_check or changed_out
                or not inst.last_outputs):
            inst.last_outputs = new_outputs

    # fail_streak 只看 run(check=fail 不累加,§2.3)
    inst.fail_streak = 0 if run_status == "ok" else (inst.fail_streak or 0) + 1

    # Y4/方案 §5:跨次状态回写 —— state_mapping {输出键 → 状态键},
    # 命中的输出复制进 state_vars(下次执行注入为变量,增量游标)。
    # 仅 run=ok 推进(失败跑的一半数据不前移游标);outputs 已过脱敏
    # 键表,复制继承;mapping 为空 = 不回写。
    if (run_status == "ok" and isinstance(tpl.state_mapping, dict)
            and tpl.state_mapping and outputs):
        merged = dict(inst.state_vars or {})
        for src, dst in tpl.state_mapping.items():
            if isinstance(dst, str) and dst and src in (outputs or {}):
                merged[dst] = outputs[src]
        inst.state_vars = merged
    try:
        inst.next_run_at = next_fire(tpl.trigger_cron, now)
    except Exception:  # noqa: BLE001 — cron 坏 = 顺延一小时,不炸调度
        inst.next_run_at = now + timedelta(hours=1)

    # ── 结论通知边沿合并(D9)── 状态机在 commit 前算好,发送在 commit 后
    notify_check: str | None = None
    if run_status == "ok" and inst.check_status in ("pass", "fail"):
        prev_notified = inst.check_notified_status or ""
        if prev_notified in ("pass", "fail"):
            period = _period_seconds(tpl.trigger_cron, prev_last_run)
            last_notified = ensure_aware(inst.check_notified_at)
            due = last_notified is None or (
                (now - last_notified).total_seconds() >= period)
            if inst.check_status != prev_notified and due:
                notify_check = inst.check_status
                inst.check_notified_status = inst.check_status
                inst.check_notified_at = now
        else:
            # 初始化静默:只回写状态,不落通知时间(= 间隔已满足)。
            # 已知取舍:存量迁移后首跑直接 fail 这次不发 —— 此类实例
            # 改造前一直在走 fail_streak 运维通知,不存在「没人知道」。
            inst.check_notified_status = inst.check_status
    await db.commit()

    # 通知(方案 §8):auth 面立即且按身份模式定向;普通运行失败 →
    # 连续 FAIL_STREAK_NOTIFY 次才通知(P1 口径,发全体 admin/operator);
    # 结论翻转通知(D9/D3)。
    auth_notify = (run_status == "auth")
    streak_notify = (run_status not in ("ok", "auth")
                     and inst.fail_streak >= FAIL_STREAK_NOTIFY
                     and inst.fail_streak % FAIL_STREAK_NOTIFY == 0)
    if auth_notify or streak_notify or notify_check is not None:
        try:
            from .notifications import create_notification
            async with db_module.SessionLocal() as ndb:
                if auth_notify and tpl.identity_mode == "personal" \
                        and inst.holder_id:
                    uids = [inst.holder_id]   # 凭证是持有人自己的
                elif notify_check is not None:
                    # D3:结论通知 —— 个人=持有人;平台=模板 owner
                    # (平台实例的 holder 是系统用户,不是收件人)
                    uids = [inst.holder_id if tpl.identity_mode == "personal"
                            else tpl.owner_id]
                else:
                    uids = (await ndb.execute(
                        select(User.id).where(User.role.in_(("admin", "operator")),
                                              User.is_system == False)  # noqa: E712
                    )).scalars().all()
                if auth_notify:
                    title = f"集成任务「{tpl.name}」凭证失效,已暂停"
                    body = ("认证失败(auth)——请在"
                            + ("我的凭证" if tpl.identity_mode == "personal"
                               else "平台凭证")
                            + "中更新凭证后自动恢复")
                elif notify_check is not None:
                    if notify_check == "fail":
                        title = f"集成任务「{tpl.name}」检查不通过"
                        body = (inst.check_message
                                or "断言未通过,详见卡片")[0:200]
                    else:
                        title = f"集成任务「{tpl.name}」检查已恢复"
                        body = "检查结论由不通过恢复为通过"
                else:
                    title = f"集成任务「{tpl.name}」连续失败 {inst.fail_streak} 次"
                    body = (inst.last_error or "")[:200]
                for uid in uids:
                    await create_notification(
                        ndb, user_id=uid, type_="integration",
                        title=title, body=body, link="/integrations")
        except Exception:  # noqa: BLE001 — 通知是增强
            logger.warning("integration: notify failed")
    return {"status": "passed" if run_status == "ok" else "failed",
            "durationMs": duration_ms, "error": error}


# ── 调度(评审 E5:短持 advisory lock)────────────────────────────

_SCHED_LOCK_KEY = 0x696E7473   # 'ints' — 集成调度固定锁号
_inflight: dict[tuple[int, str], int] = {}   # (holder, system) → 计数


def _inflight_ok(tpl: IntegrationTask, holder_id: int | None) -> bool:
    total = sum(_inflight.values())
    if total >= GLOBAL_INFLIGHT_CAP:
        return False
    if tpl.target_system and _inflight.get((holder_id or 0, tpl.target_system), 0) \
            >= PER_HOLDER_SYSTEM_CAP:
        return False
    return True


def _inflight_add(tpl: IntegrationTask, holder_id: int | None, delta: int) -> None:
    key = (holder_id or 0, tpl.target_system or "")
    cur = _inflight.get(key, 0) + delta
    if cur <= 0:
        _inflight.pop(key, None)
    else:
        _inflight[key] = cur


async def _recover_stuck(db) -> int:
    """running_since 超租约 → 回 idle + timeout(方案 §5 超时回收)。"""
    cutoff = _now() - timedelta(seconds=RUN_LEASE_SECONDS)
    rows = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.template_id.is_not(None),
            IntegrationTask.state == "running",
            IntegrationTask.running_since.is_not(None),
            IntegrationTask.running_since < cutoff,
        ).limit(20))).scalars().all()
    for r in rows:
        r.state = "idle"
        r.running_since = None
        r.run_status = "timeout"     # 租约超时是真实的「超时」面
        r.last_error = "运行租约超时,调度器回收"
        try:
            r.next_run_at = next_fire(
                (await db.get(IntegrationTask, r.template_id)).trigger_cron,
                _now())
        except Exception:  # noqa: BLE001
            r.next_run_at = _now() + timedelta(hours=1)
    if rows:
        await db.commit()
    return len(rows)


async def _claim_due(db, limit: int = 10) -> list[int]:
    now = _now()
    rows = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.template_id.is_not(None),
            IntegrationTask.state == "idle",
            IntegrationTask.enabled == True,   # noqa: E712
            IntegrationTask.next_run_at.is_not(None),
            IntegrationTask.next_run_at <= now,
        ).limit(limit))).scalars().all()
    claimed: list[int] = []
    for r in rows:
        tpl = await db.get(IntegrationTask, r.template_id)
        if tpl is None or tpl.removed_at is not None:
            r.enabled = False      # 模板没了:停实例
            continue
        if not _inflight_ok(tpl, r.holder_id):
            r.next_run_at = now + timedelta(minutes=1)   # 超限顺延
            continue
        res = (await db.execute(
            update(IntegrationTask)
            .where(IntegrationTask.id == r.id,
                   IntegrationTask.state == "idle")
            .values(state="running", running_since=now)
            .returning(IntegrationTask.id))).scalar()
        if res is not None:
            _inflight_add(tpl, r.holder_id, 1)
            claimed.append(r.id)
    await db.commit()
    return claimed


async def _spawn(instance_id: int) -> None:
    tpl_id = None
    holder = None
    try:
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, instance_id)
            if inst is not None:
                holder = inst.holder_id
                tpl_id = inst.template_id
        await run_instance(instance_id)
    except Exception as e:  # noqa: BLE001 — 单实例失败不炸调度循环
        logger.warning("integration: run instance {} failed: {}", instance_id, e)
    finally:
        if tpl_id is not None:
            async with db_module.SessionLocal() as db:
                tpl = await db.get(IntegrationTask, tpl_id)
            if tpl is not None:
                _inflight_add(tpl, holder, -1)


async def scheduler_tick() -> dict:
    """15s 一拍:通道空闲收口 → 僵尸回收 → (短持锁)认领到期实例。"""
    reaped = await channels.reap_idle()
    async with db_module.SessionLocal() as db:
        stuck = await _recover_stuck(db)
    claimed: list[int] = []
    engine = db_module.engine
    if engine.dialect.name == "postgresql":
        async with engine.connect() as conn:
            got = (await conn.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": _SCHED_LOCK_KEY})
            ).scalar()
            if not got:
                return {"claimed": [], "reaped": reaped, "stuck": stuck}
            try:
                async with db_module.SessionLocal() as db:
                    claimed = await _claim_due(db)
            finally:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": _SCHED_LOCK_KEY})
                await conn.commit()
    else:
        async with db_module.SessionLocal() as db:
            claimed = await _claim_due(db)
    for iid in claimed:
        asyncio.create_task(_spawn(iid))
    return {"claimed": claimed, "reaped": reaped, "stuck": stuck}


async def ensure_instance(
    tpl: IntegrationTask, *, holder_id: int | None = None,
) -> IntegrationTask | None:
    """模板的实例(幂等;Y3 起支持个人模式)。

    platform = 平台系统用户的唯一实例(创建模板时同步建,P1 行为);
    personal = ``holder_id`` 的订阅实例(不存在则建 —— 订阅即创建,
    方案 §4;缺 holder 返回 None)。名从模板(NOT NULL;列表只取模板行)。
    """
    if tpl.identity_mode == "personal":
        if holder_id is None:
            return None
        holder = holder_id
    else:
        holder = await get_platform_user_id()
        if holder is None:
            return None
    async with db_module.SessionLocal() as db:
        row = (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl.id,
            IntegrationTask.holder_id == holder,
        ))).scalar()
        if row is None:
            # 同表两层:实例行 name 落模板名(NOT NULL;列表只取模板行,
            # 实例名不参与展示)
            inst = IntegrationTask(
                name=tpl.name, owner_id=tpl.owner_id,
                template_id=tpl.id, holder_id=holder,
                state="idle", enabled=True, next_run_at=_now())
            db.add(inst)
            try:
                await db.commit()
                await db.refresh(inst)
                return inst
            except Exception as _e:
                logger.opt(exception=True).warning("ensure_instance insert failed: {}", _e)
                await db.rollback()
                row = (await db.execute(select(IntegrationTask).where(
                    IntegrationTask.template_id == tpl.id,
                    IntegrationTask.holder_id == holder,
                ))).scalar()
                return row
        return row


async def revive_paused_instances(user_id: int | None = None) -> int:
    """凭证复活钩子(auth_sessions 路由调用,方案 §8/设计 §3)。

    恢复范围:paused_reason ∈ {auth_failed, missing_credential} 的实例
    —— 个人模式且
    user_id 匹配 holder;平台模式不受 user_id 过滤(平台凭证池只有
    operator/admin 能改,改了即视为恢复信号)。恢复 = state=idle +
    next_run_at=now(下拍调度即重试);paused_reason 清空。
    manual 暂停的实例不受影响。返回恢复条数(审计/日志用)。
    """
    now = _now()
    async with db_module.SessionLocal() as db:
        stmt = select(IntegrationTask).where(
            IntegrationTask.template_id.isnot(None),
            IntegrationTask.state == "paused",
            IntegrationTask.paused_reason.in_(("auth_failed",
                                               "missing_credential")),
        )
        rows = (await db.execute(stmt)).scalars().all()
        revived = 0
        for inst in rows:
            tpl = await db.get(IntegrationTask, inst.template_id)
            if tpl is None:
                continue
            if (tpl.identity_mode == "personal" and user_id is not None
                    and inst.holder_id != user_id):
                continue          # 他人更新凭证 ≠ 我的凭证恢复
            inst.state = "idle"
            inst.paused_reason = ""   # 列 NOT NULL:空串 = 无暂停原因
            inst.next_run_at = now
            revived += 1
        if revived:
            await db.commit()
    return revived
