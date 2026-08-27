"""V3 阶段 1 钉死测试:每个 endpoint/<id>.py 只导出 1 个 EndpointSpec 实例。

按 V3 决策:endpoint 不再集中放,改为每接口独立文件,文件名 = <id 的第三段>。
"""
from __future__ import annotations

import importlib
from pathlib import Path

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS

SYSTEMS_ROOT = Path("src/gimbal-plate/gimbal_plate/systems")


class TestOneFilePerEndpoint:
    """systems/<sys>/endpoint/<id>.py 一文件一 EndpointSpec 实例。"""

    def test_each_endpoint_file_exports_one_endpointspec(self) -> None:
        endpoint_dir = SYSTEMS_ROOT / "fin" / "endpoint"
        py_files = [p for p in endpoint_dir.glob("*.py") if p.name != "__init__.py"]
        assert len(py_files) >= 1
        for path in py_files:
            mod_name = ".".join(path.with_suffix("").parts)
            mod = importlib.import_module(mod_name)
            # 找到模块里所有 EndpointSpec 子类的实例(模块级常量)
            ep_attrs = [
                v for v in vars(mod).values()
                if isinstance(v, EndpointSpec)
            ]
            assert len(ep_attrs) == 1, (
                f"{path.name} 应该导出 1 个 EndpointSpec 实例,实际 {len(ep_attrs)} 个"
            )

    def test_endpoint_filename_matches_id_last_segment(self) -> None:
        """文件名的语义约定:id 的第三段(<system>.<域>.<action>)中 action 部分。

        注:id 第二段是接口域(account/order/...),与 EndpointSpec.service
        (部署单元,统一为 fin-service)已解耦。
        """
        for ep in ALL_ENDPOINTS:
            # id 形如 fin.settlement.create_order
            # 文件名形如 settlement_create_order.py
            parts = ep.id.split(".")
            assert len(parts) >= 3, f"{ep.id} id 至少需要三段"
            expected_filename = f"{parts[1]}_{parts[2]}.py"
            # 验证 ALL_ENDPOINTS 中的每个 ep 都能在 endpoint 目录里找到对应文件
            endpoint_dir = SYSTEMS_ROOT / "fin" / "endpoint"
            matching = [
                p for p in endpoint_dir.glob(f"{parts[1]}_*.py")
                if ep.id.split(".")[-1] in p.stem
            ]
            assert matching, (
                f"{ep.id} 没有对应文件 {expected_filename}"
            )

    def test_endpoint_id_uniqueness_across_files(self) -> None:
        """不同 endpoint 文件的 id 不重复。"""
        ids = [ep.id for ep in ALL_ENDPOINTS]
        assert len(ids) == len(set(ids)), f"id 重复: {ids}"

    def test_no_duplicate_endpoint_spec_instances(self) -> None:
        """ALL_ENDPOINTS 聚合出的实例无重复。"""
        assert len(ALL_ENDPOINTS) == len(set(id(ep) for ep in ALL_ENDPOINTS))
