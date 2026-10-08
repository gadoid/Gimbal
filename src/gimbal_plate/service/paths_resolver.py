"""Resolve JSONPath candidates from a response body sample (API Surface B1)."""

from __future__ import annotations

from typing import Any

# Traversal limit: refuse samples whose serialized depth exceeds this. The cap
# protects the resolver from malicious or malformed samples that would otherwise
# blow the recursion stack.
_MAX_DEPTH = 32
# Hard cap on number of generated candidates. Protects downstream consumers.
_MAX_PATHS = 2000


def _walk(
    data: Any,
    prefix: str,
    depth: int,
    out: list[dict[str, Any]],
) -> None:
    if len(out) >= _MAX_PATHS or depth > _MAX_DEPTH:
        return
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{prefix}['{key}']" if prefix == "$" else f"{prefix}['{key}']"
            # Normalise the first segment to the $.key form for consistency.
            if prefix == "$":
                child = f"$.{key}"
            out.append({"path": child, "depth": depth, "extracted_by_default": False})
            _walk(value, child, depth + 1, out)
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            child = f"{prefix}[{idx}]"
            out.append({"path": child, "depth": depth, "extracted_by_default": False})
            _walk(value, child, depth + 1, out)
    # scalars terminate the walk


def resolve_paths(
    sample: Any, *, path_prefix: str | None = None
) -> list[dict[str, Any]]:
    """Return all candidate JSONPaths reachable from ``sample``."""
    if not isinstance(sample, (dict, list)):
        return []

    base = path_prefix or "$"
    out: list[dict[str, Any]] = []
    if base == "$":
        # The first element when given a dict should enumerate its own keys at
        # depth 1, matching the A4 documentation sample.
        if isinstance(sample, dict):
            for key, value in sample.items():
                child = f"$.{key}"
                out.append(
                    {"path": child, "depth": 1, "extracted_by_default": False}
                )
                _walk(value, child, 2, out)
        else:
            for idx, value in enumerate(sample):
                child = f"$.[{idx}]" if False else f"$[{idx}]"
                out.append(
                    {"path": child, "depth": 1, "extracted_by_default": False}
                )
                _walk(value, child, 2, out)
    else:
        # When a prefix is provided we still treat the sample as the children of
        # that prefix. We emit the prefix itself first.
        out.append({"path": base, "depth": 0, "extracted_by_default": False})
        if isinstance(sample, dict):
            for key, value in sample.items():
                child = f"{base}['{key}']"
                out.append(
                    {"path": child, "depth": 1, "extracted_by_default": False}
                )
                _walk(value, child, 2, out)
        else:
            for idx, value in enumerate(sample):
                child = f"{base}[{idx}]"
                out.append(
                    {"path": child, "depth": 1, "extracted_by_default": False}
                )
                _walk(value, child, 2, out)
    return out


__all__ = ["resolve_paths"]
