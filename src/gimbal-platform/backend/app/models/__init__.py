from .user import User
from .auth_session import AuthSession
from .constant_entry import ConstantEntry
from .execution import (
    Execution, ExecutionRow, ExecutionSnapshot, ExecutionJob,
)
from .composer_scenario import ComposerScenario
from .composer_data_set import ComposerDataSet
from .composer_run_scheme import ComposerRunScheme
# 权限域二期 P1:suite 成员层(组合外键 = 库层安全边界)
from .share_ref import ShareRef
from .suite import Suite, SuiteMember
from .scenario_endpoint_ref import ScenarioEndpointRef
from .adaptation_batch import AdaptationBatch
from .adaptation_snapshot import AdaptationSnapshot
from .adaptation_op import AdaptationOp
from .carry_binding import CarryGlobalDefault, CarryServiceBinding
from .board_card import BoardCard
from .environment import Environment
from .external_endpoint import ExternalEndpoint
from .service_alias import ServiceAlias
# ⑤(2026-10-13)补注册:此前未进 __init__ —— 空库 baseline 的
# create_all 看不到该表时由迁移用 sa.JSON 兜底建列,PG 上落下
# json(模型口径 JsonVar=jsonb),SQLite 面看不出漂移。
from .integration_task import IntegrationTask
# 权限域新表(M2 = P1a:只建表不上码;接口代码随 M2.5/P2)
from .permission import AuditLog, Notification, UserPref, UserStar
# 场景域事件日志(2026-09-23 批次 F3:时间线唯一数据源)
from .activity_event import ActivityEvent

__all__ = [
    "User",
    "AuthSession",
    "ConstantEntry",
    "Execution",
    "ExecutionRow",
    "ExecutionJob",
    "ExecutionSnapshot",
    "ComposerScenario",
    "ComposerDataSet",
    "ComposerRunScheme",
    "Suite",
    "SuiteMember",
    "ScenarioEndpointRef",
    "AdaptationBatch",
    "AdaptationSnapshot",
    "AdaptationOp",
    "CarryGlobalDefault",
    "CarryServiceBinding",
    "BoardCard",
    "Environment", "ExternalEndpoint", "ServiceAlias",
    "IntegrationTask",
    "AuditLog",
    "Notification",
    "ActivityEvent",
    "UserPref",
    "UserStar",
    "ShareRef",
]

from .report_definition import ReportDefinitionRow  # noqa: F401
