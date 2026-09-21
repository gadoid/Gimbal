"""Schemas for executions (V3 — 每-run 明细已随 exec_runs 表退役)。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: str
    status: str
    total_runs: int
    passed: int
    failed: int
    started_at: datetime | None
    finished_at: datetime | None
    config: dict
    # 执行时场景快照是否存在(存量行 False → 前端"导出场景"置灰)。
    has_scenario_snapshot: bool = False
    # 批次键(执行设计 §1.2):队列逐条发起的 N 条共用;单条发起/历史行
    # 为 None。列表据此渲染批徽标 + 按批筛。
    batch_id: str | None = None
    # 连续第 N 次失败(§3.2 信号列;同 owner 同 scenario 失败链长,失败单
    # 自身计入)。仅 list 端点计算填充;detail/其他消费方恒 0。
    consecutive_failures: int = 0
    # P2-2:归属台账快照(注销后带「已注销」后缀)
    owner_name: str | None = Field(default=None, alias="ownerName")


class ExecutionListItemOut(BaseModel):
    """列表行形态(M1 响应投影,PG迁移方案 §2.2 债 4 补刀):去 ``config``
    —— ``config_json`` 是凭证引用面(injectedAuths/serviceBindings),整列
    随每行列表下发是敏感面泄漏;详情页保留完整 ``config``。

    ``config_summary`` 是列表 UI 既有的四个非敏感展示字段的窄投影
    (schemeName/nRuns/parallel/stepTo/authFailFast),不携带凭证引用。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    scenario_id: str
    status: str
    total_runs: int
    passed: int
    failed: int
    started_at: datetime | None
    finished_at: datetime | None
    config_summary: dict = Field(default_factory=dict, alias="configSummary")
    has_scenario_snapshot: bool = False
    batch_id: str | None = None
    consecutive_failures: int = 0


class ExecutionListOut(BaseModel):
    """Page 信封(§4.1):既有 {items,total} 补齐 page/pageSize 即向后兼容。"""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ExecutionListItemOut]
    total: int
    page: int = 1
    page_size: int = Field(default=200, alias="pageSize")


class ExecutionSummaryOut(BaseModel):
    """执行记录顶部 KPI 带(执行设计 §3.5/§4.1):Execution 计数器/时间戳
    就能算的那部分 — 行级分布(耗时分布/失败原因构成)不落库,不在本
    响应里(§0 纪律 3:跨执行聚合不出来,等行级落库)。口径 = 查询者自己
    的执行(§5.1:执行的可见范围只有自己跑的,owner 隔离不因聚合放开)。"""

    model_config = ConfigDict(populate_by_name=True)

    # 统计窗(天);窗口只作用于「已完成」的量,进行中的单不受窗约束
    window_days: int = Field(default=7, alias="windowDays", ge=1, le=90)
    total_executions: int = Field(default=0, alias="totalExecutions")
    total_runs: int = Field(default=0, alias="totalRuns")
    passed_runs: int = Field(default=0, alias="passedRuns")
    failed_runs: int = Field(default=0, alias="failedRuns")
    # 运行级通过率 = passed / (passed + failed);分母 0 → None(前端显「—」)
    pass_rate: float | None = Field(default=None, alias="passRate")
    # execution 级平均时长(秒;有 started_at 与 finished_at 的终态单)。
    # 行级耗时分布不可得(不落库),只给 execution 级(§3.4 第 3 条)。
    avg_duration_sec: float | None = Field(default=None, alias="avgDurationSec")
    # 反复失败:窗内终态单里,同 scenario 连续失败 ≥3 次的 scenario 个数
    repeat_failure_scenarios: int = Field(default=0, alias="repeatFailureScenarios")
    # 进行中(queued/running)— 不受窗约束,发起中的单必须可见
    active_executions: int = Field(default=0, alias="activeExecutions")


class ExecutionRowOut(BaseModel):
    """行级状态(spec §9.1)— registry(asdict 的 snake_case)与 JSONL
    回放(camelCase 键)两种输入都收(populate_by_name),响应按别名
    序列化为 camelCase。"""

    model_config = ConfigDict(populate_by_name=True)

    seq: int
    dataset_id: str | None = Field(default=None, alias="datasetId")
    # 注入族行的条目 id(spec v2 §8);数据集行/旧 JSONL 回放缺键 → None。
    injection_id: str | None = Field(default=None, alias="injectionId")
    row_index: int = Field(default=0, alias="rowIndex")
    rep: int = 0
    status: str
    case_dir: str = Field(default="", alias="caseDir")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")


class ExecutionRowsOut(BaseModel):
    """M6(债 5):行级分页信封 —— {items,total,page,pageSize}。"""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ExecutionRowOut]
    total: int = 0
    page: int = 1
    page_size: int = Field(default=200, alias="pageSize")
