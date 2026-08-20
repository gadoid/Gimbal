"""Real-path tests for run_dispatcher._resolve_exec_auths.

Every run test previously monkeypatched this function away, so the
actual Fernet round-trip — including the "plaintext never lands on the
ORM row" guarantee introduced with ResolvedAuth — was untested.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import AuthSession, User
from app.services import run_dispatcher


async def _seed_owner(factory, alias: str, username: str, password: str) -> int:
    """Create a fresh user + encrypted auth session; return the user id.

    Callers pass the returned id through — never assume autoincrement
    starting at 1 (fixture changes like a bootstrap admin would silently
    break such an assumption).
    """
    async with factory() as db:
        user = User(
            username=f"u_{alias}",
            display_name=f"u_{alias}",
            password_hash="x",  # not exercised here
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        db.add(AuthSession(
            owner_id=user.id,
            alias=alias,
            url="https://svc.internal",
            username_enc=fernet_encrypt(username),
            password_enc=fernet_encrypt(password),
        ))
        await db.commit()
        return user.id


async def test_resolve_exec_auths_happy_path_and_orm_purity(fresh_db) -> None:
    """Resolved values decrypt correctly AND the ORM rows keep only
    ciphertext — the whole point of the ResolvedAuth refactor."""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")

    resolved = await run_dispatcher._resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"]
    )
    assert len(resolved) == 1
    r = resolved[0]
    assert isinstance(r, run_dispatcher.ResolvedAuth)
    assert (r.alias, r.username, r.password) == ("svc", "alice", "s3cret")
    assert r.url == "https://svc.internal"

    # The ORM row must not have gained plaintext attributes.
    async with factory() as db:
        row = (
            await db.execute(select(AuthSession))
        ).scalar_one()
        assert "username" not in row.__dict__ and "password" not in row.__dict__
        assert row.username_enc != "alice"
        assert row.password_enc != "s3cret"


async def test_resolve_exec_auths_decrypt_failure_fails_fast(fresh_db) -> None:
    """Bad ciphertext → _AuthResolveError (V1 strict semantics), not a
    silent empty-credential run."""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "good", "alice", "s3cret")
    async with factory() as db:
        db.add(AuthSession(
            owner_id=owner_id,
            alias="rotten",
            url="https://x",
            username_enc="gitleaks:not-a-fernet-token",
            password_enc=fernet_encrypt("p"),
        ))
        await db.commit()

    with pytest.raises(run_dispatcher._AuthResolveError, match="rotten"):
        await run_dispatcher._resolve_exec_auths(
            factory, owner_id=owner_id, aliases=["good", "rotten"]
        )


async def test_resolve_exec_auths_missing_alias_warns_and_continues(fresh_db) -> None:
    """An alias the owner doesn't have resolves to nothing (warning),
    the run continues — V1 semantics: missing alias is a step-level
    error at ${auth.*} resolution, not a dispatch failure."""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")

    resolved = await run_dispatcher._resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc", "ghost"]
    )
    assert [r.alias for r in resolved] == ["svc"]
