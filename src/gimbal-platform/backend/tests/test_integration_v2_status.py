"""集成线 v2 / I2 验收(方案 §5 I2 行):

- 分类函数表驱动单测(§2.2 全部分支):timeout 与 transport 分立两格、
  error_phase=timeout/cancelled → run=timeout、halted → channel、
  软失败 → pass、launch/exit2 面、auth 优先于 verifying;
- 断言失败(run=ok, check=fail)不累加 fail_streak、不暂停;
- 运行失败保留 outputs 与上次结论;
- 边沿合并(D9):初始 ''/unknown 静默回写零通知;被节流的翻转下次
  执行补发;none↔有结论不发;check_notified_at 为空按已满足间隔
  (静默回写后的首拍翻转即发);
- 双触发过期(D10):临近触发不闪烁、错过两次触发才过期、*/1 与每天
  两种 cron、cron 坏回退 1 小时;
- I3.5:旧 last_status 列/出参已删 —— cards 无 lastStatus 键,手动
  回显 result.status 只答运行面(passed ⟺ run=ok);
- 迁移映射(R-A):auth_failed 暂停实例 → run=auth(执行 LEGACY_MAP_SQL
  原文,不复制口径;测试库 ALTER 补回旧列模拟生产形状)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Notification
from app.models.integration_task import IntegrationTask
from app.services import integration_runner as ir
from tests.helpers import ensure_fk_users, register_and_login

UTC = timezone.utc


# ── §2.2 分类算法(纯函数)────────────────────────────────────────

def _step(**over) -> dict:
    row = {"step_id": "s1", "status": "failed", "error": "",
           "error_phase": None, "error_kind": "", "duration_ms": 1}
    row.update(over)
    return row


def _detail(steps=None, outputs=None, halted=False) -> dict:
    return {"scenario_id": "sc", "status": "failed", "halted": halted,
            "steps": steps if steps is not None else [], "outputs": outputs or {}}


def _classify(steps=None, *, launch="ok", exit_code=0, has_assertions=True,
              halted=False):
    return ir.classify_outcome(
        launch_status=launch, exit_code=exit_code,
        details=[_detail(steps, halted=halted)], has_assertions=has_assertions)


class TestClassifyOutcome:
    def test_launch_faces(self):
        # 墙钟超时是真实的「超时」;launch error → channel
        assert _classify(launch="timeout") == ("timeout", "unknown", "")
        assert _classify(launch="error") == ("channel", "unknown", "")

    def test_exit2_rejected_is_channel(self):
        # M2 校验拒绝 = case 形态问题(平台面),不是被检系统的契约
        assert _classify(exit_code=2) == ("channel", "unknown", "")

    def test_halted_debug_chain_is_channel(self):
        assert _classify(halted=True) == ("channel", "unknown", "")

    def test_auth_beats_verifying(self):
        # 响应 401 的状态断言([auth_status:] 标记)归 auth 面 → 暂停
        assert _classify([_step(
            error="FAIL: 200 eq 401 [auth_status:401]",
            error_phase="verifying", error_kind="auth")]) \
            == ("auth", "unknown", "")

    def test_timeout_and_transport_separate(self):
        """v1.3 分立两格(不可再合并):并入 timeout 会让角标「网络异常」
        永远出不来。"""
        assert _classify([_step(
            error="[calling] Request timeout", error_phase="calling",
            error_kind="timeout")]) == ("timeout", "unknown", "")
        assert _classify([_step(
            error="[calling] connection refused", error_phase="calling",
            error_kind="transport")]) == ("transport", "unknown", "")

    def test_timeout_phase_markers_without_typed_kind(self):
        # Q1:单元超时/协作取消标记不经 calling 类型化(kind=logic)
        assert _classify([_step(
            error="unit timeout", error_phase="timeout",
            error_kind="logic")]) == ("timeout", "unknown", "")
        assert _classify([_step(
            error="cancelled", error_phase="cancelled",
            error_kind="logic")]) == ("timeout", "unknown", "")

    def test_contract_preparing_extracting(self):
        # 依赖 I1 执行器修复;双拼写兼容
        assert _classify([_step(
            error="[preparing] $.cfg.token 提取失败",
            error_phase="preparing")])[0] == "contract"
        assert _classify([_step(
            error="[extracting] $.data.list 提取失败",
            error_phase="extracting")])[0] == "contract"
        assert _classify([_step(
            error="提取失败", error_phase="after_request")])[0] == "contract"

    def test_verifying_fail_is_run_ok_check_fail(self):
        run, check, msg = _classify([_step(
            error="FAIL: expected SUCCESS eq FAILED",
            error_phase="verifying", error_kind="logic")])
        assert (run, check) == ("ok", "fail")
        assert "SUCCESS" in msg

    def test_all_passed_with_or_without_assertions(self):
        ok = [_step(status="passed", error=None, error_kind="none")]
        assert _classify(ok, exit_code=0, has_assertions=True) \
            == ("ok", "pass", "")
        assert _classify(ok, exit_code=0, has_assertions=False) \
            == ("ok", "none", "")

    def test_soft_failure_counts_as_pass(self):
        # D6:引擎 #9 软失败不设 error、不算 failed → 按通过计
        soft = [_step(status="passed", error=None, error_kind="none")]
        assert _classify(soft, exit_code=0, has_assertions=True) \
            == ("ok", "pass", "")

    def test_fallback_logic_is_contract(self):
        # 规则 7:兜底宁报运行异常,不误报检查不通过
        assert _classify([_step(
            error="boom", error_phase=None, error_kind="logic")],
            exit_code=1) == ("contract", "unknown", "")


# ── _finish 状态推进(§2.3)────────────────────────────────────────

async def _seed_pair(*, mode="personal", holder=1, owner=1,
                     cron="*/5 * * * *") -> tuple[int, int]:
    """模板 + 实例行;返回 (tpl_id, inst_id)。"""
    async with db_module.SessionLocal() as s:
        await ensure_fk_users(s, owner, holder)
        s.add(IntegrationTask(
            name="v2用例", owner_id=owner, visibility="public",
            identity_mode=mode, scenario_id="sc-v2", target_system="fin",
            trigger_cron=cron, result_policy="latest"))
        await s.flush()
        tpl_id = (await s.execute(sa.select(IntegrationTask.id).order_by(
            IntegrationTask.id.desc()))).scalars().first()
        s.add(IntegrationTask(
            name="v2用例", owner_id=owner, holder_id=holder,
            template_id=tpl_id, enabled=True, state="idle",
            next_run_at=datetime(2026, 1, 1, tzinfo=UTC)))
        await s.commit()
        inst_id = (await s.execute(sa.select(IntegrationTask.id).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == holder))).scalars().first()
    return tpl_id, inst_id


async def _notify_count() -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(sa.func.count()).select_from(
            Notification).where(Notification.type == "integration"))
        ).scalar() or 0


class TestFinishSemantics:
    async def test_assertion_failure_no_streak_no_pause(self, client):
        await register_and_login(client, "v2_af", "pw123456")
        tpl_id, inst_id = await _seed_pair()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "",
                             check_status="fail", check_message="期望 A 实际 B",
                             outputs={"mr_count": 3})
            assert inst.fail_streak == 0            # D2:check=fail 不累加
            assert inst.state == "idle"             # 不暂停
            assert inst.run_status == "ok"
            assert inst.check_status == "fail"
            assert inst.check_message == "期望 A 实际 B"
            assert inst.check_changed_at is not None
            assert inst.last_outputs == {"mr_count": 3}   # fail 输出是证据
        _ = tpl

    async def test_run_failure_keeps_outputs_and_last_check(self, client):
        await register_and_login(client, "v2_kp", "pw123456")
        tpl_id, inst_id = await _seed_pair()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="pass",
                             outputs={"mr_count": 3})
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "transport", "connection refused",
                             outputs={"mr_count": 99})   # 通道抖动的部分输出
            assert inst.run_status == "transport"
            assert inst.last_outputs == {"mr_count": 3}   # 不被清空/覆盖
            assert inst.check_status == "pass"            # 结论保留
            assert inst.fail_streak == 1                  # run≠ok 累加

    async def test_manual_echo_status_simplified(self, client):
        """I3.5:投影列已删,手动回显 result.status 只答「能不能跑完」
        (passed ⟺ run=ok);检查结论在 instance.checkStatus。"""
        await register_and_login(client, "v2_pm", "pw123456")
        tpl_id, inst_id = await _seed_pair()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            out = await ir._finish(s, inst, tpl, "ok", "", check_status="fail")
            assert out["status"] == "passed"    # run=ok,哪怕 check=fail
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            out = await ir._finish(s, inst, tpl, "timeout", "")
            assert out["status"] == "failed"


class TestEdgeMergeNotifications:
    async def test_initial_silent_backfill_zero_notifications(self, client):
        """D9 初始化静默:check_notified_status ∈ {'', unknown} 只回写不发
        —— 迁移/新建首跑不产生全量通知风暴。"""
        await register_and_login(client, "v2_silent", "pw123456")
        tpl_id, inst_id = await _seed_pair()
        before = await _notify_count()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="fail",
                             check_message="boom")
            assert inst.check_notified_status == "fail"   # 回写
            assert inst.check_notified_at is None         # 不落通知时间
        assert await _notify_count() == before            # 零通知

    async def test_flip_after_backfill_notifies_immediately(self, client):
        """定稿小项:check_notified_at 为空 = 间隔已满足 —— 静默回写后的
        首拍真翻转即发,不被节流挡。"""
        await register_and_login(client, "v2_flip", "pw123456")
        tpl_id, inst_id = await _seed_pair()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="fail")
        before = await _notify_count()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="pass")
            assert inst.check_notified_status == "pass"
            assert inst.check_notified_at is not None
        assert await _notify_count() == before + 1       # 恢复通知发出

    async def test_throttled_flip_backfilled_next_run(self, client):
        """D9:周期内翻转被节流(不发、状态差一拍);间隔过后下次执行
        自动补发恢复通知,不吞。"""
        await register_and_login(client, "v2_thr", "pw123456")
        tpl_id, inst_id = await _seed_pair(cron="*/5 * * * *")
        # 通知位:failing(已发),时间 = 刚刚 → 周期内
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.check_notified_status = "fail"
            inst.check_notified_at = datetime.now(UTC)
            inst.check_status = "fail"
            await s.commit()
        before = await _notify_count()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="pass")
            assert inst.check_notified_status == "fail"   # 差一拍:不回写
            assert await _notify_count() == before        # 节流:不发
        # 间隔已过(>5min 周期):下次执行补发
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.check_notified_at = datetime.now(UTC) - timedelta(minutes=10)
            await s.commit()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="pass")
            assert inst.check_notified_status == "pass"
        assert await _notify_count() == before + 1        # 补发

    async def test_none_transition_never_notifies(self, client):
        """D9:none↔有结论(场景加/删断言)不发,两个方向都不发。"""
        await register_and_login(client, "v2_none", "pw123456")
        tpl_id, inst_id = await _seed_pair()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="fail")
        before = await _notify_count()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            # fail → none(删了断言):不发,也不动通知位
            await ir._finish(s, inst, tpl, "ok", "", check_status="none")
            assert inst.check_notified_status == "fail"
        # none → fail(又加回断言):与通知位同态,仍不发
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="fail")
        assert await _notify_count() == before

    async def test_platform_mode_notify_goes_to_owner(self, client):
        """D3:平台模式结论通知发模板 owner(实例 holder 是系统用户)。"""
        await register_and_login(client, "v2_own", "pw123456")
        tpl_id, inst_id = await _seed_pair(mode="platform", holder=2,
                                           owner=1)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.check_notified_status = "fail"
            inst.check_notified_at = datetime.now(UTC) - timedelta(hours=1)
            inst.check_status = "fail"
            await s.commit()
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            tpl = await s.get(IntegrationTask, tpl_id)
            await ir._finish(s, inst, tpl, "ok", "", check_status="pass")
        async with db_module.SessionLocal() as s:
            rows = (await s.execute(sa.select(Notification).where(
                Notification.type == "integration"))).scalars().all()
            assert rows and all(r.user_id == 1 for r in rows)


class TestDualTriggerStaleness:
    """D10:now > next_fire(cron, next_fire(cron, last_run)) + 2min。"""

    def test_per_minute_cron(self):
        lr = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
        # 临近触发不闪烁:10:00:30 远未错过两次(10:01/10:02)
        assert not ir.is_stale("*/1 * * * *", lr,
                               now=datetime(2026, 10, 14, 10, 0, 30, tzinfo=UTC))
        # 错过两次 + 宽限:10:04:01 > 10:02 + 2min
        assert ir.is_stale("*/1 * * * *", lr,
                           now=datetime(2026, 10, 14, 10, 4, 1, tzinfo=UTC))
        # 宽限内(= 10:04 整):不算
        assert not ir.is_stale("*/1 * * * *", lr,
                               now=datetime(2026, 10, 14, 10, 4, 0, tzinfo=UTC))

    def test_daily_cron_no_false_stale(self):
        """每天 00:00 的任务,当天 12:00 查看:旧口径(>1h)每天误报;
        双触发只在错过第二天 00:02 后过期。"""
        lr = datetime(2026, 10, 13, tzinfo=UTC)
        assert not ir.is_stale("0 0 * * *", lr,
                               now=datetime(2026, 10, 14, 12, 0, tzinfo=UTC))
        assert ir.is_stale("0 0 * * *", lr,
                           now=datetime(2026, 10, 15, 0, 3, tzinfo=UTC))

    def test_weekday_cron_over_weekend(self):
        """仅工作日 9 点:周五跑完,周末不误报;到周二 09:30(错过周一
        之外的第二次)才过期。"""
        lr = datetime(2026, 10, 9, 9, 0, tzinfo=UTC)   # 周五
        assert not ir.is_stale("0 9 * * 1-5", lr,
                               now=datetime(2026, 10, 12, 9, 30, tzinfo=UTC))
        assert ir.is_stale("0 9 * * 1-5", lr,
                           now=datetime(2026, 10, 13, 9, 30, tzinfo=UTC))

    def test_broken_cron_falls_back_to_one_hour(self):
        lr = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
        assert not ir.is_stale("bad cron", lr, now=lr + timedelta(minutes=30))
        assert ir.is_stale("bad cron", lr, now=lr + timedelta(hours=2))

    def test_never_ran_is_not_stale(self):
        assert not ir.is_stale("*/5 * * * *", None)


# ── /cards 双出(I2:新旧字段并存 + stale 双触发)──────────────────

class TestCardsDualOutput:
    async def test_cards_emit_new_fields(self, client):
        h = await register_and_login(client, "v2_cards", "pw123456")
        tpl_id, inst_id = await _seed_pair(cron="0 0 * * *")
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.run_status = "ok"
            inst.check_status = "fail"
            inst.check_message = "期望 SUCCESS 实际 FAILED"
            inst.last_run_at = datetime.now(UTC) - timedelta(hours=12)
            await s.commit()
        r = await client.post("/api/integration/cards", headers=h,
                              json={"ids": [f"fn:{tpl_id}"]})
        assert r.status_code == 200, r.text
        item = r.json()["items"][0]
        # 新字段
        assert item["runStatus"] == "ok"
        assert item["checkStatus"] == "fail"
        assert "SUCCESS" in item["checkMessage"]
        assert item["checkChangedAt"] is None or \
            isinstance(item["checkChangedAt"], str)
        # 每天 cron,12h 前跑的:双触发不过期(旧口径 1h 会误报)
        assert item["stale"] is False


# ── R-A 存量映射(执行迁移原文 SQL)────────────────────────────────

class TestLegacyMapSql:
    async def test_legacy_rows_mapped(self, client):
        """R-A:passed→ok;failed+auth_failed 暂停 → auth(不落 channel
        —— 此暂停不按周期重试,错标最严重分类无法自愈);failed 其余 →
        channel;timeout → timeout。模板行不动。

        I3.5 后模型已无 last_status 列 —— 测试库用 ALTER 补回旧列、
        以 SQL 造出生产库在 0024 迁移时的真实形状,再跑迁移原文 SQL。
        """
        import importlib.util
        from pathlib import Path
        mig_path = Path(__file__).resolve().parents[1] / "alembic" / \
            "versions" / "0024_integration_run_check_split.py"
        spec = importlib.util.spec_from_file_location("mig0024", mig_path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        await register_and_login(client, "v2_mig", "pw123456")
        async with db_module.SessionLocal() as s:
            await ensure_fk_users(s, 1, 2, 3, 4, 5)
            s.add(IntegrationTask(
                name="tpl", owner_id=1, visibility="public",
                identity_mode="platform", scenario_id="sc-v2-mig",
                trigger_cron="*/5 * * * *"))
            await s.flush()
            tpl_id = (await s.execute(sa.select(IntegrationTask.id).order_by(
                IntegrationTask.id.desc()))).scalars().first()
            legacy = [
                ("passed", "", "ok"),
                ("failed", "auth_failed", "auth"),
                ("failed", "", "channel"),
                ("failed", "missing_credential", "channel"),
                ("timeout", "", "timeout"),
            ]
            for i, (ls, pr, _) in enumerate(legacy):
                s.add(IntegrationTask(
                    name="i", owner_id=1, holder_id=i + 1,
                    template_id=tpl_id, state="idle", paused_reason=pr))
            await s.commit()

            # 补回旧列并回填 legacy 值(模拟生产库在迁移前的形状)
            conn = await s.connection()
            await conn.execute(sa.text(
                "ALTER TABLE integration_tasks "
                "ADD COLUMN IF NOT EXISTS last_status VARCHAR(16) "
                "DEFAULT ''"))
            await conn.execute(sa.text(
                "UPDATE integration_tasks SET last_status='passed' "
                "WHERE id=:i").bindparams(i=tpl_id))
            for i, (ls, _, _) in enumerate(legacy):
                await conn.execute(sa.text(
                    "UPDATE integration_tasks SET last_status=:ls "
                    "WHERE template_id=:t AND holder_id=:h").bindparams(
                    ls=ls, t=tpl_id, h=i + 1))
            for stmt in mig.LEGACY_MAP_SQL:
                await conn.execute(sa.text(stmt))
            await s.commit()
        async with db_module.SessionLocal() as s:
            conn = await s.connection()
            mapped = (await conn.execute(sa.text(
                "SELECT holder_id, run_status, check_status, last_status "
                "FROM integration_tasks WHERE template_id=:t").bindparams(
                t=tpl_id))).all()
            by_holder = {r[0]: (r[1], r[2], r[3]) for r in mapped}
            for i, (ls, _, run) in enumerate(legacy):
                got_run, got_check, _ = by_holder[i + 1]
                assert got_run == run, (ls, got_run)
                assert got_check == "unknown"
            # 模板行不映射(run 空)
            tpl_row = (await conn.execute(sa.text(
                "SELECT run_status FROM integration_tasks "
                "WHERE id=:i").bindparams(i=tpl_id))).scalar()
            assert tpl_row == ""


# ── 节流周期口径(合入评估 §3-4:nf2-nf1,与过期判定双触发法同口径)──


class TestPeriodSeconds:
    def test_manual_run_mid_interval_not_shortened(self):
        """手动执行落在周期尾部不再把周期算短:整点 cron 前两分钟跑,
        旧「nf - 锚点」口径得 2 分钟(节流偏松),nf2 - nf1 恒为真实周期。"""
        anchor = datetime(2026, 10, 15, 10, 58, tzinfo=timezone.utc)
        assert ir._period_seconds("0 * * * *", anchor) == 3600.0
        # 锚点恰在触发点上:两种口径等价,不回归
        on_fire = datetime(2026, 10, 15, 11, 0, tzinfo=timezone.utc)
        assert ir._period_seconds("0 * * * *", on_fire) == 3600.0

    def test_daily_and_fallback(self):
        anchor = datetime(2026, 10, 15, 15, 30, tzinfo=timezone.utc)
        assert ir._period_seconds("0 3 * * *", anchor) == 86400.0
        assert ir._period_seconds("bogus-cron", anchor) == 3600.0   # 回退
        assert ir._period_seconds("0 * * * *", None) >= 60.0
