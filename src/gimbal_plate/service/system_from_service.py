"""Resolve system id from a fully-qualified service name (API Surface B3)."""

from __future__ import annotations

from typing import Any


def system_from_service(services: list[str]) -> dict[str, Any]:
    """Map each ``"<system>.<service>"`` string to its system prefix."""
    resolved: list[dict[str, str]] = []
    for svc in services:
        if not isinstance(svc, str) or not svc:
            system_id = ""
        elif "." in svc:
            system_id = svc.split(".", 1)[0]
        else:
            # No dot means the convention cannot disambiguate; emit empty
            # system id and let the caller decide what to do.
            system_id = ""
        resolved.append({"service": svc, "system": system_id})
    return {"systems": resolved}


__all__ = ["system_from_service"]
