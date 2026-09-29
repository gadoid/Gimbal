"""platform 全部 endpoint 契约的聚合入口。

每端点一个文件 <域>/<动作>.py,只导出一个 EndpointSpec 实例常量。
本模块聚合所有实例供 PlateRegistry 一键注册。

**本文件由 contract_gen_py 生成,重新生成即覆盖** —— 端点文件可以手改,
这个不行。
"""
from typing import Final

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.systems.platform.endpoint.activity.get_root import (
    ACTIVITY_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_batches import (
    ADAPTATIONS_GET_BATCHES,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_batches_by_batch_id import (
    ADAPTATIONS_GET_BATCHES_BY_BATCH_ID,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_impact import (
    ADAPTATIONS_GET_IMPACT,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_impact_bulk import (
    ADAPTATIONS_GET_IMPACT_BULK,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_impact_summary import (
    ADAPTATIONS_GET_IMPACT_SUMMARY,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_refs_drift import (
    ADAPTATIONS_GET_REFS_DRIFT,
)
from gimbal_plate.systems.platform.endpoint.adaptations.get_unindexed_steps import (
    ADAPTATIONS_GET_UNINDEXED_STEPS,
)
from gimbal_plate.systems.platform.endpoint.adaptations.patch_ops_by_op_id import (
    ADAPTATIONS_PATCH_OPS_BY_OP_ID,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_batches import (
    ADAPTATIONS_POST_BATCHES,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_batches_by_batch_id_ops import (
    ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_OPS,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_batches_by_batch_id_rollback import (
    ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_ROLLBACK,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_carry_batches import (
    ADAPTATIONS_POST_CARRY_BATCHES,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_catalog_diff import (
    ADAPTATIONS_POST_CATALOG_DIFF,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_ops_by_op_id_apply import (
    ADAPTATIONS_POST_OPS_BY_OP_ID_APPLY,
)
from gimbal_plate.systems.platform.endpoint.adaptations.post_ops_by_op_id_skip import (
    ADAPTATIONS_POST_OPS_BY_OP_ID_SKIP,
)
from gimbal_plate.systems.platform.endpoint.admin.get_audit_logs import (
    ADMIN_GET_AUDIT_LOGS,
)
from gimbal_plate.systems.platform.endpoint.auth.get_me import (
    AUTH_GET_ME,
)
from gimbal_plate.systems.platform.endpoint.auth.post_change_password import (
    AUTH_POST_CHANGE_PASSWORD,
)
from gimbal_plate.systems.platform.endpoint.auth.post_login import (
    AUTH_POST_LOGIN,
)
from gimbal_plate.systems.platform.endpoint.auth.post_refresh import (
    AUTH_POST_REFRESH,
)
from gimbal_plate.systems.platform.endpoint.auth.post_register import (
    AUTH_POST_REGISTER,
)
from gimbal_plate.systems.platform.endpoint.auths.delete_by_auth_id import (
    AUTHS_DELETE_BY_AUTH_ID,
)
from gimbal_plate.systems.platform.endpoint.auths.get_by_alias_references import (
    AUTHS_GET_BY_ALIAS_REFERENCES,
)
from gimbal_plate.systems.platform.endpoint.auths.get_by_auth_id import (
    AUTHS_GET_BY_AUTH_ID,
)
from gimbal_plate.systems.platform.endpoint.auths.get_root import (
    AUTHS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.auths.patch_by_auth_id import (
    AUTHS_PATCH_BY_AUTH_ID,
)
from gimbal_plate.systems.platform.endpoint.auths.post_by_auth_id_test import (
    AUTHS_POST_BY_AUTH_ID_TEST,
)
from gimbal_plate.systems.platform.endpoint.auths.post_root import (
    AUTHS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.board_cards.delete_by_card_id import (
    BOARD_CARDS_DELETE_BY_CARD_ID,
)
from gimbal_plate.systems.platform.endpoint.board_cards.patch_by_card_id import (
    BOARD_CARDS_PATCH_BY_CARD_ID,
)
from gimbal_plate.systems.platform.endpoint.board_cards.post_by_card_id_demote import (
    BOARD_CARDS_POST_BY_CARD_ID_DEMOTE,
)
from gimbal_plate.systems.platform.endpoint.board_cards.post_by_card_id_promote import (
    BOARD_CARDS_POST_BY_CARD_ID_PROMOTE,
)
from gimbal_plate.systems.platform.endpoint.board_cards.post_root import (
    BOARD_CARDS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.carry.get_bindings import (
    CARRY_GET_BINDINGS,
)
from gimbal_plate.systems.platform.endpoint.carry.get_bindings_by_service import (
    CARRY_GET_BINDINGS_BY_SERVICE,
)
from gimbal_plate.systems.platform.endpoint.carry.get_bindings_by_service_fields import (
    CARRY_GET_BINDINGS_BY_SERVICE_FIELDS,
)
from gimbal_plate.systems.platform.endpoint.carry.get_defaults import (
    CARRY_GET_DEFAULTS,
)
from gimbal_plate.systems.platform.endpoint.carry.get_drift import (
    CARRY_GET_DRIFT,
)
from gimbal_plate.systems.platform.endpoint.carry.put_bindings_by_service import (
    CARRY_PUT_BINDINGS_BY_SERVICE,
)
from gimbal_plate.systems.platform.endpoint.carry.put_defaults import (
    CARRY_PUT_DEFAULTS,
)
from gimbal_plate.systems.platform.endpoint.catalog.get_services import (
    CATALOG_GET_SERVICES,
)
from gimbal_plate.systems.platform.endpoint.constants.delete_by_entry_id import (
    CONSTANTS_DELETE_BY_ENTRY_ID,
)
from gimbal_plate.systems.platform.endpoint.constants.get_by_entry_id import (
    CONSTANTS_GET_BY_ENTRY_ID,
)
from gimbal_plate.systems.platform.endpoint.constants.get_root import (
    CONSTANTS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.constants.patch_by_entry_id import (
    CONSTANTS_PATCH_BY_ENTRY_ID,
)
from gimbal_plate.systems.platform.endpoint.constants.post_root import (
    CONSTANTS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.data_sets.delete_by_dataset_id import (
    DATA_SETS_DELETE_BY_DATASET_ID,
)
from gimbal_plate.systems.platform.endpoint.data_sets.get_by_dataset_id import (
    DATA_SETS_GET_BY_DATASET_ID,
)
from gimbal_plate.systems.platform.endpoint.data_sets.get_root import (
    DATA_SETS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.data_sets.put_by_dataset_id import (
    DATA_SETS_PUT_BY_DATASET_ID,
)
from gimbal_plate.systems.platform.endpoint.endpoint_catalog.get_by_endpoint_id_full import (
    ENDPOINT_CATALOG_GET_BY_ENDPOINT_ID_FULL,
)
from gimbal_plate.systems.platform.endpoint.endpoint_catalog.post_by_endpoint_id_field_state_60b108 import (
    ENDPOINT_CATALOG_POST_BY_ENDPOINT_ID_FIELD_STATE_60B108,
)
from gimbal_plate.systems.platform.endpoint.endpoint_catalog.post_resolve_paths import (
    ENDPOINT_CATALOG_POST_RESOLVE_PATHS,
)
from gimbal_plate.systems.platform.endpoint.endpoints.get_by_endpoint_id_board import (
    ENDPOINTS_GET_BY_ENDPOINT_ID_BOARD,
)
from gimbal_plate.systems.platform.endpoint.executions.delete_by_execution_id import (
    EXECUTIONS_DELETE_BY_EXECUTION_ID,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id import (
    EXECUTIONS_GET_BY_EXECUTION_ID,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_case_artifact import (
    EXECUTIONS_GET_BY_EXECUTION_ID_CASE_ARTIFACT,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_debug import (
    EXECUTIONS_GET_BY_EXECUTION_ID_DEBUG,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_debug_output import (
    EXECUTIONS_GET_BY_EXECUTION_ID_DEBUG_OUTPUT,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_events import (
    EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_events_counts import (
    EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_COUNTS,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_events_stream import (
    EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_STREAM,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_rows import (
    EXECUTIONS_GET_BY_EXECUTION_ID_ROWS,
)
from gimbal_plate.systems.platform.endpoint.executions.get_by_execution_id_scenario_snapshot import (
    EXECUTIONS_GET_BY_EXECUTION_ID_SCENARIO_SNAPSHOT,
)
from gimbal_plate.systems.platform.endpoint.executions.get_root import (
    EXECUTIONS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.executions.get_summary import (
    EXECUTIONS_GET_SUMMARY,
)
from gimbal_plate.systems.platform.endpoint.executions.post_by_execution_id_cancel import (
    EXECUTIONS_POST_BY_EXECUTION_ID_CANCEL,
)
from gimbal_plate.systems.platform.endpoint.executions.post_by_execution_id_debug_command import (
    EXECUTIONS_POST_BY_EXECUTION_ID_DEBUG_COMMAND,
)
from gimbal_plate.systems.platform.endpoint.executions.post_by_execution_id_rerun import (
    EXECUTIONS_POST_BY_EXECUTION_ID_RERUN,
)
from gimbal_plate.systems.platform.endpoint.generator_catalog.get_by_kind_full import (
    GENERATOR_CATALOG_GET_BY_KIND_FULL,
)
from gimbal_plate.systems.platform.endpoint.generator_catalog.get_root import (
    GENERATOR_CATALOG_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.handoff.post_root import (
    HANDOFF_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.health.get_root import (
    HEALTH_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.me.get_preferences import (
    ME_GET_PREFERENCES,
)
from gimbal_plate.systems.platform.endpoint.me.put_preferences_by_key import (
    ME_PUT_PREFERENCES_BY_KEY,
)
from gimbal_plate.systems.platform.endpoint.notifications.get_handoff_unread import (
    NOTIFICATIONS_GET_HANDOFF_UNREAD,
)
from gimbal_plate.systems.platform.endpoint.notifications.get_preferences import (
    NOTIFICATIONS_GET_PREFERENCES,
)
from gimbal_plate.systems.platform.endpoint.notifications.get_root import (
    NOTIFICATIONS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.notifications.get_unread_count import (
    NOTIFICATIONS_GET_UNREAD_COUNT,
)
from gimbal_plate.systems.platform.endpoint.notifications.post_announcements import (
    NOTIFICATIONS_POST_ANNOUNCEMENTS,
)
from gimbal_plate.systems.platform.endpoint.notifications.post_read import (
    NOTIFICATIONS_POST_READ,
)
from gimbal_plate.systems.platform.endpoint.notifications.put_preferences import (
    NOTIFICATIONS_PUT_PREFERENCES,
)
from gimbal_plate.systems.platform.endpoint.query_views.get_by_name_rows import (
    QUERY_VIEWS_GET_BY_NAME_ROWS,
)
from gimbal_plate.systems.platform.endpoint.query_views.get_root import (
    QUERY_VIEWS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.report_definitions.delete_by_definition_id import (
    REPORT_DEFINITIONS_DELETE_BY_DEFINITION_ID,
)
from gimbal_plate.systems.platform.endpoint.report_definitions.get_by_definition_id import (
    REPORT_DEFINITIONS_GET_BY_DEFINITION_ID,
)
from gimbal_plate.systems.platform.endpoint.report_definitions.get_root import (
    REPORT_DEFINITIONS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.report_definitions.post_root import (
    REPORT_DEFINITIONS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.report_definitions.put_by_definition_id import (
    REPORT_DEFINITIONS_PUT_BY_DEFINITION_ID,
)
from gimbal_plate.systems.platform.endpoint.run.post_precheck import (
    RUN_POST_PRECHECK,
)
from gimbal_plate.systems.platform.endpoint.runs.post_root import (
    RUNS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.scenario_filter_groups.delete_by_bucket_by_group_id import (
    SCENARIO_FILTER_GROUPS_DELETE_BY_BUCKET_BY_GROUP_ID,
)
from gimbal_plate.systems.platform.endpoint.scenario_filter_groups.get_root import (
    SCENARIO_FILTER_GROUPS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.scenario_filter_groups.post_root import (
    SCENARIO_FILTER_GROUPS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.scenarios.delete_by_scenario_id import (
    SCENARIOS_DELETE_BY_SCENARIO_ID,
)
from gimbal_plate.systems.platform.endpoint.scenarios.delete_by_scenario_id_run_schemes_by_s_6a5300 import (
    SCENARIOS_DELETE_BY_SCENARIO_ID_RUN_SCHEMES_BY_S_6A5300,
)
from gimbal_plate.systems.platform.endpoint.scenarios.get_by_scenario_id import (
    SCENARIOS_GET_BY_SCENARIO_ID,
)
from gimbal_plate.systems.platform.endpoint.scenarios.get_by_scenario_id_draft import (
    SCENARIOS_GET_BY_SCENARIO_ID_DRAFT,
)
from gimbal_plate.systems.platform.endpoint.scenarios.get_by_scenario_id_run_schemes import (
    SCENARIOS_GET_BY_SCENARIO_ID_RUN_SCHEMES,
)
from gimbal_plate.systems.platform.endpoint.scenarios.get_facets import (
    SCENARIOS_GET_FACETS,
)
from gimbal_plate.systems.platform.endpoint.scenarios.get_root import (
    SCENARIOS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.scenarios.get_signals import (
    SCENARIOS_GET_SIGNALS,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_by_scenario_id_copy import (
    SCENARIOS_POST_BY_SCENARIO_ID_COPY,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_by_scenario_id_data_sets import (
    SCENARIOS_POST_BY_SCENARIO_ID_DATA_SETS,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_by_scenario_id_publish import (
    SCENARIOS_POST_BY_SCENARIO_ID_PUBLISH,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_by_scenario_id_run_schemes import (
    SCENARIOS_POST_BY_SCENARIO_ID_RUN_SCHEMES,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_by_scenario_id_star import (
    SCENARIOS_POST_BY_SCENARIO_ID_STAR,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_by_scenario_id_unpublish import (
    SCENARIOS_POST_BY_SCENARIO_ID_UNPUBLISH,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_preview_plate import (
    SCENARIOS_POST_PREVIEW_PLATE,
)
from gimbal_plate.systems.platform.endpoint.scenarios.post_root import (
    SCENARIOS_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.scenarios.put_by_scenario_id import (
    SCENARIOS_PUT_BY_SCENARIO_ID,
)
from gimbal_plate.systems.platform.endpoint.scenarios.put_by_scenario_id_run_schemes_by_scheme_id import (
    SCENARIOS_PUT_BY_SCENARIO_ID_RUN_SCHEMES_BY_SCHEME_ID,
)
from gimbal_plate.systems.platform.endpoint.service_aliases.delete_by_alias_name import (
    SERVICE_ALIASES_DELETE_BY_ALIAS_NAME,
)
from gimbal_plate.systems.platform.endpoint.service_aliases.get_root import (
    SERVICE_ALIASES_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.service_aliases.patch_by_alias_name import (
    SERVICE_ALIASES_PATCH_BY_ALIAS_NAME,
)
from gimbal_plate.systems.platform.endpoint.service_aliases.post_root import (
    SERVICE_ALIASES_POST_ROOT,
)
from gimbal_plate.systems.platform.endpoint.services.get_by_service_grid import (
    SERVICES_GET_BY_SERVICE_GRID,
)
from gimbal_plate.systems.platform.endpoint.strategy_catalog.get_by_kind_full import (
    STRATEGY_CATALOG_GET_BY_KIND_FULL,
)
from gimbal_plate.systems.platform.endpoint.strategy_catalog.get_root import (
    STRATEGY_CATALOG_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.users.delete_by_user_id import (
    USERS_DELETE_BY_USER_ID,
)
from gimbal_plate.systems.platform.endpoint.users.get_root import (
    USERS_GET_ROOT,
)
from gimbal_plate.systems.platform.endpoint.users.get_roster import (
    USERS_GET_ROSTER,
)
from gimbal_plate.systems.platform.endpoint.users.patch_by_user_id import (
    USERS_PATCH_BY_USER_ID,
)
from gimbal_plate.systems.platform.endpoint.users.post_by_user_id_reset_password import (
    USERS_POST_BY_USER_ID_RESET_PASSWORD,
)
from gimbal_plate.systems.platform.endpoint.users.post_root import (
    USERS_POST_ROOT,
)

ALL_ENDPOINTS: Final[list[EndpointSpec]] = [
    ACTIVITY_GET_ROOT,
    ADAPTATIONS_GET_BATCHES,
    ADAPTATIONS_GET_BATCHES_BY_BATCH_ID,
    ADAPTATIONS_GET_IMPACT,
    ADAPTATIONS_GET_IMPACT_BULK,
    ADAPTATIONS_GET_IMPACT_SUMMARY,
    ADAPTATIONS_GET_REFS_DRIFT,
    ADAPTATIONS_GET_UNINDEXED_STEPS,
    ADAPTATIONS_PATCH_OPS_BY_OP_ID,
    ADAPTATIONS_POST_BATCHES,
    ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_OPS,
    ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_ROLLBACK,
    ADAPTATIONS_POST_CARRY_BATCHES,
    ADAPTATIONS_POST_CATALOG_DIFF,
    ADAPTATIONS_POST_OPS_BY_OP_ID_APPLY,
    ADAPTATIONS_POST_OPS_BY_OP_ID_SKIP,
    ADMIN_GET_AUDIT_LOGS,
    AUTH_GET_ME,
    AUTH_POST_CHANGE_PASSWORD,
    AUTH_POST_LOGIN,
    AUTH_POST_REFRESH,
    AUTH_POST_REGISTER,
    AUTHS_DELETE_BY_AUTH_ID,
    AUTHS_GET_BY_ALIAS_REFERENCES,
    AUTHS_GET_BY_AUTH_ID,
    AUTHS_GET_ROOT,
    AUTHS_PATCH_BY_AUTH_ID,
    AUTHS_POST_BY_AUTH_ID_TEST,
    AUTHS_POST_ROOT,
    BOARD_CARDS_DELETE_BY_CARD_ID,
    BOARD_CARDS_PATCH_BY_CARD_ID,
    BOARD_CARDS_POST_BY_CARD_ID_DEMOTE,
    BOARD_CARDS_POST_BY_CARD_ID_PROMOTE,
    BOARD_CARDS_POST_ROOT,
    CARRY_GET_BINDINGS,
    CARRY_GET_BINDINGS_BY_SERVICE,
    CARRY_GET_BINDINGS_BY_SERVICE_FIELDS,
    CARRY_GET_DEFAULTS,
    CARRY_GET_DRIFT,
    CARRY_PUT_BINDINGS_BY_SERVICE,
    CARRY_PUT_DEFAULTS,
    CATALOG_GET_SERVICES,
    CONSTANTS_DELETE_BY_ENTRY_ID,
    CONSTANTS_GET_BY_ENTRY_ID,
    CONSTANTS_GET_ROOT,
    CONSTANTS_PATCH_BY_ENTRY_ID,
    CONSTANTS_POST_ROOT,
    DATA_SETS_DELETE_BY_DATASET_ID,
    DATA_SETS_GET_BY_DATASET_ID,
    DATA_SETS_GET_ROOT,
    DATA_SETS_PUT_BY_DATASET_ID,
    ENDPOINT_CATALOG_GET_BY_ENDPOINT_ID_FULL,
    ENDPOINT_CATALOG_POST_BY_ENDPOINT_ID_FIELD_STATE_60B108,
    ENDPOINT_CATALOG_POST_RESOLVE_PATHS,
    ENDPOINTS_GET_BY_ENDPOINT_ID_BOARD,
    EXECUTIONS_DELETE_BY_EXECUTION_ID,
    EXECUTIONS_GET_BY_EXECUTION_ID,
    EXECUTIONS_GET_BY_EXECUTION_ID_CASE_ARTIFACT,
    EXECUTIONS_GET_BY_EXECUTION_ID_DEBUG,
    EXECUTIONS_GET_BY_EXECUTION_ID_DEBUG_OUTPUT,
    EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS,
    EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_COUNTS,
    EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_STREAM,
    EXECUTIONS_GET_BY_EXECUTION_ID_ROWS,
    EXECUTIONS_GET_BY_EXECUTION_ID_SCENARIO_SNAPSHOT,
    EXECUTIONS_GET_ROOT,
    EXECUTIONS_GET_SUMMARY,
    EXECUTIONS_POST_BY_EXECUTION_ID_CANCEL,
    EXECUTIONS_POST_BY_EXECUTION_ID_DEBUG_COMMAND,
    EXECUTIONS_POST_BY_EXECUTION_ID_RERUN,
    GENERATOR_CATALOG_GET_BY_KIND_FULL,
    GENERATOR_CATALOG_GET_ROOT,
    HANDOFF_POST_ROOT,
    HEALTH_GET_ROOT,
    ME_GET_PREFERENCES,
    ME_PUT_PREFERENCES_BY_KEY,
    NOTIFICATIONS_GET_HANDOFF_UNREAD,
    NOTIFICATIONS_GET_PREFERENCES,
    NOTIFICATIONS_GET_ROOT,
    NOTIFICATIONS_GET_UNREAD_COUNT,
    NOTIFICATIONS_POST_ANNOUNCEMENTS,
    NOTIFICATIONS_POST_READ,
    NOTIFICATIONS_PUT_PREFERENCES,
    QUERY_VIEWS_GET_BY_NAME_ROWS,
    QUERY_VIEWS_GET_ROOT,
    REPORT_DEFINITIONS_DELETE_BY_DEFINITION_ID,
    REPORT_DEFINITIONS_GET_BY_DEFINITION_ID,
    REPORT_DEFINITIONS_GET_ROOT,
    REPORT_DEFINITIONS_POST_ROOT,
    REPORT_DEFINITIONS_PUT_BY_DEFINITION_ID,
    RUN_POST_PRECHECK,
    RUNS_POST_ROOT,
    SCENARIO_FILTER_GROUPS_DELETE_BY_BUCKET_BY_GROUP_ID,
    SCENARIO_FILTER_GROUPS_GET_ROOT,
    SCENARIO_FILTER_GROUPS_POST_ROOT,
    SCENARIOS_DELETE_BY_SCENARIO_ID,
    SCENARIOS_DELETE_BY_SCENARIO_ID_RUN_SCHEMES_BY_S_6A5300,
    SCENARIOS_GET_BY_SCENARIO_ID,
    SCENARIOS_GET_BY_SCENARIO_ID_DRAFT,
    SCENARIOS_GET_BY_SCENARIO_ID_RUN_SCHEMES,
    SCENARIOS_GET_FACETS,
    SCENARIOS_GET_ROOT,
    SCENARIOS_GET_SIGNALS,
    SCENARIOS_POST_BY_SCENARIO_ID_COPY,
    SCENARIOS_POST_BY_SCENARIO_ID_DATA_SETS,
    SCENARIOS_POST_BY_SCENARIO_ID_PUBLISH,
    SCENARIOS_POST_BY_SCENARIO_ID_RUN_SCHEMES,
    SCENARIOS_POST_BY_SCENARIO_ID_STAR,
    SCENARIOS_POST_BY_SCENARIO_ID_UNPUBLISH,
    SCENARIOS_POST_PREVIEW_PLATE,
    SCENARIOS_POST_ROOT,
    SCENARIOS_PUT_BY_SCENARIO_ID,
    SCENARIOS_PUT_BY_SCENARIO_ID_RUN_SCHEMES_BY_SCHEME_ID,
    SERVICE_ALIASES_DELETE_BY_ALIAS_NAME,
    SERVICE_ALIASES_GET_ROOT,
    SERVICE_ALIASES_PATCH_BY_ALIAS_NAME,
    SERVICE_ALIASES_POST_ROOT,
    SERVICES_GET_BY_SERVICE_GRID,
    STRATEGY_CATALOG_GET_BY_KIND_FULL,
    STRATEGY_CATALOG_GET_ROOT,
    USERS_DELETE_BY_USER_ID,
    USERS_GET_ROOT,
    USERS_GET_ROSTER,
    USERS_PATCH_BY_USER_ID,
    USERS_POST_BY_USER_ID_RESET_PASSWORD,
    USERS_POST_ROOT,
]

__all__ = [
    "ACTIVITY_GET_ROOT",
    "ADAPTATIONS_GET_BATCHES",
    "ADAPTATIONS_GET_BATCHES_BY_BATCH_ID",
    "ADAPTATIONS_GET_IMPACT",
    "ADAPTATIONS_GET_IMPACT_BULK",
    "ADAPTATIONS_GET_IMPACT_SUMMARY",
    "ADAPTATIONS_GET_REFS_DRIFT",
    "ADAPTATIONS_GET_UNINDEXED_STEPS",
    "ADAPTATIONS_PATCH_OPS_BY_OP_ID",
    "ADAPTATIONS_POST_BATCHES",
    "ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_OPS",
    "ADAPTATIONS_POST_BATCHES_BY_BATCH_ID_ROLLBACK",
    "ADAPTATIONS_POST_CARRY_BATCHES",
    "ADAPTATIONS_POST_CATALOG_DIFF",
    "ADAPTATIONS_POST_OPS_BY_OP_ID_APPLY",
    "ADAPTATIONS_POST_OPS_BY_OP_ID_SKIP",
    "ADMIN_GET_AUDIT_LOGS",
    "AUTH_GET_ME",
    "AUTH_POST_CHANGE_PASSWORD",
    "AUTH_POST_LOGIN",
    "AUTH_POST_REFRESH",
    "AUTH_POST_REGISTER",
    "AUTHS_DELETE_BY_AUTH_ID",
    "AUTHS_GET_BY_ALIAS_REFERENCES",
    "AUTHS_GET_BY_AUTH_ID",
    "AUTHS_GET_ROOT",
    "AUTHS_PATCH_BY_AUTH_ID",
    "AUTHS_POST_BY_AUTH_ID_TEST",
    "AUTHS_POST_ROOT",
    "BOARD_CARDS_DELETE_BY_CARD_ID",
    "BOARD_CARDS_PATCH_BY_CARD_ID",
    "BOARD_CARDS_POST_BY_CARD_ID_DEMOTE",
    "BOARD_CARDS_POST_BY_CARD_ID_PROMOTE",
    "BOARD_CARDS_POST_ROOT",
    "CARRY_GET_BINDINGS",
    "CARRY_GET_BINDINGS_BY_SERVICE",
    "CARRY_GET_BINDINGS_BY_SERVICE_FIELDS",
    "CARRY_GET_DEFAULTS",
    "CARRY_GET_DRIFT",
    "CARRY_PUT_BINDINGS_BY_SERVICE",
    "CARRY_PUT_DEFAULTS",
    "CATALOG_GET_SERVICES",
    "CONSTANTS_DELETE_BY_ENTRY_ID",
    "CONSTANTS_GET_BY_ENTRY_ID",
    "CONSTANTS_GET_ROOT",
    "CONSTANTS_PATCH_BY_ENTRY_ID",
    "CONSTANTS_POST_ROOT",
    "DATA_SETS_DELETE_BY_DATASET_ID",
    "DATA_SETS_GET_BY_DATASET_ID",
    "DATA_SETS_GET_ROOT",
    "DATA_SETS_PUT_BY_DATASET_ID",
    "ENDPOINT_CATALOG_GET_BY_ENDPOINT_ID_FULL",
    "ENDPOINT_CATALOG_POST_BY_ENDPOINT_ID_FIELD_STATE_60B108",
    "ENDPOINT_CATALOG_POST_RESOLVE_PATHS",
    "ENDPOINTS_GET_BY_ENDPOINT_ID_BOARD",
    "EXECUTIONS_DELETE_BY_EXECUTION_ID",
    "EXECUTIONS_GET_BY_EXECUTION_ID",
    "EXECUTIONS_GET_BY_EXECUTION_ID_CASE_ARTIFACT",
    "EXECUTIONS_GET_BY_EXECUTION_ID_DEBUG",
    "EXECUTIONS_GET_BY_EXECUTION_ID_DEBUG_OUTPUT",
    "EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS",
    "EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_COUNTS",
    "EXECUTIONS_GET_BY_EXECUTION_ID_EVENTS_STREAM",
    "EXECUTIONS_GET_BY_EXECUTION_ID_ROWS",
    "EXECUTIONS_GET_BY_EXECUTION_ID_SCENARIO_SNAPSHOT",
    "EXECUTIONS_GET_ROOT",
    "EXECUTIONS_GET_SUMMARY",
    "EXECUTIONS_POST_BY_EXECUTION_ID_CANCEL",
    "EXECUTIONS_POST_BY_EXECUTION_ID_DEBUG_COMMAND",
    "EXECUTIONS_POST_BY_EXECUTION_ID_RERUN",
    "GENERATOR_CATALOG_GET_BY_KIND_FULL",
    "GENERATOR_CATALOG_GET_ROOT",
    "HANDOFF_POST_ROOT",
    "HEALTH_GET_ROOT",
    "ME_GET_PREFERENCES",
    "ME_PUT_PREFERENCES_BY_KEY",
    "NOTIFICATIONS_GET_HANDOFF_UNREAD",
    "NOTIFICATIONS_GET_PREFERENCES",
    "NOTIFICATIONS_GET_ROOT",
    "NOTIFICATIONS_GET_UNREAD_COUNT",
    "NOTIFICATIONS_POST_ANNOUNCEMENTS",
    "NOTIFICATIONS_POST_READ",
    "NOTIFICATIONS_PUT_PREFERENCES",
    "QUERY_VIEWS_GET_BY_NAME_ROWS",
    "QUERY_VIEWS_GET_ROOT",
    "REPORT_DEFINITIONS_DELETE_BY_DEFINITION_ID",
    "REPORT_DEFINITIONS_GET_BY_DEFINITION_ID",
    "REPORT_DEFINITIONS_GET_ROOT",
    "REPORT_DEFINITIONS_POST_ROOT",
    "REPORT_DEFINITIONS_PUT_BY_DEFINITION_ID",
    "RUN_POST_PRECHECK",
    "RUNS_POST_ROOT",
    "SCENARIO_FILTER_GROUPS_DELETE_BY_BUCKET_BY_GROUP_ID",
    "SCENARIO_FILTER_GROUPS_GET_ROOT",
    "SCENARIO_FILTER_GROUPS_POST_ROOT",
    "SCENARIOS_DELETE_BY_SCENARIO_ID",
    "SCENARIOS_DELETE_BY_SCENARIO_ID_RUN_SCHEMES_BY_S_6A5300",
    "SCENARIOS_GET_BY_SCENARIO_ID",
    "SCENARIOS_GET_BY_SCENARIO_ID_DRAFT",
    "SCENARIOS_GET_BY_SCENARIO_ID_RUN_SCHEMES",
    "SCENARIOS_GET_FACETS",
    "SCENARIOS_GET_ROOT",
    "SCENARIOS_GET_SIGNALS",
    "SCENARIOS_POST_BY_SCENARIO_ID_COPY",
    "SCENARIOS_POST_BY_SCENARIO_ID_DATA_SETS",
    "SCENARIOS_POST_BY_SCENARIO_ID_PUBLISH",
    "SCENARIOS_POST_BY_SCENARIO_ID_RUN_SCHEMES",
    "SCENARIOS_POST_BY_SCENARIO_ID_STAR",
    "SCENARIOS_POST_BY_SCENARIO_ID_UNPUBLISH",
    "SCENARIOS_POST_PREVIEW_PLATE",
    "SCENARIOS_POST_ROOT",
    "SCENARIOS_PUT_BY_SCENARIO_ID",
    "SCENARIOS_PUT_BY_SCENARIO_ID_RUN_SCHEMES_BY_SCHEME_ID",
    "SERVICE_ALIASES_DELETE_BY_ALIAS_NAME",
    "SERVICE_ALIASES_GET_ROOT",
    "SERVICE_ALIASES_PATCH_BY_ALIAS_NAME",
    "SERVICE_ALIASES_POST_ROOT",
    "SERVICES_GET_BY_SERVICE_GRID",
    "STRATEGY_CATALOG_GET_BY_KIND_FULL",
    "STRATEGY_CATALOG_GET_ROOT",
    "USERS_DELETE_BY_USER_ID",
    "USERS_GET_ROOT",
    "USERS_GET_ROSTER",
    "USERS_PATCH_BY_USER_ID",
    "USERS_POST_BY_USER_ID_RESET_PASSWORD",
    "USERS_POST_ROOT",
    "ALL_ENDPOINTS",
]
