"""grep 守卫(authz M2a S1.2):routers/services 的属主等值比较形状冻结。

与角色字面量守卫(test_grep_guard_role_literals)同构的双断言:白名单
之外新增(或计数上涨)即红;白名单条目失效/计数下降也红(收编后忘删)。
条目锚定「路径:行内容:出现次数」—— 不含行号,无关编辑不挪条目。

形状三种:``.owner_id`` / ``.holder_id`` 等值比较、``ensure_owner(``
调用。S1.2 已收编场景 / suite / 数据集 / 运行方案 / 报告定义的写闸与
列表读面到 ``can()`` / ``zone_read_clause``;冻结的存量按类:

* 个人数据(终态):凭证会话 / 常量池 / 执行台账 / 集成实例(holder)
  / 环境注册表行 —— 本来只属于个人的对象,等值比较即终态;
* 工具与镜头(终态):重名消解、cross_owner 脱敏判定、scope=mine
  浏览镜头、展示徽标(own/mine/canManage)、本人 KPI 过滤;
* 通知 / 审计分支(终态):越属主下架才通知/入审计的分支,非权限闸;
* 删用户处置(cat3,终态):users.py 处置段;
* 待收编(非终态,随切片删行):integration 模板闸(S1.7)、shares
  引用面(S7 退役)、suites 同属主成员约束(S1.5 换同区触发器)。

豁免:``_ownership.py``(表 B / 谓词求值单点)、``zone.py``
(zone_read_clause / apply_* 三区谓词单点)。全部待收编行删空即终点。
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"

SHAPES = (
    re.compile(r"\.owner_id\s*[=!]="),
    re.compile(r"\bensure_owner\("),
    re.compile(r"\.holder_id\s*[=!]="),
)

# 存量冻结(2026-11-08,S1.2 收编后 88 条;分类见模块注释)
_ALLOWLIST: dict[str, int] = {
    "routers/access_tokens.py:.where(AuthSession.owner_id == owner_id,": 1,
    "routers/access_tokens.py:AuthSession.owner_id == holder)": 1,
    "routers/access_tokens.py:AuthSession.owner_id == tok.user_id,": 1,
    "routers/activity.py:.where(Execution.owner_id == user.id)": 1,
    "routers/auth_sessions.py:.where(AuthSession.owner_id == user.id)": 1,
    # S3.1 写面槽位过滤(owner 池内查重/同槽清默认,四元组键的 owner 面)
    "routers/auth_sessions.py:AuthSession.owner_id == user.id,": 4,
    "routers/auth_sessions.py:base = select(AuthSession).where(AuthSession.owner_id == user.id)": 1,
    "routers/auth_sessions.py:if a is None or a.owner_id != owner_id:": 1,
    "routers/constants.py:base = select(ConstantEntry).where(ConstantEntry.owner_id == user.id)": 1,
    "routers/constants.py:if entry is None or entry.owner_id != owner_id:": 1,
    "routers/environments.py:if env.owner_id != user.id and not has_capability(user, \"users.manage\"):": 1,
    "routers/executions.py:Execution.owner_id == user.id,": 2,
    "routers/executions.py:base = select(Execution).where(Execution.owner_id == user.id)": 1,
    "routers/integration.py:\"canManage\": db_tpl.owner_id == current.id,": 1,
    "routers/integration.py:\"mine\": db_tpl.owner_id == current.id,": 1,
    "routers/integration.py:AuthSession.owner_id == holder_id,": 1,
    "routers/integration.py:IntegrationTask.holder_id == holder))).scalar()": 1,
    "routers/integration.py:IntegrationTask.holder_id == user.id))).scalar()": 4,
    "routers/integration.py:if has_capability(current, \"ops.write\") or db_tpl.owner_id == current.id:": 1,
    "routers/integration.py:if tpl.owner_id != user.id:": 1,
    "routers/integration.py:subscribed = (inst is not None and inst.holder_id == user.id)": 1,
    "routers/me.py:AuthSession).where(AuthSession.owner_id == user.id))).scalar_one())": 1,
    "routers/me.py:ComposerScenario.owner_id == user.id,": 1,
    "routers/me.py:Execution.owner_id == user.id,": 2,
    "routers/me.py:IntegrationTask.holder_id == user.id))": 1,
    "routers/me.py:IntegrationTask.holder_id == user.id))).scalar_one())": 1,
    "routers/query_views.py:AuthSessionRow.owner_id == owner_id,": 1,
    "routers/scenarios.py:.where(Execution.owner_id == user.id,": 1,
    "routers/scenarios.py:if row.owner_id is not None and row.owner_id != user.id:": 1,
    "routers/scenarios.py:if su.owner_id is not None and su.owner_id != user.id:": 1,
    "routers/scenarios.py:own = row.owner_id == user.id": 1,
    "routers/scenarios.py:readable = [r for r in readable if r.owner_id == user.id]": 1,
    "routers/suites.py:Execution.owner_id == runner_id,": 1,
    "routers/suites.py:Execution.owner_id == user.id,": 2,
    "routers/suites.py:clauses = [Suite.owner_id == user.id, Suite.project_id.is_(None)]": 1,
    "routers/suites.py:clauses = [Suite.owner_id == user.id]   # 镜头(含我维护的公共副本)": 1,
    "routers/suites.py:if copy.owner_id != user.id:": 1,
    "routers/suites.py:if ex.owner_id != user.id:": 1,
    "routers/suites.py:select(Suite.mode_config).where(Suite.owner_id == user.id)": 1,
    "routers/suites.py:select(Suite.name).where(Suite.owner_id == suite.owner_id)))": 1,
    "routers/suites.py:select(Suite.name).where(Suite.owner_id == user.id)))}": 1,
    "routers/suites.py:select(func.count()).where(Suite.owner_id == suite.owner_id,": 1,
    "routers/users.py:.where(ComposerScenario.owner_id == user_id)": 3,
    "routers/users.py:.where(ComposerScenario.owner_id == user_id,": 1,
    "routers/users.py:IntegrationTask.holder_id != user_id))).scalars().all()": 1,
    "routers/users.py:IntegrationTask.holder_id == user_id))": 2,
    "routers/users.py:IntegrationTask.owner_id == user_id))).scalars().all()": 1,
    "routers/users.py:IntegrationTask.owner_id == user_id,": 3,
    "routers/users.py:ReportDefinitionRow.owner_id == user_id)": 2,
    "routers/users.py:ReportDefinitionRow.owner_id == user_id,": 1,
    "routers/users.py:Suite.owner_id == user_id,": 1,
    "routers/users.py:sa_delete(AuthSession).where(AuthSession.owner_id == user_id))": 1,
    "routers/users.py:sa_delete(ConstantEntry).where(ConstantEntry.owner_id == user_id))": 1,
    "routers/users.py:sa_delete(Suite).where(Suite.owner_id == user_id))": 2,
    "routers/users.py:sa_update(Execution).where(Execution.owner_id == user_id)": 1,
    "routers/users.py:sa_update(Suite).where(Suite.owner_id == user_id)": 1,
    "routers/users.py:select(Execution).where(Execution.owner_id == user_id)": 1,
    "routers/users.py:select(Suite.id).where(Suite.owner_id == user_id))).scalars())": 1,
    # S7.4:转换服务的 fork 幂等兜底查询(grantee 名下已有该源副本)
    "services/share_ref_retire.py:ComposerScenario.owner_id == owner_id,": 1,
    "services/share_ref_retire.py:Suite.owner_id == owner_id,": 1,
    "services/access_token.py:AuthSession.owner_id == owner_id,": 1,
    "services/access_token.py:IntegrationTask.holder_id == tpl.owner_id))).scalar()": 1,
    "services/adaptation_service.py:(refs_own if su.owner_id == owner_id": 1,
    "services/adaptation_service.py:ComposerScenario.owner_id == owner_id": 1,
    "services/adaptation_service.py:stmt = stmt.where(ComposerScenario.owner_id == user_id)": 1,
    "services/auth_references.py:if r.owner_id == user.id and (r.kinds & COUNTED_KINDS)": 1,
    "services/execution_store.py:.where(Execution.owner_id == owner_id)": 1,
    "services/integration_runner.py:IntegrationTask.holder_id != tpl.owner_id,": 2,
    "services/integration_runner.py:IntegrationTask.holder_id == holder,": 2,
    "services/integration_runner.py:and inst.holder_id != tpl.owner_id)": 1,
    # S8:复活钩子增项目来源分支,同一比较换行形态(语义不变)
    "services/integration_runner.py:and (inst.holder_id != user_id": 1,
    "services/integration_runner.py:if _token is not None and inst.holder_id == tpl.owner_id:": 1,
    "services/integration_runner.py:if row_dict and inst.holder_id != scen.owner_id:": 1,
    "services/maintenance_transfer.py:IntegrationTask.holder_id == old_owner_id))": 1,
    # S8:取用池谓词抽 _pool_clause(个人池分支;项目池走 project_id)
    "services/run_prepare.py:return DBAuthSession.owner_id == owner_id": 1,
    # 导入人本人凭证池(池命中/槽位绑定状态 —— 凭证跟人走,属主即本人
    # 的数据归属过滤,不是权限门);S7.5 起按 slot
    "services/scenario_import.py:select(AuthSession.slot).where(AuthSession.owner_id == owner_id)": 1,
    "services/scenario_import.py:AuthSession.owner_id == owner_id,": 1,
    "services/scenario_import.py:AuthSession.owner_id == user_id,": 1,
    "services/scenario_query.py:return ComposerScenario.owner_id == user.id": 1,
    # S7.0:scope=private = 我名下且未进项目(「我的」页口径;镜头谓词
    # 属查询投影不是权限门 —— 权限边界仍走 zone_read_clause)
    "services/scenario_query.py:return (ComposerScenario.owner_id == user.id) & \\": 1,
    "routers/scenarios.py:if r.owner_id == user.id and r.project_id is None]": 1,
    # S7.0:_visible 三区收口改写(私有模板 = 属主)
    "routers/integration.py:return tpl.owner_id == user.id": 1,
    # S7.2:提升门 = 申请人本人的私有原件(与发布闸同款属主单判)
    "services/project_promotion.py:if row.owner_id != applicant_id:": 2,
    "services/project_promotion.py:elif scen.owner_id == src.owner_id:": 1,
    "services/project_promotion.py:select(Suite.name).where(Suite.owner_id == suite.owner_id))).all()}": 1,
    "services/scenario_store.py:ComposerScenario.owner_id == owner_id))": 1,
    "services/scenario_store.py:ComposerScenario.owner_id == user.id": 1,
    "services/scenario_store.py:cross_owner = src.owner_id != new_owner_id": 1,
    "services/suite_copy.py:select(Suite.mode_config).where(Suite.owner_id == target.id)": 1,
    "services/suite_copy.py:select(Suite.name).where(Suite.owner_id == target.id)))}": 1,
    "services/webhook_outbox.py:if inst.holder_id != tpl.owner_id:": 1,
}


def _scan() -> Counter:
    hits: Counter = Counter()
    for sub in ("routers", "services"):
        for py in sorted((_APP / sub).rglob("*.py")):
            if py.name in ("_ownership.py", "zone.py"):
                continue
            for line in py.read_text(encoding="utf-8").splitlines():
                if any(rx.search(line) for rx in SHAPES):
                    hits[
                        f"{py.relative_to(_APP).as_posix()}:{line.strip()}"
                    ] += 1
    return hits


def test_no_new_owner_comparisons():
    """增量禁止:白名单之外的属主等值比较(或计数上涨)即失败。"""
    current = _scan()
    unknown = {k: v for k, v in current.items() if v != _ALLOWLIST.get(k)}
    assert not unknown, (
        "属主等值比较新增/计数变化(应走 can()/zone_read_clause,或归类"
        "进白名单):\n  " + "\n  ".join(f"{k}: {v}" for k, v in sorted(unknown.items())))


def test_allowlist_has_no_stale_entries():
    """白名单不腐化:收编后忘删(或计数下降)的条目同样失败。"""
    current = _scan()
    stale = {k: v for k, v in _ALLOWLIST.items() if current.get(k, 0) != v}
    assert not stale, (
        "白名单条目已不存在或计数下降(收编后请同步删除):\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in sorted(stale.items())))
