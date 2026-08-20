"""Named business-error codes for the auth/users routers.

These ints are an API contract (tests assert them; clients may branch on
them) — the constants exist so the *definition* lives in one place
instead of being re-typed at each raise-site.  Do not renumber.

Shape convention for these two routers: ``detail={"code": <int>, "msg": <str>}``.
"""
from __future__ import annotations

# auth.py
NAME_TAKEN_ON_REGISTER = 4003   # username/display_name already exists
BAD_CREDENTIALS = 4004          # login: wrong username or password
ACCOUNT_DISABLED = 4005         # login: is_active=False

# users.py
ADMIN_REQUIRED = 4031           # non-admin called an admin-only endpoint
MEMBER_PATCH_FORBIDDEN = 4032   # member patching someone else / is_admin flag
RESET_OTHER_PASSWORD = 4033     # member resetting another user's password
USER_NOT_FOUND = 4041
SELF_DELETE = 4091              # DELETE self
LAST_ADMIN = 4092               # demote/delete the final admin
NAME_TAKEN = 4093               # username/display_name already exists


def code_detail(code: int, msg: str) -> dict:
    """Uniform ``detail`` payload for the auth/users error responses."""
    return {"code": code, "msg": msg}
