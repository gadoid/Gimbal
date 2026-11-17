"""carry env 覆盖层执行链接线(registry §1.7 稀疏覆盖)。

C3b 落地了写面(编辑器 env 覆盖开关 + bindings API envId)与读面
(get_bindings 基线先、env 命中行后覆盖),但三处执行链消费点
(prepare_exec / resolve_effective_config / unit_carry_contexts)
曾全部未传 env_id —— 覆盖行只在管理面存在,注入与预览恒吃基线。
本文件把三条消费链逐一钉住:同一份布景下,带 env 位 → 覆盖值生效;
不带 env 位 → 基线值(旧调用方语义不变)。
"""
from __future__ import annotations

from app.core import db as db_module
from app.models import Environment, Service
from app.services import carry_store, run_prepare
from app.services.carry_injection import build_carry_context
from app.services.env_chain import EnvChoice

_STEP = {"kind": "step",
         "call": {"service": "fin-service", "path": "/x",
                  "request": {"kind": "request", "body": {}}}}
# 无 endpoint_id → carry 面不走 plate(锚点驱动的批量声明拉取),纯值表链


async def _seed_overlay() -> tuple[int, int]:
    """主档 fin-service + 两环境 + 基线/预发覆盖两行绑定。"""
    async with db_module.SessionLocal() as db:
        db.add(Service(name="fin-service", system="fin"))
        base_env = Environment(name="测试", is_default=True)
        uat_env = Environment(name="预发", is_default=False)
        db.add_all([base_env, uat_env])
        await db.flush()
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "基线值"},
            updated_by_id=None, updated_by_name="alice")
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "预发覆盖"},
            updated_by_id=None, updated_by_name="alice", env_id=uat_env.id)
        await db.commit()
        return base_env.id, uat_env.id


async def test_build_context_env_overlay_wins(fresh_db):
    """机制面:build_carry_context 带环境位 → 覆盖值;基线环境/无环境 → 基线。"""
    base_env_id, uat_env_id = await _seed_overlay()
    async with db_module.SessionLocal() as db:
        got_base = await build_carry_context(
            db, {"steps": [_STEP]}, env_id=None)
        got_test = await build_carry_context(
            db, {"steps": [_STEP]}, env_id=base_env_id)
        got_uat = await build_carry_context(
            db, {"steps": [_STEP]}, env_id=uat_env_id)
    assert got_base.service_bindings["fin-service"]["$.remark"] == "基线值"
    assert got_test.service_bindings["fin-service"]["$.remark"] == "基线值"
    assert got_uat.service_bindings["fin-service"]["$.remark"] == "预发覆盖"


async def test_prepare_exec_threads_env_to_carry(fresh_db):
    """执行链:派发环境位(environment 形参)随 carry 下传 —— 单场景
    prepare_exec 与凭证/地址用同一次 EnvChoice,覆盖层即生效。"""
    _, uat_env_id = await _seed_overlay()
    payload = {"definition": {"steps": [_STEP]}}
    prep_uat = await run_prepare.prepare_exec(
        db_module.SessionLocal, payload,
        resolve_mode="none", with_auth=False,
        environment=EnvChoice(uat_env_id, "explicit"))
    prep_no_env = await run_prepare.prepare_exec(
        db_module.SessionLocal, payload,
        resolve_mode="none", with_auth=False,
        environment=EnvChoice())
    assert (prep_uat.carry_ctx.service_bindings["fin-service"]["$.remark"]
            == "预发覆盖")
    assert (prep_no_env.carry_ctx.service_bindings["fin-service"]["$.remark"]
            == "基线值")


async def test_effective_preview_threads_env_to_carry(fresh_db):
    """预览面:resolve_effective_config 与执行同一位(§「预览与执行
    结构上不可能漂移」)—— 覆盖值带来源上屏,而不是恒显基线。"""
    _, uat_env_id = await _seed_overlay()
    async with db_module.SessionLocal() as db:
        cfg = await run_prepare.resolve_effective_config(
            db, {"steps": [_STEP]},
            environment=EnvChoice(uat_env_id, "explicit"))
        cfg_base = await run_prepare.resolve_effective_config(
            db, {"steps": [_STEP]}, environment=EnvChoice())
    row = cfg.carry["fin-service"]["$.remark"]
    assert row["value"] == "预发覆盖"
    assert row["source"].endswith(":base")   # 服务键档,非条目键
    assert cfg_base.carry["fin-service"]["$.remark"]["value"] == "基线值"


async def test_unit_carry_contexts_forwards_env_meta(fresh_db, monkeypatch):
    """编排链:graph_dispatch 逐单元环境位经 unit_metas['env_id'] 下传。"""
    captured: list = []

    async def _capture(db, definition, **kwargs):
        captured.append(kwargs.get("env_id"))
        return None

    monkeypatch.setattr(
        "app.services.carry_injection.build_carry_context", _capture)
    out = await run_prepare.unit_carry_contexts(
        db_module.SessionLocal, [{"steps": []}, {"steps": []}],
        [{"project_id": None, "user_id": None, "env_id": 9, "bindings": None},
         {"project_id": None, "user_id": None}])
    assert captured == [9, None]
    assert out == [None, None]
