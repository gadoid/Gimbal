"""Case endpoints: mine / public / get / favorite / copy.

Spec-1 simplifications (intentional):
* ``cases`` table is NOT written by the auth/users/cases routers in spec-1, so
  private-case scanning for ``/mine`` is empty.  ``/mine`` therefore returns
  the user's *favorited public* cases.
* favorites are persisted to ``data/favorites.json`` (instead of in-memory
  or in a DB table) so they survive ``uvicorn --reload`` restarts.  The
  case-id key is the on-disk scenarioId string (not an integer ``cases.id``,
  since the ``cases`` table itself is never written).
* ``/copy`` writes a YAML clone to disk and returns ``{case_id, path}``.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, File as FastAPIFile, Form, HTTPException, Path as PathParam, Response, UploadFile, status
from loguru import logger
from pydantic import BaseModel

from ..core.config import settings
from ..core.deps import CurrentUser
from ..schemas.case import CaseDetailOut, CaseListOut, CaseShowOut, CaseSummaryOut
from ..services.case_loader import CaseSummary, loader
from ..services.executor import _SHOW_TIMEOUT_SEC, _run_gimbal_capture
from ..services.marks_store import favorites

router = APIRouter(prefix="/cases", tags=["cases"])


def _summary_out(s: CaseSummary, *, favorited: bool = False, copied: bool = False) -> CaseSummaryOut:
    # Use model_validate + from_attributes so adding a new CaseSummary field
    # is automatically picked up here (no manual mapping drift).
    payload = CaseSummaryOut.model_validate(s, from_attributes=True).model_dump()
    payload.update(
        file_path=str(s.file_path),
        updated_at=datetime.fromtimestamp(s.updated_at).isoformat(),
        tags=list(s.tags),
        favorited_by_me=favorited,
        copied_by_me=copied,
    )
    return CaseSummaryOut(**payload)


# ── helpers ────────────────────────────────────────────────────────────
def _find_summary(case_id: str) -> CaseSummary | None:
    """Find a case summary across public + private visibilities."""
    for s in loader.scan(owner_id=None):
        if s.case_id == case_id:
            return s
    # scan(owner_id=None) only returns public; private copies live in cache.
    entry = loader._cache.get(case_id)
    return entry.summary if entry else None


def _require_modify_access(user: CurrentUser, summary: CaseSummary) -> None:
    """Single source of truth for "can this user mutate this case?".

    - private cases: only the owner
    - public cases:  only an admin

    Raises ``HTTPException(403)`` on denial; returns None on success.
    """
    if summary.visibility == "private" and summary.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only owner can modify private case",
        )
    if summary.visibility == "public" and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin only can modify public case",
        )


def _write_case_file(path: Path, payload: dict, ext: str) -> None:
    """Serialize ``payload`` to ``path`` as JSON or YAML per ``ext``.

    Caller owns path creation (``mkdir`` etc.).  Errors propagate — the
    router decides whether to swallow + log (best-effort patches) or
    surface as 500.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".json":
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


def _rewrite_scenario_id(path: Path, new_id: str, ext: str) -> None:
    """Patch the file's ``scenarioId`` field so it matches its filename stem.

    The loader uses scenarioId as the cache key (case_id), so the in-file
    field must agree with the on-disk stem or a same-scenarioId shadow
    occurs.  Best-effort: parse errors are logged and swallowed by the
    caller so a single corrupt file never blocks the operation.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw) if ext == ".json" else yaml.safe_load(raw)
        if not isinstance(parsed, dict):
            return
        parsed["scenarioId"] = new_id
        _write_case_file(path, parsed, ext)
    except Exception as e:  # noqa: BLE001  best-effort patch
        logger.warning(
            "rewrite_scenario_id failed for {} → {}: {}", path, new_id, e
        )


def _next_copy_name(user_dir: Path, stem: str, ext: str) -> Path:
    """Pick the smallest N >= 1 such that ``<stem>-copy-<N><ext>`` does not exist."""
    n = 1
    while True:
        candidate = user_dir / f"{stem}-copy-{n}{ext}"
        if not candidate.exists():
            return candidate
        n += 1


# Default scenarioId prefix for "无 scenarioId" / "空 scenarioId" uploads.
# Each user gets their own counter so scenario-1 doesn't collide between
# users; the counter scans existing files in that user's dir.
_DEFAULT_SCENARIO_PREFIX = "scenario"
_DEFAULT_SCENARIO_RE = re.compile(
    rf"^{re.escape(_DEFAULT_SCENARIO_PREFIX)}-(\d+)$"
)


def _next_default_scenario_id(user_dir: Path) -> str:
    """Return the smallest unused ``scenario-N`` for ``user_dir``.

    Scans both file stems and the on-disk scenarios whose ``scenarioId``
    field follows the pattern (so renames to/from scenario-N stay unique).
    """
    used: set[int] = set()
    if user_dir.exists():
        for p in user_dir.iterdir():
            if not p.is_file():
                continue
            m = _DEFAULT_SCENARIO_RE.match(p.stem)
            if m:
                try:
                    used.add(int(m.group(1)))
                except ValueError:
                    pass
            # Also peek inside the file — a stem may have been renamed
            # (e.g. via the rename endpoint) away from scenario-N while
            # the inner scenarioId still claims that number.
            try:
                if p.suffix.lower() == ".json":
                    inner = json.loads(p.read_text(encoding="utf-8") or "{}")
                else:
                    inner = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:  # noqa: BLE001
                continue
            sid = inner.get("scenarioId") if isinstance(inner, dict) else None
            if isinstance(sid, str):
                m2 = _DEFAULT_SCENARIO_RE.match(sid)
                if m2:
                    try:
                        used.add(int(m2.group(1)))
                    except ValueError:
                        pass
    n = 1
    while n in used:
        n += 1
    return f"{_DEFAULT_SCENARIO_PREFIX}-{n}"


def _user_has_copy_of(user_dir: Path, case_id: str) -> bool:
    """True if ``user_dir`` contains any private copy derived from ``case_id``.

    A "copy" is any file whose stem is ``<case_id>`` (unchanged), or
    begins with ``<case_id>-`` / ``<case_id>__`` followed by a separator.
    Covers the original ``<stem>-copy-N`` pattern as well as the
    user-supplied ``<stem>__rename`` pattern introduced by the
    RenameInputDialog (Spec-2 §4.3 C5).
    """
    if not user_dir.exists():
        return False
    prefix = f"{case_id}-"
    dunder = f"{case_id}__"
    for p in user_dir.iterdir():
        if not p.is_file():
            continue
        stem = p.stem
        if stem == case_id or stem.startswith(prefix) or stem.startswith(dunder):
            return True
    return False


# ── GET /mine ─────────────────────────────────────────────────────────
@router.get("/mine", response_model=CaseListOut)
async def list_mine(user: CurrentUser) -> CaseListOut:
    """Cases visible to ``user`` (Spec-2 fix: include user's private copies).

    Returns:
    - user's private cases (uploaded + copied, owned by ``user.id``)
    - PLUS the user's favorited public cases
    Each item is marked ``favorited_by_me=True`` if it's in the favorites set.
    """
    fav_ids = favorites.list_for_user(user.id)
    summaries = loader.scan(owner_id=user.id)  # public + private (owned)
    items = [
        _summary_out(s, favorited=s.case_id in fav_ids, copied=False)
        for s in summaries
    ]
    return CaseListOut(items=items, total=len(items))


# ── GET /public ───────────────────────────────────────────────────────
@router.get("/public", response_model=CaseListOut)
async def list_public(user: CurrentUser) -> CaseListOut:
    """All public cases, each flagged with ``favorited_by_me``/``copied_by_me``.

    ``copied_by_me`` covers both ``-copy-N`` and the user-renamed
    ``__suffix`` pattern (see ``_user_has_copy_of``).
    """
    fav_ids = favorites.list_for_user(user.id)
    summaries = loader.scan(owner_id=None)
    user_dir = settings.USERS_CASES_DIR / str(user.id)

    items: list[CaseSummaryOut] = []
    for s in summaries:
        copied = _user_has_copy_of(user_dir, s.case_id)
        items.append(
            _summary_out(
                s,
                favorited=s.case_id in fav_ids,
                copied=copied,
            )
        )
    return CaseListOut(items=items, total=len(items))


# ── GET /{case_id}/show ───────────────────────────────────────────────
# IMPORTANT: must be registered BEFORE the catch-all `/{case_id:path}`
# below — otherwise the `path` converter greedily captures the
# ``/show`` suffix and resolves to a non-existent case_id.
@router.get("/{case_id:path}/show", response_model=CaseShowOut)
async def get_case_show(
    user: CurrentUser,
    case_id: Annotated[str, PathParam(min_length=1)],
) -> CaseShowOut:
    """Return ``gimbal run show --from-path <yaml> --format=json`` output.

    Used by the frontend ExecutionDrawer step picker.  Auth policy mirrors
    ``GET /{case_id}``: owner-only for private cases, anyone authenticated
    for public cases; non-authorized callers get a 404 (intentional merge
    of 403/404 — see ``get_owned_execution`` in core/deps.py for the
    rationale on hiding existence).

    Implementation shells out to ``gimbal run show`` via
    :func:`_run_gimbal_capture` (no streaming, no LogHub, no disk log —
    this is a one-shot read-only call).  Errors are mapped to structured
    HTTP responses; non-zero exit codes become 502 with a stdout snippet
    so operators can diagnose without re-running gimbal themselves.
    """
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case not found: {case_id}",
        )
    # Mirror the access rule from get_case: private cases are owner-only,
    # public cases are open to any logged-in user.
    if summary.visibility == "private" and summary.owner_id != user.id:
        # Intentionally 404 (not 403) so we don't leak which case_ids
        # exist.  Matches the "existence-hiding" policy used elsewhere
        # in the platform.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case not found: {case_id}",
        )

    yaml_path = Path(summary.file_path)
    if not yaml_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"case file missing on disk: {yaml_path}",
        )

    cmd_args = [
        settings.GIMBAL_BIN,
        "run",
        "show",
        "--from-path",
        str(yaml_path),
        "--format=json",
    ]
    returncode, stdout = await _run_gimbal_capture(cmd_args, timeout=_SHOW_TIMEOUT_SEC)

    if returncode != 0:
        snippet = (stdout or "").strip()[:200]
        logger.warning(
            "gimbal run show failed for {} (exit={}): {}",
            case_id, returncode, snippet,
        )
        # Special-case the binary-not-found exit so the error message
        # is actionable for the operator.
        if returncode == 127:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="gimbal binary not on PATH on the server",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"gimbal run show failed (exit={returncode}): {snippet}",
        )
    if not stdout.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="gimbal run show returned no output",
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.warning("gimbal run show returned non-JSON for {}: {}", case_id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"gimbal run show returned invalid JSON: {e}",
        )

    # `gimbal run show` emits a JSON ARRAY (one entry per scenario in
    # the file).  Cases today always carry a single scenario, so take
    # [0]; a multi-scenario file would log a debug note.
    if not isinstance(payload, list) or not payload:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="gimbal run show returned empty/unexpected payload shape",
        )
    if len(payload) > 1:
        logger.debug(
            "case {} contains {} scenarios; showing the first",
            case_id, len(payload),
        )
    return CaseShowOut.model_validate(payload[0])


# ── GET /{case_id} ────────────────────────────────────────────────────
@router.get("/{case_id:path}", response_model=CaseDetailOut)
async def get_case(
    user: CurrentUser,
    case_id: Annotated[str, PathParam(min_length=1)],
) -> CaseDetailOut:
    """Full parsed payload + summary for a single case."""
    try:
        payload = loader.read(case_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case not found: {case_id}",
        )
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case not found: {case_id}",
        )
    # Same access rule as get_case_show: private cases are owner-only.
    # Intentionally 404 (not 403) so we don't leak which case_ids exist.
    if summary.visibility == "private" and summary.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case not found: {case_id}",
        )
    fav_ids = favorites.list_for_user(user.id)
    return CaseDetailOut(
        payload=payload,
        summary=_summary_out(summary, favorited=summary.case_id in fav_ids),
    )


# ── POST /{id}/favorite ───────────────────────────────────────────────
@router.post(
    "/{case_id:path}/favorite",
    status_code=status.HTTP_200_OK,
)
async def add_favorite(
    user: CurrentUser,
    case_id: Annotated[str, PathParam(min_length=1)],
) -> dict:
    """Mark ``case_id`` as favorited by ``user`` (persisted to favorites.json)."""
    if _find_summary(case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case not found: {case_id}",
        )
    favorites.set_mark(user.id, case_id, True)
    return {"case_id": case_id, "favorited": True}


# ── DELETE /{id}/favorite ─────────────────────────────────────────────
@router.delete(
    "/{case_id:path}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_favorite(
    user: CurrentUser,
    case_id: Annotated[str, PathParam(min_length=1)],
):
    """Unmark ``case_id`` as favorited by ``user`` (persisted to favorites.json)."""
    favorites.set_mark(user.id, case_id, False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── POST /{id}/copy ───────────────────────────────────────────────────
class CopyIn(BaseModel):
    new_name: str | None = None  # 可选 — 重命名副本


@router.post(
    "/{case_id:path}/copy",
    response_model=dict,
)
async def copy_case(
    user: CurrentUser,
    case_id: Annotated[str, PathParam(min_length=1)],
    payload: CopyIn = CopyIn(),
) -> dict:
    """Clone a public case's file into the user's private dir.

    Naming policy (Spec-2 §4.3 C5):
    * If ``new_name`` provided AND valid (matches ``stem`` of source_case_id,
      is a legal filename stem): use it as ``<user_dir>/<new_name><ext>``.
    * Else: fall back to ``<source_case_id>-copy-N.<ext>`` with the smallest
      unused ``N`` (collision-safe).
    """
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(
            status_code=404, detail=f"case not found: {case_id}"
        )
    if summary.visibility != "public":
        raise HTTPException(
            status_code=403, detail="only public cases can be copied"
        )

    user_dir = settings.USERS_CASES_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    ext = summary.file_path.suffix or ".yaml"

    new_name = (payload.new_name or "").strip() or None
    if new_name is not None:
        if _is_invalid_stem(new_name):
            raise HTTPException(
                status_code=422,
                detail="new_name 不能为空、超过 128 字符、或包含 / \\ : * ? \" < > |",
            )
        target = user_dir / f"{new_name}{ext}"
        # Refuse to silently collide — both the user's own dir AND the
        # public dir (because the loader treats a same-scenarioId public
        # case as canonical, which would shadow this fresh private copy).
        public_target = Path(settings.PUBLIC_CASES_DIR) / f"{new_name}{ext}"
        if target.exists() or public_target.exists():
            target = _next_copy_name(user_dir, new_name, ext)
    else:
        target = _next_copy_name(user_dir, summary.case_id, ext)

    shutil.copy2(summary.file_path, target)
    new_case_id = target.stem

    # Patch the cloned file's scenarioId so the loader's case_id derivation
    # matches the filename (otherwise the cache key collides with the source).
    _rewrite_scenario_id(target, new_case_id, ext)

    loader.invalidate()
    return {"case_id": new_case_id, "path": str(target)}


def _is_invalid_stem(stem: str) -> bool:
    """Return True if ``stem`` isn't a usable case_id stem.

    Allowed: any character EXCEPT path separators / control chars / dots.
    (Chinese case_ids like ``e2e订单到应收核销`` pass; spaces, parens,
    emoji, accented Latin etc. also pass.)

    Disallowed: empty, >128 chars, ``.``, ``..``, ``/\\:*?"<>|`` or NUL.
    """
    if not stem or len(stem) > 128:
        return True
    if stem in (".", ".."):
        return True
    for c in stem:
        if c == "\x00":
            return True
        if c in '/\\:*?"<>|':
            return True
    return False


# ── upload (Spec-2 §4.2 B3) ─────────────────────────────────────
@router.post("/upload", response_model=CaseSummaryOut, status_code=status.HTTP_201_CREATED)
async def upload_case(
    user: CurrentUser,
    file: UploadFile = FastAPIFile(...),
    visibility: str = Form("private"),
) -> CaseSummaryOut:
    """Upload a YAML/JSON case file; validate via CaseLoader; persist.

    ``visibility`` controls where the file lands:
    * ``"private"`` (default) → ``data/users/<user_id>/`` (workbench upload)
    * ``"public"``            → ``data/public/`` (「提交公共用例」)

    Any logged-in user may submit either; public submissions still come
    back with ``audited=True`` because the loader derives the public
    flag from the directory and that flag is informational only (admin
    audit is a future spec).
    """
    if visibility not in ("public", "private"):
        raise HTTPException(status_code=422, detail="visibility must be public or private")
    # NOTE (policy, intentionally open): member submissions to the public
    # library are a designed feature (the "+ 提交公共用例" button in
    # CasesPublic is offered to every member).  The scenarioId-stem
    # validation below is the security boundary here — no path traversal
    # and no shadow-overwrite (collisions get a ``-pub-N`` suffix).
    # Moving public uploads behind an admin audit queue is tracked as a
    # policy item in DEFERRED.md.

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty file")

    try:
        if (file.filename or "").lower().endswith(".json"):
            payload = json.loads(raw.decode("utf-8"))
        else:
            payload = yaml.safe_load(raw.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"parse failed: {e}")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="top-level must be an object")

    # Pick the destination dir + the "-<tag>-N" suffix style.
    if visibility == "public":
        target_dir = Path(settings.PUBLIC_CASES_DIR)
        suffix_tag = "pub"
    else:
        target_dir = settings.USERS_CASES_DIR / str(user.id)
        suffix_tag = "upload"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine the final case_id.  Three sources in priority order:
    #   1. A non-empty ``scenarioId`` field in the file → use as-is
    #      (subject to the collision suffix below).
    #   2. Missing/empty ``scenarioId`` in a private upload → generate the
    #      next free "scenario-N" for this user (see
    #      ``_next_default_scenario_id``).  This gives uploaded cases a
    #      clean, predictable default name instead of leaking things like
    #      ``e2e订单到应收核销-pub-3`` into the workbench.
    #   3. Missing/empty in a public upload → still required (admin wants
    #      explicit naming for the public library).
    raw_sid = payload.get("scenarioId")
    sid_str = raw_sid.strip() if isinstance(raw_sid, str) else raw_sid
    if isinstance(sid_str, str) and sid_str:
        # Path-traversal fix: the scenarioId becomes the on-disk filename
        # stem, so it must pass the same stem validation as /rename and
        # /copy ``new_name`` (rejects ``../``, separators, NUL, …).
        if _is_invalid_stem(sid_str):
            raise HTTPException(
                status_code=422,
                detail="scenarioId 不能为空、超过 128 字符、或包含 / \\ : * ? \" < > |",
            )
        case_id = sid_str
    elif visibility == "private":
        case_id = _next_default_scenario_id(target_dir)
    else:
        # Public uploads require admin-chosen naming (business rule, not
        # input validation) — keep at 400 to signal "policy requirement".
        raise HTTPException(status_code=400, detail="scenarioId is required")
    ext = ".json" if (file.filename or "").lower().endswith(".json") else ".yaml"
    # Avoid scenarioId collision (the loader uses scenarioId as the cache
    # key; identical keys shadow — see /copy and /publish for the same
    # collision policy).
    target = target_dir / f"{case_id}{ext}"
    if target.exists():
        n = 1
        while True:
            candidate = target_dir / f"{case_id}-{suffix_tag}-{n}{ext}"
            if not candidate.exists():
                target = candidate
                case_id = f"{case_id}-{suffix_tag}-{n}"
                break
            n += 1

    target.write_bytes(raw)
    # Patch scenarioId in the file to match the (possibly renamed) case_id
    # so the loader cache key doesn't collide with another file having
    # the same original scenarioId.
    try:
        cloned = json.loads(raw.decode("utf-8")) if ext == ".json" else yaml.safe_load(raw.decode("utf-8"))
        if isinstance(cloned, dict) and cloned.get("scenarioId") != case_id:
            cloned["scenarioId"] = case_id
            with target.open("w", encoding="utf-8") as f:
                if ext == ".json":
                    json.dump(cloned, f, ensure_ascii=False, indent=2)
                else:
                    yaml.safe_dump(cloned, f, allow_unicode=True, sort_keys=False)
    except Exception as e:  # noqa: BLE001
        logger.warning("upload: scenarioId patch failed for {}: {}", target, e)
    loader.invalidate()

    # Pull the fresh canonical summary from the loader so the response's
    # visibility/owner_id/audited match what /mine, /public will return
    # on their next read (consistent with /publish).
    fresh = _find_summary(case_id)
    if fresh is None:
        raise HTTPException(status_code=500, detail="upload lost the case")
    return _summary_out(fresh)


# ── save-as (Spec-2 §4.3 C7) ──────────────────────────────────
class SaveAsIn(BaseModel):
    new_name: str | None = None  # 可选 — 重命名
    visibility: str = "private"


@router.post("/{case_id:path}/save-as", response_model=dict)
async def save_as_case(
    case_id: Annotated[str, PathParam(min_length=1)],
    payload: SaveAsIn,
    user: CurrentUser,
) -> dict:
    """Save current case as a new private copy (optionally renamed)."""
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    # Access check — same rule as GET /{case_id}: private cases are
    # owner-only. Without this, save-as could be used to copy another
    # user's private case into one's own dir (data exfiltration).
    if summary.visibility == "private" and summary.owner_id != user.id:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")

    src = summary.file_path
    ext = src.suffix or ".yaml"
    new_id = (payload.new_name or "").strip() or f"{summary.case_id}-save"
    # Path-traversal fix: same stem validation as /rename and /copy.
    if _is_invalid_stem(new_id):
        raise HTTPException(
            status_code=422,
            detail="new_name 不能为空、超过 128 字符、或包含 / \\ : * ? \" < > |",
        )

    target_dir = settings.USERS_CASES_DIR / str(user.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    # save-as: if explicit new_name doesn't conflict, use it directly;
    # otherwise fall back to _next_copy_name which appends -copy-N.
    target = target_dir / f"{new_id}{ext}"
    if target.exists():
        target = _next_copy_name(target_dir, new_id, ext)
    shutil.copy2(src, target)

    # Patch scenarioId to match filename so loader cache key doesn't collide.
    _rewrite_scenario_id(target, target.stem, ext)

    loader.invalidate()
    return {"case_id": target.stem, "path": str(target)}


# ── patch (modify in place, write back yaml) ──────────────────
class CasePatchIn(BaseModel):
    payload: dict  # full case payload to write back


@router.patch("/{case_id:path}", response_model=CaseSummaryOut)
async def patch_case(
    case_id: Annotated[str, PathParam(min_length=1)],
    payload: CasePatchIn,
    user: CurrentUser,
) -> CaseSummaryOut:
    """Replace the case file content with the supplied payload."""
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")

    # Owner-only edit (Spec-2 §4.3: admin can edit any, user only own)
    _require_modify_access(user, summary)

    if not isinstance(payload.payload, dict):
        raise HTTPException(status_code=422, detail="payload must be object")
    if "scenarioId" not in payload.payload:
        raise HTTPException(status_code=422, detail="scenarioId is required")
    if str(payload.payload["scenarioId"]) != case_id:
        raise HTTPException(
            status_code=422,
            detail=f"scenarioId mismatch: {payload.payload['scenarioId']} != {case_id}",
        )

    ext = summary.file_path.suffix or ".yaml"
    _write_case_file(summary.file_path, payload.payload, ext)

    loader.invalidate()
    fresh = _find_summary(case_id)
    if fresh is None:
        raise HTTPException(status_code=500, detail="patch lost the case")
    # preserve owner-scoped flags from the summary-out helper (defaults ok)
    return _summary_out(fresh)


# ── rename (Spec-2 §4.3 C10) — change a case's scenarioId & filename ──
class RenameIn(BaseModel):
    new_case_id: str  # required, validated below


@router.post("/{case_id:path}/rename", response_model=CaseSummaryOut)
async def rename_case(
    case_id: Annotated[str, PathParam(min_length=1)],
    payload: RenameIn,
    user: CurrentUser,
) -> CaseSummaryOut:
    """Rename a case in place: rewrites the file's stem + ``scenarioId`` field.

    Permissions mirror ``/patch``:
    - private cases: owner only
    - public cases: admin only
    """
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    _require_modify_access(user, summary)

    new_stem = (payload.new_case_id or "").strip()
    if _is_invalid_stem(new_stem):
        raise HTTPException(
            status_code=422,
            detail="new_case_id 不能为空、超过 128 字符、或包含 / \\ : * ? \" < > |",
        )
    if new_stem == case_id:
        # No-op rename — return the current summary instead of erroring.
        return _summary_out(summary)

    ext = summary.file_path.suffix or ".yaml"
    target = summary.file_path.with_name(f"{new_stem}{ext}")
    if target.exists():
        raise HTTPException(
            status_code=409,
            detail=f"目标 scenarioId 已存在：{new_stem}",
        )

    # Rewrite the file content's scenarioId field to match the new stem
    # (the loader uses scenarioId as the cache key, so they must agree).
    try:
        raw = summary.file_path.read_text(encoding="utf-8")
        parsed = json.loads(raw) if ext == ".json" else yaml.safe_load(raw)
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=422,
                detail="case file top-level must be an object",
            )
        parsed["scenarioId"] = new_stem
        _write_case_file(target, parsed, ext)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("rename: rewrite failed for {} → {}: {}", summary.file_path, target, e)
        raise HTTPException(status_code=500, detail=f"rename rewrite failed: {e}") from e

    # Drop the old file (target now holds the rewritten content).
    try:
        summary.file_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("rename: unlink failed for {}: {}", summary.file_path, e)
        # The new file is already in place — log and continue; the cache
        # invalidation below will let the next scan drop the orphan stem
        # from the loader's view.

    # Migrate every user's favorite set from old case_id to new case_id so
    # favorited rows keep following the case under its new name.
    favorites.rename_item(case_id, new_stem)

    loader.invalidate()
    fresh = _find_summary(new_stem)
    if fresh is None:
        raise HTTPException(status_code=500, detail="rename lost the case")
    return _summary_out(fresh)


# ── publish (Spec-2 §4.3 C6) ──────────────────────────────────
@router.post(
    "/{case_id:path}/publish",
    response_model=CaseSummaryOut,
)
async def publish_case(
    case_id: Annotated[str, PathParam(min_length=1)],
    user: CurrentUser,
) -> CaseSummaryOut:
    """Move a private case file from ``data/users/<owner_id>/`` into
    ``data/public/`` so everyone in the org can see it. Only the case's
    owner may publish their own copies.

    Result: case becomes ``visibility=public``, ``audited=False`` until
    an admin marks it as audited separately. The original file is moved
    (not copied) — after publish the case no longer exists in the
    caller's private dir.
    """
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    if summary.visibility != "private":
        raise HTTPException(
            status_code=400,
            detail=f"case is already {summary.visibility}",
        )
    if summary.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="only the case owner may publish it",
        )

    src = summary.file_path
    public_dir = Path(settings.PUBLIC_CASES_DIR)
    public_dir.mkdir(parents=True, exist_ok=True)
    target = public_dir / src.name

    # Avoid clobbering an existing public file with the same name — append
    # a numeric suffix (mirrors the upload/copy collision logic).
    if target.exists():
        stem, ext = src.stem, src.suffix or ".yaml"
        n = 1
        while True:
            candidate = public_dir / f"{stem}-pub-{n}{ext}"
            if not candidate.exists():
                target = candidate
                break
            n += 1

    try:
        shutil.move(str(src), str(target))
    except OSError as e:
        logger.warning("publish: move failed ({} → {}): {}", src, target, e)
        raise HTTPException(status_code=500, detail=f"move failed: {e}") from e

    loader.invalidate()

    fresh = _find_summary(target.stem)
    if fresh is None:
        raise HTTPException(status_code=500, detail="publish lost the case")
    return _summary_out(fresh)


# ── delete (Spec-2 §4.3 C9) ───────────────────────────────────
@router.delete(
    "/{case_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case(
    case_id: Annotated[str, PathParam(min_length=1)],
    user: CurrentUser,
):
    """Remove a case file from disk.

    Permission rules:
    - private cases: only the owner may delete their own copies
    - public cases: admin-only
    Also removes the case_id from every user's favorites so future /mine
    or /public responses don't surface a phantom favorited reference.
    """
    summary = _find_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")

    if summary.visibility == "private" and summary.owner_id != user.id:
        raise HTTPException(status_code=403, detail="only owner can delete private case")
    if summary.visibility == "public" and not user.is_admin:
        raise HTTPException(status_code=403, detail="admin only can delete public case")

    try:
        summary.file_path.unlink()
    except FileNotFoundError:
        # Already gone — keep going so loader/favorites are still cleaned up.
        pass
    except OSError as e:
        logger.warning("delete: failed to remove {}: {}", summary.file_path, e)
        raise HTTPException(status_code=500, detail=f"unlink failed: {e}") from e

    # Drop the case_id from every user's favorite set.
    favorites.remove_item(case_id)

    loader.invalidate()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
