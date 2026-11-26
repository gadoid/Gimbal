from .user import User
from .constant_entry import ConstantEntry
from .execution import (
    Execution, ExecutionRow, ExecutionSnapshot, ExecutionJob, ExecutionStep,
)
from .composer_scenario import ComposerScenario
from .composer_data_set import ComposerDataSet
from .composer_run_scheme import ComposerRunScheme
# 权限域二期 P1:suite 成员层(组合外键 = 库层安全边界)
from .suite import Suite, SuiteMember
from .scenario_endpoint_ref import ScenarioEndpointRef
from .adaptation_batch import AdaptationBatch
from .adaptation_snapshot import AdaptationSnapshot
from .adaptation_op import AdaptationOp
from .carry_binding import CarryGlobalDefault, CarryServiceBinding
from .board_card import BoardCard
from .environment import Environment
# 部署表(M2a S2:地址第 ③ 层按 (基础服务, 环境) 取址)
from .deployment import Deployment
# 补注册:此前未进 __init__ —— 空库 baseline 的
# create_all 看不到该表时由迁移用 sa.JSON 兜底建列,PG 上落成
# json(模型口径 JsonVar=jsonb)。
from .integration_task import IntegrationTask
# 权限域新表
from .permission import AuditLog, Notification, UserPref, UserStar
# 场景域事件日志(时间线唯一数据源)
from .activity_event import ActivityEvent
# 访问令牌(webhook v4)+ 回调投递行
from .access_token import AccessToken, AccessTokenScope
from .webhook_delivery import WebhookDelivery
# 项目区(M2a S1.0:只建表不上码;授权面随 S1.1+)
from .project import Project, ProjectMember
from .project_promotion import ProjectPromotion
# UPC M2:账户组合(§5/§20.2)+ Scheme 修复状态审计与诊断(§20.3)
from .account_combo import AccountCombo
from .scheme_repair import SchemeRepairEvent, SchemeRepairDiagnosis
# §14.2 场景资产包恢复幂等台账(UPC M2 最小闭环)
from .scenario_asset_import import ScenarioAssetImport
# 执行配置(执行配置分层①:场景外部支撑的跨场景载体,scope user|project)
from .exec_config import ExecConfig
# 服务注册重构(2026-11-16,docs/service-registry-redesign.md §1):
# 主档(注册簿)/环境×系统实例/身份条目(别名迁居,env 显式化)/账户实体化
from .service import Service
from .system_env_instance import SystemEnvInstance
from .service_identity import ServiceIdentity
from .auth_account import AuthAccount
# promotion 身份授权(决策 1 阶段 4,迁移 0064;共享即授权,§5)
from .identity_grant import IdentityProjectGrant

__all__ = [
    "User",
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
    "IntegrationTask",
    "AuditLog",
    "Notification",
    "ActivityEvent",
    "UserPref",
    "UserStar",
    "AccessToken",
    "AccessTokenScope",
    "WebhookDelivery",
    "Project",
    "ProjectMember",
    "Deployment",
    "ExecConfig",
    "Service",
    "SystemEnvInstance",
    "ServiceIdentity",
    "AuthAccount",
    "IdentityProjectGrant",
    "AccountCombo",
    "SchemeRepairEvent",
    "SchemeRepairDiagnosis",
    "ScenarioAssetImport",
]

from .report_definition import ReportDefinitionRow  # noqa: F401
