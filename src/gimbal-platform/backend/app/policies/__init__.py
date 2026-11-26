"""UPC-04 能力与治理策略注册表(v2.10 §7)—— 本期唯一规范性矩阵。

能力表示容器允许什么(L1/L2 结构与功能之外的 L3 治理开关);权限
表示主体能做什么(§6);资源约束表示当前对象能否做。三者分别求值
(§7),策略集中注册、默认拒绝,不引入动态策略引擎。

* 开 ≠ 主体已授权 —— API 层仍须按 §6 矩阵鉴权;
* 关必须在 API 层拒绝(关闭能力后 API 同样拒绝,AC-07/AC-26);
* ``None`` 表示领域关系不存在(不适用),区别于显式关闭;
* 未来开放能力须修改此矩阵及对应测试 —— 矩阵之外不存在第二套开关。

私有凭证池/令牌关闭是为了避免当前无必要的秘密命名空间扩张;私有
Carry、默认环境与项目 ExecConfig 保留(它们属于容器而非主体,可隔离
同一用户的多个空间,§7 说明)。
"""
from __future__ import annotations

from ..models.project import Project

# kind → 能力开关(True/False/None=不适用);行序与 §7 矩阵一致
CAPABILITY_MATRIX: dict[str, dict[str, bool | None]] = {
    # 场景、套件、报告、模板(public 侧经发布/维护权限,§6)
    "scenario":            {"private": True,  "public": True,  "normal": True},
    "suite":               {"private": True,  "public": True,  "normal": True},
    "report_definition":   {"private": True,  "public": True,  "normal": True},
    "integration_template": {"private": True,  "public": True,  "normal": True},
    # 账户组合(M2 落地资源;public 关闭)
    "account_combo":       {"private": True,  "public": False, "normal": True},
    # 项目 Carry(public = 公共基线继承源,§11.4)
    "project_carry":       {"private": True,  "public": True,  "normal": True},
    "project_default_environment": {"private": True, "public": False, "normal": True},
    "project_exec_config": {"private": True,  "public": False, "normal": True},
    # 秘密命名空间:凭证池与边界 Token 仅 normal(本期;§7 说明)
    "project_credential_pool": {"private": False, "public": False, "normal": True},
    "project_token":       {"private": False, "public": False, "normal": True},
    # 执行/调度:public 关闭(复制后执行,§6 不变量 7)
    "execution":           {"private": True,  "public": False, "normal": True},
    # 成员关系:仅 normal 存在(领域关系,不是开关 —— None = 不适用)
    "member_management":   {"private": None,  "public": None,  "normal": True},
    # 改名/归档/删除(public = 系统治理,禁止普通删除)
    "project_lifecycle":   {"private": True,  "public": None,  "normal": True},
}


def capability_enabled(kind: str, capability: str) -> bool | None:
    """能力开关求值(集中注册、默认拒绝)。

    未登记的能力是编码错误(与 ``_ownership.roles_with`` 同口径,即刻
    KeyError,不静默拒绝)—— 未来开放能力 = 修矩阵 + 补测试。
    """
    row = CAPABILITY_MATRIX.get(capability)
    if row is None:
        raise KeyError(f"unknown capability: {capability!r}(§7 矩阵未登记)")
    if kind not in (Project.KIND_PRIVATE, Project.KIND_PUBLIC,
                    Project.KIND_NORMAL):
        raise KeyError(f"unknown project kind: {kind!r}")
    return row[kind]


def capabilities_of_kind(kind: str) -> dict[str, bool]:
    """ProjectContext.capabilities 的投影口径(§9):不适用(None)序列化
    为 False —— 前端只消费布尔;区别保留在矩阵里。"""
    return {cap: (row[kind] is True)
            for cap, row in CAPABILITY_MATRIX.items()}
