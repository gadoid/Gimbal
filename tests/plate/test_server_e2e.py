"""Plate 服务端 E2E 测试(PR-2.3)。

业务承诺(对应 PR-2.3 §3.2):
  * 真实 HTTP 拉数据 → 服务端响应 == 本地 to_dict 产物(byte-equal 锁定)
  * 服务端 manifest checksum == 本地构建的 checksum
  * 错误响应 JSON 形态符合 PR-2.1 §2.4
  * 服务端可独立启动 + 多端点协同
  * 远端服务 pin 流程:start server → SDK 拉 → 字段 pin

对应设计:PR-2.3 §3.2。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

import pytest

from Plate import registry
from Plate.manifest import PlateManifest
from Plate.server import PlateServer
from Plate.version import PlateVersion


# ── E2E fixture:session 级 server(整批测试共享一个进程) ──


@pytest.fixture(scope="module")
def e2e_server() -> Iterator[PlateServer]:
    """Module 级 E2E server:启动一次,本模块全部 E2E 测试共享。

    注意:E2E 测试读 server 是无状态的(只 GET,不改 registry 状态),
    共享 server 减少端口分配 + 启动开销。
    """
    registry.reset()
    s = PlateServer(port=0)
    s.start()
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture
def base(e2e_server: PlateServer) -> str:
    return f"http://127.0.0.1:{e2e_server.port}"


def _get(url: str) -> tuple[int, dict]:
    """便捷 GET,返回 (status, json_body)。"""
    try:
        r = urllib.request.urlopen(url)
        return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ════════════════════════════════════════════════════════════════════════════
# E2E — 字节级 pin 验证
# ════════════════════════════════════════════════════════════════════════════


class TestE2EByteEqual:
    def test_e2e_spec_service_byte_equal_to_local(
        self, base: str
    ) -> None:
        """业务需求:服务端 /v1/spec/fin?version=1.0.0 响应 == 本地 fin specs to_dict
        拼装产物(逐字段相等)。

        这是 SDK 的核心保证:HTTP 响应是 to_dict() 的精确转录,
        客户端解析后能还原为本地等价对象。
        """
        # 1. HTTP 拉
        status, body = _get(f"{base}/v1/spec/fin?version=1.0.0")
        assert status == 200

        # 2. 本地构造 spec 列表
        registry.collect("fin")
        local_specs = [
            s.to_dict() for k, s in registry._index.items() if k.service == "fin"
        ]
        local_specs_sorted = sorted(
            local_specs, key=lambda s: (s["method"], s["path"])
        )

        # 3. 校验:每条 spec 字段相等
        for remote_spec, local_spec in zip(body["specs"], local_specs_sorted):
            assert remote_spec == local_spec

    def test_e2e_manifest_checksum_matches_local(self, base: str) -> None:
        """业务需求:服务端 manifest checksum == 本地 PlateManifest 构建的 checksum。

        这是协议可执行性的核心 — checksum 锁定说明两端序列化字节级一致。
        """
        # 1. HTTP 拉 manifest
        status, body = _get(f"{base}/v1/manifest")
        assert status == 200
        remote_checksum = body["checksum"]

        # 2. 本地构造
        registry.collect("fin")
        local_specs = [
            s.to_dict() for k, s in registry._index.items() if k.service == "fin"
        ]
        local_manifest = PlateManifest.from_services(
            PlateVersion(1, 0, 0), {"fin": local_specs}
        )

        # 3. 校验
        assert remote_checksum == local_manifest.checksum

    def test_e2e_spec_endpoint_byte_equal_to_local(self, base: str) -> None:
        """业务需求:服务端单端点 spec 响应 == 本地 spec.to_dict()。"""
        status, body = _get(
            f"{base}/v1/spec/fin/POST/api/order/order/orderDetail?version=1.0.0"
        )
        assert status == 200

        local_spec = registry.resolve(
            "fin", "POST", "/api/order/order/orderDetail"
        ).to_dict()
        assert body["spec"] == local_spec


# ════════════════════════════════════════════════════════════════════════════
# E2E — 错误响应形态
# ════════════════════════════════════════════════════════════════════════════


class TestE2EErrorShape:
    def test_e2e_error_response_has_error_message_keys(self, base: str) -> None:
        """业务需求:所有错误响应 body 必含 ``error`` + ``message`` 键。

        对应 PR-2.1 §2.4 错误响应 schema。
        """
        # VERSION_NOT_FOUND
        status, body = _get(f"{base}/v1/manifest/99.0.0")
        assert status == 404
        assert "error" in body and "message" in body

        # ENDPOINT_NOT_FOUND
        status, body = _get(
            f"{base}/v1/spec/fin/POST/nonexistent?version=1.0.0"
        )
        assert status == 404
        assert "error" in body and "message" in body

        # SERVICE_NOT_FOUND
        status, body = _get(f"{base}/v1/spec/auth?version=1.0.0")
        assert status == 404
        assert "error" in body and "message" in body

        # INVALID_VERSION_FORMAT
        status, body = _get(f"{base}/v1/spec/fin?version=1.x")
        assert status == 400
        assert "error" in body and "message" in body

    def test_e2e_error_codes_are_stable(self, base: str) -> None:
        """业务需求:错误码字符串是稳定的协议契约(SDK 可枚举)。

        PR-2.1 §2.4 枚举:VERSION_NOT_FOUND / SERVICE_NOT_FOUND /
        ENDPOINT_NOT_FOUND / INVALID_VERSION_FORMAT。
        """
        status, body = _get(f"{base}/v1/manifest/99.0.0")
        assert body["error"] == "VERSION_NOT_FOUND"

        status, body = _get(f"{base}/v1/spec/auth?version=1.0.0")
        assert body["error"] == "SERVICE_NOT_FOUND"

        status, body = _get(
            f"{base}/v1/spec/fin/POST/nonexistent?version=1.0.0"
        )
        assert body["error"] == "ENDPOINT_NOT_FOUND"

        status, body = _get(f"{base}/v1/spec/fin?version=1.x")
        assert body["error"] == "INVALID_VERSION_FORMAT"


# ════════════════════════════════════════════════════════════════════════════
# E2E — 服务端可独立运行 + 多端点协同
# ════════════════════════════════════════════════════════════════════════════


class TestE2EServerStandalone:
    def test_e2e_server_starts_and_responds_healthz(self, base: str) -> None:
        """业务需求:服务进程起后,健康检查即返回(无需任何业务数据)。"""
        status, body = _get(f"{base}/healthz")
        assert status == 200
        assert body["status"] == "ok"

    def test_e2e_multi_endpoint_consistency(self, base: str) -> None:
        """业务需求:同一 (method, path) 在 spec 端点 vs manifest 端点都存在。

        即 /v1/manifest 的 fin services[0] 与 /v1/spec/fin 的 specs 是同一组端点。
        """
        # manifest 拉 fin 的所有 spec 摘要
        _, manifest_body = _get(f"{base}/v1/manifest")
        manifest_paths = sorted(
            (s["method"], s["path"])
            for s in manifest_body["services"]["fin"]
        )

        # spec/fin 拉所有 spec 摘要
        _, spec_body = _get(f"{base}/v1/spec/fin?version=1.0.0")
        spec_paths = sorted(
            (s["method"], s["path"]) for s in spec_body["specs"]
        )

        assert manifest_paths == spec_paths
        assert len(manifest_paths) == 31  # 31 个 fin 端点

    def test_e2e_manifest_pinned_same_as_default(self, base: str) -> None:
        """业务需求:GET /v1/manifest 与 GET /v1/manifest/1.0.0 字节级相等
        (本 PR 单版本,default == pinned)。
        """
        # 注意:比较字典 — 两端 checksum 必须一致(代表 byte-equal)
        _, default = _get(f"{base}/v1/manifest")
        _, pinned = _get(f"{base}/v1/manifest/1.0.0")
        assert default["checksum"] == pinned["checksum"]
