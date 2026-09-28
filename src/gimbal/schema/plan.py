"""schema/plan.py — Plan / Unit：所有执行的目标形态（v2 §2，v2.1 批次 B）。

设计要点：
  - **一条执行路径**：run scenario / run suite / run launch 全部先编译出
    Plan 再交 Engine 执行；单场景 = 只有一个单元的隐式 aggregate Plan
    （n_runs / retry / parallel 等语义只实现一次）；
  - Unit.id 是事件 / 计划清单 / 平台台账三方 join 锚点
    （别名 + 展开序号；aggregate 模式下 = scenarioId）；
  - Unit.scenario 是**生效副本**（快照语义，执行器只读）；
  - Unit.inputs 是统一输入注入原语（连线 / step_from / --var 三处复用，
    单元启动时注入为 scenario vars）——批次 B 先落地机制，聚合语义批次 C；
  - UnitPolicy 的 n_runs / retry / lock 字段先定形，乘法语义批次 D 落地
    （批次 B 期间非默认值会被 validate 拒绝并说明）。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from gimbal.schema.scenario import Scenario


class UnitPolicy(BaseModel):
    """单元级执行策略。"""
    n_runs: int = Field(default=1, ge=1, description="运行期重复次数（批次 D 落地乘法语义）")
    retry: int = Field(default=0, ge=0, description="失败后自动重跑次数（批次 D）")
    timeout: Optional[float] = Field(
        default=None, description="单元超时（秒）；每次 attempt 单独计时，"
        "超时记失败（error_phase=timeout）并触发 retry（P1-12）")
    lock: Optional[str] = Field(default=None, description="互斥锁标签（批次 D）")
    # P1-12：retry 退避与条件（由 scenario config.retry 映射，见 unit_policy_from）
    backoff_seconds: float = Field(default=0.0, ge=0, description="重试退避间隔（秒）；退避期间不持 lock")
    retry_on: list[str] = Field(default_factory=list, description="重试条件标签；空=任何失败都重试，非空=失败签名子串命中才重试")


def unit_policy_from(scenario: "Scenario", overrides: Optional[dict] = None) -> UnitPolicy:
    """scenario config.retry（RetryPolicy）→ UnitPolicy 映射（v2.1 review P1-12）。

    编译/normalize 路径的统一物化点（单场景隐式 Plan 与 graph desugar 共用）：

      - maxAttempts  → retry = maxAttempts - 1（首次执行之外的自动重跑次数）；
      - backoffSeconds → backoff_seconds（重试退避间隔；退避期间不持 lock）；
      - retryOn      → retry_on（空列表 = 任何失败都重试；非空 = 失败签名
                       命中才重试——当前无 error code 分类体系，按错误文本
                       子串匹配的简化口径，见 scheduler/plan.py `_error_signature`）。

    overrides（编排层 UnitDecl.policy_kwargs：n_runs/retry/lock/...）显式
    声明优先，逐字段覆盖场景级 config.retry 的映射结果。
    """
    fields: dict[str, Any] = {}
    retry_cfg = getattr(getattr(scenario, "config", None), "retry", None)
    if retry_cfg is not None:
        fields["retry"] = max(0, int(retry_cfg.maxAttempts) - 1)
        fields["backoff_seconds"] = max(0.0, float(retry_cfg.backoffSeconds or 0.0))
        fields["retry_on"] = [str(t) for t in (retry_cfg.retryOn or [])]
    fields.update(overrides or {})
    return UnitPolicy(**fields)


class PlanPolicy(BaseModel):
    """Plan 级执行策略。"""
    parallel: int = Field(default=1, ge=1, le=64, description="单元级并发上限；1=串行")
    fail_fast: Optional[bool] = Field(default=None, description="None=沿用全局配置 cfg.fail_fast")
    timeout: Optional[float] = Field(default=None, description="整个 Plan 的超时（秒）")


class Unit(BaseModel):
    """执行单元：一份生效副本 + 注入 + 依赖 + 策略。"""

    id: str
    scenario: Scenario
    inputs: dict[str, Any] = Field(default_factory=dict)
    needs: list[str] = Field(default_factory=list, description="上游 unit id（批次 C bind 落地）")
    shared_key: Optional[str] = Field(default=None, description="非空即 shared，按 key 去重（批次 C）")
    policy: UnitPolicy = Field(default_factory=UnitPolicy)

    @property
    def is_shared(self) -> bool:
        return self.shared_key is not None


class Plan(BaseModel):
    """编译产物：Engine 的唯一执行输入。

    括号（before/after）判定语义（v2.1 review P0-4；调度见
    scheduler/plan.py 的 before 判定门，计数见 core/runner.py
    `_assemble_aggregate`）：

      - before 单元失败/超时 → 其所有主体单元记 ``blocked``（不执行），
        ``exit_code=1``；after 括号不受影响，仍总是执行；
      - after 单元失败 → ``failed += 1``，``exit_code=1``（不影响其他行）；
      - 括号行计入 ``total``（before/after 各占一行），与主体行统一组装；
      - ``exit_code = 0`` 当且仅当 ``failed == error == halted == blocked == 0``。

    after 输入可见性（v2.1 review P0-5；业务清理总案"取消主体创建的订单"）：

      - after 单元可见上游 = before 括号 + **全部主体单元**（bind 期主体
        输出恒可见，无须 needs 声明）；
      - bind 期无上游供给的 after 输入不再 CompileError：单元 id 记入
        ``after_optional`` 成文（有供给的输入照常连线）；
      - 运行期主体未产出某连线名（失败/blocked/无该输出）→ after 该输入
        注入 ``None`` 并发 ``debug.after_input_missing`` 事件——after 必达，
        缺输入注入 None 不 Crash（见 scheduler/plan.py `_resolve_inputs`）。
    """

    units: list[Unit] = Field(default_factory=list)
    before: list[Unit] = Field(default_factory=list, description="suite 级前置括号（批次 C 落地语义）")
    after: list[Unit] = Field(default_factory=list, description="suite 级后置括号（批次 C）")
    policy: PlanPolicy = Field(default_factory=PlanPolicy)

    # ── 执行期元信息（编译器填写，Engine 消费）─────────────────
    suite_id: str = "__suite__"
    suite_name: str = "Suite"
    # 单场景隐式 Plan 标记：调试能力判定等场景用（v2：单单元 + n_runs=1 才可调试）
    implicit: bool = False
    # 编译模式（aggregate / compose / fanout / chain；批次 B 仅 aggregate）
    mode: Literal["aggregate", "compose", "fanout", "chain"] = "aggregate"
    # bind 产物（批次 C）：unit_id → {输入名: "上游unit_id:输出名"}
    # 运行期由调度器解析：inputs[名] = results[上游].outputs[输出]
    wiring: dict[str, dict[str, str]] = Field(default_factory=dict)
    # P0-5：bind 期即无上游供给的 after 单元 id（不 CompileError 成文记录；
    # 其有供给的输入照常连线，缺失语义由运行期注入 None 兜底）
    after_optional: set[str] = Field(default_factory=set)
    # P1-04：声明式订阅规格（graph.subscribe 透传；Engine 在 run 边界挂载，
    # 编译期校验见 events/subscribe.compile_subscribe）
    subscribe: Optional[list[dict[str, Any]]] = Field(
        default=None, description="声明式订阅规格（P1-04；CLI --subscribe 同款写法）")
    # N1（D-6 保留）：suite 判定门透传（Engine 判定阶段消费;checks 在编译期
    # 已展开进单元策略,不再随 Plan 携带）
    gates: Optional[list[Any]] = Field(
        default=None, description="suite 判定门（N1/D6;None=无门")

    @property
    def all_units_in_order(self) -> list[Unit]:
        """before + units + after 的展开序（判定与对账的完整清单）。"""
        return [*self.before, *self.units, *self.after]

    @model_validator(mode="after")
    def _check_units(self) -> "Plan":
        if not (self.before or self.units or self.after):
            raise ValueError("Plan 至少要有一个单元（before/units/after 其一）")
        ids = [u.id for u in self.all_units_in_order]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Plan 内 unit id 重复: {sorted(dupes)}")
        if self.implicit and (len(self.units) != 1 or self.before or self.after):
            raise ValueError("implicit Plan 必须恰好一个 units 单元且无 before/after")
        return self
