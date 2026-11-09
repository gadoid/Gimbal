"""authz M2a S7.6:公共层 carry 改动 → 项目层遮蔽通知。

语义:tier 序 公共项目层 < 项目层 —— 项目层同键覆盖值**遮住**公共层
改动(该改动对项目区执行不生效);公共层改名 / 删键也会让项目层绑定
悬空。因此:**公共层写面**(``PUT /carry/*?scope=global`` 与公共层
carry 批的 op 应用 / 回滚)落库后,凡有项目层绑定行命中本次**变更键**
(新旧值不同的键,含增删改名)的项目,向其项目管理员发一条
``carry.shadowed`` 通知。个人层覆盖不通知(本人偏好,计划只钉项目面)。

调用方约定:先 commit 值变更,再调本服务(通知失败不回滚值变更 ——
通知是增强,不是写面前置);本服务内部自行 commit。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.carry_binding import CarryGlobalDefault, CarryServiceBinding
from ..models.project import Project, ProjectMember
from . import notifications as notify_svc

TYPE = "carry.shadowed"


def changed_keys(old: dict, new: dict) -> list[str]:
    """新旧值表的结构 diff 键集(值不同 / 新增 / 删除;rename = 两个键)。"""
    keys = set(old) | set(new)
    return sorted(k for k in keys if old.get(k) != new.get(k))


async def notify_public_carry_change(
    db: AsyncSession, *, scope: "tuple[str, int] | None",
    service: str | None, old: dict, new: dict, actor_name: str,
) -> int:
    """公共层 carry 写后通知受影响项目的管理员;非公共层直通返回 0。

    service=None → 全局默认表(carry_global_defaults);否则按服务绑定
    表(carry_service_bindings)。返回发出的通知条数(增强面,失败不抛)。
    """
    from . import carry_store

    if scope is not None and tuple(scope) != await carry_store.public_scope(db):
        return 0
    keys = changed_keys(old, new)
    if not keys:
        return 0
    pub = await carry_store.public_scope(db)

    # 项目层命中行(排除公共项目自己):scope='project' ∧ scope_id ≠ 公共;
    # 逐行取 path → 通知只报该项目实际覆盖的键
    if service is None:
        stmt = select(CarryGlobalDefault.scope_id,
                      CarryGlobalDefault.field_path).where(
            CarryGlobalDefault.scope == "project",
            CarryGlobalDefault.scope_id != pub[1],
            CarryGlobalDefault.field_path.in_(keys))
    else:
        stmt = select(CarryServiceBinding.scope_id,
                      CarryServiceBinding.field_path).where(
            CarryServiceBinding.scope == "project",
            CarryServiceBinding.scope_id != pub[1],
            CarryServiceBinding.service_name == service,
            CarryServiceBinding.field_path.in_(keys))
    hit: dict[int, set[str]] = {}
    for pid, path in (await db.execute(stmt)).all():
        if pid and pid != pub[1]:
            hit.setdefault(pid, set()).add(path)
    if not hit:
        return 0

    names = {p.id: p.name for p in (await db.execute(
        select(Project).where(Project.id.in_(hit)))).scalars()}
    what = f"服务 {service} 绑定" if service else "全局默认"
    sent = 0
    for pid, hit_keys in sorted(hit.items()):
        admin_ids = list((await db.execute(select(ProjectMember.user_id).where(
            ProjectMember.project_id == pid,
            ProjectMember.role == ProjectMember.ROLE_ADMIN))).scalars())
        if not admin_ids:
            continue
        keys_sorted = sorted(hit_keys)
        body = (f"公共层 {what}的键 {', '.join(keys_sorted[:8])}"
                f"{'…' if len(keys_sorted) > 8 else ''} 已由 {actor_name} 变更;"
                f"本项目对这些键的覆盖值仍在生效(遮住该改动),请到项目配置"
                f"检查是否仍需覆盖。")
        for uid in admin_ids:
            await notify_svc.create_notification(
                db, user_id=uid, type_=TYPE,
                title=f"公共层 carry 变更(项目 {names.get(pid, pid)} 被覆盖)",
                body=body,
                link=f"/projects/{pid}?tab=config",
                payload={"projectId": pid, "service": service,
                         "keys": keys_sorted},
                commit=False)
            sent += 1
    await db.commit()
    return sent
