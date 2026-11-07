"""S1-e 转移维护者(M2a S1.6)—— 公共项目四类对象共用单点。

规则(s1-detail §〇):维护者本人 ∨ Admin+ 发起;受让人在职、非系统
用户,无需确认;落库只改 ``owner_id``(公共项目里它的语义 = 维护者),
原创建人留在审计与动态流;新旧维护者都收通知。

集成模板连带(与删用户「转让」处置同口径,实现自 users.py 处置段
抽出共用):解绑注册令牌(``token_id = NULL``,回调停发)+ 删除原
维护者的自有实例;订阅实例不动(指纹不含属主,不触发重新确认)。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from . import activity as activity_svc
from .notifications import create_notification

# 对象类型 → (资源类型, 动态流 kind);integration_template 的
# 时间线沿用 integration 域
_KIND = {
    "scenario": ("scenario", "scenario.maintainer_transferred"),
    "suite": ("suite", "suite.maintainer_transferred"),
    "report_definition": ("report_definition",
                          "report_definition.maintainer_transferred"),
    "integration_template": ("integration",
                             "integration.maintainer_transferred"),
}


async def transfer_maintenance(
    db: AsyncSession, *, obj: Any, obj_type: str, to_user: Any,
    actor: Any, obj_name: str = "",
) -> None:
    """转移公共项目对象的维护者(调用方负责闸与公共项目校验)。

    ``obj`` 需带 ``owner_id``(integration 模板另带 ``id``);落库后
    记动态流(``*.maintainer_transferred``,detail from/to)并通知新
    旧维护者(通知失败不阻断,best-effort)。
    """
    old_owner_id = obj.owner_id
    resource_type, kind = _KIND[obj_type]
    resource_id = str(getattr(obj, "scenario_id", None)
                      or getattr(obj, "id"))
    obj.owner_id = to_user.id

    if obj_type == "integration_template":
        # 令牌解绑(回调停发)+ 原维护者自有实例删除;订阅实例不动
        from ..models.integration_task import IntegrationTask

        obj.token_id = None
        await db.execute(sa_delete(IntegrationTask).where(
            IntegrationTask.template_id == obj.id,
            IntegrationTask.holder_id == old_owner_id))

    await db.commit()

    await activity_svc.record(
        db, actor_id=actor.id,
        kind=kind, resource_type=resource_type, resource_id=resource_id,
        detail={"name": obj_name or resource_id,
                "fromUserId": old_owner_id, "toUserId": to_user.id,
                "by": actor.display_name or actor.username})

    # 新旧维护者都收通知(best-effort)
    for uid, role in ((old_owner_id, "old"), (to_user.id, "new")):
        if uid is None:
            continue
        try:
            await create_notification(
                db, user_id=uid, type_="maintenance_transferred",
                title=f"维护者已转移:{obj_name or resource_id}",
                body=(f"「{obj_name or resource_id}」的维护者由 "
                      f"{actor.display_name or actor.username} 转给 "
                      f"{to_user.display_name or to_user.username}"
                      + ("(你不再是维护者)" if role == "old"
                         else "(你成为维护者)")),
                link=(f"/scenarios/{resource_id}/detail"
                      if resource_type == "scenario" else None))
        except Exception:  # noqa: BLE001 — 通知是增强
            await db.rollback()
