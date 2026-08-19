"""Shared store-error → HTTPException mapping for the V3 composer routers.

The composer stores raise either:

* ``KeyError("xxx_not_found: <id>")`` — miss on a row → 404 with the
  message part after ``": "`` (the store prefix is internal)
* ``ValueError("<code>: <message>")`` — business-rule violation whose
  status depends on the leading ``<code>`` (each call-site declares its
  own code→status table; unknown codes default to 400)

Both shapes were previously copy-pasted at 9+4 call-sites; adding a new
error code meant remembering to update every hand-written if-chain.
"""
from __future__ import annotations

from fastapi import HTTPException


def key_error_404(e: KeyError) -> HTTPException:
    """``KeyError("code: message")`` → 404 with the message part."""
    return HTTPException(status_code=404, detail=str(e).split(": ", 1)[-1])


def value_error_http(
    e: ValueError, codes: dict[str, int], default: int = 400
) -> HTTPException:
    """``ValueError("code: message")`` → HTTPException per the code table.

    ``codes`` maps the leading error code to a status; anything else
    falls back to ``default`` (400).
    """
    msg = str(e)
    code = msg.split(":", 1)[0]
    return HTTPException(status_code=codes.get(code, default), detail=msg)
