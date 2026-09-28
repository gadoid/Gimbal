"""scheduler/plan.py — Plan 调度器（v2 §运行时；批次 B 建立、批次 C 拓扑化）。

顺序：before 括号（串行先行；P0-4：任一失败/超时 → 主体全部记 blocked，
不提交执行）→ units 拓扑调度 → after 拓扑（串行，**必达**：无论
before/units 失败/取消都执行）→ 判定交 Engine。

拓扑调度（needs 依赖）：
  - ready = needs 全部完成的单元；serial 按声明序、parallel 用线程池
    （并发上限 = PlanPolicy.parallel）；
  - **blocked 级联**：某依赖失败/被阻塞的单元记 blocked（传递）；
  - fail-fast：取消尚未开始的单元（cancelled），在跑的不中断；
  - **运行期 wiring 解析**：单元启动时 inputs = 字面量 ∪ 连线值
    （连线值 = 上游 ScenarioRunResult.outputs[输出名]，按 Plan.wiring）。
    上游异常/无输出 → 该输入缺失：注入时跳过并告警（bind 已在编译期
    校验过存在性，运行期缺失只可能是上游失败路径，此时本单元多为 blocked）。
    **after 单元例外（P0-5）**：after 可见上游 = before + 全部主体，缺供给
    输入编译期不报错（Plan.after_optional 成文）；运行期连线值缺失 →
    注入 None + ``debug.after_input_missing`` 事件（清理必达，不 Crash）。

三种乘法的组合语义（v2 §三种乘法；总案开工门槛要求成文）：

  repeat   编译期展开为独立单元（id=ref#k），计入计划清单，事件/台账独立；
  n_runs   运行期重复同一单元（同一 unit id，结果带 run_index/attempts）；
           计划清单计数 = 单元数（P1-11 按单元口径）；某次失败即停止该
           单元后续 n_runs（稳定性语义：跑 N 次都过才算过）；
  retry    同一次 run 内失败后自动重跑，至多 R 次，不计清单只记
           retries_used；跑过即算过（不标 repaired——那是人工路径，批次 E）。

  组合执行序：外层 n_runs，内层 retry —— 每 run 先跑，失败重试至通过或
  次数用尽；run 结果（最终尝试）记入 attempts。lock 标签在"依赖满足、
  即将运行"时获取、乘法全部完成后释放（不持锁等依赖 → 无死锁；单元
  只持一把锁 → 无跨锁环）。

P1-12 补充语义：

  UnitPolicy.timeout   每次 attempt 用线程池 future.result(timeout=…) 包裹；
                       超时 → 该 attempt 记失败（step 级 error_phase="timeout"
                       留痕）并照常触发 retry。超时线程无法安全中止，弃跑
                       弃结果（线程自行结束后回收）。
  backoff_seconds      重试退避间隔；**退避期间不持 lock**（review Focus #5：
                       放锁睡、醒后重取——同标签其他单元可趁窗口推进）。
  retry_on             空 = 任何失败都重试；非空 = 失败签名子串命中才重试
                       （无 error code 分类体系，签名 = step error 文本拼接 /
                       异常字符串，简化口径见 `_error_signature`）。
  PlanPolicy.timeout   Plan 全局 deadline：到点尚未启动的主体单元置
                       cancelled（已启动的跑完照常计数；括号必达不受影响）。
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, wait
from dataclasses import dataclass, field
from typing import Any, Callable

from gimbal.log import get_logger
from gimbal.schema.plan import Plan, Unit

logger = get_logger(__name__)


@dataclass
class PlanOutcome:
    """一次 Plan 调度的结果（Engine 按计划清单对账）。"""
    results: dict[str, Any] = field(default_factory=dict)   # unit_id → 执行产出（含异常对象）
    blocked: set[str] = field(default_factory=set)          # 依赖失败级联
    cancelled: set[str] = field(default_factory=set)        # fail-fast 取消

    def status_of(self, unit_id: str) -> str:
        if unit_id in self.results:
            return "done"
        if unit_id in self.blocked:
            return "blocked"
        if unit_id in self.cancelled:
            return "cancelled"
        return "pending"


# attempt 超时弃跑后 join 被弃线程的时限上限（P0-08.1：跟随单元内
# 最大的 step 协议超时 + 固定余量；未声明任何协议超时时回落本默认值，
# 对齐 http 默认请求超时 30s）
_ABANDON_JOIN_TIMEOUT_SEC = 30.0
_ABANDON_JOIN_MARGIN_SEC = 5.0


def _abandon_join_timeout(unit: "Any") -> float:
    """join 被弃 attempt 的时限：max(step 协议超时) + 余量。

    协议超时取各 step ``call.timeout``（http 默认 30s；其它协议声明了
    同名字段同样计入）；余量覆盖 step 边界检测与收尾清理的耗时。
    在飞请求至多跑满协议超时——join 上限盖住它即可避免"join 先放弃、
    重试与被弃请求并发重复发送"。
    """
    worst = 0.0
    for step in getattr(unit.scenario, "steps", []) or []:
        t = getattr(getattr(step, "call", None), "timeout", None)
        if isinstance(t, (int, float)) and t > worst:
            worst = float(t)
    if worst <= 0:
        return _ABANDON_JOIN_TIMEOUT_SEC
    return worst + _ABANDON_JOIN_MARGIN_SEC


class PlanScheduler:
    """跑一个 Plan：括号先行/必达 + units 拓扑调度 + 运行期连线解析。"""

    def __init__(self, event_bus: Any = None) -> None:
        # lock 标签 → 互斥锁（"依赖满足、即将运行"时获取，防死锁）
        self._locks: dict[str, "threading.Lock"] = {}
        # 锁表自身的互斥（并行分支多线程并发调用 _lock_for）
        self._table_lock = threading.Lock()
        # 可选事件总线（P0-5：after 缺失输入注入 None 时发 debug.* 事件留痕）
        self._event_bus = event_bus

    def _lock_for(self, tag: str):
        with self._table_lock:
            return self._locks.setdefault(tag, threading.Lock())

    def run(
        self,
        plan: Plan,
        run_unit: Callable[[Unit, dict], Any],
        *,
        fail_fast: bool = False,
    ) -> PlanOutcome:
        outcome = PlanOutcome()

        # P1-12：Plan 全局 deadline（PlanPolicy.timeout，单调钟）；
        # 只作用于主体单元——括号必达语义（before 先行 / after 清理）不受影响
        deadline = None
        if plan.policy.timeout is not None:
            deadline = time.monotonic() + float(plan.policy.timeout)

        # 1. before 括号（串行先行；P0-4：任一失败 → 判定门拦下主体）
        for unit in plan.before:
            outcome.results[unit.id] = self._run_one(run_unit, unit, self._resolve_inputs(plan, outcome, unit))

        # 1.5 P0-4 判定门：before 任一失败/超时（非 passed/异常/无结果）→
        # 主体全部置 blocked、不提交执行（串行/并行两条路径共用此门）；
        # after 不受影响，仍在下方必达执行。
        if self._before_failed(plan, outcome):
            for unit in plan.units:
                outcome.blocked.add(unit.id)
        else:
            # 2. units 主体（拓扑）
            if plan.policy.parallel > 1:
                self._schedule_parallel(plan, run_unit, outcome, fail_fast, deadline)
            else:
                self._schedule_serial(plan, run_unit, outcome, fail_fast, deadline)

        # 3. after 括号（串行，必达——units 失败/取消不影响其执行）
        for unit in plan.after:
            outcome.results[unit.id] = self._run_one(run_unit, unit, self._resolve_inputs(plan, outcome, unit))

        return outcome

    # ── 输入解析（字面量 ∪ 连线值）────────────────────────────

    def _resolve_inputs(self, plan: Plan, outcome: PlanOutcome, unit: Unit) -> dict:
        inputs = dict(unit.inputs or {})
        wires = plan.wiring.get(unit.id) or {}
        after_ids = {a.id for a in plan.after}
        for input_name, src in wires.items():
            try:
                src_unit, output_name = src.split(":", 1)
            except ValueError:
                logger.warning("[PlanScheduler] 非法连线地址: {}={!r}", input_name, src)
                continue
            upstream = outcome.results.get(src_unit)
            outputs = getattr(upstream, "outputs", None) or {}
            if output_name in outputs:
                inputs[input_name] = outputs[output_name]
            elif unit.id in after_ids:
                # P0-5：after 必达（业务清理）——主体未产出该名（失败/blocked/
                # 无此输出）→ 注入 None 继续执行，不因主体失败而缺输入 Crash
                inputs[input_name] = None
                self._emit_after_input_missing(unit.id, input_name, src)
            else:
                logger.warning(
                    "[PlanScheduler] 连线取值缺失: {} ← {}（上游无此输出或未成功），跳过注入",
                    input_name, src,
                )
        return inputs

    def _emit_after_input_missing(self, unit_id: str, input_name: str, src: str) -> None:
        """P0-5：after 缺失输入注入 None 的留痕（debug.* 事件；无总线只记日志）。"""
        logger.info(
            "[PlanScheduler] after 输入缺失注入 None: unit={} input={} ← {}",
            unit_id, input_name, src,
        )
        bus = self._event_bus
        if bus is None:
            return
        try:
            from gimbal.events.types import DebugAfterInputMissingEvent
            bus.publish(DebugAfterInputMissingEvent(
                unit_id=unit_id, input_name=input_name, source=src,
            ))
        except Exception:  # noqa: BLE001  # 事件留痕失败不影响调度
            logger.debug("[PlanScheduler] after_input_missing 事件发布失败: {}", unit_id)

    # ── 串行拓扑 ─────────────────────────────────────────────

    def _schedule_serial(self, plan: Plan, run_unit, outcome: PlanOutcome,
                         fail_fast: bool, deadline: float | None = None) -> None:
        units = {u.id: u for u in plan.units}
        needs_map = {u.id: [n for n in u.needs if n in units] for u in plan.units}
        stop_scheduling = False

        for unit in plan.units:
            failed_or_blocked = [
                n for n in needs_map[unit.id]
                if self._upstream_bad(outcome, n)
            ]
            if failed_or_blocked:
                outcome.blocked.add(unit.id)
                continue
            pending = [n for n in needs_map[unit.id] if outcome.status_of(n) != "done"]
            if pending:
                # 声明序遍历中上游尚未完成：正常情况不会发生（串行按序），
                # 出现即前向依赖（needs 指向后面的单元）→ 下一轮补跑
                continue
            if stop_scheduling or self._expired(deadline):
                # P1-12：plan deadline 到点，未启动的单元置 cancelled
                outcome.cancelled.add(unit.id)
                continue
            outcome.results[unit.id] = self._run_one(
                run_unit, unit, self._resolve_inputs(plan, outcome, unit),
            )
            if fail_fast and self._result_failed(outcome.results[unit.id]):
                stop_scheduling = True

        # 前向依赖补跑轮（声明序不满足拓扑序时；循环已在编译期拒绝）
        progress = True
        while progress:
            progress = False
            for unit in plan.units:
                if outcome.status_of(unit.id) != "pending":
                    continue
                if any(self._upstream_bad(outcome, n) for n in needs_map[unit.id]):
                    outcome.blocked.add(unit.id)
                    progress = True
                    continue
                if all(outcome.status_of(n) == "done" for n in needs_map[unit.id]):
                    if stop_scheduling or self._expired(deadline):
                        outcome.cancelled.add(unit.id)
                    else:
                        outcome.results[unit.id] = self._run_one(
                            run_unit, unit, self._resolve_inputs(plan, outcome, unit),
                        )
                        if fail_fast and self._result_failed(outcome.results[unit.id]):
                            stop_scheduling = True
                    progress = True

        # 兜底：仍未决的（理论不可达，循环已被编译期拒绝）记 cancelled
        for unit in plan.units:
            if outcome.status_of(unit.id) == "pending":
                outcome.cancelled.add(unit.id)

    # ── 并行拓扑（ready-set 线程池）──────────────────────────

    def _schedule_parallel(self, plan: Plan, run_unit, outcome: PlanOutcome,
                           fail_fast: bool, deadline: float | None = None) -> None:
        units = {u.id: u for u in plan.units}
        needs_map = {u.id: [n for n in u.needs if n in units] for u in plan.units}
        lock = threading.Lock()
        stop_scheduling = False
        futures: dict[Future, Unit] = {}

        def ready_units() -> list[Unit]:
            ready = []
            for u in plan.units:
                if outcome.status_of(u.id) != "pending":
                    continue
                if any(self._upstream_bad(outcome, n) for n in needs_map[u.id]):
                    outcome.blocked.add(u.id)
                    continue
                if all(outcome.status_of(n) == "done" for n in needs_map[u.id]):
                    ready.append(u)
            return ready

        def cancel_pending() -> None:
            for u in plan.units:
                if outcome.status_of(u.id) == "pending":
                    outcome.cancelled.add(u.id)

        def cascade_blocked() -> None:
            """blocked 级联：依赖失败/阻塞者的传递闭包。"""
            changed = True
            while changed:
                changed = False
                for u in plan.units:
                    if outcome.status_of(u.id) != "pending":
                        continue
                    if any(self._upstream_bad(outcome, n) for n in needs_map[u.id]):
                        outcome.blocked.add(u.id)
                        changed = True

        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=plan.policy.parallel,
                                   thread_name_prefix="gimbal-unit") as pool:
            with lock:
                initial = ready_units()
                for u in initial:
                    if self._expired(deadline):
                        # P1-12：deadline 已到，首批也不提交
                        outcome.cancelled.add(u.id)
                        continue
                    futures[pool.submit(self._run_one, run_unit, u, self._resolve_inputs(plan, outcome, u))] = u

            while futures:
                done, _ = wait(list(futures), return_when=FIRST_COMPLETED)
                with lock:
                    for fut in done:
                        unit = futures.pop(fut)
                        try:
                            outcome.results[unit.id] = fut.result()
                        except Exception as exc:  # noqa: BLE001
                            outcome.results[unit.id] = exc
                        if self._result_failed(outcome.results[unit.id]):
                            cascade_blocked()
                            if fail_fast:
                                stop_scheduling = True
                    if stop_scheduling or self._expired(deadline):
                        # P1-12：fail-fast / plan deadline → 未启动的置 cancelled；
                        # 在飞的跑完照常计数（不抢占线程）
                        cancel_pending()
                        continue
                    for u in ready_units():
                        if u.id not in {fu.id for fu in futures.values()}:
                            if self._expired(deadline):
                                outcome.cancelled.add(u.id)
                                continue
                            futures[pool.submit(self._run_one, run_unit, u, self._resolve_inputs(plan, outcome, u))] = u
                # 空转保护：无在飞且无 ready 但仍有 pending（理论不可达）
                if not futures:
                    with lock:
                        cascade_blocked()
                        cancel_pending()
                    break

        # P1-12 兜底：deadline 到点仍未提交的 pending（如首批即被拦）置 cancelled
        if self._expired(deadline):
            cancel_pending()

    # ── 判定辅助 ─────────────────────────────────────────────

    @staticmethod
    def _before_failed(plan: Plan, outcome: PlanOutcome) -> bool:
        """P0-4 判定门：before 括号任一未通过（失败/超时/异常/无结果）。

        判定门 fail-closed：结果缺失同样视为失败（主体宁可 blocked 不可误跑）。
        """
        for unit in plan.before:
            result = outcome.results.get(unit.id)
            if result is None or PlanScheduler._result_failed(result):
                return True
        return False

    @staticmethod
    def _upstream_bad(outcome: PlanOutcome, need_id: str) -> bool:
        """上游失败（结果未通过/异常）或被阻塞 → 下游应 blocked。"""
        if need_id in outcome.blocked:
            return True
        result = outcome.results.get(need_id)
        if result is None:
            return False
        if isinstance(result, Exception):
            return True
        return getattr(result, "passed", True) is False

    @staticmethod
    def _result_failed(result: Any) -> bool:
        if isinstance(result, Exception):
            return True
        return getattr(result, "passed", True) is False

    # ── 乘法执行核（n_runs × retry）+ lock + timeout ──────────

    def _run_one(self, run_unit: Callable[[Unit, dict], Any], unit: Unit, inputs: dict) -> Any:
        policy = unit.policy
        lock = self._lock_for(policy.lock) if policy.lock else None
        if lock is None:
            return self._run_multiplication(run_unit, unit, inputs, policy)

        def _backoff(seconds: float) -> None:
            # P1-12 Review Focus #5：退避期间不持 lock——放锁睡、醒后重取，
            # 同标签其他单元可趁退避窗口推进（死锁面不变：仍单锁、不持锁等依赖）
            if seconds <= 0:
                return
            lock.release()
            try:
                time.sleep(seconds)
            finally:
                lock.acquire()

        lock.acquire()   # 依赖已满足才到这里；阻塞等待同标签单元完成
        try:
            return self._run_multiplication(run_unit, unit, inputs, policy,
                                            backoff_hook=_backoff)
        finally:
            lock.release()

    def _run_multiplication(self, run_unit, unit: Unit, inputs: dict, policy,
                            backoff_hook: Callable[[float], None] | None = None) -> Any:
        """外层 n_runs × 内层 retry；聚合为单个结果（attempts/run_index）。"""
        raw_results: list[Any] = []
        for run_no in range(1, max(1, policy.n_runs) + 1):
            result, retries_used = self._run_with_retry(
                run_unit, unit, inputs, policy, backoff_hook,
            )
            try:
                result.run_index = run_no
                result.retries_used = retries_used
            except Exception:  # noqa: BLE001  # 非 ScenarioRunResult 的替身结果
                pass
            raw_results.append(result)
            if self._result_failed(result):
                break   # 稳定性语义：某次 run 失败即停止后续 n_runs
        return self._aggregate_attempts(raw_results)

    def _run_with_retry(self, run_unit, unit: Unit, inputs: dict, policy,
                        backoff_hook: Callable[[float], None] | None = None):
        """单次 run：失败自动重跑至多 policy.retry 次；返回 (最终结果, 重试次数)。

        P1-12：
          - 每次 attempt 受 policy.timeout 包裹（None = 不限时直跑）；
          - retry_on 非空时仅失败签名命中才重试（空 = 任何失败都重试）；
          - 重试间退避 policy.backoff_seconds；持锁单元经 backoff_hook
            放锁睡醒重取（退避期间不持 lock）。
        """
        retry = max(0, policy.retry)
        retry_on = [t for t in (getattr(policy, "retry_on", None) or []) if t]
        timeout = getattr(policy, "timeout", None)
        backoff = float(getattr(policy, "backoff_seconds", 0.0) or 0.0)
        sleep_fn = backoff_hook or time.sleep
        attempt = 0
        while True:
            result = self._attempt(run_unit, unit, inputs, timeout)
            if not self._result_failed(result) or attempt >= retry:
                return result, attempt
            if retry_on and not self._error_matches(result, retry_on):
                logger.info(
                    "[PlanScheduler] retry_on 未命中，不重试: unit_id={} tags={}",
                    unit.id, retry_on,
                )
                return result, attempt
            attempt += 1
            logger.info("[PlanScheduler] retry: unit_id={} 第 {} 次重跑（上限 {}）",
                        unit.id, attempt, retry)
            if backoff > 0:
                sleep_fn(backoff)

    def _attempt(self, run_unit, unit: Unit, inputs: dict, timeout: float | None) -> Any:
        """单次 attempt：timeout=None 直跑（历史路径）；否则线程池包裹限时。

        超时的执行线程无法安全中止——**置位协作取消事件后弃跑弃结果**：
        被弃线程在下一个 step 边界/重试点检测到事件即停（防止超时后的
        retry 与被弃线程并发重复发请求——下单类接口的重复下单面）；
        在飞的单笔请求无法中断（至多与一次重试短暂重叠,有界）。
        本 attempt 以 error_phase="timeout" 的失败结果收口并交由上层重试。
        """
        if timeout is None:
            return self._safe_run(run_unit, unit, inputs)
        import concurrent.futures as cf
        cancel = threading.Event()
        # 注意：不用 with 语句——__exit__ 会 shutdown(wait=True) 等卡死任务，
        # 使限时失效；此处 wait=False + cancel_futures 尽快脱身
        pool = cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="gimbal-attempt")
        try:
            fut = pool.submit(self._safe_run, run_unit, unit, inputs, cancel)
            try:
                return fut.result(timeout=max(0.0, float(timeout)))
            except cf.TimeoutError:
                cancel.set()   # 协作取消:被弃线程在 step 边界自行终止
                logger.warning("[PlanScheduler] 单元超时(已置取消,join 被弃 attempt): unit_id={} timeout={}s",
                               unit.id, timeout)
                # 在飞请求无法中断——**join 被弃 attempt 真正退出后**再重试/返回
                # （锁在此内层,退出前锁不释放）:不等会造成新 attempt 与被弃请求
                # 并发重复发送（重叠至多 retry+1）,以及弃请求跨锁释放继续跑。
                # join 上限 = 单元内最大协议超时 + 余量（P0-08.1,见
                # _abandon_join_timeout；未声明协议超时时回落默认 30s）
                join_bound = _abandon_join_timeout(unit)
                try:
                    fut.result(timeout=join_bound)
                except cf.TimeoutError:
                    logger.error(
                        "[PlanScheduler] 被弃 attempt 超过 join 上限 {:.1f}s 仍未退出: unit_id={}",
                        join_bound, unit.id)
                except Exception:  # noqa: BLE001 — 被弃 attempt 以异常收尾,正是退出
                    pass
                return self._timeout_result(unit, float(timeout))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _timeout_result(unit: Unit, timeout: float) -> Any:
        """超时 attempt 的收口结果：status=failed（计入 failed 口径），
        step 级保留 error_phase="timeout" 留痕（reporter/平台可区分）。"""
        from datetime import datetime, timezone

        from gimbal.core.scenario_runner import ScenarioRunResult
        from gimbal.statemachine.engine import StepRunResult
        now = datetime.now(timezone.utc)
        return ScenarioRunResult(
            scenario_id=unit.id,
            status="failed",
            step_results=[StepRunResult(
                step_id="__unit_timeout__",
                status="failed",
                error=f"unit timeout after {timeout}s (policy.timeout)",
                error_phase="timeout",
                duration_ms=timeout * 1000.0,
            )],
            started_at=now,
            ended_at=now,
        )

    @staticmethod
    def _error_signature(result: Any) -> str:
        """失败签名（P1-12 简化口径）：step error 文本按序拼接；异常取 str。

        当前体系没有 error code 分类学，retryOn 只能按标签子串匹配签名
        （断言失败文本含实际值 / 协议错误文本含状态码，均可作为标签锚点）。
        """
        if isinstance(result, Exception):
            return str(result)
        parts = []
        for s in getattr(result, "step_results", None) or []:
            err = getattr(s, "error", None)
            if err:
                parts.append(str(err))
        return "\n".join(parts)

    @classmethod
    def _error_matches(cls, result: Any, retry_on: list[str]) -> bool:
        """retryOn 非空时：签名命中任一标签才允许重试。"""
        signature = cls._error_signature(result)
        return any(tag in signature for tag in retry_on)

    @staticmethod
    def _expired(deadline: float | None) -> bool:
        """P1-12：plan deadline 是否已到（None = 无 deadline）。"""
        return deadline is not None and time.monotonic() >= deadline

    @staticmethod
    def _safe_run(run_unit, unit: Unit, inputs: dict,
                  cancel: "threading.Event | None" = None) -> Any:
        # 签名探测（不能 try/except TypeError——体内的 TypeError 会被误吞并
        # 以无 cancel 形态重跑,造成重复执行）：二参旧签名按旧口径调用
        import inspect
        try:
            arity = len(inspect.signature(run_unit).parameters)
        except (TypeError, ValueError):
            arity = 2
        try:
            if cancel is not None and arity >= 3:
                return run_unit(unit, inputs, cancel=cancel)
            return run_unit(unit, inputs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[PlanScheduler] 单元执行异常: unit_id={}", unit.id)
            return exc

    @staticmethod
    def _aggregate_attempts(raw_results: list) -> Any:
        """聚合 n_runs 的多次 run：以最后一次为基座，附 attempts 简况。"""
        if not raw_results:
            return None
        base = raw_results[-1]
        attempts = []
        for r in raw_results:
            attempts.append({
                "run": getattr(r, "run_index", 0),
                "status": getattr(r, "status", "error"),
                "passed": bool(getattr(r, "passed", False)),
                "retries": getattr(r, "retries_used", 0),
                "outputs": getattr(r, "outputs", None) is not None,
            })
        try:
            base.attempts = attempts
        except Exception:  # noqa: BLE001
            pass
        return base
