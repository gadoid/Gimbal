"""End-to-end smoke test: bootstrap -> Engine.run -> artifacts."""
import sys, io, tempfile, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Quiet console
sys.stderr = io.StringIO()

from gimbal.cli.context import CLIContext
from gimbal.core.bootstrap import bootstrap
from gimbal.core.runner import Engine
from gimbal.schema.scenario import Scenario, Step


def main():
    cli = CLIContext(env="dev", mode="local", log_level="info")
    cli.extras["reporters"] = ["console", "json", "junit"]

    with tempfile.TemporaryDirectory() as td:
        cli.extras["report_dir"] = os.path.join(td, "reports")
        cfg = bootstrap(cli)
        sys.stdout.write("bootstrap OK\n")
        sys.stdout.write("  reporters: {}\n".format(list(cfg.cfg.reporters)))
        sys.stdout.write("  report_dir: {}\n".format(cfg.cfg.report_dir))
        sys.stdout.write("  reporter_runtime: {}\n".format(type(cfg.reporter_runtime).__name__))

        sc = Scenario(scenarioId="smoke-001", name="Smoke")
        sc.steps = [Step(stepId="s1", name="noop", strategy="http")]
        eng = Engine(cfg)
        res = eng.run(sc)
        sys.stdout.write("engine.run() exit_code = {}\n".format(res.exit_code))
        sys.stdout.write("artifacts:\n")
        for a in eng.artifacts:
            loc = str(a.path) if a.path else "<inline>"
            sys.stdout.write("  - {} [{}] -> {}\n".format(a.name, a.media_type, loc))
        # Verify artifact files exist
        for a in eng.artifacts:
            if a.path:
                assert os.path.isfile(a.path), f"missing: {a.path}"
        sys.stdout.write("ALL SMOKE CHECKS PASSED\n")


if __name__ == "__main__":
    main()
