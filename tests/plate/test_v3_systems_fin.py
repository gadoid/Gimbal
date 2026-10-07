"""fin 系统清单(A2 重写:Python 实例与模板工厂已退役,真源 = systems/fin/)。

旧版覆盖 systems/fin/*.py 工厂契约;A2 起模板内容转为
``systems/fin/system.md`` 的 gimbal:defaults 数据,工厂测试使命完成。
本测试保留 fin 系统的结构性验收:端点数、服务声明、默认模板可加载。
"""
from __future__ import annotations

from gimbal_plate.dialect import EndpointSpec
from tests.plate.conftest import SYSTEMS_ROOT
from gimbal_plate.loader import load_registry

_REG = load_registry([SYSTEMS_ROOT])
ALL_ENDPOINTS = [e for e in _REG.list_endpoints() if isinstance(e, EndpointSpec)]
ALL_FIN = [e for e in ALL_ENDPOINTS if e.system == "fin"]


class TestSystemsFinInventory:
    def test_endpoint_count(self):
        # 21 → 24(09-09 客户域)→ 25(09-20 demo)→ 23(S1-0 B3)
        assert len(ALL_FIN) == 23

    def test_service_declared_with_metadata(self):
        svc = _REG.get_service("fin-service")
        assert svc is not None
        assert svc.version == "1.1.0"  # gimbal:system 块声明

    def test_defaults_seeded(self):
        assert _REG.index_for("config").index.get("fin.default") is not None
        assert _REG.index_for("meta").index.get("fin.default") is not None
        assert _REG.index_for("resource").index.get("fin.tidb_test") is not None
        assert _REG.index_for("scenario").index.get("sc-fin-default") is not None


class TestQueryViews:
    def test_endpoint_with_views(self):
        eps = [e for e in ALL_FIN if e.query_views]
        assert eps, "fin 应有挂 query_views 的端点"

    def test_endpoint_count_total(self):
        assert len(ALL_ENDPOINTS) == 149
