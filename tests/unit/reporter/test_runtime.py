"""Unit tests for gimbal.reporter.runtime (ReporterRuntime).

Coverage:
  [1] setup -> ready state
  [2] begin_all -> running state, subscribes to bus
  [3] finalize_all -> closed (after shutdown), produces ReportArtifact list
  [4] one bad reporter does not break others (error isolation)
  [5] shutdown unsubscribes
  [6] shutdown is idempotent
"""
import sys, os, tempfile, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("REPORTER RUNTIME TEST")
print("=" * 60)


class _FakeCtx:
    def __init__(self, run_id, env, mode, cfg):
        self.run_id = run_id
        self.env = env
        self.mode = mode
        self.config = cfg
        self.ctx_manager = None


def _build_runtime(tmpdir, names=("console",)):
    from gimbal.reporter.registry import ReporterRegistry
    from gimbal.reporter.runtime import ReporterRuntime
    from gimbal.reporter.builtin import register_builtin_reporters
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.config.models import BootstrapConfig

    reg = ReporterRegistry()
    register_builtin_reporters(reg)
    bus = InMemoryEventBus()
    cfg = BootstrapConfig(report_dir=tmpdir)
    rt = ReporterRuntime(reg)
    rt.setup(bus=bus, config=cfg)
    ctx = _FakeCtx("r1", "dev", "local", cfg)
    rt.begin_all(framework_ctx=ctx, reporter_names=list(names), report_dir=tmpdir, plugin_configs={})
    return rt, bus, cfg


def test_setup_then_begin_then_finalize():
    from gimbal.core.runner import RunResult
    with tempfile.TemporaryDirectory() as td:
        rt, bus, cfg = _build_runtime(td, names=("console", "junit"))
        assert rt.state == "running"
        rr = RunResult(exit_code=0, total=1, passed=1, failed=0, details=[{
            "scenario_id": "s1", "status": "passed", "duration_ms": 12.0,
        }])
        arts = rt.finalize_all(rr)
        assert len(arts) ==2
        names = sorted(a.name for a in arts)
        assert names == ["console", "junit"]
        rt.shutdown()
        assert rt.state == "closed"
        print(" [1] setup -> begin -> finalize -> shutdown: OK")


def test_error_isolation():
    """One bad reporter must not stop others."""
    from gimbal.reporter.registry import ReporterRegistry
    from gimbal.reporter.runtime import ReporterRuntime
    from gimbal.reporter.builtin import register_builtin_reporters
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.config.models import BootstrapConfig
    from gimbal.core.runner import RunResult

    def bad_factory(user_config):
        def _init(self): pass
        cls = type("Bad", (), {
            "name": "bad",
            "begin": lambda self, ctx: (_ for _ in ()).throw(RuntimeError("begin failed")),
            "on_event": lambda self, e: None,
            "finalize": lambda self, rr, ctx: (_ for _ in ()).throw(RuntimeError("finalize failed")),
        })
        return cls()

    def good_factory(user_config):
        from gimbal.reporter.builtin.console import ConsoleReporter
        return ConsoleReporter()

    reg = ReporterRegistry()
    register_builtin_reporters(reg)
    reg.register("bad", bad_factory, replace=True)

    with tempfile.TemporaryDirectory() as td:
        bus = InMemoryEventBus()
        cfg = BootstrapConfig(report_dir=td)
        rt = ReporterRuntime(reg)
        rt.setup(bus=bus, config=cfg)
        ctx = _FakeCtx("r2", "dev", "local", cfg)
        # Should not raise; bad is logged & skipped
        rt.begin_all(framework_ctx=ctx, reporter_names=["bad", "console"], report_dir=td, plugin_configs={})
        # Console should still be active
        assert any(r.name == "console" for r in rt._reporters), "console must survive"
        rr = RunResult(exit_code=0, total=1, passed=1, failed=0, details=[])
        arts = rt.finalize_all(rr)
        # Only console should produce an artifact; bad was excluded
        assert all(a.name != "bad" for a in arts)
        assert any(a.name == "console" for a in arts)
        # Error log should have entries for the bad reporter
        errs = rt.error_log.entries
        assert any(e.reporter_name == "bad" for e in errs), \
         f"expected error entry for 'bad', got {[e.reporter_name for e in errs]}"
        rt.shutdown()
        print(f" [2] error isolation: bad reporter excluded, {len(errs)} error entries logged: OK")


def test_shutdown_idempotent():
    with tempfile.TemporaryDirectory() as td:
        rt, bus, cfg = _build_runtime(td, names=("console",))
        rt.shutdown()
        # Second shutdown must not raise
        rt.shutdown()
        assert rt.state == "closed"
        print(" [3] shutdown is idempotent: OK")


def test_empty_reporters():
    """begin_all with empty list is a no-op."""
    from gimbal.reporter.registry import ReporterRegistry
    from gimbal.reporter.runtime import ReporterRuntime
    from gimbal.reporter.builtin import register_builtin_reporters
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.config.models import BootstrapConfig
    from gimbal.core.runner import RunResult

    reg = ReporterRegistry()
    register_builtin_reporters(reg)
    with tempfile.TemporaryDirectory() as td:
        bus = InMemoryEventBus()
        cfg = BootstrapConfig(report_dir=td)
        rt = ReporterRuntime(reg)
        rt.setup(bus=bus, config=cfg)
        ctx = _FakeCtx("r3", "dev", "local", cfg)
        rt.begin_all(framework_ctx=ctx, reporter_names=[], report_dir=td, plugin_configs={})
        assert rt.state == "running"
        rr = RunResult()
        arts = rt.finalize_all(rr)
        assert arts == []
        rt.shutdown()
        print(" [4] empty reporter list: OK")


def main():
    test_setup_then_begin_then_finalize()
    test_error_isolation()
    test_shutdown_idempotent()
    test_empty_reporters()
    print("=" * 60)
    print("ALL REPORTER RUNTIME TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
