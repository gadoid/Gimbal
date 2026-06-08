"""Unit tests for gimbal.reporter.registry (ReporterRegistry).

Coverage:
  [1] register / unregister / available / has / get_factory / create
  [2] duplicate registration raises ReporterAlreadyRegistered
  [3] missing reporter raises ReporterNotFound
  [4] replace=True allows re-register
  [5] builtins all register cleanly
  [6] factory receives user_config dict
  [8] create() raises ReporterNotFound for unknown name in list
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("REPORTER REGISTRY TEST")
print("=" * 60)


def test_register_and_lookup():
    from gimbal.reporter.registry import ReporterRegistry
    reg = ReporterRegistry()

    def my_factory(user_config):
        class R:
            name = "mock"
        return R()

    reg.register("mock", my_factory)
    assert "mock" in reg.available()
    assert reg.has("mock")
    assert reg.get_factory("mock") is my_factory
    rs = reg.create(["mock"], {"mock": {"x": 1}})
    assert len(rs) ==1 and rs[0].name == "mock"
    print(" [1] register + lookup + create: OK")


def test_duplicate_raises():
    from gimbal.reporter.registry import ReporterRegistry, ReporterAlreadyRegistered
    reg = ReporterRegistry()
    reg.register("x", lambda c: None)
    try:
        reg.register("x", lambda c: None)
    except ReporterAlreadyRegistered:
        print(" [2] duplicate registration raises ReporterAlreadyRegistered: OK")
        return
    raise AssertionError("expected ReporterAlreadyRegistered")


def test_missing_raises():
    from gimbal.reporter.registry import ReporterRegistry, ReporterNotFound
    reg = ReporterRegistry()
    try:
        reg.get_factory("does-not-exist")
    except ReporterNotFound:
        print(" [3] missing reporter raises ReporterNotFound: OK")
        return
    raise AssertionError("expected ReporterNotFound")


def test_unregister():
    from gimbal.reporter.registry import ReporterRegistry
    reg = ReporterRegistry()
    reg.register("a", lambda c: None)
    assert reg.has("a")
    assert reg.unregister("a") is True
    assert not reg.has("a")
    assert reg.unregister("a") is False
    print(" [4] unregister: OK")


def test_replace():
    from gimbal.reporter.registry import ReporterRegistry
    reg = ReporterRegistry()
    reg.register("x", lambda c: "v1")
    reg.register("x", lambda c: "v2", replace=True)
    assert reg.get_factory("x")({"any":1}) == "v2"
    print(" [5] replace=True allows re-register: OK")


def test_builtin_registry():
    from gimbal.reporter.registry import ReporterRegistry
    from gimbal.reporter.builtin import register_builtin_reporters, BUILTIN_NAMES
    reg = ReporterRegistry()
    register_builtin_reporters(reg)
    assert set(reg.available()) == set(BUILTIN_NAMES)
    rs = reg.create(list(BUILTIN_NAMES), {})
    assert len(rs) == len(BUILTIN_NAMES)
    for r, name in zip(rs, BUILTIN_NAMES):
        assert hasattr(r, "name") and r.name == name
    print(" [6] all builtins register and instantiate: OK")


def test_factory_receives_user_config():
    from gimbal.reporter.registry import ReporterRegistry
    seen = {}
    def factory(user_config):
        seen.update(user_config)
        class R: name = "u"
        return R()
    reg = ReporterRegistry()
    reg.register("u", factory)
    reg.create(["u"], {"u": {"verbosity": "verbose", "x": 7}})
    assert seen == {"verbosity": "verbose", "x": 7}
    print(" [7] factory receives user_config dict: OK")


def test_missing_in_create():
    from gimbal.reporter.registry import ReporterRegistry, ReporterNotFound
    reg = ReporterRegistry()
    reg.register("a", lambda c: None)
    try:
        reg.create(["a", "ghost"], {})
    except ReporterNotFound:
        print(" [8] create() raises ReporterNotFound for unknown name: OK")
        return
    raise AssertionError("expected ReporterNotFound")


def main():
    test_register_and_lookup()
    test_duplicate_raises()
    test_missing_raises()
    test_unregister()
    test_replace()
    test_builtin_registry()
    test_factory_receives_user_config()
    test_missing_in_create()
    print("=" * 60)
    print("ALL REPORTER REGISTRY TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
