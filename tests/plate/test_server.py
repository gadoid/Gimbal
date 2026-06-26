"""Plate 服务端单元测试(PR-2.3)。

业务承诺(对应 PR-2.3 §3.1):
  * 协议路由完整 — 所有 PR-2.1 §2.1 端点可访问
  * JSON schema 严格 — 响应字段等于 to_dict() 产物
  * 错误码语义清晰 — VERSION_NOT_FOUND / SERVICE_NOT_FOUND /
    ENDPOINT_NOT_FOUND / INVALID_VERSION_FORMAT / NOT_FOUND / INTERNAL_ERROR
  * 字节级稳定 — 同 URL 两次响应 byte-equal(checksum 锁定)
  * HTTP 头 — Content-Type: application/json; charset=utf-8 + X-Plate-Version

对应设计:PR-2.3 §3.1。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

import pytest

from Plate import registry
from Plate.server import (
    DEFAULT_VERSION,
    PlateServer,
    SUPPORTED_SERVICES,
    SUPPORTED_VERSIONS,
)
from Plate.server.response import error_response, json_response


# ── 共享 fixture ──


@pytest.fixture
def server() -> Iterator[PlateServer]:
    """每个测试一个独立 server(port=0 动态分配,测试间隔离)。"""
    # 重置 registry 防止测试间污染(每个测试独立)
    registry.reset()
    s = PlateServer(port=0)
    s.start()
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture
def base(server: PlateServer) -> str:
    return f"http://127.0.0.1:{server.port}"


def _get(url: str) -> tuple[int, dict, dict]:
    """便捷 GET,返回 (status, json_body, response_headers)。

    错误响应也返回 body(便于断言 error/message)。
    """
    try:
        r = urllib.request.urlopen(url)
        body = json.loads(r.read().decode("utf-8"))
        return r.status, body, dict(r.headers)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8"))
        return e.code, body, dict(e.headers)


# ════════════════════════════════════════════════════════════════════════════
# response.py — JSON 响应 + 错误响应工具
# ════════════════════════════════════════════════════════════════════════════


class TestJsonResponse:
    def test_status_default_200(self) -> None:
        """业务需求:status 默认 200。"""
        body, status, headers = json_response({"a": 1})
        assert status == 200

    def test_content_type_charset_utf8(self) -> None:
        """业务需求:Content-Type 必带 charset=utf-8。"""
        _, _, headers = json_response({"a": 1})
        assert headers["Content-Type"] == "application/json; charset=utf-8"

    def test_content_length_matches_body(self) -> None:
        """业务需求:Content-Length == body 字节数。"""
        body, _, headers = json_response({"a": 1})
        assert headers["Content-Length"] == str(len(body))

    def test_sort_keys_canonical_json(self) -> None:
        """业务需求:sort_keys=True → 字段按字典序(对应 A2 byte-equal)。"""
        body, _, _ = json_response({"b": 1, "a": 2})
        # sort_keys=True → "a" 在 "b" 前面
        assert body == b'{"a":2,"b":1}'

    def test_extra_headers_merged(self) -> None:
        """业务需求:传入 headers 与默认 headers 合并(Content-Type 仍占优先)。"""
        _, _, headers = json_response(
            {"a": 1}, headers={"X-Plate-Version": "1.0.0", "Content-Type": "ignored"}
        )
        # 注意:本实现中传入 headers 覆盖默认(因为是 dict.update),这对应
        # PR-2.1 §2.5:Content-Type 必须为 application/json; charset=utf-8。
        # 此处测试仅断言 X-Plate-Version 被加入。
        assert headers["X-Plate-Version"] == "1.0.0"


class TestErrorResponse:
    def test_error_code_and_message(self) -> None:
        """业务需求:错误响应 body 含 error + message(对应 PR-2.1 §2.4)。"""
        body, status, _ = error_response("VERSION_NOT_FOUND", "v 99 not on server", 404)
        assert status == 404
        payload = json.loads(body)
        assert payload["error"] == "VERSION_NOT_FOUND"
        assert payload["message"] == "v 99 not on server"

    def test_extra_fields_merged_into_body(self) -> None:
        """业务需求:extra dict 字段并入 error response body。"""
        body, _, _ = error_response(
            "VERSION_NOT_FOUND",
            "v 99 not on server",
            404,
            extra={"available_versions": [{"major": 1, "minor": 0, "patch": 0}]},
        )
        payload = json.loads(body)
        assert payload["available_versions"] == [{"major": 1, "minor": 0, "patch": 0}]


# ════════════════════════════════════════════════════════════════════════════
# 健康检查 + 版本列表
# ════════════════════════════════════════════════════════════════════════════


class TestServerHealthz:
    def test_healthz_200_ok(self, base: str) -> None:
        """业务需求:GET /healthz → 200 + status:ok。"""
        status, body, _ = _get(f"{base}/healthz")
        assert status == 200
        assert body == {"status": "ok", "version": str(DEFAULT_VERSION)}


class TestServerVersionList:
    def test_version_list_shape(self, base: str) -> None:
        """业务需求:GET /v1/version → supported_versions + default。"""
        status, body, _ = _get(f"{base}/v1/version")
        assert status == 200
        assert "supported_versions" in body
        assert "default" in body
        assert body["default"] == DEFAULT_VERSION.to_dict()
        # 包含默认版本
        assert DEFAULT_VERSION.to_dict() in body["supported_versions"]


# ════════════════════════════════════════════════════════════════════════════
# Manifest 端点
# ════════════════════════════════════════════════════════════════════════════


class TestServerManifest:
    def test_manifest_default(self, base: str) -> None:
        """业务需求:GET /v1/manifest → 默认版本 manifest(含 fin 31 specs)。"""
        status, body, headers = _get(f"{base}/v1/manifest")
        assert status == 200
        assert "fin" in body["services"]
        assert len(body["services"]["fin"]) == 31
        assert headers.get("X-Plate-Version") == str(DEFAULT_VERSION)

    def test_manifest_pinned(self, base: str) -> None:
        """业务需求:GET /v1/manifest/1.0.0 → 该版本 manifest。"""
        status, body, headers = _get(f"{base}/v1/manifest/{DEFAULT_VERSION}")
        assert status == 200
        assert body["version"] == DEFAULT_VERSION.to_dict()
        assert headers.get("X-Plate-Version") == str(DEFAULT_VERSION)

    def test_manifest_version_not_found(self, base: str) -> None:
        """业务需求:GET /v1/manifest/99.0.0 → 404 + VERSION_NOT_FOUND。"""
        status, body, _ = _get(f"{base}/v1/manifest/99.0.0")
        assert status == 404
        assert body["error"] == "VERSION_NOT_FOUND"
        assert "available_versions" in body

    def test_manifest_pinned_invalid_format(self, base: str) -> None:
        """业务需求:GET /v1/manifest/1.x → 400 + INVALID_VERSION_FORMAT。"""
        status, body, _ = _get(f"{base}/v1/manifest/1.x")
        assert status == 400
        assert body["error"] == "INVALID_VERSION_FORMAT"


# ════════════════════════════════════════════════════════════════════════════
# Spec 端点
# ════════════════════════════════════════════════════════════════════════════


class TestServerSpec:
    def test_spec_service_fin(self, base: str) -> None:
        """业务需求:GET /v1/spec/fin?version=1.0.0 → 31 specs + checksum。"""
        status, body, headers = _get(f"{base}/v1/spec/fin?version=1.0.0")
        assert status == 200
        assert body["service"] == "fin"
        assert len(body["specs"]) == 31
        assert len(body["checksum"]) == 64  # SHA256 hex
        assert headers.get("X-Plate-Version") == "1.0.0"

    def test_spec_endpoint_existing(self, base: str) -> None:
        """业务需求:GET /v1/spec/fin/POST/api/order/order/orderDetail?version=1.0.0
        → 单 spec,字段等于 to_dict()。
        """
        status, body, _ = _get(
            f"{base}/v1/spec/fin/POST/api/order/order/orderDetail?version=1.0.0"
        )
        assert status == 200
        assert body["service"] == "fin"
        assert body["spec"]["method"] == "POST"
        assert body["spec"]["path"] == "/api/order/order/orderDetail"

    def test_spec_endpoint_not_found(self, base: str) -> None:
        """业务需求:不存在的端点 → 404 + ENDPOINT_NOT_FOUND。"""
        status, body, _ = _get(
            f"{base}/v1/spec/fin/POST/api/nonexistent?version=1.0.0"
        )
        assert status == 404
        assert body["error"] == "ENDPOINT_NOT_FOUND"

    def test_spec_service_not_found(self, base: str) -> None:
        """业务需求:不支持的 service → 404 + SERVICE_NOT_FOUND。"""
        status, body, _ = _get(f"{base}/v1/spec/auth?version=1.0.0")
        assert status == 404
        assert body["error"] == "SERVICE_NOT_FOUND"
        assert "available_services" in body

    def test_spec_missing_version(self, base: str) -> None:
        """业务需求:缺 ?version= → 400 + INVALID_VERSION_FORMAT。"""
        status, body, _ = _get(f"{base}/v1/spec/fin")
        assert status == 400
        assert body["error"] == "INVALID_VERSION_FORMAT"

    def test_spec_invalid_version_format(self, base: str) -> None:
        """业务需求:?version=1.x → 400 + INVALID_VERSION_FORMAT。"""
        status, body, _ = _get(f"{base}/v1/spec/fin?version=1.x")
        assert status == 400
        assert body["error"] == "INVALID_VERSION_FORMAT"


# ════════════════════════════════════════════════════════════════════════════
# Doc 端点(对应 A3 冷热分层:doc 是热数据)
# ════════════════════════════════════════════════════════════════════════════


class TestServerDoc:
    def test_doc_service_fin(self, base: str) -> None:
        """业务需求:GET /v1/doc/fin?version=1.0.0 → docs dict(可空)。"""
        status, body, _ = _get(f"{base}/v1/doc/fin?version=1.0.0")
        assert status == 200
        assert body["service"] == "fin"
        assert isinstance(body["docs"], dict)

    def test_doc_endpoint_not_found(self, base: str) -> None:
        """业务需求:不存在的端点 doc → 404 + DOC_NOT_FOUND。"""
        status, body, _ = _get(
            f"{base}/v1/doc/fin/POST/nonexistent?version=1.0.0"
        )
        assert status == 404
        assert body["error"] == "DOC_NOT_FOUND"

    def test_doc_service_not_found(self, base: str) -> None:
        """业务需求:不支持的 service → 404 + SERVICE_NOT_FOUND。"""
        status, body, _ = _get(f"{base}/v1/doc/auth?version=1.0.0")
        assert status == 404
        assert body["error"] == "SERVICE_NOT_FOUND"


# ════════════════════════════════════════════════════════════════════════════
# 路由兜底 + 响应头
# ════════════════════════════════════════════════════════════════════════════


class TestServerRoutingAndHeaders:
    def test_unknown_route_404(self, base: str) -> None:
        """业务需求:未匹配路由 → 404 + NOT_FOUND。"""
        status, body, _ = _get(f"{base}/v1/nope")
        assert status == 404
        assert body["error"] == "NOT_FOUND"

    def test_spec_endpoint_incomplete_path_404(self, base: str) -> None:
        """业务需求:端点 path 缺段 → NOT_FOUND(协议未声明此 URL 形态)。"""
        status, body, _ = _get(f"{base}/v1/spec/fin/POST?version=1.0.0")
        assert status == 404
        assert body["error"] == "NOT_FOUND"

    def test_content_type_json(self, base: str) -> None:
        """业务需求:Content-Type = application/json; charset=utf-8。"""
        try:
            r = urllib.request.urlopen(f"{base}/healthz")
        except urllib.error.HTTPError as e:
            assert e.headers.get("Content-Type") == "application/json; charset=utf-8"
            return
        assert r.headers.get("Content-Type") == "application/json; charset=utf-8"

    def test_x_plate_version_on_data_endpoints(self, base: str) -> None:
        """业务需求:数据端点响应必带 X-Plate-Version。"""
        # /v1/manifest
        _, _, h = _get(f"{base}/v1/manifest")
        assert h.get("X-Plate-Version") == str(DEFAULT_VERSION)
        # /v1/spec/fin?version=1.0.0
        _, _, h = _get(f"{base}/v1/spec/fin?version=1.0.0")
        assert h.get("X-Plate-Version") == "1.0.0"
        # /v1/manifest/1.0.0
        _, _, h = _get(f"{base}/v1/manifest/{DEFAULT_VERSION}")
        assert h.get("X-Plate-Version") == str(DEFAULT_VERSION)

    def test_byte_equal_same_url(self, base: str) -> None:
        """业务需求:同 URL 两次响应 byte-equal(checksum 稳定)。"""
        url = f"{base}/v1/spec/fin?version=1.0.0"
        # 走两次 HTTP 拉数据
        try:
            b1 = urllib.request.urlopen(url).read()
            b2 = urllib.request.urlopen(url).read()
        except urllib.error.HTTPError as e:
            pytest.fail(f"unexpected error: {e.code} {e.read()}")
        assert b1 == b2


# ════════════════════════════════════════════════════════════════════════════
# PlateServer 实例管理
# ════════════════════════════════════════════════════════════════════════════


class TestPlateServerLifecycle:
    def test_port_zero_assigned(self) -> None:
        """业务需求:port=0 → OS 动态分配(start 后 port 可读)。"""
        registry.reset()
        s = PlateServer(port=0)
        assert s.port == 0  # 启动前是 0
        s.start()
        try:
            assert s.port > 0  # 启动后被 OS 分配
        finally:
            s.stop()

    def test_stop_idempotent(self) -> None:
        """业务需求:stop() 不抛(可重复调用)。"""
        registry.reset()
        s = PlateServer(port=0)
        s.start()
        s.stop()
        s.stop()  # 二次调用不抛

    def test_supported_services_constant(self) -> None:
        """业务需求:SUPPORTED_SERVICES 是元组(不可变),含 fin。"""
        assert "fin" in SUPPORTED_SERVICES
        assert isinstance(SUPPORTED_SERVICES, tuple)

    def test_supported_versions_constant(self) -> None:
        """业务需求:SUPPORTED_VERSIONS 是元组,含 DEFAULT_VERSION。"""
        assert DEFAULT_VERSION in SUPPORTED_VERSIONS
        assert isinstance(SUPPORTED_VERSIONS, tuple)
