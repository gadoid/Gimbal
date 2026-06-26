"""PlateManifest 单元测试(PR-2.0)。

业务承诺:
  * 同 version + 同 services → byte-equal checksum(可复现性)
  * version / services / 服务端点变化 → checksum 变化(漂移检测)
  * ``verify()`` 自建自检通过,改 services 后 verify 抛
  * checksum 用 SHA256(hex digest)
  * services 排序无关(sort_keys + sorted services 抵消)

对应设计:PR-2.0 §2.4 + PLATE_EVOLUTION §3(版本 pin 是硬前提)。
"""
from __future__ import annotations

import hashlib
import json

import pytest

from Plate.manifest import PlateManifest
from Plate.version import PlateVersion


def _v() -> PlateVersion:
    """便捷:固定版本 v1.0.0。"""
    return PlateVersion(1, 0, 0)


def _spec(method: str, path: str) -> dict:
    """便捷:构造一个最小 EndpointSpec dict。"""
    return {
        "method": method,
        "path": path,
        "category": "query",
        "mutates_state": False,
        "bindings": [],
        "request_ref": None,
        "responses_ref": {},
        "default_response_ref": None,
        "response_data_models_ref": {},
        "summary": "",
        "description": "",
        "tags": [],
        "auth_required": False,
        "response_union_ref": {},
        "mock_hook_ref": None,
        "validate_hook_ref": None,
        "build_request_hook_ref": None,
    }


# ════════════════════════════════════════════════════════════════════════════
# checksum byte-equal
# ════════════════════════════════════════════════════════════════════════════


class TestPlateManifestChecksumDeterminism:
    def test_same_input_same_checksum(self) -> None:
        """业务需求:同输入 → 同 checksum(可复现性)。"""
        services = {"fin": [_spec("GET", "/a"), _spec("POST", "/b")]}
        m1 = PlateManifest.from_services(_v(), services)
        m2 = PlateManifest.from_services(_v(), services)
        assert m1.checksum == m2.checksum

    def test_services_dict_order_independent(self) -> None:
        """业务需求:services dict 插入顺序不影响 checksum。

        对应 A2 byte-equal:dict 内部排序。
        """
        services_a = {"fin": [_spec("GET", "/a")], "auth": [_spec("POST", "/b")]}
        services_b = {"auth": [_spec("POST", "/b")], "fin": [_spec("GET", "/a")]}
        m_a = PlateManifest.from_services(_v(), services_a)
        m_b = PlateManifest.from_services(_v(), services_b)
        assert m_a.checksum == m_b.checksum

    def test_specs_list_order_independent(self) -> None:
        """业务需求:同一 service 内端点 list 顺序不影响 checksum。

        对应 A2 byte-equal:list 排序 by (method, path)。
        """
        s_a, s_b = _spec("GET", "/a"), _spec("POST", "/b")
        m_1 = PlateManifest.from_services(_v(), {"fin": [s_a, s_b]})
        m_2 = PlateManifest.from_services(_v(), {"fin": [s_b, s_a]})
        assert m_1.checksum == m_2.checksum


# ════════════════════════════════════════════════════════════════════════════
# checksum 变化检测
# ════════════════════════════════════════════════════════════════════════════


class TestPlateManifestChecksumSensitivity:
    def test_different_version_different_checksum(self) -> None:
        """业务需求:版本升级 → checksum 变化(协议升级硬前提)。"""
        services = {"fin": [_spec("GET", "/a")]}
        m_v1 = PlateManifest.from_services(PlateVersion(1, 0, 0), services)
        m_v2 = PlateManifest.from_services(PlateVersion(2, 0, 0), services)
        assert m_v1.checksum != m_v2.checksum

    def test_different_service_count_different_checksum(self) -> None:
        """业务需求:新增 service → checksum 变化。"""
        m_one = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        m_two = PlateManifest.from_services(
            _v(),
            {"fin": [_spec("GET", "/a")], "auth": [_spec("POST", "/b")]},
        )
        assert m_one.checksum != m_two.checksum

    def test_different_endpoint_count_different_checksum(self) -> None:
        """业务需求:端点增减 → checksum 变化。"""
        m_one = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        m_two = PlateManifest.from_services(
            _v(),
            {"fin": [_spec("GET", "/a"), _spec("POST", "/b")]},
        )
        assert m_one.checksum != m_two.checksum

    def test_different_endpoint_path_different_checksum(self) -> None:
        """业务需求:端点 path 变化 → checksum 变化。"""
        m_one = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        m_two = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/b")]})
        assert m_one.checksum != m_two.checksum


# ════════════════════════════════════════════════════════════════════════════
# verify 漂移检测
# ════════════════════════════════════════════════════════════════════════════


class TestPlateManifestVerify:
    def test_verify_passes_for_built_manifest(self) -> None:
        """业务需求:from_services 构造的 manifest,verify() 不抛(自检)。"""
        m = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        m.verify()  # 不抛

    def test_verify_detects_drift_after_mutation(self) -> None:
        """业务需求:篡改 services 后 verify() 抛 ValueError(漂移检测)。

        注:frozen=True 阻止整体替换,只能改 dict 内部内容。
        """
        m = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        # 篡改内部 list
        m.services["fin"].append(_spec("GET", "/evil"))
        with pytest.raises(ValueError, match="checksum 不一致"):
            m.verify()

    def test_verify_detects_corrupted_checksum(self) -> None:
        """业务需求:checksum 字段被改坏 → verify 抛。"""
        m = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        # dataclass(frozen=True) 用 object.__setattr__ 绕过冻结
        object.__setattr__(m, "checksum", "deadbeef" * 8)
        with pytest.raises(ValueError, match="checksum 不一致"):
            m.verify()


# ════════════════════════════════════════════════════════════════════════════
# to_dict
# ════════════════════════════════════════════════════════════════════════════


class TestPlateManifestToDict:
    def test_to_dict_contains_version_services_checksum(self) -> None:
        """业务需求:to_dict 三键:version / services / checksum。"""
        m = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        d = m.to_dict()
        assert set(d.keys()) == {"version", "services", "checksum"}
        assert d["version"] == {"major": 1, "minor": 0, "patch": 0}
        assert "fin" in d["services"]

    def test_to_dict_services_sorted(self) -> None:
        """业务需求:to_dict 输出 services 已排序(调用方责任)。"""
        m = PlateManifest.from_services(
            _v(),
            {"fin": [_spec("GET", "/a")], "auth": [_spec("POST", "/b")]},
        )
        d = m.to_dict()
        assert list(d["services"].keys()) == ["auth", "fin"]

    def test_to_dict_specs_sorted_within_service(self) -> None:
        """业务需求:同 service 内端点 list 按 (method, path) 排序。

        注:Python tuple 排序先比第一个元素(method)。GET < POST(字母序),
        所以 GET 路径整体在前,POST 路径整体在后。
        """
        # 故意插入顺序打乱
        m = PlateManifest.from_services(
            _v(),
            {"fin": [_spec("POST", "/z"), _spec("GET", "/a"), _spec("POST", "/a")]},
        )
        d = m.to_dict()
        # 排序结果:GET 在前,POST 在后;POST 内按 path 升序
        expected_pairs = [("GET", "/a"), ("POST", "/a"), ("POST", "/z")]
        actual_pairs = [
            (s["method"], s["path"]) for s in d["services"]["fin"]
        ]
        assert actual_pairs == expected_pairs


# ════════════════════════════════════════════════════════════════════════════
# 算法细节
# ════════════════════════════════════════════════════════════════════════════


class TestPlateManifestAlgorithm:
    def test_checksum_is_sha256_hex(self) -> None:
        """业务需求:checksum 是 SHA256 hex digest(64 字符)。"""
        m = PlateManifest.from_services(_v(), {"fin": [_spec("GET", "/a")]})
        # SHA256 hex = 64 字符 + 全 [0-9a-f]
        assert len(m.checksum) == 64
        assert all(c in "0123456789abcdef" for c in m.checksum)

    def test_checksum_matches_manual_compute(self) -> None:
        """业务需求:compute_checksum 与手工 json.dumps(sort_keys=True)+sha256 一致。"""
        services = {"fin": [_spec("GET", "/a")]}
        expected_payload = {
            "version": {"major": 1, "minor": 0, "patch": 0},
            "services": {"fin": [_spec("GET", "/a")]},
        }
        expected = hashlib.sha256(
            json.dumps(expected_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        actual = PlateManifest.compute_checksum(_v(), services)
        assert actual == expected