"""Per-dim public view models for the plate HTTP API (ADR 0002 §D-D5).

Each dim exposes a Pydantic view that:
- Drops sensitive fields (``Config.users[].password`` / ``AuthSession.token`` …)
  by **not declaring them**, not by masking (mask can leak length).
- Picks only fields that are safe for cross-system consumption.

Per-dim views are the redaction boundary. The handler never returns
``model_dump()`` on raw schema objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.resource import ResourceUnion
from gimbal_plate.schema.scenario import Config, Meta, Scenario
from gimbal_plate.schema.service_definition import ServiceDefinition


# ── SystemView ─────────────────────────────────────────────────────


class SystemView(BaseModel):
    """Public view of a system summary (A1/A2)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    service_count: int = Field(ge=0)
    endpoint_count: int = Field(ge=0)
    registered_at: datetime | None = None

    @classmethod
    def from_summary(cls, summary: dict[str, Any]) -> "SystemView":
        return cls(**summary)


class SystemDetailView(BaseModel):
    """Full system view — extended metadata for admin / dashboard consumption.

    Light :class:`SystemView` returns just aggregated counts; the ``/full``
    endpoint exposes every field the system dim owns (id, name,
    registered_at) plus derived totals for cross-system dashboards.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    service_count: int = Field(ge=0)
    endpoint_count: int = Field(ge=0)
    registered_at: datetime | None = None

    @classmethod
    def from_summary(cls, summary: dict[str, Any]) -> "SystemDetailView":
        return cls(**summary)


# ── ServiceView ────────────────────────────────────────────────────


class ServiceView(BaseModel):
    """Public view of a :class:`ServiceDefinition`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    title: str
    version: str
    description: str = ""
    endpoint_count: int = Field(ge=0, default=0)
    system: str | None = None  # derived from endpoint index

    @classmethod
    def from_definition(
        cls, sd: ServiceDefinition, *, endpoint_count: int = 0, system: str | None = None
    ) -> "ServiceView":
        return cls(
            id=sd.name,
            name=sd.name,
            title=sd.title,
            version=sd.version,
            description=sd.description,
            endpoint_count=endpoint_count,
            system=system,
        )


class ServiceDetailView(BaseModel):
    """Full :class:`ServiceDefinition` view.

    Mirrors :class:`ServiceView` but uses ``model_dump`` directly so any
    additional fields on the underlying ServiceDefinition (e.g. ``tags``,
    ``owner``, ``owners``) surface through the ``/full`` endpoint without
    needing a schema migration.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    title: str
    version: str
    description: str = ""
    endpoint_count: int = Field(ge=0, default=0)
    system: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_definition(
        cls, sd: ServiceDefinition, *, endpoint_count: int = 0, system: str | None = None
    ) -> "ServiceDetailView":
        dump = sd.model_dump(mode="json", exclude_none=True)
        # Pull well-known fields out, push anything else into ``extra``.
        known = {"name", "title", "version", "description"}
        extra = {k: v for k, v in dump.items() if k not in known}
        return cls(
            id=sd.name,
            name=sd.name,
            title=sd.title,
            version=sd.version,
            description=sd.description,
            endpoint_count=endpoint_count,
            system=system,
            extra=extra,
        )


# ── EndpointView ───────────────────────────────────────────────────


class EndpointView(BaseModel):
    """Public view of an :class:`EndpointSpec`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    system: str
    service: str
    name: str
    description: str = ""
    method: str
    path: str
    module: str = ""
    tags: list[str] = Field(default_factory=list)
    priority: int | None = None
    version: str = "1.0.0"
    updated_at: datetime | None = None

    @classmethod
    def from_spec(cls, ep: EndpointSpec) -> "EndpointView":
        api = ep.api
        return cls(
            id=ep.id,
            system=ep.system,
            service=ep.service,
            name=ep.name,
            description=ep.description,
            method=api.method,
            path=api.path,
            module=ep.metadata.module or "",
            tags=list(ep.metadata.tags or []),
            priority=ep.metadata.priority,
            version=ep.version,
            updated_at=ep.updated_at,
        )


class EndpointDetailView(BaseModel):
    """Full :class:`EndpointSpec` contract as JSON-serialisable dict.

    Re-uses Pydantic's ``model_dump`` for full-fidelity output (the spec is
    already serialisation-safe). Exposes ``api`` / ``request`` / ``responses``
    / ``metadata`` — including every :class:`IOFieldBinding` (name / path /
    required / ui_kind / source_kind / example / assertable).

    Light :class:`EndpointView` returns only id / method / path /
    description / module / tags. The ``/full`` endpoint surfaces the full
    :class:`EndpointSpec` for code generators and assertion builders that
    need the IOFieldBinding metadata.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    system: str
    service: str
    name: str
    description: str = ""
    api: dict[str, Any]
    request: dict[str, Any] | None = None
    responses: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any]
    version: str = "1.0.0"
    updated_at: datetime | None = None

    @classmethod
    def from_spec(cls, ep: EndpointSpec) -> "EndpointDetailView":
        return cls.model_validate(ep.model_dump(mode="json", exclude_none=True))


# ── ConfigView (with redaction) ────────────────────────────────────


class _AuthSessionSafeView(BaseModel):
    """Redacted :class:`AuthSession` — drops password / token / refresh_token."""

    model_config = ConfigDict(extra="forbid")

    url: str = ""
    username: str = ""
    token_type: str = "Bearer"
    is_authenticated: bool = False
    remaining_seconds: int | None = None

    @classmethod
    def from_auth(cls, auth: Any) -> "_AuthSessionSafeView":
        # ``is_authenticated`` / ``remaining_seconds`` are computed properties
        # on AuthSession; they are safe by construction.
        return cls(
            url=auth.url,
            username=auth.username,
            token_type=auth.token_type,
            is_authenticated=getattr(auth, "is_authenticated", False),
            remaining_seconds=getattr(auth, "remaining_seconds", None),
        )


class ConfigView(BaseModel):
    """Redacted :class:`Config` view.

    Sensitive fields (``users[].password``, ``users[].token``,
    ``users[].refresh_token``, ``users[].expires_at``) are dropped
    by *not* declaring them — they never appear in the response.
    """

    model_config = ConfigDict(extra="forbid")

    setup: list[dict[str, Any]] = Field(default_factory=list)
    teardown: list[dict[str, Any]] = Field(default_factory=list)
    services: dict[str, str] = Field(default_factory=dict)
    users: dict[str, _AuthSessionSafeView] = Field(default_factory=dict)
    time_policy: dict[str, Any] = Field(default_factory=dict)
    retry: dict[str, Any] | None = None
    vars: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: Config) -> "ConfigView":
        users = {
            tag: _AuthSessionSafeView.from_auth(auth)
            for tag, auth in (cfg.users or {}).items()
        }
        # Discriminated union → dict via Pydantic round-trip.
        time_policy: dict[str, Any] = (
            cfg.timePolicy.model_dump(mode="json")
            if cfg.timePolicy is not None
            else {}
        )
        retry: dict[str, Any] | None = (
            cfg.retry.model_dump(mode="json") if cfg.retry is not None else None
        )
        return cls(
            setup=[s.model_dump(mode="json", exclude_none=True) for s in cfg.setup],
            teardown=[
                s.model_dump(mode="json", exclude_none=True) for s in cfg.teardown
            ],
            services=dict(cfg.services),
            users=users,
            time_policy=time_policy,
            retry=retry,
            vars=dict(cfg.vars),
        )


# ── ConfigDetailView (full / unredacted) ────────────────────────────


class _AuthSessionFullView(BaseModel):
    """Full :class:`AuthSession` view — keeps every credential field.

    Companion to :class:`_AuthSessionSafeView`. Used by ``ConfigDetailView``
    on the ``/full`` endpoint, where the platform client (not an unauthenticated
    reader) controls whether to surface credentials to the operator.
    """

    model_config = ConfigDict(extra="ignore")

    url: str = ""
    username: str = ""
    password: str | None = None
    token: str | None = None
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    is_authenticated: bool = False
    remaining_seconds: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_auth(cls, auth: Any) -> "_AuthSessionFullView":
        dump = auth.model_dump(mode="json", exclude_none=True)
        known = {
            "url",
            "username",
            "password",
            "token",
            "refresh_token",
            "token_type",
            "expires_at",
        }
        extra = {k: v for k, v in dump.items() if k not in known}
        return cls(
            url=auth.url,
            username=auth.username,
            password=getattr(auth, "password", None),
            token=getattr(auth, "token", None),
            refresh_token=getattr(auth, "refresh_token", None),
            token_type=auth.token_type,
            expires_at=getattr(auth, "expires_at", None),
            is_authenticated=getattr(auth, "is_authenticated", False),
            remaining_seconds=getattr(auth, "remaining_seconds", None),
            extra=extra,
        )


class ConfigDetailView(BaseModel):
    """Full :class:`Config` view — every field, including sensitive credentials.

    The light :class:`ConfigView` is used by the ``list`` endpoint and the
    default ``detail`` endpoint to avoid leaking credentials to listings.
    This view is mounted only on ``/{id}/full`` — the platform client picks
    ``full`` explicitly when it needs to render the operator-facing config
    editor. By ADR 0002 boundary rules, **Plate does not decide what's
    sensitive** — it surfaces the raw data and the client decides.
    """

    model_config = ConfigDict(extra="ignore")

    setup: list[dict[str, Any]] = Field(default_factory=list)
    teardown: list[dict[str, Any]] = Field(default_factory=list)
    services: dict[str, str] = Field(default_factory=dict)
    users: dict[str, _AuthSessionFullView] = Field(default_factory=dict)
    time_policy: dict[str, Any] = Field(default_factory=dict)
    retry: dict[str, Any] | None = None
    vars: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: Config) -> "ConfigDetailView":
        users = {
            tag: _AuthSessionFullView.from_auth(auth)
            for tag, auth in (cfg.users or {}).items()
        }
        time_policy: dict[str, Any] = (
            cfg.timePolicy.model_dump(mode="json")
            if cfg.timePolicy is not None
            else {}
        )
        retry: dict[str, Any] | None = (
            cfg.retry.model_dump(mode="json") if cfg.retry is not None else None
        )
        dump = cfg.model_dump(mode="json", exclude_none=True)
        known = {
            "setup",
            "teardown",
            "services",
            "users",
            "timePolicy",
            "retry",
            "vars",
        }
        extra = {k: v for k, v in dump.items() if k not in known}
        return cls(
            setup=[s.model_dump(mode="json", exclude_none=True) for s in cfg.setup],
            teardown=[
                s.model_dump(mode="json", exclude_none=True) for s in cfg.teardown
            ],
            services=dict(cfg.services),
            users=users,
            time_policy=time_policy,
            retry=retry,
            vars=dict(cfg.vars),
            extra=extra,
        )


# ── MetaView ───────────────────────────────────────────────────────


class MetaView(BaseModel):
    """Full :class:`Meta` view — no sensitive fields."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    module: str
    priority: int
    author: str
    owner: str
    tags: list[str]
    version: str | None = None
    create_time: datetime | None = None
    expire: bool | None = None
    requirement_ref: list[dict[str, Any]] = Field(default_factory=list)
    system: list[str] = Field(default_factory=list)

    @classmethod
    def from_meta(cls, m: Meta) -> "MetaView":
        return cls(
            name=m.name,
            description=m.description,
            module=m.module,
            priority=m.priority,
            author=m.author,
            owner=m.owner,
            tags=list(m.tags),
            version=m.version,
            create_time=m.createTime,
            expire=m.expire,
            requirement_ref=[r.model_dump(mode="json") for r in (m.requirementRef or [])],
            system=list(m.system or []),
        )


class MetaDetailView(BaseModel):
    """Full :class:`Meta` view for the ``/full`` endpoint.

    Equivalent to :class:`MetaView` today (Meta has no redaction), but kept
    as a distinct class so future Meta fields surface through ``/full``
    without breaking the light contract.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    module: str
    priority: int
    author: str
    owner: str
    tags: list[str]
    version: str | None = None
    create_time: datetime | None = None
    expire: bool | None = None
    requirement_ref: list[dict[str, Any]] = Field(default_factory=list)
    system: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_meta(cls, m: Meta) -> "MetaDetailView":
        dump = m.model_dump(mode="json", exclude_none=True)
        known = {
            "name",
            "description",
            "module",
            "priority",
            "author",
            "owner",
            "tags",
            "version",
            "createTime",
            "expire",
            "requirementRef",
            "system",
        }
        extra = {k: v for k, v in dump.items() if k not in known}
        return cls(
            name=m.name,
            description=m.description,
            module=m.module,
            priority=m.priority,
            author=m.author,
            owner=m.owner,
            tags=list(m.tags),
            version=m.version,
            create_time=m.createTime,
            expire=m.expire,
            requirement_ref=[r.model_dump(mode="json") for r in (m.requirementRef or [])],
            system=list(m.system or []),
            extra=extra,
        )


# ── ResourceView ───────────────────────────────────────────────────


class ResourceView(BaseModel):
    """Public view of any :class:`ResourceUnion` member."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["mock", "file", "mock_ref", "file_ref"]

    @classmethod
    def from_resource(cls, r: ResourceUnion) -> "ResourceView":
        dump = r.model_dump(mode="json", exclude_none=True)
        return cls(name=dump["name"], kind=dump["kind"])


class ResourceDetailView(BaseModel):
    """Full :class:`ResourceUnion` view — every field including ``image`` /
    ``config`` / ``portMapping``.

    The light :class:`ResourceView` keeps only ``name`` / ``kind`` because
    resource payloads may carry credentialed ``config`` blobs and large
    ``portMapping`` tables that aren't useful for listing UIs. The
    ``/full`` endpoint exposes the whole :class:`ResourceUnion` payload so
    platform resource editors can render / diff the underlying spec.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    kind: Literal["mock", "file", "mock_ref", "file_ref"]
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_resource(cls, r: ResourceUnion) -> "ResourceDetailView":
        dump = r.model_dump(mode="json", exclude_none=True)
        kind = dump["kind"]
        # Preserve every field; ``name`` and ``kind`` are surfaced
        # explicitly so the platform can always rely on those top-level
        # keys without scanning ``extra``.
        known = {"name", "kind"}
        extra = {k: v for k, v in dump.items() if k not in known}
        return cls(name=dump["name"], kind=kind, extra=extra)


# ── ScenarioView ───────────────────────────────────────────────────


class ScenarioMinimalView(BaseModel):
    """Phase α minimal Scenario view (ADR 0002 §D-D6).

    Full detail view ships in Phase β.
    """

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    name: str
    systems: list[str] = Field(default_factory=list)

    @classmethod
    def minimal(cls, s: Scenario) -> "ScenarioMinimalView":
        return cls(
            scenario_id=s.scenarioId,
            name=s.meta.name,
            systems=list(s.meta.system or []),
        )


class ScenarioDetailView(BaseModel):
    """Full :class:`Scenario` view — every field including ``meta`` / ``config``
    / ``resource`` / ``steps``.

    The light :class:`ScenarioView` keeps only ``scenarioId`` / ``name`` /
    ``systems`` so list endpoints don't ship entire scenario payloads. The
    ``/full`` endpoint exposes the full :class:`Scenario` so platform
    scenario editors can render / diff the underlying spec.

    Note: by ADR 0002 §11, full Scenario CRUD lives on Platform backend; the
    ``/full`` endpoint here is for read-only inspection of registered
    scenarios (e.g. cached template previews).
    """

    model_config = ConfigDict(extra="ignore")

    scenario_id: str
    name: str
    systems: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_scenario(cls, s: Scenario) -> "ScenarioDetailView":
        dump = s.model_dump(mode="json", exclude_none=True)
        # ``scenarioId`` is the registry key; ``meta.name`` is the human label.
        known = {"scenarioId", "meta", "config", "resource", "steps"}
        extra = {k: v for k, v in dump.items() if k not in known}
        # The meta / config / resource / steps dicts each carry their own
        # structured payloads — keep them inside ``extra`` under their
        # original keys so the platform client sees the full contract.
        return cls(
            scenario_id=s.scenarioId,
            name=s.meta.name,
            systems=list(s.meta.system or []),
            extra={
                "meta": dump.get("meta", {}),
                "config": dump.get("config", {}),
                "resource": dump.get("resource", {}),
                "steps": dump.get("steps", []),
                **extra,
            },
        )


# Re-export with the names referenced by grammar.py
ScenarioView = ScenarioMinimalView  # alias used by grammar.py