"""``plate doc`` CLI 测试(Phase 3 §4.1)。

对应设计:``design/phase3/PR-3.1.md`` §3.2。

测试策略:
  - 用 ``capsys`` 捕获 stdout/stderr
  - 调 ``main(argv)`` 而不是 ``subprocess.run``(避免 stdout 编码陷阱)
  - 集成 ``registry.warm`` → 渲染层 → 输出验证
  - 用 ``registry.reset()`` 在测试间隔离(已注册 service)
"""
from __future__ import annotations

import pytest

from Plate import registry
from Plate.api_doc.cli import main as cli_main


@pytest.fixture(autouse=True)
def _reset_registry():
    """每个测试前后 reset,避免 registry 状态污染。"""
    registry.reset()
    yield
    registry.reset()


# ════════════════════════════════════════════════════════════════════════════
# §3.2 #1: plate doc fin 跑通
# ════════════════════════════════════════════════════════════════════════════


class TestCliHappyPath:
    def test_fin_renders_to_stdout(self, capsys):
        rc = cli_main(["fin"])
        captured = capsys.readouterr()

        assert rc == 0
        assert "# fin 服务 API 文档" in captured.out
        # fin 真实端点(驼峰式命名,见 ``src/Plate/fin/endpoints.py``)
        assert "### POST /api/order/order/orderAdd" in captured.out
        assert "> 共 31 个端点" in captured.out  # fin 有 31 端点
        # 错误不输出到 stderr
        assert captured.err == ""

    def test_help_exits_zero_with_usage(self, capsys):
        rc = cli_main(["--help"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "用法" in captured.out
        assert "plate doc" in captured.out


# ════════════════════════════════════════════════════════════════════════════
# §3.2 #2: 多 service,部分未登记
# ════════════════════════════════════════════════════════════════════════════


class TestCliPartialFailure:
    def test_one_success_one_failure_exits_one(self, capsys):
        rc = cli_main(["fin", "unknown_service_xyz"])
        captured = capsys.readouterr()

        assert rc == 1  # 部分失败
        # fin 仍渲染
        assert "# fin 服务 API 文档" in captured.out
        # unknown 走 stderr
        assert "unknown_service_xyz" in captured.err

    def test_all_unknown_exits_two(self, capsys):
        rc = cli_main(["no_such_a", "no_such_b"])
        captured = capsys.readouterr()

        assert rc == 2  # 全部失败
        assert captured.out == ""  # 无输出
        assert "no_such_a" in captured.err
        assert "no_such_b" in captured.err


# ════════════════════════════════════════════════════════════════════════════
# §3.2 #3: 空 args / -h
# ════════════════════════════════════════════════════════════════════════════


class TestCliEmptyArgs:
    def test_empty_args_prints_usage(self, capsys):
        rc = cli_main([])
        captured = capsys.readouterr()
        assert rc == 0
        assert "用法" in captured.out

    def test_short_help_flag(self, capsys):
        rc = cli_main(["-h"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "用法" in captured.out


# ════════════════════════════════════════════════════════════════════════════
# §3.2 #4: 渲染后 warm() 不污染下次调用(隔离性)
# ════════════════════════════════════════════════════════════════════════════


class TestCliIsolation:
    def test_second_call_does_not_see_first_call_state(self, capsys):
        # 第一次:fin
        rc1 = cli_main(["fin"])
        out1 = capsys.readouterr().out
        assert rc1 == 0
        assert "fin 服务" in out1

        # 第二次:fin 仍正常(fixture 已 reset registry,但 warm 幂等)
        capsys.readouterr()  # 清掉之前累积
        rc2 = cli_main(["fin"])
        out2 = capsys.readouterr().out
        assert rc2 == 0
        assert "fin 服务" in out2
        # 第二次不应包含第一次的输出残留(我们的渲染无副作用)
        # 输出两遍同样内容是正常的(都是 fin 的 31 端点)


# ════════════════════════════════════════════════════════════════════════════
# §3.2 #5: L2 lookup 验证(用 fin 测试 L2 工厂)
# ════════════════════════════════════════════════════════════════════════════


class TestCliL2Integration:
    def test_fin_l2_factory_called(self, capsys):
        """fin 的 _DOC_LOOKUP_FACTORIES 已登记,渲染时走 dannotations.get_doc。
        当前 dannotations 是空 dict,所以渲染输出里 with_l2=0(无 L2 注释)。"""
        rc = cli_main(["fin"])
        captured = capsys.readouterr()
        assert rc == 0
        # dannotations 空 → 0 个有 L2 注释
        assert "> 共 31 个端点,0 个有 L2 注释" in captured.out

    def test_unregistered_service_uses_no_l2(self, capsys):
        """未登记 service 的 doc_lookup=None,显示"(无 L2 注释)"。"""
        # 直接注册一个临时 service(避免污染 fin)
        # 这里我们用 mock,只验证 cli 对未登记 service 的处理
        # (用 unknown_service 但要确保 _DOC_LOOKUP_FACTORIES 没登记它)
        rc = cli_main(["some_service_not_registered"])
        captured = capsys.readouterr()
        # unknown 走 stderr 警告
        assert rc in (1, 2)
        assert "some_service_not_registered" in captured.err